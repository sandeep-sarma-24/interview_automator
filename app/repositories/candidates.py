"""Candidate, profile-version (trajectory spec) and resume access.

All reads/writes are explicitly candidate-scoped by callers; nothing here
crosses the tenant boundary implicitly.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from app import util


# ─────────────────────────────── candidate ────────────────────────────────
def create_candidate(conn: sqlite3.Connection, display_name: str, email: str,
                     consent: bool = True) -> Dict[str, Any]:
    token = util.new_token()
    ts = util.now_iso()
    cur = conn.execute(
        "INSERT INTO candidate (display_name, email, api_token, status, "
        "consent_granted_at, created_at) VALUES (?,?,?,?,?,?)",
        (display_name, email, token, "ACTIVE", ts if consent else None, ts),
    )
    return get_candidate(conn, cur.lastrowid)  # type: ignore[arg-type]


def get_candidate(conn: sqlite3.Connection, candidate_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM candidate WHERE id=? AND deleted_at IS NULL",
                       (candidate_id,)).fetchone()
    return dict(row) if row else None


def get_candidate_by_token(conn: sqlite3.Connection, token: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM candidate WHERE api_token=? AND deleted_at IS NULL AND status='ACTIVE'",
        (token,)).fetchone()
    return dict(row) if row else None


def list_candidates(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM candidate WHERE deleted_at IS NULL ORDER BY id").fetchall()
    return [dict(r) for r in rows]


# ───────────────────────── profile version (trajectory) ───────────────────
_PROFILE_FIELDS = (
    "total_experience_months", "seniority_label", "core_skills_json",
    "acquiring_skills_json", "target_roles_json", "acceptable_roles_json",
    "avoid_roles_json", "target_domain_signals_json", "location_prefs_json",
    "remote_required", "current_ctc", "salary_min_multiplier",
    "salary_target_multiplier", "salary_stretch_multiplier", "weights_json",
)


def create_profile_version(conn: sqlite3.Connection, candidate_id: int,
                           spec: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new *current* profile version, retiring any previous current one."""
    ts = util.now_iso()
    row = conn.execute(
        "SELECT COALESCE(MAX(version_no),0) AS v FROM candidate_profile_version "
        "WHERE candidate_id=?", (candidate_id,)).fetchone()
    next_no = int(row["v"]) + 1

    conn.execute("UPDATE candidate_profile_version SET is_current=0 "
                 "WHERE candidate_id=? AND is_current=1", (candidate_id,))

    values = [candidate_id, next_no]
    cols = ["candidate_id", "version_no"]
    for f in _PROFILE_FIELDS:
        # Omit absent fields so the schema's NOT NULL defaults apply.
        if spec.get(f) is not None:
            cols.append(f)
            values.append(spec[f])
    cols += ["is_current", "effective_from", "created_at"]
    values += [1, ts, ts]
    placeholders = ",".join("?" for _ in cols)
    cur = conn.execute(
        f"INSERT INTO candidate_profile_version ({','.join(cols)}) VALUES ({placeholders})",
        values)
    return get_profile_version(conn, cur.lastrowid)  # type: ignore[arg-type]


def get_profile_version(conn: sqlite3.Connection, pv_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM candidate_profile_version WHERE id=?", (pv_id,)).fetchone()
    return dict(row) if row else None


def get_current_profile(conn: sqlite3.Connection, candidate_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM candidate_profile_version WHERE candidate_id=? AND is_current=1",
        (candidate_id,)).fetchone()
    return dict(row) if row else None


def set_target_embedding(conn: sqlite3.Connection, pv_id: int, vector: List[float],
                         model: str) -> None:
    conn.execute(
        "UPDATE candidate_profile_version SET target_embedding_json=?, "
        "target_embedding_model=? WHERE id=?",
        (util.dumps(vector), model, pv_id))


# ───────────────────────────────── resume ─────────────────────────────────
def upsert_resume(conn: sqlite3.Connection, candidate_id: int, label: str,
                  target_role: Optional[str], content_text: Optional[str],
                  file_path: Optional[str] = None) -> Dict[str, Any]:
    ts = util.now_iso()
    row = conn.execute(
        "SELECT id FROM resume WHERE candidate_id=? AND label=?",
        (candidate_id, label)).fetchone()
    if row:
        resume_id = row["id"]
        conn.execute("UPDATE resume SET target_role=? WHERE id=?", (target_role, resume_id))
    else:
        cur = conn.execute(
            "INSERT INTO resume (candidate_id, label, target_role, created_at) VALUES (?,?,?,?)",
            (candidate_id, label, target_role, ts))
        resume_id = cur.lastrowid

    vrow = conn.execute(
        "SELECT COALESCE(MAX(version_no),0) AS v FROM resume_version WHERE resume_id=?",
        (resume_id,)).fetchone()
    next_no = int(vrow["v"]) + 1
    conn.execute("UPDATE resume_version SET is_current=0 WHERE resume_id=? AND is_current=1",
                 (resume_id,))
    conn.execute(
        "INSERT INTO resume_version (resume_id, version_no, content_text, content_sha256, "
        "file_path, is_current, created_at) VALUES (?,?,?,?,?,1,?)",
        (resume_id, next_no, content_text, util.sha256_hex(content_text or ""), file_path, ts))
    return {"resume_id": resume_id, "label": label, "version_no": next_no}


def list_resumes(conn: sqlite3.Connection, candidate_id: int) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT r.id, r.label, r.target_role, rv.version_no, rv.content_text "
        "FROM resume r JOIN resume_version rv ON rv.resume_id=r.id AND rv.is_current=1 "
        "WHERE r.candidate_id=? ORDER BY r.label", (candidate_id,)).fetchall()
    return [dict(r) for r in rows]
