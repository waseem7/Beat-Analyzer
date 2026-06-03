import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_python_sources_compile():
    for path in (ROOT / "backend").rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_dockerfile_contains_required_runtime_contract():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "ffmpeg libsndfile1" in dockerfile
    assert "EXPOSE 8000" in dockerfile
    assert "/api/health" in dockerfile
    assert '"uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"' in dockerfile


def test_compose_contains_self_hosted_deployment_contract():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    legacy_compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert legacy_compose == compose
    required_snippets = [
        "container_name: ${CONTAINER_NAME:-beat-analyzer}",
        'user: "${PUID:-1027}:${PGID:-100}"',
        "PUID=${PUID:-1027}",
        "PGID=${PGID:-100}",
        "TZ=${TZ:-Asia/Riyadh}",
        "UMASK=${UMASK:-022}",
        "/data/music",
        "/data/analysis",
        "/data/exports",
        "/volume1/data/media/beat-analyzer",
        '"${BEAT_ANALYZER_PORT:-8000}:8000/tcp"',
        "/api/health",
        "network_mode: ${BEAT_ANALYZER_NETWORK_MODE:-synobridge}",
        "no-new-privileges:true",
        "restart: always",
    ]
    for snippet in required_snippets:
        assert snippet in compose
