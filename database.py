"""RationRight — real-data database foundation (Phase 2).

Prepares RationAI's data layer so real PDS/ration datasets can be imported in
later phases. This phase deliberately does NOT add CSV upload, government API
adapters, or UI changes — it only establishes the normalized schema, its
relationships, and a seed path for the existing synthetic dataset.

Technology decision
-------------------
The project is strictly standard-library Python with no third-party
dependencies and no PostgreSQL server configured anywhere. The documented
architecture rule is "use the simplest framework that supports tools,
structured outputs, testing, independent execution, and integration", so the
database is the Python stdlib ``sqlite3`` module. A single SQLite file
(``data/rationright.db`` by default) needs no service, no ORM dependency, and
no credentials, matching every other component of this codebase. PostgreSQL
was not chosen because nothing is configured for it and introducing a service
would violate the MVP's zero-dependency rule. The repository functions below
are the only place SQL lives, so swapping to PostgreSQL later (if ever
required) is a contained change.

Normalized internal schema
--------------------------
External datasets may use different column names (``fps_id`` vs ``fps_code``,
``district_name`` vs ``district``). We never create a table per dataset: the
database stores ONE normalized schema and the future ingestion layer maps
external columns into it (``database.py`` functions are the target).

Models (all created here because no database existed before this phase):
    data_sources         — where data came from (API/CSV/XLSX/JSON/...)
    data_imports         — one row per import operation (dataset provenance)
    beneficiaries        — non-sensitive beneficiary records (IDs only)
    fps_centers          — Fair Price Shops / distribution centers
    ration_transactions  — distribution transactions, traceable to an import
    inventory            — stock levels per center/commodity
    ai_insights          — structured AI analysis results, traceable to an import

Relationships (foreign keys):
    data_sources 1─N data_imports 1─N ration_transactions
    data_imports 1─N ai_insights
    data_imports 1─N inventory
    beneficiaries 1─N ration_transactions
    fps_centers  1─N ration_transactions
    fps_centers  1─N inventory

Agent-contract compatibility
----------------------------
``ration_transactions`` stores ``latitude``/``longitude`` (nullable) even
though the Phase 2 spec did not list them: the existing Agent 1 / Agent 2
contracts compute time difference and haversine distance from transaction
records, so the normalized table must be able to reproduce the exact
transaction objects the agents consume. ``as_agent_transaction()`` /
``get_transactions_for_agent()`` return rows in the documented 7-field
transaction shape (plus coordinates), which is the reuse point where the
agents plug in during the real-data phases.

Privacy
-------
No Aadhaar numbers, biometrics, phone numbers, passwords, or names are stored.
Beneficiaries are external references (e.g. ``BEN001``) only.

Usage::

    from database import open_db, seed_synthetic
    conn = open_db()                 # creates data/rationright.db + schema
    seed_synthetic(conn)             # import the Phase 1 synthetic dataset
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from scripts.validate_dataset import DEFAULT_DATASET_PATH, load_dataset

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "rationright.db"

# ---------------------------------------------------------------------------
# Enumerations — single source of truth, plain string constants (the project
# convention used by agents/pattern_config.py). Never hard-code these values
# elsewhere; import them.
# ---------------------------------------------------------------------------

DATA_SOURCE_TYPES = ("API", "CSV", "XLSX", "JSON", "GOVERNMENT_DATASET", "MANUAL")
DATA_SOURCE_STATUSES = ("ACTIVE", "INACTIVE", "ERROR", "SYNCING")
DATA_IMPORT_STATUSES = ("PENDING", "PROCESSING", "COMPLETED", "PARTIAL", "FAILED")
TRANSACTION_STATUSES = ("COMPLETED", "PENDING", "FAILED", "CANCELLED")
AI_INSIGHT_TYPES = (
    "DISTRIBUTION_ANOMALY",
    "INVENTORY_RISK",
    "DEMAND_FORECAST",
    "BENEFICIARY_ANOMALY",
    "OPERATIONAL_RISK",
    "RECOMMENDATION",
)
SEVERITY_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
BENEFICIARY_STATUSES = ("ACTIVE", "INACTIVE")
FPS_CENTER_STATUSES = ("ACTIVE", "INACTIVE")
DEFAULT_TRANSACTION_UNIT = "kg"

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS data_sources (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    name                    TEXT NOT NULL UNIQUE,
    type                    TEXT NOT NULL CHECK (type IN ('API','CSV','XLSX','JSON','GOVERNMENT_DATASET','MANUAL')),
    description             TEXT,
    status                  TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','INACTIVE','ERROR','SYNCING')),
    base_url                TEXT,
    last_sync_at            TEXT,
    last_successful_sync_at TEXT,
    last_error              TEXT,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS data_imports (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    data_source_id     INTEGER NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    dataset_name       TEXT NOT NULL,
    file_name          TEXT,
    file_type          TEXT,
    file_hash          TEXT,
    record_count       INTEGER NOT NULL DEFAULT 0,
    successful_records INTEGER NOT NULL DEFAULT 0,
    failed_records     INTEGER NOT NULL DEFAULT 0,
    duplicate_records  INTEGER NOT NULL DEFAULT 0,
    warnings_count     INTEGER NOT NULL DEFAULT 0,
    status             TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','PROCESSING','COMPLETED','PARTIAL','FAILED')),
    error_summary      TEXT,
    started_at         TEXT,
    completed_at       TEXT,
    created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS beneficiaries (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    external_reference TEXT NOT NULL UNIQUE,
    state              TEXT,
    district           TEXT,
    block              TEXT,
    ration_category    TEXT,
    family_size        INTEGER,
    status             TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','INACTIVE')),
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fps_centers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fps_code    TEXT NOT NULL UNIQUE,
    name        TEXT,
    state       TEXT,
    district    TEXT,
    block       TEXT,
    location    TEXT,
    latitude    REAL,
    longitude   REAL,
    capacity    REAL,
    status      TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','INACTIVE')),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ration_transactions (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    external_transaction_id TEXT NOT NULL UNIQUE,
    beneficiary_id         INTEGER REFERENCES beneficiaries(id) ON DELETE SET NULL,
    fps_center_id          INTEGER REFERENCES fps_centers(id) ON DELETE SET NULL,
    transaction_date       TEXT NOT NULL,
    commodity              TEXT NOT NULL,
    quantity               REAL NOT NULL CHECK (quantity > 0),
    unit                   TEXT NOT NULL DEFAULT 'kg',
    latitude               REAL,
    longitude              REAL,
    status                 TEXT NOT NULL DEFAULT 'COMPLETED' CHECK (status IN ('COMPLETED','PENDING','FAILED','CANCELLED')),
    source_import_id       INTEGER REFERENCES data_imports(id) ON DELETE SET NULL,
    created_at             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    fps_center_id      INTEGER REFERENCES fps_centers(id) ON DELETE SET NULL,
    commodity          TEXT NOT NULL,
    current_stock      REAL NOT NULL,
    monthly_consumption REAL,
    reorder_threshold  REAL,
    last_updated       TEXT,
    source_import_id   INTEGER REFERENCES data_imports(id) ON DELETE SET NULL,
    created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_insights (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    insight_type     TEXT NOT NULL CHECK (insight_type IN ('DISTRIBUTION_ANOMALY','INVENTORY_RISK','DEMAND_FORECAST','BENEFICIARY_ANOMALY','OPERATIONAL_RISK','RECOMMENDATION')),
    severity         TEXT NOT NULL CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    title            TEXT NOT NULL,
    description      TEXT,
    entity_type      TEXT,
    entity_id        TEXT,
    confidence       REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    recommendation   TEXT,
    evidence         TEXT,
    analysis_id      TEXT,
    source_import_id INTEGER REFERENCES data_imports(id) ON DELETE SET NULL,
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id    TEXT NOT NULL UNIQUE,
    data_import_id INTEGER REFERENCES data_imports(id) ON DELETE SET NULL,
    dataset_mode   TEXT NOT NULL DEFAULT 'synthetic' CHECK (dataset_mode IN ('synthetic','real')),
    status         TEXT NOT NULL DEFAULT 'COMPLETED' CHECK (status IN ('COMPLETED','FAILED','INSUFFICIENT_DATA')),
    anomaly_count  INTEGER NOT NULL DEFAULT 0,
    finding_count  INTEGER NOT NULL DEFAULT 0,
    case_count     INTEGER NOT NULL DEFAULT 0,
    alert_count    INTEGER NOT NULL DEFAULT 0,
    insight_count  INTEGER NOT NULL DEFAULT 0,
    analysis_types TEXT,
    filters        TEXT,
    timings        TEXT,
    duration_ms    INTEGER,
    summary        TEXT,
    error          TEXT,
    created_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_imports_source      ON data_imports(data_source_id);
CREATE INDEX IF NOT EXISTS idx_tx_beneficiary      ON ration_transactions(beneficiary_id);
CREATE INDEX IF NOT EXISTS idx_tx_center           ON ration_transactions(fps_center_id);
CREATE INDEX IF NOT EXISTS idx_tx_import           ON ration_transactions(source_import_id);
CREATE INDEX IF NOT EXISTS idx_tx_date             ON ration_transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_tx_commodity        ON ration_transactions(commodity);
CREATE INDEX IF NOT EXISTS idx_inventory_center    ON inventory(fps_center_id);
CREATE INDEX IF NOT EXISTS idx_inventory_import    ON inventory(source_import_id);
CREATE INDEX IF NOT EXISTS idx_insight_import      ON ai_insights(source_import_id);
CREATE INDEX IF NOT EXISTS idx_insight_entity      ON ai_insights(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_analysis_import     ON analysis_runs(data_import_id);

CREATE TABLE IF NOT EXISTS scenarios (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id        TEXT NOT NULL UNIQUE,
    data_import_id     INTEGER REFERENCES data_imports(id) ON DELETE SET NULL,
    entity_type        TEXT,
    entity_id          TEXT,
    commodity          TEXT,
    scenario_type      TEXT NOT NULL,
    parameters         TEXT,
    results            TEXT,
    ai_interpretation  TEXT,
    risk               TEXT,
    created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alert_rules (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    rule_type     TEXT NOT NULL,
    condition     TEXT NOT NULL,
    description   TEXT,
    severity      TEXT NOT NULL CHECK (severity IN ('INFO','LOW','MEDIUM','HIGH','CRITICAL')),
    enabled       INTEGER NOT NULL DEFAULT 1,
    threshold     REAL,
    threshold_unit TEXT,
    scope         TEXT NOT NULL DEFAULT 'GLOBAL',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id          TEXT NOT NULL UNIQUE,
    rule_type         TEXT NOT NULL,
    condition         TEXT NOT NULL,
    severity          TEXT NOT NULL CHECK (severity IN ('INFO','LOW','MEDIUM','HIGH','CRITICAL')),
    title             TEXT NOT NULL,
    description       TEXT,
    status            TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','ACKNOWLEDGED','RESOLVED','DISMISSED')),
    entity_type       TEXT,
    entity_id         TEXT,
    commodity         TEXT,
    current_value     REAL,
    threshold         REAL,
    evidence          TEXT,
    ai_explanation    TEXT,
    recommendation    TEXT,
    source_id         INTEGER REFERENCES data_sources(id) ON DELETE SET NULL,
    import_id         INTEGER REFERENCES data_imports(id) ON DELETE SET NULL,
    analysis_id       TEXT,
    created_at        TEXT NOT NULL,
    last_detected_at  TEXT NOT NULL,
    acknowledged_at   TEXT,
    resolved_at       TEXT,
    dismissed_at      TEXT,
    dismissed_reason  TEXT
);

CREATE INDEX IF NOT EXISTS idx_alerts_status   ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_type     ON alerts(rule_type);
CREATE INDEX IF NOT EXISTS idx_alerts_entity   ON alerts(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_alerts_created  ON alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_rules_type      ON alert_rules(rule_type, condition);

CREATE TABLE IF NOT EXISTS audit_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    actor         TEXT NOT NULL DEFAULT 'admin',
    action        TEXT NOT NULL,
    entity_type   TEXT,
    entity_id     TEXT,
    detail        TEXT,
    request_id    TEXT,
    created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);

CREATE TABLE IF NOT EXISTS reports (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id     TEXT NOT NULL UNIQUE,
    period_label  TEXT,
    source_label  TEXT,
    filters       TEXT,
    payload       TEXT,
    status        TEXT NOT NULL DEFAULT 'READY',
    created_at    TEXT NOT NULL
);
"""

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Current UTC time as an ISO-8601 string (naive, seconds precision)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path=DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a connection with row access and foreign keys enabled."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes if they do not already exist.

    Runs lightweight migrations for databases created before a schema change
    (e.g. the Phase 4 ``file_hash`` column on data_imports) so an existing
    ``data/rationright.db`` upgrades in place instead of being rebuilt.
    """
    conn.executescript(SCHEMA_SQL)
    run_columns = {row["name"] for row in conn.execute("PRAGMA table_info(analysis_runs)")}
    for column, ddl in (
        ("insight_count", "ALTER TABLE analysis_runs ADD COLUMN insight_count INTEGER NOT NULL DEFAULT 0"),
        ("analysis_types", "ALTER TABLE analysis_runs ADD COLUMN analysis_types TEXT"),
        ("filters", "ALTER TABLE analysis_runs ADD COLUMN filters TEXT"),
        ("timings", "ALTER TABLE analysis_runs ADD COLUMN timings TEXT"),
        ("duration_ms", "ALTER TABLE analysis_runs ADD COLUMN duration_ms INTEGER"),
    ):
        if column not in run_columns:
            conn.execute(ddl)
    insight_columns = {row["name"] for row in conn.execute("PRAGMA table_info(ai_insights)")}
    if "evidence" not in insight_columns:
        conn.execute("ALTER TABLE ai_insights ADD COLUMN evidence TEXT")
    if "analysis_id" not in insight_columns:
        conn.execute("ALTER TABLE ai_insights ADD COLUMN analysis_id TEXT")
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(data_imports)")}
    if "file_hash" not in columns:
        conn.execute("ALTER TABLE data_imports ADD COLUMN file_hash TEXT")
    if "warnings_count" not in columns:
        conn.execute(
            "ALTER TABLE data_imports ADD COLUMN warnings_count INTEGER NOT NULL DEFAULT 0"
        )
    source_columns = {row["name"] for row in conn.execute("PRAGMA table_info(data_sources)")}
    if "base_url" not in source_columns:
        conn.execute("ALTER TABLE data_sources ADD COLUMN base_url TEXT")
    if "last_successful_sync_at" not in source_columns:
        conn.execute("ALTER TABLE data_sources ADD COLUMN last_successful_sync_at TEXT")
    if "last_error" not in source_columns:
        conn.execute("ALTER TABLE data_sources ADD COLUMN last_error TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_imports_hash ON data_imports(file_hash)"
    )
    _migrate_data(conn)
    conn.commit()


def _migrate_data(conn: sqlite3.Connection) -> None:
    """Idempotent data migrations for databases seeded before a later phase.

    Phase 5: legacy imports created before the Phase 4 commodity
    normalization stored mixed-case commodities (e.g. ``Rice`` vs ``rice``),
    which would fragment analytics. Normalize existing rows to the canonical
    lowercase form. Synthetic rows are already lowercase; uploads from
    Phase 4+ are normalized at import time — this only touches legacy rows.
    """
    conn.execute(
        "UPDATE ration_transactions SET commodity = lower(commodity) "
        "WHERE commodity != lower(commodity) AND commodity IS NOT NULL"
    )


def open_db(db_path=DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Connect to ``db_path`` and ensure the schema exists (creates file/dirs)."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    init_db(conn)
    return conn


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------


def _require(value, allowed, field: str) -> None:
    if value not in allowed:
        raise ValueError(
            "%s must be one of %s, got %r" % (field, tuple(allowed), value)
        )


def _optional_number(value, field: str, low=None, high=None):
    """Validate an optional numeric field; returns the value (or None)."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("%s must be a number, got %r" % (field, value))
    if low is not None and value < low:
        raise ValueError("%s must be >= %s, got %r" % (field, low, value))
    if high is not None and value > high:
        raise ValueError("%s must be <= %s, got %r" % (field, high, value))
    return value


