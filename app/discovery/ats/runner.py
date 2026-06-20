"""ATS company-discovery runner (discovery-only).

For each due company_ats binding: conditional GET the board, parse, apply the
coarse role filter, persist (with ATS-wins dedup), detect new/closed, update
health + schedule, and log a discovery_run. Per-company fail isolation and
per-domain rate limiting throughout.

Independently runnable: `python -m app.cli discover-companies`.
"""
from __future__ import annotations

import logging
import random
import time
from typing import Any, Dict, List, Optional

import httpx

from app import util
from app.db.connection import transaction
from app.discovery import normalize
from app.discovery.ats.greenhouse import GreenhouseAdapter
from app.discovery.ats.lever import LeverAdapter
from app.discovery.base import NormalizedJob
from app.discovery.role_filter import classify, should_ingest
from app.repositories import jobs as jobs_repo
from app.repositories import registry as reg

log = logging.getLogger("discovery.ats")

_ADAPTERS = {a.key: a for a in (GreenhouseAdapter(), LeverAdapter())}
_UA = "job-copilot-discovery/0.1 (+local-first; discovery-only; polite)"
_MIN_REQUEST_SPACING = 0.6  # seconds between requests to the same ATS domain


def _conditional_get(url: str, etag: Optional[str], last_modified: Optional[str]):
    """Returns (status, body_bytes, etag, last_modified). Raises on network error."""
    headers = {"User-Agent": _UA, "Accept": "application/json"}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        r = client.get(url, headers=headers)
    if r.status_code not in (200, 304):
        r.raise_for_status()
    return r.status_code, r.content, r.headers.get("ETag"), r.headers.get("Last-Modified")


def _role_filter(jobs: List[NormalizedJob]):
    """Apply KEEP/SOFT_DROP/DROP. Returns (kept, dropped_count)."""
    kept: List[NormalizedJob] = []
    dropped = 0
    for nj in jobs:
        rc = classify(nj.title)
        if not should_ingest(rc):
            dropped += 1
            continue
        nj.role_class = rc
        kept.append(nj)
    return kept, dropped


def _detect_closed(conn, company_id: int, platform_key: str,
                   present_ids: set) -> int:
    """Mark jobs gone from the board as CLOSED (only when the board is non-empty)."""
    if not present_ids:
        return 0
    existing = jobs_repo.jobs_for_company_platform(conn, company_id, platform_key)
    gone = [j["id"] for j in existing if j.get("external_job_id") not in present_ids]
    return jobs_repo.mark_closed(conn, gone)


def run_company_discovery(platform_keys: Optional[List[str]] = None,
                          limit: int = 1000) -> Dict[str, Any]:
    keys = platform_keys or list(_ADAPTERS.keys())
    report: Dict[str, Any] = {"platforms": {}, "created": 0, "merged": 0,
                              "closed": 0, "dropped": 0, "checked": 0, "errors": 0}

    for key in keys:
        adapter = _ADAPTERS[key]
        with transaction() as conn:
            due = reg.due_company_ats(conn, key, limit)
        pstats = {"checked": 0, "created": 0, "merged": 0, "closed": 0,
                  "dropped": 0, "not_modified": 0, "errors": 0, "disabled": 0}

        for i, cats in enumerate(due):
            started = util.now_iso()
            interval = cats["schedule_interval_minutes"]
            jitter = random.randint(0, max(1, interval // 10))
            url = adapter.board_url(cats["board_token"], bool(cats["supports_full_description"]))
            try:
                status, body, etag, lastmod = _conditional_get(url, cats["etag"],
                                                               cats["last_modified"])
                if status == 304:
                    with transaction() as conn:
                        reg.record_not_modified(conn, cats["id"], interval, jitter)
                        reg.log_run(conn, cats["id"], "NOT_MODIFIED", started, 304)
                    pstats["not_modified"] += 1
                    continue

                parsed = adapter.parse(body, cats)
                present_ids = {nj.external_job_id for nj in parsed if nj.external_job_id}
                kept, dropped = _role_filter(parsed)
                content_hash = util.sha256_hex("board", *sorted(present_ids))
                changed = content_hash != (cats["board_content_hash"] or "")

                with transaction() as conn:
                    pj = normalize.persist_jobs(conn, kept)
                    closed = _detect_closed(conn, cats["company_id"], key, present_ids)
                    reg.record_success(conn, cats["id"], interval, changed, etag, lastmod,
                                       content_hash, jitter)
                    reg.log_run(conn, cats["id"], "OK", started, 200,
                                jobs_seen=len(parsed), jobs_new=pj["created"],
                                jobs_closed=closed, jobs_dropped=dropped, nbytes=len(body))
                pstats["created"] += pj["created"]
                pstats["merged"] += pj.get("merged", 0)
                pstats["closed"] += closed
                pstats["dropped"] += dropped
                pstats["checked"] += 1
            except Exception as e:  # fail-isolated per company
                with transaction() as conn:
                    res = reg.record_failure(conn, cats["id"], interval, type(e).__name__)
                    reg.log_run(conn, cats["id"], "ERROR", started, error=str(e)[:300])
                pstats["errors"] += 1
                if res.get("disabled"):
                    pstats["disabled"] += 1
                    log.warning("auto-disabled %s/%s after repeated failures",
                                key, cats["board_token"])
            # polite per-domain spacing (all of a platform's calls share one host)
            if i < len(due) - 1:
                time.sleep(_MIN_REQUEST_SPACING + random.uniform(0, 0.4))

        report["platforms"][key] = pstats
        for k in ("created", "merged", "closed", "dropped", "errors"):
            report[k] += pstats[k]
        report["checked"] += pstats["checked"]
        log.info("ATS %s: %s", key, pstats)
    return report
