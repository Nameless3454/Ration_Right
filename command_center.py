"""RationAI — Executive Command Center & Intelligence Reports backend (Phase 12).

An ORCHESTRATION layer, not another analytics engine. Everything here is a
read-only projection of the existing Phase 5 analytics, Phase 9 AI insights,
Phase 10 simulations, and Phase 11 alerts — the same formulas, thresholds,
and severity conventions are reused, never duplicated.

The command center answers, for a configurable scope (state / district / FPS /
commodity / date range):

    What is happening?          -> KPIs (with current vs previous comparison)
    Where are the problems?     -> district + FPS risk tables (ranked)
    How serious are they?       -> risk overview from Phase 11 alerts
    What changed?               -> distribution/demand/alert trends
    What does the AI recommend? -> executive summary + recommended actions
    What should be investigated?-> top AI insights + active alerts
    How fresh is the data?      -> Phase 8 freshness + source status
    Where did it come from?     -> lineage (sources -> imports -> analyses)

Hard rules:
- No fake values: every number comes from the database or a stored Phase 11
  alert / Phase 9 insight. Missing data renders as None -> "Not available".
- The executive summary is generated ONLY from a compact structured context
  (KPIs, counts, top alerts/insights) via ``agents.llm.maybe_generate`` with
  a deterministic fallback; the LLM never sees raw rows and never calculates.
- Reports are persisted (``reports`` table, RPT-YYYY-NNNN, never overwritten)
  and carry full lineage for auditability.
- Simulation results are NEVER mixed into live KPIs (Phase 10 writes only to
  the scenarios table, which this module ignores).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from agents.llm import maybe_generate
from analytics import INVENTORY_CRITICAL_DAYS, INVENTORY_WARNING_DAYS
from database import (
    DEFAULT_DB_PATH,
    get_report_by_report_id,
    insert_report,
    list_reports,
    open_db,
)
from pipeline import freshness, quality_panel

logger = logging.getLogger("rationright.command_center")

#: Default comparison window when no explicit dates are given: the last 30
#: days vs the 30 days before that.
DEFAULT_WINDOW_DAYS = 30
TREND_RANGES = ("7d", "30d", "90d")

_SEVERITY_RANK = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_date(value) -> Optional[str]:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def _window(from_date: Optional[str], to_date: Optional[str]):
    """Return ``(from_d, to_d, prev_from_d, prev_to_d)`` as ISO dates.

    Current window is [from, to] (default: the last 30 days); the previous
    window is the same length immediately before it. Deterministic, validated.
    """
    to = _iso_date(to_date) or _now().date().isoformat()
    frm = _iso_date(from_date)
    if frm is None:
        frm = (_now().date() - timedelta(days=DEFAULT_WINDOW_DAYS - 1)).isoformat()
    if frm > to:
        raise ValueError("from date must be on or before to date")
    length = (date.fromisoformat(to) - date.fromisoformat(frm)).days + 1
    prev_to = (date.fromisoformat(frm) - timedelta(days=1)).isoformat()
    prev_from = (date.fromisoformat(prev_to) - timedelta(days=length - 1)).isoformat()
    return frm, to, prev_from, prev_to


# ---------------------------------------------------------------------------
# Scope helpers (parameterized — never user-supplied SQL)
# ---------------------------------------------------------------------------

def _scope(conn, *, state=None, district=None, fps=None, commodity=None,
           from_date=None, to_date=None, tx_alias="t"):
    """WHERE clause + params scoping transactions by geography/commodity/date.

    Geography resolves through fps_centers (an FPS belongs to a district/state).
    Date uses the documented date-only comparison (both YYYY-MM-DD and
    YYYY-MM-DDTHH:MM:SS values exist in the DB).
    """
    where, params = [], {}
    if commodity:
        where.append("LOWER(%s.commodity) = LOWER(:commodity)" % tx_alias)
        params["commodity"] = commodity.strip()
    if fps:
        where.append("f.fps_code = :fps")
        params["fps"] = fps.strip()
    elif district:
        where.append("COALESCE(f.district, '') = :district")
        params["district"] = district.strip()
    elif state:
        where.append("COALESCE(f.state, '') = :state")
        params["state"] = state.strip()
    if from_date:
        where.append("substr(%s.transaction_date, 1, 10) >= :from_date" % tx_alias)
        params["from_date"] = from_date
    if to_date:
        where.append("substr(%s.transaction_date, 1, 10) <= :to_date" % tx_alias)
        params["to_date"] = to_date
    return (" WHERE " + " AND ".join(where)) if where else "", params


def _districts(conn) -> list:
    rows = conn.execute(
        "SELECT DISTINCT district FROM fps_centers "
        "WHERE district IS NOT NULL AND district != '' ORDER BY district"
    ).fetchall()
    return [r["district"] for r in rows]


def _commodities(conn) -> list:
    rows = conn.execute(
        "SELECT DISTINCT commodity FROM ration_transactions "
        "WHERE commodity IS NOT NULL ORDER BY commodity"
    ).fetchall()
    return [r["commodity"] for r in rows]


def _fps_list(conn) -> list:
    # Scope the filter to FPS centers that actually appear in transactions:
    # filtering by a center with zero records cannot change any widget, and
    # the full registry (e.g. 50k+ real FPS from an OGD sync) must never be
    # shipped to the browser as a plain <select> (performance, Phase 12 §35).
    rows = conn.execute(
        "SELECT DISTINCT f.fps_code FROM fps_centers f "
        "JOIN ration_transactions t ON t.fps_center_id = f.id "
        "WHERE f.fps_code IS NOT NULL AND f.fps_code != '' "
        "ORDER BY f.fps_code"
    ).fetchall()
    return [r["fps_code"] for r in rows]


# ---------------------------------------------------------------------------
# Alert scoping — an alert references an FPS (by code), a commodity, a data
# source, or a beneficiary; geography resolves through fps_centers.
# ---------------------------------------------------------------------------

def _scoped_alerts(conn, *, state=None, district=None, fps=None, commodity=None) -> list:
    rows = conn.execute(
        "SELECT a.*, f.district AS fps_district, f.state AS fps_state "
        "FROM alerts a LEFT JOIN fps_centers f ON f.fps_code = a.entity_id "
        "AND a.entity_type = 'fps_center' "
        "WHERE a.status IN ('OPEN','ACKNOWLEDGED') ORDER BY a.last_detected_at DESC"
    ).fetchall()
    out = []
    for row in rows:
        a = dict(row)
        if commodity and (a.get("commodity") or "") != commodity:
            continue
        if fps and not (a["entity_type"] == "fps_center" and a["entity_id"] == fps):
            continue
        if district and a.get("fps_district") != district:
            continue
        if state and a.get("fps_state") != state:
            continue
        out.append(a)
    return out


# ---------------------------------------------------------------------------
# KPIs (current vs previous window, deterministic comparisons)
# ---------------------------------------------------------------------------

def _change_pct(current, previous):
    if previous is None or current is None:
        return None
    if previous == 0:
        return None
    return round((current - previous) / previous * 100.0, 1)


def _kpi(key, label, value, unit, status, current, previous=None, *, note=None):
    return {
        "key": key, "label": label, "value": value, "unit": unit,
        "status": status, "note": note,
        "comparison": {
            "current": current,
            "previous": previous,
            "change_pct": _change_pct(current, previous),
            "available": previous is not None,
        },
    }


def _distribution_kpis(conn, *, from_date, to_date, prev_from, prev_to, scope_sql,
                       scope_params, filters) -> list:
    clause = scope_sql
    params = dict(scope_params)

    def _sum(frm, to):
        p = dict(params)
        p["from_date"] = frm
        p["to_date"] = to
        w = " AND substr(t.transaction_date, 1, 10) >= :from_date AND substr(t.transaction_date, 1, 10) <= :to_date"
        row = conn.execute(
            "SELECT COALESCE(SUM(t.quantity), 0) AS qty, COUNT(*) AS n "
            "FROM ration_transactions t LEFT JOIN fps_centers f ON f.id = t.fps_center_id "
            + clause + w, p).fetchone()
        return row["qty"], row["n"]

    cur_qty, cur_n = _sum(from_date, to_date)
    prev_qty, prev_n = _sum(prev_from, prev_to)
    return [
        _kpi("distribution", "Total distribution", round(cur_qty, 2), "kg",
             "ok" if cur_qty > 0 else "muted", cur_qty, prev_qty),
        _kpi("transactions", "Transactions", cur_n, "", "muted", cur_n, prev_n),
    ]


def _inventory_scope(scope_sql, scope_params):
    """Inventory is a point-in-time snapshot: reuse the geography/commodity
    scope but drop the date window (inventory has no transaction date)."""
    where = scope_sql.replace("t.", "i.")
    parts = [p.strip() for p in where.replace(" WHERE ", "", 1).split(" AND ") if p.strip()]
    parts = [p for p in parts if "transaction_date" not in p]
    clause = (" WHERE " + " AND ".join(parts)) if parts else ""
    params = {k: v for k, v in scope_params.items() if k not in ("from_date", "to_date")}
    return clause, params


def _inventory_kpis(conn, *, scope_sql, scope_params) -> list:
    # Inventory is a point-in-time snapshot (no history) — comparison is not
    # available and is reported honestly as such.
    where, params = _inventory_scope(scope_sql, scope_params)
    row = conn.execute(
        "SELECT COALESCE(SUM(i.current_stock), 0) AS stock, "
        " COALESCE(SUM(CASE WHEN i.monthly_consumption > 0 THEN "
        "   i.current_stock / (i.monthly_consumption / 30.0) END), 0) AS coverage_sum, "
        " COALESCE(SUM(CASE WHEN i.monthly_consumption > 0 THEN 1 ELSE 0 END), 0) AS coverage_n, "
        " COUNT(DISTINCT i.fps_center_id) AS centers "
        "FROM inventory i LEFT JOIN fps_centers f ON f.id = i.fps_center_id" + where,
        params,
    ).fetchone()
    avg_coverage = (row["coverage_sum"] / row["coverage_n"]) if row["coverage_n"] else None
    return [
        _kpi("inventory", "Total inventory", round(row["stock"], 2), "kg",
             "ok" if row["stock"] > 0 else "muted", row["stock"], None,
             note="point-in-time snapshot — no historical comparison"),
        _kpi("coverage", "Avg inventory coverage",
             round(avg_coverage, 1) if avg_coverage is not None else None,
             "days", ("warning" if avg_coverage is not None and avg_coverage < INVENTORY_WARNING_DAYS
                      else "ok" if avg_coverage is not None else "muted"),
             avg_coverage, None, note="current_stock / daily consumption"),
    ]


def _risk_fps(conn, *, scope_sql, scope_params, filters) -> list:
    """FPS with coverage below thresholds or below reorder (scoped)."""
    where, params = _inventory_scope(scope_sql, scope_params)
    rows = conn.execute(
        "SELECT COALESCE(f.fps_code, 'Unknown') AS fps_code, f.district, "
        " i.commodity, i.current_stock, i.monthly_consumption, i.reorder_threshold "
        "FROM inventory i LEFT JOIN fps_centers f ON f.id = i.fps_center_id" + where,
        params,
    ).fetchall()
    high = set()
    for r in rows:
        stock = r["current_stock"] or 0
        monthly = r["monthly_consumption"]
        if r["reorder_threshold"] is not None and stock < r["reorder_threshold"]:
            high.add(r["fps_code"])
        if monthly and monthly > 0 and stock / (monthly / 30.0) < INVENTORY_WARNING_DAYS:
            high.add(r["fps_code"])
    return sorted(high)


# ---------------------------------------------------------------------------
# District / FPS risk tables
# ---------------------------------------------------------------------------

def _district_risk(conn, *, from_date, to_date, scope_sql, scope_params, alerts) -> list:
    # Distribution per district (scoped by the caller's geography/date).
    p = dict(scope_params)
    p["from_date"] = from_date
    p["to_date"] = to_date
    rows = conn.execute(
        "SELECT COALESCE(f.district, 'Unknown') AS district, "
        " COALESCE(SUM(t.quantity), 0) AS qty, COUNT(t.id) AS n "
        "FROM ration_transactions t LEFT JOIN fps_centers f ON f.id = t.fps_center_id" +
        scope_sql +
        " AND substr(t.transaction_date, 1, 10) >= :from_date "
        " AND substr(t.transaction_date, 1, 10) <= :to_date "
        "GROUP BY district ORDER BY qty DESC",
        p,
    ).fetchall()
    # Coverage per district from inventory (point-in-time).
    inv = conn.execute(
        "SELECT COALESCE(f.district, 'Unknown') AS district, "
        " COALESCE(SUM(CASE WHEN i.monthly_consumption > 0 THEN "
        "   i.current_stock / (i.monthly_consumption / 30.0) END), 0) AS coverage_sum, "
        " COALESCE(SUM(CASE WHEN i.monthly_consumption > 0 THEN 1 ELSE 0 END), 0) AS coverage_n "
        "FROM inventory i LEFT JOIN fps_centers f ON f.id = i.fps_center_id "
        "GROUP BY district"
    ).fetchall()
    coverage = {r["district"]: (r["coverage_sum"] / r["coverage_n"] if r["coverage_n"] else None)
                for r in inv}
    # Alerts per district (alerts reference FPS codes).
    alert_counts = {}
    alert_max = {}
    fps_to_district = {
        r["fps_code"]: r["district"] for r in conn.execute(
            "SELECT fps_code, district FROM fps_centers WHERE district IS NOT NULL")
    }
    for a in alerts:
        dist = a.get("fps_district")
        if not dist and a["entity_type"] == "fps_center":
            dist = fps_to_district.get(a["entity_id"])
        if not dist:
            continue
        alert_counts[dist] = alert_counts.get(dist, 0) + 1
        alert_max[dist] = max(alert_max.get(dist, 0), _SEVERITY_RANK.get(a["severity"], 0))

    out = []
    for r in rows:
        dist = r["district"]
        cov = coverage.get(dist)
        n_alerts = alert_counts.get(dist, 0)
        severity = alert_max.get(dist, 0)
        if severity >= 4 or (cov is not None and cov < INVENTORY_CRITICAL_DAYS):
            risk = "HIGH"
        elif severity >= 3 or (cov is not None and cov < INVENTORY_WARNING_DAYS):
            risk = "MEDIUM"
        elif n_alerts or r["n"]:
            risk = "LOW"
        else:
            risk = "LOW"
        out.append({
            "district": dist, "distribution_kg": round(r["qty"], 2),
            "transactions": r["n"],
            "coverage_days": round(cov, 1) if cov is not None else None,
            "alerts": n_alerts, "risk": risk,
        })
    rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    out.sort(key=lambda d: (rank.get(d["risk"], 3), -d["distribution_kg"]))
    return out


def _fps_risk(conn, *, from_date, to_date, scope_sql, scope_params, alerts) -> list:
    p = dict(scope_params)
    p["from_date"] = from_date
    p["to_date"] = to_date
    rows = conn.execute(
        "SELECT COALESCE(f.fps_code, 'Unknown') AS fps_code, f.district, "
        " COALESCE(SUM(t.quantity), 0) AS qty, COUNT(t.id) AS n "
        "FROM ration_transactions t LEFT JOIN fps_centers f ON f.id = t.fps_center_id" +
        scope_sql +
        " AND substr(t.transaction_date, 1, 10) >= :from_date "
        " AND substr(t.transaction_date, 1, 10) <= :to_date "
        "GROUP BY fps_code ORDER BY qty DESC",
        p,
    ).fetchall()
    inv = conn.execute(
        "SELECT COALESCE(f.fps_code, 'Unknown') AS fps_code, "
        " COALESCE(SUM(CASE WHEN i.monthly_consumption > 0 THEN "
        "   i.current_stock / (i.monthly_consumption / 30.0) END), 0) AS coverage_sum, "
        " COALESCE(SUM(CASE WHEN i.monthly_consumption > 0 THEN 1 ELSE 0 END), 0) AS coverage_n, "
        " MIN(CASE WHEN i.reorder_threshold IS NOT NULL AND i.current_stock < i.reorder_threshold "
        "     THEN 1 ELSE 0 END) AS below_reorder "
        "FROM inventory i LEFT JOIN fps_centers f ON f.id = i.fps_center_id "
        "GROUP BY fps_code"
    ).fetchall()
    coverage = {r["fps_code"]: (r["coverage_sum"] / r["coverage_n"] if r["coverage_n"] else None)
                for r in inv}
    below = {r["fps_code"]: bool(r["below_reorder"]) for r in inv}
    alert_counts, alert_max = {}, {}
    for a in alerts:
        if a["entity_type"] == "fps_center" and a["entity_id"]:
            alert_counts[a["entity_id"]] = alert_counts.get(a["entity_id"], 0) + 1
            alert_max[a["entity_id"]] = max(
                alert_max.get(a["entity_id"], 0), _SEVERITY_RANK.get(a["severity"], 0))

    out = []
    for r in rows:
        fps_code = r["fps_code"]
        cov = coverage.get(fps_code)
        sev = alert_max.get(fps_code, 0)
        if sev >= 4 or (cov is not None and cov < INVENTORY_CRITICAL_DAYS) or below.get(fps_code):
            risk = "HIGH"
        elif sev >= 3 or (cov is not None and cov < INVENTORY_WARNING_DAYS):
            risk = "MEDIUM"
        else:
            risk = "LOW"
        out.append({
            "fps_code": fps_code, "district": r["district"],
            "distribution_kg": round(r["qty"], 2), "transactions": r["n"],
            "coverage_days": round(cov, 1) if cov is not None else None,
            "alerts": alert_counts.get(fps_code, 0), "risk": risk,
        })
    rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    out.sort(key=lambda d: (rank.get(d["risk"], 3), -d["distribution_kg"]))
    return out


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------

def _trends(conn, *, trend_range, from_date, to_date, scope_sql, scope_params) -> dict:
    if trend_range not in TREND_RANGES:
        trend_range = "30d"
    days = int(trend_range[:-1])
    to = _iso_date(to_date) or _now().date().isoformat()
    frm = (date.fromisoformat(to) - timedelta(days=days - 1)).isoformat()
    p = dict(scope_params)
    p["from_date"] = frm
    p["to_date"] = to

    distribution = conn.execute(
        "SELECT substr(t.transaction_date, 1, 10) AS day, "
        " COALESCE(SUM(t.quantity), 0) AS qty, COUNT(*) AS n "
        "FROM ration_transactions t LEFT JOIN fps_centers f ON f.id = t.fps_center_id" +
        scope_sql +
        " AND substr(t.transaction_date, 1, 10) >= :from_date "
        " AND substr(t.transaction_date, 1, 10) <= :to_date "
        "GROUP BY day ORDER BY day",
        p,
    ).fetchall()
    by_day = {r["day"]: r for r in distribution}
    series = []
    for offset in range(days):
        day = (date.fromisoformat(to) - timedelta(days=days - 1 - offset)).isoformat()
        r = by_day.get(day)
        series.append({"date": day, "quantity": round(r["qty"], 2) if r else 0.0,
                       "count": r["n"] if r else 0})
    by_commodity = conn.execute(
        "SELECT t.commodity, COALESCE(SUM(t.quantity), 0) AS qty, COUNT(*) AS n "
        "FROM ration_transactions t LEFT JOIN fps_centers f ON f.id = t.fps_center_id" +
        scope_sql +
        " AND substr(t.transaction_date, 1, 10) >= :from_date "
        " AND substr(t.transaction_date, 1, 10) <= :to_date "
        "GROUP BY t.commodity ORDER BY qty DESC",
        p,
    ).fetchall()
    total_qty = sum(r["quantity"] for r in series)
    return {
        "range": trend_range,
        "from": frm, "to": to,
        "total_quantity": round(total_qty, 2),
        "distribution": series,
        "by_commodity": [{"commodity": r["commodity"], "quantity": round(r["qty"], 2),
                          "count": r["n"]} for r in by_commodity],
    }


def _alert_trend(conn, days: int = 7) -> dict:
    from database import get_alert_trend

    return get_alert_trend(conn, days)


# ---------------------------------------------------------------------------
# Insights / alerts / recommended actions
# ---------------------------------------------------------------------------

def _top_insights(conn, limit: int = 5) -> list:
    rows = conn.execute(
        "SELECT * FROM ai_insights ORDER BY "
        "CASE severity WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 "
        "WHEN 'LOW' THEN 3 ELSE 4 END, id DESC LIMIT :limit",
        {"limit": limit},
    ).fetchall()
    import json as _json

    out = []
    for r in rows:
        d = dict(r)
        raw = d.get("evidence")
        if isinstance(raw, str):
            try:
                d["evidence"] = _json.loads(raw)
            except ValueError:
                d["evidence"] = None
        out.append(d)
    return out


def _recommended_actions(alerts, insights, limit: int = 6) -> list:
    actions = []
    for a in alerts:
        text = (a.get("recommendation") or "").strip()
        if not text:
            continue
        actions.append({
            "priority": a["severity"], "action": text,
            "source": "alert", "entity": a.get("entity_id"), "alert_id": a["alert_id"],
        })
    for i in insights:
        if i.get("insight_type") != "RECOMMENDATION":
            continue
        text = (i.get("recommendation") or i.get("title") or "").strip()
        if not text or any(x["action"] == text for x in actions):
            continue
        actions.append({
            "priority": i["severity"], "action": text,
            "source": "ai", "entity": i.get("entity_id"),
            "analysis_id": i.get("analysis_id"),
        })
    actions.sort(key=lambda x: -_SEVERITY_RANK.get(x["priority"], 0))
    return actions[:limit]


# ---------------------------------------------------------------------------
# Executive summary (AI from a compact structured context — deterministic
# fallback; never invents; never sees raw rows)
# ---------------------------------------------------------------------------

def _executive_summary(payload: dict, generator=None) -> dict:
    kpis = {k["key"]: k for k in payload["kpis"]}
    risk = payload["risk_overview"]
    top_alerts = [a for a in payload["active_alerts"]][:3]
    top_insights = [i for i in payload["top_insights"]][:3]
    districts = [d for d in payload["district_risk"]][:3]
    quality = payload["data_quality"]
    context = {
        "total_distribution_kg": (kpis.get("distribution") or {}).get("value"),
        "active_alerts": risk.get("total", 0),
        "alert_counts": {sev: risk.get(sev.lower(), 0) for sev in
                         ("critical", "high", "medium", "low")},
        "top_alerts": [{"title": a.get("title"), "severity": a.get("severity"),
                        "entity": a.get("entity_id")} for a in top_alerts],
        "top_insights": [{"title": i.get("title"), "severity": i.get("severity"),
                          "entity": i.get("entity_id")} for i in top_insights],
        "top_districts": [{"district": d.get("district"), "risk": d.get("risk"),
                           "alerts": d.get("alerts")} for d in districts],
        "data_quality_pct": quality.get("overall"),
        "freshness_status": payload["freshness"].get("status"),
        "data_status_note": payload["disclaimer"],
    }
    empty = (not (payload["kpis"] or [])) and risk.get("total", 0) == 0 \
        and not payload["top_insights"]
    if empty:
        return {"summary": "Insufficient data to provide a reliable executive summary.",
                "generated_by": "deterministic_fallback"}
    fallback = _fallback_summary(payload)
    text = maybe_generate("executive_summary", context, fallback, generator=generator)
    return {"summary": text,
            "generated_by": "llm" if text != fallback else "deterministic_fallback"}


def _fallback_summary(payload: dict) -> str:
    risk = payload["risk_overview"]
    kpis = {k["key"]: k for k in payload["kpis"]}
    parts = []
    dist = (kpis.get("distribution") or {}).get("value")
    if dist:
        parts.append("Total distribution is %.0f kg in the selected window." % dist)
    if risk.get("total"):
        parts.append("%d active alert(s) (%d critical, %d high) require attention." % (
            risk["total"], risk.get("critical", 0), risk.get("high", 0)))
    high_districts = [d for d in payload["district_risk"] if d["risk"] == "HIGH"][:3]
    if high_districts:
        parts.append("High-risk district(s): %s." % ", ".join(
            d["district"] for d in high_districts))
    if payload["top_insights"]:
        parts.append("Top AI insight: %s (%s)." % (
            payload["top_insights"][0]["title"], payload["top_insights"][0]["severity"]))
    if not parts:
        return "Insufficient data to provide a reliable executive summary."
    return " ".join(parts) + " This summary reflects the current monitored state and is not a prediction."


# ---------------------------------------------------------------------------
# Main orchestration entry point
# ---------------------------------------------------------------------------

def command_center(
    db_path: str = DEFAULT_DB_PATH,
    *,
    state: Optional[str] = None,
    district: Optional[str] = None,
    fps: Optional[str] = None,
    commodity: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    trend_range: str = "30d",
    generator=None,
) -> dict:
    """The complete command-center payload for one scope. Read-only."""
    conn = open_db(db_path)
    try:
        frm, to, prev_from, prev_to = _window(from_date, to_date)
        scope_sql, scope_params = _scope(
            conn, state=state, district=district, fps=fps, commodity=commodity,
            from_date=frm, to_date=to)
        filters = {"state": state, "district": district, "fps": fps,
                   "commodity": commodity, "from": frm, "to": to,
                   "trend_range": trend_range}

        alerts = _scoped_alerts(conn, state=state, district=district, fps=fps,
                                commodity=commodity)
        kpis = []
        kpis.extend(_distribution_kpis(conn, from_date=frm, to_date=to,
                                       prev_from=prev_from, prev_to=prev_to,
                                       scope_sql=scope_sql, scope_params=scope_params,
                                       filters=filters))
        kpis.extend(_inventory_kpis(conn, scope_sql=scope_sql, scope_params=scope_params))
        high_risk_fps = _risk_fps(conn, scope_sql=scope_sql, scope_params=scope_params,
                                  filters=filters)
        risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for a in alerts:
            sev = (a.get("severity") or "LOW").lower()
            if sev in risk_counts:
                risk_counts[sev] += 1
        kpis.append(_kpi("active_alerts", "Active alerts", len(alerts), "",
                         "warning" if len(alerts) else "ok", len(alerts), None,
                         note="OPEN + acknowledged (Phase 11)"))
        kpis.append(_kpi("critical_alerts", "Critical alerts",
                         risk_counts["critical"], "", "error" if risk_counts["critical"] else "ok",
                         risk_counts["critical"], None))
        kpis.append(_kpi("high_risk_fps", "High-risk FPS", len(high_risk_fps), "",
                         "error" if high_risk_fps else "ok", len(high_risk_fps), None,
                         note="coverage < %dd or below reorder threshold" % INVENTORY_WARNING_DAYS))
        quality = quality_panel(db_path=db_path)
        kpis.append(_kpi("data_quality", "Data quality",
                         quality.get("overall"), "%",
                         "ok" if (quality.get("overall") or 0) >= 90 else
                         "warning" if (quality.get("overall") or 0) is not None else "muted",
                         quality.get("overall"), None, note="global — Phase 4 formula"))

        district_risk = _district_risk(conn, from_date=frm, to_date=to,
                                       scope_sql=scope_sql, scope_params=scope_params,
                                       alerts=alerts)
        fps_risk = _fps_risk(conn, from_date=frm, to_date=to,
                             scope_sql=scope_sql, scope_params=scope_params, alerts=alerts)
        trends = _trends(conn, trend_range=trend_range, from_date=frm, to_date=to,
                         scope_sql=scope_sql, scope_params=scope_params)
        insights = _top_insights(conn)
        active = [a for a in alerts
                  if a["severity"] in ("CRITICAL", "HIGH")][:6]
        actions = _recommended_actions(alerts, insights)
        fresh = freshness(db_path=db_path)
        sources = _source_lineage(conn)
        payload = {
            "generated_at": _now().isoformat(timespec="seconds"),
            "filters": filters,
            "filter_options": {"states": _states(conn), "districts": _districts(conn),
                               "fps": _fps_list(conn), "commodities": _commodities(conn)},
            "freshness": fresh,
            "sources": sources,
            "disclaimer": _disclaimer(conn),
            "data_quality": quality,
            "kpis": kpis,
            "risk_overview": {**risk_counts, "total": len(alerts)},
            "district_risk": district_risk,
            "fps_risk": fps_risk,
            "trends": trends,
            "alert_trend": _alert_trend(conn, 7),
            "top_insights": insights,
            "active_alerts": active,
            "recommended_actions": actions,
            "lineage": _lineage(conn),
        }
        payload["executive_summary"] = _executive_summary(payload, generator=generator)
        return payload
    finally:
        conn.close()


def _states(conn) -> list:
    rows = conn.execute(
        "SELECT DISTINCT state FROM fps_centers WHERE state IS NOT NULL AND state != '' "
        "ORDER BY state"
    ).fetchall()
    return [r["state"] for r in rows]


def _source_lineage(conn) -> list:
    rows = conn.execute(
        "SELECT s.id, s.name, s.type, s.status, s.last_successful_sync_at, s.last_error, "
        " (SELECT COUNT(*) FROM data_imports i WHERE i.data_source_id = s.id) AS imports "
        "FROM data_sources s ORDER BY s.id"
    ).fetchall()
    return [dict(r) for r in rows]


def _disclaimer(conn) -> str:
    sources = [r["name"] for r in conn.execute("SELECT name FROM data_sources").fetchall()]
    real = any(s != "Synthetic Demo Dataset" for s in sources)
    mock = any("sample" in (s or "").lower() for s in sources)
    parts = []
    if real:
        parts.append("Analysis based on imported dataset.")
    if mock:
        parts.append("Includes bundled sample data (mock/test), clearly labeled.")
    if not real and sources:
        parts.append("Analysis based on synthetic demo data only.")
    if any(s == "ogd_pds_resource" for s in sources):
        parts.append("Government connector: CONNECTOR READY / NOT CONNECTED — no live source verified.")
    return " ".join(parts) if parts else "No data sources configured."


def _lineage(conn) -> dict:
    import_count = conn.execute("SELECT COUNT(*) AS n FROM data_imports").fetchone()["n"]
    latest_imports = conn.execute(
        "SELECT i.id, i.dataset_name, i.status, i.record_count, i.successful_records, "
        " i.completed_at, s.name AS source_name "
        "FROM data_imports i LEFT JOIN data_sources s ON s.id = i.data_source_id "
        "ORDER BY i.id DESC LIMIT 5"
    ).fetchall()
    analysis_count = conn.execute("SELECT COUNT(*) AS n FROM analysis_runs").fetchone()["n"]
    latest_analysis = conn.execute(
        "SELECT analysis_id, dataset_mode, status, insight_count, created_at "
        "FROM analysis_runs ORDER BY id DESC LIMIT 3"
    ).fetchall()
    return {
        "import_count": import_count,
        "latest_imports": [dict(r) for r in latest_imports],
        "analysis_count": analysis_count,
        "latest_analysis_runs": [dict(r) for r in latest_analysis],
    }


# ---------------------------------------------------------------------------
# Intelligence reports (persisted, never overwritten, fully traceable)
# ---------------------------------------------------------------------------

def generate_report(
    db_path: str = DEFAULT_DB_PATH,
    *,
    period: Optional[str] = None,
    source: Optional[str] = None,
    filters: Optional[dict] = None,
    generator=None,
) -> dict:
    """Build + persist one intelligence report; returns the stored report."""
    conn = open_db(db_path)
    try:
        seq = conn.execute("SELECT COUNT(*) AS n FROM reports").fetchone()["n"] + 1
        report_id = "RPT-%04d-%04d" % (_now().year, seq)
    finally:
        conn.close()

    cc = command_center(db_path, **(filters or {}), generator=generator)
    period_label = period or "%s – %s" % (cc["filters"]["from"], cc["filters"]["to"])
    source_label = source or (", ".join(
        s["name"] for s in cc["sources"][:3]) or "Not available")
    report = {
        "report_id": report_id,
        "period": period_label,
        "source": source_label,
        "generated_at": cc["generated_at"],
        "disclaimer": cc["disclaimer"],
        "executive_summary": cc["executive_summary"],
        "kpis": cc["kpis"],
        "risk_overview": cc["risk_overview"],
        "district_risk": cc["district_risk"],
        "fps_risk": cc["fps_risk"],
        "trends": cc["trends"],
        "top_insights": cc["top_insights"],
        "active_alerts": cc["active_alerts"],
        "recommended_actions": cc["recommended_actions"],
        "data_quality": cc["data_quality"],
        "freshness": cc["freshness"],
        "lineage": cc["lineage"],
        "filters": cc["filters"],
    }
    conn = open_db(db_path)
    try:
        insert_report(
            conn, report_id=report_id, period_label=period_label,
            source_label=source_label, filters=cc["filters"], payload=report)
        conn.commit()
    finally:
        conn.close()
    return report


def report_history(db_path: str = DEFAULT_DB_PATH) -> dict:
    conn = open_db(db_path)
    try:
        return {"reports": list_reports(conn)}
    finally:
        conn.close()


def report_detail(report_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[dict]:
    conn = open_db(db_path)
    try:
        return get_report_by_report_id(conn, report_id)
    finally:
        conn.close()
