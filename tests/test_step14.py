from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.services.integrations import integration_snapshot
from app.services.sms import send_shift_sms
from app.services.vms_submission import run_vms_connectivity_test


def test_integrations_status_dry_run_defaults() -> None:
    snapshot = integration_snapshot()
    assert snapshot["twilio"]["dry_run"] is True
    assert snapshot["twilio"]["live_ready"] is False
    assert snapshot["email"]["dry_run"] is True
    assert snapshot["email"]["live_ready"] is False
    assert snapshot["vms"]["dry_run"] is True
    assert snapshot["vms"]["live_ready"] is False


def test_integrations_status_live_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SMS_DRY_RUN", False)
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "secret")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "+15551234567")
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://api.offercare.test")
    monkeypatch.setattr(settings, "VMS_DRY_RUN", False)
    monkeypatch.setattr(settings, "VMS_SUBMISSION_URL", "https://vms.example.com/placements")

    snapshot = integration_snapshot()
    assert snapshot["twilio"]["live_ready"] is True
    assert snapshot["twilio"]["inbound_webhook_url"] == "https://api.offercare.test/shift-sniper/twilio/sms"
    assert snapshot["vms"]["live_ready"] is True


def test_sms_misconfigured_when_live_without_twilio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SMS_DRY_RUN", False)
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "")
    result = send_shift_sms(to_number="+14105550001", message_body="test")
    assert result.status == "FAILED"
    assert result.mode == "misconfigured"


@patch("twilio.rest.Client")
def test_sms_live_twilio_send(mock_client_cls, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SMS_DRY_RUN", False)
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "secret")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "+15551234567")

    message = MagicMock()
    message.sid = "SM123"
    mock_client_cls.return_value.messages.create.return_value = message

    result = send_shift_sms(to_number="+14105550001", message_body="live test")
    assert result.status == "SENT"
    assert result.mode == "twilio"
    assert result.twilio_sid == "SM123"


@patch("app.services.vms_submission.httpx.Client")
def test_vms_live_submission(mock_client_cls, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "VMS_DRY_RUN", False)
    monkeypatch.setattr(settings, "VMS_SUBMISSION_URL", "https://vms.example.com/placements")
    monkeypatch.setattr(settings, "VMS_AUTH_TOKEN", "vms-token")

    response = MagicMock()
    response.headers = {"content-type": "application/json"}
    response.json.return_value = {"reference_id": "VMS-999", "message": "accepted"}
    response.raise_for_status.return_value = None
    mock_client_cls.return_value.__enter__.return_value.post.return_value = response

    result = run_vms_connectivity_test()
    assert result["status"] == "SUBMITTED"
    assert result["mode"] == "live"
    assert result["external_ref"] == "VMS-999"


def test_integrations_status_endpoint(client: TestClient) -> None:
    response = client.get("/api/integrations/status")
    assert response.status_code == 200
    body = response.json()
    assert "twilio" in body
    assert "email" in body
    assert "vms" in body
    assert "push" in body


def test_integrations_test_sms_endpoint(client: TestClient) -> None:
    response = client.post(
        "/api/integrations/test/sms",
        json={"phone_number": "+14105550001", "message": "OfferCare test"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "DRY_RUN"


def test_integrations_test_vms_endpoint(client: TestClient) -> None:
    response = client.post("/api/integrations/test/vms")
    assert response.status_code == 200
    assert response.json()["mode"] == "dry_run"
