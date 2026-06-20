"""Discovery orchestration. Runs sources, fail-isolated, and persists jobs.

Independently runnable (`python -m app.cli discover`). Produces job rows only —
scoring and the dashboard are separate steps, so discovery has zero dependency
on either being available.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.db.connection import transaction
from app.discovery import manual, normalize
from app.discovery.base import DiscoverySource, DiscoveryUnavailable
from app.discovery.email_gmail import GmailSource

log = logging.getLogger("discovery")


def default_sources() -> List[DiscoverySource]:
    return [GmailSource()]


def run_discovery(sources: Optional[List[DiscoverySource]] = None) -> Dict[str, Any]:
    """Run each source independently; one failing never stops the others."""
    sources = sources if sources is not None else default_sources()
    report: Dict[str, Any] = {"sources": {}, "created": 0, "seen": 0, "errors": 0}

    for src in sources:
        try:
            with transaction() as conn:
                jobs = src.fetch(conn)
                stats = normalize.persist_jobs(conn, jobs)
            report["sources"][src.name] = {"status": "ok", **stats}
            for k in ("created", "seen", "errors"):
                report[k] += stats[k]
            log.info("source %s: %s", src.name, stats)
        except DiscoveryUnavailable as e:
            report["sources"][src.name] = {"status": "unavailable", "reason": str(e)}
            log.warning("source %s unavailable: %s", src.name, e)
        except Exception as e:  # never let one source kill the run
            report["sources"][src.name] = {"status": "error", "reason": str(e)}
            log.exception("source %s failed", src.name)
    return report


def add_manual_url(url: str) -> Dict[str, Any]:
    """MANUAL_DISCOVERY entry point: paste a URL -> create a job row."""
    nj = manual.fetch_url_job(url)
    with transaction() as conn:
        stats = normalize.persist_jobs(conn, [nj])
    return {"url": url, "title": nj.title, "company": nj.company_name, **stats}
