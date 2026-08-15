# RationRight — Design

## Goal
Make the real multi-agent workflow visible:

**Detect -> Verify -> Build Evidence -> Alert**

## Dashboard
Show RationRight name, description, system status, selected dataset/case, and a Run Investigation button.

## Agent Workflow
```text
[1] Transaction Analyst
        |
[2] Anomaly Investigator
        |
[3] Evidence Case Builder
        |
[4] Alert Generator
```

Each stage shows pending, running, completed, or failed.

## Transaction Panel
Show transaction ID, beneficiary reference, timestamp, location, and relevant transaction details.

## Anomaly Panel
Show anomaly type, transaction IDs, severity, reason, and source records.

## Evidence Panel
Show actual calculated evidence, for example:
```text
Time Difference: 12 minutes
Geographic Distance: 380.4 km
```
Distinguish observed, calculated, and interpreted information.

## Case Panel
Show case ID, severity, summary, evidence, confidence, and recommended action.

## Alert Panel
```text
HIGH PRIORITY

Potential transaction anomaly detected.

Evidence:
2 related transactions
12 minutes apart
380.4 km apart

Recommended Action:
Human verification
```

## Agent Activity
Only display real events:
```text
✓ Agent 1 detected candidate
✓ Agent 2 retrieved records
✓ Agent 2 calculated distance
✓ Agent 2 verified finding
✓ Agent 3 built case
✓ Agent 4 generated alert
```

Never display fake thinking or tool calls.

## Error State
```text
Agent 2 failed

Reason:
Required location information is missing.

Action:
Review the source data and retry.
```

## Integration
```text
UI -> Backend -> Real Agent Workflow -> Structured Result -> UI
```

The frontend must not reproduce agent calculations.

## Demo
Show synthetic data, run investigation, show Agent 1 detection, Agent 2 verification, evidence, Agent 3 case, Agent 4 alert, and human-review recommendation.
