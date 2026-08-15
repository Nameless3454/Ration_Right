# RationRight — Product Requirements Document

## Product
RationRight is a hackathon demonstration of a multi-agent AI workflow that analyzes synthetic ration-distribution transactions and identifies potentially suspicious patterns for human review.

## Goal
Demonstrate a genuinely working multi-agent workflow, not generic AI text.

## MVP Agents
### Agent 1 — Transaction Analyst
Detect potentially suspicious transaction patterns.
Input: transaction records.
Output: anomaly candidates.

### Agent 2 — Anomaly Investigator
Verify anomaly candidates using source records and deterministic tools.
Input: anomaly candidates plus relevant records.
Output: verified findings and evidence.

### Agent 3 — Evidence Case Builder
Convert verified findings into a structured investigation case.
Input: verified findings.
Output: evidence-backed case.

### Agent 4 — Alert Generator
Convert the completed case into a concise human-review alert.
Input: completed case.
Output: dashboard-ready alert.

## Example Pattern
Two transactions for the same beneficiary occur within a very short time interval while their recorded locations are far apart. Time and distance must be calculated using code/tools.

## Human Review
RationRight identifies investigation signals. It does not determine guilt or automatically punish anyone. Recommended action: human verification/review.

## MVP Success
The system must load synthetic data, detect a planted anomaly, verify it, calculate evidence, pass structured outputs between agents, produce a case and alert, and expose the result to the UI.

## Non-Goals
No real government data, Aadhaar/UIDAI, real beneficiary identities, live PDS integration, WhatsApp/SMS, vector databases, RAG, long-term memory, or complex autonomous planning.

## Principle
A small system that works end-to-end is better than a sophisticated system that cannot demonstrate reliable execution.
