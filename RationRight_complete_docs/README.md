# RationRight

Hackathon MVP demonstrating a working four-agent workflow: detect -> verify -> build evidence -> alert.

## Workflow

```text
Synthetic Data -> Agent 1 -> Agent 2 -> Agent 3 -> Agent 4 -> Backend -> UI
```

## Agents
1. Transaction Analyst — detects suspicious patterns.
2. Anomaly Investigator — verifies them with deterministic tools.
3. Evidence Case Builder — creates an evidence-backed case.
4. Alert Generator — creates a dashboard-ready alert.

Use synthetic data only. Suspicious patterns require human review; they are not proof of fraud.

## Documentation
- instructions.md
- prd.md
- architecture.md
- rules.md
- design.md
- memory.md
- data_contract.md
- implementation_plan.md
- agents/

Build and test each agent independently before integration.
