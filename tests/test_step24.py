from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.services.deploy_walkthrough import build_deploy_checklist

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_deploy_script_exists() -> None:
    assert (ROOT / "scripts" / "deploy-local.ps1").is_file()


def test_deploy_checklist_endpoint(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    body = response.json()
    assert "summary" in body
    assert "items" in body
    assert "twilio_console_steps" in body
    assert body["summary"]["docker_compose_command"] == "docker compose up -d --build"
    ids = {row["id"] for row in body["items"]}
    assert "database" in ids
    assert "twilio_webhook" in ids


def test_deploy_checklist_database_ready(db) -> None:
    snapshot = build_deploy_checklist(db)
    db_item = next(row for row in snapshot["items"] if row["id"] == "database")
    assert db_item["status"] == "ready"


def test_deploy_checklist_live_sms_flags(monkeypatch: pytest.MonkeyPatch, db) -> None:
    monkeypatch.setattr(settings, "SMS_DRY_RUN", False)
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "secret")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "+15551234567")
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://api.offercare.test")
    monkeypatch.setattr(settings, "TWILIO_VALIDATE_SIGNATURES", True)
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "production-admin-key-xyz")

    snapshot = build_deploy_checklist(db)
    assert snapshot["summary"]["live_sms_ready"] is True
    webhook = next(row for row in snapshot["items"] if row["id"] == "twilio_webhook")
    assert "https://api.offercare.test/shift-sniper/twilio/sms" in webhook["detail"]


def test_env_example_documents_deploy() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "PUBLIC_BASE_URL" in text
    assert "TWILIO_VALIDATE_SIGNATURES" in text
