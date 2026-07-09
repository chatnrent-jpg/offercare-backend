import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from app.api.v1 import api_v1_router

# Build a test application context specifically hosting our router
app = FastAPI()
app.include_router(api_v1_router, prefix="/api/v1")
client = TestClient(app)

def test_api_calculate_invoice_default_markup_success():
    """Confirms that HTTP POST requests correctly fall back to default corporate markup margins."""
    payload = {
        "facility_id": "fac_uuid_12345",
        "shift_id": "shift_uuid_67890",
        "base_caregiver_pay": 50.00
    }
    response = client.post("/api/v1/billing/calculate", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["facility_id"] == "fac_uuid_12345"
    assert data["base_caregiver_pay"] == 50.00
    assert data["markup_percentage"] == 25.0
    assert data["total_facility_bill"] == 62.50
    assert data["calculated_margin"] == 12.50
    assert "timestamp" in data

def test_api_calculate_invoice_custom_override_success():
    """Confirms that HTTP POST requests process premium contracted custom overrides."""
    payload = {
        "facility_id": "fac_uuid_12345",
        "shift_id": "shift_uuid_67890",
        "base_caregiver_pay": 100.00,
        "custom_markup_override": 0.40  # 40% margin lock
    }
    response = client.post("/api/v1/billing/calculate", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["markup_percentage"] == 40.0
    assert data["total_facility_bill"] == 140.00
    assert data["calculated_margin"] == 40.00

def test_api_calculate_invoice_validation_error():
    """Confirms Pydantic schema validation rejects missing required parameters."""
    payload = {
        "facility_id": "fac_uuid_12345"
        # Missing required shift_id and pay amounts
    }
    response = client.post("/api/v1/billing/calculate", json=payload)
    assert response.status_code == 422  # Unprocessable Entity (FastAPI standard)
