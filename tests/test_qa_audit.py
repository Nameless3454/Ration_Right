"""RationRight — Phase 15: Data accuracy audit.

Independently verifies the data path: upload -> validate -> import ->
analytics -> command center -> API. Every expected value in this file is
computed from raw rows / independent arithmetic, never copied from the
application output.

- Import reconciliation invariant: source = valid + invalid, imported == valid
- Normalization rules (commodity case/whitespace, date formats)
- Analytics recomputed from raw rows and compared to the service
- KPI chain: database -> analytics -> command center -> API agree
- Historical comparison: change % math + previous=0 guard
- Filter scoping isolation (no cross-scope leakage)
- Date boundaries (month / year / same-day) and null/missing data
- Duplicate-file idempotency (no double import)

Run from the project root::

    python3 -m unittest tests.test_qa_audit -v
"""

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import analytics
import database as db
from ingestion import service as ingest
from server import make_server

BASE = "http://127.0.0.1"

TRANSACTION_CSV = (
    "Transaction ID,Beneficiary ID,FPS Code,Transaction Date,Commodity,Quantity,Unit\n"
    "TX101,BEN001,FPS01,2026-08-01,rice,10,kg\n"
    "TX102,BEN001,FPS01,2026-08-02,Rice,5,kg\n"        # case-different (valid)
    "TX103,BEN002,FPS02,2026-08-01,wheat,8,kg\n"
    "TX104,BEN002,FPS02,2026-08-01,wheat,8,kg\n"        # exact duplicate of TX103
    "TX105,BEN003,FPS03,2026-08-03,rice,abc,kg\n"        # unparseable quantity
    "TX106,BEN003,FPS03,not-a-date,rice,3,kg\n"          # invalid date
    "TX107,BEN004,FPS01,2026-08-04,rice,12,kg\n"
)

# 7 data rows. Valid = 5 (TX101, TX102, TX103, TX104, TX107 — the exact
# duplicate TX104 is still a valid record, just skipped at import).
# Invalid = 2 (TX105 bad quantity, TX106 bad date). Duplicates = 1 (TX104).
# Imported = valid - duplicates = 4. Distribution = 10+5+8+12 = 35 kg.
_VALID = 5
_INVALID = 2
_DUPES = 1
_IMPORTED = 4
_DISTRIBUTION_KG = 35.0


def _fresh_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.unlink(tmp.name)
    return tmp.name


def _import_csv(db_path, csv_text=TRANSACTION_CSV, name="qa.csv"):
    """Full upload -> validate -> confirm pipeline; returns the summary."""
    upload = ingest.handle_upload(csv_text.encode(), name, "text/csv")
    token = upload["token"]
    validated = ingest.validate_step(token, dataset_type="ration_transactions",
                                     db_path=db_path)
    summary = ingest.confirm_step(token, db_path=db_path)
    return validated, summary


class ImportReconciliationTests(unittest.TestCase):
    """The source -> valid/invalid/duplicates -> imported invariant."""

    def setUp(self):
        self.db_path = _fresh_db()
        self.addCleanup(lambda: os.path.exists(self.db_path) and os.unlink(self.db_path))

    def test_reconciliation_invariant(self):
        validated, summary = _import_csv(self.db_path)
        total = validated["record_count"]
        valid = validated["valid_records"]
        invalid = validated["invalid_records"]
        dupes = validated["duplicate_records"]

        # No silent loss: every source row is accounted for exactly once.
        self.assertEqual(total, valid + invalid, "source must equal valid + invalid")
        self.assertEqual(total, 7)
        self.assertEqual(valid, _VALID)
        self.assertEqual(invalid, _INVALID)
        self.assertEqual(dupes, _DUPES)
        self.assertLessEqual(dupes, valid)

        # Imported = valid records minus the exact duplicates skipped at import.
        self.assertEqual(summary["imported"], _IMPORTED)
        self.assertEqual(summary["imported"], valid - dupes)
        self.assertEqual(summary["failed"], invalid)

        # And the database must actually contain exactly that many rows.
        conn = db.open_db(self.db_path)
        try:
            inserted = conn.execute(
                "SELECT COUNT(*) AS n FROM ration_transactions").fetchone()["n"]
        finally:
            conn.close()
        self.assertEqual(inserted, _IMPORTED, "inserted rows must match imported count")

    def test_duplicate_file_is_idempotent(self):
        validated, summary = _import_csv(self.db_path)
        self.assertEqual(summary["status"], "PARTIAL")  # 2 invalid rows
        self.assertEqual(summary["imported"], _IMPORTED)
        # Same bytes again -> ALREADY_IMPORTED, no additional rows.
        validated2, summary2 = _import_csv(self.db_path)
        self.assertEqual(summary2["status"], "ALREADY_IMPORTED")
        conn = db.open_db(self.db_path)
        try:
            inserted = conn.execute(
                "SELECT COUNT(*) AS n FROM ration_transactions").fetchone()["n"]
        finally:
            conn.close()
        self.assertEqual(inserted, _IMPORTED)


