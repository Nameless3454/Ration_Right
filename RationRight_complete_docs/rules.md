# RationRight — Rules

## Data
- Use synthetic/demo data.
- Never fabricate transaction or beneficiary information.
- Never claim access to government systems without an actual integration.
- Every factual claim must trace to supplied data or a tool result.

## Reasoning
- Separate facts from interpretation.
- An anomaly is not proof of fraud.
- Never invent missing evidence.
- Report missing information.
- Prefer deterministic calculations over LLM estimation.

## Tools
Use code/tools for arithmetic, time calculations, distance, retrieval, filtering, aggregation, and validation. Never fabricate tool results.

## Agent Boundaries
- One primary responsibility per agent.
- No unnecessary duplication.
- No hidden responsibilities.
- Do not silently change another agent's contract.
- Every agent must be independently testable.

## Outputs
Every agent returns structured output with required fields. Preserve IDs and tool-derived values. Report errors clearly.

## Safety
RationRight must never declare a beneficiary legally guilty, recommend punishment solely from an AI result, expose unnecessary personal information, fabricate official records, or present synthetic data as real government data.

Default suspicious-case action: human verification/review.

## Engineering
Keep code modular, validate inputs/outputs, log useful events, keep secrets in environment variables, never commit API keys, and avoid unnecessary dependencies.

## Vibe Coding
Follow project documents, implement requested scope only, avoid unrelated rewrites, preserve contracts, run tests, and report failures honestly.

## Done
A component is complete when it works, tests pass, failure cases are handled, the contract is respected, and it integrates without changing its responsibility.
