import pytest
import time
from fastapi.testclient import TestClient
from web.backend.main import app

client = TestClient(app)

def test_job_submission():
    response = client.post("/api/jobs", json={
        "description": "draw auth sequence",
        "aspect_ratio": "16:9",
        "resolution": "2K"
    })
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    
def test_sse_stream_not_found():
    response = client.get("/api/jobs/stream/invalid_id")
    assert response.status_code == 404

def test_full_job_flow():
    # Submit job
    response = client.post("/api/jobs", json={
        "description": "test diagram flow",
        "aspect_ratio": "1:1",
        "resolution": "1K"
    })
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    
    # Sleep a moment to let mock generation task complete
    time.sleep(1.5)
    
    # Check history
    history_resp = client.get("/api/history")
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) > 0
    assert history[0]["id"] == job_id
    assert history[0]["aspect_ratio"] == "1:1"
    assert history[0]["resolution"] == "1K"
    assert history[0]["imageUrl"].startswith("/static/")
