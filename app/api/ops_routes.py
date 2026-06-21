"""Operator dashboard API (M4 P0). All endpoints require the OPS_TOKEN.

Mounted at /api/ops. Read-only views over telemetry + a score explainability
inspector. No candidate scoping (operator sees the whole system)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from pydantic import BaseModel

from app.api.ops_auth import get_operator
from app.db.connection import transaction
from app.repositories import ops as ops_repo
from app.repositories import roles as roles_repo
from app.repositories import scoring as score_repo
from app.roles.normalize import normalize_role
from app import util

router = APIRouter(prefix="/ops", dependencies=[Depends(get_operator)])


@router.get("/health")
def ops_health() -> Dict[str, Any]:
    with transaction() as conn:
        return ops_repo.health(conn)


@router.get("/discovery")
def ops_discovery() -> Dict[str, Any]:
    with transaction() as conn:
        return ops_repo.discovery(conn)


@router.get("/discovery/drops")
def ops_discovery_drops(reason: Optional[str] = None, source: Optional[str] = None,
                        limit: int = Query(100, le=500), offset: int = Query(0, ge=0)) -> Dict[str, Any]:
    with transaction() as conn:
        return ops_repo.discovery_drops(conn, reason, source, limit, offset)


@router.get("/worker")
def ops_worker() -> Dict[str, Any]:
    with transaction() as conn:
        return ops_repo.worker(conn)


@router.get("/api-calls")
def ops_api_calls(window_hours: int = Query(24, ge=1, le=720)) -> Dict[str, Any]:
    with transaction() as conn:
        return ops_repo.api_calls(conn, window_hours)


@router.get("/errors")
def ops_errors(limit: int = Query(50, le=200)) -> Dict[str, Any]:
    with transaction() as conn:
        return ops_repo.errors(conn, limit)


@router.get("/events")
def ops_events(category: Optional[str] = None, level: Optional[str] = None,
               source: Optional[str] = None, since: Optional[str] = None,
               limit: int = Query(100, le=500), offset: int = Query(0, ge=0)) -> Dict[str, Any]:
    with transaction() as conn:
        return ops_repo.events(conn, category, level, source, since, limit, offset)


@router.get("/applications/{application_id}/explain")
def ops_explain(application_id: int) -> Dict[str, Any]:
    with transaction() as conn:
        app = score_repo.get_application_global(conn, application_id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        explain = score_repo.score_explanation(app)
        signals = score_repo.get_signals(conn, application_id)
    return {
        "application_id": application_id, "company": app["company"], "title": app["title"],
        "candidate_id": app["candidate_id"], "current_state": app["current_state"],
        "reason_code": app["reason_code"], "explain": explain, "signals": signals,
    }


# ───────────────────── M4-P1 role canonicalization visibility ───────────────
@router.get("/roles/methods")
def ops_role_methods() -> Dict[str, Any]:
    with transaction() as conn:
        return roles_repo.method_distribution(conn)


@router.get("/roles/unresolved")
def ops_role_unresolved(limit: int = Query(100, le=500)) -> Dict[str, Any]:
    with transaction() as conn:
        return {"items": roles_repo.unresolved_titles(conn, limit)}


class AliasAdd(BaseModel):
    title: str                 # the raw/normalized title to teach
    canonical_key: str


@router.post("/roles/aliases", status_code=201)
def ops_add_alias(body: AliasAdd) -> Dict[str, Any]:
    """Operator teaches a LEARNED alias and invalidates that title's cache entry."""
    norm = normalize_role(body.title)
    with transaction() as conn:
        role = roles_repo.get_role_by_key(conn, body.canonical_key)
        if not role:
            raise HTTPException(status_code=404, detail="Unknown canonical_key")
        roles_repo.upsert_alias(conn, role["id"], body.title, norm,
                                source="LEARNED", created_by="OPS")
        roles_repo.cache_invalidate(conn, util.sha256_hex("role", norm))
    return {"normalized_alias": norm, "canonical_key": body.canonical_key, "source": "LEARNED"}
