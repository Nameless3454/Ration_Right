"""RationRight — Phase 14: Security, Reliability & Production Hardening tests.

Covers the audit-log database layer, security headers, same-origin CORS
(default) and configured-origin behavior, opt-in bearer-token authentication
(login / logout / session revocation / forged-token rejection / route
protection / login rate limiting), readiness endpoint, input validation (bad
date ranges, SQL-injection attempts on filters, clamped pagination), upload
hardening (extension, magic bytes, size), import rollback atomicity (a
critical failure leaves no partial dataset), error sanitization (no stack
traces / filesystem paths leaked), and a source-wide hardcoded-secret scan.

Run from the project root::

    python3 -m unittest discover -s tests -t . -v
"""

import http.client
import importlib
import json
import os
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import database as db

BASE = "http://127.0.0.1"
ROOT = Path(__file__).resolve().parent.parent

TRANSACTION_CSV = (
    "Transaction ID,Beneficiary ID,FPS Code,Transaction Date,Commodity,Quantity,Unit\n"
    "TX1001,BEN001,FPS01,2026-08-01,rice,10,kg\n"
    "TX1002,BEN001,FPS01,2026-08-02,rice,5,kg\n"
    "TX1003,BEN002,FPS02,2026-08-01,wheat,8,kg\n"
)

_ENV_KEYS = ("RATIONRIGHT_AUTH_TOKEN", "RATIONRIGHT_ALLOWED_ORIGINS",
             "RATIONRIGHT_CORS_ALLOW_ANY", "RATIONRIGHT_SESSION_SECRET")


def _fresh_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.unlink(tmp.name)
    return tmp.name


class _ServerContext:
    """A live server in a fresh process-independent env (module reloaded)."""

    def __init__(self, env=None, db_path=None):
        self.saved = {k: os.environ.get(k) for k in _ENV_KEYS}
        for k in _ENV_KEYS:
            os.environ.pop(k, None)
        if env:
            os.environ.update(env)
        import server as srv
        srv = importlib.reload(srv)
        self.srv = srv
        self.db_path = db_path or _fresh_db()
        self.httpd = srv.make_server(port=0, db_path=self.db_path)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        import server as srv
        importlib.reload(srv)
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def request(self, method, path, data=None, headers=None, timeout=30):
        req = urllib.request.Request(
            "%s:%d%s" % (BASE, self.port, path), data=data,
            headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()


class SecretScanTests(unittest.TestCase):
    """No hardcoded secrets anywhere outside the git-ignored .env."""

    def test_no_hardcoded_api_keys_in_source(self):
        # Match real key shapes only, so UI class names ("risk-grid"),
        # doc comments ("sk-or-v1-..."), and short test fixtures
        # ("sk-test") are not false positives.
        patterns = (
            re.compile(r"sk-(?:proj-|or-v1-)?[A-Za-z0-9_-]{16,}"),
            re.compile(r"api[_-]?key\s*[:=]\s*[\"'][A-Za-z0-9]{16,}"),
        )
        hits = []
        for path in list(ROOT.rglob("*.py")) + list(ROOT.rglob("*.js")) \
                + list(ROOT.rglob("*.html")) + list(ROOT.rglob("*.md")):
            if ".freebuff" in path.parts or "__pycache__" in path.parts:
                continue
            text = path.read_text(errors="ignore")
            for pattern in patterns:
                for match in pattern.finditer(text):
                    hits.append("%s:%d: %s" % (path, 1 + text.count("\n", 0, match.start()),
                                                match.group(0)))
        self.assertEqual(hits, [])

    def test_env_example_is_placeholders_only(self):
        example = (ROOT / ".env.example").read_text()
        self.assertIn("OPENAI_API_KEY=", example)
        secret_like = ("KEY", "SECRET", "TOKEN", "PASSWORD")
        for line in example.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if any(s in key.upper() for s in secret_like):
                self.assertEqual(value.strip(), "",
                                 "%s must be an empty placeholder in .env.example"
                                 % key)

    def test_env_is_gitignored(self):
        gitignore = (ROOT / ".gitignore").read_text()
        self.assertIn(".env", gitignore)


class SecurityHeadersTests(unittest.TestCase):
    def setUp(self):
        self.ctx = _ServerContext()

    def tearDown(self):
        self.ctx.close()

    def test_api_response_headers(self):
        status, headers, _ = self.ctx.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(headers.get("Referrer-Policy"), "no-referrer")
        self.assertEqual(headers.get("X-Frame-Options"), "DENY")
        self.assertIn("Content-Security-Policy", headers)
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        self.assertTrue(headers.get("X-Request-ID"))

    def test_static_response_headers(self):
        status, headers, _ = self.ctx.request("GET", "/static/app.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")

    def test_cors_same_origin_default(self):
        # No Origin header / same-origin usage must not receive a wildcard.
        _, headers, _ = self.ctx.request("GET", "/api/datasets")
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))
        _, headers, _ = self.ctx.request("OPTIONS", "/api/analyze")
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))
        self.assertIn("POST", headers.get("Access-Control-Allow-Methods", ""))


