# RationAI — Deployment

How to run RationAI in development, test, and production-style environments.

## 1. Environments

| Environment | How to run |
|-------------|-----------|
| **Development** | `python3 server.py` (defaults; `.env` optional) |
| **Test** | `python3 -m unittest discover -s tests -t .` (uses temp databases; never touches `data/`) |
| **Production-style** | `python3 server.py --host 0.0.0.0 --port 8000 --db /var/lib/rationai/rationright.db` behind a reverse proxy; set auth + CORS + LLM env vars |

Configuration is read from the environment (a git-ignored `.env` is loaded
if present; shell exports take precedence). See `.env.example` for the
complete, placeholder-only template.

## 2. Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `RATIONRIGHT_DB_PATH` | `data/rationright.db` | SQLite database file (honored by `server.py`) |
| `RATIONRIGHT_LLM_ENABLED` | off | Opt-in LLM narratives |
| `OPENAI_API_KEY` | — | Server-side AI key (never exposed to the browser) |
| `RATIONRIGHT_LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible endpoint |
| `RATIONRIGHT_LLM_MODEL` | `gpt-4o-mini` | Model name |
| `RATIONRIGHT_AUTH_TOKEN` | empty (open mode) | When set, enables token auth |
| `RATIONRIGHT_SESSION_SECRET` | — | HMAC secret for session cookies (required with auth) |
| `RATIONRIGHT_ALLOWED_ORIGINS` | empty (same-origin) | Comma-separated CORS allow-list |
| `RATIONRIGHT_CORS_ALLOW_ANY` | `0` | `1` restores `Access-Control-Allow-Origin: *` (not recommended with auth) |
| `RATIONRIGHT_MAX_ROWS` | `500000` | Per-import row cap |

Never put real secrets in `.env.example`, documentation, or the repository.
`.env` is git-ignored.

## 3. Database deployment

- SQLite; the schema is created and migrated automatically on first open
  (`database.open_db`). There is **no separate migration command**.
- Verified safe: fresh database (full schema created), existing database
  (idempotent re-open), and upgrades from earlier phases (Phase 2–14 tables
  added incrementally, all `CREATE TABLE IF NOT EXISTS` / additive).
- Imports are transactional: a failed import rolls back completely (Phase 14,
  test-verified) — no partial production dataset.
- **Backups**: copy the SQLite file while no server holds it (or use SQLite's
  online backup). Document the backup location in your ops notes — RationAI
  does not implement automatic backups.

## 4. Production considerations

- **Reverse proxy**: terminate TLS at a proxy (nginx/Caddy) and forward to the
  API. The app already sends `X-Content-Type-Options`, `Referrer-Policy`,
  `X-Frame-Options`, and a same-origin CSP.
- **Auth**: enable `RATIONRIGHT_AUTH_TOKEN` + `RATIONRIGHT_SESSION_SECRET`.
  Sessions are `HttpOnly` + `SameSite=Lax` cookies; logout revokes
  server-side. Health/ready/auth-status stay public.
- **CORS**: keep same-origin (default) or set `RATIONRIGHT_ALLOWED_ORIGINS`.
- **Rate limits**: in-memory per-process limits on expensive endpoints
  (analyze 30/min, monitoring 30/min, reports 30/min, upload 60/min,
  simulation 60/min, login 5/min). Note: in-memory — they reset on restart.
- **Logging**: structured INFO/WARN/ERROR logs with request IDs; secrets are
  never logged (test-verified).
- **Secrets**: `OPENAI_API_KEY` must stay server-side. The final secret scan
  (Phase 16) reports zero hits in source/config/docs/tests.

## 5. Release checklist

- [x] Production build: static frontend + Python backend start cleanly (no build step)
- [x] Database migrations succeed (fresh + existing + upgrade)
- [x] Environment configuration documented (`.env.example`, placeholders only)
- [x] No secrets in the repository (final scan: 0 hits)
- [x] AI key server-side; timeouts (15 s) + fail-open error handling
- [x] Authentication tested (login/logout/revocation/forgery/rate-limit)
- [x] Authorization: server-side protection on every route when auth enabled
- [x] Data ingestion tested (reconciliation invariant, rollback, row cap)
- [x] Analytics verified (independent recomputation, KPI chain)
- [x] Alerts verified (thresholds, dedup, lifecycle)
- [x] AI tested (scorecard, failure modes, no retry storm)
- [x] Simulation tested (deterministic math, never modifies data)
- [x] Reports tested (values match command center, lineage)
- [x] Security regression passed (Phase 14 suite re-run)
- [x] UI regression passed (Phase 13 polish intact, console clean)
- [x] Mobile checked (responsive layout, no horizontal overflow)
- [x] Main demo dataset ready (`data/rationright.db`)
- [x] Demo reset available (seed script, frontend reset)
- [x] README complete
- [x] Demo guide complete (`docs/DEMO.md`)
- [x] Limitations documented (`docs/LIMITATIONS.md`)
- [x] Deployment instructions complete (this document)
