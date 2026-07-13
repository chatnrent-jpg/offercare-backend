"""
Wave Match Dispatcher — Autonomous SMS Wave Matching

Sprint: VCAI-TIER1-SPRINT-2026-07-07
Purpose: Dynamic multi-wave SMS dispatch to maximize shift fill rates.

Strategy:
- Wave 1 (0-5min): Top 5 nurses (highest reliability + closest proximity)
- Wave 2 (5-10min): Next 10 nurses (good reliability + reasonable proximity)
- Wave 3 (10-20min): Expanded pool (all qualified, willing to travel)
- Wave 4 (20+min): Premium rate increase + re-ping Wave 1 & 2 with bonus

Real-time YES/NO response processing with instant shift locking.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional
from uuid import UUID

from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import (
    WaveDispatchConfig,
    WaveDispatchRun,
    ProviderReliabilityScore,
    NurseSmsDispatchLog,
    MarylandProvider,
    MarylandFacility,
    OfferCareJobOffer,
)


@dataclass
class WaveConfig:
    """Configuration for a single wave."""
    wave_number: int
    size: int
    delay_seconds: int


@dataclass
class NurseCandidate:
    """Nurse candidate with priority score."""
    provider: MarylandProvider
    priority_score: float
    distance_miles: float
    reliability_score: float


class WaveMatchDispatcher:
    """
    Autonomous SMS wave dispatcher for shift matching.
    
    Main entry point: start_autonomous_waves(shift_ids)
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
    
    async def start_autonomous_waves(self, shift_ids: List[str]):
        """
        Start wave dispatching for one or more shifts.
        
        This runs as a background task and manages the entire wave lifecycle.
        
        Args:
            shift_ids: List of shift IDs (as strings) to dispatch
        """
        if not settings.WAVE_DISPATCH_ENABLED:
            print("[WAVE DISPATCH] Feature disabled")
            return
        
        for shift_id_str in shift_ids:
            try:
                shift_id = UUID(shift_id_str) if isinstance(shift_id_str, str) else shift_id_str
                
                # Create wave run record
                wave_run = await self._create_wave_run(shift_id)
                
                # Launch background wave processor
                asyncio.create_task(self._execute_wave_sequence(wave_run))
                
            except Exception as e:
                print(f"[WAVE DISPATCH ERROR] Failed to start waves for shift {shift_id_str}: {e}")
    
    async def _create_wave_run(self, shift_id: UUID) -> WaveDispatchRun:
        """Create new wave run record."""
        wave_run = WaveDispatchRun(
            shift_id=shift_id,
            current_wave="1",
            total_dispatched="0",
            total_accepted="0",
            total_declined="0",
            run_state="ACTIVE"
        )
        self.db.add(wave_run)
        await self.db.commit()
        await self.db.refresh(wave_run)
        return wave_run
    
    async def _execute_wave_sequence(self, wave_run: WaveDispatchRun):
        """
        Execute the full wave sequence until shift is filled or timeout.
        
        Runs asynchronously in background.
        """
        try:
            # Get shift and facility
            shift = await self._get_shift(wave_run.shift_id)
            if not shift:
                await self._complete_wave_run(wave_run, "SHIFT_NOT_FOUND")
                return
            
            # Get facility config
            config = await self._get_wave_config(shift.facility_id)
            
            print(f"[WAVE DISPATCH] Starting waves for shift {wave_run.shift_id}")
            
            # Wave 1
            wave_1_nurses = await self._get_wave_candidates(shift, wave=1, size=int(config.wave_1_size))
            await self._dispatch_wave(wave_run, wave_1_nurses, wave_number=1)
            await asyncio.sleep(int(config.wave_1_delay_seconds))
            
            if await self._is_shift_filled(shift):
                return await self._complete_wave_run(wave_run, "FILLED_WAVE_1")
            
            # Wave 2
            wave_run.current_wave = "2"
            await self.db.commit()
            wave_2_nurses = await self._get_wave_candidates(shift, wave=2, size=int(config.wave_2_size))
            await self._dispatch_wave(wave_run, wave_2_nurses, wave_number=2)
            await asyncio.sleep(int(config.wave_2_delay_seconds))
            
            if await self._is_shift_filled(shift):
                return await self._complete_wave_run(wave_run, "FILLED_WAVE_2")
            
            # Wave 3
            wave_run.current_wave = "3"
            await self.db.commit()
            wave_3_nurses = await self._get_wave_candidates(shift, wave=3, size=int(config.wave_3_size))
            await self._dispatch_wave(wave_run, wave_3_nurses, wave_number=3)
            await asyncio.sleep(int(config.wave_3_delay_seconds))
            
            if await self._is_shift_filled(shift):
                return await self._complete_wave_run(wave_run, "FILLED_WAVE_3")
            
            # Wave 4 (bonus round)
            if config.wave_4_bonus_enabled:
                wave_run.current_wave = "4"
                await self.db.commit()
                await self._dispatch_bonus_wave(
                    wave_run,
                    wave_1_nurses + wave_2_nurses,
                    float(config.wave_4_bonus_amount_per_hour)
                )
                await asyncio.sleep(600)  # 10 minutes for bonus wave
                
                if await self._is_shift_filled(shift):
                    return await self._complete_wave_run(wave_run, "FILLED_WAVE_4_BONUS")
            
            # Timeout - no fill
            await self._complete_wave_run(wave_run, "TIMEOUT_NO_FILL")
            
        except Exception as e:
            print(f"[WAVE DISPATCH ERROR] Wave sequence failed: {e}")
            await self._complete_wave_run(wave_run, f"ERROR: {str(e)[:50]}")
    
    async def _get_shift(self, shift_id: UUID) -> Optional[OfferCareJobOffer]:
        """Get shift by ID."""
        stmt = select(OfferCareJobOffer).where(OfferCareJobOffer.offer_id == shift_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def _get_wave_config(self, facility_id: UUID) -> WaveDispatchConfig:
        """Get wave config for facility (or default)."""
        stmt = select(WaveDispatchConfig).where(WaveDispatchConfig.facility_id == facility_id)
        result = await self.db.execute(stmt)
        config = result.scalar_one_or_none()
        
        if config:
            return config
        
        # Return default config
        return WaveDispatchConfig(
            facility_id=facility_id,
            wave_1_size=str(settings.WAVE_DISPATCH_DEFAULT_WAVE_1_SIZE),
            wave_1_delay_seconds="300",
            wave_2_size=str(settings.WAVE_DISPATCH_DEFAULT_WAVE_2_SIZE),
            wave_2_delay_seconds="300",
            wave_3_size=str(settings.WAVE_DISPATCH_DEFAULT_WAVE_3_SIZE),
            wave_3_delay_seconds="600",
            wave_4_bonus_enabled=settings.WAVE_DISPATCH_BONUS_ENABLED,
            wave_4_bonus_amount_per_hour=Decimal(str(settings.WAVE_DISPATCH_BONUS_AMOUNT))
        )
    
    async def _get_wave_candidates(
        self,
        shift: OfferCareJobOffer,
        wave: int,
        size: int
    ) -> List[NurseCandidate]:
        """
        Get qualified nurses for this wave using priority scoring.
        
        Priority Score Formula:
        - Reliability Score: 40%
        - Proximity: 30%
        - Recent Activity: 20%
        - Historical Facility Rating: 10%
        """
        # Get facility for distance calculation
        facility_stmt = select(MarylandFacility).where(
            MarylandFacility.facility_id == shift.facility_id
        )
        facility_result = await self.db.execute(facility_stmt)
        facility = facility_result.scalar_one_or_none()
        
        if not facility:
            return []
        
        # Get all qualified providers
        providers_stmt = select(MarylandProvider).where(
            and_(
                MarylandProvider.credential_type == shift.shift_role.split("_")[0],  # Extract CNA/GNA/LPN
                MarylandProvider.dispatch_status == "ACTIVE",
                MarylandProvider.sms_opt_out == "false",
                or_(
                    MarylandProvider.latitude.isnot(None),
                    MarylandProvider.longitude.isnot(None)
                )
            )
        )
        providers_result = await self.db.execute(providers_stmt)
        providers = providers_result.scalars().all()
        
        # Score each candidate
        candidates = []
        for provider in providers:
            # Skip if already dispatched in this run
            if await self._already_dispatched(shift.offer_id, provider.provider_id):
                continue
            
            score = await self._calculate_priority_score(provider, facility, shift)
            distance = self._calculate_distance(
                provider.latitude,
                provider.longitude,
                facility.latitude,
                facility.longitude
            )
            reliability = await self._get_reliability_score(provider.provider_id)
            
            candidates.append(NurseCandidate(
                provider=provider,
                priority_score=score,
                distance_miles=distance,
                reliability_score=reliability
            ))
        
        # Sort by priority score (highest first)
        candidates.sort(key=lambda c: c.priority_score, reverse=True)
        
        # Return top N for this wave
        return candidates[:size]
    
    async def _calculate_priority_score(
        self,
        provider: MarylandProvider,
        facility: MarylandFacility,
        shift: OfferCareJobOffer
    ) -> float:
        """
        Calculate priority score (0-100).
        
        Factors:
        - Reliability Score: 40%
        - Proximity: 30%
        - Recent Activity: 20%
        - Historical Facility Rating: 10%
        """
        # Reliability score (0-100)
        reliability = await self._get_reliability_score(provider.provider_id)
        
        # Distance score (closer = higher, max 50 miles for full points)
        distance = self._calculate_distance(
            provider.latitude,
            provider.longitude,
            facility.latitude,
            facility.longitude
        )
        proximity_score = max(0, 100 - (distance / 50.0 * 100))
        
        # Recent activity score (shifts in last 7 days)
        recent_shifts = await self._count_recent_shifts(provider.provider_id, days=7)
        activity_score = min(100, recent_shifts * 20)  # Cap at 100
        
        # Historical facility rating from past placements
        from sqlalchemy import select, func
        from app.models import ClinicalPlacementLedger, OfferCareJobOffer
        
        facility_rating = 3.0  # Default
        try:
            stmt = (
                select(func.avg(ClinicalPlacementLedger.provider_rating))
                .join(OfferCareJobOffer, ClinicalPlacementLedger.offer_id == OfferCareJobOffer.offer_id)
                .where(
                    OfferCareJobOffer.facility_id == shift.facility_id,
                    ClinicalPlacementLedger.provider_rating.isnot(None)
                )
            )
            result = await self.db.execute(stmt)
            avg_rating = result.scalar()
            if avg_rating:
                facility_rating = float(avg_rating)
        except Exception as e:
            print(f"[WAVE] Failed to get facility rating: {e}")
        
        facility_score = (facility_rating / 5.0) * 100
        
        # Weighted sum
        total_score = (
            reliability * 0.40 +
            proximity_score * 0.30 +
            activity_score * 0.20 +
            facility_score * 0.10
        )
        
        return total_score
    
    def _calculate_distance(
        self,
        lat1: Optional[Decimal],
        lon1: Optional[Decimal],
        lat2: Optional[Decimal],
        lon2: Optional[Decimal]
    ) -> float:
        """Calculate haversine distance in miles."""
        if not all([lat1, lon1, lat2, lon2]):
            return 999.0  # Default to far away if coords missing
        
        from math import radians, sin, cos, sqrt, atan2
        
        # Convert to float
        lat1_f, lon1_f = float(lat1), float(lon1)
        lat2_f, lon2_f = float(lat2), float(lon2)
        
        # Haversine formula
        R = 3959  # Earth radius in miles
        dlat = radians(lat2_f - lat1_f)
        dlon = radians(lon2_f - lon1_f)
        a = sin(dlat/2)**2 + cos(radians(lat1_f)) * cos(radians(lat2_f)) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c
        
        return distance
    
    async def _get_reliability_score(self, provider_id: UUID) -> float:
        """Get provider reliability score (0-100)."""
        stmt = select(ProviderReliabilityScore).where(
            ProviderReliabilityScore.provider_id == provider_id
        )
        result = await self.db.execute(stmt)
        score_record = result.scalar_one_or_none()
        
        if score_record:
            return float(score_record.reliability_score)
        
        # Default score for new providers
        return 50.0
    
    async def _count_recent_shifts(self, provider_id: UUID, days: int) -> int:
        """Count shifts completed in last N days."""
        from app.models import ClinicalPlacementLedger
        from sqlalchemy import select, func
        from datetime import datetime, timedelta, timezone
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        try:
            stmt = select(func.count(ClinicalPlacementLedger.placement_id)).where(
                ClinicalPlacementLedger.provider_id == provider_id,
                ClinicalPlacementLedger.outbound_payload_timestamp >= cutoff_date
            )
            result = await self.db.execute(stmt)
            return result.scalar() or 0
        except Exception as e:
            print(f"[WAVE] Failed to count recent shifts: {e}")
            return 0
    
    async def _already_dispatched(self, shift_id: UUID, provider_id: UUID) -> bool:
        """Check if provider was already dispatched for this shift."""
        stmt = select(NurseSmsDispatchLog).where(
            and_(
                NurseSmsDispatchLog.shift_id == shift_id,
                NurseSmsDispatchLog.provider_id == provider_id
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None
    
    async def _dispatch_wave(
        self,
        wave_run: WaveDispatchRun,
        nurses: List[NurseCandidate],
        wave_number: int
    ):
        """
        Send SMS to all nurses in this wave.
        """
        shift = await self._get_shift(wave_run.shift_id)
        if not shift:
            return
        
        for i, candidate in enumerate(nurses):
            message = await self._build_shift_offer_sms(shift, candidate, wave_number)
            
            # Send via Twilio
            message_sid = await self._send_sms(
                to_phone=candidate.provider.phone_number,
                message=message
            )
            
            # Log dispatch
            dispatch_log = NurseSmsDispatchLog(
                shift_id=shift.offer_id,
                provider_id=candidate.provider.provider_id,
                wave_number=str(wave_number),
                dispatch_priority=str(i + 1),
                message_body=message,
                twilio_message_sid=message_sid
            )
            self.db.add(dispatch_log)
            
            wave_run.total_dispatched = str(int(wave_run.total_dispatched) + 1)
        
        await self.db.commit()
        print(f"[WAVE DISPATCH] Wave {wave_number}: Dispatched to {len(nurses)} nurses")
    
    async def _build_shift_offer_sms(
        self,
        shift: OfferCareJobOffer,
        candidate: NurseCandidate,
        wave_number: int
    ) -> str:
        """Build personalized shift offer message."""
        # Get facility name from database
        from app.models import MarylandFacility
        from sqlalchemy import select
        
        facility_name = "Healthcare Facility"  # Default
        try:
            stmt = select(MarylandFacility).where(MarylandFacility.facility_id == shift.facility_id)
            result = await self.db.execute(stmt)
            facility = result.scalar_one_or_none()
            if facility:
                facility_name = facility.name
        except Exception as e:
            print(f"[WAVE] Failed to get facility name: {e}")
        
        # Format shift times
        start_time = shift.shift_starts_at.strftime("%I:%M %p") if shift.shift_starts_at else "TBD"
        end_time = shift.shift_ends_at.strftime("%I:%M %p") if shift.shift_ends_at else "TBD"
        date_str = shift.shift_starts_at.strftime("%a, %b %d") if shift.shift_starts_at else "TBD"
        
        return f"""Hi! 👋

{facility_name} needs a {shift.shift_role} for:
📅 {date_str}
⏰ {start_time} - {end_time}
💰 ${float(shift.hourly_pay_rate):.2f}/hr
📍 {candidate.distance_miles:.1f} mi away

Reply YES to accept or NO to decline.
"""
    
    async def _dispatch_bonus_wave(
        self,
        wave_run: WaveDispatchRun,
        previous_nurses: List[NurseCandidate],
        bonus_per_hour: float
    ):
        """
        Wave 4: Re-ping Wave 1 & 2 nurses with premium bonus.
        """
        shift = await self._get_shift(wave_run.shift_id)
        if not shift:
            return
        
        for i, candidate in enumerate(previous_nurses):
            # Build bonus message
            original_rate = float(shift.hourly_pay_rate)
            bonus_rate = original_rate + bonus_per_hour
            
            message = f"""🌟 PREMIUM BONUS OFFER 🌟

This shift is still open with a BONUS!

💰 ${bonus_rate:.2f}/hr (${bonus_per_hour:.2f} bonus!)
📅 {shift.shift_starts_at.strftime("%a, %b %d") if shift.shift_starts_at else "TBD"}
⏰ {shift.shift_starts_at.strftime("%I:%M %p") if shift.shift_starts_at else "TBD"}

Reply YES to accept this premium rate!
"""
            
            message_sid = await self._send_sms(
                to_phone=candidate.provider.phone_number,
                message=message
            )
            
            dispatch_log = NurseSmsDispatchLog(
                shift_id=shift.offer_id,
                provider_id=candidate.provider.provider_id,
                wave_number="4",
                dispatch_priority=str(i + 1),
                message_body=message,
                twilio_message_sid=message_sid
            )
            self.db.add(dispatch_log)
            
            wave_run.total_dispatched = str(int(wave_run.total_dispatched) + 1)
        
        await self.db.commit()
        print(f"[WAVE DISPATCH] Wave 4 (Bonus): Dispatched to {len(previous_nurses)} nurses")
    
    async def _send_sms(self, to_phone: str, message: str) -> Optional[str]:
        """Send SMS via Twilio."""
        if settings.SMS_DRY_RUN or settings.WAVE_DISPATCH_DRY_RUN:
            print(f"[DRY RUN] SMS to {to_phone}: {message[:50]}...")
            return None
        
        try:
            from twilio.rest import Client
            
            client = Client(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN
            )
            
            msg = client.messages.create(
                body=message,
                from_=settings.TWILIO_FROM_NUMBER,
                to=to_phone
            )
            
            return msg.sid
            
        except Exception as e:
            print(f"[ERROR] Failed to send SMS: {e}")
            return None
    
    async def _is_shift_filled(self, shift: OfferCareJobOffer) -> bool:
        """Check if shift is filled."""
        # Refresh shift from database
        await self.db.refresh(shift)
        return shift.compliance_lock_status in ["LOCKED", "FILLED"]
    
    async def _complete_wave_run(self, wave_run: WaveDispatchRun, reason: str):
        """Complete wave run with reason."""
        wave_run.run_state = "COMPLETED"
        wave_run.completed_at = datetime.utcnow()
        wave_run.completion_reason = reason
        await self.db.commit()
        print(f"[WAVE DISPATCH] Completed: {reason}")
    
    async def process_nurse_response(
        self,
        provider_phone: str,
        message_body: str
    ) -> Dict:
        """
        Process nurse's SMS response to a shift offer.
        
        Handles: YES, NO, MAYBE, questions, etc.
        """
        # Find the provider
        provider_stmt = select(MarylandProvider).where(
            MarylandProvider.phone_number == provider_phone
        )
        provider_result = await self.db.execute(provider_stmt)
        provider = provider_result.scalar_one_or_none()
        
        if not provider:
            return {"status": "unknown_provider"}
        
        # Find most recent pending dispatch for this provider
        dispatch_stmt = select(NurseSmsDispatchLog).where(
            and_(
                NurseSmsDispatchLog.provider_id == provider.provider_id,
                NurseSmsDispatchLog.response_intent.is_(None)
            )
        ).order_by(desc(NurseSmsDispatchLog.dispatched_at)).limit(1)
        
        dispatch_result = await self.db.execute(dispatch_stmt)
        recent_dispatch = dispatch_result.scalar_one_or_none()
        
        if not recent_dispatch:
            await self._send_sms(
                to_phone=provider_phone,
                message="Sorry, I don't have any active shift offers for you right now."
            )
            return {"status": "no_active_offer"}
        
        # Parse response intent
        message_lower = message_body.lower().strip()
        
        if any(word in message_lower for word in ["yes", "accept", "take it", "i'm in", "sounds good", "ok", "okay"]):
            return await self._handle_nurse_acceptance(recent_dispatch, provider)
        
        elif any(word in message_lower for word in ["no", "decline", "can't", "cannot", "pass", "not interested"]):
            return await self._handle_nurse_decline(recent_dispatch, provider)
        
        else:
            # Unclear response - ask for clarification
            await self._send_sms(
                to_phone=provider_phone,
                message="Just to confirm - are you saying YES to accept the shift, or NO to decline?"
            )
            return {"status": "clarification_needed"}
    
    async def _handle_nurse_acceptance(
        self,
        dispatch_log: NurseSmsDispatchLog,
        provider: MarylandProvider
    ) -> Dict:
        """Handle nurse accepting the shift."""
        shift = await self._get_shift(dispatch_log.shift_id)
        
        if not shift:
            return {"status": "shift_not_found"}
        
        # Check if shift is still available
        if shift.compliance_lock_status != "BROADCASTING":
            await self._send_sms(
                to_phone=provider.phone_number,
                message="Sorry, this shift was just filled by another nurse. I'll reach out about the next one!"
            )
            dispatch_log.response_intent = "ACCEPT_TOO_LATE"
            dispatch_log.responded_at = datetime.utcnow()
            await self.db.commit()
            return {"status": "shift_already_filled"}
        
        # Lock the shift
        shift.compliance_lock_status = "LOCKED"
        shift.assigned_provider_id = provider.provider_id
        
        # Update dispatch log
        dispatch_log.response_intent = "ACCEPT"
        dispatch_log.responded_at = datetime.utcnow()
        dispatch_log.response_message = "Accepted via SMS"
        
        # Update wave run stats
        wave_run_stmt = select(WaveDispatchRun).where(
            WaveDispatchRun.shift_id == dispatch_log.shift_id
        )
        wave_run_result = await self.db.execute(wave_run_stmt)
        wave_run = wave_run_result.scalar_one_or_none()
        
        if wave_run and wave_run.run_state == "ACTIVE":
            wave_run.total_accepted = str(int(wave_run.total_accepted) + 1)
            await self._complete_wave_run(wave_run, "FILLED_BY_NURSE_ACCEPTANCE")
        
        await self.db.commit()
        
        # Send confirmation
        await self._send_sms(
            to_phone=provider.phone_number,
            message="🎉 You got it! Shift confirmed. Check your portal for details and directions. See you there!"
        )
        
        # Notify facility of match
        from app.models import MarylandFacility
        from sqlalchemy import select
        
        try:
            stmt = select(MarylandFacility).where(MarylandFacility.facility_id == shift.facility_id)
            result = await self.db.execute(stmt)
            facility = result.scalar_one_or_none()
            
            if facility:
                notification_msg = f"Shift filled! {provider.first_name} {provider.last_name} ({provider.credential_type}) confirmed for {shift.shift_starts_at.strftime('%I:%M %p')} shift."
                
                if not settings.SMS_DRY_RUN:
                    from app.services.sms import send_sms
                    # Facility contact number would need to be added to facility model
                    print(f"[WAVE] Would send SMS to facility: {notification_msg}")
                else:
                    print(f"[WAVE] DRY RUN: {notification_msg}")
        except Exception as e:
            print(f"[WAVE] Failed to notify facility: {e}")
        
        return {"status": "accepted", "shift_id": str(shift.offer_id)}
    
    async def _handle_nurse_decline(
        self,
        dispatch_log: NurseSmsDispatchLog,
        provider: MarylandProvider
    ) -> Dict:
        """Handle nurse declining the shift."""
        dispatch_log.response_intent = "DECLINE"
        dispatch_log.responded_at = datetime.utcnow()
        dispatch_log.response_message = "Declined via SMS"
        
        # Update wave run stats
        wave_run_stmt = select(WaveDispatchRun).where(
            WaveDispatchRun.shift_id == dispatch_log.shift_id
        )
        wave_run_result = await self.db.execute(wave_run_stmt)
        wave_run = wave_run_result.scalar_one_or_none()
        
        if wave_run:
            wave_run.total_declined = str(int(wave_run.total_declined) + 1)
        
        await self.db.commit()
        
        await self._send_sms(
            to_phone=provider.phone_number,
            message="No problem! Thanks for letting me know. 👍"
        )
        
        return {"status": "declined"}


# Convenience function for route handlers
async def process_nurse_sms_response(
    provider_phone: str,
    message_body: str
) -> Dict:
    """Process nurse SMS response (convenience wrapper)."""
    async with WaveMatchDispatcher() as dispatcher:
        return await dispatcher.process_nurse_response(provider_phone, message_body)
