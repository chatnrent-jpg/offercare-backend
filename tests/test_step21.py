from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.middleware.rate_limit import reset_rate_limiter


def test_health_includes_production_flags(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert "rate_limit_enabled" in body
    assert "security_headers_enabled" in body


def test_security_headers_on_api_response(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SECURITY_HEADERS_ENABLED", True)
    response = client.get("/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"


def test_login_rate_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN_PER_MINUTE", 2)
    reset_rate_limiter()

    payload = {"email": "missing@offercare.demo", "password": "WrongPass1"}
    for _ in range(2):
        assert client.post("/api/clinicians/login", json=payload).status_code == 401

    blocked = client.post("/api/clinicians/login", json=payload)
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "rate_limit_exceeded"


def test_rate_limit_disabled_allows_burst(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    reset_rate_limiter()
    payload = {"email": "missing@offercare.demo", "password": "WrongPass1"}
    for _ in range(5):
        assert client.post("/api/clinicians/login", json=payload).status_code == 401
