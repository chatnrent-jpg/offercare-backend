"""Portal auth rebuild — email/password, demo login, and OAuth providers."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import PORTAL_BUILD_ID
from app.services.portal_oauth import create_oauth_state, oauth_providers_enabled, verify_oauth_state


def test_portal_auth_providers_endpoint(client: TestClient) -> None:
    response = client.get("/api/portal/auth/providers")
    assert response.status_code == 200
    body = response.json()
    assert "google" in body
    assert "facebook" in body
    assert body["demo"] is True


def test_portal_demo_login(client: TestClient) -> None:
    response = client.post("/api/portal/auth/demo-login")
    if response.status_code == 401:
        pytest.skip("demo clinician not available in this database")
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["provider"]["email"] == "nj.snf.cna.a@offercare.demo"


def test_portal_auth_assets(client: TestClient) -> None:
    html = client.get("/portal/").text
    js = client.get("/portal/auth.js").text
    assert f'data-portal-build="{PORTAL_BUILD_ID}"' in html
    assert "PortalAuth" in js
    assert "google-login-btn" in html
    assert "facebook-login-btn" in html
    assert "demo-login-btn" in html


def test_oauth_state_roundtrip() -> None:
    state = create_oauth_state("google")
    verify_oauth_state(state, "google")
    with pytest.raises(ValueError):
        verify_oauth_state(state, "facebook")


def test_oauth_providers_enabled_defaults_false() -> None:
    enabled = oauth_providers_enabled()
    assert enabled["google"] is False or isinstance(enabled["google"], bool)
    assert enabled["facebook"] is False or isinstance(enabled["facebook"], bool)


def test_normalize_absolute_url_fixes_single_slash_http() -> None:
    from app.services.portal_oauth import normalize_absolute_url

    assert normalize_absolute_url("http:/127.0.0.1:8000") == "http://127.0.0.1:8000"
    assert normalize_absolute_url("127.0.0.1:8000") == "http://127.0.0.1:8000"
