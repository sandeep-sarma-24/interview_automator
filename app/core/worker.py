"""Single-worker loop (M0).

Serialized by design: discovery then scoring, one cycle at a time, under the
heavy-resource lock — never concurrent. This is the spine the later workflow
engine (M6) grows into. V1 has no leasing: one process, one item-class at a time.
"""
from __future__ import annotations

import logging
import signal
import time
from typing import Optional

from app.core.backup import run_backup
from app.core.locks import ResourceBusy, heavy_resource_lock
from app.discovery import service as discovery_service
from app.discovery.ats import runner as ats_runner
from app.scoring import service as scoring_service

log = logging.getLogger("worker")
_stop = False


def _handle_signal(signum, frame) -> None:  # noqa: ANN001
    global _stop
    _stop = True
    log.info("stop requested (signal %s); finishing current cycle", signum)


def run_cycle(do_backup: bool = False) -> None:
    """One serialized cycle. Each step is fail-isolated so one error doesn't
    abort the rest (graceful degradation)."""
    try:
        with heavy_resource_lock():
            try:
                rep = discovery_service.run_discovery()
                log.info("email/manual discovery: created=%s seen=%s", rep["created"], rep["seen"])
            except Exception:
                log.exception("email discovery cycle failed")
            try:
                rep = ats_runner.run_company_discovery()
                log.info("ATS discovery: checked=%s created=%s merged=%s closed=%s dropped=%s",
                         rep["checked"], rep["created"], rep["merged"], rep["closed"], rep["dropped"])
            except Exception:
                log.exception("ATS discovery cycle failed")
            try:
                rep = scoring_service.run_scoring()
                log.info("scoring: %s", rep.get("candidates"))
            except Exception:
                log.exception("scoring cycle failed")
            if do_backup:
                try:
                    log.info("backup: %s", run_backup())
                except Exception:
                    log.exception("backup failed")
    except ResourceBusy:
        log.warning("heavy resource busy; skipping this cycle")


def run_worker(interval_seconds: int = 1800, once: bool = False) -> None:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    log.info("worker started (interval=%ss, once=%s)", interval_seconds, once)
    last_backup_day: Optional[str] = None

    while not _stop:
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        do_backup = today != last_backup_day
        run_cycle(do_backup=do_backup)
        if do_backup:
            last_backup_day = today
        if once:
            break
        # interruptible sleep
        for _ in range(interval_seconds):
            if _stop:
                break
            time.sleep(1)
    log.info("worker stopped")
