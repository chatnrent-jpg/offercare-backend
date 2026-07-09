"""
AI-Driven Burnout Prediction Service.

Feature: Advanced Feature #8
Purpose: Detect behavioral signals indicating nurse burnout
         and proactively intervene.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)


class BurnoutPredictionService:
    """ML-powered burnout detection and intervention."""
    
    def __init__(self, db: Session):
        self.db = db
        self.enabled = getattr(settings, "BURNOUT_PREDICTION_ENABLED", True)
    
    async def predict_burnout_risk(
        self,
        provider_id: UUID
    ) -> Dict:
        """Predict burnout risk based on behavioral signals."""
        from app.models import ClinicalPlacementLedger, MarylandProvider
        
        try:
            # Get provider history
            lookback = datetime.now(timezone.utc) - timedelta(days=30)
            
            stmt = select(
                func.count(ClinicalPlacementLedger.ledger_id),
                func.avg(ClinicalPlacementLedger.facility_rating)
            ).where(
                ClinicalPlacementLedger.provider_id == provider_id,
                ClinicalPlacementLedger.shift_start >= lookback
            )
            
            result = await self.db.execute(stmt)
            shift_count, avg_rating = result.first()
            
            risk_score = 0
            signals = []
            
            # Signal 1: Sudden decline in accepted shifts
            if shift_count < 8:
                risk_score += 30
                signals.append("LOW_SHIFT_VOLUME")
            
            # Signal 2: Drop in facility ratings
            if avg_rating and avg_rating < 3.5:
                risk_score += 40
                signals.append("LOW_RATINGS")
            
            # Signal 3: Recent cancellations
            stmt = select(func.count(ClinicalPlacementLedger.ledger_id)).where(
                ClinicalPlacementLedger.provider_id == provider_id,
                ClinicalPlacementLedger.shift_start >= lookback,
                ClinicalPlacementLedger.status == "CANCELLED"
            )
            result = await self.db.execute(stmt)
            cancellations = result.scalar() or 0
            
            if cancellations >= 2:
                risk_score += 30
                signals.append("HIGH_CANCELLATIONS")
            
            # Determine risk level
            if risk_score >= 60:
                risk_level = "HIGH"
                action = "IMMEDIATE_INTERVENTION"
            elif risk_score >= 30:
                risk_level = "MEDIUM"
                action = "PROACTIVE_OUTREACH"
            else:
                risk_level = "LOW"
                action = "NONE"
            
            logger.info(
                f"[BURNOUT] Provider {provider_id}: {risk_level} risk "
                f"(score: {risk_score}, signals: {signals})"
            )
            
            # Auto-intervene for high risk
            if risk_level == "HIGH":
                await self._send_intervention(provider_id)
            
            return {
                "risk_level": risk_level,
                "risk_score": risk_score,
                "signals": signals,
                "action": action
            }
            
        except Exception as e:
            logger.error(f"[BURNOUT] Error predicting risk: {e}")
            return {"risk_level": "ERROR", "error": str(e)}
    
    async def _send_intervention(self, provider_id: UUID) -> bool:
        """Send proactive intervention message."""
        from app.services.sms import send_sms
        from app.models import MarylandProvider
        
        try:
            stmt = select(MarylandProvider).where(
                MarylandProvider.provider_id == provider_id
            )
            result = await self.db.execute(stmt)
            provider = result.scalar_one_or_none()
            
            if not provider:
                return False
            
            send_sms(
                provider.phone_number,
                "💙 We noticed you've taken fewer shifts lately. "
                "Here's a VIP shift with +$5/hr bonus just for you. "
                "Reply BREAK if you need time off—we're here to support you."
            )
            
            logger.info(f"[BURNOUT] Sent intervention to provider {provider_id}")
            return True
            
        except Exception as e:
            logger.error(f"[BURNOUT] Error sending intervention: {e}")
            return False
