"""RationRight — Phase 5: database analytics tests.

Covers the analytics service (``analytics.py``) and its HTTP endpoints:
overview KPIs, distribution aggregation, inventory risk, beneficiary
search/filter/pagination/sort, FPS analytics, deterministic operational
alerts, date-range filtering, empty databases, and API validation.

Run from the project root::

    python3 -m unittest discover -s tests -t . -v
"""

import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import analytics
import database as db
from server import make_server

BASE = "http://127.0.0.1"


def _seed(conn, with_inventory=True):
    """Seed a deterministic, known dataset into a temp database."""
    db.seed_synthetic(conn)
    src_id = db.get_data_source_by_name(conn, "Uploaded Dataset")
    if src_id is None:
        src_id = db.insert_data_source(
            conn, name="Uploaded Dataset", source_type="MANUAL",
            description="test", status="ACTIVE",
        )
    imp_id = db.insert_data_import(
        conn, data_source_id=src_id, dataset_name="test_up",
        file_name="t.csv", file_type="CSV", record_count=5,
        status="COMPLETED",
    )
    db.upsert_beneficiaries(conn, [
        {"external_reference": "REAL001", "state": "UP", "district": "Lucknow",
         "ration_category": "AAY", "family_size": 4, "status": "ACTIVE"},
        {"external_reference": "REAL002", "state": "UP", "district": "Kanpur",
         "ration_category": "PHH", "family_size": 3, "status": "ACTIVE"},
        {"external_reference": "REAL003", "state": "MH", "district": "Pune",
         "ration_category": "PHH", "family_size": 5, "status": "INACTIVE"},
    ])
    ben_map = db.beneficiary_ids(conn, ["REAL001", "REAL002", "REAL003"])
    db.upsert_fps_centers(conn, [
        {"fps_code": "FPS10", "name": "Lucknow Center", "district": "Lucknow",
         "state": "UP", "status": "ACTIVE"},
        {"fps_code": "FPS11", "name": "Kanpur Center", "district": "Kanpur",
         "state": "UP", "status": "ACTIVE"},
        {"fps_code": "FPS12", "name": "Pune Center", "district": "Pune",
         "state": "MH", "status": "ACTIVE"},
    ])
    center_map = db.fps_center_ids(conn, ["FPS10", "FPS11", "FPS12"])
    db.insert_transactions_batch(conn, [
        {"external_transaction_id": "R1", "beneficiary_id": ben_map["REAL001"],
         "fps_center_id": center_map["FPS10"], "transaction_date": "2026-08-01",
         "commodity": "rice", "quantity": 100.0, "unit": "kg", "status": "COMPLETED",
         "source_import_id": imp_id, "latitude": 26.8, "longitude": 80.9},
        {"external_transaction_id": "R2", "beneficiary_id": ben_map["REAL001"],
         "fps_center_id": center_map["FPS10"], "transaction_date": "2026-08-03",
         "commodity": "wheat", "quantity": 50.0, "unit": "kg", "status": "COMPLETED",
         "source_import_id": imp_id, "latitude": 26.8, "longitude": 80.9},
        {"external_transaction_id": "R3", "beneficiary_id": ben_map["REAL002"],
         "fps_center_id": center_map["FPS11"], "transaction_date": "2026-08-05",
         "commodity": "rice", "quantity": 40.0, "unit": "kg", "status": "FAILED",
         "source_import_id": imp_id, "latitude": 26.4, "longitude": 80.3},
        {"external_transaction_id": "R4", "beneficiary_id": ben_map["REAL003"],
         "fps_center_id": center_map["FPS12"], "transaction_date": "2026-08-07",
         "commodity": "pulses", "quantity": 25.0, "unit": "kg", "status": "COMPLETED",
         "source_import_id": imp_id, "latitude": 18.5, "longitude": 73.8},
    ] + [
        # Four more failures at FPS11 so HIGH_FAILURE_RATE triggers (5 tx, all failed).
        {"external_transaction_id": "R%d" % n, "beneficiary_id": ben_map["REAL002"],
         "fps_center_id": center_map["FPS11"], "transaction_date": "2026-08-%02d" % n,
         "commodity": "wheat", "quantity": 1.0, "unit": "kg", "status": "FAILED",
         "source_import_id": imp_id, "latitude": 26.4, "longitude": 80.3}
        for n in (5, 6, 7, 8)
    ])
    if with_inventory:
        db.insert_inventory_batch(conn, [
            {"fps_center_id": center_map["FPS10"], "commodity": "rice",
             "current_stock": 500.0, "monthly_consumption": 300.0,
             "reorder_threshold": 200.0, "source_import_id": imp_id},
            {"fps_center_id": center_map["FPS10"], "commodity": "wheat",
             "current_stock": 100.0, "monthly_consumption": 400.0,
             "reorder_threshold": 150.0, "source_import_id": imp_id},
        ])
    conn.commit()
    return imp_id


class AnalyticsServiceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "an.db"
        self.addCleanup(self._tmp.cleanup)
        self.conn = db.open_db(self.db_path)
        _seed(self.conn)

    def tearDown(self):
        self.conn.close()

    # ---- overview ----
    def test_overview_kpis(self):
        ov = analytics.overview(self.conn)
        self.assertEqual(ov["total_beneficiaries"], 5 + 3)  # synthetic 5 + real 3
        self.assertEqual(ov["active_beneficiaries"], 5 + 2)
        self.assertEqual(ov["total_fps_centers"], 3)  # synthetic seed creates none
        self.assertEqual(ov["total_transactions"], 25 + 8)
        self.assertEqual(ov["ration_distributed_kg"], 184.0 + 219.0)  # synthetic + real rows
        self.assertEqual(ov["by_status"]["COMPLETED"], 25 + 3)
        self.assertEqual(ov["by_status"]["FAILED"], 5)
        self.assertEqual(ov["districts_covered"], 3)
        self.assertIn("rice", ov["commodities_distributed"])

    def test_overview_provenance(self):
        ov = analytics.overview(self.conn)
        names = {s["name"]: s["transaction_count"] for s in ov["data_sources"]}
        self.assertEqual(names.get("Synthetic Demo Dataset"), 25)
        self.assertEqual(names.get("Uploaded Dataset"), 8)
        self.assertIsNotNone(ov["last_import"])

    def test_overview_range_filter(self):
        ov7 = analytics.overview(self.conn, range_key="7d")  # last 7 days from today
        self.assertLessEqual(ov7["total_transactions"], 25 + 4)
        with self.assertRaises(analytics.AnalyticsError):
            analytics.overview(self.conn, range_key="bogus")
        with self.assertRaises(analytics.AnalyticsError):
            analytics.overview(self.conn, range_key="custom")  # missing from/to
        with self.assertRaises(analytics.AnalyticsError):
            analytics.overview(self.conn, range_key="custom", from_date="2026-09-01", to_date="2026-08-01")
        ov_custom = analytics.overview(self.conn, range_key="custom",
                                       from_date="2026-08-01", to_date="2026-08-05")
        # matches the raw SQL over the same window (consistency check)
        raw = self.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(quantity), 0) FROM ration_transactions "
            "WHERE substr(transaction_date, 1, 10) BETWEEN '2026-08-01' AND '2026-08-05'"
        ).fetchone()
        self.assertEqual(ov_custom["total_transactions"], raw[0])
        self.assertEqual(ov_custom["ration_distributed_kg"], raw[1])

    # ---- distribution ----
    def test_distribution_aggregates(self):
        d = analytics.distribution(self.conn, granularity="day")
        self.assertEqual(d["total_quantity"], 403.0)
        by = {c["commodity"]: c["quantity"] for c in d["by_commodity"]}
        # totals must equal the raw SQL (aggregation correctness)
        for commodity in ("rice", "wheat", "pulses", "kerosene", "sugar"):
            raw = self.conn.execute(
                "SELECT COALESCE(SUM(quantity), 0) FROM ration_transactions WHERE commodity = ?",
                (commodity,),
            ).fetchone()[0]
            self.assertEqual(by.get(commodity, 0.0), raw, commodity)
        districts = {r["district"]: r["quantity"] for r in d["by_district"]}
        self.assertEqual(districts["Lucknow"], 150.0)
        self.assertEqual(districts["Kanpur"], 44.0)
        centers = {r["fps_code"]: r["quantity"] for r in d["by_center"]}
        self.assertEqual(centers["FPS10"], 150.0)
        statuses = {r["status"]: r["count"] for r in d["by_status"]}
        self.assertEqual(statuses["FAILED"], 5)

    def test_distribution_trend_backfills(self):
        d = analytics.distribution(self.conn, granularity="day")
        self.assertEqual(d["trend"]["granularity"], "day")
        self.assertGreater(len(d["trend"]["labels"]), 0)
        for commodity in d["trend"]["series"]:
            self.assertEqual(len(d["trend"]["series"][commodity]), len(d["trend"]["labels"]))
        # sum of a commodity's trend must equal its by_commodity total (consistency)
        by = {c["commodity"]: c["quantity"] for c in d["by_commodity"]}
        for commodity, values in d["trend"]["series"].items():
            self.assertAlmostEqual(sum(values), by.get(commodity, 0.0), places=2)
        m = analytics.distribution(self.conn, granularity="month")
        self.assertTrue(all(len(b) == 7 for b in m["trend"]["labels"]))
        w = analytics.distribution(self.conn, granularity="week")
        self.assertTrue(all("W" in b for b in w["trend"]["labels"]))
        with self.assertRaises(analytics.AnalyticsError):
            analytics.distribution(self.conn, granularity="year")

    # ---- inventory ----
    def test_inventory_risk(self):
        inv = analytics.inventory(self.conn)
        self.assertEqual(inv["total_stock_kg"], 600.0)
        by = {c["commodity"]: c for c in inv["by_commodity"]}
        # rice: 500 * 30 / 300 = 50 days -> HEALTHY
        self.assertEqual(by["rice"]["days_remaining"], 50.0)
        self.assertEqual(by["rice"]["status"], "HEALTHY")
        # wheat: 100 * 30 / 400 = 7.5 days -> CRITICAL
        self.assertEqual(by["wheat"]["days_remaining"], 7.5)
        self.assertEqual(by["wheat"]["status"], "CRITICAL")
        self.assertEqual(len(inv["low_stock_items"]), 1)  # wheat below threshold
        self.assertEqual(inv["low_stock_items"][0]["commodity"], "wheat")
        self.assertIn("critical_days", inv["thresholds"])

    # ---- beneficiaries ----
    def test_beneficiaries_pagination_and_filters(self):
        p1 = analytics.beneficiaries(self.conn, page=1, per_page=5)
        self.assertEqual(p1["total"], 8)
        self.assertEqual(len(p1["rows"]), 5)
        self.assertEqual(p1["active"], 7)
        p2 = analytics.beneficiaries(self.conn, page=2, per_page=5)
        self.assertEqual(len(p2["rows"]), 3)
        # filter by district
        lko = analytics.beneficiaries(self.conn, district="Lucknow")
        self.assertEqual(lko["total"], 1)
        self.assertEqual(lko["rows"][0]["external_reference"], "REAL001")
        # filter by status
        inact = analytics.beneficiaries(self.conn, status="INACTIVE")
        self.assertEqual(inact["total"], 1)
        self.assertEqual(inact["rows"][0]["external_reference"], "REAL003")
        # search
        q = analytics.beneficiaries(self.conn, q="REAL")
        self.assertEqual(q["total"], 3)
        q2 = analytics.beneficiaries(self.conn, q="real002")
        self.assertEqual(q2["total"], 1)
        # sort
        by_qty = analytics.beneficiaries(self.conn, sort="total_quantity", per_page=1)
        self.assertEqual(by_qty["rows"][0]["external_reference"], "REAL001")
        with self.assertRaises(analytics.AnalyticsError):
            analytics.beneficiaries(self.conn, sort="evil; DROP TABLE")
        with self.assertRaises(analytics.AnalyticsError):
            analytics.beneficiaries(self.conn, page=0)
        with self.assertRaises(analytics.AnalyticsError):
            analytics.beneficiaries(self.conn, per_page=99999)

    def test_beneficiary_detail(self):
        detail = analytics.beneficiary_detail(self.conn, "REAL001")
        self.assertEqual(detail["beneficiary"]["district"], "Lucknow")
        self.assertEqual(len(detail["transactions"]), 2)
        self.assertEqual(detail["transactions"][0]["ration_type"], "rice")
        with self.assertRaises(analytics.AnalyticsError):
            analytics.beneficiary_detail(self.conn, "NOPE")

    # ---- fps ----
    def test_fps_analytics(self):
        fps = analytics.fps(self.conn)
        self.assertEqual(fps["total"], 3)
        self.assertEqual(fps["active"], 3)
        by_code = {c["fps_code"]: c for c in fps["centers"]}
        self.assertEqual(by_code["FPS10"]["transaction_count"], 2)
        self.assertEqual(by_code["FPS10"]["quantity_distributed"], 150.0)
        self.assertEqual(by_code["FPS10"]["inventory_count"], 2)
        self.assertEqual(by_code["FPS11"]["transaction_count"], 5)

    # ---- operational alerts ----
    def test_operational_alerts(self):
        alerts = analytics.operational_alerts(self.conn)
        cats = {a["category"] for a in alerts["alerts"]}
        self.assertIn("LOW_INVENTORY", cats)          # wheat below threshold
        self.assertIn("HIGH_FAILURE_RATE", cats)      # FPS11: 1 of 1 failed
        # deterministic ids and order (high first)
        severities = [a["severity"] for a in alerts["alerts"]]
        self.assertEqual(severities, sorted(severities, key=lambda s: {"high": 0, "medium": 1, "low": 2}[s]))
        low_inv = [a for a in alerts["alerts"] if a["category"] == "LOW_INVENTORY"][0]
        self.assertEqual(low_inv["entity_id"], "FPS10")
        self.assertEqual(low_inv["commodity"], "wheat")

    # ---- transactions feed ----
    def test_transactions_feed(self):
        t = analytics.transactions(self.conn, page=1, per_page=10)
        self.assertEqual(t["total"], 33)
        self.assertEqual(len(t["rows"]), 10)
        t2 = analytics.transactions(self.conn, page=4, per_page=10)
        self.assertEqual(len(t2["rows"]), 3)
        failed = analytics.transactions(self.conn, status="FAILED")
        self.assertEqual(failed["total"], 5)
        with self.assertRaises(analytics.AnalyticsError):
            analytics.transactions(self.conn, status="REFUNDED")

    def test_consistency_overview_vs_distribution(self):
        ov = analytics.overview(self.conn)
        d = analytics.distribution(self.conn)
        self.assertEqual(ov["ration_distributed_kg"], d["total_quantity"])
        self.assertEqual(ov["total_transactions"], d["by_status"] and sum(x["count"] for x in d["by_status"]))


class EmptyDatabaseTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "empty.db"
        self.addCleanup(self._tmp.cleanup)
        self.conn = db.open_db(self.db_path)

    def tearDown(self):
        self.conn.close()

    def test_empty_database_returns_zeros(self):
        ov = analytics.overview(self.conn)
        self.assertEqual(ov["total_beneficiaries"], 0)
        self.assertEqual(ov["total_transactions"], 0)
        self.assertEqual(ov["ration_distributed_kg"], 0.0)
        d = analytics.distribution(self.conn)
        self.assertEqual(d["total_quantity"], 0.0)
        self.assertEqual(d["trend"]["labels"], [])
        self.assertEqual(d["trend"]["series"], {})
        inv = analytics.inventory(self.conn)
        self.assertEqual(inv["total_stock_kg"], 0.0)
        self.assertEqual(inv["items"], [])
        b = analytics.beneficiaries(self.conn)
        self.assertEqual(b["total"], 0)
        self.assertEqual(b["rows"], [])
        fps = analytics.fps(self.conn)
        self.assertEqual(fps["total"], 0)
        alerts = analytics.operational_alerts(self.conn)
        self.assertEqual(alerts["count"], 0)


class AnalyticsAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls._tmp.name) / "api.db"
        conn = db.open_db(cls.db_path)
        _seed(conn)
        conn.close()
        cls.server = make_server("127.0.0.1", 0, db_path=cls.db_path)
        cls.port = cls.server.server_address[1]
        cls.base = "%s:%d" % (BASE, cls.port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _get(self, path):
        req = urllib.request.Request(self.base + path)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.status, response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    def test_overview_endpoint(self):
        status, raw = self._get("/api/analytics/overview")
        self.assertEqual(status, 200)
        import json
        data = json.loads(raw)
        self.assertEqual(data["total_transactions"], 33)
        self.assertEqual(data["ration_distributed_kg"], 403.0)

    def test_distribution_endpoint_with_granularity(self):
        import json
        status, raw = self._get("/api/analytics/distribution?granularity=month")
        self.assertEqual(status, 200)
        data = json.loads(raw)
        self.assertEqual(data["granularity"], "month")
        self.assertIn("series", data["trend"])

    def test_beneficiaries_endpoint_pagination(self):
        import json
        status, raw = self._get("/api/analytics/beneficiaries?page=2&per_page=5&sort=total_quantity")
        self.assertEqual(status, 200)
        data = json.loads(raw)
        self.assertEqual(data["page"], 2)
        self.assertEqual(len(data["rows"]), 3)

    def test_invalid_range_rejected_400(self):
        status, raw = self._get("/api/analytics/overview?range=nonsense")
        self.assertEqual(status, 400)
        self.assertIn("Invalid range", raw)

    def test_custom_range_validation(self):
        status, _ = self._get("/api/analytics/overview?range=custom&from=2026-08-01")
        self.assertEqual(status, 400)
        status, raw = self._get("/api/analytics/overview?range=custom&from=2026-08-09&to=2026-08-01")
        self.assertEqual(status, 400)

    def test_unknown_endpoint_400(self):
        status, _ = self._get("/api/analytics/bogus")
        self.assertEqual(status, 400)

    def test_alerts_endpoint(self):
        import json
        status, raw = self._get("/api/analytics/alerts")
        self.assertEqual(status, 200)
        data = json.loads(raw)
        cats = {a["category"] for a in data["alerts"]}
        self.assertIn("LOW_INVENTORY", cats)

    def test_missing_beneficiary_400(self):
        status, _ = self._get("/api/analytics/beneficiaries/NOBODY")
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
