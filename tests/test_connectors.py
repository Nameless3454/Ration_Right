"""RationRight — Phase 7: external data connector tests.

Covers the fetcher (timeout/retry/backoff/rate-limit), the connector sync
service (success, auth, malformed, empty, partial, duplicate, recovery), and
the data-source API. ALL external responses are MOCKED — no live government
API is claimed. The official OGD India source is documented in
``connectors/profiles.py`` and verified to fail cleanly when no API key is
configured (honest, not fake).

Run from the project root::

    python3 -m unittest discover -s tests -t . -v
"""

import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

import database as db
from connectors import service as conn_service
from connectors import sync_source
from connectors.errors import HttpStatusError, RateLimitError
from connectors.fetcher import http_get_bytes

SAMPLE_CSV = (Path(__file__).resolve().parent.parent / "data" / "sample" / "pds_sample.csv")


class FetcherRetryTests(unittest.TestCase):
    """Unit tests for the HTTP fetcher's retry/backoff policy."""

    def _patch_urlopen(self, responses, sleep_log=None):
        import connectors.fetcher as fetcher_mod

        calls = {"n": 0}

        class FakeResp:
            def __init__(self, data):
                self._data = data

            def getcode(self):
                return 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return self._data

        class FakeURLError(urllib.error.URLError):
            pass

        def fake_urlopen(request, timeout=None):
            calls["n"] += 1
            resp = responses[min(calls["n"] - 1, len(responses) - 1)]
            if isinstance(resp, Exception):
                raise resp
            if isinstance(resp, int):
                raise urllib.error.HTTPError(request.full_url, resp, "err", {}, None)
            return FakeResp(resp)

        self._orig = fetcher_mod.urllib.request.urlopen
        fetcher_mod.urllib.request.urlopen = fake_urlopen
        self._fetcher_mod = fetcher_mod
        self.addCleanup(setattr, fetcher_mod.urllib.request, "urlopen", self._orig)
        return calls

    def test_success(self):
        calls = self._patch_urlopen([b"data"])
        self.assertEqual(http_get_bytes("http://x"), b"data")
        self.assertEqual(calls["n"], 1)

    def test_404_no_retry(self):
        calls = self._patch_urlopen([404])
        with self.assertRaises(HttpStatusError) as cm:
            http_get_bytes("http://x")
        self.assertEqual(cm.exception.status, 404)
        self.assertFalse(cm.exception.retryable)
        self.assertEqual(calls["n"], 1)  # permanent error: exactly one attempt

    def test_500_retries_then_succeeds(self):
        sleep_log = []
        calls = self._patch_urlopen([500, 500, b"ok"])
        self.assertEqual(http_get_bytes("http://x", sleep=sleep_log.append), b"ok")
        self.assertEqual(calls["n"], 3)
        self.assertEqual(len(sleep_log), 2)  # backoff between attempts

    def test_500_exhausts_attempts(self):
        calls = self._patch_urlopen([500, 500, 500, 500])
        with self.assertRaises(HttpStatusError):
            http_get_bytes("http://x", max_attempts=3)
        self.assertEqual(calls["n"], 3)

    def test_429_respects_retry_after(self):
        import connectors.fetcher as fetcher_mod
        import urllib.error as ue

        calls = {"n": 0}
        sleep_log = []

        def fake_urlopen(request, timeout=None):
            calls["n"] += 1
            if calls["n"] == 1:
                e = ue.HTTPError(request.full_url, 429, "too many", {}, None)
                e.headers = {"Retry-After": "2"}
                raise e

            class FakeResp:
                def getcode(self):
                    return 200

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def read(self):
                    return b"ok"

            return FakeResp()

        orig = fetcher_mod.urllib.request.urlopen
        fetcher_mod.urllib.request.urlopen = fake_urlopen
        self.addCleanup(setattr, fetcher_mod.urllib.request, "urlopen", orig)
        self.assertEqual(http_get_bytes("http://x", sleep=sleep_log.append), b"ok")
        self.assertEqual(sleep_log, [2.0])  # honoured Retry-After

    def test_timeout_retries(self):
        import connectors.fetcher as fetcher_mod

        calls = {"n": 0}
        sleep_log = []

        def fake_urlopen(request, timeout=None):
            calls["n"] += 1
            raise urllib.error.URLError("timed out")

        orig = fetcher_mod.urllib.request.urlopen
        fetcher_mod.urllib.request.urlopen = fake_urlopen
        self.addCleanup(setattr, fetcher_mod.urllib.request, "urlopen", orig)
        from connectors.errors import TimeoutError

        with self.assertRaises(TimeoutError):
            http_get_bytes("http://x", max_attempts=2, sleep=sleep_log.append)
        self.assertEqual(calls["n"], 2)


