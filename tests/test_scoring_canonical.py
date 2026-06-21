"""P1-C tests: canonical role matching replaces the trajectory input.
Verifies the required behavior, the version gate, fallback, and that ONLY
the trajectory dimension changed (skills/location/salary untouched)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.app import app
from app.db.connection import transaction
from app.roles.seed import seed_roles
from app.repositories import jobs as J, candidates as C
from app.scoring import rules
from app.scoring.service import run_scoring
from app import util

client = TestClient(app)
DESC = "Build and operate software with Python. Remote. 3-5 years experience. " * 4


def _backend_candidate():
    seed_roles(embed=False, reset=True)
    with transaction() as conn:
        cand = C.create_candidate(conn, "BE", "be@test")
        C.create_profile_version(conn, cand["id"], {
            "total_experience_months": 48,
            "core_skills_json": util.dumps(["python", "backend"]),
            "target_roles_json": util.dumps(["backend engineer"]),
            "acceptable_roles_json": util.dumps([]),       # deliberately NOT "software engineer"
            "avoid_roles_json": util.dumps(["program manager"]),
            "target_domain_signals_json": util.dumps([]),
            "remote_required": 0, "current_ctc": 2000000})
        for co, title in [("A", "Software Development Engineer"), ("B", "Backend Engineer"),
                          ("C", "AI Engineer"), ("D", "Program Manager")]:
            comp = J.get_or_create_company(conn, co)
            J.upsert_job(conn, comp["id"], util.sha256_hex(co, title), {
                "source": "MANUAL", "discovery_method": "MANUAL", "title": title,
                "description_text": DESC, "is_remote": 1, "location": "Remote",
                "signal_density": "RICH"})
    return cand["id"]


def test_required_behavior_canonical_forward_and_version():
    cid = _backend_candidate()
    run_scoring(cid)
    with transaction() as conn:
        rows = {r["title"]: dict(r) for r in conn.execute(
            "SELECT j.title, s.trajectory_direction, s.total_score, s.scoring_model_version, s.breakdown_json "
            "FROM application a JOIN job j ON j.id=a.job_id "
            "JOIN application_score s ON s.application_id=a.id AND s.is_current=1 "
            "WHERE a.candidate_id=?", (cid,))}

    sde = rows["Software Development Engineer"]
    # SDE -> software_engineer_generic -> related to backend -> FORWARD (the whole point)
    assert sde["trajectory_direction"] == "FORWARD"
    assert sde["scoring_model_version"].startswith("rules-v2-canonical")
    bd = util.loads(sde["breakdown_json"])
    assert bd["role_match"]["job_canonical"] == "software_engineer_generic"
    assert bd["role_match"]["method"] == "ALIAS"

    assert rows["Backend Engineer"]["trajectory_direction"] == "LEAP"      # exact primary target
    assert rows["Program Manager"]["trajectory_direction"] == "BACKWARD"   # avoid canonical
    # ranking reflects canonical relationship: SDE (forward) outranks PM (backward)
    assert rows["Software Development Engineer"]["total_score"] > rows["Program Manager"]["total_score"]


def test_v1_vs_v2_same_job_only_trajectory_changes():
    seed_roles(embed=False, reset=True)
    pv = {"total_experience_months": 48, "core_skills_json": util.dumps(["python", "backend"]),
          "target_roles_json": util.dumps(["backend engineer"]),
          "acceptable_roles_json": util.dumps([]), "avoid_roles_json": util.dumps(["program manager"]),
          "target_domain_signals_json": util.dumps([]), "remote_required": 0, "current_ctc": 2000000}
    profile = rules.build_profile(pv)
    job = {"title": "Software Development Engineer", "description_text": DESC,
           "is_remote": 1, "location": "Remote", "signal_density": "RICH"}
    role_ctx = {"primary": "backend_engineer", "targets": {"backend_engineer"},
                "avoids": {"program_project_manager"},
                "related": {"software_engineer_generic", "full_stack_engineer", "data_engineer"},
                "job_canonical": "software_engineer_generic", "method": "ALIAS"}

    v1, _ = rules.score_job(profile, job, None, 0.0, False, None)        # legacy keyword path
    v2, _ = rules.score_job(profile, job, None, 0.0, False, role_ctx)    # canonical path

    # trajectory: legacy MISSES (STALL); canonical resolves (FORWARD)
    assert v1["trajectory_direction"] == "STALL"
    assert v2["trajectory_direction"] == "FORWARD"
    assert v2["total_score"] > v1["total_score"]
    # ONLY trajectory changed — other dimensions identical, weights untouched:
    for dim in ("skill_score", "location_score", "experience_score", "salary_fit_score"):
        assert v1[dim] == v2[dim]
    assert v2["breakdown"]["weights"] == v1["breakdown"]["weights"]


def test_unresolved_title_falls_back_to_keyword():
    seed_roles(embed=False, reset=True)
    pv = {"total_experience_months": 48, "core_skills_json": util.dumps(["python"]),
          "target_roles_json": util.dumps(["backend engineer"]), "acceptable_roles_json": util.dumps([]),
          "avoid_roles_json": util.dumps([]), "target_domain_signals_json": util.dumps([]),
          "remote_required": 0, "current_ctc": 2000000}
    profile = rules.build_profile(pv)
    job = {"title": "Underwater Basket Weaver", "description_text": DESC, "is_remote": 1,
           "signal_density": "RICH"}
    # job_canonical None -> FALLBACK to legacy trajectory, method=FALLBACK
    res, _ = rules.score_job(profile, job, None, 0.0, False,
                             {"job_canonical": None, "primary": "backend_engineer",
                              "targets": {"backend_engineer"}, "avoids": set(), "related": set()})
    assert res["breakdown"]["role_match"]["method"] == "FALLBACK"
    assert res["trajectory_direction"] in ("STALL", "LATERAL")
