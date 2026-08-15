"""RationRight — database import (Phase 3 + Phase 4).

Turns validated, normalized records into database rows with full provenance:
every inserted row points at the DataImport that produced it, which points at
its DataSource and records the SHA-256 hash of the uploaded file.

Duplicate strategy (never blindly deleted; classified and counted):
- EXACT_DUPLICATE: the same external transaction id (or, for datasets without
  an ID column, the identical composite content) recurs — in this file or
  already in the database;
- POSSIBLE_DUPLICATE: a different external id shares the same composite
  content (fps, date, commodity, quantity) — the same transaction recorded
  twice under two ids;
- UNIQUE: everything else, which is imported.

Records stream through ``executemany`` batches (default 500) inside one
transaction so large datasets do not build unbounded Python-side state.
"""

from __future__ import annotations

import logging
import time

from database import (
    DEFAULT_TRANSACTION_UNIT,
    beneficiary_ids,
    existing_beneficiary_refs,
    existing_fps_codes,
    existing_transaction_ids,
    fps_center_ids,
    get_data_import,
    get_data_source_by_name,
    insert_data_import,
    insert_data_source,
    insert_inventory_batch,
    insert_transactions_batch,
    upsert_beneficiaries,
    upsert_fps_centers,
)
from ingestion import validation
from ingestion.validation import quality_report

logger = logging.getLogger("rationright.ingestion")

UPLOADED_SOURCE_NAME = "Uploaded Dataset"
BATCH_SIZE = 500
MAX_ERROR_SUMMARY_CHARS = 800
MAX_ERROR_EXAMPLES = 5


def _now_iso():
    from database import _now_iso as _now
    return _now()


def _composite_key(normalized: dict):
    return (
        (normalized.get("fps_center_id") or "").strip().lower(),
        (normalized.get("transaction_date") or "").strip(),
        (normalized.get("commodity") or "").strip().lower(),
        normalized.get("quantity"),
    )


def _natural_key(dataset_type: str, normalized: dict):
    if dataset_type in ("beneficiaries", "fps_centers"):
        return (normalized.get("external_reference") or normalized.get("fps_code") or "").strip().lower()
    if dataset_type == "inventory":
        return (
            (normalized.get("fps_center_id") or "").strip().lower(),
            (normalized.get("commodity") or "").strip().lower(),
        )
    return _composite_key(normalized)


