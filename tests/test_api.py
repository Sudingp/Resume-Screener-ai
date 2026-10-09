"""Unit and integration tests for FastAPI REST API endpoints."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from screener.api import app

client = TestClient(app)
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "resumes"


def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "schema_version" in data


def test_screen_batch_endpoint():
    payload = {
        "input_dir": str(FIXTURES_DIR),
        "concurrency": 2,
        "no_llm": True,
        "no_github": True,
    }
    response = client.post("/screen", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Batch screening completed successfully"
    summary = data["summary"]
    assert summary["total_files"] == 15
    assert summary["duplicates_skipped"] == 1
    assert len(data["top_candidates"]) > 0


def test_get_results_endpoint():
    # Fetch results after batch screen
    response = client.get("/results")
    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0

    # Filter by eligible
    res_eligible = client.get("/results?status_filter=eligible")
    assert res_eligible.status_code == 200
    for r in res_eligible.json():
        assert r["status"] == "eligible"

    # Filter by rejected
    res_rejected = client.get("/results?status_filter=rejected")
    assert res_rejected.status_code == 200
    for r in res_rejected.json():
        assert r["status"] == "rejected"


def test_screen_single_file_endpoint():
    pdf_path = FIXTURES_DIR / "python_ai_strong.pdf"
    with open(pdf_path, "rb") as f:
        files = {"file": ("python_ai_strong.pdf", f, "application/pdf")}
        response = client.post("/screen/file", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "eligible"
    assert data["eligible"] is True
    assert data["total_score"] is not None
    assert "score_breakdown" in data
    assert "Python" in data["matched_skills"]


def test_screen_invalid_directory_returns_400():
    payload = {
        "input_dir": "non_existent_folder_xyz_123",
    }
    response = client.post("/screen", json=payload)
    assert response.status_code == 400
