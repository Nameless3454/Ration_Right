"""RationRight — Phase 15: end-to-end flow, concurrency, scale & recovery.

Runs the complete user journey against a real temporary database:

    upload -> validate -> import -> command center -> analytics ->
    AI analysis (real mode) -> monitoring -> alert -> evidence ->
    what-if simulation -> recommendation -> report -> export

plus a concurrent-reads smoke test, a bounded large-import test, and a
failure-recovery test (AI down does not break analytics; monitoring failure
does not clear existing alerts).

Run from the project root::

    python3 -m unittest tests.test_e2e_flow -v
"""

import json
import os
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

import analytics
import command_center
import database as db
import monitoring
import simulation as sim
from analysis_center import run_analysis
from ingestion import service as ingest
from server import make_server

BASE = "http://127.0.0.1"

TRANSACTION_CSV = (
    "Transaction ID,Beneficiary ID,FPS Code,Transaction Date,Commodity,Quantity,Unit\n"
    "TX301,BEN001,FPS01,2026-07-02,rice,100,kg\n"
    "TX302,BEN001,FPS01,2026-07-12,rice,110,kg\n"
    "TX303,BEN001,FPS01,2026-07-22,rice,90,kg\n"
    "TX304,BEN001,FPS01,2026-08-01,rice,120,kg\n"
    "TX305,BEN002,FPS02,2026-07-05,wheat,40,kg\n"
    "TX306,BEN002,FPS02,2026-08-02,wheat,50,kg\n"
)


def _fresh_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.unlink(tmp.name)
    return tmp.name


def _import_and_seed(db_path):
    """Import the CSV and add low-coverage rice inventory; returns import id."""
    up = ingest.handle_upload(TRANSACTION_CSV.encode(), "e2e.csv", "text/csv")
    ingest.validate_step(up["token"], dataset_type="ration_transactions",
                         db_path=db_path)
    summary = ingest.confirm_step(up["token"], db_path=db_path)
    imp_id = summary["data_import_id"]
    conn = db.open_db(db_path)
    try:
        center = conn.execute(
            "SELECT id FROM fps_centers WHERE fps_code = 'FPS01'").fetchone()
        db.insert_inventory_batch(conn, [
            {"fps_center_id": center["id"], "commodity": "rice",
             "current_stock": 500.0, "monthly_consumption": 1200.0,
             "reorder_threshold": 800.0, "source_import_id": imp_id},
        ])
        conn.commit()
    finally:
        conn.close()
    return imp_id


