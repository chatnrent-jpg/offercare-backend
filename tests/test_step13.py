from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]


def test_deploy_artifacts_exist() -> None:
    assert (ROOT / "Dockerfile").is_file()
    assert (ROOT / "docker-compose.yml").is_file()
    assert (ROOT / ".env.example").is_file()
    assert (ROOT / "scripts" / "docker-entrypoint.sh").is_file()


def test_docker_compose_parses() -> None:
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "services:" in text
    assert "  db:" in text
    assert "  api:" in text
    assert "build: ." in text


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_env_example_documents_admin_key() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "ADMIN_API_KEY" in text
    assert "DATABASE_URL" in text
    assert "JWT_SECRET_KEY" in text
