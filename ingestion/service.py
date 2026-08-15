"""RationRight — ingestion service (Phase 3 + Phase 4).

Coordinates the multi-step import flow behind the API:

    handle_upload  -> save temp file, sniff type, parse, auto-map, preview
    validate_step  -> apply user mapping/dataset type/sheet, validate, dedup,
                      quality score, duplicate classification, normalized preview
    confirm_step   -> idempotency check (file hash), import into the database,
                      clean up the temp file
    import_history / import_status -> DataImport provenance queries

Phase 4 additions
-----------------
- The uploaded bytes are hashed (SHA-256) at upload time. If the exact same
  file has already been imported, validation reports it and confirm refuses
  to import again — the user is pointed at the existing DataImport instead.
- The validate response now includes the deterministic quality score, the
  EXACT/POSSIBLE duplicate classification, warning examples, and a
  normalized preview (original vs normalized values).

Security model
--------------
- The user-supplied filename is used ONLY for extension detection — never as
  a filesystem path (no path traversal possible).
- Uploaded bytes go to a private temp directory via ``tempfile`` with a
  random token name; the file is deleted after the import (or when the
  pending entry expires), never served publicly, and never executed.
- Size is capped (``RATIONRIGHT_MAX_UPLOAD_MB``, default 10 MB).
- No secrets, environment variables, or raw file contents are logged.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import tempfile
import threading
import time
from pathlib import Path

from database import DEFAULT_DB_PATH, get_import_by_hash, open_db
from ingestion import mapping as mapmod
from ingestion import validation
from ingestion.importer import UPLOADED_SOURCE_NAME, run_import
from ingestion.mapping import MappingError
from ingestion.parsers import (
    FileTooLargeError,
    ParseError,
    get_max_rows,
    get_max_upload_bytes,
    parse_file,
    sniff_file_type,
    verify_magic_bytes,
)

logger = logging.getLogger("rationright.ingestion")

PENDING_TTL_SECONDS = 30 * 60  # stale pending uploads expire after 30 minutes
PREVIEW_ROWS = 20

_PENDING = {}          # token -> entry dict
_PENDING_LOCK = threading.Lock()


class NotFoundError(Exception):
    """Raised when a pending upload token or import id does not exist."""


class _Entry:
    def __init__(self, token, temp_path, file_name, file_type, dataset_name,
                 headers, rows, sheets, warnings, dataset_type, mapping,
                 file_hash, created_at):
        self.token = token
        self.temp_path = temp_path
        self.file_name = file_name
        self.file_type = file_type
        self.dataset_name = dataset_name
        self.headers = headers
        self.rows = rows
        self.sheets = sheets
        self.warnings = warnings
        self.dataset_type = dataset_type
        self.mapping = mapping          # list of {"external", "internal"}
        self.sheet = None
        self.file_hash = file_hash      # SHA-256 of the uploaded bytes
        self.created_at = created_at


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


def handle_upload(data: bytes, filename: str, content_type: str = "") -> dict:
    """Accept an uploaded file, store it safely, and prepare the import flow.

    Returns the detected file info, inferred dataset type, auto mapping,
    sheet list, preview rows, and warnings. No database writes happen here.
    """
    if len(data) > get_max_upload_bytes():
        raise FileTooLargeError(
            "File too large. Maximum upload size is %d MB."
            % (get_max_upload_bytes() // (1024 * 1024))
        )
    file_type = sniff_file_type(filename, content_type)
    verify_magic_bytes(file_type, data)

    token = secrets.token_hex(8)
    file_hash = hashlib.sha256(data).hexdigest()
    upload_dir = _upload_dir()
    temp_path = upload_dir / ("up_%s.%s" % (token, file_type))
    with open(temp_path, "wb") as fh:
        fh.write(data)

    try:
        parsed = parse_file(temp_path, file_type)
    except ParseError:
        _safe_unlink(temp_path)
        raise

    headers = parsed["headers"]
    rows = parsed["rows"]
    sheets = parsed["sheets"]
    warnings = list(parsed.get("warnings", []))
    dataset_type = mapmod.infer_dataset_type(headers)
    auto = mapmod.detect_mapping(headers, dataset_type)
    warnings.extend(auto["warnings"])

    dataset_name = _default_dataset_name(filename)
    entry = _Entry(
        token=token, temp_path=temp_path, file_name=filename,
        file_type=file_type, dataset_name=dataset_name, headers=headers,
        rows=rows, sheets=sheets, warnings=warnings,
        dataset_type=dataset_type, mapping=auto["mapping"],
        file_hash=file_hash, created_at=time.time(),
    )
    with _PENDING_LOCK:
        _purge_stale_locked()
        _PENDING[token] = entry

    logger.info(
        "[Ingestion] Upload %s: %s (%s), %d record(s), type=%s",
        token, filename, file_type, len(rows), dataset_type,
    )
    return {
        "token": token,
        "file_name": filename,
        "file_type": file_type,
        "dataset_name": dataset_name,
        "record_count": len(rows),
        "detected_columns": headers,
        "sheets": sheets,
        "dataset_type": dataset_type,
        "dataset_type_label": mapmod.DATASET_TYPE_LABELS[dataset_type],
        "mapping": auto["mapping"],
        "missing_required": auto["missing_required"],
        "warnings": warnings,
        "preview": _preview(headers, rows),
    }


# ---------------------------------------------------------------------------
# Validate (mapping + validation + duplicates + preview)
# ---------------------------------------------------------------------------


def validate_step(
    token: str,
    *,
    dataset_type: str = None,
    mapping: dict = None,
    sheet: str = None,
    db_path=DEFAULT_DB_PATH,
) -> dict:
    """Apply the user's mapping/dataset type/sheet and validate every record.

    ``mapping`` is an optional dict of ``external header -> internal field``
    overrides; when omitted the stored auto mapping is used. Stores the
    confirmed choices on the pending entry so confirm_step uses them.
    Returns a full validation report (counts, errors, duplicates, preview).
    """
    entry = _get_entry(token)
    if len(entry.rows) > get_max_rows():
        raise FileTooLargeError(
            "The file contains %d rows, exceeding the configured limit of %d. "
            "Set RATIONRIGHT_MAX_ROWS to raise the limit."
            % (len(entry.rows), get_max_rows())
        )
    if dataset_type:
        if dataset_type not in mapmod.DATASET_TYPES:
            raise MappingError(
                "Unknown dataset type %r. Supported: %s"
                % (dataset_type, ", ".join(mapmod.DATASET_TYPES))
            )
        entry.dataset_type = dataset_type
    if sheet is not None and entry.sheet != sheet:
        parsed = parse_file(entry.temp_path, entry.file_type, sheet=sheet)
        entry.headers = parsed["headers"]
        entry.rows = parsed["rows"]
        entry.sheets = parsed.get("sheets", entry.sheets)
        entry.sheet = sheet
        entry.warnings = list(parsed.get("warnings", []))

    mapping_list = _apply_mapping_overrides(entry, mapping)
    missing = mapmod.validate_mapping(mapping_list, entry.dataset_type)
    if missing:
        raise MappingError(" ".join(missing))

    mapping_dict = mapmod.mapping_to_dict(mapping_list)
    summary = validation.summarize(
        entry.rows, entry.dataset_type, entry.headers, mapping_dict
    )
    duplicates = validation.classify_duplicates(
        entry.rows, entry.dataset_type, entry.headers, mapping_dict
    )
    quality = validation.quality_report(
        total=len(entry.rows),
        invalid=summary["invalid_records"],
        duplicates=duplicates["exact"] + duplicates["possible"],
        warnings=summary["warning_count"],
    )
    mapped_columns = [
        {"external": m["external"], "internal": m["internal"]}
        for m in mapping_list
    ]
    already = _already_imported(entry, db_path)
    return {
        "token": token,
        "file_name": entry.file_name,
        "file_type": entry.file_type,
        "dataset_name": entry.dataset_name,
        "dataset_type": entry.dataset_type,
        "dataset_type_label": mapmod.DATASET_TYPE_LABELS[entry.dataset_type],
        "sheets": entry.sheets,
        "sheet": entry.sheet,
        "detected_columns": entry.headers,
        "mapped_columns": mapped_columns,
        "required_fields": [
            {"field": f, "label": mapmod.field_label(f)}
            for f in mapmod.required_fields(entry.dataset_type)
        ],
        "record_count": summary["total_records"],
        "valid_records": summary["valid_records"],
        "invalid_records": summary["invalid_records"],
        "duplicate_records": duplicates["exact"] + duplicates["possible"],
        "duplicates": duplicates,
        "warning_count": summary["warning_count"],
        "errors": summary["errors"],
        "warnings": entry.warnings,
        "warning_examples": summary["warnings"],
        "preview": _preview(entry.headers, entry.rows),
        "preview_normalized": summary["preview_normalized"],
        "quality": quality,
        "already_imported": already,
    }


# ---------------------------------------------------------------------------
# Confirm (import)
# ---------------------------------------------------------------------------


def confirm_step(token: str, *, db_path=DEFAULT_DB_PATH) -> dict:
    """Run the confirmed import and clean up the temporary file.

    Idempotency: if the exact same file (SHA-256) has already been imported,
    no new records are written — the existing DataImport is returned instead.
    """
    entry = _get_entry(token)
    mapping_list = entry.mapping
    missing = mapmod.validate_mapping(mapping_list, entry.dataset_type)
    if missing:
        raise MappingError(" ".join(missing))
    mapping_dict = mapmod.mapping_to_dict(mapping_list)

    already = _already_imported(entry, db_path)
    if already:
        _drop_entry(token)
        return {
            "status": "ALREADY_IMPORTED",
            "message": "This dataset appears to have already been imported.",
            "existing_import": already,
        }

    conn = open_db(db_path)
    try:
        summary = run_import(
            conn,
            file_name=entry.file_name,
            file_type=entry.file_type,
            dataset_name=entry.dataset_name,
            source_name=UPLOADED_SOURCE_NAME,
            dataset_type=entry.dataset_type,
            headers=entry.headers,
            rows=entry.rows,
            mapping=mapping_dict,
            file_hash=entry.file_hash,
        )
    except Exception:
        # Phase 14: a critical failure must not leave a half-imported dataset.
        # Everything (import row, beneficiaries, FPS, transactions, inventory)
        # is written in one transaction, so roll back and surface a clean error.
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        raise
    finally:
        conn.close()

    _drop_entry(token)
    return summary


# ---------------------------------------------------------------------------
# History / status
# ---------------------------------------------------------------------------


def import_history(db_path=DEFAULT_DB_PATH) -> list:
    conn = open_db(db_path)
    try:
        rows = conn.execute(
            "SELECT i.id, i.dataset_name, i.file_name, i.file_type, i.record_count, "
            " i.successful_records, i.failed_records, i.duplicate_records, i.status, "
            " i.error_summary, i.started_at, i.completed_at, i.created_at, "
            " s.name AS source_name, s.type AS source_type "
            "FROM data_imports i JOIN data_sources s ON s.id = i.data_source_id "
            "ORDER BY i.id DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def import_status(import_id: int, *, db_path=DEFAULT_DB_PATH) -> dict:
    conn = open_db(db_path)
    try:
        row = conn.execute(
            "SELECT i.id, i.dataset_name, i.file_name, i.file_type, i.record_count, "
            " i.successful_records, i.failed_records, i.duplicate_records, i.status, "
            " i.error_summary, i.started_at, i.completed_at, i.created_at, "
            " s.name AS source_name, s.type AS source_type "
            "FROM data_imports i JOIN data_sources s ON s.id = i.data_source_id "
            "WHERE i.id = :id",
            {"id": import_id},
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise NotFoundError("Import %s was not found." % import_id)
    return dict(row)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _upload_dir() -> Path:
    base = Path(tempfile.gettempdir()) / "rationright_uploads"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _safe_unlink(path) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not remove temp file %s", path)


def _default_dataset_name(filename: str) -> str:
    stem = Path(filename).stem.strip() or "uploaded_dataset"
    return stem[:120]


def _get_entry(token: str) -> _Entry:
    with _PENDING_LOCK:
        _purge_stale_locked()
        entry = _PENDING.get(token)
    if entry is None:
        raise NotFoundError(
            "This upload session has expired or does not exist. Please upload the file again."
        )
    return entry


def _drop_entry(token: str) -> None:
    with _PENDING_LOCK:
        entry = _PENDING.pop(token, None)
    if entry is not None:
        _safe_unlink(entry.temp_path)


def _purge_stale_locked() -> None:
    now = time.time()
    stale = [
        token for token, entry in _PENDING.items()
        if now - entry.created_at > PENDING_TTL_SECONDS
    ]
    for token in stale:
        entry = _PENDING.pop(token, None)
        if entry is not None:
            _safe_unlink(entry.temp_path)


def _apply_mapping_overrides(entry: _Entry, overrides: dict) -> list:
    """Merge user overrides ({external header -> internal field}) into the
    stored mapping list. Returns the resulting list (also stored)."""
    mapping_list = []
    for item in entry.mapping:
        external = item["external"]
        internal = item["internal"]
        if isinstance(overrides, dict) and external in overrides:
            value = overrides[external]
            internal = None if value in (None, "", "ignore") else value
        mapping_list.append({"external": external, "internal": internal})
    entry.mapping = mapping_list
    return mapping_list


def _preview(headers: list, rows: list) -> dict:
    return {
        "headers": headers,
        "rows": rows[:PREVIEW_ROWS],
        "shown": min(PREVIEW_ROWS, len(rows)),
        "total": len(rows),
    }


def _already_imported(entry: _Entry, db_path) -> dict:
    """Look up an existing COMPLETED/PARTIAL import with the same file hash.

    Returns a compact provenance dict (or None) so the UI can show
    "This dataset appears to have already been imported" with a link to the
    existing import instead of duplicating records.
    """
    if not entry.file_hash:
        return None
    conn = open_db(db_path)
    try:
        row = get_import_by_hash(conn, entry.file_hash)
    finally:
        conn.close()
    if row is None:
        return None
    return {
        "data_import_id": row["id"],
        "dataset_name": row["dataset_name"],
        "file_name": row["file_name"],
        "status": row["status"],
        "record_count": row["record_count"],
        "imported": row["successful_records"],
        "duplicates": row["duplicate_records"],
        "failed": row["failed_records"],
        "completed_at": row["completed_at"],
    }
