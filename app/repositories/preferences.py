"""Per-candidate company preferences (PREFERRED / NEUTRAL / AVOID / BLOCKED)."""
from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from app import util
from app.repositories import jobs as jobs_repo

VALID = ("PREFERRED", "NEUTRAL", "AVOID", "BLOCKED")


def set_preference(conn: sqlite3.Connection, candidate_id: int, company_name: str,
                   preference: str, note: Optional[str] = None) -> Dict[str, Any]:
    if preference not in VALID:
        raise ValueError(f"preference must be one of {VALID}")
    company = jobs_repo.get_or_create_company(conn, company_name)
    ts = util.now_iso()
    conn.execute(
        "INSERT INTO company_preference (candidate_id, company_id, preference, note, created_at) "
        "VALUES (?,?,?,?,?) "
        "ON CONFLICT(candidate_id, company_id) DO UPDATE SET "
        "preference=excluded.preference, note=excluded.note, updated_at=?",
        (candidate_id, company["id"], preference, note, ts, ts))
    return {"company": company["name"], "preference": preference}


def get_preference(conn: sqlite3.Connection, candidate_id: int,
                   company_id: int) -> Optional[str]:
    row = conn.execute(
        "SELECT preference FROM company_preference WHERE candidate_id=? AND company_id=?",
        (candidate_id, company_id)).fetchone()
    return row["preference"] if row else None


def list_preferences(conn: sqlite3.Connection, candidate_id: int) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT c.name AS company, cp.preference, cp.note "
        "FROM company_preference cp JOIN company c ON c.id=cp.company_id "
        "WHERE cp.candidate_id=? ORDER BY cp.preference, c.name", (candidate_id,)).fetchall()
    return [dict(r) for r in rows]
