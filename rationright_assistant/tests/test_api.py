import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_health_check():
    """Verify /health returns 200 and healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "RationRight AI Assistant" in data["service"]


def test_system_info():
    """Verify /api/info returns operational metadata."""
    response = client.get("/api/info")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "0.1.0"
    assert "data_directory" in data
    assert "db_path" in data
    assert "chroma_directory" in data

