"""RationRight — Phase 12: Executive Command Center & Intelligence Reports tests.

Covers ``command_center.py`` + the reports database layer + the new server
routes: KPI accuracy and previous-period comparison, risk overview matching
persisted Phase 11 alerts, district/FPS risk ranking, trend aggregation
consistency (chart totals agree with KPI totals), executive summary with the
deterministic fallback and LLM injection, alert/insight integration, global
filters, report generation/persistence/history/detail with full lineage, the
no-fabricated-values guarantee on an empty database, and the API surface
through the real server on an isolated temp database.

Run from the project root::

    python3 -m unittest discover -s tests -t . -v
"""

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import command_center
import database as db
from server import make_server

BASE = "http://127.0.0.1"

_SEED_COUNTER = [0]


def _now_iso_ago(days=0):
    return (datetime.now(timezone.utc) - timedelta(days=days)
            ).isoformat(timespec="seconds")


def _seed(conn, *, with_alerts=True, quality=100.0):
    """A deterministic fixture with transactions, inventory and alerts.

    Two FPS centers: UP-A1 (rice, healthy coverage) and UP-B1 (rice,
    low coverage -> warning), one district, one inventory record and one
    persisted alert, so every command-center section has real data.
    """
    _SEED_COUNTER[0] += 1
    seed_n = _SEED_COUNTER[0]

    src = db.insert_data_source(
        conn, name="cc_source_%d" % seed_n, source_type="CSV",
        description="command center fixture", status="ACTIVE")
    imp = db.insert_data_import(
        conn, data_source_id=src, dataset_name="cc_fixture_%d" % seed_n,
        file_name="fixture.csv", file_type="CSV",
        record_count=12, successful_records=12, failed_records=0,
        duplicate_records=0, status="COMPLETED")

    db.upsert_beneficiaries(conn, [{"external_reference": "R1", "name": "A",
                                    "state": "UP", "district": "Lucknow"}])
    ben = db.beneficiary_ids(conn, ["R1"])
    db.upsert_fps_centers(conn, [
        {"fps_code": "UP-A1", "name": "Center A", "state": "UP",
         "district": "Lucknow"},
        {"fps_code": "UP-B1", "name": "Center B", "state": "UP",
         "district": "Lucknow"},
    ])
    fps_ids = db.fps_center_ids(conn, ["UP-A1", "UP-B1"])
    db.insert_inventory_batch(conn, [
        {"fps_center_id": fps_ids["UP-A1"], "commodity": "rice",
         "current_stock": 2000, "reorder_threshold": 500},
        {"fps_center_id": fps_ids["UP-B1"], "commodity": "rice",
         "current_stock": 200, "reorder_threshold": 500},
    ])
    # 4 rice transactions at UP-A1 (45 days ago -> previous window) and 10
    # rice transactions at UP-B1 (yesterday -> current window): the KPI
    # comparison must be current 1000 vs previous 400 (+150%).
    tx = []
    for i in range(4):
        tx.append({
            "external_transaction_id": "CC%02d-A-%d" % (seed_n, i),
            "beneficiary_id": ben["R1"], "fps_center_id": fps_ids["UP-A1"],
            "commodity": "rice", "quantity": 100,
            "transaction_date": _now_iso_ago(45),
            "unit": "kg", "latitude": 26.8, "longitude": 80.9,
            "status": "COMPLETED", "source_import_id": imp,
        })
    for i in range(10):
        tx.append({
            "external_transaction_id": "CC%02d-B-%d" % (seed_n, i),
            "beneficiary_id": ben["R1"], "fps_center_id": fps_ids["UP-B1"],
            "commodity": "rice", "quantity": 100,
            "transaction_date": _now_iso_ago(1),
            "unit": "kg", "latitude": 26.8, "longitude": 80.9,
            "status": "COMPLETED", "source_import_id": imp,
        })
    db.insert_transactions_batch(conn, tx)

    if with_alerts:
        db.insert_alert(
            conn, alert_id="ALT-TEST-%04d" % seed_n, rule_type="INVENTORY_RISK",
            condition="coverage_low", severity="HIGH",
            title="Inventory coverage below threshold",
            status="OPEN", entity_type="fps_center", entity_id="UP-B1",
            commodity="rice", current_value=2.0, threshold=30.0,
            evidence="{}", created_at=_now_iso_ago(0))
    return {"src": src, "imp": imp, "seed_n": seed_n}


