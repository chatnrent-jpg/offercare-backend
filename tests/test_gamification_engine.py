"""
Tests for Gamification Engine (Tier 2 Feature #8)

Sprint: VCAI-TIER2-SPRINT-2026-07-07
Coverage: Tier calculation, achievements, perks
"""

import pytest
from uuid import uuid4

from app.services.gamification_engine import GamificationEngine, TierStatus
from app.models import MarylandProvider, ProviderTierStatus


class TestTierCalculation:
    """Test tier calculation logic."""
    
    @pytest.mark.asyncio
    async def test_bronze_tier(self, async_db):
        """Test Bronze tier (0-49 shifts)"""
        provider_id = uuid4()
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Bronze Nurse",
            email="bronze@test.com",
            phone_number="+14105551000",
            npi_number="1000000000",
            md_license_number="RN100000",
            credential_type="CNA"
        )
        async_db.add(provider)
        
        tier_status = ProviderTierStatus(
            provider_id=provider_id,
            total_shifts_completed="25"
        )
        async_db.add(tier_status)
        await async_db.commit()
        
        engine = GamificationEngine(db=async_db)
        tier = await engine.calculate_tier(provider_id)
        
        assert tier.current_tier == "BRONZE"
        assert tier.next_tier == "SILVER"
        assert "Instant pay" not in tier.perks
    
    @pytest.mark.asyncio
    async def test_silver_tier(self, async_db):
        """Test Silver tier (50-149 shifts)"""
        provider_id = uuid4()
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Silver Nurse",
            email="silver@test.com",
            phone_number="+14105552000",
            npi_number="2000000000",
            md_license_number="RN200000",
            credential_type="GNA"
        )
        async_db.add(provider)
        
        tier_status = ProviderTierStatus(
            provider_id=provider_id,
            total_shifts_completed="75"
        )
        async_db.add(tier_status)
        await async_db.commit()
        
        engine = GamificationEngine(db=async_db)
        tier = await engine.calculate_tier(provider_id)
        
        assert tier.current_tier == "SILVER"
        assert tier.next_tier == "GOLD"
        assert any("Instant pay" in perk for perk in tier.perks)
    
    @pytest.mark.asyncio
    async def test_gold_tier(self, async_db):
        """Test Gold tier (150-299 shifts)"""
        provider_id = uuid4()
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Gold Nurse",
            email="gold@test.com",
            phone_number="+14105553000",
            npi_number="3000000000",
            md_license_number="RN300000",
            credential_type="LPN"
        )
        async_db.add(provider)
        
        tier_status = ProviderTierStatus(
            provider_id=provider_id,
            total_shifts_completed="200"
        )
        async_db.add(tier_status)
        await async_db.commit()
        
        engine = GamificationEngine(db=async_db)
        tier = await engine.calculate_tier(provider_id)
        
        assert tier.current_tier == "GOLD"
        assert tier.next_tier == "PLATINUM"
        assert any("+5%" in perk for perk in tier.perks)
    
    @pytest.mark.asyncio
    async def test_platinum_tier(self, async_db):
        """Test Platinum tier (300+ shifts)"""
        provider_id = uuid4()
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Platinum Nurse",
            email="platinum@test.com",
            phone_number="+14105554000",
            npi_number="4000000000",
            md_license_number="RN400000",
            credential_type="RN"
        )
        async_db.add(provider)
        
        tier_status = ProviderTierStatus(
            provider_id=provider_id,
            total_shifts_completed="350"
        )
        async_db.add(tier_status)
        await async_db.commit()
        
        engine = GamificationEngine(db=async_db)
        tier = await engine.calculate_tier(provider_id)
        
        assert tier.current_tier == "PLATINUM"
        assert tier.next_tier is None
        assert any("+10%" in perk for perk in tier.perks)


class TestAchievements:
    """Test achievement checking."""
    
    @pytest.mark.asyncio
    async def test_check_achievements(self, async_db):
        """Test getting all achievements"""
        provider_id = uuid4()
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Achievement Nurse",
            email="achieve@test.com",
            phone_number="+14105555000",
            npi_number="5000000000",
            md_license_number="RN500000",
            credential_type="CNA"
        )
        async_db.add(provider)
        await async_db.commit()
        
        engine = GamificationEngine(db=async_db)
        achievements = await engine.check_achievements(provider_id)
        
        assert len(achievements) > 0
        assert any(a.achievement_type == "PERFECT_ATTENDANCE" for a in achievements)
        assert any(a.achievement_type == "RELIABILITY_CHAMPION" for a in achievements)


class TestStreakManagement:
    """Test attendance streak management."""
    
    @pytest.mark.asyncio
    async def test_increment_attendance_streak(self, async_db):
        """Test incrementing perfect attendance streak"""
        provider_id = uuid4()
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Streak Nurse",
            email="streak@test.com",
            phone_number="+14105556000",
            npi_number="6000000000",
            md_license_number="RN600000",
            credential_type="LPN"
        )
        async_db.add(provider)
        
        tier_status = ProviderTierStatus(
            provider_id=provider_id,
            perfect_attendance_streak="5"
        )
        async_db.add(tier_status)
        await async_db.commit()
        
        engine = GamificationEngine(db=async_db)
        await engine.increment_attendance_streak(provider_id)
        
        await async_db.refresh(tier_status)
        assert int(tier_status.perfect_attendance_streak) == 6
    
    @pytest.mark.asyncio
    async def test_reset_attendance_streak(self, async_db):
        """Test resetting streak on late arrival"""
        provider_id = uuid4()
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Late Nurse",
            email="late@test.com",
            phone_number="+14105557000",
            npi_number="7000000000",
            md_license_number="RN700000",
            credential_type="RN"
        )
        async_db.add(provider)
        
        tier_status = ProviderTierStatus(
            provider_id=provider_id,
            perfect_attendance_streak="8"
        )
        async_db.add(tier_status)
        await async_db.commit()
        
        engine = GamificationEngine(db=async_db)
        await engine.reset_attendance_streak(provider_id)
        
        await async_db.refresh(tier_status)
        assert int(tier_status.perfect_attendance_streak) == 0
