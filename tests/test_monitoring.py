"""RationRight — Phase 11: Early Warning, Alerts & Monitoring Center tests.

Covers ``monitoring.py`` + the alerts database layer: rule seeding, every
deterministic detector (inventory risk, operational risk, demand spike/drop,
data freshness, source failure, data quality, analysis-insight conversion),
deduplication, auto-resolution, the alert lifecycle (acknowledge / resolve /
dismiss with reason), dismissed-condition persistence, filters/search/
pagination, trend, the no-source-data-mutation guarantee, and the AI
explanation with its deterministic fallback. API surface is exercised
through the real server (like test_api.py).

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

import database as db
import monitoring
from server import make_server

BASE = "http://127.0.0.1"

_SEED_COUNTER = [0]


def _now_iso_ago(days=0, hours=0):
    return (datetime.now(timezone.utc) - timedelta(days=days, hours=hours)
            ).isoformat(timespec="seconds")


def _seed(conn, *, stale_source=False, failed_source=False, low_quality=True,
          low_inventory=True, with_transactions=True):
    """Deterministic fixture exercising every detector."""
    _SEED_COUNTER[0] += 1
    seed_n = _SEED_COUNTER[0]

    # Sources
    upload = db.get_data_source_by_name(conn, "Uploaded Dataset")
    src_id = db.insert_data_source(
        conn, name="Uploaded Dataset", source_type="MANUAL", description="t",
        status="ACTIVE",
    ) if upload is None else upload["id"]
    if stale_source:
        db.insert_data_source(
            conn, name="external_pds_%d" % seed_n, source_type="API",
            description="external source", status="ACTIVE",
            last_sync_at=_now_iso_ago(hours=50),
        )
        conn.execute(
            "UPDATE data_sources SET last_successful_sync_at = :ts "
            "WHERE name = :name",
            {"ts": _now_iso_ago(hours=50), "name": "external_pds_%d" % seed_n})
    if failed_source:
        db.insert_data_source(
            conn, name="broken_source_%d" % seed_n, source_type="API",
            description="broken", status="ERROR", last_sync_at=_now_iso_ago(hours=1),
        )
        conn.execute(
            "UPDATE data_sources SET last_error = 'Connection refused' "
            "WHERE name = :name", {"name": "broken_source_%d" % seed_n})

    # Import — optionally low quality (DATA_QUALITY detector).
    imp_id = db.insert_data_import(
        conn, data_source_id=src_id, dataset_name="pds_fixture_%d" % seed_n,
        file_name="fixture.csv", file_type="CSV",
        record_count=10, successful_records=(8 if low_quality else 10),
        failed_records=(2 if low_quality else 0), duplicate_records=0,
        status="PARTIAL" if low_quality else "COMPLETED")

    db.upsert_beneficiaries(conn, [{"external_reference": "RB1",
                                    "district": "Lucknow",
                                    "ration_category": "AAY",
                                    "family_size": 4, "status": "ACTIVE"}])
    ben = db.beneficiary_ids(conn, ["RB1"])
    db.upsert_fps_centers(conn, [
        {"fps_code": "FPS1", "name": "One", "district": "Lucknow",
         "state": "UP", "status": "ACTIVE"},
        {"fps_code": "FPS2", "name": "Two", "district": "Kanpur",
         "state": "UP", "status": "ACTIVE"},
    ])
    fps = db.fps_center_ids(conn, ["FPS1", "FPS2"])

    # Inventory: FPS1 critical coverage + below reorder; FPS2 healthy.
    db.insert_inventory_batch(conn, [
        {"fps_center_id": fps["FPS1"], "commodity": "rice",
         "current_stock": 100.0, "monthly_consumption": 1200.0,
         "reorder_threshold": 500.0, "source_import_id": imp_id},
        {"fps_center_id": fps["FPS2"], "commodity": "rice",
         "current_stock": 2000.0, "monthly_consumption": 1200.0,
         "reorder_threshold": 500.0, "source_import_id": imp_id},
    ]) if low_inventory else None

    if with_transactions:
        # Monthly rice demand per FPS1: May 120, Jun 140, Jul 160, Aug 60
        # (>= 3 tx in Aug) -> DEMAND_DROP, and 3 of 6+ FPS1 tx FAILED
        # (>= 5 tx, >= 10%) -> high failure rate. FPS2 stays silent -> no
        # recent distribution.
        rows = []
        seq = 0
        months = [("2026-05", 2, 60.0), ("2026-06", 2, 70.0),
                  ("2026-07", 2, 80.0), ("2026-08", 3, 20.0)]
        for month, count, qty in months:
            for i in range(count):
                seq += 1
                failed = month in ("2026-05",) and i == 0
                rows.append({
                    "external_transaction_id": "MTX%03d-%04d" % (seed_n, seq),
                    "beneficiary_id": ben["RB1"], "fps_center_id": fps["FPS1"],
                    "transaction_date": "%s-%02d" % (month, i + 1),
                    "commodity": "rice", "quantity": qty, "unit": "kg",
                    "latitude": 26.8, "longitude": 80.9,
                    "status": "FAILED" if failed else "COMPLETED",
                    "source_import_id": imp_id,
                })
        db.insert_transactions_batch(conn, rows)

    # A persisted Phase 9 anomaly insight -> DISTRIBUTION_ANOMALY alert,
    # with its analysis run so the alert lineage resolves end to end.
    db.insert_analysis_run(conn, analysis_id="RA-2026-9001",
                           data_import_id=imp_id, dataset_mode="real",
                           status="COMPLETED", insight_count=1)
    db.insert_ai_insight(
        conn, insight_type="DISTRIBUTION_ANOMALY", severity="HIGH",
        title="Unusual distribution pattern",
        description="Verified against transaction data; requires human review.",
        entity_type="beneficiary", entity_id="RB1",
        evidence={"time_difference_minutes": 12, "distance_km": 5.2},
        confidence=0.9, analysis_id="RA-2026-9001",
        source_import_id=imp_id)
    conn.commit()
    return imp_id


class DetectorTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "mon.db"
        self.addCleanup(self._tmp.cleanup)
        for name in ("RATIONRIGHT_LLM_ENABLED", "OPENAI_API_KEY"):
            os.environ.pop(name, None)
        self.conn = db.open_db(self.db_path)
        self.imp_id = _seed(self.conn, stale_source=True, failed_source=True)
        self.conn.close()

    def _conditions(self):
        conn = db.open_db(self.db_path)
        try:
            rules = monitoring._rule_map(conn)
            return {
                "inventory": monitoring._inventory_candidates(conn, rules),
                "operational": monitoring._operational_candidates(conn, rules),
                "demand": monitoring._demand_candidates(conn, rules),
                "freshness": monitoring._freshness_candidates(conn, rules),
                "source": monitoring._source_failure_candidates(conn, rules),
                "quality": monitoring._quality_candidates(conn, rules),
                "insight": monitoring._insight_candidates(conn, rules),
            }
        finally:
            conn.close()

    def test_rules_seeded_idempotently(self):
        monitoring.run_monitoring(db_path=self.db_path)
        n1 = len(monitoring.alert_rules_view(db_path=self.db_path)["rules"])
        monitoring.run_monitoring(db_path=self.db_path)
        n2 = len(monitoring.alert_rules_view(db_path=self.db_path)["rules"])
        self.assertEqual(n1, n2)
        self.assertGreaterEqual(n1, 11)

    def test_inventory_detectors(self):
        inv = self._conditions()["inventory"]
        by_cond = {}
        for c in inv:
            by_cond.setdefault(c["condition"], []).append(c)
        self.assertEqual(len(by_cond.get("coverage_critical", [])), 1)
        crit = by_cond["coverage_critical"][0]
        self.assertEqual(crit["entity_id"], "FPS1")
        self.assertEqual(crit["severity"], "CRITICAL")
        self.assertEqual(by_cond.get("below_reorder", [])[0]["entity_id"], "FPS1")
        # FPS2 healthy -> no coverage_warning/critical for it
        self.assertFalse([c for c in by_cond.get("coverage_warning", [])
                          if c["entity_id"] == "FPS2"])

    def test_operational_detectors(self):
        op = self._conditions()["operational"]
        by_cond = {}
        for c in op:
            by_cond.setdefault(c["condition"], []).append(c)
        failure = [c for c in by_cond.get("high_failure_rate", [])
                   if c["entity_id"] == "FPS1"]
        self.assertEqual(len(failure), 1)
        self.assertGreaterEqual(failure[0]["current_value"], 10.0)
        # FPS2 has NO transaction history at all (registry-style record): the
        # rule only fires for a center that distributed before but went
        # silent — otherwise a real 50k+ FPS registry would flood the alert
        # center with LOW alerts and stall monitoring (Phase 11 evidence).
        quiet = [c for c in by_cond.get("no_recent_distribution", [])
                 if c["entity_id"] == "FPS2"]
        self.assertEqual(len(quiet), 0)

    def test_no_recent_distribution_requires_history(self):
        """no_recent_distribution fires only when a center HAS completed
        transactions historically but none in the window; a registry FPS with
        zero transactions ever is never flagged."""
        conn = db.open_db(self.db_path)
        ben = db.beneficiary_ids(conn, ["RB1"])
        fps = db.fps_center_ids(conn, ["FPS1", "FPS2"])
        # FPS3: a registry-only center (like a real OGD FPS list) — no tx.
        db.upsert_fps_centers(conn, [{"fps_code": "FPS3", "name": "Three",
                                      "district": "Pune", "state": "MH",
                                      "status": "ACTIVE"}])
        f3 = db.fps_center_ids(conn, ["FPS3"])["FPS3"]
        # FPS2 gets OLD completed transactions (before the 30-day window).
        db.insert_transactions_batch(conn, [
            {"external_transaction_id": "OLD1", "beneficiary_id": ben["RB1"],
             "fps_center_id": fps["FPS2"], "transaction_date": "2026-03-05",
             "commodity": "rice", "quantity": 5.0, "unit": "kg",
             "latitude": 26.5, "longitude": 80.5,
             "status": "COMPLETED", "source_import_id": self.imp_id},
            {"external_transaction_id": "OLD2", "beneficiary_id": ben["RB1"],
             "fps_center_id": fps["FPS2"], "transaction_date": "2026-03-06",
             "commodity": "rice", "quantity": 6.0, "unit": "kg",
             "latitude": 26.5, "longitude": 80.5,
             "status": "COMPLETED", "source_import_id": self.imp_id},
        ])
        conn.commit()
        conn.close()
        conn = db.open_db(self.db_path)
        try:
            rules = monitoring._rule_map(conn)
            op = monitoring._operational_candidates(conn, rules)
        finally:
            conn.close()
        by_entity = {c["entity_id"]: c for c in op
                     if c["condition"] == "no_recent_distribution"}
        # FPS2: has history, silent in the window -> flagged.
        self.assertIn("FPS2", by_entity)
        # FPS3: no history at all -> never flagged.
        self.assertNotIn("FPS3", by_entity)

    def test_demand_drop_detector(self):
        demand = self._conditions()["demand"]
        drops = [c for c in demand if c["condition"] == "demand_drop"
                 and c["commodity"] == "rice"]
        self.assertEqual(len(drops), 1)
        self.assertLessEqual(drops[0]["current_value"], -20.0)
        self.assertEqual(drops[0]["severity"], "HIGH")  # deviation <= -2x
        self.assertFalse([c for c in demand if c["condition"] == "demand_spike"])

    def test_freshness_source_quality_detectors(self):
        conds = self._conditions()
        self.assertEqual(len(conds["freshness"]), 1)
        self.assertEqual(conds["freshness"][0]["condition"], "stale")
        self.assertGreater(conds["freshness"][0]["current_value"], 24.0)
        self.assertEqual(len(conds["source"]), 1)
        self.assertEqual(conds["source"][0]["condition"], "sync_failed")
        self.assertEqual(conds["source"][0]["severity"], "CRITICAL")
        quality = [c for c in conds["quality"] if c["condition"] == "low_quality"]
        self.assertEqual(len(quality), 1)
        self.assertEqual(quality[0]["current_value"], 80.0)
        self.assertEqual(quality[0]["import_id"], self.imp_id)

    def test_insight_conversion_detector(self):
        insights = self._conditions()["insight"]
        self.assertEqual(len(insights), 1)
        self.assertEqual(insights[0]["analysis_id"], "RA-2026-9001")
        self.assertEqual(insights[0]["entity_id"], "RB1")


class MonitoringEngineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "mon2.db"
        self.addCleanup(self._tmp.cleanup)
        for name in ("RATIONRIGHT_LLM_ENABLED", "OPENAI_API_KEY"):
            os.environ.pop(name, None)
        self.conn = db.open_db(self.db_path)
        self.imp_id = _seed(self.conn, stale_source=True, failed_source=True)
        self.conn.close()

    def _alerts(self, **filters):
        return monitoring.list_alerts_view(db_path=self.db_path, per_page=100,
                                           **filters)

    def test_run_creates_deduped_alerts(self):
        r1 = monitoring.run_monitoring(db_path=self.db_path)
        self.assertGreaterEqual(r1["created"], 6)  # inv x2 + failure + quiet +
        # drop + freshness + source + quality + insight
        self.assertEqual(r1["resolved"], 0)
        total1 = self._alerts()["total"]
        # second run: nothing new, everything refreshed
        r2 = monitoring.run_monitoring(db_path=self.db_path)
        self.assertEqual(r2["created"], 0)
        self.assertEqual(r2["updated"], total1)
        self.assertEqual(self._alerts()["total"], total1)

    def test_ai_explanation_deterministic_fallback(self):
        # No LLM configured -> every alert carries a deterministic explanation.
        monitoring.run_monitoring(db_path=self.db_path)
        alerts = self._alerts()["alerts"]
        self.assertTrue(all(a["ai_explanation"] and
                            a["ai_explanation"]["generated_by"] == "deterministic_fallback"
                            for a in alerts))
        self.assertTrue(all(a["ai_explanation"]["summary"] for a in alerts))

    def test_ai_explanation_injected_generator_and_failure(self):
        calls = []
        def fake_gen(kind, context, fallback):
            calls.append(kind)
            return "AI explanation for %s." % context["alert_type"]
        monitoring.run_monitoring(db_path=self.db_path, generator=fake_gen)
        self.assertIn("alert_explanation", calls)
        alerts = self._alerts()["alerts"]
        self.assertTrue(all(a["ai_explanation"]["generated_by"] == "llm"
                            for a in alerts))
        # a throwing generator must not break monitoring
        r = monitoring.run_monitoring(
            db_path=self.db_path,
            generator=lambda *a: (_ for _ in ()).throw(RuntimeError("x")))
        self.assertIn("created", r)

    def test_auto_resolution_when_condition_clears(self):
        monitoring.run_monitoring(db_path=self.db_path)
        conn = db.open_db(self.db_path)
        try:
            # fix the inventory: FPS1 gets plenty of stock
            conn.execute(
                "UPDATE inventory SET current_stock = 9000, "
                "reorder_threshold = 500 WHERE commodity = 'rice' "
                "AND fps_center_id = (SELECT id FROM fps_centers WHERE fps_code='FPS1')")
            # fix the source failure + freshness
            conn.execute(
                "UPDATE data_sources SET status = 'ACTIVE', last_error = NULL, "
                "last_successful_sync_at = :now",
                {"now": datetime.now(timezone.utc).isoformat(timespec="seconds")})
            conn.commit()
        finally:
            conn.close()
        r = monitoring.run_monitoring(db_path=self.db_path)
        self.assertGreaterEqual(r["resolved"], 3)  # critical + below_reorder + sync
        resolved = [a for a in self._alerts(status="RESOLVED")["alerts"]]
        self.assertTrue(all(a["resolved_at"] for a in resolved))

    def test_lifecycle_acknowledge_resolve_dismiss(self):
        monitoring.run_monitoring(db_path=self.db_path)
        alert = self._alerts(status="OPEN")["alerts"][0]
        aid = alert["alert_id"]
        self.assertTrue(monitoring.set_alert_status_view(
            aid, "ACKNOWLEDGED", db_path=self.db_path))
        detail = monitoring.alert_detail_view(aid, db_path=self.db_path)
        self.assertEqual(detail["status"], "ACKNOWLEDGED")
        self.assertTrue(detail["acknowledged_at"])
        self.assertTrue(monitoring.set_alert_status_view(
            aid, "RESOLVED", db_path=self.db_path))
        detail = monitoring.alert_detail_view(aid, db_path=self.db_path)
        self.assertEqual(detail["status"], "RESOLVED")
        self.assertTrue(detail["resolved_at"])
        # dismiss with reason preserves the row
        alert2 = self._alerts(status="OPEN")["alerts"][0]
        self.assertTrue(monitoring.set_alert_status_view(
            alert2["alert_id"], "DISMISSED", dismissed_reason="False positive",
            db_path=self.db_path))
        detail = monitoring.alert_detail_view(alert2["alert_id"], db_path=self.db_path)
        self.assertEqual(detail["status"], "DISMISSED")
        self.assertEqual(detail["dismissed_reason"], "False positive")
        self.assertEqual(self._alerts()["total"], 8)  # nothing deleted

    def test_dismissed_condition_is_not_recreated_while_persistent(self):
        monitoring.run_monitoring(db_path=self.db_path)
        total = self._alerts()["total"]
        open_alert = self._alerts(status="OPEN")["alerts"][0]
        monitoring.set_alert_status_view(open_alert["alert_id"], "DISMISSED",
                                         db_path=self.db_path)
        # same condition persists -> monitoring must NOT recreate it
        r = monitoring.run_monitoring(db_path=self.db_path)
        self.assertEqual(r["created"], 0)
        self.assertEqual(self._alerts()["total"], total)
        self.assertIsNone(monitoring.alert_detail_view(
            open_alert["alert_id"], db_path=self.db_path).get("resolved_at"))

    def test_resolved_condition_recurs_creates_new_alert(self):
        monitoring.run_monitoring(db_path=self.db_path)
        open_alert = self._alerts(status="OPEN")["alerts"][0]
        monitoring.set_alert_status_view(open_alert["alert_id"], "RESOLVED",
                                         db_path=self.db_path)
        r = monitoring.run_monitoring(db_path=self.db_path)
        self.assertEqual(r["created"], 1)  # the resolved condition is active again
        self.assertEqual(self._alerts(status="OPEN")["total"], 8)
        self.assertEqual(self._alerts(status="RESOLVED")["total"], 1)

    def test_no_source_data_mutation(self):
        conn = db.open_db(self.db_path)
        try:
            before = {
                "tx": conn.execute("SELECT COUNT(*), SUM(quantity) FROM "
                                   "ration_transactions").fetchone(),
                "inv": conn.execute("SELECT COUNT(*), SUM(current_stock) FROM "
                                    "inventory").fetchone(),
                "ben": conn.execute("SELECT COUNT(*) FROM beneficiaries").fetchone(),
                "imp": conn.execute("SELECT COUNT(*), SUM(successful_records) FROM "
                                    "data_imports").fetchone(),
                "src": conn.execute("SELECT COUNT(*) FROM data_sources").fetchone(),
            }
        finally:
            conn.close()
        monitoring.run_monitoring(db_path=self.db_path)
        monitoring.run_monitoring(db_path=self.db_path)
        conn = db.open_db(self.db_path)
        try:
            after = {
                "tx": conn.execute("SELECT COUNT(*), SUM(quantity) FROM "
                                   "ration_transactions").fetchone(),
                "inv": conn.execute("SELECT COUNT(*), SUM(current_stock) FROM "
                                    "inventory").fetchone(),
                "ben": conn.execute("SELECT COUNT(*) FROM beneficiaries").fetchone(),
                "imp": conn.execute("SELECT COUNT(*), SUM(successful_records) FROM "
                                    "data_imports").fetchone(),
                "src": conn.execute("SELECT COUNT(*) FROM data_sources").fetchone(),
            }
        finally:
            conn.close()
        for key in before:
            self.assertEqual(tuple(before[key]), tuple(after[key]),
                             "%s mutated by monitoring" % key)

    def test_filters_search_pagination_trend(self):
        monitoring.run_monitoring(db_path=self.db_path)
        self.assertEqual(self._alerts(severity="CRITICAL")["total"], 2)  # sync failure + critical coverage
        self.assertEqual(self._alerts(rule_type="SOURCE_FAILURE")["total"], 1)
        self.assertEqual(self._alerts(status="OPEN")["total"],
                         self._alerts()["total"])
        q = self._alerts(q="FPS1")["total"]
        self.assertGreaterEqual(q, 2)  # inventory alerts reference FPS1
        self.assertEqual(self._alerts(rule_type="DEMAND_DROP")["total"], 1)
        self.assertGreaterEqual(self._alerts(q="rice")["total"], 1)
        page = monitoring.list_alerts_view(db_path=self.db_path, page=1, per_page=2)
        self.assertEqual(len(page["alerts"]), 2)
        self.assertGreater(page["pages"], 1)
        trend = monitoring.alert_trend(db_path=self.db_path, days=7)
        self.assertGreaterEqual(trend["total"], 8)
        self.assertEqual(len(trend["series"]), 7)

    def test_detail_lineage(self):
        monitoring.run_monitoring(db_path=self.db_path)
        quality = self._alerts(rule_type="DATA_QUALITY")["alerts"][0]
        detail = monitoring.alert_detail_view(quality["alert_id"], db_path=self.db_path)
        self.assertIn("import", detail["lineage"])
        self.assertEqual(detail["lineage"]["import"]["dataset_name"],
                         "pds_fixture_%d" % (_SEED_COUNTER[0],))
        anomaly = self._alerts(rule_type="DISTRIBUTION_ANOMALY")["alerts"][0]
        detail2 = monitoring.alert_detail_view(anomaly["alert_id"], db_path=self.db_path)
        self.assertIn("analysis", detail2["lineage"])
        self.assertEqual(detail2["lineage"]["analysis"]["analysis_id"],
                         "RA-2026-9001")

    def test_rule_configuration_changes_behavior(self):
        monitoring.run_monitoring(db_path=self.db_path)
        rules = monitoring.alert_rules_view(db_path=self.db_path)["rules"]
        quality_rule = next(r for r in rules
                            if r["condition"] == "low_quality")
        # raise the quality threshold above the fixture's 80% -> still alert
        monitoring.update_rule_view(quality_rule["id"], threshold=75.0,
                                    db_path=self.db_path)
        monitoring.run_monitoring(db_path=self.db_path)
        self.assertEqual(self._alerts(rule_type="DATA_QUALITY")["total"], 1)
        # disable the rule -> next run resolves the existing alert
        monitoring.update_rule_view(quality_rule["id"], enabled=False,
                                    db_path=self.db_path)
        r = monitoring.run_monitoring(db_path=self.db_path)
        self.assertGreaterEqual(r["resolved"], 1)
        self.assertEqual(self._alerts(rule_type="DATA_QUALITY",
                                      status="OPEN")["total"], 0)


class AlertApiTests(unittest.TestCase):
    """API tests run against a THROWAWAY database so they never pollute the
    demo database (``data/rationright.db``)."""

    @classmethod
    def setUpClass(cls):
        for name in ("RATIONRIGHT_LLM_ENABLED", "OPENAI_API_KEY"):
            os.environ.pop(name, None)
        cls._tmp = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls._tmp.name) / "api.db"
        conn = db.open_db(cls.db_path)
        _seed(conn, stale_source=True, failed_source=True)
        conn.close()
        cls.server = make_server("127.0.0.1", 0, db_path=cls.db_path)
        cls.port = cls.server.server_address[1]
        cls.base = f"{BASE}:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls._tmp.cleanup()

    def request(self, method, path, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"} if data else {}
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode() or "{}")

    def test_alert_endpoints(self):
        status, payload = self.request("POST", "/api/monitoring/run", {})
        self.assertEqual(status, 200)
        self.assertIn("created", payload)
        status, summary = self.request("GET", "/api/alerts/summary")
        self.assertEqual(status, 200)
        self.assertIn("total_active", summary)
        status, trend = self.request("GET", "/api/alerts/trend?days=7")
        self.assertEqual(status, 200)
        self.assertEqual(len(trend["series"]), 7)
        status, rules = self.request("GET", "/api/alerts/rules")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(rules["rules"]), 11)
        status, listing = self.request("GET", "/api/alerts?per_page=3")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(listing["total"], 1)
        alert = listing["alerts"][0]
        status, detail = self.request("GET", "/api/alerts/" + alert["alert_id"])
        self.assertEqual(status, 200)
        self.assertIn("lineage", detail)
        # lifecycle through the API
        status, ack = self.request(
            "POST", "/api/alerts/" + alert["alert_id"] + "/acknowledge", {})
        self.assertEqual(status, 200)
        self.assertEqual(ack["status"], "ACKNOWLEDGED")
        status, dis = self.request(
            "POST", "/api/alerts/" + alert["alert_id"] + "/dismiss",
            {"reason": "False positive"})
        self.assertEqual(status, 200)
        self.assertEqual(dis["status"], "DISMISSED")
        # unknown alert -> 404
        status, _ = self.request("GET", "/api/alerts/ALT-0000-0000")
        self.assertEqual(status, 404)
        # invalid body -> 400
        status, _ = self.request("POST", "/api/alerts/" + alert["alert_id"] + "/resolve", "not-json")
        self.assertEqual(status, 400)
        # rule update
        rule_id = rules["rules"][0]["id"]
        status, updated = self.request("POST", "/api/alerts/rules/" + str(rule_id),
                                       {"enabled": True})
        self.assertEqual(status, 200)
        self.assertTrue(updated["enabled"])


if __name__ == "__main__":
    unittest.main()
