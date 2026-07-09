"""
Tests for Wave Match Dispatcher (Tier 1 Feature #2)

Sprint: VCAI-TIER1-SPRINT-2026-07-07
Coverage: Wave sequencing, priority scoring, nurse responses, acceptance/decline handling
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from app.services.wave_match_dispatcher import (
    WaveMatchDispatcher,
    NurseCandidate,
    process_nurse_sms_response
)
from app.models import (
    WaveDispatchConfig,
    WaveDispatchRun,
    ProviderReliabilityScore,
    NurseSmsDispatchLog,
    MarylandProvider,
    MarylandFacility,
    OfferCareJobOffer,
)


class TestWaveConfiguration:
    """Test wave dispatch configuration."""
    
    @pytest.mark.asyncio
    async def test_get_default_config(self, async_db):
        """Test getting default wave config when none exists"""
        dispatcher = WaveMatchDispatcher(db=async_db)
        
        facility_id = uuid4()
        config = await dispatcher._get_wave_config(facility_id)
        
        assert config is not None
        assert config.wave_1_size == "5"
        assert config.wave_2_size == "10"
        assert config.wave_3_size == "20"
        assert config.wave_4_bonus_enabled is True
    
    @pytest.mark.asyncio
    async def test_facility_specific_config(self, async_db):
        """Test facility-specific wave configuration"""
        # Create custom config
        facility_id = uuid4()
        custom_config = WaveDispatchConfig(
            facility_id=facility_id,
            wave_1_size="3",
            wave_2_size="8",
            wave_3_size="15",
            wave_1_delay_seconds="180"
        )
        async_db.add(custom_config)
        await async_db.commit()
        
        dispatcher = WaveMatchDispatcher(db=async_db)
        config = await dispatcher._get_wave_config(facility_id)
        
        assert config.wave_1_size == "3"
        assert config.wave_2_size == "8"
        assert config.wave_3_size == "15"


class TestPriorityScoring:
    """Test nurse priority scoring algorithm."""
    
    @pytest.mark.asyncio
    async def test_calculate_distance(self):
        """Test haversine distance calculation"""
        dispatcher = WaveMatchDispatcher()
        
        # Baltimore to Towson (~10 miles)
        distance = dispatcher._calculate_distance(
            lat1=Decimal("39.2904"),  # Baltimore
            lon1=Decimal("-76.6122"),
            lat2=Decimal("39.4015"),  # Towson
            lon2=Decimal("-76.6019")
        )
        
        assert 9 < distance < 11  # Approximately 10 miles
    
    @pytest.mark.asyncio
    async def test_calculate_distance_missing_coords(self):
        """Test distance calculation with missing coordinates"""
        dispatcher = WaveMatchDispatcher()
        
        distance = dispatcher._calculate_distance(
            lat1=None,
            lon1=None,
            lat2=Decimal("39.2904"),
            lon2=Decimal("-76.6122")
        )
        
        assert distance == 999.0  # Default far distance
    
    @pytest.mark.asyncio
    async def test_priority_score_components(self, async_db):
        """Test priority score calculation with all components"""
        # Create test facility
        facility = MarylandFacility(
            facility_id=uuid4(),
            name="Test Hospital",
            facility_type="HOSPITAL",
            county="Baltimore",
            state="MD",
            latitude=Decimal("39.2904"),
            longitude=Decimal("-76.6122")
        )
        async_db.add(facility)
        
        # Create test provider
        provider = MarylandProvider(
            provider_id=uuid4(),
            full_name="Test Nurse",
            email="test@test.com",
            phone_number="+14105551111",
            npi_number="1234567890",
            md_license_number="TEST123",
            credential_type="CNA",
            latitude=Decimal("39.3000"),  # Close to facility
            longitude=Decimal("-76.6100")
        )
        async_db.add(provider)
        
        # Create reliability score
        reliability = ProviderReliabilityScore(
            provider_id=provider.provider_id,
            reliability_score=Decimal("75.0"),
            on_time_rate=Decimal("0.95"),
            cancellation_rate=Decimal("0.05")
        )
        async_db.add(reliability)
        
        # Create test shift
        shift = OfferCareJobOffer(
            offer_id=uuid4(),
            facility_id=facility.facility_id,
            shift_role="CNA",
            hourly_pay_rate=Decimal("25.00")
        )
        async_db.add(shift)
        
        await async_db.commit()
        
        dispatcher = WaveMatchDispatcher(db=async_db)
        score = await dispatcher._calculate_priority_score(provider, facility, shift)
        
        # Score should be between 0 and 100
        assert 0 <= score <= 100
        # Should be reasonably high (good reliability + close proximity)
        assert score > 50


class TestWaveSequencing:
    """Test wave dispatch sequencing and timing."""
    
    @pytest.mark.asyncio
    async def test_create_wave_run(self, async_db):
        """Test creating a new wave run"""
        dispatcher = WaveMatchDispatcher(db=async_db)
        
        shift_id = uuid4()
        wave_run = await dispatcher._create_wave_run(shift_id)
        
        assert wave_run is not None
        assert wave_run.shift_id == shift_id
        assert wave_run.current_wave == "1"
        assert wave_run.run_state == "ACTIVE"
        assert wave_run.total_dispatched == "0"
    
    @pytest.mark.asyncio
    async def test_complete_wave_run(self, async_db):
        """Test completing a wave run"""
        dispatcher = WaveMatchDispatcher(db=async_db)
        
        wave_run = WaveDispatchRun(
            shift_id=uuid4(),
            run_state="ACTIVE"
        )
        async_db.add(wave_run)
        await async_db.commit()
        await async_db.refresh(wave_run)
        
        await dispatcher._complete_wave_run(wave_run, "FILLED_WAVE_1")
        
        assert wave_run.run_state == "COMPLETED"
        assert wave_run.completion_reason == "FILLED_WAVE_1"
        assert wave_run.completed_at is not None


class TestCandidateSelection:
    """Test nurse candidate selection and filtering."""
    
    @pytest.mark.asyncio
    async def test_exclude_already_dispatched(self, async_db):
        """Test that already-dispatched nurses are excluded"""
        shift_id = uuid4()
        provider_id = uuid4()
        
        # Create dispatch log (already dispatched)
        dispatch_log = NurseSmsDispatchLog(
            shift_id=shift_id,
            provider_id=provider_id,
            wave_number="1",
            message_body="Test"
        )
        async_db.add(dispatch_log)
        await async_db.commit()
        
        dispatcher = WaveMatchDispatcher(db=async_db)
        already_dispatched = await dispatcher._already_dispatched(shift_id, provider_id)
        
        assert already_dispatched is True
    
    @pytest.mark.asyncio
    async def test_not_already_dispatched(self, async_db):
        """Test that new nurses are not marked as dispatched"""
        dispatcher = WaveMatchDispatcher(db=async_db)
        
        shift_id = uuid4()
        provider_id = uuid4()
        
        already_dispatched = await dispatcher._already_dispatched(shift_id, provider_id)
        
        assert already_dispatched is False


class TestNurseResponseHandling:
    """Test processing nurse SMS responses."""
    
    @pytest.mark.asyncio
    async def test_nurse_accepts_shift(self, async_db):
        """Test nurse accepting a shift with YES"""
        # Create test data
        shift_id = uuid4()
        provider_id = uuid4()
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Test Nurse",
            email="nurse@test.com",
            phone_number="+14105552222",
            npi_number="9876543210",
            md_license_number="NURSE123",
            credential_type="CNA"
        )
        async_db.add(provider)
        
        shift = OfferCareJobOffer(
            offer_id=shift_id,
            facility_id=uuid4(),
            shift_role="CNA",
            hourly_pay_rate=Decimal("25.00"),
            compliance_lock_status="BROADCASTING"
        )
        async_db.add(shift)
        
        dispatch_log = NurseSmsDispatchLog(
            shift_id=shift_id,
            provider_id=provider_id,
            wave_number="1",
            message_body="Test shift offer"
        )
        async_db.add(dispatch_log)
        
        wave_run = WaveDispatchRun(
            shift_id=shift_id,
            run_state="ACTIVE"
        )
        async_db.add(wave_run)
        
        await async_db.commit()
        
        dispatcher = WaveMatchDispatcher(db=async_db)
        
        with patch.object(dispatcher, '_send_sms', return_value="mock-sid"):
            result = await dispatcher.process_nurse_response(
                provider_phone="+14105552222",
                message_body="YES"
            )
        
        assert result["status"] == "accepted"
        
        # Verify shift is locked
        await async_db.refresh(shift)
        assert shift.compliance_lock_status == "LOCKED"
        assert shift.assigned_provider_id == provider_id
        
        # Verify dispatch log updated
        await async_db.refresh(dispatch_log)
        assert dispatch_log.response_intent == "ACCEPT"
        assert dispatch_log.responded_at is not None
    
    @pytest.mark.asyncio
    async def test_nurse_declines_shift(self, async_db):
        """Test nurse declining a shift with NO"""
        provider_id = uuid4()
        shift_id = uuid4()
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Test Nurse",
            email="nurse2@test.com",
            phone_number="+14105553333",
            npi_number="1111111111",
            md_license_number="NURSE456",
            credential_type="GNA"
        )
        async_db.add(provider)
        
        dispatch_log = NurseSmsDispatchLog(
            shift_id=shift_id,
            provider_id=provider_id,
            wave_number="1",
            message_body="Test offer"
        )
        async_db.add(dispatch_log)
        
        wave_run = WaveDispatchRun(
            shift_id=shift_id,
            run_state="ACTIVE"
        )
        async_db.add(wave_run)
        
        await async_db.commit()
        
        dispatcher = WaveMatchDispatcher(db=async_db)
        
        with patch.object(dispatcher, '_send_sms', return_value="mock-sid"):
            result = await dispatcher.process_nurse_response(
                provider_phone="+14105553333",
                message_body="NO can't make it"
            )
        
        assert result["status"] == "declined"
        
        # Verify dispatch log updated
        await async_db.refresh(dispatch_log)
        assert dispatch_log.response_intent == "DECLINE"
        assert dispatch_log.responded_at is not None
        
        # Verify wave run stats updated
        await async_db.refresh(wave_run)
        assert wave_run.total_declined == "1"
    
    @pytest.mark.asyncio
    async def test_nurse_unclear_response(self, async_db):
        """Test unclear nurse response requiring clarification"""
        provider_id = uuid4()
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Test Nurse",
            email="nurse3@test.com",
            phone_number="+14105554444",
            npi_number="2222222222",
            md_license_number="NURSE789",
            credential_type="LPN"
        )
        async_db.add(provider)
        
        dispatch_log = NurseSmsDispatchLog(
            shift_id=uuid4(),
            provider_id=provider_id,
            wave_number="2",
            message_body="Test"
        )
        async_db.add(dispatch_log)
        
        await async_db.commit()
        
        dispatcher = WaveMatchDispatcher(db=async_db)
        
        with patch.object(dispatcher, '_send_sms', return_value="mock-sid"):
            result = await dispatcher.process_nurse_response(
                provider_phone="+14105554444",
                message_body="Maybe, let me check"
            )
        
        assert result["status"] == "clarification_needed"
    
    @pytest.mark.asyncio
    async def test_shift_already_filled(self, async_db):
        """Test nurse accepting after shift is already filled"""
        provider_id = uuid4()
        shift_id = uuid4()
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Test Nurse",
            email="nurse4@test.com",
            phone_number="+14105555555",
            npi_number="3333333333",
            md_license_number="NURSE999",
            credential_type="CNA"
        )
        async_db.add(provider)
        
        shift = OfferCareJobOffer(
            offer_id=shift_id,
            facility_id=uuid4(),
            shift_role="CNA",
            hourly_pay_rate=Decimal("25.00"),
            compliance_lock_status="FILLED"  # Already filled
        )
        async_db.add(shift)
        
        dispatch_log = NurseSmsDispatchLog(
            shift_id=shift_id,
            provider_id=provider_id,
            wave_number="1",
            message_body="Test"
        )
        async_db.add(dispatch_log)
        
        await async_db.commit()
        
        dispatcher = WaveMatchDispatcher(db=async_db)
        
        with patch.object(dispatcher, '_send_sms', return_value="mock-sid"):
            result = await dispatcher.process_nurse_response(
                provider_phone="+14105555555",
                message_body="YES"
            )
        
        assert result["status"] == "shift_already_filled"


class TestSmsMessageFormatting:
    """Test SMS message formatting for shift offers."""
    
    def test_build_shift_offer_message(self):
        """Test building personalized shift offer SMS"""
        dispatcher = WaveMatchDispatcher()
        
        shift = OfferCareJobOffer(
            offer_id=uuid4(),
            facility_id=uuid4(),
            shift_role="CNA",
            hourly_pay_rate=Decimal("28.50"),
            shift_starts_at=datetime(2026, 7, 10, 7, 0),
            shift_ends_at=datetime(2026, 7, 10, 19, 0)
        )
        
        provider = MarylandProvider(
            provider_id=uuid4(),
            full_name="Test Nurse",
            email="test@test.com",
            phone_number="+14105556666",
            npi_number="4444444444",
            md_license_number="TEST",
            credential_type="CNA"
        )
        
        candidate = NurseCandidate(
            provider=provider,
            priority_score=75.0,
            distance_miles=5.5,
            reliability_score=80.0
        )
        
        message = dispatcher._build_shift_offer_sms(shift, candidate, wave_number=1)
        
        assert "CNA" in message
        assert "$28.50" in message
        assert "5.5 mi" in message
        assert "YES" in message
        assert "NO" in message


@pytest.mark.asyncio
async def test_process_nurse_sms_response_convenience_function(async_db):
    """Test convenience wrapper function for nurse responses"""
    provider_id = uuid4()
    
    provider = MarylandProvider(
        provider_id=provider_id,
        full_name="Test Nurse",
        email="test@test.com",
        phone_number="+14105557777",
        npi_number="5555555555",
        md_license_number="TEST123",
        credential_type="CNA"
    )
    async_db.add(provider)
    await async_db.commit()
    
    result = await process_nurse_sms_response(
        provider_phone="+14105557777",
        message_body="YES"
    )
    
    # Should return no active offer since we didn't create a dispatch log
    assert result["status"] == "no_active_offer"
