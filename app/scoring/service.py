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
from app.core import telemetry
from app.db.connection import transaction
from app.domain import Reason, State

# Stage-0 reason code -> drop-inspection reason label.
_DROP_REASON = {
    "COMPANY_BLOCKED": "BLOCKED_COMPANY",
    "NOT_REMOTE": "NOT_REMOTE",
    "LOCATION_INELIGIBLE": "LOCATION",
    "SENIORITY_UNDER": "SENIORITY",
    "SENIORITY_OVER": "SENIORITY",
}
from app.repositories import candidates as cand_repo
from app.repositories import jobs as jobs_repo
from app.repositories import preferences as pref_repo
from app.repositories import roles as roles_repo
from app.repositories import scoring as score_repo
from app.roles.resolver import RoleResolver
from app.scoring.embeddings import EmbeddingProvider
from app.scoring import rules

log = logging.getLogger("scoring")


def _resolve_role_list(resolver: RoleResolver, free_text: List[str]) -> List[str]:
    keys: List[str] = []
    for r in free_text:
        k = resolver.resolve(r).get("canonical_key")
        if k and k not in keys:
            keys.append(k)
    return keys


def _build_role_context(resolver: RoleResolver, pv: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve candidate target/avoid roles -> canonical (persist once), and expand
    the related-role family graph. job_canonical is attached per job."""
    from app import util
    targets = util.loads(pv.get("target_canonical_roles_json"))
    avoids = util.loads(pv.get("avoid_canonical_roles_json"))
    if targets is None or avoids is None:
        targets = _resolve_role_list(resolver, util.loads(pv.get("target_roles_json"), []))
        avoids = _resolve_role_list(resolver, util.loads(pv.get("avoid_roles_json"), []))
        with transaction() as conn:
            cand_repo.set_canonical_roles(conn, pv["id"], targets, avoids)
    with transaction() as conn:
        graph = roles_repo.related_graph(conn)
    related = set()
    for t in targets:
        related |= set(graph.get(t, []))
    related -= set(targets)
    return {"primary": targets[0] if targets else None,
            "targets": set(targets), "avoids": set(avoids), "related": related}


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
    resolver = RoleResolver(provider)
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
        role_base = _build_role_context(resolver, pv)

        with transaction() as conn:
            todo = jobs_repo.jobs_without_application(conn, cand["id"], limit)

        stats = {"scored": 0, "shortlisted": 0, "filtered": 0, "leaps": 0}
        for job in todo:
            sim, used = _similarity_for_job(provider, job, target_text, target_vec)
            jc = resolver.resolve(job.get("title") or "")   # canonical resolve (own txns, cached)
            role_ctx = {**role_base, "job_canonical": jc["canonical_key"], "method": jc["method"]}
            drop_reason = None
            with transaction() as conn:
                app = score_repo.get_or_create_application(conn, cand["id"], job["id"], pv["id"])
                pref = pref_repo.get_preference(conn, cand["id"], job["company_id"])

                reason = rules.stage0_filter(profile, job, pref)
                if reason:
                    state = State.REJECTED if reason == Reason.COMPANY_BLOCKED else State.FILTERED
                    score_repo.transition(conn, app["id"], state, reason)
                    stats["filtered"] += 1
                    drop_reason = _DROP_REASON.get(reason, reason)
                else:
                    result, signals = rules.score_job(profile, job, pref, sim, used, role_ctx)
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
            # DROP inspection event (outside the transaction)
            if drop_reason:
                telemetry.record_event("DISCOVERY", "DROP", source="SCORING",
                                       message=job.get("title"),
                                       metadata={"company": job.get("company_name"),
                                                 "title": job.get("title"), "reason": drop_reason})

        report["candidates"][cand["display_name"]] = {"status": "ok", **stats}
        telemetry.record_event("SCORING", "score_complete", source=report["backend"],
                               message=cand["display_name"], metadata=stats)
        log.info("scored %s: %s", cand["display_name"], stats)
    return report


def rescore(candidate_id: Optional[int] = None, limit: int = 1000000) -> Dict[str, Any]:
    """Re-score EXISTING applications with the current model (rules-v2-canonical).
    Writes a new current score (retiring the prior one). Human verdicts are
    preserved: scored is refreshed but the application state is left unchanged."""
    provider = EmbeddingProvider()
    resolver = RoleResolver(provider)
    threshold = get_settings().shortlist_threshold
    report: Dict[str, Any] = {"backend": "ollama" if provider.available else "fallback",
                              "candidates": {}}
    with transaction() as conn:
        cands = ([c for c in [cand_repo.get_candidate(conn, candidate_id)] if c]
                 if candidate_id is not None else cand_repo.list_candidates(conn))

    for cand in cands:
        if cand.get("status") != "ACTIVE":
            continue
        with transaction() as conn:
            pv = cand_repo.get_current_profile(conn, cand["id"])
        if not pv:
            report["candidates"][cand["display_name"]] = {"status": "skipped", "reason": "no profile"}
            continue
        profile = rules.build_profile(pv)
        target_text = profile.target_text
        target_vec = _ensure_target_embedding(provider, pv, target_text)
        role_base = _build_role_context(resolver, pv)

        with transaction() as conn:
            apps = [dict(r) for r in conn.execute(
                "SELECT a.id AS app_id, a.job_id, a.verdict FROM application a "
                "WHERE a.candidate_id=? AND a.deleted_at IS NULL LIMIT ?", (cand["id"], limit))]

        stats = {"rescored": 0, "shortlisted": 0, "filtered": 0, "verdict_preserved": 0}
        for ap in apps:
            with transaction() as conn:
                job = jobs_repo.get_job(conn, ap["job_id"])
            if not job:
                continue
            sim, used = _similarity_for_job(provider, job, target_text, target_vec)
            jc = resolver.resolve(job.get("title") or "")
            role_ctx = {**role_base, "job_canonical": jc["canonical_key"], "method": jc["method"]}
            with transaction() as conn:
                pref = pref_repo.get_preference(conn, cand["id"], job["company_id"])
                reason = rules.stage0_filter(profile, job, pref)
                if reason:
                    if ap["verdict"] is None:
                        state = State.REJECTED if reason == Reason.COMPANY_BLOCKED else State.FILTERED
                        score_repo.transition(conn, ap["app_id"], state, reason)
                        stats["filtered"] += 1
                    else:
                        stats["verdict_preserved"] += 1
                    continue
                result, signals = rules.score_job(profile, job, pref, sim, used, role_ctx)
                score_repo.write_score(conn, ap["app_id"], result, signals)
                stats["rescored"] += 1
                if ap["verdict"] is not None:
                    stats["verdict_preserved"] += 1          # score refreshed; state left to human
                elif result["leap_override"] or result["total_score"] >= threshold:
                    score_repo.transition(conn, ap["app_id"], State.SHORTLISTED,
                                          "leap" if result["leap_override"] else "threshold")
                    stats["shortlisted"] += 1
                else:
                    score_repo.transition(conn, ap["app_id"], State.SCORED)
        report["candidates"][cand["display_name"]] = {"status": "ok", **stats}
        telemetry.record_event("SCORING", "rescore_complete", source=report["backend"],
                               message=cand["display_name"], metadata=stats)
        log.info("rescored %s: %s", cand["display_name"], stats)
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