class SyncServiceTests(unittest.TestCase):
    """Sync outcomes with an injected fake fetcher (no network)."""

    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "conn.db"
        self.addCleanup(self._tmp.cleanup)
        conn = db.open_db(self.db_path)
        conn_service.register_configured_sources(self.db_path)
        conn.close()
        self.sample_id = self._source_id("sample_open_pds")
        self.ogd_id = self._source_id("ogd_pds_resource")

    def _source_id(self, name):
        conn = db.open_db(self.db_path)
        try:
            row = db.get_data_source_by_name(conn, name)
            return row["id"] if row else None
        finally:
            conn.close()

    def _source(self, source_id):
        conn = db.open_db(self.db_path)
        try:
            return db.get_data_source(conn, source_id)
        finally:
            conn.close()

    def _csv_fetcher(self, data=None):
        payload = data if data is not None else SAMPLE_CSV.read_bytes()
        return lambda url: payload

    def _sync(self, source_id, fetcher):
        return sync_source(
            source_id, db_path=self.db_path, fetcher=fetcher,
            request_host="127.0.0.1:1",
        )

    def test_successful_csv_sync(self):
        summary = self._sync(self.sample_id, self._csv_fetcher())
        self.assertEqual(summary["status"], "COMPLETED")
        self.assertEqual(summary["fetched"], 14)
        self.assertEqual(summary["imported"], 14)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["duplicates"], 0)
        self.assertEqual(summary["quality"]["score"], 100.0)
        src = self._source(self.sample_id)
        self.assertEqual(src["status"], "ACTIVE")
        self.assertIsNotNone(src["last_successful_sync_at"])
        self.assertIsNone(src["last_error"])
        # provenance: an import record exists for this source
        conn = db.open_db(self.db_path)
        try:
            n = conn.execute("SELECT COUNT(*) FROM data_imports WHERE data_source_id=?",
                             (self.sample_id,)).fetchone()[0]
        finally:
            conn.close()
        self.assertGreaterEqual(n, 1)

    def test_repeat_sync_is_idempotent(self):
        self._sync(self.sample_id, self._csv_fetcher())
        summary = self._sync(self.sample_id, self._csv_fetcher())
        self.assertEqual(summary["status"], "UP_TO_DATE")
        self.assertEqual(summary["imported"], 0)
        self.assertEqual(summary["duplicates"], 14)
        self.assertEqual(summary["duplicates_exact"], 14)
        conn = db.open_db(self.db_path)
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM ration_transactions t JOIN data_imports i "
                "ON i.id = t.source_import_id WHERE i.data_source_id=?",
                (self.sample_id,),
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(n, 14)  # NOT doubled

    def test_auth_missing_never_fetches(self):
        calls = {"n": 0}

        def fetcher(url):
            calls["n"] += 1
            return b""

        summary = self._sync(self.ogd_id, fetcher)
        self.assertEqual(summary["status"], "ERROR")
        self.assertIn("API key not configured", summary["error"])
        self.assertEqual(calls["n"], 0)  # no fetch attempted without a key
        src = self._source(self.ogd_id)
        self.assertEqual(src["status"], "ERROR")
        self.assertIn("GOVERNMENT_DATA_API_KEY", src["last_error"])

    def test_key_present_reactivates_ogd_source(self):
        """Integrating a GOVERNMENT_DATA_API_KEY reactivates a source row that
        was created/left INACTIVE or ERROR for lack of one, and the key itself
        is never echoed into any public output (server-side only)."""
        key = "a" * 50
        with mock.patch.dict(os.environ, {"GOVERNMENT_DATA_API_KEY": key}):
            # INACTIVE (no key at setUp) -> ACTIVE, stale error cleared
            conn_service.register_configured_sources(self.db_path)
            src = self._source(self.ogd_id)
            self.assertEqual(src["status"], "ACTIVE")
            self.assertIsNone(src["last_error"])
            # ERROR (failed sync) -> ACTIVE once a key exists
            conn = db.open_db(self.db_path)
            try:
                conn.execute(
                    "UPDATE data_sources SET status = 'ERROR' WHERE id = :id",
                    {"id": self.ogd_id},
                )
                conn.commit()
            finally:
                conn.close()
            conn_service.register_configured_sources(self.db_path)
            src = self._source(self.ogd_id)
            self.assertEqual(src["status"], "ACTIVE")
            # key never appears in any public view; auth state is a boolean
            # and a source that has never synced is never "CONNECTED"
            conn = db.open_db(self.db_path)
            try:
                view = conn_service.source_view(conn, src)
            finally:
                conn.close()
            self.assertNotIn(key, json.dumps(view))
            self.assertIs(view["auth_configured"], True)
            self.assertEqual(view["connection_status"], "CONNECTOR_READY")
            self.assertNotEqual(view["connection_status"], "CONNECTED")
        # key removed again -> back to INACTIVE with an actionable error
        conn_service.register_configured_sources(self.db_path)
        src = self._source(self.ogd_id)
        self.assertEqual(src["status"], "INACTIVE")
        self.assertIn("GOVERNMENT_DATA_API_KEY", src["last_error"] or "")

    def test_http_404_error(self):
        def fetcher(url):
            raise HttpStatusError(404, "not found")

        summary = self._sync(self.sample_id, fetcher)
        self.assertEqual(summary["status"], "ERROR")
        self.assertFalse(summary["retryable"])
        self.assertIn("404", summary["error"])
        src = self._source(self.sample_id)
        self.assertEqual(src["status"], "ERROR")
        self.assertIsNone(src["last_successful_sync_at"])

    def _mh_fps_page(self, offset, limit, total=4, prefix="F"):
        """A page of Maharashtra-FPS-shaped records (real OGD resource schema)."""
        records = []
        for i in range(offset, min(offset + limit, total)):
            records.append({
                "_sr_no_": i + 1,
                "district_name": "Nandurbar",
                "name_of_block_tehsil": "Navapur",
                "area_type": "Rural",
                "name_of_fps": "SHOP-%s%d" % (prefix, i),
                "fps_id": 149728200000 + i,
                "longitude_of_fps": "73.59",
                "latitude_of_fps": 21.16,
            })
        return {"total": total, "records": records, "count": len(records)}

    def test_ogd_sync_sends_key_and_format(self):
        """A real OGD sync (with GOVERNMENT_DATA_API_KEY set) builds the
        documented URL — /resource/{id} + api-key + format=json + offset/limit
        — and imports the FPS registry as fps_centers, then reports CONNECTED
        only after the verified sync."""
        key = "a" * 50
        with mock.patch.dict(os.environ, {"GOVERNMENT_DATA_API_KEY": key}):
            conn_service.register_configured_sources(self.db_path)  # INACTIVE -> ACTIVE
            urls = []

            def fetcher(url):
                urls.append(url)
                offset = 0 if "offset=0" in url else 2
                return json.dumps(self._mh_fps_page(offset, 2)).encode()

            summary = self._sync(self.ogd_id, fetcher)
            self.assertEqual(summary["status"], "COMPLETED")
            self.assertEqual(summary["imported"], 4)
            self.assertEqual(summary["failed"], 0)
            self.assertEqual(len(urls), 2)
            for url in urls:
                self.assertIn("/resource/87e32686-a3a1-4b2f-ba3f-ac6cf7327f86", url)
                self.assertIn("api-key=%s" % key, url)
                self.assertIn("format=json", url)
            # verified sync -> CONNECTED (not CONNECTOR_READY)
            src = self._source(self.ogd_id)
            self.assertEqual(src["status"], "ACTIVE")
            conn = db.open_db(self.db_path)
            try:
                view = conn_service.source_view(conn, src)
            finally:
                conn.close()
            self.assertEqual(view["connection_status"], "CONNECTED")
            self.assertIs(view["auth_configured"], True)
            # the key still never leaves the server in any public view
            self.assertNotIn(key, json.dumps(view))
            # FPS centers landed in the database
            conn = db.open_db(self.db_path)
            try:
                n = conn.execute("SELECT COUNT(*) AS n FROM fps_centers").fetchone()["n"]
            finally:
                conn.close()
            self.assertEqual(n, 4)

    def test_rate_limit_error(self):
        def fetcher(url):
            raise RateLimitError("rate limited", retry_after=1.0)

        summary = self._sync(self.sample_id, fetcher)
        self.assertEqual(summary["status"], "ERROR")
        self.assertTrue(summary["retryable"])

    def test_malformed_response(self):
        # Not a valid CSV structure -> mapping fails with a clear message.
        summary = self._sync(self.sample_id, lambda url: b"this is not a csv")
        self.assertEqual(summary["status"], "ERROR")
        self.assertIn("no data rows", summary["error"])
        self.assertNotIn("Traceback", summary["error"])

    def test_malformed_json(self):
        # Valid CSV header but garbage data rows -> parse/mapping error.
        summary = self._sync(self.sample_id, lambda url: b"{\"broken\": true")
        self.assertEqual(summary["status"], "ERROR")
        self.assertNotIn("Traceback", summary["error"])

    def test_empty_response(self):
        summary = self._sync(self.sample_id, lambda url: b"")
        self.assertEqual(summary["status"], "ERROR")
        self.assertIn("empty", summary["error"].lower())

    def test_partial_import(self):
        # Add one invalid row (bad quantity) -> PARTIAL, valid rows imported.
        lines = SAMPLE_CSV.read_text().strip().splitlines()
        bad = lines[1].replace("1200", "abc")  # first data row, quantity -> invalid
        payload = ("\n".join([lines[0], bad] + lines[2:])).encode()
        summary = self._sync(self.sample_id, lambda url: payload)
        self.assertEqual(summary["status"], "PARTIAL")
        self.assertEqual(summary["imported"], 13)
        self.assertEqual(summary["failed"], 1)

    def test_source_recovery_after_failure(self):
        def failing(url):
            raise HttpStatusError(503, "unavailable")

        summary = self._sync(self.sample_id, failing)
        self.assertEqual(summary["status"], "ERROR")
        # now the source recovers
        summary = self._sync(self.sample_id, self._csv_fetcher())
        self.assertEqual(summary["status"], "COMPLETED")
        src = self._source(self.sample_id)
        self.assertEqual(src["status"], "ACTIVE")
        self.assertIsNone(src["last_error"])
        self.assertIsNotNone(src["last_successful_sync_at"])

    def test_json_pagination_merges_pages(self):
        profile = {
            "name": "paged", "label": "Paged", "type": "API",
            "base_url": "https://example.test/api", "format": "json",
            "dataset_type": "ration_transactions",
            "dataset_name": "paged_sync", "file_name": "p.json",
            "requires_auth": False,
            "pagination": {"type": "offset", "offset_param": "offset",
                           "limit_param": "limit", "page_size": 2,
                           "records_key": "records", "total_key": "total"},
            "mapping": {
                "fps_id": "fps_center_id", "district_name": "district",
                "commodity_name": "commodity", "distributed_qty": "quantity",
                "date": "transaction_date", "transaction_id": "external_transaction_id",
            },
        }
        page1 = {"total": 4, "records": [
            {"transaction_id": "P1", "fps_id": "F1", "district_name": "D1",
             "commodity_name": "Rice", "distributed_qty": 10, "date": "2026-08-01"},
            {"transaction_id": "P2", "fps_id": "F1", "district_name": "D1",
             "commodity_name": "Wheat", "distributed_qty": 20, "date": "2026-08-02"},
        ]}
        page2 = {"total": 4, "records": [
            {"transaction_id": "P3", "fps_id": "F2", "district_name": "D2",
             "commodity_name": "Rice", "distributed_qty": 15, "date": "2026-08-03"},
            {"transaction_id": "P4", "fps_id": "F2", "district_name": "D2",
             "commodity_name": "Sugar", "distributed_qty": 5, "date": "2026-08-04"},
        ]}
        urls = []

        def fetcher(url):
            urls.append(url)
            return json.dumps(page1 if "offset=0" in url else page2).encode()

        from connectors.base import connector_for
        conn = db.open_db(self.db_path)
        try:
            src_id = db.insert_data_source(conn, name="paged", source_type="API",
                                           description="paged test", status="ACTIVE")
            conn.commit()
        finally:
            conn.close()
        from connectors.service import run_sync_import

        connector = connector_for(profile)
        pages = connector.fetch(fetcher, lambda b: b)
        headers, rows = connector.parse(pages)
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(urls), 2)  # two pages fetched, stopped at total
        mapping = connector.map_columns(headers)
        import database as db2
        conn = db.open_db(self.db_path)
        try:
            summary = run_sync_import(conn, {"id": src_id, "name": "paged"},
                                      profile, headers, rows, mapping, pages)
        finally:
            conn.close()
        self.assertEqual(summary["imported"], 4)


