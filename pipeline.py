"""RationAI — data pipeline status, quality, freshness, lineage (Phase 8).

The user-facing Data Pipeline experience is driven entirely from real
database state — nothing here invents numbers. It answers:

    Where does data come from?        -> data_sources
    How does it enter RationAI?       -> data_imports (fetch counts)
    How is it validated/normalized?   -> stored valid/failed/warnings counts
    How are duplicates handled?       -> stored duplicate counts
    How does it reach the database?   -> live table counts
    How do analytics consume it?      -> the Phase 5 analytics service
    How do AI agents consume it?      -> analysis_runs + ai_insights

The quality score reuses the exact Phase 4 formula (``quality_report``) —
there is only one quality calculation in the system. Freshness thresholds
are documented constants below. Analysis runs are recorded by the server
after every real workflow execution (see ``record_analysis_run``), giving
every AI insight a durable lineage chain:

    AI insight <- analysis run <- data import <- data source

No LLM calls, no API keys, no secrets anywhere in this module.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from connectors.errors import (
    AuthError,
    ConnectorError,
    HttpStatusError,
    RateLimitError,
    TimeoutError as ConnectorTimeoutError,
    UnreachableError,
)
from connectors.fetcher import http_get_bytes
from connectors.profiles import get_profile
from database import (
    DEFAULT_DB_PATH,
    get_analysis_runs_for_import,
    get_data_source,
    insert_analysis_run,
    open_db,
)
from ingestion.validation import quality_report

logger = logging.getLogger("rationright.pipeline")

#: Freshness thresholds (documented, configurable): FRESH under 24h,
#: RECENT under 7 days, STALE under 30 days; older or unknown = UNKNOWN.
FRESH_MAX_SECONDS = 24 * 3600
RECENT_MAX_SECONDS = 7 * 24 * 3600
STALE_MAX_SECONDS = 30 * 24 * 3600

#: Duplicate-rate warning threshold for the DEDUPLICATE stage.
DUPLICATE_WARN_PCT = 5.0

PIPELINE_STAGES = [
    ("source", "Source", "Where data comes from"),
    ("extract", "Extract", "Fetch / parse raw records"),
    ("validate", "Validate", "Required fields + business rules"),
    ("normalize", "Normalize", "Dates, numbers, commodities, units"),
    ("deduplicate", "Deduplicate", "Exact + possible duplicate handling"),
    ("database", "Database", "Normalized tables with provenance"),
    ("analytics", "Analytics", "Phase 5 aggregation layer"),
    ("ai", "AI", "Multi-agent analysis"),
]


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
        # Stored naive timestamps are UTC (``_now_iso`` writes an explicit
        # offset; legacy rows may be naive) — treat them as UTC so age
        # calculations never mix naive and aware datetimes.
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _fmt_age(seconds: float) -> str:
    if seconds < 3600:
        return "%d minutes" % max(1, int(seconds // 60))
    if seconds < 86400:
        return "%d hours" % int(seconds // 3600)
    return "%d days" % int(seconds // 86400)


# ---------------------------------------------------------------------------
# Analysis run recording (called by the server after each workflow execution)
# ---------------------------------------------------------------------------

def record_analysis_run(
    result: dict,
    *,
    dataset_mode: str,
    data_import_id: Optional[int] = None,
    db_path: str = DEFAULT_DB_PATH,
    analysis_types: Optional[list] = None,
    filters: Optional[dict] = None,
    timings: Optional[dict] = None,
    duration_ms: Optional[int] = None,
) -> dict:
    """Persist durable metadata about one workflow run; returns the run dict.

    The full workflow result continues to be returned to the UI live — this
    only records the provenance/count summary so lineage survives page loads.
    ``analysis_types`` / ``filters`` / ``timings`` / ``duration_ms`` are
    stored with the run so Analysis History can reproduce each run (Phase 9).
    """
    anomalies = result.get("anomalies") or []
    findings = result.get("findings") or []
    cases = result.get("cases") or []
    alerts = result.get("alerts") or []
    insights = result.get("insights") or []
    skipped = bool(result.get("skipped_reason"))
    types_status = result.get("types") or {}

    if result.get("errors"):
        status = "FAILED"
        summary = "; ".join(str(e) for e in result["errors"])[:300]
    elif skipped:
        status = "INSUFFICIENT_DATA"
        summary = str(result.get("skipped_reason"))[:300]
    else:
        status = "COMPLETED"
        summary = "%d anomaly(ies) -> %d finding(s) -> %d case(s) -> %d alert(s)" % (
            len(anomalies), len(findings), len(cases), len(alerts),
        )

    conn = open_db(db_path)
    try:
        seq = conn.execute("SELECT COUNT(*) AS n FROM analysis_runs").fetchone()["n"] + 1
        analysis_id = "RA-%04d-%04d" % (_now().year, seq)
        insert_analysis_run(
            conn,
            analysis_id=analysis_id,
            data_import_id=data_import_id,
            dataset_mode=dataset_mode,
            status=status,
            anomaly_count=len(anomalies),
            finding_count=len(findings),
            case_count=len(cases),
            alert_count=len(alerts),
            insight_count=len(insights),
            analysis_types=analysis_types,
            filters=filters,
            timings=timings,
            duration_ms=duration_ms,
            summary=summary,
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "analysis_id": analysis_id,
        "status": status,
        "summary": summary,
        "dataset_mode": dataset_mode,
        "data_import_id": data_import_id,
        "insight_count": len(insights),
        "types": types_status,
        "timings": timings,
        "duration_ms": duration_ms,
        "created_at": None,  # resolved by run_detail/lineage queries
    }


# ---------------------------------------------------------------------------
# Pipeline status (8 stages + overall + checks)
# ---------------------------------------------------------------------------

def _stage(key, label, sub, status, records, detail, last_execution=None):
    return {
        "key": key, "label": label, "sub": sub, "status": status,
        "records": records, "detail": detail, "last_execution": last_execution,
    }


def pipeline_status(db_path: str = DEFAULT_DB_PATH) -> dict:
    """Overall pipeline health + per-stage state, computed from the database.

    Every stage reports real counts from data_sources / data_imports /
    ration_transactions / beneficiaries / inventory / analysis_runs /
    ai_insights and the Phase 5 analytics service. Stages whose metric does
    not exist yet report ``status: \"unknown\"`` and ``records: None`` — the
    UI renders those as \"Not available\", never as fake numbers.
    """
    conn = open_db(db_path)
    try:
        sources = conn.execute("SELECT * FROM data_sources ORDER BY id").fetchall()
        source_rows = [dict(r) for r in sources]

        totals = conn.execute(
            "SELECT COALESCE(SUM(record_count),0) AS fetched, "
            " COALESCE(SUM(successful_records),0) AS valid, "
            " COALESCE(SUM(failed_records),0) AS invalid, "
            " COALESCE(SUM(duplicate_records),0) AS dupes, "
            " COALESCE(SUM(warnings_count),0) AS warnings "
            "FROM data_imports"
        ).fetchone()
        last_import = conn.execute(
            "SELECT i.*, s.name AS source_name FROM data_imports i "
            "JOIN data_sources s ON s.id = i.data_source_id "
            "ORDER BY i.id DESC LIMIT 1"
        ).fetchone()

        db_counts = {
            "transactions": conn.execute("SELECT COUNT(*) AS n FROM ration_transactions").fetchone()["n"],
            "beneficiaries": conn.execute("SELECT COUNT(*) AS n FROM beneficiaries").fetchone()["n"],
            "centers": conn.execute("SELECT COUNT(*) AS n FROM fps_centers").fetchone()["n"],
            "inventory": conn.execute("SELECT COUNT(*) AS n FROM inventory").fetchone()["n"],
        }
        analysis_runs = conn.execute("SELECT COUNT(*) AS n FROM analysis_runs").fetchone()["n"]
        ai_insights = conn.execute("SELECT COUNT(*) AS n FROM ai_insights").fetchone()["n"]
        latest_import_at = conn.execute(
            "SELECT MAX(completed_at) AS ts FROM data_imports "
            "WHERE status IN ('COMPLETED','PARTIAL')"
        ).fetchone()["ts"]
    finally:
        conn.close()

    fetched, valid, invalid, dupes, warnings = (
        totals["fetched"], totals["valid"], totals["invalid"],
        totals["dupes"], totals["warnings"],
    )
    last_import_dict = dict(last_import) if last_import is not None else None
    last_import_status = (last_import_dict or {}).get("status")
    has_data = db_counts["transactions"] > 0 or db_counts["beneficiaries"] > 0

    # ---- per-stage status -------------------------------------------------
    stages = []
    stages.append(_stage(
        "source", "Source", PIPELINE_STAGES[0][2],
        "error" if not source_rows else "ok",
        len(source_rows), "%d configured source(s)" % len(source_rows),
    ))
    stages.append(_stage(
        "extract", "Extract", PIPELINE_STAGES[1][2],
        "warn" if fetched == 0 else "ok",
        fetched, "records fetched across %d import(s)" % (len([s for s in source_rows]) if source_rows else 0),
        last_import_dict.get("completed_at") if last_import_dict else None,
    ))
    if invalid > 0:
        validate_status = "warn"
        validate_detail = "%d valid, %d invalid, %d warnings" % (valid, invalid, warnings)
    elif fetched == 0:
        validate_status = "warn"
        validate_detail = "no records to validate yet"
    else:
        validate_status = "ok"
        validate_detail = "all %d record(s) valid, %d warning(s)" % (valid, warnings)
    stages.append(_stage("validate", "Validate", PIPELINE_STAGES[2][2], validate_status, valid, validate_detail,
                         last_import_dict.get("completed_at") if last_import_dict else None))
    stages.append(_stage(
        "normalize", "Normalize", PIPELINE_STAGES[3][2],
        "warn" if valid == 0 else "ok",
        valid, "normalized records (dates, numbers, commodities, units)",
        last_import_dict.get("completed_at") if last_import_dict else None,
    ))
    duplicate_pct = (dupes / fetched * 100) if fetched else 0.0
    stages.append(_stage(
        "deduplicate", "Deduplicate", PIPELINE_STAGES[4][2],
        "warn" if fetched and duplicate_pct > DUPLICATE_WARN_PCT else "ok",
        dupes, "duplicates (%.1f%% of fetched)" % duplicate_pct if fetched else "no records yet",
    ))
    stages.append(_stage(
        "database", "Database", PIPELINE_STAGES[5][2],
        "warn" if not has_data else "ok",
        sum(db_counts.values()),
        "stored: %d transaction(s), %d beneficiary(ies), %d center(s), %d inventory" % (
            db_counts["transactions"], db_counts["beneficiaries"],
            db_counts["centers"], db_counts["inventory"]),
    ))

    # Analytics stage: ask the Phase 5 service whether it can compute.
    try:
        import analytics  # noqa: PLC0415
        aconn = analytics.analytics(db_path=db_path)
        try:
            overview = analytics.overview(aconn)
        finally:
            aconn.close()
        analytics_ok = True
        analytics_detail = "KPIs computed: %d metric(s)" % len(overview)
    except Exception:  # noqa: BLE001
        analytics_ok = False
        analytics_detail = "analytics service unavailable"
    stages.append(_stage(
        "analytics", "Analytics", PIPELINE_STAGES[6][2],
        "ok" if analytics_ok else "error",
        None if not analytics_ok else (len(overview) if analytics_ok else None),
        analytics_detail,
    ))

    ai_status = "ok" if analysis_runs > 0 else ("warn" if has_data else "unknown")
    ai_detail = "%d analysis run(s), %d persisted AI insight(s)" % (analysis_runs, ai_insights)
    if analysis_runs == 0:
        ai_detail = "no analysis run yet — run the multi-agent workflow"
    stages.append(_stage("ai", "AI", PIPELINE_STAGES[7][2], ai_status, analysis_runs, ai_detail))

    # ---- checks + overall -------------------------------------------------
    external = [s for s in source_rows if s["name"] in ("ogd_pds_resource",)]
    external_ready = all(
        s["status"] in ("ACTIVE", "SYNCING") and s.get("last_successful_sync_at")
        for s in external
    ) if external else True

    checks = [
        {"label": "Source configured", "ok": bool(source_rows),
         "detail": "%d source(s)" % len(source_rows)},
        {"label": "External source available", "ok": external_ready,
         "detail": "Official OGD connector ready but not live (no API key configured)"
                   if external and not external_ready else "No external source configured"},
        {"label": "Last import successful", "ok": last_import_status in (None, "COMPLETED", "PARTIAL"),
         "detail": last_import_status or "no imports yet"},
        {"label": "Database synchronized", "ok": has_data,
         "detail": "%d stored record(s)" % sum(db_counts.values())},
        {"label": "Analytics available", "ok": analytics_ok, "detail": analytics_detail},
        {"label": "AI available", "ok": analysis_runs > 0,
         "detail": "%d analysis run(s)" % analysis_runs},
    ]

    overall = "HEALTHY"
    if not source_rows or (last_import_status == "FAILED") or not analytics_ok:
        overall = "ERROR"
    elif not has_data or last_import_status == "PARTIAL" or not external_ready or analysis_runs == 0:
        overall = "WARNING"

    return {
        "overall": overall,
        "stages": stages,
        "checks": checks,
        "generated_at": _now().isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------------------
# Freshness
# ---------------------------------------------------------------------------

def freshness(db_path: str = DEFAULT_DB_PATH) -> dict:
    """Data freshness from the latest successful import timestamp.

    No timestamp -> UNKNOWN (never assumed). Thresholds documented in the
    module constants.
    """
    conn = open_db(db_path)
    try:
        latest = conn.execute(
            "SELECT MAX(completed_at) AS ts FROM data_imports "
            "WHERE status IN ('COMPLETED','PARTIAL')"
        ).fetchone()["ts"]
    finally:
        conn.close()

    parsed = _parse_ts(latest)
    if parsed is None:
        return {"latest_data_at": None, "age_seconds": None, "age_label": None,
                "status": "UNKNOWN", "detail": "No successful import recorded yet."}
    age = (_now() - parsed).total_seconds()
    if age < FRESH_MAX_SECONDS:
        status = "FRESH"
    elif age < RECENT_MAX_SECONDS:
        status = "RECENT"
    elif age < STALE_MAX_SECONDS:
        status = "STALE"
    else:
        status = "UNKNOWN"
    return {
        "latest_data_at": latest,
        "age_seconds": round(age, 1),
        "age_label": _fmt_age(age),
        "status": status,
        "detail": "Latest data %s ago (thresholds: FRESH < 24h, RECENT < 7d, STALE < 30d)."
                  % _fmt_age(age),
    }


# ---------------------------------------------------------------------------
# Data quality panel (reuses the single Phase 4 formula)
# ---------------------------------------------------------------------------

def quality_panel(db_path: str = DEFAULT_DB_PATH) -> dict:
    """Aggregated quality across imports, using the exact Phase 4 formula.

    The overall score is the record-count-weighted mean of each import's
    ``quality_report`` score (transparent and deterministic). Completeness
    (missing required fields) is not stored per import, so it is reported
    as ``None`` — the UI renders \"Not available\" rather than inventing it.
    """
    conn = open_db(db_path)
    try:
        rows = conn.execute(
            "SELECT id, dataset_name, record_count, successful_records, "
            " failed_records, duplicate_records, warnings_count, status, completed_at "
            "FROM data_imports ORDER BY id"
        ).fetchall()
    finally:
        conn.close()

    entries = []
    total_weight = 0
    weighted = 0.0
    totals = {"records": 0, "valid": 0, "invalid": 0, "duplicates": 0, "warnings": 0}
    for row in rows:
        r = dict(row)
        if r["record_count"] > 0:
            report = quality_report(
                total=r["record_count"],
                invalid=r["failed_records"],
                duplicates=r["duplicate_records"],
                warnings=r["warnings_count"],
            )
            weight = r["record_count"]
            weighted += report["score"] * weight
            total_weight += weight
        else:
            report = {"score": None, "valid_pct": None, "duplicate_pct": None, "warning_pct": None}
        totals["records"] += r["record_count"]
        totals["valid"] += r["successful_records"]
        totals["invalid"] += r["failed_records"]
        totals["duplicates"] += r["duplicate_records"]
        totals["warnings"] += r["warnings_count"]
        entries.append({
            "data_import_id": r["id"],
            "dataset_name": r["dataset_name"],
            "status": r["status"],
            "completed_at": r["completed_at"],
            "score": report["score"],
            "records": r["record_count"],
        })

    overall = round(weighted / total_weight, 1) if total_weight else None
    n = max(len(entries), 1)
    validity = round(100.0 - (totals["invalid"] / totals["records"] * 100), 1) if totals["records"] else None
    duplicate_rate = round(totals["duplicates"] / totals["records"] * 100, 1) if totals["records"] else None
    consistency = round(100.0 - (totals["warnings"] / totals["records"] * 100), 1) if totals["records"] else None

    return {
        "overall_score": overall,
        "import_count": len(entries),
        "totals": totals,
        "breakdown": {
            "validity": validity,
            "consistency": consistency,
            "duplicate_rate": duplicate_rate,
            "completeness": None,
        },
        "formula": "Phase 4 quality_report: 100 - 3.0*invalid%% - 2.0*duplicates%% - 0.5*warnings%%",
        "entries": entries,
    }


# ---------------------------------------------------------------------------
# Pipeline runs (import history with filters/search/pagination)
# ---------------------------------------------------------------------------

def pipeline_runs(
    db_path: str = DEFAULT_DB_PATH,
    *,
    source: Optional[int] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page: int = 1,
    per_page: int = 10,
) -> dict:
    """Import history as pipeline runs: real DataImport records, filtered and
    paginated server-side. Each run carries its deterministic quality score."""
    conn = open_db(db_path)
    try:
        where = []
        params = {}
        if source is not None:
            where.append("i.data_source_id = :source")
            params["source"] = source
        if status:
            where.append("i.status = :status")
            params["status"] = status
        if q:
            where.append(
                "(i.dataset_name LIKE :q OR i.file_name LIKE :q OR s.name LIKE :q)"
            )
            params["q"] = "%" + q + "%"
        if from_date:
            where.append("i.completed_at >= :from_date")
            params["from_date"] = from_date
        if to_date:
            where.append("i.completed_at <= :to_date")
            params["to_date"] = to_date
        clause = ("WHERE " + " AND ".join(where)) if where else ""

        count_row = conn.execute(
            "SELECT COUNT(*) AS n FROM data_imports i "
            "JOIN data_sources s ON s.id = i.data_source_id " + clause,
            params,
        ).fetchone()
        total = count_row["n"]

        rows = conn.execute(
            "SELECT i.id, i.dataset_name, i.file_name, i.file_type, i.record_count, "
            " i.successful_records, i.failed_records, i.duplicate_records, "
            " i.warnings_count, i.status, i.error_summary, i.started_at, "
            " i.completed_at, s.name AS source_name, s.type AS source_type "
            "FROM data_imports i JOIN data_sources s ON s.id = i.data_source_id "
            + clause + " ORDER BY i.id DESC LIMIT :limit OFFSET :offset",
            dict(params, limit=per_page, offset=(page - 1) * per_page),
        ).fetchall()

        sources = conn.execute("SELECT id, name FROM data_sources ORDER BY id").fetchall()
        statuses = conn.execute(
            "SELECT DISTINCT status FROM data_imports ORDER BY status"
        ).fetchall()
    finally:
        conn.close()

    runs = []
    for row in rows:
        r = dict(row)
        score = None
        if r["record_count"] > 0:
            score = quality_report(
                total=r["record_count"], invalid=r["failed_records"],
                duplicates=r["duplicate_records"], warnings=r["warnings_count"],
            )["score"]
        r["quality_score"] = score
        runs.append(r)

    return {
        "runs": runs,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, -(-total // per_page)),
        "sources": [dict(s) for s in sources],
        "statuses": [dict(s)["status"] for s in statuses],
    }


# ---------------------------------------------------------------------------
# Run detail / lineage
# ---------------------------------------------------------------------------

def run_detail(import_id: int, db_path: str = DEFAULT_DB_PATH):
    """Full lineage for one pipeline run:

        source -> import -> records -> database -> analytics -> analysis -> AI
    """
    conn = open_db(db_path)
    try:
        row = conn.execute(
            "SELECT i.*, s.name AS source_name, s.type AS source_type, "
            " s.status AS source_status "
            "FROM data_imports i JOIN data_sources s ON s.id = i.data_source_id "
            "WHERE i.id = :imp",
            {"imp": import_id},
        ).fetchone()
        if row is None:
            return None
        imp = dict(row)

        db_counts = {
            "transactions": conn.execute(
                "SELECT COUNT(*) AS n FROM ration_transactions WHERE source_import_id = :imp",
                {"imp": import_id}).fetchone()["n"],
            "beneficiaries": conn.execute(
                "SELECT COUNT(DISTINCT b.id) AS n FROM ration_transactions t "
                "JOIN beneficiaries b ON b.id = t.beneficiary_id "
                "WHERE t.source_import_id = :imp",
                {"imp": import_id}).fetchone()["n"],
            "inventory": conn.execute(
                "SELECT COUNT(*) AS n FROM inventory WHERE source_import_id = :imp",
                {"imp": import_id}).fetchone()["n"],
        }
        ai_insights = conn.execute(
            "SELECT COUNT(*) AS n FROM ai_insights WHERE source_import_id = :imp",
            {"imp": import_id}).fetchone()["n"]
        runs = get_analysis_runs_for_import(conn, import_id=import_id)
    finally:
        conn.close()

    quality = quality_report(
        total=imp["record_count"], invalid=imp["failed_records"],
        duplicates=imp["duplicate_records"], warnings=imp["warnings_count"],
    ) if imp["record_count"] > 0 else None

    return {
        "import": {
            "data_import_id": imp["id"],
            "dataset_name": imp["dataset_name"],
            "file_name": imp["file_name"],
            "file_type": imp["file_type"],
            "status": imp["status"],
            "error_summary": imp["error_summary"],
            "started_at": imp["started_at"],
            "completed_at": imp["completed_at"],
        },
        "source": {
            "data_source_id": imp.get("data_source_id"),
            "name": imp["source_name"],
            "type": imp["source_type"],
            "status": imp.get("source_status"),
        },
        "records": {
            "record_count": imp["record_count"],
            "successful_records": imp["successful_records"],
            "failed_records": imp["failed_records"],
            "duplicate_records": imp["duplicate_records"],
            "warnings_count": imp["warnings_count"],
            "quality": quality,
        },
        "database": db_counts,
        "analytics": {"available": True, "detail": "Phase 5 analytics query this import's records"},
        "analysis_runs": runs,
        "ai_insights": ai_insights,
    }


# ---------------------------------------------------------------------------
# Connection test (real probe, never faked)
# ---------------------------------------------------------------------------

def test_connection(
    source_id: int,
    *,
    db_path: str = DEFAULT_DB_PATH,
    request_host: Optional[str] = None,
    fetcher: Callable = http_get_bytes,
    timeout: float = 6.0,
) -> dict:
    """Probe one configured source and report the actual outcome.

    Auth-required sources without a server-side key are reported as
    NOT_CONFIGURED WITHOUT fetching (never claimed as connected). The probe
    is a single request (no retries) with a short timeout so the UI responds
    quickly. ``fetcher`` is injectable for tests.
    """
    checked_at = _now().isoformat(timespec="seconds")
    conn = open_db(db_path)
    try:
        source = get_data_source(conn, source_id)
    finally:
        conn.close()
    if source is None:
        return {"status": "error", "category": "UNKNOWN_SOURCE",
                "detail": "Unknown data source.", "checked_at": checked_at}
    profile = get_profile(source["name"])
    if profile is None:
        return {"status": "error", "category": "NOT_CONFIGURED",
                "detail": "No connector profile is registered for this source.",
                "checked_at": checked_at}

    from connectors.profiles import _ogd_api_key
    if profile.get("requires_auth") and not _ogd_api_key():
        return {
            "status": "not_configured", "category": "AUTH_NOT_CONFIGURED",
            "detail": "Connector is implemented, but no API key is configured "
                      "server-side (set %s). Connection was NOT tested."
                      % profile.get("auth_env_var"),
            "checked_at": checked_at,
            "source_name": source["name"],
        }

    base_url = source.get("base_url") or profile.get("base_url")
    if not base_url:
        return {"status": "error", "category": "NOT_CONFIGURED",
                "detail": "No endpoint URL is configured for this source.",
                "checked_at": checked_at}
    if base_url.startswith("/"):
        if not request_host:
            return {"status": "error", "category": "NOT_CONFIGURED",
                    "detail": "Relative source URL requires the request host.",
                    "checked_at": checked_at}
        url = "http://%s%s" % (request_host, base_url)
    else:
        url = base_url

    try:
        body = fetcher(url, timeout=timeout, max_attempts=1)
    except AuthError as exc:
        return {"status": "error", "category": "AUTH_FAILED",
                "detail": str(exc), "checked_at": checked_at, "source_name": source["name"]}
    except RateLimitError as exc:
        return {"status": "error", "category": "RATE_LIMITED",
                "detail": str(exc), "checked_at": checked_at, "source_name": source["name"]}
    except ConnectorTimeoutError as exc:
        return {"status": "error", "category": "TIMEOUT",
                "detail": str(exc), "checked_at": checked_at, "source_name": source["name"]}
    except UnreachableError as exc:
        return {"status": "error", "category": "UNREACHABLE",
                "detail": str(exc), "checked_at": checked_at, "source_name": source["name"]}
    except HttpStatusError as exc:
        return {"status": "error", "category": "HTTP_ERROR",
                "detail": str(exc), "checked_at": checked_at, "source_name": source["name"]}
    except ConnectorError as exc:
        return {"status": "error", "category": "ERROR",
                "detail": str(exc), "checked_at": checked_at, "source_name": source["name"]}
    except Exception:  # noqa: BLE001
        logger.error("Connection probe failed unexpectedly:", exc_info=True)
        return {"status": "error", "category": "ERROR",
                "detail": "The connection test failed for an unexpected reason.",
                "checked_at": checked_at, "source_name": source["name"]}

    return {"status": "ok", "category": "CONNECTION_OK",
            "detail": "Connection successful — received %d byte(s)." % len(body),
            "checked_at": checked_at, "source_name": source["name"]}