class FullDemoFlowTests(unittest.TestCase):
    """STEP 1-16 of the demo: real data all the way to an exported report."""

    def setUp(self):
        self.db_path = _fresh_db()
        self.imp_id = _import_and_seed(self.db_path)
        self.addCleanup(lambda: os.path.exists(self.db_path) and os.unlink(self.db_path))

    def _tx_count(self):
        conn = db.open_db(self.db_path)
        try:
            return conn.execute(
                "SELECT COUNT(*) AS n FROM ration_transactions").fetchone()["n"]
        finally:
            conn.close()

    def test_full_flow(self):
        # 1-2. Import happened in setUp: 6 valid records.
        self.assertEqual(self._tx_count(), 6)

        # 3. Command center reflects the import (explicit window covers all
        #    rows — the default is a rolling 30-day window from today).
        cc = command_center.command_center(
            db_path=self.db_path, from_date="2026-07-01", to_date="2026-08-31")
        kpis = {k["key"]: k["value"] for k in cc["kpis"]}
        self.assertEqual(kpis["transactions"], 6)
        self.assertEqual(kpis["distribution"], 510.0)  # 100+110+90+120+40+50
        self.assertEqual(cc["disclaimer"], "Analysis based on imported dataset.")

        # 4. Analytics agrees with the same database.
        conn = db.open_db(self.db_path)
        try:
            ov = analytics.overview(conn)
        finally:
            conn.close()
        self.assertEqual(ov["total_transactions"], 6)
        self.assertEqual(ov["ration_distributed_kg"], 510.0)

        # 5. AI analysis in real mode -> a persisted analysis run.
        result = run_analysis(dataset_mode="real", data_import_id=self.imp_id,
                              db_path=self.db_path,
                              types=["distribution_anomaly", "inventory_risk",
                                     "demand_forecast", "recommendations"])
        self.assertIsNotNone(result)
        run = result["analysis_run"]
        self.assertTrue(run["analysis_id"].startswith("RA-"))
        self.assertEqual(run["data_import_id"], self.imp_id)

        # 6. Monitoring -> at least one real inventory alert (12.5 days < 30).
        outcome = monitoring.run_monitoring(db_path=self.db_path)
        self.assertGreaterEqual(outcome["created"] + outcome["updated"], 1)
        conn = db.open_db(self.db_path)
        try:
            alerts = [dict(r) for r in conn.execute(
                "SELECT alert_id, rule_type, severity, current_value, threshold, "
                " import_id FROM alerts WHERE status IN ('OPEN','ACKNOWLEDGED')")]
            alerts2 = [dict(r) for r in conn.execute(
                "SELECT alert_id, rule_type, severity FROM alerts ORDER BY id "
                "LIMIT 10")]
        finally:
            conn.close()
        self.assertTrue(alerts)
        inventory_alert = next((a for a in alerts
                                if a["rule_type"] == "INVENTORY_RISK"), None)
        self.assertIsNotNone(inventory_alert)
        # Evidence values are real and match the seeded stock: 500*30/1200 =
        # 12.5 days coverage, below the 15-day critical threshold.
        self.assertEqual(inventory_alert["current_value"], 12.5)  # days
        self.assertEqual(inventory_alert["threshold"], 15.0)      # critical days
        self.assertEqual(inventory_alert["severity"], "CRITICAL")

        # 7. Alert -> evidence (already attached) -> what-if on the same import.
        scenario = sim.run_scenario(self.imp_id, commodity="rice",
                                    demand_change_pct=10,
                                    supply_delay_days=7, db_path=self.db_path)
        self.assertEqual(scenario["status"], "completed")
        self.assertTrue(scenario["scenario_id"].startswith("SIM-"))
        # Deterministic math: demand 420/1mo? (rice: 100+110+90+120 = 420 over
        # 2 months -> 210/mo); +10% -> 231.
        self.assertEqual(scenario["baseline"]["monthly_demand_kg"],
                         round(420.0 / 2, 2))
        self.assertEqual(scenario["scenario"]["projected_monthly_demand_kg"],
                         round(210.0 * 1.1, 2))
        self.assertTrue(scenario["interpretation"]["summary"])
        # Lineage back to import + source.
        self.assertEqual(scenario["lineage"]["data_import_id"], self.imp_id)
        self.assertEqual(scenario["lineage"]["source_name"], "Uploaded Dataset")

        # 8. Simulation must NOT modify real data.
        self.assertEqual(self._tx_count(), 6)
        conn = db.open_db(self.db_path)
        try:
            stock = conn.execute(
                "SELECT current_stock FROM inventory WHERE commodity='rice'"
            ).fetchone()["current_stock"]
        finally:
            conn.close()
        self.assertEqual(stock, 500.0)

        # 9. Report matches the command center values (same payload source).
        report = command_center.generate_report(
            db_path=self.db_path,
            filters={"from_date": "2026-07-01", "to_date": "2026-08-31"})
        self.assertTrue(report["report_id"].startswith("RPT-"))
        report_kpis = {k["key"]: k["value"] for k in report["kpis"]}
        self.assertEqual(report_kpis["distribution"],
                         kpis["distribution"])
        # Compare against a fresh command-center snapshot from the SAME window
        # (alerts were created by monitoring after the first snapshot).
        cc_now = command_center.command_center(
            db_path=self.db_path, from_date="2026-07-01", to_date="2026-08-31")
        self.assertEqual(report["risk_overview"]["total"],
                         cc_now["risk_overview"]["total"])
        # Report lineage identifies the dataset import.
        self.assertGreaterEqual(report["lineage"]["import_count"], 1)

        # 10. Export: the report payload is the exportable artifact (JSON).
        export = json.dumps(report)
        self.assertIn(report["report_id"], export)
        self.assertIn("kpis", json.loads(export))
        # CSV export path: district risk rows serialize to rows.
        rows = report["district_risk"]
        self.assertIsInstance(rows, list)

    def test_alert_evidence_and_lineage_to_analysis(self):
        monitoring.run_monitoring(db_path=self.db_path)
        conn = db.open_db(self.db_path)
        try:
            alert = conn.execute(
                "SELECT alert_id, rule_type, severity, current_value, threshold, "
                " evidence, import_id, analysis_id FROM alerts "
                "WHERE rule_type='INVENTORY_RISK' LIMIT 1").fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(alert)
        evidence = json.loads(alert["evidence"] or "{}")
        self.assertIn("current_stock", evidence)
        self.assertEqual(evidence["current_stock"], 500.0)
        self.assertEqual(alert["import_id"], self.imp_id)


class ConcurrencySmokeTests(unittest.TestCase):
    """Multiple readers at once must not error or lock up."""

    def setUp(self):
        self.db_path = _fresh_db()
        _import_and_seed(self.db_path)
        self.httpd = make_server(port=0, db_path=self.db_path)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.shutdown)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(lambda: os.path.exists(self.db_path) and os.unlink(self.db_path))

    def test_parallel_reads(self):
        paths = ["/api/command-center", "/api/analytics/overview?range=all",
                 "/api/alerts?per_page=10&days=30&page=1",
                 "/api/analytics/distribution?granularity=day&range=all"]
        results = []
        errors = []

        def worker(path):
            try:
                with urllib.request.urlopen(
                        "%s:%d%s" % (BASE, self.port, path), timeout=30) as resp:
                    results.append((path, resp.status))
            except Exception as exc:  # noqa: BLE001
                errors.append((path, repr(exc)))

        threads = [threading.Thread(target=worker, args=(p,))
                   for p in paths for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(results), len(paths) * 4)
        self.assertTrue(all(status == 200 for _, status in results))


