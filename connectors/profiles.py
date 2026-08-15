"""RationAI — source profiles (Phase 7, centralized configuration).

Every external data source is described ONCE here: URL, format, dataset
type, field mapping, auth, pagination, and documentation. The database
stores the source row (name/type/base_url/status/timestamps) and the sync
service looks its connector profile up by name — URLs and mappings are never
scattered through the application, and no user-supplied URL can ever be
fetched (sync is only possible for a registered source id).

Live vs sample — be honest:

* ``ogd_pds_resource`` points at the OFFICIAL Government of India Open Data
  (OGD) Platform API (api.data.gov.in) — the "Fair Price Shop details,
  Maharashtra (Sep–Dec 2025)" resource, fetched with the server-side key
  (env ``GOVERNMENT_DATA_API_KEY``) and imported as ``fps_centers``. Without
  a key, a sync fails cleanly with an actionable message instead of
  pretending to be live; with a key, the sync is real and the source is only
  ever labeled CONNECTED after a verified successful sync.

* ``sample_open_pds`` is a SMALL BUNDLED sample served by the RationAI app
  itself (``/sample/pds_sample.csv``). It exists purely to exercise the full
  connector pipeline (real HTTP fetch -> parse -> validate -> import) and is
  clearly labelled in the UI as sample data — it is NOT government data.
"""

from __future__ import annotations

import os

#: Env var that would hold the OGD India API key. Server-side only.
OGD_API_KEY_ENV = "GOVERNMENT_DATA_API_KEY"

#: Official OGD Platform India API documentation.
OGD_DOC_URL = "https://www.data.gov.in/apis"
OGD_API_BASE = "https://api.data.gov.in"


def _ogd_api_key() -> str:
    return os.environ.get(OGD_API_KEY_ENV, "").strip()


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

PROFILES = {
    # --- Official source (documented; requires an API key) -----------------
    "ogd_pds_resource": {
        "name": "ogd_pds_resource",
        "label": "OGD India — Fair Price Shops, Maharashtra (Sep–Dec 2025)",
        "type": "API",
        "description": (
            "Official Government of India Open Data (OGD) Platform API resource: "
            "Fair Price Shop details for Maharashtra, September–December 2025 "
            "(52,793 shops with district, block/tehsil and geo-coordinates). "
            "Requires a free data.gov.in API key (GOVERNMENT_DATA_API_KEY)."
        ),
        "base_url": (
            "https://api.data.gov.in/resource/87e32686-a3a1-4b2f-ba3f-ac6cf7327f86"
        ),
        "format": "json",
        "dataset_type": "fps_centers",
        "dataset_name": "ogd_mh_fps_2025",
        "file_name": "ogd_mh_fps_2025.json",
        "requires_auth": True,
        "auth_env_var": OGD_API_KEY_ENV,
        # Sent by JsonUrlConnector as a query parameter (server-side only).
        "api_key_param": "api-key",
        "pagination": {"type": "offset", "offset_param": "offset", "limit_param": "limit",
                       "page_size": 10000, "records_key": "records", "total_key": "total"},
        "mapping": {
            # Real columns of the Maharashtra FPS resource -> fps_centers
            # fields (required: fps_code, district).
            "fps_id": "fps_code",
            "district_name": "district",
            "name_of_fps": "name",
            "name_of_block_tehsil": "block",
            "latitude_of_fps": "latitude",
            "longitude_of_fps": "longitude",
        },
        "documentation_url": OGD_DOC_URL,
        "update_frequency": "varies by resource — verify before re-sync",
        "terms": "Free registration; API key required; usage per OGD platform terms.",
    },
    # --- Bundled sample (NOT government data; exercises the pipeline) ------
    "sample_open_pds": {
        "name": "sample_open_pds",
        "label": "Sample PDS dataset (bundled with RationAI)",
        "type": "CSV",
        "description": (
            "A small, deterministic sample dataset bundled with the app and "
            "served from /sample/pds_sample.csv. It exists so the connector "
            "pipeline (HTTP fetch, parse, validate, import) can be exercised "
            "end to end. This is SAMPLE data — not an external government "
            "source."
        ),
        "base_url": "/sample/pds_sample.csv",  # relative -> resolved against the app origin
        "format": "csv",
        "dataset_type": "ration_transactions",
        "dataset_name": "sample_open_pds_sync",
        "file_name": "pds_sample.csv",
        "requires_auth": False,
        "pagination": None,
        "mapping": {
            "Transaction ID": "external_transaction_id",
            "FPS Code": "fps_center_id",
            "District Name": "district",
            "Commodity": "commodity",
            "Quantity Distributed": "quantity",
            "Transaction Date": "transaction_date",
            "Beneficiary ID": "beneficiary_id",
            "Latitude": "latitude",
            "Longitude": "longitude",
        },
        "documentation_url": None,
        "update_frequency": "n/a (static sample)",
        "terms": "Sample data for demonstration; not real PDS records.",
    },
}


def get_profile(name: str):
    """Return the connector profile for a source name, or None."""
    return PROFILES.get(name)


def list_profiles() -> list:
    """All registered profiles (for documentation/registration)."""
    return list(PROFILES.values())
