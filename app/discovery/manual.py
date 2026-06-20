"""MANUAL_DISCOVERY: paste a job URL -> create a job record (then it gets scored).

Used for jobs found via Reddit / X / referrals. Best-effort page parse; even if
the fetch fails we still create a minimal trackable job from the URL.
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from app.discovery.base import NormalizedJob

_UA = "job-copilot/0.1 (+local-first; respects robots)"


def _meta(soup: BeautifulSoup, prop: str, attr: str = "property") -> Optional[str]:
    tag = soup.find("meta", attrs={attr: prop})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None


def fetch_url_job(url: str) -> NormalizedJob:
    url = url.strip()
    host = urlsplit(url).netloc or "unknown"
    title = url
    company = host.replace("www.", "").split(".")[0].capitalize()
    description = None
    location = None

    try:
        with httpx.Client(timeout=15.0, follow_redirects=True,
                          headers={"User-Agent": _UA}) as client:
            resp = client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            title = (_meta(soup, "og:title")
                     or (soup.title.get_text(strip=True) if soup.title else None)
                     or title)
            company = _meta(soup, "og:site_name") or company
            description = (_meta(soup, "og:description")
                          or _meta(soup, "description", attr="name"))
            if not description:
                body = soup.find("body")
                if body:
                    description = " ".join(body.get_text(" ", strip=True).split())[:4000]
    except Exception:
        pass  # keep the minimal record built from the URL

    return NormalizedJob(
        title=(title or url)[:200],
        company_name=company or host,
        source="MANUAL",
        discovery_method="MANUAL",
        source_ref="MANUAL",
        source_url=url,
        description_text=description,
        location=location,
        raw={"host": host},
    )
