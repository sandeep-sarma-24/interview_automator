"""Nightly SQLite backup using the online backup API (safe while WAL is active).

The DB holds irreplaceable application history + PII; the architecture review
flagged 'no backup' as a critical gap, so this ships in M0. Evidence/resume
files live on disk and should be backed up by the same off-laptop job (see
README) — this covers the database itself.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from app.config import get_settings


def run_backup(keep: int = 14) -> Dict[str, object]:
    settings = get_settings()
    settings.ensure_dirs()
    if not settings.db_path.exists():
        return {"status": "skipped", "reason": "no database yet"}

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = settings.backup_dir / f"copilot-{stamp}.sqlite"

    src = sqlite3.connect(str(settings.db_path))
    try:
        out = sqlite3.connect(str(dest))
        try:
            src.backup(out)  # consistent snapshot, even with concurrent readers
            # collapse into a single clean file (no -wal/-shm sidecars).
            out.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            out.execute("PRAGMA journal_mode=DELETE")
        finally:
            out.close()
    finally:
        src.close()

    # The TRUNCATE checkpoint flushed all data into the main file; drop sidecars
    # so each backup is exactly one self-contained .sqlite file.
    for suffix in ("-wal", "-shm"):
        Path(str(dest) + suffix).unlink(missing_ok=True)

    pruned = _prune(settings.backup_dir, keep)
    return {"status": "ok", "backup": str(dest),
            "size_bytes": dest.stat().st_size, "pruned": pruned}


def _prune(backup_dir: Path, keep: int) -> int:
    backups = sorted(backup_dir.glob("copilot-*.sqlite"))
    excess = backups[:-keep] if keep > 0 else []
    for old in excess:
        old.unlink(missing_ok=True)
    return len(excess)
