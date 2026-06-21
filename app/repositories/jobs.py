"""Company and job persistence (companies are shared; jobs are global)."""
from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from app import util


def get_or_create_company(conn: sqlite3.Connection, name: str,
                          domain: Optional[str] = None) -> Dict[str, Any]:
    norm = util.normalize_company_name(name) or util.normalize_text(name) or "unknown"
    row = conn.execute("SELECT * FROM company WHERE normalized_name=?", (norm,)).fetchone()
    if row:
        return dict(row)
    cur = conn.execute(
        "INSERT INTO company (name, normalized_name, domain, created_at) VALUES (?,?,?,?)",
        (name.strip() or norm, norm, domain, util.now_iso()))
    return dict(conn.execute("SELECT * FROM company WHERE id=?", (cur.lastrowid,)).fetchone())


def find_company(conn: sqlite3.Connection, name: str) -> Optional[Dict[str, Any]]:
    norm = util.normalize_company_name(name) or util.normalize_text(name)
    row = conn.execute("SELECT * FROM company WHERE normalized_name=?", (norm,)).fetchone()
    return dict(row) if row else None


# Fields a discovery source may provide for a job.
_JOB_FIELDS = (
    "source", "discovery_method", "source_ref", "source_url", "external_job_id",
    "title", "description_text", "location", "is_remote", "min_experience_months",
    "max_experience_months", "salary_text", "salary_min", "salary_max", "currency",
    "signal_density", "raw_payload_json", "posted_at", "role_class", "content_key",
)


def upsert_job(conn: sqlite3.Connection, company_id: int, dedup_hash: str,
               data: Dict[str, Any]) -> Dict[str, Any]:
    """Insert a job; if the dedup_hash already exists, just refresh last_seen_at.

    Returns the job row plus a transient ``_created`` flag.
    """
    ts = util.now_iso()
    existing = conn.execute("SELECT * FROM job WHERE dedup_hash=?", (dedup_hash,)).fetchone()
    if existing:
        conn.execute("UPDATE job SET last_seen_at=? WHERE id=?", (ts, existing["id"]))
        d = dict(existing)
        d["_created"] = False
        return d

    cols = ["company_id", "dedup_hash"]
    vals: List[Any] = [company_id, dedup_hash]
    for f in _JOB_FIELDS:
        cols.append(f)
        vals.append(data.get(f))
    cols += ["discovered_at", "last_seen_at"]
    vals += [ts, ts]
    placeholders = ",".join("?" for _ in cols)
    cur = conn.execute(f"INSERT INTO job ({','.join(cols)}) VALUES ({placeholders})", vals)
    d = dict(conn.execute("SELECT * FROM job WHERE id=?", (cur.lastrowid,)).fetchone())
    d["_created"] = True
    return d


def get_job(conn: sqlite3.Connection, job_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM job WHERE id=?", (job_id,)).fetchone()
    return dict(row) if row else None


def get_by_dedup_hash(conn: sqlite3.Connection, dedup_hash: str) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM job WHERE dedup_hash=?", (dedup_hash,)).fetchone()
    return dict(row) if row else None


def bump_last_seen(conn: sqlite3.Connection, job_id: int, ts: str) -> None:
    conn.execute("UPDATE job SET last_seen_at=? WHERE id=?", (ts, job_id))


def find_cross_source_match(conn: sqlite3.Connection, content_key: str,
                            incoming_is_api: bool) -> Optional[Dict[str, Any]]:
    """Find a same-content job from the *other* source class, for ATS-wins merge.

    incoming API   -> look for an existing non-API row (to upgrade to ATS).
    incoming email -> look for an existing API row (to defer to; ATS already wins).
    Same-source duplicates are intentionally NOT matched here (distinct reqs share
    a content_key but differ by URL/dedup_hash).
    """
    if not content_key:
        return None
    if incoming_is_api:
        row = conn.execute(
            "SELECT * FROM job WHERE content_key=? AND source!='API' LIMIT 1",
            (content_key,)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM job WHERE content_key=? AND source='API' LIMIT 1",
            (content_key,)).fetchone()
    return dict(row) if row else None


def upgrade_to_ats(conn: sqlite3.Connection, job_id: int, dedup_hash: str,
                   data: Dict[str, Any], ts: str) -> None:
    """ATS record wins: replace a previously email/manual-discovered row in place."""
    conn.execute(
        "UPDATE job SET source='API', discovery_method='API', source_ref=?, source_url=?, "
        "external_job_id=?, title=?, description_text=COALESCE(?, description_text), "
        "location=COALESCE(?, location), is_remote=COALESCE(?, is_remote), "
        "signal_density='RICH', role_class=?, dedup_hash=?, last_seen_at=? WHERE id=?",
        (data.get("source_ref"), data.get("source_url"), data.get("external_job_id"),
         data.get("title"), data.get("description_text"), data.get("location"),
         data.get("is_remote"), data.get("role_class"), dedup_hash, ts, job_id))


def jobs_for_company_platform(conn: sqlite3.Connection, company_id: int,
                              source_ref: str) -> List[Dict[str, Any]]:
    """Active jobs previously discovered for a company via a given ATS platform
    (used for closure detection)."""
    rows = conn.execute(
        "SELECT id, external_job_id, last_seen_at, ingestion_status FROM job "
        "WHERE company_id=? AND source='API' AND source_ref=? "
        "AND ingestion_status NOT IN ('CLOSED','ARCHIVED')",
        (company_id, source_ref)).fetchall()
    return [dict(r) for r in rows]


def mark_closed(conn: sqlite3.Connection, job_ids: List[int]) -> int:
    if not job_ids:
        return 0
    qs = ",".join("?" for _ in job_ids)
    conn.execute(f"UPDATE job SET ingestion_status='CLOSED' WHERE id IN ({qs})", job_ids)
    return len(job_ids)


def jobs_without_application(conn: sqlite3.Connection, candidate_id: int,
                             limit: int = 500) -> List[Dict[str, Any]]:
    """Jobs that have no application row for this candidate yet (need scoring)."""
    rows = conn.execute(
        "SELECT j.*, c.name AS company_name FROM job j "
        "JOIN company c ON c.id=j.company_id "
        "LEFT JOIN application a ON a.job_id=j.id AND a.candidate_id=? "
        "WHERE a.id IS NULL AND j.ingestion_status NOT IN ('ARCHIVED','CLOSED') "
        "ORDER BY j.discovered_at DESC LIMIT ?",
        (candidate_id, limit)).fetchall()
    return [dict(r) for r in rows]


def get_embedding(conn: sqlite3.Connection, job_id: int, model: str) -> Optional[List[float]]:
    row = conn.execute("SELECT vector_json FROM job_embedding WHERE job_id=? AND model=?",
                       (job_id, model)).fetchone()
    return util.loads(row["vector_json"]) if row else None


def save_embedding(conn: sqlite3.Connection, job_id: int, model: str,
                   vector: List[float]) -> None:
    conn.execute(
        "INSERT INTO job_embedding (job_id, model, vector_json, created_at) VALUES (?,?,?,?) "
        "ON CONFLICT(job_id, model) DO UPDATE SET vector_json=excluded.vector_json",
        (job_id, model, util.dumps(vector), util.now_iso()))
