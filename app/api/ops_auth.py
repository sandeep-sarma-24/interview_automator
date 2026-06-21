"""Operator authentication (M4 P0): a single shared OPS_TOKEN, no RBAC.

If SCRAPER_OPS_TOKEN is unset, every operator endpoint returns 503 (disabled by
default — never silently open). Constant-time comparison; the token is never logged.
"""
from __future__ import annotations

import secrets

from fastapi import Header, HTTPException

from app.config import get_settings


def get_operator(x_ops_token: str = Header(default="")) -> bool:
    token = get_settings().ops_token
    if not token:
        raise HTTPException(status_code=503,
                            detail="Operator endpoints disabled (SCRAPER_OPS_TOKEN not set)")
    if not x_ops_token or not secrets.compare_digest(x_ops_token, token):
        raise HTTPException(status_code=401, detail="Invalid operator token")
    return True
