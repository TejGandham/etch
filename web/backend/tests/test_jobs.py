import os
import pytest
import time

# Set mock environment before importing backend app to prevent hitting live Gemini API in tests
os.environ["GOOGLE_API_KEY"] = "mock"

from fastapi.testclient import TestClient
from web.backend.main import app, execute_generation_task, DiagramRequest, jobs_cache
import etch

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


# --- reference_images wiring ------------------------------------------------


def test_reference_images_threaded_into_run_generation(monkeypatch):
    """req.reference_images is loaded via etch._load_reference_images and threaded
    into etch._run_generation as the reference_images= kwarg."""
    captured = {}

    def fake_load_reference_images(paths, provider):
        captured["load_paths"] = paths
        return ["FAKE_REF_1", "FAKE_REF_2"]

    def fake_run_generation(**kwargs):
        captured["reference_images"] = kwargs.get("reference_images")
        with etch._jobs_lock:
            etch._jobs[kwargs["job_id"]] = {
                "status": "complete",
                "created": etch.datetime.now(),
                "file_path": "diagram_unused.png",
            }

    monkeypatch.setenv("GOOGLE_API_KEY", "real-key-not-mock")
    monkeypatch.setattr(etch, "_load_reference_images", fake_load_reference_images)
    monkeypatch.setattr(etch, "_run_generation", fake_run_generation)

    job_id = "test-job-refs-threaded"
    jobs_cache[job_id] = {"status": "queued", "error": None}
    req = DiagramRequest(
        description="draw a box",
        reference_images=["/tmp/ref_a.png", "/tmp/ref_b.png"],
    )
    execute_generation_task(job_id, req)

    assert captured["load_paths"] == ["/tmp/ref_a.png", "/tmp/ref_b.png"]
    assert captured["reference_images"] == ["FAKE_REF_1", "FAKE_REF_2"]
    assert jobs_cache[job_id]["status"] == "complete"


def test_reference_image_load_failure_marks_job_failed(monkeypatch):
    """A ValueError from _load_reference_images (bad path, unsupported format,
    over provider max, etc.) fails the job with the error string instead of
    crashing the background task or calling _run_generation."""

    def fake_load_reference_images_raises(paths, provider):
        raise ValueError("cannot read reference image: boom")

    run_generation_called = {"value": False}

    def fake_run_generation(**kwargs):
        run_generation_called["value"] = True

    monkeypatch.setenv("GOOGLE_API_KEY", "real-key-not-mock")
    monkeypatch.setattr(etch, "_load_reference_images", fake_load_reference_images_raises)
    monkeypatch.setattr(etch, "_run_generation", fake_run_generation)

    job_id = "test-job-refs-load-fail"
    jobs_cache[job_id] = {"status": "queued", "error": None}
    req = DiagramRequest(
        description="draw a box",
        reference_images=["/tmp/bad_ref.png"],
    )
    execute_generation_task(job_id, req)

    assert jobs_cache[job_id]["status"] == "failed"
    assert "boom" in jobs_cache[job_id]["error"]
    assert run_generation_called["value"] is False


def test_no_reference_images_field_behaves_as_before():
    """Omitting reference_images entirely is unaffected: mock mode still
    completes normally (matches test_full_job_flow's baseline behavior)."""
    response = client.post("/api/jobs", json={
        "description": "no references supplied",
        "aspect_ratio": "1:1",
        "resolution": "1K"
    })
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    time.sleep(1.5)

    assert jobs_cache[job_id]["status"] == "complete"
    assert jobs_cache[job_id]["imageUrl"].startswith("/static/")


def test_reference_images_ignored_in_mock_mode():
    """Mock mode (no key configured / key == 'mock') never calls the provider,
    so reference_images must not be loaded or cause a failure there — even a
    nonexistent path must not break the mock-mode fallback."""
    response = client.post("/api/jobs", json={
        "description": "mock mode with references",
        "aspect_ratio": "1:1",
        "resolution": "1K",
        "reference_images": ["/nonexistent/path/should/not/be/read.png"]
    })
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    time.sleep(1.5)

    assert jobs_cache[job_id]["status"] == "complete"
    assert jobs_cache[job_id]["imageUrl"].startswith("/static/")
