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

from app.core import health
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
    import time as _t
    from app.core import telemetry
    health.write_heartbeat()  # alive at cycle start
    summary = {"email_created": 0, "ats_created": 0, "ats_dropped": 0, "errors": 0}
    started = _t.monotonic()
    try:
        with heavy_resource_lock():
            try:
                rep = discovery_service.run_discovery()
                summary["email_created"] = rep["created"]
                log.info("email/manual discovery: created=%s seen=%s", rep["created"], rep["seen"])
            except Exception as e:
                summary["errors"] += 1
                telemetry.record_error("WORKER", "discovery", e)
                log.exception("email discovery cycle failed")
            try:
                rep = ats_runner.run_company_discovery()
                summary["ats_created"], summary["ats_dropped"] = rep["created"], rep["dropped"]
                log.info("ATS discovery: checked=%s created=%s merged=%s closed=%s dropped=%s",
                         rep["checked"], rep["created"], rep["merged"], rep["closed"], rep["dropped"])
            except Exception as e:
                summary["errors"] += 1
                telemetry.record_error("WORKER", "ats", e)
                log.exception("ATS discovery cycle failed")
            try:
                rep = scoring_service.run_scoring()
                log.info("scoring: %s", rep.get("candidates"))
            except Exception as e:
                summary["errors"] += 1
                telemetry.record_error("WORKER", "scoring", e)
                log.exception("scoring cycle failed")
            if do_backup:
                try:
                    log.info("backup: %s", run_backup())
                except Exception:
                    log.exception("backup failed")
                try:
                    from app.core.telemetry import prune_telemetry
                    log.info("prune: %s", prune_telemetry())
                except Exception:
                    log.exception("prune failed")
        telemetry.record_event("WORKER", "cycle_complete", source="SYSTEM",
                               level="ERROR" if summary["errors"] else "INFO",
                               duration_ms=int((_t.monotonic() - started) * 1000),
                               metadata=summary)
    except ResourceBusy:
        telemetry.record_event("WORKER", "cycle_skipped", source="SYSTEM",
                               level="WARN", message="heavy resource busy")
        log.warning("heavy resource busy; skipping this cycle")
    finally:
        health.write_heartbeat()  # alive at cycle end (covers long cycles)


def run_worker(interval_seconds: int = 1800, once: bool = False) -> None:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    health.write_heartbeat()  # immediate freshness on boot
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
