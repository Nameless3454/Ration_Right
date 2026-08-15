"""RationRight — record validation and normalization (Phase 3 + Phase 4).

The normalization layer between uploaded datasets and the database:

    Raw Record -> Column Mapping -> Type Conversion -> Value Normalization
                -> Business Validation -> Normalized Record

Principles
----------
- External datasets differ; RationAI stores ONE consistent internal format.
- String fields are trimmed and whitespace-collapsed; geographic text fields
  (state/district/block/name/location) are title-cased for consistency.
- Commodities map through a configurable alias table to a canonical key
  (lowercase, matching the Phase 1 demo dataset's internal format). Unknown
  commodities are reported as warnings, never silently guessed.
- Units normalize ``kg``-family values to ``kg``; other units are kept with a
  warning.
- Dates support ISO-8601, ``YYYY/MM/DD``, ``DD-MM-YYYY``, ``DD/MM/YYYY``,
  month-name formats, and Excel serial numbers. Ambiguous ``DD/MM`` dates are
  flagged (interpreted as DD/MM) instead of being silently assumed; impossible
  dates are rejected.
- Numbers handle ``1,200`` and ``1200 kg``; invalid text is an error, never
  silently converted to zero.
- Warnings do not block import; errors do.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from ingestion import mapping

# Excel serial-date epoch for the 1900 date system.
EXCEL_EPOCH = datetime(1899, 12, 30)
_EXCEL_MAX_SERIAL = 2958465  # 9999-12-31

_NUMBER_CLEAN = re.compile(r"^[+-]?\d+(?:[.,]\d+)?$")

# ---------------------------------------------------------------------------
# Commodity normalization (configurable alias table).
# Canonical values are lowercase keys that match the Phase 1 dataset's
# internal format ("rice", "wheat", "sugar", "kerosene", ...) plus the
# Phase 4 additions "pulses" and "oil".
# ---------------------------------------------------------------------------

COMMODITY_CANONICAL = ("rice", "wheat", "pulses", "sugar", "oil", "kerosene")

COMMODITY_LABELS = {
    "rice": "Rice", "wheat": "Wheat", "pulses": "Pulses",
    "sugar": "Sugar", "oil": "Oil", "kerosene": "Kerosene",
}

COMMODITY_ALIASES = {
    "rice": {"rice", "ricegrain", "rawrice", "parboiledrice", "basmati",
             "basmaticommon", "ricegrain", "grains"},
    "wheat": {"wheat", "wholewheat", "wheataata", "atta", "gehu"},
    "pulses": {"pulses", "pulse", "dal", "dals", "lentils", "lentil", "grams",
               "pulsesgrain", "toor", "moong", "chana", "arhar", "tur"},
    "sugar": {"sugar", "sugargrain", "gur", "shakkar", "sakkhar"},
    "oil": {"oil", "cookingoil", "edibleoil", "mustardoil", "groundnutoil",
            "palmoil", "vanaspati", "refinedoil"},
    "kerosene": {"kerosene", "kerosine", "kero", "skooil"},
}

UNIT_KG_ALIASES = {"kg", "kgs", "kilogram", "kilograms", "kilogramme",
                   "kilogrammes", "kilo", "kilos", "kilogrammes"}


def commodity_label(key) -> str:
    if not key:
        return ""
    return COMMODITY_LABELS.get(key, str(key))


def normalize_commodity(value):
    """Map a commodity spelling to its canonical key.

    Returns ``(canonical_key, changed, warning)`` where ``warning`` is None
    for known commodities. Unknown commodities keep the trimmed original with
    a warning — never silently guessed.
    """
    text = _collapse(to_text(value))
    if not text:
        return None, False, None
    normalized = re.sub(r"[^a-z0-9]", "", text.lower())
    for canonical, aliases in COMMODITY_ALIASES.items():
        if normalized in aliases:
            changed = canonical != text.lower()
            warning = None
            if changed:
                warning = (
                    "Commodity %r normalized to %r."
                    % (text, commodity_label(canonical))
                )
            return canonical, changed, warning
    return text, False, (
        "Unrecognized commodity %r; kept as-is." % text
    )


def normalize_unit(value):
    """Normalize kg-family units to ``kg``. Returns (unit, changed, warning)."""
    text = _collapse(to_text(value)).lower()
    if not text:
        return None, False, None
    if text in UNIT_KG_ALIASES:
        return "kg", text != "kg", None
    return text, False, "Unrecognized unit %r; kept as-is." % to_text(value)


# ---------------------------------------------------------------------------
# String normalization
# ---------------------------------------------------------------------------

_SMALL_WORDS = {"of", "and", "the", "at", "in", "for", "on", "a"}


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _title_case(text: str) -> str:
    words = []
    for word in text.split(" "):
        if word and word.lower() not in _SMALL_WORDS:
            words.append(word[:1].upper() + word[1:].lower())
        else:
            words.append(word.lower())
    return " ".join(words)


def normalize_string(value, title: bool = False):
    """Trim/collapse whitespace; optionally title-case geographic text.

    Returns ``(normalized, changed, warning)``. Case is NOT altered where it
    may carry meaning (IDs, codes, categories) unless ``title=True``.
    All-caps short values (len <= 3, e.g. state codes like ``UP``) are
    treated as abbreviations and left untouched — title-casing them would
    destroy their meaning (``UP`` -> ``Up``).
    """
    text = _collapse(to_text(value))
    if not text:
        return None, bool(text), None
    if title and text != _title_case(text) and not _is_abbreviation(text):
        return _title_case(text), True, (
            "Value %r normalized to %r." % (to_text(value), _title_case(text))
        )
    changed = text != to_text(value)
    return text, changed, None


def _is_abbreviation(text: str) -> bool:
    return len(text) <= 3 and text.isupper()


# ---------------------------------------------------------------------------
# Value coercion
# ---------------------------------------------------------------------------


class ValidationError(Exception):
    """Raised when a row cannot be coerced at all (malformed record)."""


def to_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_number(value):
    """Parse a numeric cell: ints/floats, thousands separators, trailing
    units (``1200 kg``). Returns float or None — never guesses."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = to_text(value).lower().rstrip("s")
    for suffix in (" kg", "kg", " gm", "gm", " g", "g", " ltr", "ltr", " litre", "litre"):
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
            break
    text = text.replace(",", "").strip()
    if not _NUMBER_CLEAN.match(text):
        return None
    try:
        return float(text)
    except ValueError:
        return None


