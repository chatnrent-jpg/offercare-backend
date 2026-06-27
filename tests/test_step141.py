"""Production launch attestation (step 141)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.services.production_go_live_record import reset_sealed_launch_record_for_tests, seal_production_go_live_record
from app.services.production_launch_attestation import (
    PRODUCTION_LAUNCH_ATTESTATION_JSON_FILENAME,
    PRODUCTION_LAUNCH_ATTESTATION_MD_FILENAME,
    attest_production_launch,
    build_production_launch_attestation,
    compute_go_live_record_digest,
    reset_launch_attestation_for_tests,
)
from app.services.production_launch_perfection_seal import reset_production_launch_perfection_seal_for_tests
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
def production_attestation_live(monkeypatch: pytest.MonkeyPatch) -> None:
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


def _seal_go_live(client: TestClient) -> dict:
    return client.post(
        "/api/deploy/production-go-live-record/seal",
        json={"probe_scrapers": False},
    ).json()


def test_production_launch_attestation_endpoint(client: TestClient) -> None:
    response = client.get("/api/deploy/production-launch-attestation")
    assert response.status_code == 200
    body = response.json()
    assert "production_launch_attestation_ready" in body
    assert "production_go_live_record_ready" in body
    assert "digest_sha256" in body
    assert "attestation_markdown" in body
    assert "checks" in body
    assert any(row["id"] == "production_launch_attestation" for row in body["checks"])
    assert "# VettedCare Maryland Production Launch Attestation" in body["attestation_markdown"]


def test_production_launch_attestation_markdown_download(client: TestClient) -> None:
    response = client.get("/api/deploy/production-launch-attestation.md")
    assert response.status_code == 200
    assert PRODUCTION_LAUNCH_ATTESTATION_MD_FILENAME in response.headers.get("content-disposition", "")
    assert "SHA-256 digest" in response.text
    assert "Compliance sign-off" in response.text


def test_production_launch_attestation_json_download(client: TestClient) -> None:
    response = client.get("/api/deploy/production-launch-attestation.json")
    assert response.status_code == 200
    assert PRODUCTION_LAUNCH_ATTESTATION_JSON_FILENAME in response.headers.get("content-disposition", "")
    assert "production_launch_attestation_ready" in response.text


def test_production_launch_attestation_ready_after_attest(
    client: TestClient,
    production_attestation_live: None,
) -> None:
    _seal_go_live(client)
    attest = client.post("/api/deploy/production-launch-attestation/attest").json()
    assert attest["ok"] is True
    body = client.get("/api/deploy/production-launch-attestation").json()
    assert body["production_launch_attestation_ready"] is True
    assert body["attested"] is True
    assert body["digest_valid"] is True
    assert body["digest_sha256"] == attest["digest_sha256"]
    assert body["summary"]["deploy_bundle_file_count"] == 18


def test_production_launch_attestation_attest_endpoint(
    client: TestClient,
    production_attestation_live: None,
) -> None:
    _seal_go_live(client)
    response = client.post("/api/deploy/production-launch-attestation/attest")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["already_attested"] is False
    assert body["digest_sha256"]
    assert len(body["digest_sha256"]) == 64
    assert body["deploy_bundle_file_count"] == 18
    assert body["attestation_id"]


def test_production_launch_attestation_attest_is_idempotent(
    client: TestClient,
    production_attestation_live: None,
) -> None:
    _seal_go_live(client)
    first = client.post("/api/deploy/production-launch-attestation/attest").json()
    second = client.post("/api/deploy/production-launch-attestation/attest").json()
    assert first["ok"] is True
    assert second["ok"] is True
    assert second["already_attested"] is True
    assert second["attestation_id"] == first["attestation_id"]
    assert second["digest_sha256"] == first["digest_sha256"]


def test_production_launch_attestation_attest_helper(db: Session, production_attestation_live: None) -> None:
    seal_production_go_live_record(db, probe_scrapers=False)
    result = attest_production_launch(db)
    assert result["ok"] is True
    assert result["deploy_bundle_file_count"] == 18
    attestation = build_production_launch_attestation(db)
    assert attestation["production_launch_attestation_ready"] is True


def test_compute_go_live_record_digest_stable(db: Session, production_attestation_live: None) -> None:
    seal_production_go_live_record(db, probe_scrapers=False)
    attestation = build_production_launch_attestation(db)
    subject = attestation["attestation_subject"]
    assert subject is not None
    first = compute_go_live_record_digest(subject)
    second = compute_go_live_record_digest(subject)
    assert first == second
    assert len(first) == 64


def test_deploy_checklist_includes_production_launch_attestation_item(client: TestClient) -> None:
    checklist = client.get("/api/deploy/checklist").json()
    item = next(row for row in checklist["items"] if row["id"] == "production_launch_attestation")
    assert item["status"] in {"ready", "warning", "blocked"}
    assert checklist["production_launch_attestation_steps"]
    assert checklist["production_launch_attestation"] is not None


def test_deploy_checklist_summary_includes_attestation_flags(client: TestClient) -> None:
    summary = client.get("/api/deploy/checklist").json()["summary"]
    assert "production_launch_attestation_ready" in summary
    assert "production_launch_attestation_ready_count" in summary


def test_deploy_checklist_csv_includes_production_launch_attestation_steps(client: TestClient) -> None:
    csv_text = client.get("/api/deploy/checklist.csv").text
    assert "PRODUCTION LAUNCH ATTESTATION STEPS" in csv_text
    assert "attest launch" in csv_text.lower()


def test_health_includes_production_launch_attestation_ready(client: TestClient) -> None:
    body = client.get("/health").json()
    assert "production_launch_attestation_ready" in body


def test_admin_production_launch_attestation_panel(client: TestClient) -> None:
    html = client.get("/admin").text
    js = client.get("/admin/app.js").text
    assert 'id="production-launch-attestation-summary"' in html
    assert "attest-production-launch-btn" in html
    assert "renderProductionLaunchAttestation" in js
    assert "/api/deploy/production-launch-attestation/attest" in js
    assert "attestProductionLaunch" in js


def test_production_launch_attestation_blocked_without_go_live(
    client: TestClient,
    production_attestation_live: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SMS_DRY_RUN", True)
    body = client.get("/api/deploy/production-launch-attestation").json()
    assert body["production_launch_attestation_ready"] is False
    go_live_check = next(row for row in body["checks"] if row["id"] == "production_go_live_record")
    assert go_live_check["status"] == "blocked"


def test_production_launch_attestation_attest_fails_without_seal(client: TestClient) -> None:
    body = client.post("/api/deploy/production-launch-attestation/attest").json()
    assert body["ok"] is False
    assert "sealed go-live record" in body["message"].lower()


def test_production_launch_attestation_builder(db: Session, production_attestation_live: None) -> None:
    attestation = build_production_launch_attestation(db)
    assert attestation["production_launch_attestation_ready"] is False
    assert attestation["production_go_live_record"] is not None
    assert "Cryptographic attestation" in attestation["attestation_markdown"]


def test_deploy_bundle_includes_production_launch_attestation_artifacts(client: TestClient) -> None:
    response = client.get("/api/deploy/deploy-bundle.zip")
    assert response.status_code == 200
    content = response.content
    assert PRODUCTION_LAUNCH_ATTESTATION_MD_FILENAME.encode() in content
    assert PRODUCTION_LAUNCH_ATTESTATION_JSON_FILENAME.encode() in content
