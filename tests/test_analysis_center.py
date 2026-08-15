"""RationRight — Phase 9: AI Analysis Command Center tests.

Covers ``analysis_center.py``: the analysis type registry, the backend
precheck (readiness per type, never faked), deterministic per-import insights
(operational risk, inventory risk, demand forecast with its sufficiency gate),
the merged command-center run (real agents + deterministic checks + persisted
config), analysis history/detail, and the API surface.

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

import analysis_center as ac
import database as db
from server import make_server

BASE = "http://127.0.0.1"


def _seed_synthetic(conn):
    db.seed_synthetic(conn)


def _seed_real(conn, months=4, with_inventory=True, with_failures=True):
    """A real import with enough history for every deterministic check."""
    src = db.get_data_source_by_name(conn, "Uploaded Dataset")
    src_id = db.insert_data_source(
        conn, name="Uploaded Dataset", source_type="MANUAL",
        description="t", status="ACTIVE",
    ) if src is None else src["id"]
    imp_id = db.insert_data_import(
        conn, data_source_id=src_id, dataset_name="pds_aug",
        file_name="pds_aug.csv", file_type="CSV", record_count=100,
        successful_records=100, status="COMPLETED",
    )
    db.upsert_beneficiaries(conn, [{"external_reference": "RB1", "district": "Lucknow",
                                    "ration_category": "AAY", "family_size": 4, "status": "ACTIVE"}])
    ben = db.beneficiary_ids(conn, ["RB1"])
    db.upsert_fps_centers(conn, [{"fps_code": "FPS1", "name": "Center One", "district": "Lucknow",
                                  "state": "UP", "status": "ACTIVE"}])
    fps = db.fps_center_ids(conn, ["FPS1"])
    rows = []
    seq = 0
    for month in range(months):
        m = "%02d" % (5 + month)  # 2026-05 .. 2026-08
        for i in range(3):
            seq += 1
            status = "FAILED" if (with_failures and i >= 1 and month == 0) else "COMPLETED"
            rows.append({
                "external_transaction_id": "TX%04d" % seq,
                "beneficiary_id": ben["RB1"], "fps_center_id": fps["FPS1"],
                "transaction_date": "2026-%s-%02d" % (m, i + 1),
                "commodity": "rice", "quantity": 100.0 + i * 10, "unit": "kg",
                "latitude": 26.8, "longitude": 80.9, "status": status,
                "source_import_id": imp_id,
            })
    db.insert_transactions_batch(conn, rows)
    if with_inventory:
        db.insert_inventory_batch(conn, [{
            "fps_center_id": fps["FPS1"], "commodity": "rice",
            "current_stock": 200.0, "monthly_consumption": 900.0,
            "reorder_threshold": 150.0, "source_import_id": imp_id,
        }])
    conn.commit()
    return imp_id


class RegistryAndPrecheckTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "ac.db"
        self.addCleanup(self._tmp.cleanup)
        self.conn = db.open_db(self.db_path)

    def test_registry_has_five_real_types(self):
        types = ac.analysis_type_registry()
        keys = {t["key"] for t in types}
        self.assertEqual(keys, {"distribution_anomaly", "recommendations",
                                "operational_risk", "inventory_risk", "demand_forecast"})
        kinds = {t["kind"] for t in types}
        self.assertEqual(kinds, {"agents", "deterministic"})
        # every type has a human description (no fake agent names)
        for t in types:
            self.assertTrue(t["label"] and t["description"])

    def test_precheck_synthetic_honest_disables(self):
        _seed_synthetic(self.conn)
        pre = ac.precheck(dataset_mode="synthetic", db_path=self.db_path)
        self.assertTrue(pre["ok"])
        by_key = {t["key"]: t for t in pre["types"]}
        self.assertTrue(by_key["distribution_anomaly"]["enabled"])
        self.assertTrue(by_key["operational_risk"]["enabled"])
        # no inventory -> disabled with an actionable reason (never faked)
        self.assertFalse(by_key["inventory_risk"]["enabled"])
        self.assertIn("no inventory records", by_key["inventory_risk"]["reason"].lower())
        # synthetic history is short -> forecast honestly disabled
        self.assertFalse(by_key["demand_forecast"]["enabled"])
        self.assertIn("historical month", by_key["demand_forecast"]["reason"].lower())

    def test_precheck_real_dataset_enables_with_data(self):
        imp_id = _seed_real(self.conn)
        pre = ac.precheck(dataset_mode="real", data_import_id=imp_id, db_path=self.db_path)
        by_key = {t["key"]: t for t in pre["types"]}
        self.assertEqual(pre["dataset"]["historical_months"], 4)
        self.assertTrue(by_key["demand_forecast"]["enabled"])
        self.assertTrue(by_key["inventory_risk"]["enabled"])
        self.assertTrue(by_key["distribution_anomaly"]["enabled"])

    def test_precheck_unknown_import(self):
        pre = ac.precheck(dataset_mode="real", data_import_id=999999, db_path=self.db_path)
        self.assertFalse(pre["ok"])


class DeterministicInsightsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "det.db"
        self.addCleanup(self._tmp.cleanup)
        self.conn = db.open_db(self.db_path)

    def test_operational_risk_detects_failure_rate(self):
        imp_id = _seed_real(self.conn, with_inventory=False, with_failures=True)
        conn = db.open_db(self.db_path)
        try:
            ops = ac.operational_risk_insights(conn, imp_id, {"analysis_id": "RA-T"})
        finally:
            conn.close()
        failure = [o for o in ops if "failure rate" in o["title"].lower()]
        self.assertEqual(len(failure), 1)
        self.assertGreaterEqual(failure[0]["evidence"]["failure_rate"], 0.10)
        self.assertEqual(failure[0]["insight_type"], "OPERATIONAL_RISK")

    def test_inventory_risk_projects_days_remaining(self):
        imp_id = _seed_real(self.conn)
        conn = db.open_db(self.db_path)
        try:
            inv = ac.inventory_risk_insights(conn, imp_id, {"analysis_id": "RA-T"})
        finally:
            conn.close()
        # stock 200, monthly 900 -> days = 200/(900/30) = 6.7 -> CRITICAL
        self.assertEqual(len(inv), 1)
        self.assertEqual(inv[0]["severity"], "CRITICAL")
        self.assertAlmostEqual(inv[0]["evidence"]["days_remaining"], 6.7, places=1)
        self.assertFalse(inv[0]["deterministic"] is True and False)  # deterministic flag is True
        self.assertTrue(inv[0]["deterministic"])

    def test_demand_forecast_sufficient_and_insufficient(self):
        imp_id = _seed_real(self.conn)  # 4 months
        conn = db.open_db(self.db_path)
        try:
            fc = ac.demand_forecast_insights(conn, imp_id, {"analysis_id": "RA-T"})
        finally:
            conn.close()
        completed = [f for f in fc if f["status"] == "completed"]
        self.assertEqual(len(completed), 1)
        self.assertIn("forecast", completed[0]["title"].lower())
        self.assertIn("historical_basis", completed[0]["evidence"])
        self.assertIsNotNone(completed[0]["confidence"])

        # a single-month import -> INSUFFICIENT_DATA, no guessed number
        tiny = db.insert_data_import(
            self.conn, data_source_id=1, dataset_name="tiny", record_count=2,
            successful_records=2, status="COMPLETED")
        db.upsert_fps_centers(self.conn, [{"fps_code": "FPS2", "status": "ACTIVE"}])
        fps = db.fps_center_ids(self.conn, ["FPS2"])
        db.insert_transactions_batch(self.conn, [
            {"external_transaction_id": "T1", "beneficiary_id": None, "fps_center_id": fps["FPS2"],
             "transaction_date": "2026-07-01", "commodity": "wheat", "quantity": 5.0, "unit": "kg",
             "latitude": 26.8, "longitude": 80.9, "status": "COMPLETED", "source_import_id": tiny},
            {"external_transaction_id": "T2", "beneficiary_id": None, "fps_center_id": fps["FPS2"],
             "transaction_date": "2026-07-02", "commodity": "wheat", "quantity": 6.0, "unit": "kg",
             "latitude": 26.9, "longitude": 81.0, "status": "COMPLETED", "source_import_id": tiny},
        ])
        self.conn.commit()
        conn = db.open_db(self.db_path)
        try:
            fc2 = ac.demand_forecast_insights(conn, tiny, {"analysis_id": "RA-T"})
        finally:
            conn.close()
        self.assertEqual(len(fc2), 1)
        self.assertEqual(fc2[0]["status"], "insufficient_data")
        self.assertIn("historical period", fc2[0]["reason"])
        self.assertNotIn("predicted_quantity", fc2[0]["evidence"])


class RunAnalysisTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "run.db"
        self.addCleanup(self._tmp.cleanup)
        self.conn = db.open_db(self.db_path)

    def test_run_analysis_synthetic_merges_insights(self):
        _seed_synthetic(self.conn)
        r = ac.run_analysis(
            dataset_mode="synthetic",
            types=["distribution_anomaly", "recommendations", "operational_risk",
                   "inventory_risk", "demand_forecast"],
            db_path=self.db_path,
        )
        self.assertIsNotNone(r)
        # merged result keeps the Phase 6 shape
        self.assertEqual(r["workflow_status"], "completed")
        self.assertIn("insights", r)
        self.assertGreaterEqual(len(r["insights"]), 5)  # 4 forecast + anomaly + rec
        self.assertIn("types", r)
        self.assertEqual(r["types"]["distribution_anomaly"]["status"], "completed")
        self.assertEqual(r["types"]["recommendations"]["status"], "completed")
        self.assertEqual(r["types"]["inventory_risk"]["status"], "insufficient_data")
        # analysis run persisted with the real id stamped on sources
        run = r["analysis_run"]
        self.assertTrue(run["analysis_id"].startswith("RA-"))
        for i in r["insights"]:
            self.assertEqual(i["source"]["analysis_id"], run["analysis_id"])
        # real stage timings from the orchestrator
        self.assertEqual(set((r.get("timings") or {}).keys()),
                         {"agent_1", "agent_2", "agent_3", "agent_4"})

    def test_run_analysis_real_with_filters(self):
        imp_id = _seed_real(self.conn)
        r = ac.run_analysis(
            dataset_mode="real", data_import_id=imp_id,
            types=["distribution_anomaly", "recommendations", "operational_risk",
                   "inventory_risk", "demand_forecast"],
            filters={"commodity": "rice"}, db_path=self.db_path,
        )
        self.assertIsNotNone(r)
        self.assertEqual(r["types"]["demand_forecast"]["status"], "completed")
        self.assertEqual(r["types"]["inventory_risk"]["status"], "completed")
        self.assertIn("filters_applied", r["dataset"])
        self.assertEqual(r["dataset"]["filters_applied"]["commodity"], "rice")

    def test_run_analysis_unknown_import(self):
        r = ac.run_analysis(dataset_mode="real", data_import_id=999999, types=["distribution_anomaly"], db_path=self.db_path)
        self.assertIsNone(r)

    def test_history_and_detail_round_trip(self):
        _seed_synthetic(self.conn)
        r = ac.run_analysis(
            dataset_mode="synthetic",
            types=["distribution_anomaly", "recommendations"],
            filters={"commodity": "rice"}, db_path=self.db_path,
        )
        hist = ac.analysis_history(db_path=self.db_path)
        self.assertEqual(hist["total"], 1)
        entry = hist["runs"][0]
        self.assertEqual(entry["analysis_id"], r["analysis_run"]["analysis_id"])
        self.assertEqual(entry["analysis_types"], ["distribution_anomaly", "recommendations"])
        self.assertGreater(entry["insight_count"], 0)
        detail = ac.analysis_detail(entry["id"], db_path=self.db_path)
        self.assertEqual(detail["filters"]["commodity"], "rice")
        self.assertIsNotNone(detail["timings"])

    def test_history_empty(self):
        hist = ac.analysis_history(db_path=self.db_path)
        self.assertEqual(hist["total"], 0)
        self.assertEqual(hist["runs"], [])


class AnalysisCenterApiTests(unittest.TestCase):
    """End-to-end API tests against the real server (dev DB)."""

    @classmethod
    def setUpClass(cls):
        cls.server = make_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.base = f"{BASE}:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def request(self, method, path, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"} if data else {}
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_types_endpoint(self):
        status, payload = self.request("GET", "/api/analysis/types")
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["types"]), 5)

    def test_precheck_endpoint(self):
        status, payload = self.request("POST", "/api/analysis/precheck", {"dataset": "synthetic"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["dataset"]["dataset_name"], "Synthetic Demo Dataset")
        self.assertEqual(len(payload["types"]), 5)

    def test_analyze_command_center(self):
        status, payload = self.request("POST", "/api/analyze", {
            "dataset": "synthetic",
            "types": ["distribution_anomaly", "recommendations"],
        })
        self.assertEqual(status, 200)
        self.assertIn("insights", payload)
        self.assertIn("analysis_run", payload)
        self.assertIn("types", payload)
        self.assertGreaterEqual(len(payload["insights"]), 2)

    def test_analyze_unknown_type_400(self):
        status, payload = self.request("POST", "/api/analyze", {
            "dataset": "synthetic", "types": ["bogus"],
        })
        self.assertEqual(status, 400)
        self.assertIn("Unknown analysis type", payload["error"])

    def test_analyze_unknown_import_404(self):
        status, payload = self.request("POST", "/api/analyze", {
            "dataset": "real", "data_import_id": 999999,
            "types": ["distribution_anomaly"],
        })
        self.assertEqual(status, 404)

    def test_analyze_invalid_filters_400(self):
        status, _ = self.request("POST", "/api/analyze", {
            "dataset": "synthetic", "types": ["distribution_anomaly"],
            "filters": "not-an-object",
        })
        self.assertEqual(status, 400)

    def test_history_endpoints(self):
        status, payload = self.request("GET", "/api/analysis/history?per_page=5")
        self.assertEqual(status, 200)
        self.assertIn("runs", payload)
        if payload["runs"]:
            rid = payload["runs"][0]["id"]
            status, detail = self.request("GET", "/api/analysis/history/%d" % rid)
            self.assertEqual(status, 200)
            self.assertEqual(detail["id"], rid)
        status, _ = self.request("GET", "/api/analysis/history/999999")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
