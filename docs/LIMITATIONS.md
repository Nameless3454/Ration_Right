# RationAI — Known Limitations

Presented professionally and honestly. RationAI does not claim capabilities
it does not have.

## 1. No live government data

The Phase 7 connector for official PDS data is implemented and documented but
**not connected**: no live credentials or verified government source exist in
this deployment. The UI always shows `CONNECTOR READY / NOT CONNECTED` for it
and never claims live/verified status. All demonstrated data is either a real
**imported dataset** (clearly labeled) or the **synthetic demo dataset**
(labeled "Synthetic Demo Data").

## 2. AI is optional and external

- Narratives (explanations, summaries, interpretations) depend on an
  OpenAI-compatible endpoint when `RATIONRIGHT_LLM_ENABLED=1` and a key are
  set. Without them, deterministic templates are used — the platform is fully
  functional either way.
- The AI only interprets supplied, pre-computed facts. It never performs
  arithmetic, thresholds, or evidence calculations.
- **No AI accuracy percentage is claimed** — there is insufficient evaluation
  data, and the Phase 15 scorecard measures the architecture (what the model
  receives, what code protects), not a specific model's output.
- Model availability, latency, and cost are external factors.

## 3. Single-operator scope

The optional authentication is a **single shared access token**, not
multi-user accounts or role-based authorization. This is deliberate for the
hackathon/demo scope. There is no per-user data isolation because there are
no per-user accounts.

## 4. Database and scale

- SQLite: excellent for the demo and small deployments; a client-server
  database (PostgreSQL) is future work.
- Verified at 20,000-row import scale; production-scale (millions of rows)
  datasets were not available for testing.
- Rate limiting is in-memory and per-process (resets on restart).
- Session revocation is in-memory (resets on restart).

## 5. Notifications

Alerts are in-app only. Email/SMS/push notifications are **not** implemented
and are never sent — by design.

## 6. Geography

District/FPS risk views use tabular rankings, not a real map. Location data
is only as complete as the imported dataset (records without coordinates are
honestly skipped by the anomaly agent).

## 7. Time

Dates are stored as ISO strings; timezone handling is minimal and data
assumes the source's local time. Day-level windows are UTC-agnostic.