_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y",
                 "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y")


def parse_date_detailed(value):
    """Parse a date; returns ``(iso_value, warnings)``.

    Supports ISO-8601, YYYY/MM/DD, DD-MM-YYYY, DD/MM/YYYY, month-name
    formats, and Excel serial numbers. Slash/dash dates where both parts are
    <= 12 are flagged as ambiguous (interpreted as DD/MM) so the ambiguity is
    visible instead of silently assumed. Impossible dates return (None, [])."""
    if value is None or value == "":
        return None, []
    if isinstance(value, bool):
        return None, []
    if isinstance(value, (int, float)):
        serial = float(value)
        if not (1 <= serial <= _EXCEL_MAX_SERIAL):
            return None, ["Date serial %s is out of range." % value]
        day = EXCEL_EPOCH + timedelta(days=int(serial))
        return day.date().isoformat(), []

    text = _collapse(to_text(value))
    if not text:
        return None, []
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        iso = dt.isoformat(sep="T", timespec="seconds") if "T" in text else dt.date().isoformat()
        return iso, []
    except ValueError:
        pass

    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        warnings = []
        if fmt in ("%d/%m/%Y", "%d-%m-%Y") and parsed.month <= 12 and parsed.day <= 12:
            warnings.append(
                "Date %r is ambiguous; interpreted as DD/MM/YYYY (%s)."
                % (text, parsed.date().isoformat())
            )
        return parsed.date().isoformat(), warnings
    return None, ["Date %r is not a valid date." % to_text(value)]


def parse_date(value):
    """Backward-compatible wrapper returning just the ISO value or None."""
    iso, _ = parse_date_detailed(value)
    return iso


def parse_int(value):
    """Parse a positive integer (for family_size). Returns int or None."""
    number = parse_number(value)
    if number is None or number != int(number) or number <= 0:
        return None
    return int(number)


def normalize_status(value, dataset_type):
    """Uppercase and validate a status against the type's allowed set."""
    text = to_text(value).upper()
    if not text:
        return None, None
    allowed = mapping.STATUS_ALLOWED.get(dataset_type, ())
    if allowed and text not in allowed:
        return None, "status %r is not valid (allowed: %s)" % (to_text(value), ", ".join(allowed))
    return text, None


# ---------------------------------------------------------------------------
# Record validation
# ---------------------------------------------------------------------------

