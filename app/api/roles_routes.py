"""Canonical role API (M4-P1, candidate-authenticated).

Read-only taxonomy + a resolver debug endpoint. Not consumed by scoring or
onboarding in this slice.
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from app.api.auth import get_current_candidate
from app.db.connection import transaction
from app.repositories import roles as roles_repo

router = APIRouter(prefix="/roles")


@router.get("")
def list_roles(_cand: Dict[str, Any] = Depends(get_current_candidate)) -> List[Dict[str, Any]]:
    with transaction() as conn:
        return roles_repo.list_canonical_roles(conn)


@router.get("/resolve")
def resolve_role(title: str = Query(..., min_length=1),
                 _cand: Dict[str, Any] = Depends(get_current_candidate)) -> Dict[str, Any]:
    """Debug: resolve a title to its canonical role (alias -> embedding -> UNRESOLVED)."""
    from app.roles.resolver import RoleResolver
    return {"title": title, **RoleResolver().resolve(title)}
