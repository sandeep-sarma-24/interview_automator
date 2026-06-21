"""Seed the canonical role taxonomy + MANUAL aliases, and (when Ollama is up)
precompute canonical embeddings. Idempotent. Embeddings are optional — the
resolver runs alias-only until they exist (graceful)."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

from app.db.connection import transaction
from app.repositories import roles as roles_repo
from app.roles.normalize import normalize_role

log = logging.getLogger("roles.seed")
_DATA = Path(__file__).resolve().parent / "canonical_roles.json"


def load_taxonomy() -> Dict[str, Any]:
    return json.loads(_DATA.read_text(encoding="utf-8"))


def seed_roles(embed: bool = True, reset: bool = False) -> Dict[str, Any]:
    data = load_taxonomy()
    roles, aliases = 0, 0
    with transaction() as conn:
        if reset:
            # Clean re-seed (e.g. after removing canonical roles). Cached matches
            # to removed roles are nulled via ON DELETE SET NULL; clear the cache too.
            conn.execute("DELETE FROM role_match_cache")
            conn.execute("DELETE FROM role_alias")
            conn.execute("DELETE FROM canonical_role")
        for role in data["roles"]:
            rid = roles_repo.upsert_canonical_role(conn, role)
            roles += 1
            for alias in role.get("aliases", []):
                roles_repo.upsert_alias(conn, rid, alias, normalize_role(alias),
                                        source="MANUAL", created_by="SYSTEM")
                aliases += 1
    report = {"roles": roles, "aliases": aliases, "embedded": 0}
    if embed:
        report["embedded"] = embed_roles()
    return report


def embed_roles() -> int:
    """Precompute canonical embeddings (label + description). Requires Ollama;
    returns 0 (and logs) if unavailable."""
    from app.scoring.embeddings import EmbeddingProvider
    provider = EmbeddingProvider()
    if not provider.available:
        log.warning("Ollama unavailable; canonical embeddings not computed (resolver = alias-only)")
        return 0
    with transaction() as conn:
        roles = roles_repo.list_canonical_roles(conn)
    count = 0
    for r in roles:
        text = f"{r['label']}. {r.get('description') or ''}".strip()
        vec = provider.embed(text)
        if vec:
            with transaction() as conn:
                roles_repo.set_canonical_embedding(conn, r["key"], vec, provider.model)
            count += 1
    return count
