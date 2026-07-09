import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from app.api.v1 import api_v1_router

# Initialize a standard test app context containing our v1 routes
app = FastAPI()
app.include_router(api_v1_router, prefix="/api/v1")
client = TestClient(app)

def test_api_verify_mbon_credential_success():
    """Confirms live HTTP POST payloads route successfully to the MBON compliance adapter."""
    payload = {
        "license_number": "LPN123456",
        "profession": "LPN"
    }
    response = client.post("/api/v1/scale/verify-mbon", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["verified"] is True
    assert data["status"] == "ACTIVE"
    assert "expires_at" in data

def test_api_segment_dispatch_waves_success():
    """Confirms live array payloads process and divide into tiered 5-minute segments."""
    payload = {
        "provider_ids": [f"nurse_id_{i}" for i in range(10)]
    }
    response = client.post("/api/v1/scale/segment-waves", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "waves" in data
    # Tier 1 should contain the first 5 top matches
    assert len(data["waves"]["1"]) == 5

def test_api_segment_dispatch_waves_empty_validation_error():
    """Confirms the API router validates and rejects empty tracking lists."""
    payload = {
        "provider_ids": []
    }
    response = client.post("/api/v1/scale/segment-waves", json=payload)
    # Fastapi should catch the custom validation check exception or schema rule failure
    assert response.status_code == 400
    assert "detail" in response.json()


def test_api_generate_ohcq_audit_ledger_success():
    """Confirms historical data extracts generate signed, deterministic ledger payloads."""
    payload = {
        "facility_id": "fac_7e2a1b9c4d8e0f1a3b5c6d7e8",
        "start_date": "2026-01-01",
        "end_date": "2026-06-30"
    }
    response = client.post("/api/v1/scale/export-ohcq-audit", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "ledger_id" in data
    assert "merkle_root_hash" in data
    assert "cryptographic_signature" in data
    assert "exported_at" in data
    
    # Verify metadata contains our inspection targets
    assert data["metadata_summary"]["facility_id"] == payload["facility_id"]
    assert data["metadata_summary"]["total_verified_shifts"] > 0
    assert data["metadata_summary"]["oig_exclusion_violations"] == 0
