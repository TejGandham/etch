import os
import pytest
from fastapi.testclient import TestClient
from web.backend.main import app

client = TestClient(app)

def test_scan_codebase():
    # Scan active server directory
    response = client.post("/api/config/scan", json={"path": os.getcwd()})
    assert response.status_code == 200
    data = response.json()
    assert "tree" in data
    assert "readme" in data
    assert "is_valid" in data
    assert data["is_valid"] is True
