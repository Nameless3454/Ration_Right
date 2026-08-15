# RationAI — Official Demo Guide

A repeatable demo that shows the complete decision-intelligence workflow.
The demo database (`data/rationright.db`) already contains imported datasets,
alerts, insights, and reports — **no manual database edits are needed during
the presentation**.

## Before the demo

1. Start the server:

   ```bash
   python3 server.py --db data/rationright.db
   ```

2. Open `http://127.0.0.1:8000/#/command` and confirm:
   - The Command Center loads with 8 KPI cards and a green "Data fresh" chip.
   - The Alert Center bell shows the active-alert count.
3. If the LLM is enabled (`.env`), the executive summary is AI-written; if
   not, it is the deterministic summary — both are correct for the demo.
4. To restore a clean state: see [Reset](#reset-procedure).

## The 6-minute script

| Time | Step | Where | What the judge sees |
|------|------|-------|---------------------|
| 0:00 | **Problem** | — | "PDS systems produce huge operational data; identifying supply risk and anomalies is reactive. RationAI turns it into a decision workflow: Data → Analytics → AI → Evidence → Alerts → Simulation → Action." |
| 0:30 | **Command Center** | `#/command` | Data-status chip (fresh), executive summary, KPI cards (distribution, coverage, alerts, quality), risk overview (Critical/High/Medium chips). |
| 1:00 | **Data honesty** | Command Center → Data Sources (`#/sources`) | Show the government connector: **CONNECTOR READY / NOT CONNECTED** — "Live government API credentials are not configured; this demo runs on a real imported dataset, clearly labeled." |
| 1:30 | **Risk detection** | Command Center risk chips → Alert Center | Click a severity chip → Alert Center opens pre-filtered. Open a HIGH/CRITICAL alert: current value vs threshold vs difference, evidence (stock, consumption, coverage), lineage (source/dataset/import). |
| 2:00 | **AI analysis** | `#/analysis` (AI Analysis) | Select the imported dataset, choose agents (Distribution Anomaly, Inventory Risk, Demand, Recommendations), Run → real agent execution status → completed insights. |
| 2:45 | **Evidence** | Click an insight → View Evidence | Observed vs expected vs deviation, district/FPS, supporting records, dataset/import/analysis IDs. Emphasize: every number is calculated, the AI only interprets. |
| 3:15 | **Alert** | Alert Center | Acknowledge an alert (status → ACKNOWLEDGED, timestamp recorded), or show the OPEN → RESOLVED lifecycle. |
| 3:45 | **What-If** | Alert → Run What-If → Decision Support (`#/simulation`) | Demand +10% + supply delay 7 days → before/after coverage, deterministic impact, risk, AI interpretation. "Simulation never modifies real data — verified." |
| 4:30 | **Recommendation** | Simulation result / Alert details | Priority, action, reason, evidence. "Decision support, not automated action." |
| 5:00 | **Intelligence report** | Command Center → Generate Report | RPT-… generated, opened: executive summary → KPIs → risk → alerts → insights → actions → data quality → lineage. Export JSON/CSV. |
| 5:30 | **Architecture / lineage** | Report lineage + `docs/ARCHITECTURE.md` | Source → Import → Analysis → Insight → Alert → Report. "Every answer is traceable to its origin." |
| 6:00 | **Conclusion** | — | "Deterministic core + AI interpretation + full traceability. Not a chatbot — a decision-intelligence workflow." |

## Exact click path

1. `#/command` → observe KPIs → click a severity chip (e.g. **HIGH**) → Alert Center opens filtered.
2. Alert Center → open an alert → **View Details** → evidence + lineage → **Run What-If**.
3. Decision Support → keep the preselected dataset/commodity → set **Demand +10%**, **Supply delay 7** → **Run Simulation** → read impact/risk/recommendation.
4. Back to `#/command` → **Generate Report** → click the new report in the history → **Export JSON / CSV**.

## Expected behavior

- Every number on screen comes from the database (backend-computed).
- AI-generated text is labeled **AI interpretation**; deterministic values are
  labeled **Calculated** — the two never mix.
- No console errors; all API calls return 200.
- The sidebar, ⌘K palette, and data-status chip work throughout.

## Reset procedure

- **Frontend state**: the profile menu → **Log out** → **Reset demo state**
  clears in-memory state (safe; does not touch the database).
- **Database**: the demo database is regenerable and idempotent:

  ```bash
  # WARNING: resets ONLY the synthetic demo source's rows in the given DB.
  python3 scripts/seed_database.py --db data/rationright.db
  ```

  For a completely fresh demo database, copy `data/rationright.db` to a
  backup before the event, then restore it if the demo goes wrong.

## Failure fallback plan (demo never dies)

| Failure | Fallback |
|---------|----------|
| **LLM/OpenAI down or no key** | Everything keeps working — deterministic summaries/explanations are used, labeled "Deterministic". Say: "AI narratives are optional; the platform is deterministic-first." |
| **External source unavailable** | Connectors are `CONNECTOR_READY / NOT_CONNECTED` by design — there is nothing to fail; show the label honestly. |
| **Database corrupted/locked** | Restart with a fresh DB: `python3 server.py --db data/rationright.db` (or restore your backup). The schema auto-creates. |
| **Import fails mid-demo** | The import is transactional — it rolls back cleanly with an error message; the previous dataset stays intact. |
| **Network/console error on a widget** | Widgets render individual error + Retry states; other widgets keep working. |

## Troubleshooting

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).
