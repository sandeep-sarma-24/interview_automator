"""Sprint 1 smoke tests (under the /api prefix): onboarding -> discovery ->
scoring -> feed, isolation, graceful degradation, and the trajectory inversion.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.app import app

client = TestClient(app)


def _onboard(email: str) -> dict:
    tok = client.post("/api/candidates",
                      json={"display_name": email, "email": email}).json()["api_token"]
    h = {"X-Candidate-Token": tok}
    client.post("/api/onboarding/profile", headers=h, json={
        "total_experience_months": 48,
        "core_skills": ["python", "backend", "payments"],
        "acquiring_skills": ["llm", "ml", "ai product"],
        "target_roles": ["ai product engineer", "backend engineer"],
        "avoid_roles": ["qa", "manual testing", "sdet"],
        "target_domain_signals": ["llm", "rag", "ai product"],
        "cities": ["bangalore", "gurgaon"], "current_ctc": 2000000})
    return h


def _seed_jobs() -> None:
    from app.db.connection import transaction
    from app.repositories import jobs as J
    from app import util
    rows = [
        ("Datadog", "AI Product Engineer", "Build LLM AI products in Python. RAG agents. 2+ years. " * 6, 1, "Remote"),
        ("HashiCorp", "Backend Engineer", "Scalable Python backend APIs. 3-6 years. " * 6, 1, "Remote"),
        ("BigCo", "Senior QA Automation Lead", "Lead manual testing SDET QA. 6+ years quality assurance. " * 6, 0, "Bangalore"),
        ("Infosys", "AI Product Engineer", "LLM AI product. " * 8, 1, "Remote"),
    ]
    with transaction() as conn:
        for company, title, desc, remote, loc in rows:
            comp = J.get_or_create_company(conn, company)
            J.upsert_job(conn, comp["id"], util.sha256_hex(company, title, loc), {
                "source": "MANUAL", "discovery_method": "MANUAL", "title": title,
                "description_text": desc, "is_remote": remote, "location": loc,
                "signal_density": "RICH"})


def test_root_health():
    assert client.get("/health").status_code == 200          # Docker liveness at root
    assert client.get("/api/health").status_code == 200      # SPA-facing


def test_auth_required():
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/feed", headers={"X-Candidate-Token": "bogus"}).status_code == 401


def test_trajectory_inversion_and_blocked():
    h = _onboard("mohit@test")
    client.post("/api/preferences", headers=h, json={"company": "Infosys", "preference": "BLOCKED"})
    _seed_jobs()
    report = client.post("/api/actions/score", headers=h).json()
    assert report["candidates"]["mohit@test"]["status"] == "ok"

    feed = client.get("/api/feed", headers=h, params={"states": "SHORTLISTED,SCORED"}).json()
    assert "items" in feed and "total" in feed
    by_title = {r["title"]: r for r in feed["items"]}

    ai = by_title["AI Product Engineer"]      # Datadog (Infosys one is blocked)
    qa = by_title["Senior QA Automation Lead"]
    assert ai["total_score"] > qa["total_score"]
    assert ai["trajectory_direction"] == "LEAP"
    assert ai["current_state"] == "SHORTLISTED"
    assert qa["trajectory_direction"] == "BACKWARD"

    rejected = client.get("/api/feed", headers=h, params={"states": "REJECTED"}).json()["items"]
    assert any(r["company"].lower().startswith("infosys") for r in rejected)


def test_verdict_drives_state_and_summary():
    h = _onboard("verdict@test")
    _seed_jobs()
    client.post("/api/actions/score", headers=h)
    feed = client.get("/api/feed", headers=h, params={"states": "SHORTLISTED"}).json()["items"]
    assert feed
    aid = feed[0]["application_id"]

    # INTERESTED -> AWAITING_REVIEW, note persisted + returned
    r = client.post(f"/api/applications/{aid}/verdict", headers=h,
                    json={"verdict": "INTERESTED", "note": "great fit"}).json()
    assert r["current_state"] == "AWAITING_REVIEW" and r["verdict_note"] == "great fit"
    detail = client.get(f"/api/applications/{aid}", headers=h).json()
    assert detail["verdict"] == "INTERESTED" and detail["verdict_note"] == "great fit"

    # WRONG_MATCH -> REJECTED (calibration signal)
    other = client.get("/api/feed", headers=h, params={"states": "SHORTLISTED,SCORED"}).json()["items"]
    wid = next(x["application_id"] for x in other if x["application_id"] != aid)
    rw = client.post(f"/api/applications/{wid}/verdict", headers=h,
                     json={"verdict": "WRONG_MATCH"}).json()
    assert rw["current_state"] == "REJECTED"

    # bad verdict -> 422
    assert client.post(f"/api/applications/{aid}/verdict", headers=h,
                       json={"verdict": "NOPE"}).status_code == 422

    s = client.get("/api/summary", headers=h).json()
    assert s["interested"] >= 1 and s["wrong_match"] >= 1
    assert s["by_state"].get("AWAITING_REVIEW", 0) >= 1


def test_diagnostics_shape():
    h = _onboard("diag@test")
    d = client.get("/api/diagnostics", headers=h).json()
    assert "sources" in d and "totals" in d and "recent_runs" in d
    keys = {s["source"] for s in d["sources"]}
    assert {"GREENHOUSE", "LEVER", "EMAIL", "MANUAL"}.issubset(keys)


def test_feed_pagination():
    h = _onboard("page@test")
    _seed_jobs()
    client.post("/api/actions/score", headers=h)
    page = client.get("/api/feed", headers=h,
                      params={"states": "SHORTLISTED,SCORED", "limit": 1, "offset": 0}).json()
    assert page["limit"] == 1 and len(page["items"]) <= 1 and page["total"] >= 1


def test_isolation():
    h1 = _onboard("a@test")
    _seed_jobs()
    client.post("/api/actions/score", headers=h1)
    feed = client.get("/api/feed", headers=h1).json()["items"]
    assert feed
    app_id = feed[0]["application_id"]

    h2 = _onboard("b@test")
    assert client.get(f"/api/applications/{app_id}", headers=h2).status_code == 404
    assert client.post(f"/api/applications/{app_id}/verdict", headers=h2,
                       json={"verdict": "INTERESTED"}).status_code == 404


def test_manual_discovery_and_dedup():
    h = _onboard("c@test")
    r1 = client.post("/api/jobs/manual", headers=h, json={"url": "http://localhost:9/x-role"}).json()
    r2 = client.post("/api/jobs/manual", headers=h, json={"url": "http://localhost:9/x-role?utm=1"}).json()
    assert r1["created"] == 1
    assert r2["created"] == 0 and r2["seen"] == 1  # canonical-URL dedup
