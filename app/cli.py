"""Unified CLI. Every subcommand is independently runnable (graceful degradation):

    python -m app.cli migrate          # create/upgrade the schema (idempotent)
    python -m app.cli seed             # demo candidate + sample jobs (local testing)
    python -m app.cli discover         # run discovery sources (Gmail, ...)
    python -m app.cli manual <url>     # MANUAL_DISCOVERY: add one job by URL
    python -m app.cli score [--candidate ID]
    python -m app.cli worker [--interval 1800] [--once]
    python -m app.cli serve [--host 127.0.0.1] [--port 8765]
    python -m app.cli backup
    python -m app.cli gmail-auth       # one-time Gmail OAuth consent
"""
from __future__ import annotations

import argparse
import json
import sys

from app.config import get_settings


def _print(obj) -> None:  # noqa: ANN001
    print(json.dumps(obj, indent=2, default=str))


def cmd_migrate(_args) -> None:  # noqa: ANN001
    from app.db.connection import apply_schema
    apply_schema()
    _print({"status": "ok", "db": str(get_settings().db_path)})


def cmd_init(_args) -> None:  # noqa: ANN001
    """First-boot, offline-safe: schema/migrations + mandatory ATS platform rows.

    Idempotent. Does NOT seed the company universe (that is a deliberate,
    network-dependent manual step: `seed-companies`)."""
    from app.db.connection import apply_schema
    from app.discovery.ats.seed import seed_platforms
    apply_schema()
    seed_platforms()
    _print({"status": "ok", "db": str(get_settings().db_path), "platforms_seeded": True})


def cmd_healthcheck(args) -> None:  # noqa: ANN001
    """Exit 0 healthy / 1 unhealthy. Used by container HEALTHCHECK."""
    from app.core import health
    detail = {"db": "ok" if health.db_ok() else "unreachable"}
    healthy = detail["db"] == "ok"
    if args.worker:
        age = health.heartbeat_age_seconds()
        fresh = age is not None and age <= args.max_age
        detail["heartbeat_age_s"] = round(age, 1) if age is not None else None
        detail["heartbeat_fresh"] = fresh
        healthy = healthy and fresh
    print(json.dumps(detail))
    sys.exit(0 if healthy else 1)


def cmd_seed(_args) -> None:  # noqa: ANN001
    from app.db.connection import apply_schema, transaction
    from app.repositories import candidates as C, jobs as J, preferences as P
    from app import util
    apply_schema()
    with transaction() as conn:
        row = conn.execute("SELECT * FROM candidate WHERE email=?", ("demo@local",)).fetchone()
        if row:
            cand = dict(row)
        else:
            cand = C.create_candidate(conn, "Demo Candidate", "demo@local")
            C.create_profile_version(conn, cand["id"], {
                "total_experience_months": 48,
                "core_skills_json": util.dumps(["python", "backend", "payments", "apis"]),
                "acquiring_skills_json": util.dumps(["llm", "ml", "ai product"]),
                "target_roles_json": util.dumps(["ai product engineer", "backend engineer"]),
                "acceptable_roles_json": util.dumps(["platform engineer", "applied ai"]),
                "avoid_roles_json": util.dumps(["qa", "manual testing", "sdet"]),
                "target_domain_signals_json": util.dumps(["llm", "rag", "agents", "ai product"]),
                "location_prefs_json": util.dumps({"cities": ["bangalore", "gurgaon"]}),
                "remote_required": 0, "current_ctc": 2000000})
            P.set_preference(conn, cand["id"], "Stripe", "PREFERRED")
            P.set_preference(conn, cand["id"], "Infosys", "BLOCKED")
            samples = [
                ("Datadog", "AI Product Engineer",
                 "Build LLM-powered AI products with Python. RAG, agents, applied AI. 2+ years. " * 6, 1, "Remote"),
                ("HashiCorp", "Backend Engineer",
                 "Scalable backend APIs in Python at a strong product company. 3-6 years. " * 6, 1, "Remote"),
                ("BigCo", "Senior QA Automation Lead",
                 "Lead manual testing / SDET automation QA. 6+ years in quality assurance. " * 6, 0, "Bangalore"),
                ("Infosys", "AI Product Engineer", "LLM AI product role. " * 8, 1, "Remote"),
            ]
            for company, title, desc, remote, loc in samples:
                comp = J.get_or_create_company(conn, company)
                J.upsert_job(conn, comp["id"], util.sha256_hex(company, title, loc), {
                    "source": "MANUAL", "discovery_method": "MANUAL", "title": title,
                    "description_text": desc, "is_remote": remote, "location": loc,
                    "signal_density": "RICH"})
    from app.scoring.service import run_scoring
    report = run_scoring(cand["id"])
    _print({"candidate_id": cand["id"], "api_token": cand["api_token"], "scoring": report})


def cmd_discover(_args) -> None:  # noqa: ANN001
    from app.discovery.service import run_discovery
    _print(run_discovery())


def cmd_seed_companies(args) -> None:  # noqa: ANN001
    from app.db.connection import apply_schema
    from app.discovery.ats.seed import seed_companies
    apply_schema()
    _print(seed_companies(verify=not args.no_verify))


