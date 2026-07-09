from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from data_engine.b2b_invoicing import B2BInvoicingEngine

router = APIRouter()

class InvoiceRequest(BaseModel):
    facility_id: str = Field(..., description="Target enterprise facility UUID")
    shift_id: str = Field(..., description="Completed shift transactional UUID")
    base_caregiver_pay: float = Field(..., description="Raw hourly/flat rate paid out to provider")
    custom_markup_override: Optional[float] = Field(None, description="Optional custom contracted margin override (e.g. 0.30)")

@router.post("/calculate", status_code=status.HTTP_200_OK)
async def generate_invoice_endpoint(payload: InvoiceRequest):
    """
    HTTP Gateway exposing the B2B Invoicing Markup Engine.
    Processes corporate margins and generates structured auditing payloads.
    """
    try:
        engine = B2BInvoicingEngine()
        raw_invoice_json = engine.calculate_facility_invoice(
            facility_id=payload.facility_id,
            shift_id=payload.shift_id,
            base_pay=payload.base_caregiver_pay,
            custom_markup=payload.custom_markup_override
        )
        # Safely decode the stringified engine payload back into a standard API JSON output
        import json
        return json.loads(raw_invoice_json)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Financial processing anomaly encountered: {str(e)}"
        )