# ---------------------------------------------------------------------------
# DataSource
# ---------------------------------------------------------------------------


def insert_data_source(
    conn: sqlite3.Connection,
    *,
    name: str,
    source_type: str,
    description: Optional[str] = None,
    status: str = "ACTIVE",
    last_sync_at: Optional[str] = None,
    base_url: Optional[str] = None,
) -> int:
    """Insert a data source; returns its id. ``name`` must be unique."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("data source name must be a non-empty string")
    _require(source_type, DATA_SOURCE_TYPES, "data source type")
    _require(status, DATA_SOURCE_STATUSES, "data source status")
    now = _now_iso()
    cur = conn.execute(
        "INSERT INTO data_sources "
        "(name, type, description, status, base_url, last_sync_at, created_at, updated_at) "
        "VALUES (:name, :type, :description, :status, :base_url, :last_sync_at, :created_at, :updated_at)",
        {
            "name": name.strip(),
            "type": source_type,
            "description": description,
            "status": status,
            "base_url": base_url,
            "last_sync_at": last_sync_at,
            "created_at": now,
            "updated_at": now,
        },
    )
    return cur.lastrowid


def get_data_source_by_name(conn: sqlite3.Connection, name: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM data_sources WHERE name = :name", {"name": name}
    ).fetchone()
    return dict(row) if row is not None else None


def get_data_source(conn: sqlite3.Connection, data_source_id: int) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM data_sources WHERE id = :id", {"id": data_source_id}
    ).fetchone()
    return dict(row) if row is not None else None


def list_data_sources(conn: sqlite3.Connection) -> list:
    rows = conn.execute("SELECT * FROM data_sources ORDER BY id").fetchall()
    return [dict(row) for row in rows]


def set_data_source_status(
    conn: sqlite3.Connection, data_source_id: int, status: str
) -> None:
    _require(status, DATA_SOURCE_STATUSES, "data source status")
    conn.execute(
        "UPDATE data_sources SET status = :status, updated_at = :now WHERE id = :id",
        {"status": status, "now": _now_iso(), "id": data_source_id},
    )


def update_data_source_sync(
    conn: sqlite3.Connection,
    data_source_id: int,
    *,
    status: str,
    last_sync_at: Optional[str] = None,
    last_successful_sync_at: Optional[str] = None,
    last_error: Optional[str] = None,
) -> None:
    """Record the outcome of a sync attempt on a data source (Phase 7).

    ``status`` uses the existing conventions (ACTIVE = healthy/connected,
    ERROR = last sync failed, SYNCING = in progress, INACTIVE = not
    configured). ``last_sync_at`` records every attempt; the successful
    timestamp and last error are tracked separately so the UI can show
    "last successful update" even after a failure.
    """
    _require(status, DATA_SOURCE_STATUSES, "data source status")
    conn.execute(
        "UPDATE data_sources SET status = :status, "
        " last_sync_at = COALESCE(:last_sync_at, last_sync_at), "
        " last_successful_sync_at = COALESCE(:last_successful_sync_at, last_successful_sync_at), "
        " last_error = :last_error, updated_at = :now "
        "WHERE id = :id",
        {
            "status": status,
            "last_sync_at": last_sync_at,
            "last_successful_sync_at": last_successful_sync_at,
            "last_error": last_error,
            "now": _now_iso(),
            "id": data_source_id,
        },
    )


# ---------------------------------------------------------------------------
# DataImport
# ---------------------------------------------------------------------------


def insert_data_import(
    conn: sqlite3.Connection,
    *,
    data_source_id: int,
    dataset_name: str,
    file_name: Optional[str] = None,
    file_type: Optional[str] = None,
    file_hash: Optional[str] = None,
    record_count: int = 0,
    successful_records: int = 0,
    failed_records: int = 0,
    duplicate_records: int = 0,
    warnings_count: int = 0,
    status: str = "PENDING",
    error_summary: Optional[str] = None,
    started_at: Optional[str] = None,
    completed_at: Optional[str] = None,
) -> int:
    """Insert one import operation; returns its id. Records provenance for
    every row imported and every AI insight later derived from this data.
    ``file_hash`` (SHA-256 of the uploaded bytes) makes repeated imports of
    the exact same dataset detectable (Phase 4 idempotency)."""
    if not isinstance(dataset_name, str) or not dataset_name.strip():
        raise ValueError("dataset_name must be a non-empty string")
    _require(status, DATA_IMPORT_STATUSES, "data import status")
    for field, value in (
        ("record_count", record_count),
        ("successful_records", successful_records),
        ("failed_records", failed_records),
        ("duplicate_records", duplicate_records),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("%s must be a non-negative integer" % field)
    cur = conn.execute(
        "INSERT INTO data_imports "
        "(data_source_id, dataset_name, file_name, file_type, file_hash, record_count, "
        " successful_records, failed_records, duplicate_records, warnings_count, status, "
        " error_summary, started_at, completed_at, created_at) "
        "VALUES (:data_source_id, :dataset_name, :file_name, :file_type, :file_hash, :record_count, "
        " :successful_records, :failed_records, :duplicate_records, :warnings_count, :status, "
        " :error_summary, :started_at, :completed_at, :created_at)",
        {
            "data_source_id": data_source_id,
            "dataset_name": dataset_name.strip(),
            "file_name": file_name,
            "file_type": file_type,
            "file_hash": file_hash,
            "record_count": record_count,
            "successful_records": successful_records,
            "failed_records": failed_records,
            "duplicate_records": duplicate_records,
            "warnings_count": warnings_count,
            "status": status,
            "error_summary": error_summary,
            "started_at": started_at,
            "completed_at": completed_at,
            "created_at": _now_iso(),
        },
    )
    return cur.lastrowid


def get_import_by_hash(conn: sqlite3.Connection, file_hash: str) -> Optional[dict]:
    """Return the most recent completed/partial import for a file hash, or
    None. Used to detect repeated uploads of the exact same dataset."""
    row = conn.execute(
        "SELECT i.*, s.name AS source_name "
        "FROM data_imports i JOIN data_sources s ON s.id = i.data_source_id "
        "WHERE i.file_hash = :hash AND i.status IN ('COMPLETED','PARTIAL') "
        "ORDER BY i.id DESC LIMIT 1",
        {"hash": file_hash},
    ).fetchone()
    return dict(row) if row is not None else None


def get_data_import(conn: sqlite3.Connection, import_id: int) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM data_imports WHERE id = :id", {"id": import_id}
    ).fetchone()
    return dict(row) if row is not None else None


def get_imports_for_source(
    conn: sqlite3.Connection, data_source_id: int
) -> list:
    rows = conn.execute(
        "SELECT * FROM data_imports WHERE data_source_id = :sid ORDER BY id",
        {"sid": data_source_id},
    ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Beneficiary
# ---------------------------------------------------------------------------


def upsert_beneficiary(
    conn: sqlite3.Connection,
    *,
    external_reference: str,
    state: Optional[str] = None,
    district: Optional[str] = None,
    block: Optional[str] = None,
    ration_category: Optional[str] = None,
    family_size: Optional[int] = None,
    status: str = "ACTIVE",
) -> int:
    """Insert a beneficiary or update an existing one (same external
    reference). Returns the internal id. Non-sensitive fields only — never
    store Aadhaar, biometrics, phones, or passwords."""
    if not isinstance(external_reference, str) or not external_reference.strip():
        raise ValueError("external_reference must be a non-empty string")
    _require(status, BENEFICIARY_STATUSES, "beneficiary status")
    if family_size is not None and (
        isinstance(family_size, bool) or not isinstance(family_size, int) or family_size <= 0
    ):
        raise ValueError("family_size must be a positive integer or None")
    now = _now_iso()
    conn.execute(
        "INSERT INTO beneficiaries "
        "(external_reference, state, district, block, ration_category, family_size, status, created_at, updated_at) "
        "VALUES (:er, :state, :district, :block, :cat, :fs, :status, :now, :now) "
        "ON CONFLICT(external_reference) DO UPDATE SET "
        "  state = excluded.state, district = excluded.district, block = excluded.block, "
        "  ration_category = excluded.ration_category, family_size = excluded.family_size, "
        "  status = excluded.status, updated_at = excluded.updated_at",
        {
            "er": external_reference.strip(),
            "state": state,
            "district": district,
            "block": block,
            "cat": ration_category,
            "fs": family_size,
            "status": status,
            "now": now,
        },
    )
    row = conn.execute(
        "SELECT id FROM beneficiaries WHERE external_reference = :er",
        {"er": external_reference.strip()},
    ).fetchone()
    return row["id"]


def get_beneficiary_by_external_ref(
    conn: sqlite3.Connection, external_reference: str
) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM beneficiaries WHERE external_reference = :er",
        {"er": external_reference},
    ).fetchone()
    return dict(row) if row is not None else None


def list_beneficiaries(conn: sqlite3.Connection) -> list:
    rows = conn.execute("SELECT * FROM beneficiaries ORDER BY external_reference").fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# FPSCenter
# ---------------------------------------------------------------------------


def insert_fps_center(
    conn: sqlite3.Connection,
    *,
    fps_code: str,
    name: Optional[str] = None,
    state: Optional[str] = None,
    district: Optional[str] = None,
    block: Optional[str] = None,
    location: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    capacity: Optional[float] = None,
    status: str = "ACTIVE",
) -> int:
    """Insert a Fair Price Shop / distribution center; returns its id."""
    if not isinstance(fps_code, str) or not fps_code.strip():
        raise ValueError("fps_code must be a non-empty string")
    _require(status, FPS_CENTER_STATUSES, "fps center status")
    _optional_number(latitude, "latitude", low=-90.0, high=90.0)
    _optional_number(longitude, "longitude", low=-180.0, high=180.0)
    _optional_number(capacity, "capacity", low=0.0)
    now = _now_iso()
    cur = conn.execute(
        "INSERT INTO fps_centers "
        "(fps_code, name, state, district, block, location, latitude, longitude, capacity, status, created_at, updated_at) "
        "VALUES (:code, :name, :state, :district, :block, :location, :lat, :lon, :cap, :status, :now, :now)",
        {
            "code": fps_code.strip(),
            "name": name,
            "state": state,
            "district": district,
            "block": block,
            "location": location,
            "lat": latitude,
            "lon": longitude,
            "cap": capacity,
            "status": status,
            "now": now,
        },
    )
    return cur.lastrowid


def get_fps_center_by_code(conn: sqlite3.Connection, fps_code: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM fps_centers WHERE fps_code = :code", {"code": fps_code}
    ).fetchone()
    return dict(row) if row is not None else None


def list_fps_centers(conn: sqlite3.Connection) -> list:
    rows = conn.execute("SELECT * FROM fps_centers ORDER BY fps_code").fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# RationTransaction
# ---------------------------------------------------------------------------


def insert_transaction(
    conn: sqlite3.Connection,
    *,
    external_transaction_id: str,
    beneficiary_id: Optional[int] = None,
    fps_center_id: Optional[int] = None,
    transaction_date: str,
    commodity: str,
    quantity: float,
    unit: str = DEFAULT_TRANSACTION_UNIT,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    status: str = "COMPLETED",
    source_import_id: Optional[int] = None,
) -> int:
    """Insert one normalized ration transaction; returns its id.

    ``external_transaction_id`` must be unique (duplicates raise
    ``sqlite3.IntegrityError`` — the ingestion layer reports those as
    duplicate records rather than silently overwriting). ``latitude`` /
    ``longitude`` are stored so Agent 1/Agent 2 can reproduce their exact
    input records (``as_agent_transaction``).
    """
    if not isinstance(external_transaction_id, str) or not external_transaction_id.strip():
        raise ValueError("external_transaction_id must be a non-empty string")
    if not isinstance(transaction_date, str) or not transaction_date.strip():
        raise ValueError("transaction_date must be a non-empty string")
    if not isinstance(commodity, str) or not commodity.strip():
        raise ValueError("commodity must be a non-empty string")
    if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or quantity <= 0:
        raise ValueError("quantity must be a positive number")
    _require(status, TRANSACTION_STATUSES, "transaction status")
    _optional_number(latitude, "latitude", low=-90.0, high=90.0)
    _optional_number(longitude, "longitude", low=-180.0, high=180.0)
    cur = conn.execute(
        "INSERT INTO ration_transactions "
        "(external_transaction_id, beneficiary_id, fps_center_id, transaction_date, "
        " commodity, quantity, unit, latitude, longitude, status, source_import_id, created_at) "
        "VALUES (:ext, :ben, :fps, :date, :commodity, :qty, :unit, :lat, :lon, :status, :imp, :now)",
        {
            "ext": external_transaction_id.strip(),
            "ben": beneficiary_id,
            "fps": fps_center_id,
            "date": transaction_date,
            "commodity": commodity.strip(),
            "qty": quantity,
            "unit": unit,
            "lat": latitude,
            "lon": longitude,
            "status": status,
            "imp": source_import_id,
            "now": _now_iso(),
        },
    )
    return cur.lastrowid


def as_agent_transaction(row: dict) -> dict:
    """Convert a normalized transaction row into the documented agent-contract
    shape (exactly the 7 transaction fields Agent 1/Agent 2 consume, plus the
    coordinates their calculations need). This is the seam where the existing
    agents plug into real data."""
    return {
        "transaction_id": row["external_transaction_id"],
        "beneficiary_id": row["beneficiary_external_reference"],
        "timestamp": row["transaction_date"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "ration_type": row["commodity"],
        "quantity": row["quantity"],
    }


def get_transactions_for_agent(
    conn: sqlite3.Connection, import_id: Optional[int] = None
) -> list:
    """Return all transactions (optionally for one import) in the agent
    contract shape, joined with beneficiary external references."""
    if import_id is not None:
        rows = conn.execute(
            "SELECT t.*, b.external_reference AS beneficiary_external_reference "
            "FROM ration_transactions t "
            "LEFT JOIN beneficiaries b ON b.id = t.beneficiary_id "
            "WHERE t.source_import_id = :imp ORDER BY t.id",
            {"imp": import_id},
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT t.*, b.external_reference AS beneficiary_external_reference "
            "FROM ration_transactions t "
            "LEFT JOIN beneficiaries b ON b.id = t.beneficiary_id "
            "ORDER BY t.id"
        ).fetchall()
    return [as_agent_transaction(dict(row)) for row in rows]


def get_transactions_for_import(
    conn: sqlite3.Connection, import_id: int
) -> list:
    rows = conn.execute(
        "SELECT t.*, b.external_reference AS beneficiary_external_reference "
        "FROM ration_transactions t "
        "LEFT JOIN beneficiaries b ON b.id = t.beneficiary_id "
        "WHERE t.source_import_id = :imp ORDER BY t.id",
        {"imp": import_id},
    ).fetchall()
    return [dict(row) for row in rows]


def get_transactions_for_beneficiary(
    conn: sqlite3.Connection, external_reference: str
) -> list:
    rows = conn.execute(
        "SELECT t.*, b.external_reference AS beneficiary_external_reference "
        "FROM ration_transactions t "
        "LEFT JOIN beneficiaries b ON b.id = t.beneficiary_id "
        "WHERE b.external_reference = :er ORDER BY t.id",
        {"er": external_reference},
    ).fetchall()
    return [dict(row) for row in rows]


def get_transaction_by_external_id(
    conn: sqlite3.Connection, external_transaction_id: str
) -> Optional[dict]:
    row = conn.execute(
        "SELECT t.*, b.external_reference AS beneficiary_external_reference "
        "FROM ration_transactions t "
        "LEFT JOIN beneficiaries b ON b.id = t.beneficiary_id "
        "WHERE t.external_transaction_id = :ext",
        {"ext": external_transaction_id},
    ).fetchone()
    return dict(row) if row is not None else None


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


def insert_inventory(
    conn: sqlite3.Connection,
    *,
    fps_center_id: Optional[int] = None,
    commodity: str,
    current_stock: float,
    monthly_consumption: Optional[float] = None,
    reorder_threshold: Optional[float] = None,
    last_updated: Optional[str] = None,
    source_import_id: Optional[int] = None,
) -> int:
    """Insert one inventory record; returns its id."""
    if not isinstance(commodity, str) or not commodity.strip():
        raise ValueError("commodity must be a non-empty string")
    if isinstance(current_stock, bool) or not isinstance(current_stock, (int, float)) or current_stock < 0:
        raise ValueError("current_stock must be a non-negative number")
    for field, value in (
        ("monthly_consumption", monthly_consumption),
        ("reorder_threshold", reorder_threshold),
    ):
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0):
            raise ValueError("%s must be a non-negative number or None" % field)
    cur = conn.execute(
        "INSERT INTO inventory "
        "(fps_center_id, commodity, current_stock, monthly_consumption, reorder_threshold, "
        " last_updated, source_import_id, created_at) "
        "VALUES (:fps, :commodity, :stock, :monthly, :threshold, :updated, :imp, :now)",
        {
            "fps": fps_center_id,
            "commodity": commodity.strip(),
            "stock": current_stock,
            "monthly": monthly_consumption,
            "threshold": reorder_threshold,
            "updated": last_updated,
            "imp": source_import_id,
            "now": _now_iso(),
        },
    )
    return cur.lastrowid


def get_inventory_for_center(
    conn: sqlite3.Connection, fps_center_id: int
) -> list:
    rows = conn.execute(
        "SELECT * FROM inventory WHERE fps_center_id = :fps ORDER BY commodity",
        {"fps": fps_center_id},
    ).fetchall()
    return [dict(row) for row in rows]


def get_inventory_for_import(
    conn: sqlite3.Connection, import_id: int
) -> list:
    rows = conn.execute(
        "SELECT * FROM inventory WHERE source_import_id = :imp ORDER BY id",
        {"imp": import_id},
    ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# AIInsight
# ---------------------------------------------------------------------------


def insert_ai_insight(
    conn: sqlite3.Connection,
    *,
    insight_type: str,
    severity: str,
    title: str,
    description: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    confidence: Optional[float] = None,
    recommendation: Optional[str] = None,
    evidence: Optional[dict] = None,
    analysis_id: Optional[str] = None,
    source_import_id: Optional[int] = None,
) -> int:
    """Insert one structured AI insight; returns its id.

    Every insight is traceable to the import (dataset) that produced it via
    ``source_import_id``, plus the analysis run that produced it via
    ``analysis_id`` (Phase 11 adds these so monitoring can convert an insight
    into an alert with full lineage: alert <- insight <- analysis <- import).
    """
    import json as _json

    _require(insight_type, AI_INSIGHT_TYPES, "insight type")
    _require(severity, SEVERITY_LEVELS, "severity")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title must be a non-empty string")
    if confidence is not None and (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not (0.0 <= confidence <= 1.0)
    ):
        raise ValueError("confidence must be a number in [0, 1] or None")
    cur = conn.execute(
        "INSERT INTO ai_insights "
        "(insight_type, severity, title, description, entity_type, entity_id, "
        " confidence, recommendation, evidence, analysis_id, source_import_id, created_at) "
        "VALUES (:type, :severity, :title, :desc, :entity_type, :entity_id, "
        " :confidence, :recommendation, :evidence, :aid, :imp, :now)",
        {
            "type": insight_type,
            "severity": severity,
            "title": title,
            "desc": description,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "confidence": confidence,
            "recommendation": recommendation,
            "evidence": _json.dumps(evidence) if evidence else None,
            "aid": analysis_id,
            "imp": source_import_id,
            "now": _now_iso(),
        },
    )
    return cur.lastrowid


def get_insights_for_import(conn: sqlite3.Connection, import_id: int) -> list:
    rows = conn.execute(
        "SELECT * FROM ai_insights WHERE source_import_id = :imp ORDER BY id",
        {"imp": import_id},
    ).fetchall()
    return [dict(row) for row in rows]


def get_insights_since(
    conn: sqlite3.Connection,
    *,
    insight_type: Optional[str] = None,
    min_severity: Optional[str] = None,
    limit: int = 200,
) -> list:
    """Recent persisted insights, optionally filtered by type/severity
    (severity order: LOW < MEDIUM < HIGH < CRITICAL). Used by the monitoring
    engine to convert analysis insights into alerts."""
    import json as _json

    where, params = [], {}
    if insight_type:
        where.append("insight_type = :itype")
        params["itype"] = insight_type
    if min_severity:
        rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        cutoff = rank.get(min_severity)
        if cutoff is not None:
            where.append("CASE severity WHEN 'LOW' THEN 0 WHEN 'MEDIUM' THEN 1 "
                         "WHEN 'HIGH' THEN 2 WHEN 'CRITICAL' THEN 3 END >= :rank")
            params["rank"] = cutoff
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        "SELECT * FROM ai_insights" + where_sql +
        " ORDER BY id DESC LIMIT :limit",
        {**params, "limit": limit},
    ).fetchall()
    out = []
    for row in rows:
        d = dict(row)
        raw = d.get("evidence")
        if isinstance(raw, str):
            try:
                d["evidence"] = _json.loads(raw)
            except ValueError:
                d["evidence"] = None
        out.append(d)
    return out


def get_insights_for_entity(
    conn: sqlite3.Connection, entity_type: str, entity_id: str
) -> list:
    rows = conn.execute(
        "SELECT * FROM ai_insights WHERE entity_type = :t AND entity_id = :id ORDER BY id",
        {"t": entity_type, "id": entity_id},
    ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# AnalysisRun (Phase 8 — lineage metadata)
#
# One row per multi-agent workflow run. Lets the Data Pipeline page answer
# "which dataset produced this AI insight?" end to end:
#   AI insight <- analysis run <- data import <- data source.
# The workflow result itself stays in the UI (it is returned in real time);
# this table only records durable metadata (counts + status + provenance).
# ---------------------------------------------------------------------------

ANALYSIS_RUN_STATUSES = ("COMPLETED", "FAILED", "INSUFFICIENT_DATA")

SCENARIO_TYPES = ("DEMAND_CHANGE", "SUPPLY_DELAY", "INVENTORY_CHANGE", "COMBINED")


def insert_analysis_run(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    data_import_id: Optional[int] = None,
    dataset_mode: str = "synthetic",
    status: str = "COMPLETED",
    anomaly_count: int = 0,
    finding_count: int = 0,
    case_count: int = 0,
    alert_count: int = 0,
    insight_count: int = 0,
    analysis_types: Optional[list] = None,
    filters: Optional[dict] = None,
    timings: Optional[dict] = None,
    duration_ms: Optional[int] = None,
    summary: Optional[str] = None,
    error: Optional[str] = None,
) -> int:
    """Record one multi-agent analysis run; returns its id.

    ``analysis_types`` / ``filters`` / ``timings`` are stored as JSON so the
    Analysis History page can reproduce each run's configuration (Phase 9).
    """
    import json as _json

    if not isinstance(analysis_id, str) or not analysis_id.strip():
        raise ValueError("analysis_id must be a non-empty string")
    _require(dataset_mode, ("synthetic", "real"), "dataset_mode")
    _require(status, ANALYSIS_RUN_STATUSES, "analysis status")
    for field, value in (
        ("anomaly_count", anomaly_count),
        ("finding_count", finding_count),
        ("case_count", case_count),
        ("alert_count", alert_count),
        ("insight_count", insight_count),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("%s must be a non-negative integer" % field)
    conn.execute(
        "INSERT OR REPLACE INTO analysis_runs "
        "(analysis_id, data_import_id, dataset_mode, status, anomaly_count, "
        " finding_count, case_count, alert_count, insight_count, "
        " analysis_types, filters, timings, duration_ms, summary, error, created_at) "
        "VALUES (:aid, :imp, :mode, :status, :anomalies, :findings, :cases, "
        " :alerts, :insights, :types, :filters, :timings, :duration, :summary, "
        " :error, :now)",
        {
            "aid": analysis_id.strip(),
            "imp": data_import_id,
            "mode": dataset_mode,
            "status": status,
            "anomalies": anomaly_count,
            "findings": finding_count,
            "cases": case_count,
            "alerts": alert_count,
            "insights": insight_count,
            "types": _json.dumps(analysis_types) if analysis_types else None,
            "filters": _json.dumps(filters) if filters else None,
            "timings": _json.dumps(timings) if timings else None,
            "duration": duration_ms,
            "summary": summary,
            "error": error,
            "now": _now_iso(),
        },
    )
    row = conn.execute(
        "SELECT id FROM analysis_runs WHERE analysis_id = :aid",
        {"aid": analysis_id.strip()},
    ).fetchone()
    return row["id"]


def get_analysis_runs_for_import(
    conn: sqlite3.Connection, import_id: Optional[int] = None, limit: int = 20
) -> list:
    """Recent analysis runs, optionally filtered to one data import."""
    if import_id is not None:
        rows = conn.execute(
            "SELECT * FROM analysis_runs WHERE data_import_id = :imp "
            "ORDER BY id DESC LIMIT :limit",
            {"imp": import_id, "limit": limit},
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM analysis_runs ORDER BY id DESC LIMIT :limit",
            {"limit": limit},
        ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Scenario (Phase 10 — decision-support what-if simulations)
#
# Stores ONLY simulation metadata/results — a scenario NEVER writes to
# inventory, beneficiaries, or transactions. ``parameters`` / ``results`` /
# ``ai_interpretation`` are JSON so the Decision Support page can reproduce
# any scenario (SIM-YYYY-NNNN) and trace it back to its dataset/import/source.
# ---------------------------------------------------------------------------


def insert_scenario(
    conn: sqlite3.Connection,
    *,
    scenario_id: str,
    data_import_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    commodity: Optional[str] = None,
    scenario_type: str,
    parameters: Optional[dict] = None,
    results: Optional[dict] = None,
    ai_interpretation: Optional[dict] = None,
    risk: Optional[str] = None,
) -> int:
    """Record one what-if simulation; returns its id."""
    import json as _json

    if not isinstance(scenario_id, str) or not scenario_id.strip():
        raise ValueError("scenario_id must be a non-empty string")
    if scenario_type not in SCENARIO_TYPES:
        _require(scenario_type, SCENARIO_TYPES, "scenario type")
    conn.execute(
        "INSERT OR REPLACE INTO scenarios "
        "(scenario_id, data_import_id, entity_type, entity_id, commodity, "
        " scenario_type, parameters, results, ai_interpretation, risk, created_at) "
        "VALUES (:sid, :imp, :etype, :eid, :commodity, :stype, :params, :results, "
        " :ai, :risk, :now)",
        {
            "sid": scenario_id.strip(),
            "imp": data_import_id,
            "etype": entity_type,
            "eid": entity_id,
            "commodity": commodity,
            "stype": scenario_type,
            "params": _json.dumps(parameters) if parameters else None,
            "results": _json.dumps(results) if results else None,
            "ai": _json.dumps(ai_interpretation) if ai_interpretation else None,
            "risk": risk,
            "now": _now_iso(),
        },
    )
    row = conn.execute(
        "SELECT id FROM scenarios WHERE scenario_id = :sid", {"sid": scenario_id.strip()}
    ).fetchone()
    return row["id"]


def get_scenarios(conn: sqlite3.Connection, limit: int = 20) -> list:
    rows = conn.execute(
        "SELECT * FROM scenarios ORDER BY id DESC LIMIT :limit", {"limit": limit}
    ).fetchall()
    return [dict(row) for row in rows]


def get_scenario(conn: sqlite3.Connection, scenario_id: str):
    row = conn.execute(
        "SELECT * FROM scenarios WHERE scenario_id = :sid", {"sid": scenario_id}
    ).fetchone()
    return dict(row) if row is not None else None


def get_scenario_by_id(conn: sqlite3.Connection, scenario_pk: int):
    row = conn.execute(
        "SELECT * FROM scenarios WHERE id = :id", {"id": scenario_pk}
    ).fetchone()
    return dict(row) if row is not None else None


# ---------------------------------------------------------------------------
# Alert rules + alerts (Phase 11 — early warning & monitoring)
#
# One row per deterministic monitoring rule (configurable threshold/enabled)
# and one row per detected condition. Alerts carry evidence (JSON), an AI
# explanation (JSON, with a deterministic fallback), and lineage links
# (source / import / analysis) so every alert can be traced back to data.
# ---------------------------------------------------------------------------

ALERT_TYPES = (
    "INVENTORY_RISK",
    "OPERATIONAL_RISK",
    "DISTRIBUTION_ANOMALY",
    "DEMAND_SPIKE",
    "DEMAND_DROP",
    "SUPPLY_DELAY",
    "DATA_QUALITY",
    "DATA_FRESHNESS",
    "SOURCE_FAILURE",
)
ALERT_STATUSES = ("OPEN", "ACKNOWLEDGED", "RESOLVED", "DISMISSED")
ALERT_SEVERITIES = ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")


def insert_alert_rule(
    conn: sqlite3.Connection,
    *,
    name: str,
    rule_type: str,
    condition: str,
    description: Optional[str] = None,
    severity: str = "MEDIUM",
    enabled: bool = True,
    threshold: Optional[float] = None,
    threshold_unit: Optional[str] = None,
    scope: str = "GLOBAL",
) -> int:
    """Insert a monitoring rule; returns its id. ``name`` must be unique."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("rule name must be a non-empty string")
    _require(rule_type, ALERT_TYPES, "alert rule type")
    _require(severity, ALERT_SEVERITIES, "alert rule severity")
    now = _now_iso()
    cur = conn.execute(
        "INSERT INTO alert_rules "
        "(name, rule_type, condition, description, severity, enabled, threshold, "
        " threshold_unit, scope, created_at, updated_at) "
        "VALUES (:name, :rtype, :cond, :desc, :severity, :enabled, :threshold, "
        " :unit, :scope, :now, :now)",
        {
            "name": name.strip(),
            "rtype": rule_type,
            "cond": condition,
            "desc": description,
            "severity": severity,
            "enabled": 1 if enabled else 0,
            "threshold": threshold,
            "unit": threshold_unit,
            "scope": scope,
            "now": now,
        },
    )
    return cur.lastrowid


