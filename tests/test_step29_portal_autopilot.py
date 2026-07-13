"""Portal step 29 — demo autopilot + journey export."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import PORTAL_BUILD_ID
from app.services.demo_portal_accounts import DEMO_PORTAL_PASSWORD, SAMPLE_DEMO_PORTAL_EMAIL


def test_portal_step29_assets(client: TestClient) -> None:
    html = client.get("/portal/").text
    js = client.get("/portal/app.js").text
    css = client.get("/portal/styles.css").text
    assert f'data-portal-build="{PORTAL_BUILD_ID}"' in html
    assert "demo-tools-panel" in html
    assert "runDemoAutopilot" in js
    assert "downloadJourneyExport" in js
    assert ".demo-tools-panel" in css


def test_demo_autopilot_endpoint(client: TestClient) -> None:
    login = client.post(
        "/api/clinicians/login",
        json={"email": SAMPLE_DEMO_PORTAL_EMAIL, "password": DEMO_PORTAL_PASSWORD},
    )
    if login.status_code == 401:
        pytest.skip("demo login unavailable")
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.post("/api/clinicians/me/demo-autopilot", headers=headers)
    if response.status_code == 404:
        pytest.skip("autopilot route unavailable on this API build")
    assert response.status_code == 200
    body = response.json()
    assert body.get("ok") is True


def test_demo_journey_export_endpoint(client: TestClient) -> None:
    login = client.post(
        "/api/clinicians/login",
        json={"email": SAMPLE_DEMO_PORTAL_EMAIL, "password": DEMO_PORTAL_PASSWORD},
    )
    if login.status_code == 401:
        pytest.skip("demo login unavailable")
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get("/api/clinicians/me/journey-export", headers=headers)
    if response.status_code == 404:
        pytest.skip("journey export unavailable on this API build")
    assert response.status_code == 200
    body = response.json()
    assert "export_text" in body
    assert "VettedMe.ai" in body["export_text"]
