"""Twilio live SMS production runbook and lock reply smoke (step 135)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.services.twilio_lock_reply_smoke import run_twilio_lock_reply_smoke
from app.services.twilio_sms_production_runbook import (
    TWILIO_SMS_PRODUCTION_RUNBOOK_JSON_FILENAME,
    build_twilio_sms_production_runbook,
)


@pytest.fixture
def twilio_production_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SMS_DRY_RUN", False)
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "secret")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "+15551234567")
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://api.offercare.example.com")
    monkeypatch.setattr(settings, "TWILIO_VALIDATE_SIGNATURES", True)


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_twilio_go_live_profile_endpoint(client: TestClient) -> None:
    response = client.get("/api/integrations/twilio/go-live-profile")
    assert response.status_code == 200
    body = response.json()
    assert "production_ready" in body
    assert "live_sms_ready" in body
    assert "checks" in body
    assert "env_snippet" in body
    assert any(row["id"] == "twilio_inbound_webhook" for row in body["checks"])


def test_twilio_production_ready_when_fully_configured(
    client: TestClient,
    twilio_production_live: None,
) -> None:
    body = client.get("/api/integrations/twilio/go-live-profile").json()
    assert body["production_ready"] is True
    assert body["live_sms_ready"] is True
    assert body["summary"]["inbound_webhook_url"] == "https://api.offercare.example.com/shift-sniper/twilio/sms"
    assert "SMS_DRY_RUN=false" in body["env_snippet"]


def test_twilio_lock_reply_smoke_endpoint(client: TestClient) -> None:
    response = client.post("/api/integrations/twilio/lock-reply-smoke", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "locked"
    assert body["placement_id"]
    assert body["reply_keyword"] == "YES"


def test_twilio_lock_reply_smoke_helper(db: Session) -> None:
    result = run_twilio_lock_reply_smoke(db)
    assert result["ok"] is True
    assert result["status"] == "locked"
    assert result["facility_name"]


def test_deploy_checklist_includes_live_sms_production_item(client: TestClient) -> None:
    checklist = client.get("/api/deploy/checklist").json()
    item = next(row for row in checklist["items"] if row["id"] == "live_sms_production")
    assert item["status"] in {"ready", "warning", "blocked"}
    assert checklist["live_sms_production_steps"]
    assert checklist["twilio_sms_production_runbook"] is not None


def test_deploy_checklist_summary_includes_twilio_flags(client: TestClient) -> None:
    summary = client.get("/api/deploy/checklist").json()["summary"]
    assert "live_sms_ready" in summary
    assert "twilio_sms_production_ready" in summary


def test_deploy_checklist_csv_includes_live_sms_production_steps(client: TestClient) -> None:
    csv_text = client.get("/api/deploy/checklist.csv").text
    assert "LIVE SMS PRODUCTION STEPS" in csv_text
    assert "lock reply smoke" in csv_text.lower()


def test_health_includes_twilio_production_flags(client: TestClient) -> None:
    body = client.get("/health").json()
    assert "live_sms_ready" in body
    assert "twilio_sms_production_ready" in body


def test_admin_integrations_twilio_controls(client: TestClient) -> None:
    html = client.get("/admin").text
    js = client.get("/admin/app.js").text
    assert "twilio-lock-reply-smoke-btn" in html
    assert "copy-twilio-go-live-env-btn" in html
    assert "/api/integrations/twilio/lock-reply-smoke" in js
    assert "/api/integrations/twilio/go-live-profile" in js
    assert "runTwilioLockReplySmoke" in js


def test_twilio_production_blocked_without_https(
    client: TestClient,
    twilio_production_live: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "")
    body = client.get("/api/integrations/twilio/go-live-profile").json()
    assert body["production_ready"] is False
    public_check = next(row for row in body["checks"] if row["id"] == "public_https")
    assert public_check["status"] == "blocked"


def test_twilio_production_runbook_builder(db: Session, twilio_production_live: None) -> None:
    runbook = build_twilio_sms_production_runbook(db)
    assert runbook["production_ready"] is True
    assert len(runbook["twilio_console_steps"]) >= 4


def test_deploy_bundle_includes_twilio_runbook(client: TestClient) -> None:
    response = client.get("/api/deploy/deploy-bundle.zip")
    assert response.status_code == 200
    assert TWILIO_SMS_PRODUCTION_RUNBOOK_JSON_FILENAME.encode() in response.content
