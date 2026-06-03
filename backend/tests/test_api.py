import os
import tempfile

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="beat-analyzer-test-data-"))
os.environ.setdefault("IMPORT_DIR", tempfile.mkdtemp(prefix="beat-analyzer-test-import-"))

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_export_tracks_csv_has_expected_header():
    response = client.get("/api/exports/tracks.csv")
    assert response.status_code == 200
    assert response.text.startswith("file,bpm,bpm_half,first_salsa_1,first_salsa_5")


def test_static_app_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "Latin Beat Analyzer" in response.text
