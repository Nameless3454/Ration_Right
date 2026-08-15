"""RationAI — data context layer (Phase 6).

The step between the database and the existing multi-agent workflow:

    Database
        |  (SQL selection + aggregation, NOT raw table dumps)
        v
    Data context (relevant records + compact dataset summary)
        |
        v
    run_workflow(transactions)  -- the unchanged orchestrator + 4 agents

The existing agents keep their exact contracts. This service only decides
WHICH real dataset to analyze, exports its transactions in the documented
7-field agent shape, checks data sufficiency BEFORE any agent runs, and
attaches provenance (data_import_id, dataset name, record counts, data
quality) to the workflow result so every AI insight stays traceable to the
dataset that produced it.

No LLM calls live here. No fake data is ever produced: if a dataset has too
few records to analyze, the workflow returns a structured insufficient-data
result instead of asking agents to guess.
"""

from __future__ import annotations

import logging
from typing import Optional

from database import (
    DEFAULT_DB_PATH,
    as_agent_transaction,
    get_transactions_for_agent,
    open_db,
)
from workflow import run_workflow

logger = logging.getLogger("rationright.data_context")

#: Minimum number of transactions required before Agent 1 runs. A single
#: record cannot form a time/geographic pattern, so running the agents on
#: fewer than this would be meaningless. Documented, deterministic threshold.
MIN_TRANSACTIONS_FOR_AGENTS = 2

#: Structured description of what is missing when a dataset is insufficient.
REQUIRED_DATA_FOR_ANALYSIS = [
    "transaction records (external_transaction_id, beneficiary, fps, "
    "transaction_date, commodity, quantity, latitude, longitude)",
    "at least %d transaction records" % MIN_TRANSACTIONS_FOR_AGENTS,
]


def _dataset_block_for_import(imp: dict, transactions: list) -> dict:
    """Build the provenance/quality block attached to workflow results."""
    record_count = imp.get("record_count") or 0
    successful = imp.get("successful_records") or 0
    quality = None
    if record_count > 0:
        quality = round(successful / record_count, 4)
    timestamps = sorted(
        t["timestamp"] for t in transactions if t.get("timestamp")
    )
    commodities = sorted({t["ration_type"] for t in transactions if t.get("ration_type")})
    return {
        "mode": "real",
        "data_import_id": imp["id"],
        "dataset_name": imp.get("dataset_name"),
        "source_name": imp.get("source_name"),
        "source_type": imp.get("source_type"),
        "file_name": imp.get("file_name"),
        "file_type": imp.get("file_type"),
        "status": imp.get("status"),
        "record_count": record_count,
        "successful_records": successful,
        "data_quality": quality,
        "transaction_count": len(transactions),
        "total_quantity_kg": round(sum(t.get("quantity") or 0 for t in transactions), 3),
        "date_range": [timestamps[0], timestamps[-1]] if timestamps else None,
        "commodities": commodities,
    }


