"""Discovery contracts. A DiscoverySource yields normalized job dicts.

Sources are independent and fail-isolated: one source raising must never stop
the others (graceful degradation). The scoring step is entirely separate, so
discovery runs and produces job rows even when scoring/dashboard are down.
"""
from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


class DiscoveryUnavailable(Exception):
    """Raised by a source that cannot run right now (e.g. Gmail not authorized).

    The discovery service catches this and continues with other sources.
    """


@dataclass
class NormalizedJob:
    title: str
    company_name: str
    source: str                       # EMAIL | MANUAL | API
    discovery_method: str             # EMAIL | MANUAL | API
    source_ref: Optional[str] = None  # e.g. LINKEDIN / NAUKRI / INDEED / gmail msg id
    source_url: Optional[str] = None
    external_job_id: Optional[str] = None
    description_text: Optional[str] = None
    location: Optional[str] = None
    is_remote: Optional[int] = None
    posted_at: Optional[str] = None
    salary_text: Optional[str] = None
    role_class: Optional[str] = None   # KEEP | SOFT_DROP (set by ATS ingest filter)
    raw: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DiscoverySource:
    name = "base"

    def fetch(self, conn: sqlite3.Connection) -> List[NormalizedJob]:  # pragma: no cover
        raise NotImplementedError
