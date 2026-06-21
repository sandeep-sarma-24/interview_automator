"""Fail-safe observability telemetry (M4 P0).

Hard rules (by design):
  * NEVER raises into application workflows — every write is wrapped and swallowed.
  * Uses its OWN short-lived connection; never participates in a business
    transaction. A low busy-timeout (250 ms) means that even if it were called
    while a write transaction is open in the same thread, it fails fast and
    silently instead of deadlocking.
  * Records ALL outbound API calls; stores host + path only (NO query strings,
    tokens, or secrets).

Writers: record_event / record_api_call / record_error, plus the `timed`
context manager. Retention: prune_telemetry (30 days), run daily by the worker
and via `cli prune`.
"""
from __future__ import annotations

import logging
import sqlite3
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, Optional
from urllib.parse import urlsplit

from app import util
from app.config import get_settings

log = logging.getLogger("telemetry")

_RETENTION_DAYS = 30
_STACK_LIMIT = 6000
_MSG_LIMIT = 1000


def _conn() -> sqlite3.Connection:
    # Own connection, autocommit, fast-fail busy timeout. WAL is already set on
    # the database file, so concurrent reads are unaffected.
    c = sqlite3.connect(str(get_settings().db_path), timeout=0.25, isolation_level=None)
    c.execute("PRAGMA busy_timeout = 250")
    return c


# ─────────────────────────────── writers ──────────────────────────────────
def record_event(category: str, action: str, *, level: str = "INFO",
                 source: Optional[str] = None, message: Optional[str] = None,
                 entity_type: Optional[str] = None, entity_id: Optional[int] = None,
                 duration_ms: Optional[int] = None,
                 metadata: Optional[Dict[str, Any]] = None) -> None:
    try:
        c = _conn()
        try:
            c.execute(
                "INSERT INTO ops_event (ts, level, category, source, action, message, "
                "entity_type, entity_id, duration_ms, metadata_json) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (util.now_iso(), level, category, source, action,
                 (message or "")[:_MSG_LIMIT] or None, entity_type, entity_id,
                 duration_ms, util.dumps(metadata) if metadata else None))
        finally:
            c.close()
    except Exception:  # telemetry must never break the caller
        pass


def record_api_call(service: str, method: str, url: str, *, status_code: Optional[int],
                    latency_ms: int, ok: bool, retry_count: int = 0,
                    error: Optional[str] = None) -> None:
    """Record an outbound call. Only host + path are kept (query/secrets stripped)."""
    try:
        parts = urlsplit(url)
        host, path = parts.netloc, parts.path  # NO query, NO fragment, NO userinfo creds
        c = _conn()
        try:
            c.execute(
                "INSERT INTO api_call (ts, service, method, host, path, status_code, ok, "
                "latency_ms, retry_count, error) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (util.now_iso(), service, method, host, path, status_code,
                 1 if ok else 0, latency_ms, retry_count,
                 (error or "")[:_MSG_LIMIT] or None))
        finally:
            c.close()
    except Exception:
        pass


def record_error(category: str, source: Optional[str], exc: BaseException, *,
                 context: Optional[Dict[str, Any]] = None) -> None:
    """Upsert a deduplicated error (grouped by category/type/message/top-frame)."""
    try:
        etype = type(exc).__name__
        msg = str(exc)[:_MSG_LIMIT]
        stack = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[:_STACK_LIMIT]
        top = _top_frame(exc)
        ehash = util.sha256_hex(category, etype, msg.split("\n")[0], top)
        ts = util.now_iso()
        c = _conn()
        try:
            c.execute(
                "INSERT INTO error_event (error_hash, category, source, error_type, message, "
                "stack_trace, context_json, count, first_seen, last_seen) "
                "VALUES (?,?,?,?,?,?,?,1,?,?) "
                "ON CONFLICT(error_hash) DO UPDATE SET count=count+1, last_seen=excluded.last_seen, "
                "stack_trace=excluded.stack_trace, message=excluded.message, "
                "context_json=excluded.context_json",
                (ehash, category, source, etype, msg, stack,
                 util.dumps(context) if context else None, ts, ts))
        finally:
            c.close()
    except Exception:
        pass


def _top_frame(exc: BaseException) -> str:
    tb = exc.__traceback__
    last = ""
    while tb is not None:
        last = f"{tb.tb_frame.f_code.co_filename}:{tb.tb_lineno}"
        tb = tb.tb_next
    return last


@contextmanager
def timed(category: str, action: str, *, source: Optional[str] = None,
          metadata: Optional[Dict[str, Any]] = None) -> Iterator[None]:
    """Measure duration and emit an event; record_error + ERROR event on failure (re-raises)."""
    start = time.monotonic()
    try:
        yield
    except Exception as e:
        record_error(category, source, e, context=metadata)
        record_event(category, action, level="ERROR", source=source,
                     duration_ms=int((time.monotonic() - start) * 1000),
                     message=type(e).__name__, metadata=metadata)
        raise
    else:
        record_event(category, action, source=source,
                     duration_ms=int((time.monotonic() - start) * 1000), metadata=metadata)


# ──────────────────────────────── retention ───────────────────────────────
def prune_telemetry(days: int = _RETENTION_DAYS) -> Dict[str, int]:
    """Delete telemetry older than `days`. Safe to run anytime (own connection)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    deleted = {"ops_event": 0, "api_call": 0, "error_event": 0}
    try:
        c = _conn()
        try:
            deleted["ops_event"] = c.execute("DELETE FROM ops_event WHERE ts < ?", (cutoff,)).rowcount
            deleted["api_call"] = c.execute("DELETE FROM api_call WHERE ts < ?", (cutoff,)).rowcount
            deleted["error_event"] = c.execute(
                "DELETE FROM error_event WHERE last_seen < ?", (cutoff,)).rowcount
        finally:
            c.close()
    except Exception as e:
        record_error("SYSTEM", "prune", e)
        return deleted
    record_event("SYSTEM", "prune", source="SYSTEM",
                 message=f"pruned >{days}d", metadata=deleted)
    return deleted
