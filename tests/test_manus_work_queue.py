"""Tests for Manus work queue and integration config."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.care_taxonomy import synthetic_npi_for_caregiver
from app.services.manus_work_queue import build_manus_work_queue

TEST_MANUS_KEY = "offercare-test-manus-key"


@pytest.fixture(autouse=True)
def _configure_manus_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "MANUS_API_KEY", TEST_MANUS_KEY)


@pytest.fixture
def manus_headers() -> dict[str, str]:
    return {"X-Manus-Key": TEST_MANUS_KEY}


def test_manus_config_requires_key(client: TestClient) -> None:
    response = client.get("/api/vettedcare/manus/config")
    assert response.status_code == 401


def test_manus_config_returns_endpoints(client: TestClient, manus_headers: dict[str, str]) -> None:
    response = client.get("/api/vettedcare/manus/config", headers=manus_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["auth_header"] == "X-Manus-Key"
    assert "work_queue" in body["endpoints"]
    assert "MBON" in body["required_checks"]


def test_manus_work_queue_returns_items(client: TestClient, manus_headers: dict[str, str]) -> None:
    response = client.get("/api/vettedcare/manus/work-queue?limit=5", headers=manus_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["queue"] == "due"
    assert body["returned"] <= 5
    assert "items" in body


def test_manus_provider_work_order_not_found(client: TestClient, manus_headers: dict[str, str]) -> None:
    response = client.get(f"/api/vettedcare/manus/providers/{uuid4()}", headers=manus_headers)
    assert response.status_code == 404


def test_work_queue_includes_new_action_needed_provider() -> None:
    db = SessionLocal()
    token = uuid4().hex[:10].upper()
    email = f"manus.queue.{token.lower()}@example.com"
    digits = "".join(ch for ch in token if ch.isdigit())[-10:].rjust(10, "7")
    provider = MarylandProvider(
        full_name="Manus Queue Test RN",
        email=email,
        phone_number=f"+1{digits}",
        npi_number=synthetic_npi_for_caregiver(email),
        md_license_number=f"RN{token}",
        state="MD",
        credential_type="RN",
        service_lines="HOSPITAL",
        license_status="UNVERIFIED",
        min_hourly_rate=40.0,
        response_propensity=0.8,
        fatigue_score=0.0,
    )
    try:
        db.add(provider)
        db.commit()
        payload = build_manus_work_queue(db, limit=200, queue="action_needed")
        ids = {row["provider_id"] for row in payload["items"]}
        assert str(provider.provider_id) in ids
    finally:
        db.query(MarylandProvider).filter(MarylandProvider.email == email).delete()
        db.commit()
        db.close()
