"""RationRight — database analytics service (Phase 5).

The dashboard's numbers come from HERE, never from the frontend: every metric
is an SQL aggregation over the normalized database (``data/rationright.db``),
so a change to a database record changes the dashboard on the next fetch.

The database contains the seeded synthetic demo dataset (import source
"Synthetic Demo Dataset") plus any datasets uploaded through Phase 3/4. All
analytics operate over the full database — demo data is preserved and real
data simply adds to the aggregates, with per-source provenance reported so the
UI can show exactly which imports are contributing.

Supported queries
-----------------
- ``overview``          KPI cards + provenance (time-range aware)
- ``distribution``      by commodity / district / center / status + trend
- ``inventory``         stock, consumption, days remaining, risk status
- ``beneficiaries``     searchable, filterable, paginated registry
- ``fps``               centers with distribution activity
- ``alerts``            deterministic operational alerts (no AI)
- ``transactions``      paginated transaction feed (agent-contract shape)

Deterministic rules documented here (never computed in the UI):

- **Inventory risk** — ``days_remaining = current_stock * 30 / monthly_consumption``
  (30-day month assumption). ``CRITICAL`` below 15 days, ``WARNING`` below 30
  days, otherwise ``HEALTHY``; ``UNKNOWN`` when no consumption is recorded.
- **Low-stock alert** — ``current_stock < reorder_threshold`` → HIGH.
- **High failure-rate alert** — at an FPS, ``failed / (failed + completed) >= 10%``
  with at least 5 transactions → MEDIUM.
- **No recent distribution alert** — an FPS with zero completed transactions
  in the last 30 days → LOW.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from database import DEFAULT_DB_PATH, as_agent_transaction, open_db

RANGES = ("today", "7d", "30d", "all", "custom")
RANGE_LABELS = {
    "today": "Today",
    "7d": "Last 7 days",
    "30d": "Last 30 days",
    "all": "All time",
    "custom": "Custom range",
}
GRANULARITIES = ("day", "week", "month")
BENEFICIARY_SORTS = (
    "external_reference", "transaction_count", "total_quantity",
    "last_transaction", "district",
)
BENEFICIARY_DEFAULT_SORT = "external_reference"
BENEFICIARY_SORTS_SQL = {
    "external_reference": "b.external_reference COLLATE NOCASE",
    "transaction_count": "transaction_count DESC",
    "total_quantity": "total_quantity DESC",
    "last_transaction": "last_transaction DESC",
    "district": "b.district COLLATE NOCASE",
}

# --- documented thresholds -------------------------------------------------
INVENTORY_CRITICAL_DAYS = 15
INVENTORY_WARNING_DAYS = 30
FAILURE_RATE_THRESHOLD = 0.10
FAILURE_MIN_TRANSACTIONS = 5
NO_RECENT_DISTRIBUTION_DAYS = 30

MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 10


class AnalyticsError(ValueError):
    """Raised for invalid analytics parameters (mapped to HTTP 400)."""


# ---------------------------------------------------------------------------
# Range handling
# ---------------------------------------------------------------------------


def resolve_range(range_key: str, from_date: str = None, to_date: str = None):
    """Return ``(start_iso, end_iso)`` — inclusive, ``None`` when unfiltered.

    ``range_key`` must be one of RANGES. ``custom`` requires both ``from_date``
    and ``to_date`` as ISO dates (``YYYY-MM-DD``) with from <= to. Date-only
    comparison is used because the database stores both ``YYYY-MM-DD`` and
    ``YYYY-MM-DDTHH:MM:SS`` values.
    """
    if range_key not in RANGES:
        raise AnalyticsError(
            "Invalid range %r. Supported: %s" % (range_key, ", ".join(RANGES))
        )
    if range_key == "all":
        return None, None
    if range_key == "custom":
        if not from_date or not to_date:
            raise AnalyticsError("Custom range requires both 'from' and 'to' (YYYY-MM-DD).")
        try:
            date.fromisoformat(from_date)
            date.fromisoformat(to_date)
        except (TypeError, ValueError):
            raise AnalyticsError("Invalid date. Use YYYY-MM-DD.")
        if from_date > to_date:
            raise AnalyticsError("'from' must not be after 'to'.")
        return from_date, to_date
    today = date.today().isoformat()
    days = {"today": 0, "7d": 6, "30d": 29}[range_key]
    start = (date.today() - timedelta(days=days)).isoformat()
    return start, today


def _date_clause(range_key: str, from_date: str = None, to_date: str = None):
    """SQL fragment + params filtering on ``substr(transaction_date, 1, 10)``."""
    start, end = resolve_range(range_key, from_date, to_date)
    if start is None:
        return "", {}
    return (
        " AND substr(transaction_date, 1, 10) BETWEEN :d_start AND :d_end",
        {"d_start": start, "d_end": end},
    )


def _require_page(page, per_page):
    try:
        page = int(page)
        per_page = int(per_page)
    except (TypeError, ValueError):
        raise AnalyticsError("page and per_page must be integers.")
    if page < 1:
        raise AnalyticsError("page must be >= 1.")
    if per_page < 1 or per_page > MAX_PAGE_SIZE:
        raise AnalyticsError("per_page must be between 1 and %d." % MAX_PAGE_SIZE)
    return page, per_page


# ---------------------------------------------------------------------------
# Overview KPIs
# ---------------------------------------------------------------------------


def overview(conn: sqlite3.Connection, range_key: str = "all",
             from_date: str = None, to_date: str = None) -> dict:
    clause, params = _date_clause(range_key, from_date, to_date)

    tx_row = conn.execute(
        "SELECT COUNT(*) AS n, "
        " COALESCE(SUM(quantity), 0) AS qty, "
        " COALESCE(SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END), 0) AS completed, "
        " COALESCE(SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END), 0) AS failed, "
        " COALESCE(SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END), 0) AS pending, "
        " COALESCE(SUM(CASE WHEN status = 'CANCELLED' THEN 1 ELSE 0 END), 0) AS cancelled "
        " FROM ration_transactions WHERE 1 = 1" + clause,
        params,
    ).fetchone()

    ben_row = conn.execute(
        "SELECT COUNT(*) AS n, "
        " COALESCE(SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END), 0) AS active "
        " FROM beneficiaries"
    ).fetchone()
    fps_row = conn.execute(
        "SELECT COUNT(*) AS n, "
        " COALESCE(SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END), 0) AS active "
        " FROM fps_centers"
    ).fetchone()
    district_row = conn.execute(
        "SELECT COUNT(DISTINCT district) AS n FROM beneficiaries "
        "WHERE district IS NOT NULL AND district != ''"
    ).fetchone()

    by_commodity = [
        dict(r) for r in conn.execute(
            "SELECT commodity, COALESCE(SUM(quantity), 0) AS quantity, COUNT(*) AS count "
            "FROM ration_transactions WHERE 1 = 1" + clause +
            " GROUP BY commodity ORDER BY quantity DESC",
            params,
        )
    ]
    by_status = {
        "COMPLETED": tx_row["completed"], "FAILED": tx_row["failed"],
        "PENDING": tx_row["pending"], "CANCELLED": tx_row["cancelled"],
    }
    commodities = sorted({r["commodity"] for r in by_commodity if r["commodity"]})

    sources = [
        dict(r) for r in conn.execute(
            "SELECT s.id, s.name, s.type, "
            " COUNT(t.id) AS transaction_count, "
            " MAX(i.completed_at) AS last_import_at "
            "FROM data_sources s "
            "LEFT JOIN data_imports i ON i.data_source_id = s.id "
            "LEFT JOIN ration_transactions t ON t.source_import_id = i.id "
            "GROUP BY s.id ORDER BY s.id"
        )
    ]
    last_import = None
    if sources:
        with_imports = [s for s in sources if s["last_import_at"]]
        if with_imports:
            newest = max(with_imports, key=lambda s: s["last_import_at"])
            last_import = {
                "source_id": newest["id"],
                "source_name": newest["name"],
                "last_import_at": newest["last_import_at"],
            }

    return {
        "range": range_key,
        "range_label": RANGE_LABELS.get(range_key, range_key),
        "total_beneficiaries": ben_row["n"],
        "active_beneficiaries": ben_row["active"],
        "total_fps_centers": fps_row["n"],
        "active_fps_centers": fps_row["active"],
        "total_transactions": tx_row["n"],
        "ration_distributed_kg": round(tx_row["qty"], 2),
        "distribution_count": tx_row["n"],
        "by_status": by_status,
        "districts_covered": district_row["n"],
        "commodities_distributed": commodities,
        "by_commodity": by_commodity,
        "data_sources": sources,
        "last_import": last_import,
    }


# ---------------------------------------------------------------------------
# Distribution analytics
# ---------------------------------------------------------------------------


def distribution(conn: sqlite3.Connection, range_key: str = "all",
                 granularity: str = "day",
                 from_date: str = None, to_date: str = None) -> dict:
    if granularity not in GRANULARITIES:
        raise AnalyticsError(
            "Invalid granularity %r. Supported: %s" % (granularity, ", ".join(GRANULARITIES))
        )
    clause, params = _date_clause(range_key, from_date, to_date)

    total_quantity = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) AS q FROM ration_transactions WHERE 1 = 1" + clause,
        params,
    ).fetchone()["q"]

    by_commodity = [
        dict(r) for r in conn.execute(
            "SELECT commodity, COALESCE(SUM(quantity), 0) AS quantity, COUNT(*) AS count "
            "FROM ration_transactions WHERE 1 = 1" + clause +
            " GROUP BY commodity ORDER BY quantity DESC",
            params,
        )
    ]
    by_district = [
        dict(r) for r in conn.execute(
            "SELECT COALESCE(NULLIF(b.district, ''), 'Unknown') AS district, "
            " COALESCE(SUM(t.quantity), 0) AS quantity, COUNT(t.id) AS count "
            "FROM ration_transactions t "
            "LEFT JOIN beneficiaries b ON b.id = t.beneficiary_id "
            "WHERE 1 = 1" + clause +
            " GROUP BY district ORDER BY quantity DESC",
            params,
        )
    ]
    by_center = [
        dict(r) for r in conn.execute(
            "SELECT COALESCE(f.fps_code, 'Unknown') AS fps_code, "
            " COALESCE(SUM(t.quantity), 0) AS quantity, COUNT(t.id) AS count "
            "FROM ration_transactions t "
            "LEFT JOIN fps_centers f ON f.id = t.fps_center_id "
            "WHERE 1 = 1" + clause +
            " GROUP BY fps_code ORDER BY quantity DESC",
            params,
        )
    ]
    by_status = [
        dict(r) for r in conn.execute(
            "SELECT COALESCE(status, 'UNKNOWN') AS status, COUNT(*) AS count "
            "FROM ration_transactions WHERE 1 = 1" + clause +
            " GROUP BY status ORDER BY count DESC",
            params,
        )
    ]

    bucket_expr = {
        "day": "substr(transaction_date, 1, 10)",
        "week": "strftime('%Y-W%W', substr(transaction_date, 1, 10))",
        "month": "substr(transaction_date, 1, 7)",
    }[granularity]
    rows = conn.execute(
        ("SELECT %s AS bucket, commodity, COALESCE(SUM(quantity), 0) AS quantity "
         "FROM ration_transactions WHERE 1 = 1" + clause +
         " GROUP BY bucket, commodity ORDER BY bucket") % bucket_expr,
        params,
    ).fetchall()

    labels = []
    series = {}
    by_bucket = {}
    for row in rows:
        bucket = row["bucket"]
        if bucket not in by_bucket:
            by_bucket[bucket] = {}
            labels.append(bucket)
        by_bucket[bucket][row["commodity"]] = row["quantity"]
        series.setdefault(row["commodity"], {})
    commodities = sorted({r["commodity"] for r in by_commodity if r["commodity"]})
    trend = {
        "granularity": granularity,
        "labels": labels,
        "series": {
            commodity: [
                round(by_bucket.get(label, {}).get(commodity, 0.0), 2)
                for label in labels
            ]
            for commodity in commodities
        },
    }

    return {
        "range": range_key,
        "range_label": RANGE_LABELS.get(range_key, range_key),
        "granularity": granularity,
        "total_quantity": round(total_quantity, 2),
        "by_commodity": by_commodity,
        "by_district": by_district,
        "by_center": by_center,
        "by_status": by_status,
        "trend": trend,
    }


# ---------------------------------------------------------------------------
# Inventory analytics
# ---------------------------------------------------------------------------


def inventory(conn: sqlite3.Connection) -> dict:
    by_commodity = []
    for r in conn.execute(
        "SELECT commodity, "
        " COALESCE(SUM(current_stock), 0) AS current_stock, "
        " COALESCE(SUM(monthly_consumption), 0) AS monthly_consumption, "
        " MIN(reorder_threshold) AS reorder_threshold, "
        " COUNT(DISTINCT fps_center_id) AS center_count "
        "FROM inventory GROUP BY commodity ORDER BY current_stock DESC"
    ):
        stock = r["current_stock"]
        consumption = r["monthly_consumption"]
        if consumption and consumption > 0:
            days_remaining = round(stock * 30.0 / consumption, 1)
            status = (
                "CRITICAL" if days_remaining < INVENTORY_CRITICAL_DAYS
                else "WARNING" if days_remaining < INVENTORY_WARNING_DAYS
                else "HEALTHY"
            )
        else:
            days_remaining = None
            status = "UNKNOWN"
        by_commodity.append({
            "commodity": r["commodity"],
            "current_stock": stock,
            "monthly_consumption": consumption,
            "reorder_threshold": r["reorder_threshold"],
            "center_count": r["center_count"],
            "days_remaining": days_remaining,
            "status": status,
        })

    items = [dict(r) for r in conn.execute(
        "SELECT i.id, i.commodity, i.current_stock, i.monthly_consumption, "
        " i.reorder_threshold, COALESCE(f.fps_code, 'Unknown') AS fps_code, "
        " substr(i.last_updated, 1, 10) AS last_updated "
        "FROM inventory i LEFT JOIN fps_centers f ON f.id = i.fps_center_id "
        "ORDER BY i.commodity, fps_code"
    )]
    low_stock = [
        item for item in items
        if item["reorder_threshold"] is not None
        and item["current_stock"] < item["reorder_threshold"]
    ]
    by_center = [
        dict(r) for r in conn.execute(
            "SELECT COALESCE(f.fps_code, 'Unknown') AS fps_code, "
            " COALESCE(SUM(i.current_stock), 0) AS current_stock, COUNT(i.id) AS items "
            "FROM inventory i LEFT JOIN fps_centers f ON f.id = i.fps_center_id "
            "GROUP BY fps_code ORDER BY current_stock DESC"
        )
    ]

    return {
        "total_stock_kg": round(sum(r["current_stock"] for r in by_commodity), 2),
        "by_commodity": by_commodity,
        "items": items,
        "by_center": by_center,
        "low_stock_items": low_stock,
        "critical_commodities": [
            r for r in by_commodity if r["status"] in ("CRITICAL", "WARNING")
        ],
        "thresholds": {
            "critical_days": INVENTORY_CRITICAL_DAYS,
            "warning_days": INVENTORY_WARNING_DAYS,
            "method": "days_remaining = current_stock * 30 / monthly_consumption",
        },
    }


# ---------------------------------------------------------------------------
# Beneficiary analytics (server-side search / filter / pagination / sort)
# ---------------------------------------------------------------------------


def beneficiaries(conn: sqlite3.Connection, *, q: str = None, state: str = None,
                  district: str = None, category: str = None, status: str = None,
                  page: int = 1, per_page: int = DEFAULT_PAGE_SIZE,
                  sort: str = BENEFICIARY_DEFAULT_SORT) -> dict:
    page, per_page = _require_page(page, per_page)
    if sort not in BENEFICIARY_SORTS:
        raise AnalyticsError(
            "Invalid sort %r. Supported: %s" % (sort, ", ".join(BENEFICIARY_SORTS))
        )

    where = []
    params = {}
    if q:
        where.append("b.external_reference LIKE :q ESCAPE '\\'")
        params["q"] = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    for field, column in (("state", "b.state"), ("district", "b.district"),
                          ("ration_category", "b.ration_category"), ("status", "b.status")):
        value = locals().get(field)
        if value and value != "all":
            where.append("%s = :%s" % (column, field))
            params[field] = value
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    base = (
        "SELECT b.id, b.external_reference, b.state, b.district, b.block, "
        " b.ration_category, b.family_size, b.status, "
        " COUNT(t.id) AS transaction_count, "
        " COALESCE(SUM(t.quantity), 0) AS total_quantity, "
        " MIN(substr(t.transaction_date, 1, 10)) AS first_transaction, "
        " MAX(substr(t.transaction_date, 1, 10)) AS last_transaction, "
        " AVG(t.latitude) AS avg_latitude, AVG(t.longitude) AS avg_longitude "
        "FROM beneficiaries b LEFT JOIN ration_transactions t ON t.beneficiary_id = b.id"
    )
    group_sql = " GROUP BY b.id"
    total = conn.execute(
        "SELECT COUNT(*) AS n FROM (" + base + where_sql + group_sql + ")",
        params,
    ).fetchone()["n"]
    active = conn.execute(
        "SELECT COUNT(*) AS n FROM beneficiaries WHERE status = 'ACTIVE'"
    ).fetchone()["n"]

    order_sql = " ORDER BY " + BENEFICIARY_SORTS_SQL[sort]
    if sort != "external_reference":
        order_sql += ", b.external_reference COLLATE NOCASE"
    rows = conn.execute(
        base + where_sql + group_sql + order_sql +
        " LIMIT :limit OFFSET :offset",
        {**params, "limit": per_page, "offset": (page - 1) * per_page},
    ).fetchall()
    result_rows = []
    for r in rows:
        row = dict(r)
        row["avg_latitude"] = round(row["avg_latitude"], 4) if row["avg_latitude"] is not None else None
        row["avg_longitude"] = round(row["avg_longitude"], 4) if row["avg_longitude"] is not None else None
        result_rows.append(row)

    def distinct(column):
        return [
            r[0] for r in conn.execute(
                "SELECT DISTINCT %s FROM beneficiaries WHERE %s IS NOT NULL AND %s != '' "
                "ORDER BY 1" % (column, column, column)
            )
        ]

    return {
        "total": total,
        "active": active,
        "page": page,
        "per_page": per_page,
        "sort": sort,
        "rows": result_rows,
        "filters": {
            "states": distinct("state"),
            "districts": distinct("district"),
            "categories": distinct("ration_category"),
            "statuses": [r[0] for r in conn.execute(
                "SELECT DISTINCT status FROM beneficiaries ORDER BY 1"
            )],
        },
    }


def beneficiary_detail(conn: sqlite3.Connection, external_reference: str) -> dict:
    """One beneficiary plus its transactions (agent-contract shape)."""
    ben = conn.execute(
        "SELECT * FROM beneficiaries WHERE external_reference = :ref",
        {"ref": external_reference},
    ).fetchone()
    if ben is None:
        raise AnalyticsError("Beneficiary %r was not found." % external_reference)
    transactions = [
        as_agent_transaction(dict(r)) for r in conn.execute(
            "SELECT t.*, b.external_reference AS beneficiary_external_reference "
            "FROM ration_transactions t "
            "LEFT JOIN beneficiaries b ON b.id = t.beneficiary_id "
            "WHERE t.beneficiary_id = :id ORDER BY t.transaction_date",
            {"id": ben["id"]},
        )
    ]
    return {"beneficiary": dict(ben), "transactions": transactions}


# ---------------------------------------------------------------------------
# FPS analytics
# ---------------------------------------------------------------------------


def fps(conn: sqlite3.Connection) -> dict:
    centers = []
    for r in conn.execute(
        "SELECT f.id, f.fps_code, f.name, f.state, f.district, f.location, "
        " f.latitude, f.longitude, f.capacity, f.status, "
        " COUNT(t.id) AS transaction_count, "
        " COALESCE(SUM(t.quantity), 0) AS quantity_distributed, "
        " (SELECT COUNT(*) FROM inventory i WHERE i.fps_center_id = f.id) AS inventory_count "
        "FROM fps_centers f LEFT JOIN ration_transactions t ON t.fps_center_id = f.id "
        "GROUP BY f.id ORDER BY quantity_distributed DESC"
    ):
        row = dict(r)
        row["latitude"] = round(row["latitude"], 4) if row["latitude"] is not None else None
        row["longitude"] = round(row["longitude"], 4) if row["longitude"] is not None else None
        centers.append(row)
    active = sum(1 for c in centers if c["status"] == "ACTIVE")
    return {
        "total": len(centers),
        "active": active,
        "centers": centers,
        "total_transactions": sum(c["transaction_count"] for c in centers),
        "total_quantity_kg": round(sum(c["quantity_distributed"] for c in centers), 2),
    }


# ---------------------------------------------------------------------------
# Deterministic operational alerts (no AI)
# ---------------------------------------------------------------------------


def _next_alert_id():
    # deterministic ids: sequential per request (sorted output)
    counter = [0]

    def _make(prefix, key):
        counter[0] += 1
        return "OP-%s-%03d" % (prefix, counter[0])

    return _make


def operational_alerts(conn: sqlite3.Connection,
                       recent_days: int = NO_RECENT_DISTRIBUTION_DAYS) -> dict:
    alerts = []
    make_id = _next_alert_id()

    # 1. LOW INVENTORY — current_stock < reorder_threshold
    for r in conn.execute(
        "SELECT i.commodity, i.current_stock, i.reorder_threshold, i.fps_center_id, "
        " COALESCE(f.fps_code, 'Unknown') AS fps_code "
        "FROM inventory i LEFT JOIN fps_centers f ON f.id = i.fps_center_id "
        "WHERE i.reorder_threshold IS NOT NULL AND i.current_stock < i.reorder_threshold "
        "ORDER BY (i.reorder_threshold - i.current_stock) DESC"
    ):
        alerts.append({
            "alert_id": make_id("INV", r["fps_code"]),
            "category": "LOW_INVENTORY",
            "severity": "high",
            "title": "Inventory below reorder threshold",
            "message": "Stock of %s at %s is below the reorder threshold "
                       "(%.2f < %.2f)." % (r["commodity"], r["fps_code"],
                                           r["current_stock"], r["reorder_threshold"]),
            "entity_type": "fps_center",
            "entity_id": r["fps_code"],
            "commodity": r["commodity"],
            "current_stock": r["current_stock"],
            "reorder_threshold": r["reorder_threshold"],
        })

    # 2. HIGH FAILURE RATE — per FPS
    for r in conn.execute(
        "SELECT COALESCE(f.fps_code, 'Unknown') AS fps_code, "
        " COALESCE(SUM(CASE WHEN t.status = 'FAILED' THEN 1 ELSE 0 END), 0) AS failed, "
        " COALESCE(SUM(CASE WHEN t.status IN ('COMPLETED','FAILED') THEN 1 ELSE 0 END), 0) AS total "
        "FROM ration_transactions t LEFT JOIN fps_centers f ON f.id = t.fps_center_id "
        "GROUP BY fps_code"
    ):
        total = r["total"]
        if total < FAILURE_MIN_TRANSACTIONS:
            continue
        rate = r["failed"] / total
        if rate >= FAILURE_RATE_THRESHOLD:
            alerts.append({
                "alert_id": make_id("FAIL", r["fps_code"]),
                "category": "HIGH_FAILURE_RATE",
                "severity": "medium",
                "title": "Transaction failure rate is elevated",
                "message": "%d of %d transactions at %s failed (%.0f%% >= %.0f%% threshold). "
                           "Requires human review." % (
                               r["failed"], total, r["fps_code"], rate * 100,
                               FAILURE_RATE_THRESHOLD * 100),
                "entity_type": "fps_center",
                "entity_id": r["fps_code"],
                "failed": r["failed"],
                "total": total,
                "failure_rate": round(rate, 4),
            })

    # 3. NO RECENT DISTRIBUTION — per FPS
    cutoff = (date.today() - timedelta(days=recent_days)).isoformat()
    for r in conn.execute(
        "SELECT f.id, f.fps_code, f.name, f.district, "
        " COALESCE(SUM(CASE WHEN t.status = 'COMPLETED' THEN 1 ELSE 0 END), 0) AS completed "
        "FROM fps_centers f LEFT JOIN ration_transactions t "
        "  ON t.fps_center_id = f.id AND substr(t.transaction_date, 1, 10) >= :cutoff "
        "GROUP BY f.id HAVING completed = 0",
        {"cutoff": cutoff},
    ):
        alerts.append({
            "alert_id": make_id("QUIET", r["fps_code"]),
            "category": "NO_RECENT_DISTRIBUTION",
            "severity": "low",
            "title": "No recent distribution activity detected",
            "message": "FPS %s (%s) has no completed transactions in the last "
                       "%d days. Verify the center is operating." % (
                           r["fps_code"], r["district"] or "district unknown",
                           recent_days),
            "entity_type": "fps_center",
            "entity_id": r["fps_code"],
            "recent_days": recent_days,
        })

    alerts.sort(key=lambda a: ({"high": 0, "medium": 1, "low": 2}.get(a["severity"], 3), a["alert_id"]))
    return {
        "generated_at": date.today().isoformat(),
        "recent_days": recent_days,
        "count": len(alerts),
        "alerts": alerts,
        "rules": {
            "LOW_INVENTORY": "current_stock < reorder_threshold",
            "HIGH_FAILURE_RATE": "failed / (failed + completed) >= 10% with >= 5 transactions",
            "NO_RECENT_DISTRIBUTION": "no completed transactions in the last %d days" % recent_days,
        },
    }


# ---------------------------------------------------------------------------
# Transaction feed
# ---------------------------------------------------------------------------


def transactions(conn: sqlite3.Connection, range_key: str = "all",
                 status: str = None, page: int = 1,
                 per_page: int = DEFAULT_PAGE_SIZE,
                 from_date: str = None, to_date: str = None) -> dict:
    page, per_page = _require_page(page, per_page)
    clause, params = _date_clause(range_key, from_date, to_date)
    if status:
        if status not in ("COMPLETED", "PENDING", "FAILED", "CANCELLED"):
            raise AnalyticsError(
                "Invalid status %r. Supported: COMPLETED, PENDING, FAILED, CANCELLED." % status
            )
        clause += " AND t.status = :status"
        params["status"] = status

    total = conn.execute(
        "SELECT COUNT(*) AS n FROM ration_transactions t WHERE 1 = 1" + clause,
        params,
    ).fetchone()["n"]
    rows = [
        as_agent_transaction(dict(r)) for r in conn.execute(
            "SELECT t.*, b.external_reference AS beneficiary_external_reference "
            "FROM ration_transactions t "
            "LEFT JOIN beneficiaries b ON b.id = t.beneficiary_id "
            "WHERE 1 = 1" + clause +
            " ORDER BY t.transaction_date, t.id LIMIT :limit OFFSET :offset",
            {**params, "limit": per_page, "offset": (page - 1) * per_page},
        )
    ]
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def analytics(db_path=DEFAULT_DB_PATH):
    """Context helper: open a connection for an analytics call."""
    return open_db(db_path)
