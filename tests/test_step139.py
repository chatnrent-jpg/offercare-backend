"""Production launch ceremony (step 139)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.services.production_launch_ceremony import (
    PRODUCTION_LAUNCH_CEREMONY_JSON_FILENAME,
    PRODUCTION_LAUNCH_CEREMONY_MD_FILENAME,
    build_production_launch_ceremony,
    run_production_launch_ceremony,
)


@pytest.fixture
def production_launch_live(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_production_launch_ceremony_endpoint(client: TestClient) -> None:
    response = client.get("/api/deploy/production-launch-ceremony")
    assert response.status_code == 200
    body = response.json()
    assert "launch_ceremony_ready" in body
    assert "production_perfection_ready" in body
    assert "signoff_markdown" in body
    assert "checks" in body
    assert "steps" in body
    assert any(row["id"] == "production_launch_ceremony" for row in body["checks"])
    assert "# VettedCare Maryland Production Launch Ceremony" in body["signoff_markdown"]


def test_production_launch_ceremony_markdown_download(client: TestClient) -> None:
    response = client.get("/api/deploy/production-launch-ceremony.md")
    assert response.status_code == 200
    assert PRODUCTION_LAUNCH_CEREMONY_MD_FILENAME in response.headers.get("content-disposition", "")
    assert "# VettedCare Maryland Production Launch Ceremony" in response.text
    assert "Stakeholder sign-off" in response.text


def test_production_launch_ceremony_json_download(client: TestClient) -> None:
    response = client.get("/api/deploy/production-launch-ceremony.json")
    assert response.status_code == 200
    assert PRODUCTION_LAUNCH_CEREMONY_JSON_FILENAME in response.headers.get("content-disposition", "")
    assert "launch_ceremony_ready" in response.text


def test_production_launch_ceremony_ready_when_fully_configured(
    client: TestClient,
    production_launch_live: None,
) -> None:
    body = client.get("/api/deploy/production-launch-ceremony").json()
    assert body["launch_ceremony_ready"] is True
    assert body["production_perfection_ready"] is True
    assert body["summary"]["deploy_bundle_file_count"] == 15


def test_production_launch_ceremony_run_endpoint(client: TestClient, production_launch_live: None) -> None:
    response = client.post(
        "/api/deploy/production-launch-ceremony/run",
        json={"probe_scrapers": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["perfection_check_ok"] is True
    assert body["deploy_bundle_file_count"] == 15
    assert "# VettedCare Maryland Production Launch Ceremony" in body["signoff_markdown"]


def test_production_launch_ceremony_run_helper(db: Session, production_launch_live: None) -> None:
    result = run_production_launch_ceremony(db, probe_scrapers=False)
    assert result["ok"] is True
    assert result["perfection_check_ok"] is True
    assert result["deploy_bundle_file_count"] == 15


def test_deploy_checklist_includes_production_launch_ceremony_item(client: TestClient) -> None:
    checklist = client.get("/api/deploy/checklist").json()
    item = next(row for row in checklist["items"] if row["id"] == "production_launch_ceremony")
    assert item["status"] in {"ready", "warning", "blocked"}
    assert checklist["production_launch_ceremony_steps"]
    assert checklist["production_launch_ceremony"] is not None


def test_deploy_checklist_summary_includes_launch_ceremony_flags(client: TestClient) -> None:
    summary = client.get("/api/deploy/checklist").json()["summary"]
    assert "production_launch_ceremony_ready" in summary
    assert "production_launch_ceremony_ready_count" in summary


def test_deploy_checklist_csv_includes_production_launch_ceremony_steps(client: TestClient) -> None:
    csv_text = client.get("/api/deploy/checklist.csv").text
    assert "PRODUCTION LAUNCH CEREMONY STEPS" in csv_text
    assert "launch ceremony" in csv_text.lower()


def test_health_includes_production_launch_ceremony_ready(client: TestClient) -> None:
    body = client.get("/health").json()
    assert "production_launch_ceremony_ready" in body


def test_admin_production_launch_ceremony_panel(client: TestClient) -> None:
    html = client.get("/admin").text
    js = client.get("/admin/app.js").text
    assert 'id="production-launch-ceremony-summary"' in html
    assert "run-production-launch-ceremony-btn" in html
    assert "renderProductionLaunchCeremony" in js
    assert "/api/deploy/production-launch-ceremony/run" in js
    assert "/api/deploy/production-launch-ceremony.md" in js
    assert "runProductionLaunchCeremony" in js


def test_production_launch_ceremony_blocked_without_perfection(
    client: TestClient,
    production_launch_live: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SMS_DRY_RUN", True)
    body = client.get("/api/deploy/production-launch-ceremony").json()
    assert body["launch_ceremony_ready"] is False
    perfection_check = next(row for row in body["checks"] if row["id"] == "production_perfection")
    assert perfection_check["status"] == "blocked"


def test_production_launch_ceremony_builder(db: Session, production_launch_live: None) -> None:
    ceremony = build_production_launch_ceremony(db)
    assert ceremony["launch_ceremony_ready"] is True
    assert ceremony["production_perfection_capstone"] is not None
    assert "Stakeholder sign-off" in ceremony["signoff_markdown"]


def test_deploy_bundle_includes_production_launch_ceremony_artifacts(client: TestClient) -> None:
    response = client.get("/api/deploy/deploy-bundle.zip")
    assert response.status_code == 200
    content = response.content
    assert PRODUCTION_LAUNCH_CEREMONY_MD_FILENAME.encode() in content
    assert PRODUCTION_LAUNCH_CEREMONY_JSON_FILENAME.encode() in content
