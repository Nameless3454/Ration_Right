# RationAI — Troubleshooting

Common failures and their fixes, based on the actual application behavior.

## AI unavailable (LLM narratives missing / deterministic text shown)

**Symptom:** Every explanation/summary is the plain "deterministic" text and
the UI labels it `Deterministic fallback`.

**Cause:** `RATIONRIGHT_LLM_ENABLED` is off, `OPENAI_API_KEY` is missing, or
the provider call failed (timeout/429/500 — the platform degrades gracefully
by design).

**Fix:**

```bash
export RATIONRIGHT_LLM_ENABLED=1
export OPENAI_API_KEY=sk-...          # server-side only
python3 server.py
```

Check the server log for `LLM narrative generation failed (...)` warnings —
they name the cause (e.g. `HTTP Error 401`, `timeout`). **This is not an
error**: the platform is designed to run without the LLM.

## No dashboard data / zeros everywhere

**Symptom:** Command Center KPIs are 0 or "No data".

**Causes / fixes:**

- No import yet → Data → **Import Data** → upload a CSV and confirm the import.
- Wrong database → confirm `--db` / `RATIONRIGHT_DB_PATH` points at the file
  that contains the import.
- The default KPI window is a rolling 30 days up to **today** — data older
  than that is legitimately excluded. Use the date-range filter to confirm.
- Seed the demo DB: `python3 scripts/seed_database.py`.

## Database errors / locked

**Symptom:** `database is locked`, or the server fails to start.

**Fixes:**

- Only one process should hold the SQLite file; stop duplicate servers
  (`pkill -f server.py` on the host).
- Schema auto-creates on first open, so a deleted/corrupt file can simply be
  recreated — but keep a backup if the file contains demo work.
- Migrations are idempotent: opening an older DB upgrades it in place.

## Auth overlay appears unexpectedly

**Symptom:** The UI shows "RationAI — sign in" on every page.

**Cause:** `RATIONRIGHT_AUTH_TOKEN` is set (intentionally, or leaked from a
previous shell).

**Fix:** unset it for the open demo mode, or sign in with the configured
token (Settings → System status shows the readiness state).

## CORS / cross-origin problems

**Symptom:** Browser requests blocked.

**Cause:** Serving the frontend from a different origin than the API while
`RATIONRIGHT_ALLOWED_ORIGINS` is empty (default is same-origin only).

**Fix:** Serve both from the same origin (`python3 server.py` serves the
frontend), or set `RATIONRIGHT_ALLOWED_ORIGINS=https://your-frontend`.

## Import fails or is rejected

**Symptom:** Upload returns an error (400/413).

**Causes:** unsupported extension, content-type/magic-byte mismatch, file >
10 MB, > `RATIONRIGHT_MAX_ROWS` rows, or invalid schema mapping. The error
message names the problem. Imports are transactional — a failure leaves no
partial data.

## Health / readiness

- `GET /api/health` — process alive + component checks.
- `GET /api/ready` — `{checks: {database, ai, external_sources}, timestamp}`.

If `/api/ready` reports `ai: NOT_CONFIGURED` that is expected when no key is
set — it is not a fault.
