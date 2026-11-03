"""
Safe, parameterized, read-only SQL query functions for RationRight datasets.
LLM or API requests only execute these validated, predefined operations.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import sqlite3

from src.config import settings
from src.db.database import get_db_connection


def get_latest_import_id(db_path: Optional[Path] = None) -> Optional[str]:
    """Retrieve the import_id of the most recent successful dataset import."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT import_id 
            FROM import_batches 
            WHERE status = 'SUCCESS' 
            ORDER BY import_timestamp DESC 
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        return row["import_id"] if row else None


def get_import_summary(import_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Retrieve metadata and per-table record counts for a specific import."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT import_id, import_timestamp, dataset_name, total_records, status, source_type, source_path, details
            FROM import_batches
            WHERE import_id = ?
            """,
            (import_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_beneficiaries_summary(import_id: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Get aggregate beneficiary counts, categories, and review flag breakdowns."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                COUNT(*) as total_beneficiaries,
                SUM(CASE WHEN category = 'PHH' THEN 1 ELSE 0 END) as phh_count,
                SUM(CASE WHEN category = 'AAY' THEN 1 ELSE 0 END) as aay_count,
                SUM(CASE WHEN identity_status = 'verified' THEN 1 ELSE 0 END) as verified_count,
                SUM(CASE WHEN identity_status = 'possible_duplicate' THEN 1 ELSE 0 END) as duplicate_flag_count,
                SUM(CASE WHEN identity_status = 'review_required' THEN 1 ELSE 0 END) as review_required_count,
                SUM(CASE WHEN collection_status = 'multiple_claims' THEN 1 ELSE 0 END) as multiple_claims_count
            FROM beneficiaries
            WHERE import_id = ?
            """,
            (import_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else {}


def get_beneficiary_by_id(
    import_id: str,
    beneficiary_id: str,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve a single beneficiary record by its beneficiary_id."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT b.beneficiary_id, b.ration_card_id, b.head_name, b.category, b.family_size,
                   b.pwd_id, s.shop_name, b.monthly_entitlement_kg, b.last_collection_date,
                   b.collection_status, b.identity_status, b.review_reason
            FROM beneficiaries b
            LEFT JOIN pwd_shops s ON b.pwd_id = s.pwd_id AND b.import_id = s.import_id
            WHERE b.import_id = ? AND UPPER(b.beneficiary_id) = UPPER(?)
            """,
            (import_id, beneficiary_id),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_shop_or_dealer_by_id(
    import_id: str,
    entity_id: str,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve a Fair Price Shop or Dealer profile by pwd_id or dealer_id."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT s.pwd_id, s.shop_name, s.dealer_id, s.district, s.state, s.monthly_capacity_kg,
                   a.complaints_count, a.late_opening_days, a.manual_override_count, a.inspection_status
            FROM pwd_shops s
            LEFT JOIN pwd_audits a ON s.pwd_id = a.pwd_id AND s.import_id = a.import_id
            WHERE s.import_id = ? AND (
                UPPER(s.pwd_id) = UPPER(?) OR UPPER(s.dealer_id) = UPPER(?)
            )
            """,
            (import_id, entity_id, entity_id),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_flagged_beneficiaries(
    import_id: str,
    flag_type: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve individual beneficiary records marked with review flags.
    flag_type can be 'possible_duplicate', 'multiple_claims', or None (returns all flagged).
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        if flag_type == "possible_duplicate":
            cursor.execute(
                """
                SELECT b.beneficiary_id, b.ration_card_id, b.head_name, b.category, b.family_size,
                       b.pwd_id, s.shop_name, b.identity_status, b.collection_status, b.review_reason
                FROM beneficiaries b
                LEFT JOIN pwd_shops s ON b.pwd_id = s.pwd_id AND b.import_id = s.import_id
                WHERE b.import_id = ? AND b.identity_status = 'possible_duplicate'
                ORDER BY b.beneficiary_id
                """,
                (import_id,),
            )
        elif flag_type == "multiple_claims":
            cursor.execute(
                """
                SELECT b.beneficiary_id, b.ration_card_id, b.head_name, b.category, b.family_size,
                       b.pwd_id, s.shop_name, b.identity_status, b.collection_status, b.review_reason
                FROM beneficiaries b
                LEFT JOIN pwd_shops s ON b.pwd_id = s.pwd_id AND b.import_id = s.import_id
                WHERE b.import_id = ? AND b.collection_status = 'multiple_claims'
                ORDER BY b.beneficiary_id
                """,
                (import_id,),
            )
        else:
            cursor.execute(
                """
                SELECT b.beneficiary_id, b.ration_card_id, b.head_name, b.category, b.family_size,
                       b.pwd_id, s.shop_name, b.identity_status, b.collection_status, b.review_reason
                FROM beneficiaries b
                LEFT JOIN pwd_shops s ON b.pwd_id = s.pwd_id AND b.import_id = s.import_id
                WHERE b.import_id = ? AND (
                    b.identity_status IN ('possible_duplicate', 'review_required')
                    OR b.collection_status = 'multiple_claims'
                )
                ORDER BY b.beneficiary_id
                """,
                (import_id,),
            )
        return [dict(r) for r in cursor.fetchall()]


def get_inventory_status(
    import_id: str,
    pwd_id: Optional[str] = None,
    commodity: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve inventory stock status, with optional pagination (limit/offset).
    Includes computed expected closing stock and physical stock discrepancy.
    """
    query = """
        SELECT 
            i.inventory_id, i.pwd_id, s.shop_name, i.month, i.commodity,
            i.opening_stock_kg, i.received_kg, i.distributed_kg,
            i.closing_stock_kg, i.physical_stock_kg, i.unit,
            (i.opening_stock_kg + i.received_kg - i.distributed_kg) as expected_closing_kg,
            (i.physical_stock_kg - (i.opening_stock_kg + i.received_kg - i.distributed_kg)) as physical_discrepancy_kg
        FROM inventory i
        LEFT JOIN pwd_shops s ON i.pwd_id = s.pwd_id AND i.import_id = s.import_id
        WHERE i.import_id = ?
    """
    params: List[Any] = [import_id]
    if pwd_id:
        query += " AND i.pwd_id = ?"
        params.append(pwd_id)
    if commodity:
        query += " AND LOWER(i.commodity) = LOWER(?)"
        params.append(commodity)
    query += " ORDER BY i.pwd_id, i.commodity"

    if limit is not None:
        validated_limit = max(1, min(int(limit), 200))
        validated_offset = max(0, int(offset or 0))
        query += " LIMIT ? OFFSET ?"
        params.extend([validated_limit, validated_offset])

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def get_inventory_count(
    import_id: str,
    pwd_id: Optional[str] = None,
    commodity: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Return total count of matching inventory rows for pagination metadata."""
    query = "SELECT COUNT(*) as cnt FROM inventory WHERE import_id = ?"
    params: List[Any] = [import_id]
    if pwd_id:
        query += " AND pwd_id = ?"
        params.append(pwd_id)
    if commodity:
        query += " AND LOWER(commodity) = LOWER(?)"
        params.append(commodity)

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        return row["cnt"] if row else 0


def get_shop_complaints_ranking(
    import_id: str,
    limit: int = 10,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Retrieve shops ranked by citizen complaints and audit violations."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                a.audit_id, a.pwd_id, s.shop_name, s.district, s.state,
                a.complaints_count, a.late_opening_days, a.manual_override_count,
                a.inspection_status
            FROM pwd_audits a
            LEFT JOIN pwd_shops s ON a.pwd_id = s.pwd_id AND a.import_id = s.import_id
            WHERE a.import_id = ?
            ORDER BY a.complaints_count DESC, a.manual_override_count DESC
            LIMIT ?
            """,
            (import_id, limit),
        )
        return [dict(r) for r in cursor.fetchall()]


def get_audit_summary(import_id: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Retrieve aggregate compliance and inspection metrics across all shops in an import."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                COUNT(*) as total_audits,
                SUM(complaints_count) as total_complaints,
                SUM(manual_override_count) as total_manual_overrides,
                SUM(late_opening_days) as total_late_days,
                SUM(CASE WHEN inspection_status = 'passed' THEN 1 ELSE 0 END) as passed_inspections,
                SUM(CASE WHEN inspection_status = 'pending' THEN 1 ELSE 0 END) as pending_inspections,
                SUM(CASE WHEN inspection_status = 'failed' THEN 1 ELSE 0 END) as failed_inspections
            FROM pwd_audits
            WHERE import_id = ?
            """,
            (import_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else {}


def get_transactions_summary(
    import_id: str,
    channel: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Retrieve transaction volume, channel breakdown, and distributed grain totals."""
    query = """
        SELECT 
            COUNT(*) as total_transactions,
            SUM(quantity_kg) as total_grain_distributed_kg,
            SUM(CASE WHEN channel = 'biometric' THEN 1 ELSE 0 END) as biometric_count,
            SUM(CASE WHEN channel = 'manual_override' THEN 1 ELSE 0 END) as manual_override_count,
            SUM(CASE WHEN commodity = 'Rice' THEN quantity_kg ELSE 0 END) as rice_distributed_kg,
            SUM(CASE WHEN commodity = 'Wheat' THEN quantity_kg ELSE 0 END) as wheat_distributed_kg
        FROM transactions
        WHERE import_id = ?
    """
    params: List[Any] = [import_id]
    if channel:
        query += " AND channel = ?"
        params.append(channel)

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else {}
