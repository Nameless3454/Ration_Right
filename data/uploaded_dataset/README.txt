# RationRight synthetic demo dataset

All records are fictional and intended only for UI, API integration, and anomaly-detection testing. They are not government records and must not be used to accuse or deny benefits to real people.

## Demo API credentials
For a local mock backend only:
- API_KEY: RATIONRIGHT_DEMO_KEY_2026
- Header: x-api-key: RATIONRIGHT_DEMO_KEY_2026

This is a public placeholder, NOT a real secret and NOT a hosted API key.

## Suggested REST endpoints
- GET /api/beneficiaries
- GET /api/pwd-shops
- GET /api/inventory
- GET /api/transactions
- GET /api/pwd-audits
- GET /api/alerts

## Suggested alert rules
1. Possible duplicate: repeated identity/household fingerprint.
2. Multiple claims: repeated successful transaction for same beneficiary, commodity and entitlement period.
3. Stock mismatch: expected closing = opening + received - distributed; compare with recorded closing and physical stock.
4. Unusual manual activity: high manual override count, repeated complaints, failed inspection, or late opening.
5. Every alert is a review lead, not proof of fraud. Require field verification and allow correction/appeal.

## Example request
curl -H "x-api-key: RATIONRIGHT_DEMO_KEY_2026" http://localhost:3000/api/beneficiaries
