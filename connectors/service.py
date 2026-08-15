"""RationAI — external data sync service (Phase 7).

Orchestrates one sync:

    SYNC -> mark source SYNCING -> fetch -> parse -> map -> validate
         -> run_import (Phase 4 pipeline: normalize, dedup, provenance)
         -> update DataSource timestamps/status -> sync summary

Reuses the existing ingestion pipeline end to end; no second parser or
importer exists. Safety rules honoured here:

* A failed sync NEVER deletes or replaces existing data — the last
  successful dataset stays in the database and the UI shows the last
  successful timestamp alongside the error.
* Only REGISTERED sources (a numeric data_source_id whose row matches a
  server-side profile) can be synced — users cannot submit URLs to fetch
  (no SSRF).
* Credentials live only in server-side environment variables and are never
  logged or returned.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from connectors.base import connector_for, sha256_bytes
from connectors.errors import (
    AuthError,
    ConnectorError,
    SourceNotConfiguredError,
    SyncFailure,
)

from connectors.fetcher import http_get_bytes
from connectors.profiles import get_profile, list_profiles
from database import (
    DEFAULT_DB_PATH,
    get_data_import,
    get_data_source,
    get_data_source_by_name,
    insert_data_import,
    insert_data_source,
    open_db,
    update_data_source_sync,
)

logger = logging.getLogger("rationright.connectors")

#: Exceptions that carry a user-safe message. Ingestion parse/mapping
#: errors (reused from the Phase 3 pipeline) are user-safe too.
from ingestion.parsers import EmptyDatasetError, ParseError  # noqa: E402
from ingestion.mapping import MappingError  # noqa: E402

_USER_SAFE = (
    ConnectorError,
    SourceNotConfiguredError,
    SyncFailure,
    ParseError,
    EmptyDatasetError,
    MappingError,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Registration (centralized configuration -> database rows)
# ---------------------------------------------------------------------------

def register_configured_sources(db_path: str = DEFAULT_DB_PATH) -> list:
    """Ensure every configured profile has a DataSource row.

    Idempotent: creates missing sources, refreshes their base_url/type/
    description, and marks auth-required sources that lack a key as INACTIVE
    with an actionable last_error (they remain visible but cannot sync).
    """
    conn = open_db(db_path)
    try:
        registered = []
        for profile in list_profiles():
            existing = get_data_source_by_name(conn, profile["name"])
            needs_key = bool(profile.get("requires_auth"))
            from connectors.profiles import _ogd_api_key
            has_key = not needs_key or bool(_ogd_api_key())
            if existing is None:
                source_id = insert_data_source(
                    conn,
                    name=profile["name"],
                    source_type=profile["type"],
                    description=profile.get("description"),
                    status="ACTIVE" if has_key else "INACTIVE",
                    base_url=profile.get("base_url"),
                )
                if not has_key:
                    update_data_source_sync(
                        conn, source_id, status="INACTIVE",
                        last_error=(
                            "Requires an API key — set the %s environment variable "
                            "server-side." % profile.get("auth_env_var")
                        ),
                    )
                registered.append(profile["name"])
            else:
                changed = False
                if existing.get("base_url") != profile.get("base_url"):
                    conn.execute(
                        "UPDATE data_sources SET base_url = :url, updated_at = :now WHERE id = :id",
                        {"url": profile.get("base_url"), "now": _now_iso(), "id": existing["id"]},
                    )
                    changed = True
                if existing.get("description") != profile.get("description"):
                    conn.execute(
                        "UPDATE data_sources SET description = :desc, updated_at = :now WHERE id = :id",
                        {"desc": profile.get("description"), "now": _now_iso(), "id": existing["id"]},
                    )
                    changed = True
                if not has_key and existing.get("status") == "ACTIVE":
                    update_data_source_sync(
                        conn, existing["id"], status="INACTIVE",
                        last_error="Requires an API key — set the %s environment "
                                   "variable server-side." % profile.get("auth_env_var"),
                    )
                    changed = True
                if has_key and existing.get("status") in ("INACTIVE", "ERROR"):
                    # A key is now configured server-side: reactivate a source
                    # that was previously inactive/errored for lack of one and
                    # clear the stale error (no sync has happened yet, so the
                    # UI must still never claim a live connection).
                    update_data_source_sync(
                        conn, existing["id"], status="ACTIVE", last_error=None,
                    )
                    changed = True
                if changed:
                    registered.append(profile["name"])
        conn.commit()
        return registered
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------

def connection_status(source: dict) -> str:
    """Derive the UI-facing connection state from the DB row.

    Uses the existing status conventions (ACTIVE/INACTIVE/ERROR/SYNCING)
    and maps them to the connector lifecycle the UI displays:
    CONNECTED / SYNCING / PARTIAL / ERROR / DISCONNECTED.
    """
    status = (source.get("status") or "").upper()
    if status == "SYNCING":
        return "SYNCING"
    if status == "ERROR":
        return "ERROR"
    if status == "INACTIVE":
        return "DISCONNECTED"
    if status == "ACTIVE":
        if source.get("last_successful_sync_at"):
            return "CONNECTED"
        if source.get("last_error"):
            return "DISCONNECTED"
        return "CONNECTED"
    return "DISCONNECTED"


def source_view(conn, source: dict) -> dict:
    """Public view of a source: row + derived connection state + last import."""
    view = {
        "data_source_id": source["id"],
        "name": source["name"],
        "type": source["type"],
        "description": source.get("description"),
        "base_url": source.get("base_url"),
        "status": source.get("status"),
        "connection_status": connection_status(source),
        "last_sync_at": source.get("last_sync_at"),
        "last_successful_sync_at": source.get("last_successful_sync_at"),
        "last_error": source.get("last_error"),
    }
    last = conn.execute(
        "SELECT id, dataset_name, record_count, successful_records, failed_records, "
        "duplicate_records, status, started_at, completed_at "
        "FROM data_imports WHERE data_source_id = :sid "
        "ORDER BY id DESC LIMIT 1",
        {"sid": source["id"]},
    ).fetchone()
    if last is not None:
        view["last_import"] = {
            "data_import_id": last["id"],
            "dataset_name": last["dataset_name"],
            "record_count": last["record_count"],
            "successful_records": last["successful_records"],
            "failed_records": last["failed_records"],
            "duplicate_records": last["duplicate_records"],
            "status": last["status"],
            "completed_at": last["completed_at"],
        }
    profile = get_profile(source["name"])
    if profile:
        view["format"] = profile.get("format")
        view["dataset_type"] = profile.get("dataset_type")
        view["requires_auth"] = bool(profile.get("requires_auth"))
        view["documentation_url"] = profile.get("documentation_url")
        view["label"] = profile.get("label")
    # A source with a registered connector profile but no successful
    # connection is CONNECTOR_READY, not merely DISCONNECTED — the UI must
    # never imply a live connection that has not been verified (Phase 8).
    if view["connection_status"] == "DISCONNECTED" and profile:
        view["connection_status"] = "CONNECTOR_READY"
    elif view["connection_status"] == "CONNECTED" and profile and not source.get("last_successful_sync_at"):
        # ACTIVE with a key configured but NO successful sync yet: the source
        # is ready to sync, never connected/live. (connection_status maps
        # ACTIVE-no-sync to CONNECTED for local datasets, which is fine —
        # those are not external connectors.)
        view["connection_status"] = "CONNECTOR_READY"
    # Server-side auth state as a boolean only — the credential itself never
    # leaves the server (Phase 14 secret rules).
    if profile and profile.get("requires_auth"):
        from connectors.profiles import _ogd_api_key
        view["auth_configured"] = bool(_ogd_api_key())
    return view


def list_sources(db_path: str = DEFAULT_DB_PATH) -> list:
    conn = open_db(db_path)
    try:
        rows = conn.execute("SELECT * FROM data_sources ORDER BY id").fetchall()
        return [source_view(conn, dict(r)) for r in rows]
    finally:
        conn.close()


def get_source_status(source_id: int, db_path: str = DEFAULT_DB_PATH):
    conn = open_db(db_path)
    try:
        source = get_data_source(conn, source_id)
        if source is None:
            return None
        return source_view(conn, source)
    finally:
        conn.close()


def list_source_imports(source_id: int, db_path: str = DEFAULT_DB_PATH) -> list:
    conn = open_db(db_path)
    try:
        rows = conn.execute(
            "SELECT id, dataset_name, file_name, file_type, record_count, "
            "successful_records, failed_records, duplicate_records, status, "
            "error_summary, started_at, completed_at "
            "FROM data_imports WHERE data_source_id = :sid ORDER BY id DESC",
            {"sid": source_id},
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

def _record_failed_import(
    conn, source: dict, profile: dict, error: str
) -> int:
    now = _now_iso()
    import_id = insert_data_import(
        conn,
        data_source_id=source["id"],
        dataset_name=profile.get("dataset_name") or source["name"],
        file_name=profile.get("file_name"),
        file_type=profile.get("format"),
        record_count=0,
        failed_records=1,
        status="FAILED",
        error_summary=error[:500],
        started_at=now,
        completed_at=now,
    )
    conn.commit()
    return import_id


def sync_source(
    source_id: int,
    *,
    db_path: str = DEFAULT_DB_PATH,
    request_host: Optional[str] = None,
    fetcher: Callable = http_get_bytes,
) -> dict:
    """Sync one registered source. Returns a summary dict (never raises for
    expected failures — those are recorded on the source/import and returned)."""
    conn = open_db(db_path)
    try:
        source = get_data_source(conn, source_id)
        if source is None:
            raise SyncFailure("Unknown data source id %r" % source_id)
        profile = get_profile(source["name"])
        if profile is None:
            raise SyncFailure(
                "Source %r has no connector profile configured." % source["name"]
            )

        # ---- auth pre-check (no fetch, no retry) ---------------------------
        from connectors.profiles import _ogd_api_key
        if profile.get("requires_auth") and not _ogd_api_key():
            error = (
                "API key not configured. Set the %s environment variable "
                "server-side, then retry." % profile.get("auth_env_var")
            )
            import_id = _record_failed_import(conn, source, profile, error)
            update_data_source_sync(
                conn, source["id"], status="ERROR",
                last_sync_at=_now_iso(), last_error=error,
            )
            conn.commit()
            return {
                "status": "ERROR",
                "source_name": source["name"],
                "source_id": source["id"],
                "data_import_id": import_id,
                "fetched": 0,
                "imported": 0,
                "error": error,
                "retryable": False,
                "message": "Sync failed — see error. Existing data is unchanged.",
            }

        # ---- mark SYNCING --------------------------------------------------
        update_data_source_sync(conn, source["id"], status="SYNCING")
        conn.commit()

        def resolve_url(base_url: str) -> str:
            if base_url.startswith("/"):
                if not request_host:
                    raise SourceNotConfiguredError(
                        "Relative source URL requires the request host."
                    )
                return "http://%s%s" % (request_host, base_url)
            return base_url

        try:
            connector = connector_for(profile)
            pages = connector.fetch(fetcher, resolve_url)
            headers, rows = connector.parse(pages)
            mapping = connector.map_columns(headers)
            summary = run_sync_import(
                conn, source, profile, headers, rows, mapping, pages
            )
        except Exception as exc:  # noqa: BLE001
            error = _safe_error(exc)
            import_id = _record_failed_import(conn, source, profile, error)
            update_data_source_sync(
                conn, source["id"], status="ERROR",
                last_sync_at=_now_iso(), last_error=error,
            )
            conn.commit()
            return {
                "status": "ERROR",
                "source_name": source["name"],
                "source_id": source["id"],
                "data_import_id": import_id,
                "fetched": 0,
                "imported": 0,
                "error": error,
                "retryable": isinstance(exc, ConnectorError) and exc.retryable,
                "message": "Sync failed — existing data is unchanged. "
                           "Showing the last successful dataset.",
            }

        # A re-sync that finds nothing new is a SUCCESS, not a failure:
        # the importer reports 0 imported + all duplicates (nothing changed).
        # Re-label that import record COMPLETED so provenance stays honest.
        if summary["status"] == "FAILED" and summary["failed"] == 0 and summary["duplicates"] > 0:
            sync_status = "UP_TO_DATE"
            conn.execute(
                "UPDATE data_imports SET status = 'COMPLETED', error_summary = NULL "
                "WHERE id = :import_id",
                {"import_id": summary["data_import_id"]},
            )
        else:
            sync_status = "COMPLETED" if summary["status"] == "COMPLETED" else "PARTIAL"
        update_data_source_sync(
            conn, source["id"], status="ACTIVE",
            last_sync_at=_now_iso(), last_successful_sync_at=_now_iso(),
            last_error=None,
        )
        conn.commit()
        return {
            "status": sync_status,
            "source_name": source["name"],
            "source_id": source["id"],
            "data_import_id": summary["data_import_id"],
            "fetched": summary["record_count"],
            "imported": summary["imported"],
            "failed": summary["failed"],
            "duplicates": summary["duplicates"],
            "duplicates_exact": summary["duplicates_exact"],
            "duplicates_possible": summary["duplicates_possible"],
            "warnings": summary["warnings"],
            "quality": summary["quality"],
            "pages_fetched": len(pages),
            "message": "Sync completed." if sync_status == "COMPLETED"
                       else "Sync completed — no new records (already up to date)."
                       if sync_status == "UP_TO_DATE"
                       else "Sync completed with partial failures.",
        }
    finally:
        conn.close()


def run_sync_import(
    conn, source: dict, profile: dict, headers: list, rows: list,
    mapping: dict, pages: list,
) -> dict:
    """Run the existing Phase 4 import pipeline on parsed source rows."""
    from ingestion.importer import run_import

    payload = b"".join(pages)
    return run_import(
        conn,
        file_name=profile.get("file_name") or (source["name"] + "." + (profile.get("format") or "csv")),
        file_type=profile.get("format") or "csv",
        dataset_name=profile.get("dataset_name") or source["name"],
        source_name=source["name"],
        dataset_type=profile.get("dataset_type") or "ration_transactions",
        headers=headers,
        rows=rows,
        mapping=mapping,
        file_hash=sha256_bytes(payload),
    )


def _safe_error(exc: Exception) -> str:
    """User-safe error text: never leaks stack traces or credentials."""
    if isinstance(exc, _USER_SAFE):
        return str(exc)
    logger.error("Sync failed (internal): %s", exc, exc_info=True)
    return "The sync failed for an unexpected reason."
