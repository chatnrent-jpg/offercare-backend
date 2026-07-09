"""
Gamification Engine — Nurse Retention & Engagement

Sprint: VCAI-TIER2-SPRINT-2026-07-07
Purpose: Loyalty program with tiers, achievements, and rewards.

Tier System:
- BRONZE (0-49 shifts): Basic access
- SILVER (50-149 shifts): Instant pay, priority dispatch
- GOLD (150-299 shifts): VIP shifts, +5% bonus
- PLATINUM (300+ shifts): Exclusive shifts, +10% bonus, concierge service

Achievements:
- PERFECT_ATTENDANCE: 10 consecutive on-time shifts
- EARLY_BIRD: 50 shifts completed before scheduled time
- FACILITY_FAVORITE: 4.8+ avg rating from facilities
- WEEKEND_WARRIOR: 25 weekend shifts
- NIGHT_OWL: 50 night shifts
- RAPID_RESPONDER: Average <2min response time
- RELIABILITY_CHAMPION: 95+ reliability score maintained for 90 days

Perks:
- Instant pay (no wait for shift completion)
- Priority SMS dispatch (first to receive shift offers)
- VIP shift access (high-paying exclusive shifts)
- Rate bonuses (+5% to +10%)
- Dedicated support line
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import (
    ProviderAchievementLog,
    ProviderTierStatus,
    ProviderReliabilityScore,
    MarylandProvider,
)


@dataclass
class TierStatus:
    """Provider tier status."""
    current_tier: str
    tier_points: int
    next_tier: Optional[str]
    points_to_next_tier: Optional[int]
    perks: List[str]


@dataclass
class Achievement:
    """Achievement details."""
    achievement_type: str
    achievement_name: str
    achievement_description: str
    reward: str
    earned: bool


class GamificationEngine:
    """
    Gamification and retention engine.
    
    Main entry points:
    - calculate_tier(provider_id)
    - check_achievements(provider_id)
    - get_perks(provider_id)
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
    
    async def calculate_tier(self, provider_id: UUID) -> TierStatus:
        """
        Calculate provider's current tier based on shift history.
        
        Tier Thresholds:
        - BRONZE: 0-49 shifts
        - SILVER: 50-149 shifts
        - GOLD: 150-299 shifts
        - PLATINUM: 300+ shifts
        
        Returns:
            TierStatus with current tier and perks
        """
        if not settings.GAMIFICATION_ENABLED:
            return TierStatus(
                current_tier="BRONZE",
                tier_points=0,
                next_tier=None,
                points_to_next_tier=None,
                perks=[]
            )
        
        # Get or create tier status
        tier_status = await self._get_tier_status(provider_id)
        
        # Count actual completed shifts from database
        from app.models import ClinicalPlacementLedger
        from sqlalchemy import select, func
        
        stmt = select(func.count(ClinicalPlacementLedger.placement_id)).where(
            ClinicalPlacementLedger.provider_id == provider_id
        )
        result = await self.db.execute(stmt)
        total_shifts = result.scalar() or int(tier_status.total_shifts_completed)
        
        # Determine tier
        if total_shifts >= settings.GAMIFICATION_TIER_PLATINUM_THRESHOLD:
            current_tier = "PLATINUM"
            next_tier = None
            points_to_next = None
        elif total_shifts >= settings.GAMIFICATION_TIER_GOLD_THRESHOLD:
            current_tier = "GOLD"
            next_tier = "PLATINUM"
            points_to_next = settings.GAMIFICATION_TIER_PLATINUM_THRESHOLD - total_shifts
        elif total_shifts >= settings.GAMIFICATION_TIER_SILVER_THRESHOLD:
            current_tier = "SILVER"
            next_tier = "GOLD"
            points_to_next = settings.GAMIFICATION_TIER_GOLD_THRESHOLD - total_shifts
        else:
            current_tier = "BRONZE"
            next_tier = "SILVER"
            points_to_next = settings.GAMIFICATION_TIER_SILVER_THRESHOLD - total_shifts
        
        # Update tier if changed
        if tier_status.current_tier != current_tier:
            tier_status.current_tier = current_tier
            tier_status.last_tier_change = datetime.utcnow()
            await self.db.commit()
            
            print(f"[GAMIFICATION] Provider {provider_id} tier updated to {current_tier}")
            
            # Award tier achievement
            await self._award_achievement(
                provider_id=provider_id,
                achievement_type=f"TIER_{current_tier}",
                reward=f"Unlocked {current_tier} tier perks"
            )
        
        # Get perks for tier
        perks = self._get_tier_perks(current_tier)
        
        # Update perks in database
        tier_status.perks_unlocked = json.dumps(perks)
        tier_status.tier_points = str(total_shifts)
        tier_status.calculated_at = datetime.utcnow()
        await self.db.commit()
        
        return TierStatus(
            current_tier=current_tier,
            tier_points=total_shifts,
            next_tier=next_tier,
            points_to_next_tier=points_to_next,
            perks=perks
        )
    
    def _get_tier_perks(self, tier: str) -> List[str]:
        """Get perks for tier."""
        all_perks = {
            "BRONZE": [
                "Standard shift access",
                "Email support"
            ],
            "SILVER": [
                "Standard shift access",
                "Email support",
                "Instant pay (same-day)",
                "Priority dispatch"
            ],
            "GOLD": [
                "Standard shift access",
                "Email support",
                "Instant pay (same-day)",
                "Priority dispatch",
                "VIP shift access",
                "+5% hourly rate bonus",
                "Dedicated support line"
            ],
            "PLATINUM": [
                "Standard shift access",
                "Email support",
                "Instant pay (same-day)",
                "Priority dispatch",
                "VIP shift access",
                "+10% hourly rate bonus",
                "Dedicated support line",
                "Exclusive high-paying shifts",
                "Concierge scheduling service"
            ]
        }
        return all_perks.get(tier, [])
    
    async def check_achievements(self, provider_id: UUID) -> List[Achievement]:
        """
        Check which achievements provider has earned.
        
        Returns list of all achievements with earned status.
        """
        if not settings.GAMIFICATION_ENABLED:
            return []
        
        # Get existing achievements
        stmt = select(ProviderAchievementLog).where(
            ProviderAchievementLog.provider_id == provider_id
        )
        result = await self.db.execute(stmt)
        earned_achievements = {log.achievement_type for log in result.scalars().all()}
        
        # Define all possible achievements
        all_achievements = [
            Achievement(
                achievement_type="PERFECT_ATTENDANCE",
                achievement_name="Perfect Attendance",
                achievement_description="Complete 10 consecutive on-time shifts",
                reward="Instant pay unlocked",
                earned="PERFECT_ATTENDANCE" in earned_achievements
            ),
            Achievement(
                achievement_type="EARLY_BIRD",
                achievement_name="Early Bird",
                achievement_description="Complete 50 shifts before scheduled time",
                reward="+2% rate bonus",
                earned="EARLY_BIRD" in earned_achievements
            ),
            Achievement(
                achievement_type="FACILITY_FAVORITE",
                achievement_name="Facility Favorite",
                achievement_description="Maintain 4.8+ average facility rating",
                reward="VIP badge",
                earned="FACILITY_FAVORITE" in earned_achievements
            ),
            Achievement(
                achievement_type="WEEKEND_WARRIOR",
                achievement_name="Weekend Warrior",
                achievement_description="Complete 25 weekend shifts",
                reward="Weekend bonus +$3/hr",
                earned="WEEKEND_WARRIOR" in earned_achievements
            ),
            Achievement(
                achievement_type="NIGHT_OWL",
                achievement_name="Night Owl",
                achievement_description="Complete 50 night shifts",
                reward="Night shift bonus +$2/hr",
                earned="NIGHT_OWL" in earned_achievements
            ),
            Achievement(
                achievement_type="RAPID_RESPONDER",
                achievement_name="Rapid Responder",
                achievement_description="Average <2min SMS response time",
                reward="Priority dispatch",
                earned="RAPID_RESPONDER" in earned_achievements
            ),
            Achievement(
                achievement_type="RELIABILITY_CHAMPION",
                achievement_name="Reliability Champion",
                achievement_description="95+ reliability score for 90 days",
                reward="+5% rate bonus",
                earned="RELIABILITY_CHAMPION" in earned_achievements
            )
        ]
        
        return all_achievements
    
    async def _get_tier_status(self, provider_id: UUID) -> ProviderTierStatus:
        """Get or create provider tier status."""
        stmt = select(ProviderTierStatus).where(ProviderTierStatus.provider_id == provider_id)
        result = await self.db.execute(stmt)
        tier_status = result.scalar_one_or_none()
        
        if not tier_status:
            # Create new tier status
            tier_status = ProviderTierStatus(
                provider_id=provider_id,
                current_tier="BRONZE",
                tier_points="0",
                total_shifts_completed="0"
            )
            self.db.add(tier_status)
            await self.db.commit()
            await self.db.refresh(tier_status)
        
        return tier_status
    
    async def _award_achievement(
        self,
        provider_id: UUID,
        achievement_type: str,
        reward: str
    ):
        """Award achievement to provider."""
        # Check if already awarded
        stmt = select(ProviderAchievementLog).where(
            ProviderAchievementLog.provider_id == provider_id,
            ProviderAchievementLog.achievement_type == achievement_type
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            return  # Already awarded
        
        # Create achievement log
        achievement_log = ProviderAchievementLog(
            provider_id=provider_id,
            achievement_type=achievement_type,
            reward_unlocked=reward
        )
        self.db.add(achievement_log)
        await self.db.commit()
        
        print(f"[GAMIFICATION] Achievement awarded: {achievement_type} to provider {provider_id}")
        
        # Send notification to provider
        try:
            from app.models import MarylandProvider
            from sqlalchemy import select
            
            # Get provider details
            stmt = select(MarylandProvider).where(MarylandProvider.provider_id == provider_id)
            result = await self.db.execute(stmt)
            provider = result.scalar_one_or_none()
            
            if provider and provider.phone:
                # Send SMS notification if SMS is enabled
                if not settings.SMS_DRY_RUN and settings.TWILIO_ACCOUNT_SID:
                    from app.services.sms import send_sms
                    
                    message = f"🎉 Congratulations! You've earned the {achievement_type} achievement! "
                    if reward_unlocked:
                        message += f"Reward: {reward_unlocked}"
                    
                    await send_sms(provider.phone, message)
                else:
                    print(f"[GAMIFICATION] DRY RUN: Would send SMS to {provider.phone}")
        except Exception as e:
            print(f"[GAMIFICATION] Failed to send notification: {e}")
    
    async def increment_shift_count(self, provider_id: UUID):
        """Increment shift count for provider (called after shift completion)."""
        tier_status = await self._get_tier_status(provider_id)
        
        current_count = int(tier_status.total_shifts_completed)
        tier_status.total_shifts_completed = str(current_count + 1)
        await self.db.commit()
        
        # Recalculate tier
        await self.calculate_tier(provider_id)
    
    async def increment_attendance_streak(self, provider_id: UUID):
        """Increment perfect attendance streak."""
        tier_status = await self._get_tier_status(provider_id)
        
        current_streak = int(tier_status.perfect_attendance_streak)
        tier_status.perfect_attendance_streak = str(current_streak + 1)
        await self.db.commit()
        
        # Check for perfect attendance achievement
        if current_streak + 1 >= 10:
            await self._award_achievement(
                provider_id=provider_id,
                achievement_type="PERFECT_ATTENDANCE",
                reward="Instant pay unlocked"
            )
    
    async def reset_attendance_streak(self, provider_id: UUID):
        """Reset attendance streak (called on late arrival or no-show)."""
        tier_status = await self._get_tier_status(provider_id)
        tier_status.perfect_attendance_streak = "0"
        await self.db.commit()


# Convenience functions
async def update_provider_tier(provider_id: UUID) -> TierStatus:
    """Update provider tier (convenience wrapper)."""
    async with GamificationEngine() as engine:
        return await engine.calculate_tier(provider_id)


async def get_provider_perks(provider_id: UUID) -> List[str]:
    """Get provider's current perks (convenience wrapper)."""
    async with GamificationEngine() as engine:
        tier_status = await engine.calculate_tier(provider_id)
        return tier_status.perks