def list_agent_datasets(db_path: str = DEFAULT_DB_PATH) -> list:
    """List datasets that can be analyzed by the agents (real mode).

    Returns imports that actually contain transaction records, ordered by
    most recent first. The synthetic demo dataset is NOT included here — it
    is always available as ``dataset: "synthetic"`` in the API (and appears
    in the DB only as the seed used to power the demo dataset view).
    """
    conn = open_db(db_path)
    try:
        rows = conn.execute(
            "SELECT i.id, i.dataset_name, i.file_name, i.file_type, "
            "       i.record_count, i.successful_records, i.status, "
            "       i.completed_at, s.name AS source_name, s.type AS source_type, "
            "       (SELECT COUNT(*) FROM ration_transactions t "
            "         WHERE t.source_import_id = i.id) AS transaction_count "
            "FROM data_imports i "
            "JOIN data_sources s ON s.id = i.data_source_id "
            "WHERE i.status IN ('COMPLETED', 'PARTIAL') "
            "AND s.name != 'Synthetic Demo Dataset' "
            "AND (SELECT COUNT(*) FROM ration_transactions t "
            "     WHERE t.source_import_id = i.id) > 0 "
            "ORDER BY i.id DESC"
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def get_import_metadata(import_id: int, db_path: str = DEFAULT_DB_PATH):
    """Return data_import metadata joined with its data source, or None."""
    conn = open_db(db_path)
    try:
        row = conn.execute(
            "SELECT i.*, s.name AS source_name, s.type AS source_type "
            "FROM data_imports i "
            "JOIN data_sources s ON s.id = i.data_source_id "
            "WHERE i.id = :imp",
            {"imp": import_id},
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def get_filtered_transactions_for_agent(
    conn,
    import_id: int,
    *,
    commodity: Optional[str] = None,
    fps_code: Optional[str] = None,
    district: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> list:
    """Export one import's transactions in the agent contract shape, filtered
    with validated, parameterized constraints (Phase 9 command center).

    Filters are whitelisted fields joined server-side (FPS/district come from
    the fps_centers table); the agents always receive a compact selection,
    never a raw table dump.
    """
    where = ["t.source_import_id = :imp"]
    params = {"imp": import_id}
    if commodity:
        where.append("LOWER(t.commodity) = LOWER(:commodity)")
        params["commodity"] = commodity.strip()
    if fps_code:
        where.append("f.fps_code = :fps")
        params["fps"] = fps_code.strip()
    if district:
        where.append("LOWER(f.district) = LOWER(:district)")
        params["district"] = district.strip()
    if from_date:
        where.append("t.transaction_date >= :from_date")
        params["from_date"] = from_date.strip()
    if to_date:
        where.append("t.transaction_date <= :to_date")
        params["to_date"] = to_date.strip()
    rows = conn.execute(
        "SELECT t.*, b.external_reference AS beneficiary_external_reference "
        "FROM ration_transactions t "
        "LEFT JOIN beneficiaries b ON b.id = t.beneficiary_id "
        "LEFT JOIN fps_centers f ON f.id = t.fps_center_id "
        "WHERE " + " AND ".join(where) + " ORDER BY t.id",
        params,
    ).fetchall()
    return [as_agent_transaction(dict(row)) for row in rows]


def prepare_agent_context(
    import_id: int,
    db_path: str = DEFAULT_DB_PATH,
    filters: Optional[dict] = None,
) -> Optional[dict]:
    """Select one real dataset and export its transactions for the agents.

    Returns None if the import does not exist. Otherwise a context dict:

        {
          "dataset": {...provenance + quality + sufficiency...},
          "transactions": [...7-field agent contract rows...],
          "sufficient": bool,
          "reason": str | None,       # when insufficient
          "required_data": [...]      # when insufficient
        }

    Sufficiency is checked here, BEFORE any agent runs. An insufficient
    dataset never reaches the agents. ``filters`` is an optional validated
    dict (commodity/fps_code/district/from_date/to_date) applied to the
    transaction selection (Phase 9).
    """
    filters = filters or {}
    imp = get_import_metadata(import_id, db_path)
    if imp is None:
        return None
    conn = open_db(db_path)
    try:
        if any(filters.get(k) for k in ("commodity", "fps_code", "district", "from_date", "to_date")):
            transactions = get_filtered_transactions_for_agent(conn, import_id, **{
                k: filters[k] for k in ("commodity", "fps_code", "district", "from_date", "to_date")
                if filters.get(k)
            })
        else:
            transactions = get_transactions_for_agent(conn, import_id=import_id)
    finally:
        conn.close()

    block = _dataset_block_for_import(imp, transactions)
    if len(transactions) < MIN_TRANSACTIONS_FOR_AGENTS:
        block["sufficient"] = False
        block["reason"] = (
            "Dataset has %d transaction record(s); at least %d are required "
            "to evaluate time/geographic patterns."
            % (len(transactions), MIN_TRANSACTIONS_FOR_AGENTS)
        )
        block["required_data"] = list(REQUIRED_DATA_FOR_ANALYSIS)
        return {"dataset": block, "transactions": [], "sufficient": False}

    block["sufficient"] = True
    return {"dataset": block, "transactions": transactions, "sufficient": True}


def synthetic_dataset_block(transactions: list) -> dict:
    """Provenance block for the built-in synthetic demo dataset."""
    timestamps = sorted(t.get("timestamp") for t in transactions if t.get("timestamp"))
    commodities = sorted({t.get("ration_type") for t in transactions if t.get("ration_type")})
    return {
        "mode": "synthetic",
        "dataset_name": "Synthetic Demo Dataset",
        "source_name": "Synthetic Demo Dataset",
        "source_type": "JSON",
        "transaction_count": len(transactions),
        "total_quantity_kg": round(sum(t.get("quantity") or 0 for t in transactions), 3),
        "date_range": [timestamps[0], timestamps[-1]] if timestamps else None,
        "commodities": commodities,
        "data_quality": None,
        "sufficient": len(transactions) >= MIN_TRANSACTIONS_FOR_AGENTS,
    }


def run_workflow_on_dataset(
    import_id: int,
    *,
    db_path: str = DEFAULT_DB_PATH,
    max_interval_minutes: Optional[int] = None,
    min_distance_km: Optional[float] = None,
    filters: Optional[dict] = None,
) -> Optional[dict]:
    """Run the real multi-agent workflow on one imported dataset.

    Returns None if the import does not exist. The workflow result carries a
    ``dataset`` provenance block; insufficient datasets produce a structured
    result without invoking any agent. ``filters`` optionally restricts the
    transaction selection (commodity/fps_code/district/from_date/to_date).
    """
    context = prepare_agent_context(import_id, db_path, filters=filters)
    if context is None:
        return None

    if not context["sufficient"]:
        return {
            "workflow_status": "completed",
            "dataset": context["dataset"],
            "stages": {
                "agent_1": "skipped",
                "agent_2": "skipped",
                "agent_3": "skipped",
                "agent_4": "skipped",
            },
            "anomalies": [],
            "unverified_findings": [],
            "findings": [],
            "cases": [],
            "alerts": [],
            "errors": [],
            "skipped_reason": context["dataset"].get("reason"),
        }

    kwargs = {}
    if max_interval_minutes is not None:
        kwargs["max_interval_minutes"] = max_interval_minutes
    if min_distance_km is not None:
        kwargs["min_distance_km"] = min_distance_km
    result = run_workflow(context["transactions"], **kwargs)
    result["dataset"] = context["dataset"]
    if filters:
        result["dataset"]["filters_applied"] = {
            k: v for k, v in filters.items() if v
        }
    logger.info(
        "[RationRight] Real-data analysis: import #%d (%s) — %d transaction(s)%s",
        import_id,
        context["dataset"].get("dataset_name"),
        len(context["transactions"]),
        (" with filters %r" % filters) if filters else "",
    )
    return result