def cmd_discover_companies(args) -> None:  # noqa: ANN001
    from app.discovery.ats.runner import run_company_discovery
    platforms = [p.strip().upper() for p in args.platforms.split(",")] if args.platforms else None
    _print(run_company_discovery(platform_keys=platforms, limit=args.limit))


def cmd_manual(args) -> None:  # noqa: ANN001
    from app.discovery.service import add_manual_url
    _print(add_manual_url(args.url))


def cmd_seed_roles(args) -> None:  # noqa: ANN001
    from app.db.connection import apply_schema
    from app.roles.seed import seed_roles
    apply_schema()
    _print(seed_roles(embed=not args.no_embed, reset=args.reset))


def cmd_embed_roles(_args) -> None:  # noqa: ANN001
    from app.roles.seed import embed_roles
    _print({"embedded": embed_roles()})


def cmd_resolve_titles(args) -> None:  # noqa: ANN001
    from app.db.connection import transaction
    from app.roles.resolver import resolve_titles
    with transaction() as conn:
        rows = conn.execute(
            "SELECT DISTINCT title FROM job ORDER BY discovered_at DESC LIMIT ?",
            (args.limit,)).fetchall()
    _print(resolve_titles([r["title"] for r in rows]))


def cmd_score(args) -> None:  # noqa: ANN001
    from app.scoring.service import run_scoring
    _print(run_scoring(candidate_id=args.candidate))


def cmd_rescore(args) -> None:  # noqa: ANN001
    from app.scoring.service import rescore
    _print(rescore(candidate_id=args.candidate))


def cmd_worker(args) -> None:  # noqa: ANN001
    from app.core.worker import run_worker
    run_worker(interval_seconds=args.interval, once=args.once)


def cmd_serve(args) -> None:  # noqa: ANN001
    import uvicorn
    s = get_settings()
    uvicorn.run("app.api.app:app", host=args.host or s.api_host,
                port=args.port or s.api_port, log_level="info")


def cmd_backup(_args) -> None:  # noqa: ANN001
    from app.core.backup import run_backup
    _print(run_backup())


def cmd_prune(_args) -> None:  # noqa: ANN001
    from app.core.telemetry import prune_telemetry
    _print(prune_telemetry())


def cmd_gmail_auth(_args) -> None:  # noqa: ANN001
    from app.discovery.email_gmail import authorize_interactive
    path = authorize_interactive()
    _print({"status": "ok", "token": path})


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="app.cli", description="Job copilot CLI")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("migrate").set_defaults(func=cmd_migrate)
    sub.add_parser("init").set_defaults(func=cmd_init)
    sub.add_parser("seed").set_defaults(func=cmd_seed)
    sub.add_parser("discover").set_defaults(func=cmd_discover)

    sr = sub.add_parser("seed-roles")
    sr.add_argument("--no-embed", action="store_true", help="skip canonical embeddings")
    sr.add_argument("--reset", action="store_true", help="wipe role tables before seeding")
    sr.set_defaults(func=cmd_seed_roles)
    sub.add_parser("embed-roles").set_defaults(func=cmd_embed_roles)
    rt = sub.add_parser("resolve-titles")
    rt.add_argument("--limit", type=int, default=5000)
    rt.set_defaults(func=cmd_resolve_titles)

    hc = sub.add_parser("healthcheck")
    hc.add_argument("--worker", action="store_true",
                    help="also require a fresh worker heartbeat")
    hc.add_argument("--max-age", type=float, default=4000.0,
                    help="max heartbeat age in seconds before unhealthy")
    hc.set_defaults(func=cmd_healthcheck)

    scs = sub.add_parser("seed-companies")
    scs.add_argument("--no-verify", action="store_true",
                     help="skip board-token auto-verification")
    scs.set_defaults(func=cmd_seed_companies)

    dcs = sub.add_parser("discover-companies")
    dcs.add_argument("--platforms", default=None, help="comma list e.g. GREENHOUSE,LEVER")
    dcs.add_argument("--limit", type=int, default=1000, help="max boards per platform")
    dcs.set_defaults(func=cmd_discover_companies)

    m = sub.add_parser("manual"); m.add_argument("url"); m.set_defaults(func=cmd_manual)

    sc = sub.add_parser("score")
    sc.add_argument("--candidate", type=int, default=None)
    sc.set_defaults(func=cmd_score)

    rs = sub.add_parser("rescore")  # re-score existing applications with rules-v2-canonical
    rs.add_argument("--candidate", type=int, default=None)
    rs.set_defaults(func=cmd_rescore)

    w = sub.add_parser("worker")
    w.add_argument("--interval", type=int, default=1800)
    w.add_argument("--once", action="store_true")
    w.set_defaults(func=cmd_worker)

    sv = sub.add_parser("serve")
    sv.add_argument("--host", default=None)
    sv.add_argument("--port", type=int, default=None)
    sv.set_defaults(func=cmd_serve)

    sub.add_parser("backup").set_defaults(func=cmd_backup)
    sub.add_parser("prune").set_defaults(func=cmd_prune)
    sub.add_parser("gmail-auth").set_defaults(func=cmd_gmail_auth)
    return p


def main(argv=None) -> int:  # noqa: ANN001
    import logging
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
