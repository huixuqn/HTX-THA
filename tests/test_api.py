from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert "message" in r.json()

def test_upload_invalid_file():
    r = client.post(
        "/api/images",
        files={"file": ("test.txt", b"not an image", "text/plain")}
    )
    assert r.status_code == 400

def test_stats():
    r = client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    assert "total" in data
    assert "failed" in data
    assert "success_rate" in data
    assert "average_processing_time_seconds" in data

def test_stats_shape():
    r = client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    assert set(["total", "failed", "success_rate", "average_processing_time_seconds"]).issubset(data.keys())
    assert isinstance(data["success_rate"], str)