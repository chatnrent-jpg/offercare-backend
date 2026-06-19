"""Production launch perfection seal (step 142)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.services.production_go_live_record import reset_sealed_launch_record_for_tests
from app.services.production_launch_attestation import reset_launch_attestation_for_tests
from app.services.production_launch_perfection_seal import (
    PRODUCTION_LAUNCH_PERFECTION_SEAL_JSON_FILENAME,
    build_production_launch_perfection_seal,
    reset_production_launch_perfection_seal_for_tests,
    seal_production_launch_perfection,
)
from app.services.production_launch_archive import reset_production_launch_archive_for_tests
from app.services.production_launch_finale import reset_production_launch_finale_for_tests
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
def production_perfection_seal_live(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_production_launch_perfection_seal_endpoint(client: TestClient) -> None:
    response = client.get("/api/deploy/production-launch-perfection-seal")
    assert response.status_code == 200
    body = response.json()
    assert "production_launch_perfection_ready" in body
    assert "production_perfection_ready" in body
    assert "production_launch_attestation_ready" in body
    assert "checks" in body
    assert "steps" in body
    assert any(row["id"] == "production_launch_perfection_seal" for row in body["checks"])


def test_production_launch_perfection_seal_json_download(client: TestClient) -> None:
    response = client.get("/api/deploy/production-launch-perfection-seal.json")
    assert response.status_code == 200
    assert PRODUCTION_LAUNCH_PERFECTION_SEAL_JSON_FILENAME in response.headers.get("content-disposition", "")
    assert "production_launch_perfection_ready" in response.text


def test_production_launch_perfection_ready_after_seal(
    client: TestClient,
    production_perfection_seal_live: None,
) -> None:
    seal = client.post(
        "/api/deploy/production-launch-perfection-seal/seal",
        json={"probe_scrapers": False},
    ).json()
    assert seal["ok"] is True
    body = client.get("/api/deploy/production-launch-perfection-seal").json()
    assert body["production_launch_perfection_ready"] is True
    assert body["production_launch_attestation_ready"] is True
    assert body["production_go_live_record_ready"] is True
    assert body["sealed"] is True
    assert body["summary"]["deploy_bundle_file_count"] == 19


def test_production_launch_perfection_seal_run_endpoint(
    client: TestClient,
    production_perfection_seal_live: None,
) -> None:
    response = client.post(
        "/api/deploy/production-launch-perfection-seal/seal",
        json={"probe_scrapers": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["already_sealed"] is False
    assert body["production_launch_perfection_ready"] is True
    assert body["production_launch_attestation_ready"] is True
    assert body["production_go_live_record_ready"] is True
    assert body["deploy_bundle_file_count"] == 19
    assert body["seal_id"]
    assert body["digest_sha256"]
    assert len(body["digest_sha256"]) == 64


def test_production_launch_perfection_seal_is_idempotent(
    client: TestClient,
    production_perfection_seal_live: None,
) -> None:
    first = client.post(
        "/api/deploy/production-launch-perfection-seal/seal",
        json={"probe_scrapers": False},
    ).json()
    second = client.post(
        "/api/deploy/production-launch-perfection-seal/seal",
        json={"probe_scrapers": False},
    ).json()
    assert first["ok"] is True
    assert second["ok"] is True
    assert second["already_sealed"] is True
    assert second["seal_id"] == first["seal_id"]
    assert second["digest_sha256"] == first["digest_sha256"]


def test_production_launch_perfection_seal_helper(db: Session, production_perfection_seal_live: None) -> None:
    result = seal_production_launch_perfection(db, probe_scrapers=False)
    assert result["ok"] is True
    assert result["deploy_bundle_file_count"] == 19
    capstone = build_production_launch_perfection_seal(db)
    assert capstone["production_launch_perfection_ready"] is True


def test_deploy_checklist_includes_production_launch_perfection_seal_item(client: TestClient) -> None:
    checklist = client.get("/api/deploy/checklist").json()
    item = next(row for row in checklist["items"] if row["id"] == "production_launch_perfection_seal")
    assert item["status"] in {"ready", "warning", "blocked"}
    assert checklist["production_launch_perfection_seal_steps"]
    assert checklist["production_launch_perfection_seal"] is not None


def test_deploy_checklist_summary_includes_perfection_seal_flags(client: TestClient) -> None:
    summary = client.get("/api/deploy/checklist").json()["summary"]
    assert "production_launch_perfection_ready" in summary
    assert "production_launch_perfection_ready_count" in summary


def test_deploy_checklist_csv_includes_production_launch_perfection_seal_steps(client: TestClient) -> None:
    csv_text = client.get("/api/deploy/checklist.csv").text
    assert "PRODUCTION LAUNCH PERFECTION SEAL STEPS" in csv_text
    assert "seal launch perfection" in csv_text.lower()


def test_health_includes_production_launch_perfection_ready(client: TestClient) -> None:
    body = client.get("/health").json()
    assert "production_launch_perfection_ready" in body


def test_admin_production_launch_perfection_seal_panel(client: TestClient) -> None:
    html = client.get("/admin").text
    js = client.get("/admin/app.js").text
    assert 'id="production-launch-perfection-seal-summary"' in html
    assert "seal-production-launch-perfection-btn" in html
    assert "renderProductionLaunchPerfectionSeal" in js
    assert "/api/deploy/production-launch-perfection-seal/seal" in js
    assert "sealProductionLaunchPerfection" in js


def test_production_launch_perfection_seal_blocked_without_perfection(
    client: TestClient,
    production_perfection_seal_live: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SMS_DRY_RUN", True)
    body = client.get("/api/deploy/production-launch-perfection-seal").json()
    assert body["production_launch_perfection_ready"] is False
    perfection_check = next(row for row in body["checks"] if row["id"] == "production_perfection")
    assert perfection_check["status"] == "blocked"


def test_production_launch_perfection_seal_run_fails_without_perfection(client: TestClient) -> None:
    body = client.post(
        "/api/deploy/production-launch-perfection-seal/seal",
        json={"probe_scrapers": False},
    ).json()
    assert body["ok"] is False
    assert "perfection" in body["message"].lower()


def test_production_launch_perfection_seal_builder(db: Session, production_perfection_seal_live: None) -> None:
    capstone = build_production_launch_perfection_seal(db)
    assert capstone["production_launch_perfection_ready"] is False
    assert capstone["production_launch_attestation"] is not None
    assert capstone["production_perfection_capstone"] is not None


def test_deploy_bundle_includes_production_launch_perfection_seal_artifact(client: TestClient) -> None:
    response = client.get("/api/deploy/deploy-bundle.zip")
    assert response.status_code == 200
    assert PRODUCTION_LAUNCH_PERFECTION_SEAL_JSON_FILENAME.encode() in response.content