# Text fields passed through (trimmed/collapsed). Geographic names are
# title-cased; IDs/codes/categories keep their case.
_TITLE_TEXT_FIELDS = ("state", "district", "block", "name", "location")
_PLAIN_TEXT_FIELDS = (
    "external_reference", "fps_code", "external_transaction_id",
    "beneficiary_id", "fps_center_id", "ration_category",
)


def validate_record(record: dict, dataset_type: str):
    """Validate one mapped record.

    ``record`` maps internal field -> raw cell value. Returns
    ``(normalized_record, errors, warnings)``. ``normalized_record`` is None
    when there are errors (the record must not be imported). Warnings carry
    explicit normalization notes (e.g. ``District ' LUCKNOW ' -> 'Lucknow'``).
    """
    errors = []
    warnings = []
    normalized = {}

    for field in mapping.required_fields(dataset_type):
        if not to_text(record.get(field)):
            errors.append("missing required field %s" % mapping.field_label(field))

    # --- string fields ---
    for field in _TITLE_TEXT_FIELDS:
        raw = record.get(field)
        if raw is None or to_text(raw) == "":
            continue
        value, _, warning = normalize_string(raw, title=True)
        if value is not None:
            normalized[field] = value
        if warning:
            warnings.append(
                "%s %s" % (mapping.field_label(field), warning[0].lower() + warning[1:])
            )
    for field in _PLAIN_TEXT_FIELDS:
        raw = record.get(field)
        if raw is None or to_text(raw) == "":
            continue
        value, changed, warning = normalize_string(raw, title=False)
        if value is not None:
            normalized[field] = value
        if warning:
            warnings.append(
                "%s %s" % (mapping.field_label(field), warning[0].lower() + warning[1:])
            )

    # --- status ---
    if dataset_type in ("beneficiaries", "fps_centers", "ration_transactions", "combined"):
        status, status_error = normalize_status(record.get("status"), dataset_type)
        if status_error:
            errors.append(status_error)
        elif status is not None:
            normalized["status"] = status

    # --- commodity ---
    if dataset_type in ("ration_transactions", "inventory", "combined"):
        raw = record.get("commodity")
        if to_text(raw) == "":
            errors.append("missing required field Commodity")
        else:
            canonical, _, warning = normalize_commodity(raw)
            if canonical is None:
                errors.append("missing required field Commodity")
            else:
                normalized["commodity"] = canonical
                if warning:
                    warnings.append(warning)

    # --- unit ---
    raw_unit = record.get("unit")
    if raw_unit is not None and to_text(raw_unit) != "":
        unit, _, warning = normalize_unit(raw_unit)
        if unit is not None:
            normalized["unit"] = unit
        if warning:
            warnings.append(warning)

    # --- dates ---
    for field in ("transaction_date", "last_updated"):
        raw = record.get(field)
        if raw is None or to_text(raw) == "":
            continue
        parsed, date_warnings = parse_date_detailed(raw)
        if parsed is None:
            errors.append("%s %r is not a valid date" % (mapping.field_label(field), to_text(raw)))
        else:
            normalized[field] = parsed
            for warning in date_warnings:
                warnings.append(warning)
            if to_text(raw) != parsed and not any("ambiguous" in w for w in date_warnings):
                warnings.append("%s %r normalized to %r." % (
                    mapping.field_label(field), to_text(raw), parsed))

    # --- numbers ---
    for field, minimum in (
        ("quantity", 0.0), ("capacity", 0.0), ("current_stock", 0.0),
        ("monthly_consumption", 0.0), ("reorder_threshold", 0.0),
    ):
        raw = record.get(field)
        if raw is None or to_text(raw) == "":
            continue
        number = parse_number(raw)
        if number is None:
            errors.append("%s %r is not numeric" % (mapping.field_label(field), to_text(raw)))
        elif minimum == 0.0 and number <= 0:
            errors.append("%s must be a positive number, got %r" % (
                mapping.field_label(field), to_text(raw)))
        else:
            normalized[field] = number
            if to_text(raw).replace(" ", "").lower().endswith("kg") or "," in to_text(raw):
                warnings.append("%s %r normalized to %g." % (
                    mapping.field_label(field), to_text(raw), number))

    if dataset_type in ("ration_transactions", "combined"):
        if "quantity" in normalized and normalized["quantity"] <= 0:
            errors.append("quantity must be a positive number")

    # --- coordinates ---
    lat_raw = record.get("latitude")
    if lat_raw is not None and to_text(lat_raw) != "":
        lat = parse_number(lat_raw)
        if lat is None or not (-90 <= lat <= 90):
            errors.append("latitude %r is invalid (must be a number in [-90, 90])" % to_text(lat_raw))
        else:
            normalized["latitude"] = lat
    lon_raw = record.get("longitude")
    if lon_raw is not None and to_text(lon_raw) != "":
        lon = parse_number(lon_raw)
        if lon is None or not (-180 <= lon <= 180):
            errors.append("longitude %r is invalid (must be a number in [-180, 180])" % to_text(lon_raw))
        else:
            normalized["longitude"] = lon

    # --- family size ---
    fs_raw = record.get("family_size")
    if fs_raw is not None and to_text(fs_raw) != "":
        fs = parse_int(fs_raw)
        if fs is None:
            errors.append("family_size %r must be a positive integer" % to_text(fs_raw))
        else:
            normalized["family_size"] = fs

    if errors:
        return None, errors, warnings
    return normalized, [], warnings


