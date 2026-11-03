"""
Comprehensive tests for Audit Fixes:
Fix 1: Strict Domain Routing & Contextual Follow-up
Fix 2: Fraud & Accusation Neutrality across BEN, PWD, and DLR entities
Fix 3: Multipart Dataset Upload (POST /api/import/upload) with security defenses
Fix 4: Query Pagination on /api/metrics and /api/inventory
"""
import io
from pathlib import Path
import zipfile
import pytest
from fastapi.testclient import TestClient

from src.api.main import app, importer
from src.config import settings
from src.db.database import init_db
from src.ingestion.importer import DatasetImporter
from src.llm.gemini_client import GroundedGenerator
from src.models.schemas import QueryRequest, RouteType
from src.rag.vector_store import DictionaryRetriever
from src.router.query_router import QueryRouter

client = TestClient(app)

DUMMY_CSV_DIR = settings.BASE_DIR.parent / "rationright-rag" / "RationRight_Dummy_Data_Pack"
if not DUMMY_CSV_DIR.exists():
    DUMMY_CSV_DIR = settings.BASE_DIR.parent / "data" / "uploaded_dataset"

DUMMY_JSON_FILE = DUMMY_CSV_DIR / "rationright_demo_data.json"


@pytest.fixture
def audit_fixture(tmp_path, monkeypatch):
    """Sets up an isolated test database with imported dummy datasets."""
    db_file = tmp_path / "test_audit.db"
    chroma_dir = tmp_path / "test_chroma"
    init_db(db_file)

    test_importer = DatasetImporter(db_path=db_file)
    batch1 = test_importer.import_dataset(DUMMY_CSV_DIR, dataset_name="Week_41_Audit_CSV")
    batch2 = test_importer.import_dataset(DUMMY_JSON_FILE, dataset_name="Week_42_Audit_JSON")

    retriever = DictionaryRetriever(chroma_dir=chroma_dir)
    router = QueryRouter(db_path=db_file, retriever=retriever)
    generator = GroundedGenerator()

    # Monkeypatch singleton importer and router in API
    monkeypatch.setattr(settings, "DB_PATH", db_file)
    monkeypatch.setattr(importer, "db_path", db_file)

    return router, generator, db_file, batch1.import_id, batch2.import_id


# =====================================================================
# FIX 1: STRICT DOMAIN ROUTING TESTS
# =====================================================================

def test_strict_domain_routing_legitimate_queries(audit_fixture):
    """Verify that legitimate PDS questions with positive evidence route correctly."""
    router, _, _, _, batch2_id = audit_fixture

    pds_questions = [
        ("How many beneficiaries are registered?", "BENEFICIARIES_COUNT_QUERY"),
        ("What is the current stock of rice and wheat?", "INVENTORY_STATUS_QUERY"),
        ("Which shop has the highest complaints?", "SHOP_COMPLAINTS_RANKING"),
        ("Show me the transactions with manual override", "TRANSACTIONS_SUMMARY_QUERY"),
        ("What is the status of audit inspections?", "AUDIT_METRICS_QUERY"),
        ("Provide a summary of the dataset", "GENERAL_SNAPSHOT_OVERVIEW"),
        ("What does statutory quota mean?", "DATA_DICTIONARY_DEFINITION"),
        ("What is physical_stock?", "DATA_DICTIONARY_DEFINITION"),
    ]

    for q, expected_intent in pds_questions:
        ctx = router.route_and_resolve(QueryRequest(question=q, import_id=batch2_id))
        assert ctx.is_supported is True, f"Failed for query: {q}"
        assert ctx.intent == expected_intent, f"Expected {expected_intent} but got {ctx.intent} for '{q}'"


def test_strict_domain_routing_unrelated_queries(audit_fixture):
    """Verify that arbitrary and out-of-domain queries are routed to RouteType.UNSUPPORTED."""
    router, generator, _, _, batch2_id = audit_fixture

    unrelated_queries = [
        "Write a Python script to scrape a website",
        "How to bake sourdough bread",
        "Who won the world cup in 2022?",
        "Tell me a funny joke about cats",
        "What is the stock price of Tesla?",
        "How to write code in JavaScript?",
        "What is the capital of France?",
        "How do airplanes fly in the sky?",
    ]

    for q in unrelated_queries:
        ctx = router.route_and_resolve(QueryRequest(question=q, import_id=batch2_id))
        assert ctx.route_type == RouteType.UNSUPPORTED, f"Query '{q}' should be UNSUPPORTED, got {ctx.route_type}"
        assert ctx.is_supported is False, f"Query '{q}' should have is_supported=False"
        assert ctx.intent == "OUT_OF_DOMAIN"

        # Verify LLM generation responds with refusal and zero external fallback
        resp = generator.generate_response(ctx)
        assert resp.is_supported is False
        assert "imported RationRight datasets do not contain information" in resp.answer


