"""RationRight — file parsers (Phase 3).

Parses uploaded CSV, JSON, and XLSX files into a uniform shape:

    {"headers": [str, ...], "rows": [[...], ...], "sheets": [str, ...],
     "warnings": [str, ...]}

Everything here is standard library only: ``csv``, ``json``, ``zipfile``, and
``xml.etree``. XLSX is an OOXML ZIP container, so a minimal, dependency-free
reader is implemented that handles the shapes real government/Excel exports
use: shared strings, inline strings, plain numbers, multiple worksheets, and
header rows. Formulas are not evaluated (the cached value is read), and date
cells stored as Excel serial numbers are converted during validation (see
``ingestion.validation.parse_date``).

Errors raise ``ParseError`` (bad content), ``EmptyDatasetError`` (no records),
``UnsupportedFileTypeError`` (bad extension/content type), or
``FileTooLargeError`` (enforced by the caller, defined here).
"""

from __future__ import annotations

import csv
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB default; see service.get_max_upload_bytes
MAX_ROWS = 500_000  # row cap; see get_max_rows()

EXT_TO_TYPE = {
    ".csv": "csv",
    ".xlsx": "xlsx",
    ".json": "json",
}

# Content types considered acceptable per file type (base part, before ';').
CONTENT_TYPE_OK = {
    "csv": {"text/csv", "application/csv", "text/plain", "application/octet-stream"},
    "xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
        "application/octet-stream",
    },
    "json": {"application/json", "text/json", "application/octet-stream"},
}

JSON_WRAPPER_KEYS = ("data", "records", "rows", "transactions", "items", "results")


class ParseError(Exception):
    """Raised when a file cannot be parsed or does not look like its type."""


class EmptyDatasetError(ParseError):
    """Raised when a file contains no data rows."""


class UnsupportedFileTypeError(ParseError):
    """Raised for unsupported extensions or mismatched content types."""


class FileTooLargeError(ParseError):
    """Raised when the upload exceeds the configured maximum size."""


# ---------------------------------------------------------------------------
# File-type detection
# ---------------------------------------------------------------------------


def get_max_upload_bytes() -> int:
    """Maximum upload size in bytes; overridable via RATIONRIGHT_MAX_UPLOAD_MB."""
    import os
    try:
        mb = float(os.environ.get("RATIONRIGHT_MAX_UPLOAD_MB", "") or 0)
    except ValueError:
        mb = 0
    return int(mb * 1024 * 1024) if mb > 0 else MAX_UPLOAD_BYTES


def get_max_rows() -> int:
    """Maximum number of rows per uploaded dataset; overridable via
    RATIONRIGHT_MAX_ROWS. Guards memory/CPU on large files."""
    import os

    try:
        rows = int(os.environ.get("RATIONRIGHT_MAX_ROWS", "") or 0)
    except ValueError:
        rows = 0
    return rows if rows > 0 else MAX_ROWS


def sniff_file_type(filename: str, content_type: str = "") -> str:
    """Return ``csv``/``xlsx``/``json`` or raise UnsupportedFileTypeError."""
    if not filename:
        raise UnsupportedFileTypeError("No file was provided.")
    ext = Path(filename).suffix.lower()
    if ext not in EXT_TO_TYPE:
        raise UnsupportedFileTypeError(
            "Unsupported file type. Please upload CSV, XLSX, or JSON."
        )
    file_type = EXT_TO_TYPE[ext]

    base = (content_type or "").split(";", 1)[0].strip().lower()
    if base:
        ok_for_this = CONTENT_TYPE_OK[file_type]
        if base not in ok_for_this:
            # If it matches a *different* type, the extension/content-type
            # disagree; otherwise it is an unknown type we still accept.
            for other, accepted in CONTENT_TYPE_OK.items():
                if other != file_type and base in accepted:
                    raise UnsupportedFileTypeError(
                        "The file content type (%s) does not match its extension (.%s)."
                        % (base or "unknown", file_type)
                    )
    return file_type


