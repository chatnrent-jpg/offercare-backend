import json
import dataclasses
from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, Any

@dataclasses.dataclass(frozen=True)
class InvoicePayload:
    facility_id: str
    shift_id: str
    base_caregiver_pay: float
    markup_percentage: float
    total_facility_bill: float
    calculated_margin: float
    timestamp: str

class B2BInvoicingEngine:
    """Calculates enterprise client markup tiers and logs auditable billing states."""
    
    def __init__(self, default_markup_rate: float = 0.25):
        # Enforces a baseline 25% corporate margin markup unless custom contracted
        self.default_markup_rate = default_markup_rate

    def calculate_facility_invoice(
        self, 
        facility_id: str, 
        shift_id: str, 
        base_pay: float, 
        custom_markup: float = None
    ) -> str:
        """Computes margin calculations and generates a validated JSON billing payload."""
        markup_rate = custom_markup if custom_markup is not None else self.default_markup_rate
        
        # Enforce exact decimal math precision for high-volume enterprise compliance auditing
        base_pay_dec = Decimal(str(base_pay))
        markup_rate_dec = Decimal(str(markup_rate))
        
        total_bill_dec = base_pay_dec * (Decimal("1.0") + markup_rate_dec)
        margin_earned_dec = total_bill_dec - base_pay_dec
        
        payload = InvoicePayload(
            facility_id=facility_id,
            shift_id=shift_id,
            base_caregiver_pay=float(base_pay_dec),
            markup_percentage=float(markup_rate_dec * 100),
            total_facility_bill=float(total_bill_dec),
            calculated_margin=float(margin_earned_dec),
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        return json.dumps(dataclasses.asdict(payload))
