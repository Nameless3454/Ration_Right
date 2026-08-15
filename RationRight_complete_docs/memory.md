# RationRight — Project Memory

## Purpose
Record important implementation decisions, discoveries, and changes.

## Current State
RationRight is a hackathon MVP. The team is learning agent development, so simple independently testable agents are preferred over complex autonomous systems.

## Locked Workflow
```text
Transaction Analyst
      ->
Anomaly Investigator
      ->
Evidence Case Builder
      ->
Alert Generator
```

## Architecture Decision
Agents are built and tested individually before integration. The UI uses the actual backend workflow.

## Data Decision
Use synthetic transaction data.

## AI Decision
Use LLMs for reasoning and interpretation. Use deterministic tools for exact calculations and data operations.

## Important Decisions
- Do not build all agents at once.
- Freeze each agent contract before connecting it.
- Do not add advanced infrastructure without a real MVP need.
- A working small agent is more valuable than an unreliable sophisticated agent.

## Update Format
```text
Date:
Decision:
Reason:
Affected files:
```

---

## Decision Log

```text
Date: 2026-08-08
Decision: Added a normalized SQLite data layer (database.py) as the real-data
  foundation. Seven tables: data_sources, data_imports, beneficiaries,
  fps_centers, ration_transactions, inventory, ai_insights. Ration transactions
  store latitude/longitude so Agent 1/Agent 2 can reproduce their exact input
  records (as_agent_transaction / get_transactions_for_agent).
Reason: Phase 2 of the real-data program (Phase 1 audit found no database at
  all). The project is stdlib-only with no PostgreSQL configured, so the
  database is stdlib sqlite3 — one file, no service, no credentials. Normalized
  schema means later ingestion maps external column names into these tables
  instead of creating a table per dataset. Agents were NOT changed.
Affected files: database.py, scripts/seed_database.py, tests/test_database.py,
  .gitignore (*.db), memory.md
```
