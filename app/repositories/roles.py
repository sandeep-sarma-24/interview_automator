"""Persistence for canonical roles, aliases, and the resolver cache (M4-P1)."""
from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from app import util


# ───────────────────────────── canonical_role ─────────────────────────────
def upsert_canonical_role(conn: sqlite3.Connection, role: Dict[str, Any]) -> int:
    ts = util.now_iso()
    existing = conn.execute("SELECT id FROM canonical_role WHERE key=?", (role["key"],)).fetchone()
    if existing:
        conn.execute(
            "UPDATE canonical_role SET label=?, family=?, description=?, related_roles_json=? WHERE id=?",
            (role["label"], role["family"], role.get("description"),
             util.dumps(role.get("related", [])), existing["id"]))
        return int(existing["id"])
    cur = conn.execute(
        "INSERT INTO canonical_role (key, label, family, description, related_roles_json, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (role["key"], role["label"], role["family"], role.get("description"),
         util.dumps(role.get("related", [])), ts))
    return int(cur.lastrowid)


def set_canonical_embedding(conn: sqlite3.Connection, key: str, vector: List[float],
                            model: str) -> None:
    conn.execute("UPDATE canonical_role SET embedding_json=?, embedding_model=? WHERE key=?",
                 (util.dumps(vector), model, key))


def list_canonical_roles(conn: sqlite3.Connection, with_embeddings: bool = False) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, key, label, family, description, related_roles_json, embedding_json, "
        "embedding_model FROM canonical_role ORDER BY family, label").fetchall()
    out = []
    for r in rows:
        d = {"id": r["id"], "key": r["key"], "label": r["label"], "family": r["family"],
             "description": r["description"],
             "related": util.loads(r["related_roles_json"], [])}
        if with_embeddings:
            d["embedding"] = util.loads(r["embedding_json"])
            d["embedding_model"] = r["embedding_model"]
        out.append(d)
    return out


def get_role_by_key(conn: sqlite3.Connection, key: str) -> Optional[Dict[str, Any]]:
    r = conn.execute("SELECT id, key, label, family FROM canonical_role WHERE key=?", (key,)).fetchone()
    return dict(r) if r else None


def related_graph(conn: sqlite3.Connection) -> Dict[str, List[str]]:
    """{canonical_key: [related canonical keys]} — used by canonical trajectory eval."""
    return {r["key"]: util.loads(r["related_roles_json"], [])
            for r in conn.execute("SELECT key, related_roles_json FROM canonical_role")}


# ─────────────────────────────── role_alias ───────────────────────────────
def upsert_alias(conn: sqlite3.Connection, canonical_role_id: int, alias_text: str,
                 normalized: str, source: str, created_by: str,
                 confidence: Optional[float] = None) -> None:
    if not normalized:
        return
    conn.execute(
        "INSERT INTO role_alias (canonical_role_id, alias_text, normalized_alias, source, "
        "created_by, confidence, created_at) VALUES (?,?,?,?,?,?,?) "
        "ON CONFLICT(normalized_alias) DO UPDATE SET canonical_role_id=excluded.canonical_role_id, "
        "alias_text=excluded.alias_text, source=excluded.source, created_by=excluded.created_by",
        (canonical_role_id, alias_text, normalized, source, created_by, confidence, util.now_iso()))


def lookup_alias(conn: sqlite3.Connection, normalized: str) -> Optional[Dict[str, Any]]:
    r = conn.execute(
        "SELECT cr.id AS canonical_role_id, cr.key, cr.label FROM role_alias a "
        "JOIN canonical_role cr ON cr.id=a.canonical_role_id WHERE a.normalized_alias=?",
        (normalized,)).fetchone()
    return dict(r) if r else None


# ───────────────────────────── role_match_cache ───────────────────────────
def cache_get(conn: sqlite3.Connection, title_hash: str) -> Optional[Dict[str, Any]]:
    r = conn.execute(
        "SELECT rmc.canonical_role_id, rmc.method, rmc.score, rmc.normalized_title, cr.key "
        "FROM role_match_cache rmc LEFT JOIN canonical_role cr ON cr.id=rmc.canonical_role_id "
        "WHERE rmc.title_hash=?", (title_hash,)).fetchone()
    return dict(r) if r else None


def cache_put(conn: sqlite3.Connection, title_hash: str, normalized_title: str,
              canonical_role_id: Optional[int], method: str, score: Optional[float]) -> None:
    conn.execute(
        "INSERT INTO role_match_cache (title_hash, normalized_title, canonical_role_id, method, "
        "score, resolved_at) VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(title_hash) DO UPDATE SET canonical_role_id=excluded.canonical_role_id, "
        "method=excluded.method, score=excluded.score, resolved_at=excluded.resolved_at",
        (title_hash, normalized_title, canonical_role_id, method, score, util.now_iso()))


def cache_invalidate(conn: sqlite3.Connection, title_hash: str) -> None:
    conn.execute("DELETE FROM role_match_cache WHERE title_hash=?", (title_hash,))


# ───────────────────────────── ops visibility ─────────────────────────────
def method_distribution(conn: sqlite3.Connection) -> Dict[str, Any]:
    counts = {r["method"]: r["n"] for r in conn.execute(
        "SELECT method, COUNT(*) n FROM role_match_cache GROUP BY method")}
    total = sum(counts.values())
    resolved = counts.get("ALIAS", 0) + counts.get("EMBEDDING", 0)
    return {"counts": counts, "total": total,
            "coverage_pct": round(100.0 * resolved / total, 1) if total else 0.0}


def unresolved_titles(conn: sqlite3.Connection, limit: int = 100) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT normalized_title, score AS best_sim, resolved_at FROM role_match_cache "
        "WHERE method='UNRESOLVED' ORDER BY resolved_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
