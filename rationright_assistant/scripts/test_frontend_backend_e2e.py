"""
End-to-End integration test script verifying that the FastAPI backend API contracts
expected by the React frontend are 100% functional, verified, and complete.
"""
import sys
from pathlib import Path
from fastapi.testclient import TestClient

from src.api.main import app
from src.config import settings

client = TestClient(app)

def test_frontend_backend_contracts():
    print("Testing End-to-End API Contracts for Frontend...")

    # 1. System info contract (Header component)
    res_info = client.get("/api/info")
    assert res_info.status_code == 200
    info_data = res_info.json()
    assert "service" in info_data
    assert "db_path" in info_data
    print("✓ /api/info matches SystemInfo contract")

    # 2. Imports list contract (SnapshotSelector & Header component)
    res_imports = client.get("/api/imports")
    assert res_imports.status_code == 200
    imports_data = res_imports.json()
    assert isinstance(imports_data, list)
    print(f"✓ /api/imports returned {len(imports_data)} historical imports")

    # 3. Metrics contract (OperationsDashboard component)
    res_metrics = client.get("/api/metrics/latest?limit=50&offset=0")
    assert res_metrics.status_code == 200
    metrics_data = res_metrics.json()
    assert "beneficiaries" in metrics_data
    assert "inventory" in metrics_data
    assert "audits" in metrics_data
    assert "shop_complaints" in metrics_data
    assert "transactions" in metrics_data
    assert "total_inventory_records" in metrics_data
    assert metrics_data["beneficiaries"]["total_beneficiaries"] > 0
    print("✓ /api/metrics/latest matches SnapshotMetricsResponse contract")

    # 4. Chat endpoint contract (FloatingChatbot component)
    res_chat = client.post(
        "/api/chat",
        json={"question": "Which records have duplicate flags?"}
    )
    assert res_chat.status_code == 200
    chat_data = res_chat.json()
    assert "answer" in chat_data
    assert "route_type" in chat_data
    assert "intent" in chat_data
    assert "evidence" in chat_data
    assert chat_data["route_type"] == "STRUCTURED"
    assert "BEN007" in chat_data["answer"] or "BEN014" in chat_data["answer"]
    print("✓ /api/chat matches ChatResponse contract with verified evidence")

    # 5. Unsupported query handling in Chat (FloatingChatbot component)
    res_unsupported = client.post(
        "/api/chat",
        json={"question": "Write a python script to scrape a site"}
    )
    assert res_unsupported.status_code == 200
    unsup_data = res_unsupported.json()
    assert unsup_data["route_type"] == "UNSUPPORTED"
    assert unsup_data["is_supported"] is False
    assert "imported RationRight datasets do not contain information" in unsup_data["answer"]
    print("✓ /api/chat out-of-domain refusal verified")

    print("\nAll Frontend <-> Backend API contracts 100% verified!")

if __name__ == "__main__":
    test_frontend_backend_contracts()

