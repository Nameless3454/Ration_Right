"""
Tests for Phase 3: Safe Structured Queries & Weekly Snapshot Comparisons.
"""
import copy
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.config import settings
from src.db.database import init_db
from src.ingestion.importer import DatasetImporter
from src.query_engine.comparator import compare_snapshots
from src.query_engine.safe_queries import (
    get_audit_summary,
    get_beneficiaries_summary,
    get_flagged_beneficiaries,
    get_import_summary,
    get_inventory_status,
    get_latest_import_id,
    get_shop_complaints_ranking,
    get_transactions_summary,
)

client = TestClient(app)

DUMMY_CSV_DIR = settings.BASE_DIR.parent / "rationright-rag" / "RationRight_Dummy_Data_Pack"
if not DUMMY_CSV_DIR.exists():
    DUMMY_CSV_DIR = settings.BASE_DIR.parent / "data" / "uploaded_dataset"

DUMMY_JSON_FILE = DUMMY_CSV_DIR / "rationright_demo_data.json"


@pytest.fixture
def populated_db(tmp_path):
    """Initializes a test database and imports the baseline weekly dummy dataset."""
    db_file = tmp_path / "test_comparison.db"
    init_db(db_file)
    importer = DatasetImporter(db_path=db_file)
    batch = importer.import_dataset(DUMMY_CSV_DIR, dataset_name="Week_41_Baseline")
    return db_file, batch.import_id


def test_safe_queries(populated_db):
    """Test all safe query functions against the baseline import."""
    db_file, import_id = populated_db

    # 1. Latest import ID
    latest = get_latest_import_id(db_path=db_file)
    assert latest == import_id

    # 2. Beneficiaries summary
    ben_sum = get_beneficiaries_summary(import_id, db_path=db_file)
    assert ben_sum["total_beneficiaries"] == 20
    assert ben_sum["phh_count"] == 15
    assert ben_sum["aay_count"] == 5
    assert ben_sum["duplicate_flag_count"] == 2
    assert ben_sum["multiple_claims_count"] == 1

    # 3. Flagged beneficiaries
    dups = get_flagged_beneficiaries(import_id, flag_type="possible_duplicate", db_path=db_file)
    assert len(dups) == 2
    dup_ids = {d["beneficiary_id"] for d in dups}
    assert dup_ids == {"BEN007", "BEN014"}

    multis = get_flagged_beneficiaries(import_id, flag_type="multiple_claims", db_path=db_file)
    assert len(multis) == 1
    assert multis[0]["beneficiary_id"] == "BEN019"

    # 4. Inventory status and calculations
    inv = get_inventory_status(import_id, db_path=db_file)
    assert len(inv) == 10
    # Check INV003 discrepancy (-280 kg)
    inv3 = next(i for i in inv if i["inventory_id"] == "INV003")
    assert inv3["expected_closing_kg"] == 800
    assert inv3["physical_stock_kg"] == 520
    assert inv3["physical_discrepancy_kg"] == -280

    # 5. Complaints ranking
    ranking = get_shop_complaints_ranking(import_id, limit=5, db_path=db_file)
    assert len(ranking) == 5
    assert ranking[0]["pwd_id"] == "PWD004"
    assert ranking[0]["complaints_count"] == 6

    # 6. Audits summary
    aud_sum = get_audit_summary(import_id, db_path=db_file)
    assert aud_sum["total_audits"] == 5
    assert aud_sum["total_complaints"] == 14
    assert aud_sum["failed_inspections"] == 1

    # 7. Transactions summary
    tx_sum = get_transactions_summary(import_id, db_path=db_file)
    assert tx_sum["total_transactions"] == 5
    assert tx_sum["biometric_count"] == 3
    assert tx_sum["manual_override_count"] == 2


