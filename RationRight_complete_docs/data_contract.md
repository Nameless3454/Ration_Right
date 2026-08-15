# RationRight — Data Contract

## Purpose
Define shared structures between agents. The implementation may use Pydantic, JSON Schema, or another validator, but the conceptual contract must remain stable.

## Transaction
```json
{
  "transaction_id": "TX001",
  "beneficiary_id": "BEN001",
  "timestamp": "2026-08-01T10:30:00",
  "latitude": 19.0760,
  "longitude": 72.8777,
  "ration_type": "rice",
  "quantity": 10
}
```

## Anomaly Candidate
```json
{
  "anomaly_id": "ANOM001",
  "anomaly_type": "rapid_geographic_transaction",
  "transaction_ids": ["TX001", "TX002"],
  "beneficiary_id": "BEN001",
  "reason": "Two transactions occurred within a short time interval at distant locations.",
  "severity": "high"
}
```

## Verified Finding
```json
{
  "finding_id": "FIND001",
  "anomaly_id": "ANOM001",
  "status": "verified",
  "transaction_ids": ["TX001", "TX002"],
  "evidence": {
    "time_difference_minutes": 12,
    "distance_km": 380.4
  },
  "evidence_sources": ["TX001", "TX002"],
  "explanation": "Calculated evidence supports the anomaly candidate."
}
```

## Investigation Case
```json
{
  "case_id": "CASE001",
  "severity": "high",
  "status": "requires_human_review",
  "finding_ids": ["FIND001"],
  "summary": "Potential transaction anomaly requiring human verification.",
  "evidence": [
    {"type": "time_difference", "value": 12, "unit": "minutes"},
    {"type": "distance", "value": 380.4, "unit": "km"}
  ],
  "confidence": 0.92,
  "recommended_action": "Human verification"
}
```

## Alert
```json
{
  "alert_id": "ALERT001",
  "case_id": "CASE001",
  "severity": "high",
  "title": "Potential transaction anomaly detected",
  "message": "Two related transactions require human verification.",
  "recommended_action": "Human verification",
  "status": "open"
}
```

## Contract Rules
- Preserve IDs across agents.
- Do not silently change tool-derived values.
- Report missing required data.
- Do not fabricate confidence.
- Free-form text cannot replace required structured fields.
- New fields require documentation updates.
