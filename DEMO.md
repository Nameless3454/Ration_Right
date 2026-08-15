# RationRight Demo

> **Phase 16:** the official, timed demo guide is now **[docs/DEMO.md](docs/DEMO.md)**
> (exact click path, expected behavior, reset procedure, failure fallbacks).
> This file documents the original Phase 1–6 canonical anomaly scenario.

RationRight is a hackathon MVP: a four-agent workflow that analyzes **synthetic**
ration-distribution transactions, detects a deliberately planted suspicious
pattern, verifies it with deterministic calculations, builds an investigation
case, and generates a human-review alert. No real government data, Aadhaar
numbers, or personal information is used — the dataset is explicitly labeled
"Synthetic Demo Data".

## Problem

Public ration-distribution (PDS) systems are vulnerable to suspicious
transaction patterns — for example, a single beneficiary appearing at two
locations that are hundreds of kilometres apart within minutes. Reviewing
transactions manually does not scale, and automated systems that jump straight
to "fraud" risk accusing innocent people.

## Solution

RationRight separates **detection**, **verification**, **case building**, and
**alerting** into four deterministic agents. It only ever says: *this pattern
is worth a human look.* Every alert includes the exact calculated evidence and
the source transactions so a human reviewer can trace the reasoning end to end.
All calculations (time differences, geographic distance) are deterministic code,
not guesses and not LLM output.

## Canonical Scenario

One scenario is used for the demo (default dataset, default thresholds):

- **Normal behavior:** beneficiaries receive ration at nearby shops on
  realistic schedules; some have transactions on different days or at nearby
  locations close in time (control cases).
- **Suspicious pattern:** beneficiary `BEN001` has transaction `TX001` at
  Mumbai (19.076, 72.8777) on `2026-08-01T10:00:00` and transaction `TX002` at
  Delhi (28.6139, 77.209) on `2026-08-01T10:12:00` — 12 minutes apart, ~1148 km
  apart.
- **Agent 1** detects the rapid-geographic-transaction pattern: same
  beneficiary, interval ≤ 60 minutes, distance ≥ 100 km. It emits anomaly
  candidate `ANOM001` for `TX001`/`TX002`.
- **Agent 2** independently looks up those exact transactions, parses their
  timestamps, computes the time difference (12.0 minutes) and haversine
  distance (1148.09 km), evaluates the thresholds, and returns verified finding
  `FIND001`.
- **Agent 3** builds investigation case `CASE001` (`requires_human_review`),
  preserving Agent 2's evidence unchanged and tracing every fact to source
  transactions.
- **Agent 4** generates alert `ALERT001` (`open`, severity `high`) with the
  verified evidence and the recommendation **Human verification**.
- **Human** decides whether the pattern warrants further investigation. The
  system never declares guilt.

## Multi-Agent Workflow

```
Synthetic Dataset (data/synthetic/transactions.json)
        ↓
Agent 1 — Transaction Analyst   → anomaly candidates
        ↓
Agent 2 — Anomaly Investigator  → verified findings (deterministic evidence)
        ↓
Agent 3 — Evidence Case Builder → investigation cases
        ↓
Agent 4 — Alert Generator       → human-review alerts
        ↓
Human Review
```

The orchestrator (`workflow.run_workflow`) passes real outputs between the real
agents — no mocked or hard-coded results. Only verified findings continue; zero
anomalies is a clean, non-error outcome.

## Demo Steps

### Prerequisites

- Python 3.9+ (standard library only — no `pip install`, no build step, no
  database, no API key).
- No required environment variables. Optional: `RATIONRIGHT_ANALYZE_DELAY_MS`
  adds an artificial delay before analysis (ms) to observe the loading state;
  results stay real. Default `0`.

### Start Backend (also serves the frontend)

```bash
python3 server.py
# -> RationRight server running at http://127.0.0.1:8000
```

Optional flags: `--host`, `--port`, `--dataset <path>`,
`--analyze-delay-ms <ms>`. The server validates the dataset at startup and
refuses to start with a clear error if it is missing or invalid.

### Run the Demo

1. Open `http://127.0.0.1:8000` in a browser.
2. Click **Run Analysis** — the button disables ("Running analysis…") and a
   truthful status appears while the real workflow runs.
3. Read the result: pipeline statuses (all four stages COMPLETED), summary
   stats (25 transactions / 1 anomaly / 1 finding / 1 case / 1 alert).
4. In the alert card, review the evidence (**12 minutes**, **1148.09 km**), the
   traceability chain (`ALERT001 → CASE001 → FIND001 → ANOM001 → TX001, TX002`),
   and the source transaction table.
5. The alert shows **Pending human review** and recommends **Human
   verification**.

**Reset Demo** returns to a clean starting state. Results are session-only:
refreshing the browser returns to a clean dashboard.

## Expected Result

The canonical demo is deterministic — every run produces the same core result:

- **Dataset:** `data/synthetic/transactions.json` — 25 transactions,
  5 beneficiaries, labeled "Synthetic Demo Data".
- **Anomaly:** `ANOM001` (`rapid_geographic_transaction`) — `TX001` (Mumbai,
  10:00) and `TX002` (Delhi, 10:12), both `BEN001`.
- **Finding:** `FIND001` — `verified`, evidence `time_difference_minutes: 12.0`,
  `distance_km: 1148.09` (computed by deterministic code, not stored in the
  data).
- **Case:** `CASE001` — `requires_human_review`, confidence 0.9,
  `recommended_action: "Human verification"`.
- **Alert:** `ALERT001` — `status: open`, `severity: high`.

Verified by five consecutive runs: identical anomaly, transaction IDs,
evidence, case, and alert on every run.

## Human Review

RationRight is decision support, not a judge. The UI uses careful language
("Potential anomaly", "Pending human review", "Verified against transaction
data") and never claims fraud or guilt. The final decision — whether the pattern
warrants action — belongs to a human reviewer.

## Optional LLM Narratives (Phase 10)

The workflow is fully deterministic by default and runs with **no API key and
no extra dependency** (the LLM call uses only the Python standard library).
Optionally, an OpenAI-compatible model can write the human-readable narrative
(Agent 2's explanation, Agent 3's case summary, Agent 4's alert message) while
every calculation, evidence value, ID, severity, and status stays in
deterministic code.

```bash
# copy the template, then fill in your own key (never commit a real key)
cp .env.example .env
# .env is git-ignored; contains RATIONRIGHT_LLM_ENABLED, OPENAI_API_KEY,
# RATIONRIGHT_LLM_BASE_URL (https://openrouter.ai/api/v1 for OpenRouter keys),
# RATIONRIGHT_LLM_MODEL (default gpt-4o-mini)
python3 server.py
```

The LLM layer is fail-open: if the key is absent, the call fails or times out,
or the model returns unusable/guilt-implying text, the deterministic template
is used and the workflow continues normally. The key stays server-side and is
never logged or sent to the browser.

## Limitations

- Single MVP pattern (`rapid_geographic_transaction`); one case aggregates all
  verified findings per run; one alert per case.
- Narratives default to deterministic templates; LLM-written text requires the
  optional Phase 10 setup above and never changes calculated evidence.
- Results are session-only (no persistence); the dataset is fixed synthetic
  data (no multi-dataset selection).
- Evidence values are exact (no "approximately" formatting).

## Health Check & Tests

```bash
python3 scripts/health_check.py            # dataset, agents, workflow smoke run
python3 scripts/health_check.py --url http://127.0.0.1:8000   # also checks the live API
python3 -m unittest discover -s tests -t . -v   # 106 tests
```
