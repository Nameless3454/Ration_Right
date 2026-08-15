# RationRight — Architecture

## System Flow

```text
Synthetic Dataset
      |
      v
Agent 1 — Transaction Analyst
      |
      v
Agent 2 — Anomaly Investigator
      |             |        +--> Deterministic Tools
      v
Agent 3 — Evidence Case Builder
      |
      v
Agent 4 — Alert Generator
      |
      v
Final Case / Alert
      |
      v
Backend API
      |
      v
UI
```

## Agent Boundaries
### Agent 1
Detects suspicious patterns. Does not verify final evidence, declare fraud, or generate final alerts.

### Agent 2
Verifies candidates and calculates evidence. Does not invent evidence or make legal conclusions.

### Agent 3
Organizes verified evidence into a case. Does not create or modify evidence.

### Agent 4
Communicates the completed case. Does not alter evidence or make legal conclusions.

## LLM/Tool Boundary
```text
LLM: interpretation, reasoning, classification, summarization
CODE/TOOLS: arithmetic, time difference, geographic distance, filtering, lookup, validation
```

## Integration
```text
Agent 1 output -> Agent 2 input
Agent 2 output -> Agent 3 input
Agent 3 output -> Agent 4 input
```

Structured contracts are mandatory.

## Backend
A simple endpoint may be `POST /investigate`. The backend loads data, invokes agents, validates outputs, handles failures, and returns the final result.

## UI
The UI consumes backend results and shows actual agent status, findings, calculations, evidence, case, and alert. It must not fake activity.

## Development Order
```text
Build Agent -> Unit Test -> Manual Test -> Failure Test -> Freeze Contract -> Next Agent
```

Use the simplest framework that supports tools, structured outputs, testing, independent execution, and integration.
