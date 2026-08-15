# RationAI — Intelligent Ration & Food Security Intelligence Platform

**RationAI converts public-distribution-system (PDS) operational data into
actionable intelligence** — a deterministic analytics + multi-agent AI
pipeline that detects anomalies, quantifies inventory risk, raises early
warnings, simulates what-if scenarios, and produces auditable intelligence
reports. Every insight is traceable to its source data.

> Status: **READY FOR DEMO** — see [Known limitations](#known-limitations)
> for the honest boundaries (no live government API, optional LLM).

---

## Problem

Public distribution systems generate large amounts of operational data, but
identifying supply risks, anomalies, and emerging shortages is difficult and
reactive. Analysts drown in spreadsheets; alerts arrive too late; and nobody
can say *why* a number matters or *where* it came from.

## Solution

RationAI turns that data into a **decision-intelligence workflow**:

```
Data → Analytics → AI → Evidence → Alerts → Simulation → Action
```

Not a chatbot. A deterministic core (aggregations, risk thresholds,
percentages, evidence) with an optional AI layer (interpretation, summaries,
recommendations) on top — and full lineage from source → import → analysis →
insight → alert → report.

## Features (by phase)

| Area | What it does |
|------|--------------|
| **Ingestion** (P3–4) | CSV / XLSX / JSON upload → mapping → validation → normalization → duplicate handling → transactional import (50k+ rows/sec-scale; 500k row cap) |
| **Analytics** (P5) | Distribution, inventory coverage, demand, district/FPS views, operational alerts — all computed server-side from the database |
| **Multi-agent AI** (P6, 9) | Four agents: transaction analyst → anomaly investigator → evidence case builder → alert generator. Deterministic calculations; LLM only writes human-readable narrative (opt-in) |
| **Data sources & pipeline** (P7–8) | Connector architecture for external sources, source status (CONNECTOR_READY / NOT_CONNECTED / ACTIVE), import history, pipeline stages, data quality, freshness |
| **Decision support** (P10) | Deterministic what-if simulation (demand ±%, supply delay, inventory change) with AI interpretation — never writes to real data |
| **Early warning** (P11) | Configurable alert rules, deduplication, lifecycle (OPEN → ACKNOWLEDGED → RESOLVED / DISMISSED), notification bell |
| **Command Center** (P12) | Executive KPIs with previous-period comparison, risk overview, district/FPS risk, trends, AI insights, top alerts, recommended actions |
| **Reports** (P12) | Auditable intelligence reports (JSON/CSV export), never overwritten, full lineage |
| **UI/UX** (P13) | Design tokens, sectioned sidebar, ⌘K command palette, data-status chip, toasts, reduced-motion support |
| **Security** (P14) | Opt-in token auth, same-origin CORS, security headers, rate limiting, audit log, import rollback, secret hygiene |
| **QA** (P15) | 456 tests (unit/integration/API/database/AI-evaluation/E2E/security), AI evaluation scorecard, performance baselines |

## Architecture

```
                 USER (browser)
                       │
                       ▼
              RATIONAI API  (Python stdlib HTTP server)
                       │
        ┌──────────────┼──────────────────┐
        ▼              ▼                  ▼
   SQLite DB      OpenAI-compatible   External data
   (analytics,     API (optional,      connectors
    alerts,          server-side)      (Phase 7/8)
    reports)                            │
                       │                ▼
                       │          DATA SOURCES
        ┌──────────────┴───────────────┐
        ▼                              ▼
   ANALYTICS SERVICES            AI AGENTS (4)
   (aggregations, risk,         (detect → verify →
    freshness, quality)          evidence → alert)
        │                              │
        ▼                              ▼
   COMMAND CENTER (orchestration view) ──► REPORTS / EXPORT
```

Full details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Tech stack

- **Backend**: Python 3.9+ standard library only — `http.server` API, `sqlite3`
  database, `urllib` for the OpenAI-compatible chat API. **Zero third-party
  runtime dependencies.**
- **Frontend**: vanilla HTML/CSS/JS (no build step, no framework).
- **Database**: SQLite (schema auto-created on first open — no separate
  migration step).
- **AI**: any OpenAI-compatible endpoint (OpenAI or OpenRouter), opt-in,
  server-side key only.

## Quick start

Requirements: Python 3.9+ (nothing else — no pip install needed).

```bash
# 1. Get the code
git clone <repo> && cd RationAI          # (or copy the folder)

# 2. Configure environment (optional; everything has safe defaults)
cp .env.example .env                     # then edit with your own values

# 3. Create/seed the database
python3 scripts/seed_database.py         # demo dataset (deterministic, idempotent)

# 4. Start the backend (serves the API + static frontend)
python3 server.py                        # → http://127.0.0.1:8000

# 5. Open the Command Center
#    http://127.0.0.1:8000/#/command

# 6. Import a real dataset
#    Data → Import Data → upload CSV/XLSX/JSON → validate → import
```

Optional flags: `--port`, `--host`, `--db <path>`, `--dataset <path>`.
`RATIONRIGHT_DB_PATH` env var is honored by `server.py`.

### AI configuration (optional)

The platform works fully with deterministic output and no key. To enable
LLM-written narratives:

```bash
export RATIONRIGHT_LLM_ENABLED=1
export OPENAI_API_KEY=sk-...            # server-side only — never in the browser
# export RATIONRIGHT_LLM_BASE_URL=https://openrouter.ai/api/v1   # for OpenRouter
python3 server.py
```

Any AI failure degrades gracefully to the deterministic templates — the demo
never breaks because of the model.

### Authentication (optional)

```bash
export RATIONRIGHT_AUTH_TOKEN=change-me
export RATIONRIGHT_SESSION_SECRET=change-me-too
python3 server.py                        # UI shows a sign-in overlay
```

## Database

- Schema is created automatically on first open (`database.open_db`), with
  migrations applied idempotently (Phase 2–14 tables). Fresh DB, existing DB,
  and upgrades are all safe — verified in the test suite.
- Seed: `python3 scripts/seed_database.py` (synthetic demo dataset, labeled
  "Synthetic Demo Data"; idempotent — re-running resets only the synthetic
  source's rows).
- Demo database used in screenshots: `data/rationright.db` (imported datasets,
  alerts, insights, reports from the demo flow).

## Testing

```bash
python3 -m unittest discover -s tests -t .        # 456 tests, all green
```

Coverage of the suites: unit (agents, workflow, llm), database, ingestion,
analytics, API contract, command center, monitoring, simulation, security
(Phase 14), QA audit (Phase 15), AI evaluation scorecard, full end-to-end
flow. See [QA_REPORT.md](QA_REPORT.md) for the full results.

## Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — environment configuration,
production considerations (headers, CORS, auth, rate limits, backups), and
the release checklist.

## Known limitations

- **No live government API.** The Phase 7 connector for official PDS data is
  `CONNECTOR READY / NOT CONNECTED` — it is never shown as live. All demo data
  is imported or synthetic and clearly labeled.
- **AI is optional and external.** Narratives depend on an OpenAI-compatible
  endpoint; deterministic output is always the fallback. No AI accuracy
  percentage is claimed.
- **Single-operator scope.** The optional auth is a single shared access
  token, not multi-user role management — by design for the demo scope.
- **SQLite.** Suitable for the demo and small deployments; a client-server
  database is future work.
- See [docs/LIMITATIONS.md](docs/LIMITATIONS.md) and
  [docs/ROADMAP.md](docs/ROADMAP.md) for the full list and future work.

## Demo

A complete, repeatable 6-minute demo script (exact click path, expected
behavior, reset, and failure fallbacks) is in [docs/DEMO.md](docs/DEMO.md).

## Documentation index

| Doc | Contents |
|-----|----------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Deployment diagram, agent architecture, deterministic vs AI split, data lineage |
| [docs/DEMO.md](docs/DEMO.md) | Timed demo script, click path, expected behavior, reset, failure plan |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production deployment, environment config, database, release checklist |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common failures and fixes |
| [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | Honest limitations |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Future work (post-hackathon) |
| [QA_REPORT.md](QA_REPORT.md) | Phase 15 test results, AI scorecard, performance |
