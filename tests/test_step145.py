"""Production launch perfection manifest / bundle verification (step 145)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.services.production_go_live_record import reset_sealed_launch_record_for_tests
from app.services.production_launch_attestation import reset_launch_attestation_for_tests
from app.services.production_launch_perfection_seal import reset_production_launch_perfection_seal_for_tests
from app.services.production_launch_archive import reset_production_launch_archive_for_tests
from app.services.production_launch_finale import reset_production_launch_finale_for_tests
from app.services.production_launch_perfection_manifest import (
    PRODUCTION_LAUNCH_PERFECTION_MANIFEST_JSON_FILENAME,
    build_production_launch_perfection_manifest,
    compare_bundle_against_archive,
    reset_production_launch_bundle_verification_for_tests,
    verify_production_launch_bundle,
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
def production_bundle_verify_live(monkeypatch: pytest.MonkeyPatch) -> None:
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


def _run_finale(client: TestClient) -> dict:
    return client.post(
        "/api/deploy/production-launch-finale/run",
        json={"probe_scrapers": False},
    ).json()


def test_production_launch_perfection_manifest_endpoint(client: TestClient) -> None:
    response = client.get("/api/deploy/production-launch-perfection-manifest")
    assert response.status_code == 200
    body = response.json()
    assert "production_launch_bundle_verified_ready" in body
    assert "verification_entries" in body
    assert "checks" in body
    assert any(row["id"] == "production_launch_bundle_verification" for row in body["checks"])


def test_production_launch_perfection_manifest_json_download(client: TestClient) -> None:
    response = client.get("/api/deploy/production-launch-perfection-manifest.json")
    assert response.status_code == 200
    assert PRODUCTION_LAUNCH_PERFECTION_MANIFEST_JSON_FILENAME in response.headers.get(
        "content-disposition", ""
    )
    assert "production_launch_bundle_verified_ready" in response.text


def test_production_launch_bundle_verified_ready_after_verify(
    client: TestClient,
    production_bundle_verify_live: None,
) -> None:
    _run_finale(client)
    verified = client.post("/api/deploy/production-launch-perfection-manifest/verify").json()
    assert verified["ok"] is True
    assert verified["deploy_bundle_file_count"] == 22
    assert verified["matched_count"] == 19
    assert verified["supplemental_count"] == 2

    body = client.get("/api/deploy/production-launch-perfection-manifest").json()
    assert body["production_launch_bundle_verified_ready"] is True
    assert body["digest_valid"] is True
    assert body["matched_count"] == 19
    assert body["supplemental_count"] == 2
    assert body["bundle_file_count"] == 22
    assert len(body["verification_entries"]) == 21

    health = client.get("/health").json()
    assert health["production_launch_bundle_verified_ready"] is True


def test_production_launch_bundle_verify_endpoint(
    client: TestClient,
    production_bundle_verify_live: None,
) -> None:
    _run_finale(client)
    response = client.post("/api/deploy/production-launch-perfection-manifest/verify")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["already_verified"] is False
    assert body["verification_id"]
    assert body["manifest_digest"]
    assert len(body["manifest_digest"]) == 64


def test_production_launch_bundle_verify_is_idempotent(
    client: TestClient,
    production_bundle_verify_live: None,
) -> None:
    _run_finale(client)
    first = client.post("/api/deploy/production-launch-perfection-manifest/verify").json()
    second = client.post("/api/deploy/production-launch-perfection-manifest/verify").json()
    assert first["ok"] is True
    assert second["ok"] is True
    assert second["already_verified"] is True
    assert second["verification_id"] == first["verification_id"]


def test_production_launch_bundle_verify_helper(db: Session, production_bundle_verify_live: None) -> None:
    from app.services.production_launch_finale import run_production_launch_finale

    run_production_launch_finale(db, probe_scrapers=False)
    result = verify_production_launch_bundle(db)
    assert result["ok"] is True
    assert result["deploy_bundle_file_count"] == 22
    manifest = build_production_launch_perfection_manifest(db)
    assert manifest["production_launch_bundle_verified_ready"] is True


def test_deploy_checklist_includes_production_launch_bundle_verification_item(
    client: TestClient,
) -> None:
    checklist = client.get("/api/deploy/checklist").json()
    item = next(row for row in checklist["items"] if row["id"] == "production_launch_bundle_verification")
    assert item["status"] in {"ready", "warning", "blocked"}
    assert checklist["production_launch_bundle_verification_steps"]
    assert checklist["production_launch_bundle_verification"] is not None


def test_deploy_checklist_summary_includes_bundle_verified_flags(client: TestClient) -> None:
    summary = client.get("/api/deploy/checklist").json()["summary"]
    assert "production_launch_bundle_verified_ready" in summary
    assert "production_launch_bundle_verified_ready_count" in summary


def test_deploy_checklist_csv_includes_bundle_verification_steps(client: TestClient) -> None:
    csv_text = client.get("/api/deploy/checklist.csv").text
    assert "PRODUCTION LAUNCH BUNDLE VERIFICATION STEPS" in csv_text
    assert "verify launch bundle" in csv_text.lower()


def test_health_includes_production_launch_bundle_verified_ready(client: TestClient) -> None:
    body = client.get("/health").json()
    assert "production_launch_bundle_verified_ready" in body


def test_admin_production_launch_bundle_verification_panel(client: TestClient) -> None:
    html = client.get("/admin").text
    js = client.get("/admin/app.js").text
    assert 'id="production-launch-bundle-verification-summary"' in html
    assert "verify-production-launch-bundle-btn" in html
    assert "renderProductionLaunchBundleVerification" in js
    assert "/api/deploy/production-launch-perfection-manifest/verify" in js
    assert "verifyProductionLaunchBundle" in js


def test_production_launch_bundle_verify_blocked_without_finale(
    client: TestClient,
    production_bundle_verify_live: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SMS_DRY_RUN", True)
    body = client.get("/api/deploy/production-launch-perfection-manifest").json()
    assert body["production_launch_bundle_verified_ready"] is False
    finale_check = next(row for row in body["checks"] if row["id"] == "production_launch_finale")
    assert finale_check["status"] == "blocked"


def test_production_launch_bundle_verify_fails_without_finale(client: TestClient) -> None:
    body = client.post("/api/deploy/production-launch-perfection-manifest/verify").json()
    assert body["ok"] is False
    assert "finale" in body["message"].lower()


def test_production_launch_perfection_manifest_builder(db: Session) -> None:
    manifest = build_production_launch_perfection_manifest(db)
    assert manifest["production_launch_bundle_verified_ready"] is False
    assert manifest["production_launch_finale"] is not None
    assert len(manifest["bundle_artifacts"]) == 22


def test_compare_bundle_against_archive_without_archive(db: Session) -> None:
    comparison = compare_bundle_against_archive(db)
    assert comparison["all_archived_matched"] is False
    assert comparison["archived_artifact_count"] == 0


def test_deploy_bundle_includes_production_launch_perfection_manifest_artifact(
    client: TestClient,
) -> None:
    response = client.get("/api/deploy/deploy-bundle.zip")
    assert response.status_code == 200
    assert PRODUCTION_LAUNCH_PERFECTION_MANIFEST_JSON_FILENAME.encode() in response.content
