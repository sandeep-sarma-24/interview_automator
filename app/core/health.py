"""Health helpers shared by the worker heartbeat and the `healthcheck` CLI.

Kept dependency-light. The worker writes a heartbeat each cycle; the container
health check reads it (plus a DB liveness probe) so a *hung* worker is detected,
not merely a dead process.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import get_settings

_FMT = "%Y-%m-%dT%H:%M:%SZ"


def heartbeat_path() -> Path:
    return get_settings().base_dir / "worker.heartbeat"


def write_heartbeat() -> None:
    p = heartbeat_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(datetime.now(timezone.utc).strftime(_FMT), encoding="utf-8")


def heartbeat_age_seconds() -> Optional[float]:
    """Seconds since the last heartbeat, or None if there is no heartbeat yet."""
    p = heartbeat_path()
    if not p.exists():
        return None
    try:
        ts = datetime.strptime(p.read_text().strip(), _FMT).replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds()
    except (ValueError, OSError):
        # fall back to file mtime if the contents are unreadable
        return datetime.now(timezone.utc).timestamp() - p.stat().st_mtime


def db_ok() -> bool:
    """True if the SQLite database is reachable and answering."""
    from app.db.connection import connect
    try:
        conn = connect()
        try:
            conn.execute("SELECT 1").fetchone()
            return True
        finally:
            conn.close()
    except Exception:
        return False
