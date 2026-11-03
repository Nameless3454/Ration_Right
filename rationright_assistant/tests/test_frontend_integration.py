"""
Integration tests for Frontend-Backend API Integration phase.
Verifies that every API contract utilized by the React frontend components
(Header, SnapshotSelector, DatasetUploadModal, OperationsDashboard, FloatingChatbot)
behaves precisely as expected against the live FastAPI RAG backend.
"""
import io
from pathlib import Path
import zipfile
import pytest
from fastapi.testclient import TestClient

from src.api.main import app, importer, router
from src.config import settings
from src.db.database import init_db
from src.ingestion.importer import DatasetImporter

client = TestClient(app)

DUMMY_CSV_DIR = settings.BASE_DIR.parent / "rationright-rag" / "RationRight_Dummy_Data_Pack"
if not DUMMY_CSV_DIR.exists():
    DUMMY_CSV_DIR = settings.BASE_DIR.parent / "data" / "uploaded_dataset"

DUMMY_JSON_FILE = DUMMY_CSV_DIR / "rationright_demo_data.json"


@pytest.fixture
def integration_db(tmp_path, monkeypatch):
    """Sets up an isolated test database with imported snapshots for testing frontend contracts."""
    db_file = tmp_path / "frontend_integration.db"
    init_db(db_file)

    test_importer = DatasetImporter(db_path=db_file)
    batch1 = test_importer.import_dataset(DUMMY_CSV_DIR, dataset_name="Week_41_Frontend_CSV")
    batch2 = test_importer.import_dataset(DUMMY_JSON_FILE, dataset_name="Week_42_Frontend_JSON")

    monkeypatch.setattr(settings, "DB_PATH", db_file)
    monkeypatch.setattr(importer, "db_path", db_file)
    monkeypatch.setattr(router, "db_path", db_file)

    return db_file, batch1.import_id, batch2.import_id


