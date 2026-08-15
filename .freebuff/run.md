# RationRight — Preview Run Doc

Project: RationRight (hackathon MVP) — Python 3.9+ **standard library only**:
no package manager, no dependencies to install, no build step.

## Reproduce artifacts

None required. There are no env files (`.env`, `.env.local`) and no secrets —
the server needs only the checked-in files. The only optional env var is
`RATIONRIGHT_ANALYZE_DELAY_MS` (adds an artificial analysis delay; default 0).

Verify the checkout is intact with:

```bash
python3 scripts/health_check.py            # dataset + all 4 agents + workflow smoke run
python3 -m unittest discover -s tests -t . # full test suite (106 tests)
```

## Run the server

Single process serves the dashboard UI and the workflow API:

```bash
cd /Users/sahoo/Documents/RationRight
python3 server.py --port 8000
# -> http://127.0.0.1:8000  (GET / = dashboard; /api/health, /api/dataset, POST /api/analyze)
```

Start it detached so it outlives the session, logging to the preview log:

```bash
python3 - <<'EOF'
import subprocess, sys
with open('/Users/sahoo/Documents/RationRight/.freebuff/preview-6bfc9b59-07d7-44d2-9e4b-b73e8ee822d2.log', 'a') as log:
    subprocess.Popen([sys.executable, 'server.py', '--port', '8000'],
                     stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
EOF
```

> Detach gotcha (macOS, verified Aug 2026): `start_new_session=True` is the ONLY
> reliable detach here. Plain `nohup ... & disown` gets reaped when the command
> runner kills the process group, and `launchctl submit` FAILS with
> `[Errno 1] Operation not permitted` because the project lives under
> `~/Documents` (macOS TCC blocks launchd-spawned jobs from accessing
> Documents). Verify survival with `kill -0 <pid>` from a SEPARATE tool call
> before registering the preview.
>
> OGD API key + real sync (Aug 2026): `GOVERNMENT_DATA_API_KEY` lives ONLY in
> the git-ignored `.env` (server-side; `.env.example` has an empty placeholder).
> `register_configured_sources` reactivates INACTIVE/ERROR rows when a key
> appears and refreshes base_url/description; `source_view` reports
> `auth_configured` (boolean) and never CONNECTED before a verified sync.
>
> The `ogd_pds_resource` profile now points at a REAL, verified OGD India
> resource — "Fair Price Shop details, Maharashtra (Sep–Dec 2025)"
> (`/resource/87e32686-a3a1-4b2f-ba3f-ac6cf7327f86`, 52,793 records), fetched
> with `api-key=` + `format=json` (server-side, never logged) and imported as
> `fps_centers` (page_size 10,000; 6 pages). A live sync imported 51,179
> shops (92 dirty-coordinate rows rejected, 1,522 dupes, 47,711 title-case
> normalization warnings -> quality 48.5; all honest). Known quirks: the
> fetcher needed a real User-Agent (`Python-urllib` gets stalled by
> api.data.gov.in); `command_center._fps_list` is scoped to FPS WITH
> transactions (51k registry must not ship to the browser as a `<select>`);
> the OPERATIONAL_RISK no_recent_distribution rule requires transaction
> history (`ever > 0`) so a registry FPS never floods alerts (was: 51k LOW
> alerts + 120s+ monitoring timeout).

Wait for `curl -s http://127.0.0.1:8000/api/health` to return `"status": "ok"`,
then register the preview at `http://127.0.0.1:8000` with the server's pid.

Usage: click **Run Analysis** in the dashboard to execute the real multi-agent
workflow (Agent 1 → 4) on the synthetic dataset; **Reset Demo** clears results.

Phase 6 added a **dataset selector** on the Analysis view: pick the synthetic
demo dataset or any imported real dataset (from `GET /api/datasets`). Real-data
runs post `{"dataset": "real", "data_import_id": N}` to `/api/analyze`; the
same four agents run on the imported transactions, and the result carries a
`dataset` provenance block (import id, name, record counts, data quality).

