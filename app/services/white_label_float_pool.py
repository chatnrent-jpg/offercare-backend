"""
White-Labeled Float Pool Service.

Feature: Enterprise Feature #7
Purpose: First-dibs internal staff portal with 4-hour timeout
         before floating to external marketplace.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)


class WhiteLabelFloatPoolService:
    """Internal staff float pool with timeout logic."""
    
    def __init__(self, db: Session):
        self.db = db
        self.enabled = getattr(settings, "FLOAT_POOL_ENABLED", True)
        self.timeout_hours = 4  # Float to external after 4 hours
    
    async def post_to_internal_pool(
        self,
        facility_id: UUID,
        shift_id: UUID
    ) -> Dict:
        """Post shift to facility's internal staff first."""
        from app.models import OfferCareJobOffer
        from app.services.sms import send_sms
        
        try:
            stmt = select(OfferCareJobOffer).where(
                OfferCareJobOffer.offer_id == shift_id
            )
            result = await self.db.execute(stmt)
            shift = result.scalar_one_or_none()
            
            if not shift:
                return {"status": "ERROR"}
            
            # Mark as internal-only
            shift.internal_only = True
            shift.float_timeout = datetime.now(timezone.utc) + timedelta(hours=self.timeout_hours)
            await self.db.commit()
            
            # Notify internal staff
            internal_staff = await self._get_internal_staff(facility_id)
            for staff in internal_staff:
                send_sms(
                    staff.phone_number,
                    f"🏥 INTERNAL SHIFT: {shift.shift_start.strftime('%a %m/%d')} available. "
                    f"Reply CLAIM within 4 hours."
                )
            
            logger.info(
                f"[FLOAT_POOL] Posted shift {shift_id} to internal pool "
                f"({len(internal_staff)} staff notified)"
            )
            
            return {
                "status": "POSTED_INTERNAL",
                "staff_notified": len(internal_staff),
                "timeout": shift.float_timeout.isoformat()
            }
            
        except Exception as e:
            logger.error(f"[FLOAT_POOL] Error posting to internal pool: {e}")
            return {"status": "ERROR", "error": str(e)}
    
    async def _get_internal_staff(self, facility_id: UUID) -> List:
        """Get facility's internal PRN staff."""
        from app.models import MarylandProvider
        
        stmt = select(MarylandProvider).where(
            MarylandProvider.home_facility_id == facility_id,
            MarylandProvider.employment_type == "INTERNAL_PRN"
        )
        
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def check_float_timeout(self, shift_id: UUID) -> bool:
        """Check if shift should float to external marketplace."""
        from app.models import OfferCareJobOffer
        from app.services.wave_match_dispatcher import WaveMatchDispatcher
        
        try:
            stmt = select(OfferCareJobOffer).where(
                OfferCareJobOffer.offer_id == shift_id
            )
            result = await self.db.execute(stmt)
            shift = result.scalar_one_or_none()
            
            if not shift or not shift.internal_only:
                return False
            
            now = datetime.now(timezone.utc)
            
            if now >= shift.float_timeout:
                # Float to external
                shift.internal_only = False
                await self.db.commit()
                
                dispatcher = WaveMatchDispatcher(self.db)
                await dispatcher.trigger_wave_dispatch(shift_id)
                
                logger.info(f"[FLOAT_POOL] Shift {shift_id} floated to external marketplace")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"[FLOAT_POOL] Error checking timeout: {e}")
            return False
