"""
Tests for Conversational Response Generation & Natural Language Presentation.
Validates the 6 core question types:
1. Simple numerical question
2. Beneficiary summary
3. Suspicious-record question
4. Inventory stock / comparison question
5. Field-definition question
6. Unsupported general question
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
def conv_env(tmp_path):
    """Sets up an isolated database and router with imported weekly data."""
    db_file = tmp_path / "conv_test.db"
    chroma_dir = tmp_path / "conv_chroma"
    init_db(db_file)

    importer = DatasetImporter(db_path=db_file)
    batch = importer.import_dataset(DUMMY_CSV_DIR, dataset_name="Week_41_Verified")

    retriever = DictionaryRetriever(chroma_dir=chroma_dir)
    router = QueryRouter(db_path=db_file, retriever=retriever)
    generator = GroundedGenerator()
    return router, generator, batch.import_id


# 1. Simple Numerical Question
def test_conversational_simple_numerical_question(conv_env):
    """Test 'How many beneficiaries are there?' returns a natural answer first with verified counts."""
    router, generator, import_id = conv_env
    req = QueryRequest(question="How many beneficiaries are there?")
    ctx = router.route_and_resolve(req)
    res = generator.generate_response(ctx)

    assert res.is_supported is True
    # Direct answer first:
    assert res.answer.startswith("There are 20 beneficiaries registered")
    # Breakdown included:
    assert "Total Registered Beneficiaries:** 20" in res.answer
    assert "Priority Households (PHH):** 15" in res.answer
    assert "Antyodaya Anna Yojana (AAY):** 5" in res.answer
    # Conversational explanation:
    assert "Among these, 2 records are flagged as possible duplicates and 1 record has a multiple-claims flag" in res.answer
    assert "not proof of wrongdoing" in res.answer
    # Source attribution at bottom:
    assert res.answer.strip().endswith(f"*Source: `Week_41_Verified` (Import ID: `{import_id}`)*")


# 2. Beneficiary Summary Question
def test_conversational_beneficiary_summary(conv_env):
    """Test asking for a summary of beneficiaries provides a structured, conversational summary."""
    router, generator, import_id = conv_env
    req = QueryRequest(question="Provide a summary of beneficiaries registered this week")
    ctx = router.route_and_resolve(req)
    res = generator.generate_response(ctx)

    assert res.is_supported is True
    assert "There are 20 beneficiaries registered" in res.answer or "Beneficiary Enrollment Summary" in res.answer
    assert "PHH" in res.answer
    assert "AAY" in res.answer
    assert "Biometrically Verified" in res.answer
    assert "*Source:" in res.answer


# 3. Suspicious Record Question
def test_conversational_suspicious_record_question(conv_env):
    """Test 'Which records have duplicate flags?' answers conversationally with IDs and neutrality disclaimer."""
    router, generator, import_id = conv_env
    req = QueryRequest(question="Which records have duplicate flags?")
    ctx = router.route_and_resolve(req)
    res = generator.generate_response(ctx)

    assert res.is_supported is True
    # Direct answer first:
    assert "There are 2 beneficiary records flagged as possible duplicates" in res.answer
    # Identifies records:
    assert "BEN007" in res.answer
    assert "BEN014" in res.answer
    # Neutrality disclaimer:
    assert "administrative review lead" in res.answer.lower()
    assert "not evidence of fraud" in res.answer.lower()
    assert "appeal" in res.answer.lower()
    # Source at bottom:
    assert "*Source:" in res.answer


# 4. Inventory Comparison / Stock Question
def test_conversational_inventory_stock_question(conv_env):
    """Test 'What is the current stock of rice and wheat?' returns a conversational ledger and table."""
    router, generator, import_id = conv_env
    req = QueryRequest(question="What is the current stock of rice and wheat?")
    ctx = router.route_and_resolve(req)
    res = generator.generate_response(ctx)

    assert res.is_supported is True
    # Natural language lead:
    assert "verified commodity inventory ledger and physical audit status" in res.answer
    # Markdown table structure:
    assert "| Fair Price Shop | Commodity |" in res.answer
    assert "| :--- | :--- |" in res.answer
    # Administrative notice and source:
    assert "Administrative Notice:" in res.answer
    assert f"*Source: `Week_41_Verified` (Import ID: `{import_id}`)*" in res.answer


# 5. Field Definition Question
def test_conversational_field_definition_question(conv_env):
    """Test 'What does statutory quota mean?' returns official RAG policy documentation."""
    router, generator, _ = conv_env
    req = QueryRequest(question="What does statutory quota mean?")
    ctx = router.route_and_resolve(req)
    res = generator.generate_response(ctx)

    assert res.is_supported is True
    assert res.route_type == RouteType.RAG_DEFINITION
    # Conversational intro:
    assert "According to official RationRight system documentation" in res.answer
    # Entitlement details from chroma:
    assert "5 kg" in res.answer or "NFSA" in res.answer or "quota" in res.answer.lower()
    assert "*Source: RationRight Official Data Dictionary" in res.answer


# 6. Unsupported General Question
def test_conversational_unsupported_question(conv_env):
    """Test out-of-domain questions are strictly refused with zero hallucination."""
    router, generator, _ = conv_env
    req = QueryRequest(question="What is the weather in Delhi?")
    ctx = router.route_and_resolve(req)
    res = generator.generate_response(ctx)

    assert res.is_supported is False
    assert res.route_type == RouteType.UNSUPPORTED
    assert "The imported RationRight datasets do not contain information to answer this question" in res.answer