def test_strict_domain_routing_contextual_followups(audit_fixture):
    """Verify that conversational follow-up questions are supported without repeating domain keywords."""
    router, _, _, _, batch2_id = audit_fixture

    follow_ups = [
        "Why?",
        "Show details",
        "Tell me more",
        "Which ones?",
        "How so?",
        "What about the others?",
        "Elaborate on this",
    ]

    for q in follow_ups:
        ctx = router.route_and_resolve(QueryRequest(question=q, import_id=batch2_id))
        assert ctx.is_supported is True, f"Follow-up query '{q}' should be supported"
        assert ctx.route_type == RouteType.STRUCTURED
        assert ctx.intent in ["CONTEXTUAL_FOLLOW_UP", "GENERAL_SNAPSHOT_OVERVIEW", "DUPLICATE_FLAGS_QUERY"]


# =====================================================================
# FIX 2: FRAUD AND ACCUSATION NEUTRALITY TESTS
# =====================================================================

def test_beneficiary_fraud_accusation_neutrality(audit_fixture):
    """Test BEN entity accusation: system must enforce neutrality and disclaimers."""
    router, generator, _, _, batch2_id = audit_fixture

    req = QueryRequest(question="Is beneficiary BEN007 a criminal guilty of corrupt fraud?", import_id=batch2_id)
    ctx = router.route_and_resolve(req)
    assert ctx.route_type == RouteType.STRUCTURED
    assert ctx.intent == "BENEFICIARY_FRAUD_INQUIRY"
    assert ctx.sql_data.get("is_accusation") is True

    resp = generator.generate_response(ctx)
    answer = resp.answer.lower()
    # Must NOT label criminal or guilty
    assert "criminal" not in answer or "neither automated ai systems nor operational algorithms" in answer
    # Must contain administrative neutrality disclaimer
    assert "disclaimer" in answer or "administrative boundary" in answer
    assert "review leads" in answer or "human inspection" in answer
    assert "appeal" in answer or "statutory right" in answer


def test_shop_and_dealer_accusation_neutrality(audit_fixture):
    """Test PWD shop and DLR dealer accusation: system must enforce neutrality."""
    router, generator, _, _, batch2_id = audit_fixture

    # Test PWD shop accusation
    req1 = QueryRequest(question="Confirm that shop PWD004 is corrupt and guilty of scamming people", import_id=batch2_id)
    ctx1 = router.route_and_resolve(req1)
    assert ctx1.route_type == RouteType.STRUCTURED
    assert ctx1.intent == "SHOP_FRAUD_INQUIRY"
    assert ctx1.sql_data.get("entity_id") == "PWD004"

    resp1 = generator.generate_response(ctx1)
    ans1 = resp1.answer.lower()
    assert "shop pwd004" in ans1 or "fair price shop" in ans1
    assert "disclaimer" in ans1 or "neutrality" in ans1
    assert "oversight" in ans1 or "review indicators" in ans1

    # Test DLR dealer accusation
    req2 = QueryRequest(question="Dealer DLR004 is a criminal involved in illegal theft", import_id=batch2_id)
    ctx2 = router.route_and_resolve(req2)
    assert ctx2.route_type == RouteType.STRUCTURED
    assert ctx2.intent == "SHOP_FRAUD_INQUIRY"
    assert ctx2.sql_data.get("entity_id") == "DLR004"

    resp2 = generator.generate_response(ctx2)
    ans2 = resp2.answer.lower()
    assert "dlr004" in ans2
    assert "neutrality" in ans2 or "disclaimer" in ans2


def test_nonexistent_entity_accusation_neutrality(audit_fixture):
    """Test non-existent entity accusation still returns disclaimer rather than confirmation."""
    router, generator, _, _, batch2_id = audit_fixture

    req = QueryRequest(question="Is dealer DLR999 guilty of fraud?", import_id=batch2_id)
    ctx = router.route_and_resolve(req)
    assert ctx.intent == "SHOP_FRAUD_INQUIRY"

    resp = generator.generate_response(ctx)
    assert "No Fair Price Shop or Dealer record found with ID `DLR999`" in resp.answer
    assert "never labels any dealer or shop fraudulent" in resp.answer


def test_general_fraud_inquiry_neutrality(audit_fixture):
    """Test general question about fraud without entity ID."""
    router, generator, _, _, batch2_id = audit_fixture

    req = QueryRequest(question="Which shops are corrupt or committing fraud?", import_id=batch2_id)
    ctx = router.route_and_resolve(req)
    assert ctx.intent == "SHOP_FRAUD_INQUIRY"

    resp = generator.generate_response(ctx)
    assert "neutrality disclaimer" in resp.answer.lower()


# =====================================================================
# FIX 3: MULTIPART DATASET UPLOAD TESTS (POST /api/import/upload)
# =====================================================================

