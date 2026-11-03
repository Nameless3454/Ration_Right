"""
Unit and integration tests for Phase 4: Basic RAG Knowledge Base with ChromaDB.
"""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.rag.vector_store import DictionaryRetriever, get_retriever
from src.rag.dictionary_data import DICTIONARY_CHUNKS

client = TestClient(app)


@pytest.fixture
def test_retriever(tmp_path):
    """Provides an isolated ChromaDB instance for testing."""
    chroma_dir = tmp_path / "test_chroma"
    return DictionaryRetriever(chroma_dir=chroma_dir)


def test_retriever_initialization(test_retriever):
    """Verify that ChromaDB seeds all dictionary chunks."""
    assert test_retriever.collection.count() == len(DICTIONARY_CHUNKS)


def test_flag_definition_retrieval(test_retriever):
    """Test retrieving semantic definition for 'possible_duplicate'."""
    results = test_retriever.query("What does possible_duplicate mean in RationRight?", top_k=2)
    assert len(results) > 0
    top = results[0]
    assert top["id"] == "flag_possible_duplicate"
    assert "review lead" in top["content"]
    assert "not proof of fraud" in top["content"]


def test_welfare_policy_retrieval(test_retriever):
    """Test retrieving statutory quota for AAY and PHH."""
    # Test AAY
    results_aay = test_retriever.query("What is the statutory monthly quota for Antyodaya Anna Yojana?", top_k=2)
    assert len(results_aay) > 0
    assert results_aay[0]["id"] == "quota_aay"
    assert "35.0 kg" in results_aay[0]["content"]

    # Test PHH
    results_phh = test_retriever.query("How much grain does a Priority Household get per person?", top_k=2)
    assert len(results_phh) > 0
    assert results_phh[0]["id"] == "quota_phh"
    assert "5.0 kg" in results_phh[0]["content"]


def test_inventory_definition_retrieval(test_retriever):
    """Test retrieving stock ledger definitions and mismatch formula."""
    results = test_retriever.query("How is stock mismatch and closing stock discrepancy calculated?", top_k=2)
    assert len(results) > 0
    match_ids = {r["id"] for r in results}
    assert "alert_stock_mismatch" in match_ids or "schema_inventory" in match_ids


def test_governance_disclaimer_retrieval(test_retriever):
    """Test retrieving administrative boundaries regarding fraud declarations."""
    results = test_retriever.query("Can the AI declare a beneficiary fraudulent?", top_k=2)
    assert len(results) > 0
    top = results[0]
    assert "governance" in top["category"]
    assert "NEVER declare a beneficiary 'fraudulent'" in top["content"]


def test_api_dictionary_search_endpoint():
    """Test POST /api/dictionary/search endpoint."""
    payload = {
        "query": "What does manual_override mean in distribution transactions?",
        "top_k": 2,
    }
    response = client.post("/api/dictionary/search", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data) <= 2
    assert any("manual_override" in item["id"] for item in data)
    assert "content" in data[0]
    assert "score" in data[0]
