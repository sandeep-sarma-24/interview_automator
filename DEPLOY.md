# Deployment Guide — Job Discovery & Application Copilot

Local-first, single-laptop deployment via Docker Compose. One command brings up
the whole system:

```bash
docker compose up -d
```

This starts three containers — **init** (migrate + seed system config), **api**
(FastAPI), and **worker** (discovery → scoring loop) — sharing one persistent
data volume. **Ollama runs on the host**, not in a container; if it is down the
system keeps working on the deterministic fallback scorer.

---

## Architecture at a glance

```
docker compose up -d
   │
   ├─ init    one-shot: app.cli init (schema + migrations + ATS platform rows). Offline.
   │            └─ on success ─┐
   ├─ api ◀──────────────────────┤  uvicorn, published 127.0.0.1:8765 only
   └─ worker ◀───────────────────┘  serialized discovery+scoring loop + daily backup
                                   │
                          scraper_data volume  →  /data
                          (sqlite, resumes, backups, secrets, lock, heartbeat)

   Host Ollama (http://host.docker.internal:11434)  ← optional; graceful fallback
```

- **No service depends on Ollama.** Startup never blocks on it.
- **Company-universe seeding is never automatic** — it is a deliberate command
  (see step 9), so first boot is offline-safe.
- **API is bound to loopback** (`127.0.0.1:8765`). Tailscale/dashboard exposure
  is revisited when the M3 dashboard lands (see end of this doc).

---

## First-time setup on a brand-new machine

This is the exact sequence for setting up the dedicated server laptop.

```bash
# 1. Install Docker (Docker Desktop on macOS, or Docker Engine + Compose v2 on Linux).
#    Verify:
docker --version && docker compose version

# 2. Install Ollama on the HOST (https://ollama.com/download).
#    Verify it is serving:
curl -s http://localhost:11434/api/tags

# 3. Pull the embedding model (improves scoring; optional — fallback works without it):
ollama pull nomic-embed-text

# 4. Configure the project:
cd /path/to/Scraper
cp .env.docker.example .env          # adjust if needed (defaults are fine on Docker Desktop)

# 5. Build and start everything:
docker compose up -d --build
#    Wait for health:
docker compose ps                    # api + worker should become "healthy"

# 6. Create the first candidate (returns an api_token — save it):
curl -s -X POST http://127.0.0.1:8765/candidates \
  -H 'Content-Type: application/json' \
  -d '{"display_name":"Mohit","email":"mohit@you.dev"}'
export TOK=<paste api_token>

# 7. Upload / set the resume + profile (trajectory spec drives scoring):
curl -s -X POST http://127.0.0.1:8765/onboarding/profile -H "X-Candidate-Token: $TOK" \
  -H 'Content-Type: application/json' -d '{
    "total_experience_months":48,
    "core_skills":["python","backend","apis"],
    "acquiring_skills":["llm","ml","ai"],
    "target_roles":["ai product engineer","backend engineer"],
    "avoid_roles":["qa","sales"],
    "target_domain_signals":["llm","ml","ai"],
    "remote_required":false,"current_ctc":2000000}'
curl -s -X POST http://127.0.0.1:8765/onboarding/resume -H "X-Candidate-Token: $TOK" \
  -H 'Content-Type: application/json' -d '{"label":"Backend SDE","target_role":"backend engineer","content_text":"...resume text..."}'

# 8. Add company preferences (PREFERRED / NEUTRAL / AVOID / BLOCKED):
curl -s -X POST http://127.0.0.1:8765/preferences -H "X-Candidate-Token: $TOK" \
  -H 'Content-Type: application/json' -d '{"company":"Infosys","preference":"BLOCKED"}'

# 9. Seed the company universe (MANUAL, network — verifies board tokens live):
docker compose run --rm api python -m app.cli seed-companies

# 10. Verify discovery + scoring end to end:
docker compose run --rm api python -m app.cli discover-companies --limit 3
docker compose run --rm api python -m app.cli score
curl -s "http://127.0.0.1:8765/feed?states=SHORTLISTED&limit=5" -H "X-Candidate-Token: $TOK"
```

After this, the **worker** keeps discovering + scoring on its interval
(`WORKER_INTERVAL`, default 1800s) and takes a daily DB backup automatically.

---

## Everyday operations

```bash
docker compose up -d                  # start (after reboot it auto-starts: restart=unless-stopped)
docker compose ps                     # health states
docker compose logs -f worker         # follow worker
docker compose logs -f api
docker compose restart worker         # reload after a config change
docker compose down                   # stop (data volume preserved)
docker compose down -v                # stop AND delete data  ⚠ destroys the DB

# Manual one-shots (run in an ephemeral container that shares the data volume):
docker compose run --rm api python -m app.cli seed-companies
docker compose run --rm api python -m app.cli discover-companies --platforms GREENHOUSE --limit 5
docker compose run --rm api python -m app.cli backup
docker compose run --rm api python -m app.cli manual https://boards.greenhouse.io/acme/jobs/123
```

### Development mode (hot reload, source-mounted)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```
- `api` runs `uvicorn --reload` watching the bind-mounted `./app`.
- `worker` uses a 120s cycle for fast feedback.

---

## Verification checklist

