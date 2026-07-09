"""
Tests for Dynamic Pricing Engine (Tier 2 Features #6 & #7)

Sprint: VCAI-TIER2-SPRINT-2026-07-07
Coverage: Auto-negotiation, surge pricing, rate caps
"""

import pytest
from uuid import uuid4

from app.services.dynamic_pricing_engine import DynamicPricingEngine, NegotiationResult, SurgeStatus
from app.models import FacilityRateConfig


class TestRateNegotiation:
    """Test auto-negotiation logic."""
    
    @pytest.mark.asyncio
    async def test_negotiate_urgent_shift(self, async_db):
        """Test negotiating rate for urgent shift (<2 hours)"""
        facility_id = uuid4()
        shift_id = uuid4()
        
        # Create facility rate config
        rate_config = FacilityRateConfig(
            facility_id=facility_id,
            base_hourly_rate_cna=25.00,
            max_hourly_rate_cna=40.00
        )
        async_db.add(rate_config)
        await async_db.commit()
        
        engine = DynamicPricingEngine(db=async_db)
        
        result = await engine.negotiate_rate(
            shift_id=shift_id,
            facility_id=facility_id,
            credential_type="CNA",
            current_rate=25.0,
            time_until_shift_minutes=60  # 1 hour = very urgent
        )
        
        assert result.negotiated is True
        assert result.new_rate > result.original_rate
        assert result.increase_pct > 40.0  # High urgency = high increase
    
    @pytest.mark.asyncio
    async def test_enforce_max_rate_cap(self, async_db):
        """Test max rate cap enforcement"""
        facility_id = uuid4()
        shift_id = uuid4()
        
        rate_config = FacilityRateConfig(
            facility_id=facility_id,
            base_hourly_rate_lpn=35.00,
            max_hourly_rate_lpn=50.00  # Cap at $50
        )
        async_db.add(rate_config)
        await async_db.commit()
        
        engine = DynamicPricingEngine(db=async_db)
        
        result = await engine.negotiate_rate(
            shift_id=shift_id,
            facility_id=facility_id,
            credential_type="LPN",
            current_rate=48.0,  # Already near max
            time_until_shift_minutes=30  # Critical urgency
        )
        
        assert result.negotiated is True
        assert result.new_rate <= 50.0  # Should not exceed cap


class TestUrgencyCalculation:
    """Test urgency score calculation."""
    
    def test_low_urgency(self):
        """Test low urgency (6+ hours away)"""
        engine = DynamicPricingEngine()
        
        urgency = engine._calculate_urgency_score(400)  # 6.67 hours
        assert urgency == 20.0
    
    def test_medium_urgency(self):
        """Test medium urgency (2-4 hours)"""
        engine = DynamicPricingEngine()
        
        urgency = engine._calculate_urgency_score(180)  # 3 hours
        assert urgency == 60.0
    
    def test_high_urgency(self):
        """Test high urgency (<1 hour)"""
        engine = DynamicPricingEngine()
        
        urgency = engine._calculate_urgency_score(30)  # 30 minutes
        assert urgency == 100.0


class TestSurgePricing:
    """Test surge pricing events."""
    
    @pytest.mark.asyncio
    async def test_trigger_surge_event(self, async_db):
        """Test triggering surge pricing event"""
        engine = DynamicPricingEngine(db=async_db)
        
        event_id = await engine.trigger_surge_event(
            event_type="WEATHER",
            surge_multiplier=1.5,
            trigger_reason="Blizzard warning in Baltimore",
            affected_regions=["21201", "21202"],
            unfilled_shifts_count=35
        )
        
        assert event_id is not None
    
    @pytest.mark.asyncio
    async def test_get_active_surge(self, async_db):
        """Test getting active surge multiplier"""
        engine = DynamicPricingEngine(db=async_db)
        
        # Trigger surge
        await engine.trigger_surge_event(
            event_type="HIGH_DEMAND",
            surge_multiplier=1.8,
            trigger_reason="Flu outbreak",
            unfilled_shifts_count=50
        )
        
        # Get surge status
        status = await engine.get_surge_multiplier()
        
        assert status.surge_active is True
        assert status.surge_multiplier == 1.8
    
    @pytest.mark.asyncio
    async def test_no_active_surge(self, async_db):
        """Test when no surge is active"""
        engine = DynamicPricingEngine(db=async_db)
        
        status = await engine.get_surge_multiplier()
        
        assert status.surge_active is False
        assert status.surge_multiplier == 1.0