def verify_magic_bytes(file_type: str, data: bytes) -> None:
    """Cheap content checks that catch mislabeled files before full parsing."""
    if file_type == "xlsx":
        if not data[:2] == b"PK":
            raise ParseError("The file is not a valid XLSX workbook (missing ZIP header).")
    elif file_type == "json":
        stripped = data.lstrip(b"\xef\xbb\xbf \t\r\n")
        if not stripped or stripped[:1] not in (b"{", b"["):
            raise ParseError("The file is not valid JSON: expected an array or object.")
    elif file_type == "csv":
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ParseError("The CSV file is not valid UTF-8.")


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

_CSV_DELIMITERS = (",", ";", "\t", "|")


def parse_csv(path: Path) -> dict:
    """Parse a CSV file (UTF-8, optional BOM, common delimiters, quoted
    fields, commas inside quotes). The first non-empty row is the header."""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise ParseError("Could not read the uploaded file: %s" % exc)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ParseError("The CSV file is not valid UTF-8.")

    lines = text.splitlines()
    if not lines:
        raise EmptyDatasetError("The CSV file is empty.")

    # Sniff delimiter from the first non-empty line.
    first = next((ln for ln in lines if ln.strip()), "")
    delimiter = ","
    best = -1
    for candidate in _CSV_DELIMITERS:
        count = first.count(candidate)
        if count > best:
            best, delimiter = count, candidate

    # A single unbalanced double-quote is the most common sign of a truncated
    # or otherwise corrupted CSV (the csv module silently tolerates it).
    if text.count('"') % 2 != 0:
        raise ParseError(
            "Could not parse the CSV file: unterminated quoted field."
        )

    try:
        reader = csv.reader(lines, delimiter=delimiter)
        rows = [row for row in reader if any(cell.strip() for cell in row)]
    except csv.Error as exc:
        raise ParseError("Could not parse the CSV file: %s" % exc)

    if not rows:
        raise EmptyDatasetError("The CSV file contains no data rows.")
    return _rows_to_records(rows, "CSV")


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


def parse_json(path: Path) -> dict:
    """Parse a JSON dataset: either a top-level array of records or an object
    wrapping a record array under a key such as ``data``/``records``/``rows``."""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise ParseError("Could not read the uploaded file: %s" % exc)
    try:
        parsed = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ParseError("The JSON file could not be parsed: %s" % exc)

    records = None
    if isinstance(parsed, list):
        records = parsed
    elif isinstance(parsed, dict):
        for key in JSON_WRAPPER_KEYS:
            if isinstance(parsed.get(key), list):
                records = parsed[key]
                break
        if records is None:
            # A single record object (all scalar values) is accepted as one row.
            if all(not isinstance(v, (list, dict)) for v in parsed.values()):
                records = [parsed]
            else:
                raise ParseError(
                    "The JSON structure was not recognized: expected an array of "
                    "records or an object wrapping a record array (e.g. {\"data\": [...]})."
                )
    else:
        raise ParseError(
            "The JSON structure was not recognized: expected an array of records "
            "or an object wrapping a record array."
        )

    if not records:
        raise EmptyDatasetError("The JSON dataset contains no records.")

    if all(isinstance(r, dict) for r in records):
        headers = []
        for record in records:
            for key in record:
                if key not in headers:
                    headers.append(str(key))
        rows = [
            ["" if key not in record else _scalar(record[key]) for key in headers]
            for record in records
        ]
        return {"headers": headers, "rows": rows, "sheets": [], "warnings": []}

    if all(isinstance(r, (list, tuple)) for r in records):
        width = max((len(r) for r in records), default=0)
        headers = ["column_%d" % (i + 1) for i in range(width)]
        rows = [[_scalar(cell) for cell in r] for r in records]
        return {"headers": headers, "rows": rows, "sheets": [], "warnings": []}

    raise ParseError(
        "The JSON records are inconsistent: mix of objects and arrays."
    )


