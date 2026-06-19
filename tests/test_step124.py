from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.services.care_taxonomy import synthetic_npi_for_caregiver


def test_join_landing_page_served(client: TestClient) -> None:
    html = client.get("/join").text
    assert html.strip().startswith("<!DOCTYPE html>")
    assert "Maryland CNA & LPN Shifts" in html
    assert 'id="apply-form"' in html
    assert "/join/styles.css" in html
    assert "/join/app.js" in html


def test_join_landing_assets(client: TestClient) -> None:
    js = client.get("/join/app.js")
    css = client.get("/join/styles.css")
    assert js.status_code == 200
    assert css.status_code == 200
    assert "/api/landing/maryland/apply" in js.text
    assert ".pay-grid" in css.text


def test_maryland_landing_api_payload(client: TestClient) -> None:
    body = client.get("/api/landing/maryland").json()
    assert "Emergency CNA & LPN" in body["headline"]
    assert body["apply_defaults"]["state"] == "MD"
    codes = {row["code"] for row in body["credentials"]}
    assert codes == {"CNA", "LPN", "GNA"}
    assert all(row["typical_hourly_pay"] > 0 for row in body["credentials"])


def test_maryland_landing_apply_runs_credentialing(client: TestClient) -> None:
    token = uuid4().hex[:10]
    email = f"landing.cna.{token}@example.com"
    response = client.post(
        "/api/landing/maryland/apply",
        json={
            "full_name": "Landing Test CNA",
            "email": email,
            "phone_number": f"410555{token[:4]}",
            "md_license_number": f"CNA-MD-{token.upper()}",
            "credential_type": "CNA",
            "min_hourly_rate": 24.0,
            "password": "testpass123",
            "home_zip": "21201",
        },
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
        json={
            "full_name": "Test User EXCLUDED",
            "email": f"excluded.{token}@example.com",
            "phone_number": f"410556{token[:4]}",
            "md_license_number": f"CNA-MD-EX{token[:6].upper()}",
            "credential_type": "CNA",
            "min_hourly_rate": 22.0,
            "password": "testpass123",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["credentialing_blocked"] is True
    assert body["dispatch_status"] == "SUSPENDED"


def test_maryland_landing_apply_lpn_requires_npi(client: TestClient) -> None:
    token = uuid4().hex[:10]
    response = client.post(
        "/api/landing/maryland/apply",
        json={
            "full_name": "Landing LPN",
            "email": f"lpn.{token}@example.com",
            "phone_number": f"410557{token[:4]}",
            "md_license_number": f"LPN-MD-{token.upper()}",
            "credential_type": "LPN",
            "min_hourly_rate": 35.0,
            "password": "testpass123",
        },
    )
    assert response.status_code == 422


def test_maryland_landing_apply_lpn_with_npi(client: TestClient) -> None:
    token = uuid4().hex[:10]
    email = f"lpn.ok.{token}@example.com"
    response = client.post(
        "/api/landing/maryland/apply",
        json={
            "full_name": "Landing LPN OK",
            "email": email,
            "phone_number": f"410558{token[:4]}",
            "md_license_number": f"LPN-MD-{token.upper()}",
            "credential_type": "LPN",
            "npi_number": synthetic_npi_for_caregiver(email),
            "min_hourly_rate": 36.0,
            "password": "testpass123",
        },
    )
    assert response.status_code == 200
    assert response.json()["credential_type"] == "LPN"