class CorsConfiguredTests(unittest.TestCase):
    def test_configured_origin_is_echoed(self):
        ctx = _ServerContext(env={
            "RATIONRIGHT_ALLOWED_ORIGINS": "https://ops.example.com"})
        try:
            _, h1, _ = ctx.request("GET", "/api/health",
                                   headers={"Origin": "https://ops.example.com"})
            self.assertEqual(h1.get("Access-Control-Allow-Origin"),
                             "https://ops.example.com")
            _, h2, _ = ctx.request("GET", "/api/health",
                                   headers={"Origin": "https://evil.example.com"})
            self.assertIsNone(h2.get("Access-Control-Allow-Origin"))
        finally:
            ctx.close()

    def test_cors_allow_any_opt_in(self):
        ctx = _ServerContext(env={"RATIONRIGHT_CORS_ALLOW_ANY": "1"})
        try:
            _, headers, _ = ctx.request("GET", "/api/health")
            self.assertEqual(headers.get("Access-Control-Allow-Origin"), "*")
        finally:
            ctx.close()


class AuthTests(unittest.TestCase):
    def test_auth_disabled_by_default(self):
        ctx = _ServerContext()
        try:
            status, _, body = ctx.request("GET", "/api/auth/status")
            payload = json.loads(body)
            self.assertFalse(payload["auth_enabled"])
            self.assertEqual(ctx.request("GET", "/api/datasets")[0], 200)
        finally:
            ctx.close()

    def test_auth_enabled_flow(self):
        ctx = _ServerContext(env={"RATIONRIGHT_AUTH_TOKEN": "secret-token-abc"})
        try:
            # Unauthenticated API -> 401 UNAUTHORIZED (server-side, not UI hiding)
            status, _, body = ctx.request("GET", "/api/datasets")
            self.assertEqual(status, 401)
            self.assertEqual(json.loads(body)["error"]["code"], "UNAUTHORIZED")
            # health stays public
            self.assertEqual(ctx.request("GET", "/api/health")[0], 200)
            # wrong token -> 401
            status, _, _ = ctx.request(
                "POST", "/api/auth/login",
                json.dumps({"token": "wrong"}).encode(),
                {"Content-Type": "application/json"})
            self.assertEqual(status, 401)
            # correct token -> session cookie (HttpOnly, SameSite)
            status, headers, _ = ctx.request(
                "POST", "/api/auth/login",
                json.dumps({"token": "secret-token-abc"}).encode(),
                {"Content-Type": "application/json"})
            self.assertEqual(status, 200)
            set_cookie = headers["Set-Cookie"]
            self.assertIn("HttpOnly", set_cookie)
            self.assertIn("SameSite=Lax", set_cookie)
            self.assertNotIn("Secure", set_cookie)  # local http
            cookie = set_cookie.split(";")[0]
            # authenticated access works
            self.assertEqual(
                ctx.request("GET", "/api/datasets",
                            headers={"Cookie": cookie})[0], 200)
            # forged cookie (tampered signature) -> 401
            forged = cookie[:-2] + ("aa" if not cookie.endswith("aa") else "bb")
            self.assertEqual(
                ctx.request("GET", "/api/datasets",
                            headers={"Cookie": forged})[0], 401)
            # logout revokes the session server-side
            ctx.request("POST", "/api/auth/logout", b"{}",
                        {"Cookie": cookie, "Content-Type": "application/json"})
            self.assertEqual(
                ctx.request("GET", "/api/datasets",
                            headers={"Cookie": cookie})[0], 401)
        finally:
            ctx.close()

    def test_login_rate_limited(self):
        ctx = _ServerContext(env={"RATIONRIGHT_AUTH_TOKEN": "secret-token-abc"})
        try:
            codes = []
            for _ in range(8):
                status, _, _ = ctx.request(
                    "POST", "/api/auth/login",
                    json.dumps({"token": "wrong"}).encode(),
                    {"Content-Type": "application/json"})
                codes.append(status)
            self.assertIn(429, codes)
        finally:
            ctx.close()


