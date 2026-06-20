"""Sprint 1 smoke tests: onboarding -> discovery -> scoring -> feed, isolation,
graceful degradation (Ollama down), and the trajectory inversion that is the
whole point of the system.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.app import app

client = TestClient(app)


def _onboard(email: str) -> dict:
    tok = client.post("/candidates",
                      json={"display_name": email, "email": email}).json()["api_token"]
    h = {"X-Candidate-Token": tok}
    client.post("/onboarding/profile", headers=h, json={
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


def test_auth_required():
    assert client.get("/me").status_code == 401
    assert client.get("/feed", headers={"X-Candidate-Token": "bogus"}).status_code == 401


def test_trajectory_inversion_and_blocked():
    h = _onboard("mohit@test")
    client.post("/preferences", headers=h, json={"company": "Infosys", "preference": "BLOCKED"})
    _seed_jobs()
    report = client.post("/actions/score", headers=h).json()
    assert report["candidates"]["mohit@test"]["status"] == "ok"

    feed = client.get("/feed", headers=h, params={"states": "SHORTLISTED,SCORED"}).json()
    by_title = {r["title"]: r for r in feed}

    ai = by_title["AI Product Engineer"]      # Datadog (Infosys one is blocked)
    qa = by_title["Senior QA Automation Lead"]
    # The inversion: the AI leap outranks the higher-experience-match QA lead.
    assert ai["total_score"] > qa["total_score"]
    assert ai["trajectory_direction"] == "LEAP"
    assert ai["current_state"] == "SHORTLISTED"
    assert qa["trajectory_direction"] == "BACKWARD"

    # BLOCKED company is hard-filtered even though it's an AI leap.
    rejected = client.get("/feed", headers=h, params={"states": "REJECTED"}).json()
    assert any(r["company"].lower().startswith("infosys") for r in rejected)


def test_isolation():
    h1 = _onboard("a@test")
    _seed_jobs()
    client.post("/actions/score", headers=h1)
    feed = client.get("/feed", headers=h1).json()
    assert feed
    app_id = feed[0]["application_id"]

    h2 = _onboard("b@test")
    assert client.get(f"/applications/{app_id}", headers=h2).status_code == 404


def test_manual_discovery_and_dedup():
    h = _onboard("c@test")
    r1 = client.post("/jobs/manual", headers=h, json={"url": "http://localhost:9/x-role"}).json()
    r2 = client.post("/jobs/manual", headers=h, json={"url": "http://localhost:9/x-role?utm=1"}).json()
    assert r1["created"] == 1
    assert r2["created"] == 0 and r2["seen"] == 1  # canonical-URL dedup
