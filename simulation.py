"""RationAI — Decision Support & What-If Simulation backend (Phase 10).

Turns RationAI into a decision-support system: an operator takes a real
problem (a district, an FPS, a commodity) and asks *what happens if this
changes* — demand +10%, a 7-day supply delay, an inventory change.

Hard rules honoured here:

- **Deterministic calculations only.** Every number in a scenario result is
  computed from the real database baseline by this module's arithmetic
  (projected demand, daily consumption, coverage days, stock after delay,
  reorder requirement). The LLM is never asked to calculate.
- **Simulations never touch real data.** A scenario operates on derived
  values; only the scenario metadata/result is persisted (``scenarios``
  table). Inventory, beneficiaries, transactions, and imports are read-only.
- **No invented baselines.** If the selected entity/commodity has no data,
  the result is a structured INSUFFICIENT_DATA — never an AI guess.
- **Validated inputs.** demand change in [-50, +100]%, supply delay in
  [0, 365] days, inventory change in [-100, +100]% (documented constants).
- **Reuses the existing risk thresholds** (INVENTORY_CRITICAL_DAYS=15,
  INVENTORY_WARNING_DAYS=30) — no second, incompatible risk system.
- **AI interpretation is optional and fail-open**: the deterministic
  explanation is always present; the LLM (if enabled) only rephrases it from
  the supplied values via ``agents.llm.maybe_generate``.

Scenario IDs (SIM-YYYY-NNNN) and their results are persisted so history can
reproduce any simulation and trace it back to dataset -> import -> source.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from agents.llm import maybe_generate
from analytics import INVENTORY_CRITICAL_DAYS, INVENTORY_WARNING_DAYS
from data_context import get_import_metadata
from database import (
    DEFAULT_DB_PATH,
    get_scenario,
    get_scenario_by_id,
    get_scenarios,
    insert_scenario,
    open_db,
)

logger = logging.getLogger("rationright.simulation")

DAYS_PER_MONTH = 30

# --- validated input ranges (documented) -----------------------------------
DEMAND_CHANGE_MIN = -50
DEMAND_CHANGE_MAX = 100
SUPPLY_DELAY_MIN = 0
SUPPLY_DELAY_MAX = 365
INVENTORY_CHANGE_MIN = -100
INVENTORY_CHANGE_MAX = 100

SIMULATION_TYPES = [
    {"key": "DEMAND_CHANGE", "label": "Demand change",
     "description": "Project demand, daily consumption, and coverage when "
                    "monthly demand changes by a percentage."},
    {"key": "SUPPLY_DELAY", "label": "Supply delay",
     "description": "Estimate the stock position after a supply delay of N "
                    "days at the projected consumption rate."},
    {"key": "INVENTORY_CHANGE", "label": "Inventory change",
     "description": "Project coverage when available inventory is increased "
                    "or reduced by a percentage."},
    {"key": "COMBINED", "label": "Combined scenario",
     "description": "Demand change + supply delay + inventory change in one "
                    "scenario."},
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def simulation_type_registry() -> list:
    return list(SIMULATION_TYPES)


# ---------------------------------------------------------------------------
# Entities (loaded from the database — never hardcoded)
# ---------------------------------------------------------------------------

def _scope_clause(prefix: str, *, fps_code=None, district=None, commodity=None):
    """Parameterized WHERE fragment + params for entity/commodity scoping.

    ``prefix`` is the table alias ("t" for transactions, "i" for inventory);
    transactions are already filtered by import id by the caller.
    """
    where = []
    params = {}
    if commodity:
        where.append("LOWER(%s.commodity) = LOWER(:commodity)" % prefix)
        params["commodity"] = commodity.strip()
    if fps_code:
        where.append("f.fps_code = :fps")
        params["fps"] = fps_code.strip()
    if district:
        where.append("LOWER(f.district) = LOWER(:district)")
        params["district"] = district.strip()
    return (" AND " + " AND ".join(where)) if where else "", params


def simulation_entities(import_id: int, db_path: str = DEFAULT_DB_PATH) -> dict:
    """Commodities / districts / FPS centers actually present in one import."""
    conn = open_db(db_path)
    try:
        commodities = [r["commodity"] for r in conn.execute(
            "SELECT DISTINCT commodity FROM ration_transactions "
            "WHERE source_import_id = :imp AND commodity IS NOT NULL "
            "ORDER BY commodity", {"imp": import_id})]
        districts = [r["district"] for r in conn.execute(
            "SELECT DISTINCT f.district FROM ration_transactions t "
            "JOIN fps_centers f ON f.id = t.fps_center_id "
            "WHERE t.source_import_id = :imp AND f.district IS NOT NULL "
            "ORDER BY f.district", {"imp": import_id})]
        fps = [r["fps_code"] for r in conn.execute(
            "SELECT DISTINCT f.fps_code FROM ration_transactions t "
            "JOIN fps_centers f ON f.id = t.fps_center_id "
            "WHERE t.source_import_id = :imp AND f.fps_code IS NOT NULL "
            "ORDER BY f.fps_code", {"imp": import_id})]
        inv_commodities = [r["commodity"] for r in conn.execute(
            "SELECT DISTINCT commodity FROM inventory "
            "WHERE source_import_id = :imp AND commodity IS NOT NULL "
            "ORDER BY commodity", {"imp": import_id})]
    finally:
        conn.close()
    for c in inv_commodities:
        if c not in commodities:
            commodities.append(c)
    return {"commodities": sorted(commodities), "districts": districts, "fps": fps}


# ---------------------------------------------------------------------------
# Current situation (real baseline, scoped to one import)
# ---------------------------------------------------------------------------

def current_situation(import_id: int, db_path: str = DEFAULT_DB_PATH) -> dict:
    """Real current metrics for one import — reused from the DB, not faked.

    Inventory coverage reuses the Phase 5 formula (stock x 30 / monthly
    consumption) and thresholds (CRITICAL < 15 days, WARNING < 30 days).
    """
    conn = open_db(db_path)
    try:
        inv = conn.execute(
            "SELECT COALESCE(SUM(current_stock), 0) AS stock, "
            " COALESCE(SUM(monthly_consumption), 0) AS monthly "
            "FROM inventory WHERE source_import_id = :imp",
            {"imp": import_id},
        ).fetchone()
        stock, monthly = inv["stock"], inv["monthly"]
        if monthly and monthly > 0:
            coverage_days = round(stock * DAYS_PER_MONTH / monthly, 1)
        else:
            coverage_days = None

        risk_items = conn.execute(
            "SELECT COALESCE(f.fps_code, 'Unknown') AS fps_code, "
            " f.district, i.commodity, i.current_stock, i.monthly_consumption, "
            " i.reorder_threshold "
            "FROM inventory i LEFT JOIN fps_centers f ON f.id = i.fps_center_id "
            "WHERE i.source_import_id = :imp ORDER BY i.current_stock",
            {"imp": import_id},
        ).fetchall()
        high_risk_fps = set()
        high_risk_districts = set()
        risk_levels = []
        for r in risk_items:
            days = None
            if r["monthly_consumption"] and r["monthly_consumption"] > 0:
                days = r["current_stock"] * DAYS_PER_MONTH / r["monthly_consumption"]
            below_threshold = (r["reorder_threshold"] is not None
                               and r["current_stock"] < r["reorder_threshold"])
            if days is not None and days < INVENTORY_CRITICAL_DAYS or below_threshold:
                high_risk_fps.add(r["fps_code"])
                if r["district"]:
                    high_risk_districts.add(r["district"])
                risk_levels.append({
                    "fps_code": r["fps_code"], "district": r["district"],
                    "commodity": r["commodity"], "current_stock": r["current_stock"],
                    "days_remaining": round(days, 1) if days is not None else None,
                    "reorder_threshold": r["reorder_threshold"],
                })

        tx = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(quantity), 0) AS qty, "
            " MIN(transaction_date) AS d0, MAX(transaction_date) AS d1 "
            "FROM ration_transactions WHERE source_import_id = :imp",
            {"imp": import_id},
        ).fetchone()
    finally:
        conn.close()

    daily = round(monthly / DAYS_PER_MONTH, 2) if monthly else 0.0
    return {
        "inventory_stock_kg": round(stock, 2),
        "monthly_consumption_kg": round(monthly, 2),
        "average_daily_consumption_kg": daily,
        "estimated_coverage_days": coverage_days,
        "high_risk_fps": sorted(high_risk_fps),
        "high_risk_districts": sorted(high_risk_districts),
        "risk_items": risk_levels,
        "transaction_count": tx["n"],
        "total_quantity_kg": round(tx["qty"], 2),
        "date_range": [tx["d0"], tx["d1"]] if tx["d0"] else None,
    }


# ---------------------------------------------------------------------------
# Scenario execution
# ---------------------------------------------------------------------------

class SimulationError(ValueError):
    """Invalid scenario parameters (mapped to HTTP 400)."""


def _scenario_type(demand_pct, delay_days, inventory_pct) -> str:
    active = []
    if demand_pct:
        active.append("DEMAND_CHANGE")
    if delay_days:
        active.append("SUPPLY_DELAY")
    if inventory_pct:
        active.append("INVENTORY_CHANGE")
    if not active:
        return "COMBINED"
    return "COMBINED" if len(active) > 1 else active[0]


def _insufficient(reason: str) -> dict:
    return {"status": "INSUFFICIENT_DATA", "reason": reason, "scenario_id": None}


def run_scenario(
    import_id: int,
    *,
    commodity: Optional[str] = None,
    district: Optional[str] = None,
    fps_code: Optional[str] = None,
    demand_change_pct: int = 0,
    supply_delay_days: int = 0,
    inventory_change_pct: int = 0,
    db_path: str = DEFAULT_DB_PATH,
    generator=None,
):
    """Run one deterministic what-if simulation on a real import.

    Returns the scenario result (with ``status: \"completed\"``) or a
    structured INSUFFICIENT_DATA result. Never writes to inventory,
    transactions, or beneficiaries — only the scenario row is persisted.
    ``generator`` is injected into the LLM call for tests.
    """
    demand_change_pct = int(demand_change_pct or 0)
    supply_delay_days = int(supply_delay_days or 0)
    inventory_change_pct = int(inventory_change_pct or 0)
    if not (DEMAND_CHANGE_MIN <= demand_change_pct <= DEMAND_CHANGE_MAX):
        raise SimulationError(
            "Demand change must be between %d%% and +%d%%, got %d%%."
            % (DEMAND_CHANGE_MIN, DEMAND_CHANGE_MAX, demand_change_pct))
    if not (SUPPLY_DELAY_MIN <= supply_delay_days <= SUPPLY_DELAY_MAX):
        raise SimulationError(
            "Supply delay must be between %d and %d days, got %d."
            % (SUPPLY_DELAY_MIN, SUPPLY_DELAY_MAX, supply_delay_days))
    if not (INVENTORY_CHANGE_MIN <= inventory_change_pct <= INVENTORY_CHANGE_MAX):
        raise SimulationError(
            "Inventory change must be between %d%% and +%d%%, got %d%%."
            % (INVENTORY_CHANGE_MIN, INVENTORY_CHANGE_MAX, inventory_change_pct))
    if not commodity:
        raise SimulationError("A commodity is required for the simulation.")

    imp = get_import_metadata(import_id, db_path)
    if imp is None:
        return _insufficient("The selected dataset import does not exist.")

    conn = open_db(db_path)
    try:
        # ---- baseline demand: average monthly quantity for the scope -------
        scope_where, scope_params = _scope_clause(
            "t", fps_code=fps_code, district=district, commodity=commodity)
        months = conn.execute(
            "SELECT substr(transaction_date, 1, 7) AS period, "
            " COALESCE(SUM(quantity), 0) AS qty "
            "FROM ration_transactions t "
            "LEFT JOIN fps_centers f ON f.id = t.fps_center_id "
            "WHERE t.source_import_id = :imp" + scope_where + " "
            "GROUP BY period ORDER BY period",
            dict(scope_params, imp=import_id),
        ).fetchall()
        if not months:
            return _insufficient(
                "No transactions found for %s%s%s in this dataset." % (
                    commodity or "",
                    " at FPS %s" % fps_code if fps_code else "",
                    " in %s" % district if district else ""))
        monthly_demand = sum(m["qty"] for m in months) / len(months)

        # ---- baseline stock / consumption / threshold ----------------------
        inv_where, inv_params = _scope_clause(
            "i", fps_code=fps_code, district=district, commodity=commodity)
        inv = conn.execute(
            "SELECT COALESCE(SUM(i.current_stock), 0) AS stock, "
            " COALESCE(SUM(i.monthly_consumption), 0) AS monthly, "
            " MIN(i.reorder_threshold) AS threshold "
            "FROM inventory i "
            "LEFT JOIN fps_centers f ON f.id = i.fps_center_id "
            "WHERE i.source_import_id = :imp" + inv_where,
            dict(inv_params, imp=import_id),
        ).fetchone()
        stock = inv["stock"]
        monthly_consumption = inv["monthly"]
        reorder_threshold = inv["threshold"]
    finally:
        conn.close()

    # ---- deterministic projections (all guarded) ---------------------------
    baseline_daily = (monthly_consumption / DAYS_PER_MONTH
                      if monthly_consumption and monthly_consumption > 0 else None)
    projected_demand = monthly_demand * (1 + demand_change_pct / 100.0)
    projected_daily = (baseline_daily * (1 + demand_change_pct / 100.0)
                       if baseline_daily is not None else None)
    stock_after_change = stock * (1 + inventory_change_pct / 100.0)

    coverage_current = (round(stock / baseline_daily, 1)
                        if baseline_daily and baseline_daily > 0 else None)
    coverage_projected = (round(stock_after_change / projected_daily, 1)
                          if projected_daily and projected_daily > 0 else None)

    consumption_rate_for_delay = projected_daily if projected_daily is not None else baseline_daily
    if consumption_rate_for_delay is None:
        consumption_during_delay = None
        stock_after_delay = None
    else:
        consumption_during_delay = consumption_rate_for_delay * supply_delay_days
        stock_after_delay = max(0.0, stock_after_change - consumption_during_delay)

    reorder_requirement = None
    if projected_demand is not None and stock_after_delay is not None:
        reorder_requirement = round(max(0.0, projected_demand - stock_after_delay), 2)

    # ---- risk classification (reuses the Phase 5 thresholds) ---------------
    def _classify_risk() -> str:
        if stock <= 0:
            return "CRITICAL"  # zero inventory cannot cover any demand
        if stock_after_delay is not None and stock_after_delay <= 0:
            return "CRITICAL"
        if reorder_threshold is not None and stock_after_delay is not None \
                and stock_after_delay < reorder_threshold:
            return "CRITICAL"
        if coverage_projected is None:
            return "UNKNOWN"
        if coverage_projected < INVENTORY_CRITICAL_DAYS:
            return "CRITICAL"
        if coverage_projected < INVENTORY_WARNING_DAYS:
            return "WARNING"
        return "HEALTHY"

    risk = _classify_risk()

    coverage_label = (
        "NOT CALCULABLE" if coverage_projected is None
        else "%.1f days" % coverage_projected)
    results = {
        "status": "completed",
        "baseline": {
            "monthly_demand_kg": round(monthly_demand, 2),
            "current_stock_kg": round(stock, 2),
            "monthly_consumption_kg": round(monthly_consumption, 2),
            "daily_consumption_kg": round(baseline_daily, 2) if baseline_daily is not None else None,
            "coverage_days": coverage_current,
            "reorder_threshold": reorder_threshold,
        },
        "scenario": {
            "demand_change_pct": demand_change_pct,
            "supply_delay_days": supply_delay_days,
            "inventory_change_pct": inventory_change_pct,
            "projected_monthly_demand_kg": round(projected_demand, 2),
            "projected_daily_consumption_kg": round(projected_daily, 2) if projected_daily is not None else None,
            "stock_after_inventory_change_kg": round(stock_after_change, 2),
            "consumption_during_delay_kg": round(consumption_during_delay, 2)
                if consumption_during_delay is not None else None,
            "projected_stock_after_delay_kg": round(stock_after_delay, 2)
                if stock_after_delay is not None else None,
            "projected_coverage_days": coverage_projected,
            "coverage_label": coverage_label,
            "simulated_reorder_requirement_kg": reorder_requirement,
        },
        "risk": risk,
    }

    # ---- deterministic explanation (always present; LLM may rephrase) ------
    why = _explain(commodity, district, fps_code, demand_change_pct,
                   supply_delay_days, inventory_change_pct, baseline_daily,
                   projected_daily, stock, stock_after_change,
                   stock_after_delay, coverage_projected, reorder_threshold, risk)
    context = {
        "commodity": commodity,
        "district": district or "all districts",
        "fps": fps_code or "all FPS centers",
        "baseline_monthly_demand_kg": round(monthly_demand, 2),
        "scenario_monthly_demand_kg": round(projected_demand, 2),
        "demand_change_pct": demand_change_pct,
        "supply_delay_days": supply_delay_days,
        "inventory_change_pct": inventory_change_pct,
        "current_stock_kg": round(stock, 2),
        "projected_stock_after_delay_kg": results["scenario"]["projected_stock_after_delay_kg"],
        "coverage_days_current": coverage_current,
        "coverage_days_projected": coverage_projected,
        "reorder_threshold": reorder_threshold,
        "risk": risk,
    }
    ai_text = maybe_generate("scenario_interpretation", context, why, generator=generator)

    # ---- persist ONLY the scenario metadata/result -------------------------
    scenario_type = _scenario_type(demand_change_pct, supply_delay_days, inventory_change_pct)
    conn = open_db(db_path)
    try:
        seq = conn.execute("SELECT COUNT(*) AS n FROM scenarios").fetchone()["n"] + 1
        scenario_id = "SIM-%04d-%04d" % (_now().year, seq)
        insert_scenario(
            conn,
            scenario_id=scenario_id,
            data_import_id=import_id,
            entity_type="fps_center" if fps_code else ("district" if district else "dataset"),
            entity_id=fps_code or district or "whole_dataset",
            commodity=commodity,
            scenario_type=scenario_type,
            parameters={
                "commodity": commodity, "district": district, "fps_code": fps_code,
                "demand_change_pct": demand_change_pct,
                "supply_delay_days": supply_delay_days,
                "inventory_change_pct": inventory_change_pct,
            },
            results=results,
            ai_interpretation={"summary": ai_text, "generated_by": "llm" if ai_text != why else "deterministic_fallback"},
            risk=risk,
        )
        conn.commit()
    finally:
        conn.close()

    results.update({
        "scenario_id": scenario_id,
        "commodity": commodity,
        "entity": {"type": "fps_center" if fps_code else ("district" if district else "dataset"),
                   "id": fps_code or district or "whole_dataset"},
        "interpretation": {"summary": ai_text,
                           "generated_by": "llm" if ai_text != why else "deterministic_fallback"},
        "lineage": {
            "dataset_name": imp.get("dataset_name"),
            "source_name": imp.get("source_name"),
            "data_import_id": import_id,
        },
    })
    logger.info(
        "[Simulation] %s %s %s demand=%d%% delay=%dd inv=%d%% -> risk=%s",
        scenario_id, commodity, fps_code or district or "all",
        demand_change_pct, supply_delay_days, inventory_change_pct, risk,
    )
    return results


def _explain(commodity, district, fps_code, demand_pct, delay_days, inventory_pct,
             baseline_daily, projected_daily, stock, stock_after_change,
             stock_after_delay, coverage_projected, reorder_threshold, risk) -> str:
    """Deterministic, evidence-based explanation (the LLM fallback)."""
    parts = []
    scope = "At %s" % (fps_code or district or "the whole dataset")
    parts.append("%s, a %d%% change in %s demand" % (
        scope, demand_pct, commodity))
    if baseline_daily is not None:
        parts.append("moves projected daily consumption from %.1f to %.1f kg/day"
                     % (baseline_daily, projected_daily))
    if delay_days:
        parts.append("and a %d-day supply delay consumes an additional "
                     "%.1f kg of stock" % (delay_days,
                                           (projected_daily or 0) * delay_days))
    if coverage_projected is not None:
        parts.append("projected inventory coverage is %.1f days" % coverage_projected)
    else:
        parts.append("projected coverage cannot be calculated")
    if reorder_threshold is not None and stock_after_delay is not None:
        parts.append("(reorder threshold %.1f kg)" % reorder_threshold)
    text = " ".join(parts) + ". This is a scenario result, not a prediction — "
    if risk == "CRITICAL":
        text += "the projected position is critical and requires immediate review."
    elif risk == "WARNING":
        text += "the projected position is a warning that warrants review."
    else:
        text += "the projected position remains healthy."
    return text


# ---------------------------------------------------------------------------
# History / detail (persisted scenarios only — real data is never changed)
# ---------------------------------------------------------------------------

def scenario_history(db_path: str = DEFAULT_DB_PATH, *, page: int = 1, per_page: int = 10) -> dict:
    conn = open_db(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) AS n FROM scenarios").fetchone()["n"]
        rows = conn.execute(
            "SELECT s.*, i.dataset_name, i.file_name, src.name AS source_name "
            "FROM scenarios s "
            "LEFT JOIN data_imports i ON i.id = s.data_import_id "
            "LEFT JOIN data_sources src ON src.id = i.data_source_id "
            "ORDER BY s.id DESC LIMIT :limit OFFSET :offset",
            {"limit": per_page, "offset": (page - 1) * per_page},
        ).fetchall()
    finally:
        conn.close()

    entries = []
    for row in rows:
        r = dict(row)
        entries.append({
            "id": r["id"],
            "scenario_id": r["scenario_id"],
            "data_import_id": r["data_import_id"],
            "dataset_name": r.get("dataset_name"),
            "source_name": r.get("source_name"),
            "entity_type": r.get("entity_type"),
            "entity_id": r.get("entity_id"),
            "commodity": r.get("commodity"),
            "scenario_type": r.get("scenario_type"),
            "risk": r.get("risk"),
            "created_at": r["created_at"],
        })
    return {"scenarios": entries, "total": total, "page": page, "per_page": per_page,
            "pages": max(1, -(-total // per_page))}


def scenario_detail(scenario_pk: int, db_path: str = DEFAULT_DB_PATH):
    import json as _json

    conn = open_db(db_path)
    try:
        row = get_scenario_by_id(conn, scenario_pk)
        if row is None:
            return None
        imp = conn.execute(
            "SELECT i.dataset_name, s.name AS source_name FROM data_imports i "
            "JOIN data_sources s ON s.id = i.data_source_id WHERE i.id = :imp",
            {"imp": row["data_import_id"]},
        ).fetchone()
    finally:
        conn.close()
    detail = dict(row)
    detail["dataset_name"] = imp["dataset_name"] if imp else None
    detail["source_name"] = imp["source_name"] if imp else None
    for key in ("parameters", "results", "ai_interpretation"):
        raw = detail.get(key)
        detail[key] = _json.loads(raw) if raw else None
    return detail
