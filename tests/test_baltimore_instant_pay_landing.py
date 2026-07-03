from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.services.worker_consent import WORKER_CONSENT_VERSION


def _text_apply_payload(**overrides):
    suffix = str(uuid4().int % 10000).zfill(4)
    base = {
        "phone_number": f"410555{suffix}",
        "full_name": "Baltimore Test CNA",
        "credential_type": "CNA",
        "consent_version": WORKER_CONSENT_VERSION,
        "consent_sms_dispatch": True,
    }
    base.update(overrides)
    return base


def test_baltimore_landing_page_served(client: TestClient) -> None:
    html = client.get("/baltimore-instant-pay-cna/").text
    assert html.strip().startswith("<!DOCTYPE html>")
    assert "Baltimore Instant Pay CNA" in html
    assert 'id="text-apply-form"' in html
    assert "/baltimore-instant-pay-cna/styles.css" in html
    assert "/baltimore-instant-pay-cna/app.js" in html


def test_baltimore_landing_api_payload(client: TestClient) -> None:
    body = client.get("/api/landing/baltimore-instant-pay-cna").json()
    assert body["slug"] == "baltimore-instant-pay-cna"
    assert body["market"] == "Baltimore"
    assert len(body["selling_points"]) == 2
    assert body["selling_points"][0]["id"] == "instant_stripe_payout"
    assert "Stripe" in body["selling_points"][0]["body"]
    assert body["selling_points"][1]["id"] == "w2_compliance"
    assert "W-2" in body["selling_points"][1]["body"]
    assert body["text_apply"]["cta_label"]


def test_baltimore_text_apply_queues_intake(client: TestClient) -> None:
    suffix = str(uuid4().int % 10000).zfill(4)
    phone = f"443555{suffix}"
    response = client.post(
        "/api/landing/baltimore-instant-pay-cna/text-apply",
        json=_text_apply_payload(phone_number=phone),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["queue_status"] == "QUEUED"
    assert body["market"] == "Baltimore"
    assert body["credential_type"] == "CNA"
    assert body["intake_id"]


def test_baltimore_text_apply_requires_consent(client: TestClient) -> None:
    response = client.post(
        "/api/landing/baltimore-instant-pay-cna/text-apply",
        json=_text_apply_payload(consent_sms_dispatch=False),
    )
    assert response.status_code == 422


def test_baltimore_text_apply_rejects_duplicate(client: TestClient) -> None:
    suffix = str(uuid4().int % 10000).zfill(4)
    phone = f"301555{suffix}"
    payload = _text_apply_payload(phone_number=phone)
    first = client.post("/api/landing/baltimore-instant-pay-cna/text-apply", json=payload)
    assert first.status_code == 200
    second = client.post("/api/landing/baltimore-instant-pay-cna/text-apply", json=payload)
    assert second.status_code == 409
    assert second.json()["detail"] == "duplicate_application"