class NormalizationTests(unittest.TestCase):
    """Phase 4 normalization rules: case, whitespace, dates, units."""

    def test_commodity_normalization(self):
        from ingestion import validation
        self.assertEqual(validation.normalize_commodity(" rice ")[0], "rice")
        self.assertEqual(validation.normalize_commodity("Rice")[0], "rice")
        self.assertEqual(validation.normalize_commodity("RICE")[0], "rice")
        self.assertEqual(validation.normalize_commodity("wheataata")[0], "wheat")
        # Unknown commodities warn but are never silently guessed.
        key, changed, warning = validation.normalize_commodity("unmapped-crop")
        self.assertEqual(key, "unmapped-crop")
        self.assertIsNotNone(warning)

    def test_date_normalization_formats(self):
        from ingestion import validation
        for raw in ("2026-08-01", "2026/08/01", "01-08-2026", "01/08/2026",
                    "1 Aug 2026"):
            self.assertEqual(validation.parse_date(raw), "2026-08-01", raw)
        self.assertIsNone(validation.parse_date("not-a-date"))

    def test_numeric_normalization(self):
        from ingestion import validation
        self.assertEqual(validation.parse_number("1,200"), 1200.0)
        self.assertEqual(validation.parse_number("1200 kg"), 1200.0)
        self.assertIsNone(validation.parse_number("abc"))


