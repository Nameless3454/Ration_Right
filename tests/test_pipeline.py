"""RationRight — Phase 8: Data Pipeline status, quality, freshness, lineage.

Covers ``pipeline.py``: the 8-stage pipeline status, overall health checks,
data freshness thresholds, the data quality panel (reusing the Phase 4
formula), server-side run history with filters/search/pagination, per-run
lineage (source -> import -> records -> database -> analysis -> AI), and the
real connection-test probe. Also verifies that ``POST /api/analyze`` records
a durable analysis run so AI insights trace back to their dataset.

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
import pipeline as pl
from connectors.errors import AuthError, UnreachableError
from server import make_server

BASE = "http://127.0.0.1"


def _seed(conn):
    """Deterministic temp DB: synthetic seed + one completed upload import."""
    db.seed_synthetic(conn)
    src = db.get_data_source_by_name(conn, "Uploaded Dataset")
    if src is None:
        src_id = db.insert_data_source(
            conn, name="Uploaded Dataset", source_type="MANUAL",
            description="test", status="ACTIVE",
        )
    else:
        src_id = src["id"]
    imp_id = db.insert_data_import(
        conn, data_source_id=src_id, dataset_name="up_test_aug",
        file_name="up_test.csv", file_type="CSV", record_count=100,
        successful_records=90, failed_records=6, duplicate_records=4,
        warnings_count=5, status="PARTIAL",
    )
    # Two real transaction rows so lineage counts are meaningful.
    db.upsert_beneficiaries(conn, [{"external_reference": "RB01", "district": "Lucknow",
                                    "ration_category": "AAY", "family_size": 4, "status": "ACTIVE"}])
    ben_map = db.beneficiary_ids(conn, ["RB01"])
    db.insert_transactions_batch(conn, [
        {"external_transaction_id": "UP1", "beneficiary_id": ben_map["RB01"],
         "fps_center_id": None, "transaction_date": "2026-08-01", "commodity": "rice",
         "quantity": 10.0, "unit": "kg", "latitude": 26.8, "longitude": 80.9,
         "status": "COMPLETED", "source_import_id": imp_id},
        {"external_transaction_id": "UP2", "beneficiary_id": ben_map["RB01"],
         "fps_center_id": None, "transaction_date": "2026-08-02", "commodity": "wheat",
         "quantity": 5.0, "unit": "kg", "latitude": 26.9, "longitude": 81.0,
         "status": "COMPLETED", "source_import_id": imp_id},
    ])
    conn.commit()
    return src_id, imp_id


class PipelineStatusTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "pipe.db"
        self.addCleanup(self._tmp.cleanup)
        self.conn = db.open_db(self.db_path)

    def test_status_stages_reflect_real_database(self):
        """Each stage reports counts computed from the actual database."""
        _seed(self.conn)
        status = pl.pipeline_status(db_path=self.db_path)
        by_key = {s["key"]: s for s in status["stages"]}
        # source: 2 configured sources (synthetic + uploaded)
        self.assertEqual(by_key["source"]["records"], 2)
        # extract: sum of record_count across imports = 25 + 100
        self.assertEqual(by_key["extract"]["records"], 125)
        # validate: sum of successful/failed/warnings
        self.assertEqual(by_key["validate"]["records"], 25 + 90)
        self.assertIn("6 invalid", by_key["validate"]["detail"])
        # deduplicate: 4 duplicates reported (0 from synthetic)
        self.assertEqual(by_key["deduplicate"]["records"], 4)
        # database: stored rows exist
        self.assertGreater(by_key["database"]["records"], 0)
        # ai: no analysis run yet -> warn/unknown, never a fake number
        self.assertIn(by_key["ai"]["status"], ("warn", "unknown"))
        self.assertEqual(by_key["ai"]["records"], 0)

    def test_overall_warns_without_analysis_then_healthy_after_run(self):
        db.seed_synthetic(self.conn)  # last import COMPLETED
        self.assertEqual(pl.pipeline_status(db_path=self.db_path)["overall"], "WARNING")
        pl.record_analysis_run(
            {"anomalies": [], "findings": [], "cases": [], "alerts": [],
             "errors": [], "workflow_status": "completed"},
            dataset_mode="synthetic", db_path=self.db_path,
        )
        self.assertEqual(pl.pipeline_status(db_path=self.db_path)["overall"], "HEALTHY")

    def test_overall_error_when_last_import_failed(self):
        db.seed_synthetic(self.conn)
        src = db.get_data_source_by_name(self.conn, "Uploaded Dataset")
        if src is None:
            src_id = db.insert_data_source(
                self.conn, name="Uploaded Dataset", source_type="MANUAL", status="ACTIVE")
        else:
            src_id = src["id"]
        db.insert_data_import(
            self.conn, data_source_id=src_id, dataset_name="broken",
            record_count=0, failed_records=1, status="FAILED",
        )
        self.conn.commit()
        self.assertEqual(pl.pipeline_status(db_path=self.db_path)["overall"], "ERROR")


class FreshnessTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "fresh.db"
        self.addCleanup(self._tmp.cleanup)
        self.conn = db.open_db(self.db_path)

    def test_unknown_without_imports(self):
        f = pl.freshness(db_path=self.db_path)
        self.assertEqual(f["status"], "UNKNOWN")
        self.assertIsNone(f["latest_data_at"])

    def test_fresh_after_seed(self):
        db.seed_synthetic(self.conn)
        f = pl.freshness(db_path=self.db_path)
        self.assertEqual(f["status"], "FRESH")
        self.assertIsNotNone(f["age_label"])

    def test_stale_with_old_timestamp(self):
        db.seed_synthetic(self.conn)
        self.conn.execute(
            "UPDATE data_imports SET completed_at = '2026-01-01T00:00:00'"
        )
        self.conn.commit()
        self.assertEqual(pl.freshness(db_path=self.db_path)["status"], "UNKNOWN")


class QualityPanelTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "quality.db"
        self.addCleanup(self._tmp.cleanup)
        self.conn = db.open_db(self.db_path)

    def test_score_matches_phase4_formula(self):
        _seed(self.conn)
        q = pl.quality_panel(db_path=self.db_path)
        # Synthetic import: 25/25/0/0 -> 100. Upload: 100 records, 6 invalid,
        # 4 dupes, 5 warnings -> 100 - 3*6 - 2*4 - 0.5*5 = 100-18-8-2.5 = 71.5.
        # Weighted: (100*25 + 71.5*100) / 125 = (2500 + 7150)/125 = 77.2.
        self.assertEqual(q["overall_score"], 77.2)
        self.assertEqual(q["breakdown"]["completeness"], None)  # not stored -> Not available
        self.assertEqual(q["totals"]["records"], 125)

    def test_empty_database(self):
        q = pl.quality_panel(db_path=self.db_path)
        self.assertIsNone(q["overall_score"])
        self.assertEqual(q["totals"]["records"], 0)


class PipelineRunsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "runs.db"
        self.addCleanup(self._tmp.cleanup)
        self.conn = db.open_db(self.db_path)
        self.src_id, self.imp_id = _seed(self.conn)

    def test_runs_listed_with_quality(self):
        data = pl.pipeline_runs(db_path=self.db_path)
        self.assertEqual(data["total"], 2)
        ids = {r["id"] for r in data["runs"]}
        self.assertIn(self.imp_id, ids)
        by_id = {r["id"]: r for r in data["runs"]}
        self.assertEqual(by_id[self.imp_id]["quality_score"], 71.5)
        self.assertIn("Uploaded Dataset", [s["name"] for s in data["sources"]])

    def test_source_filter(self):
        data = pl.pipeline_runs(db_path=self.db_path, source=self.src_id)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["runs"][0]["id"], self.imp_id)

    def test_status_filter_and_search(self):
        data = pl.pipeline_runs(db_path=self.db_path, status="PARTIAL")
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["runs"][0]["status"], "PARTIAL")
        data = pl.pipeline_runs(db_path=self.db_path, q="up_test")
        self.assertEqual(data["total"], 1)
        data = pl.pipeline_runs(db_path=self.db_path, q="nonexistent")
        self.assertEqual(data["total"], 0)

    def test_pagination(self):
        data = pl.pipeline_runs(db_path=self.db_path, page=1, per_page=1)
        self.assertEqual(len(data["runs"]), 1)
        self.assertEqual(data["pages"], 2)
        self.assertEqual(data["total"], 2)
        page2 = pl.pipeline_runs(db_path=self.db_path, page=2, per_page=1)
        self.assertNotEqual(data["runs"][0]["id"], page2["runs"][0]["id"])


class LineageTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "lineage.db"
        self.addCleanup(self._tmp.cleanup)
        self.conn = db.open_db(self.db_path)
        self.src_id, self.imp_id = _seed(self.conn)

    def test_run_detail_lineage_chain(self):
        pl.record_analysis_run(
            {"anomalies": [{}], "findings": [{}], "cases": [{}], "alerts": [{}],
             "errors": [], "workflow_status": "completed"},
            dataset_mode="real", data_import_id=self.imp_id, db_path=self.db_path,
        )
        detail = pl.run_detail(self.imp_id, db_path=self.db_path)
        self.assertIsNotNone(detail)
        self.assertEqual(detail["import"]["data_import_id"], self.imp_id)
        self.assertEqual(detail["source"]["name"], "Uploaded Dataset")
        self.assertEqual(detail["records"]["record_count"], 100)
        self.assertEqual(detail["records"]["quality"]["score"], 71.5)
        self.assertEqual(detail["database"]["transactions"], 2)  # this import's rows
        self.assertEqual(detail["database"]["beneficiaries"], 1)
        self.assertEqual(len(detail["analysis_runs"]), 1)
        self.assertEqual(detail["analysis_runs"][0]["dataset_mode"], "real")
        self.assertEqual(detail["analysis_runs"][0]["alert_count"], 1)

    def test_run_detail_unknown_import(self):
        self.assertIsNone(pl.run_detail(999999, db_path=self.db_path))

    def test_record_analysis_run_statuses(self):
        run = pl.record_analysis_run(
            {"anomalies": [], "findings": [], "cases": [], "alerts": [],
             "errors": [], "skipped_reason": "Dataset has 1 transaction record(s).",
             "workflow_status": "completed"},
            dataset_mode="real", data_import_id=self.imp_id, db_path=self.db_path,
        )
        self.assertTrue(run["analysis_id"].startswith("RA-"))
        conn = db.open_db(self.db_path)
        try:
            runs = db.get_analysis_runs_for_import(conn, import_id=self.imp_id)
        finally:
            conn.close()
        self.assertEqual(runs[0]["status"], "INSUFFICIENT_DATA")
        self.assertEqual(runs[0]["summary"], "Dataset has 1 transaction record(s).")


class ConnectionTestTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "conn.db"
        self.addCleanup(self._tmp.cleanup)
        self.conn = db.open_db(self.db_path)
        db.seed_synthetic(self.conn)

    def _add_source(self, name, source_type, base_url, status="ACTIVE"):
        sid = db.insert_data_source(
            self.conn, name=name, source_type=source_type,
            description="t", status=status, base_url=base_url,
        )
        self.conn.commit()  # release the write lock before probe connections
        return sid

    def test_unknown_source(self):
        probe = pl.test_connection(999999, db_path=self.db_path)
        self.assertEqual(probe["category"], "UNKNOWN_SOURCE")
        self.assertEqual(probe["status"], "error")

    def test_ogd_without_key_is_not_tested(self):
        """Auth-required source with no key: NOT_CONFIGURED, never fetched."""
        sid = self._add_source("ogd_pds_resource", "API", "https://example.in/api")
        probe = pl.test_connection(sid, db_path=self.db_path)
        self.assertEqual(probe["category"], "AUTH_NOT_CONFIGURED")
        self.assertEqual(probe["status"], "not_configured")
        self.assertIn("NOT tested", probe["detail"])

    def test_successful_probe(self):
        sid = self._add_source("sample_open_pds", "CSV", "/sample/pds_sample.csv")
        probe = pl.test_connection(
            sid, db_path=self.db_path, request_host="127.0.0.1:8000",
            fetcher=lambda url, timeout=6, max_attempts=1: b"a,b,c\n1,2,3\n",
        )
        self.assertEqual(probe["status"], "ok")
        self.assertEqual(probe["category"], "CONNECTION_OK")

    def test_auth_failure_probe(self):
        sid = self._add_source("sample_open_pds", "CSV", "/sample/pds_sample.csv")
        def fail(url, timeout=6, max_attempts=1):
            raise AuthError("The source rejected the request credentials (HTTP 401)")
        probe = pl.test_connection(
            sid, db_path=self.db_path, request_host="127.0.0.1:8000", fetcher=fail,
        )
        self.assertEqual(probe["category"], "AUTH_FAILED")

    def test_unreachable_probe(self):
        sid = self._add_source("sample_open_pds", "CSV", "/sample/pds_sample.csv")
        def fail(url, timeout=6, max_attempts=1):
            raise UnreachableError("Could not reach the source")
        probe = pl.test_connection(
            sid, db_path=self.db_path, request_host="127.0.0.1:8000", fetcher=fail,
        )
        self.assertEqual(probe["category"], "UNREACHABLE")


class PipelineApiTests(unittest.TestCase):
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
            with urllib.request.urlopen(req, timeout=20) as response:
                return response.status, response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    def test_pipeline_status_endpoint(self):
        status, body = self.request("GET", "/api/pipeline/status")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertIn(payload["overall"], ("HEALTHY", "WARNING", "ERROR"))
        self.assertEqual(len(payload["stages"]), 8)

    def test_pipeline_freshness_endpoint(self):
        status, body = self.request("GET", "/api/pipeline/freshness")
        self.assertEqual(status, 200)
        self.assertIn(json.loads(body)["status"], ("FRESH", "RECENT", "STALE", "UNKNOWN"))

    def test_pipeline_runs_endpoint(self):
        status, body = self.request("GET", "/api/pipeline/runs?per_page=5")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertIn("runs", payload)
        self.assertIn("total", payload)

    def test_pipeline_run_detail_endpoint(self):
        _, body = self.request("GET", "/api/pipeline/runs?per_page=1")
        run_id = json.loads(body)["runs"][0]["id"]
        status, body = self.request("GET", "/api/pipeline/runs/%d" % run_id)
        self.assertEqual(status, 200)
        detail = json.loads(body)
        for key in ("import", "source", "records", "database", "analysis_runs"):
            self.assertIn(key, detail)

    def test_pipeline_run_detail_unknown(self):
        status, _ = self.request("GET", "/api/pipeline/runs/999999")
        self.assertEqual(status, 404)

    def test_connection_test_unknown_source(self):
        status, body = self.request("POST", "/api/data-sources/999999/test", {})
        self.assertEqual(status, 404)

    def test_analyze_records_analysis_run(self):
        """POST /api/analyze now persists lineage metadata in the result."""
        status, body = self.request("POST", "/api/analyze", {"dataset": "synthetic"})
        self.assertEqual(status, 200)
        result = json.loads(body)
        run = result.get("analysis_run")
        self.assertIsNotNone(run)
        self.assertTrue(run["analysis_id"].startswith("RA-"))
        self.assertEqual(run["status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
