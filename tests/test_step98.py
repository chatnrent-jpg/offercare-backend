from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_admin_dashboard_includes_demo_demo_gates_container(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "demo-demo-gates" in html.text
    css = client.get("/admin/styles.css")
    assert css.status_code == 200
    assert ".demo-demo-gates" in css.text
    assert ".demo-demo-gates-list" in css.text


def test_admin_app_js_renders_demo_gates(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "renderDemoGates" in text
    assert "demoDemoGates" in text
    assert "Demo confirmation gates" in text
    assert "data.demo_gates" in text


def test_deploy_checklist_demo_steps_mention_demo_panel_inline_gate_matrix(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any(
        "demo environment panel renders the embedded demo_gates gate matrix" in step.lower()
        for step in steps
    )


def test_demo_status_next_steps_mention_demo_panel_inline_gate_matrix(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any(
        "demo environment panel renders the embedded demo_gates gate matrix" in step.lower()
        for step in steps
    )


def test_demo_status_includes_demo_gates_for_panel_render(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.get("/api/seed/demo-status").json()
    demo_gates = body["demo_gates"]
    assert demo_gates is not None
    assert demo_gates["gate_count"] == 9
    assert len(demo_gates["gates"]) == 9
    assert any(row["id"] == "reset_environment" and row["active"] for row in demo_gates["gates"])
    assert any(row["id"] == "export_walkthrough" and not row["active"] for row in demo_gates["gates"])
