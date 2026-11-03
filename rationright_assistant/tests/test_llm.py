"""
Unit and integration tests for Phase 6: Grounded Response Generation with Gemini & Strict Prompting.
"""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
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


@pytest.fixture
def chat_fixture(tmp_path):
    """Initializes database with sample data and builds router and generator."""
    db_file = tmp_path / "test_chat.db"
    chroma_dir = tmp_path / "test_chroma"
    init_db(db_file)

    importer = DatasetImporter(db_path=db_file)
    batch = importer.import_dataset(DUMMY_CSV_DIR, dataset_name="Week_41_Verified")

    retriever = DictionaryRetriever(chroma_dir=chroma_dir)
    router = QueryRouter(db_path=db_file, retriever=retriever)
    generator = GroundedGenerator()
    return router, generator, batch.import_id


def test_grounded_beneficiary_counts(chat_fixture):
    """Test answering beneficiary count questions with verified figures and citation."""
    router, generator, import_id = chat_fixture
    req = QueryRequest(question="How many beneficiaries were imported this week?")
    ctx = router.route_and_resolve(req)
    res = generator.generate_response(ctx)

    assert res.is_supported is True
    assert import_id in res.answer
    assert "20" in res.answer
    assert "15" in res.answer  # PHH
    assert "5" in res.answer   # AAY


def test_grounded_duplicate_flags_neutrality(chat_fixture):
    """Test duplicate flags answering: must cite records and NEVER declare fraud."""
    router, generator, import_id = chat_fixture
    req = QueryRequest(question="Which records have duplicate flags?")
    ctx = router.route_and_resolve(req)
    res = generator.generate_response(ctx)

    assert res.is_supported is True
    assert "BEN007" in res.answer
    assert "BEN014" in res.answer
    assert import_id in res.answer

    # Strict Fraud Disclaimer Enforcement
    lower_ans = res.answer.lower()
    assert "fraud" not in lower_ans or "not" in lower_ans
    assert "guilty" not in lower_ans
    assert "corrupt" not in lower_ans


def test_grounded_unsupported_refusal(chat_fixture):
    """Test strict refusal of questions unsupported by imported RationRight data."""
    router, generator, _ = chat_fixture
    req = QueryRequest(question="What is the capital of Italy and who is the prime minister?")
    ctx = router.route_and_resolve(req)
    res = generator.generate_response(ctx)

    assert res.is_supported is False
    assert "The imported RationRight datasets do not contain information to answer this question" in res.answer


def test_grounded_definition_answering(chat_fixture):
    """Test explaining system flags via RAG documentation."""
    router, generator, _ = chat_fixture
    req = QueryRequest(question="What does possible_duplicate mean?")
    ctx = router.route_and_resolve(req)
    res = generator.generate_response(ctx)

    assert res.is_supported is True
    assert "Possible Duplicate" in res.answer
    assert "fingerprint" in res.answer.lower() or "biometric" in res.answer.lower()


def test_api_chat_endpoint():
    """Test POST /api/chat endpoint."""
    payload = {"question": "Which shops have the highest complaints?"}
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_supported"] is True
    assert "PWD004" in data["answer"]
    assert "Import ID" in data["answer"]
    assert "evidence" in data

