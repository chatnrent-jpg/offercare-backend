"""
Tests for Tier 3 Enterprise Features (#9-#12)

Sprint: VCAI-TIER3-SPRINT-2026-07-07
Coverage: EHR integration, PBJ reporting, anti-poaching, shift bundling
"""

import pytest
from datetime import date
from uuid import uuid4

from app.services.ehr_integration_gateway import EHRIntegrationGateway
from app.services.pbj_reporting_engine import PBJReportingEngine
from app.services.antipoaching_nlp_monitor import AntiPoachingNLPMonitor
from app.services.shift_bundling_optimizer import ShiftBundlingOptimizer
from app.models import MarylandProvider, EHRIntegrationConfig


class TestEHRIntegration:
    """Test EHR integration gateway."""
    
    @pytest.mark.asyncio
    async def test_configure_ehr_integration(self, async_db):
        """Test configuring EHR for facility"""
        facility_id = uuid4()
        
        gateway = EHRIntegrationGateway(db=async_db)
        
        config_id = await gateway.configure_integration(
            facility_id=facility_id,
            ehr_system="MATRIXCARE",
            api_endpoint="https://api.matrixcare.com",
            api_key="test-key",
            ehr_facility_id="FAC123"
        )
        
        assert config_id is not None
    
    @pytest.mark.asyncio
    async def test_sync_inbound_shifts(self, async_db):
        """Test syncing shifts from EHR"""
        facility_id = uuid4()
        
        # Create config first
        config = EHRIntegrationConfig(
            facility_id=facility_id,
            ehr_system="MATRIXCARE",
            ehr_api_endpoint="https://test.com",
            sync_enabled="1"
        )
        async_db.add(config)
        await async_db.commit()
        
        gateway = EHRIntegrationGateway(db=async_db)
        result = await gateway.sync_inbound_shifts(facility_id)
        
        assert result.success is True
        assert result.shifts_synced >= 0


class TestPBJReporting:
    """Test PBJ reporting engine."""
    
    @pytest.mark.asyncio
    async def test_generate_pbj_report(self, async_db):
        """Test generating PBJ report"""
        facility_id = uuid4()
        
        engine = PBJReportingEngine(db=async_db)
        
        export_id = await engine.generate_pbj_report(
            facility_id=facility_id,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
            cms_provider_id="123456"
        )
        
        assert export_id is not None


class TestAntiPoaching:
    """Test anti-poaching NLP monitor."""
    
    @pytest.mark.asyncio
    async def test_detect_phone_number_sharing(self, async_db):
        """Test detecting phone number exchange"""
        monitor = AntiPoachingNLPMonitor(db=async_db)
        
        message = "Call me at 410-555-1234 to discuss working directly"
        
        analysis = await monitor.analyze_message(message)
        
        assert analysis.risk_detected is True
        assert analysis.risk_score > 50.0
        assert "PHONE_NUMBER_SHARED" in analysis.indicators
    
    @pytest.mark.asyncio
    async def test_detect_direct_hire_language(self, async_db):
        """Test detecting direct hiring attempts"""
        monitor = AntiPoachingNLPMonitor(db=async_db)
        
        message = "Why don't you hire me directly and cut out the middleman"
        
        analysis = await monitor.analyze_message(message)
        
        assert analysis.risk_detected is True
        assert "DIRECT_HIRE_LANGUAGE" in analysis.indicators
    
    @pytest.mark.asyncio
    async def test_normal_message_low_risk(self, async_db):
        """Test normal message returns low risk"""
        monitor = AntiPoachingNLPMonitor(db=async_db)
        
        message = "Looking forward to the shift tomorrow!"
        
        analysis = await monitor.analyze_message(message)
        
        assert analysis.risk_detected is False
        assert analysis.risk_score < 30.0


class TestShiftBundling:
    """Test shift bundling optimizer."""
    
    @pytest.mark.asyncio
    async def test_create_shift_bundle(self, async_db):
        """Test creating shift bundle"""
        provider_id = uuid4()
        shift_ids = [uuid4(), uuid4(), uuid4()]
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Bundle Test Nurse",
            email="bundle@test.com",
            phone_number="+14105559000",
            npi_number="9000000000",
            md_license_number="RN900000",
            credential_type="CNA"
        )
        async_db.add(provider)
        await async_db.commit()
        
        optimizer = ShiftBundlingOptimizer(db=async_db)
        
        bundle = await optimizer.create_bundle(
            shift_ids=shift_ids,
            provider_id=provider_id,
            bundle_name="Weekend Bundle"
        )
        
        assert bundle.bundle_id is not None
        assert len(bundle.shift_ids) == 3
        assert bundle.total_hours > 0
        assert bundle.total_earnings > 0
