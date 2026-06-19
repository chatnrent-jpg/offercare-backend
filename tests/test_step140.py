"""Production go-live record (step 140)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.services.production_go_live_record import (
    PRODUCTION_GO_LIVE_RECORD_JSON_FILENAME,
    build_production_go_live_record,
    reset_sealed_launch_record_for_tests,
    seal_production_go_live_record,
)
from app.services.production_launch_attestation import reset_launch_attestation_for_tests
from app.services.production_launch_perfection_seal import reset_production_launch_perfection_seal_for_tests
from app.services.production_launch_archive import reset_production_launch_archive_for_tests
from app.services.production_launch_finale import reset_production_launch_finale_for_tests
from app.services.production_launch_perfection_manifest import (
    reset_production_launch_bundle_verification_for_tests,
)


@pytest.fixture(autouse=True)
def clear_sealed_record() -> None:
    reset_sealed_launch_record_for_tests()
    reset_launch_attestation_for_tests()
    reset_production_launch_perfection_seal_for_tests()
    reset_production_launch_archive_for_tests()
    reset_production_launch_finale_for_tests()
    reset_production_launch_bundle_verification_for_tests()


@pytest.fixture
def production_go_live_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LIVE_SCRAPER_GATEWAY_BASE_URL", "https://adapters.example.com")
    monkeypatch.setattr(settings, "LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED", False)
    monkeypatch.setattr(settings, "MBON_VERIFY_DRY_RUN", False)
    monkeypatch.setattr(settings, "OIG_SCREEN_DRY_RUN", False)
    monkeypatch.setattr(settings, "MD_JUDICIARY_DRY_RUN", False)
    monkeypatch.setattr(settings, "JOB_BOARD_SCRAPE_DRY_RUN", False)
    monkeypatch.setattr(settings, "VMS_INGEST_DRY_RUN", False)
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://api.offercare.example.com")
    monkeypatch.setattr(settings, "STAFFING_VMS_WORKER_ENABLED", True)
    monkeypatch.setattr(settings, "STAFFING_JOB_BOARD_WORKER_ENABLED", True)
    monkeypatch.setattr(settings, "COMPLIANCE_MONITOR_WORKER_ENABLED", True)
    monkeypatch.setattr(settings, "SNIPER_CASCADE_WORKER_ENABLED", True)
    monkeypatch.setattr(settings, "SNIPER_CASCADE_ENABLED", True)
    monkeypatch.setattr(settings, "SMS_DRY_RUN", False)
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "secret")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "+15551234567")
    monkeypatch.setattr(settings, "TWILIO_VALIDATE_SIGNATURES", True)


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_production_go_live_record_endpoint(client: TestClient) -> None:
    response = client.get("/api/deploy/production-go-live-record")
    assert response.status_code == 200
    body = response.json()
    assert "production_go_live_record_ready" in body
    assert "launch_ceremony_ready" in body
    assert "health_snapshot" in body
    assert "checks" in body
    assert "steps" in body
    assert body["sealed"] is False
    assert any(row["id"] == "production_go_live_record" for row in body["checks"])


def test_production_go_live_record_json_download(client: TestClient) -> None:
    response = client.get("/api/deploy/production-go-live-record.json")
    assert response.status_code == 200
    assert PRODUCTION_GO_LIVE_RECORD_JSON_FILENAME in response.headers.get("content-disposition", "")
    assert "production_go_live_record_ready" in response.text
    assert "health_snapshot" in response.text


def test_production_go_live_record_ready_after_seal(
    client: TestClient,
    production_go_live_live: None,
) -> None:
    seal = client.post(
        "/api/deploy/production-go-live-record/seal",
        json={"probe_scrapers": False},
    ).json()
    assert seal["ok"] is True
    body = client.get("/api/deploy/production-go-live-record").json()
    assert body["production_go_live_record_ready"] is True
    assert body["sealed"] is True
    assert body["immutable"] is True
    assert body["record_id"] == seal["record_id"]
    assert body["summary"]["deploy_bundle_file_count"] == 16


def test_production_go_live_record_seal_endpoint(client: TestClient, production_go_live_live: None) -> None:
    response = client.post(
        "/api/deploy/production-go-live-record/seal",
        json={"probe_scrapers": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["already_sealed"] is False
    assert body["perfection_check_ok"] is True
    assert body["deploy_bundle_file_count"] == 16
    assert body["record_id"]
    assert body["sealed_at"]
    assert body["health_snapshot"]["production_perfection_ready"] is True


def test_production_go_live_record_seal_is_idempotent(client: TestClient, production_go_live_live: None) -> None:
    first = client.post(
        "/api/deploy/production-go-live-record/seal",
        json={"probe_scrapers": False},
    ).json()
    second = client.post(
        "/api/deploy/production-go-live-record/seal",
        json={"probe_scrapers": False},
    ).json()
    assert first["ok"] is True
    assert second["ok"] is True
    assert second["already_sealed"] is True
    assert second["record_id"] == first["record_id"]


def test_production_go_live_record_seal_helper(db: Session, production_go_live_live: None) -> None:
    result = seal_production_go_live_record(db, probe_scrapers=False)
    assert result["ok"] is True
    assert result["deploy_bundle_file_count"] == 16
    assert result["health_snapshot"]["production_launch_ceremony_ready"] is True


def test_deploy_checklist_includes_production_go_live_record_item(client: TestClient) -> None:
    checklist = client.get("/api/deploy/checklist").json()
    item = next(row for row in checklist["items"] if row["id"] == "production_go_live_record")
    assert item["status"] in {"ready", "warning", "blocked"}
    assert checklist["production_go_live_record_steps"]
    assert checklist["production_go_live_record"] is not None


def test_deploy_checklist_summary_includes_go_live_record_flags(client: TestClient) -> None:
    summary = client.get("/api/deploy/checklist").json()["summary"]
    assert "production_go_live_record_ready" in summary
    assert "production_go_live_record_ready_count" in summary


def test_deploy_checklist_csv_includes_production_go_live_record_steps(client: TestClient) -> None:
    csv_text = client.get("/api/deploy/checklist.csv").text
    assert "PRODUCTION GO-LIVE RECORD STEPS" in csv_text
    assert "seal launch record" in csv_text.lower()


def test_health_includes_production_go_live_record_ready(client: TestClient) -> None:
    body = client.get("/health").json()
    assert "production_go_live_record_ready" in body


def test_admin_production_go_live_record_panel(client: TestClient) -> None:
    html = client.get("/admin").text
    js = client.get("/admin/app.js").text
    assert 'id="production-go-live-record-summary"' in html
    assert "seal-production-go-live-record-btn" in html
    assert "renderProductionGoLiveRecord" in js
    assert "/api/deploy/production-go-live-record/seal" in js
    assert "sealProductionGoLiveRecord" in js


def test_production_go_live_record_blocked_without_ceremony(
    client: TestClient,
    production_go_live_live: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SMS_DRY_RUN", True)
    body = client.get("/api/deploy/production-go-live-record").json()
    assert body["production_go_live_record_ready"] is False
    ceremony_check = next(row for row in body["checks"] if row["id"] == "production_launch_ceremony")
    assert ceremony_check["status"] == "blocked"


def test_production_go_live_record_builder(db: Session, production_go_live_live: None) -> None:
    record = build_production_go_live_record(db)
    assert record["production_go_live_record_ready"] is False
    assert record["production_launch_ceremony"] is not None
    assert record["health_snapshot"]["database"] == "ok"


def test_deploy_bundle_includes_production_go_live_record_artifact(client: TestClient) -> None:
    response = client.get("/api/deploy/deploy-bundle.zip")
    assert response.status_code == 200
    assert PRODUCTION_GO_LIVE_RECORD_JSON_FILENAME.encode() in response.content
