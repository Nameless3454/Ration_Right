"""
Weekly dataset ingestion engine for RationRight CSV and JSON batches.
Stamps every record with a unique import_id and preserves historical snapshots.
"""
import csv
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import sqlite3

from src.config import settings
from src.db.database import get_db_connection, init_db
from src.models.schemas import ImportBatchResponse, ImportBatchSummary

logger = logging.getLogger(__name__)


def generate_import_id(prefix: str = "IMP") -> str:
    """Generate a chronological unique identifier for the import batch."""
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"{prefix}_{now_str}_{short_uuid}"


class DatasetImporter:
    """Handles importing weekly datasets into SQLite."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.DB_PATH
        init_db(self.db_path)

    def import_dataset(
        self,
        dataset_path: Union[str, Path],
        dataset_name: Optional[str] = None,
        custom_import_id: Optional[str] = None,
    ) -> ImportBatchResponse:
        """
        Main entrypoint: Detects whether source is a directory of CSVs or a JSON file,
        parses the records, inserts them with import_id, and records batch history.
        """
        path = Path(dataset_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Dataset path does not exist: {path}")

        import_id = custom_import_id or generate_import_id()
        import_timestamp = datetime.now(timezone.utc).isoformat()
        dataset_label = dataset_name or path.name

        if path.is_file() and path.suffix.lower() == ".json":
            source_type = "json"
        elif path.is_dir():
            source_type = "csv"
        else:
            raise ValueError(
                f"Unsupported dataset format at {path}. Must be a directory of CSVs or a .json file."
            )

        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                # 1. Insert parent record in import_batches FIRST so foreign keys succeed
                cursor.execute(
                    """
                    INSERT INTO import_batches 
                    (import_id, import_timestamp, dataset_name, total_records, status, source_type, source_path, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        import_id,
                        import_timestamp,
                        dataset_label,
                        0,
                        "PROCESSING",
                        source_type,
                        str(path),
                        "{}",
                    ),
                )

                # 2. Ingest child tables
                if source_type == "json":
                    counts = self._import_from_json(cursor, path, import_id)
                else:
                    counts = self._import_from_csv_dir(cursor, path, import_id)

                total_records = sum(counts.values())

                # 3. Update parent record with final totals and SUCCESS status
                cursor.execute(
                    """
                    UPDATE import_batches 
                    SET total_records = ?, status = ?, details = ?
                    WHERE import_id = ?
                    """,
                    (
                        total_records,
                        "SUCCESS",
                        json.dumps(counts),
                        import_id,
                    ),
                )
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Error importing batch {import_id}: {e}")
                raise e

        return ImportBatchResponse(
            import_id=import_id,
            import_timestamp=import_timestamp,
            dataset_name=dataset_label,
            total_records=total_records,
            status="SUCCESS",
            source_type=source_type,
            source_path=str(path),
            table_counts=counts,
        )

    def _import_from_csv_dir(self, cursor: sqlite3.Cursor, dir_path: Path, import_id: str) -> Dict[str, int]:
        """Ingest all CSV files found in directory into respective tables using active cursor."""
        counts: Dict[str, int] = {}

        # 1. PWD Shops
        shops_file = dir_path / "pwd_shops.csv"
        if shops_file.exists():
            counts["pwd_shops"] = self._insert_shops(cursor, shops_file, import_id)

        # 2. Beneficiaries
        ben_file = dir_path / "beneficiaries.csv"
        if ben_file.exists():
            counts["beneficiaries"] = self._insert_beneficiaries(cursor, ben_file, import_id)

        # 3. Inventory
        inv_file = dir_path / "inventory.csv"
        if inv_file.exists():
            counts["inventory"] = self._insert_inventory(cursor, inv_file, import_id)

        # 4. Transactions
        txn_file = dir_path / "transactions.csv"
        if txn_file.exists():
            counts["transactions"] = self._insert_transactions(cursor, txn_file, import_id)

        # 5. PWD Audits
        aud_file = dir_path / "pwd_audits.csv"
        if aud_file.exists():
            counts["pwd_audits"] = self._insert_audits(cursor, aud_file, import_id)

        return counts

    def _import_from_json(self, cursor: sqlite3.Cursor, json_file: Path, import_id: str) -> Dict[str, int]:
        """Ingest consolidated JSON file into respective tables using active cursor."""
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        counts: Dict[str, int] = {}

        # 1. PWD Shops
        if "pwd_shops" in data:
            rows = [
                (
                    import_id,
                    s["pwd_id"],
                    s["shop_name"],
                    s["dealer_id"],
                    s["district"],
                    s["state"],
                    int(s["monthly_capacity_kg"]),
                    float(s.get("gps_lat") or 0.0),
                    float(s.get("gps_lon") or 0.0),
                )
                for s in data["pwd_shops"]
            ]
            cursor.executemany(
                """
                INSERT INTO pwd_shops 
                (import_id, pwd_id, shop_name, dealer_id, district, state, monthly_capacity_kg, gps_lat, gps_lon)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            counts["pwd_shops"] = len(rows)

        # 2. Beneficiaries
        if "beneficiaries" in data:
            rows = [
                (
                    import_id,
                    b["beneficiary_id"],
                    b["ration_card_id"],
                    b["head_name"],
                    int(b["family_size"]),
                    b["category"],
                    b["pwd_id"],
                    int(b["monthly_entitlement_kg"]),
                    b.get("last_collection_date"),
                    b.get("collection_status", "collected"),
                    b.get("identity_status", "verified"),
                    b.get("review_reason"),
                    1 if b.get("demo_record", True) else 0,
                )
                for b in data["beneficiaries"]
            ]
            cursor.executemany(
                """
                INSERT INTO beneficiaries 
                (import_id, beneficiary_id, ration_card_id, head_name, family_size, category, pwd_id,
                 monthly_entitlement_kg, last_collection_date, collection_status, identity_status, review_reason, demo_record)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            counts["beneficiaries"] = len(rows)

        # 3. Inventory
        if "inventory" in data:
            rows = [
                (
                    import_id,
                    i["inventory_id"],
                    i["pwd_id"],
                    i["month"],
                    i["commodity"],
                    int(i["opening_stock_kg"]),
                    int(i["received_kg"]),
                    int(i["distributed_kg"]),
                    int(i["closing_stock_kg"]),
                    int(i["physical_stock_kg"]),
                    i.get("unit", "kg"),
                    1 if i.get("demo_record", True) else 0,
                )
                for i in data["inventory"]
            ]
            cursor.executemany(
                """
                INSERT INTO inventory 
                (import_id, inventory_id, pwd_id, month, commodity, opening_stock_kg, received_kg,
                 distributed_kg, closing_stock_kg, physical_stock_kg, unit, demo_record)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            counts["inventory"] = len(rows)

        # 4. Transactions
        if "transactions" in data:
            rows = [
                (
                    import_id,
                    t["transaction_id"],
                    t["beneficiary_id"],
                    t["pwd_id"],
                    t["date"],
                    t["commodity"],
                    int(t["quantity_kg"]),
                    t["channel"],
                    t["status"],
                    1 if t.get("demo_record", True) else 0,
                )
                for t in data["transactions"]
            ]
            cursor.executemany(
                """
                INSERT INTO transactions 
                (import_id, transaction_id, beneficiary_id, pwd_id, date, commodity, quantity_kg, channel, status, demo_record)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            counts["transactions"] = len(rows)

        # 5. PWD Audits
        if "pwd_audits" in data:
            rows = [
                (
                    import_id,
                    a["audit_id"],
                    a["pwd_id"],
                    a["period"],
                    int(a["late_opening_days"]),
                    int(a["manual_override_count"]),
                    int(a["complaints_count"]),
                    a["inspection_status"],
                    1 if a.get("demo_record", True) else 0,
                )
                for a in data["pwd_audits"]
            ]
            cursor.executemany(
                """
                INSERT INTO pwd_audits 
                (import_id, audit_id, pwd_id, period, late_opening_days, manual_override_count, complaints_count, inspection_status, demo_record)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            counts["pwd_audits"] = len(rows)

        return counts

    def _insert_shops(self, cursor: sqlite3.Cursor, file_path: Path, import_id: str) -> int:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [
                (
                    import_id,
                    r["pwd_id"].strip(),
                    r["shop_name"].strip(),
                    r["dealer_id"].strip(),
                    r["district"].strip(),
                    r["state"].strip(),
                    int(r["monthly_capacity_kg"]),
                    float(r.get("gps_lat") or 0.0),
                    float(r.get("gps_lon") or 0.0),
                )
                for r in reader
            ]
        cursor.executemany(
            """
            INSERT INTO pwd_shops 
            (import_id, pwd_id, shop_name, dealer_id, district, state, monthly_capacity_kg, gps_lat, gps_lon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        return len(rows)

    def _insert_beneficiaries(self, cursor: sqlite3.Cursor, file_path: Path, import_id: str) -> int:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [
                (
                    import_id,
                    r["beneficiary_id"].strip(),
                    r["ration_card_id"].strip(),
                    r["head_name"].strip(),
                    int(r["family_size"]),
                    r["category"].strip(),
                    r["pwd_id"].strip(),
                    int(r["monthly_entitlement_kg"]),
                    r.get("last_collection_date", "").strip() or None,
                    r.get("collection_status", "collected").strip(),
                    r.get("identity_status", "verified").strip(),
                    r.get("review_reason", "").strip() or None,
                    1 if str(r.get("demo_record", "True")).lower() in ["true", "1"] else 0,
                )
                for r in reader
            ]
        cursor.executemany(
            """
            INSERT INTO beneficiaries 
            (import_id, beneficiary_id, ration_card_id, head_name, family_size, category, pwd_id,
             monthly_entitlement_kg, last_collection_date, collection_status, identity_status, review_reason, demo_record)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        return len(rows)

    def _insert_inventory(self, cursor: sqlite3.Cursor, file_path: Path, import_id: str) -> int:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [
                (
                    import_id,
                    r["inventory_id"].strip(),
                    r["pwd_id"].strip(),
                    r["month"].strip(),
                    r["commodity"].strip(),
                    int(r["opening_stock_kg"]),
                    int(r["received_kg"]),
                    int(r["distributed_kg"]),
                    int(r["closing_stock_kg"]),
                    int(r["physical_stock_kg"]),
                    r.get("unit", "kg").strip(),
                    1 if str(r.get("demo_record", "True")).lower() in ["true", "1"] else 0,
                )
                for r in reader
            ]
        cursor.executemany(
            """
            INSERT INTO inventory 
            (import_id, inventory_id, pwd_id, month, commodity, opening_stock_kg, received_kg,
             distributed_kg, closing_stock_kg, physical_stock_kg, unit, demo_record)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        return len(rows)

    def _insert_transactions(self, cursor: sqlite3.Cursor, file_path: Path, import_id: str) -> int:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [
                (
                    import_id,
                    r["transaction_id"].strip(),
                    r["beneficiary_id"].strip(),
                    r["pwd_id"].strip(),
                    r["date"].strip(),
                    r["commodity"].strip(),
                    int(r["quantity_kg"]),
                    r["channel"].strip(),
                    r["status"].strip(),
                    1 if str(r.get("demo_record", "True")).lower() in ["true", "1"] else 0,
                )
                for r in reader
            ]
        cursor.executemany(
            """
            INSERT INTO transactions 
            (import_id, transaction_id, beneficiary_id, pwd_id, date, commodity, quantity_kg, channel, status, demo_record)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        return len(rows)

    def _insert_audits(self, cursor: sqlite3.Cursor, file_path: Path, import_id: str) -> int:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [
                (
                    import_id,
                    r["audit_id"].strip(),
                    r["pwd_id"].strip(),
                    r["period"].strip(),
                    int(r["late_opening_days"]),
                    int(r["manual_override_count"]),
                    int(r["complaints_count"]),
                    r["inspection_status"].strip(),
                    1 if str(r.get("demo_record", "True")).lower() in ["true", "1"] else 0,
                )
                for r in reader
            ]
        cursor.executemany(
            """
            INSERT INTO pwd_audits 
            (import_id, audit_id, pwd_id, period, late_opening_days, manual_override_count, complaints_count, inspection_status, demo_record)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        return len(rows)

    def list_imports(self) -> List[ImportBatchSummary]:
        """Retrieve list of all historical import batches, ordered by timestamp descending."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT import_id, import_timestamp, dataset_name, total_records, status, source_type, source_path
                FROM import_batches
                ORDER BY import_timestamp DESC
                """
            )
            rows = cursor.fetchall()
            return [
                ImportBatchSummary(
                    import_id=row["import_id"],
                    import_timestamp=row["import_timestamp"],
                    dataset_name=row["dataset_name"],
                    total_records=row["total_records"],
                    status=row["status"],
                    source_type=row["source_type"],
                    source_path=row["source_path"],
                )
                for row in rows
            ]
