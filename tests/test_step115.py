from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_admin_app_js_renders_demo_admin_actions_catalog(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "demo_admin_actions" in text
    assert "Demo admin actions" in text
    assert "demo-admin-actions-list" in text
    assert "renderDemoGatesPanel" in text


def test_admin_styles_include_demo_admin_actions_list(client: TestClient) -> None:
    css = client.get("/admin/styles.css")
    assert css.status_code == 200
    text = css.text
    assert ".demo-admin-actions-list" in text
    assert ".demo-demo-admin-actions-list" in text
    assert ".deploy-demo-admin-actions-list" in text


def test_deploy_checklist_demo_steps_mention_panel_demo_admin_actions_catalog(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any(
        "deploy walkthrough panel renders the embedded demo admin actions catalog" in step.lower()
        for step in steps
    )
    assert any(
        "demo environment panel renders the embedded demo admin actions catalog" in step.lower()
        for step in steps
    )


def test_demo_status_next_steps_mention_panel_demo_admin_actions_catalog(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any(
        "demo environment panel renders the embedded demo admin actions catalog" in step.lower()
        for step in steps
    )


def test_demo_status_demo_gates_include_admin_actions_for_panel_render(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    demo_gates = client.get("/api/seed/demo-status").json()["demo_gates"]
    assert len(demo_gates["demo_admin_actions"]) == 8
    assert demo_gates["demo_admin_actions"][0]["endpoint"] == "POST /api/seed/demo-setup"
    assert demo_gates["demo_admin_actions"][3]["field"] == "demo_status.demo_gates"


def test_deploy_checklist_demo_gates_include_admin_actions_for_panel_render(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    demo_gates = client.get("/api/deploy/checklist").json()["demo_gates"]
    assert len(demo_gates["demo_admin_actions"]) == 8
    assert demo_gates["demo_admin_actions"][7]["action"] == "Ensure demo push subscriptions"
