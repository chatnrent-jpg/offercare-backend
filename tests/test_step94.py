from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_admin_deploy_panel_includes_gate_export_buttons(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "copy-deploy-gates-btn" in html.text
    assert "download-deploy-gates-txt-btn" in html.text
    assert html.text.count("Copy active gates") >= 2
    assert html.text.count("Download gates (.txt)") >= 2


def test_admin_app_js_shares_gate_export_helpers(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "copyDemoGatesToClipboard" in text
    assert "downloadDemoGatesTxtFile" in text
    assert "copyDeployGatesBtn" in text
    assert "downloadDeployGatesTxtBtn" in text


def test_deploy_gate_buttons_do_not_use_export_ready_gate(client: TestClient) -> None:
    js = client.get("/admin/app.js").text
    copyHandler = js.split("copyDeployGatesBtn?.addEventListener")[1].split("downloadDeployGatesTxtBtn?.addEventListener")[0]
    txtHandler = js.split("downloadDeployGatesTxtBtn?.addEventListener")[1].split("downloadDeployBundleBtn?.addEventListener")[0]
    assert "confirmDemoReadyExport" not in copyHandler
    assert "confirmDemoReadyExport" not in txtHandler


def test_deploy_checklist_mentions_deploy_panel_gate_exports(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["export_steps"]
    assert any("deploy panel" in step.lower() and "copy active gates" in step.lower() for step in steps)


def test_demo_gates_endpoints_still_work_for_deploy_panel_actions(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    gates = client.get("/api/seed/demo-gates")
    assert gates.status_code == 200
    assert gates.json()["clipboard_text"]

    txt = client.get("/api/seed/demo-gates.txt")
    assert txt.status_code == 200
    assert "Gate matrix:" in txt.text
