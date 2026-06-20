"""Registry access: ATS platforms, per-company discovery bindings, run log."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app import util

# Default cadence per tier (minutes): Tier1 8h, Tier2 daily, Tier3 ~3 days.
TIER_INTERVAL = {"TIER1": 480, "TIER2": 1440, "TIER3": 4320}
MAX_FAILURES = 5  # consecutive hard failures -> auto-disable


# ───────────────────────────── ats_platform ───────────────────────────────
def upsert_platform(conn: sqlite3.Connection, key: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    row = conn.execute("SELECT * FROM ats_platform WHERE key=?", (key,)).fetchone()
    if row:
        return dict(row)
    conn.execute(
        "INSERT INTO ats_platform (key, display_name, discovery_kind, endpoint_template, "
        "supports_full_description, capability_tier_default, automation_difficulty, "
        "rate_limit_per_min, notes, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (key, spec["display_name"], spec["discovery_kind"], spec["endpoint_template"],
         1 if spec.get("supports_full_description") else 0,
         spec.get("capability_tier_default", "DISCOVERY_ONLY"),
         spec.get("automation_difficulty"), spec.get("rate_limit_per_min", 30),
         spec.get("notes"), util.now_iso()))
    return dict(conn.execute("SELECT * FROM ats_platform WHERE key=?", (key,)).fetchone())


def get_platform(conn: sqlite3.Connection, key: str) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM ats_platform WHERE key=?", (key,)).fetchone()
    return dict(row) if row else None


# ───────────────────────────── company_ats ────────────────────────────────
def upsert_company_ats(conn: sqlite3.Connection, company_id: int, platform_id: int,
                       board_token: str, tier: str, board_url: Optional[str] = None,
                       careers_url: Optional[str] = None,
                       priority_score: Optional[float] = None) -> Dict[str, Any]:
    interval = TIER_INTERVAL.get(tier, 1440)
    ts = util.now_iso()
    existing = conn.execute(
        "SELECT * FROM company_ats WHERE company_id=? AND ats_platform_id=? AND board_token=?",
        (company_id, platform_id, board_token)).fetchone()
    if existing:
        conn.execute(
            "UPDATE company_ats SET tier=?, schedule_interval_minutes=?, board_url=?, "
            "careers_url=?, priority_score=?, updated_at=? WHERE id=?",
            (tier, interval, board_url, careers_url, priority_score, ts, existing["id"]))
        return dict(conn.execute("SELECT * FROM company_ats WHERE id=?",
                                 (existing["id"],)).fetchone())
    cur = conn.execute(
        "INSERT INTO company_ats (company_id, ats_platform_id, board_token, board_url, "
        "careers_url, tier, priority_score, schedule_interval_minutes, next_check_at, "
        "created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (company_id, platform_id, board_token, board_url, careers_url, tier,
         priority_score, interval, ts, ts))  # next_check_at=now -> due immediately
    return dict(conn.execute("SELECT * FROM company_ats WHERE id=?", (cur.lastrowid,)).fetchone())


def due_company_ats(conn: sqlite3.Connection, platform_key: str,
                    limit: int = 1000) -> List[Dict[str, Any]]:
    now = util.now_iso()
    rows = conn.execute(
        "SELECT ca.*, c.name AS company_name, p.key AS platform_key, "
        "p.endpoint_template, p.supports_full_description "
        "FROM company_ats ca "
        "JOIN company c ON c.id=ca.company_id "
        "JOIN ats_platform p ON p.id=ca.ats_platform_id "
        "WHERE ca.is_active=1 AND p.key=? AND (ca.next_check_at IS NULL OR ca.next_check_at<=?) "
        "ORDER BY ca.priority_score DESC NULLS LAST, ca.next_check_at "
        "LIMIT ?", (platform_key, now, limit)).fetchall()
    return [dict(r) for r in rows]


def _next_check(interval_minutes: int, jitter_minutes: int = 0) -> str:
    when = datetime.now(timezone.utc) + timedelta(minutes=interval_minutes + jitter_minutes)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def record_success(conn: sqlite3.Connection, cats_id: int, interval_minutes: int,
                   changed: bool, etag: Optional[str], last_modified: Optional[str],
                   content_hash: Optional[str], jitter_minutes: int = 0) -> None:
    ts = util.now_iso()
    conn.execute(
        "UPDATE company_ats SET last_checked_at=?, last_success_at=?, next_check_at=?, "
        "etag=?, last_modified=?, board_content_hash=?, consecutive_failures=0, "
        "health_status='HEALTHY', last_change_at=CASE WHEN ? THEN ? ELSE last_change_at END, "
        "updated_at=? WHERE id=?",
        (ts, ts, _next_check(interval_minutes, jitter_minutes), etag, last_modified,
         content_hash, 1 if changed else 0, ts, ts, cats_id))


def record_not_modified(conn: sqlite3.Connection, cats_id: int, interval_minutes: int,
                        jitter_minutes: int = 0) -> None:
    ts = util.now_iso()
    conn.execute(
        "UPDATE company_ats SET last_checked_at=?, last_success_at=?, next_check_at=?, "
        "consecutive_failures=0, health_status='HEALTHY', updated_at=? WHERE id=?",
        (ts, ts, _next_check(interval_minutes, jitter_minutes), ts, cats_id))


def record_failure(conn: sqlite3.Connection, cats_id: int, interval_minutes: int,
                   reason: str) -> Dict[str, Any]:
    ts = util.now_iso()
    row = conn.execute("SELECT consecutive_failures FROM company_ats WHERE id=?",
                       (cats_id,)).fetchone()
    fails = (row["consecutive_failures"] if row else 0) + 1
    if fails >= MAX_FAILURES:
        conn.execute(
            "UPDATE company_ats SET consecutive_failures=?, health_status='BROKEN', "
            "is_active=0, disabled_reason=?, last_checked_at=?, updated_at=? WHERE id=?",
            (fails, f"auto-disabled after {fails} failures: {reason}", ts, ts, cats_id))
        return {"disabled": True, "failures": fails}
    # back off: push next check out by the interval
    conn.execute(
        "UPDATE company_ats SET consecutive_failures=?, health_status='DEGRADED', "
        "last_checked_at=?, next_check_at=?, updated_at=? WHERE id=?",
        (fails, ts, _next_check(interval_minutes), ts, cats_id))
    return {"disabled": False, "failures": fails}


def log_run(conn: sqlite3.Connection, cats_id: int, status: str, started_at: str,
            http_status: Optional[int] = None, jobs_seen: int = 0, jobs_new: int = 0,
            jobs_closed: int = 0, jobs_dropped: int = 0, nbytes: Optional[int] = None,
            error: Optional[str] = None) -> None:
    conn.execute(
        "INSERT INTO discovery_run (company_ats_id, started_at, finished_at, status, "
        "http_status, jobs_seen, jobs_new, jobs_closed, jobs_dropped, bytes, error) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (cats_id, started_at, util.now_iso(), status, http_status, jobs_seen, jobs_new,
         jobs_closed, jobs_dropped, nbytes, error))


def diagnostics(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Per-source discovery health for the Diagnostics screen (global, not per-candidate)."""
    sources: List[Dict[str, Any]] = []
    for key in ("GREENHOUSE", "LEVER"):
        prow = conn.execute("SELECT id FROM ats_platform WHERE key=?", (key,)).fetchone()
        if not prow:
            continue
        pid = prow["id"]
        agg = conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(is_active) AS active, "
            "SUM(CASE WHEN health_status='HEALTHY' THEN 1 ELSE 0 END) AS healthy, "
            "SUM(CASE WHEN health_status='DEGRADED' THEN 1 ELSE 0 END) AS degraded, "
            "SUM(CASE WHEN health_status='BROKEN' THEN 1 ELSE 0 END) AS broken, "
            "MAX(last_success_at) AS last_sync "
            "FROM company_ats WHERE ats_platform_id=?", (pid,)).fetchone()
        jobs = conn.execute("SELECT COUNT(*) FROM job WHERE source='API' AND source_ref=?",
                            (key,)).fetchone()[0]
        failed = conn.execute(
            "SELECT COUNT(*) FROM discovery_run dr JOIN company_ats ca ON ca.id=dr.company_ats_id "
            "WHERE ca.ats_platform_id=? AND dr.status='ERROR'", (pid,)).fetchone()[0]
        broken = agg["broken"] or 0
        degraded = agg["degraded"] or 0
        status = "ERROR" if broken > 0 else ("DEGRADED" if degraded > 0 else "OK")
        sources.append({
            "source": key, "type": "ATS", "active_boards": agg["active"] or 0,
            "healthy": agg["healthy"] or 0, "degraded": degraded, "broken": broken,
            "last_sync": agg["last_sync"], "jobs_discovered": jobs, "jobs_failed": failed,
            "status": status})

    for src in ("EMAIL", "MANUAL"):
        r = conn.execute("SELECT COUNT(*) AS n, MAX(last_seen_at) AS last FROM job WHERE source=?",
                         (src,)).fetchone()
        sources.append({
            "source": src, "type": src, "active_boards": None, "last_sync": r["last"],
            "jobs_discovered": r["n"], "jobs_failed": 0,
            "status": "OK" if r["n"] else "IDLE"})

    recent = [dict(r) for r in conn.execute(
        "SELECT c.name AS company, p.key AS platform, dr.status, dr.jobs_new, dr.jobs_dropped, "
        "dr.error, dr.started_at FROM discovery_run dr "
        "JOIN company_ats ca ON ca.id=dr.company_ats_id "
        "JOIN company c ON c.id=ca.company_id "
        "JOIN ats_platform p ON p.id=ca.ats_platform_id "
        "ORDER BY dr.started_at DESC LIMIT 20")]

    totals = {
        "companies_active": conn.execute("SELECT COUNT(*) FROM company_ats WHERE is_active=1").fetchone()[0],
        "companies_disabled": conn.execute("SELECT COUNT(*) FROM company_ats WHERE is_active=0").fetchone()[0],
        "jobs_total": conn.execute("SELECT COUNT(*) FROM job").fetchone()[0],
    }
    return {"sources": sources, "recent_runs": recent, "totals": totals}


def registry_summary(conn: sqlite3.Connection) -> Dict[str, Any]:
    rows = conn.execute(
        "SELECT p.key AS platform, ca.health_status, ca.is_active, COUNT(*) AS n "
        "FROM company_ats ca JOIN ats_platform p ON p.id=ca.ats_platform_id "
        "GROUP BY p.key, ca.health_status, ca.is_active").fetchall()
    return {"breakdown": [dict(r) for r in rows]}
