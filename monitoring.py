"""RationAI — Early Warning, Alerts & Monitoring Center backend (Phase 11).

Turns RationAI into a PROACTIVE monitoring system: deterministic rules run
over the real database, detect conditions, and persist alerts with an
OPEN -> ACKNOWLEDGED -> RESOLVED / DISMISSED lifecycle. The AI is only ever
asked to EXPLAIN a condition that deterministic code already detected — it
never decides thresholds and never invents evidence.

Flow:

    REAL DATA
      -> load rules (alert_rules, configurable)
      -> run deterministic detectors (this module, no LLM)
      -> deduplicate (one OPEN/ACKNOWLEDGED alert per condition key)
      -> create / update / auto-resolve alerts
      -> optional AI explanation (``agents.llm.maybe_generate``, fail-open)

Detectors and their documented thresholds (the alert_rules table holds the
authoritative, operator-adjustable values; these are the built-in defaults):

    INVENTORY_RISK   coverage_critical    days_remaining < 15 days
    INVENTORY_RISK   coverage_warning     days_remaining < 30 days
    INVENTORY_RISK   below_reorder        current_stock < reorder_threshold
    OPERATIONAL_RISK high_failure_rate    failed/(failed+completed) >= 10% (>=5 tx)
    OPERATIONAL_RISK no_recent_distribution  no completed tx in last 30 days
    DEMAND_SPIKE     demand_spike         latest month >= 20% above prior average
    DEMAND_DROP      demand_drop          latest month <= 20% below prior average
    DATA_FRESHNESS   stale                last successful sync older than 24 h
    SOURCE_FAILURE   sync_failed          data source status = ERROR
    DATA_QUALITY     low_quality          import quality score < 90%
    DISTRIBUTION_ANOMALY analysis_insight converted from a persisted Phase 9
                            insight (severity >= MEDIUM)

Rules:
- **Dedup** — one OPEN/ACKNOWLEDGED alert per (rule_type, condition, entity,
  commodity) key. Re-detection updates ``last_detected_at``/evidence instead
  of creating duplicates. A RESOLVED condition that becomes active again
  creates a new alert; a DISMISSED alert is left alone while the same
  condition persists (operator intentionally dismissed it) and only a new
  occurrence after it clears produces a new alert.
- **Auto-resolve** — OPEN/ACKNOWLEDGED alerts whose condition is no longer
  detected are marked RESOLVED with ``resolved_at``.
- **Safety** — monitoring NEVER writes to inventory, beneficiaries,
  transactions, imports, or sources. Only the alerts/alert_rules tables are
  touched. Failed monitoring leaves existing alerts untouched.
- **Honesty** — SUPPLY_DELAY is listed in the alert taxonomy but is a
  what-if simulation input (Phase 10), not a condition observable in the
  database; no detector exists for it and none is fabricated.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from agents.llm import maybe_generate
from analytics import (
    FAILURE_MIN_TRANSACTIONS,
    FAILURE_RATE_THRESHOLD,
    INVENTORY_CRITICAL_DAYS,
    INVENTORY_WARNING_DAYS,
    NO_RECENT_DISTRIBUTION_DAYS,
)
from database import (
    ALERT_SEVERITIES,
    ALERT_TYPES,
    DEFAULT_DB_PATH,
    get_active_alert_for_condition,
    get_alert_by_alert_id,
    get_alert_rule,
    get_alert_trend,
    get_condition_history,
    get_insights_since,
    get_open_alert_counts,
    insert_alert,
    list_alerts,
    list_alert_rules,
    open_db,
    seed_alert_rules,
    update_alert_rule,
    update_alert_status,
)

logger = logging.getLogger("rationright.monitoring")

# --- built-in default thresholds (the alert_rules table overrides these) -----
DEMAND_SPIKE_PCT = 20.0
DEMAND_DROP_PCT = 20.0
FRESHNESS_HOURS = 24.0
QUALITY_WARN_PCT = 90.0
DEMAND_MIN_TRANSACTIONS = 3

DEFAULT_RULES = [
    {"name": "Inventory critical coverage", "rule_type": "INVENTORY_RISK",
     "condition": "coverage_critical", "severity": "CRITICAL",
     "threshold": float(INVENTORY_CRITICAL_DAYS), "threshold_unit": "days",
     "description": "Estimated stock coverage below the critical threshold (days)."},
    {"name": "Inventory warning coverage", "rule_type": "INVENTORY_RISK",
     "condition": "coverage_warning", "severity": "HIGH",
     "threshold": float(INVENTORY_WARNING_DAYS), "threshold_unit": "days",
     "description": "Estimated stock coverage below the warning threshold (days)."},
    {"name": "Stock below reorder threshold", "rule_type": "INVENTORY_RISK",
     "condition": "below_reorder", "severity": "HIGH", "threshold": None,
     "description": "Current stock below the record's reorder threshold."},
    {"name": "Elevated transaction failure rate", "rule_type": "OPERATIONAL_RISK",
     "condition": "high_failure_rate", "severity": "MEDIUM",
     "threshold": round(FAILURE_RATE_THRESHOLD * 100, 2), "threshold_unit": "percent",
     "description": "Failed / (failed + completed) >= threshold percent, with "
                    "at least %d transactions at a center." % FAILURE_MIN_TRANSACTIONS},
    {"name": "No recent distribution", "rule_type": "OPERATIONAL_RISK",
     "condition": "no_recent_distribution", "severity": "LOW",
     "threshold": float(NO_RECENT_DISTRIBUTION_DAYS), "threshold_unit": "days",
     "description": "No completed distribution at a center in the last N days."},
    {"name": "Demand spike", "rule_type": "DEMAND_SPIKE",
     "condition": "demand_spike", "severity": "MEDIUM",
     "threshold": DEMAND_SPIKE_PCT, "threshold_unit": "percent",
     "description": "Latest month's demand at least N percent above the average "
                    "of the preceding months."},
    {"name": "Demand drop", "rule_type": "DEMAND_DROP",
     "condition": "demand_drop", "severity": "MEDIUM",
     "threshold": DEMAND_DROP_PCT, "threshold_unit": "percent",
     "description": "Latest month's demand at most N percent below the average "
                    "of the preceding months."},
    {"name": "Data freshness", "rule_type": "DATA_FRESHNESS",
     "condition": "stale", "severity": "MEDIUM",
     "threshold": FRESHNESS_HOURS, "threshold_unit": "hours",
     "description": "A source whose last successful sync is older than N hours."},
    {"name": "Source sync failure", "rule_type": "SOURCE_FAILURE",
     "condition": "sync_failed", "severity": "CRITICAL", "threshold": None,
     "description": "A data source whose last sync attempt ended in ERROR."},
    {"name": "Dataset quality below threshold", "rule_type": "DATA_QUALITY",
     "condition": "low_quality", "severity": "MEDIUM",
     "threshold": QUALITY_WARN_PCT, "threshold_unit": "percent",
     "description": "An import whose Phase 4 quality score (successful / total "
                    "records) is below N percent."},
    {"name": "Analysis anomaly insight", "rule_type": "DISTRIBUTION_ANOMALY",
     "condition": "analysis_insight", "severity": "MEDIUM", "threshold": None,
     "description": "A persisted Phase 9 distribution-anomaly insight "
                    "(severity >= MEDIUM) surfaced as an alert."},
]

_SEVERITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(ts) -> Optional[datetime]:
    if not ts:
        return None
    try:
        parsed = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _round(value, digits=2):
    if value is None:
        return None
    return round(float(value), digits)


def _seed_rules(conn) -> None:
    seed_alert_rules(conn, DEFAULT_RULES)
    conn.commit()


def _rule_map(conn) -> dict:
    """Rules keyed by (rule_type, condition) -> config dict."""
    rules = {}
    for rule in list_alert_rules(conn):
        rules[(rule["rule_type"], rule["condition"])] = rule
    return rules


def _threshold(rules, rule_type: str, condition: str, default: float) -> Optional[float]:
    rule = rules.get((rule_type, condition))
    if rule is None:
        return default
    if rule["threshold"] is not None:
        return float(rule["threshold"])
    return default


def _enabled(rules, rule_type: str, condition: str) -> bool:
    rule = rules.get((rule_type, condition))
    return rule is None or bool(rule["enabled"])


# ---------------------------------------------------------------------------
# Detectors — deterministic, parameterized SQL, no LLM
# ---------------------------------------------------------------------------

def _candidate(rule_type, condition, severity, title, description, *, evidence,
               recommendation=None, entity_type=None, entity_id=None,
               commodity=None, current_value=None, threshold=None,
               source_id=None, import_id=None, analysis_id=None) -> dict:
    return {
        "rule_type": rule_type, "condition": condition, "severity": severity,
        "title": title, "description": description, "evidence": evidence or {},
        "recommendation": recommendation, "entity_type": entity_type,
        "entity_id": entity_id, "commodity": commodity,
        "current_value": current_value, "threshold": threshold,
        "source_id": source_id, "import_id": import_id, "analysis_id": analysis_id,
    }


def _inventory_candidates(conn, rules) -> list:
    out = []
    if not (_enabled(rules, "INVENTORY_RISK", "coverage_critical")
            or _enabled(rules, "INVENTORY_RISK", "coverage_warning")
            or _enabled(rules, "INVENTORY_RISK", "below_reorder")):
        return out
    critical_days = _threshold(rules, "INVENTORY_RISK", "coverage_critical",
                               float(INVENTORY_CRITICAL_DAYS))
    warning_days = _threshold(rules, "INVENTORY_RISK", "coverage_warning",
                              float(INVENTORY_WARNING_DAYS))
    rows = conn.execute(
        "SELECT i.commodity, i.current_stock, i.monthly_consumption, "
        " i.reorder_threshold, i.source_import_id, "
        " COALESCE(f.fps_code, 'Unknown') AS fps_code, f.district, "
        " di.data_source_id AS source_id "
        "FROM inventory i LEFT JOIN fps_centers f ON f.id = i.fps_center_id "
        "LEFT JOIN data_imports di ON di.id = i.source_import_id "
        "ORDER BY i.commodity, fps_code"
    ).fetchall()
    for r in rows:
        stock = r["current_stock"] or 0.0
        monthly = r["monthly_consumption"]
        entity = {"entity_type": "fps_center", "entity_id": r["fps_code"],
                  "commodity": r["commodity"], "import_id": r["source_import_id"],
                  "source_id": r["source_id"]}
        if monthly is not None and monthly > 0:
            days = stock / (monthly / 30.0)
            if days < critical_days:
                out.append(_candidate(
                    "INVENTORY_RISK", "coverage_critical", "CRITICAL",
                    "Critical inventory coverage at %s" % r["fps_code"],
                    "Stock of %s at %s covers approximately %.1f days at the "
                    "observed consumption rate (below the %.0f-day critical "
                    "threshold)." % (r["commodity"], r["fps_code"], days, critical_days),
                    evidence={"commodity": r["commodity"], "fps_code": r["fps_code"],
                              "district": r["district"],
                              "current_stock": _round(stock),
                              "monthly_consumption": _round(monthly),
                              "daily_consumption": _round(monthly / 30.0),
                              "days_remaining": _round(days, 1),
                              "threshold_days": critical_days},
                    recommendation="Initiate immediate replenishment review for %s at %s."
                                   % (r["commodity"], r["fps_code"]),
                    current_value=_round(days, 1), threshold=critical_days, **entity))
            elif days < warning_days:
                out.append(_candidate(
                    "INVENTORY_RISK", "coverage_warning", "HIGH",
                    "Inventory coverage approaching warning threshold at %s" % r["fps_code"],
                    "Stock of %s at %s covers approximately %.1f days (below the "
                    "%.0f-day warning threshold)." % (r["commodity"], r["fps_code"],
                                                      days, warning_days),
                    evidence={"commodity": r["commodity"], "fps_code": r["fps_code"],
                              "district": r["district"],
                              "current_stock": _round(stock),
                              "monthly_consumption": _round(monthly),
                              "daily_consumption": _round(monthly / 30.0),
                              "days_remaining": _round(days, 1),
                              "threshold_days": warning_days},
                    recommendation="Review replenishment for %s at %s."
                                   % (r["commodity"], r["fps_code"]),
                    current_value=_round(days, 1), threshold=warning_days, **entity))
        if r["reorder_threshold"] is not None and stock < r["reorder_threshold"]:
            out.append(_candidate(
                "INVENTORY_RISK", "below_reorder", "HIGH",
                "Inventory below reorder threshold at %s" % r["fps_code"],
                "Stock of %s at %s is %.2f kg, below the %.2f kg reorder "
                "threshold." % (r["commodity"], r["fps_code"], stock,
                                r["reorder_threshold"]),
                evidence={"commodity": r["commodity"], "fps_code": r["fps_code"],
                          "current_stock": _round(stock),
                          "reorder_threshold": _round(r["reorder_threshold"])},
                recommendation="Review replenishment for %s at %s."
                               % (r["commodity"], r["fps_code"]),
                current_value=_round(stock), threshold=_round(r["reorder_threshold"]),
                **entity))
    return out


def _operational_candidates(conn, rules) -> list:
    out = []
    # Elevated failure rate per FPS.
    if _enabled(rules, "OPERATIONAL_RISK", "high_failure_rate"):
        pct = _threshold(rules, "OPERATIONAL_RISK", "high_failure_rate",
                         FAILURE_RATE_THRESHOLD * 100)
        for r in conn.execute(
            "SELECT COALESCE(f.fps_code, 'Unknown') AS fps_code, f.district, "
            " COALESCE(SUM(CASE WHEN t.status = 'FAILED' THEN 1 ELSE 0 END), 0) AS failed, "
            " COALESCE(SUM(CASE WHEN t.status IN ('COMPLETED','FAILED') THEN 1 ELSE 0 END), 0) AS total, "
            " MAX(t.source_import_id) AS import_id "
            "FROM ration_transactions t LEFT JOIN fps_centers f ON f.id = t.fps_center_id "
            "GROUP BY fps_code"
        ):
            total = r["total"]
            if total < FAILURE_MIN_TRANSACTIONS:
                continue
            rate = r["failed"] / total
            if rate * 100 >= pct:
                out.append(_candidate(
                    "OPERATIONAL_RISK", "high_failure_rate", "MEDIUM",
                    "Transaction failure rate elevated at %s" % r["fps_code"],
                    "%d of %d transactions at %s failed (%.0f%% >= %.0f%% "
                    "threshold). Requires human review." % (
                        r["failed"], total, r["fps_code"], rate * 100, pct),
                    evidence={"fps_code": r["fps_code"], "district": r["district"],
                              "failed_transactions": r["failed"],
                              "total_transactions": total,
                              "failure_rate_pct": _round(rate * 100),
                              "threshold_pct": pct},
                    recommendation="Review the failing transactions at %s."
                                   % r["fps_code"],
                    current_value=_round(rate * 100), threshold=pct,
                    entity_type="fps_center", entity_id=r["fps_code"],
                    import_id=r["import_id"]))
    # No recent distribution per FPS.
    if _enabled(rules, "OPERATIONAL_RISK", "no_recent_distribution"):
        recent_days = int(_threshold(rules, "OPERATIONAL_RISK",
                                     "no_recent_distribution",
                                     float(NO_RECENT_DISTRIBUTION_DAYS)))
        cutoff = (_now() - timedelta(days=recent_days)).date().isoformat()
        for r in conn.execute(
            "SELECT f.fps_code, f.district, "
            " COALESCE(SUM(CASE WHEN t.status = 'COMPLETED' AND "
            "   substr(t.transaction_date, 1, 10) >= :cutoff THEN 1 ELSE 0 END), 0) AS completed, "
            " COALESCE(SUM(CASE WHEN t.status = 'COMPLETED' THEN 1 ELSE 0 END), 0) AS ever "
            "FROM fps_centers f LEFT JOIN ration_transactions t ON t.fps_center_id = f.id "
            "GROUP BY f.fps_code HAVING completed = 0 AND ever > 0",
            {"cutoff": cutoff},
        ):
            out.append(_candidate(
                "OPERATIONAL_RISK", "no_recent_distribution", "LOW",
                "No recent distribution activity at %s" % r["fps_code"],
                "FPS %s (%s) has no completed transactions in the last %d days "
                "(cutoff %s). Verify the center is operating." % (
                    r["fps_code"], r["district"] or "district unknown",
                    recent_days, cutoff),
                evidence={"fps_code": r["fps_code"], "district": r["district"],
                          "recent_days": recent_days, "cutoff": cutoff},
                recommendation="Verify %s is operating and record distributions."
                               % r["fps_code"],
                current_value=0, threshold=float(recent_days),
                entity_type="fps_center", entity_id=r["fps_code"]))
    return out


def _demand_candidates(conn, rules) -> list:
    out = []
    spike_on = _enabled(rules, "DEMAND_SPIKE", "demand_spike")
    drop_on = _enabled(rules, "DEMAND_DROP", "demand_drop")
    if not (spike_on or drop_on):
        return out
    spike_pct = _threshold(rules, "DEMAND_SPIKE", "demand_spike", DEMAND_SPIKE_PCT)
    drop_pct = _threshold(rules, "DEMAND_DROP", "demand_drop", DEMAND_DROP_PCT)
    rows = conn.execute(
        "SELECT substr(transaction_date, 1, 7) AS period, commodity, "
        " COUNT(*) AS n, SUM(quantity) AS qty "
        "FROM ration_transactions WHERE transaction_date IS NOT NULL "
        "GROUP BY period, commodity ORDER BY period, commodity"
    ).fetchall()
    by_commodity = {}
    for r in rows:
        by_commodity.setdefault(r["commodity"], []).append(
            {"period": r["period"], "n": r["n"], "qty": r["qty"]})
    for commodity in sorted(by_commodity):
        series = sorted(by_commodity[commodity], key=lambda item: item["period"])
        if len(series) < 2:
            continue  # need a baseline month to compare against
        latest = series[-1]
        if latest["n"] < DEMAND_MIN_TRANSACTIONS:
            continue  # too little activity in the latest month to judge a change
        prior = series[:-1]
        baseline = sum(item["qty"] for item in prior) / len(prior)
        if baseline <= 0:
            continue
        deviation = (latest["qty"] - baseline) / baseline * 100.0
        if spike_on and deviation >= spike_pct:
            severity = "HIGH" if deviation >= 2 * spike_pct else "MEDIUM"
            out.append(_candidate(
                "DEMAND_SPIKE", "demand_spike", severity,
                "Demand spike detected for %s" % commodity,
                "Demand for %s in %s was %.0f kg, %.1f%% above the average of "
                "the %d preceding month(s) (%.0f kg)." % (
                    commodity, latest["period"], latest["qty"], deviation,
                    len(prior), baseline),
                evidence={"commodity": commodity, "latest_period": latest["period"],
                          "latest_quantity": _round(latest["qty"]),
                          "baseline_periods": [item["period"] for item in prior],
                          "baseline_average": _round(baseline),
                          "deviation_pct": _round(deviation),
                          "threshold_pct": spike_pct},
                recommendation="Investigate the demand increase for %s and confirm "
                               "supply keeps pace." % commodity,
                current_value=_round(deviation), threshold=spike_pct,
                entity_type="commodity", entity_id=commodity, commodity=commodity))
        elif drop_on and deviation <= -drop_pct:
            severity = "HIGH" if deviation <= -2 * drop_pct else "MEDIUM"
            out.append(_candidate(
                "DEMAND_DROP", "demand_drop", severity,
                "Demand drop detected for %s" % commodity,
                "Demand for %s in %s was %.0f kg, %.1f%% below the average of "
                "the %d preceding month(s) (%.0f kg)." % (
                    commodity, latest["period"], latest["qty"], abs(deviation),
                    len(prior), baseline),
                evidence={"commodity": commodity, "latest_period": latest["period"],
                          "latest_quantity": _round(latest["qty"]),
                          "baseline_periods": [item["period"] for item in prior],
                          "baseline_average": _round(baseline),
                          "deviation_pct": _round(deviation),
                          "threshold_pct": drop_pct},
                recommendation="Check whether the demand drop for %s reflects a "
                               "data gap or a real reduction in uptake." % commodity,
                current_value=_round(deviation), threshold=drop_pct,
                entity_type="commodity", entity_id=commodity, commodity=commodity))
    return out


def _freshness_candidates(conn, rules) -> list:
    out = []
    if not _enabled(rules, "DATA_FRESHNESS", "stale"):
        return out
    hours = _threshold(rules, "DATA_FRESHNESS", "stale", FRESHNESS_HOURS)
    now = _now()
    for r in conn.execute(
        "SELECT id, name, last_successful_sync_at, last_sync_at "
        "FROM data_sources WHERE last_successful_sync_at IS NOT NULL"
    ):
        last = _parse_ts(r["last_successful_sync_at"])
        if last is None:
            continue
        age_hours = (now - last).total_seconds() / 3600.0
        if age_hours > hours:
            out.append(_candidate(
                "DATA_FRESHNESS", "stale", "MEDIUM",
                "Data source has not been updated recently",
                "Source %r has not been updated for %.1f hours (threshold %.0f "
                "hours). Last successful sync: %s." % (
                    r["name"], age_hours, hours, r["last_successful_sync_at"]),
                evidence={"source": r["name"],
                          "last_successful_sync_at": r["last_successful_sync_at"],
                          "last_sync_attempt_at": r["last_sync_at"],
                          "age_hours": _round(age_hours),
                          "threshold_hours": hours},
                recommendation="Trigger a sync for %r." % r["name"],
                current_value=_round(age_hours), threshold=hours,
                entity_type="data_source", entity_id=r["name"],
                source_id=r["id"]))
    return out


def _source_failure_candidates(conn, rules) -> list:
    out = []
    if not _enabled(rules, "SOURCE_FAILURE", "sync_failed"):
        return out
    for r in conn.execute(
        "SELECT id, name, last_error, last_successful_sync_at, last_sync_at "
        "FROM data_sources WHERE status = 'ERROR' AND last_error IS NOT NULL"
    ):
        out.append(_candidate(
            "SOURCE_FAILURE", "sync_failed", "CRITICAL",
            "Data source synchronization failed",
            "Source %r synchronization failed: %s" % (r["name"], r["last_error"]),
            evidence={"source": r["name"], "error": r["last_error"],
                      "last_sync_attempt_at": r["last_sync_at"],
                      "last_successful_sync_at": r["last_successful_sync_at"]},
            recommendation="Retry the sync for %r once the source is reachable "
                           "again." % r["name"],
            current_value=None, threshold=None,
            entity_type="data_source", entity_id=r["name"], source_id=r["id"]))
    return out


def _quality_candidates(conn, rules) -> list:
    out = []
    if not _enabled(rules, "DATA_QUALITY", "low_quality"):
        return out
    pct = _threshold(rules, "DATA_QUALITY", "low_quality", QUALITY_WARN_PCT)
    for r in conn.execute(
        "SELECT id, dataset_name, record_count, successful_records, "
        " failed_records, duplicate_records, warnings_count, data_source_id, "
        " status FROM data_imports "
        "WHERE status IN ('COMPLETED','PARTIAL') AND record_count > 0"
    ):
        quality = r["successful_records"] / r["record_count"] * 100.0
        if quality < pct:
            out.append(_candidate(
                "DATA_QUALITY", "low_quality", "MEDIUM",
                "Dataset quality below configured threshold",
                "Dataset %r quality is %.1f%% (%.0f of %.0f records valid), below "
                "the %.0f%% threshold." % (
                    r["dataset_name"], quality, r["successful_records"],
                    r["record_count"], pct),
                evidence={"dataset_name": r["dataset_name"],
                          "record_count": r["record_count"],
                          "valid_records": r["successful_records"],
                          "failed_records": r["failed_records"],
                          "duplicate_records": r["duplicate_records"],
                          "warnings_count": r["warnings_count"],
                          "quality_pct": _round(quality),
                          "threshold_pct": pct},
                recommendation="Review the invalid records in %r before relying "
                               "on it." % r["dataset_name"],
                current_value=_round(quality), threshold=pct,
                entity_type="data_import", entity_id=str(r["id"]),
                import_id=r["id"], source_id=r["data_source_id"]))
    return out


def _insight_candidates(conn, rules) -> list:
    """Convert persisted Phase 9 DISTRIBUTION_ANOMALY insights (severity >=
    MEDIUM) into alerts, reusing the existing anomaly detection — no new
    anomaly engine. One active alert per beneficiary; re-analysis updates it.
    """
    out = []
    if not _enabled(rules, "DISTRIBUTION_ANOMALY", "analysis_insight"):
        return out
    for insight in get_insights_since(
        conn, insight_type="DISTRIBUTION_ANOMALY", min_severity="MEDIUM", limit=200
    ):
        entity_type = insight.get("entity_type") or "beneficiary"
        entity_id = insight.get("entity_id")
        if not entity_id:
            continue
        evidence = insight.get("evidence") or {}
        out.append(_candidate(
            "DISTRIBUTION_ANOMALY", "analysis_insight", insight["severity"],
            insight["title"],
            insight.get("description") or insight.get("title"),
            evidence=evidence,
            recommendation=insight.get("recommendation"),
            entity_type=entity_type, entity_id=entity_id,
            commodity=None, current_value=None, threshold=None,
            import_id=insight.get("source_import_id"),
            analysis_id=insight.get("analysis_id")))
    return out


# ---------------------------------------------------------------------------
# Explanation (deterministic fallback; optional LLM rephrase — never invents)
# ---------------------------------------------------------------------------

def _explain_fallback(cand: dict) -> str:
    ev = cand["evidence"] or {}
    entity = "%s %s" % (cand["entity_type"] or "entity", cand["entity_id"] or "?")
    label = cand["rule_type"].replace("_", " ").title()
    if cand["condition"] in ("coverage_critical", "coverage_warning"):
        return ("The monitoring rule %r detected that %s has an estimated "
                "%.1f days of %s stock remaining, which is below the configured "
                "%.0f-day threshold. This means the center could face a stockout "
                "within the current consumption pattern." % (
                    label, entity, cand["current_value"] or 0,
                    cand["commodity"] or "commodity", cand["threshold"] or 0))
    if cand["condition"] == "below_reorder":
        return ("The monitoring rule %r detected that %s stock for %s "
                "(%.1f kg) has fallen below its reorder threshold (%.1f kg). "
                "Replenishment should be reviewed now to avoid a gap." % (
                    label, entity, cand["commodity"] or "commodity",
                    cand["current_value"] or 0, cand["threshold"] or 0))
    if cand["condition"] == "high_failure_rate":
        return ("The monitoring rule %r detected an elevated transaction "
                "failure rate at %s: %.0f%% of transactions failed against a "
                "%.0f%% threshold. A high failure rate can signal data or "
                "distribution problems that need human review." % (
                    label, entity, cand["current_value"] or 0,
                    cand["threshold"] or 0))
    if cand["condition"] == "no_recent_distribution":
        return ("The monitoring rule %r found no completed distribution at %s "
                "within the configured %d-day window. The center may be "
                "inactive or its transactions may not have been recorded." % (
                    label, entity, int(cand["threshold"] or 0)))
    if cand["condition"] in ("demand_spike", "demand_drop"):
        direction = "above" if cand["condition"] == "demand_spike" else "below"
        return ("The monitoring rule %r detected %s demand for %s deviating "
                "%.1f%% %s the historical monthly average (threshold %.0f%%). "
                "This may indicate a real change in demand or a data issue "
                "worth investigating." % (
                    label, direction, cand["commodity"] or "commodity",
                    abs(cand["current_value"] or 0), direction,
                    cand["threshold"] or 0))
    if cand["condition"] == "stale":
        return ("The monitoring rule %r detected that %s has not been updated "
                "for %.1f hours, beyond the configured %.0f-hour freshness "
                "threshold. Dashboards and analysis may be running on stale "
                "data; a sync should be triggered." % (
                    label, entity, cand["current_value"] or 0,
                    cand["threshold"] or 0))
    if cand["condition"] == "sync_failed":
        return ("The monitoring rule %r detected that %s failed its last "
                "synchronization attempt. The previous successful dataset is "
                "retained, but the source should be retried once available." % (
                    label, entity))
    if cand["condition"] == "low_quality":
        return ("The monitoring rule %r detected that dataset %s scored "
                "%.1f%% quality, below the configured %.0f%% threshold. "
                "Invalid records should be reviewed in the source file before "
                "relying on this dataset." % (
                    label, entity, cand["current_value"] or 0,
                    cand["threshold"] or 0))
    if cand["condition"] == "analysis_insight":
        return ("A Phase 9 AI analysis surfaced a distribution anomaly for %s "
                "that was verified against the underlying transaction data and "
                "crossed the alert threshold. The anomaly requires human "
                "review; see the linked analysis for the full evidence." % entity)
    return ("The monitoring rule %r detected a condition at %s. Review the "
            "evidence and take the recommended action." % (label, entity))


def _ai_explanation(cand: dict, generator=None) -> dict:
    ev = cand["evidence"] or {}
    context = {
        "alert_type": cand["rule_type"],
        "condition": cand["condition"],
        "entity_type": cand["entity_type"],
        "entity_id": cand["entity_id"],
        "commodity": cand["commodity"],
        "current_value": cand["current_value"],
        "threshold": cand["threshold"],
        "evidence": {k: str(v)[:120] for k, v in list(ev.items())[:12]},
    }
    fallback = _explain_fallback(cand)
    text = maybe_generate("alert_explanation", context, fallback, generator=generator)
    return {"summary": text,
            "generated_by": "llm" if text != fallback else "deterministic_fallback"}


def _condition_key(cand: dict) -> tuple:
    return (cand["rule_type"], cand["condition"],
            cand.get("entity_type"), cand.get("entity_id"), cand.get("commodity"))


# ---------------------------------------------------------------------------
# The monitoring engine
# ---------------------------------------------------------------------------

def run_monitoring(db_path: str = DEFAULT_DB_PATH, generator=None) -> dict:
    """Run every enabled rule over the database; create/update/resolve alerts.

    Returns a run summary. NEVER modifies source data — only the alerts and
    alert_rules tables are touched. ``generator`` lets tests inject (or fail)
    the LLM narrative exactly like ``simulation.run_scenario``; the engine
    still only EXPLAINS conditions it already detected deterministically.
    """
    conn = open_db(db_path)
    try:
        _seed_rules(conn)
        rules = _rule_map(conn)
        candidates = []
        for detector in (
            _inventory_candidates, _operational_candidates, _demand_candidates,
            _freshness_candidates, _source_failure_candidates,
            _quality_candidates, _insight_candidates,
        ):
            candidates.extend(detector(conn, rules))

        by_key = {_condition_key(c): c for c in candidates}
        created = updated = 0
        for cand in candidates:
            key = _condition_key(cand)
            existing = get_active_alert_for_condition(
                conn, cand["rule_type"], cand["condition"], cand.get("entity_type"),
                cand.get("entity_id"), cand.get("commodity"))
            if existing is not None:
                # Condition persists -> refresh evidence, keep one alert open.
                conn.execute(
                    "UPDATE alerts SET severity = :severity, title = :title, "
                    " description = :desc, current_value = :cur, threshold = :thr, "
                    " evidence = :evidence, recommendation = :rec, "
                    " source_id = COALESCE(:sid, source_id), "
                    " import_id = COALESCE(:iid, import_id), "
                    " analysis_id = COALESCE(:aid, analysis_id), "
                    " last_detected_at = :now WHERE id = :id",
                    {
                        "severity": cand["severity"], "title": cand["title"],
                        "desc": cand["description"], "cur": cand["current_value"],
                        "thr": cand["threshold"],
                        "evidence": _json_dumps(cand["evidence"]),
                        "rec": cand["recommendation"], "sid": cand["source_id"],
                        "iid": cand["import_id"], "aid": cand["analysis_id"],
                        "now": _now().isoformat(timespec="seconds"),
                        "id": existing["id"],
                    })
                updated += 1
                continue
            history = get_condition_history(
                conn, cand["rule_type"], cand["condition"], cand.get("entity_type"),
                cand.get("entity_id"), cand.get("commodity"))
            if history and history[0]["status"] == "DISMISSED":
                # Operator intentionally dismissed this condition — do not
                # re-create it while the same condition persists.
                continue
            seq = conn.execute("SELECT COUNT(*) AS n FROM alerts").fetchone()["n"] + 1
            alert_id = "ALT-%04d-%04d" % (_now().year, seq)
            explanation = _ai_explanation(cand, generator=generator)
            insert_alert(
                conn,
                alert_id=alert_id,
                rule_type=cand["rule_type"],
                condition=cand["condition"],
                severity=cand["severity"],
                title=cand["title"],
                description=cand["description"],
                entity_type=cand.get("entity_type"),
                entity_id=cand.get("entity_id"),
                commodity=cand.get("commodity"),
                current_value=cand.get("current_value"),
                threshold=cand.get("threshold"),
                evidence=cand["evidence"],
                ai_explanation=explanation,
                recommendation=cand.get("recommendation"),
                source_id=cand.get("source_id"),
                import_id=cand.get("import_id"),
                analysis_id=cand.get("analysis_id"),
            )
            created += 1
            logger.info(
                "[Monitoring] created %s (%s/%s @ %s)", alert_id,
                cand["rule_type"], cand["condition"],
                cand.get("entity_id") or cand.get("commodity") or "?")

        # Auto-resolve conditions that are no longer detected.
        resolved = 0
        active = conn.execute(
            "SELECT * FROM alerts WHERE status IN ('OPEN','ACKNOWLEDGED')"
        ).fetchall()
        for row in active:
            a = dict(row)
            key = (a["rule_type"], a["condition"], a["entity_type"],
                   a["entity_id"], a["commodity"])
            if key not in by_key:
                conn.execute(
                    "UPDATE alerts SET status = 'RESOLVED', resolved_at = :now "
                    "WHERE id = :id",
                    {"now": _now().isoformat(timespec="seconds"), "id": a["id"]})
                resolved += 1
        conn.commit()
        counts = get_open_alert_counts(conn)
        return {
            "generated_at": _now().isoformat(timespec="seconds"),
            "created": created,
            "updated": updated,
            "resolved": resolved,
            "rules_enabled": sum(1 for rule in rules.values() if rule["enabled"]),
            "summary": counts,
        }
    finally:
        conn.close()


def _json_dumps(value) -> Optional[str]:
    import json as _json

    return _json.dumps(value) if value else None


# ---------------------------------------------------------------------------
# Read / write views used by the API + UI
# ---------------------------------------------------------------------------

def monitoring_status(db_path: str = DEFAULT_DB_PATH) -> dict:
    """Alert center status: active counts + last run info + enabled rules."""
    conn = open_db(db_path)
    try:
        _seed_rules(conn)
        counts = get_open_alert_counts(conn)
        by_type = {}
        for r in conn.execute(
            "SELECT rule_type, COUNT(*) AS n FROM alerts "
            "WHERE status IN ('OPEN','ACKNOWLEDGED') GROUP BY rule_type"
        ):
            by_type[r["rule_type"]] = r["n"]
        last_created = conn.execute(
            "SELECT MAX(created_at) AS t FROM alerts"
        ).fetchone()["t"]
        rules = list_alert_rules(conn)
    finally:
        conn.close()
    return {
        "counts": counts,
        "by_type": by_type,
        "rules": rules,
        "last_alert_created_at": last_created,
    }


def alert_summary(db_path: str = DEFAULT_DB_PATH) -> dict:
    conn = open_db(db_path)
    try:
        return get_open_alert_counts(conn)
    finally:
        conn.close()


def alert_trend(db_path: str = DEFAULT_DB_PATH, days: int = 7) -> dict:
    conn = open_db(db_path)
    try:
        return get_alert_trend(conn, days)
    finally:
        conn.close()


def alert_rules_view(db_path: str = DEFAULT_DB_PATH) -> dict:
    conn = open_db(db_path)
    try:
        _seed_rules(conn)
        return {"rules": list_alert_rules(conn)}
    finally:
        conn.close()


def update_rule_view(
    rule_id: int,
    *,
    enabled: Optional[bool] = None,
    threshold: Optional[float] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> Optional[dict]:
    conn = open_db(db_path)
    try:
        rule = get_alert_rule(conn, rule_id)
        if rule is None:
            return None
        if threshold is not None and (
            isinstance(threshold, bool) or not isinstance(threshold, (int, float))
            or threshold < 0
        ):
            raise ValueError("threshold must be a non-negative number")
        update_alert_rule(conn, rule_id, enabled=enabled, threshold=threshold)
        conn.commit()
        return get_alert_rule(conn, rule_id)
    finally:
        conn.close()


def list_alerts_view(
    db_path: str = DEFAULT_DB_PATH,
    *,
    q: Optional[str] = None,
    severity: Optional[str] = None,
    rule_type: Optional[str] = None,
    status: Optional[str] = None,
    days: Optional[int] = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    conn = open_db(db_path)
    try:
        return list_alerts(
            conn, q=q, severity=severity, rule_type=rule_type, status=status,
            days=days, page=page, per_page=per_page,
        )
    finally:
        conn.close()


def alert_detail_view(alert_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[dict]:
    """One alert decoded, plus lineage (source/dataset/analysis) for the UI."""
    conn = open_db(db_path)
    try:
        row = get_alert_by_alert_id(conn, alert_id)
        if row is None:
            return None
        alert = _decode(row)
        lineage = {}
        if alert.get("import_id"):
            imp = conn.execute(
                "SELECT i.dataset_name, i.file_name, i.file_type, i.record_count, "
                " i.successful_records, i.failed_records, i.duplicate_records, "
                " i.status AS import_status, s.name AS source_name "
                "FROM data_imports i LEFT JOIN data_sources s ON s.id = i.data_source_id "
                "WHERE i.id = :iid", {"iid": alert["import_id"]},
            ).fetchone()
            if imp is not None:
                lineage["import"] = dict(imp)
        elif alert.get("source_id"):
            src = conn.execute(
                "SELECT name, type, status, last_sync_at, last_successful_sync_at, "
                " last_error FROM data_sources WHERE id = :sid",
                {"sid": alert["source_id"]},
            ).fetchone()
            if src is not None:
                lineage["source"] = dict(src)
        if alert.get("analysis_id"):
            run = conn.execute(
                "SELECT analysis_id, dataset_mode, status, insight_count, "
                " summary, created_at FROM analysis_runs "
                "WHERE analysis_id = :aid", {"aid": alert["analysis_id"]},
            ).fetchone()
            if run is not None:
                lineage["analysis"] = dict(run)
        alert["lineage"] = lineage
        return alert
    finally:
        conn.close()


def _decode(row: dict) -> dict:
    import json as _json

    out = dict(row)
    for field in ("evidence", "ai_explanation"):
        raw = out.get(field)
        if isinstance(raw, str):
            try:
                out[field] = _json.loads(raw)
            except ValueError:
                out[field] = None
    return out


def set_alert_status_view(
    alert_id: str,
    status: str,
    *,
    dismissed_reason: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> bool:
    if status not in ("ACKNOWLEDGED", "RESOLVED", "DISMISSED"):
        raise ValueError("status must be ACKNOWLEDGED, RESOLVED, or DISMISSED")
    conn = open_db(db_path)
    try:
        changed = update_alert_status(
            conn, alert_id, status, dismissed_reason=dismissed_reason)
        conn.commit()
        return changed
    finally:
        conn.close()


# Keep the alert type taxonomy importable from this module too.
ALERT_TYPE_TAXONOMY = list(ALERT_TYPES)
SEVERITY_ORDER = list(ALERT_SEVERITIES)
