# RationRight — Demo Checklist

Run through this checklist before presenting. All checks pass on a clean
checkout with a stock Python 3.9+.

## Setup

- [ ] Environment configured (no env vars required; optional
      `RATIONRIGHT_ANALYZE_DELAY_MS` for observing the loading state)
- [ ] Backend starts: `python3 server.py` prints the URL, no startup errors
- [ ] Frontend starts (served by the same process) — dashboard renders
- [ ] Dataset loads: dashboard chip shows "Synthetic demo data · 25 transactions"
- [ ] `python3 scripts/health_check.py` prints PASS for every component

## Core flow

- [ ] Open `http://127.0.0.1:8000` — dashboard renders
- [ ] Click **Run Analysis** — button disables, truthful loading message appears
- [ ] Double-clicking during the run does not start a second workflow
- [ ] Agent 1 works — detects `ANOM001` (TX001/TX002, BEN001)
- [ ] Agent 2 works — verifies `FIND001` (12.0 minutes, 1148.09 km)
- [ ] Agent 3 works — builds case `CASE001` (requires human review)
- [ ] Agent 4 works — generates alert `ALERT001` (open, high)
- [ ] Alert generated and displayed with Alert / Case / Finding / Anomaly /
      Transaction IDs
- [ ] Evidence displayed and matches the backend exactly (12 minutes,
      1148.09 km)
- [ ] Source transactions visible in the transaction table (TX001, TX002)
- [ ] Human review visible: "Pending human review", "Human verification"
- [ ] **Reset Demo** returns to a clean state and re-enables Run Analysis

## Failure behavior

- [ ] Stopping the server, then Run Analysis, shows a clear error (never
      "completed")
- [ ] Restarting the server and clicking **Retry** completes the analysis

## Quality gates

- [ ] No critical console errors in the browser dev tools during the flow
- [ ] No critical backend errors in the server log
- [ ] UI responsive at desktop and narrower widths (no horizontal page overflow)
- [ ] All unit/integration tests pass (456 as of Phase 15):
      `python3 -m unittest discover -s tests -t . -v`
      (full results: see QA_REPORT.md)
- [ ] Official demo guide: see docs/DEMO.md (timed script, click path,
      reset, failure fallbacks)
- [ ] Five complete end-to-end runs pass (each: Run Analysis → alert →
      evidence → transactions)
- [ ] 60-second demo passes (problem → dashboard → run → workflow → alert →
      evidence → human review)