class IndependentAnalyticsTests(unittest.TestCase):
    """Recompute analytics from raw rows; compare to the service."""

    def setUp(self):
        self.db_path = _fresh_db()
        conn = db.open_db(self.db_path)
        src = db.insert_data_source(conn, name="Uploaded Dataset",
                                    source_type="MANUAL", description="t",
                                    status="ACTIVE")
        imp = db.insert_data_import(conn, data_source_id=src,
                                    dataset_name="audit", file_name="a.csv",
                                    file_type="CSV", record_count=4,
                                    status="COMPLETED")
        db.upsert_beneficiaries(conn, [
            {"external_reference": "B1", "state": "UP", "district": "Lucknow",
             "ration_category": "AAY", "family_size": 4, "status": "ACTIVE"},
            {"external_reference": "B2", "state": "UP", "district": "Kanpur",
             "ration_category": "PHH", "family_size": 3, "status": "ACTIVE"},
        ])
        bm = db.beneficiary_ids(conn, ["B1", "B2"])
        db.upsert_fps_centers(conn, [
            {"fps_code": "F01", "name": "A", "district": "Lucknow",
             "state": "UP", "status": "ACTIVE"},
            {"fps_code": "F02", "name": "B", "district": "Kanpur",
             "state": "UP", "status": "ACTIVE"},
        ])
        cm = db.fps_center_ids(conn, ["F01", "F02"])
        # Known rows: rice 100+40 (COMPLETED) + wheat 20 (FAILED) + pulses 60.
        db.insert_transactions_batch(conn, [
            {"external_transaction_id": "A1", "beneficiary_id": bm["B1"],
             "fps_center_id": cm["F01"], "transaction_date": "2026-08-01",
             "commodity": "rice", "quantity": 100.0, "unit": "kg",
             "status": "COMPLETED", "source_import_id": imp,
             "latitude": 26.8, "longitude": 80.9},
            {"external_transaction_id": "A2", "beneficiary_id": bm["B1"],
             "fps_center_id": cm["F01"], "transaction_date": "2026-08-02",
             "commodity": "rice", "quantity": 40.0, "unit": "kg",
             "status": "COMPLETED", "source_import_id": imp,
             "latitude": 26.8, "longitude": 80.9},
            {"external_transaction_id": "A3", "beneficiary_id": bm["B2"],
             "fps_center_id": cm["F02"], "transaction_date": "2026-08-03",
             "commodity": "wheat", "quantity": 20.0, "unit": "kg",
             "status": "FAILED", "source_import_id": imp,
             "latitude": 26.4, "longitude": 80.3},
            {"external_transaction_id": "A4", "beneficiary_id": bm["B2"],
             "fps_center_id": cm["F02"], "transaction_date": "2026-08-04",
             "commodity": "pulses", "quantity": 60.0, "unit": "kg",
             "status": "COMPLETED", "source_import_id": imp,
             "latitude": 26.4, "longitude": 80.3},
        ])
        db.insert_inventory_batch(conn, [
            {"fps_center_id": cm["F01"], "commodity": "rice",
             "current_stock": 500.0, "monthly_consumption": 300.0,
             "reorder_threshold": 200.0, "source_import_id": imp},
        ])
        conn.commit()
        conn.close()
        self.addCleanup(lambda: os.path.exists(self.db_path) and os.unlink(self.db_path))

    def _raw_totals(self):
        conn = db.open_db(self.db_path)
        try:
            rows = [dict(r) for r in conn.execute(
                "SELECT commodity, quantity, status FROM ration_transactions")]
        finally:
            conn.close()
        return rows

    def test_overview_matches_independent_recomputation(self):
        rows = self._raw_totals()
        expect_qty = round(sum(r["quantity"] for r in rows), 2)
        expect_n = len(rows)
        expect_completed = sum(1 for r in rows if r["status"] == "COMPLETED")
        expect_failed = sum(1 for r in rows if r["status"] == "FAILED")
        rice = sum(r["quantity"] for r in rows if r["commodity"] == "rice")

        conn = db.open_db(self.db_path)
        try:
            ov = analytics.overview(conn)
        finally:
            conn.close()
        self.assertEqual(ov["ration_distributed_kg"], expect_qty)
        self.assertEqual(ov["total_transactions"], expect_n)
        self.assertEqual(ov["distribution_count"], expect_n)
        self.assertEqual(ov["by_status"]["COMPLETED"], expect_completed)
        self.assertEqual(ov["by_status"]["FAILED"], expect_failed)
        by_commodity = {c["commodity"]: c["quantity"] for c in ov["by_commodity"]}
        self.assertEqual(by_commodity["rice"], rice)
        self.assertEqual(ov["total_beneficiaries"], 2)

    def test_distribution_granularity_totals_match(self):
        conn = db.open_db(self.db_path)
        try:
            dist = analytics.distribution(conn, granularity="day")
        finally:
            conn.close()
        trend = dist["trend"]
        labels = trend["labels"]
        self.assertEqual(len(labels), 4)  # one bucket per transaction day
        total = sum(sum(v for v in trend["series"][c]) for c in trend["series"])
        self.assertEqual(total, 220.0)
        # Bucket for 2026-08-01 must be exactly the rice 100 row.
        idx = labels.index("2026-08-01")
        self.assertEqual(trend["series"]["rice"][idx], 100.0)

    def test_inventory_coverage_independent(self):
        conn = db.open_db(self.db_path)
        try:
            inv = analytics.inventory(conn)
        finally:
            conn.close()
        # F01 rice: stock 500, monthly consumption 300 -> ~50 days coverage.
        item = next(i for i in inv["by_commodity"] if i["commodity"] == "rice")
        self.assertEqual(item["current_stock"], 500.0)
        self.assertEqual(item["monthly_consumption"], 300.0)
        expect_days = round(500.0 / (300.0 / 30.0), 1)
        self.assertAlmostEqual(item["days_remaining"], expect_days, delta=0.2)
        # The raw items array also exposes the same stock for traceability.
        raw = next(i for i in inv["items"] if i["fps_code"] == "F01"
                   and i["commodity"] == "rice")
        self.assertEqual(raw["current_stock"], 500.0)