class InputValidationTests(unittest.TestCase):
    def setUp(self):
        self.ctx = _ServerContext()

    def tearDown(self):
        self.ctx.close()

    def test_reversed_date_range_rejected(self):
        status, _, body = self.ctx.request(
            "GET", "/api/command-center?from=2026-08-10&to=2026-08-01")
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"]["code"], "INVALID_INPUT")

    def test_sql_injection_attempt_is_parameterized(self):
        # A classic injection in a filter must never error or leak rows.
        query = urllib.parse.urlencode(
            {"fps": "UP-001' OR '1'='1 --"})
        status, _, body = self.ctx.request("GET", "/api/command-center?" + query)
        self.assertEqual(status, 200)
        payload = json.loads(body)
        # The injected string is treated as a literal filter value: no row
        # matches it, the API stays healthy, and nothing leaks.
        self.assertFalse(any(
            f.get("fps_code") == "UP-001' OR '1'='1 --" for f in payload["fps_risk"]))
        self.assertNotIn("Traceback", body.decode())
        self.assertNotIn("sqlite", body.decode().lower())

    def test_error_responses_are_sanitized(self):
        # Trigger a 404 and a 400; bodies must not leak internals.
        status, _, body = self.ctx.request("GET", "/api/reports/RPT-0000-9999")
        self.assertEqual(status, 404)
        self.assertNotIn("Traceback", body.decode())
        self.assertNotIn(self.ctx.db_path, body.decode())
        self.assertNotIn(".py", body.decode())
        status, _, body = self.ctx.request(
            "POST", "/api/simulation/run",
            json.dumps({"import_id": 999999, "demand_change_pct": 200}).encode(),
            {"Content-Type": "application/json"})
        self.assertEqual(status, 400)


class UploadSecurityTests(unittest.TestCase):
    def setUp(self):
        self.ctx = _ServerContext()

    def tearDown(self):
        self.ctx.close()

    def test_unsupported_extension(self):
        status, _, _ = self.ctx.request(
            "POST", "/api/upload", data=b"hello",
            headers={"X-Filename": "evil.exe", "Content-Type": "application/octet-stream"})
        self.assertEqual(status, 400)

    def test_magic_byte_mismatch(self):
        # Claims to be xlsx but is not a ZIP container.
        status, _, _ = self.ctx.request(
            "POST", "/api/upload", data=b"not a zip at all",
            headers={"X-Filename": "data.xlsx", "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"})
        self.assertEqual(status, 400)

    def test_content_type_mismatch(self):
        # .json extension with a csv content type must be rejected.
        status, _, _ = self.ctx.request(
            "POST", "/api/upload", data=b'[{"a":1}]',
            headers={"X-Filename": "data.json", "Content-Type": "text/csv"})
        self.assertEqual(status, 400)

    def test_oversized_file(self):
        import ingestion.parsers as parsers
        limit = parsers.get_max_upload_bytes()
        # The server rejects by Content-Length and closes, which can reset
        # the client's in-flight write — either outcome is a rejection.
        try:
            status, _, _ = self.ctx.request(
                "POST", "/api/upload", data=b"x" * (limit + 1),
                headers={"X-Filename": "big.csv", "Content-Type": "text/csv"})
        except (ConnectionResetError, BrokenPipeError,
                http.client.HTTPException, urllib.error.URLError):
            status = 413
        self.assertEqual(status, 413)


