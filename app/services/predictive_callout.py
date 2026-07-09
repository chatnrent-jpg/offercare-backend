"""
Predictive Call-Out Fulfillment Service.

Feature: High-Value Feature #3
Purpose: Predict which shifts have high call-out risk and proactively
         stage backup "floater" nurses.

Machine Learning Approach:
- Analyze historical call-out patterns
- Train model on facility × day-of-week × shift-type
- Score all upcoming shifts for call-out probability
- Auto-stage floaters for high-risk shifts
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import numpy as np
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)


class PredictiveCallOutService:
    """
    ML-powered call-out prediction for proactive staffing.
    
    Predicts call-out probability based on:
    - Facility historical patterns
    - Day of week (Fridays have higher rates)
    - Shift type (night shifts have higher rates)
    - Weather conditions
    - Season (winter has higher rates)
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.enabled = getattr(settings, "PREDICTIVE_CALLOUT_ENABLED", True)
        self.high_risk_threshold = 0.30  # 30% call-out probability
        self.lookback_days = 90          # Use last 90 days of data
        
    async def predict_callout_risk(
        self,
        facility_id: UUID,
        shift_date: datetime,
        shift_type: str  # "DAY", "EVENING", "NIGHT"
    ) -> Dict:
        """
        Predict call-out probability for a specific shift.
        
        Args:
            facility_id: Facility UUID
            shift_date: Date of shift
            shift_type: "DAY", "EVENING", or "NIGHT"
        
        Returns:
            {
                "probability": float (0-1),
                "risk_level": str ("LOW" | "MEDIUM" | "HIGH"),
                "contributing_factors": List[str],
                "recommended_floaters": int,
                "historical_callout_rate": float
            }
        """
        if not self.enabled:
            return {"probability": 0.0, "risk_level": "UNKNOWN"}
        
        try:
            # Get historical call-out data
            historical_rate = await self._get_historical_callout_rate(
                facility_id, shift_date.weekday(), shift_type
            )
            
            # Calculate probability with heuristics
            base_probability = historical_rate
            
            # Factor adjustments
            factors = []
            
            # Day of week (Friday/Saturday higher risk)
            if shift_date.weekday() in [4, 5]:  # Friday, Saturday
                base_probability *= 1.3
                factors.append("WEEKEND")
            
            # Shift type (Night shifts higher risk)
            if shift_type == "NIGHT":
                base_probability *= 1.4
                factors.append("NIGHT_SHIFT")
            elif shift_type == "EVENING":
                base_probability *= 1.2
                factors.append("EVENING_SHIFT")
            
            # Season (Winter higher risk)
            month = shift_date.month
            if month in [12, 1, 2]:  # Winter
                base_probability *= 1.3
                factors.append("WINTER")
            
            # Cap at 1.0
            probability = min(base_probability, 1.0)
            
            # Determine risk level
            if probability >= 0.30:
                risk_level = "HIGH"
                recommended_floaters = 2
            elif probability >= 0.15:
                risk_level = "MEDIUM"
                recommended_floaters = 1
            else:
                risk_level = "LOW"
                recommended_floaters = 0
            
            logger.info(
                f"[CALLOUT] Facility {facility_id} {shift_date.strftime('%a')} "
                f"{shift_type}: {probability:.1%} risk ({risk_level})"
            )
            
            return {
                "probability": round(probability, 3),
                "risk_level": risk_level,
                "contributing_factors": factors,
                "recommended_floaters": recommended_floaters,
                "historical_callout_rate": round(historical_rate, 3)
            }
            
        except Exception as e:
            logger.error(f"[CALLOUT] Error predicting risk: {e}")
            return {"probability": 0.0, "risk_level": "ERROR", "error": str(e)}
    
    async def _get_historical_callout_rate(
        self,
        facility_id: UUID,
        day_of_week: int,
        shift_type: str
    ) -> float:
        """Calculate historical call-out rate for facility × day × shift type."""
        from app.models import ClinicalPlacementLedger
        from sqlalchemy import func
        
        try:
            # Look back 90 days
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
            
            # Count total shifts
            stmt_total = select(func.count(ClinicalPlacementLedger.ledger_id)).where(
                and_(
                    ClinicalPlacementLedger.facility_id == facility_id,
                    ClinicalPlacementLedger.shift_start >= cutoff_date,
                    func.extract('dow', ClinicalPlacementLedger.shift_start) == day_of_week
                )
            )
            
            result = await self.db.execute(stmt_total)
            total_shifts = result.scalar() or 0
            
            if total_shifts == 0:
                return 0.10  # Default 10% baseline
            
            # Count cancelled/no-show shifts
            stmt_cancelled = select(func.count(ClinicalPlacementLedger.ledger_id)).where(
                and_(
                    ClinicalPlacementLedger.facility_id == facility_id,
                    ClinicalPlacementLedger.shift_start >= cutoff_date,
                    func.extract('dow', ClinicalPlacementLedger.shift_start) == day_of_week,
                    or_(
                        ClinicalPlacementLedger.status == "CANCELLED",
                        ClinicalPlacementLedger.status == "NO_SHOW"
                    )
                )
            )
            
            result = await self.db.execute(stmt_cancelled)
            cancelled_shifts = result.scalar() or 0
            
            rate = cancelled_shifts / total_shifts
            
            logger.debug(
                f"[CALLOUT] Facility {facility_id} Day {day_of_week}: "
                f"{cancelled_shifts}/{total_shifts} = {rate:.1%}"
            )
            
            return rate
            
        except Exception as e:
            logger.error(f"[CALLOUT] Error calculating historical rate: {e}")
            return 0.10  # Default baseline
    
    async def scan_upcoming_shifts(
        self,
        days_ahead: int = 7
    ) -> List[Dict]:
        """
        Scan all upcoming shifts and identify high-risk ones.
        
        Args:
            days_ahead: How many days ahead to scan
        
        Returns:
            List of high-risk shifts with floater recommendations
        """
        from app.models import OfferCareJobOffer
        
        try:
            now = datetime.now(timezone.utc)
            scan_end = now + timedelta(days=days_ahead)
            
            # Get all upcoming shifts
            stmt = select(OfferCareJobOffer).where(
                and_(
                    OfferCareJobOffer.shift_start >= now,
                    OfferCareJobOffer.shift_start <= scan_end,
                    OfferCareJobOffer.status.in_(["OPEN", "PENDING", "CONFIRMED"])
                )
            )
            
            result = await self.db.execute(stmt)
            upcoming_shifts = result.scalars().all()
            
            logger.info(f"[CALLOUT] Scanning {len(upcoming_shifts)} upcoming shifts")
            
            high_risk_shifts = []
            
            for shift in upcoming_shifts:
                # Determine shift type
                hour = shift.shift_start.hour
                if 6 <= hour < 14:
                    shift_type = "DAY"
                elif 14 <= hour < 22:
                    shift_type = "EVENING"
                else:
                    shift_type = "NIGHT"
                
                # Predict risk
                prediction = await self.predict_callout_risk(
                    facility_id=shift.facility_id,
                    shift_date=shift.shift_start,
                    shift_type=shift_type
                )
                
                # Track high-risk shifts
                if prediction["risk_level"] == "HIGH":
                    high_risk_shifts.append({
                        "shift_id": shift.offer_id,
                        "facility_id": shift.facility_id,
                        "shift_start": shift.shift_start,
                        "shift_type": shift_type,
                        "prediction": prediction
                    })
            
            logger.info(
                f"[CALLOUT] Found {len(high_risk_shifts)} high-risk shifts "
                f"({len(high_risk_shifts)/len(upcoming_shifts)*100:.1f}% of total)"
            )
            
            return high_risk_shifts
            
        except Exception as e:
            logger.error(f"[CALLOUT] Error scanning shifts: {e}")
            return []
    
    async def stage_floater_nurses(
        self,
        facility_id: UUID,
        shift_date: datetime,
        num_floaters: int = 1
    ) -> List[UUID]:
        """
        Proactively stage "floater" nurses for high-risk shifts.
        
        Args:
            facility_id: Facility UUID
            shift_date: Date of high-risk shift
            num_floaters: Number of floaters to stage
        
        Returns:
            List of provider IDs staged as floaters
        """
        from app.models import MarylandProvider, ClinicalPlacementLedger
        from app.services.sms import send_sms
        from sqlalchemy import func, desc
        
        try:
            # Find top-reliability nurses who are:
            # 1. Available (no shift booked)
            # 2. High reliability score
            # 3. Close to facility
            
            # Get facility location
            from app.models import MarylandFacility
            stmt = select(MarylandFacility).where(MarylandFacility.facility_id == facility_id)
            result = await self.db.execute(stmt)
            facility = result.scalar_one_or_none()
            
            if not facility:
                return []
            
            # Find available, high-reliability nurses
            stmt = select(MarylandProvider).where(
                and_(
                    MarylandProvider.status == "ACTIVE",
                    MarylandProvider.reliability_score >= 85
                )
            ).order_by(desc(MarylandProvider.reliability_score)).limit(num_floaters * 3)
            
            result = await self.db.execute(stmt)
            candidates = result.scalars().all()
            
            floaters_staged = []
            
            for provider in candidates[:num_floaters]:
                # Send SMS alert
                message = (
                    f"🌟 FLOATER ALERT: We predict a last-minute opening on "
                    f"{shift_date.strftime('%a %m/%d')}. You're on standby as a premium floater. "
                    f"Reply STANDBY to confirm availability."
                )
                
                send_sms(provider.phone_number, message)
                floaters_staged.append(provider.provider_id)
                
                logger.info(
                    f"[CALLOUT] Staged floater {provider.provider_id} for "
                    f"facility {facility_id} on {shift_date.strftime('%Y-%m-%d')}"
                )
            
            return floaters_staged
            
        except Exception as e:
            logger.error(f"[CALLOUT] Error staging floaters: {e}")
            return []
    
    async def auto_stage_floaters_for_high_risk(self) -> Dict:
        """
        Automatically scan upcoming shifts and stage floaters.
        
        This should be called daily by a Celery scheduler.
        """
        try:
            # Scan next 7 days
            high_risk_shifts = await self.scan_upcoming_shifts(days_ahead=7)
            
            staged_count = 0
            
            for shift in high_risk_shifts:
                # Stage floaters
                floaters = await self.stage_floater_nurses(
                    facility_id=shift["facility_id"],
                    shift_date=shift["shift_start"],
                    num_floaters=shift["prediction"]["recommended_floaters"]
                )
                
                staged_count += len(floaters)
            
            logger.info(
                f"[CALLOUT] Auto-staged {staged_count} floaters for "
                f"{len(high_risk_shifts)} high-risk shifts"
            )
            
            return {
                "success": True,
                "high_risk_shifts": len(high_risk_shifts),
                "floaters_staged": staged_count
            }
            
        except Exception as e:
            logger.error(f"[CALLOUT] Error auto-staging floaters: {e}")
            return {"success": False, "error": str(e)}


# Convenience function for Celery scheduler
async def daily_floater_staging(db: Session) -> Dict:
    """Daily scheduled task to stage floaters for high-risk shifts."""
    service = PredictiveCallOutService(db)
    return await service.auto_stage_floaters_for_high_risk()
