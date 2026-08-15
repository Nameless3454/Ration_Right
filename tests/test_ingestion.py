"""RationRight — Phase 3: dataset ingestion tests.

Covers the full pipeline — parsers (CSV/JSON/XLSX), column mapping, record
validation, duplicate detection, database import states (COMPLETED/PARTIAL/
FAILED), large datasets, file security, the API flow (upload -> validate ->
confirm -> history), and preservation of the existing demo data.

Run from the project root::

    python3 -m unittest discover -s tests -t . -v
"""

import io
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import database as db
import ingestion.service as service
from ingestion import mapping as mapmod
from ingestion import validation
from ingestion.parsers import (
    EmptyDatasetError,
    ParseError,
    UnsupportedFileTypeError,
    parse_csv,
    parse_file,
    parse_json,
    parse_xlsx,
    sniff_file_type,
)
from server import make_server

BASE = "http://127.0.0.1"


# ---------------------------------------------------------------------------
# Test data builders
# ---------------------------------------------------------------------------

TRANSACTION_CSV = (
    "Transaction ID,Beneficiary ID,FPS Code,Transaction Date,Commodity,Quantity,Unit\n"
    "TX1001,BEN001,FPS01,2026-08-01,rice,10,kg\n"
    "TX1002,BEN001,FPS01,2026-08-02,rice,5,kg\n"
    "TX1003,BEN002,FPS02,2026-08-01,wheat,8,kg\n"
)

TRANSACTION_CSV_QUOTED = (
    'id,beneficiary,commodity,"quantity, kg",date\n'
    "T1,BEN1,\"rice, basmati\",\"1,200\",2026-08-01\n"
    "T2,BEN2,wheat,840,2026-08-02\n"
)

BENEFICIARY_CSV = (
    "Beneficiary ID,State,District,Ration Category,Family Size,Status\n"
    "BEN101,Maharashtra,Pune,AAY,4,ACTIVE\n"
    "BEN102,Maharashtra,Nagpur,PHH,3,ACTIVE\n"
)

FPS_CSV = (
    "FPS Code,Name,District,State,Capacity\n"
    "FPS01,Kanpur Center #04,Kanpur,UP,5000\n"
    "FPS02,Lucknow Center #11,Lucknow,UP,4200\n"
)

INVENTORY_CSV = (
    "FPS Code,Commodity,Current Stock,Monthly Consumption,Reorder Threshold\n"
    "FPS01,rice,1200,300,200\n"
    "FPS01,wheat,800,250,150\n"
)

COMBINED_CSV = (
    "Transaction ID,Beneficiary ID,State,District,FPS Code,Transaction Date,Commodity,Quantity\n"
    "C1,BEN201,UP,Lucknow,FPS01,2026-08-01,rice,10\n"
    "C2,BEN201,UP,Lucknow,FPS01,2026-08-03,wheat,5\n"
)


def write_temp(data: bytes, suffix: str) -> Path:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    return Path(path)


def _col_letter(index: int) -> str:
    out = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        out = chr(65 + remainder) + out
    return out


def _cell_xml(ref: str, value):
    if isinstance(value, bool):
        return '<c r="%s" t="b"><v>%d</v></c>' % (ref, 1 if value else 0)
    if isinstance(value, (int, float)):
        return '<c r="%s"><v>%s</v></c>' % (ref, value)
    return '<c r="%s" t="inlineStr"><is><t>%s</t></is></c>' % (ref, value)