def run_import(
    conn,
    *,
    file_name: str,
    file_type: str,
    dataset_name: str,
    source_name: str,
    dataset_type: str,
    headers: list,
    rows: list,
    mapping: dict,
    file_hash: str = None,
):
    """Import validated, normalized records into the database.

    ``mapping`` maps external header -> internal field (from the user's
    confirmed mapping). Returns the import summary, including duplicate
    classification counts, a deterministic quality score, and provenance.
    """
    started = time.perf_counter()
    source = get_data_source_by_name(conn, source_name)
    if source is None:
        source_id = insert_data_source(
            conn, name=source_name, source_type="MANUAL",
            description="Datasets uploaded by the user", status="ACTIVE",
        )
    else:
        source_id = source["id"]

    import_id = insert_data_import(
        conn, data_source_id=source_id, dataset_name=dataset_name,
        file_name=file_name, file_type=file_type, file_hash=file_hash,
        record_count=len(rows), status="PROCESSING", started_at=_now_iso(),
    )

    # Exact keys pre-seeded from the database (transactions with external ids
    # already present are EXACT duplicates of the existing records).
    seen_exact = {("ext", i) for i in existing_transaction_ids(conn)}
    seen_composite = set()
    beneficiary_map = beneficiary_ids(conn, existing_beneficiary_refs(conn))
    center_map = fps_center_ids(conn, existing_fps_codes(conn))

    pending_beneficiaries = []
    pending_centers = []
    pending_transactions = []
    pending_inventory = []
    counters = {
        "imported": 0, "failed": 0, "duplicates": 0,
        "duplicates_exact": 0, "duplicates_possible": 0, "warnings": 0,
    }
    error_examples = []
    tx_seq = 0

    def flush():
        if pending_beneficiaries:
            upsert_beneficiaries(conn, pending_beneficiaries)
            beneficiary_map.update(
                beneficiary_ids(
                    conn, [r["external_reference"] for r in pending_beneficiaries]
                )
            )
            pending_beneficiaries.clear()
        if pending_centers:
            upsert_fps_centers(conn, pending_centers)
            center_map.update(
                fps_center_ids(conn, [r["fps_code"] for r in pending_centers])
            )
            pending_centers.clear()
        if pending_transactions:
            resolved = []
            for transaction in pending_transactions:
                row = dict(transaction)
                ref = row.pop("_beneficiary_ref", None)
                if ref:
                    row["beneficiary_id"] = beneficiary_map.get(ref)
                code = row.pop("_fps_code", None)
                if code:
                    row["fps_center_id"] = center_map.get(code)
                resolved.append(row)
            insert_transactions_batch(conn, resolved)
            pending_transactions.clear()
        if pending_inventory:
            resolved = []
            for item in pending_inventory:
                row = dict(item)
                code = row.pop("_fps_code", None)
                if code:
                    row["fps_center_id"] = center_map.get(code)
                resolved.append(row)
            insert_inventory_batch(conn, resolved)
            pending_inventory.clear()

    for row_number, row in enumerate(rows, start=2):
        record = _record_from_row(row, headers, mapping)
        normalized, errors, warnings = validation.validate_record(record, dataset_type)
        counters["warnings"] += len(warnings)
        if errors:
            counters["failed"] += 1
            if len(error_examples) < MAX_ERROR_EXAMPLES:
                error_examples.append({
                    "row": row_number,
                    "errors": errors[:3],
                    "values": {k: v for k, v in record.items() if v not in (None, "")},
                })
            continue

        # --- duplicate classification (Phase 4) ---
        if dataset_type in ("ration_transactions", "combined"):
            external_id = (normalized.get("external_transaction_id") or "").strip()
            composite = _composite_key(normalized)
            if external_id:
                exact_key = ("ext", external_id)
                if exact_key in seen_exact:
                    counters["duplicates"] += 1
                    counters["duplicates_exact"] += 1
                    continue
                if composite in seen_composite:
                    counters["duplicates"] += 1
                    counters["duplicates_possible"] += 1
                    continue
                seen_exact.add(exact_key)
                seen_composite.add(composite)
            else:
                if composite in seen_composite:
                    counters["duplicates"] += 1
                    counters["duplicates_exact"] += 1
                    continue
                seen_composite.add(composite)
        else:
            key = _natural_key(dataset_type, normalized)
            if key in seen_exact:
                counters["duplicates"] += 1
                counters["duplicates_exact"] += 1
                continue
            seen_exact.add(key)

        # Transactions without an ID column get a deterministic generated id
        # AFTER classification so the composite key still governs uniqueness.
        if dataset_type in ("ration_transactions", "combined"):
            if not (normalized.get("external_transaction_id") or "").strip():
                tx_seq += 1
                normalized["external_transaction_id"] = "IMP%04d-%06d" % (import_id, tx_seq)

        _stage_record(
            dataset_type, normalized, import_id,
            pending_beneficiaries, pending_centers,
            pending_transactions, pending_inventory,
        )
        counters["imported"] += 1
        if len(pending_transactions) + len(pending_inventory) + len(pending_beneficiaries) + len(pending_centers) >= BATCH_SIZE:
            flush()

    flush()
    # Phase 14: no mid-import commit. Everything (import row, upserts, batches)
    # lands in ONE transaction so a critical failure rolls back cleanly instead
    # of leaving a half-imported dataset behind.

    elapsed = time.perf_counter() - started
    status = "COMPLETED"
    if counters["imported"] == 0:
        status = "FAILED"
    elif counters["failed"] > 0:
        status = "PARTIAL"

    error_summary = _build_error_summary(error_examples)
    quality = quality_report(
        total=len(rows),
        invalid=counters["failed"],
        duplicates=counters["duplicates"],
        warnings=counters["warnings"],
    )
    completed_at = _now_iso()
    conn.execute(
        "UPDATE data_imports SET status = :status, successful_records = :ok, "
        "failed_records = :failed, duplicate_records = :dupes, "
        "warnings_count = :warnings, error_summary = :summary, "
        "completed_at = :completed_at "
        "WHERE id = :import_id",
        {
            "status": status,
            "ok": counters["imported"],
            "failed": counters["failed"],
            "dupes": counters["duplicates"],
            "warnings": counters["warnings"],
            "summary": error_summary,
            "completed_at": completed_at,
            "import_id": import_id,
        },
    )
    conn.commit()

    summary = {
        "status": status,
        "data_import_id": import_id,
        "data_source_id": source_id,
        "dataset_name": dataset_name,
        "source_name": source_name,
        "file_name": file_name,
        "file_type": file_type,
        "file_hash": file_hash,
        "dataset_type": dataset_type,
        "record_count": len(rows),
        "imported": counters["imported"],
        "failed": counters["failed"],
        "duplicates": counters["duplicates"],
        "duplicates_exact": counters["duplicates_exact"],
        "duplicates_possible": counters["duplicates_possible"],
        "warnings": counters["warnings"],
        "quality": quality,
        "error_summary": error_summary,
        "error_examples": error_examples,
        "processing_time_seconds": round(elapsed, 3),
        "started_at": get_data_import(conn, import_id)["started_at"],
        "completed_at": completed_at,
    }
    logger.info(
        "[Ingestion] Import %s %s: %d imported, %d failed, %d duplicates "
        "(exact=%d possible=%d), %d warnings, quality=%s%% (%.3fs)",
        import_id, status, counters["imported"], counters["failed"],
        counters["duplicates"], counters["duplicates_exact"],
        counters["duplicates_possible"], counters["warnings"],
        quality["score"], elapsed,
    )
    return summary


