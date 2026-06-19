from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_admin_open_shifts_includes_notify_matched_button(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "data-notify-matched" in text
    assert "notifyMatchedOffer" in text
    assert "/api/shifts/offers/" in text
    assert "notify-matched" in text


def test_portal_service_worker_deep_links_matched_shift(client: TestClient) -> None:
    response = client.get("/portal/sw.js")
    assert response.status_code == 200
    text = response.text
    assert "offer_id" in text
    assert "/portal/?offer=" in text


def test_portal_app_focuses_offer_from_push_alert(client: TestClient) -> None:
    js = client.get("/portal/app.js")
    assert js.status_code == 200
    text = js.text
    assert "focusOfferFromAlert" in text
    assert "getOfferIdFromQuery" in text
    assert "shift-highlight" in text


def test_deploy_checklist_mentions_matched_push_deep_link(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["portal_steps"]
    assert any("offer=" in step for step in steps)
