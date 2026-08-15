"""RationRight — Phase 7/8: backend API tests.

Starts the real server on an ephemeral port and exercises the endpoints,
including the Phase 8 health check and startup validation.

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

from scripts.validate_dataset import DEFAULT_DATASET_PATH, load_dataset
from server import build_health, make_server, validate_startup

BASE = "http://127.0.0.1"


def request(method, url, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, response.read().decode("utf-8"), dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8"), dict(exc.headers)


class TestRationRightAPI(unittest.TestCase):
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

    def test_dashboard_loads(self):
        """TEST 1 — the dashboard HTML is served.

        The shell is branded RationAI; interactive views (including the Run
        Analysis button) are rendered client-side from the real API.
        """
        status, body, _ = request("GET", self.base + "/")
        self.assertEqual(status, 200)
        self.assertIn("RationAI", body)
        self.assertIn("Overview", body)
        self.assertIn("/static/app.js", body)

    def test_dataset_endpoint(self):
        """The real Phase 1 dataset is exposed for the UI."""
        status, body, _ = request("GET", self.base + "/api/dataset")
        self.assertEqual(status, 200)
        dataset = json.loads(body)
        self.assertEqual(dataset["metadata"]["label"], "Synthetic Demo Data")
        self.assertEqual(len(dataset["transactions"]), 25)

    def test_analyze_runs_real_workflow(self):
        """POST /api/analyze executes the real agents end to end."""
        status, body, _ = request("POST", self.base + "/api/analyze", {"dataset": "synthetic"})
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result["workflow_status"], "completed")
        self.assertEqual(
            result["stages"],
            {"agent_1": "completed", "agent_2": "completed",
             "agent_3": "completed", "agent_4": "completed"},
        )
        self.assertEqual(len(result["anomalies"]), 1)
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(len(result["cases"]), 1)
        self.assertEqual(len(result["alerts"]), 1)
        self.assertEqual(result["errors"], [])

    def test_analyze_result_is_traceable_to_real_data(self):
        """The final alert traces back to actual Phase 1 transactions."""
        _, body, _ = request("POST", self.base + "/api/analyze", {})
        result = json.loads(body)
        _, dataset_body, _ = request("GET", self.base + "/api/dataset")
        real_ids = {t["transaction_id"] for t in json.loads(dataset_body)["transactions"]}

        alert = result["alerts"][0]
        case = result["cases"][0]
        finding = result["findings"][0]
        anomaly = result["anomalies"][0]
        self.assertEqual(alert["case_id"], case["case_id"])
        self.assertEqual(case["finding_ids"], [finding["finding_id"]])
        self.assertEqual(finding["anomaly_id"], anomaly["anomaly_id"])
        self.assertTrue(set(anomaly["transaction_ids"]).issubset(real_ids))
        self.assertEqual(anomaly["transaction_ids"], ["TX001", "TX002"])

    def test_analyze_evidence_matches_calculation(self):
        """The alert carries the exact calculated evidence (no mocks)."""
        _, body, _ = request("POST", self.base + "/api/analyze", {"dataset": "synthetic"})
        result = json.loads(body)
        finding = result["findings"][0]
        self.assertEqual(finding["status"], "verified")
        self.assertEqual(finding["evidence"]["time_difference_minutes"], 12.0)
        self.assertAlmostEqual(finding["evidence"]["distance_km"], 1148.09, places=2)
        alert = result["alerts"][0]
        self.assertIn("12.0", alert["message"])
        self.assertIn("1148.09", alert["message"])

    def test_unknown_dataset_rejected(self):
        # Phase 6: "real" is now a valid mode but requires data_import_id;
        # a bogus mode name is still rejected.
        status, body, _ = request("POST", self.base + "/api/analyze", {"dataset": "bogus"})
        self.assertEqual(status, 400)
        self.assertIn("Unknown dataset mode", body)
        status, body, _ = request("POST", self.base + "/api/analyze", {"dataset": "real"})
        self.assertEqual(status, 400)
        self.assertIn("data_import_id", body)

    def test_invalid_json_rejected(self):
        req = urllib.request.Request(
            self.base + "/api/analyze",
            data=b"{not json",
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=15)
        self.assertEqual(ctx.exception.code, 400)

    def test_unknown_path_404(self):
        status, _, _ = request("GET", self.base + "/api/nope")
        self.assertEqual(status, 404)

    def test_cors_preflight(self):
        """Phase 14: same-origin by default — no wildcard CORS header; the
        preflight still answers with allowed methods. Configured origins are
        covered in test_security.py."""
        status, _, headers = request("OPTIONS", self.base + "/api/analyze")
        self.assertEqual(status, 204)
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))
        self.assertIn("POST", headers.get("Access-Control-Allow-Methods", ""))

    # ---------- Phase 8: health check / startup validation ----------

    def test_health_endpoint(self):
        """GET /api/health reports every component as ok on the real system."""
        status, body, _ = request("GET", self.base + "/api/health")
        self.assertEqual(status, 200)
        health = json.loads(body)
        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["service"], "rationright")
        for name in ("dataset", "agent_1", "agent_2", "agent_3", "agent_4", "config"):
            self.assertIn(name, health["checks"], "missing check: %s" % name)
            self.assertEqual(health["checks"][name]["status"], "ok", name)
        self.assertIn("25 transaction(s)", health["checks"]["dataset"]["detail"])

    def test_health_build_detects_bad_dataset(self):
        """build_health reports a degraded/error dataset instead of crashing."""
        health = build_health(dataset_path=Path("/nonexistent/transactions.json"))
        self.assertEqual(health["status"], "error")
        self.assertEqual(health["checks"]["dataset"]["status"], "error")

    def test_startup_validation_rejects_missing_dataset(self):
        with self.assertRaises(ValueError) as ctx:
            validate_startup(Path("/nonexistent/transactions.json"))
        self.assertIn("not found", str(ctx.exception).lower())

    def test_startup_validation_rejects_invalid_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps({"transactions": [{"transaction_id": "TX1"}]}), encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                validate_startup(bad)
            self.assertIn("validation", str(ctx.exception).lower())

    def test_clean_dataset_analyze_returns_zero_alerts(self):
        """A dataset without the planted anomaly completes cleanly with 0 alerts."""
        with tempfile.TemporaryDirectory() as tmp:
            clean_path = Path(tmp) / "clean.json"
            dataset = load_dataset(DEFAULT_DATASET_PATH)
            dataset["transactions"] = [
                t for t in dataset["transactions"]
                if t["transaction_id"] not in ("TX001", "TX002")
            ]
            clean_path.write_text(json.dumps(dataset), encoding="utf-8")

            server = make_server("127.0.0.1", 0, dataset_path=clean_path)
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                status, body, _ = request("POST", f"{BASE}:{port}/api/analyze", {"dataset": "synthetic"})
                self.assertEqual(status, 200)
                result = json.loads(body)
                self.assertEqual(result["workflow_status"], "completed")
                self.assertEqual(result["anomalies"], [])
                self.assertEqual(result["findings"], [])
                self.assertEqual(result["cases"], [])
                self.assertEqual(result["alerts"], [])
                self.assertEqual(result["errors"], [])
                self.assertEqual(result["stages"]["agent_1"], "completed")
                self.assertEqual(result["stages"]["agent_2"], "skipped")
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
