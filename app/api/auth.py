"""Per-candidate auth & isolation.

Tailscale secures the network path; this enforces the tenant boundary inside
the app. Every authed request resolves to exactly one candidate via an opaque
token, and all data access is scoped to that candidate id.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import Header, HTTPException

from app.db.connection import connect
from app.repositories import candidates as cand_repo


def get_current_candidate(x_candidate_token: str = Header(default="")) -> Dict[str, Any]:
    if not x_candidate_token:
        raise HTTPException(status_code=401, detail="Missing X-Candidate-Token header")
    conn = connect()
    try:
        cand = cand_repo.get_candidate_by_token(conn, x_candidate_token)
    finally:
        conn.close()
    if not cand:
        raise HTTPException(status_code=401, detail="Invalid or inactive candidate token")
    return cand
