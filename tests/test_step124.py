from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.services.care_taxonomy import synthetic_npi_for_caregiver
from app.services.worker_consent import WORKER_CONSENT_VERSION
from app.services.worker_terms_of_service import WORKER_TERMS_VERSION


def _apply_payload(**overrides):
    base = {
        "full_name": "Landing Test CNA",
        "email": f"landing.cna.{uuid4().hex[:10]}@example.com",
        "phone_number": f"410555{uuid4().hex[:4]}",
        "md_license_number": f"CNA-MD-{uuid4().hex[:8].upper()}",
        "credential_type": "CNA",
        "min_hourly_rate": 24.0,
        "password": "testpass123",
        "consent_version": WORKER_CONSENT_VERSION,
        "consent_credential_screening": True,
        "consent_sms_dispatch": True,
        "consent_privacy_policy": True,
        "consent_terms_of_service": True,
        "consent_aedt_30_day": True,
    }
    base.update(overrides)
    return base


def test_join_landing_page_served(client: TestClient) -> None:
    html = client.get("/join").text
    assert html.strip().startswith("<!DOCTYPE html>")
    assert "Maryland CNA & LPN Shifts" in html
    assert 'id="apply-form"' in html
    assert 'id="consent-tos"' in html
    assert 'id="consent-privacy"' in html
    assert 'id="privacy-overlay"' in html
    assert 'id="tos-overlay"' in html
    assert 'id="tos-body"' in html
    assert "/join/styles.css" in html
    assert "/join/app.js" in html


def test_join_landing_assets(client: TestClient) -> None:
    js = client.get("/join/app.js")
    css = client.get("/join/styles.css")
    assert js.status_code == 200
    assert css.status_code == 200
    assert "/api/landing/maryland/apply" in js.text
    assert ".pay-grid" in css.text


def test_maryland_privacy_policy_api(client: TestClient) -> None:
    body = client.get("/api/landing/maryland/privacy-policy").json()
    assert body["title"] == "VettedMe.ai Clinician Privacy Policy"
    assert len(body["sections"]) >= 10
    assert any("STOP" in section["body"] for section in body["sections"])


def test_maryland_terms_of_service_api(client: TestClient) -> None:
    body = client.get("/api/landing/maryland/terms-of-service").json()
    assert body["title"] == "VettedMe.ai Clinician Terms of Service"
    assert body["version"] == WORKER_TERMS_VERSION
    assert len(body["sections"]) >= 10
    assert any("W-2" in section["body"] for section in body["sections"])


def test_maryland_landing_api_payload(client: TestClient) -> None:
    body = client.get("/api/landing/maryland").json()
    assert "Emergency CNA & LPN" in body["headline"]
    assert body["apply_defaults"]["state"] == "MD"
    assert body["consent_disclosures"]["version"] == WORKER_CONSENT_VERSION
    assert "terms_of_service" in body["consent_disclosures"]
    assert body["consent_disclosures"]["terms_of_service_url"] == "/api/landing/maryland/terms-of-service"
    assert body["consent_disclosures"]["privacy_policy_url"] == "/api/landing/maryland/privacy-policy"
    assert body["privacy_policy"]["title"] == "VettedMe.ai Clinician Privacy Policy"
    assert len(body["terms_of_service"]["sections"]) >= 10
    codes = {row["code"] for row in body["credentials"]}
    assert codes == {"CNA", "LPN", "GNA"}
    assert all(row["typical_hourly_pay"] > 0 for row in body["credentials"])


def test_maryland_landing_apply_requires_consent(client: TestClient) -> None:
    payload = _apply_payload()
    del payload["consent_sms_dispatch"]
    payload["consent_sms_dispatch"] = False
    response = client.post("/api/landing/maryland/apply", json=payload)
    assert response.status_code == 422
    assert "consent_required" in str(response.json()["detail"])


def test_maryland_landing_apply_runs_credentialing(client: TestClient) -> None:
    token = uuid4().hex[:10]
    email = f"landing.cna.{token}@example.com"
    response = client.post(
        "/api/landing/maryland/apply",
        json=_apply_payload(
            full_name="Landing Test CNA",
            email=email,
            phone_number=f"410555{token[:4]}",
            md_license_number=f"CNA-MD-{token.upper()}",
            home_zip="21201",
        ),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["license_status"] == "VERIFIED"
    assert body["dispatch_status"] == "ACTIVE"
    assert body["mbon_status"] == "ACTIVE"
    assert body["oig_status"] == "CLEAR"
    assert body["credentialing_blocked"] is False
    assert body["portal_url"] == "/portal"


def test_maryland_landing_apply_blocks_excluded_name(client: TestClient) -> None:
    token = uuid4().hex[:10]
    response = client.post(
        "/api/landing/maryland/apply",
        json=_apply_payload(
            full_name="Test User EXCLUDED",
            email=f"excluded.{token}@example.com",
            phone_number=f"410556{token[:4]}",
            md_license_number=f"CNA-MD-EX{token[:6].upper()}",
            min_hourly_rate=22.0,
        ),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["credentialing_blocked"] is True
    assert body["dispatch_status"] == "SUSPENDED"


def test_maryland_landing_apply_lpn_requires_npi(client: TestClient) -> None:
    token = uuid4().hex[:10]
    response = client.post(
        "/api/landing/maryland/apply",
        json=_apply_payload(
            full_name="Landing LPN",
            email=f"lpn.{token}@example.com",
            phone_number=f"410557{token[:4]}",
            md_license_number=f"LPN-MD-{token.upper()}",
            credential_type="LPN",
            min_hourly_rate=35.0,
        ),
    )
    assert response.status_code == 422


def test_maryland_landing_apply_lpn_with_npi(client: TestClient) -> None:
    token = uuid4().hex[:10]
    email = f"lpn.ok.{token}@example.com"
    response = client.post(
        "/api/landing/maryland/apply",
        json=_apply_payload(
            full_name="Landing LPN OK",
            email=email,
            phone_number=f"410558{token[:4]}",
            md_license_number=f"LPN-MD-{token.upper()}",
            credential_type="LPN",
            npi_number=synthetic_npi_for_caregiver(email),
            min_hourly_rate=36.0,
        ),
    )
    assert response.status_code == 200
    assert response.json()["credential_type"] == "LPN"