Phase 7 added **external connectors** (`connectors/`): Data Sources view at
`#/sources`, endpoints `GET /api/data-sources`, `GET /api/data-sources/<id>`,
`GET /api/data-sources/<id>/status|imports`, `POST /api/data-sources/<id>/sync`.
Registered sources: `sample_open_pds` (bundled sample CSV served at
`/sample/pds_sample.csv` — clearly labeled sample, exercises the full
fetch->parse->validate->import pipeline) and `ogd_pds_resource` (official OGD
India API — documented; requires `GOVERNMENT_DATA_API_KEY`, fails cleanly when
absent).

Phase 8 added the **Data Pipeline** view at `#/pipeline` (nav: Data Pipeline):
`GET /api/pipeline/status` (8 stages + overall HEALTHY/WARNING/ERROR + checks),
`GET /api/pipeline/freshness` (FRESH/RECENT/STALE/UNKNOWN thresholds), `GET
/api/pipeline/quality` (Phase 4 formula aggregated per import), `GET
/api/pipeline/runs?source=&status=&q=&from=&to=&page=&per_page=` (filtered,
server-paginated run history), `GET /api/pipeline/runs/<import_id>` (full
lineage: source -> import -> records -> database -> analytics -> analysis ->
AI), and `POST /api/data-sources/<id>/test` (real connection probe — never
faked; auth-required sources without a key report AUTH_NOT_CONFIGURED without
fetching). Every `POST /api/analyze` now also records an `analysis_runs` row
(`RA-YYYY-NNNN`) attached to the result as `analysis_run`, so AI insights trace
back to their dataset; the AI Insights view shows this lineage. Sources with a
registered connector profile but no live connection are labeled
`CONNECTOR_READY` (never CONNECTED/LIVE), and each source card carries an
honest origin badge (DEMO / REAL IMPORTED / MOCK · TEST / OFFICIAL · NOT
LIVE).

Phase 9 turned the Analysis view (`#/analysis`) into the **AI Analysis
Command Center**: `GET /api/analysis/types` (5 real types — 2 map to the
Phase 6 agents, 3 are deterministic DB checks), `POST /api/analysis/precheck`
(readiness per type, computed from the DB, never faked), `GET
/api/analysis/history[?page=&per_page=]` + `GET /api/analysis/history/<id>`
(persisted run metadata), and `POST /api/analyze` now accepts optional
`types` + `filters` (commodity/fps/district/from/to, validated server-side).
The orchestrator records real per-stage `timings`; analysis_runs persist
types/filters/timings/duration; the UI shows insight cards with severity/type
filters + search, expandable Evidence (calculated values + source lineage) and
Recommendation panels, an agent activity log with real timestamps, Export
JSON, and Run Again (creates a new analysis id, never overwrites).

Phase 10 added **Decision Support / What-If Simulation** at `#/simulation`
(nav: Decision Support). Backend: `simulation.py` (scenario engine) + a
`scenarios` table (metadata/results only — real tables are never written).
Endpoints: `GET /api/simulation/types` (DEMAND_CHANGE, SUPPLY_DELAY,
INVENTORY_CHANGE, COMBINED), `GET /api/simulation/entities?import_id=`,
`GET /api/simulation/situation?import_id=` (real baseline: stock,
consumption, coverage, high-risk FPS/districts), `POST /api/simulation/run`
(validated: demand −50…+100%, delay 0–365d, inventory −100…+100%),
`GET /api/simulation/history[?page=&per_page=]` and
`GET /api/simulation/history/<id>`. All math is deterministic
(projected_demand = baseline × (1+pct/100), coverage = stock/daily, stock
after delay, reorder requirement); risk reuses the Phase 5 thresholds
(CRITICAL <15d, WARNING <30d); zero stock → CRITICAL, zero consumption →
NOT CALCULABLE/UNKNOWN, missing data → structured INSUFFICIENT_DATA. AI
interpretation (`scenario_interpretation` prompt in agents/llm.py) only
rephrases the supplied values via `maybe_generate` with a deterministic
fallback; each result carries lineage (Scenario → Dataset → Import →
Source). The view shows current situation KPIs + risk table, a scenario
builder (commodity/district/FPS selects + sliders), a Before/After result
table with simulated requirement, an insight-confirmation note, history
with View (full detail) and Run Again (new scenario id).