def seed_alert_rules(conn: sqlite3.Connection, rules: list) -> None:
    """Idempotently upsert the default rule set (by name)."""
    now = _now_iso()
    for rule in rules:
        conn.execute(
            "INSERT INTO alert_rules "
            "(name, rule_type, condition, description, severity, enabled, threshold, "
            " threshold_unit, scope, created_at, updated_at) "
            "VALUES (:name, :rtype, :cond, :desc, :severity, :enabled, :threshold, "
            " :unit, :scope, :now, :now) "
            "ON CONFLICT(name) DO UPDATE SET "
            "  description = excluded.description, severity = excluded.severity, "
            "  threshold = excluded.threshold, threshold_unit = excluded.threshold_unit, "
            "  updated_at = excluded.updated_at",
            {
                "name": rule["name"],
                "rtype": rule["rule_type"],
                "cond": rule["condition"],
                "desc": rule["description"],
                "severity": rule["severity"],
                "enabled": 1 if rule.get("enabled", True) else 0,
                "threshold": rule.get("threshold"),
                "unit": rule.get("threshold_unit"),
                "scope": rule.get("scope", "GLOBAL"),
                "now": now,
            },
        )


def list_alert_rules(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        "SELECT * FROM alert_rules ORDER BY id"
    ).fetchall()
    return [dict(row) for row in rows]


