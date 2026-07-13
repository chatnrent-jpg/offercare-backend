"""
Production-Grade Pytest Suite for OHCQ Deployment Checklist
Tests the Maryland Department of Health / OHCQ compliance endpoint
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def client():
    """
    Initializes a clean, reusable TestClient instance 
    hooked into the core VettedMe backend application.
    """
    with TestClient(app) as test_client:
        yield test_client


def test_get_deployment_checklist_success(client):
    """
    Validates that the checklist endpoint responds with a 200 OK 
    status and confirms the root dictionary key footprint is fully intact.
    """
    response = client.get("/api/deploy/checklist/ohcq-demo")
    assert response.status_code == 200
    
    payload = response.json()
    assert "summary" in payload
    assert "maryland_production_runbook" in payload
    assert "maryland_launch_capstone" in payload
    assert "items" in payload


def test_maryland_ohcq_compliance_gates(client):
    """
    Strict validation of Layer 1 & Layer 2 Maryland OHCQ regulatory requirements.
    Ensures the server flags mandatory live registry connection gates as True.
    """
    response = client.get("/api/deploy/checklist/ohcq-demo")
    payload = response.json()
    
    # Layer 1 Verification (MBON Scraper Telemetry)
    runbook = payload["maryland_production_runbook"]
    assert runbook is not None
    assert runbook["production_ready"] is True
    assert any(check["layer"] == "OHCQ / MBON Validation" for check in runbook["checks"])
    
    # Layer 2 Verification (HB 1106 Disclosure & Licensing Gates)
    capstone = payload["maryland_launch_capstone"]
    assert capstone is not None
    assert capstone["launch_ready"] is True
    assert capstone["live_scrapers_all_live"] is True
    assert any("HB 1106" in check["gate_name"] for check in capstone["checks"])


def test_summary_and_operational_dashboard_metrics(client):
    """
    Verifies global summary boolean configurations and checks that the 
    production readiness metrics are properly tracked.
    """
    response = client.get("/api/deploy/checklist/ohcq-demo")
    payload = response.json()
    
    # Global Readiness Summary
    summary = payload["summary"]
    assert summary["maryland_production_ready"] is True
    assert summary["maryland_launch_ready"] is True
    assert summary["blocked"] == 0
    assert summary["warnings"] == 0


def test_demo_gates_and_admin_actions(client):
    """
    Validates that demo gates and admin action structures are present
    and properly formatted for OHCQ compliance tracking.
    """
    response = client.get("/api/deploy/checklist/ohcq-demo")
    payload = response.json()
    
    # Demo Gates Structure
    demo_gates = payload["demo_gates"]
    assert demo_gates is not None
    assert "gates_active" in demo_gates
    assert "bypassed_gates" in demo_gates
    assert "enforced_gates" in demo_gates
    
    # Admin Actions List
    assert "demo_admin_actions" in payload
    assert isinstance(payload["demo_admin_actions"], list)


def test_twilio_and_portal_steps(client):
    """
    Verifies that Twilio SMS and portal deployment steps are 
    included in the checklist response.
    """
    response = client.get("/api/deploy/checklist/ohcq-demo")
    payload = response.json()
    
    # Twilio Console Steps
    assert "twilio_console_steps" in payload
    assert isinstance(payload["twilio_console_steps"], list)
    assert len(payload["twilio_console_steps"]) > 0
    
    # Portal Steps
    assert "portal_steps" in payload
    assert isinstance(payload["portal_steps"], list)


def test_mbon_check_structure(client):
    """
    Deep validation of MBON (Maryland Board of Nursing) check structure
    to ensure all required compliance fields are present.
    """
    response = client.get("/api/deploy/checklist/ohcq-demo")
    payload = response.json()
    
    runbook = payload["maryland_production_runbook"]
    checks = runbook["checks"]
    
    # Verify at least one check exists
    assert len(checks) > 0
    
    # Verify check structure
    mbon_check = checks[0]
    assert "id" in mbon_check
    assert "name" in mbon_check
    assert "layer" in mbon_check
    assert "status" in mbon_check
    assert "checked_at" in mbon_check
    assert "passed" in mbon_check
    
    # Verify MBON-specific fields
    assert mbon_check["passed"] is True
    assert mbon_check["status"] == "PASSED"


def test_hb1106_capstone_check_structure(client):
    """
    Deep validation of HB 1106 AEDT disclosure compliance check structure.
    """
    response = client.get("/api/deploy/checklist/ohcq-demo")
    payload = response.json()
    
    capstone = payload["maryland_launch_capstone"]
    checks = capstone["checks"]
    
    # Verify at least one check exists
    assert len(checks) > 0
    
    # Verify check structure
    hb1106_check = checks[0]
    assert "id" in hb1106_check
    assert "gate_name" in hb1106_check
    assert "status" in hb1106_check
    assert "passed" in hb1106_check
    assert "critical" in hb1106_check
    
    # Verify HB 1106-specific fields
    assert hb1106_check["passed"] is True
    assert hb1106_check["critical"] is True


def test_deployment_items_structure(client):
    """
    Validates that deployment checklist items are properly structured
    with all required fields for audit trail compliance.
    """
    response = client.get("/api/deploy/checklist/ohcq-demo")
    payload = response.json()
    
    items = payload["items"]
    assert len(items) > 0
    
    # Verify item structure
    item = items[0]
    assert "id" in item
    assert "title" in item
    assert "status" in item
    assert "detail" in item
    
    # Verify Healthcare Credentials item
    assert "Healthcare Credentials" in item["title"]
    assert item["status"] == "ready"


def test_runbook_environment_snippet(client):
    """
    Verifies that environment configuration snippets are included
    for operational deployment guidance.
    """
    response = client.get("/api/deploy/checklist/ohcq-demo")
    payload = response.json()
    
    runbook = payload["maryland_production_runbook"]
    assert "env_snippet" in runbook
    assert len(runbook["env_snippet"]) > 0
    
    capstone = payload["maryland_launch_capstone"]
    assert "env_snippet" in capstone
    assert len(capstone["env_snippet"]) > 0


def test_launch_urls_and_probes(client):
    """
    Validates that launch URLs and probe configurations are included
    for live scraper monitoring.
    """
    response = client.get("/api/deploy/checklist/ohcq-demo")
    payload = response.json()
    
    runbook = payload["maryland_production_runbook"]
    assert "launch_urls" in runbook
    assert isinstance(runbook["launch_urls"], dict)
    assert "probes" in runbook
    assert isinstance(runbook["probes"], list)
    
    capstone = payload["maryland_launch_capstone"]
    assert "launch_urls" in capstone
    assert isinstance(capstone["launch_urls"], dict)
    assert "probes" in capstone
    assert isinstance(capstone["probes"], list)


def test_summary_count_fields(client):
    """
    Comprehensive validation of all summary count fields to ensure
    accurate production readiness metrics.
    """
    response = client.get("/api/deploy/checklist/ohcq-demo")
    payload = response.json()
    
    summary = payload["summary"]
    
    # Core counts
    assert summary["ready"] >= 0
    assert summary["warnings"] >= 0
    assert summary["blocked"] >= 0
    
    # Maryland-specific counts
    assert "maryland_production_ready_count" in summary
    assert "maryland_production_warning_count" in summary
    assert "maryland_production_blocked_count" in summary
    
    assert "maryland_launch_ready_count" in summary
    assert "maryland_launch_warning_count" in summary
    assert "maryland_launch_blocked_count" in summary
    
    # Operations counts
    assert "production_ops_ready_count" in summary
    assert "production_perfection_ready_count" in summary
    assert "production_launch_ceremony_ready_count" in summary


def test_response_schema_compliance(client):
    """
    Final comprehensive check that the entire response payload
    matches the expected OHCQ-compliant schema structure.
    """
    response = client.get("/api/deploy/checklist/ohcq-demo")
    assert response.status_code == 200
    
    payload = response.json()
    
    # Top-level required fields
    required_fields = [
        "summary",
        "demo_gates",
        "demo_admin_actions",
        "twilio_console_steps",
        "portal_steps",
        "maryland_production_runbook",
        "maryland_launch_capstone",
        "items"
    ]
    
    for field in required_fields:
        assert field in payload, f"Missing required field: {field}"
    
    # Verify no critical errors in response
    assert payload["summary"]["blocked"] == 0
    assert payload["maryland_production_runbook"]["production_ready"] is True
    assert payload["maryland_launch_capstone"]["launch_ready"] is True
