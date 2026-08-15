# RationRight — Synthetic Transaction Dataset

> **Label: Synthetic Demo Data** — every record in this file is fictional.
> It is not real government data, not real PDS data, not Aadhaar/UIDAI data,
> and not real personal information. It exists only to demonstrate the
> RationRight multi-agent workflow.

## Overview

- **File:** `data/synthetic/transactions.json`
- **Records:** 25 transactions (`TX001`–`TX025`)
- **Beneficiaries:** 5 (`BEN001`–`BEN005`)
- **Ration types:** `rice`, `wheat`, `sugar`, `kerosene`
- **Time window:** `2026-07-01` to `2026-08-07` (ISO-8601, naive local times)

## Purpose

This dataset is the Phase 1 deliverable of RationRight. It will be consumed by
the four agents built in later phases. It contains:

1. normal transactions;
2. control cases that look unusual but are legitimate;
3. exactly **one deliberately planted suspicious pattern**
   (`rapid_geographic_transaction`).

## Contract

Every transaction follows the documented structure in
`RationRight_complete_docs/data_contract.md` — exactly seven fields:

| Field | Example |
|---|---|
| `transaction_id` | `TX001` |
| `beneficiary_id` | `BEN001` |
| `timestamp` | `2026-08-01T10:00:00` |
| `latitude` | `19.0760` |
| `longitude` | `72.8777` |
| `ration_type` | `rice` |
| `quantity` | `10` |

**Derived values are NOT stored in the dataset.** Fields such as
`time_difference_minutes` or `distance_km` are intentionally absent from the
transaction objects; later phases must compute them with deterministic
code/tools, never with LLM estimation.

Dataset-level metadata (name, version, label, description) lives in the
top-level `metadata` object, separate from the transaction records.

## Planted Anomaly

One rapid-geographic-transaction pattern is deliberately planted:

| | Transaction A | Transaction B |
|---|---|---|
| ID | `TX001` | `TX002` |
| Beneficiary | `BEN001` | `BEN001` |
| Timestamp | `2026-08-01T10:00:00` | `2026-08-01T10:12:00` |
| Location | Mumbai `(19.0760, 72.8777)` | Delhi `(28.6139, 77.2090)` |
| Ration | rice, 10 | rice, 10 |

The same beneficiary has two transactions **12 minutes apart** at locations
**~1148.09 km apart** (great-circle, computed by the haversine formula in
`scripts/validate_dataset.py`). Physically implausible to travel that distance
in 12 minutes — this is the signal Agent 1 must detect in Phase 2 and Agent 2
must verify in Phase 3.

The anomaly is planted as a **data pattern only**. No anomaly result is stored
in the JSON; nothing in the dataset claims an agent detected anything.

## Control Cases

Legitimate-looking cases that must NOT match the same pattern (short interval
AND large distance). Verified values below were computed with the same
deterministic helpers used by the validator:

1. **Short interval, nearby locations** — `TX006`/`TX007` (`BEN002`): 12.0 min
   apart but only ~0.45 km apart (Pune). Fails the distance condition.
2. **Short interval, nearby locations** — `TX016`/`TX017` (`BEN005`): 10.0 min
   apart but only ~0.64 km apart (Hyderabad). Fails the distance condition.
3. **Far apart, different days** — `TX010`/`TX011` (`BEN003`): ~1148.09 km
   apart (Delhi → Mumbai) but 4770 min (~3.3 days) apart. Fails the interval
   condition.
4. **Far apart, different days** — `TX001`/`TX025` (`BEN001`): ~845.32 km apart
   (Mumbai → Bangalore) but 5460 min (~3.8 days) apart. Fails the interval
   condition. Same beneficiary as the planted anomaly, which specifically tests
   that "far apart" alone is not flagged.
5. **Same location, longer interval** — `TX013`/`TX014` (`BEN004`): 0.00 km
   apart but 90 min apart. Fails both conditions.

## Validation & Tests

Run the standalone validator:

```bash
python3 scripts/validate_dataset.py
```

It checks the contract, confirms the planted anomaly satisfies the pattern
(same beneficiary + short interval + large distance), scans all same-beneficiary
pairs, and fails if any pair other than the planted one meets the thresholds.

Run the test suite (from the project root):

```bash
python3 -m unittest discover -s tests -t . -v
```

Tests cover: loading, unique IDs, required fields, valid timestamps, valid
coordinates, positive quantities, planted-pair presence, planted-pair pattern
satisfaction, and that normal/control records never trip the thresholds.