def _stage_record(
    dataset_type, normalized, import_id,
    pending_beneficiaries, pending_centers, pending_transactions, pending_inventory,
):
    """Append a normalized record to the appropriate pending batch list."""
    if dataset_type == "beneficiaries":
        pending_beneficiaries.append({
            "external_reference": normalized.get("external_reference", ""),
            "state": normalized.get("state"),
            "district": normalized.get("district"),
            "block": normalized.get("block"),
            "ration_category": normalized.get("ration_category"),
            "family_size": normalized.get("family_size"),
            "status": normalized.get("status", "ACTIVE"),
        })
        return

    if dataset_type == "fps_centers":
        pending_centers.append({
            "fps_code": normalized.get("fps_code", ""),
            "name": normalized.get("name"),
            "state": normalized.get("state"),
            "district": normalized.get("district"),
            "block": normalized.get("block"),
            "location": normalized.get("location"),
            "latitude": normalized.get("latitude"),
            "longitude": normalized.get("longitude"),
            "capacity": normalized.get("capacity"),
            "status": normalized.get("status", "ACTIVE"),
        })
        return

    if dataset_type == "inventory":
        # ``fps_center_id`` on the file is an external FPS code; ensure the
        # center exists and resolve the code to its internal id at flush time.
        if normalized.get("fps_center_id"):
            pending_centers.append({
                "fps_code": normalized["fps_center_id"],
                "status": "ACTIVE",
            })
        pending_inventory.append({
            "fps_center_id": None,
            "_fps_code": normalized.get("fps_center_id"),
            "commodity": normalized.get("commodity", ""),
            "current_stock": normalized.get("current_stock", 0.0),
            "monthly_consumption": normalized.get("monthly_consumption"),
            "reorder_threshold": normalized.get("reorder_threshold"),
            "last_updated": normalized.get("last_updated"),
            "source_import_id": import_id,
        })
        return

    # transactions / combined — also creates beneficiary/center records from
    # any detail columns present (refs resolved to internal ids at flush time).
    if normalized.get("beneficiary_id"):
        pending_beneficiaries.append({
            "external_reference": normalized["beneficiary_id"],
            "state": normalized.get("state"),
            "district": normalized.get("district"),
            "block": normalized.get("block"),
            "ration_category": normalized.get("ration_category"),
            "family_size": normalized.get("family_size"),
            "status": "ACTIVE",
        })
    if normalized.get("fps_center_id"):
        pending_centers.append({
            "fps_code": normalized["fps_center_id"],
            "name": normalized.get("name"),
            "state": normalized.get("state"),
            "district": normalized.get("district"),
            "block": normalized.get("block"),
            "location": normalized.get("location"),
            "latitude": normalized.get("latitude"),
            "longitude": normalized.get("longitude"),
            "status": "ACTIVE",
        })

    pending_transactions.append({
        "external_transaction_id": normalized.get("external_transaction_id", ""),
        "beneficiary_id": None,
        "fps_center_id": None,
        "_beneficiary_ref": normalized.get("beneficiary_id"),
        "_fps_code": normalized.get("fps_center_id"),
        "transaction_date": normalized.get("transaction_date", ""),
        "commodity": normalized.get("commodity", ""),
        "quantity": normalized.get("quantity", 0.0),
        "unit": normalized.get("unit") or DEFAULT_TRANSACTION_UNIT,
        "latitude": normalized.get("latitude"),
        "longitude": normalized.get("longitude"),
        "status": normalized.get("status", "COMPLETED"),
        "source_import_id": import_id,
    })


def _record_from_row(row, headers, mapping: dict) -> dict:
    """Build an internal-field record from a raw row using the mapping."""
    record = {}
    for index, header in enumerate(headers):
        field = mapping.get(header)
        if field:
            record[field] = row[index] if index < len(row) else ""
    return record


def _build_error_summary(examples: list) -> str:
    if not examples:
        return ""
    parts = []
    for example in examples:
        parts.append("Row %d: %s" % (example["row"], "; ".join(example["errors"])))
    text = " | ".join(parts)
    if len(text) > MAX_ERROR_SUMMARY_CHARS:
        text = text[:MAX_ERROR_SUMMARY_CHARS].rstrip() + "..."
    return text
