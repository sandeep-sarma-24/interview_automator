"""Best-effort parsers for job-alert emails (LinkedIn / Naukri / Indeed / generic).

Email layouts change often, so these are deliberately permissive: extract what
we can, skip what we can't, never raise. Missing a few cards is acceptable
(graceful) — these jobs are THIN by nature and get a low confidence at scoring.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup

from app.discovery.base import NormalizedJob

# Hrefs that look like an actual posting (vs nav/unsubscribe/profile links).
_JOB_URL_RE = re.compile(
    r"(jobs/view|/viewjob|/job-detail|/jobs/|naukri\.com/job|indeed\.com/(rc|viewjob)"
    r"|comm/jobs)", re.I)
_NAV_TEXT_RE = re.compile(
    r"^(view job|see all|unsubscribe|view all|apply now|jobs?|view|settings|help)$", re.I)
_SEP_RE = re.compile(r"\s*[·•|–—]\s*|\s{2,}|\n")


def detect_source(sender: str, subject: str) -> str:
    blob = f"{sender} {subject}".lower()
    if "linkedin" in blob:
        return "LINKEDIN"
    if "naukri" in blob:
        return "NAUKRI"
    if "indeed" in blob:
        return "INDEED"
    return "GENERIC"


def _clean(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _company_location(container_text: str, title: str) -> Tuple[str, Optional[str]]:
    rest = _clean(container_text.replace(title, " ", 1))
    parts = [p for p in _SEP_RE.split(rest) if p and p.strip()]
    company = parts[0].strip() if parts else ""
    location = parts[1].strip() if len(parts) > 1 else None
    # Guard against junk like trailing "Remote" being read as the company.
    if company.lower() in ("remote", "new"):
        company = parts[1].strip() if len(parts) > 1 else company
    return company, location


def parse_email(html: str, source_ref: str) -> List[NormalizedJob]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    jobs: List[NormalizedJob] = []
    seen_urls = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not _JOB_URL_RE.search(href):
            continue
        title = _clean(a.get_text(" ", strip=True))
        if not title or len(title) < 3 or len(title) > 140 or _NAV_TEXT_RE.match(title):
            continue
        url = href.split("?")[0]
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Climb to the smallest enclosing card: the first ancestor whose text
        # has content beyond the title (company/location), capped so we don't
        # swallow sibling cards in table layouts.
        container = a.parent if a.parent is not None else a
        ctext = _clean(container.get_text(" ", strip=True))
        levels = 0
        while (container.parent is not None and len(ctext) <= len(title) + 3
               and levels < 2):
            container = container.parent
            ctext = _clean(container.get_text(" ", strip=True))
            levels += 1
        company, location = _company_location(ctext, title)
        if not company:
            company = source_ref.capitalize()  # last-resort placeholder

        jobs.append(NormalizedJob(
            title=title,
            company_name=company,
            source="EMAIL",
            discovery_method="EMAIL",
            source_ref=source_ref,
            source_url=url,
            location=location,
            description_text=None,
            raw={"snippet": ctext[:500]},
        ))
    return jobs
