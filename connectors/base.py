"""RationAI — connector abstractions (Phase 7).

A ``DataConnector`` turns one external source into validated, mapped,
normalized records that the existing Phase 3/4 ingestion pipeline imports:

    DataSource -> Connector -> Fetcher -> Raw response -> Parser
        -> Column mapper -> Validator -> Normalizer -> Database

The four operations below map directly onto the existing pipeline pieces:
``fetch`` (this package), ``parse`` (``ingestion.parsers``), ``map_columns``
(``ingestion.mapping``), ``validate`` (``ingestion.validation``). The sync
service (``connectors.service``) drives the DB/provenance/status side.

No URL is ever user-supplied: connectors only fetch the ``base_url`` from
their registered profile, which lives server-side.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from connectors.errors import InvalidResponseError
from connectors.fetcher import MAX_PAGES
from ingestion import mapping as mapmod
from ingestion import parsers
from ingestion import validation
from ingestion.mapping import MappingError


def sha256_bytes(data: bytes) -> str:
    """Stable content hash for idempotent re-import detection (Phase 4)."""
    return hashlib.sha256(data).hexdigest()


class DataConnector(ABC):
    """Base class for all external data connectors."""

    def __init__(self, profile: dict):
        self.profile = profile

    # -- fetch --------------------------------------------------------------

    @abstractmethod
    def fetch(self, fetcher, resolve_url) -> list:
        """Fetch the source and return raw page bodies (list of bytes).

        ``resolve_url`` turns the profile's (possibly relative) base_url into
        an absolute URL. ``fetcher`` is the HTTP fetch function (injectable
        for tests). Returns a LIST so paginated JSON sources can yield
        multiple pages; single-body sources return a one-element list.
        """

    # -- parse --------------------------------------------------------------

    @abstractmethod
    def parse(self, pages: list) -> tuple:
        """Parse raw bodies into ``(headers, rows)``."""

    # -- map ----------------------------------------------------------------

    def map_columns(self, headers: list) -> dict:
        """Map external headers to internal fields.

        Profile mappings (explicit, source-specific) win; the generic alias
        table (``ingestion.mapping.detect_mapping``) fills the rest. Returns
        ``{external_header: internal_field}`` — the importer contract.
        """
        detected = mapmod.detect_mapping(headers, self.profile["dataset_type"])
        mapping = mapmod.mapping_to_dict(detected["mapping"])
        mappable = set(mapmod.mappable_fields(self.profile["dataset_type"]))
        profile_mapping = self.profile.get("mapping") or {}
        for external, internal in profile_mapping.items():
            # Apply only when the column exists AND the target is a valid
            # internal field for this dataset type (a bad profile entry must
            # never break the required-field contract).
            if internal not in mappable:
                continue
            for header in headers:
                if header.strip().lower() == external.strip().lower():
                    mapping[header] = internal
                    break
        required = mapmod.required_fields(self.profile["dataset_type"])
        missing = [f for f in required if f not in mapping.values()]
        if missing:
            raise MappingError(
                "Required field(s) not present or not mapped: %s" % ", ".join(missing)
            )
        return mapping

    # -- validate -----------------------------------------------------------

    def validate(self, headers: list, rows: list, mapping: dict) -> dict:
        """Run the Phase 4 validation pipeline; returns the summary."""
        return validation.summarize(rows, self.profile["dataset_type"], headers, mapping)


class CsvUrlConnector(DataConnector):
    """Connector for a downloadable CSV file (reuses the Phase 3 CSV parser)."""

    format = "csv"

    def fetch(self, fetcher, resolve_url) -> list:
        return [fetcher(resolve_url(self.profile["base_url"]))]

    def parse(self, pages: list) -> tuple:
        if not pages or not pages[0]:
            raise InvalidResponseError("The source returned an empty response.")
        data = pages[0]
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(data)
            path = Path(tmp.name)
        try:
            parsed = parsers.parse_file(path, "csv")
        finally:
            path.unlink(missing_ok=True)
        headers = parsed.get("headers") or []
        rows = parsed.get("rows") or []
        if not rows:
            raise InvalidResponseError("The source returned an empty dataset (no rows).")
        return headers, rows


class JsonUrlConnector(DataConnector):
    """Connector for a JSON API/dataset.

    Supports offset/limit pagination when the profile declares it (the OGD
    India API pattern): pages are fetched until the declared total is reached
    or a page yields no records, with a hard page cap so a broken source
    cannot loop forever.
    """

    format = "json"

    def _query_params(self) -> list:
        """Static query params for this profile, appended to every request.

        Server-side only: the auth key is read from the environment and NEVER
        logged, stored, or exposed to the client (Phase 14 secret rules)."""
        params = []
        key_param = self.profile.get("api_key_param")
        if key_param:
            from connectors.profiles import _ogd_api_key
            key = _ogd_api_key()
            if not key:
                raise InvalidResponseError(
                    "API key not configured. Set the %s environment variable "
                    "server-side, then retry." % self.profile.get("auth_env_var", "")
                )
            params.append("%s=%s" % (key_param, key))
        if (self.profile.get("format") or "").lower() == "json":
            params.append("format=json")
        return params

    def fetch(self, fetcher, resolve_url) -> list:
        pagination = self.profile.get("pagination")
        base = resolve_url(self.profile["base_url"])
        base_params = self._query_params()
        sep = "&" if "?" in base else "?"
        if not pagination or pagination.get("type") != "offset":
            url = base if not base_params else "%s%s%s" % (base, sep, "&".join(base_params))
            return [fetcher(url)]
        offset_param = pagination.get("offset_param", "offset")
        limit_param = pagination.get("limit_param", "limit")
        page_size = int(pagination.get("page_size", 1000))
        pages = []
        offset = 0
        while offset // page_size < MAX_PAGES:
            params = list(base_params) + [
                "%s=%d" % (offset_param, offset), "%s=%d" % (limit_param, page_size)]
            pages.append(fetcher("%s%s%s" % (base, sep, "&".join(params))))
            try:
                payload = json.loads(pages[-1].decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                # One malformed page: fail the sync rather than guessing.
                raise InvalidResponseError("The source returned malformed JSON.")
            records = payload.get(pagination.get("records_key", "records")) or []
            total = payload.get(pagination.get("total_key"))
            offset += len(records)
            if not records:
                break
            if total is not None and offset >= int(total):
                break
        return pages

    def parse(self, pages: list) -> tuple:
        records = []
        for page in pages:
            if not page:
                raise InvalidResponseError("The source returned an empty response.")
            try:
                payload = json.loads(page.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                raise InvalidResponseError("The source returned malformed JSON.")
            pagination = self.profile.get("pagination")
            if pagination:
                chunk = payload.get(pagination.get("records_key", "records")) or []
            elif isinstance(payload, list):
                chunk = payload
            else:
                # Wrapped formats handled by the Phase 3 JSON parser.
                chunk = None
            if chunk is not None:
                records.extend(chunk)
            else:
                # Fall back to the shared JSON parser for wrapped objects.
                with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
                    tmp.write(page)
                    path = Path(tmp.name)
                try:
                    parsed = parsers.parse_file(path, "json")
                finally:
                    path.unlink(missing_ok=True)
                return parsed.get("headers") or [], parsed.get("rows") or []
        if not records:
            raise InvalidResponseError("The source returned an empty dataset (no records).")
        # Reuse the Phase 3 JSON parser on the merged record list.
        merged = json.dumps(records).encode("utf-8")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp.write(merged)
            path = Path(tmp.name)
        try:
            parsed = parsers.parse_file(path, "json")
        finally:
            path.unlink(missing_ok=True)
        return parsed.get("headers") or [], parsed.get("rows") or []


def connector_for(profile: dict) -> DataConnector:
    """Factory: build the right connector for a profile."""
    fmt = (profile.get("format") or "csv").lower()
    if fmt == "json":
        return JsonUrlConnector(profile)
    if fmt == "csv":
        return CsvUrlConnector(profile)
    raise InvalidResponseError("Unsupported connector format %r" % fmt)
