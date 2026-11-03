"""
Comparison engine for evaluating changes across historical weekly snapshots.
Compares inventory, beneficiaries, transactions, and audit records.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
import sqlite3

from src.config import settings
from src.db.database import get_db_connection
from src.query_engine.safe_queries import (
    get_audit_summary,
    get_beneficiaries_summary,
    get_import_summary,
    get_inventory_status,
)


def compare_snapshots(
    import_id_a: str,
    import_id_b: str,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Compare two weekly import snapshots:
    import_id_a: Baseline snapshot (e.g. Previous Week)
    import_id_b: Target snapshot (e.g. Current Week)
    """
    summary_a = get_import_summary(import_id_a, db_path)
    summary_b = get_import_summary(import_id_b, db_path)

    if not summary_a:
        raise ValueError(f"Baseline import snapshot not found: {import_id_a}")
    if not summary_b:
        raise ValueError(f"Target import snapshot not found: {import_id_b}")

    # 1. Batch metadata comparison
    metadata_diff = {
        "baseline_import": {
            "import_id": import_id_a,
            "dataset_name": summary_a["dataset_name"],
            "timestamp": summary_a["import_timestamp"],
            "total_records": summary_a["total_records"],
        },
        "target_import": {
            "import_id": import_id_b,
            "dataset_name": summary_b["dataset_name"],
            "timestamp": summary_b["import_timestamp"],
            "total_records": summary_b["total_records"],
        },
        "total_records_delta": summary_b["total_records"] - summary_a["total_records"],
    }

    # 2. Beneficiary comparison
    ben_sum_a = get_beneficiaries_summary(import_id_a, db_path)
    ben_sum_b = get_beneficiaries_summary(import_id_b, db_path)

    ben_aggregate_diff = {
        "total_beneficiaries_delta": (ben_sum_b.get("total_beneficiaries") or 0) - (ben_sum_a.get("total_beneficiaries") or 0),
        "phh_delta": (ben_sum_b.get("phh_count") or 0) - (ben_sum_a.get("phh_count") or 0),
        "aay_delta": (ben_sum_b.get("aay_count") or 0) - (ben_sum_a.get("aay_count") or 0),
        "duplicate_flags_delta": (ben_sum_b.get("duplicate_flag_count") or 0) - (ben_sum_a.get("duplicate_flag_count") or 0),
        "multiple_claims_delta": (ben_sum_b.get("multiple_claims_count") or 0) - (ben_sum_a.get("multiple_claims_count") or 0),
    }

    # Record-level beneficiary changes
    beneficiary_changes = _compare_beneficiary_records(import_id_a, import_id_b, db_path)

    # 3. Inventory comparison
    inventory_changes = _compare_inventory_records(import_id_a, import_id_b, db_path)

    # 4. Audit compliance comparison
    audit_sum_a = get_audit_summary(import_id_a, db_path)
    audit_sum_b = get_audit_summary(import_id_b, db_path)

    audit_diff = {
        "complaints_delta": (audit_sum_b.get("total_complaints") or 0) - (audit_sum_a.get("total_complaints") or 0),
        "manual_overrides_delta": (audit_sum_b.get("total_manual_overrides") or 0) - (audit_sum_a.get("total_manual_overrides") or 0),
        "late_opening_days_delta": (audit_sum_b.get("total_late_days") or 0) - (audit_sum_a.get("total_late_days") or 0),
        "failed_inspections_delta": (audit_sum_b.get("failed_inspections") or 0) - (audit_sum_a.get("failed_inspections") or 0),
    }

    return {
        "metadata_comparison": metadata_diff,
        "beneficiaries_summary_delta": ben_aggregate_diff,
        "beneficiary_changes": beneficiary_changes,
        "inventory_changes": inventory_changes,
        "audit_compliance_delta": audit_diff,
    }


def _compare_beneficiary_records(
    import_id_a: str,
    import_id_b: str,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Identify newly added, removed, and status-altered beneficiary records."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT beneficiary_id, ration_card_id, head_name, category, identity_status, collection_status, monthly_entitlement_kg
            FROM beneficiaries WHERE import_id = ?
            """,
            (import_id_a,),
        )
        records_a = {row["beneficiary_id"]: dict(row) for row in cursor.fetchall()}

        cursor.execute(
            """
            SELECT beneficiary_id, ration_card_id, head_name, category, identity_status, collection_status, monthly_entitlement_kg
            FROM beneficiaries WHERE import_id = ?
            """,
            (import_id_b,),
        )
        records_b = {row["beneficiary_id"]: dict(row) for row in cursor.fetchall()}

    added = [records_b[b_id] for b_id in records_b if b_id not in records_a]
    removed = [records_a[b_id] for b_id in records_a if b_id not in records_b]
    
    status_altered = []
    for b_id in records_b:
        if b_id in records_a:
            rec_a = records_a[b_id]
            rec_b = records_b[b_id]
            if (
                rec_a["identity_status"] != rec_b["identity_status"]
                or rec_a["collection_status"] != rec_b["collection_status"]
                or rec_a["monthly_entitlement_kg"] != rec_b["monthly_entitlement_kg"]
            ):
                status_altered.append({
                    "beneficiary_id": b_id,
                    "head_name": rec_b["head_name"],
                    "before": {
                        "identity_status": rec_a["identity_status"],
                        "collection_status": rec_a["collection_status"],
                        "monthly_entitlement_kg": rec_a["monthly_entitlement_kg"],
                    },
                    "after": {
                        "identity_status": rec_b["identity_status"],
                        "collection_status": rec_b["collection_status"],
                        "monthly_entitlement_kg": rec_b["monthly_entitlement_kg"],
                    },
                })

    return {
        "newly_added_count": len(added),
        "removed_count": len(removed),
        "status_altered_count": len(status_altered),
        "newly_added": added,
        "removed": removed,
        "status_altered": status_altered,
    }


def _compare_inventory_records(
    import_id_a: str,
    import_id_b: str,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Compare inventory stock levels by shop and commodity between two weeks."""
    inv_a = get_inventory_status(import_id_a, db_path=db_path)
    inv_b = get_inventory_status(import_id_b, db_path=db_path)

    map_a = {(i["pwd_id"], i["commodity"]): i for i in inv_a}
    map_b = {(i["pwd_id"], i["commodity"]): i for i in inv_b}

    all_keys = sorted(list(set(map_a.keys()) | set(map_b.keys())))
    item_changes = []
    total_physical_delta = 0

    for key in all_keys:
        pwd_id, commodity = key
        item_a = map_a.get(key)
        item_b = map_b.get(key)

        phys_a = item_a["physical_stock_kg"] if item_a else 0
        phys_b = item_b["physical_stock_kg"] if item_b else 0
        dist_a = item_a["distributed_kg"] if item_a else 0
        dist_b = item_b["distributed_kg"] if item_b else 0
        shop_name = (item_b or item_a)["shop_name"]

        phys_delta = phys_b - phys_a
        dist_delta = dist_b - dist_a
        total_physical_delta += phys_delta

        if phys_delta != 0 or dist_delta != 0:
            item_changes.append({
                "pwd_id": pwd_id,
                "shop_name": shop_name,
                "commodity": commodity,
                "baseline_physical_kg": phys_a,
                "target_physical_kg": phys_b,
                "physical_stock_delta_kg": phys_delta,
                "baseline_distributed_kg": dist_a,
                "target_distributed_kg": dist_b,
                "distributed_delta_kg": dist_delta,
            })

    return {
        "changed_inventory_items_count": len(item_changes),
        "total_physical_stock_delta_kg": total_physical_delta,
        "item_changes": item_changes,
    }