def get_alert_rule(conn: sqlite3.Connection, rule_id: int) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM alert_rules WHERE id = :id", {"id": rule_id}
    ).fetchone()
    return dict(row) if row is not None else None


def update_alert_rule(
    conn: sqlite3.Connection,
    rule_id: int,
    *,
    enabled: Optional[bool] = None,
    threshold: Optional[float] = None,
) -> None:
    """Update a rule's enabled flag and/or numeric threshold."""
    sets, params = [], {}
    if enabled is not None:
        sets.append("enabled = :enabled")
        params["enabled"] = 1 if enabled else 0
    if threshold is not None:
        sets.append("threshold = :threshold")
        params["threshold"] = threshold
    if not sets:
        return
    sets.append("updated_at = :now")
    params["now"] = _now_iso()
    params["id"] = rule_id
    conn.execute(
        "UPDATE alert_rules SET %s WHERE id = :id" % ", ".join(sets), params
    )


def insert_alert(
    conn: sqlite3.Connection,
    *,
    alert_id: str,
    rule_type: str,
    condition: str,
    severity: str,
    title: str,
    description: Optional[str] = None,
    status: str = "OPEN",
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    commodity: Optional[str] = None,
    current_value: Optional[float] = None,
    threshold: Optional[float] = None,
    evidence: Optional[dict] = None,
    ai_explanation: Optional[dict] = None,
    recommendation: Optional[str] = None,
    source_id: Optional[int] = None,
    import_id: Optional[int] = None,
    analysis_id: Optional[str] = None,
    created_at: Optional[str] = None,
) -> int:
    """Insert one alert; returns its id."""
    import json as _json

    if not isinstance(alert_id, str) or not alert_id.strip():
        raise ValueError("alert_id must be a non-empty string")
    _require(rule_type, ALERT_TYPES, "alert type")
    _require(severity, ALERT_SEVERITIES, "alert severity")
    _require(status, ALERT_STATUSES, "alert status")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title must be a non-empty string")
    now = created_at or _now_iso()
    cur = conn.execute(
        "INSERT INTO alerts "
        "(alert_id, rule_type, condition, severity, title, description, status, "
        " entity_type, entity_id, commodity, current_value, threshold, evidence, "
        " ai_explanation, recommendation, source_id, import_id, analysis_id, "
        " created_at, last_detected_at) "
        "VALUES (:aid, :rtype, :cond, :severity, :title, :desc, :status, "
        " :etype, :eid, :commodity, :cur, :thr, :evidence, :ai, :rec, "
        " :sid, :iid, :aid2, :now, :now)",
        {
            "aid": alert_id.strip(),
            "rtype": rule_type,
            "cond": condition,
            "severity": severity,
            "title": title,
            "desc": description,
            "status": status,
            "etype": entity_type,
            "eid": entity_id,
            "commodity": commodity,
            "cur": current_value,
            "thr": threshold,
            "evidence": _json.dumps(evidence) if evidence else None,
            "ai": _json.dumps(ai_explanation) if ai_explanation else None,
            "rec": recommendation,
            "sid": source_id,
            "iid": import_id,
            "aid2": analysis_id,
            "now": now,
        },
    )
    return cur.lastrowid


