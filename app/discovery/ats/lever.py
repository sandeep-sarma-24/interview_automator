"""Lever public Postings API adapter (discovery-only).

  GET https://api.lever.co/v0/postings/{token}?mode=json
  -> [{id,text,hostedUrl,categories:{location,team,commitment},descriptionPlain,createdAt}]
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.discovery.ats.base import ATSAdapter
from app.discovery.base import NormalizedJob

_BASE = "https://api.lever.co/v0/postings/{token}?mode=json"


def _epoch_ms_to_iso(ms: Optional[int]) -> Optional[str]:
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, OverflowError, OSError):
        return None


class LeverAdapter(ATSAdapter):
    key = "LEVER"

    def board_url(self, token: str, supports_full_description: bool) -> str:
        return _BASE.format(token=token)

    def parse(self, payload: bytes, cats: Dict[str, Any]) -> List[NormalizedJob]:
        postings = json.loads(payload)
        company = cats["company_name"]
        out: List[NormalizedJob] = []
        for p in postings:
            title = (p.get("text") or "").strip()
            if not title:
                continue
            cat = p.get("categories") or {}
            desc = p.get("descriptionPlain") or p.get("description") or ""
            commitment = cat.get("commitment")
            workplace = (p.get("workplaceType") or "").lower()  # remote/onsite/hybrid
            out.append(NormalizedJob(
                title=title,
                company_name=company,
                source="API",
                discovery_method="API",
                source_ref="LEVER",
                source_url=p.get("hostedUrl") or p.get("applyUrl"),
                external_job_id=str(p.get("id")) if p.get("id") else None,
                description_text=" ".join(desc.split())[:8000],
                location=cat.get("location"),
                is_remote=1 if workplace == "remote" else (0 if workplace in ("on-site", "onsite") else None),
                posted_at=_epoch_ms_to_iso(p.get("createdAt")),
                raw={"team": cat.get("team"), "commitment": commitment},
            ))
        return out
