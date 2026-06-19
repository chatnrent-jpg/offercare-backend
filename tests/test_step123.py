from __future__ import annotations

from fastapi.testclient import TestClient


def test_admin_dashboard_includes_compliance_panel(client: TestClient) -> None:
    html = client.get("/admin").text
    assert "compliance-panel" in html
    assert "Maryland COMAR compliance" in html
    assert "compliance-summary" in html
    assert "compliance-providers-table" in html


def test_admin_app_js_renders_compliance_dashboard(client: TestClient) -> None:
    js = client.get("/admin/app.js").text
    assert "renderComplianceSummary" in js
    assert "loadComplianceDashboard" in js
    assert "/api/compliance/overview" in js
    assert "screenProviderCredentials" in js
    assert "runComplianceMonitor" in js


def test_admin_styles_include_compliance_flags(client: TestClient) -> None:
    css = client.get("/admin/styles.css").text
    assert ".compliance-flags" in css
    assert ".compliance-flag.dry" in css


def test_compliance_overview_endpoint(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.get("/api/compliance/overview?limit=25").json()
    assert body["total_providers"] >= 1
    assert "dispatch_active" in body
    assert "dispatch_suspended" in body
    assert "dry_run_flags" in body
    assert isinstance(body["providers"], list)
    if body["providers"]:
        row = body["providers"][0]
        assert "dispatch_eligible" in row
        assert "expiring_documents" in row


def test_pending_clinicians_table_has_screen_action_in_admin_js(client: TestClient) -> None:
    js = client.get("/admin/app.js").text
    assert 'data-screen="${row.provider_id}"' in js
    assert "Screen</button>" in js