def get_alert_by_alert_id(conn: sqlite3.Connection, alert_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM alerts WHERE alert_id = :aid", {"aid": alert_id}
    ).fetchone()
    return dict(row) if row is not None else None


def get_alert(conn: sqlite3.Connection, alert_pk: int) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM alerts WHERE id = :id", {"id": alert_pk}
    ).fetchone()
    return dict(row) if row is not None else None


def get_active_alert_for_condition(
    conn: sqlite3.Connection,
    rule_type: str,
    condition: str,
    entity_type: Optional[str],
    entity_id: Optional[str],
    commodity: Optional[str],
) -> Optional[dict]:
    """The OPEN/ACKNOWLEDGED alert for one condition key, if any (dedup)."""
    row = conn.execute(
        "SELECT * FROM alerts WHERE rule_type = :rtype AND condition = :cond "
        "AND COALESCE(entity_type, '') = COALESCE(:etype, '') "
        "AND COALESCE(entity_id, '') = COALESCE(:eid, '') "
        "AND COALESCE(commodity, '') = COALESCE(:commodity, '') "
        "AND status IN ('OPEN','ACKNOWLEDGED') ORDER BY id DESC LIMIT 1",
        {
            "rtype": rule_type, "cond": condition, "etype": entity_type,
            "eid": entity_id, "commodity": commodity,
        },
    ).fetchone()
    return dict(row) if row is not None else None


