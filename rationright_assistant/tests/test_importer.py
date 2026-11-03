"""
Unit and integration tests for Phase 2: Weekly Ingestion Engine into SQLite.
"""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.config import settings
from src.db.database import get_db_connection, init_db
from src.ingestion.importer import DatasetImporter

client = TestClient(app)

DUMMY_CSV_DIR = settings.BASE_DIR.parent / "rationright-rag" / "RationRight_Dummy_Data_Pack"
if not DUMMY_CSV_DIR.exists():
    DUMMY_CSV_DIR = settings.BASE_DIR.parent / "data" / "uploaded_dataset"

DUMMY_JSON_FILE = DUMMY_CSV_DIR / "rationright_demo_data.json"


@pytest.fixture
def test_db(tmp_path):
    """Provides an isolated temporary database for test runs."""
    db_file = tmp_path / "test_assistant.db"
    init_db(db_file)
    return db_file


def test_schema_initialization(test_db):
    """Verify that all tables and indexes are created properly."""
    with get_db_connection(test_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row["name"] for row in cursor.fetchall()}
        
    expected_tables = {
        "import_batches",
        "pwd_shops",
        "beneficiaries",
        "inventory",
        "transactions",
        "pwd_audits",
    }
    assert expected_tables.issubset(tables)


def test_import_from_csv_dir(test_db):
    """Test importing CSV files from the synthetic dummy data pack."""
    importer = DatasetImporter(db_path=test_db)
    result = importer.import_dataset(
        dataset_path=DUMMY_CSV_DIR,
        dataset_name="Week_41_Test_CSV",
    )

    assert result.status == "SUCCESS"
    assert result.source_type == "csv"
    assert result.total_records == 45
    assert result.table_counts["pwd_shops"] == 5
    assert result.table_counts["beneficiaries"] == 20
    assert result.table_counts["inventory"] == 10
    assert result.table_counts["transactions"] == 5
    assert result.table_counts["pwd_audits"] == 5

    # Check database records
    with get_db_connection(test_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM beneficiaries WHERE import_id = ?", (result.import_id,))
        assert cursor.fetchone()["cnt"] == 20

        cursor.execute("SELECT COUNT(*) as cnt FROM import_batches WHERE import_id = ?", (result.import_id,))
        assert cursor.fetchone()["cnt"] == 1


def test_import_from_json(test_db):
    """Test importing consolidated JSON dataset."""
    importer = DatasetImporter(db_path=test_db)
    result = importer.import_dataset(
        dataset_path=DUMMY_JSON_FILE,
        dataset_name="Week_41_Test_JSON",
    )

    assert result.status == "SUCCESS"
    assert result.source_type == "json"
    assert result.total_records == 45
    assert result.table_counts["beneficiaries"] == 20


def test_multiple_imports_preserve_history(test_db):
    """Verify that sequential weekly imports do not overwrite each other."""
    importer = DatasetImporter(db_path=test_db)
    
    # Import Week 1 (from CSV)
    batch1 = importer.import_dataset(DUMMY_CSV_DIR, dataset_name="Week_41")
    # Import Week 2 (from JSON)
    batch2 = importer.import_dataset(DUMMY_JSON_FILE, dataset_name="Week_42")

    assert batch1.import_id != batch2.import_id

    imports = importer.list_imports()
    assert len(imports) == 2
    import_ids = {imp.import_id for imp in imports}
    assert batch1.import_id in import_ids
    assert batch2.import_id in import_ids

    # Total beneficiaries should now be 40 (20 per import)
    with get_db_connection(test_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM beneficiaries")
        assert cursor.fetchone()["cnt"] == 40


def test_api_import_and_list_endpoints(monkeypatch, test_db):
    """Test POST /api/import and GET /api/imports endpoints."""
    # Monkeypatch the global importer's db_path to use test_db
    from src.api.main import importer
    monkeypatch.setattr(importer, "db_path", test_db)

    # 1. Test POST /api/import
    payload = {
        "dataset_path": str(DUMMY_CSV_DIR),
        "dataset_name": "API_Test_Batch",
    }
    response = client.post("/api/import", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["total_records"] == 45
    assert "import_id" in data

    # 2. Test GET /api/imports
    list_response = client.get("/api/imports")
    assert list_response.status_code == 200
    batch_list = list_response.json()
    assert len(batch_list) >= 1
    assert batch_list[0]["dataset_name"] == "API_Test_Batch"


def test_import_nonexistent_path():
    """Verify appropriate 404 error when path doesn't exist."""
    response = client.post("/api/import", json={"dataset_path": "/invalid/nonexistent/path"})
    assert response.status_code == 404

