# RationRight — Instructions

## Core Instruction
Build a small, reliable, testable multi-agent hackathon demo. Optimize for working agents, deterministic evidence, structured outputs, easy debugging, and reliable integration.

## Vibe Coding Rules
- Implement only the requested scope.
- Read relevant project docs before coding.
- Preserve working code.
- Do not invent requirements.
- Do not silently add agents.
- Do not silently change schemas.
- Do not add unnecessary frameworks.
- Do not replace deterministic calculations with LLM guesses.
- Run tests before declaring work complete.

## Every Agent Must Have
- one primary purpose;
- input schema;
- output schema;
- tools;
- limitations;
- system prompt;
- success criteria;
- test cases;
- failure cases;
- integration contract.

## LLM vs Code
LLM: interpretation, classification, reasoning, explanation, summarization.
Code/tools: arithmetic, timestamps, distance, filtering, grouping, lookup, validation, schema enforcement.

## MVP Restrictions
Do not add vector databases, RAG, complex memory, autonomous long-term planning, real government APIs, real beneficiary data, or unnecessary microservices unless explicitly approved.

## Integration
No UI integration is complete unless it uses the actual backend workflow. Do not fake agent progress.

## Definition of Done
An agent is complete only when its tests pass, failures are handled, its contract is respected, and it runs independently.