def test_cors_headers_for_frontend():
    """Verify CORS middleware allows frontend cross-origin requests."""
    res = client.options(
        "/api/chat",
        headers={
            "Origin": "http://localhost:5174",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") in ["*", "http://localhost:5174"]


def test_system_info_contract(integration_db):
    """Verify /api/info contract used by Header component for health and status."""
    res = client.get("/api/info")
    assert res.status_code == 200
    data = res.json()
    assert data["service"] == settings.PROJECT_NAME
    assert data["version"] == settings.VERSION
    assert "db_path" in data
    assert "llm_model" in data


def test_imports_list_contract(integration_db):
    """Verify /api/imports contract used by SnapshotSelector component."""
    _, batch1_id, batch2_id = integration_db

    res = client.get("/api/imports")
    assert res.status_code == 200
    imports = res.json()
    assert len(imports) >= 2
    import_ids = [i["import_id"] for i in imports]
    assert batch1_id in import_ids
    assert batch2_id in import_ids
    for imp in imports:
        assert "dataset_name" in imp
        assert "total_records" in imp
        assert "import_timestamp" in imp
        assert imp["status"] == "SUCCESS"


def test_metrics_dashboard_contract(integration_db):
    """Verify /api/metrics/{import_id} contract used by OperationsDashboard component."""
    _, _, batch2_id = integration_db

    res = client.get(f"/api/metrics/{batch2_id}?limit=50&offset=0")
    assert res.status_code == 200
    data = res.json()

    # 1. Beneficiaries
    b = data["beneficiaries"]
    assert b["total_beneficiaries"] == 20
    assert b["phh_count"] == 15
    assert b["aay_count"] == 5
    assert b["duplicate_flag_count"] == 2
    assert b["multiple_claims_count"] == 1

    # 2. Inventory Ledger
    inv = data["inventory"]
    assert len(inv) > 0
    first_item = inv[0]
    assert "commodity" in first_item
    assert "opening_stock_kg" in first_item
    assert "received_kg" in first_item
    assert "distributed_kg" in first_item
    assert "closing_stock_kg" in first_item
    assert "physical_stock_kg" in first_item
    assert "physical_discrepancy_kg" in first_item

    # 3. Shop Complaints Ranking
    shops = data["shop_complaints"]
    assert len(shops) > 0
    assert "complaints_count" in shops[0]
    assert "inspection_status" in shops[0]

    # 4. Transactions
    tx = data["transactions"]
    assert "total_transactions" in tx
    assert ("total_grain_distributed_kg" in tx) or ("total_distributed_kg" in tx)
    assert "biometric_count" in tx
    assert "manual_override_count" in tx


def test_paginated_inventory_endpoint(integration_db):
    """Verify /api/inventory/{import_id} contract used for filtered ledger views."""
    _, _, batch2_id = integration_db

    # Test filtering by Rice
    res_rice = client.get(f"/api/inventory/{batch2_id}?commodity=Rice&limit=10&offset=0")
    assert res_rice.status_code == 200
    rice_data = res_rice.json()
    assert rice_data["total"] == 5
    for item in rice_data["inventory"]:
        assert item["commodity"] == "Rice"

    # Test pagination
    res_page = client.get(f"/api/inventory/{batch2_id}?limit=2&offset=0")
    assert res_page.status_code == 200
    page_data = res_page.json()
    assert len(page_data["inventory"]) == 2
    assert page_data["limit"] == 2
    assert page_data["offset"] == 0


def test_multipart_upload_workflow(integration_db, tmp_path):
    """Verify /api/import/upload contract used by DatasetUploadModal component."""
    # 1. Valid ZIP upload
    zip_path = tmp_path / "frontend_upload.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for csv_file in DUMMY_CSV_DIR.glob("*.csv"):
            zf.write(csv_file, arcname=csv_file.name)

    with open(zip_path, "rb") as f:
        res_upload = client.post(
            "/api/import/upload",
            files={"file": ("frontend_upload.zip", f, "application/zip")},
            data={"dataset_name": "Frontend_Integration_Upload"},
        )
    assert res_upload.status_code == 201
    upload_data = res_upload.json()
    assert upload_data["status"] == "SUCCESS"
    assert upload_data["dataset_name"] == "Frontend_Integration_Upload"
    assert upload_data["total_records"] > 0
    assert "beneficiaries" in upload_data["table_counts"]

    # 2. Invalid file upload (rejected)
    bad_file = io.BytesIO(b"not a valid dataset")
    res_bad = client.post(
        "/api/import/upload",
        files={"file": ("invalid.txt", bad_file, "text/plain")},
    )
    assert res_bad.status_code == 400
    assert "Unsupported file format" in res_bad.json()["detail"]


def test_chatbot_chat_workflow(integration_db):
    """Verify /api/chat contract used by FloatingChatbot component."""
    _, _, batch2_id = integration_db

    # 1. Legitimate operational question
    res_q1 = client.post(
        "/api/chat",
        json={"question": "Which records have duplicate flags?", "import_id": batch2_id},
    )
    assert res_q1.status_code == 200
    data_q1 = res_q1.json()
    assert data_q1["route_type"] == "STRUCTURED"
    assert data_q1["is_supported"] is True
    assert "BEN007" in data_q1["answer"]
    assert "evidence" in data_q1
    assert "records" in data_q1["evidence"]["sql_data"]

    # 2. Policy RAG definition question
    res_q2 = client.post(
        "/api/chat",
        json={"question": "What does statutory quota mean?", "import_id": batch2_id},
    )
    assert res_q2.status_code == 200
    data_q2 = res_q2.json()
    assert data_q2["route_type"] == "RAG_DEFINITION"
    assert "rag_context" in data_q2["evidence"]

    # 3. Accusatory question (verifying administrative neutrality disclaimer)
    res_q3 = client.post(
        "/api/chat",
        json={"question": "Is dealer DLR004 corrupt and guilty of fraud?", "import_id": batch2_id},
    )
    assert res_q3.status_code == 200
    data_q3 = res_q3.json()
    assert "disclaimer" in data_q3["answer"].lower() or "neutrality" in data_q3["answer"].lower()

    # 4. Out-of-domain unsupported question (verifying clean refusal)
    res_q4 = client.post(
        "/api/chat",
        json={"question": "Write a python script to parse logs", "import_id": batch2_id},
    )
    assert res_q4.status_code == 200
    data_q4 = res_q4.json()
    assert data_q4["route_type"] == "UNSUPPORTED"
    assert data_q4["is_supported"] is False
    assert "imported RationRight datasets do not contain information" in data_q4["answer"]
