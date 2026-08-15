"""RationRight — dataset ingestion pipeline (Phase 3).

    UPLOAD -> FILE TYPE CHECK -> PARSE -> COLUMN DETECTION -> SCHEMA MAPPING
           -> VALIDATION -> DUPLICATE DETECTION -> PREVIEW -> USER CONFIRMATION
           -> DATABASE IMPORT -> IMPORT SUMMARY

No uploaded record reaches the production tables before the user confirms:
every file goes through parsing, mapping, and validation first. The public
entry points live in ``ingestion.service`` and are wired to the API by
``server.py``.
"""

from ingestion.parsers import (
    EmptyDatasetError,
    FileTooLargeError,
    ParseError,
    UnsupportedFileTypeError,
    parse_file,
    sniff_file_type,
)
from ingestion.mapping import MappingError
from ingestion.service import (
    NotFoundError,
    confirm_step,
    handle_upload,
    import_history,
    import_status,
    validate_step,
)

__all__ = [
    "EmptyDatasetError",
    "FileTooLargeError",
    "MappingError",
    "NotFoundError",
    "ParseError",
    "UnsupportedFileTypeError",
    "confirm_step",
    "handle_upload",
    "import_history",
    "import_status",
    "parse_file",
    "sniff_file_type",
    "validate_step",
]
