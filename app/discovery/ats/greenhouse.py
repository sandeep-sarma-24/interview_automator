"""Greenhouse public Job Board API adapter (discovery-only).

  GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
  -> {"jobs":[{id,title,absolute_url,location:{name},updated_at,content(HTML)}], "meta":{...}}
"""
from __future__ import annotations

import html as html_lib
import json
from typing import Any, Dict, List

from bs4 import BeautifulSoup

from app.discovery.ats.base import ATSAdapter
from app.discovery.base import NormalizedJob

_BASE = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def _strip_html(content: str) -> str:
    if not content:
        return ""
    text = BeautifulSoup(html_lib.unescape(content), "html.parser").get_text(" ", strip=True)
    return " ".join(text.split())[:8000]


class GreenhouseAdapter(ATSAdapter):
    key = "GREENHOUSE"

    def board_url(self, token: str, supports_full_description: bool) -> str:
        url = _BASE.format(token=token)
        return url + "?content=true" if supports_full_description else url

    def parse(self, payload: bytes, cats: Dict[str, Any]) -> List[NormalizedJob]:
        data = json.loads(payload)
        company = cats["company_name"]
        out: List[NormalizedJob] = []
        for j in data.get("jobs", []):
            title = (j.get("title") or "").strip()
            if not title:
                continue
            loc = (j.get("location") or {}).get("name")
            out.append(NormalizedJob(
                title=title,
                company_name=company,
                source="API",
                discovery_method="API",
                source_ref="GREENHOUSE",
                source_url=j.get("absolute_url"),
                external_job_id=str(j.get("id")) if j.get("id") is not None else None,
                description_text=_strip_html(j.get("content") or ""),
                location=loc,
                posted_at=j.get("updated_at") or j.get("first_published"),
                raw={"departments": [d.get("name") for d in j.get("departments", []) or []]},
            ))
        return out
