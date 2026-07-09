import pytest
import json
from data_engine.b2b_invoicing import B2BInvoicingEngine

def test_calculate_facility_invoice_payload_default_margin():
    """Confirms default 25% margin markups compute exact billing numbers."""
    engine = B2BInvoicingEngine()
    raw_payload = engine.calculate_facility_invoice(
        facility_id="fac_corp_a",
        shift_id="shift_001",
        base_pay=40.00
    )
    
    data = json.loads(raw_payload)
    assert data["facility_id"] == "fac_corp_a"
    assert data["base_caregiver_pay"] == 40.00
    assert data["markup_percentage"] == 25.0
    assert data["total_facility_bill"] == 50.00
    assert data["calculated_margin"] == 10.00
    assert "timestamp" in data

def test_calculate_facility_invoice_payload_custom_margin():
    """Confirms custom corporate contract markups override baseline settings perfectly."""
    engine = B2BInvoicingEngine()
    raw_payload = engine.calculate_facility_invoice(
        facility_id="fac_corp_b",
        shift_id="shift_002",
        base_pay=50.00,
        custom_markup=0.30  # 30% Contracted markup
    )
    
    data = json.loads(raw_payload)
    assert data["markup_percentage"] == 30.0
    assert data["total_facility_bill"] == 65.00
    assert data["calculated_margin"] == 15.00
