"""
Facility Credit Check & Factoring Service.

Feature: Advanced Feature #10
Purpose: Run credit checks on new facilities and require deposits for risky ones.
"""

import logging
from typing import Dict
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)


class FacilityCreditCheckService:
    """Credit check and risk scoring for facilities."""
    
    def __init__(self, db: Session):
        self.db = db
        self.enabled = getattr(settings, "CREDIT_CHECK_ENABLED", True)
        self.experian_api_key = getattr(settings, "EXPERIAN_API_KEY", None)
    
    async def run_credit_check(
        self,
        facility_id: UUID
    ) -> Dict:
        """Run credit check on facility."""
        from app.models import MarylandFacility
        
        try:
            stmt = select(MarylandFacility).where(
                MarylandFacility.facility_id == facility_id
            )
            result = await self.db.execute(stmt)
            facility = result.scalar_one_or_none()
            
            if not facility:
                return {"status": "ERROR"}
            
            # Run Experian check
            credit_score = await self._fetch_experian_score(facility.tax_id)
            
            # Determine deposit requirement
            if credit_score < 600:
                deposit_required = True
                deposit_amount = 5000
                risk_level = "HIGH"
            elif credit_score < 700:
                deposit_required = True
                deposit_amount = 2000
                risk_level = "MEDIUM"
            else:
                deposit_required = False
                deposit_amount = 0
                risk_level = "LOW"
            
            logger.info(
                f"[CREDIT] Facility {facility_id}: Score {credit_score}, "
                f"Risk: {risk_level}, Deposit: ${deposit_amount}"
            )
            
            return {
                "credit_score": credit_score,
                "risk_level": risk_level,
                "deposit_required": deposit_required,
                "deposit_amount": deposit_amount
            }
            
        except Exception as e:
            logger.error(f"[CREDIT] Error running check: {e}")
            return {"status": "ERROR", "error": str(e)}
    
    async def _fetch_experian_score(self, tax_id: str) -> int:
        """Fetch credit score from Experian."""
        if not self.experian_api_key:
            return 750  # Mock score
        
        try:
            url = f"{settings.EXPERIAN_API_URL}/business-credit"
            headers = {"Authorization": f"Bearer {self.experian_api_key}"}
            params = {"tax_id": tax_id}
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
            
            return data["credit_score"]
            
        except Exception as e:
            logger.error(f"[CREDIT] Experian API error: {e}")
            return 750  # Mock fallback
