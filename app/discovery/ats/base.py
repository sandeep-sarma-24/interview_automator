"""ATS adapter contract for discovery-only fetch + parse.

An adapter ONLY knows how to (a) build a board URL from a token and (b) turn the
board's JSON into NormalizedJob objects. All scheduling, HTTP, conditional-GET,
rate-limiting, change/closure detection and health live in the runner — so
adding an ATS later is just a parser, not a new pipeline.

Discovery-only: no auth, no login, no credentials, no browser, no submission.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.discovery.base import NormalizedJob


class ATSAdapter:
    key: str = "BASE"

    def board_url(self, token: str, supports_full_description: bool) -> str:  # pragma: no cover
        raise NotImplementedError

    def parse(self, payload: bytes, cats: Dict[str, Any]) -> List[NormalizedJob]:  # pragma: no cover
        """Turn a board payload into normalized jobs (no role filtering here)."""
        raise NotImplementedError
