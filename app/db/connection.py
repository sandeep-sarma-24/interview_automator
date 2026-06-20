"""SQLite connection management.

Critical SQLite correctness settings, applied on every connection:
  * foreign_keys = ON   (OFF by default in SQLite — easy to forget, fatal)
  * journal_mode = WAL  (readers don't block the 24x7 writer)
  * busy_timeout        (wait instead of erroring under brief contention)
Row factory returns sqlite3.Row so callers get dict-like access.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from app.config import get_settings

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    settings = get_settings()
    path = db_path or settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


@contextmanager
def transaction(db_path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    """Connection that commits on success and rolls back on exception."""
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# Additive, idempotent column migrations for DBs created before a column existed.
# (CREATE TABLE IF NOT EXISTS won't add columns to a pre-existing table.)
_COLUMN_MIGRATIONS = [
    ("job", "role_class", "TEXT"),
    ("job", "content_key", "TEXT"),
    ("application", "verdict", "TEXT"),
    ("application", "verdict_note", "TEXT"),
    ("application", "verdict_at", "TEXT"),
]


def _ensure_column(conn: sqlite3.Connection, table: str, col: str, decl: str) -> None:
    existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    if col not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


def apply_schema(db_path: Optional[Path] = None) -> None:
    """Idempotently create all tables/indexes and apply additive migrations."""
    sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    with transaction(db_path) as conn:
        # Verify STRICT-table support (SQLite >= 3.37) for a clear error.
        ver = tuple(int(x) for x in sqlite3.sqlite_version.split("."))
        if ver < (3, 37, 0):
            raise RuntimeError(
                f"SQLite {sqlite3.sqlite_version} too old; STRICT tables need >= 3.37"
            )
        conn.executescript(sql)
        for table, col, decl in _COLUMN_MIGRATIONS:
            _ensure_column(conn, table, col, decl)
        # Index on a migrated column — created after the column is guaranteed.
        conn.execute("CREATE INDEX IF NOT EXISTS ix_job_content_key ON job (content_key)")