def _fresh_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.unlink(tmp.name)
    return tmp.name


class CommandCenterCoreTests(unittest.TestCase):
    def setUp(self):
        self.db_path = _fresh_db()
        self.conn = db.open_db(self.db_path)
        self.s = _seed(self.conn)
        self.conn.commit()
        self.conn.close()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_kpi_accuracy(self):
        cc = command_center.command_center(db_path=self.db_path)
        kpis = {k["key"]: k for k in cc["kpis"]}
        # current window = last 30 days -> 10 transactions (1000 kg rice)
        self.assertEqual(kpis["distribution"]["value"], 1000.0)
        self.assertEqual(kpis["transactions"]["value"], 10)
        self.assertEqual(kpis["inventory"]["value"], 2200.0)
        # active alerts KPI matches persisted alerts
        self.assertEqual(kpis["active_alerts"]["value"], 1)
        self.assertEqual(kpis["critical_alerts"]["value"], 0)
        self.assertEqual(kpis["high_risk_fps"]["value"], 1)  # UP-B1 below reorder

    def test_kpi_previous_period_comparison(self):
        cc = command_center.command_center(db_path=self.db_path)
        kpis = {k["key"]: k for k in cc["kpis"]}
        cmp = kpis["distribution"]["comparison"]
        self.assertTrue(cmp["available"])
        # current 1000 vs previous 400 (4 x 100 on day 45) -> +150%
        self.assertEqual(cmp["current"], 1000.0)
        self.assertEqual(cmp["previous"], 400.0)
        self.assertEqual(cmp["change_pct"], 150.0)

    def test_risk_overview_matches_alerts(self):
        cc = command_center.command_center(db_path=self.db_path)
        self.assertEqual(cc["risk_overview"]["total"], 1)
        self.assertEqual(cc["risk_overview"]["high"], 1)
        self.assertEqual(len(cc["active_alerts"]), 1)
        self.assertEqual(cc["active_alerts"][0]["severity"], "HIGH")

    def test_district_and_fps_ranking(self):
        cc = command_center.command_center(db_path=self.db_path)
        self.assertTrue(cc["district_risk"])
        d = cc["district_risk"][0]
        self.assertEqual(d["district"], "Lucknow")
        self.assertEqual(d["distribution_kg"], 1000.0)
        self.assertEqual(d["alerts"], 1)
        # one HIGH alert on a district -> documented MEDIUM district risk
        self.assertEqual(d["risk"], "MEDIUM")
        fps = {f["fps_code"]: f for f in cc["fps_risk"]}
        # UP-B1 is below its reorder threshold -> HIGH, listed first (sorted)
        self.assertEqual(cc["fps_risk"][0]["fps_code"], "UP-B1")
        self.assertEqual(fps["UP-B1"]["risk"], "HIGH")

    def test_trend_totals_consistent_with_kpis(self):
        cc = command_center.command_center(db_path=self.db_path)
        t = cc["trends"]
        series_total = sum(s["quantity"] for s in t["distribution"])
        by_comm_total = sum(c["quantity"] for c in t["by_commodity"])
        kpi_total = {k["key"]: k for k in cc["kpis"]}["distribution"]["value"]
        # KPI totals and chart totals must agree (Phase 5 consistency rule)
        self.assertEqual(series_total, 1000.0)
        self.assertEqual(by_comm_total, 1000.0)
        self.assertEqual(series_total, kpi_total)
        self.assertEqual(t["by_commodity"][0]["commodity"], "rice")

    def test_executive_summary_fallback_is_evidence_based(self):
        cc = command_center.command_center(db_path=self.db_path)
        es = cc["executive_summary"]
        self.assertEqual(es["generated_by"], "deterministic_fallback")
        self.assertIn("1000", es["summary"])       # real KPI number
        self.assertIn("1", es["summary"])          # real alert count
        # the fallback is honest: it explicitly disclaims prediction
        self.assertIn("not a prediction", es["summary"])

    def test_executive_summary_llm_injection(self):
        def gen(kind, context, fallback):
            return "A generated summary mentioning " + str(
                context.get("active_alerts")) + " alert(s)."
        cc = command_center.command_center(
            db_path=self.db_path, generator=gen)
        es = cc["executive_summary"]
        self.assertEqual(es["generated_by"], "llm")
        self.assertIn("1 alert", es["summary"])

    def test_executive_summary_survives_llm_failure(self):
        def boom(kind, context, fallback):
            raise RuntimeError("API down")
        cc = command_center.command_center(
            db_path=self.db_path, generator=boom)
        self.assertEqual(cc["executive_summary"]["generated_by"],
                         "deterministic_fallback")

    def test_filters_narrow_kpis_and_trends(self):
        full = command_center.command_center(db_path=self.db_path)
        # FPS filter -> only UP-B1's 10 transactions
        fps = command_center.command_center(
            db_path=self.db_path, fps="UP-B1")
        self.assertEqual({k["key"]: k for k in fps["kpis"]}["distribution"]["value"],
                         1000.0)
        self.assertEqual(fps["filters"]["fps"], "UP-B1")
        # Commodity filter with an empty commodity -> honest zeros, no fabrications
        empty = command_center.command_center(db_path=self.db_path, commodity="wheat")
        self.assertEqual({k["key"]: k for k in empty["kpis"]}["distribution"]["value"], 0)
        self.assertEqual(empty["trends"]["total_quantity"], 0)
        # The full-scope payload still carries the same totals
        self.assertEqual({k["key"]: k for k in full["kpis"]}["distribution"]["value"],
                         1000.0)

    def test_sources_and_lineage(self):
        cc = command_center.command_center(db_path=self.db_path)
        self.assertTrue(any(s["name"].startswith("cc_source_") for s in cc["sources"]))
        self.assertEqual(cc["lineage"]["import_count"], 1)
        self.assertEqual(cc["lineage"]["latest_imports"][0]["dataset_name"],
                         "cc_fixture_%d" % self.s["seed_n"])
        # honest disclaimer: imported dataset, no claim of live government data
        self.assertIn("Analysis based on imported dataset", cc["disclaimer"])

    def test_freshness_honest(self):
        cc = command_center.command_center(db_path=self.db_path)
        # No successful sync timestamp -> UNKNOWN, never assumed FRESH
        self.assertEqual(cc["freshness"]["status"], "UNKNOWN")

    def test_empty_database_no_fabricated_values(self):
        path = _fresh_db()
        try:
            conn = db.open_db(path)
            conn.commit()
            conn.close()
            cc = command_center.command_center(db_path=path)
            kpis = {k["key"]: k for k in cc["kpis"]}
            for key in ("distribution", "transactions", "inventory",
                        "active_alerts", "critical_alerts", "high_risk_fps"):
                self.assertEqual(kpis[key]["value"], 0)
            self.assertIsNone(kpis["coverage"]["value"])
            self.assertEqual(cc["risk_overview"]["total"], 0)
            self.assertEqual(cc["executive_summary"]["summary"],
                             "Insufficient data to provide a reliable "
                             "executive summary.")
            self.assertEqual(cc["freshness"]["status"], "UNKNOWN")
        finally:
            if os.path.exists(path):
                os.unlink(path)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.db_path = _fresh_db()
        self.conn = db.open_db(self.db_path)
        self.s = _seed(self.conn)
        self.conn.commit()
        self.conn.close()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_report_generation_persists(self):
        report = command_center.generate_report(
            db_path=self.db_path, period="Test window", source="Test source")
        self.assertTrue(report["report_id"].startswith("RPT-"))
        self.assertEqual(report["period"], "Test window")
        self.assertEqual(report["source"], "Test source")
        # report carries the same evidence-backed sections
        self.assertEqual(len(report["kpis"]), 8)
        self.assertEqual(report["risk_overview"]["total"], 1)
        self.assertEqual(report["executive_summary"]["generated_by"],
                         "deterministic_fallback")
        self.assertTrue(report["disclaimer"])
        self.assertTrue(report["lineage"]["import_count"] >= 1)

    def test_report_history_and_detail(self):
        r1 = command_center.generate_report(db_path=self.db_path, period="P1")
        r2 = command_center.generate_report(db_path=self.db_path, period="P2")
        history = command_center.report_history(db_path=self.db_path)
        ids = [h["report_id"] for h in history["reports"]]
        self.assertEqual(len(ids), 2)
        self.assertIn(r1["report_id"], ids)
        detail = command_center.report_detail(r1["report_id"], db_path=self.db_path)
        self.assertEqual(detail["report_id"], r1["report_id"])
        self.assertEqual(detail["period_label"], "P1")
        payload = detail["payload"]
        self.assertEqual(payload["kpis"][0]["key"], "distribution")
        self.assertEqual(payload["risk_overview"]["total"], 1)

    def test_reports_never_overwrite(self):
        r1 = command_center.generate_report(db_path=self.db_path, period="P1")
        r2 = command_center.generate_report(db_path=self.db_path, period="P1")
        self.assertNotEqual(r1["report_id"], r2["report_id"])
        history = command_center.report_history(db_path=self.db_path)["reports"]
        self.assertEqual(len(history), 2)

    def test_report_generator_injection(self):
        def gen(kind, context, fallback):
            return "Executive summary from the LLM."
        report = command_center.generate_report(
            db_path=self.db_path, period="P", generator=gen)
        self.assertEqual(report["executive_summary"]["generated_by"], "llm")


