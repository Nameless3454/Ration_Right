# RationAI (RationRight) — Project Memory

Compact working memory for AI/agent sessions. Companion to `.freebuff/run.md` (how to run
the preview), `README.md` (user docs), `QA_REPORT.md` (Phase 15 audit), and `docs/`.

## What this is

**RationAI** is a decision-intelligence platform for India's Public Distribution System (PDS):
operational distribution data → deterministic analytics → multi-agent AI → evidence → alerts →
what-if simulation → recommended actions → intelligence reports. It is **not a chatbot**; every
AI statement rests on deterministic calculations, structured evidence, and traceable lineage
(source → import → analysis → insight → alert → report).

- **Language/runtime:** Python 3.9+, **standard library only** — zero third-party runtime deps,
  no package manager, no build step. Frontend is a single static app (`static/app.js` + CSS/HTML).
- **Server:** one process (`server.py`) serves the static frontend + JSON API on port 8000.
- **Database:** SQLite (`data/rationright.db`), schema auto-creates and migrates idempotently.

## Status (verified Aug 2026)

- **Phase 16 complete — release status READY FOR DEMO.** All 16 phases shipped
  (architecture → DB → ingestion → validation → dashboard → multi-agent AI → connectors →
  pipeline → AI analysis → decision support → alerts → command center → UI polish → security →
  testing/QA → finalization).
- **Tests: 459/459 pass, 0 skipped** (stdlib `unittest`, `python3 -m unittest discover -s tests -t .`,
  ~29s). No new dependencies ever added.
- **Live demo DB state (14 tables):** 59 ration transactions, 51,187 FPS centers (real OGD
  sync), 9 alerts, 4 scenarios, 9 reports, 237 analysis runs, 11 AI insights, 168 audit entries,
  4 data sources.
- **LLM:** optional, server-side only (`OPENAI_API_KEY`), 15s timeout, rate-limited,
  fail-open to deterministic fallback. Without a key the whole app still works.

## Golden rules (never violate)

1. **Never fabricate data**: no fake KPIs, alerts, trends, timestamps, sources, or AI numbers.
   Missing data → `N/A` / `INSUFFICIENT DATA` / "Insufficient historical data".
2. **Never claim live**: a source is CONNECTOR_READY until a real sync verifies it; OGD shows
   `OFFICIAL · NOT LIVE` until a verified sync, then `OFFICIAL · VERIFIED SYNC`. Never claim a
   government API is live unless actually connected and verified.
3. **Secrets live only in `.env`** (git-ignored; no `.git` dir exists yet). `.env.example` has
   placeholders only. Never log/expose API keys; the key rides in server-side URLs only, never
   printed.
4. **Simulations never write real data** — scenario metadata/results go to `scenarios` only.
   Monitoring never writes inventory/transactions/imports/sources (test-enforced).
5. **No duplicate systems**: reuse Phase 5 analytics, Phase 6 agents, Phase 9 insights,
   Phase 11 alerts. Command Center is an orchestration/view layer — no business math in frontend.

## Architecture

```
DATA SOURCES (CSV/XLSX/JSON upload, sample, OGD India API)
   ↓  ingestion/ (file→schema→data validation→normalize→transactional import)
DATABASE (SQLite, 14 tables)
   ↓  analytics.py (deterministic KPIs: coverage, demand, risk thresholds)
   ├─ workflow.py + agents/  → AI analysis (4 agents, optional LLM, deterministic fallback)
   ├─ analysis_center.py     → Phase 9 AI Analysis Command Center + ai_insights
   ├─ monitoring.py          → Phase 11 alert engine (11 deterministic rules, dedup, auto-resolve)
   ├─ simulation.py          → Phase 10 what-if scenarios (deterministic math)
   └─ command_center.py      → Phase 12 Command Center orchestration + reports
FRONTEND (static/app.js, hash-routed SPA) → Command Center, Overview, Data, AI, Alerts,
                                            Decision Support, Reports, Settings
```

Key modules: `server.py` (routes/auth/rate-limit/audit/headers), `database.py`,
`analytics.py`, `data_context.py`, `ingestion/` (`service.py`, `mapping.py`, `validation.py`),
`connectors/` (`profiles.py`, `service.py`, `base.py`, `fetcher.py`, `sync.py`), `agents/`
(`env.py`, `llm.py`, four agent modules), `workflow.py`, `monitoring.py`, `simulation.py`,
`command_center.py`, `pipeline.py`, `analysis_center.py`, `tests/` (15 suites).

