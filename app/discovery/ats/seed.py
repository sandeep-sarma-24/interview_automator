"""Seed ATS platform reference data + the approved Wave-1 company universe.

`seed_companies(verify=True)` creates company + company_ats rows and then probes
each board token once: resolving tokens stay active; non-resolving tokens are
auto-disabled (health=BROKEN) so the worker never wastes cycles on them. This is
the auto-verification of board tokens.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

import httpx

from app.core import telemetry
from app.db.connection import transaction
from app.discovery.ats.greenhouse import GreenhouseAdapter
from app.discovery.ats.lever import LeverAdapter
from app.repositories import jobs as jobs_repo
from app.repositories import registry as reg
from app import util

log = logging.getLogger("discovery.ats.seed")

_WAVE1 = Path(__file__).resolve().parent / "wave1.json"
_ADAPTERS = {"GREENHOUSE": GreenhouseAdapter(), "LEVER": LeverAdapter()}
_UA = "job-copilot-discovery/0.1 (+local-first; discovery-only; polite)"

PLATFORM_SPECS = {
    "GREENHOUSE": {
        "display_name": "Greenhouse", "discovery_kind": "JSON_API",
        "endpoint_template": "https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
        "supports_full_description": True, "capability_tier_default": "DISCOVERY_ONLY",
        "automation_difficulty": "EASY", "rate_limit_per_min": 60,
    },
    "LEVER": {
        "display_name": "Lever", "discovery_kind": "JSON_API",
        "endpoint_template": "https://api.lever.co/v0/postings/{token}?mode=json",
        "supports_full_description": True, "capability_tier_default": "DISCOVERY_ONLY",
        "automation_difficulty": "EASY", "rate_limit_per_min": 60,
    },
}


def seed_platforms() -> None:
    with transaction() as conn:
        for key, spec in PLATFORM_SPECS.items():
            reg.upsert_platform(conn, key, spec)


def _verify_token(ats: str, token: str) -> Dict[str, Any]:
    """Probe the board once. Returns {ok, http, count}."""
    adapter = _ADAPTERS[ats]
    url = adapter.board_url(token, supports_full_description=False)
    start = time.monotonic()
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True,
                          headers={"User-Agent": _UA}) as client:
            r = client.get(url)
        telemetry.record_api_call(ats, "GET", url, status_code=r.status_code,
                                  latency_ms=int((time.monotonic() - start) * 1000),
                                  ok=r.status_code == 200)
        if r.status_code != 200:
            return {"ok": False, "http": r.status_code, "count": 0}
        count = len(adapter.parse(r.content, {"company_name": ""}))
        return {"ok": True, "http": 200, "count": count}
    except Exception as e:  # noqa: BLE001
        telemetry.record_api_call(ats, "GET", url, status_code=None,
                                  latency_ms=int((time.monotonic() - start) * 1000),
                                  ok=False, error=type(e).__name__)
        return {"ok": False, "http": "ERR:" + type(e).__name__, "count": 0}


def load_wave1() -> List[Dict[str, Any]]:
    return json.loads(_WAVE1.read_text(encoding="utf-8"))["companies"]


def seed_companies(verify: bool = True) -> Dict[str, Any]:
    seed_platforms()
    entries = load_wave1()
    report = {"total": len(entries), "active": 0, "disabled": 0, "rows": []}

    for i, e in enumerate(entries):
        with transaction() as conn:
            company = jobs_repo.get_or_create_company(conn, e["company"])
            platform = reg.get_platform(conn, e["ats"])
            cats = reg.upsert_company_ats(conn, company["id"], platform["id"],
                                          e["token"], e["tier"])
        status = "active"
        if verify:
            res = _verify_token(e["ats"], e["token"])
            if not res["ok"]:
                with transaction() as conn:
                    conn.execute(
                        "UPDATE company_ats SET is_active=0, health_status='BROKEN', "
                        "disabled_reason=?, updated_at=? WHERE id=?",
                        (f"token did not resolve (http {res['http']})", util.now_iso(), cats["id"]))
                status = "disabled"
                report["disabled"] += 1
            else:
                report["active"] += 1
            report["rows"].append({"company": e["company"], "ats": e["ats"],
                                   "token": e["token"], "status": status,
                                   "live_jobs": res.get("count")})
            if i < len(entries) - 1:
                time.sleep(0.4)
        else:
            report["active"] += 1
    return report
