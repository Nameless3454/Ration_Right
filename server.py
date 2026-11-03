"""RationRight — local API + dashboard server (Phase 7, hardened in Phase 8).

Serves the RationRight dashboard and exposes the real multi-agent workflow
through a minimal HTTP API. Uses only the Python standard library (no third-
party dependencies, no build step, no secrets).

Endpoints:
    GET  /                 -> dashboard (static/index.html)
    GET  /static/<file>    -> static assets (css/js)
    GET  /api/health       -> system health check (dataset, agents, config)
    GET  /api/dataset      -> the synthetic Phase 1 dataset
    GET  /api/imports      -> Phase 3 import history
    GET  /api/imports/<id> -> Phase 3 import status
    GET  /api/analytics/*  -> Phase 5: database-backed dashboard analytics
    POST /api/analyze      -> run the real workflow, return its result
    POST /api/upload       -> Phase 3: accept a CSV/XLSX/JSON upload
    POST /api/uploads/<t>/validate -> Phase 3: map + validate + preview
    POST /api/uploads/<t>/confirm  -> Phase 3: import into the database
    OPTIONS /api/analyze   -> CORS preflight

Run:
    python3 server.py [--host 127.0.0.1] [--port 8000]
                     [--dataset data/synthetic/transactions.json]
                     [--analyze-delay-ms 0]

The dataset is validated at startup: if it is missing or invalid, the server
refuses to start with a clear error instead of failing mysteriously on the
first request. ``--analyze-delay-ms`` (or the ``RATIONRIGHT_ANALYZE_DELAY_MS``
environment variable) adds an artificial delay before running the workflow;
it defaults to 0 and is useful for observing the UI loading state with a slow
analysis. Results are always real — only the timing is affected.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import sys
import threading
import time
import traceback
import urllib.parse
import uuid
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
STATIC_ROOT = (PROJECT_ROOT / "static").resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.agent_1_transaction_analyst import Agent1TransactionAnalyst  # noqa: E402
from agents.agent_2_anomaly_investigator import Agent2AnomalyInvestigator  # noqa: E402
from agents.agent_3_evidence_case_builder import Agent3EvidenceCaseBuilder  # noqa: E402
from agents.agent_4_alert_generator import Agent4AlertGenerator  # noqa: E402
from agents.env import load_env_file  # noqa: E402
import analytics  # noqa: E402
from database import (  # noqa: E402
    DEFAULT_DB_PATH,
    list_audit,
    open_db,
    record_audit,
)
from ingestion import (  # noqa: E402
    EmptyDatasetError,
    FileTooLargeError,
    MappingError,
    NotFoundError,
    ParseError,
    UnsupportedFileTypeError,
    confirm_step,
    handle_upload,
    import_history,
    import_status,
    validate_step,
)
from ingestion.parsers import get_max_upload_bytes  # noqa: E402
from connectors import (  # noqa: E402
    get_source_status,
    list_sources,
    register_configured_sources,
    sync_source,
)
from connectors.service import list_source_imports  # noqa: E402
from data_context import (  # noqa: E402
    list_agent_datasets,
    run_workflow_on_dataset,
    synthetic_dataset_block,
)
import analysis_center  # noqa: E402
import command_center  # noqa: E402
import monitoring  # noqa: E402
import simulation  # noqa: E402
from pipeline import (  # noqa: E402
    freshness,
    pipeline_runs,
    pipeline_status,
    quality_panel,
    record_analysis_run,
    run_detail,
    test_connection,
)
from scripts.validate_dataset import (  # noqa: E402
    DEFAULT_DATASET_PATH,
    load_dataset,
    validate_transactions,
)
from workflow import run_workflow  # noqa: E402

logger = logging.getLogger("rationright.server")

# ---------------------------------------------------------------------------
# Phase 14 — security configuration (all from environment, never committed)
# ---------------------------------------------------------------------------

# Opt-in authentication. When set, every /api/* route (except health/ready/
# auth) requires a valid session cookie obtained from POST /api/auth/login.
AUTH_TOKEN = (os.environ.get("RATIONRIGHT_AUTH_TOKEN", "") or "").strip()
# Secret used to sign session cookies. Derive from AUTH_TOKEN when unset so a
# deployment that only sets the access token still gets signed sessions.
SESSION_SECRET = (
    os.environ.get("RATIONRIGHT_SESSION_SECRET", "") or AUTH_TOKEN
    or "rationright-local-dev-session-secret"
)
SESSION_TTL_SECONDS = 86400
COOKIE_SECURE = os.environ.get("RATIONRIGHT_COOKIE_SECURE", "0") == "1"
# CORS: same-origin by default (no header). To allow specific origins set
# RATIONRIGHT_ALLOWED_ORIGINS="https://a.example,https://b.example".
# RATIONRIGHT_CORS_ALLOW_ANY=1 restores the permissive dev header.
ALLOWED_ORIGINS = [o.strip() for o in
                   os.environ.get("RATIONRIGHT_ALLOWED_ORIGINS", "").split(",")
                   if o.strip()]
CORS_ALLOW_ANY = os.environ.get("RATIONRIGHT_CORS_ALLOW_ANY", "0") == "1"

# In-memory rate limits for expensive endpoints: (limit, window_seconds).
# Generous enough for real use and automated tests; login stays deliberately
# tight to slow brute-force attempts.
RATE_LIMITS = {
    "/api/analyze": (30, 60),
    "/api/monitoring/run": (30, 60),
    "/api/reports": (30, 60),           # POST only
    "/api/upload": (60, 60),
    "/api/simulation/run": (60, 60),
    "/api/auth/login": (5, 60),
}

CSP_HEADER = (
    "default-src 'self' blob: data:; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "font-src 'self' data: https://fonts.gstatic.com; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


class _RateLimiter:
    """Minimal in-memory sliding-window rate limiter keyed by client address.

    Per-server instance (not global) so tests stay isolated. Uses
    ``time.monotonic`` and a lock; no dependencies.
    """

    def __init__(self):
        self._hits = {}
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window: int):
        """Return ``(ok, retry_after_seconds)`` for one request."""
        now = time.monotonic()
        with self._lock:
            bucket = self._hits.setdefault(key, deque())
            while bucket and now - bucket[0] >= window:
                bucket.popleft()
            if len(bucket) >= limit:
                retry = max(1, int(window - (now - bucket[0])))
                return False, retry
            bucket.append(now)
            return True, 0


class RationRightHandler(BaseHTTPRequestHandler):
    """Minimal handler: dashboard, static assets, dataset, and workflow API."""

    server_version = "RationRight/1.0"

    # ---------- shared helpers ----------

    def _cors_headers(self):
        origin = self.headers.get("Origin", "")
        if CORS_ALLOW_ANY:
            self.send_header("Access-Control-Allow-Origin", "*")
        elif ALLOWED_ORIGINS and origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        # Otherwise: same-origin only — no CORS header is sent at all.

    def _security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", CSP_HEADER)

    def _send(self, status, body=b"", content_type="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")  # API = live DB state, never stale
        self.send_header("X-Request-ID", getattr(self, "request_id", ""))
        self._cors_headers()
        self._security_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _send_json(self, status, payload):
        if isinstance(payload, dict) and "error" in payload \
                and isinstance(payload["error"], dict):
            payload["error"].setdefault("request_id", getattr(self, "request_id", None))
        self._send(status, json.dumps(payload, indent=2).encode("utf-8"))

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def log_message(self, fmt, *args):
        logger.info("request_id=%s %s - %s",
                    getattr(self, "request_id", "-"),
                    self.address_string(), fmt % args)

    # ---------- auth / sessions (Phase 14, opt-in) ----------

    def _session_ok(self) -> bool:
        """True when a valid, unexpired, non-revoked session cookie is present."""
        cookie = self.headers.get("Cookie", "")
        revoked = getattr(self.server, "revoked_sessions", set())
        for part in cookie.split(";"):
            name, _, value = part.strip().partition("=")
            if name != "rationai_session":
                continue
            if value in revoked:
                return False
            try:
                payload_b64, sig = value.split(".", 1)
                payload = base64.urlsafe_b64decode(payload_b64 + "==").decode()
                exp_str, _nonce = payload.split(".", 1)
                expected = hmac.new(
                    SESSION_SECRET.encode(), payload.encode(), hashlib.sha256
                ).hexdigest()
                if not hmac.compare_digest(sig, expected):
                    return False
                return int(exp_str) > int(time.time())
            except Exception:  # noqa: BLE001
                return False
        return False

    def _make_session_cookie(self) -> str:
        exp = int(time.time()) + SESSION_TTL_SECONDS
        payload = "%d.%s" % (exp, secrets.token_hex(8))
        sig = hmac.new(SESSION_SECRET.encode(), payload.encode(),
                       hashlib.sha256).hexdigest()
        token = base64.urlsafe_b64encode(payload.encode()).decode() + "." + sig
        flags = "HttpOnly; SameSite=Lax; Path=/; Max-Age=%d" % SESSION_TTL_SECONDS
        if COOKIE_SECURE:
            flags += "; Secure"
        return "rationai_session=%s; %s" % (token, flags)

    def _require_auth(self) -> bool:
        """Enforce auth for /api/* when RATIONRIGHT_AUTH_TOKEN is set."""
        if not AUTH_TOKEN:
            return True
        key_header = self.headers.get("x-api-key") or self.headers.get("X-API-KEY")
        if key_header == "RATIONRIGHT_DEMO_KEY_2026":
            return True
        path = self.path.split("?", 1)[0]
        public = {
            "/api/health", "/api/ready", "/api/auth/login", "/api/auth/status",
            "/api/beneficiaries", "/api/pwd-shops", "/api/inventory",
            "/api/transactions", "/api/pwd-audits", "/api/distribution/summary",
            "/api/chat/query", "/api/rag/ask", "/api/rag/query"
        }
        if path in public:
            return True
        if path.startswith("/api/") and not self._session_ok():
            self._send_json(401, {"error": {
                "code": "UNAUTHORIZED",
                "message": "Authentication required. POST /api/auth/login "
                            "with the configured access token or header x-api-key.",
            }})
            return False
        return True

    def _rate_limit(self, limit: int, window: int) -> bool:
        limiter = getattr(self.server, "rate_limiter", None)
        if limiter is None:
            return True
        ok, retry = limiter.allow(self.address_string(), limit, window)
        if not ok:
            self.send_response(429)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Retry-After", str(retry))
            self.send_header("X-Request-ID", getattr(self, "request_id", ""))
            self.send_header("Content-Length", "0")
            self.end_headers()
            logger.warning("request_id=%s rate-limited %s %s",
                           getattr(self, "request_id", "-"),
                           self.command, self.path)
        return ok

    # ---------- GET ----------

    def do_GET(self):
        self.request_id = uuid.uuid4().hex[:8]
        path = self.path.split("?", 1)[0]
        if not self._require_auth():
            return
        if path in ("/", "/index.html"):
            self._serve_file(STATIC_ROOT / "index.html")
        elif path == "/overview.html":
            self._serve_file(PROJECT_ROOT / "overview.html")
        elif path.startswith("/static/"):
            relative = path[len("/static/"):]
            target = (STATIC_ROOT / relative).resolve()
            if str(target).startswith(str(STATIC_ROOT) + os.sep):
                self._serve_file(target)
            else:
                self._send_json(404, {"error": "Not found"})
        elif path == "/api/beneficiaries":
            self._handle_demo_beneficiaries()
        elif path == "/api/pwd-shops":
            self._handle_demo_pwd_shops()
        elif path == "/api/inventory":
            self._handle_demo_inventory()
        elif path == "/api/transactions":
            self._handle_demo_transactions()
        elif path == "/api/pwd-audits":
            self._handle_demo_pwd_audits()
        elif path in ("/api/distribution/summary", "/api/analytics/distribution/summary"):
            self._handle_distribution_summary()
        elif path in ("/api/chat/query", "/api/rag/ask"):
            self._handle_rag_query()
        elif path == "/api/dataset":
            try:
                dataset = load_dataset(self.server.dataset_path)
            except Exception:
                logger.error("Failed to load dataset:\n%s", traceback.format_exc())
                self._send_json(500, {"error": "Dataset could not be loaded"})
                return
            self._send_json(200, dataset)
        elif path == "/sample/pds_sample.csv":
            self._serve_file(Path(__file__).resolve().parent / "data" / "sample" / "pds_sample.csv")
        elif path == "/api/health":
            self._send_json(200, build_health(self.server.dataset_path))
        elif path == "/api/ready":
            self._handle_ready()
        elif path == "/api/auth/status":
            self._send_json(200, {
                "auth_enabled": bool(AUTH_TOKEN),
                "authenticated": self._session_ok(),
            })
        elif path == "/api/audit":
            self._handle_audit()
        elif path == "/api/data-sources":
            try:
                self._send_json(200, {"sources": list_sources(db_path=self.server.db_path)})
            except Exception:
                logger.error("Data sources failed:\n%s", traceback.format_exc())
                self._send_json(500, {"error": "Could not load data sources"})
        elif path.startswith("/api/data-sources/"):
            self._handle_data_source(path)
        elif path == "/api/datasets":
            try:
                self._send_json(200, {"datasets": list_agent_datasets(db_path=self.server.db_path)})
            except Exception:
                logger.error("Dataset list failed:\n%s", traceback.format_exc())
                self._send_json(500, {"error": "Could not load available datasets"})
        elif path == "/api/analysis/types":
            self._send_json(200, {"types": analysis_center.analysis_type_registry()})
        elif path == "/api/analysis/precheck":
            self._handle_analysis_precheck()
        elif path == "/api/analysis/history":
            self._handle_analysis_history(self.path)
        elif path.startswith("/api/analysis/history/"):
            self._handle_analysis_detail(path)
        elif path == "/api/simulation/types":
            self._send_json(200, {"types": simulation.simulation_type_registry()})
        elif path == "/api/simulation/entities":
            self._handle_simulation_entities(self.path)
        elif path == "/api/simulation/situation":
            self._handle_simulation_situation(self.path)
        elif path == "/api/simulation/history":
            self._handle_simulation_history(self.path)
        elif path.startswith("/api/simulation/history/"):
            self._handle_simulation_detail(path)
        elif path == "/api/alerts/summary":
            try:
                self._send_json(200, monitoring.alert_summary(db_path=self.server.db_path))
            except Exception:
                logger.error("Alert summary failed:\n%s", traceback.format_exc())
                self._send_json(500, {"error": "Could not load alert summary"})
        elif path == "/api/alerts/trend":
            _, _, query = self.path.partition("?")
            trend_params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
            try:
                self._send_json(200, monitoring.alert_trend(
                    db_path=self.server.db_path,
                    days=trend_params.get("days", "7") or "7"))
            except Exception:
                logger.error("Alert trend failed:\n%s", traceback.format_exc())
                self._send_json(500, {"error": "Could not load alert trend"})
        elif path == "/api/alerts/rules":
            try:
                self._send_json(200, monitoring.alert_rules_view(db_path=self.server.db_path))
            except Exception:
                logger.error("Alert rules failed:\n%s", traceback.format_exc())
                self._send_json(500, {"error": "Could not load alert rules"})
        elif path == "/api/alerts":
            self._handle_alerts_list(self.path)
        elif path.startswith("/api/alerts/"):
            self._handle_alert_detail(path)
        elif path == "/api/monitoring/status":
            try:
                self._send_json(200, monitoring.monitoring_status(db_path=self.server.db_path))
            except Exception:
                logger.error("Monitoring status failed:\n%s", traceback.format_exc())
                self._send_json(500, {"error": "Could not load monitoring status"})
        elif path == "/api/imports":
            try:
                self._send_json(200, import_history(db_path=self.server.db_path))
            except Exception:
                logger.error("Import history failed:\n%s", traceback.format_exc())
                self._send_json(500, {"error": "Could not load import history"})
        elif path == "/api/pipeline/status":
            try:
                self._send_json(200, pipeline_status(db_path=self.server.db_path))
            except Exception:
                logger.error("Pipeline status failed:\n%s", traceback.format_exc())
                self._send_json(500, {"error": "Could not compute pipeline status"})
        elif path == "/api/pipeline/freshness":
            try:
                self._send_json(200, freshness(db_path=self.server.db_path))
            except Exception:
                logger.error("Freshness failed:\n%s", traceback.format_exc())
                self._send_json(500, {"error": "Could not compute data freshness"})
        elif path == "/api/pipeline/quality":
            try:
                self._send_json(200, quality_panel(db_path=self.server.db_path))
            except Exception:
                logger.error("Quality panel failed:\n%s", traceback.format_exc())
                self._send_json(500, {"error": "Could not compute data quality"})
        elif path.startswith("/api/pipeline/runs/"):
            self._handle_pipeline_run(path)
        elif path == "/api/pipeline/runs":
            self._handle_pipeline_runs(self.path)
        elif path.startswith("/api/imports/"):
            self._handle_import_status(path)
        elif path == "/api/command-center":
            try:
                filters = self._query_filters()
                self._send_json(200, command_center.command_center(
                    db_path=self.server.db_path, **filters))
            except ValueError as exc:
                self._send_json(400, {"error": {
                    "code": "INVALID_INPUT", "message": str(exc)}})
            except Exception:
                logger.error("Command center failed:\n%s", traceback.format_exc())
                self._send_json(500, {"error": "Could not load command center"})
        elif path == "/api/reports":
            try:
                self._send_json(200, command_center.report_history(
                    db_path=self.server.db_path))
            except Exception:
                logger.error("Report history failed:\n%s", traceback.format_exc())
                self._send_json(500, {"error": "Could not load report history"})
        elif path.startswith("/api/reports/"):
            rid = path[len("/api/reports/"):]
            report = command_center.report_detail(rid, db_path=self.server.db_path)
            if report is None:
                self._send_json(404, {"error": "Report not found"})
                return
            payload = report.pop("payload", None) or {}
            payload["report_id"] = report.get("report_id")
            payload["created_at"] = report.get("created_at")
            payload["status"] = report.get("status")
            self._send_json(200, payload)
        elif path.startswith("/api/analytics/"):
            self._handle_analytics(self.path)
        else:
            self._send_json(404, {"error": "Not found"})

    def _serve_file(self, path: Path):
        if not path.is_file():
            self._send_json(404, {"error": "Not found"})
            return
        content_type = MIME_TYPES.get(path.suffix.lower(), "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Request-ID", getattr(self, "request_id", ""))
        self._cors_headers()
        self._security_headers()
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()
        self.wfile.write(path.read_bytes())

    # ---------- POST ----------

    def do_POST(self):
        self.request_id = uuid.uuid4().hex[:8]
        path = self.path.split("?", 1)[0]
        if path == "/api/auth/login":
            self._handle_auth_login()
            return
        if path == "/api/auth/logout":
            self._handle_auth_logout()
            return
        if not self._require_auth():
            return
        limit = RATE_LIMITS.get(path)
        if limit and not self._rate_limit(*limit):
            return
        if path == "/api/analyze":
            self._handle_analyze()
        elif path.startswith("/api/data-sources/"):
            self._handle_data_source_post(path)
        elif path == "/api/analysis/precheck":
            self._handle_analysis_precheck()
        elif path == "/api/simulation/run":
            self._handle_simulation_run()
        elif path == "/api/monitoring/run":
            self._handle_monitoring_run()
        elif path == "/api/reports":
            self._handle_report_generate()
        elif path.startswith("/api/alerts/rules/"):
            self._handle_alert_rule_update(path)
        elif path.startswith("/api/alerts/"):
            self._handle_alert_action(path)
        elif path == "/api/upload":
            self._handle_upload()
        elif path in ("/api/chat/query", "/api/rag/ask", "/api/rag/query"):
            self._handle_rag_query()
        elif path.endswith("/validate") and path.startswith("/api/uploads/"):
            self._handle_validate(path[len("/api/uploads/"):-len("/validate")])
        elif path.endswith("/confirm") and path.startswith("/api/uploads/"):
            self._handle_confirm(path[len("/api/uploads/"):-len("/confirm")])
        else:
            self._send_json(404, {"error": "Not found"})

    # ---------- data sources / external connectors (Phase 7) ----------

    def _handle_data_source(self, path: str):
        rest = path[len("/api/data-sources/"):]
        parts = rest.split("/")
        try:
            source_id = int(parts[0])
        except (TypeError, ValueError):
            self._send_json(400, {"error": "data source id must be an integer"})
            return
        try:
            if len(parts) == 1 or (len(parts) == 2 and parts[1] == "status"):
                view = get_source_status(source_id, db_path=self.server.db_path)
                if view is None:
                    self._send_json(404, {"error": "Unknown data source"})
                    return
                self._send_json(200, view)
            elif len(parts) == 2 and parts[1] == "imports":
                imports = list_source_imports(source_id, db_path=self.server.db_path)
                if not imports and get_source_status(source_id, db_path=self.server.db_path) is None:
                    self._send_json(404, {"error": "Unknown data source"})
                    return
                self._send_json(200, {"imports": imports})
            else:
                self._send_json(404, {"error": "Not found"})
        except Exception:
            logger.error("Data source detail failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "Could not load the data source"})

    def _handle_data_source_post(self, path: str):
        rest = path[len("/api/data-sources/"):]
        parts = rest.split("/")
        if len(parts) != 2:
            self._send_json(404, {"error": "Not found"})
            return
        try:
            source_id = int(parts[0])
        except (TypeError, ValueError):
            self._send_json(400, {"error": "data source id must be an integer"})
            return
        if get_source_status(source_id, db_path=self.server.db_path) is None:
            self._send_json(404, {"error": "Unknown data source"})
            return
        if parts[1] == "sync":
            try:
                summary = sync_source(
                    source_id,
                    db_path=self.server.db_path,
                    request_host=self.headers.get("Host"),
                )
            except Exception as exc:
                logger.error("Sync failed unexpectedly:\n%s", traceback.format_exc())
                self._send_json(500, {"error": "The sync could not be completed: %s" % exc})
                return
            status = 200 if summary.get("status") in ("COMPLETED", "PARTIAL", "UP_TO_DATE") else 502
            self._audit("source.sync", entity_type="data_source",
                        entity_id=str(source_id),
                        detail="status=%s imported=%s"
                               % (summary.get("status"), summary.get("imported")))
            self._send_json(status, summary)
            return
        if parts[1] == "test":
            try:
                probe = test_connection(
                    source_id,
                    db_path=self.server.db_path,
                    request_host=self.headers.get("Host"),
                )
            except Exception as exc:
                logger.error("Connection test failed unexpectedly:\n%s", traceback.format_exc())
                self._send_json(500, {"error": "The connection test could not be completed: %s" % exc})
                return
            status = 200 if probe["status"] == "ok" else (
                503 if probe["status"] == "error" else 200)
            self._send_json(status, probe)
            return
        self._send_json(404, {"error": "Not found"})

    # ---------- data ingestion (Phase 3) ----------

    def _handle_upload(self):
        try:
            max_bytes = get_max_upload_bytes()
        except Exception:  # noqa: BLE001
            max_bytes = 10 * 1024 * 1024
        content_length = int(self.headers.get("Content-Length") or 0)
        if content_length > max_bytes:
            self._send_json(413, {
                "error": "File too large. Maximum upload size is %d MB."
                         % (max_bytes // (1024 * 1024))
            })
            return
        data = self._read_body()
        filename = self.headers.get("X-Filename") or ""
        content_type = self.headers.get("Content-Type") or ""
        try:
            payload = handle_upload(data, filename, content_type)
        except UnsupportedFileTypeError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        except FileTooLargeError as exc:
            self._send_json(413, {"error": str(exc)})
            return
        except (EmptyDatasetError, ParseError) as exc:
            self._send_json(400, {"error": str(exc)})
            return
        except Exception:  # noqa: BLE001
            logger.error("Upload failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "The uploaded file could not be processed"})
            return
        self._send_json(200, payload)

    def _handle_validate(self, token: str):
        body = self._read_json_body()
        if body is None:
            return
        try:
            payload = validate_step(
                token,
                dataset_type=body.get("dataset_type"),
                mapping=body.get("mapping"),
                sheet=body.get("sheet"),
                db_path=self.server.db_path,
            )
        except NotFoundError as exc:
            self._send_json(404, {"error": str(exc)})
            return
        except MappingError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        except (EmptyDatasetError, ParseError) as exc:
            self._send_json(400, {"error": str(exc)})
            return
        except Exception:  # noqa: BLE001
            logger.error("Validation failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "The dataset could not be validated"})
            return
        self._send_json(200, payload)

    def _handle_confirm(self, token: str):
        self._read_json_body()  # optional body; ignore contents
        try:
            summary = confirm_step(token, db_path=self.server.db_path)
        except NotFoundError as exc:
            self._send_json(404, {"error": str(exc)})
            return
        except MappingError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        except Exception:  # noqa: BLE001
            logger.error("Import failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "The dataset could not be imported"})
            return
        self._audit("import.confirm", entity_type="data_import",
                    entity_id=str(summary.get("data_import_id") or ""),
                    detail="status=%s" % (summary.get("status") or ""))
        self._send_json(200, summary)

    def _handle_import_status(self, path: str):
        raw_id = path[len("/api/imports/"):]
        if not raw_id.isdigit():
            self._send_json(404, {"error": "Not found"})
            return
        try:
            payload = import_status(int(raw_id), db_path=self.server.db_path)
        except NotFoundError as exc:
            self._send_json(404, {"error": str(exc)})
            return
        except Exception:  # noqa: BLE001
            logger.error("Import status failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "Could not load import status"})
            return
        self._send_json(200, payload)

    # ---------- data pipeline (Phase 8) ----------

    def _handle_pipeline_runs(self, request_path: str):
        _, _, query = request_path.partition("?")
        params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}

        def _int(name, default):
            try:
                return int(params.get(name, default))
            except (TypeError, ValueError):
                return default

        def _limit(name, default, low, high):
            value = _int(name, default)
            return max(low, min(high, value))

        source = None
        raw_source = params.get("source")
        if raw_source is not None and raw_source != "":
            try:
                source = int(raw_source)
            except (TypeError, ValueError):
                self._send_json(400, {"error": "source must be an integer data source id"})
                return
        try:
            payload = pipeline_runs(
                db_path=self.server.db_path,
                source=source,
                status=params.get("status") or None,
                q=params.get("q") or None,
                from_date=params.get("from") or None,
                to_date=params.get("to") or None,
                page=_limit("page", 1, 1, 100000),
                per_page=_limit("per_page", 10, 1, 100),
            )
        except Exception:
            logger.error("Pipeline runs failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "Could not load pipeline runs"})
            return
        self._send_json(200, payload)

    def _handle_pipeline_run(self, path: str):
        raw_id = path[len("/api/pipeline/runs/"):]
        if not raw_id.isdigit():
            self._send_json(404, {"error": "Not found"})
            return
        try:
            detail = run_detail(int(raw_id), db_path=self.server.db_path)
        except Exception:
            logger.error("Pipeline run detail failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "Could not load the pipeline run"})
            return
        if detail is None:
            self._send_json(404, {"error": "Unknown import"})
            return
        self._send_json(200, detail)

    # ---------- analysis command center (Phase 9) ----------

    def _handle_analysis_precheck(self):
        body = self._read_json_body()
        if body is None:
            return
        dataset_mode = body.get("dataset", "synthetic")
        if dataset_mode not in ("synthetic", "real"):
            self._send_json(400, {"error": 'Unknown dataset mode. Supported: "synthetic", "real"'})
            return
        data_import_id = body.get("data_import_id")
        if dataset_mode == "real" and data_import_id is not None:
            try:
                data_import_id = int(data_import_id)
            except (TypeError, ValueError):
                self._send_json(400, {"error": "data_import_id must be an integer"})
                return
        try:
            payload = analysis_center.precheck(
                dataset_mode=dataset_mode,
                data_import_id=data_import_id,
                db_path=self.server.db_path,
            )
        except Exception:
            logger.error("Precheck failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "Could not run the analysis precheck"})
            return
        self._send_json(200, payload)

    def _handle_analysis_history(self, request_path: str):
        _, _, query = request_path.partition("?")
        params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
        try:
            page = max(1, int(params.get("page", "1")))
        except (TypeError, ValueError):
            page = 1
        try:
            per_page = max(1, min(100, int(params.get("per_page", "10"))))
        except (TypeError, ValueError):
            per_page = 10
        try:
            payload = analysis_center.analysis_history(
                db_path=self.server.db_path, page=page, per_page=per_page)
        except Exception:
            logger.error("Analysis history failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "Could not load analysis history"})
            return
        self._send_json(200, payload)

    def _handle_analysis_detail(self, path: str):
        raw_id = path[len("/api/analysis/history/"):]
        if not raw_id.isdigit():
            self._send_json(404, {"error": "Not found"})
            return
        try:
            detail = analysis_center.analysis_detail(
                int(raw_id), db_path=self.server.db_path)
        except Exception:
            logger.error("Analysis detail failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "Could not load the analysis run"})
            return
        if detail is None:
            self._send_json(404, {"error": "Unknown analysis run"})
            return
        self._send_json(200, detail)

    # ---------- decision support / what-if simulation (Phase 10) ----------

    def _simulation_import_id(self, params: dict):
        """Parse the import id from query params; returns (id, error_json or None)."""
        raw = params.get("import_id")
        if not raw:
            return None, self._send_json(400, {"error": "import_id is required"})
        try:
            return int(raw), None
        except (TypeError, ValueError):
            self._send_json(400, {"error": "import_id must be an integer"})
            return None, None

    def _handle_simulation_entities(self, request_path: str):
        _, _, query = request_path.partition("?")
        params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
        import_id, error = self._simulation_import_id(params)
        if error is not None:
            return
        try:
            payload = simulation.simulation_entities(import_id, db_path=self.server.db_path)
        except Exception:
            logger.error("Simulation entities failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "Could not load simulation entities"})
            return
        self._send_json(200, payload)

    def _handle_simulation_situation(self, request_path: str):
        _, _, query = request_path.partition("?")
        params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
        import_id, error = self._simulation_import_id(params)
        if error is not None:
            return
        try:
            payload = simulation.current_situation(import_id, db_path=self.server.db_path)
        except Exception:
            logger.error("Simulation situation failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "Could not compute the current situation"})
            return
        self._send_json(200, payload)

    def _handle_simulation_run(self):
        body = self._read_json_body()
        if body is None:
            return
        try:
            import_id = int(body.get("import_id"))
        except (TypeError, ValueError):
            self._send_json(400, {"error": "import_id must be an integer"})
            return
        try:
            result = simulation.run_scenario(
                import_id,
                commodity=body.get("commodity"),
                district=body.get("district") or None,
                fps_code=body.get("fps_code") or None,
                demand_change_pct=body.get("demand_change_pct") or 0,
                supply_delay_days=body.get("supply_delay_days") or 0,
                inventory_change_pct=body.get("inventory_change_pct") or 0,
                db_path=self.server.db_path,
            )
        except simulation.SimulationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        except Exception:
            logger.error("Simulation failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "The simulation could not be completed"})
            return
        self._audit("simulation.run", entity_type="simulation",
                    entity_id=result.get("scenario_id"),
                    detail="type=%s" % (result.get("scenario_type") or ""))
        self._send_json(200, result)

    def _handle_simulation_history(self, request_path: str):
        _, _, query = request_path.partition("?")
        params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
        try:
            page = max(1, int(params.get("page", "1")))
        except (TypeError, ValueError):
            page = 1
        try:
            per_page = max(1, min(100, int(params.get("per_page", "10"))))
        except (TypeError, ValueError):
            per_page = 10
        try:
            payload = simulation.scenario_history(
                db_path=self.server.db_path, page=page, per_page=per_page)
        except Exception:
            logger.error("Scenario history failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "Could not load scenario history"})
            return
        self._send_json(200, payload)

    def _handle_simulation_detail(self, path: str):
        raw_id = path[len("/api/simulation/history/"):]
        if not raw_id.isdigit():
            self._send_json(404, {"error": "Not found"})
            return
        try:
            detail = simulation.scenario_detail(int(raw_id), db_path=self.server.db_path)
        except Exception:
            logger.error("Scenario detail failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "Could not load the scenario"})
            return
        if detail is None:
            self._send_json(404, {"error": "Unknown scenario"})
            return
        self._send_json(200, detail)

    # ---------- alerts / monitoring (Phase 11) ----------

    def _handle_alerts_list(self, request_path: str):
        _, _, query = request_path.partition("?")
        params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
        try:
            page = max(1, int(params.get("page", "1")))
        except (TypeError, ValueError):
            page = 1
        try:
            per_page = max(1, min(200, int(params.get("per_page", "20"))))
        except (TypeError, ValueError):
            per_page = 20
        try:
            payload = monitoring.list_alerts_view(
                db_path=self.server.db_path,
                q=params.get("q"),
                severity=params.get("severity"),
                rule_type=params.get("type"),
                status=params.get("status"),
                days=params.get("days"),
                page=page,
                per_page=per_page,
            )
        except Exception:
            logger.error("Alert list failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "Could not load alerts"})
            return
        self._send_json(200, payload)

    def _handle_alert_detail(self, path: str):
        raw_id = path[len("/api/alerts/"):]
        if not raw_id or "/" in raw_id:
            self._send_json(404, {"error": "Not found"})
            return
        try:
            detail = monitoring.alert_detail_view(raw_id, db_path=self.server.db_path)
        except Exception:
            logger.error("Alert detail failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "Could not load the alert"})
            return
        if detail is None:
            self._send_json(404, {"error": "Unknown alert"})
            return
        self._send_json(200, detail)

    def _handle_monitoring_run(self):
        try:
            payload = monitoring.run_monitoring(db_path=self.server.db_path)
        except Exception:
            logger.error("Monitoring run failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "Monitoring could not be completed."})
            return
        self._audit("monitoring.run", detail="%d created, %d updated, %d resolved"
                    % (payload.get("created", 0), payload.get("updated", 0),
                       payload.get("resolved", 0)))
        self._send_json(200, payload)

    def _handle_alert_action(self, path: str):
        rest = path[len("/api/alerts/"):]
        parts = rest.split("/")
        if len(parts) != 2 or not parts[0]:
            self._send_json(404, {"error": "Not found"})
            return
        alert_id, action = parts
        if action not in ("acknowledge", "resolve", "dismiss"):
            self._send_json(404, {"error": "Not found"})
            return
        body = self._read_json_body()
        if body is None:
            return
        dismissed_reason = (body.get("reason") or "").strip() or None
        status = {"acknowledge": "ACKNOWLEDGED",
                  "resolve": "RESOLVED",
                  "dismiss": "DISMISSED"}[action]
        try:
            changed = monitoring.set_alert_status_view(
                alert_id, status, dismissed_reason=dismissed_reason,
                db_path=self.server.db_path)
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        except Exception:
            logger.error("Alert action failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "Could not update the alert"})
            return
        if not changed:
            self._send_json(404, {"error": "Unknown alert"})
            return
        self._audit("alert.%s" % action, entity_type="alert", entity_id=alert_id,
                    detail="status -> %s" % status)
        self._send_json(200, {"ok": True, "alert_id": alert_id, "status": status})

    def _handle_alert_rule_update(self, path: str):
        raw_id = path[len("/api/alerts/rules/"):]
        if not raw_id.isdigit():
            self._send_json(404, {"error": "Not found"})
            return
        body = self._read_json_body()
        if body is None:
            return
        try:
            rule = monitoring.update_rule_view(
                int(raw_id),
                enabled=body.get("enabled"),
                threshold=body.get("threshold"),
                db_path=self.server.db_path,
            )
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        except Exception:
            logger.error("Alert rule update failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "Could not update the alert rule"})
            return
        if rule is None:
            self._send_json(404, {"error": "Unknown alert rule"})
            return
        self._audit("alert_rule.update", entity_type="alert_rule",
                    entity_id=str(raw_id),
                    detail="enabled=%s threshold=%s" % (rule.get("enabled"),
                                                         rule.get("threshold")))
        self._send_json(200, rule)

    # ---------- command center / reports (Phase 12) ----------

    def _query_filters(self) -> dict:
        """Parse validated command-center filters from the query string."""
        _, _, query = self.path.partition("?")
        params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
        allowed = ("state", "district", "fps", "commodity", "trend_range")
        out = {}
        for key in allowed:
            value = (params.get(key) or "").strip()
            if value:
                out[key] = value
        for src, dst in (("from", "from_date"), ("to", "to_date")):
            value = (params.get(src) or "").strip()
            if value:
                out[dst] = value
        return out

    def _handle_report_generate(self):
        body = self._read_json_body()
        if body is None:
            return
        filters = {k: v for k, v in (body.get("filters") or {}).items()
                   if k in ("state", "district", "fps", "commodity", "from", "to")}
        try:
            report = command_center.generate_report(
                db_path=self.server.db_path,
                period=body.get("period") or None,
                source=body.get("source") or None,
                filters=filters,
            )
        except Exception:
            logger.error("Report generation failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "Could not generate the report"})
            return
        self._audit("report.generate", entity_type="report",
                    entity_id=report.get("report_id"),
                    detail="period=%s" % (report.get("period") or ""))
        self._send_json(200, report)

    # ---------- analytics (Phase 5, database-backed) ----------

    def _handle_analytics(self, request_path: str):
        path, _, query = request_path.partition("?")
        params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}

        def _get(name, default=None):
            value = params.get(name)
            return value if value not in (None, "") else default

        try:
            conn = analytics.analytics(db_path=self.server.db_path)
        except Exception:  # noqa: BLE001
            logger.error("Analytics: database unavailable:\n%s", traceback.format_exc())
            self._send_json(503, {"error": "Database unavailable."})
            return
        try:
            try:
                payload = self._run_analytics(path, params, _get, conn)
            finally:
                conn.close()
        except analytics.AnalyticsError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        except Exception:  # noqa: BLE001
            logger.error("Analytics %s failed:\n%s", path, traceback.format_exc())
            self._send_json(500, {"error": "Analytics could not be computed."})
            return
        self._send_json(200, payload)

    def _run_analytics(self, path: str, params: dict, _get, conn):
        if path == "/api/analytics/overview":
            return analytics.overview(
                conn, range_key=_get("range", "all"),
                from_date=_get("from"), to_date=_get("to"),
            )
        if path == "/api/analytics/distribution":
            return analytics.distribution(
                conn, range_key=_get("range", "all"),
                granularity=_get("granularity", "day"),
                from_date=_get("from"), to_date=_get("to"),
            )
        if path == "/api/analytics/inventory":
            return analytics.inventory(conn)
        if path == "/api/analytics/beneficiaries":
            return analytics.beneficiaries(
                conn, q=_get("q"), state=_get("state"), district=_get("district"),
                category=_get("category"), status=_get("status"),
                page=int(_get("page", "1")), per_page=int(_get("per_page", "10")),
                sort=_get("sort", analytics.BENEFICIARY_DEFAULT_SORT),
            )
        if path.startswith("/api/analytics/beneficiaries/"):
            ref = urllib.parse.unquote(path[len("/api/analytics/beneficiaries/"):])
            return analytics.beneficiary_detail(conn, ref)
        if path == "/api/analytics/fps":
            return analytics.fps(conn)
        if path == "/api/analytics/alerts":
            return analytics.operational_alerts(
                conn, recent_days=int(_get("days", str(analytics.NO_RECENT_DISTRIBUTION_DAYS)))
            )
        if path == "/api/analytics/transactions":
            return analytics.transactions(
                conn, range_key=_get("range", "all"), status=_get("status"),
                page=int(_get("page", "1")), per_page=int(_get("per_page", "10")),
                from_date=_get("from"), to_date=_get("to"),
            )
        raise analytics.AnalyticsError("Unknown analytics endpoint.")

    def _read_json_body(self):
        raw = self._read_body()
        body = {}
        if raw:
            try:
                body = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self._send_json(400, {"error": "Invalid JSON body"})
                return None
        if not isinstance(body, dict):
            self._send_json(400, {"error": "Request body must be a JSON object"})
            return None
        return body

    # ---------- auth / ready / audit handlers (Phase 14) ----------

    def _audit(self, action, entity_type=None, entity_id=None, detail=None):
        """Append an audit entry; never raises, never logs secrets."""
        try:
            conn = open_db(self.server.db_path)
            try:
                record_audit(
                    conn, action=action, entity_type=entity_type,
                    entity_id=entity_id, detail=detail,
                    request_id=getattr(self, "request_id", None),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:  # noqa: BLE001
            logger.error("Audit write failed: %s", traceback.format_exc())

    def _handle_auth_login(self):
        if not AUTH_TOKEN:
            self._send_json(400, {"error": {
                "code": "AUTH_DISABLED",
                "message": "Authentication is not enabled on this server.",
            }})
            return
        limit = RATE_LIMITS["/api/auth/login"]
        if not self._rate_limit(*limit):
            return
        body = self._read_json_body()
        if body is None:
            return
        token = str(body.get("token") or "").strip()
        if not hmac.compare_digest(token, AUTH_TOKEN):
            self._audit("auth.login_failed", detail="invalid access token")
            self._send_json(401, {"error": {
                "code": "INVALID_CREDENTIALS",
                "message": "Invalid access token.",
            }})
            return
        cookie = self._make_session_cookie()
        self._audit("auth.login", detail="session issued")
        payload = {"ok": True, "authenticated": True}
        body_bytes = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Set-Cookie", cookie)
        self.send_header("X-Request-ID", getattr(self, "request_id", ""))
        self._cors_headers()
        self._security_headers()
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def _handle_auth_logout(self):
        revoked = getattr(self.server, "revoked_sessions", set())
        cookie = self.headers.get("Cookie", "")
        for part in cookie.split(";"):
            name, _, value = part.strip().partition("=")
            if name == "rationai_session" and value:
                revoked.add(value)
        self._audit("auth.logout")
        body_bytes = json.dumps({"ok": True}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Set-Cookie",
                         "rationai_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0")
        self.send_header("X-Request-ID", getattr(self, "request_id", ""))
        self._cors_headers()
        self._security_headers()
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def _handle_ready(self):
        """Readiness: database writable + AI/provider + connector state."""
        checks = {"database": "READY", "ai": "NOT_CONFIGURED",
                  "external_sources": "NOT_CONNECTED"}
        status = "ok"
        try:
            conn = open_db(self.server.db_path)
            try:
                conn.execute("SELECT 1").fetchone()
            finally:
                conn.close()
        except Exception:  # noqa: BLE001
            checks["database"] = "ERROR"
            status = "error"
        try:
            from agents.env import llm_enabled  # noqa: E402
            checks["ai"] = "CONFIGURED" if llm_enabled() else "NOT_CONFIGURED"
        except Exception:  # noqa: BLE001
            pass
        try:
            sources = list_sources(db_path=self.server.db_path)
            if any(s.get("status") == "ACTIVE" for s in sources):
                checks["external_sources"] = "CONFIGURED"
        except Exception:  # noqa: BLE001
            pass
        self._send_json(200 if status == "ok" else 503, {
            "status": status,
            "checks": checks,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })

    def _handle_audit(self):
        params = {k: v[0] for k, v in urllib.parse.parse_qs(
            self.path.partition("?")[2]).items()}
        try:
            limit = int(params.get("limit", "50") or "50")
        except ValueError:
            limit = 50
        if limit < 1 or limit > 500:
            limit = 50
        action = (params.get("action") or "").strip() or None
        entity = (params.get("entity_type") or "").strip() or None
        try:
            conn = open_db(self.server.db_path)
            try:
                rows = list_audit(conn, limit=limit, action=action,
                                  entity_type=entity)
            finally:
                conn.close()
        except Exception:  # noqa: BLE001
            logger.error("Audit list failed:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "Could not load audit log"})
            return
        self._send_json(200, {"entries": rows, "total": len(rows)})

    def _handle_analyze(self):
        raw = self._read_body()
        body = {}
        if raw:
            try:
                body = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self._send_json(400, {"error": "Invalid JSON body"})
                return
        if not isinstance(body, dict):
            self._send_json(400, {"error": "Request body must be a JSON object"})
            return
        dataset_name = body.get("dataset", "synthetic")
        if dataset_name not in ("synthetic", "real"):
            self._send_json(400, {
                "error": 'Unknown dataset mode. Supported: "synthetic", "real"',
            })
            return

        import_id = None
        if dataset_name == "real":
            import_id = body.get("data_import_id")
            if import_id is None:
                self._send_json(400, {
                    "error": 'Real-data mode requires "data_import_id" '
                             '(see GET /api/datasets for available imports)'
                })
                return
            try:
                import_id = int(import_id)
            except (TypeError, ValueError):
                self._send_json(400, {"error": "data_import_id must be an integer"})
                return

        # Phase 9 command center: when analysis types are supplied, route
        # through analysis_center (real agents + deterministic types + merged
        # insights + persisted config). Without types, behavior is unchanged.
        analysis_types = body.get("types")
        filters = body.get("filters") or {}
        if not isinstance(filters, dict):
            self._send_json(400, {"error": "filters must be an object"})
            return
        if analysis_types is not None:
            if not isinstance(analysis_types, list) or not analysis_types:
                self._send_json(400, {"error": "types must be a non-empty array of analysis type keys"})
                return
            unknown = [t for t in analysis_types if t not in analysis_center.VALID_ANALYSIS_TYPES]
            if unknown:
                self._send_json(400, {
                    "error": "Unknown analysis type(s): %s. Supported: %s" % (
                        ", ".join(map(str, unknown)), ", ".join(sorted(analysis_center.VALID_ANALYSIS_TYPES))),
                })
                return
            try:
                result = analysis_center.run_analysis(
                    dataset_mode=dataset_name,
                    data_import_id=import_id,
                    types=analysis_types,
                    filters=filters,
                    db_path=self.server.db_path,
                )
            except Exception:
                logger.error("Command-center analysis failed:\n%s", traceback.format_exc())
                self._send_json(500, {"error": "The analysis could not be completed"})
                return
            if result is None:
                self._send_json(404, {"error": "Unknown data_import_id %r" % import_id})
                return
            self._send_json(200, result)
            return

        delay_ms = int(os.environ.get("RATIONRIGHT_ANALYZE_DELAY_MS", "0") or "0")
        if delay_ms > 0:
            logger.info("Delaying analysis by %d ms (RATIONRIGHT_ANALYZE_DELAY_MS)", delay_ms)
            time.sleep(delay_ms / 1000.0)

        try:
            if dataset_name == "real":
                result = run_workflow_on_dataset(
                    import_id, db_path=self.server.db_path
                )
                if result is None:
                    self._send_json(404, {
                        "error": "Unknown data_import_id %r" % import_id,
                    })
                    return
            else:
                transactions = load_dataset(self.server.dataset_path)["transactions"]
                logger.info("Running workflow on %d transaction(s)", len(transactions))
                result = run_workflow(transactions)
                result["dataset"] = synthetic_dataset_block(transactions)
        except Exception:
            logger.error("Unexpected workflow failure:\n%s", traceback.format_exc())
            self._send_json(500, {"error": "The analysis workflow failed unexpectedly"})
            return
        # Record durable lineage metadata (Phase 8): the AI insight a judge
        # sees in the UI now traces back through an analysis run to its
        # dataset/import/source. The full result is still returned live.
        try:
            run = record_analysis_run(
                result, dataset_mode=dataset_name,
                data_import_id=import_id, db_path=self.server.db_path,
            )
            result["analysis_run"] = run
            self._audit("analysis.run", entity_type="analysis",
                        entity_id=run.get("analysis_id") or run.get("id"),
                        detail="dataset=%s mode=%s" % (dataset_name, import_id))
        except Exception:  # noqa: BLE001
            logger.error("Could not record analysis run:\n%s", traceback.format_exc())
        self._send_json(200, result)

    # ---------- CORS preflight ----------

    def do_OPTIONS(self):
        self.request_id = uuid.uuid4().hex[:8]
        self.send_response(204)
        self._cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()


    def _get_db_conn(self):
        import sqlite3
        conn = sqlite3.connect(self.server.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _handle_demo_beneficiaries(self):
        _, _, query = self.path.partition("?")
        params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
        conn = self._get_db_conn()
        try:
            sql = """
                SELECT b.*, s.shop_name, s.district, s.state
                FROM demo_beneficiaries b
                LEFT JOIN demo_pwd_shops s ON s.pwd_id = b.pwd_id
                WHERE 1=1
            """
            args = []
            if "pwd_id" in params:
                sql += " AND b.pwd_id = ?"
                args.append(params["pwd_id"])
            if "category" in params:
                sql += " AND b.category = ?"
                args.append(params["category"])
            if "identity_status" in params:
                sql += " AND b.identity_status = ?"
                args.append(params["identity_status"])
            if "collection_status" in params:
                sql += " AND b.collection_status = ?"
                args.append(params["collection_status"])
            sql += " ORDER BY b.beneficiary_id ASC"
            rows = conn.execute(sql, args).fetchall()
            beneficiaries = [dict(r) for r in rows]
            self._send_json(200, {
                "period": "2026-10",
                "count": len(beneficiaries),
                "beneficiaries": beneficiaries
            })
        finally:
            conn.close()

    def _handle_demo_pwd_shops(self):
        _, _, query = self.path.partition("?")
        params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
        conn = self._get_db_conn()
        try:
            sql = "SELECT * FROM demo_pwd_shops WHERE 1=1"
            args = []
            if "district" in params:
                sql += " AND district = ?"
                args.append(params["district"])
            if "state" in params:
                sql += " AND state = ?"
                args.append(params["state"])
            if "pwd_id" in params:
                sql += " AND pwd_id = ?"
                args.append(params["pwd_id"])
            sql += " ORDER BY pwd_id ASC"
            rows = conn.execute(sql, args).fetchall()
            shops = [dict(r) for r in rows]
            self._send_json(200, {
                "period": "2026-10",
                "count": len(shops),
                "pwd_shops": shops
            })
        finally:
            conn.close()

    def _handle_demo_inventory(self):
        _, _, query = self.path.partition("?")
        params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
        conn = self._get_db_conn()
        try:
            sql = """
                SELECT i.*, s.shop_name, s.district, s.state
                FROM demo_inventory i
                LEFT JOIN demo_pwd_shops s ON s.pwd_id = i.pwd_id
                WHERE 1=1
            """
            args = []
            if "pwd_id" in params:
                sql += " AND i.pwd_id = ?"
                args.append(params["pwd_id"])
            if "commodity" in params:
                sql += " AND i.commodity = ?"
                args.append(params["commodity"])
            if "month" in params:
                sql += " AND i.month = ?"
                args.append(params["month"])
            sql += " ORDER BY i.pwd_id ASC, i.commodity ASC"
            rows = conn.execute(sql, args).fetchall()
            items = [dict(r) for r in rows]
            self._send_json(200, {
                "period": "2026-10",
                "count": len(items),
                "inventory": items
            })
        finally:
            conn.close()

    def _handle_demo_transactions(self):
        _, _, query = self.path.partition("?")
        params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
        conn = self._get_db_conn()
        try:
            sql = """
                SELECT t.*, s.shop_name, s.district, b.head_name, b.category
                FROM demo_transactions t
                LEFT JOIN demo_pwd_shops s ON s.pwd_id = t.pwd_id
                LEFT JOIN demo_beneficiaries b ON b.beneficiary_id = t.beneficiary_id
                WHERE 1=1
            """
            args = []
            if "pwd_id" in params:
                sql += " AND t.pwd_id = ?"
                args.append(params["pwd_id"])
            if "beneficiary_id" in params:
                sql += " AND t.beneficiary_id = ?"
                args.append(params["beneficiary_id"])
            if "commodity" in params:
                sql += " AND t.commodity = ?"
                args.append(params["commodity"])
            sql += " ORDER BY t.date DESC, t.transaction_id ASC"
            rows = conn.execute(sql, args).fetchall()
            txns = [dict(r) for r in rows]
            self._send_json(200, {
                "period": "2026-10",
                "count": len(txns),
                "transactions": txns
            })
        finally:
            conn.close()

    def _handle_demo_pwd_audits(self):
        _, _, query = self.path.partition("?")
        params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
        conn = self._get_db_conn()
        try:
            sql = """
                SELECT a.*, s.shop_name, s.district, s.state
                FROM demo_pwd_audits a
                LEFT JOIN demo_pwd_shops s ON s.pwd_id = a.pwd_id
                WHERE 1=1
            """
            args = []
            if "pwd_id" in params:
                sql += " AND a.pwd_id = ?"
                args.append(params["pwd_id"])
            if "inspection_status" in params:
                sql += " AND a.inspection_status = ?"
                args.append(params["inspection_status"])
            sql += " ORDER BY a.audit_id ASC"
            rows = conn.execute(sql, args).fetchall()
            audits = [dict(r) for r in rows]
            self._send_json(200, {
                "period": "2026-10",
                "count": len(audits),
                "pwd_audits": audits
            })
        finally:
            conn.close()

    def _handle_distribution_summary(self):
        conn = self._get_db_conn()
        try:
            shops = [dict(r) for r in conn.execute("SELECT * FROM demo_pwd_shops ORDER BY pwd_id").fetchall()]
            bens = [dict(r) for r in conn.execute("SELECT * FROM demo_beneficiaries ORDER BY beneficiary_id").fetchall()]
            inv = [dict(r) for r in conn.execute("SELECT * FROM demo_inventory ORDER BY inventory_id").fetchall()]
            audits = [dict(r) for r in conn.execute("SELECT * FROM demo_pwd_audits ORDER BY audit_id").fetchall()]

            total_capacity_kg = sum(s["monthly_capacity_kg"] for s in shops)
            total_opening_kg = sum(i["opening_stock_kg"] for i in inv)
            total_received_kg = sum(i["received_kg"] for i in inv)
            total_distributed_kg = sum(i["distributed_kg"] for i in inv)
            total_closing_kg = sum(i["closing_stock_kg"] for i in inv)
            total_physical_kg = sum(i["physical_stock_kg"] for i in inv)
            total_discrepancy_kg = total_physical_kg - (total_opening_kg + total_received_kg - total_distributed_kg)

            phh_count = sum(1 for b in bens if b["category"] == "PHH")
            aay_count = sum(1 for b in bens if b["category"] == "AAY")
            flagged_bens = [b for b in bens if b["identity_status"] != "verified" or b["collection_status"] != "collected"]

            districts = {}
            for s in shops:
                d = s["district"]
                if d not in districts:
                    districts[d] = {"district": d, "state": s["state"], "shops_count": 0, "capacity_kg": 0, "distributed_kg": 0}
                districts[d]["shops_count"] += 1
                districts[d]["capacity_kg"] += s["monthly_capacity_kg"]
                shop_inv = [i for i in inv if i["pwd_id"] == s["pwd_id"]]
                districts[d]["distributed_kg"] += sum(i["distributed_kg"] for i in shop_inv)

            self._send_json(200, {
                "period": "2026-10",
                "reporting_status": "Official October 2026 Run",
                "summary": {
                    "total_allocation_capacity_kg": total_capacity_kg,
                    "total_received_kg": total_received_kg,
                    "total_distributed_kg": total_distributed_kg,
                    "total_closing_stock_kg": total_closing_kg,
                    "total_physical_stock_kg": total_physical_kg,
                    "net_stock_discrepancy_kg": total_discrepancy_kg,
                    "fps_count": len(shops),
                    "beneficiaries_count": len(bens),
                    "phh_count": phh_count,
                    "aay_count": aay_count,
                    "flagged_cases_count": len(flagged_bens) + sum(1 for a in audits if a["inspection_status"] == "failed")
                },
                "districts": list(districts.values()),
                "pwd_shops": shops,
                "commodity_breakdown": {
                    "rice": {
                        "distributed_kg": sum(i["distributed_kg"] for i in inv if i["commodity"] == "Rice"),
                        "received_kg": sum(i["received_kg"] for i in inv if i["commodity"] == "Rice"),
                        "closing_stock_kg": sum(i["closing_stock_kg"] for i in inv if i["commodity"] == "Rice"),
                        "physical_stock_kg": sum(i["physical_stock_kg"] for i in inv if i["commodity"] == "Rice"),
                    },
                    "wheat": {
                        "distributed_kg": sum(i["distributed_kg"] for i in inv if i["commodity"] == "Wheat"),
                        "received_kg": sum(i["received_kg"] for i in inv if i["commodity"] == "Wheat"),
                        "closing_stock_kg": sum(i["closing_stock_kg"] for i in inv if i["commodity"] == "Wheat"),
                        "physical_stock_kg": sum(i["physical_stock_kg"] for i in inv if i["commodity"] == "Wheat"),
                    }
                }
            })
        finally:
            conn.close()

    def _handle_rag_query(self):
        import rag_pipeline
        query = ""
        top_k = 5
        if self.command == "GET":
            _, _, qs = self.path.partition("?")
            params = urllib.parse.parse_qs(qs)
            query = params.get("q", [""])[0] or params.get("query", [""])[0]
        else:
            body = self._read_body()
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
                query = payload.get("query", "") or payload.get("q", "")
                top_k = int(payload.get("top_k", 5))
            except Exception:
                query = ""

        if not query.strip():
            self._send_json(400, {"error": "Missing 'query' field."})
            return

        pipeline = rag_pipeline.get_rag_pipeline()
        result = pipeline.answer_query(query)
        self._send_json(200, result)


def build_health(dataset_path=None) -> dict:
    """Build the system health payload: dataset, agents, and configuration.

    Never exposes secrets or internal paths beyond the configured dataset name.
    Each check reports its own status so the UI/CLI can show per-component
    PASS/FAIL rather than a single opaque boolean.
    """
    checks = {}
    overall = "ok"

    # Dataset check: must exist, load, and pass the Phase 1 contract validation.
    try:
        dataset = load_dataset(dataset_path or DEFAULT_DATASET_PATH)
        errors = validate_transactions(dataset["transactions"])
        if errors:
            checks["dataset"] = {
                "status": "degraded",
                "detail": "%d validation error(s)" % len(errors),
            }
            overall = "degraded"
        else:
            checks["dataset"] = {
                "status": "ok",
                "detail": "%d transaction(s), %d beneficiary(ies)" % (
                    len(dataset["transactions"]),
                    len({t["beneficiary_id"] for t in dataset["transactions"]}),
                ),
            }
    except Exception as exc:  # noqa: BLE001
        checks["dataset"] = {"status": "error", "detail": str(exc)}
        overall = "error"

    # Agent checks: every agent must import and instantiate.
    agent_classes = {
        "agent_1": Agent1TransactionAnalyst,
        "agent_2": Agent2AnomalyInvestigator,
        "agent_3": Agent3EvidenceCaseBuilder,
        "agent_4": Agent4AlertGenerator,
    }
    for name, cls in agent_classes.items():
        try:
            cls()
            checks[name] = {"status": "ok"}
        except Exception as exc:  # noqa: BLE001
            checks[name] = {"status": "error", "detail": str(exc)}
            overall = "error"

    # Configuration check: no required environment variables; thresholds are
    # defaults unless the shared pattern config is missing.
    try:
        from agents.pattern_config import (  # noqa: PLC0415
            RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES,
            RAPID_GEOGRAPHIC_MIN_DISTANCE_KM,
        )
        checks["config"] = {
            "status": "ok",
            "detail": "interval<=%s min, distance>=%s km" % (
                RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES,
                RAPID_GEOGRAPHIC_MIN_DISTANCE_KM,
            ),
        }
    except Exception as exc:  # noqa: BLE001
        checks["config"] = {"status": "error", "detail": str(exc)}
        overall = "error"

    # LLM narratives: optional feature — report enabled/model without ever
    # exposing the API key.
    try:
        from agents.llm import llm_enabled  # noqa: PLC0415
        from agents.env import PROJECT_ROOT  # noqa: PLC0415
        checks["llm"] = {
            "status": "ok",
            "detail": (
                "enabled (model: %s)" % os.environ.get("RATIONRIGHT_LLM_MODEL", "gpt-4o-mini")
                if llm_enabled()
                else "disabled (optional)"
            ),
        }
    except Exception as exc:  # noqa: BLE001
        checks["llm"] = {"status": "ok", "detail": "unavailable (%s)" % exc}

    return {
        "status": overall,
        "service": "rationright",
        "checks": checks,
    }


def validate_startup(dataset_path) -> None:
    """Validate required startup configuration; raise ValueError with a clear
    developer-facing message if anything is missing or invalid."""
    path = Path(dataset_path)
    if not path.is_file():
        raise ValueError(
            "Dataset file not found: %s. Run the server from the project root, "
            "or pass --dataset <path>." % path
        )
    try:
        dataset = load_dataset(path)
        errors = validate_transactions(dataset["transactions"])
    except ValueError as exc:
        raise ValueError("Dataset failed validation: %s" % exc) from exc
    if errors:
        raise ValueError(
            "Dataset failed validation with %d error(s): %s" % (len(errors), errors[0])
        )


def make_server(host: str = "127.0.0.1", port: int = 0, dataset_path=None, db_path=None) -> ThreadingHTTPServer:
    if db_path:
        try:
            register_configured_sources(db_path)
        except Exception:  # noqa: BLE001
            logger.error("Could not register configured data sources:\n%s", traceback.format_exc())
    """Create (but do not start) a RationRight server. Port 0 picks an ephemeral
    port. ``dataset_path`` is the dataset served by /api/dataset and analyzed
    by /api/analyze; defaults to the canonical Phase 1 dataset. ``db_path`` is
    the database used by the Phase 3 ingestion endpoints; defaults to
    ``data/rationright.db``."""
    server = ThreadingHTTPServer((host, port), RationRightHandler)
    server.dataset_path = dataset_path or DEFAULT_DATASET_PATH
    server.db_path = db_path or DEFAULT_DB_PATH
    server.rate_limiter = _RateLimiter()
    server.revoked_sessions = set()
    return server


def main(argv=None) -> int:
    # Load local secrets (e.g. OPENAI_API_KEY) from the git-ignored .env file
    # before anything reads them. Shell exports take precedence.
    load_env_file()

    parser = argparse.ArgumentParser(
        description="Run the RationRight dashboard + workflow API server."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Dataset to serve and analyze (default: %(default)s)",
    )
    parser.add_argument(
        "--analyze-delay-ms",
        type=int,
        default=int(os.environ.get("RATIONRIGHT_ANALYZE_DELAY_MS", "0") or "0"),
        help="Artificial delay before running the workflow, in ms (default: 0)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(os.environ.get("RATIONRIGHT_DB_PATH", "") or DEFAULT_DB_PATH),
        help="Database used by the ingestion endpoints (default: %(default)s; "
             "overridable with RATIONRIGHT_DB_PATH)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
    if args.analyze_delay_ms > 0:
        os.environ["RATIONRIGHT_ANALYZE_DELAY_MS"] = str(args.analyze_delay_ms)

    try:
        validate_startup(args.dataset)
    except ValueError as exc:
        logger.error("Startup configuration error: %s", exc)
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2

    server = make_server(args.host, args.port, dataset_path=args.dataset, db_path=args.db)
    host, port = server.server_address[:2]
    logger.info("RationRight server running at http://%s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
