"""RationRight — minimal local environment loader (Phase 10).

Loads ``KEY=VALUE`` pairs from a local ``.env`` file (default) into the
process environment WITHOUT overriding variables that are already set, so
shell exports win. Only the standard library is used — no dotenv dependency.

The ``.env`` file is intended for LOCAL development secrets such as
``OPENAI_API_KEY`` and is git-ignored (see ``.gitignore``: ``.env`` and
``.env.*`` are never committed). Never commit a real key.

Usage::

    from agents.env import load_env_file
    load_env_file()            # reads ./RationRight/.env relative to project root
    load_env_file("config.env")
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_env_file(path=None) -> None:
    """Load KEY=VALUE lines from ``path`` (default: project-root ``.env``).

    Existing environment variables are never overwritten. Missing files are
    ignored silently (the app must still run without a .env). Malformed lines
    (no ``=``) are skipped. Values may optionally be quoted with single or
    double quotes.
    """
    env_path = Path(path) if path is not None else PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return
    with open(env_path, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if not key:
                continue
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            if key not in os.environ:
                os.environ[key] = value
