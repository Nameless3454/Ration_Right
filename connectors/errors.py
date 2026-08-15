"""RationAI — connector error types (Phase 7).

Every failure during an external sync is classified so the sync service can
decide whether to retry, mark the source ERROR, and surface a clear
user-facing reason — without ever deleting or fabricating data.
"""

from __future__ import annotations

from typing import Optional


class ConnectorError(Exception):
    """Base class for all connector failures."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class AuthError(ConnectorError):
    """The source rejected our credentials (401/403) or credentials are
    missing. Never retried — retrying would just hammer the source."""


class RateLimitError(ConnectorError):
    """The source returned 429. Retryable after ``retry_after`` seconds."""

    def __init__(self, message: str, *, retry_after: Optional[float] = None):
        super().__init__(message, retryable=True)
        self.retry_after = retry_after


class HttpStatusError(ConnectorError):
    """The source returned an unexpected HTTP status."""

    def __init__(self, status: int, message: str, *, retryable: bool = False):
        super().__init__("%s (HTTP %d)" % (message, status), retryable=retryable)
        self.status = status


class TimeoutError(ConnectorError):
    """The source did not answer within the configured timeout."""


class UnreachableError(ConnectorError):
    """DNS/connection-level failure. Retryable."""


class InvalidResponseError(ConnectorError):
    """The source answered but the payload could not be parsed (malformed
    JSON/CSV, unexpected structure, or an empty dataset)."""


class SourceNotConfiguredError(ConnectorError):
    """The source exists but cannot sync yet (e.g. missing API key)."""


class SyncFailure(Exception):
    """Wraps any connector/import failure during a sync so the service can
    record it on the DataSource and DataImport without aborting the request
    in an unstructured way."""