def get_condition_history(
    conn: sqlite3.Connection,
    rule_type: str,
    condition: str,
    entity_type: Optional[str],
    entity_id: Optional[str],
    commodity: Optional[str],
) -> list:
    """All alerts (any status) for one condition key, newest first."""
    rows = conn.execute(
        "SELECT * FROM alerts WHERE rule_type = :rtype AND condition = :cond "
        "AND COALESCE(entity_type, '') = COALESCE(:etype, '') "
        "AND COALESCE(entity_id, '') = COALESCE(:eid, '') "
        "AND COALESCE(commodity, '') = COALESCE(:commodity, '') "
        "ORDER BY id DESC",
        {
            "rtype": rule_type, "cond": condition, "etype": entity_type,
            "eid": entity_id, "commodity": commodity,
        },
    ).fetchall()
    return [dict(row) for row in rows]


def list_alerts(
    conn: sqlite3.Connection,
    *,
    q: Optional[str] = None,
    severity: Optional[str] = None,
    rule_type: Optional[str] = None,
    status: Optional[str] = None,
    days: Optional[int] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    commodity: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Server-side filtered + searched + paginated alert list."""
    if isinstance(per_page, bool) or not isinstance(per_page, int) or per_page <= 0:
        per_page = 20
    if isinstance(page, bool) or not isinstance(page, int) or page <= 0:
        page = 1
    per_page = min(per_page, 200)
    where, params = [], {}
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("(a.alert_id LIKE :q ESCAPE '\\' OR a.title LIKE :q ESCAPE '\\' "
                     "OR a.description LIKE :q ESCAPE '\\' OR COALESCE(a.entity_id, '') LIKE :q ESCAPE '\\' "
                     "OR COALESCE(a.commodity, '') LIKE :q ESCAPE '\\')")
        params["q"] = "%" + escaped + "%"
    for field, column in (
        ("severity", "a.severity"), ("rule_type", "a.rule_type"),
        ("status", "a.status"), ("entity_type", "a.entity_type"),
        ("entity_id", "a.entity_id"), ("commodity", "a.commodity"),
    ):
        value = locals().get(field)
        if value and value != "all":
            where.append("%s = :%s" % (column, field))
            params[field] = value
    if days and days != "all":
        try:
            cutoff = (
                datetime.now(timezone.utc) - timedelta(days=int(days))
            ).isoformat(timespec="seconds")
        except (TypeError, ValueError):
            cutoff = None
        if cutoff:
            where.append("a.created_at >= :cutoff")
            params["cutoff"] = cutoff
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    total = conn.execute(
        "SELECT COUNT(*) AS n FROM alerts a" + where_sql, params
    ).fetchone()["n"]
    rows = conn.execute(
        "SELECT a.*, s.name AS source_name, i.dataset_name "
        "FROM alerts a LEFT JOIN data_sources s ON s.id = a.source_id "
        "LEFT JOIN data_imports i ON i.id = a.import_id "
        + where_sql + " ORDER BY a.last_detected_at DESC, a.id DESC "
        "LIMIT :limit OFFSET :offset",
        {**params, "limit": per_page, "offset": (page - 1) * per_page},
    ).fetchall()
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, -(-total // per_page)),
        "alerts": [_decode_alert(dict(row)) for row in rows],
    }


def _decode_alert(row: dict) -> dict:
    """Decode JSON columns on an alert row into dicts for the API."""
    import json as _json

    for field in ("evidence", "ai_explanation"):
        raw = row.get(field)
        if isinstance(raw, str):
            try:
                row[field] = _json.loads(raw)
            except ValueError:
                row[field] = None
    return row


def get_open_alert_counts(conn: sqlite3.Connection) -> dict:
    """Active alert counts by severity (OPEN + ACKNOWLEDGED)."""
    counts = {sev: 0 for sev in ALERT_SEVERITIES}
    rows = conn.execute(
        "SELECT severity, status, COUNT(*) AS n FROM alerts "
        "WHERE status IN ('OPEN','ACKNOWLEDGED') GROUP BY severity, status"
    ).fetchall()
    open_by_sev = {sev: 0 for sev in ALERT_SEVERITIES}
    ack_by_sev = {sev: 0 for sev in ALERT_SEVERITIES}
    total_open = total_ack = 0
    for r in rows:
        if r["status"] == "OPEN":
            open_by_sev[r["severity"]] = r["n"]
            total_open += r["n"]
        else:
            ack_by_sev[r["severity"]] = r["n"]
            total_ack += r["n"]
    return {
        "open": open_by_sev,
        "acknowledged": ack_by_sev,
        "total_open": total_open,
        "total_acknowledged": total_ack,
        "total_active": total_open + total_ack,
    }


def get_alert_trend(conn: sqlite3.Connection, days: int = 7) -> dict:
    """Alerts created per day for the last ``days`` days (actual records)."""
    from datetime import timedelta

    days = max(1, min(int(days), 90))
    today = datetime.now(timezone.utc).date()
    rows = conn.execute(
        "SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS n "
        "FROM alerts WHERE substr(created_at, 1, 10) >= :start "
        "GROUP BY day ORDER BY day",
        {"start": (today - timedelta(days=days - 1)).isoformat()},
    ).fetchall()
    by_day = {r["day"]: r["n"] for r in rows}
    series = []
    for offset in range(days):
        day = (today - timedelta(days=days - 1 - offset)).isoformat()
        series.append({"date": day, "count": by_day.get(day, 0)})
    return {"days": days, "series": series,
            "total": sum(item["count"] for item in series)}


def update_alert_status(
    conn: sqlite3.Connection,
    alert_id: str,
    status: str,
    *,
    dismissed_reason: Optional[str] = None,
) -> bool:
    """Transition one alert's status; returns True when a row changed.

    OPEN -> ACKNOWLEDGED (records acknowledged_at), OPEN/ACKNOWLEDGED ->
    RESOLVED (records resolved_at), and -> DISMISSED (records dismissed_at +
    optional reason). The alert row is never deleted — history is preserved.
    """
    _require(status, ALERT_STATUSES, "alert status")
    row = get_alert_by_alert_id(conn, alert_id)
    if row is None:
        return False
    now = _now_iso()
    if status == "ACKNOWLEDGED":
        conn.execute(
            "UPDATE alerts SET status = 'ACKNOWLEDGED', acknowledged_at = :now "
            "WHERE id = :id", {"now": now, "id": row["id"]})
    elif status == "RESOLVED":
        conn.execute(
            "UPDATE alerts SET status = 'RESOLVED', resolved_at = :now "
            "WHERE id = :id", {"now": now, "id": row["id"]})
    elif status == "DISMISSED":
        conn.execute(
            "UPDATE alerts SET status = 'DISMISSED', dismissed_at = :now, "
            " dismissed_reason = :reason WHERE id = :id",
            {"now": now, "reason": dismissed_reason, "id": row["id"]})
    else:  # re-open (used by tests / recovery)
        conn.execute(
            "UPDATE alerts SET status = 'OPEN' WHERE id = :id", {"id": row["id"]})
    return True


# ---------------------------------------------------------------------------
# Intelligence reports (Phase 12 — Executive Command Center)
#
# One row per generated report. ``payload`` holds the full structured report
# (KPIs, risk, trends, insights, alerts, recommendations, quality, lineage) so
# history can reproduce any report; reports are never overwritten.
# ---------------------------------------------------------------------------


def insert_report(
    conn: sqlite3.Connection,
    *,
    report_id: str,
    period_label: Optional[str] = None,
    source_label: Optional[str] = None,
    filters: Optional[dict] = None,
    payload: Optional[dict] = None,
    status: str = "READY",
) -> int:
    """Insert one generated report; returns its id."""
    import json as _json

    if not isinstance(report_id, str) or not report_id.strip():
        raise ValueError("report_id must be a non-empty string")
    cur = conn.execute(
        "INSERT INTO reports "
        "(report_id, period_label, source_label, filters, payload, status, created_at) "
        "VALUES (:rid, :period, :source, :filters, :payload, :status, :now)",
        {
            "rid": report_id.strip(),
            "period": period_label,
            "source": source_label,
            "filters": _json.dumps(filters) if filters else None,
            "payload": _json.dumps(payload) if payload else None,
            "status": status,
            "now": _now_iso(),
        },
    )
    return cur.lastrowid


def list_reports(conn: sqlite3.Connection, limit: int = 50) -> list:
    rows = conn.execute(
        "SELECT id, report_id, period_label, source_label, status, created_at "
        "FROM reports ORDER BY id DESC LIMIT :limit", {"limit": limit}
    ).fetchall()
    return [dict(row) for row in rows]


def get_report_by_report_id(conn: sqlite3.Connection, report_id: str) -> Optional[dict]:
    import json as _json

    row = conn.execute(
        "SELECT * FROM reports WHERE report_id = :rid", {"rid": report_id}
    ).fetchone()
    if row is None:
        return None
    report = dict(row)
    for field in ("filters", "payload"):
        raw = report.get(field)
        if isinstance(raw, str):
            try:
                report[field] = _json.loads(raw)
            except ValueError:
                report[field] = None
    return report


# ---------------------------------------------------------------------------
# Audit log (Phase 14 — append-only operational trail, never stores secrets)
# ---------------------------------------------------------------------------


def record_audit(
    conn: sqlite3.Connection,
    *,
    action: str,
    actor: str = "admin",
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    detail: Optional[str] = None,
    request_id: Optional[str] = None,
) -> int:
    """Append one audit entry. ``detail`` must never contain secrets; callers
    pass short human summaries only. Returns the new row id."""
    if not isinstance(action, str) or not action.strip():
        raise ValueError("action must be a non-empty string")
    cur = conn.execute(
        "INSERT INTO audit_log "
        "(actor, action, entity_type, entity_id, detail, request_id, created_at) "
        "VALUES (:actor, :action, :entity_type, :entity_id, :detail, :request_id, :now)",
        {
            "actor": (actor or "admin").strip()[:64],
            "action": action.strip()[:64],
            "entity_type": (entity_type or "").strip()[:64] or None,
            "entity_id": (entity_id or "").strip()[:128] or None,
            "detail": (detail or "").strip()[:512] or None,
            "request_id": (request_id or "").strip()[:64] or None,
            "now": _now_iso(),
        },
    )
    return cur.lastrowid


def list_audit(
    conn: sqlite3.Connection,
    *,
    limit: int = 50,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
) -> list:
    """Recent audit entries, newest first. Limit is clamped to 1..500."""
    if isinstance(limit, bool) or not isinstance(limit, int):
        limit = 50
    limit = max(1, min(int(limit), 500))
    sql = "SELECT id, actor, action, entity_type, entity_id, detail, request_id, created_at " \
          "FROM audit_log"
    clauses, params = [], {}
    if action:
        clauses.append("action = :action")
        params["action"] = str(action)[:64]
    if entity_type:
        clauses.append("entity_type = :entity_type")
        params["entity_type"] = str(entity_type)[:64]
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id DESC LIMIT :limit"
    params["limit"] = limit
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Seeding — the existing synthetic dataset
# ---------------------------------------------------------------------------

SYNTHETIC_SOURCE_NAME = "Synthetic Demo Dataset"


def seed_synthetic(
    conn: sqlite3.Connection, dataset_path=DEFAULT_DATASET_PATH
) -> dict:
    """Import the Phase 1 synthetic dataset into the normalized schema.

    Deterministic and idempotent: running it again resets only the synthetic
    source's imports/transactions and re-imports them, so the demo database is
    always in the same state. Beneficiaries are upserted (never deleted — real
    data may reference them). The synthetic data contains no FPS centers,
    inventory, or AI insights, so none are created and nothing is invented.
    """
    dataset = load_dataset(dataset_path)
    transactions = dataset["transactions"]
    metadata = dataset.get("metadata", {})
    now = _now_iso()

    # --- reset any previous synthetic import (children first, then import) ---
    source = get_data_source_by_name(conn, SYNTHETIC_SOURCE_NAME)
    if source is not None:
        import_ids = [
            row["id"]
            for row in conn.execute(
                "SELECT id FROM data_imports WHERE data_source_id = :sid",
                {"sid": source["id"]},
            ).fetchall()
        ]
        for import_id in import_ids:
            for table in ("ai_insights", "inventory", "ration_transactions"):
                conn.execute(
                    "DELETE FROM %s WHERE source_import_id = :iid" % table,
                    {"iid": import_id},
                )
            conn.execute("DELETE FROM data_imports WHERE id = :iid", {"iid": import_id})
        conn.execute("DELETE FROM data_sources WHERE id = :sid", {"sid": source["id"]})

    # --- data source + import (provenance) ---
    source_id = insert_data_source(
        conn,
        name=SYNTHETIC_SOURCE_NAME,
        source_type="JSON",
        description=metadata.get("description"),
        status="ACTIVE",
        last_sync_at=now,
    )
    import_id = insert_data_import(
        conn,
        data_source_id=source_id,
        dataset_name=metadata.get("dataset_name") or "rationright-synthetic-transactions",
        file_name="transactions.json",
        file_type="json",
        record_count=len(transactions),
        successful_records=len(transactions),
        failed_records=0,
        duplicate_records=0,
        status="COMPLETED",
        started_at=now,
        completed_at=now,
    )

    # --- beneficiaries + transactions ---
    beneficiary_ids = {}
    for tx in transactions:
        ref = tx["beneficiary_id"]
        if ref not in beneficiary_ids:
            beneficiary_ids[ref] = upsert_beneficiary(conn, external_reference=ref, status="ACTIVE")
        insert_transaction(
            conn,
            external_transaction_id=tx["transaction_id"],
            beneficiary_id=beneficiary_ids[ref],
            transaction_date=tx["timestamp"],
            commodity=tx["ration_type"],
            quantity=tx["quantity"],
            unit=DEFAULT_TRANSACTION_UNIT,
            latitude=tx["latitude"],
            longitude=tx["longitude"],
            status="COMPLETED",
            source_import_id=import_id,
        )

    conn.commit()
    return {
        "data_source_id": source_id,
        "data_import_id": import_id,
        "beneficiaries": len(beneficiary_ids),
        "transactions": len(transactions),
        "fps_centers": 0,
        "inventory": 0,
        "ai_insights": 0,
    }


def seed_database(db_path=DEFAULT_DB_PATH, dataset_path=DEFAULT_DATASET_PATH) -> dict:
    """Open (creating if needed) the database and seed the synthetic dataset."""
    conn = open_db(db_path)
    try:
        return seed_synthetic(conn, dataset_path=dataset_path)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Batch helpers (used by the ingestion pipeline for large datasets).
#
# Values passed to these helpers are expected to be pre-validated and
# normalized by ``ingestion/``; they exist so an import streams through
# ``executemany`` batches instead of thousands of single-row round trips.
# ---------------------------------------------------------------------------


_BENEFICIARY_KEYS = (
    "external_reference", "state", "district", "block",
    "ration_category", "family_size", "status",
)


def upsert_beneficiaries(conn: sqlite3.Connection, records: list) -> None:
    """Bulk upsert beneficiaries. Each record is a dict with
    ``external_reference`` (required) plus optional state/district/block/
    ration_category/family_size/status; missing keys default to None (records
    derived from transaction rows carry only the fields they have)."""
    now = _now_iso()
    rows = []
    for record in records:
        row = {key: record.get(key) for key in _BENEFICIARY_KEYS}
        row["status"] = row["status"] or "ACTIVE"
        row["now"] = now
        rows.append(row)
    conn.executemany(
        "INSERT INTO beneficiaries "
        "(external_reference, state, district, block, ration_category, family_size, status, created_at, updated_at) "
        "VALUES (:external_reference, :state, :district, :block, :ration_category, "
        " :family_size, :status, :now, :now) "
        "ON CONFLICT(external_reference) DO UPDATE SET "
        "  state = excluded.state, district = excluded.district, block = excluded.block, "
        "  ration_category = excluded.ration_category, family_size = excluded.family_size, "
        "  status = excluded.status, updated_at = excluded.updated_at",
        rows,
    )


def beneficiary_ids(conn: sqlite3.Connection, refs) -> dict:
    """Map external references to internal beneficiary ids (only those found)."""
    refs = [r for r in refs if r]
    if not refs:
        return {}
    placeholders = ",".join("?" for _ in refs)
    rows = conn.execute(
        "SELECT id, external_reference FROM beneficiaries "
        "WHERE external_reference IN (%s)" % placeholders,
        list(refs),
    ).fetchall()
    return {row["external_reference"]: row["id"] for row in rows}


def existing_beneficiary_refs(conn: sqlite3.Connection) -> set:
    rows = conn.execute("SELECT external_reference FROM beneficiaries").fetchall()
    return {row["external_reference"] for row in rows}


_FPS_CENTER_KEYS = (
    "fps_code", "name", "state", "district", "block", "location",
    "latitude", "longitude", "capacity", "status",
)


def upsert_fps_centers(conn: sqlite3.Connection, records: list) -> None:
    """Bulk upsert FPS centers. Each record is a dict with ``fps_code``
    (required) plus optional name/state/district/block/location/latitude/
    longitude/capacity/status; missing keys default to None."""
    now = _now_iso()
    rows = []
    for record in records:
        row = {key: record.get(key) for key in _FPS_CENTER_KEYS}
        row["status"] = row["status"] or "ACTIVE"
        row["now"] = now
        rows.append(row)
    conn.executemany(
        "INSERT INTO fps_centers "
        "(fps_code, name, state, district, block, location, latitude, longitude, capacity, status, created_at, updated_at) "
        "VALUES (:fps_code, :name, :state, :district, :block, :location, :latitude, "
        " :longitude, :capacity, :status, :now, :now) "
        "ON CONFLICT(fps_code) DO UPDATE SET "
        "  name = excluded.name, state = excluded.state, district = excluded.district, "
        "  block = excluded.block, location = excluded.location, latitude = excluded.latitude, "
        "  longitude = excluded.longitude, capacity = excluded.capacity, "
        "  status = excluded.status, updated_at = excluded.updated_at",
        rows,
    )


def fps_center_ids(conn: sqlite3.Connection, codes) -> dict:
    """Map FPS codes to internal center ids (only those found)."""
    codes = [c for c in codes if c]
    if not codes:
        return {}
    placeholders = ",".join("?" for _ in codes)
    rows = conn.execute(
        "SELECT id, fps_code FROM fps_centers WHERE fps_code IN (%s)" % placeholders,
        list(codes),
    ).fetchall()
    return {row["fps_code"]: row["id"] for row in rows}


def existing_fps_codes(conn: sqlite3.Connection) -> set:
    rows = conn.execute("SELECT fps_code FROM fps_centers").fetchall()
    return {row["fps_code"] for row in rows}


def existing_transaction_ids(conn: sqlite3.Connection) -> set:
    rows = conn.execute("SELECT external_transaction_id FROM ration_transactions").fetchall()
    return {row["external_transaction_id"] for row in rows}


def insert_transactions_batch(conn: sqlite3.Connection, records: list) -> None:
    """Bulk insert normalized transaction records (already validated)."""
    now = _now_iso()
    conn.executemany(
        "INSERT INTO ration_transactions "
        "(external_transaction_id, beneficiary_id, fps_center_id, transaction_date, "
        " commodity, quantity, unit, latitude, longitude, status, source_import_id, created_at) "
        "VALUES (:external_transaction_id, :beneficiary_id, :fps_center_id, :transaction_date, "
        " :commodity, :quantity, :unit, :latitude, :longitude, :status, :source_import_id, :now)",
        [dict(record, now=now) for record in records],
    )


def insert_inventory_batch(conn: sqlite3.Connection, records: list) -> None:
    """Bulk insert normalized inventory records (already validated).

    Missing optional keys (``last_updated``, ``monthly_consumption``,
    ``reorder_threshold``) default to None so partial records import safely.
    """
    now = _now_iso()
    defaults = {
        "fps_center_id": None, "commodity": "", "current_stock": 0.0,
        "monthly_consumption": None, "reorder_threshold": None,
        "last_updated": None, "source_import_id": None,
    }
    conn.executemany(
        "INSERT INTO inventory "
        "(fps_center_id, commodity, current_stock, monthly_consumption, reorder_threshold, "
        " last_updated, source_import_id, created_at) "
        "VALUES (:fps_center_id, :commodity, :current_stock, :monthly_consumption, "
        " :reorder_threshold, :last_updated, :source_import_id, :now)",
        [dict(defaults, **record, now=now) for record in records],
    )
