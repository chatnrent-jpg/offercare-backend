from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_admin_deploy_panel_includes_export_gates_json_button(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "download-deploy-gates-json-btn" in html.text
    assert html.text.count("Export gates (.json)") >= 2


def test_admin_app_js_shares_gates_json_helper(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "downloadDemoGatesJsonFile" in text
    assert "downloadDeployGatesJsonBtn" in text
    assert "/api/seed/demo-gates.json" in text


def test_deploy_export_gates_json_button_does_not_use_export_ready_gate(client: TestClient) -> None:
    js = client.get("/admin/app.js").text
    handler = js.split("downloadDeployGatesJsonBtn?.addEventListener")[1].split("downloadDeployBundleBtn?.addEventListener")[0]
    assert "confirmDemoReadyExport" not in handler


def test_deploy_checklist_mentions_deploy_panel_gates_json_export(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["export_steps"]
    assert any(
        "deploy panel" in step.lower() and "export gates (.json)" in step.lower()
        for step in steps
    )


def test_demo_gates_json_endpoint_still_works_for_deploy_panel(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-gates.json")
    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")
    assert "offercare-demo-gates.json" in response.headers.get("content-disposition", "")
    body = response.json()
    assert body["gate_count"] == 9
    assert body["clipboard_text"]
