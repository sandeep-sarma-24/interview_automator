"""Config-driven coarse role classifier (M1.5 ingest filter).

Three tiers:
  KEEP       — core technical engineering roles (stored)
  SOFT_DROP  — adjacent technical roles: Product, Solutions, TPM, DevRel (stored,
               flagged so scoring/dashboard can deprioritize later)
  DROP       — obviously non-technical roles (NOT ingested)

Rules live in role_filter.json (override path via SCRAPER_ROLE_FILTER_CONFIG),
so the taxonomy is tuned without code changes. Precedence is deliberate:
  soft_drop_phrases  ->  drop  ->  keep  ->  default
so "Sales Engineer" lands in SOFT_DROP (not DROP via "sales", not KEEP via
"engineer"), and unmatched titles fall to a safe default (SOFT_DROP) rather than
being silently lost.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

from app import util

_DEFAULT_CONFIG = Path(__file__).resolve().parent / "role_filter.json"

KEEP = "KEEP"
SOFT_DROP = "SOFT_DROP"
DROP = "DROP"


@lru_cache(maxsize=1)
def _load_config() -> Dict[str, object]:
    path = Path(os.environ.get("SCRAPER_ROLE_FILTER_CONFIG", str(_DEFAULT_CONFIG)))
    data = json.loads(path.read_text(encoding="utf-8"))
    # pre-normalize keyword lists once
    for key in ("soft_drop_phrases", "keep", "drop"):
        data[key] = [util.normalize_text(k) for k in data.get(key, []) if k.strip()]
    data["default"] = data.get("default", SOFT_DROP)
    return data


def reload_config() -> None:
    _load_config.cache_clear()


def _contains_any(text: str, needles: List[str]) -> bool:
    return any(n and n in text for n in needles)


def classify(title: str) -> str:
    """Return KEEP | SOFT_DROP | DROP for a job title."""
    cfg = _load_config()
    # pad with spaces so " ml " style boundary tokens match at edges too
    t = f" {util.normalize_text(title)} "
    if _contains_any(t, cfg["soft_drop_phrases"]):   # type: ignore[arg-type]
        return SOFT_DROP
    if _contains_any(t, cfg["drop"]):                # type: ignore[arg-type]
        return DROP
    if _contains_any(t, cfg["keep"]):                # type: ignore[arg-type]
        return KEEP
    return cfg["default"]  # type: ignore[return-value]


def should_ingest(role_class: str) -> bool:
    """KEEP and SOFT_DROP are stored; DROP is filtered out at ingest."""
    return role_class != DROP
