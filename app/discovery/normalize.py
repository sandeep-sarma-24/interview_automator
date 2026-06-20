"""Normalization, dedup hashing, remote detection and persistence of jobs."""
from __future__ import annotations

import re
import sqlite3
from typing import Any, Dict, List
from urllib.parse import urlsplit, urlunsplit

from app import util
from app.discovery.base import NormalizedJob
from app.repositories import jobs as jobs_repo

_REMOTE_RE = re.compile(r"\b(remote|work\s*from\s*home|wfh|anywhere|distributed)\b", re.I)
_ONSITE_RE = re.compile(r"\b(on[\s-]?site|in[\s-]?office|hybrid)\b", re.I)
_RICH_DESC_CHARS = 400


def canonical_url(url: str) -> str:
    """Strip query/fragment so the same posting dedups across tracking params."""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


def detect_remote(*texts: str) -> Any:
    blob = " ".join(t for t in texts if t)
    if not blob:
        return None
    if _REMOTE_RE.search(blob):
        return 1
    if _ONSITE_RE.search(blob):
        return 0
    return None


def dedup_hash(job: NormalizedJob) -> str:
    if job.source_url:
        return util.sha256_hex("url", canonical_url(job.source_url))
    return content_key(job)


def content_key(job: NormalizedJob) -> str:
    """Source-agnostic identity (company|title|location) for cross-source dedup."""
    return util.sha256_hex(
        "ck",
        util.normalize_company_name(job.company_name),
        util.normalize_text(job.title),
        util.normalize_text(job.location or ""),
    )


def signal_density(job: NormalizedJob) -> str:
    desc = job.description_text or ""
    return "RICH" if len(desc) >= _RICH_DESC_CHARS else "THIN"


def persist_jobs(conn: sqlite3.Connection, jobs: List[NormalizedJob]) -> Dict[str, int]:
    """Persist normalized jobs with dedup + ATS-wins cross-source merge.

    Returns counts: created, seen (re-sighted), merged (email/manual upgraded to
    ATS), errors. Order of checks: exact dedup_hash -> cross-source merge -> insert.
    """
    created = seen = merged = errors = 0
    for nj in jobs:
        try:
            if not nj.title or not nj.company_name:
                errors += 1
                continue
            if nj.is_remote is None:
                nj.is_remote = detect_remote(nj.title, nj.description_text or "",
                                             nj.location or "")
            ts = util.now_iso()
            dh = dedup_hash(nj)
            ck = content_key(nj)
            is_api = nj.source == "API"

            # 1. exact duplicate (same canonical URL / content) -> re-sighting
            existing = jobs_repo.get_by_dedup_hash(conn, dh)
            if existing:
                jobs_repo.bump_last_seen(conn, existing["id"], ts)
                seen += 1
                continue

            data = _job_data(nj, ck)

            # 2. cross-source: ATS record wins
            match = jobs_repo.find_cross_source_match(conn, ck, is_api)
            if match:
                if is_api and match["source"] != "API":
                    jobs_repo.upgrade_to_ats(conn, match["id"], dh, data, ts)
                    merged += 1
                    continue
                if not is_api and match["source"] == "API":
                    jobs_repo.bump_last_seen(conn, match["id"], ts)  # defer to ATS
                    seen += 1
                    continue
                # same-source content match -> fall through to insert (distinct req)

            # 3. new job
            company = jobs_repo.get_or_create_company(conn, nj.company_name)
            jobs_repo.upsert_job(conn, company["id"], dh, data)
            created += 1
        except Exception:
            errors += 1
    return {"created": created, "seen": seen, "merged": merged, "errors": errors}


def _job_data(nj: NormalizedJob, ck: str) -> Dict[str, Any]:
    return {
        "source": nj.source, "discovery_method": nj.discovery_method,
        "source_ref": nj.source_ref, "source_url": nj.source_url,
        "external_job_id": nj.external_job_id, "title": nj.title.strip(),
        "description_text": nj.description_text, "location": nj.location,
        "is_remote": nj.is_remote, "salary_text": nj.salary_text,
        "signal_density": signal_density(nj),
        "raw_payload_json": util.dumps(nj.raw) if nj.raw else None,
        "posted_at": nj.posted_at, "role_class": nj.role_class, "content_key": ck,
    }
