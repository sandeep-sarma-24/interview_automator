"""Scoring orchestration: discover -> create application -> Stage 0/1/2 -> persist.

Independently runnable (`python -m app.cli score`). Degrades gracefully:
  * No Ollama  -> token-overlap similarity (handled in EmbeddingProvider).
  * No profile -> candidate skipped with a clear note (can't score without a
    trajectory spec).
DB writes are per-job and short, so a crash mid-run just resumes (idempotent:
already-scored jobs have an application row and are skipped next time).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.config import get_settings
from app.db.connection import transaction
from app.domain import Reason, State
from app.repositories import candidates as cand_repo
from app.repositories import jobs as jobs_repo
from app.repositories import preferences as pref_repo
from app.repositories import scoring as score_repo
from app.scoring.embeddings import EmbeddingProvider
from app.scoring import rules

log = logging.getLogger("scoring")


def _ensure_target_embedding(provider: EmbeddingProvider, pv: Dict[str, Any],
                             target_text: str) -> Optional[List[float]]:
    if not provider.available:
        return None
    from app import util
    cached = util.loads(pv.get("target_embedding_json"))
    if cached and pv.get("target_embedding_model") == provider.model:
        return cached
    vec = provider.embed(target_text)
    if vec:
        with transaction() as conn:
            cand_repo.set_target_embedding(conn, pv["id"], vec, provider.model)
    return vec


def run_scoring(candidate_id: Optional[int] = None, limit: int = 1000) -> Dict[str, Any]:
    provider = EmbeddingProvider()
    threshold = get_settings().shortlist_threshold
    report: Dict[str, Any] = {"backend": "ollama" if provider.available else "fallback",
                              "candidates": {}}

    with transaction() as conn:
        if candidate_id is not None:
            cands = [c for c in [cand_repo.get_candidate(conn, candidate_id)] if c]
        else:
            cands = cand_repo.list_candidates(conn)

    for cand in cands:
        if cand.get("status") != "ACTIVE":
            continue
        with transaction() as conn:
            pv = cand_repo.get_current_profile(conn, cand["id"])
        if not pv:
            report["candidates"][cand["display_name"]] = {"status": "skipped",
                                                           "reason": "no profile/trajectory spec"}
            continue

        profile = rules.build_profile(pv)
        target_text = profile.target_text
        target_vec = _ensure_target_embedding(provider, pv, target_text)

        with transaction() as conn:
            todo = jobs_repo.jobs_without_application(conn, cand["id"], limit)

        stats = {"scored": 0, "shortlisted": 0, "filtered": 0, "leaps": 0}
        for job in todo:
            sim, used = _similarity_for_job(provider, job, target_text, target_vec)
            with transaction() as conn:
                app = score_repo.get_or_create_application(conn, cand["id"], job["id"], pv["id"])
                pref = pref_repo.get_preference(conn, cand["id"], job["company_id"])

                reason = rules.stage0_filter(profile, job, pref)
                if reason:
                    state = State.REJECTED if reason == Reason.COMPANY_BLOCKED else State.FILTERED
                    score_repo.transition(conn, app["id"], state, reason)
                    stats["filtered"] += 1
                    continue

                result, signals = rules.score_job(profile, job, pref, sim, used)
                score_repo.write_score(conn, app["id"], result, signals)
                if result["leap_override"] or result["total_score"] >= threshold:
                    score_repo.transition(conn, app["id"], State.SHORTLISTED,
                                          "leap" if result["leap_override"] else "threshold")
                    stats["shortlisted"] += 1
                    if result["leap_override"]:
                        stats["leaps"] += 1
                else:
                    score_repo.transition(conn, app["id"], State.SCORED)
                    stats["scored"] += 1

        report["candidates"][cand["display_name"]] = {"status": "ok", **stats}
        log.info("scored %s: %s", cand["display_name"], stats)
    return report


def _similarity_for_job(provider: EmbeddingProvider, job: Dict[str, Any],
                        target_text: str, target_vec) -> Any:
    job_text = f"{job.get('title') or ''} {job.get('description_text') or ''}".strip()
    job_vec = None
    if provider.available:
        with transaction() as conn:
            job_vec = jobs_repo.get_embedding(conn, job["id"], provider.model)
        if job_vec is None:
            job_vec = provider.embed(job_text)
            if job_vec:
                with transaction() as conn:
                    jobs_repo.save_embedding(conn, job["id"], provider.model, job_vec)
    return provider.similarity(job_text, target_text, job_vec, target_vec)