## Data sources (4)

| id | name | type | status |
|----|------|------|--------|
| 2  | Synthetic Demo Dataset | ACTIVE | last sync 2026-08-08 (sample) |
| 3  | Uploaded Dataset | ACTIVE | real imports via UI |
| 4  | ogd_pds_resource | ACTIVE | **verified real sync** 2026-08-12 — Fair Price Shop details, Maharashtra (Sep–Dec 2025), 52,793 fetched → 51,179 imported |
| 5  | sample_open_pds | ACTIVE | bundled sample CSV (MOCK/TEST) |

## OGD India integration (last major work)

- Key format `579b46…` = data.gov.in OGD key → `GOVERNMENT_DATA_API_KEY` in `.env`
  (the ONLY holder; re-scan 0 hits elsewhere). `.env.example` documents it as a placeholder.
- Profile now points at a real verified resource
  `/resource/87e32686-a3a1-4b2f-ba3f-ac6cf7327f86`, fetched with `api-key=` + `format=json`
  + a real User-Agent (urllib's default gets stalled by api.data.gov.in), page_size 10,000
  (6 pages ≤ MAX_PAGES 20), imported as `fps_centers`.
- Import stats (all honest): 92 rows rejected for dirty coordinates, 1,522 source dupes,
  47,711 title-case normalization warnings → quality 48.5 (real data is ALL-CAPS).
- This resource is an **FPS registry, not transaction-level PDS data** — it feeds
  FPS/geographic intelligence, not transaction KPIs. OGD India doesn't expose per-transaction
  PDS records.

## Gotchas (learned the hard way)

- **Detach on macOS:** only `subprocess.Popen(..., start_new_session=True)` survives the
  command runner. `nohup & disown` gets reaped; `launchctl submit` fails with
  `[Errno 1] Operation not permitted` because the workspace is under `~/Documents` (TCC).
  Verify with `kill -0 <pid>` from a separate tool call.
- **Registry FPS ≠ distribution failure:** the OPERATIONAL_RISK `no_recent_distribution` rule
  requires transaction history (`ever > 0`) — otherwise a 51k registry floods LOW alerts
  (was: 51k+ alerts, 120s+ monitoring timeout, DB lock). Run now takes 0.075s.
- **Never ship 51k FPS to the browser:** `command_center._fps_list` is scoped to FPS **with
  transactions** (51,187 → 8 options). Payload was 1.15 MB → 27 KB.
- **A key appearing must reactivate sources:** `register_configured_sources` flips
  INACTIVE/ERROR → ACTIVE when a key appears; status stays CONNECTOR_READY until a verified
  sync; `auth_configured` (boolean, never the key) drives the UI credential row.
- **Import atomicity:** whole import wrapped in one transaction; mid-import crash rolls back
  (staging row deleted). `MAX_ROWS` default 500,000.
- **Auth is opt-in** (`RATIONRIGHT_AUTH_TOKEN`): HMAC-signed HttpOnly SameSite=Lax cookie;
  health/ready/auth-status public; off by default (zero demo friction).

## How to run / test

```bash
cd /Users/sahoo/Documents/RationRight
python3 server.py --port 8000          # → http://127.0.0.1:8000
python3 -m unittest discover -s tests -t .   # full suite (459)
python3 scripts/health_check.py        # dataset + agents + workflow smoke
```

Frontend views: `#/command` (Command Center), `#/overview`, `#/analysis` (AI Analysis),
`#/alerts` (Alert Center), `#/simulation` (Decision Support), `#/reports` (Intelligence
Reports), `#/sources`, `#/pipeline`, `#/settings`. Global filter bar + ⌘K palette.

## Known limitations

Documented honestly in `docs/LIMITATIONS.md`: no live government *transaction* API (connector
is real and verified but registry-scope); LLM optional/external (no AI accuracy % claimed);
single-operator opt-in auth (one shared token by design); SQLite + ~20k-row verified scale;
in-app alerts only; tabular (not map) geography.

## Convention reminders

- Match existing style: stdlib only, no new deps, unittest suites in `tests/`, module-level
  docstrings, honest error strings, `Cache-Control: no-store` on API.
- Validate JS with `jsc <file>` or in-browser (jsc isn't on PATH by default).
- Update `.freebuff/run.md` when the run procedure or integration notes change (procedures only,
  never secret values).
