"""M4-P1 first-slice tests: normalization, taxonomy seed, resolver
(alias/embedding/unresolved), cache, and ops visibility."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.app import app
from app.db.connection import transaction
from app.roles.normalize import normalize_role
from app.roles.resolver import RoleResolver
from app.roles.seed import seed_roles
from app.repositories import roles as roles_repo
from app import util

client = TestClient(app)
OPS = {"X-Ops-Token": "test-ops-token"}


class FakeProvider:
    def __init__(self, available: bool, vec=None):
        self.available = available
        self.model = "fake"
        self._vec = vec

    def embed(self, _text: str):
        return self._vec


def _seed():
    seed_roles(embed=False)


def test_normalize_seniority():
    assert normalize_role("Senior Software Engineer II") == "software engineer"
    assert normalize_role("Staff Backend Engineer, Payments") == "backend engineer"
    assert normalize_role("Backend Engineer (Remote)") == "backend engineer"
    assert normalize_role("Sr. SDE I") == "sde"


def test_seed_idempotent_and_generic_parent():
    _seed()
    r2 = seed_roles(embed=False, reset=True)
    assert r2["roles"] == 8
    with transaction() as conn:
        # "software development engineer" -> Generic SE (NOT Backend)
        a = roles_repo.lookup_alias(conn, "software development engineer")
        assert a and a["key"] == "software_engineer_generic"
        # Backend has no "software engineer" alias
        b = roles_repo.lookup_alias(conn, "software engineer")
        assert b["key"] == "software_engineer_generic"


def test_resolver_alias():
    _seed()
    r = RoleResolver(provider=FakeProvider(available=False))
    res = r.resolve("Senior Backend Developer")
    assert res["method"] == "ALIAS" and res["canonical_key"] == "backend_engineer"
    res2 = r.resolve("Software Development Engineer")
    assert res2["canonical_key"] == "software_engineer_generic"


def test_resolver_unresolved_when_no_embeddings():
    _seed()
    r = RoleResolver(provider=FakeProvider(available=False))
    res = r.resolve("Underwater Basket Weaver")
    assert res["method"] == "UNRESOLVED" and res["canonical_key"] is None
    # one event recorded for this distinct title
    with transaction() as conn:
        n = conn.execute("SELECT COUNT(*) FROM ops_event WHERE action='role_unresolved' "
                         "AND source='UNRESOLVED'").fetchone()[0]
    assert n >= 1


def test_resolver_embedding_and_cache():
    _seed()
    # give two canonicals deterministic vectors; fake provider returns the backend vector
    with transaction() as conn:
        roles_repo.set_canonical_embedding(conn, "backend_engineer", [1.0, 0.0, 0.0], "fake")
        roles_repo.set_canonical_embedding(conn, "frontend_engineer", [0.0, 1.0, 0.0], "fake")
    r = RoleResolver(provider=FakeProvider(available=True, vec=[1.0, 0.0, 0.0]))
    res = r.resolve("Distributed Systems Wizard")     # not an alias -> embedding
    assert res["method"] == "EMBEDDING" and res["canonical_key"] == "backend_engineer"
    assert res["score"] >= 0.80
    # second resolve = cache hit (no re-embed)
    res2 = r.resolve("Distributed Systems Wizard")
    assert res2["cached"] is True and res2["canonical_key"] == "backend_engineer"


def test_api_roles_auth():
    _seed()
    assert client.get("/api/roles").status_code == 401  # candidate auth required
    tok = client.post("/api/candidates", json={"display_name": "r", "email": "r@t"}).json()["api_token"]
    roles = client.get("/api/roles", headers={"X-Candidate-Token": tok}).json()
    assert len(roles) == 8
    rr = client.get("/api/roles/resolve", headers={"X-Candidate-Token": tok},
                    params={"title": "Backend Developer"}).json()
    assert rr["canonical_key"] == "backend_engineer"


def test_ops_role_visibility_and_learned_alias():
    _seed()
    r = RoleResolver(provider=FakeProvider(available=False))
    r.resolve("Totally Novel Role Title")  # -> UNRESOLVED, cached
    methods = client.get("/api/ops/roles/methods", headers=OPS).json()
    assert "counts" in methods and methods["total"] >= 1

    unresolved = client.get("/api/ops/roles/unresolved", headers=OPS).json()["items"]
    assert any("novel" in u["normalized_title"] for u in unresolved)

    # operator teaches a LEARNED alias -> title now resolves ALIAS
    add = client.post("/api/ops/roles/aliases", headers=OPS,
                      json={"title": "Totally Novel Role Title", "canonical_key": "backend_engineer"})
    assert add.status_code == 201
    res = RoleResolver(provider=FakeProvider(available=False)).resolve("Totally Novel Role Title")
    assert res["method"] == "ALIAS" and res["canonical_key"] == "backend_engineer"

    # bad canonical key -> 404
    assert client.post("/api/ops/roles/aliases", headers=OPS,
                       json={"title": "x", "canonical_key": "nope"}).status_code == 404