def build_xlsx(sheets):
    """Build a minimal XLSX in memory. ``sheets`` = [(name, [rows...]), ...]."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        sheet_count = len(sheets)
        overrides = "".join(
            '<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            % (i + 1) for i in range(sheet_count)
        )
        z.writestr("[Content_Types].xml", (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            + overrides + "</Types>"
        ))
        z.writestr("_rels/.rels", (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>"
        ))
        sheets_xml = "".join(
            '<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (name, i + 1, i + 1)
            for i, (name, _) in enumerate(sheets)
        )
        z.writestr("xl/workbook.xml", (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            "<sheets>" + sheets_xml + "</sheets></workbook>"
        ))
        rels = "".join(
            '<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>'
            % (i + 1, i + 1) for i in range(sheet_count)
        )
        z.writestr("xl/_rels/workbook.xml.rels", (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + rels + "</Relationships>"
        ))
        for i, (_, rows) in enumerate(sheets):
            sheet_data = ""
            for r_idx, row in enumerate(rows, start=1):
                cells = "".join(
                    _cell_xml(_col_letter(c), value)
                    for c, value in enumerate(row)
                )
                sheet_data += '<row r="%d">%s</row>' % (r_idx, cells)
            z.writestr("xl/worksheets/sheet%d.xml" % (i + 1), (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                "<sheetData>" + sheet_data + "</sheetData></worksheet>"
            ))
    return buf.getvalue()


def build_xlsx_shared_strings(rows):
    """XLSX using the shared-strings table (the common Excel export layout)."""
    strings = []
    for row in rows:
        for value in row:
            if isinstance(value, str) and value not in strings:
                strings.append(value)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
            "</Types>"
        ))
        z.writestr("_rels/.rels", (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>"
        ))
        z.writestr("xl/workbook.xml", (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Data" sheetId="1" r:id="rId1"/></sheets></workbook>'
        ))
        z.writestr("xl/_rels/workbook.xml.rels", (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>"
        ))
        sst = "".join("<si><t>%s</t></si>" % s for s in strings)
        z.writestr("xl/sharedStrings.xml", (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="%d" uniqueCount="%d">%s</sst>'
            % (len(strings), len(strings), sst)
        ))
        sheet_data = ""
        for r_idx, row in enumerate(rows, start=1):
            cells = ""
            for c, value in enumerate(row):
                ref = _col_letter(c) + str(r_idx)
                if isinstance(value, str):
                    idx = strings.index(value)
                    cells += '<c r="%s" t="s"><v>%d</v></c>' % (ref, idx)
                else:
                    cells += '<c r="%s"><v>%s</v></c>' % (ref, value)
            sheet_data += '<row r="%d">%s</row>' % (r_idx, cells)
        z.writestr("xl/worksheets/sheet1.xml", (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<sheetData>" + sheet_data + "</sheetData></worksheet>"
        ))
    return buf.getvalue()


def cleanup_upload(token):
    if token:
        service._drop_entry(token)


# ---------------------------------------------------------------------------
# 1. Parsers
# ---------------------------------------------------------------------------


class TestParsers(unittest.TestCase):
    def test_valid_csv(self):
        path = write_temp(TRANSACTION_CSV.encode("utf-8"), ".csv")
        parsed = parse_csv(path)
        self.assertEqual(parsed["headers"], ["Transaction ID", "Beneficiary ID", "FPS Code", "Transaction Date", "Commodity", "Quantity", "Unit"])
        self.assertEqual(len(parsed["rows"]), 3)

    def test_csv_quoted_fields_commas_utf8(self):
        path = write_temp(TRANSACTION_CSV_QUOTED.encode("utf-8"), ".csv")
        parsed = parse_csv(path)
        self.assertEqual(parsed["rows"][0], ["T1", "BEN1", "rice, basmati", "1,200", "2026-08-01"])
        # semicolon delimiter + BOM
        semicolon = "\ufeffDate;Quantity;Commodity\n2026-08-01;10;rice\n".encode("utf-8")
        path2 = write_temp(semicolon, ".csv")
        parsed2 = parse_csv(path2)
        self.assertEqual(parsed2["headers"], ["Date", "Quantity", "Commodity"])
        self.assertEqual(parsed2["rows"][0], ["2026-08-01", "10", "rice"])

    def test_invalid_csv(self):
        path = write_temp(b'id,qty\n"unterminated,10\n', ".csv")
        with self.assertRaises(ParseError):
            parse_csv(path)

    def test_empty_csv(self):
        path = write_temp(b"id,qty\n", ".csv")
        with self.assertRaises(EmptyDatasetError):
            parse_csv(path)

    def test_valid_json_array_and_wrapped(self):
        path = write_temp(json.dumps([
            {"fps_code": "UP-001", "district": "Lucknow", "commodity": "Rice", "quantity": 120},
            {"fps_code": "UP-002", "district": "Kanpur", "commodity": "Wheat", "quantity": 80},
        ]).encode("utf-8"), ".json")
        parsed = parse_json(path)
        self.assertEqual(parsed["headers"], ["fps_code", "district", "commodity", "quantity"])
        self.assertEqual(len(parsed["rows"]), 2)

        wrapped = write_temp(json.dumps({"data": [
            {"fps_code": "UP-001", "quantity": 10},
            {"fps_code": "UP-002", "quantity": 20},
        ]}).encode("utf-8"), ".json")
        parsed2 = parse_json(wrapped)
        self.assertEqual(len(parsed2["rows"]), 2)

    def test_invalid_json(self):
        path = write_temp(b"{not json", ".json")
        with self.assertRaises(ParseError):
            parse_json(path)

    def test_unrecognized_json_structure(self):
        path = write_temp(json.dumps({"nested": {"a": [1, 2]}}).encode("utf-8"), ".json")
        with self.assertRaises(ParseError):
            parse_json(path)

    def test_valid_xlsx_inline_strings(self):
        rows = [["Transaction ID", "Commodity", "Quantity"],
                ["T1", "rice", 10],
                ["T2", "wheat", 5]]
        path = write_temp(build_xlsx([("Transactions", rows)]), ".xlsx")
        parsed = parse_xlsx(path)
        self.assertEqual(parsed["headers"], ["Transaction ID", "Commodity", "Quantity"])
        self.assertEqual(parsed["rows"], [["T1", "rice", "10"], ["T2", "wheat", "5"]])
        self.assertEqual(parsed["sheets"], ["Transactions"])

    def test_valid_xlsx_shared_strings(self):
        rows = [["Commodity", "Quantity"], ["Rice", 100], ["Wheat", 50]]
        path = write_temp(build_xlsx_shared_strings(rows), ".xlsx")
        parsed = parse_xlsx(path)
        self.assertEqual(parsed["headers"], ["Commodity", "Quantity"])
        self.assertEqual(parsed["rows"], [["Rice", "100"], ["Wheat", "50"]])

    def test_xlsx_multiple_sheets_and_selection(self):
        data = [
            ("Transactions", [["Transaction ID", "Quantity"], ["T1", 10]]),
            ("Inventory", [["Commodity", "Current Stock"], ["rice", 500]]),
            ("Beneficiaries", [["Beneficiary ID"], ["B1"]]),
        ]
        path = write_temp(build_xlsx(data), ".xlsx")
        parsed = parse_xlsx(path)
        self.assertEqual(parsed["sheets"], ["Transactions", "Inventory", "Beneficiaries"])
        self.assertEqual(parsed["headers"], ["Transaction ID", "Quantity"])
        picked = parse_xlsx(path, sheet="Inventory")
        self.assertEqual(picked["headers"], ["Commodity", "Current Stock"])
        picked2 = parse_xlsx(path, sheet=3)  # 1-based: 1=Transactions, 2=Inventory, 3=Beneficiaries
        self.assertEqual(picked2["headers"], ["Beneficiary ID"])
        with self.assertRaises(ParseError):
            parse_xlsx(path, sheet="Missing")

    def test_invalid_xlsx(self):
        path = write_temp(b"this is not a zip file", ".xlsx")
        with self.assertRaises(ParseError):
            parse_xlsx(path)

    def test_empty_xlsx(self):
        path = write_temp(build_xlsx([("Empty", [["A"]] )]), ".xlsx")
        # header only, no data rows
        path = write_temp(build_xlsx([("Empty", [["A"]])]), ".xlsx")
        with self.assertRaises(EmptyDatasetError):
            parse_xlsx(path)

    def test_sniff_file_type(self):
        self.assertEqual(sniff_file_type("data.csv", "text/csv"), "csv")
        self.assertEqual(sniff_file_type("data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"), "xlsx")
        self.assertEqual(sniff_file_type("data.json", "application/json"), "json")
        with self.assertRaises(UnsupportedFileTypeError):
            sniff_file_type("data.txt", "text/plain")
        with self.assertRaises(UnsupportedFileTypeError):
            sniff_file_type("data.csv", "application/json")  # content type mismatch

    def test_parse_file_dispatch(self):
        path = write_temp(TRANSACTION_CSV.encode("utf-8"), ".csv")
        parsed = parse_file(path, "csv")
        self.assertEqual(len(parsed["rows"]), 3)
        with self.assertRaises(UnsupportedFileTypeError):
            parse_file(path, "pdf")


# ---------------------------------------------------------------------------
# 2. Mapping
# ---------------------------------------------------------------------------


class TestMapping(unittest.TestCase):
    def test_normalize_header(self):
        self.assertEqual(mapmod.normalize_header("District Name"), "districtname")
        self.assertEqual(mapmod.normalize_header("Qty Distributed"), "qtydistributed")

    def test_auto_mapping_aliases(self):
        headers = ["FPS Code", "District Name", "Commodity", "Quantity Distributed", "Transaction Date"]
        result = mapmod.detect_mapping(headers, "ration_transactions")
        by_external = {m["external"]: m["internal"] for m in result["mapping"]}
        self.assertEqual(by_external["FPS Code"], "fps_center_id")
        self.assertEqual(by_external["District Name"], "district")
        self.assertEqual(by_external["Commodity"], "commodity")
        self.assertEqual(by_external["Quantity Distributed"], "quantity")
        self.assertEqual(by_external["Transaction Date"], "transaction_date")

    def test_missing_required_reported(self):
        result = mapmod.detect_mapping(["Commodity", "Quantity"], "ration_transactions")
        self.assertIn("transaction_date", result["missing_required"])

    def test_validate_mapping_rejects_duplicates_and_unknown(self):
        ok = mapmod.validate_mapping(
            [{"external": "A", "internal": "fps_center_id"},
             {"external": "B", "internal": "commodity"},
             {"external": "C", "internal": "quantity"},
             {"external": "D", "internal": "transaction_date"}], "ration_transactions")
        self.assertEqual(ok, [])
        with self.assertRaises(mapmod.MappingError):
            mapmod.validate_mapping(
                [{"external": "A", "internal": "fps_center_id"},
                 {"external": "B", "internal": "commodity"},
                 {"external": "C", "internal": "commodity"},
                 {"external": "D", "internal": "quantity"},
                 {"external": "E", "internal": "transaction_date"}], "ration_transactions")
        with self.assertRaises(mapmod.MappingError):
            mapmod.validate_mapping([{"external": "A", "internal": "not_a_field"}], "ration_transactions")

    def test_infer_dataset_type(self):
        self.assertEqual(mapmod.infer_dataset_type(["FPS Code", "Commodity", "Quantity", "Date"]), "ration_transactions")
        self.assertEqual(mapmod.infer_dataset_type(["FPS Code", "Name", "District"]), "fps_centers")
        self.assertEqual(mapmod.infer_dataset_type(["Beneficiary ID", "State", "Family Size"]), "beneficiaries")
        self.assertEqual(mapmod.infer_dataset_type(["FPS Code", "Commodity", "Current Stock"]), "inventory")


# ---------------------------------------------------------------------------
# 3. Validation
# ---------------------------------------------------------------------------


class TestValidation(unittest.TestCase):
    def test_quantity_with_commas_and_units(self):
        self.assertEqual(validation.parse_number("1,200"), 1200.0)
        self.assertEqual(validation.parse_number("1200 kg"), 1200.0)
        self.assertEqual(validation.parse_number(42), 42.0)
        self.assertIsNone(validation.parse_number("abc"))

    def test_dates_iso_and_excel_serial(self):
        self.assertEqual(validation.parse_date("2026-08-01"), "2026-08-01")
        self.assertEqual(validation.parse_date("2026/08/01"), "2026-08-01")
        self.assertEqual(validation.parse_date("01/08/2026"), "2026-08-01")
        self.assertEqual(validation.parse_date("2026-08-01T10:00:00"), "2026-08-01T10:00:00")
        self.assertEqual(validation.parse_date(45200), "2023-10-01")
        self.assertIsNone(validation.parse_date("not-a-date"))
        self.assertIsNone(validation.parse_date(99999999))

    def test_validate_transaction_record(self):
        good = {"external_transaction_id": "T1", "beneficiary_id": "B1",
                "fps_center_id": "FPS01", "transaction_date": "2026-08-01",
                "commodity": "rice", "quantity": "10"}
        normalized, errors, _ = validation.validate_record(good, "ration_transactions")
        self.assertEqual(errors, [])
        self.assertEqual(normalized["quantity"], 10.0)
        self.assertNotIn("status", normalized)  # absent status is left unset (defaults later)

        bad_qty = dict(good, quantity="abc")
        _, errors, _ = validation.validate_record(bad_qty, "ration_transactions")
        self.assertTrue(any("not numeric" in e for e in errors))

        bad_date = dict(good, transaction_date="31-13-2020")
        _, errors, _ = validation.validate_record(bad_date, "ration_transactions")
        self.assertTrue(any("not a valid date" in e for e in errors))

        missing = {k: v for k, v in good.items() if k != "quantity"}
        _, errors, _ = validation.validate_record(missing, "ration_transactions")
        self.assertTrue(any("missing required" in e for e in errors))

    def test_status_validation(self):
        rec = {"fps_center_id": "FPS01", "transaction_date": "2026-08-01",
               "commodity": "rice", "quantity": 1, "status": "REFUNDED"}
        _, errors, _ = validation.validate_record(rec, "ration_transactions")
        self.assertTrue(any("status" in e for e in errors))
        rec2 = dict(rec, status="cancelled")
        normalized, errors, _ = validation.validate_record(rec2, "ration_transactions")
        self.assertEqual(errors, [])
        self.assertEqual(normalized["status"], "CANCELLED")


# ---------------------------------------------------------------------------
# 3b. Phase 4 — normalization & quality (column/string/commodity/date/number/
# unit normalization, required-field & business validation, structured
# warnings/errors, duplicate classification, quality score)
# ---------------------------------------------------------------------------


class Phase4NormalizationTests(unittest.TestCase):
    # 1. Column normalization (extendable alias table)
    def test_column_name_normalization(self):
        fps_aliases = ["FPS Code", "FPS_ID", "FPS Id", "Fair Price Shop Code"]
        district_aliases = ["District", "District Name", "District_Name"]
        qty_aliases = ["Qty", "Quantity", "Quantity Distributed", "Qty Distributed"]
        date_aliases = ["Date", "Transaction Date", "Transaction_Date"]
        for header in fps_aliases:
            mapping = mapmod.detect_mapping([header], "ration_transactions")
            self.assertEqual(mapping["mapping"][0]["internal"], "fps_center_id", header)
        for header in district_aliases:
            mapping = mapmod.detect_mapping([header], "ration_transactions")
            self.assertEqual(mapping["mapping"][0]["internal"], "district", header)
        for header in qty_aliases:
            mapping = mapmod.detect_mapping([header], "ration_transactions")
            self.assertEqual(mapping["mapping"][0]["internal"], "quantity", header)
        for header in date_aliases:
            mapping = mapmod.detect_mapping([header], "ration_transactions")
            self.assertEqual(mapping["mapping"][0]["internal"], "transaction_date", header)
        # each internal field is used at most once — a later alias for an
        # already-mapped field resolves to ignore
        mapping = mapmod.detect_mapping(["FPS Code", "FPS_ID"], "ration_transactions")
        internals = [m["internal"] for m in mapping["mapping"]]
        self.assertEqual(internals, ["fps_center_id", None])

    # 2. String normalization
    def test_string_normalization(self):
        self.assertEqual(validation.normalize_string(" Lucknow ")[0], "Lucknow")
        self.assertEqual(validation.normalize_string("LUCKNOW", title=True)[0], "Lucknow")
        self.assertEqual(validation.normalize_string("rice")[0], "rice")  # case kept for non-geo
        self.assertEqual(validation.normalize_string(""), (None, False, None))
        # abbreviations are preserved (state codes must not become "Up")
        self.assertEqual(validation.normalize_string("UP", title=True)[0], "UP")
        self.assertEqual(validation.normalize_string("   ")[0], None)

    # 3. Commodity normalization
    def test_commodity_normalization(self):
        for raw, expected in [("rice", "rice"), ("RICE", "rice"), ("Rice Grain", "rice"),
                              ("wheat", "wheat"), ("WHEAT", "wheat"), ("Pulses", "pulses"),
                              ("Sugar", "sugar"), ("Cooking Oil", "oil"), ("Kerosene", "kerosene")]:
            canonical, _, warning = validation.normalize_commodity(raw)
            self.assertEqual(canonical, expected, raw)
        # unknown commodities are warned, never silently mapped
        canonical, _, warning = validation.normalize_commodity("Biryani")
        self.assertEqual(canonical, "Biryani")
        self.assertIsNotNone(warning)

    # 4. Date normalization
    def test_date_normalization(self):
        for raw, expected in [("2026-08-01", "2026-08-01"), ("01-08-2026", "2026-08-01"),
                              ("08/01/2026", "2026-01-08"), ("01 Aug 2026", "2026-08-01"),
                              ("1 August 2026", "2026-08-01"), ("2026/08/01", "2026-08-01")]:
            self.assertEqual(validation.parse_date(raw), expected, raw)
        # ambiguous DD/MM dates are flagged, not silently assumed
        iso, warnings = validation.parse_date_detailed("01/02/2026")
        self.assertEqual(iso, "2026-02-01")
        self.assertTrue(any("ambiguous" in w for w in warnings))
        # impossible dates rejected
        self.assertIsNone(validation.parse_date("31-13-2020"))
        self.assertIsNone(validation.parse_date("45/99/2026"))

    # 5. Numeric normalization
    def test_numeric_normalization(self):
        self.assertEqual(validation.parse_number("1200"), 1200.0)
        self.assertEqual(validation.parse_number("1,200"), 1200.0)
        self.assertEqual(validation.parse_number("1200 kg"), 1200.0)
        self.assertIsNone(validation.parse_number("abc"))
        self.assertIsNone(validation.parse_number(""))

    # 6. Unit normalization
    def test_unit_normalization(self):
        for raw in ["kg", "KG", "kilogram", "kilograms", "Kgs"]:
            unit, _, warning = validation.normalize_unit(raw)
            self.assertEqual(unit, "kg", raw)
        unit, _, warning = validation.normalize_unit("litre")
        self.assertEqual(unit, "litre")
        self.assertIsNotNone(warning)  # kept as-is with a warning

    # 7. Required-field validation per dataset type
    def test_required_field_validation(self):
        tx = {"external_transaction_id": "T1", "fps_center_id": "FPS01",
              "transaction_date": "2026-08-01", "commodity": "rice", "quantity": 1}
        self.assertEqual(validation.validate_record(tx, "ration_transactions")[1], [])
        missing_fps = {k: v for k, v in tx.items() if k != "fps_center_id"}
        _, errors, _ = validation.validate_record(missing_fps, "ration_transactions")
        self.assertTrue(any("FPS Code (ref)" in e for e in errors))

        ben = {"external_reference": "B1", "district": "Lucknow",
               "family_size": 4, "ration_category": "AAY"}
        self.assertEqual(validation.validate_record(ben, "beneficiaries")[1], [])
        missing_cat = {k: v for k, v in ben.items() if k != "ration_category"}
        _, errors, _ = validation.validate_record(missing_cat, "beneficiaries")
        self.assertTrue(any("Ration Category" in e for e in errors))

        fps = {"fps_code": "FPS01", "district": "Kanpur"}
        self.assertEqual(validation.validate_record(fps, "fps_centers")[1], [])

        inv = {"fps_center_id": "FPS01", "commodity": "rice", "current_stock": 100}
        self.assertEqual(validation.validate_record(inv, "inventory")[1], [])

    # 8. Business validation
    def test_business_validation(self):
        good = {"fps_center_id": "FPS01", "transaction_date": "2026-08-01",
                "commodity": "rice", "quantity": 10}
        for bad in [dict(good, quantity=0), dict(good, quantity=-5)]:
            _, errors, _ = validation.validate_record(bad, "ration_transactions")
            self.assertTrue(any("positive" in e for e in errors), bad)
        ben = {"external_reference": "B1", "district": "D", "ration_category": "AAY", "family_size": 0}
        _, errors, _ = validation.validate_record(ben, "beneficiaries")
        self.assertTrue(any("family_size" in e for e in errors))
        inv = {"fps_center_id": "FPS01", "commodity": "rice", "current_stock": -1}
        _, errors, _ = validation.validate_record(inv, "inventory")
        self.assertTrue(any("positive" in e for e in errors))
        # coordinates validated too
        tx = dict(good, latitude=95)
        _, errors, _ = validation.validate_record(tx, "ration_transactions")
        self.assertTrue(any("latitude" in e for e in errors))

    # 10. Structured warnings
    def test_structured_warnings(self):
        good = {"fps_center_id": "FPS01", "transaction_date": "2026-08-01",
                "commodity": "rice", "quantity": 10,
                "district": " LUCKNOW ", "state": "UP"}
        normalized, errors, warnings = validation.validate_record(good, "ration_transactions")
        self.assertEqual(errors, [])
        self.assertEqual(normalized["district"], "Lucknow")
        self.assertEqual(normalized["state"], "UP")
        self.assertTrue(any("normalized" in w for w in warnings))

    # 11. Structured record results
    def test_record_result_structured(self):
        good = {"fps_center_id": "FPS01", "transaction_date": "2026-08-01",
                "commodity": "rice", "quantity": 10}
        result = validation.record_result(good, "ration_transactions")
        self.assertEqual(result["status"], "VALID")
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["normalized"]["quantity"], 10.0)
        bad = dict(good, quantity="abc")
        result = validation.record_result(bad, "ration_transactions")
        self.assertEqual(result["status"], "INVALID")
        self.assertTrue(any("numeric" in e for e in result["errors"]))

    # 9. Duplicate classification
    def test_duplicate_classification(self):
        headers = ["id", "fps", "date", "commodity", "quantity"]
        mapping = {"id": "external_transaction_id", "fps": "fps_center_id",
                   "date": "transaction_date", "commodity": "commodity", "quantity": "quantity"}
        rows = [
            ["T1", "FPS01", "2026-08-01", "rice", "10"],
            ["T1", "FPS01", "2026-08-01", "rice", "10"],   # EXACT (same id)
            ["T2", "FPS01", "2026-08-01", "rice", "10"],   # POSSIBLE (same content, new id)
            ["T3", "FPS01", "2026-08-02", "wheat", "5"],   # UNIQUE
        ]
        result = validation.classify_duplicates(rows, "ration_transactions", headers, mapping)
        self.assertEqual(result["unique"], 2)
        self.assertEqual(result["exact"], 1)
        self.assertEqual(result["possible"], 1)

    # 13. Quality score — transparent, deterministic formula
    def test_quality_score_formula(self):
        self.assertEqual(validation.quality_score(total=100, invalid=0, duplicates=0, warnings=0), 100.0)
        self.assertEqual(validation.quality_score(total=100, invalid=1, duplicates=0, warnings=0), 97.0)
        self.assertEqual(validation.quality_score(total=100, invalid=0, duplicates=1, warnings=0), 98.0)
        self.assertEqual(validation.quality_score(total=100, invalid=0, duplicates=0, warnings=1), 99.5)
        self.assertEqual(validation.quality_score(total=100, invalid=50, duplicates=0, warnings=0), 0.0)  # clamped
        # same input -> same score (deterministic, no randomness)
        self.assertEqual(validation.quality_score(124821, 181, 128, 34),
                         validation.quality_score(124821, 181, 128, 34))
        # 100 - (3*1% invalid + 2*1% duplicates + 0.5*2% warnings) = 94
        report = validation.quality_report(100, invalid=1, duplicates=1, warnings=2)
        self.assertEqual(report["score"], 94.0)
        self.assertEqual(report["valid_pct"], 98.0)


# ---------------------------------------------------------------------------
# 4. Import states (service-level, temp database)
# ---------------------------------------------------------------------------


class ImportFlowTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "ingest.db"
        self.addCleanup(self._tmp.cleanup)

    def _upload_and_validate(self, data: bytes, filename: str, dataset_type=None, mapping=None):
        upload = service.handle_upload(data, filename, "application/octet-stream")
        self.addCleanup(cleanup_upload, upload["token"])
        validated = service.validate_step(
            upload["token"], dataset_type=dataset_type or upload["dataset_type"],
            mapping=mapping, db_path=self.db_path,
        )
        return upload, validated

    def test_successful_transaction_import(self):
        data = TRANSACTION_CSV.encode("utf-8")
        upload, validated = self._upload_and_validate(data, "up_aug_2026.csv")
        self.assertEqual(validated["valid_records"], 3)
        self.assertEqual(validated["invalid_records"], 0)
        self.assertEqual(validated["duplicate_records"], 0)
        summary = service.confirm_step(upload["token"], db_path=self.db_path)
        self.assertEqual(summary["status"], "COMPLETED")
        self.assertEqual(summary["imported"], 3)
        self.assertEqual(summary["failed"], 0)

        conn = db.open_db(self.db_path)
        try:
            agent_rows = db.get_transactions_for_agent(conn)
            self.assertEqual(len(agent_rows), 3)
            self.assertEqual(agent_rows[0]["transaction_id"], "TX1001")
            self.assertEqual(agent_rows[0]["beneficiary_id"], "BEN001")
            # provenance: import -> source
            tx = db.get_transaction_by_external_id(conn, "TX1001")
            imp = db.get_data_import(conn, tx["source_import_id"])
            self.assertEqual(imp["status"], "COMPLETED")
            self.assertEqual(imp["successful_records"], 3)
            src = db.get_data_source(conn, imp["data_source_id"])
            self.assertEqual(src["name"], "Uploaded Dataset")
            # beneficiaries were auto-created from the refs
            refs = sorted(b["external_reference"] for b in db.list_beneficiaries(conn))
            self.assertEqual(refs, ["BEN001", "BEN002"])
        finally:
            conn.close()

    def test_partial_import(self):
        csv = "id,fps,date,commodity,quantity\nT1,FPS01,2026-08-01,rice,10\nT2,FPS01,2026-08-01,rice,abc\nT3,FPS01,2026-08-01,wheat,5\n"
        upload, validated = self._upload_and_validate(csv.encode("utf-8"), "partial.csv")
        self.assertEqual(validated["valid_records"], 2)
        self.assertEqual(validated["invalid_records"], 1)
        summary = service.confirm_step(upload["token"], db_path=self.db_path)
        self.assertEqual(summary["status"], "PARTIAL")
        self.assertEqual(summary["imported"], 2)
        self.assertEqual(summary["failed"], 1)
        self.assertIn("Row 3", summary["error_summary"])

    def test_failed_import(self):
        csv = "id,fps,date,commodity,quantity\nT1,FPS01,not-a-date,rice,10\nT2,FPS01,2026-08-01,rice,abc\n"
        upload, _ = self._upload_and_validate(csv.encode("utf-8"), "bad.csv")
        summary = service.confirm_step(upload["token"], db_path=self.db_path)
        self.assertEqual(summary["status"], "FAILED")
        self.assertEqual(summary["imported"], 0)
        conn = db.open_db(self.db_path)
        try:
            self.assertEqual(db.get_transactions_for_agent(conn), [])
        finally:
            conn.close()

    def test_duplicate_detection_within_file(self):
        csv = "id,fps,date,commodity,quantity\nT1,FPS01,2026-08-01,rice,10\nT1,FPS01,2026-08-01,rice,10\nT2,FPS01,2026-08-02,wheat,5\n"
        upload, validated = self._upload_and_validate(csv.encode("utf-8"), "dupes.csv")
        self.assertEqual(validated["duplicate_records"], 1)
        summary = service.confirm_step(upload["token"], db_path=self.db_path)
        self.assertEqual(summary["duplicates"], 1)
        self.assertEqual(summary["imported"], 2)

    def test_duplicate_against_existing_database(self):
        # Import once, then import the same file again: idempotent — the
        # second upload of identical bytes (same file hash) is refused and
        # points at the existing import instead of duplicating records.
        csv = "id,fps,date,commodity,quantity\nT1,FPS01,2026-08-01,rice,10\n"
        upload, _ = self._upload_and_validate(csv.encode("utf-8"), "once.csv")
        first = service.confirm_step(upload["token"], db_path=self.db_path)
        self.assertEqual(first["status"], "COMPLETED")
        self.assertEqual(first["imported"], 1)
        upload2, validated2 = self._upload_and_validate(csv.encode("utf-8"), "twice.csv")
        # the validate step already flags the repeated dataset
        self.assertIsNotNone(validated2["already_imported"])
        self.assertEqual(validated2["already_imported"]["data_import_id"], first["data_import_id"])
        summary2 = service.confirm_step(upload2["token"], db_path=self.db_path)
        self.assertEqual(summary2["status"], "ALREADY_IMPORTED")
        self.assertEqual(summary2["existing_import"]["data_import_id"], first["data_import_id"])
        conn = db.open_db(self.db_path)
        try:
            self.assertEqual(len(db.get_transactions_for_agent(conn)), 1)
        finally:
            conn.close()

    def test_composite_key_without_transaction_id(self):
        csv = "beneficiary,fps,date,commodity,quantity\nB1,FPS01,2026-08-01,rice,10\nB1,FPS01,2026-08-01,rice,10\nB1,FPS01,2026-08-02,wheat,5\n"
        upload, validated = self._upload_and_validate(csv.encode("utf-8"), "noid.csv")
        self.assertEqual(validated["duplicate_records"], 1)
        summary = service.confirm_step(upload["token"], db_path=self.db_path)
        self.assertEqual(summary["imported"], 2)
        conn = db.open_db(self.db_path)
        try:
            rows = db.get_transactions_for_agent(conn)
            self.assertEqual(len(rows), 2)
            # generated deterministic IDs, all traceable to the import
            self.assertTrue(all(r["transaction_id"].startswith("IMP") for r in rows))
        finally:
            conn.close()

    def test_missing_required_column_rejected(self):
        csv = "id,commodity,quantity\nT1,rice,10\n"  # no date column
        upload = service.handle_upload(csv.encode("utf-8"), "nocol.csv", "application/octet-stream")
        self.addCleanup(cleanup_upload, upload["token"])
        with self.assertRaises(mapmod.MappingError):
            service.validate_step(upload["token"], dataset_type="ration_transactions", db_path=self.db_path)

    def test_empty_dataset_rejected(self):
        with self.assertRaises(EmptyDatasetError):
            service.handle_upload(b"id,date,commodity,quantity\n", "empty.csv", "text/csv")

    def test_unsupported_file_rejected(self):
        with self.assertRaises(UnsupportedFileTypeError):
            service.handle_upload(b"hello", "notes.txt", "text/plain")

    def test_oversized_file_rejected(self):
        big = b"x" * (service.get_max_upload_bytes() + 1)
        with self.assertRaises(ParseError):
            service.handle_upload(big, "big.csv", "text/csv")

    def test_beneficiaries_import(self):
        upload, validated = self._upload_and_validate(BENEFICIARY_CSV.encode("utf-8"), "bens.csv", dataset_type="beneficiaries")
        self.assertEqual(validated["valid_records"], 2)
        summary = service.confirm_step(upload["token"], db_path=self.db_path)
        self.assertEqual(summary["status"], "COMPLETED")
        conn = db.open_db(self.db_path)
        try:
            rows = db.list_beneficiaries(conn)
            self.assertEqual(len(rows), 2)
            self.assertEqual(db.get_beneficiary_by_external_ref(conn, "BEN101")["district"], "Pune")
            self.assertEqual(db.get_beneficiary_by_external_ref(conn, "BEN101")["ration_category"], "AAY")
        finally:
            conn.close()

    def test_fps_centers_import(self):
        upload, _ = self._upload_and_validate(FPS_CSV.encode("utf-8"), "centers.csv", dataset_type="fps_centers")
        summary = service.confirm_step(upload["token"], db_path=self.db_path)
        self.assertEqual(summary["status"], "COMPLETED")
        conn = db.open_db(self.db_path)
        try:
            self.assertEqual(len(db.list_fps_centers(conn)), 2)
            self.assertEqual(db.get_fps_center_by_code(conn, "FPS01")["capacity"], 5000)
        finally:
            conn.close()

    def test_inventory_import(self):
        upload, validated = self._upload_and_validate(INVENTORY_CSV.encode("utf-8"), "inv.csv", dataset_type="inventory")
        self.assertEqual(validated["valid_records"], 2)
        summary = service.confirm_step(upload["token"], db_path=self.db_path)
        self.assertEqual(summary["status"], "COMPLETED")
        conn = db.open_db(self.db_path)
        try:
            center_id = db.get_fps_center_by_code(conn, "FPS01")
            self.assertIsNotNone(center_id)
            rows = db.get_inventory_for_center(conn, center_id["id"])
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["current_stock"], 1200.0)
        finally:
            conn.close()

    def test_combined_import_creates_beneficiaries_and_transactions(self):
        upload, validated = self._upload_and_validate(COMBINED_CSV.encode("utf-8"), "combined.csv", dataset_type="combined")
        self.assertEqual(validated["valid_records"], 2)
        summary = service.confirm_step(upload["token"], db_path=self.db_path)
        self.assertEqual(summary["status"], "COMPLETED")
        conn = db.open_db(self.db_path)
        try:
            ben = db.get_beneficiary_by_external_ref(conn, "BEN201")
            self.assertIsNotNone(ben)
            self.assertEqual(ben["district"], "Lucknow")
            self.assertEqual(ben["state"], "UP")
            self.assertEqual(len(db.get_transactions_for_agent(conn)), 2)
        finally:
            conn.close()

    def test_demo_data_preserved_alongside_imports(self):
        conn = db.open_db(self.db_path)
        db.seed_synthetic(conn)
        conn.close()
        data = "id,fps,date,commodity,quantity\nR1,FPS01,2026-08-01,rice,10\nR2,FPS01,2026-08-02,wheat,5\n"
        upload, _ = self._upload_and_validate(data.encode("utf-8"), "real.csv")
        service.confirm_step(upload["token"], db_path=self.db_path)
        conn = db.open_db(self.db_path)
        try:
            sources = {s["name"] for s in db.list_data_sources(conn)}
            self.assertIn("Synthetic Demo Dataset", sources)
            self.assertIn("Uploaded Dataset", sources)
            self.assertEqual(len(db.get_transactions_for_agent(conn)), 25 + 2)
            # demo rows still traceable to the synthetic import
            demo = db.get_transaction_by_external_id(conn, "TX001")
            self.assertEqual(db.get_data_source(conn, db.get_data_import(conn, demo["source_import_id"])["data_source_id"])["name"],
                             "Synthetic Demo Dataset")
        finally:
            conn.close()

    def test_large_dataset_import(self):
        # Distinct quantities keep every composite key unique (a repeated
        # composite under a different id would be a POSSIBLE duplicate).
        rows = ["id,fps,date,commodity,quantity"]
        rows.extend(
            "T%05d,FPS01,2026-08-01,rice,%d" % (i, (i % 10000) + 1)
            for i in range(1, 10001)
        )
        csv = "\n".join(rows) + "\n"
        upload, validated = self._upload_and_validate(csv.encode("utf-8"), "large.csv")
        self.assertEqual(validated["valid_records"], 10000)
        summary = service.confirm_step(upload["token"], db_path=self.db_path)
        self.assertEqual(summary["status"], "COMPLETED")
        self.assertEqual(summary["imported"], 10000)
        self.assertLess(summary["processing_time_seconds"], 30)
        conn = db.open_db(self.db_path)
        try:
            self.assertEqual(len(db.get_transactions_for_agent(conn)), 10000)
        finally:
            conn.close()

    def test_import_history_and_status(self):
        data = "id,fps,date,commodity,quantity\nH1,FPS01,2026-08-01,rice,10\n"
        upload, _ = self._upload_and_validate(data.encode("utf-8"), "hist.csv")
        summary = service.confirm_step(upload["token"], db_path=self.db_path)
        history = service.import_history(db_path=self.db_path)
        self.assertEqual(len(history), 1)
        entry = history[0]
        self.assertEqual(entry["dataset_name"], "hist")
        self.assertEqual(entry["status"], "COMPLETED")
        self.assertEqual(entry["successful_records"], 1)
        self.assertEqual(entry["source_name"], "Uploaded Dataset")
        status = service.import_status(summary["data_import_id"], db_path=self.db_path)
        self.assertEqual(status["record_count"], 1)


# ---------------------------------------------------------------------------
# 5. API flow (real server, temp database)
# ---------------------------------------------------------------------------


def http_request(method, url, data=None, headers=None):
    headers = dict(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


class TestIngestionAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls._tmp.name) / "api.db"
        cls.server = make_server("127.0.0.1", 0, db_path=cls.db_path)
        cls.port = cls.server.server_address[1]
        cls.base = "%s:%d" % (BASE, cls.port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls._tmp.cleanup()

    def test_full_api_flow_with_real_csv(self):
        # 1. upload
        status, body = http_request(
            "POST", self.base + "/api/upload", data=TRANSACTION_CSV.encode("utf-8"),
            headers={"X-Filename": "up_aug_2026.csv", "Content-Type": "text/csv"},
        )
        self.assertEqual(status, 200)
        upload = json.loads(body)
        self.assertEqual(upload["file_type"], "csv")
        self.assertEqual(upload["record_count"], 3)
        self.assertEqual(upload["dataset_type"], "ration_transactions")
        token = upload["token"]

        # 2. validate
        status, body = http_request(
            "POST", self.base + "/api/uploads/%s/validate" % token,
            data=json.dumps({"dataset_type": "ration_transactions"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 200)
        validated = json.loads(body)
        self.assertEqual(validated["valid_records"], 3)
        self.assertEqual(validated["invalid_records"], 0)

        # 3. confirm
        status, body = http_request(
            "POST", self.base + "/api/uploads/%s/confirm" % token,
            data=b"{}", headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 200)
        summary = json.loads(body)
        self.assertEqual(summary["status"], "COMPLETED")
        self.assertEqual(summary["imported"], 3)

        # 4. history + status
        status, body = http_request("GET", self.base + "/api/imports")
        self.assertEqual(status, 200)
        history = json.loads(body)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["dataset_name"], "up_aug_2026")

        status, body = http_request("GET", self.base + "/api/imports/%d" % summary["data_import_id"])
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "COMPLETED")

        # The confirm deleted the temp file: a second confirm is a 404.
        status, body = http_request(
            "POST", self.base + "/api/uploads/%s/confirm" % token, data=b"{}",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 404)

    def test_api_rejects_unsupported_file(self):
        status, body = http_request(
            "POST", self.base + "/api/upload", data=b"hello",
            headers={"X-Filename": "notes.txt", "Content-Type": "text/plain"},
        )
        self.assertEqual(status, 400)
        self.assertIn("Unsupported file type", body)

    def test_api_rejects_oversized_file(self):
        old = service.get_max_upload_bytes()
        os.environ["RATIONRIGHT_MAX_UPLOAD_MB"] = "0.0001"
        try:
            status, body = http_request(
                "POST", self.base + "/api/upload", data=b"x" * 4096,
                headers={"X-Filename": "big.csv", "Content-Type": "text/csv"},
            )
            self.assertEqual(status, 413)
        finally:
            os.environ.pop("RATIONRIGHT_MAX_UPLOAD_MB", None)
            self.assertIsNotNone(old)

    def test_api_rejects_path_traversal_filename(self):
        # The filename is used only for type detection — a traversal name must
        # never touch the filesystem and must simply be accepted as CSV.
        status, body = http_request(
            "POST", self.base + "/api/upload", data=TRANSACTION_CSV.encode("utf-8"),
            headers={"X-Filename": "../../../etc/passwd.csv", "Content-Type": "text/csv"},
        )
        self.assertEqual(status, 200)
        upload = json.loads(body)
        self.assertEqual(upload["file_type"], "csv")
        cleanup_upload(upload["token"])

    def test_api_invalid_json_upload(self):
        status, body = http_request(
            "POST", self.base + "/api/upload", data=b"{not json",
            headers={"X-Filename": "data.json", "Content-Type": "application/json"},
        )
        self.assertEqual(status, 400)

    def test_api_empty_dataset(self):
        status, body = http_request(
            "POST", self.base + "/api/upload", data=b"id,qty\n",
            headers={"X-Filename": "empty.csv", "Content-Type": "text/csv"},
        )
        self.assertEqual(status, 400)
        self.assertIn("no data rows", body)

    def test_api_mapping_validation_error(self):
        status, body = http_request(
            "POST", self.base + "/api/upload", data=TRANSACTION_CSV.encode("utf-8"),
            headers={"X-Filename": "t.csv", "Content-Type": "text/csv"},
        )
        upload = json.loads(body)
        # force a bad dataset type choice -> required fields not mappable
        status, body = http_request(
            "POST", self.base + "/api/uploads/%s/validate" % upload["token"],
            data=json.dumps({"dataset_type": "inventory"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 400)
        cleanup_upload(upload["token"])

    def test_api_unknown_token_404(self):
        status, body = http_request(
            "POST", self.base + "/api/uploads/deadbeef/validate", data=b"{}",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