def record_result(record: dict, dataset_type: str) -> dict:
    """Structured per-record validation result (Phase 4):

    ``{"status": "VALID"|"INVALID", "warnings": [...], "errors": [...],
       "normalized": {...}}`` — the errors/warnings are structured lists, not
    one text blob."""
    normalized, errors, warnings = validate_record(record, dataset_type)
    if errors:
        return {"status": "INVALID", "warnings": warnings, "errors": errors, "normalized": None}
    return {"status": "VALID", "warnings": warnings, "errors": [], "normalized": normalized}


def summarize(rows: list, dataset_type: str, headers: list, mapping_dict: dict):
    """Validate every row and aggregate counts.

    Returns totals, counts, example errors, example warnings, and a normalized
    preview (first valid records) so the UI can show original vs normalized
    data side by side."""
    total = len(rows)
    valid = 0
    invalid = 0
    warning_count = 0
    errors_examples = []
    warning_examples = []
    preview_normalized = []
    for row_number, row in enumerate(rows, start=2):  # 1 is the header
        record = _record_from_row(row, headers, mapping_dict)
        normalized, errors, warnings = validate_record(record, dataset_type)
        warning_count += len(warnings)
        if errors:
            invalid += 1
            if len(errors_examples) < 10:
                errors_examples.append({
                    "row": row_number,
                    "errors": errors[:3],
                    "values": {k: v for k, v in record.items() if v not in (None, "")},
                })
        else:
            valid += 1
            if len(preview_normalized) < 10:
                preview_normalized.append({
                    "row": row_number,
                    "status": "VALID",
                    "warnings": warnings,
                    "original": {
                        k: v for k, v in record.items() if v not in (None, "")
                    },
                    "normalized": normalized,
                })
        if warnings and len(warning_examples) < 10:
            warning_examples.append({"row": row_number, "warnings": warnings[:3]})
    return {
        "total_records": total,
        "valid_records": valid,
        "invalid_records": invalid,
        "warning_count": warning_count,
        "errors": errors_examples,
        "warnings": warning_examples,
        "preview_normalized": preview_normalized,
    }


# ---------------------------------------------------------------------------
# Duplicate classification (Phase 4)
# ---------------------------------------------------------------------------


