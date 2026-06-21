"""Read-model for the operator dashboard (M4 P0). Read-only queries over the
telemetry tables (ops_event, api_call, error_event) + existing discovery_run /
company_ats. No writes here."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app import util
from app.core import health as health_mod


def _since(hours: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _percentile(values: List[int], p: float) -> Optional[int]:
    if not values:
        return None
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return s[k]


# ─────────────────────────────── health ───────────────────────────────────
def health(conn: sqlite3.Connection) -> Dict[str, Any]:
    age = health_mod.heartbeat_age_seconds()
    worker_status = "RUNNING" if (age is not None and age < 4000) else "STALE"
    # Ollama: infer from the most recent OLLAMA api_call (no network call here).
    o = conn.execute("SELECT ok FROM api_call WHERE service='OLLAMA' ORDER BY ts DESC LIMIT 1").fetchone()
    ollama = "up" if (o and o["ok"] == 1) else ("down" if o else "unknown")
    disc = conn.execute(
        "SELECT SUM(CASE WHEN health_status='HEALTHY' THEN 1 ELSE 0 END) healthy, "
        "SUM(CASE WHEN health_status='DEGRADED' THEN 1 ELSE 0 END) degraded, "
        "SUM(CASE WHEN health_status='BROKEN' THEN 1 ELSE 0 END) broken FROM company_ats").fetchone()
    last_err = conn.execute("SELECT MAX(last_seen) FROM error_event").fetchone()[0]
    last_disc = conn.execute(
        "SELECT MAX(ts) FROM ops_event WHERE category='DISCOVERY' AND action='discovery_complete'").fetchone()[0]
    return {
        "db": "ok",
        "worker": {"status": worker_status, "heartbeat_age_s": round(age, 1) if age else None},
        "ollama": {"status": ollama, "mode": "fallback" if ollama != "up" else "ollama"},
        "discovery": {"healthy": disc["healthy"] or 0, "degraded": disc["degraded"] or 0,
                      "broken": disc["broken"] or 0},
        "totals": {
            "jobs": conn.execute("SELECT COUNT(*) FROM job").fetchone()[0],
            "companies_active": conn.execute("SELECT COUNT(*) FROM company_ats WHERE is_active=1").fetchone()[0],
            "companies_disabled": conn.execute("SELECT COUNT(*) FROM company_ats WHERE is_active=0").fetchone()[0],
        },
        "last_error_at": last_err, "last_discovery_at": last_disc,
    }


# ───────────────────────────── discovery ──────────────────────────────────
def discovery(conn: sqlite3.Connection) -> Dict[str, Any]:
    sources = []
    for src in ("GREENHOUSE", "LEVER", "EMAIL", "MANUAL"):
        ev = conn.execute(
            "SELECT ts, metadata_json FROM ops_event WHERE category='DISCOVERY' "
            "AND action='discovery_complete' AND source=? ORDER BY ts DESC LIMIT 1", (src,)).fetchone()
        meta = util.loads(ev["metadata_json"], {}) if ev else {}
        entry = {"source": src, "last_run": ev["ts"] if ev else None,
                 "jobs_new": meta.get("created", 0), "jobs_dropped": meta.get("dropped", 0)}
        if src in ("GREENHOUSE", "LEVER"):
            pid = conn.execute("SELECT id FROM ats_platform WHERE key=?", (src,)).fetchone()
            if pid:
                h = conn.execute(
                    "SELECT SUM(is_active) active, "
                    "SUM(CASE WHEN health_status='BROKEN' THEN 1 ELSE 0 END) broken "
                    "FROM company_ats WHERE ats_platform_id=?", (pid["id"],)).fetchone()
                entry["active_boards"] = h["active"] or 0
                entry["status"] = "ERROR" if (h["broken"] or 0) else "OK"
        else:
            entry["status"] = "OK" if entry["jobs_new"] or ev else "IDLE"
        sources.append(entry)

    reasons = {r["reason"]: r["n"] for r in conn.execute(
        "SELECT json_extract(metadata_json,'$.reason') reason, COUNT(*) n FROM ops_event "
        "WHERE category='DISCOVERY' AND action='DROP' GROUP BY reason")}
    failing = [dict(r) for r in conn.execute(
        "SELECT c.name AS company, ca.board_token AS token, ca.disabled_reason AS reason "
        "FROM company_ats ca JOIN company c ON c.id=ca.company_id "
        "WHERE ca.is_active=0 OR ca.health_status='BROKEN' LIMIT 50")]
    recent = [dict(r) for r in conn.execute(
        "SELECT c.name company, p.key platform, dr.status, dr.jobs_new, dr.jobs_dropped, "
        "dr.error, dr.started_at FROM discovery_run dr "
        "JOIN company_ats ca ON ca.id=dr.company_ats_id JOIN company c ON c.id=ca.company_id "
        "JOIN ats_platform p ON p.id=ca.ats_platform_id ORDER BY dr.started_at DESC LIMIT 20")]
    return {"sources": sources, "rejection_reasons": reasons,
            "failing_boards": failing, "recent_runs": recent}


def discovery_drops(conn: sqlite3.Connection, reason: Optional[str] = None,
                    source: Optional[str] = None, limit: int = 100,
                    offset: int = 0) -> Dict[str, Any]:
    where = "WHERE category='DISCOVERY' AND action='DROP'"
    params: List[Any] = []
    if reason:
        where += " AND json_extract(metadata_json,'$.reason')=?"
        params.append(reason)
    if source:
        where += " AND source=?"
        params.append(source)
    total = conn.execute(f"SELECT COUNT(*) FROM ops_event {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT ts, source, json_extract(metadata_json,'$.company') company, "
        f"json_extract(metadata_json,'$.title') title, "
        f"json_extract(metadata_json,'$.reason') reason FROM ops_event {where} "
        f"ORDER BY ts DESC LIMIT ? OFFSET ?", params + [limit, offset]).fetchall()
    return {"total": total, "limit": limit, "offset": offset, "items": [dict(r) for r in rows]}


# ─────────────────────────────── worker ───────────────────────────────────
def worker(conn: sqlite3.Connection) -> Dict[str, Any]:
    age = health_mod.heartbeat_age_seconds()
    cycles = [dict(r) for r in conn.execute(
        "SELECT ts, level, duration_ms, metadata_json FROM ops_event "
        "WHERE category='WORKER' AND action='cycle_complete' ORDER BY ts DESC LIMIT 20")]
    for c in cycles:
        c["metadata"] = util.loads(c.pop("metadata_json"), {})
    unscored = conn.execute(
        "SELECT COUNT(*) FROM job j WHERE NOT EXISTS "
        "(SELECT 1 FROM application a WHERE a.job_id=j.id)").fetchone()[0]
    by_state = {r["current_state"]: r["n"] for r in conn.execute(
        "SELECT current_state, COUNT(*) n FROM application WHERE deleted_at IS NULL "
        "GROUP BY current_state")}
    return {"status": "RUNNING" if (age is not None and age < 4000) else "STALE",
            "heartbeat_age_s": round(age, 1) if age else None,
            "recent_cycles": cycles, "backlogs": {"unscored_jobs": unscored, "by_state": by_state}}


# ─────────────────────────────── api calls ────────────────────────────────
def api_calls(conn: sqlite3.Connection, window_hours: int = 24) -> Dict[str, Any]:
    since = _since(window_hours)
    services = [r[0] for r in conn.execute(
        "SELECT DISTINCT service FROM api_call WHERE ts >= ?", (since,))]
    by_service = []
    for svc in services:
        rows = conn.execute(
            "SELECT ok, latency_ms, retry_count FROM api_call WHERE service=? AND ts >= ?",
            (svc, since)).fetchall()
        lat = [r["latency_ms"] for r in rows if r["latency_ms"] is not None]
        by_service.append({
            "service": svc, "calls": len(rows),
            "failures": sum(1 for r in rows if r["ok"] == 0),
            "retries": sum((r["retry_count"] or 0) for r in rows),
            "p50_ms": _percentile(lat, 50), "p95_ms": _percentile(lat, 95)})
    recent_failures = [dict(r) for r in conn.execute(
        "SELECT ts, service, host, path, status_code, error FROM api_call "
        "WHERE ok=0 AND ts >= ? ORDER BY ts DESC LIMIT 50", (since,))]
    return {"window_hours": window_hours, "by_service": by_service,
            "recent_failures": recent_failures}


# ─────────────────────────────── errors ───────────────────────────────────
def errors(conn: sqlite3.Connection, limit: int = 50) -> Dict[str, Any]:
    rows = conn.execute(
        "SELECT category, source, error_type, message, stack_trace, count, first_seen, last_seen "
        "FROM error_event ORDER BY last_seen DESC LIMIT ?", (limit,)).fetchall()
    return {"groups": [dict(r) for r in rows]}


# ─────────────────────────────── events ───────────────────────────────────
def events(conn: sqlite3.Connection, category: Optional[str] = None,
           level: Optional[str] = None, source: Optional[str] = None,
           since: Optional[str] = None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    where = "WHERE 1=1"
    params: List[Any] = []
    for col, val in (("category", category), ("level", level), ("source", source)):
        if val:
            where += f" AND {col}=?"
            params.append(val)
    if since:
        where += " AND ts >= ?"
        params.append(since)
    total = conn.execute(f"SELECT COUNT(*) FROM ops_event {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT ts, level, category, source, action, message, duration_ms, metadata_json "
        f"FROM ops_event {where} ORDER BY ts DESC LIMIT ? OFFSET ?",
        params + [limit, offset]).fetchall()
    return {"total": total, "limit": limit, "offset": offset, "items": [dict(r) for r in rows]}