class KpiChainTests(unittest.TestCase):
    """database -> analytics -> command center -> API must agree."""

    def setUp(self):
        self.db_path = _fresh_db()
        _validated, summary = _import_csv(self.db_path)
        self.summary = summary
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.httpd = make_server(port=0, db_path=self.db_path)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.shutdown)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(lambda: os.path.exists(self.db_path) and os.unlink(self.db_path))

    def _get(self, path):
        with urllib.request.urlopen(
                "%s:%d%s" % (BASE, self.port, path), timeout=20) as resp:
            return json.loads(resp.read())

    def test_command_center_kpis_match_database(self):
        cc = self._get("/api/command-center")
        ov = self._get("/api/analytics/overview?range=all")
        kpis = {k["key"]: k["value"] for k in cc["kpis"]}

        # Imported quantity: 10+5+8+12 = 35 kg (valid rows only).
        self.assertEqual(kpis["distribution"], 35.0)
        self.assertEqual(kpis["distribution"], ov["ration_distributed_kg"])
        self.assertEqual(kpis["transactions"], ov["total_transactions"])
        self.assertEqual(kpis["transactions"], self.summary["imported"])

        # Database ground truth, independent of both services.
        conn = db.open_db(self.db_path)
        try:
            ground = conn.execute(
                "SELECT COALESCE(SUM(quantity), 0) AS qty FROM ration_transactions"
            ).fetchone()["qty"]
        finally:
            conn.close()
        self.assertEqual(kpis["distribution"], round(ground, 2))

    def test_filter_isolation_no_cross_scope_leak(self):
        cc = self._get("/api/command-center?commodity=rice")
        kpis = {k["key"]: k["value"] for k in cc["kpis"]}
        # Only rice rows: 10 + 5 + 12 = 27 kg (TX101, TX102, TX107).
        self.assertEqual(kpis["distribution"], 27.0)
        # Wheat must NOT appear in the scoped payload.
        trend = cc["trends"]
        wheat = [b for b in trend.get("by_commodity", []) if b.get("commodity") == "wheat"]
        self.assertFalse(wheat)

    def test_district_filter(self):
        # FPS rows carry no district on the upload path, so a district filter
        # must not leak any other scope's rows into the KPIs.
        cc = self._get("/api/command-center?district=Lucknow")
        kpis = {k["key"]: k["value"] for k in cc["kpis"]}
        for key, value in kpis.items():
            if value is None:
                continue
            self.assertEqual(value, 0, "KPI %r leaked non-zero value %r" % (key, value))


class HistoricalComparisonTests(unittest.TestCase):
    """change % math and the previous=0 / missing-previous guards."""

    def test_change_pct_math(self):
        import command_center
        self.assertEqual(command_center._change_pct(120, 100), 20.0)
        self.assertEqual(command_center._change_pct(100, 120), -16.7)

    def test_previous_zero_is_not_misleading(self):
        # (120 - 0) / 0 is undefined; must not produce +inf or a fake %.
        import command_center
        self.assertIsNone(command_center._change_pct(120, 0))

    def test_missing_previous(self):
        import command_center
        self.assertIsNone(command_center._change_pct(None, 100))


class DateBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.db_path = _fresh_db()
        _import_csv(self.db_path)
        self.addCleanup(lambda: os.path.exists(self.db_path) and os.unlink(self.db_path))

    def _count_between(self, from_date, to_date):
        conn = db.open_db(self.db_path)
        try:
            ov = analytics.overview(conn, range_key="custom",
                                    from_date=from_date, to_date=to_date)
            return ov["total_transactions"]
        finally:
            conn.close()

    def test_month_boundary(self):
        # Imported TX dates: 08-01, 08-02, 08-01, 08-04 -> 4 rows (the exact
        # duplicate TX104 was skipped at import).
        self.assertEqual(self._count_between("2026-08-01", "2026-08-31"), 4)
        self.assertEqual(self._count_between("2026-07-01", "2026-07-31"), 0)

    def test_same_day_range(self):
        self.assertEqual(self._count_between("2026-08-01", "2026-08-01"), 2)

    def test_year_boundary(self):
        self.assertEqual(self._count_between("2025-12-31", "2026-01-01"), 0)


class NullMissingDataTests(unittest.TestCase):
    def test_empty_database_never_crashes(self):
        db_path = _fresh_db()
        conn = db.open_db(db_path)
        conn.close()
        try:
            conn = db.open_db(db_path)
            ov = analytics.overview(conn)
            inv = analytics.inventory(conn)
        finally:
            conn.close()
        self.assertEqual(ov["total_transactions"], 0)
        self.assertEqual(ov["ration_distributed_kg"], 0)
        self.assertEqual(inv["items"], [])
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