class CommandCenterApiTests(unittest.TestCase):
    """API tests on an isolated temp database (never pollutes the demo DB)."""

    def setUp(self):
        self.db_path = _fresh_db()
        conn = db.open_db(self.db_path)
        _seed(conn)
        conn.commit()
        conn.close()
        self.httpd = make_server(port=0, db_path=self.db_path)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def _get(self, path):
        with urllib.request.urlopen(
                "%s:%d%s" % (BASE, self.port, path), timeout=15) as resp:
            return json.loads(resp.read())

    def test_command_center_endpoint(self):
        cc = self._get("/api/command-center")
        self.assertIn("kpis", cc)
        self.assertEqual(cc["risk_overview"]["total"], 1)
        self.assertIn("executive_summary", cc)
        # filters accepted via query string
        filtered = self._get("/api/command-center?fps=UP-B1")
        self.assertEqual(filtered["filters"]["fps"], "UP-B1")
        self.assertEqual({k["key"]: k for k in filtered["kpis"]}["distribution"]["value"],
                         1000.0)

    def test_report_endpoints(self):
        req = urllib.request.Request(
            "%s:%d/api/reports" % (BASE, self.port),
            data=json.dumps({"period": "API window"}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=20) as resp:
            report = json.loads(resp.read())
        self.assertTrue(report["report_id"].startswith("RPT-"))
        history = self._get("/api/reports")
        self.assertEqual(len(history["reports"]), 1)
        detail = self._get("/api/reports/" + report["report_id"])
        self.assertEqual(detail["report_id"], report["report_id"])
        self.assertEqual(detail["period"], "API window")
        self.assertIn("kpis", detail)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._get("/api/reports/RPT-0000-9999")
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