def _scalar(value):
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if value is None:
        return ""
    return value


# ---------------------------------------------------------------------------
# XLSX (minimal stdlib reader)
# ---------------------------------------------------------------------------


def parse_xlsx(path: Path, sheet: Optional[str] = None) -> dict:
    """Parse an XLSX workbook.

    ``sheet`` may be a sheet name or a 1-based index; defaults to the first
    worksheet. Returns headers, rows, and the list of available sheet names so
    the UI can let the user pick one when the file has several.
    """
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise ParseError("Could not read the uploaded file: %s" % exc)
    if not raw[:2] == b"PK":
        raise ParseError("The file is not a valid XLSX workbook (missing ZIP header).")
    try:
        archive = zipfile.ZipFile(Path(path))
    except zipfile.BadZipFile:
        raise ParseError("The file is not a valid XLSX workbook (corrupt ZIP).")

    warnings = []
    try:
        sheets = _sheet_names(archive)
        if not sheets:
            raise ParseError("The XLSX workbook contains no worksheets.")
        sheet_target = _resolve_sheet(archive, sheets, sheet, warnings)
        shared = _shared_strings(archive)
        rows = _sheet_rows(archive, sheet_target, shared)
    except ParseError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ParseError("Could not read the XLSX workbook: %s" % exc)
    finally:
        archive.close()

    if not rows:
        raise EmptyDatasetError("The selected worksheet contains no data.")
    return _rows_to_records(rows, "XLSX", extra={"sheets": sheets, "warnings": warnings})


def _sheet_names(archive: zipfile.ZipFile) -> list:
    """Sheet display names in workbook order."""
    try:
        root = ET.fromstring(archive.read("xl/workbook.xml"))
    except KeyError:
        raise ParseError("The XLSX workbook is missing xl/workbook.xml.")
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
          "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    names = []
    for sheet in root.findall(".//m:sheets/m:sheet", ns):
        name = sheet.get("name")
        if name:
            names.append(name)
    return names


def _resolve_sheet(archive, sheets, requested, warnings) -> str:
    """Return the worksheet XML path for the requested sheet (name or index)."""
    if requested is None:
        index = 0
    elif isinstance(requested, int):
        index = requested - 1 if requested >= 1 else 0
    else:
        lowered = {name.lower(): i for i, name in enumerate(sheets)}
        if requested.lower() not in lowered:
            raise ParseError(
                "Worksheet '%s' not found. Available sheets: %s"
                % (requested, ", ".join(sheets))
            )
        index = lowered[requested.lower()]

    if index < 0 or index >= len(sheets):
        raise ParseError(
            "Worksheet index %s is out of range (available sheets: %s)"
            % (index + 1, ", ".join(sheets))
        )
    if len(sheets) > 1 and requested is None:
        warnings.append(
            "The workbook has %d worksheets (%s); using the first. Select a sheet "
            "to import another." % (len(sheets), ", ".join(sheets))
        )

    # Map workbook r:id -> worksheet target via xl/_rels/workbook.xml.rels.
    rels = {}
    try:
        rel_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
        for rel in rel_root.findall(".//r:Relationship", ns):
            rid = rel.get("Id")
            target = rel.get("Target")
            if rid and target:
                rels[rid] = target.lstrip("/")
    except (KeyError, ET.ParseError):
        rels = {}

    try:
        wb_root = ET.fromstring(archive.read("xl/workbook.xml"))
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
              "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
        sheet_els = wb_root.findall(".//m:sheets/m:sheet", ns)
    except (KeyError, ET.ParseError):
        sheet_els = []

    if index < len(sheet_els):
        rid = sheet_els[index].get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        if rid and rid in rels:
            target = rels[rid]
            if not target.startswith("xl/"):
                target = "xl/" + target
            return target

    # Fallback to the conventional worksheets/sheetN.xml layout.
    return "xl/worksheets/sheet%d.xml" % (index + 1)


