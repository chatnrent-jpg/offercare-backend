from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


def test_portal_manifest_is_valid_json(client: TestClient) -> None:
    response = client.get("/portal/manifest.webmanifest")
    assert response.status_code == 200
    manifest = json.loads(response.text)
    assert manifest["name"] == "VettedMe.ai Clinician Portal"
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/portal/"
    assert manifest["icons"][0]["src"] == "/portal/icon.svg"


def test_portal_icon_served(client: TestClient) -> None:
    response = client.get("/portal/icon.svg")
    assert response.status_code == 200
    assert "svg" in response.headers["content-type"]
    assert "<svg" in response.text


def test_portal_has_pwa_meta_tags(client: TestClient) -> None:
    response = client.get("/portal/")
    assert response.status_code == 200
    text = response.text
    assert 'rel="manifest"' in text
    assert 'name="theme-color"' in text
    assert 'name="apple-mobile-web-app-capable"' in text
    assert "viewport-fit=cover" in text
    assert "install-banner" in text
    assert "install-app-btn" in text


def test_portal_mid_atlantic_copy(client: TestClient) -> None:
    response = client.get("/portal/")
    text = response.text
    assert "Mid-Atlantic clinicians" in text
    assert "PA, DE, and NJ" in text
    assert "Matched shifts" in text


def test_portal_apply_form_includes_expansion_states(client: TestClient) -> None:
    response = client.get("/portal/")
    text = response.text
    assert 'value="PA"' in text
    assert 'value="DE"' in text
    assert 'value="NJ"' in text


def test_portal_service_worker_has_offline_shell(client: TestClient) -> None:
    response = client.get("/portal/sw.js")
    assert response.status_code == 200
    text = response.text
    assert "install" in text
    assert "caches" in text
    assert "/portal/manifest.webmanifest" in text
    assert "showNotification" in text


def test_portal_js_registers_service_worker(client: TestClient) -> None:
    response = client.get("/portal/app.js")
    assert response.status_code == 200
    text = response.text
    assert "registerPortalServiceWorker" in text
    assert "beforeinstallprompt" in text
    assert "installPortalApp" in text


def test_portal_styles_include_mobile_safe_area(client: TestClient) -> None:
    response = client.get("/portal/styles.css")
    assert response.status_code == 200
    text = response.text
    assert "safe-area-inset" in text
    assert "install-banner" in text
    assert "@media (max-width: 720px)" in text
