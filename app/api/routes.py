"""HTTP routes: onboarding wizard, company preferences, ranked feed, manual URL.

The dashboard/review UI (gates, approvals) arrives in M3; Sprint 1 exposes the
read model (ranked feed + application detail with signals) and the inputs needed
to make it useful (onboarding + preferences + manual discovery).
"""
from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api import schemas
from app.api.auth import get_current_candidate
from app.db.connection import transaction
from app.discovery import service as discovery_service
from app.repositories import candidates as cand_repo
from app.repositories import preferences as pref_repo
from app.repositories import scoring as score_repo
from app.scoring import service as scoring_service

router = APIRouter()


# ─────────────────────────────── health ───────────────────────────────────
@router.get("/health")
def health(response: Response) -> Dict[str, Any]:
    """Liveness + DB accessibility. 200 when the DB answers, 503 otherwise."""
    from app.core.health import db_ok
    if not db_ok():
        response.status_code = 503
        return {"status": "degraded", "db": "unreachable"}
    return {"status": "ok", "db": "ok"}


# ───────────────────────── onboarding wizard ──────────────────────────────
@router.post("/candidates", status_code=201)
def create_candidate(body: schemas.CandidateCreate) -> Dict[str, Any]:
    """Bootstrap a candidate. Returns the API token (store it; used for all calls)."""
    with transaction() as conn:
        try:
            cand = cand_repo.create_candidate(conn, body.display_name, body.email, body.consent)
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Candidate email already exists")
    return {"id": cand["id"], "display_name": cand["display_name"],
            "api_token": cand["api_token"]}


@router.post("/onboarding/profile", status_code=201)
def set_profile(spec: schemas.TrajectorySpec,
                cand: Dict[str, Any] = Depends(get_current_candidate)) -> Dict[str, Any]:
    with transaction() as conn:
        pv = cand_repo.create_profile_version(conn, cand["id"], spec.to_spec())
    return {"profile_version_id": pv["id"], "version_no": pv["version_no"]}


@router.post("/onboarding/resume", status_code=201)
def upsert_resume(body: schemas.ResumeUpsert,
                  cand: Dict[str, Any] = Depends(get_current_candidate)) -> Dict[str, Any]:
    with transaction() as conn:
        res = cand_repo.upsert_resume(conn, cand["id"], body.label, body.target_role,
                                      body.content_text)
    return res


@router.get("/me")
def me(cand: Dict[str, Any] = Depends(get_current_candidate)) -> Dict[str, Any]:
    with transaction() as conn:
        pv = cand_repo.get_current_profile(conn, cand["id"])
        resumes = cand_repo.list_resumes(conn, cand["id"])
    return {
        "id": cand["id"], "display_name": cand["display_name"], "email": cand["email"],
        "has_profile": pv is not None,
        "profile_version_no": pv["version_no"] if pv else None,
        "resumes": [{"label": r["label"], "target_role": r["target_role"]} for r in resumes],
    }


# ──────────────────────── company preferences ─────────────────────────────
@router.post("/preferences", status_code=201)
def set_preference(body: schemas.PreferenceSet,
                   cand: Dict[str, Any] = Depends(get_current_candidate)) -> Dict[str, Any]:
    try:
        with transaction() as conn:
            return pref_repo.set_preference(conn, cand["id"], body.company,
                                            body.preference, body.note)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/preferences")
def list_preferences(cand: Dict[str, Any] = Depends(get_current_candidate)) -> List[Dict[str, Any]]:
    with transaction() as conn:
        return pref_repo.list_preferences(conn, cand["id"])


# ──────────────────────────── ranked feed ─────────────────────────────────
@router.get("/feed")
def feed(cand: Dict[str, Any] = Depends(get_current_candidate),
         states: Optional[str] = Query(default="SHORTLISTED,SCORED"),
         search: Optional[str] = None,
         limit: int = Query(default=50, le=500),
         offset: int = Query(default=0, ge=0)) -> Dict[str, Any]:
    state_list = [s.strip() for s in states.split(",")] if states else None
    with transaction() as conn:
        items = score_repo.ranked_applications(conn, cand["id"], state_list, search, limit, offset)
        total = score_repo.count_applications(conn, cand["id"], state_list, search)
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/applications/{application_id}")
def application_detail(application_id: int,
                       cand: Dict[str, Any] = Depends(get_current_candidate)) -> Dict[str, Any]:
    with transaction() as conn:
        app = score_repo.get_application_for_candidate(conn, cand["id"], application_id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        app["signals"] = score_repo.get_signals(conn, application_id)
    return app


_VALID_VERDICTS = ("INTERESTED", "NOT_INTERESTED", "BOOKMARK", "WRONG_MATCH")


@router.post("/applications/{application_id}/verdict")
def set_verdict(application_id: int, body: schemas.VerdictRequest,
                cand: Dict[str, Any] = Depends(get_current_candidate)) -> Dict[str, Any]:
    """Human triage verdict (drives the state machine; note persisted)."""
    if body.verdict not in _VALID_VERDICTS:
        raise HTTPException(status_code=422, detail=f"verdict must be one of {_VALID_VERDICTS}")
    with transaction() as conn:
        result = score_repo.set_verdict(conn, cand["id"], application_id, body.verdict, body.note)
    if result is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return result


@router.get("/summary")
def summary(cand: Dict[str, Any] = Depends(get_current_candidate)) -> Dict[str, Any]:
    with transaction() as conn:
        return score_repo.summary_counts(conn, cand["id"])


@router.get("/diagnostics")
def diagnostics(cand: Dict[str, Any] = Depends(get_current_candidate)) -> Dict[str, Any]:
    from app.repositories import registry as reg
    with transaction() as conn:
        return reg.diagnostics(conn)


# ─────────────────────── manual discovery + actions ───────────────────────
@router.post("/jobs/manual", status_code=201)
def add_manual_job(body: schemas.ManualUrl,
                   cand: Dict[str, Any] = Depends(get_current_candidate)) -> Dict[str, Any]:
    """Paste a job URL (Reddit/X/referral) -> creates a job row to be scored."""
    return discovery_service.add_manual_url(body.url)


@router.post("/actions/score")
def trigger_score(cand: Dict[str, Any] = Depends(get_current_candidate)) -> Dict[str, Any]:
    """Convenience: score this candidate now. In production the worker does this."""
    return scoring_service.run_scoring(cand["id"])
