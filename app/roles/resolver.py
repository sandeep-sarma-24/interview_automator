"""Role resolver (M4-P1): title -> canonical role via alias -> embedding -> UNRESOLVED.

Self-contained: opens its OWN short transactions for cache/alias DB access and
performs the (network) embedding BETWEEN them, so it never holds a write
transaction across a network call. Telemetry is emitted after those transactions
close (fail-safe, own connection). Results are cached in role_match_cache so each
distinct normalized title is resolved — and its UNRESOLVED event emitted — once.

NOT wired into scoring in this slice.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from app import util
from app.config import get_settings
from app.core import telemetry
from app.db.connection import transaction
from app.repositories import roles as roles_repo
from app.roles.normalize import normalize_role
from app.scoring.embeddings import EmbeddingProvider, _cosine

log = logging.getLogger("roles.resolver")


class RoleResolver:
    def __init__(self, provider: Optional[EmbeddingProvider] = None) -> None:
        self.provider = provider or EmbeddingProvider()
        self.threshold = get_settings().canonical_assign_threshold
        with transaction() as conn:
            self.canon = roles_repo.list_canonical_roles(conn, with_embeddings=True)
        self._embedded = [c for c in self.canon if c.get("embedding")]

    # (canonical_role_id, key, method, score)
    def _embed_match(self, norm: str) -> Tuple[Optional[int], Optional[str], str, Optional[float]]:
        if not self.provider.available or not self._embedded:
            return None, None, "UNRESOLVED", None
        vec = self.provider.embed(norm)
        if not vec:
            return None, None, "UNRESOLVED", None
        best, best_sim = None, -1.0
        for c in self._embedded:
            s = _cosine(vec, c["embedding"])
            if s > best_sim:
                best_sim, best = s, c
        if best_sim >= self.threshold and best is not None:
            return best["id"], best["key"], "EMBEDDING", round(best_sim, 4)
        return None, None, "UNRESOLVED", round(best_sim, 4)

    def resolve(self, title: str) -> Dict[str, Any]:
        norm = normalize_role(title)
        if not norm:
            return {"canonical_key": None, "canonical_role_id": None,
                    "method": "UNRESOLVED", "score": None, "cached": False}
        h = util.sha256_hex("role", norm)

        with transaction() as conn:
            cached = roles_repo.cache_get(conn, h)
        if cached:
            return {"canonical_key": cached["key"], "canonical_role_id": cached["canonical_role_id"],
                    "method": cached["method"], "score": cached["score"], "cached": True}

        with transaction() as conn:
            alias = roles_repo.lookup_alias(conn, norm)
        if alias:
            rid, key, method, score = alias["canonical_role_id"], alias["key"], "ALIAS", 1.0
        else:
            rid, key, method, score = self._embed_match(norm)  # network OUTSIDE any txn

        with transaction() as conn:
            roles_repo.cache_put(conn, h, norm, rid, method, score)

        if method == "UNRESOLVED":  # one event per distinct title (cache short-circuits next time)
            telemetry.record_event("SCORING", "role_unresolved", source="UNRESOLVED",
                                   message=title[:200], metadata={"normalized": norm, "best_sim": score})
        return {"canonical_key": key, "canonical_role_id": rid, "method": method,
                "score": score, "cached": False}


def resolve_titles(titles: List[str], provider: Optional[EmbeddingProvider] = None) -> Dict[str, Any]:
    """Batch-resolve distinct titles (one shared provider). Returns counts by method."""
    resolver = RoleResolver(provider)
    counts = {"ALIAS": 0, "EMBEDDING": 0, "UNRESOLVED": 0, "cached": 0}
    seen = set()
    for t in titles:
        n = normalize_role(t)
        if n in seen:
            continue
        seen.add(n)
        res = resolver.resolve(t)
        if res["cached"]:
            counts["cached"] += 1
        counts[res["method"]] = counts.get(res["method"], 0) + 1
    return {"distinct_titles": len(seen),
            "backend": "ollama" if resolver.provider.available else "fallback", **counts}