| Check | Command | Expect |
|---|---|---|
| Containers healthy | `docker compose ps` | `api`, `worker` = `healthy`; `init` = `exited (0)` |
| API + DB | `curl 127.0.0.1:8765/health` | `{"status":"ok","db":"ok"}` (200) |
| Worker heartbeat | `docker compose exec worker python -m app.cli healthcheck --worker` | exit 0 |
| Platforms seeded | `docker compose run --rm api python -m app.cli discover-companies --limit 0` | runs without error |
| Persistence | `docker compose down && docker compose up -d` | data still present |
| Ollama (optional) | `curl localhost:11434/api/tags` | model list; if down, scoring logs `fallback` |

---

## Data & persistence

Everything important lives in the **`scraper_data`** named volume, mounted at `/data`:

```
/data/copilot.sqlite        the database (candidates, profiles, prefs, jobs, scores, registry)
/data/resumes/              uploaded resume files
/data/backups/              daily DB snapshots (single-file .sqlite)
/data/secrets/              Gmail OAuth credentials + token (optional)
/data/worker.lock           heavy-resource fcntl lock
/data/worker.heartbeat      worker liveness marker
```

`docker compose down` keeps the volume; only `down -v` deletes it. **For true
durability, copy `/data/backups` (and `/data/resumes`) off the laptop** — a
single SSD is still a single point of failure. To inspect a backup:

```bash
docker run --rm -v job-copilot_scraper_data:/data alpine ls -la /data/backups
```

### Optional: Gmail discovery
Gmail OAuth is interactive, so run it on the **host** and copy the token in:
```bash
# on host (one-time): python -m app.cli gmail-auth   -> produces token json
docker cp gmail_credentials.json $(docker compose ps -q api):/data/secrets/
docker cp gmail_token.json       $(docker compose ps -q api):/data/secrets/
```
ATS company discovery works without Gmail.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `api`/`worker` never start | `init` failed | `docker compose logs init` — usually a volume permission or disk issue |
| `/health` returns 503 | DB unreachable inside container | check the `scraper_data` volume is mounted; `docker compose logs api` |
| Worker shows `unhealthy` | first cycle still running, or hung | normal during a long first load (≤ start_period 120s + cycle); if persistent, `docker compose logs worker` |
| Scoring logs `fallback` not `ollama` | host Ollama down or model missing | `curl localhost:11434/api/tags`; `ollama pull nomic-embed-text`. **Not an error — system still scores.** |
| `host.docker.internal` unresolved (Linux) | older Docker | the compose `extra_hosts: host-gateway` handles it; ensure Compose v2 |
| Discovery finds nothing | universe not seeded | run step 9 (`seed-companies`) — it is intentionally manual |
| Many companies auto-disabled | board tokens didn't resolve | expected for a few; check `discovery_run` / `company_ats.disabled_reason` |
| Permission denied on `/data` | volume pre-created as root | use a fresh named volume (it inherits the image's uid 10001), or `chown -R 10001:10001` the volume |
| Port 8765 in use | another process | set `HOST_API_PORT` in `.env` |

Logs are captured by Docker (`json-file`, rotated at 10 MB × 3). View with
`docker compose logs`. There is no separate log volume by design.

---

## Resource profile (Ryzen 5 5600H / 8 GB)

| Container | mem_limit | Notes |
|---|---|---|
| init | 256m | one-shot |
| api | 512m | read-mostly FastAPI |
| worker | 768m | discovery + scoring (embeddings run in **host** Ollama, not here) |

Total cap ≈ 1.5 GB, leaving ample headroom; host Ollama uses its own memory
(`nomic-embed-text` is small). `restart: unless-stopped` keeps api/worker up
24×7 and across reboots.

---

## Security notes

- Runs as **non-root** (uid 10001) inside the image; the data volume inherits
  that ownership.
- **No secrets in the image or compose** — overrides come from `.env`
  (git-ignored); Gmail credentials live only in the `/data/secrets` volume.
- API is published on **`127.0.0.1` only**. Do not change to `0.0.0.0` on the
  host until access is fronted by Tailscale + auth.

---

## Future: M3 Dashboard Integration (documentation only — not implemented)

Today the API surface is **FastAPI + Swagger** (`/docs`) plus JSON endpoints
(onboarding, preferences, ranked `/feed`, application detail). It is sufficient
to drive the system via curl and to validate discovery + scoring quality.

When **M3** is built, this deployment will grow a human-interaction layer:

- **Dashboard UI** — the mobile-first "decision device": counts-first triage,
  ranked feed with `±` match-explanation signals.
- **Review Queue** — Gate #1 ("pursue this job?") over the shortlist.
- **Job Approval** — Gate #2: approve the exact `application_preview` payload
  (hash-bound), plus the missing-information answer loop.
- **Application Assistant** — the laptop "execution device": the batch
  Submission Session that opens prepared applications for human-guided submit
  (Gate #3), arriving with the later ATS-assisted milestones.

Deployment implications to revisit at M3:
- **Network exposure**: front the API with **Tailscale** (and app-level auth)
  so the dashboard is reachable from a phone — at which point the
  `127.0.0.1`-only binding is widened deliberately, not before.
- Likely a small **static/SPA** served by the API container (or a sidecar), and
  SSE for the live submit screen.

No code changes are implied here — this is a forward note so the deployment
topology is ready to evolve when M3 work begins.
