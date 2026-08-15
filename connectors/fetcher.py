"""RationAI — HTTP fetcher for external data sources (Phase 7).

stdlib-only ``urllib`` wrapper with the operational behavior the sync
service needs:

- request timeout (no hanging syncs)
- controlled retries with exponential backoff (5xx and network errors)
- NO retry on permanent client errors (404, 401, 403, 400)
- 429 honoured: sleeps ``Retry-After`` when provided
- a hard attempt cap so a broken source cannot loop forever

The fetcher is deliberately tiny and side-effect free (no logging of the
body, no credentials in exceptions) so the sync service and tests can
inject a fake fetcher for the full failure matrix.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from typing import Callable, Optional

from connectors.errors import (
    AuthError,
    HttpStatusError,
    RateLimitError,
    TimeoutError,
    UnreachableError,
)

DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_BASE_SECONDS = 0.5
DEFAULT_MAX_BACKOFF_SECONDS = 8.0

#: Hard cap on how many pages a paginated connector may fetch in one sync.
MAX_PAGES = 20


def _backoff_delay(attempt: int, base: float, cap: float) -> float:
    """Exponential backoff with jitter-free deterministic growth:
    0.5s, 1s, 2s, ... capped at ``cap``. Small for a demo, documented."""
    return min(base * (2 ** max(attempt - 1, 0)), cap)


def http_get_bytes(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    headers: Optional[dict] = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_base: float = DEFAULT_BACKOFF_BASE_SECONDS,
    backoff_cap: float = DEFAULT_MAX_BACKOFF_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> bytes:
    """Fetch ``url`` and return the raw response body.

    Raises the classified ``ConnectorError`` subclasses on failure. Never
    retries permanent errors; respects 429 ``Retry-After``; caps attempts.
    """
    # A real User-Agent is required: some providers (e.g. api.data.gov.in)
    # stall requests that carry urllib's default "Python-urllib" header.
    merged_headers = {"User-Agent": "RationAI/2.0 (local demo; https://data.gov.in)"}
    merged_headers.update(headers or {})
    request = urllib.request.Request(url, headers=merged_headers)
    attempt = 0
    while True:
        attempt += 1
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                status = resp.getcode()
                if status is not None and status >= 400:
                    raise HttpStatusError(
                        status, "Source returned an error status"
                    )
                return resp.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            if status in (401, 403):
                raise AuthError(
                    "The source rejected the request credentials (HTTP %d)" % status
                )
            if status == 404:
                raise HttpStatusError(
                    status, "The source URL was not found", retryable=False
                )
            if status == 429:
                retry_after = None
                raw = exc.headers.get("Retry-After") if exc.headers else None
                if raw:
                    try:
                        retry_after = max(0.0, float(raw))
                    except (TypeError, ValueError):
                        retry_after = None
                if attempt < max_attempts:
                    sleep(retry_after if retry_after is not None
                          else _backoff_delay(attempt, backoff_base, backoff_cap))
                    continue
                raise RateLimitError(
                    "The source rate-limited the request (HTTP 429)",
                    retry_after=retry_after,
                )
            if status in (500, 502, 503, 504):
                if attempt < max_attempts:
                    sleep(_backoff_delay(attempt, backoff_base, backoff_cap))
                    continue
                raise HttpStatusError(
                    status, "The source is unavailable", retryable=True
                )
            raise HttpStatusError(status, "The source rejected the request")
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                if attempt < max_attempts:
                    sleep(_backoff_delay(attempt, backoff_base, backoff_cap))
                    continue
                raise TimeoutError(
                    "The source did not respond within %gs" % timeout
                )
            if attempt < max_attempts:
                sleep(_backoff_delay(attempt, backoff_base, backoff_cap))
                continue
            raise UnreachableError(
                "Could not reach the source: %s" % (reason or exc)
            )
        except TimeoutError:
            if attempt < max_attempts:
                sleep(_backoff_delay(attempt, backoff_base, backoff_cap))
                continue
            raise
