"""
Tests for Incident Handler (Tier 2 Feature #5)

Sprint: VCAI-TIER2-SPRINT-2026-07-07
Coverage: Intent extraction, severity calculation, penalties, backup dispatch
"""

import pytest
from datetime import datetime
from uuid import uuid4

from app.services.incident_handler import IncidentHandler, IncidentResult
from app.models import ShiftIncidentLog, BackupDispatchRun, MarylandProvider, ProviderReliabilityScore


class TestIncidentIntentExtraction:
    """Test incident intent extraction from messages."""
    
    @pytest.mark.asyncio
    async def test_extract_cancellation_intent(self, async_db):
        """Test detecting cancellation from message"""
        handler = IncidentHandler(db=async_db)
        
        messages = [
            "I can't make my shift tonight, flat tire",
            "Cancel my shift please, I'm sick",
            "Won't be able to come in, family emergency"
        ]
        
        for message in messages:
            intent = await handler._extract_incident_intent(message)
            assert intent["type"] == "CANCELLATION"
            assert intent["confidence"] > 0.8
    
    @pytest.mark.asyncio
    async def test_extract_late_arrival_intent(self, async_db):
        """Test detecting late arrival from message"""
        handler = IncidentHandler(db=async_db)
        
        messages = [
            "Running late, stuck in traffic",
            "Gonna be late, be there in 30 min",
            "Delayed, should arrive soon"
        ]
        
        for message in messages:
            intent = await handler._extract_incident_intent(message)
            assert intent["type"] == "LATE_ARRIVAL"
    
    @pytest.mark.asyncio
    async def test_extract_emergency_intent(self, async_db):
        """Test detecting emergency from message"""
        handler = IncidentHandler(db=async_db)
        
        messages = [
            "Emergency! Had an accident",
            "Urgent - need to go to hospital",
            "Critical situation, can't make it"
        ]
        
        for message in messages:
            intent = await handler._extract_incident_intent(message)
            assert intent["type"] in ["EMERGENCY", "CANCELLATION"]


class TestSeverityCalculation:
    """Test incident severity calculation."""
    
    def test_calculate_cancellation_severity(self):
        """Test cancellation severity is CRITICAL"""
        handler = IncidentHandler()
        
        intent = {"type": "CANCELLATION", "reason": "sick"}
        severity = handler._calculate_severity(intent, uuid4())
        
        assert severity == "CRITICAL"
    
    def test_calculate_late_arrival_severity(self):
        """Test late arrival severity is MEDIUM"""
        handler = IncidentHandler()
        
        intent = {"type": "LATE_ARRIVAL", "reason": "traffic"}
        severity = handler._calculate_severity(intent, uuid4())
        
        assert severity == "MEDIUM"
    
    def test_calculate_emergency_severity(self):
        """Test emergency severity is CRITICAL"""
        handler = IncidentHandler()
        
        intent = {"type": "EMERGENCY", "reason": "accident"}
        severity = handler._calculate_severity(intent, uuid4())
        
        assert severity == "CRITICAL"


class TestReliabilityPenalties:
    """Test reliability score penalties."""
    
    @pytest.mark.asyncio
    async def test_apply_cancellation_penalty(self, async_db):
        """Test applying cancellation penalty"""
        provider_id = uuid4()
        
        # Create provider with reliability score
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Test Nurse",
            email="penalty@test.com",
            phone_number="+14105557777",
            npi_number="7777777777",
            md_license_number="RN777777",
            credential_type="RN"
        )
        async_db.add(provider)
        
        score_record = ProviderReliabilityScore(
            provider_id=provider_id,
            reliability_score=80.0
        )
        async_db.add(score_record)
        await async_db.commit()
        
        handler = IncidentHandler(db=async_db)
        penalty = await handler._apply_reliability_penalty(provider_id, "CANCELLATION")
        
        assert penalty == 5.0
        
        # Verify score was reduced
        await async_db.refresh(score_record)
        assert float(score_record.reliability_score) == 75.0
    
    @pytest.mark.asyncio
    async def test_apply_noshow_penalty(self, async_db):
        """Test applying no-show penalty (higher than cancellation)"""
        provider_id = uuid4()
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Test Nurse 2",
            email="noshow@test.com",
            phone_number="+14105558888",
            npi_number="8888888888",
            md_license_number="RN888888",
            credential_type="LPN"
        )
        async_db.add(provider)
        
        score_record = ProviderReliabilityScore(
            provider_id=provider_id,
            reliability_score=80.0
        )
        async_db.add(score_record)
        await async_db.commit()
        
        handler = IncidentHandler(db=async_db)
        penalty = await handler._apply_reliability_penalty(provider_id, "NO_SHOW")
        
        assert penalty == 10.0
        
        # Verify score was reduced
        await async_db.refresh(score_record)
        assert float(score_record.reliability_score) == 70.0
    
    @pytest.mark.asyncio
    async def test_no_penalty_for_emergency(self, async_db):
        """Test no penalty for genuine emergencies"""
        provider_id = uuid4()
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Test Nurse 3",
            email="emergency@test.com",
            phone_number="+14105559999",
            npi_number="9999999999",
            md_license_number="RN999999",
            credential_type="CNA"
        )
        async_db.add(provider)
        
        score_record = ProviderReliabilityScore(
            provider_id=provider_id,
            reliability_score=80.0
        )
        async_db.add(score_record)
        await async_db.commit()
        
        handler = IncidentHandler(db=async_db)
        penalty = await handler._apply_reliability_penalty(provider_id, "EMERGENCY")
        
        assert penalty == 0.0
        
        # Verify score unchanged
        await async_db.refresh(score_record)
        assert float(score_record.reliability_score) == 80.0