def test_snapshot_diffing(populated_db, tmp_path):
    """
    Test comparing two weekly snapshots with simulated changes in inventory and beneficiaries.
    """
    db_file, import_id_1 = populated_db
    importer = DatasetImporter(db_path=db_file)

    # Create a synthetic Week 42 JSON with changes:
    with open(DUMMY_JSON_FILE, "r") as f:
        data_w42 = json.load(f)

    # Change 1: Alter inventory stock for PWD001 Rice
    data_w42["inventory"][0]["physical_stock_kg"] = 400  # down from 470
    data_w42["inventory"][0]["distributed_kg"] = 1600    # up from 1500

    # Change 2: Add a new beneficiary
    new_ben = copy.deepcopy(data_w42["beneficiaries"][0])
    new_ben["beneficiary_id"] = "BEN999"
    new_ben["ration_card_id"] = "DEMO-RC-99999"
    new_ben["head_name"] = "New Enrolled Beneficiary"
    new_ben["identity_status"] = "verified"
    data_w42["beneficiaries"].append(new_ben)

    # Change 3: Alter existing beneficiary status (BEN001 gets flagged)
    data_w42["beneficiaries"][0]["identity_status"] = "possible_duplicate"

    # Save to temp JSON and import as Week 42
    w42_file = tmp_path / "week_42.json"
    with open(w42_file, "w") as f:
        json.dump(data_w42, f)

    batch_2 = importer.import_dataset(w42_file, dataset_name="Week_42_Simulated")
    import_id_2 = batch_2.import_id

    # Run comparison
    diff = compare_snapshots(import_id_1, import_id_2, db_path=db_file)

    # Assertions
    assert diff["metadata_comparison"]["total_records_delta"] == 1  # 1 new beneficiary
    assert diff["beneficiaries_summary_delta"]["total_beneficiaries_delta"] == 1
    assert diff["beneficiaries_summary_delta"]["duplicate_flags_delta"] == 1  # BEN001 newly flagged

    # Beneficiary records diff
    assert diff["beneficiary_changes"]["newly_added_count"] == 1
    assert diff["beneficiary_changes"]["newly_added"][0]["beneficiary_id"] == "BEN999"
    assert diff["beneficiary_changes"]["status_altered_count"] == 1
    assert diff["beneficiary_changes"]["status_altered"][0]["beneficiary_id"] == "BEN001"

    # Inventory diff
    assert diff["inventory_changes"]["changed_inventory_items_count"] == 1
    item = diff["inventory_changes"]["item_changes"][0]
    assert item["commodity"] == "Rice"
    assert item["physical_stock_delta_kg"] == -70  # 400 - 470
    assert item["distributed_delta_kg"] == 100     # 1600 - 1500


def test_api_comparison_and_metrics(monkeypatch, populated_db, tmp_path):
    """Test /api/compare and /api/metrics endpoints."""
    db_file, import_id_1 = populated_db

    from src.api.main import importer
    monkeypatch.setattr(importer, "db_path", db_file)

    # Import second batch so we have at least 2 historical imports
    batch_2 = importer.import_dataset(DUMMY_JSON_FILE, dataset_name="Week_42_API_Test")

    # 1. Test POST /api/compare (defaults to comparing latest 2 imports)
    res_compare = client.post("/api/compare", json={})
    assert res_compare.status_code == 200
    comp_data = res_compare.json()
    assert "metadata_comparison" in comp_data
    assert "beneficiary_changes" in comp_data
    assert "inventory_changes" in comp_data

    # 2. Test GET /api/metrics/latest
    # Monkeypatch settings DB_PATH to use test DB for queries
    import src.query_engine.safe_queries as sq
    import src.api.main as main_mod
    monkeypatch.setattr(settings, "DB_PATH", db_file)

    res_metrics = client.get("/api/metrics/latest")
    assert res_metrics.status_code == 200
    metrics_data = res_metrics.json()
    assert metrics_data["beneficiaries"]["total_beneficiaries"] == 20
    assert len(metrics_data["inventory"]) == 10
    assert len(metrics_data["shop_complaints"]) == 5