class DataSourceApiTests(unittest.TestCase):
    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "api.db"
        self.addCleanup(self._tmp.cleanup)
        conn = db.open_db(self.db_path)
        conn_service.register_configured_sources(self.db_path)
        conn.close()
        from server import make_server

        self.server = make_server("127.0.0.1", 0, db_path=str(self.db_path))
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def _get(self, path):
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path), timeout=30) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def _post(self, path, body=None):
        req = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (self.port, path),
            data=json.dumps(body or {}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_list_and_detail(self):
        status, payload = self._get("/api/data-sources")
        self.assertEqual(status, 200)
        names = {s["name"] for s in payload["sources"]}
        self.assertIn("sample_open_pds", names)
        self.assertIn("ogd_pds_resource", names)
        sample = next(s for s in payload["sources"] if s["name"] == "sample_open_pds")
        status, detail = self._get("/api/data-sources/%d" % sample["data_source_id"])
        self.assertEqual(status, 200)
        self.assertEqual(detail["name"], "sample_open_pds")

    def test_unknown_source_404(self):
        self.assertEqual(self._get("/api/data-sources/9999")[0], 404)
        self.assertEqual(self._post("/api/data-sources/9999/sync")[0], 404)

    def test_sync_via_api_with_bundled_sample(self):
        status, payload = self._get("/api/data-sources")
        sample = next(s for s in payload["sources"] if s["name"] == "sample_open_pds")
        status, summary = self._post(
            "/api/data-sources/%d/sync" % sample["data_source_id"]
        )
        self.assertEqual(status, 200)
        self.assertEqual(summary["status"], "COMPLETED")
        self.assertEqual(summary["imported"], 14)
        status, imports = self._get("/api/data-sources/%d/imports" % sample["data_source_id"])
        self.assertEqual(status, 200)
        self.assertEqual(len(imports["imports"]), 1)
        status, st = self._get("/api/data-sources/%d/status" % sample["data_source_id"])
        self.assertEqual(status, 200)
        self.assertEqual(st["connection_status"], "CONNECTED")

    def test_sync_ignores_user_supplied_url(self):
        # SSRF guard: a crafted URL in the body must be ignored — the sync
        # only ever fetches the registered base_url.
        status, payload = self._get("/api/data-sources")
        sample = next(s for s in payload["sources"] if s["name"] == "sample_open_pds")
        status, summary = self._post(
            "/api/data-sources/%d/sync" % sample["data_source_id"],
            {"url": "http://169.254.169.254/latest/meta-data"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(summary["status"], "COMPLETED")  # fetched registered sample URL

    def test_ogd_source_honest_not_live(self):
        """The official source is never presented as live: the connector is
        implemented (CONNECTOR_READY), the API key is missing, and a sync
        attempt fails cleanly without touching data (Phase 8 label)."""
        status, payload = self._get("/api/data-sources")
        ogd = next(s for s in payload["sources"] if s["name"] == "ogd_pds_resource")
        self.assertEqual(ogd["connection_status"], "CONNECTOR_READY")
        self.assertNotEqual(ogd["connection_status"], "CONNECTED")
        self.assertIn("GOVERNMENT_DATA_API_KEY", ogd["last_error"] or "")
        status, summary = self._post("/api/data-sources/%d/sync" % ogd["data_source_id"])
        self.assertEqual(status, 502)
        self.assertEqual(summary["status"], "ERROR")
        self.assertIn("API key not configured", summary["error"])


if __name__ == "__main__":
    unittest.main()