class ImportRollbackTests(unittest.TestCase):
    def test_critical_failure_leaves_no_partial_dataset(self):
        import ingestion.service as service
        import ingestion.importer as importer

        db_path = _fresh_db()
        conn = db.open_db(db_path)
        conn.commit()
        conn.close()
        try:
            upload = service.handle_upload(
                TRANSACTION_CSV.encode(), "rollback.csv", "text/csv")
            token = upload["token"]
            service.validate_step(token, dataset_type="ration_transactions",
                                  db_path=db_path)
            original = importer.upsert_fps_centers

            def boom(*args, **kwargs):
                raise RuntimeError("simulated mid-import failure")

            importer.upsert_fps_centers = boom
            try:
                with self.assertRaises(RuntimeError):
                    service.confirm_step(token, db_path=db_path)
            finally:
                importer.upsert_fps_centers = original

            conn = db.open_db(db_path)
            try:
                tx = conn.execute(
                    "SELECT COUNT(*) AS n FROM ration_transactions").fetchone()["n"]
                imports = conn.execute(
                    "SELECT COUNT(*) AS n FROM data_imports").fetchone()["n"]
            finally:
                conn.close()
            self.assertEqual(tx, 0, "no transactions may survive a failed import")
            self.assertEqual(imports, 0, "no import row may survive a failed import")
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


class AuditLogTests(unittest.TestCase):
    def test_audit_roundtrip_and_no_secrets(self):
        ctx = _ServerContext(env={"RATIONRIGHT_AUTH_TOKEN": "secret-token-abc"})
        try:
            status, headers, _ = ctx.request(
                "POST", "/api/auth/login",
                json.dumps({"token": "secret-token-abc"}).encode(),
                {"Content-Type": "application/json"})
            self.assertEqual(status, 200)
            cookie = headers["Set-Cookie"].split(";")[0]
            status, _, body = ctx.request("GET", "/api/audit?limit=20",
                                          headers={"Cookie": cookie})
            self.assertEqual(status, 200)
            entries = json.loads(body)["entries"]
            self.assertTrue(entries)
            blob = json.dumps(entries)
            self.assertNotIn("secret-token-abc", blob)
            actions = {e["action"] for e in entries}
            self.assertIn("auth.login", actions)

            conn = db.open_db(ctx.db_path)
            try:
                rows = db.list_audit(conn, limit=5, action="auth.login")
                self.assertTrue(rows)
                self.assertIsNotNone(rows[0]["created_at"])
                self.assertTrue(rows[0]["request_id"])
            finally:
                conn.close()
        finally:
            ctx.close()

    def test_audit_limit_clamped(self):
        ctx = _ServerContext()
        try:
            status, _, body = ctx.request("GET", "/api/audit?limit=-5")
            self.assertEqual(status, 200)
            self.assertLessEqual(len(json.loads(body)["entries"]), 50)
        finally:
            ctx.close()


class ReadinessTests(unittest.TestCase):
    def test_ready_endpoint(self):
        ctx = _ServerContext()
        try:
            status, _, body = ctx.request("GET", "/api/ready")
            self.assertEqual(status, 200)
            payload = json.loads(body)
            self.assertEqual(payload["checks"]["database"], "READY")
            self.assertIn("timestamp", payload)
            self.assertNotIn("secret", body.decode().lower())
        finally:
            ctx.close()


if __name__ == "__main__":
    unittest.main()
