"""
Dynamic Pricing Engine — Auto-Negotiation + Surge Pricing

Sprint: VCAI-TIER2-SPRINT-2026-07-07
Purpose: Intelligent rate optimization for maximum shift fill rates.

Features:
- Auto-Negotiation: Gradually increase rates for urgent unfilled shifts
- Surge Pricing: Market-wide rate multipliers during high demand
- Budget Enforcement: Never exceed facility max rates
- Audit Trail: Complete negotiation history

Auto-Negotiation Flow:
1. Shift unfilled 6 hours before start → +10% rate bump
2. Still unfilled after Wave 2 → +20% rate bump
3. Still unfilled after Wave 3 → +30% rate bump (up to max)

Surge Pricing Triggers:
- Weather: Blizzard, hurricane → 1.5x surge
- Holiday: Christmas, Thanksgiving → 1.3x surge
- High Demand: 20+ unfilled shifts in region → 1.2x-2.5x surge
- Outbreak: Flu, COVID → 1.8x surge
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import (
    FacilityRateConfig,
    RateNegotiationHistory,
    SurgePricingEvent,
)


@dataclass
class NegotiationResult:
    """Result of rate negotiation."""
    negotiated: bool
    original_rate: float
    new_rate: float
    increase_pct: float
    negotiation_id: Optional[UUID] = None


@dataclass
class SurgeStatus:
    """Current surge pricing status."""
    surge_active: bool
    surge_multiplier: float
    surge_reason: str
    event_id: Optional[UUID] = None


class DynamicPricingEngine:
    """
    Intelligent pricing engine for auto-negotiation and surge pricing.
    
    Main entry points:
    - negotiate_rate(shift_id, facility_id, credential_type)
    - get_surge_multiplier(region, credential_type)
    - trigger_surge_event(event_type, multiplier, reason)
    """
    
    def __init__(self, db: Optional[AsyncSession] = None):
        """Initialize with optional database session."""
        self.db = db
        self._should_close_db = db is None
    
    async def __aenter__(self):
        """Async context manager entry."""
        if self.db is None:
            self.db = AsyncSessionLocal()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._should_close_db and self.db:
            await self.db.close()
    
    async def negotiate_rate(
        self,
        shift_id: UUID,
        facility_id: UUID,
        credential_type: str,
        current_rate: float,
        time_until_shift_minutes: int,
        negotiation_trigger: str = "URGENCY"
    ) -> NegotiationResult:
        """
        Negotiate rate increase for unfilled shift.
        
        Args:
            shift_id: Shift UUID
            facility_id: Facility UUID
            credential_type: CNA, GNA, LPN, RN
            current_rate: Current hourly rate
            time_until_shift_minutes: Minutes until shift starts
            negotiation_trigger: URGENCY, WAVE_FAILURE, MANUAL
        
        Returns:
            NegotiationResult with new rate and increase %
        """
        if not settings.AUTO_NEGOTIATION_ENABLED:
            return NegotiationResult(
                negotiated=False,
                original_rate=current_rate,
                new_rate=current_rate,
                increase_pct=0.0
            )
        
        # Get facility rate config
        rate_config = await self._get_facility_rate_config(facility_id)
        
        if rate_config.auto_negotiate_enabled != "1":
            return NegotiationResult(
                negotiated=False,
                original_rate=current_rate,
                new_rate=current_rate,
                increase_pct=0.0
            )
        
        # Calculate urgency score (0-100)
        urgency_score = self._calculate_urgency_score(time_until_shift_minutes)
        
        # Calculate rate increase percentage based on urgency
        increase_pct = self._calculate_rate_increase(urgency_score)
        
        # Calculate new rate
        new_rate = current_rate * (1 + increase_pct / 100)
        
        # Enforce max rate cap
        max_rate = self._get_max_rate(rate_config, credential_type)
        if new_rate > max_rate:
            new_rate = max_rate
            increase_pct = ((new_rate - current_rate) / current_rate) * 100
        
        # Only negotiate if increase is meaningful
        if increase_pct < 5.0:
            return NegotiationResult(
                negotiated=False,
                original_rate=current_rate,
                new_rate=current_rate,
                increase_pct=0.0
            )
        
        # Log negotiation
        negotiation_record = await self._log_negotiation(
            shift_id=shift_id,
            facility_id=facility_id,
            original_rate=current_rate,
            negotiated_rate=new_rate,
            increase_pct=increase_pct,
            urgency_score=urgency_score,
            time_until_shift_minutes=time_until_shift_minutes,
            negotiation_trigger=negotiation_trigger
        )
        
        print(f"[PRICING] Negotiated rate for shift {shift_id}: ${current_rate:.2f} → ${new_rate:.2f} (+{increase_pct:.1f}%)")
        
        return NegotiationResult(
            negotiated=True,
            original_rate=current_rate,
            new_rate=new_rate,
            increase_pct=increase_pct,
            negotiation_id=negotiation_record.id
        )
    
    def _calculate_urgency_score(self, time_until_shift_minutes: int) -> float:
        """
        Calculate urgency score (0-100) based on time until shift.
        
        Urgency increases as shift approaches:
        - 6+ hours away: 20
        - 4-6 hours: 40
        - 2-4 hours: 60
        - 1-2 hours: 80
        - <1 hour: 100
        """
        if time_until_shift_minutes >= 360:  # 6+ hours
            return 20.0
        elif time_until_shift_minutes >= 240:  # 4-6 hours
            return 40.0
        elif time_until_shift_minutes >= 120:  # 2-4 hours
            return 60.0
        elif time_until_shift_minutes >= 60:  # 1-2 hours
            return 80.0
        else:  # <1 hour
            return 100.0
    
    def _calculate_rate_increase(self, urgency_score: float) -> float:
        """
        Calculate rate increase percentage based on urgency.
        
        Formula: increase_pct = (urgency_score / 100) * max_increase
        
        Examples:
        - Urgency 20 → 12% increase
        - Urgency 40 → 24% increase
        - Urgency 60 → 36% increase
        - Urgency 80 → 48% increase
        - Urgency 100 → 60% increase (max)
        """
        max_increase = settings.AUTO_NEGOTIATION_MAX_INCREASE_PCT
        return (urgency_score / 100) * max_increase
    
    def _get_max_rate(self, rate_config: FacilityRateConfig, credential_type: str) -> float:
        """Get max hourly rate for credential type."""
        max_rates = {
            "CNA": float(rate_config.max_hourly_rate_cna),
            "GNA": float(rate_config.max_hourly_rate_gna),
            "LPN": float(rate_config.max_hourly_rate_lpn),
            "RN": float(rate_config.max_hourly_rate_rn)
        }
        return max_rates.get(credential_type, 100.0)
    
    async def _get_facility_rate_config(self, facility_id: UUID) -> FacilityRateConfig:
        """Get or create facility rate config."""
        stmt = select(FacilityRateConfig).where(FacilityRateConfig.facility_id == facility_id)
        result = await self.db.execute(stmt)
        config = result.scalar_one_or_none()
        
        if not config:
            # Create default config
            config = FacilityRateConfig(facility_id=facility_id)
            self.db.add(config)
            await self.db.commit()
            await self.db.refresh(config)
        
        return config
    
    async def _log_negotiation(
        self,
        shift_id: UUID,
        facility_id: UUID,
        original_rate: float,
        negotiated_rate: float,
        increase_pct: float,
        urgency_score: float,
        time_until_shift_minutes: int,
        negotiation_trigger: str
    ) -> RateNegotiationHistory:
        """Log rate negotiation to history."""
        record = RateNegotiationHistory(
            shift_id=shift_id,
            facility_id=facility_id,
            original_rate=Decimal(str(original_rate)),
            negotiated_rate=Decimal(str(negotiated_rate)),
            rate_increase_pct=Decimal(str(increase_pct)),
            urgency_score=Decimal(str(urgency_score)),
            time_until_shift_minutes=str(time_until_shift_minutes),
            negotiation_trigger=negotiation_trigger
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record
    
    # ═══════════════════════════════════════════════════════════════
    # SURGE PRICING
    # ═══════════════════════════════════════════════════════════════
    
    async def get_surge_multiplier(
        self,
        region: Optional[str] = None,
        credential_type: Optional[str] = None
    ) -> SurgeStatus:
        """
        Get current surge multiplier for region and credential type.
        
        Returns active surge event or 1.0x (no surge).
        """
        if not settings.SURGE_PRICING_ENABLED:
            return SurgeStatus(
                surge_active=False,
                surge_multiplier=1.0,
                surge_reason="Surge pricing disabled"
            )
        
        # Find active surge events
        stmt = select(SurgePricingEvent).where(
            and_(
                SurgePricingEvent.started_at <= datetime.utcnow(),
                SurgePricingEvent.ended_at.is_(None)
            )
        ).order_by(SurgePricingEvent.surge_multiplier.desc())
        
        result = await self.db.execute(stmt)
        active_surges = list(result.scalars().all())
        
        if not active_surges:
            return SurgeStatus(
                surge_active=False,
                surge_multiplier=1.0,
                surge_reason="No active surge"
            )
        
        # Return highest multiplier
        top_surge = active_surges[0]
        return SurgeStatus(
            surge_active=True,
            surge_multiplier=float(top_surge.surge_multiplier),
            surge_reason=top_surge.trigger_reason or top_surge.event_type,
            event_id=top_surge.id
        )
    
    async def trigger_surge_event(
        self,
        event_type: str,
        surge_multiplier: float,
        trigger_reason: str,
        affected_regions: Optional[List[str]] = None,
        affected_credential_types: Optional[List[str]] = None,
        unfilled_shifts_count: Optional[int] = None
    ) -> UUID:
        """
        Trigger a surge pricing event.
        
        Args:
            event_type: WEATHER, HOLIDAY, HIGH_DEMAND, OUTBREAK
            surge_multiplier: 1.2x to 2.5x
            trigger_reason: Human-readable reason
            affected_regions: List of affected zip codes or regions
            affected_credential_types: List of affected types (CNA, GNA, etc.)
            unfilled_shifts_count: Number of unfilled shifts triggering surge
        
        Returns:
            Surge event ID
        """
        # Enforce max multiplier
        if surge_multiplier > settings.SURGE_PRICING_MAX_MULTIPLIER:
            surge_multiplier = settings.SURGE_PRICING_MAX_MULTIPLIER
        
        surge_event = SurgePricingEvent(
            event_type=event_type,
            surge_multiplier=Decimal(str(surge_multiplier)),
            trigger_reason=trigger_reason,
            affected_regions=json.dumps(affected_regions) if affected_regions else None,
            affected_credential_types=json.dumps(affected_credential_types) if affected_credential_types else None,
            unfilled_shifts_count=str(unfilled_shifts_count) if unfilled_shifts_count else None
        )
        self.db.add(surge_event)
        await self.db.commit()
        await self.db.refresh(surge_event)
        
        print(f"[PRICING] Surge event triggered: {event_type} - {surge_multiplier}x - {trigger_reason}")
        
        return surge_event.id
    
    async def end_surge_event(self, surge_event_id: UUID):
        """End an active surge event."""
        stmt = select(SurgePricingEvent).where(SurgePricingEvent.id == surge_event_id)
        result = await self.db.execute(stmt)
        surge_event = result.scalar_one_or_none()
        
        if surge_event:
            surge_event.ended_at = datetime.utcnow()
            await self.db.commit()
            print(f"[PRICING] Surge event ended: {surge_event.event_type}")


# Convenience functions
async def auto_negotiate_shift_rate(
    shift_id: UUID,
    facility_id: UUID,
    credential_type: str,
    current_rate: float,
    time_until_shift_minutes: int
) -> NegotiationResult:
    """Auto-negotiate shift rate (convenience wrapper)."""
    async with DynamicPricingEngine() as engine:
        return await engine.negotiate_rate(
            shift_id, facility_id, credential_type,
            current_rate, time_until_shift_minutes
        )


async def get_current_surge_multiplier(region: Optional[str] = None) -> float:
    """Get current surge multiplier (convenience wrapper)."""
    async with DynamicPricingEngine() as engine:
        status = await engine.get_surge_multiplier(region)
        return status.surge_multiplier