def classify_duplicates(rows: list, dataset_type: str, headers: list, mapping_dict: dict) -> dict:
    """Classify each record as UNIQUE / EXACT_DUPLICATE / POSSIBLE_DUPLICATE.

    - transactions with an ID: EXACT when the same external id recurs;
      POSSIBLE when a different id shares the same composite content
      (fps, date, commodity, quantity) — the same transaction recorded twice;
    - transactions without an ID: identical composite -> EXACT;
    - other types: identical natural key -> EXACT.

    Returns counts plus the first few samples for the error report."""
    exact_keys = set()
    composite_keys = set()
    counts = {"unique": 0, "exact": 0, "possible": 0}
    samples = []

    for row_number, row in enumerate(rows, start=2):
        record = _record_from_row(row, headers, mapping_dict)
        normalized, errors, _ = validate_record(record, dataset_type)
        if errors:
            continue
        if dataset_type in ("ration_transactions", "combined"):
            external_id = (normalized.get("external_transaction_id") or "").strip()
            composite = _composite_key(normalized)
            if external_id:
                exact_key = ("ext", external_id)
                if exact_key in exact_keys:
                    counts["exact"] += 1
                    _sample(samples, row_number, "EXACT_DUPLICATE",
                            "Transaction ID %r was already seen." % external_id)
                elif composite in composite_keys:
                    counts["possible"] += 1
                    _sample(samples, row_number, "POSSIBLE_DUPLICATE",
                            "Same content (%s) with a different transaction ID." % _composite_label(normalized))
                else:
                    counts["unique"] += 1
                    exact_keys.add(exact_key)
                    composite_keys.add(composite)
            else:
                if composite in composite_keys:
                    counts["exact"] += 1
                    _sample(samples, row_number, "EXACT_DUPLICATE",
                            "Identical record content (%s)." % _composite_label(normalized))
                else:
                    counts["unique"] += 1
                    composite_keys.add(composite)
        else:
            key = _natural_key(dataset_type, normalized)
            if key in exact_keys:
                counts["exact"] += 1
                _sample(samples, row_number, "EXACT_DUPLICATE",
                        "Duplicate of a record already seen in this dataset.")
            else:
                counts["unique"] += 1
                exact_keys.add(key)
    return {**counts, "samples": samples}


def _sample(samples: list, row: int, kind: str, reason: str) -> None:
    if len(samples) < 10:
        samples.append({"row": row, "kind": kind, "reason": reason})


def _composite_key(normalized: dict):
    return (
        (normalized.get("fps_center_id") or "").strip().lower(),
        (normalized.get("transaction_date") or "").strip(),
        (normalized.get("commodity") or "").strip().lower(),
        normalized.get("quantity"),
    )


def _composite_label(normalized: dict) -> str:
    return "fps=%s date=%s commodity=%s qty=%s" % (
        normalized.get("fps_center_id") or "-",
        normalized.get("transaction_date") or "-",
        commodity_label(normalized.get("commodity")) or "-",
        normalized.get("quantity") or "-",
    )


def _natural_key(dataset_type: str, normalized: dict):
    if dataset_type in ("beneficiaries", "fps_centers"):
        return (normalized.get("external_reference") or normalized.get("fps_code") or "").strip().lower()
    if dataset_type == "inventory":
        return (
            (normalized.get("fps_center_id") or "").strip().lower(),
            (normalized.get("commodity") or "").strip().lower(),
        )
    return _composite_key(normalized)


# ---------------------------------------------------------------------------
# Data quality score (Phase 4)
# ---------------------------------------------------------------------------

# Transparent, deterministic formula (no AI): start at 100 and subtract
# penalties for invalid records (3x), duplicates (2x), and warnings (0.5x),
# each measured as a percentage of total records. Clamped to [0, 100].
QUALITY_WEIGHTS = {"invalid": 3.0, "duplicates": 2.0, "warnings": 0.5}


def quality_score(total: int, invalid: int, duplicates: int, warnings: int) -> float:
    """Deterministic 0-100 quality score. Formula documented in the module
    docstring and QUALITY_WEIGHTS."""
    if total <= 0:
        return 0.0
    invalid_pct = invalid / total * 100
    duplicate_pct = duplicates / total * 100
    warning_pct = warnings / total * 100
    score = 100.0 - (
        QUALITY_WEIGHTS["invalid"] * invalid_pct
        + QUALITY_WEIGHTS["duplicates"] * duplicate_pct
        + QUALITY_WEIGHTS["warnings"] * warning_pct
    )
    return round(max(0.0, min(100.0, score)), 1)


def quality_report(total: int, invalid: int, duplicates: int, warnings: int) -> dict:
    """Structured quality report with the breakdown lines shown in the UI."""
    if total <= 0:
        return {"score": 0.0, "valid_pct": 0.0, "duplicate_pct": 0.0, "warning_pct": 0.0}
    valid = total - invalid - duplicates
    return {
        "score": quality_score(total, invalid, duplicates, warnings),
        "valid_pct": round((valid / total) * 100, 1),
        "duplicate_pct": round(duplicates / total * 100, 1),
        "warning_pct": round(warnings / total * 100, 1),
        "invalid_pct": round(invalid / total * 100, 1),
    }


def _record_from_row(row, headers, mapping_dict: dict) -> dict:
    """Build an internal-field record from a raw row using the mapping."""
    record = {}
    for index, header in enumerate(headers):
        field = mapping_dict.get(header)
        if field:
            record[field] = row[index] if index < len(row) else ""
    return record
