# RationRight - Project Memory

## Project Overview
RationRight is a multi-agent AI platform for detecting and investigating suspicious patterns in Indian Public Distribution System (PDS) data.

## Architecture
- **Backend**: Python 3.9+ (standard library only, no dependencies)
- **Frontend**: Vanilla JavaScript (no framework)
- **Database**: SQLite (data/rationright.db)
- **AI Integration**: OpenAI API (server-side, never exposed to frontend)

## Core Pipeline
```
Data → Analytics → AI → Evidence → Alerts → Simulation → Action
```

## Agent Workflow
1. **Agent 1** - Transaction Analyst: Detects rapid geographic transactions
2. **Agent 2** - Anomaly Investigator: Verifies findings
3. **Agent 3** - Evidence Builder: Creates investigation cases
4. **Agent 4** - Alert Generator: Generates alerts

## Dataset Types
The system supports these dataset types:
- `ration_transactions` - Transaction-level data (required for AI analysis)
- `beneficiaries` - Beneficiary records
- `fps_centers` - Fair Price Shop centers
- `inventory` - Stock levels
- `combined` - Mixed dataset
- `operational_summary` - District-level aggregate reports (NEW)

## Recent Changes (Phase 17+)

### Operational Summary Support
Added support for importing district-level operational summary reports (e.g., PDS authentication reports with columns like District, Total Cards, Biometric, Aadhar OTP, etc.).

**Files Modified:**
- `ingestion/mapping.py` - Added `operational_summary` dataset type with detection, fields, aliases, and validation
- `ingestion/validation.py` - Added validation for operational summary number fields and report_date
- `ingestion/importer.py` - Added handling for operational summary records in `_stage_record` and `flush`
- `database.py` - Added `operational_summaries` table with insert/query functions
- `static/app.js` - Added `operational_summary` to upload types, fields, and helpful info message

**Detection Logic:**
- Detects files with district + total_cards/total_transactions/biometric columns
- Automatically classifies as "Operational / District Summary"
- Shows info message explaining it cannot be used for transaction-level anomaly detection

## Synthetic Dataset v2
- **21,709 transactions** (seed=42, deterministic)
- **2,500 beneficiaries**
- **120 FPS centers**
- **20 districts** across 8 states
- **5 commodities** (rice, wheat, pulses, sugar, millet)
- **15 seeded anomalies** (rapid geographic transactions)
- **0 false positives** in normal transactions
- **100% detection rate** for seeded anomalies

**Anomaly Thresholds (from agents/pattern_config.py):**
- `RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES = 60` (interval <= 60 min)
- `RAPID_GEOGRAPHIC_MIN_DISTANCE_KM = 100` (distance >= 100 km)

## Key Endpoints
- `GET /api/health` - System health check
- `GET /api/ready` - Readiness check
- `POST /api/analyze` - Run AI analysis (supports synthetic and real datasets)
- `GET /api/datasets` - List available datasets
- `GET /api/alerts` - Get alerts
- `GET /api/command-center` - Command center data

## Test Status
- **459 tests passing** (Phase 15 count)
- All ingestion tests pass
- AI evaluation scorecard: all PASS

## Known Limitations
- No live government API integration
- Optional LLM (works with deterministic fallback)
- Single-operator authentication
- Synthetic data for demo purposes

## Deployment
```bash
# Start server
python3 server.py --port 8000

# Run tests
python3 -m unittest discover -s tests -t .

# Health check
curl http://127.0.0.1:8000/api/health
```
