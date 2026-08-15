"""RationAI — AI Analysis Command Center backend (Phase 9).

Builds the command-center experience on top of the EXISTING Phase 6
multi-agent architecture and Phase 8 lineage — no second AI architecture, no
new agents, no fake results:

    Dataset (real import or synthetic)
        -> filters (commodity / FPS / district / date range, validated)
        -> Phase 6 workflow (the same 4 agents) for agent-based analysis types
        -> deterministic per-import calculations for the rest
        -> a unified ``insights`` array + per-type status map
        -> a persisted analysis run (RA-YYYY-NNNN) with types/filters/timings

Five analysis types are offered. Two map to the real agents; three are
clearly labeled deterministic calculations (no LLM) computed by this module
from database records with documented sufficiency gates:

    distribution_anomaly  -> Agents 1-2 (detect + verify)   [agents]
    recommendations       -> Agents 3-4 (case + alert)      [agents]
    operational_risk      -> DB checks (failure rate,       [deterministic]
                             recent distribution, low stock)
    inventory_risk        -> stock vs consumption projection [deterministic]
    demand_forecast       -> linear trend projection with a  [deterministic]
                             sufficiency gate (>=3 periods)

Every insight carries ``deterministic: true|false`` so the UI can always
distinguish CALCULATED values from AI interpretation, and a ``source`` block
(dataset, import, analysis id) so each insight stays traceable.

Nothing is invented: agents that lack data report INSUFFICIENT_DATA with a
reason instead of producing guesses, and no token/cost metrics are exposed
(the backend does not record them).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from analytics import (
    FAILURE_MIN_TRANSACTIONS,
    FAILURE_RATE_THRESHOLD,
    INVENTORY_CRITICAL_DAYS,
    INVENTORY_WARNING_DAYS,
    NO_RECENT_DISTRIBUTION_DAYS,
)
from data_context import (
    MIN_TRANSACTIONS_FOR_AGENTS,
    get_import_metadata,
    prepare_agent_context,
    run_workflow_on_dataset,
    synthetic_dataset_block,
)
from database import (
    DEFAULT_DB_PATH,
    get_data_source_by_name,
    insert_ai_insight,
    open_db,
)
from pipeline import record_analysis_run
from scripts.validate_dataset import DEFAULT_DATASET_PATH, load_dataset
from workflow import run_workflow

logger = logging.getLogger("rationright.analysis_center")

#: Minimum distinct months of history required for a deterministic forecast.
MIN_FORECAST_PERIODS = 3

ANALYSIS_TYPES = [
    {
        "key": "distribution_anomaly",
        "label": "Distribution Anomaly Detection",
        "kind": "agents",
        "agents": ["agent_1", "agent_2"],
        "description": "Identify unusual distribution patterns using the real "
                       "Agent 1 (detection) and Agent 2 (verification) pipeline.",
    },
    {
        "key": "recommendations",
        "label": "Recommendations & Alerts",
        "kind": "agents",
        "agents": ["agent_3", "agent_4"],
        "description": "Build an investigation case (Agent 3) and generate a "
                       "human-review alert with a recommended action (Agent 4).",
    },
    {
        "key": "operational_risk",
        "label": "Operational Risk",
        "kind": "deterministic",
        "description": "Deterministic database checks: elevated transaction "
                       "failure rate, no recent distribution, low inventory.",
    },
    {
        "key": "inventory_risk",
        "label": "Inventory Risk",
        "kind": "deterministic",
        "description": "Deterministic stock projection: days remaining from "
                       "current stock and monthly consumption.",
    },
    {
        "key": "demand_forecast",
        "label": "Demand Forecasting",
        "kind": "deterministic",
        "description": "Deterministic linear-trend projection of future demand "
                       "from at least %d months of history." % MIN_FORECAST_PERIODS,
    },
]

VALID_ANALYSIS_TYPES = {t["key"] for t in ANALYSIS_TYPES}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def analysis_type_registry() -> list:
    """Public registry of selectable analysis types (labels + descriptions)."""
    return list(ANALYSIS_TYPES)


def _synthetic_import_id(conn) -> Optional[int]:
    source = get_data_source_by_name(conn, "Synthetic Demo Dataset")
    if source is None:
        return None
    row = conn.execute(
        "SELECT id FROM data_imports WHERE data_source_id = :sid ORDER BY id DESC LIMIT 1",
        {"sid": source["id"]},
    ).fetchone()
    return row["id"] if row else None


def _filter_synthetic(transactions: list, filters: dict) -> list:
    """Apply commodity/date filters to the synthetic transaction list."""
    commodity = (filters.get("commodity") or "").strip().lower()
    from_date = (filters.get("from_date") or "").strip()
    to_date = (filters.get("to_date") or "").strip()
    out = []
    for tx in transactions:
        if commodity and (tx.get("ration_type") or "").strip().lower() != commodity:
            continue
        ts = (tx.get("timestamp") or "")[:10]
        if from_date and ts < from_date[:10]:
            continue
        if to_date and ts > to_date[:10]:
            continue
        out.append(tx)
    return out


# ---------------------------------------------------------------------------
# Precheck — verified before anything runs
# ---------------------------------------------------------------------------

def precheck(
    *,
    dataset_mode: str,
    data_import_id: Optional[int] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> dict:
    """Readiness report for one dataset + every analysis type.

    Every number is queried from the database. Types whose required data is
    missing are reported DISABLED with a reason — they never run and never
    produce guessed results.
    """
    conn = open_db(db_path)
    try:
        if dataset_mode == "real":
            imp = get_import_metadata(data_import_id, db_path) if data_import_id else None
            if imp is None:
                return {"ok": False, "error": "Unknown dataset import."}
            record_count = imp.get("record_count") or 0
            valid_count = imp.get("successful_records") or 0
            tx_count = conn.execute(
                "SELECT COUNT(*) AS n FROM ration_transactions WHERE source_import_id = :imp",
                {"imp": data_import_id},
            ).fetchone()["n"]
            coords = conn.execute(
                "SELECT COUNT(*) AS n FROM ration_transactions "
                "WHERE source_import_id = :imp AND latitude IS NOT NULL AND longitude IS NOT NULL",
                {"imp": data_import_id},
            ).fetchone()["n"]
            inventory_count = conn.execute(
                "SELECT COUNT(*) AS n FROM inventory WHERE source_import_id = :imp",
                {"imp": data_import_id},
            ).fetchone()["n"]
            months = conn.execute(
                "SELECT COUNT(DISTINCT substr(transaction_date, 1, 7)) AS n "
                "FROM ration_transactions WHERE source_import_id = :imp "
                "AND transaction_date IS NOT NULL",
                {"imp": data_import_id},
            ).fetchone()["n"]
            dataset = {
                "dataset_name": imp.get("dataset_name"),
                "source_name": imp.get("source_name"),
                "data_import_id": data_import_id,
                "record_count": record_count,
                "valid_records": valid_count,
                "invalid_records": imp.get("failed_records") or 0,
                "duplicates": imp.get("duplicate_records") or 0,
                "transaction_count": tx_count,
                "inventory_count": inventory_count,
                "historical_months": months,
                "quality": round(valid_count / record_count * 100, 1) if record_count else None,
            }
        else:
            tx_count = len(_filter_synthetic(
                load_dataset(DEFAULT_DATASET_PATH)["transactions"], {}
            ))
            coords = tx_count  # the synthetic dataset always carries coordinates
            inventory_count = 0
            months = conn.execute(
                "SELECT COUNT(DISTINCT substr(transaction_date, 1, 7)) AS n "
                "FROM ration_transactions WHERE source_import_id = :imp",
                {"imp": _synthetic_import_id(conn)},
            ).fetchone()["n"] if _synthetic_import_id(conn) else 0
            dataset = {
                "dataset_name": "Synthetic Demo Dataset",
                "source_name": "Synthetic Demo Dataset",
                "data_import_id": None,
                "record_count": tx_count,
                "valid_records": tx_count,
                "invalid_records": 0,
                "duplicates": 0,
                "transaction_count": tx_count,
                "inventory_count": 0,
                "historical_months": months,
                "quality": 100.0,
            }

        checks = {
            "dataset_available": {"ok": True, "detail": dataset["dataset_name"]},
            "valid_records": {"ok": dataset["valid_records"] > 0,
                              "detail": "%d valid record(s)" % dataset["valid_records"]},
            "sufficient_transactions": {"ok": tx_count >= MIN_TRANSACTIONS_FOR_AGENTS,
                                        "detail": "%d transaction(s); %d required for agent analysis"
                                                  % (tx_count, MIN_TRANSACTIONS_FOR_AGENTS)},
            "coordinates_available": {"ok": coords > 0,
                                      "detail": "%d transaction(s) with coordinates"
                                                % coords if coords else "no coordinates — "
                                                "geographic verification is limited"},
        }

        types = []
        for t in ANALYSIS_TYPES:
            key = t["key"]
            if key == "distribution_anomaly":
                enabled = tx_count >= MIN_TRANSACTIONS_FOR_AGENTS
                reason = None if enabled else (
                    "Only %d transaction(s) available; at least %d required." % (
                        tx_count, MIN_TRANSACTIONS_FOR_AGENTS))
            elif key == "recommendations":
                enabled = tx_count >= MIN_TRANSACTIONS_FOR_AGENTS
                reason = None if enabled else (
                    "Requires distribution anomaly detection to run first.")
            elif key == "operational_risk":
                enabled = tx_count > 0
                reason = None if enabled else "No transactions to check."
            elif key == "inventory_risk":
                enabled = inventory_count > 0
                reason = None if enabled else (
                    "This dataset has no inventory records; import an inventory "
                    "dataset to enable stock-risk analysis.")
            elif key == "demand_forecast":
                enabled = months >= MIN_FORECAST_PERIODS
                reason = None if enabled else (
                    "Only %d historical month(s) available; at least %d are "
                    "required for a reliable forecast." % (months, MIN_FORECAST_PERIODS))
            else:
                enabled, reason = False, "Unknown analysis type."
            types.append({"key": key, "label": t["label"], "kind": t["kind"],
                          "enabled": enabled, "reason": reason})
    finally:
        conn.close()

    return {"ok": True, "dataset": dataset, "checks": checks, "types": types,
            "generated_at": _now_iso()}


# ---------------------------------------------------------------------------
# Deterministic per-import insights (calculated, not AI)
# ---------------------------------------------------------------------------

def _insight(insight_type, severity, title, summary, *, evidence=None,
             confidence=None, recommendation=None, entity_type=None,
             entity_id=None, deterministic=True, status="completed",
             reason=None, source=None):
    return {
        "insight_type": insight_type,
        "severity": severity,
        "title": title,
        "summary": summary,
        "evidence": evidence or {},
        "confidence": confidence,
        "recommendation": recommendation,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "deterministic": deterministic,
        "status": status,
        "reason": reason,
        "source": source or {},
    }


def operational_risk_insights(conn, import_id: int, source: dict) -> list:
    """Per-import operational checks (failure rate / inactivity / low stock).

    Same documented thresholds as the Phase 5 operational alerts
    (FAILURE_RATE_THRESHOLD, NO_RECENT_DISTRIBUTION_DAYS), computed only for
    centers touched by this dataset.
    """
    insights = []

    # 1. Elevated failure rate per FPS in this import.
    for r in conn.execute(
        "SELECT COALESCE(f.fps_code, 'Unknown') AS fps_code, "
        " COALESCE(SUM(CASE WHEN t.status = 'FAILED' THEN 1 ELSE 0 END), 0) AS failed, "
        " COALESCE(SUM(CASE WHEN t.status IN ('COMPLETED','FAILED') THEN 1 ELSE 0 END), 0) AS total "
        "FROM ration_transactions t LEFT JOIN fps_centers f ON f.id = t.fps_center_id "
        "WHERE t.source_import_id = :imp GROUP BY fps_code",
        {"imp": import_id},
    ):
        total = r["total"]
        if total < FAILURE_MIN_TRANSACTIONS:
            continue
        rate = r["failed"] / total
        if rate >= FAILURE_RATE_THRESHOLD:
            insights.append(_insight(
                "OPERATIONAL_RISK", "MEDIUM",
                "Transaction failure rate is elevated at %s" % r["fps_code"],
                "%d of %d transactions at %s failed (%.0f%% >= %.0f%% threshold). "
                "Requires human review." % (r["failed"], total, r["fps_code"],
                                            rate * 100, FAILURE_RATE_THRESHOLD * 100),
                evidence={"failed_transactions": r["failed"], "total_transactions": total,
                          "failure_rate": round(rate, 4),
                          "threshold": FAILURE_RATE_THRESHOLD},
                entity_type="fps_center", entity_id=r["fps_code"], source=source,
            ))

    # 2. No recent distribution — reference date is this import's newest tx.
    latest = conn.execute(
        "SELECT MAX(transaction_date) AS d FROM ration_transactions "
        "WHERE source_import_id = :imp", {"imp": import_id},
    ).fetchone()["d"]
    if latest:
        cutoff = (datetime.fromisoformat(str(latest)[:10]) -
                  timedelta(days=NO_RECENT_DISTRIBUTION_DAYS)).date().isoformat()
        for r in conn.execute(
            "SELECT f.id, f.fps_code, f.name, f.district, "
            " COALESCE(SUM(CASE WHEN t.status = 'COMPLETED' THEN 1 ELSE 0 END), 0) AS completed "
            "FROM fps_centers f LEFT JOIN ration_transactions t "
            "  ON t.fps_center_id = f.id AND t.source_import_id = :imp "
            "  AND substr(t.transaction_date, 1, 10) >= :cutoff "
            "GROUP BY f.id HAVING completed = 0",
            {"imp": import_id, "cutoff": cutoff},
        ):
            insights.append(_insight(
                "OPERATIONAL_RISK", "LOW",
                "No recent distribution activity at %s" % r["fps_code"],
                "No completed distribution was recorded at %s in the last %d days "
                "(reference date %s)." % (r["fps_code"], NO_RECENT_DISTRIBUTION_DAYS, cutoff),
                evidence={"reference_date": cutoff,
                          "recent_days": NO_RECENT_DISTRIBUTION_DAYS},
                entity_type="fps_center", entity_id=r["fps_code"], source=source,
            ))

    # 3. Low stock from this import's inventory records.
    for r in conn.execute(
        "SELECT i.commodity, i.current_stock, i.reorder_threshold, "
        " COALESCE(f.fps_code, 'Unknown') AS fps_code "
        "FROM inventory i LEFT JOIN fps_centers f ON f.id = i.fps_center_id "
        "WHERE i.source_import_id = :imp AND i.reorder_threshold IS NOT NULL "
        "AND i.current_stock < i.reorder_threshold "
        "ORDER BY (i.reorder_threshold - i.current_stock) DESC",
        {"imp": import_id},
    ):
        insights.append(_insight(
            "OPERATIONAL_RISK", "HIGH",
            "Inventory below reorder threshold at %s" % r["fps_code"],
            "Stock of %s at %s is below the reorder threshold (%.2f < %.2f)."
            % (r["commodity"], r["fps_code"], r["current_stock"], r["reorder_threshold"]),
            evidence={"current_stock": r["current_stock"],
                      "reorder_threshold": r["reorder_threshold"]},
            recommendation="Review replenishment for %s at %s." % (r["commodity"], r["fps_code"]),
            entity_type="fps_center", entity_id=r["fps_code"], source=source,
        ))
    return insights


def inventory_risk_insights(conn, import_id: int, source: dict) -> list:
    """Stock-vs-consumption projection with documented thresholds.

    days_remaining = current_stock / (monthly_consumption / 30); CRITICAL < 15,
    WARNING < 30, else HEALTHY (same constants as Phase 5 analytics).
    """
    insights = []
    for r in conn.execute(
        "SELECT i.commodity, i.current_stock, i.monthly_consumption, "
        " i.reorder_threshold, COALESCE(f.fps_code, 'Unknown') AS fps_code "
        "FROM inventory i LEFT JOIN fps_centers f ON f.id = i.fps_center_id "
        "WHERE i.source_import_id = :imp ORDER BY i.commodity, fps_code",
        {"imp": import_id},
    ):
        stock = r["current_stock"]
        monthly = r["monthly_consumption"]
        if monthly is None or monthly <= 0:
            continue
        days = stock / (monthly / 30.0)
        if days < INVENTORY_CRITICAL_DAYS:
            severity, status = "CRITICAL", "at risk of running out within %d days" % INVENTORY_CRITICAL_DAYS
        elif days < INVENTORY_WARNING_DAYS:
            severity, status = "HIGH", "approaching the %d-day warning threshold" % INVENTORY_WARNING_DAYS
        else:
            severity, status = "LOW", "healthy"
        insights.append(_insight(
            "INVENTORY_RISK", severity,
            "%s stock at %s may fall below safe levels" % (r["commodity"], r["fps_code"]),
            "Current stock of %s at %s covers approximately %.1f days at the "
            "observed consumption rate (%s)." % (r["commodity"], r["fps_code"], days, status),
            evidence={
                "current_stock": stock,
                "monthly_consumption": monthly,
                "daily_consumption": round(monthly / 30.0, 2),
                "days_remaining": round(days, 1),
                "reorder_threshold": r["reorder_threshold"],
                "critical_threshold_days": INVENTORY_CRITICAL_DAYS,
                "warning_threshold_days": INVENTORY_WARNING_DAYS,
            },
            recommendation="Initiate replenishment review for %s at %s." % (
                r["commodity"], r["fps_code"]),
            entity_type="fps_center", entity_id=r["fps_code"], source=source,
        ))
    return insights


def demand_forecast_insights(conn, import_id: int, source: dict) -> list:
    """Deterministic linear-trend forecast per commodity.

    Uses each commodity's monthly totals; at least MIN_FORECAST_PERIODS months
    are required, otherwise a structured INSUFFICIENT_DATA insight is returned
    instead of a guessed forecast. The formula (least-squares slope projected
    one period) is documented and reproducible.
    """
    rows = conn.execute(
        "SELECT substr(transaction_date, 1, 7) AS period, commodity, "
        " SUM(quantity) AS qty "
        "FROM ration_transactions WHERE source_import_id = :imp "
        "AND transaction_date IS NOT NULL "
        "GROUP BY period, commodity ORDER BY period",
        {"imp": import_id},
    ).fetchall()
    by_commodity = {}
    for r in rows:
        by_commodity.setdefault(r["commodity"], {})[r["period"]] = r["qty"]

    insights = []
    for commodity in sorted(by_commodity):
        periods = sorted(by_commodity[commodity])
        if len(periods) < MIN_FORECAST_PERIODS:
            insights.append(_insight(
                "DEMAND_FORECAST", "LOW",
                "Demand forecast not available for %s" % commodity,
                "Not enough history for a reliable forecast.",
                evidence={"historical_periods": len(periods),
                          "required_periods": MIN_FORECAST_PERIODS},
                status="insufficient_data",
                reason="Only %d historical period(s) available for %s; at least %d "
                       "are required." % (len(periods), commodity, MIN_FORECAST_PERIODS),
                entity_type="commodity", entity_id=commodity, source=source,
            ))
            continue
        # least-squares slope over index positions 0..n-1
        n = len(periods)
        x_mean = (n - 1) / 2.0
        y_mean = sum(by_commodity[commodity][p] for p in periods) / n
        num = sum((i - x_mean) * (by_commodity[commodity][p] - y_mean)
                  for i, p in enumerate(periods))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / den if den else 0.0
        predicted = max(0.0, y_mean + slope * n)  # one period ahead
        trend = "INCREASING" if slope > 0 else ("DECREASING" if slope < 0 else "STABLE")
        # deterministic confidence: fit quality, capped at 0.9
        if den and sum((i - x_mean) ** 2 for i in range(n)) > 0:
            ss_res = sum((by_commodity[commodity][p] - (y_mean + slope * (i - x_mean))) ** 2
                         for i, p in enumerate(periods))
            ss_tot = sum((by_commodity[commodity][p] - y_mean) ** 2 for p in periods)
            r_squared = 1 - ss_res / ss_tot if ss_tot else 0.0
            confidence = round(max(0.0, min(0.9, r_squared)), 2)
        else:
            confidence = None
        insights.append(_insight(
            "DEMAND_FORECAST", "MEDIUM" if abs(slope) > 0 else "LOW",
            "%s demand forecast for %s" % (trend.title(), commodity),
            "Monthly demand for %s is projected at %.0f kg for the next period "
            "(%s trend across %d observed period(s))." % (
                commodity, predicted, trend.lower(), n),
            evidence={"commodity": commodity,
                      "forecast_period": _next_period(periods[-1]),
                      "predicted_quantity": round(predicted, 1),
                      "trend": trend,
                      "historical_periods": len(periods),
                      "historical_basis": {p: round(by_commodity[commodity][p], 1)
                                           for p in periods}},
            confidence=confidence,
            recommendation="Use the projected demand to plan allocation for %s."
                           % commodity,
            entity_type="commodity", entity_id=commodity, source=source,
        ))
    if not insights:
        insights.append(_insight(
            "DEMAND_FORECAST", "LOW", "Demand forecast not available",
            "This dataset has no dated transactions to project demand from.",
            status="insufficient_data",
            reason="No historical transaction periods are available.",
            source=source,
        ))
    return insights


def _next_period(period: str) -> str:
    year, month = int(period[:4]), int(period[5:7])
    month += 1
    if month > 12:
        month, year = 1, year + 1
    return "%04d-%02d" % (year, month)


# ---------------------------------------------------------------------------
# Run (the command center path)
# ---------------------------------------------------------------------------

def _source_block(dataset_block: dict, analysis_id: str) -> dict:
    return {
        "dataset_name": dataset_block.get("dataset_name"),
        "source_name": dataset_block.get("source_name"),
        "data_import_id": dataset_block.get("data_import_id"),
        "mode": dataset_block.get("mode"),
        "analysis_id": analysis_id,
    }


def run_analysis(
    *,
    dataset_mode: str,
    data_import_id: Optional[int] = None,
    types: Optional[list] = None,
    filters: Optional[dict] = None,
    db_path: str = DEFAULT_DB_PATH,
    max_interval_minutes: Optional[int] = None,
    min_distance_km: Optional[float] = None,
) -> Optional[dict]:
    """Run the command-center analysis and return the merged result.

    Returns None if the requested real import does not exist. The result keeps
    the exact Phase 6 shape (so the existing Analysis view still works) plus:
    ``insights`` (unified array), ``types`` (per-type status map), ``config``,
    ``analysis_run`` (persisted lineage metadata), and ``timings``.
    """
    import time as _time

    _started = _time.perf_counter()
    types = [t for t in (types or []) if t in VALID_ANALYSIS_TYPES]
    filters = {k: v for k, v in (filters or {}).items() if v}
    if not types:
        types = ["distribution_anomaly", "recommendations"]

    agent_types = [t for t in types if t in ("distribution_anomaly", "recommendations")]
    deterministic_types = [t for t in types if t not in ("distribution_anomaly", "recommendations")]

    if dataset_mode == "real":
        result = run_workflow_on_dataset(
            data_import_id, db_path=db_path, filters=filters,
            max_interval_minutes=max_interval_minutes,
            min_distance_km=min_distance_km,
        )
        if result is None:
            return None
        dataset_block = result.get("dataset") or {}
    else:
        transactions = _filter_synthetic(
            load_dataset(DEFAULT_DATASET_PATH)["transactions"], filters)
        kwargs = {}
        if max_interval_minutes is not None:
            kwargs["max_interval_minutes"] = max_interval_minutes
        if min_distance_km is not None:
            kwargs["min_distance_km"] = min_distance_km
        result = run_workflow(transactions, **kwargs)
        result["dataset"] = synthetic_dataset_block(transactions)
        if filters:
            result["dataset"]["filters_applied"] = filters
        dataset_block = result["dataset"]

    # ---- deterministic types ----------------------------------------------
    insights = []
    types_status = {}
    analysis_id = "PENDING"
    if deterministic_types:
        conn = open_db(db_path)
        try:
            import_id_for_deterministic = data_import_id if dataset_mode == "real" else _synthetic_import_id(conn)
            source = {"dataset_name": dataset_block.get("dataset_name"),
                      "source_name": dataset_block.get("source_name"),
                      "data_import_id": import_id_for_deterministic,
                      "mode": dataset_mode,
                      "analysis_id": analysis_id}
            if "operational_risk" in deterministic_types:
                ops = operational_risk_insights(conn, import_id_for_deterministic, source) if import_id_for_deterministic else []
                types_status["operational_risk"] = {"status": "completed",
                                                    "count": len(ops),
                                                    "reason": None if ops else "No operational signals detected in this dataset."}
                insights.extend(ops)
            if "inventory_risk" in deterministic_types:
                inv = inventory_risk_insights(conn, import_id_for_deterministic, source) if import_id_for_deterministic else []
                types_status["inventory_risk"] = {"status": "completed" if inv else "insufficient_data",
                                                  "count": len(inv),
                                                  "reason": None if inv else "No inventory records in this dataset."}
                insights.extend(inv)
            if "demand_forecast" in deterministic_types:
                fc = demand_forecast_insights(conn, import_id_for_deterministic, source) if import_id_for_deterministic else [
                    _insight("DEMAND_FORECAST", "LOW", "Demand forecast not available",
                             "No transaction history to project demand from.",
                             status="insufficient_data",
                             reason="No historical transaction periods are available.",
                             source=source)]
                completed_fc = [i for i in fc if i["status"] == "completed"]
                types_status["demand_forecast"] = {"status": "completed" if completed_fc else "insufficient_data",
                                                   "count": len(completed_fc),
                                                   "reason": None if completed_fc else (fc[0].get("reason") if fc else None)}
                insights.extend(fc)
        finally:
            conn.close()

    # ---- agent types: map the workflow result onto insights ----------------
    if agent_types:
        anomalies = result.get("anomalies") or []
        findings = result.get("findings") or []
        alerts = result.get("alerts") or []
        if "distribution_anomaly" in agent_types:
            anomaly_insights = []
            for finding in findings:
                anomaly = next((a for a in anomalies if a.get("anomaly_id") == finding.get("anomaly_id")), None)
                severity = "HIGH" if finding.get("evidence", {}).get("distance_km") else "MEDIUM"
                anomaly_insights.append(_insight(
                    "DISTRIBUTION_ANOMALY", severity,
                    "Distribution anomaly detected for %s" % (anomaly or {}).get("beneficiary_id", "unknown beneficiary"),
                    finding.get("explanation") or (finding.get("summary") or "Anomalous distribution pattern verified against transaction data."),
                    evidence=finding.get("evidence") or {},
                    confidence=finding.get("confidence"),
                    recommendation=alerts[0].get("recommended_action") if alerts else None,
                    entity_type="beneficiary",
                    entity_id=(anomaly or {}).get("beneficiary_id"),
                    deterministic=False,
                    source=_source_block(dataset_block, "PENDING"),
                ))
            insights.extend(anomaly_insights)
            types_status["distribution_anomaly"] = {
                "status": "completed" if anomaly_insights else ("skipped" if not anomalies else "completed"),
                "count": len(anomaly_insights),
                "reason": None if anomaly_insights else ("No anomaly candidates detected." if not anomalies else "No verified findings."),
            }
        if "recommendations" in agent_types:
            rec_insights = []
            for alert in alerts:
                rec_insights.append(_insight(
                    "RECOMMENDATION", "HIGH" if (alert.get("severity") or "low").lower() == "high" else "MEDIUM",
                    "Recommendation: %s" % (alert.get("recommended_action") or "human review"),
                    alert.get("message") or "An investigation case was created for human review.",
                    evidence={"case_id": alert.get("case_id"),
                              "alert_id": alert.get("alert_id")},
                    confidence=alert.get("confidence"),
                    recommendation=alert.get("recommended_action"),
                    entity_type="beneficiary",
                    entity_id=alerts[0].get("beneficiary_id") if alerts else None,
                    deterministic=False,
                    source=_source_block(dataset_block, "PENDING"),
                ))
            insights.extend(rec_insights)
            types_status["recommendations"] = {
                "status": "completed" if rec_insights else "skipped",
                "count": len(rec_insights),
                "reason": None if rec_insights else "No alert was generated (no verified anomalies).",
            }

    # ---- persist the run (with the real analysis id) -----------------------
    result["insights"] = insights
    result["types"] = types_status
    result["config"] = {"analysis_types": types, "filters": filters}
    duration_ms = int((_time.perf_counter() - _started) * 1000)
    run = record_analysis_run(
        result,
        dataset_mode=dataset_mode,
        data_import_id=data_import_id,
        db_path=db_path,
        analysis_types=types,
        filters=filters,
        timings=result.get("timings"),
        duration_ms=duration_ms,
    )
    analysis_id = run["analysis_id"]
    # stamp the real analysis id onto insight sources (they were built with a
    # placeholder id before persistence)
    for insight in insights:
        insight["source"]["analysis_id"] = analysis_id

    # Persist REAL-dataset insights so monitoring can convert them into alerts
    # with full lineage (alert <- insight <- analysis <- import). Synthetic
    # demo insights stay ephemeral — they never become monitoring alerts.
    if dataset_mode == "real" and data_import_id is not None:
        conn = open_db(db_path)
        try:
            for insight in insights:
                if insight.get("status") == "insufficient_data":
                    continue  # nothing was actually detected — never alert on it
                insert_ai_insight(
                    conn,
                    insight_type=insight["insight_type"],
                    severity=insight["severity"],
                    title=insight["title"],
                    description=insight.get("summary"),
                    entity_type=insight.get("entity_type"),
                    entity_id=insight.get("entity_id"),
                    confidence=insight.get("confidence"),
                    recommendation=insight.get("recommendation"),
                    evidence=insight.get("evidence"),
                    analysis_id=analysis_id,
                    source_import_id=data_import_id,
                )
            conn.commit()
        finally:
            conn.close()

    result["analysis_run"] = run
    result["duration_ms"] = duration_ms
    logger.info(
        "[AnalysisCenter] %s %s: %d insight(s) across %d type(s) (%.3fs)",
        analysis_id, dataset_mode, len(insights), len(types), duration_ms / 1000.0,
    )
    return result


# ---------------------------------------------------------------------------
# History / detail (real persisted runs)
# ---------------------------------------------------------------------------

def analysis_history(db_path: str = DEFAULT_DB_PATH, *, page: int = 1, per_page: int = 10) -> dict:
    conn = open_db(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) AS n FROM analysis_runs").fetchone()["n"]
        rows = conn.execute(
            "SELECT r.*, i.dataset_name, i.file_name, s.name AS source_name "
            "FROM analysis_runs r "
            "LEFT JOIN data_imports i ON i.id = r.data_import_id "
            "LEFT JOIN data_sources s ON s.id = i.data_source_id "
            "ORDER BY r.id DESC LIMIT :limit OFFSET :offset",
            {"limit": per_page, "offset": (page - 1) * per_page},
        ).fetchall()
    finally:
        conn.close()

    runs = []
    for row in rows:
        r = dict(row)
        runs.append({
            "id": r["id"],
            "analysis_id": r["analysis_id"],
            "dataset_mode": r["dataset_mode"],
            "data_import_id": r["data_import_id"],
            "dataset_name": r.get("dataset_name") or ("Synthetic Demo Dataset" if r["dataset_mode"] == "synthetic" else None),
            "source_name": r.get("source_name"),
            "status": r["status"],
            "insight_count": r["insight_count"],
            "anomaly_count": r["anomaly_count"],
            "finding_count": r["finding_count"],
            "case_count": r["case_count"],
            "alert_count": r["alert_count"],
            "analysis_types": json.loads(r["analysis_types"]) if r.get("analysis_types") else None,
            "duration_ms": r.get("duration_ms"),
            "created_at": r["created_at"],
            "summary": r.get("summary"),
        })
    return {"runs": runs, "total": total, "page": page, "per_page": per_page,
            "pages": max(1, -(-total // per_page))}


def analysis_detail(run_id: int, db_path: str = DEFAULT_DB_PATH):
    conn = open_db(db_path)
    try:
        row = conn.execute(
            "SELECT r.*, i.dataset_name, s.name AS source_name "
            "FROM analysis_runs r "
            "LEFT JOIN data_imports i ON i.id = r.data_import_id "
            "LEFT JOIN data_sources s ON s.id = i.data_source_id "
            "WHERE r.id = :id",
            {"id": run_id},
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    r = dict(row)
    return {
        "id": r["id"],
        "analysis_id": r["analysis_id"],
        "dataset_mode": r["dataset_mode"],
        "data_import_id": r["data_import_id"],
        "dataset_name": r.get("dataset_name") or ("Synthetic Demo Dataset" if r["dataset_mode"] == "synthetic" else None),
        "source_name": r.get("source_name"),
        "status": r["status"],
        "insight_count": r["insight_count"],
        "anomaly_count": r["anomaly_count"],
        "finding_count": r["finding_count"],
        "case_count": r["case_count"],
        "alert_count": r["alert_count"],
        "analysis_types": json.loads(r["analysis_types"]) if r.get("analysis_types") else None,
        "filters": json.loads(r["filters"]) if r.get("filters") else None,
        "timings": json.loads(r["timings"]) if r.get("timings") else None,
        "duration_ms": r.get("duration_ms"),
        "created_at": r["created_at"],
        "summary": r.get("summary"),
        "error": r.get("error"),
    }
