"""
Patient Acuity-Based Staffing Service.

Feature: Enterprise Feature #5
Purpose: Integrate with EHR acuity scores to recommend appropriate
         license types (CNA → GNA → LPN escalation).
"""

import logging
from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)


class PatientAcuityStaffingService:
    """Acuity-based staffing recommendations."""
    
    def __init__(self, db: Session):
        self.db = db
        self.enabled = getattr(settings, "ACUITY_STAFFING_ENABLED", True)
        
        # Acuity score to license type mapping
        self.acuity_rules = {
            (0, 2): "CNA",   # Low acuity
            (3, 4): "GNA",   # Medium acuity
            (5, 5): "LPN"    # High acuity
        }
    
    async def get_facility_acuity(
        self,
        facility_id: UUID
    ) -> Optional[float]:
        """Fetch current acuity score from EHR."""
        from app.services.ehr_integration_gateway import EHRIntegrationGateway
        
        try:
            gateway = EHRIntegrationGateway(self.db)
            acuity_data = await gateway.fetch_acuity_scores(facility_id)
            return acuity_data.get("average_acuity", 2.5)
        except Exception as e:
            logger.error(f"[ACUITY] Error fetching acuity: {e}")
            return None
    
    def recommend_license_type(self, acuity_score: float) -> str:
        """Recommend appropriate license type based on acuity."""
        for (min_acuity, max_acuity), license_type in self.acuity_rules.items():
            if min_acuity <= acuity_score <= max_acuity:
                return license_type
        return "LPN"  # Default to highest license
    
    async def check_shift_upgrade(
        self,
        shift_id: UUID
    ) -> Dict:
        """Check if shift requires license type upgrade."""
        from app.models import OfferCareJobOffer
        
        try:
            stmt = select(OfferCareJobOffer).where(
                OfferCareJobOffer.offer_id == shift_id
            )
            result = await self.db.execute(stmt)
            shift = result.scalar_one_or_none()
            
            if not shift:
                return {"status": "ERROR"}
            
            acuity = await self.get_facility_acuity(shift.facility_id)
            if not acuity:
                return {"status": "UNKNOWN"}
            
            recommended = self.recommend_license_type(acuity)
            current = shift.license_required or "CNA"
            
            if recommended != current:
                logger.warning(
                    f"[ACUITY] Shift {shift_id} upgrade recommended: "
                    f"{current} → {recommended} (acuity: {acuity})"
                )
                return {
                    "status": "UPGRADE_NEEDED",
                    "current": current,
                    "recommended": recommended,
                    "acuity_score": acuity
                }
            
            return {"status": "APPROPRIATE", "acuity_score": acuity}
            
        except Exception as e:
            logger.error(f"[ACUITY] Error checking upgrade: {e}")
            return {"status": "ERROR", "error": str(e)}
