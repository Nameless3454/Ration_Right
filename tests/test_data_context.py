"""RationRight — Phase 6: real-data multi-agent connection tests.

Covers the data context layer (``data_context.py``): dataset selection for
the agents, agent-contract transaction export, data sufficiency checks,
provenance + data-quality attachment, and the extended ``/api/analyze``
contract (``synthetic`` vs ``real`` + ``data_import_id``). The four existing
agents and the orchestrator are NOT modified — this phase only changes what
data feeds them.

Run from the project root::

    python3 -m unittest discover -s tests -t . -v
"""

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import database as db
import data_context as dc
from server import make_server

BASE = "http://127.0.0.1"


def _seed(conn, with_tiny_import=False):
    """Deterministic temp DB: synthetic seed + one real upload import."""
    db.seed_synthetic(conn)
    src_id = db.get_data_source_by_name(conn, "Uploaded Dataset")
    if src_id is None:
        src_id = db.insert_data_source(
            conn, name="Uploaded Dataset", source_type="MANUAL",
            description="test", status="ACTIVE",
        )
    imp_id = db.insert_data_import(
        conn, data_source_id=src_id, dataset_name="up_test_aug",
        file_name="up_test.csv", file_type="CSV", record_count=3,
        successful_records=3, status="COMPLETED",
    )
    db.upsert_beneficiaries(conn, [
        {"external_reference": "RB001", "state": "UP", "district": "Lucknow",
         "ration_category": "AAY", "family_size": 4, "status": "ACTIVE"},
    ])
    ben_map = db.beneficiary_ids(conn, ["RB001"])
    db.upsert_fps_centers(conn, [
        {"fps_code": "FPS99", "name": "Test Center", "district": "Lucknow",
         "state": "UP", "status": "ACTIVE"},
    ])
    center_map = db.fps_center_ids(conn, ["FPS99"])
    db.insert_transactions_batch(conn, [
        {"external_transaction_id": "RT1", "beneficiary_id": ben_map["RB001"],
         "fps_center_id": center_map["FPS99"], "transaction_date": "2026-08-01",
         "commodity": "rice", "quantity": 100.0, "unit": "kg", "status": "COMPLETED",
         "source_import_id": imp_id, "latitude": 26.8, "longitude": 80.9},
        {"external_transaction_id": "RT2", "beneficiary_id": ben_map["RB001"],
         "fps_center_id": center_map["FPS99"], "transaction_date": "2026-08-02",
         "commodity": "rice", "quantity": 120.0, "unit": "kg", "status": "COMPLETED",
         "source_import_id": imp_id, "latitude": 26.9, "longitude": 81.0},
        {"external_transaction_id": "RT3", "beneficiary_id": ben_map["RB001"],
         "fps_center_id": center_map["FPS99"], "transaction_date": "2026-08-03",
         "commodity": "wheat", "quantity": 40.0, "unit": "kg", "status": "COMPLETED",
         "source_import_id": imp_id, "latitude": 26.7, "longitude": 80.8},
    ])
    tiny_imp_id = None
    if with_tiny_import:
        tiny_imp_id = db.insert_data_import(
            conn, data_source_id=src_id, dataset_name="tiny_one_tx",
            file_name="tiny.csv", file_type="CSV", record_count=1,
            successful_records=1, status="COMPLETED",
        )
        db.insert_transactions_batch(conn, [
            {"external_transaction_id": "RT9", "beneficiary_id": ben_map["RB001"],
             "fps_center_id": center_map["FPS99"], "transaction_date": "2026-08-04",
             "commodity": "rice", "quantity": 10.0, "unit": "kg", "status": "COMPLETED",
             "source_import_id": tiny_imp_id, "latitude": 26.8, "longitude": 80.9},
        ])
    conn.commit()
    return imp_id, tiny_imp_id


class DataContextServiceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "dc.db"
        self.addCleanup(self._tmp.cleanup)
        self.conn = db.open_db(self.db_path)
        self.imp_id, self.tiny_imp_id = _seed(self.conn, with_tiny_import=True)

    def tearDown(self):
        self.conn.close()

    # ---- dataset selection ----

    def test_list_agent_datasets_excludes_synthetic_source(self):
        datasets = dc.list_agent_datasets(str(self.db_path))
        names = [d["dataset_name"] for d in datasets]
        self.assertIn("up_test_aug", names)
        # The seeded synthetic source must not appear as a "real" dataset.
        self.assertNotIn("rationright-synthetic-transactions", names)
        by_name = {d["dataset_name"]: d for d in datasets}
        self.assertEqual(by_name["up_test_aug"]["transaction_count"], 3)

    def test_prepare_agent_context_returns_agent_contract(self):
        ctx = dc.prepare_agent_context(self.imp_id, str(self.db_path))
        self.assertTrue(ctx["sufficient"])
        self.assertEqual(len(ctx["transactions"]), 3)
        tx = ctx["transactions"][0]
        # Exactly the documented 7-field agent shape + coordinates.
        self.assertEqual(
            set(tx),
            {"transaction_id", "beneficiary_id", "timestamp", "latitude",
             "longitude", "ration_type", "quantity"},
        )
        self.assertEqual(tx["transaction_id"], "RT1")
        self.assertEqual(tx["beneficiary_id"], "RB001")
        self.assertEqual(tx["timestamp"], "2026-08-01")
        self.assertEqual(tx["ration_type"], "rice")

    def test_provenance_and_quality(self):
        ctx = dc.prepare_agent_context(self.imp_id, str(self.db_path))
        d = ctx["dataset"]
        self.assertEqual(d["mode"], "real")
        self.assertEqual(d["data_import_id"], self.imp_id)
        self.assertEqual(d["dataset_name"], "up_test_aug")
        self.assertEqual(d["source_name"], "Uploaded Dataset")
        self.assertEqual(d["data_quality"], 1.0)  # 3/3 successful
        self.assertEqual(d["transaction_count"], 3)
        self.assertEqual(d["date_range"], ["2026-08-01", "2026-08-03"])
        self.assertEqual(d["commodities"], ["rice", "wheat"])

    def test_unknown_import_returns_none(self):
        self.assertIsNone(dc.prepare_agent_context(9999, str(self.db_path)))
        self.assertIsNone(dc.run_workflow_on_dataset(9999, db_path=str(self.db_path)))

    # ---- sufficiency ----

    def test_insufficient_data_never_invokes_agents(self):
        ctx = dc.prepare_agent_context(self.tiny_imp_id, str(self.db_path))
        self.assertFalse(ctx["sufficient"])
        self.assertIn("at least 2 are required", ctx["dataset"]["reason"])
        self.assertIsInstance(ctx["dataset"]["required_data"], list)
        result = dc.run_workflow_on_dataset(self.tiny_imp_id, db_path=str(self.db_path))
        self.assertEqual(result["workflow_status"], "completed")
        self.assertEqual(result["stages"]["agent_1"], "skipped")
        self.assertEqual(result["stages"]["agent_2"], "skipped")
        self.assertEqual(result["stages"]["agent_3"], "skipped")
        self.assertEqual(result["stages"]["agent_4"], "skipped")
        self.assertEqual(result["anomalies"], [])
        self.assertEqual(result["alerts"], [])
        self.assertIn("reason", result["dataset"])

    # ---- end-to-end real workflow ----

    def test_real_workflow_completes_with_provenance(self):
        result = dc.run_workflow_on_dataset(self.imp_id, db_path=str(self.db_path))
        self.assertEqual(result["workflow_status"], "completed")
        self.assertEqual(result["stages"]["agent_1"], "completed")
        # Clean data -> no anomalies -> later stages skipped, not failed.
        self.assertEqual(result["anomalies"], [])
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["cases"], [])
        self.assertEqual(result["alerts"], [])
        self.assertEqual(result["dataset"]["data_import_id"], self.imp_id)
        self.assertEqual(result["dataset"]["transaction_count"], 3)

    def test_real_workflow_traceability_when_anomaly_present(self):
        # A dataset with a rapid geographic pattern must flow through ALL
        # agents and keep IDs connected end to end.
        conn = db.open_db(self.db_path)
        src = db.get_data_source_by_name(conn, "Uploaded Dataset")
        src_id = src["id"] if src else db.insert_data_source(
            conn, name="Uploaded Dataset", source_type="MANUAL",
            description="test", status="ACTIVE",
        )
        imp = db.insert_data_import(
            conn, data_source_id=src_id, dataset_name="anomaly_set",
            file_name="a.csv", file_type="CSV", record_count=4,
            successful_records=4, status="COMPLETED",
        )
        ben_map = db.beneficiary_ids(conn, ["RB001"])
        center_map = db.fps_center_ids(conn, ["FPS99"])
        db.insert_transactions_batch(conn, [
            {"external_transaction_id": "AX1", "beneficiary_id": ben_map["RB001"],
             "fps_center_id": center_map["FPS99"], "transaction_date": "2026-08-01 10:00",
             "commodity": "rice", "quantity": 100.0, "unit": "kg", "status": "COMPLETED",
             "source_import_id": imp, "latitude": 26.8, "longitude": 80.9},
            # Same beneficiary, 30 minutes later, ~400 km away -> candidate.
            {"external_transaction_id": "AX2", "beneficiary_id": ben_map["RB001"],
             "fps_center_id": center_map["FPS99"], "transaction_date": "2026-08-01 10:30",
             "commodity": "rice", "quantity": 120.0, "unit": "kg", "status": "COMPLETED",
             "source_import_id": imp, "latitude": 29.9, "longitude": 78.1},
            {"external_transaction_id": "AX3", "beneficiary_id": ben_map["RB001"],
             "fps_center_id": center_map["FPS99"], "transaction_date": "2026-08-02 09:00",
             "commodity": "wheat", "quantity": 30.0, "unit": "kg", "status": "COMPLETED",
             "source_import_id": imp, "latitude": 26.8, "longitude": 80.9},
            {"external_transaction_id": "AX4", "beneficiary_id": ben_map["RB001"],
             "fps_center_id": center_map["FPS99"], "transaction_date": "2026-08-02 09:15",
             "commodity": "wheat", "quantity": 20.0, "unit": "kg", "status": "COMPLETED",
             "source_import_id": imp, "latitude": 26.9, "longitude": 81.0},
        ])
        conn.commit()
        conn.close()

        result = dc.run_workflow_on_dataset(imp, db_path=str(self.db_path))
        self.assertEqual(result["workflow_status"], "completed")
        self.assertEqual(result["stages"]["agent_4"], "completed")
        self.assertTrue(result["anomalies"])
        self.assertTrue(result["findings"])
        self.assertTrue(result["cases"])
        self.assertTrue(result["alerts"])
        # Traceability: alert -> case -> finding -> anomaly -> transactions.
        alert = result["alerts"][0]
        case = next(c for c in result["cases"] if c["case_id"] == alert["case_id"])
        finding = next(f for f in result["findings"] if f["finding_id"] in case["finding_ids"])
        anomaly = next(a for a in result["anomalies"] if a["anomaly_id"] == finding["anomaly_id"])
        tx_ids = anomaly["transaction_ids"]
        self.assertTrue(tx_ids)
        self.assertEqual(set(tx_ids), {"AX1", "AX2"})
        self.assertEqual(result["dataset"]["data_import_id"], imp)
        # Evidence is deterministic backend math, present on the finding.
        self.assertGreaterEqual(finding["evidence"]["distance_km"], 300)

    def test_quality_reflects_partial_import(self):
        # successful 2 of 5 -> quality 0.4
        conn = db.open_db(self.db_path)
        src = db.get_data_source_by_name(conn, "Uploaded Dataset")
        src_id = src["id"] if src else db.insert_data_source(
            conn, name="Uploaded Dataset", source_type="MANUAL",
            description="test", status="ACTIVE",
        )
        imp = db.insert_data_import(
            conn, data_source_id=src_id, dataset_name="partial_set",
            file_name="p.csv", file_type="CSV", record_count=5,
            successful_records=2, status="PARTIAL",
        )
        ben_map = db.beneficiary_ids(conn, ["RB001"])
        center_map = db.fps_center_ids(conn, ["FPS99"])
        db.insert_transactions_batch(conn, [
            {"external_transaction_id": "PX%d" % n, "beneficiary_id": ben_map["RB001"],
             "fps_center_id": center_map["FPS99"], "transaction_date": "2026-08-%02d" % n,
             "commodity": "rice", "quantity": 10.0, "unit": "kg", "status": "COMPLETED",
             "source_import_id": imp, "latitude": 26.8, "longitude": 80.9}
            for n in (5, 6, 7)
        ])
        conn.commit()
        conn.close()
        ctx = dc.prepare_agent_context(imp, str(self.db_path))
        self.assertEqual(ctx["dataset"]["data_quality"], 0.4)


class AnalyzeApiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "api.db"
        self.addCleanup(self._tmp.cleanup)
        conn = db.open_db(self.db_path)
        self.imp_id, _ = _seed(conn)
        conn.close()
        self.server = make_server("127.0.0.1", 0, db_path=str(self.db_path))
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def _post(self, path, body):
        req = urllib.request.Request(
            BASE + ":%d%s" % (self.port, path),
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def _get(self, path):
        with urllib.request.urlopen(BASE + ":%d%s" % (self.port, path), timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_datasets_endpoint(self):
        status, payload = self._get("/api/datasets")
        self.assertEqual(status, 200)
        names = [d["dataset_name"] for d in payload["datasets"]]
        self.assertIn("up_test_aug", names)

    def test_analyze_real(self):
        status, result = self._post("/api/analyze", {"dataset": "real", "data_import_id": self.imp_id})
        self.assertEqual(status, 200)
        self.assertEqual(result["workflow_status"], "completed")
        self.assertEqual(result["dataset"]["mode"], "real")
        self.assertEqual(result["dataset"]["data_import_id"], self.imp_id)
        self.assertEqual(result["dataset"]["data_quality"], 1.0)

    def test_analyze_real_requires_import_id(self):
        status, payload = self._post("/api/analyze", {"dataset": "real"})
        self.assertEqual(status, 400)
        self.assertIn("data_import_id", payload["error"])

    def test_analyze_real_unknown_import(self):
        status, payload = self._post("/api/analyze", {"dataset": "real", "data_import_id": 9999})
        self.assertEqual(status, 404)
        self.assertIn("Unknown data_import_id", payload["error"])

    def test_analyze_unknown_mode(self):
        status, payload = self._post("/api/analyze", {"dataset": "bogus"})
        self.assertEqual(status, 400)
        self.assertIn("synthetic", payload["error"])

    def test_analyze_synthetic_unchanged_with_dataset_block(self):
        status, result = self._post("/api/analyze", {"dataset": "synthetic"})
        self.assertEqual(status, 200)
        # Regression: the demo dataset still produces its planted anomaly.
        self.assertEqual(result["workflow_status"], "completed")
        self.assertEqual(len(result["anomalies"]), 1)
        self.assertEqual(len(result["alerts"]), 1)
        self.assertEqual(result["dataset"]["mode"], "synthetic")
        self.assertEqual(result["dataset"]["dataset_name"], "Synthetic Demo Dataset")
        self.assertEqual(result["dataset"]["transaction_count"], 25)

    def test_analyze_defaults_to_synthetic(self):
        status, result = self._post("/api/analyze", {})
        self.assertEqual(status, 200)
        self.assertEqual(result["dataset"]["mode"], "synthetic")


if __name__ == "__main__":
    unittest.main()