Phase 11 added the **Early Warning, Alerts & Monitoring Center** (nav: Alerts →
Alert Center). Backend: `monitoring.py` (deterministic engine) + `alerts` /
`alert_rules` tables. `POST /api/monitoring/run` evaluates 11 configurable
rules (alert_rules, seeded idempotently): INVENTORY_RISK (coverage <15d
CRITICAL / <30d HIGH, stock < reorder threshold), OPERATIONAL_RISK (failure
rate ≥10% with ≥5 tx, no distribution in 30d), DEMAND_SPIKE / DEMAND_DROP
(latest month vs prior average, ≥20% with ≥3 tx), DATA_FRESHNESS (last
successful sync > 24h), SOURCE_FAILURE (source ERROR), DATA_QUALITY (import
quality < 90%), DISTRIBUTION_ANOMALY (persisted Phase 9 insights, severity
≥ MEDIUM, converted with analysis lineage). Dedup = one OPEN/ACKNOWLEDGED
alert per (type, condition, entity, commodity); re-detection updates
last_detected_at/evidence; cleared conditions auto-RESOLVE; DISMISSED
conditions are not re-created while they persist. Lifecycle API:
`GET /api/alerts[?q=&severity=&type=&status=&days=&page=&per_page=]`,
`GET /api/alerts/<id>` (evidence + AI explanation + lineage),
`GET /api/alerts/summary|trend|rules`, `POST /api/alerts/<id>/acknowledge|resolve|dismiss`
(dismiss takes an optional reason), `POST /api/alerts/rules/<id>`
(enabled/threshold). Phase 9 `run_analysis` now persists real-dataset
insights to `ai_insights` (with evidence + analysis_id) so anomaly alerts
carry alert ← insight ← analysis ← import provenance. AI explanation uses a
new `alert_explanation` prompt via `maybe_generate` with a deterministic
fallback (flagged honestly). Monitoring NEVER writes to inventory,
beneficiaries, transactions, imports, or sources (test-enforced). The Alert
Center view shows open-alert counts (bell badge = total active), a 7-day
trend, rule toggles + thresholds, filters/search, expandable cards with
evidence/AI explanation/recommendation/lineage, Acknowledge/Resolve/Dismiss
actions, View Analysis (Phase 9) and Run What-If (Phase 10, preselects the
alert's dataset/commodity). API responses now send `Cache-Control: no-store`.

## Phase 12 — Executive Command Center + Intelligence Reports

- New **Command Center** is the landing page (`#/command`, first nav item). It is a
  pure orchestration/view layer — every number comes from the new
  `command_center.py` service (one `GET /api/command-center` call), which reuses
  Phase 5 analytics (window/coverage/trend SQL), Phase 11 persisted alerts, Phase 9
  persisted insights/analysis runs, and Phase 8 freshness/lineage/quality — no
  business metrics are computed in the frontend.
- Sections: freshness header (status dot FRESH/RECENT/STALE/UNKNOWN + age + sources +
  honest disclaimer incl. "CONNECTOR READY / NOT CONNECTED"), deterministic or LLM
  executive summary (never invented numbers; fallback explicitly says "not a
  prediction"), 8 KPI cards with previous-period comparison (`change_pct` computed
  server-side; "no comparison available" when absent), risk overview (severity chips
  click → Alert Center pre-filtered), alert 7-day trend, district + FPS risk tables
  (severity-based HIGH/MEDIUM/LOW), trend intelligence (30-day distribution bars +
  by-commodity), top AI insights, active alerts, recommended actions (prioritized by
  severity, all from alerts/insights), data lineage (latest imports + analysis runs).
- Global filters (state/district/FPS/commodity/from/to/trend_range) refetch the whole
  payload consistently — verified in-browser (commodity=rice narrows KPIs to 8,888 kg
  and trend totals agree; KPI total == chart total == by-commodity total).
- **Intelligence reports**: `POST /api/reports` persists a full report
  (`reports` table, `RPT-YYYY-NNNN`, never overwrites; history/detail endpoints).
  The detail shows exec summary, KPIs, risk overview, alerts, insights,
  recommendations, data quality, lineage. Export JSON (payload) + CSV (district
  risk). Verified end-to-end in-browser (RPT-2026-0002 generated and opened).
- Fixed a real gap surfaced by Phase 12: the importer now preserves state/district
  when creating FPS centers from transaction datasets (previously dropped).
- `tests/test_command_center.py`: 18 tests — KPI accuracy + comparison math,
  risk-overview/alert agreement, district/FPS ranking, trend consistency, exec-summary
  fallback + LLM injection + LLM-failure survival, global filters, empty-DB honesty
  (zeros / "Insufficient data" / UNKNOWN freshness — never fabricated), report
  generation/history/detail/never-overwrite/generator injection, API routes on an
  isolated temp DB. Full suite: **387 tests pass**.

## Phase 13 — Professional UI/UX Polish + Interactive Experience

UI/UX-only phase — no backend or business-logic changes (full 387-test suite
unchanged and green).

- **Sidebar navigation** reorganized into labelled sections — OVERVIEW
  (Command Center, Overview), DATA (Beneficiaries, Ration Distribution,
  Inventory, Import Data, Data Sources, Data Pipeline), INTELLIGENCE (AI
  Analysis, Analytics, AI Insights, Alerts, Decision Support), REPORTING
  (Reports), SYSTEM (Settings). `title` attributes keep nav usable when
  collapsed; collapsed mode shows divider markers instead of labels; active
  item gets a subtle left accent + `aria-current="page"`.
- **Top-bar DataStatus chip** (`#data-status-chip`) — a reusable component fed
  by `/api/pipeline/freshness` (throttled 30 s, never fabricated): FRESH
  "Data fresh" / RECENT / STALE / UNKNOWN "No sync data" with a semantic dot
  and the real backend detail as tooltip.
- **Command palette** (⌘K / Ctrl+K, existing overlay upgraded): grouped
  results — Navigate (views), Datasets, Alerts, Entities (FPS / districts /
  commodities) — built from existing endpoints (`/api/datasets`,
  `/api/alerts`, `/api/command-center` filter_options, cached 2 min).
  Activation drills down: alert → Alert Center pre-filtered; dataset → AI
  Analysis preselected; FPS/district/commodity → Command Center scoped (all
  verified in-browser, including re-render when already on the target route).
  Focus returns to the trigger on close; results get aria-labels.
- **Design tokens**: added semantic tokens (`--text-warning`, `--text-info`,
  `--text-critical`, `--surface-critical/-soft`, `--surface-warning`,
  `--surface-info`, `--border-critical/-warning/-info/-success/-soft`,
  `--amber`, `--focus-ring`) and replaced **61 scattered hex literals** in the
  CSS with them — the only remaining hex values are the `:root` token
  definitions themselves.
- **Polish**: `prefers-reduced-motion` global rule; render guard so one
  failing view renders a Retry error state instead of a blank app; toasts now
  carry per-kind icons (✓/✕/⚠/ℹ) + `role="status"`; palette results scroll
  within a max-height.
- Browser-verified: sidebar sections + collapse, status chip (fresh dot +
  detail tooltip), palette groups/search/activation, focus restore, toast
  markup, zero console errors, zero horizontal overflow at desktop.

## Phase 14 — Security, Reliability & Production Hardening

**Audit findings (real gaps found & fixed).** No hardcoded secrets existed
(source scan, `.env` git-ignored, `.env.example` placeholders only) ✓. Real
gaps fixed this phase:

- **CORS was `*` on every response** → now same-origin by default;
  `RATIONRIGHT_ALLOWED_ORIGINS` echoes only configured origins;
  `RATIONRIGHT_CORS_ALLOW_ANY=1` restores `*` explicitly (tests cover all three).
- **No security headers** → `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, and a same-origin
  CSP are now on every response (static + API).
- **No authentication/authorization** → opt-in token auth
  (`RATIONRIGHT_AUTH_TOKEN`): `POST /api/auth/login` exchanges the token for an
  HMAC-signed `HttpOnly` `SameSite=Lax` session cookie; logout revokes
  server-side; forged/tampered cookies → 401; health/ready/auth-status stay
  public; every other API is protected. Frontend shows a sign-in overlay on
  401 and friendly errors, never a stack trace. Off by default → zero demo
  friction; one env var turns it on.
- **No audit log** → new `audit_log` table (append-only via API) +
  `record_audit`/`list_audit`; wired to login/logout, imports, analysis runs,
  monitoring, alert acknowledge/resolve/dismiss, rule changes, report
  generation, simulations, and connector syncs. Entries carry request IDs and
  never secrets (test-verified).
- **Import atomicity** → removed the mid-import `commit()` (previously a
  critical failure could leave half-imported rows); `confirm_step` now wraps
  the whole import in a transaction and rolls back on any failure, deleting
  the staging entry. A test injects a mid-import crash and asserts zero
  surviving transactions/import rows.
- **Row cap** → `MAX_ROWS = 500_000` (configurable via
  `RATIONRIGHT_MAX_ROWS`) enforced in `ingestion/service.py`.
- **CSV formula injection** → the frontend `toCsv` export sanitizes cells
  beginning with `=`, `+`, `-`, `@` (prepends a tab) so exports can't carry
  spreadsheet formulas.
- **Rate limiting** → in-memory sliding-window limiter on expensive
  endpoints: analyze 30/min, monitoring 30/min, reports (POST) 30/min,
  upload 60/min, simulation 60/min, login 5/min (tight, to slow brute force).
  Verified live: 30 in-window runs OK then 429s.
- **Input validation** → reversed date ranges → 400 `INVALID_INPUT`;
  SQL-injection attempts treated as literal filter values (parameterized
  queries — test-verified, no traceback/sqlite leak); pagination clamped;
  uploads reject wrong extensions, content-type mismatches, magic-byte
  mismatches, and oversized files (413).
- **Error sanitization** → production error bodies never include stack
  traces, `.py` paths, or db paths (test-verified).
- **Request IDs + structured logging** → every request gets a request ID
  (`request_id=…` in access logs) for traceability.
- **`GET /api/ready`** readiness endpoint → `{checks: {database: READY,
  ai: …, external_sources: …}, timestamp}`; surfaced in Settings as a live
  **System status** panel + append-only **Audit trail** tail.

**Tests:** `tests/test_security.py` — 22 tests (secret scan, .env.example
placeholders, .gitignore, headers, CORS ×3, auth ×3 incl. revocation +
forgery + login rate limit, input validation ×3, upload ×4, import rollback,
audit ×2, ready). Full suite: **409 tests, all green** (387 prior + 22 new).

**Browser E2E:** open mode unchanged (Command Center 8 KPIs, clean console,
zero failed requests); auth mode verified end-to-end — 401 → sign-in overlay
→ login → app loads → Settings System status (database READY, ai
NOT_CONFIGURED, sources CONFIGURED) + audit trail (auth.login/out,
analysis.run, report.generate) → logout → overlay returns. Rate limiting
verified live (429 after 30 monitoring runs in a minute).

## Phase 15 — Testing, AI Evaluation & Data Accuracy

QA audit phase — no new features, no business-logic changes. Added 47 tests
across 3 new suites; the full suite grew from 409 to **456 tests, all green,
0 skipped** (framework: existing stdlib `unittest`; no new dependencies).

- **tests/test_qa_audit.py (18)** — import reconciliation invariant
  (source = valid + invalid; imported = valid − duplicates; DB rows match),
  duplicate-file idempotency, normalization rules, analytics recomputed
  independently from raw rows, KPI chain (DB → analytics → command center →
  API) agreement, comparison % math + previous=0 guard, filter isolation,
  date boundaries, null/missing-data safety.
- **tests/test_ai_evaluation.py (23)** — injected-generator evaluation
  (scorecard, all PASS): missing data refused (INSUFFICIENT_DATA), number
  accuracy into LLM context == calculated values, source attribution honest,
  confidence deterministic (0.9, not LLM), failure modes (timeout/429/500/
  malformed/missing key) degrade to fallback, exactly-once attempt (no
  retry storm), context hygiene (no secrets/raw rows).
- **tests/test_e2e_flow.py (6)** — full upload→import→command center→
  analytics→analysis→alert→evidence→what-if→recommendation→report→export
  flow; parallel-reads concurrency smoke (16 reqs, no errors); 20k-row
  import exact + bounded pagination; failure recovery (AI down / monitoring
  failure keep analytics and alerts intact).

Findings: NO bugs in application calculations — every audit failure was a
wrong test expectation (confirmed correct behaviors instead: dedup key
(FPS,date,commodity,qty), rolling 30-day KPI window, 15-day CRITICAL
inventory threshold). Security: all 22 Phase 14 tests re-ran green.
Performance: analytics endpoints 2–3 ms; 20k-row import ≈ 1.0 s total;
command-center 2.3 s dominated by the opt-in live LLM call (deterministic
parts sub-10 ms). Coverage: stdlib `trace --summary` = 100% lines executed
in every core module (proxy metric; coverage.py not installed).

Release gate: **READY WITH KNOWN LIMITATIONS** (limitations are
environmental — no live government API, no production-scale dataset — not
defects). Full report: `QA_REPORT.md`.

## Phase 16 — Final Deployment, Demo & Hackathon Readiness

Finalization phase — no new features. Two small bug fixes + full documentation.

**Bug fixes:**
- `RATIONRIGHT_DB_PATH` env var was documented nowhere and honored nowhere —
  wired into `server.py` (argparse default) so the documented env config works.
- The sidebar "Reports" entry pointed at the legacy Phase-5 report-cards page,
  while the Phase 12 Intelligence Report system (history/generate/view/export)
  lived only inside the Command Center. Added the Intelligence Reports section
  (reuse of `ccReports`/`generateCommandReport`/`viewCommandReport`) to the
  Reports page, so the nav reaches the report system that backs the demo.
  Also fixed a mismatched quote that broke JS parsing in the inserted block.
- `.env.example` expanded to a complete placeholder-only template (DB path,
  auth, session secret, CORS, max rows, LLM).

**Documentation (new):** README.md (overview, problem/solution, features,
architecture, tech stack, quick start, env, DB, testing, deployment,
limitations, roadmap); docs/ARCHITECTURE.md (deployment diagram, pipeline,
agent architecture, deterministic-vs-AI split, lineage); docs/DEMO.md
(6-minute timed demo script, exact click path, reset, failure fallback plan);
docs/TROUBLESHOOTING.md; docs/DEPLOYMENT.md (env table, DB deployment,
release checklist); docs/LIMITATIONS.md (honest limits); docs/ROADMAP.md
(future work). Updated DEMO.md pointer + DEMO_CHECKLIST.md stale test count.

**Final verification:** 456/456 tests green; fresh-DB migration idempotent;
final secret scan 0 hits; /api/health + /api/ready healthy; CORS same-origin
with security headers; browser pass across Command Center, Data Sources
(honest labels: OGD = OFFICIAL · NOT LIVE, sample = MOCK/TEST, uploads = REAL
IMPORTED), Alerts, Decision Support, AI Analysis, Pipeline, Settings,
Reports (open + generate + export verified, console clean, no overflow).
Release status: **READY FOR DEMO** (demo flow works end-to-end; limitations
documented — no live government API, optional LLM, single-operator auth).
