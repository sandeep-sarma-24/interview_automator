"""M4 P0 tests: ops auth, telemetry-backed ops endpoints, drop inspection,
and score explainability (operator + candidate)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.app import app
from app.config import get_settings

client = TestClient(app)
OPS = {"X-Ops-Token": "test-ops-token"}


def _candidate_with_jobs(email: str) -> dict:
    tok = client.post("/api/candidates",
                      json={"display_name": email, "email": email}).json()["api_token"]
    h = {"X-Candidate-Token": tok}
    client.post("/api/onboarding/profile", headers=h, json={
        "total_experience_months": 48, "core_skills": ["python", "backend"],
        "target_roles": ["ai product engineer", "backend engineer"],
        "avoid_roles": ["qa"], "target_domain_signals": ["llm", "ai"],
        "remote_required": True, "current_ctc": 2000000})
    from app.db.connection import transaction
    from app.repositories import jobs as J
    from app import util
    rows = [
        ("Datadog", "AI Product Engineer", "LLM AI python " * 40, 1, "Remote"),
        ("OnsiteCo", "Backend Engineer", "python backend " * 40, 0, "Pune"),  # NOT_REMOTE drop
    ]
    with transaction() as conn:
        for co, title, desc, remote, loc in rows:
            comp = J.get_or_create_company(conn, co)
            J.upsert_job(conn, comp["id"], util.sha256_hex(co, title, loc), {
                "source": "MANUAL", "discovery_method": "MANUAL", "title": title,
                "description_text": desc, "is_remote": remote, "location": loc,
                "signal_density": "RICH"})
    client.post("/api/actions/score", headers=h)
    return h


def test_ops_auth():
    # configured token: missing/wrong -> 401
    assert client.get("/api/ops/health").status_code == 401
    assert client.get("/api/ops/health", headers={"X-Ops-Token": "nope"}).status_code == 401
    # correct -> 200
    assert client.get("/api/ops/health", headers=OPS).status_code == 200


def test_ops_auth_disabled_when_unset():
    s = get_settings()
    saved = s.ops_token
    try:
        s.ops_token = None  # simulate unconfigured
        r = client.get("/api/ops/health", headers=OPS)
        assert r.status_code == 503
    finally:
        s.ops_token = saved


def test_ops_endpoints_shapes():
    _candidate_with_jobs("ops1@test")
    health = client.get("/api/ops/health", headers=OPS).json()
    assert health["db"] == "ok" and "worker" in health and "discovery" in health

    disc = client.get("/api/ops/discovery", headers=OPS).json()
    assert "sources" in disc and "rejection_reasons" in disc and "recent_runs" in disc

    wk = client.get("/api/ops/worker", headers=OPS).json()
    assert "backlogs" in wk and "recent_cycles" in wk

    calls = client.get("/api/ops/api-calls", headers=OPS).json()
    assert "by_service" in calls

    errs = client.get("/api/ops/errors", headers=OPS).json()
    assert "groups" in errs

    ev = client.get("/api/ops/events", headers=OPS, params={"category": "SCORING"}).json()
    assert ev["total"] >= 1  # score_complete emitted


def test_discovery_drops():
    _candidate_with_jobs("ops2@test")
    drops = client.get("/api/ops/discovery/drops", headers=OPS,
                       params={"reason": "NOT_REMOTE"}).json()
    assert drops["total"] >= 1
    item = drops["items"][0]
    assert item["reason"] == "NOT_REMOTE" and item["title"] and item["company"]


def test_explainability_candidate_and_operator():
    h = _candidate_with_jobs("ops3@test")
    feed = client.get("/api/feed", headers=h, params={"states": "SHORTLISTED"}).json()["items"]
    assert feed
    aid = feed[0]["application_id"]

    # candidate job-detail explain
    detail = client.get(f"/api/applications/{aid}", headers=h).json()
    ex = detail["explain"]
    assert set(ex["dimensions"]) == {"trajectory", "skills", "location", "experience", "salary"}
    assert ex["final_score"] is not None
    # weighted_sum + company_adjust ~= final_score (within rounding)
    assert abs((ex["weighted_sum"] + ex["company_adjust"]) - ex["final_score"]) < 0.01

    # operator explain (global, requires ops token)
    assert client.get(f"/api/ops/applications/{aid}/explain").status_code == 401
    opx = client.get(f"/api/ops/applications/{aid}/explain", headers=OPS).json()
    assert opx["explain"]["dimensions"]["trajectory"]["weight"] == 0.45
    assert "signals" in opx
