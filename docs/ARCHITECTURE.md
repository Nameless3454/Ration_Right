# RationAI — Architecture

This document matches the actual implementation (Phase 1–16). Nothing here
describes infrastructure that does not exist.

## 1. Deployment architecture

```
                        USER (browser — static frontend served by the API)
                                      │
                                      ▼
                    RATIONAI API  (Python stdlib http.server)
                    • static files + JSON API on one server
                    • opt-in token auth (Phase 14)
                    • security headers, same-origin CORS, rate limits
                    • structured logs with request IDs
                    • /api/health + /api/ready
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        ▼                             ▼                             ▼
   SQLite database            OpenAI-compatible API           External data
   • schema auto-created      • opt-in (RATIONRIGHT_LLM_       connectors
   • analytics / alerts /       ENABLED + OPENAI_API_KEY)      (Phase 7/8 —
     insights / reports       • server-side key only           CONNECTOR_READY /
     / audit log              • 15 s timeout, fail-open        NOT_CONNECTED)
        │                     • never called for arithmetic            │
        ▼                                                             ▼
   ANALYTICS SERVICES                                      DATA SOURCES
   (aggregations, risk,                                  (source status,
    freshness, quality)                                   sync metadata)
        │
        ▼
   COMMAND CENTER  (orchestration layer — Phase 12)
        │
        ▼
   REPORTS  (persisted, auditable, JSON/CSV export)
```

- One Python process serves the frontend and the API (no separate frontend
  build/host needed). The frontend is static HTML/CSS/JS — no build step.
- The database is a single SQLite file. Schema creation and migrations are
  idempotent and run automatically on open.
- The LLM is reached **only** server-side; the browser never sees a key.

## 2. Data pipeline (as implemented)

```
External / uploaded data
   → File validation (extension, content-type, magic bytes, size, row cap)
   → Schema mapping (external header → internal field)
   → Record validation + normalization (Phase 4)
   → Duplicate classification (exact/possible)
   → Transactional import (one transaction; rollback on any failure)
   → SQLite database
   → Analytics services (aggregations, inventory risk, freshness, quality)
   → AI agents (detect → verify → evidence → alert)
   → Alerts (deterministic rules) / Insights (persisted)
   → Command Center / Decision Support / Reports
```

Every record is traceable: `DataSource → DataImport → rows → analysis →
insight → alert → recommendation → report`.

## 3. Agent architecture (Phase 6 — as implemented)

| Agent | Purpose | Input | Output | Evidence | Failure behavior |
|-------|---------|-------|--------|----------|------------------|
| **Agent 1 — Transaction Analyst** | Detect suspicious patterns (e.g. rapid geographic transactions: same beneficiary, ≤ 60 min apart, ≥ 100 km) | Transaction dataset | Anomaly candidates | Timestamps + coordinates | Candidate is skipped (never fails the workflow) |
| **Agent 2 — Anomaly Investigator** | Verify a candidate with deterministic math | Candidate + its transactions | Verified finding (verified / not verified) | Calculated time difference + geographic distance | Verified fields are code-computed; narrative is LLM-optional (deterministic fallback) |
| **Agent 3 — Evidence Case Builder** | Assemble a human-review case | Verified findings | Investigation case | Evidence list (time/distance), confidence (0.9 / 0.5), severity | Validation raises on malformed input; narrative fallback deterministic |
| **Agent 4 — Alert Generator** | Produce the operator-facing alert | Case | Alert message + recommended action | Same evidence + confidence | Refuses (raises) rather than fabricating an alert without findings |

The LLM (when enabled) only writes the human-readable `explanation`,
`summary`, and `message` fields. Every number, ID, severity, status, and
confidence value is deterministic code — the model cannot change them
(verified by the Phase 15 AI evaluation suite).

## 4. Deterministic vs AI (Phase 15 verification)

**Deterministic code (never delegated to the model):**

- inventory calculations (`days_remaining = stock × 30 / monthly_consumption`)
- risk thresholds and severity classification
- percentages and change % (previous-period comparison)
- aggregations (distribution, demand, status counts)
- duplicate detection, quality score (Phase 4 formula)
- anomaly verification math (time difference, geographic distance)
- alert rule evaluation and deduplication
- what-if simulation arithmetic
- report values and lineage

**AI (optional, opt-in):**

- interpretation / summarization of supplied facts
- scenario interpretation and executive summaries
- alert explanations and recommendation phrasing

The AI receives only structured, pre-computed facts (never raw rows, never
secrets). All AI output is validated (length, forbidden guilt language) and
displayed separately from calculated values — evidence is never replaced by
model text.

## 5. Data lineage (as implemented)

```
Source  →  Dataset/Import  →  Database rows  →  Analytics
   →  AI Analysis run (RA-…)  →  Insight (evidence)  →  Alert (ALT-…)
   →  Recommendation  →  Report (RPT-…)
```

Every alert, insight, scenario (SIM-…), and report carries its
`data_import_id` / `analysis_id` / `source` references, and the UI exposes
`View Analysis`, `View Evidence`, `View Source`, and `Run What-If` links so a
judge can trace any answer back to its origin.
