# Job Copilot — M3 Review Dashboard (frontend)

Mobile-first React SPA for the M3 review workflow: onboard a candidate, see
trajectory-ranked jobs, understand *why* each scored as it did, and triage them
(INTERESTED / NOT_INTERESTED / BOOKMARK / WRONG_MATCH). The verdict drives the
backend state machine and collects calibration data.

**Stack:** React 18 + TypeScript + Vite + Tailwind + TanStack Query.
**Auth:** per-candidate token (`X-Candidate-Token`), stored in `localStorage`,
Tailscale-gated. **Same-origin** with the API under `/api`.

## Develop

Requires Node 18+ and the backend running on `:8765`.

```bash
# 1. start the backend (in the repo root)
.venv/bin/python -m app.cli serve         # or: docker compose up -d

# 2. start the frontend (here)
cd frontend
npm install
npm run dev                                # http://localhost:5173 (proxies /api -> :8765)
```

Override the proxy target if the backend isn't on localhost:
`VITE_API_TARGET=http://host:8765 npm run dev`.

## Build (static)

```bash
npm run build      # type-checks (tsc -b) then emits ./dist
npm run preview    # serve the build locally
```

In production the `dist/` bundle is served by FastAPI as static files — that
wiring (and the Docker build stage) is a **separate deployment step**, kept out
of this milestone deliberately. No Node runs in production.

## Structure

```
src/
  lib/        apiClient (token-injecting fetch), types (mirror API contracts), queryKeys, format
  auth/       AuthContext + RequireAuth + RequireProfile guards
  hooks/      one hook per resource (TanStack Query queries + mutations)
  components/ AppShell, TabBar, job/* (JobCard, badges, signals, verdicts), forms/*
  pages/      Login, Onboarding, Dashboard, Review, ApplicationDetail, Companies, Diagnostics, You
```

## Routes

`/login · /onboarding` (public) — then the tab shell: `/` Dashboard ·
`/review` + `/review/:id` · `/companies` · `/diagnostics` · `/you`.

## Notes
- **Match explanation is the hero** — the `±` signals and trajectory badge lead;
  the score is a supporting stat.
- Signals use **glyph + color** (`+ − ~`), never color alone (accessibility).
- The feed is paginated (`limit`/`offset`); filters live in the URL.
- Graceful degradation: if Ollama is down the backend scores via fallback; the
  UI just shows whatever the DB holds.
