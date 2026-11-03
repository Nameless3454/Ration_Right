"""
Unit and integration tests for Phase 5: Question Routing between Structured SQL and RAG.
"""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.config import settings
from src.db.database import init_db
from src.ingestion.importer import DatasetImporter
from src.models.schemas import QueryRequest, RouteType
from src.rag.vector_store import DictionaryRetriever
from src.router.query_router import QueryRouter

client = TestClient(app)

DUMMY_CSV_DIR = settings.BASE_DIR.parent / "rationright-rag" / "RationRight_Dummy_Data_Pack"
if not DUMMY_CSV_DIR.exists():
    DUMMY_CSV_DIR = settings.BASE_DIR.parent / "data" / "uploaded_dataset"

DUMMY_JSON_FILE = DUMMY_CSV_DIR / "rationright_demo_data.json"


@pytest.fixture
def router_fixture(tmp_path):
    """Sets up an isolated database with two imports and a test router."""
    db_file = tmp_path / "test_router.db"
    chroma_dir = tmp_path / "test_chroma"
    init_db(db_file)

    importer = DatasetImporter(db_path=db_file)
    batch1 = importer.import_dataset(DUMMY_CSV_DIR, dataset_name="Week_41_CSV")
    batch2 = importer.import_dataset(DUMMY_JSON_FILE, dataset_name="Week_42_JSON")

    retriever = DictionaryRetriever(chroma_dir=chroma_dir)
    router = QueryRouter(db_path=db_file, retriever=retriever)
    return router, batch1.import_id, batch2.import_id


def test_route_beneficiary_counts(router_fixture):
    """Verify routing of 'how many beneficiaries' questions."""
    router, _, _ = router_fixture
    req = QueryRequest(question="How many beneficiaries were imported this week?")
    ctx = router.route_and_resolve(req)

    assert ctx.route_type == RouteType.STRUCTURED
    assert ctx.intent == "BENEFICIARIES_COUNT_QUERY"
    assert ctx.is_supported is True
    assert ctx.sql_data["total_beneficiaries"] == 20
    assert ctx.sql_data["phh_count"] == 15
    assert ctx.sql_data["aay_count"] == 5
    assert ctx.import_id_cited is not None


def test_route_duplicate_flags(router_fixture):
    """Verify routing of duplicate records filter query."""
    router, _, _ = router_fixture
    req = QueryRequest(question="Which records have duplicate flags?")
    ctx = router.route_and_resolve(req)

    assert ctx.route_type == RouteType.STRUCTURED
    assert ctx.intent == "DUPLICATE_FLAGS_QUERY"
    assert ctx.sql_data["count"] == 2
    ben_ids = {r["beneficiary_id"] for r in ctx.sql_data["records"]}
    assert ben_ids == {"BEN007", "BEN014"}


def test_route_shop_complaints(router_fixture):
    """Verify routing of shop complaint ranking queries."""
    router, _, _ = router_fixture
    req = QueryRequest(question="Which shops have the highest complaints?")
    ctx = router.route_and_resolve(req)

    assert ctx.route_type == RouteType.STRUCTURED
    assert ctx.intent == "SHOP_COMPLAINTS_RANKING"
    assert len(ctx.sql_data["ranking"]) > 0
    assert ctx.sql_data["ranking"][0]["pwd_id"] == "PWD004"
    assert ctx.sql_data["ranking"][0]["complaints_count"] == 6


def test_route_comparison(router_fixture):
    """Verify routing of week-over-week comparison questions."""
    router, _, _ = router_fixture
    req = QueryRequest(question="Compare this week's inventory with last week's.")
    ctx = router.route_and_resolve(req)

    assert ctx.route_type == RouteType.STRUCTURED
    assert ctx.intent == "WEEKLY_SNAPSHOT_COMPARISON"
    assert "metadata_comparison" in ctx.sql_data
    assert "inventory_changes" in ctx.sql_data


def test_route_rag_definitions(router_fixture):
    """Verify routing of definition and policy questions to ChromaDB."""
    router, _, _ = router_fixture

    # Test 1: Flag definition
    req_flag = QueryRequest(question="What does possible_duplicate mean?")
    ctx_flag = router.route_and_resolve(req_flag)
    assert ctx_flag.route_type == RouteType.RAG_DEFINITION
    assert ctx_flag.intent == "DATA_DICTIONARY_DEFINITION"
    assert len(ctx_flag.rag_context) > 0
    assert any("possible_duplicate" in doc["id"] for doc in ctx_flag.rag_context)

    # Test 2: Welfare policy quota
    req_quota = QueryRequest(question="What is the statutory quota for AAY households?")
    ctx_quota = router.route_and_resolve(req_quota)
    assert ctx_quota.route_type == RouteType.RAG_DEFINITION
    assert any("quota_aay" in doc["id"] for doc in ctx_quota.rag_context)


def test_route_hybrid(router_fixture):
    """Verify hybrid routing for queries requesting both records and definitions."""
    router, _, _ = router_fixture
    req = QueryRequest(question="Show duplicate records and explain what the duplicate flag means")
    ctx = router.route_and_resolve(req)

    assert ctx.route_type == RouteType.HYBRID
    assert ctx.intent == "HYBRID_RECORDS_AND_DEFINITION"
    assert ctx.sql_data is not None
    assert len(ctx.sql_data["flagged_records"]) == 2
    assert ctx.rag_context is not None
    assert len(ctx.rag_context) > 0


def test_route_unsupported(router_fixture):
    """Verify out-of-domain questions are detected and marked unsupported."""
    router, _, _ = router_fixture
    req = QueryRequest(question="What is the capital of France and what is the weather there?")
    ctx = router.route_and_resolve(req)

    assert ctx.route_type == RouteType.UNSUPPORTED
    assert ctx.intent == "OUT_OF_DOMAIN"
    assert ctx.is_supported is False
    assert ctx.sql_data is None


def test_api_route_endpoint():
    """Test POST /api/route endpoint with FastAPI TestClient."""
    payload = {"question": "How many beneficiaries were imported this week?"}
    response = client.post("/api/route", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["route_type"] == "STRUCTURED"
    assert data["is_supported"] is True
    assert "sql_data" in data

