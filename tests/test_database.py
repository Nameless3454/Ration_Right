"""RationRight — Phase 2: database foundation tests.

Covers the normalized schema, enumeration validation, CRUD for all seven
models, foreign-key integrity, the provenance chain (transaction -> import ->
source; insight -> import), the deterministic synthetic seed (including
idempotency), and the agent-contract export used later to feed real data to
the existing agents.

Run from the project root::

    python3 -m unittest discover -s tests -t . -v
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

import database as db
from scripts.validate_dataset import DEFAULT_DATASET_PATH, load_dataset


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "test_rationright.db"
        self.conn = db.open_db(self.db_path)
        self.addCleanup(self.conn.close)
        self.addCleanup(self._tmp.cleanup)

    # ---------------- schema ----------------

    def test_schema_creates_all_tables(self):
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = {row["name"] for row in rows}
        for table in (
            "data_sources", "data_imports", "beneficiaries", "fps_centers",
            "ration_transactions", "inventory", "ai_insights",
        ):
            self.assertIn(table, names, "missing table %s" % table)

    def test_init_db_is_idempotent(self):
        db.init_db(self.conn)  # second run must not raise
        db.init_db(self.conn)

    def test_foreign_keys_are_enforced(self):
        self.conn.execute("PRAGMA foreign_keys = ON")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO data_imports (data_source_id, dataset_name, status, created_at) "
                "VALUES (999, 'ghost', 'PENDING', 'now')"
            )

    # ---------------- data source ----------------

    def test_insert_and_get_data_source(self):
        sid = db.insert_data_source(self.conn, name="Gov API", source_type="GOVERNMENT_DATASET")
        src = db.get_data_source(self.conn, sid)
        self.assertEqual(src["name"], "Gov API")
        self.assertEqual(src["type"], "GOVERNMENT_DATASET")
        self.assertEqual(src["status"], "ACTIVE")
        self.assertEqual(db.get_data_source_by_name(self.conn, "Gov API")["id"], sid)

    def test_data_source_enum_validation(self):
        with self.assertRaises(ValueError):
            db.insert_data_source(self.conn, name="x", source_type="DATABASE")
        with self.assertRaises(ValueError):
            db.insert_data_source(self.conn, name="x", source_type="CSV", status="SYNCED")

    def test_data_source_name_unique(self):
        db.insert_data_source(self.conn, name="dup", source_type="MANUAL")
        with self.assertRaises(sqlite3.IntegrityError):
            db.insert_data_source(self.conn, name="dup", source_type="MANUAL")

    def test_set_data_source_status(self):
        sid = db.insert_data_source(self.conn, name="s", source_type="API")
        db.set_data_source_status(self.conn, sid, "SYNCING")
        self.assertEqual(db.get_data_source(self.conn, sid)["status"], "SYNCING")
        with self.assertRaises(ValueError):
            db.set_data_source_status(self.conn, sid, "ON")

    # ---------------- data import ----------------

    def test_insert_and_get_data_import(self):
        sid = db.insert_data_source(self.conn, name="src", source_type="JSON")
        iid = db.insert_data_import(
            self.conn, data_source_id=sid, dataset_name="d1", file_name="a.json",
            file_type="json", record_count=10, successful_records=8,
            failed_records=2, duplicate_records=1, status="PARTIAL",
            error_summary="2 rows failed", started_at="t0", completed_at="t1",
        )
        imp = db.get_data_import(self.conn, iid)
        self.assertEqual(imp["data_source_id"], sid)
        self.assertEqual(imp["status"], "PARTIAL")
        self.assertEqual(imp["duplicate_records"], 1)

    def test_data_import_enum_validation(self):
        sid = db.insert_data_source(self.conn, name="src2", source_type="CSV")
        with self.assertRaises(ValueError):
            db.insert_data_import(self.conn, data_source_id=sid, dataset_name="d", status="DONE")
        with self.assertRaises(ValueError):
            db.insert_data_import(self.conn, data_source_id=sid, dataset_name="d", record_count=-1)

    def test_imports_for_source(self):
        sid = db.insert_data_source(self.conn, name="src3", source_type="JSON")
        i1 = db.insert_data_import(self.conn, data_source_id=sid, dataset_name="a")
        i2 = db.insert_data_import(self.conn, data_source_id=sid, dataset_name="b")
        ids = [r["id"] for r in db.get_imports_for_source(self.conn, sid)]
        self.assertEqual(ids, [i1, i2])

    # ---------------- beneficiary ----------------

    def test_upsert_beneficiary(self):
        bid = db.upsert_beneficiary(
            self.conn, external_reference="BEN999", state="MH", district="Pune",
            ration_category="AAY", family_size=4,
        )
        row = db.get_beneficiary_by_external_ref(self.conn, "BEN999")
        self.assertEqual(row["id"], bid)
        self.assertEqual(row["state"], "MH")
        self.assertEqual(row["ration_category"], "AAY")
        self.assertEqual(row["family_size"], 4)

    def test_upsert_beneficiary_updates_in_place(self):
        db.upsert_beneficiary(self.conn, external_reference="BEN1", district="Pune")
        bid2 = db.upsert_beneficiary(self.conn, external_reference="BEN1", district="Nagpur", family_size=3)
        rows = self.conn.execute("SELECT COUNT(*) AS n FROM beneficiaries").fetchone()
        self.assertEqual(rows["n"], 1, "upsert must not create duplicates")
        self.assertEqual(db.get_beneficiary_by_external_ref(self.conn, "BEN1")["id"], bid2)
        self.assertEqual(db.get_beneficiary_by_external_ref(self.conn, "BEN1")["district"], "Nagpur")

    def test_beneficiary_validation(self):
        with self.assertRaises(ValueError):
            db.upsert_beneficiary(self.conn, external_reference="", )
        with self.assertRaises(ValueError):
            db.upsert_beneficiary(self.conn, external_reference="B", family_size=0)
        with self.assertRaises(ValueError):
            db.upsert_beneficiary(self.conn, external_reference="B", status="BANNED")

    # ---------------- fps center ----------------

    def test_insert_and_get_fps_center(self):
        cid = db.insert_fps_center(
            self.conn, fps_code="FPS001", name="Kanpur Center #04", state="UP",
            district="Kanpur", location="Sector 4", latitude=26.44, longitude=80.33,
            capacity=5000,
        )
        row = db.get_fps_center_by_code(self.conn, "FPS001")
        self.assertEqual(row["id"], cid)
        self.assertEqual(row["capacity"], 5000)
        self.assertEqual(row["status"], "ACTIVE")

    def test_fps_center_validation(self):
        with self.assertRaises(ValueError):
            db.insert_fps_center(self.conn, fps_code="", )
        with self.assertRaises(ValueError):
            db.insert_fps_center(self.conn, fps_code="F", latitude=95)

    def test_fps_center_code_unique(self):
        db.insert_fps_center(self.conn, fps_code="FPS1")
        with self.assertRaises(sqlite3.IntegrityError):
            db.insert_fps_center(self.conn, fps_code="FPS1")

    # ---------------- transactions ----------------

    def _seeded_transaction(self):
        source_id = db.insert_data_source(self.conn, name="src", source_type="JSON")
        import_id = db.insert_data_import(self.conn, data_source_id=source_id, dataset_name="d")
        ben_id = db.upsert_beneficiary(self.conn, external_reference="BEN001")
        tx_id = db.insert_transaction(
            self.conn, external_transaction_id="TX001", beneficiary_id=ben_id,
            transaction_date="2026-08-01T10:00:00", commodity="rice", quantity=10,
            latitude=19.0760, longitude=72.8777, source_import_id=import_id,
        )
        return source_id, import_id, ben_id, tx_id

    def test_insert_and_get_transaction(self):
        _, import_id, _, tx_id = self._seeded_transaction()
        row = db.get_transaction_by_external_id(self.conn, "TX001")
        self.assertEqual(row["id"], tx_id)
        self.assertEqual(row["beneficiary_external_reference"], "BEN001")
        self.assertEqual(row["source_import_id"], import_id)
        self.assertEqual(row["unit"], "kg")

    def test_transaction_external_id_unique(self):
        self._seeded_transaction()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO ration_transactions (external_transaction_id, transaction_date, commodity, quantity, status, created_at) "
                "VALUES ('TX001', '2026-08-01', 'rice', 5, 'COMPLETED', 'now')"
            )

    def test_transaction_validation(self):
        ben_id = db.upsert_beneficiary(self.conn, external_reference="B1")
        with self.assertRaises(ValueError):
            db.insert_transaction(self.conn, external_transaction_id="T1", beneficiary_id=ben_id,
                                  transaction_date="2026-01-01", commodity="rice", quantity=0)
        with self.assertRaises(ValueError):
            db.insert_transaction(self.conn, external_transaction_id="T1", beneficiary_id=ben_id,
                                  transaction_date="2026-01-01", commodity="", quantity=1)
        with self.assertRaises(ValueError):
            db.insert_transaction(self.conn, external_transaction_id="T1", beneficiary_id=ben_id,
                                  transaction_date="2026-01-01", commodity="rice", quantity=1,
                                  status="REFUNDED")

    def test_transaction_bad_foreign_keys_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            db.insert_transaction(
                self.conn, external_transaction_id="T1", beneficiary_id=4242,
                transaction_date="2026-01-01", commodity="rice", quantity=1,
            )

    def test_agent_contract_export_matches_input(self):
        self._seeded_transaction()
        agent_rows = db.get_transactions_for_agent(self.conn)
        self.assertEqual(len(agent_rows), 1)
        expected = {
            "transaction_id": "TX001",
            "beneficiary_id": "BEN001",
            "timestamp": "2026-08-01T10:00:00",
            "latitude": 19.0760,
            "longitude": 72.8777,
            "ration_type": "rice",
            "quantity": 10,
        }
        self.assertEqual(agent_rows[0], expected)
        self.assertEqual(set(agent_rows[0].keys()), set(expected.keys()))

    # ---------------- inventory ----------------

    def test_insert_and_get_inventory(self):
        cid = db.insert_fps_center(self.conn, fps_code="F1")
        iid = db.insert_inventory(
            self.conn, fps_center_id=cid, commodity="wheat", current_stock=420.0,
            monthly_consumption=120.0, reorder_threshold=80.0,
        )
        rows = db.get_inventory_for_center(self.conn, cid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], iid)
        self.assertEqual(rows[0]["current_stock"], 420.0)

    def test_inventory_validation(self):
        with self.assertRaises(ValueError):
            db.insert_inventory(self.conn, commodity="wheat", current_stock=-1)
        with self.assertRaises(ValueError):
            db.insert_inventory(self.conn, commodity="", current_stock=1)

    # ---------------- ai insights ----------------

    def test_insert_and_get_ai_insight(self):
        source_id = db.insert_data_source(self.conn, name="s", source_type="JSON")
        import_id = db.insert_data_import(self.conn, data_source_id=source_id, dataset_name="d")
        insight_id = db.insert_ai_insight(
            self.conn, insight_type="DISTRIBUTION_ANOMALY", severity="HIGH",
            title="Rapid geographic transaction", description="TX001 / TX002",
            entity_type="BENEFICIARY", entity_id="BEN001", confidence=0.9,
            recommendation="Human verification", source_import_id=import_id,
        )
        rows = db.get_insights_for_import(self.conn, import_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], insight_id)
        self.assertEqual(rows[0]["source_import_id"], import_id)

    def test_ai_insight_enum_validation(self):
        with self.assertRaises(ValueError):
            db.insert_ai_insight(self.conn, insight_type="PREDICTION", severity="HIGH", title="t")
        with self.assertRaises(ValueError):
            db.insert_ai_insight(self.conn, insight_type="RECOMMENDATION", severity="SEVERE", title="t")
        with self.assertRaises(ValueError):
            db.insert_ai_insight(self.conn, insight_type="RECOMMENDATION", severity="HIGH", title="t", confidence=1.5)

    def test_insights_for_entity(self):
        source_id = db.insert_data_source(self.conn, name="s2", source_type="JSON")
        import_id = db.insert_data_import(self.conn, data_source_id=source_id, dataset_name="d")
        db.insert_ai_insight(self.conn, insight_type="INVENTORY_RISK", severity="MEDIUM",
                             title="Low wheat", entity_type="FPS_CENTER", entity_id="F1",
                             source_import_id=import_id)
        db.insert_ai_insight(self.conn, insight_type="DEMAND_FORECAST", severity="LOW",
                             title="Rice demand up", entity_type="FPS_CENTER", entity_id="F2",
                             source_import_id=import_id)
        rows = db.get_insights_for_entity(self.conn, "FPS_CENTER", "F1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Low wheat")

    # ---------------- seed + traceability ----------------

    def test_seed_synthetic_round_trip(self):
        summary = db.seed_synthetic(self.conn)
        self.assertEqual(summary["transactions"], 25)
        self.assertEqual(summary["beneficiaries"], 5)
        self.assertEqual(summary["fps_centers"], 0)
        self.assertEqual(summary["inventory"], 0)
        self.assertEqual(summary["ai_insights"], 0)

        # agent-contract export equals the source JSON exactly
        agent_rows = db.get_transactions_for_agent(self.conn)
        raw = load_dataset(DEFAULT_DATASET_PATH)["transactions"]
        self.assertEqual(len(agent_rows), len(raw))
        for got, expected in zip(agent_rows, raw):
            self.assertEqual(got["transaction_id"], expected["transaction_id"])
            self.assertEqual(got["beneficiary_id"], expected["beneficiary_id"])
            self.assertEqual(got["timestamp"], expected["timestamp"])
            self.assertEqual(got["latitude"], expected["latitude"])
            self.assertEqual(got["longitude"], expected["longitude"])
            self.assertEqual(got["ration_type"], expected["ration_type"])
            self.assertEqual(got["quantity"], expected["quantity"])

        # provenance chain: transaction -> import -> source
        tx = db.get_transaction_by_external_id(self.conn, "TX001")
        self.assertIsNotNone(tx)
        imp = db.get_data_import(self.conn, tx["source_import_id"])
        self.assertEqual(imp["dataset_name"], "rationright-synthetic-transactions")
        src = db.get_data_source(self.conn, imp["data_source_id"])
        self.assertEqual(src["name"], db.SYNTHETIC_SOURCE_NAME)
        self.assertEqual(src["type"], "JSON")
        self.assertEqual(imp["status"], "COMPLETED")
        self.assertEqual(imp["successful_records"], 25)

        # all 25 transactions point at the one import
        count = self.conn.execute(
            "SELECT COUNT(*) AS n FROM ration_transactions WHERE source_import_id = :iid",
            {"iid": imp["id"]},
        ).fetchone()["n"]
        self.assertEqual(count, 25)

        # beneficiaries exported are exactly BEN001..BEN005
        refs = sorted(b["external_reference"] for b in db.list_beneficiaries(self.conn))
        self.assertEqual(refs, ["BEN001", "BEN002", "BEN003", "BEN004", "BEN005"])

    def test_seed_synthetic_is_idempotent(self):
        db.seed_synthetic(self.conn)
        db.seed_synthetic(self.conn)
        db.seed_synthetic(self.conn)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) AS n FROM data_sources").fetchone()["n"], 1
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) AS n FROM data_imports").fetchone()["n"], 1
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) AS n FROM ration_transactions").fetchone()["n"], 25
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) AS n FROM beneficiaries").fetchone()["n"], 5
        )

    def test_transactions_for_beneficiary(self):
        db.seed_synthetic(self.conn)
        rows = db.get_transactions_for_beneficiary(self.conn, "BEN001")
        self.assertEqual(len(rows), 6)  # TX001..TX005 + TX025
        self.assertTrue(all(r["beneficiary_external_reference"] == "BEN001" for r in rows))

    def test_import_has_no_inventory_or_insights(self):
        summary = db.seed_synthetic(self.conn)
        self.assertEqual(db.get_inventory_for_import(self.conn, summary["data_import_id"]), [])
        self.assertEqual(db.get_insights_for_import(self.conn, summary["data_import_id"]), [])


class SeedDatabaseSmokeTest(unittest.TestCase):
    """End-to-end: seed via the public entry point on a temp file."""

    def test_seed_database_entry_point(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "seed.db"
            summary = db.seed_database(db_path=db_path)
            self.assertEqual(summary["transactions"], 25)
            conn = db.connect(db_path)
            try:
                n = conn.execute("SELECT COUNT(*) AS n FROM ration_transactions").fetchone()["n"]
                self.assertEqual(n, 25)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