def _shared_strings(archive: zipfile.ZipFile) -> list:
    """Shared strings table: concatenated <t> text per <si> entry."""
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except (KeyError, ET.ParseError):
        return []
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings = []
    for si in root.findall(".//m:si", ns):
        parts = []
        for t in si.findall(".//m:t", ns):
            if t.text:
                parts.append(t.text)
        strings.append("".join(parts))
    return strings


def _sheet_rows(archive: zipfile.ZipFile, sheet_target: str, shared: list) -> list:
    """Parse a worksheet into a list of rows (each a list of cell values)."""
    try:
        root = ET.fromstring(archive.read(sheet_target))
    except KeyError:
        raise ParseError("The XLSX workbook is missing %s." % sheet_target)
    except ET.ParseError as exc:
        raise ParseError("The XLSX worksheet could not be read: %s" % exc)

    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows = []
    for row_el in root.findall(".//m:sheetData/m:row", ns):
        cells = {}
        max_col = -1
        for cell in row_el.findall("m:c", ns):
            ref = cell.get("r", "")
            col = _column_index(ref)
            if col is None:
                continue
            max_col = max(max_col, col)
            value = _cell_value(cell, ns, shared)
            if value != "":
                cells[col] = value
        row = [cells.get(i, "") for i in range(max_col + 1)]
        rows.append(row)
    return rows


def _cell_value(cell, ns, shared: list) -> str:
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        parts = []
        for t in cell.findall(".//m:t", ns):
            if t.text:
                parts.append(t.text)
        return "".join(parts)
    v_el = cell.find("m:v", ns)
    raw = v_el.text if v_el is not None and v_el.text is not None else ""
    if cell_type == "s":
        index = int(raw) if raw.isdigit() else -1
        if 0 <= index < len(shared):
            return shared[index]
        return ""
    if cell_type == "b":
        return "TRUE" if raw == "1" else "FALSE"
    return raw


def _column_index(ref: str) -> Optional[int]:
    """'A' -> 0, 'B' -> 1, ..., 'AA' -> 26; None for empty refs."""
    letters = "".join(ch for ch in ref if ch.isalpha())
    if not letters:
        return None
    index = 0
    for ch in letters.upper():
        index = index * 26 + (ord(ch) - ord("A") + 1)
    return index - 1


# ---------------------------------------------------------------------------
# Shared row/header normalization
# ---------------------------------------------------------------------------


def _rows_to_records(rows: list, label: str, extra: Optional[dict] = None) -> dict:
    """First non-empty row becomes the header; rows are padded to the header
    length. Returns the uniform parser output dict."""
    header = [str(cell).strip() for cell in rows[0]]
    body = rows[1:]
    warnings = list((extra or {}).get("warnings", []))
    for i, name in enumerate(header):
        if not name:
            warnings.append("Column %d has no header name; it will be ignored." % (i + 1))
    for i, name in enumerate(header):
        if header.count(name) > 1 and name:
            warnings.append("Duplicate column name %r; only the first is used." % name)
            break

    width = len(header)
    normalized = []
    for row in body:
        if len(row) > width:
            warnings.append(
                "Row %d has more cells than the header; extra cells ignored." % (len(normalized) + 2)
            )
            row = row[:width]
        normalized.append(["" if cell is None else cell for cell in row] + [""] * (width - len(row)))

    if not normalized:
        raise EmptyDatasetError("The %s file contains no data rows." % label)
    return {"headers": header, "rows": normalized, "sheets": list(extra.get("sheets", [])) if extra else [], "warnings": warnings}


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def parse_file(path, file_type: str, sheet: Optional[str] = None) -> dict:
    """Parse a file by its detected type (``csv``/``xlsx``/``json``)."""
    if file_type == "csv":
        return parse_csv(path)
    if file_type == "json":
        return parse_json(path)
    if file_type == "xlsx":
        return parse_xlsx(path, sheet=sheet)
    raise UnsupportedFileTypeError(
        "Unsupported file type. Please upload CSV, XLSX, or JSON."
    )