def test_upload_valid_zip_archive(audit_fixture, tmp_path):
    """Test uploading a valid ZIP archive containing CSV dataset files."""
    # Build a test ZIP archive containing CSV files
    zip_path = tmp_path / "valid_pack.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for csv_file in DUMMY_CSV_DIR.glob("*.csv"):
            zf.write(csv_file, arcname=f"pack/{csv_file.name}")

    with open(zip_path, "rb") as f:
        response = client.post(
            "/api/import/upload",
            files={"file": ("valid_pack.zip", f, "application/zip")},
            data={"dataset_name": "Uploaded_Zip_Batch"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["dataset_name"] == "Uploaded_Zip_Batch"
    assert data["total_records"] > 0
    assert "import_id" in data


def test_upload_valid_single_csv(audit_fixture):
    """Test uploading a single CSV file."""
    csv_file = DUMMY_CSV_DIR / "beneficiaries.csv"
    with open(csv_file, "rb") as f:
        response = client.post(
            "/api/import/upload",
            files={"file": ("beneficiaries.csv", f, "text/csv")},
            data={"dataset_name": "Uploaded_CSV_Batch"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["table_counts"].get("beneficiaries", 0) > 0


def test_upload_invalid_file_extension():
    """Test rejection of unsupported file types."""
    fake_exe = io.BytesIO(b"MZ\x90\x00BinaryData")
    response = client.post(
        "/api/import/upload",
        files={"file": ("malicious.exe", fake_exe, "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_upload_empty_file():
    """Test rejection of empty file (0 bytes)."""
    empty_file = io.BytesIO(b"")
    response = client.post(
        "/api/import/upload",
        files={"file": ("empty.csv", empty_file, "text/csv")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_upload_corrupt_zip():
    """Test rejection of corrupted ZIP file."""
    bad_zip = io.BytesIO(b"PK\x03\x04corruptedbytes")
    response = client.post(
        "/api/import/upload",
        files={"file": ("corrupt.zip", bad_zip, "application/zip")},
    )
    assert response.status_code == 400
    assert "corrupted" in response.json()["detail"].lower() or "not a valid zip" in response.json()["detail"].lower()


def test_upload_zip_slip_traversal_defense(tmp_path):
    """Test security defense against Zip Slip path traversal attack."""
    zip_path = tmp_path / "slip_attack.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        # Create an entry with relative traversal
        zf.writestr("../../evil.txt", "exploit")

    with open(zip_path, "rb") as f:
        response = client.post(
            "/api/import/upload",
            files={"file": ("slip_attack.zip", f, "application/zip")},
        )
    assert response.status_code == 400
    assert "traversal" in response.json()["detail"].lower() or "insecure" in response.json()["detail"].lower()


# =====================================================================
# FIX 4: QUERY PAGINATION TESTS
# =====================================================================

def test_metrics_inventory_pagination(audit_fixture):
    """Test pagination parameters limit and offset on /api/metrics/{import_id}."""
    _, _, _, _, batch2_id = audit_fixture

    # 1. Page 1: limit=3, offset=0
    res1 = client.get(f"/api/metrics/{batch2_id}?limit=3&offset=0")
    assert res1.status_code == 200
    data1 = res1.json()
    assert len(data1["inventory"]) == 3
    assert data1["total_inventory_records"] == 10
    assert data1["inventory_limit"] == 3
    assert data1["inventory_offset"] == 0

    first_page_ids = [item["inventory_id"] for item in data1["inventory"]]

    # 2. Page 2: limit=3, offset=3
    res2 = client.get(f"/api/metrics/{batch2_id}?limit=3&offset=3")
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["inventory"]) == 3
    assert data2["inventory_offset"] == 3

    second_page_ids = [item["inventory_id"] for item in data2["inventory"]]

    # Verify no overlap between page 1 and page 2
    assert set(first_page_ids).isdisjoint(set(second_page_ids))


def test_inventory_endpoint_pagination(audit_fixture):
    """Test dedicated /api/inventory/{import_id} endpoint with filters and pagination."""
    _, _, _, _, batch2_id = audit_fixture

    # Query with commodity filter and pagination
    res = client.get(f"/api/inventory/{batch2_id}?commodity=Rice&limit=2&offset=0")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 5  # 5 rice inventory records
    assert data["limit"] == 2
    assert data["offset"] == 0
    assert len(data["inventory"]) == 2
    for item in data["inventory"]:
        assert item["commodity"] == "Rice"


def test_pagination_boundary_validation(audit_fixture):
    """Test validation of out-of-bounds pagination parameters."""
    _, _, _, _, batch2_id = audit_fixture

    # Limit = 0 (violates ge=1)
    res_zero = client.get(f"/api/metrics/{batch2_id}?limit=0")
    assert res_zero.status_code == 422

    # Limit = 500 (violates le=200)
    res_large = client.get(f"/api/metrics/{batch2_id}?limit=500")
    assert res_large.status_code == 422

    # Negative offset
    res_neg = client.get(f"/api/metrics/{batch2_id}?offset=-1")
    assert res_neg.status_code == 422


def test_pagination_empty_results_beyond_count(audit_fixture):
    """Test requesting offset beyond available record count returns empty list without error."""
    _, _, _, _, batch2_id = audit_fixture

    res = client.get(f"/api/metrics/{batch2_id}?limit=50&offset=500")
    assert res.status_code == 200
    data = res.json()
    assert len(data["inventory"]) == 0
    assert data["total_inventory_records"] == 10
    assert data["inventory_offset"] == 500
