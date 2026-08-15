"""RationRight — Phase 10: Decision Support & What-If Simulation tests.

Covers ``simulation.py``: the scenario type registry, database-driven
entities/current situation, the deterministic scenario engine (demand
change, supply delay, inventory change, FPS/district scoping), input
validation and documented bounds, edge cases (zero stock / zero
consumption), the INSUFFICIENT_DATA contract, persistence (scenario
metadata only — real records are never modified), history/detail with
lineage, AI interpretation with its deterministic fallback, and the API
surface.

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
import simulation as sim
from server import make_server

BASE = "http://127.0.0.1"

_SEED_COUNTER = [0]


def _seed(conn, with_inventory=True, months=4, stock=1000.0,
          monthly=1200.0, threshold=500.0):
    """A real import with transactions + inventory for scenario math."""
    src = db.get_data_source_by_name(conn, "Uploaded Dataset")
    src_id = db.insert_data_source(
        conn, name="Uploaded Dataset", source_type="MANUAL",
        description="t", status="ACTIVE",
    ) if src is None else src["id"]
    imp_id = db.insert_data_import(
        conn, data_source_id=src_id, dataset_name="pds_aug",
        file_name="pds_aug.csv", file_type="CSV", record_count=100,
        successful_records=100, status="COMPLETED")
    db.upsert_beneficiaries(conn, [{"external_reference": "RB1",
                                    "district": "Lucknow",
                                    "ration_category": "AAY",
                                    "family_size": 4, "status": "ACTIVE"}])
    ben = db.beneficiary_ids(conn, ["RB1"])
    db.upsert_fps_centers(conn, [
        {"fps_code": "FPS1", "name": "Center One", "district": "Lucknow",
         "state": "UP", "status": "ACTIVE"},
        {"fps_code": "FPS2", "name": "Center Two", "district": "Kanpur",
         "state": "UP", "status": "ACTIVE"},
    ])
    fps = db.fps_center_ids(conn, ["FPS1", "FPS2"])
    rows = []
    _SEED_COUNTER[0] += 1
    seed_n = _SEED_COUNTER[0]
    seq = 0
    for month in range(months):
        m = "%02d" % (5 + month)  # 2026-05 .. 2026-08
        for i in range(4):
            seq += 1
            fps_id, qty = (fps["FPS1"], 100.0 + i * 10) if i % 2 == 0 \
                else (fps["FPS2"], 80.0 + i * 5)
            rows.append({
                "external_transaction_id": "TX%03d-%04d" % (seed_n, seq),
                "beneficiary_id": ben["RB1"], "fps_center_id": fps_id,
                "transaction_date": "2026-%s-%02d" % (m, i + 1),
                "commodity": "rice", "quantity": qty, "unit": "kg",
                "latitude": 26.8, "longitude": 80.9, "status": "COMPLETED",
                "source_import_id": imp_id,
            })
    db.insert_transactions_batch(conn, rows)
    if with_inventory:
        db.insert_inventory_batch(conn, [
            {"fps_center_id": fps["FPS1"], "commodity": "rice",
             "current_stock": stock, "monthly_consumption": monthly,
             "reorder_threshold": threshold, "source_import_id": imp_id},
            {"fps_center_id": fps["FPS2"], "commodity": "rice",
             "current_stock": stock * 2.4, "monthly_consumption": monthly * 2,
             "reorder_threshold": threshold, "source_import_id": imp_id},
        ])
    conn.commit()
    return imp_id


class ScenarioMathTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "sim.db"
        self.addCleanup(self._tmp.cleanup)
        self.conn = db.open_db(self.db_path)
        self.imp_id = _seed(self.conn)
        self.conn.close()

    def test_registry_types_are_real_and_described(self):
        types = sim.simulation_type_registry()
        keys = {t["key"] for t in types}
        self.assertEqual(keys, {"DEMAND_CHANGE", "SUPPLY_DELAY",
                                "INVENTORY_CHANGE", "COMBINED"})
        for t in types:
            self.assertTrue(t["label"] and t["description"])

    def test_entities_come_from_the_database(self):
        e = sim.simulation_entities(self.imp_id, db_path=self.db_path)
        self.assertEqual(e["commodities"], ["rice"])
        self.assertEqual(e["districts"], ["Kanpur", "Lucknow"])
        self.assertEqual(e["fps"], ["FPS1", "FPS2"])

    def test_current_situation_reports_real_metrics(self):
        sit = sim.current_situation(self.imp_id, db_path=self.db_path)
        self.assertEqual(sit["transaction_count"], 16)
        # 400 kg/month across 4 months (FPS1 220 + FPS2 180 per month)
        self.assertEqual(sit["total_quantity_kg"], 1600.0)
        # inventory 1000 + 2400 = 3400; consumption 1200 + 2400 = 3600/mo
        self.assertEqual(sit["inventory_stock_kg"], 3400.0)
        self.assertEqual(sit["monthly_consumption_kg"], 3600.0)
        self.assertEqual(sit["average_daily_consumption_kg"], 120.0)
        self.assertEqual(sit["estimated_coverage_days"],
                         round(3400 * 30 / 3600, 1))  # 28.3 days
        self.assertEqual(len(sit["high_risk_fps"]), 0)

    def test_demand_plus_ten_percent_is_deterministic(self):
        r = sim.run_scenario(self.imp_id, commodity="rice",
                             demand_change_pct=10, db_path=self.db_path)
        self.assertEqual(r["status"], "completed")
        # baseline monthly demand: 1600 kg over 4 months = 400 kg/month
        self.assertEqual(r["baseline"]["monthly_demand_kg"], 400.0)
        self.assertEqual(r["scenario"]["projected_monthly_demand_kg"], 440.0)
        # daily consumption 120 -> 132 kg/day; coverage 3400/132 = 25.8 days
        self.assertEqual(r["baseline"]["daily_consumption_kg"], 120.0)
        self.assertEqual(r["scenario"]["projected_daily_consumption_kg"], 132.0)
        self.assertEqual(r["scenario"]["projected_coverage_days"],
                         round(3400 / 132, 1))
        self.assertEqual(r["risk"], "WARNING")  # < 30-day threshold
        self.assertEqual(r["entity"]["id"], "whole_dataset")

    def test_demand_minus_ten_percent(self):
        r = sim.run_scenario(self.imp_id, commodity="rice",
                             demand_change_pct=-10, db_path=self.db_path)
        self.assertEqual(r["scenario"]["projected_monthly_demand_kg"], 360.0)
        self.assertEqual(r["scenario"]["projected_daily_consumption_kg"], 108.0)
        self.assertEqual(r["scenario"]["projected_coverage_days"],
                         round(3400 / 108, 1))
        self.assertEqual(r["risk"], "HEALTHY")

    def test_supply_delay_consumes_stock(self):
        r = sim.run_scenario(self.imp_id, commodity="rice",
                             supply_delay_days=7, db_path=self.db_path)
        sc = r["scenario"]
        self.assertEqual(sc["consumption_during_delay_kg"], 840.0)  # 120*7
        self.assertEqual(sc["projected_stock_after_delay_kg"], 2560.0)
        # requirement: projected monthly demand 400 - stock after delay 2560 -> 0
        self.assertEqual(sc["simulated_reorder_requirement_kg"], 0.0)

    def test_inventory_change_scale(self):
        r = sim.run_scenario(self.imp_id, commodity="rice",
                             inventory_change_pct=-25, db_path=self.db_path)
        self.assertEqual(r["scenario"]["stock_after_inventory_change_kg"], 2550.0)
        self.assertEqual(r["scenario"]["projected_coverage_days"],
                         round(2550 / 120, 1))
        r2 = sim.run_scenario(self.imp_id, commodity="rice",
                              inventory_change_pct=50, db_path=self.db_path)
        self.assertEqual(r2["scenario"]["stock_after_inventory_change_kg"], 5100.0)

    def test_combined_scenario(self):
        r = sim.run_scenario(self.imp_id, commodity="rice",
                             demand_change_pct=100, supply_delay_days=30,
                             inventory_change_pct=-50, db_path=self.db_path)
        sc = r["scenario"]
        self.assertEqual(sc["stock_after_inventory_change_kg"], 1700.0)
        self.assertEqual(sc["projected_daily_consumption_kg"], 240.0)
        self.assertEqual(sc["consumption_during_delay_kg"], 7200.0)
        self.assertEqual(sc["projected_stock_after_delay_kg"], 0.0)
        self.assertEqual(r["risk"], "CRITICAL")  # stock exhausted by the delay
        self.assertEqual(sc["simulated_reorder_requirement_kg"],
                         round(max(0.0, 800.0 - 0.0), 2))

    def test_fps_scoping_uses_only_that_center(self):
        r = sim.run_scenario(self.imp_id, commodity="rice", fps_code="FPS2",
                             db_path=self.db_path)
        self.assertEqual(r["entity"]["id"], "FPS2")
        self.assertEqual(r["entity"]["type"], "fps_center")
        # FPS2 only: stock 2400 kg, consumption 2400/mo -> daily 80
        self.assertEqual(r["baseline"]["current_stock_kg"], 2400.0)
        self.assertEqual(r["baseline"]["daily_consumption_kg"], 80.0)
        # FPS2 monthly demand: 720 kg over 4 months = 180 kg/month
        self.assertEqual(r["baseline"]["monthly_demand_kg"], 180.0)

    def test_district_scoping(self):
        r = sim.run_scenario(self.imp_id, commodity="rice", district="Kanpur",
                             db_path=self.db_path)
        self.assertEqual(r["entity"]["id"], "Kanpur")
        self.assertEqual(r["entity"]["type"], "district")
        self.assertEqual(r["baseline"]["current_stock_kg"], 2400.0)

    def test_zero_inventory_is_critical_not_unknown(self):
        conn = db.open_db(self.db_path)
        try:
            imp2 = _seed(conn, with_inventory=True, stock=0.0)
        finally:
            conn.close()
        r = sim.run_scenario(imp2, commodity="rice", db_path=self.db_path)
        self.assertEqual(r["risk"], "CRITICAL")


class EdgeCaseAndSafetyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "sim.db"
        self.addCleanup(self._tmp.cleanup)
        self.conn = db.open_db(self.db_path)

    def test_zero_consumption_marks_coverage_not_calculable(self):
        imp_id = _seed(self.conn, with_inventory=True, monthly=0.0)
        r = sim.run_scenario(imp_id, commodity="rice", db_path=self.db_path)
        self.assertEqual(r["scenario"]["coverage_label"], "NOT CALCULABLE")
        self.assertEqual(r["baseline"]["daily_consumption_kg"], None)
        self.assertEqual(r["risk"], "UNKNOWN")

    def test_no_inventory_means_no_stock_but_transactions_exist(self):
        imp_id = _seed(self.conn, with_inventory=False)
        r = sim.run_scenario(imp_id, commodity="rice", db_path=self.db_path)
        self.assertEqual(r["status"], "completed")
        self.assertEqual(r["baseline"]["current_stock_kg"], 0.0)
        self.assertEqual(r["risk"], "CRITICAL")

    def test_missing_scope_data_returns_insufficient(self):
        imp_id = _seed(self.conn)
        r = sim.run_scenario(imp_id, commodity="wheat", db_path=self.db_path)
        self.assertEqual(r["status"], "INSUFFICIENT_DATA")
        self.assertIn("no transactions", r["reason"].lower())
        self.assertIsNone(r["scenario_id"])

    def test_unknown_import_returns_insufficient(self):
        r = sim.run_scenario(99999, commodity="rice", db_path=self.db_path)
        self.assertEqual(r["status"], "INSUFFICIENT_DATA")

    def test_validation_rejects_out_of_range_values(self):
        with self.assertRaises(sim.SimulationError):
            sim.run_scenario(self.imp_id if False else 1, commodity="rice",
                             demand_change_pct=101, db_path=self.db_path)
        with self.assertRaises(sim.SimulationError):
            sim.run_scenario(1, commodity="rice", demand_change_pct=-51,
                             db_path=self.db_path)
        with self.assertRaises(sim.SimulationError):
            sim.run_scenario(1, commodity="rice", supply_delay_days=366,
                             db_path=self.db_path)
        with self.assertRaises(sim.SimulationError):
            sim.run_scenario(1, commodity="rice", supply_delay_days=-1,
                             db_path=self.db_path)
        with self.assertRaises(sim.SimulationError):
            sim.run_scenario(1, commodity="rice", inventory_change_pct=101,
                             db_path=self.db_path)
        with self.assertRaises(sim.SimulationError):
            sim.run_scenario(1, commodity=None, db_path=self.db_path)

    def test_boundary_values_are_accepted(self):
        imp_id = _seed(self.conn)
        r = sim.run_scenario(imp_id, commodity="rice", demand_change_pct=100,
                             supply_delay_days=0, inventory_change_pct=-100,
                             db_path=self.db_path)
        self.assertEqual(r["status"], "completed")
        self.assertEqual(r["scenario"]["stock_after_inventory_change_kg"], 0.0)
        self.assertEqual(r["risk"], "CRITICAL")

    def test_scenario_never_modifies_real_records(self):
        imp_id = _seed(self.conn)
        conn = db.open_db(self.db_path)
        before = {
            "stock": conn.execute("SELECT COALESCE(SUM(current_stock),0) FROM inventory").fetchone()[0],
            "tx": conn.execute("SELECT COUNT(*) FROM ration_transactions").fetchone()[0],
            "ben": conn.execute("SELECT COUNT(*) FROM beneficiaries").fetchone()[0],
        }
        conn.close()
        sim.run_scenario(imp_id, commodity="rice", demand_change_pct=50,
                         supply_delay_days=30, inventory_change_pct=-50,
                         db_path=self.db_path)
        conn = db.open_db(self.db_path)
        after = {
            "stock": conn.execute("SELECT COALESCE(SUM(current_stock),0) FROM inventory").fetchone()[0],
            "tx": conn.execute("SELECT COUNT(*) FROM ration_transactions").fetchone()[0],
            "ben": conn.execute("SELECT COUNT(*) FROM beneficiaries").fetchone()[0],
        }
        conn.close()
        self.assertEqual(before, after)

    def test_ai_interpretation_fallback_and_injection(self):
        imp_id = _seed(self.conn)
        # no LLM enabled -> deterministic fallback, flagged honestly
        r = sim.run_scenario(imp_id, commodity="rice", demand_change_pct=10,
                             db_path=self.db_path)
        self.assertEqual(r["interpretation"]["generated_by"],
                         "deterministic_fallback")
        self.assertIn("scenario result, not a prediction", r["interpretation"]["summary"])
        # injected generator -> llm path (deterministic math unchanged)
        calls = []
        def fake_gen(kind, context, fallback):
            calls.append(kind)
            return "AI: %s demand moves coverage from %s to %s days." % (
                context["demand_change_pct"],
                context["coverage_days_current"], context["coverage_days_projected"])
        r2 = sim.run_scenario(imp_id, commodity="rice", demand_change_pct=10,
                              db_path=self.db_path, generator=fake_gen)
        self.assertEqual(calls, ["scenario_interpretation"])
        self.assertEqual(r2["interpretation"]["generated_by"], "llm")
        self.assertEqual(r2["scenario"]["projected_monthly_demand_kg"],
                         r["scenario"]["projected_monthly_demand_kg"])
        # an injected generator that throws must not break the scenario
        r3 = sim.run_scenario(imp_id, commodity="rice", demand_change_pct=10,
                              db_path=self.db_path,
                              generator=lambda *a: (_ for _ in ()).throw(RuntimeError("x")))
        self.assertEqual(r3["status"], "completed")


class PersistenceAndLineageTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "sim.db"
        self.addCleanup(self._tmp.cleanup)
        self.conn = db.open_db(self.db_path)
        self.imp_id = _seed(self.conn)
        self.conn.close()

    def test_scenario_persisted_with_lineage(self):
        r = sim.run_scenario(self.imp_id, commodity="rice", district="Lucknow",
                             demand_change_pct=10, supply_delay_days=7,
                             db_path=self.db_path)
        self.assertRegex(r["scenario_id"], r"^SIM-\d{4}-\d{4}$")
        self.assertEqual(r["lineage"]["data_import_id"], self.imp_id)
        self.assertEqual(r["lineage"]["dataset_name"], "pds_aug")
        self.assertEqual(r["lineage"]["source_name"], "Uploaded Dataset")
        # persisted detail
        conn = db.open_db(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM scenarios WHERE scenario_id = :s",
                {"s": r["scenario_id"]}).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["risk"], r["risk"])
            self.assertEqual(row["entity_id"], "Lucknow")
            params = json.loads(row["parameters"])
            self.assertEqual(params["demand_change_pct"], 10)
            self.assertEqual(params["supply_delay_days"], 7)
        finally:
            conn.close()

    def test_history_and_detail_reproduce_the_scenario(self):
        sim.run_scenario(self.imp_id, commodity="rice", demand_change_pct=10,
                         db_path=self.db_path)
        sim.run_scenario(self.imp_id, commodity="rice", fps_code="FPS1",
                         supply_delay_days=5, db_path=self.db_path)
        hist = sim.scenario_history(db_path=self.db_path)
        self.assertEqual(hist["total"], 2)
        self.assertEqual(len(hist["scenarios"]), 2)
        first = hist["scenarios"][0]
        self.assertIn("dataset_name", first)
        self.assertIn("source_name", first)
        self.assertEqual(first["source_name"], "Uploaded Dataset")
        detail = sim.scenario_detail(first["id"], db_path=self.db_path)
        self.assertEqual(detail["scenario_id"], first["scenario_id"])
        self.assertEqual(detail["results"]["status"], "completed")
        self.assertEqual(detail["parameters"]["commodity"], "rice")
        self.assertEqual(detail["dataset_name"], "pds_aug")
        self.assertIsNotNone(detail["ai_interpretation"]["summary"])

    def test_run_again_creates_a_new_scenario(self):
        r1 = sim.run_scenario(self.imp_id, commodity="rice", demand_change_pct=10,
                              db_path=self.db_path)
        r2 = sim.run_scenario(self.imp_id, commodity="rice", demand_change_pct=10,
                              db_path=self.db_path)
        self.assertNotEqual(r1["scenario_id"], r2["scenario_id"])
        self.assertEqual(r1["scenario"]["projected_monthly_demand_kg"],
                         r2["scenario"]["projected_monthly_demand_kg"])


class SimulationApiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "sim-api.db"
        self.addCleanup(self._tmp.cleanup)
        self.conn = db.open_db(self.db_path)
        self.imp_id = _seed(self.conn)
        self.conn.close()
        server = make_server(host="127.0.0.1", port=0, db_path=self.db_path)
        self.thread = threading.Thread(target=server.serve_forever, daemon=True)
        self.thread.start()
        self.port = server.server_address[1]

    def _get(self, path):
        with urllib.request.urlopen(BASE + ":" + str(self.port) + path, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())

    def _post(self, path, body):
        req = urllib.request.Request(
            BASE + ":" + str(self.port) + path,
            data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())

    def test_types_endpoint(self):
        status, payload = self._get("/api/simulation/types")
        self.assertEqual(status, 200)
        self.assertEqual({t["key"] for t in payload["types"]},
                         {"DEMAND_CHANGE", "SUPPLY_DELAY", "INVENTORY_CHANGE", "COMBINED"})

    def test_entities_and_situation_endpoints(self):
        status, e = self._get("/api/simulation/entities?import_id=%d" % self.imp_id)
        self.assertEqual(status, 200)
        self.assertEqual(e["commodities"], ["rice"])
        status, sit = self._get("/api/simulation/situation?import_id=%d" % self.imp_id)
        self.assertEqual(status, 200)
        self.assertEqual(sit["inventory_stock_kg"], 3400.0)

    def test_run_endpoint_completes_and_persists(self):
        status, r = self._post("/api/simulation/run", {
            "import_id": self.imp_id, "commodity": "rice",
            "demand_change_pct": 50, "supply_delay_days": 30,
            "inventory_change_pct": -50})
        self.assertEqual(status, 200)
        self.assertEqual(r["status"], "completed")
        self.assertEqual(r["risk"], "CRITICAL")  # stock exhausted by delay
        status, hist = self._get("/api/simulation/history")
        self.assertEqual(status, 200)
        self.assertEqual(hist["total"], 1)
        status, detail = self._get("/api/simulation/history/%d" % hist["scenarios"][0]["id"])
        self.assertEqual(status, 200)
        self.assertEqual(detail["scenario_id"], r["scenario_id"])

    def test_run_endpoint_400_on_invalid_input(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post("/api/simulation/run", {
                "import_id": self.imp_id, "commodity": "rice",
                "demand_change_pct": 200})
        self.assertEqual(ctx.exception.code, 400)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post("/api/simulation/run", {"commodity": "rice"})
        self.assertEqual(ctx.exception.code, 400)

    def test_run_endpoint_insufficient_data_is_200(self):
        status, r = self._post("/api/simulation/run", {
            "import_id": self.imp_id, "commodity": "sugar"})
        self.assertEqual(status, 200)
        self.assertEqual(r["status"], "INSUFFICIENT_DATA")


if __name__ == "__main__":
    unittest.main()
