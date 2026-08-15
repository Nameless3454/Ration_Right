# RationRight — Implementation Plan

## Phase 0 — Setup
Create the documentation structure and confirm the architecture before coding.

## Phase 1 — Synthetic Dataset
Create a small deterministic dataset containing normal records and at least one planted suspicious pattern.

## Phase 2 — Agent 1
Build Transaction Analyst. Test detection, normal data, missing fields, and invalid input.

## Phase 3 — Agent 2
Build Anomaly Investigator. Add deterministic transaction lookup, time difference, geographic distance, and validation tools. Test independently.

## Phase 4 — Agent 3
Build Evidence Case Builder. Test verified findings, unverified findings, missing evidence, multiple findings, and malformed input.

## Phase 5 — Agent 4
Build Alert Generator. Test high/medium severity, incomplete case, and invalid input.

## Phase 6 — Agent Integration
Connect:
```text
Agent 1 -> Agent 2 -> Agent 3 -> Agent 4
```
Validate every boundary.

## Phase 7 — End-to-End Test
Run one complete synthetic investigation:
```text
Dataset -> Anomaly -> Verified Evidence -> Case -> Alert
```

## Phase 8 — Backend
Expose the workflow through a simple API such as `POST /investigate`.

## Phase 9 — UI
Connect the UI to the real backend. Do not simulate results.

## Phase 10 — Demo Hardening
Prepare deterministic demo data, one successful investigation, one failure case, clear status, evidence, and final alert.

## Phase 11 — Optional Improvements
Only after MVP works consider more anomaly types, tools, visualizations, or datasets.

## MVP Complete
One planted suspicious pattern must travel through all four real agents and produce an evidence-backed case and alert visible in the UI.
