"""Production launch perfection finale (step 144)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.services.production_go_live_record import reset_sealed_launch_record_for_tests
from app.services.production_launch_attestation import reset_launch_attestation_for_tests
from app.services.production_launch_perfection_seal import reset_production_launch_perfection_seal_for_tests
from app.services.production_launch_archive import (
    PRODUCTION_LAUNCH_ARCHIVE_JSON_FILENAME,
    reset_production_launch_archive_for_tests,
)
from app.services.production_launch_finale import (
    PRODUCTION_LAUNCH_FINALE_JSON_FILENAME,
    build_production_launch_finale,
    reset_production_launch_finale_for_tests,
    run_production_launch_finale,
)
from app.services.production_launch_perfection_manifest import (
    reset_production_launch_bundle_verification_for_tests,
)


@pytest.fixture(autouse=True)
def clear_launch_state() -> None:
    reset_sealed_launch_record_for_tests()
    reset_launch_attestation_for_tests()
    reset_production_launch_perfection_seal_for_tests()
    reset_production_launch_archive_for_tests()
    reset_production_launch_finale_for_tests()
    reset_production_launch_bundle_verification_for_tests()


@pytest.fixture
def production_finale_live(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_production_launch_finale_endpoint(client: TestClient) -> None:
    response = client.get("/api/deploy/production-launch-finale")
    assert response.status_code == 200
    body = response.json()
    assert "production_launch_finale_ready" in body
    assert "production_launch_archive_ready" in body
    assert "production_launch_perfection_ready" in body
    assert "checks" in body
    assert any(row["id"] == "production_launch_finale" for row in body["checks"])


def test_production_launch_finale_json_download(client: TestClient) -> None:
    response = client.get("/api/deploy/production-launch-finale.json")
    assert response.status_code == 200
    assert PRODUCTION_LAUNCH_FINALE_JSON_FILENAME in response.headers.get("content-disposition", "")
    assert "production_launch_finale_ready" in response.text


def test_production_launch_finale_ready_after_run(
    client: TestClient,
    production_finale_live: None,
) -> None:
    result = client.post(
        "/api/deploy/production-launch-finale/run",
        json={"probe_scrapers": False},
    ).json()
    assert result["ok"] is True
    assert result["deploy_bundle_file_count"] == 21

    body = client.get("/api/deploy/production-launch-finale").json()
    assert body["production_launch_finale_ready"] is True
    assert body["production_launch_archive_ready"] is True
    assert body["production_launch_perfection_ready"] is True
    assert body["completed"] is True
    assert body["summary"]["deploy_bundle_file_count"] == 21
    assert len(body["bundle_artifacts"]) == 21

    health = client.get("/health").json()
    assert health["production_launch_finale_ready"] is True
    assert health["production_launch_archive_ready"] is True
    assert health["production_launch_perfection_ready"] is True


def test_production_launch_finale_run_endpoint(
    client: TestClient,
    production_finale_live: None,
) -> None:
    response = client.post(
        "/api/deploy/production-launch-finale/run",
        json={"probe_scrapers": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["already_completed"] is False
    assert body["deploy_bundle_file_count"] == 21
    assert body["finale_id"]
    assert body["manifest_digest"]
    assert len(body["manifest_digest"]) == 64


def test_production_launch_finale_run_is_idempotent(
    client: TestClient,
    production_finale_live: None,
) -> None:
    first = client.post(
        "/api/deploy/production-launch-finale/run",
        json={"probe_scrapers": False},
    ).json()
    second = client.post(
        "/api/deploy/production-launch-finale/run",
        json={"probe_scrapers": False},
    ).json()
    assert first["ok"] is True
    assert second["ok"] is True
    assert second["already_completed"] is True
    assert second["finale_id"] == first["finale_id"]
    assert second["manifest_digest"] == first["manifest_digest"]


def test_production_launch_finale_helper(db: Session, production_finale_live: None) -> None:
    result = run_production_launch_finale(db, probe_scrapers=False)
    assert result["ok"] is True
    assert result["deploy_bundle_file_count"] == 21
    finale = build_production_launch_finale(db)
    assert finale["production_launch_finale_ready"] is True


def test_deploy_checklist_includes_production_launch_finale_item(client: TestClient) -> None:
    checklist = client.get("/api/deploy/checklist").json()
    item = next(row for row in checklist["items"] if row["id"] == "production_launch_finale")
    assert item["status"] in {"ready", "warning", "blocked"}
    assert checklist["production_launch_finale_steps"]
    assert checklist["production_launch_finale"] is not None


def test_deploy_checklist_summary_includes_finale_flags(client: TestClient) -> None:
    summary = client.get("/api/deploy/checklist").json()["summary"]
    assert "production_launch_finale_ready" in summary
    assert "production_launch_finale_ready_count" in summary


def test_deploy_checklist_csv_includes_production_launch_finale_steps(client: TestClient) -> None:
    csv_text = client.get("/api/deploy/checklist.csv").text
    assert "PRODUCTION LAUNCH PERFECTION FINALE STEPS" in csv_text
    assert "run launch finale" in csv_text.lower()


def test_health_includes_production_launch_finale_ready(client: TestClient) -> None:
    body = client.get("/health").json()
    assert "production_launch_finale_ready" in body


def test_admin_production_launch_finale_panel(client: TestClient) -> None:
    html = client.get("/admin").text
    js = client.get("/admin/app.js").text
    assert 'id="production-launch-finale-summary"' in html
    assert "run-production-launch-finale-btn" in html
    assert "renderProductionLaunchFinale" in js
    assert "/api/deploy/production-launch-finale/run" in js
    assert "runProductionLaunchFinale" in js


def test_production_launch_finale_blocked_without_perfection(
    client: TestClient,
    production_finale_live: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SMS_DRY_RUN", True)
    body = client.get("/api/deploy/production-launch-finale").json()
    assert body["production_launch_finale_ready"] is False
    perfection_check = next(row for row in body["checks"] if row["id"] == "production_perfection")
    assert perfection_check["status"] == "blocked"


def test_production_launch_finale_run_fails_without_perfection(client: TestClient) -> None:
    body = client.post(
        "/api/deploy/production-launch-finale/run",
        json={"probe_scrapers": False},
    ).json()
    assert body["ok"] is False
    assert "perfection" in body["message"].lower()


def test_production_launch_finale_builder(db: Session) -> None:
    finale = build_production_launch_finale(db)
    assert finale["production_launch_finale_ready"] is False
    assert finale["production_launch_archive"] is not None
    assert finale["production_perfection_capstone"] is not None
    assert len(finale["bundle_artifacts"]) == 21


def test_deploy_bundle_includes_production_launch_finale_artifact(client: TestClient) -> None:
    response = client.get("/api/deploy/deploy-bundle.zip")
    assert response.status_code == 200
    assert PRODUCTION_LAUNCH_FINALE_JSON_FILENAME.encode() in response.content
    assert PRODUCTION_LAUNCH_ARCHIVE_JSON_FILENAME.encode() in response.content
