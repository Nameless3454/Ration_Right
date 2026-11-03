# RationRight — Product Context

## Product Overview
RationRight is a government operations platform designed to support officials working with India's Public Distribution System (PDS).

## Existing Modules
The existing application contains:
- Beneficiary management
- Inventory management
- Distribution transaction monitoring
- Fair Price Shop management
- Audit records
- Suspicious-record detection and flagging

These modules already exist in a separate project.

## AI Assistant Purpose
The new AI assistant will answer questions strictly using datasets imported into RationRight on a weekly basis.

It should help authorized officials:
- Understand imported beneficiary data.
- Review inventory information.
- Analyze distribution transactions.
- Review Fair Price Shop records.
- Understand audit information.
- Compare weekly imports.
- Identify changes between historical datasets.

## Data Sources
The application works with:
- `beneficiaries.csv`
- `inventory.csv`
- `transactions.csv`
- `pwd_shops.csv`
- `pwd_audits.csv`
- `rationright_demo_data.json`

The supplied dummy dataset is synthetic and is only for development and demonstration.

## Weekly Data Behaviour
The assistant must support:
1. The latest weekly import.
2. Historical weekly imports.
3. Comparisons between selected imports.

Historical snapshots must be preserved.

## Important Boundaries
- Do not rebuild existing RationRight modules.
- Do not modify the existing application.
- Do not invent data or values.
- Do not use external websites or general LLM knowledge as evidence.
- Do not independently declare a beneficiary fraudulent.
- Do not make final administrative decisions.

## Architecture Principle
Use structured database queries for numerical and record-level questions.

Use RAG for schema descriptions, field definitions, data dictionaries and explanations of existing system flags.

The LLM should explain verified results, not invent them.

## Development Scope
The first version is a standalone prototype. Integration with the existing RationRight application will happen later through APIs.

