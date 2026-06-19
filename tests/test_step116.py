from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_admin_app_js_wires_top_level_demo_admin_actions_to_panels(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "resolveDemoAdminActions" in text
    assert "renderDeployDemoGates(data.demo_gates, data.demo_admin_actions)" in text
    assert "renderDemoGates(data.demo_gates, data.demo_admin_actions)" in text


def test_admin_app_js_copy_gates_mentions_admin_actions_catalog(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "adminActionCount" in text
    assert "Copied gate matrix + admin actions" in text
    assert "demo_admin_actions" in text


def test_demo_status_includes_top_level_demo_admin_actions_for_panel_wiring(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.get("/api/seed/demo-status").json()
    assert len(body["demo_admin_actions"]) == 8
    assert len(body["demo_gates"]["demo_admin_actions"]) == 8
    assert body["demo_admin_actions"][0]["endpoint"] == "POST /api/seed/demo-setup"


def test_deploy_checklist_includes_top_level_demo_admin_actions_for_panel_wiring(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.get("/api/deploy/checklist").json()
    assert len(body["demo_admin_actions"]) == 8
    assert len(body["demo_gates"]["demo_admin_actions"]) == 8
    assert body["demo_admin_actions"][6]["endpoint"] == "POST /api/seed/demo-portal-accounts"


def test_demo_gates_clipboard_text_includes_admin_actions_catalog(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.get("/api/seed/demo-gates").json()
    assert len(body["demo_admin_actions"]) == 8
    assert "Demo admin actions:" in body["clipboard_text"]
    assert "POST /api/seed/demo-push-subscriptions" in body["clipboard_text"]


def test_demo_status_next_steps_mention_copy_gates_admin_actions_catalog(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any(
        "copy active gates" in step.lower() and "demo admin actions catalog" in step.lower()
        for step in steps
    )


def test_deploy_checklist_export_steps_mention_copy_gates_admin_actions_catalog(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["export_steps"]
    assert any(
        "copy active gates" in step.lower() and "demo admin actions catalog" in step.lower()
        for step in steps
    )
