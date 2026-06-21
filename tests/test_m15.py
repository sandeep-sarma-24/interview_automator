"""M1.5 tests: role filter, ATS adapters, cross-source ATS-wins dedup, seeding.
All offline (no network) and deterministic.
"""
from __future__ import annotations

import json

from app.db.connection import transaction
from app.discovery import normalize
from app.discovery.ats.greenhouse import GreenhouseAdapter
from app.discovery.ats.lever import LeverAdapter
from app.discovery.ats.runner import _role_filter
from app.discovery.base import NormalizedJob
from app.discovery.role_filter import DROP, KEEP, SOFT_DROP, classify
from app.repositories import jobs as jobs_repo
from app.repositories import registry as reg


def test_role_classification_precedence():
    assert classify("Senior Backend Engineer") == KEEP
    assert classify("AI Product Engineer") == KEEP           # bare 'engineer' -> KEEP
    assert classify("Machine Learning Engineer") == KEEP
    assert classify("Sales Engineer") == SOFT_DROP           # soft phrase beats KEEP
    assert classify("Solutions Architect") == SOFT_DROP
    assert classify("Product Manager") == SOFT_DROP
    assert classify("Account Executive") == DROP
    assert classify("Recruiter") == DROP
    assert classify("VP of Engineering") == DROP             # DROP beats KEEP
    assert classify("Totally Unmatched Role") == SOFT_DROP   # safe default


def test_greenhouse_parse():
    payload = json.dumps({"jobs": [
        {"id": 7, "title": "Backend Engineer", "absolute_url": "https://x/7",
         "location": {"name": "Remote"}, "content": "<p>Python &amp; APIs</p>"},
    ]}).encode()
    jobs = GreenhouseAdapter().parse(payload, {"company_name": "Acme"})
    assert len(jobs) == 1
    j = jobs[0]
    assert j.external_job_id == "7" and j.source == "API" and j.source_ref == "GREENHOUSE"
    assert "Python & APIs" in j.description_text  # html unescaped + stripped


def test_lever_parse():
    payload = json.dumps([
        {"id": "abc", "text": "Platform Engineer", "hostedUrl": "https://j/abc",
         "categories": {"location": "Remote"}, "descriptionPlain": "Go backend",
         "createdAt": 1700000000000, "workplaceType": "remote"},
    ]).encode()
    jobs = LeverAdapter().parse(payload, {"company_name": "Acme"})
    assert jobs[0].source_ref == "LEVER" and jobs[0].is_remote == 1
    assert jobs[0].posted_at and jobs[0].posted_at.startswith("2023")


def test_role_filter_drops_nontech():
    jobs = [NormalizedJob(title=t, company_name="Acme", source="API", discovery_method="API")
            for t in ["Backend Engineer", "Account Executive", "Product Manager"]]
    kept, dropped = _role_filter(jobs)
    assert len(dropped) == 1 and len(kept) == 2
    classes = {j.title: j.role_class for j in kept}
    assert classes["Backend Engineer"] == KEEP
    assert classes["Product Manager"] == SOFT_DROP


def test_cross_source_ats_wins():
    company = "DedupCo"
    email = NormalizedJob(title="Backend Engineer", company_name=company, source="EMAIL",
                          discovery_method="EMAIL", source_ref="LINKEDIN",
                          source_url="https://linkedin.com/jobs/view/1", location="Remote")
    ats = NormalizedJob(title="Backend Engineer", company_name=company, source="API",
                        discovery_method="API", source_ref="GREENHOUSE",
                        source_url="https://boards.greenhouse.io/dedupco/1",
                        description_text="x" * 500, role_class="KEEP",
                        external_job_id="1", location="Remote")
    with transaction() as conn:
        assert normalize.persist_jobs(conn, [email])["created"] == 1
        res = normalize.persist_jobs(conn, [ats])
        assert res["created"] == 0 and res["merged"] == 1   # ATS won, no new row
        rows = conn.execute(
            "SELECT source, signal_density FROM job j JOIN company c ON c.id=j.company_id "
            "WHERE c.normalized_name LIKE '%dedupco%'").fetchall()
    assert len(rows) == 1 and rows[0]["source"] == "API" and rows[0]["signal_density"] == "RICH"


def test_seed_offline_creates_registry():
    from app.discovery.ats.seed import seed_companies
    report = seed_companies(verify=False)   # offline: no token probing
    assert report["total"] == 50 and report["active"] == 50
    with transaction() as conn:
        due_gh = reg.due_company_ats(conn, "GREENHOUSE", limit=100)
        assert len(due_gh) > 0
        assert reg.get_platform(conn, "LEVER") is not None
