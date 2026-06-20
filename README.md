# Job Discovery & Application Copilot — Sprint 1 (M0 + M1 + M2)

A **local-first, anti-ban, human-guided** job discovery & application copilot for
a dedicated laptop (Ryzen 5 5600H / 8 GB / 24×7). It is **not** an autonomous
apply bot — human approval and human-guided submission are mandatory by design.

**Sprint 1 ships the value chain that needs no browser automation and no LLM
generation model:**

```
discovery (email alerts + manual URL)  →  scoring (trajectory-first)  →  ranked feed (API)
```

At the end of Sprint 1 you can onboard a candidate, ingest jobs with **zero ban
risk**, and get a **career-trajectory-ranked** list back. The mobile review
dashboard, resume preparation, and Playwright-assisted applying come in later
milestones (M3+). See `docs`/design history for the full roadmap.

> Why this ordering: discovery + scoring + review are the real risk. Playwright
> (highest ban risk, highest maintenance) is deferred to M7. Validate that the
> rankings make you say *"yes, I'd genuinely apply to this"* before automating.

---

## What's in Sprint 1

| Milestone | Delivered |
|---|---|
| **M0** foundation | SQLite (STRICT/WAL/FK) schema, single-worker loop, per-candidate auth + isolation, nightly DB backup, onboarding wizard (trajectory spec), company-preference model, CLI, launchd services |
| **M1** discovery | Gmail OAuth ingestion of LinkedIn/Naukri/Indeed **job-alert emails** (no scraping), **manual paste-URL** discovery, normalization + canonical-URL dedup |
| **M2** scoring | Stage 0 hard filters → Stage 1 embeddings (Ollama `nomic-embed-text`, with deterministic fallback) → Stage 2 deterministic rules; trajectory-first weights, company-preference adjustment, `±` signal explanations, LEAP override |
| **M1.5** company discovery | Greenhouse + Lever public-API discovery (discovery-only); company registry (`ats_platform`/`company_ats`/`discovery_run`); tier scheduling + conditional GET + per-domain rate limiting; config-driven role filter (KEEP/SOFT_DROP/DROP); ATS-wins cross-source dedup; health auto-disable; Wave-1 universe seeder with board-token auto-verification |

**Explicitly NOT in Sprint 1** (later milestones): browser automation, the
review/approval dashboard, resume selection/preparation, LLM-written
explanations, Greenhouse/Lever API discovery.

---

## Setup

Requires Python 3.9+ and SQLite ≥ 3.37 (both present on recent macOS).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt        # add requirements-dev.txt for tests
cp .env.example .env                              # then edit paths
.venv/bin/python -m app.cli migrate               # create the database
```

### Optional: Ollama embeddings (recommended, not required)
```bash
ollama pull nomic-embed-text        # if Ollama is missing, scoring uses a token-overlap fallback
```

### Optional: Gmail discovery (one-time)
1. Create a **dedicated Gmail account** for job alerts; route LinkedIn/Naukri/Indeed
   alerts to it (set up the alerts on those sites).
2. In Google Cloud, enable the Gmail API and download a **Desktop OAuth client**
   to the path in `SCRAPER_GMAIL_CREDENTIALS`.
3. Authorize once:
   ```bash
   .venv/bin/python -m app.cli gmail-auth
   ```

---

## Quick start (local demo)

```bash
.venv/bin/python -m app.cli seed       # demo candidate + sample jobs + scores; prints an api_token
.venv/bin/python -m app.cli serve      # API at http://127.0.0.1:8765
```

Use the printed token:
```bash
TOK=<api_token>
curl -s localhost:8765/feed -H "X-Candidate-Token: $TOK" | python3 -m json.tool
```

You'll see the **trajectory inversion** in action: a remote AI Product Engineer
role outranks a higher-paying Senior QA Lead, and a BLOCKED company is filtered
out entirely.

---

## CLI

```
migrate         create/upgrade schema (idempotent)
seed            demo candidate + sample jobs (local testing)
discover        run email/manual discovery sources (Gmail, ...)
manual <url>    add one job by URL (MANUAL_DISCOVERY)
seed-companies [--no-verify]        seed Wave-1 universe + auto-verify board tokens
discover-companies [--platforms GREENHOUSE,LEVER] [--limit N]   ATS company discovery
score [--candidate ID]
worker [--interval 1800] [--once]   serialized discovery -> scoring loop + daily backup
serve [--host --port]
backup
gmail-auth      one-time Gmail OAuth consent
```

## API (all data-mutating/reading routes need `X-Candidate-Token`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/candidates` | bootstrap a candidate (returns token) |
| POST | `/onboarding/profile` | set trajectory spec (new profile version) |
| POST | `/onboarding/resume` | upsert a versioned resume |
| GET  | `/me` | candidate + profile summary |
| POST | `/preferences` | set company PREFERRED/NEUTRAL/AVOID/BLOCKED |
| GET  | `/preferences` | list preferences |
| GET  | `/feed` | ranked applications (`?states=&search=&limit=`) |
| GET  | `/applications/{id}` | one application + score signals (ownership-scoped) |
| POST | `/jobs/manual` | paste-URL discovery |
| POST | `/actions/score` | score this candidate now (worker does this in prod) |

---

## How scoring works (M2)

Per candidate × job, after onboarding's **trajectory spec**:

- **Stage 0 — hard filters** (no LLM): BLOCKED company; remote gate (if required);
  **seniority/total-years** experience gate. *Domain experience the candidate is
  acquiring (e.g. ML) is never gated* — it becomes a flagged "stretch" signal, so
  transition roles survive.
- **Stage 1 — embeddings**: job text vs the candidate's target-role profile,
  cosine via Ollama `nomic-embed-text`; **falls back to token overlap** if Ollama
  is down (degrade, don't fail).
- **Stage 2 — deterministic rules**: weighted dimensions
  **trajectory 0.45 / skills 0.20 / location 0.15 / experience 0.15 / salary 0.05**,
  then a company-preference adjustment. Missing salary is **neutral, never penalized**.
- **LEAP override**: any role classified as a leap toward the target is always
  shortlisted (high recall), labelled with warnings + a confidence value.

Each score stores `± signals` (e.g. `+Strong move toward AI Product · +Python ·
−No salary data`) — the explanation matters more than the number.

---

## Architecture notes

- **Local-first, single laptop.** SQLite + bare venv + launchd; no Docker (RAM).
- **Independently runnable, gracefully degrading services**: discovery works
  without scoring; scoring works without the dashboard; the API serves whatever
  is in the DB even if Gmail/Ollama are down.
- **Single worker, serialized** under a heavy-resource file lock (only one heavy
  op at a time on 8 GB; no leasing in V1 by design).
- **Per-candidate isolation** enforced server-side (Tailscale secures the path,
  not the tenant boundary).
- **Backups** run daily to `data/backups/`; sync that + `data/resumes/`
  off-laptop for real durability.

Run `cp deploy/launchd/*.plist ~/Library/LaunchAgents/` (after editing paths) to
run the API + worker 24×7 — see `deploy/launchd/README.md`.

## Tests

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```
