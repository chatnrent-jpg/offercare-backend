"""Production launch archive (step 143)."""

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
    archive_production_launch,
    build_artifact_manifest,
    build_production_launch_archive,
    compute_manifest_digest,
    reset_production_launch_archive_for_tests,
)
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
def production_archive_live(monkeypatch: pytest.MonkeyPatch) -> None:
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


def _seal_perfection(client: TestClient) -> dict:
    return client.post(
        "/api/deploy/production-launch-perfection-seal/seal",
        json={"probe_scrapers": False},
    ).json()


def test_production_launch_archive_endpoint(client: TestClient) -> None:
    response = client.get("/api/deploy/production-launch-archive")
    assert response.status_code == 200
    body = response.json()
    assert "production_launch_archive_ready" in body
    assert "production_launch_perfection_ready" in body
    assert "manifest" in body
    assert "manifest_digest" in body
    assert "checks" in body
    assert any(row["id"] == "production_launch_archive" for row in body["checks"])


def test_production_launch_archive_json_download(client: TestClient) -> None:
    response = client.get("/api/deploy/production-launch-archive.json")
    assert response.status_code == 200
    assert PRODUCTION_LAUNCH_ARCHIVE_JSON_FILENAME in response.headers.get("content-disposition", "")
    assert "production_launch_archive_ready" in response.text
    assert "manifest" in response.text


def test_production_launch_archive_ready_after_archive(
    client: TestClient,
    production_archive_live: None,
) -> None:
    _seal_perfection(client)
    archived = client.post("/api/deploy/production-launch-archive/archive").json()
    assert archived["ok"] is True
    body = client.get("/api/deploy/production-launch-archive").json()
    assert body["production_launch_archive_ready"] is True
    assert body["archived"] is True
    assert body["digest_valid"] is True
    assert body["artifact_count"] == 19
    assert body["summary"]["deploy_bundle_file_count"] == 20
    assert len(body["manifest"]) == 19


def test_production_launch_archive_archive_endpoint(
    client: TestClient,
    production_archive_live: None,
) -> None:
    _seal_perfection(client)
    response = client.post("/api/deploy/production-launch-archive/archive")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["already_archived"] is False
    assert body["artifact_count"] == 19
    assert body["deploy_bundle_file_count"] == 20
    assert body["manifest_digest"]
    assert len(body["manifest_digest"]) == 64
    assert body["archive_id"]


def test_production_launch_archive_archive_is_idempotent(
    client: TestClient,
    production_archive_live: None,
) -> None:
    _seal_perfection(client)
    first = client.post("/api/deploy/production-launch-archive/archive").json()
    second = client.post("/api/deploy/production-launch-archive/archive").json()
    assert first["ok"] is True
    assert second["ok"] is True
    assert second["already_archived"] is True
    assert second["archive_id"] == first["archive_id"]
    assert second["manifest_digest"] == first["manifest_digest"]


def test_production_launch_archive_helper(db: Session, production_archive_live: None) -> None:
    from app.services.production_launch_perfection_seal import seal_production_launch_perfection

    seal_production_launch_perfection(db, probe_scrapers=False)
    result = archive_production_launch(db)
    assert result["ok"] is True
    assert result["deploy_bundle_file_count"] == 20
    archive = build_production_launch_archive(db)
    assert archive["production_launch_archive_ready"] is True


def test_build_artifact_manifest_has_checksums(db: Session) -> None:
    manifest = build_artifact_manifest(db)
    assert len(manifest) == 19
    for row in manifest:
        assert row["filename"]
        assert len(row["sha256"]) == 64
        assert row["byte_count"] > 0


def test_compute_manifest_digest_stable(db: Session) -> None:
    manifest = build_artifact_manifest(db)
    first = compute_manifest_digest(manifest)
    second = compute_manifest_digest(manifest)
    assert first == second


def test_deploy_checklist_includes_production_launch_archive_item(client: TestClient) -> None:
    checklist = client.get("/api/deploy/checklist").json()
    item = next(row for row in checklist["items"] if row["id"] == "production_launch_archive")
    assert item["status"] in {"ready", "warning", "blocked"}
    assert checklist["production_launch_archive_steps"]
    assert checklist["production_launch_archive"] is not None


def test_deploy_checklist_summary_includes_archive_flags(client: TestClient) -> None:
    summary = client.get("/api/deploy/checklist").json()["summary"]
    assert "production_launch_archive_ready" in summary
    assert "production_launch_archive_ready_count" in summary


def test_deploy_checklist_csv_includes_production_launch_archive_steps(client: TestClient) -> None:
    csv_text = client.get("/api/deploy/checklist.csv").text
    assert "PRODUCTION LAUNCH ARCHIVE STEPS" in csv_text
    assert "archive launch" in csv_text.lower()


def test_health_includes_production_launch_archive_ready(client: TestClient) -> None:
    body = client.get("/health").json()
    assert "production_launch_archive_ready" in body


def test_admin_production_launch_archive_panel(client: TestClient) -> None:
    html = client.get("/admin").text
    js = client.get("/admin/app.js").text
    assert 'id="production-launch-archive-summary"' in html
    assert "archive-production-launch-btn" in html
    assert "renderProductionLaunchArchive" in js
    assert "/api/deploy/production-launch-archive/archive" in js
    assert "archiveProductionLaunch" in js


def test_production_launch_archive_blocked_without_perfection_seal(
    client: TestClient,
    production_archive_live: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SMS_DRY_RUN", True)
    body = client.get("/api/deploy/production-launch-archive").json()
    assert body["production_launch_archive_ready"] is False
    seal_check = next(row for row in body["checks"] if row["id"] == "production_launch_perfection_seal")
    assert seal_check["status"] == "blocked"


def test_production_launch_archive_archive_fails_without_perfection_seal(client: TestClient) -> None:
    body = client.post("/api/deploy/production-launch-archive/archive").json()
    assert body["ok"] is False
    assert "perfection seal" in body["message"].lower()


def test_production_launch_archive_builder(db: Session, production_archive_live: None) -> None:
    archive = build_production_launch_archive(db)
    assert archive["production_launch_archive_ready"] is False
    assert archive["production_launch_perfection_seal"] is not None
    assert len(archive["manifest"]) == 19


def test_deploy_bundle_includes_production_launch_archive_artifact(client: TestClient) -> None:
    response = client.get("/api/deploy/deploy-bundle.zip")
    assert response.status_code == 200
    assert PRODUCTION_LAUNCH_ARCHIVE_JSON_FILENAME.encode() in response.content