class TestIncidentLogging:
    """Test incident logging to database."""
    
    @pytest.mark.asyncio
    async def test_log_incident(self, async_db):
        """Test creating incident log"""
        provider_id = uuid4()
        shift_id = uuid4()
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Log Test Nurse",
            email="log@test.com",
            phone_number="+14105551234",
            npi_number="1234561234",
            md_license_number="RN123456",
            credential_type="RN"
        )
        async_db.add(provider)
        await async_db.commit()
        
        handler = IncidentHandler(db=async_db)
        
        incident_log = await handler._log_incident(
            provider_id=provider_id,
            shift_id=shift_id,
            incident_type="CANCELLATION",
            severity="CRITICAL",
            reported_via="SMS",
            message="Can't make it, flat tire",
            intent_data={"type": "CANCELLATION", "reason": "flat tire"}
        )
        
        assert incident_log.id is not None
        assert incident_log.incident_type == "CANCELLATION"
        assert incident_log.incident_severity == "CRITICAL"
        assert incident_log.reported_via == "SMS"


class TestBackupDispatch:
    """Test backup dispatch triggering."""
    
    @pytest.mark.asyncio
    async def test_trigger_backup_dispatch(self, async_db):
        """Test triggering backup dispatch after cancellation"""
        provider_id = uuid4()
        shift_id = uuid4()
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Backup Test Nurse",
            email="backup@test.com",
            phone_number="+14105556789",
            npi_number="6789012345",
            md_license_number="RN678901",
            credential_type="LPN"
        )
        async_db.add(provider)
        await async_db.commit()
        
        handler = IncidentHandler(db=async_db)
        
        # Create incident log first
        incident_log = await handler._log_incident(
            provider_id=provider_id,
            shift_id=shift_id,
            incident_type="CANCELLATION",
            severity="CRITICAL",
            reported_via="SMS",
            message="Can't make it",
            intent_data={"type": "CANCELLATION"}
        )
        
        # Trigger backup dispatch
        backup_dispatched = await handler._trigger_backup_dispatch(
            incident_log, shift_id, provider_id
        )
        
        assert backup_dispatched is True


class TestEndToEndIncident:
    """Test complete incident processing flow."""
    
    @pytest.mark.asyncio
    async def test_process_cancellation_incident(self, async_db):
        """Test full cancellation incident processing"""
        provider_id = uuid4()
        shift_id = uuid4()
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="E2E Test Nurse",
            email="e2e@test.com",
            phone_number="+14105554321",
            npi_number="4321098765",
            md_license_number="RN432109",
            credential_type="CNA"
        )
        async_db.add(provider)
        
        score_record = ProviderReliabilityScore(
            provider_id=provider_id,
            reliability_score=85.0
        )
        async_db.add(score_record)
        await async_db.commit()
        
        handler = IncidentHandler(db=async_db)
        
        result = await handler.process_incident(
            provider_id=provider_id,
            shift_id=shift_id,
            message="I can't make my shift tonight, I have a flat tire",
            reported_via="SMS"
        )
        
        assert result.success is True
        assert result.incident_id is not None
        assert result.backup_dispatched is True
        assert result.reliability_penalty == 5.0
        
        # Verify reliability score was reduced
        await async_db.refresh(score_record)
        assert float(score_record.reliability_score) == 80.0