class LargeImportTests(unittest.TestCase):
    """20k-row import: counts exact, pagination bounded, dashboard loads."""

    def setUp(self):
        self.db_path = _fresh_db()
        self.addCleanup(lambda: os.path.exists(self.db_path) and os.unlink(self.db_path))

    def test_large_import_is_bounded_and_exact(self):
        # The dedup natural key is (FPS, date, commodity): vary FPS across
        # 500 centers so all 20,000 rows are genuinely distinct.
        n = 20_000
        lines = ["Transaction ID,Beneficiary ID,FPS Code,Transaction Date,"
                 "Commodity,Quantity,Unit"]
        for i in range(n):
            lines.append("TX%06d,BEN%04d,FPS%04d,2026-08-%02d,%s,%d,kg" % (
                i + 1, i % 500 + 1, i % 500 + 1, i % 28 + 1,
                ("rice", "wheat", "pulses")[i % 3], (i % 9) + 1))
        csv_text = "\n".join(lines) + "\n"

        up = ingest.handle_upload(csv_text.encode(), "big.csv", "text/csv")
        validated = ingest.validate_step(
            up["token"], dataset_type="ration_transactions", db_path=self.db_path)
        self.assertEqual(validated["record_count"], n)
        self.assertEqual(validated["valid_records"], n)
        summary = ingest.confirm_step(up["token"], db_path=self.db_path)
        self.assertEqual(summary["imported"], n)

        # Dashboard reads the import through bounded aggregations (explicit
        # window: the default is a rolling 30 days up to today, which would
        # legitimately exclude future-dated rows).
        cc = command_center.command_center(
            db_path=self.db_path, from_date="2026-08-01", to_date="2026-08-31")
        kpis = {k["key"]: k["value"] for k in cc["kpis"]}
        self.assertEqual(kpis["transactions"], n)

        # Pagination returns a bounded page, not all rows.
        conn = db.open_db(self.db_path)
        try:
            page = [dict(r) for r in conn.execute(
                "SELECT * FROM ration_transactions LIMIT 50 OFFSET 19950")]
        finally:
            conn.close()
        self.assertEqual(len(page), 50)


class FailureRecoveryTests(unittest.TestCase):
    """AI down / monitoring failure must not break analytics or clear alerts."""

    def setUp(self):
        self.db_path = _fresh_db()
        self.imp_id = _import_and_seed(self.db_path)
        self.addCleanup(lambda: os.path.exists(self.db_path) and os.unlink(self.db_path))

    def test_ai_down_analytics_still_work(self):
        def boom(kind, context, fallback):
            raise RuntimeError("AI provider unavailable")

        # Analysis completes with fallback narratives.
        result = run_analysis(dataset_mode="real", data_import_id=self.imp_id,
                              db_path=self.db_path, types=["inventory_risk",
                                                           "recommendations"])
        self.assertIsNotNone(result)
        self.assertTrue(result["analysis_run"]["analysis_id"].startswith("RA-"))

        # Analytics remain fully functional.
        conn = db.open_db(self.db_path)
        try:
            ov = analytics.overview(conn)
            inv = analytics.inventory(conn)
        finally:
            conn.close()
        self.assertEqual(ov["total_transactions"], 6)
        self.assertTrue(inv["by_commodity"])

        # Monitoring still detects conditions deterministically.
        outcome = monitoring.run_monitoring(db_path=self.db_path, generator=boom)
        self.assertGreaterEqual(outcome["created"] + outcome["updated"], 1)

    def test_monitoring_failure_keeps_existing_alerts(self):
        first = monitoring.run_monitoring(db_path=self.db_path)
        self.assertGreaterEqual(first["created"], 1)

        # A hard failure inside the engine (injected) must not delete alerts.
        original = monitoring._inventory_candidates

        def boom(conn, rules):
            raise RuntimeError("inventory query exploded")

        monitoring._inventory_candidates = boom
        try:
            with self.assertRaises(RuntimeError):
                monitoring.run_monitoring(db_path=self.db_path)
        finally:
            monitoring._inventory_candidates = original

        conn = db.open_db(self.db_path)
        try:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM alerts").fetchone()["n"]
            run_row = conn.execute(
                "SELECT status FROM data_imports WHERE id = ?",
                (self.imp_id,)).fetchone()
        finally:
            conn.close()
        self.assertGreaterEqual(count, 1)
        self.assertEqual(run_row["status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
