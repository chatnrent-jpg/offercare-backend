"""
CMS Star Rating Safeguards Service.

Feature: Enterprise Feature #6
Purpose: Monitor facility staffing ratios and alert if close to
         dropping a CMS star rating.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict
from uuid import UUID

import httpx
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)


class CMSStarSafeguardsService:
    """Protect facility CMS star ratings through staffing ratio monitoring."""
    
    def __init__(self, db: Session):
        self.db = db
        self.enabled = getattr(settings, "CMS_STAR_SAFEGUARDS_ENABLED", True)
        
        # CMS minimum staffing ratios (hours per resident per day)
        self.min_ratios = {
            "RN": 0.75,   # 45 min/resident/day
            "LPN": 0.55,  # 33 min/resident/day
            "CNA": 2.8    # 168 min/resident/day
        }
    
    async def check_staffing_ratio(
        self,
        facility_id: UUID
    ) -> Dict:
        """Check current staffing ratio vs. CMS requirements."""
        from app.models import ClinicalPlacementLedger, MarylandFacility
        
        try:
            # Get facility resident count
            stmt = select(MarylandFacility).where(
                MarylandFacility.facility_id == facility_id
            )
            result = await self.db.execute(stmt)
            facility = result.scalar_one_or_none()
            
            if not facility:
                return {"status": "ERROR"}
            
            resident_count = getattr(facility, "resident_count", 100)
            
            # Calculate actual staffing hours (last 14 days)
            cutoff = datetime.now(timezone.utc) - timedelta(days=14)
            
            stmt = select(
                func.sum(ClinicalPlacementLedger.hours_worked)
            ).where(
                ClinicalPlacementLedger.facility_id == facility_id,
                ClinicalPlacementLedger.shift_start >= cutoff
            )
            
            result = await self.db.execute(stmt)
            total_hours = result.scalar() or 0
            
            # Calculate ratio
            hours_per_resident_per_day = total_hours / (resident_count * 14)
            
            # Check against CMS minimum
            min_required = self.min_ratios["CNA"]  # Simplified
            
            if hours_per_resident_per_day < min_required * 0.9:
                status = "CRITICAL"
                logger.error(
                    f"[CMS] Facility {facility_id} CRITICAL: "
                    f"{hours_per_resident_per_day:.2f} hrs/res/day (min: {min_required})"
                )
            elif hours_per_resident_per_day < min_required:
                status = "WARNING"
                logger.warning(
                    f"[CMS] Facility {facility_id} WARNING: "
                    f"{hours_per_resident_per_day:.2f} hrs/res/day"
                )
            else:
                status = "COMPLIANT"
            
            return {
                "status": status,
                "current_ratio": round(hours_per_resident_per_day, 2),
                "required_ratio": min_required,
                "facility_id": facility_id
            }
            
        except Exception as e:
            logger.error(f"[CMS] Error checking ratio: {e}")
            return {"status": "ERROR", "error": str(e)}
