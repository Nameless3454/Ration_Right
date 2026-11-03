"""
Database initialization, connection handling, and schema definitions for SQLite.
"""
import sqlite3
from pathlib import Path
from typing import Optional
from src.config import settings


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Return a connection with Row factory and foreign keys enabled."""
    target_path = db_path or settings.DB_PATH
    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Initialize all SQLite tables and indexes."""
    target_path = db_path or settings.DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    with get_db_connection(target_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS import_batches (
            import_id TEXT PRIMARY KEY,
            import_timestamp TEXT NOT NULL,
            dataset_name TEXT NOT NULL,
            total_records INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_path TEXT,
            details TEXT
        );

        CREATE TABLE IF NOT EXISTS pwd_shops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id TEXT NOT NULL,
            pwd_id TEXT NOT NULL,
            shop_name TEXT NOT NULL,
            dealer_id TEXT NOT NULL,
            district TEXT NOT NULL,
            state TEXT NOT NULL,
            monthly_capacity_kg INTEGER NOT NULL,
            gps_lat REAL,
            gps_lon REAL,
            FOREIGN KEY (import_id) REFERENCES import_batches (import_id) ON DELETE CASCADE,
            UNIQUE(import_id, pwd_id)
        );

        CREATE TABLE IF NOT EXISTS beneficiaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id TEXT NOT NULL,
            beneficiary_id TEXT NOT NULL,
            ration_card_id TEXT NOT NULL,
            head_name TEXT NOT NULL,
            family_size INTEGER NOT NULL,
            category TEXT NOT NULL,
            pwd_id TEXT NOT NULL,
            monthly_entitlement_kg INTEGER NOT NULL,
            last_collection_date TEXT,
            collection_status TEXT NOT NULL,
            identity_status TEXT NOT NULL,
            review_reason TEXT,
            demo_record INTEGER DEFAULT 1,
            FOREIGN KEY (import_id) REFERENCES import_batches (import_id) ON DELETE CASCADE,
            UNIQUE(import_id, beneficiary_id)
        );

        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id TEXT NOT NULL,
            inventory_id TEXT NOT NULL,
            pwd_id TEXT NOT NULL,
            month TEXT NOT NULL,
            commodity TEXT NOT NULL,
            opening_stock_kg INTEGER NOT NULL,
            received_kg INTEGER NOT NULL,
            distributed_kg INTEGER NOT NULL,
            closing_stock_kg INTEGER NOT NULL,
            physical_stock_kg INTEGER NOT NULL,
            unit TEXT DEFAULT 'kg',
            demo_record INTEGER DEFAULT 1,
            FOREIGN KEY (import_id) REFERENCES import_batches (import_id) ON DELETE CASCADE,
            UNIQUE(import_id, inventory_id)
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id TEXT NOT NULL,
            transaction_id TEXT NOT NULL,
            beneficiary_id TEXT NOT NULL,
            pwd_id TEXT NOT NULL,
            date TEXT NOT NULL,
            commodity TEXT NOT NULL,
            quantity_kg INTEGER NOT NULL,
            channel TEXT NOT NULL,
            status TEXT NOT NULL,
            demo_record INTEGER DEFAULT 1,
            FOREIGN KEY (import_id) REFERENCES import_batches (import_id) ON DELETE CASCADE,
            UNIQUE(import_id, transaction_id)
        );

        CREATE TABLE IF NOT EXISTS pwd_audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id TEXT NOT NULL,
            audit_id TEXT NOT NULL,
            pwd_id TEXT NOT NULL,
            period TEXT NOT NULL,
            late_opening_days INTEGER NOT NULL,
            manual_override_count INTEGER NOT NULL,
            complaints_count INTEGER NOT NULL,
            inspection_status TEXT NOT NULL,
            demo_record INTEGER DEFAULT 1,
            FOREIGN KEY (import_id) REFERENCES import_batches (import_id) ON DELETE CASCADE,
            UNIQUE(import_id, audit_id)
        );

        -- Performance Indexes
        CREATE INDEX IF NOT EXISTS idx_shops_import ON pwd_shops(import_id);
        CREATE INDEX IF NOT EXISTS idx_shops_pwd ON pwd_shops(pwd_id);
        CREATE INDEX IF NOT EXISTS idx_ben_import ON beneficiaries(import_id);
        CREATE INDEX IF NOT EXISTS idx_ben_pwd ON beneficiaries(pwd_id);
        CREATE INDEX IF NOT EXISTS idx_ben_identity ON beneficiaries(identity_status);
        CREATE INDEX IF NOT EXISTS idx_ben_collection ON beneficiaries(collection_status);
        CREATE INDEX IF NOT EXISTS idx_inv_import ON inventory(import_id);
        CREATE INDEX IF NOT EXISTS idx_inv_pwd ON inventory(pwd_id);
        CREATE INDEX IF NOT EXISTS idx_txn_import ON transactions(import_id);
        CREATE INDEX IF NOT EXISTS idx_txn_ben ON transactions(beneficiary_id);
        CREATE INDEX IF NOT EXISTS idx_aud_import ON pwd_audits(import_id);
        CREATE INDEX IF NOT EXISTS idx_aud_pwd ON pwd_audits(pwd_id);
        """)

