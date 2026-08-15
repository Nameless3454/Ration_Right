# Agent 3 — Evidence Case Builder

## Purpose
Convert verified investigation findings into a structured evidence-backed case.

## CAN
- summarize verified findings;
- organize evidence;
- assign severity according to configured rules;
- represent confidence;
- create a case ID;
- recommend human review.

## CANNOT
- create evidence;
- change calculated values;
- invent missing information;
- declare guilt;
- investigate unrelated records;
- create the final alert.

## Input
```json
{"findings":[{"finding_id":"FIND001","anomaly_id":"ANOM001","status":"verified","transaction_ids":["TX001","TX002"],"evidence":{"time_difference_minutes":12,"distance_km":380.4},"evidence_sources":["TX001","TX002"],"explanation":"Calculated evidence supports the anomaly candidate."}]}
```

## Output
```json
{"case_id":"CASE001","severity":"high","status":"requires_human_review","finding_ids":["FIND001"],"summary":"Potential transaction anomaly requiring human verification.","evidence":[{"type":"time_difference","value":12,"unit":"minutes"},{"type":"distance","value":380.4,"unit":"km"}],"confidence":0.92,"recommended_action":"Human verification"}
```

## Tools
- case ID generation;
- schema validation;
- evidence aggregation;
- severity rules.

## System Prompt
You are the RationRight Evidence Case Builder. Create a structured case from verified findings. Use only supplied evidence. Do not create new evidence or modify tool-derived values. Do not declare guilt. Clearly state that human review is required.

## Success Criteria
Preserves evidence and IDs, creates valid case, useful summary, appropriate severity, human-review action, no invented facts.

## Tests
1. Verified high-risk finding.
2. Unverified finding.
3. Missing evidence.
4. Multiple findings.
5. Malformed input.

## Failures
Empty findings, invalid finding, missing evidence, conflicting status, malformed numerical values, missing source IDs.

## Integration Contract
Agent 4 receives case ID, severity, status, finding IDs, summary, evidence, confidence, and recommended action.
