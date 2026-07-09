"""
Tests for Conversational SMS Dispatch Agent (Tier 1 Feature)

Sprint: VCAI-TIER1-SPRINT-2026-07-07
Coverage: Intent extraction, session management, shift confirmation flows
"""

import pytest
import json
from datetime import datetime, date
from unittest.mock import Mock, AsyncMock, patch

from app.services.conversational_dispatch_agent import (
    ConversationalDispatchAgent,
    IntentData,
    DispatchResult,
    process_facility_sms
)
from app.models import ConversationalSmsSession, ConversationalSmsMessage


class TestIntentExtraction:
    """Test AI intent extraction from natural language."""
    
    @pytest.mark.asyncio
    async def test_extract_intent_simple_request(self, async_db):
        """Test extraction of simple shift request: 'Need 2 GNAs for night shift tonight'"""
        agent = ConversationalDispatchAgent(db=async_db)
        
        # Create mock session
        session = ConversationalSmsSession(
            session_id="test-session-1",
            facility_phone="+14105551234",
            session_state="INTENT_DETECTION"
        )
        async_db.add(session)
        await async_db.commit()
        
        # Test dry-run pattern matching
        intent = agent._extract_intent_dry_run("Need 2 GNAs for night shift tonight")
        
        assert intent.shift_type == "GNA"
        assert intent.count == 2
        assert intent.shift_time == "night"
        assert intent.urgency in ["high", "urgent"]
    
    @pytest.mark.asyncio
    async def test_extract_intent_cna_request(self, async_db):
        """Test CNA extraction"""
        agent = ConversationalDispatchAgent(db=async_db)
        
        intent = agent._extract_intent_dry_run("Need 3 CNAs for tomorrow morning")
        
        assert intent.shift_type == "CNA"
        assert intent.count == 3
        assert intent.shift_time == "morning"
        assert intent.date == "tomorrow"
    
    @pytest.mark.asyncio
    async def test_extract_intent_lpn_urgent(self, async_db):
        """Test urgent LPN request"""
        agent = ConversationalDispatchAgent(db=async_db)
        
        intent = agent._extract_intent_dry_run("URGENT - need 1 LPN ASAP")
        
        assert intent.shift_type == "LPN"
        assert intent.count == 1
        assert intent.urgency == "urgent"
    
    @pytest.mark.asyncio
    async def test_extract_intent_unclear(self, async_db):
        """Test unclear request requiring clarification"""
        agent = ConversationalDispatchAgent(db=async_db)
        
        intent = agent._extract_intent_dry_run("Need some help tonight")
        
        # Should have missing required fields
        assert intent.shift_type is None or intent.count is None


class TestSessionManagement:
    """Test SMS conversation session lifecycle."""
    
    @pytest.mark.asyncio
    async def test_create_new_session(self, async_db):
        """Test creating a new conversation session"""
        agent = ConversationalDispatchAgent(db=async_db)
        
        session = await agent._get_or_create_session(
            facility_phone="+14105551111",
            to_phone="+14105559999"
        )
        
        assert session is not None
        assert session.facility_phone == "+14105551111"
        assert session.session_state == "INTENT_DETECTION"
        assert session.message_count == "1"
    
    @pytest.mark.asyncio
    async def test_reuse_existing_session(self, async_db):
        """Test reusing an existing active session"""
        agent = ConversationalDispatchAgent(db=async_db)
        
        # Create first session
        session1 = await agent._get_or_create_session(
            facility_phone="+14105552222",
            to_phone="+14105559999"
        )
        
        # Get same session again
        session2 = await agent._get_or_create_session(
            facility_phone="+14105552222",
            to_phone="+14105559999"
        )
        
        assert session1.session_id == session2.session_id
        assert session2.message_count == "2"


class TestShiftRequestFlow:
    """Test full conversational shift request flow."""
    
    @pytest.mark.asyncio
    async def test_handle_initial_request(self, async_db):
        """Test handling initial shift request with valid data"""
        agent = ConversationalDispatchAgent(db=async_db)
        
        # Create session
        session = ConversationalSmsSession(
            session_id="test-session-2",
            facility_phone="+14105553333",
            session_state="INTENT_DETECTION"
        )
        async_db.add(session)
        await async_db.commit()
        
        # Create intent
        intent = IntentData(
            shift_type="CNA",
            count=2,
            shift_time="evening",
            date="today",
            urgency="medium"
        )
        
        # Mock SMS sending
        with patch.object(agent, '_send_sms', return_value="mock-sid"):
            result = await agent._handle_shift_request_intent(session, intent)
        
        assert result.status == "CONFIRMATION_REQUESTED"
        assert session.session_state == "SHIFT_CREATION"
        assert "CNA" in result.response_message
        assert "YES" in result.response_message
    
    @pytest.mark.asyncio
    async def test_handle_clarification_needed(self, async_db):
        """Test requesting clarification for unclear intent"""
        agent = ConversationalDispatchAgent(db=async_db)
        
        session = ConversationalSmsSession(
            session_id="test-session-3",
            facility_phone="+14105554444",
            session_state="INTENT_DETECTION"
        )
        async_db.add(session)
        await async_db.commit()
        
        # Unclear intent (missing shift type)
        intent = IntentData(
            shift_type=None,
            count=2,
            shift_time="night",
            urgency="medium"
        )
        
        with patch.object(agent, '_send_sms', return_value="mock-sid"):
            result = await agent._handle_shift_request_intent(session, intent)
        
        assert result.status == "CLARIFICATION_NEEDED"
        assert "CNA, GNA, or LPN" in result.response_message


class TestConfirmationHandling:
    """Test shift confirmation response handling."""
    
    @pytest.mark.asyncio
    async def test_confirmation_yes(self, async_db):
        """Test facility confirms with YES"""
        agent = ConversationalDispatchAgent(db=async_db)
        
        # Create session with intent data
        session = ConversationalSmsSession(
            session_id="test-session-4",
            facility_phone="+14105555555",
            session_state="SHIFT_CREATION",
            intent_data=json.dumps({
                "shift_type": "GNA",
                "count": 1,
                "shift_time": "morning",
                "date": "tomorrow"
            })
        )
        async_db.add(session)
        await async_db.commit()
        
        intent = IntentData(raw_message="YES")
        
        with patch.object(agent, '_send_sms', return_value="mock-sid"):
            result = await agent._handle_shift_confirmation(session, intent, "YES")
        
        assert result.status == "DISPATCH_STARTED"
        assert session.session_state == "NURSE_DISPATCH"
        assert "reaching out" in result.response_message.lower()
    
    @pytest.mark.asyncio
    async def test_confirmation_no(self, async_db):
        """Test facility cancels with NO"""
        agent = ConversationalDispatchAgent(db=async_db)
        
        session = ConversationalSmsSession(
            session_id="test-session-5",
            facility_phone="+14105556666",
            session_state="SHIFT_CREATION",
            intent_data=json.dumps({
                "shift_type": "CNA",
                "count": 2,
                "shift_time": "night"
            })
        )
        async_db.add(session)
        await async_db.commit()
        
        intent = IntentData(raw_message="NO")
        
        with patch.object(agent, '_send_sms', return_value="mock-sid"):
            result = await agent._handle_shift_confirmation(session, intent, "NO")
        
        assert result.status == "CANCELLED"
        assert session.session_state == "COMPLETE"
        assert session.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_confirmation_unclear(self, async_db):
        """Test unclear confirmation response"""
        agent = ConversationalDispatchAgent(db=async_db)
        
        session = ConversationalSmsSession(
            session_id="test-session-6",
            facility_phone="+14105557777",
            session_state="SHIFT_CREATION",
            intent_data=json.dumps({
                "shift_type": "LPN",
                "count": 1
            })
        )
        async_db.add(session)
        await async_db.commit()
        
        intent = IntentData(raw_message="Maybe later")
        
        with patch.object(agent, '_send_sms', return_value="mock-sid"):
            result = await agent._handle_shift_confirmation(session, intent, "Maybe later")
        
        assert result.status == "CLARIFICATION_NEEDED"
        assert "YES" in result.response_message
        assert "NO" in result.response_message


class TestMessageLogging:
    """Test SMS message logging."""
    
    @pytest.mark.asyncio
    async def test_log_inbound_message(self, async_db):
        """Test logging inbound facility message"""
        agent = ConversationalDispatchAgent(db=async_db)
        
        await agent._log_message(
            session_id="test-session-log-1",
            direction="INBOUND",
            from_phone="+14105558888",
            to_phone="+14105559999",
            message_body="Need 2 CNAs for tonight",
            twilio_message_sid="SM123456"
        )
        
        # Verify message was logged
        from sqlalchemy import select
        stmt = select(ConversationalSmsMessage).where(
            ConversationalSmsMessage.session_id == "test-session-log-1"
        )
        result = await async_db.execute(stmt)
        message = result.scalar_one_or_none()
        
        assert message is not None
        assert message.direction == "INBOUND"
        assert message.from_phone == "+14105558888"
        assert message.message_body == "Need 2 CNAs for tonight"
        assert message.twilio_message_sid == "SM123456"
    
    @pytest.mark.asyncio
    async def test_log_outbound_message(self, async_db):
        """Test logging outbound system message"""
        agent = ConversationalDispatchAgent(db=async_db)
        
        await agent._log_message(
            session_id="test-session-log-2",
            direction="OUTBOUND",
            from_phone="+14105559999",
            to_phone="+14105558888",
            message_body="Got it! Reply YES to confirm.",
            intent_classification={"type": "confirmation_request"}
        )
        
        from sqlalchemy import select
        stmt = select(ConversationalSmsMessage).where(
            ConversationalSmsMessage.session_id == "test-session-log-2"
        )
        result = await async_db.execute(stmt)
        message = result.scalar_one_or_none()
        
        assert message is not None
        assert message.direction == "OUTBOUND"
        assert "YES" in message.message_body


class TestEndToEndFlow:
    """Test complete end-to-end conversation flows."""
    
    @pytest.mark.asyncio
    async def test_full_successful_flow(self, async_db):
        """Test complete flow from request to dispatch"""
        agent = ConversationalDispatchAgent(db=async_db)
        
        facility_phone = "+14105550001"
        twilio_phone = "+14105559999"
        
        # Step 1: Initial request
        with patch.object(agent, '_send_sms', return_value="mock-sid-1"):
            result1 = await agent.process_inbound_facility_sms(
                from_phone=facility_phone,
                to_phone=twilio_phone,
                message_body="Need 2 GNAs for night shift tonight"
            )
        
        assert result1.status == "CONFIRMATION_REQUESTED"
        assert result1.session_state == "SHIFT_CREATION"
        
        # Step 2: Confirm with YES
        with patch.object(agent, '_send_sms', return_value="mock-sid-2"):
            result2 = await agent.process_inbound_facility_sms(
                from_phone=facility_phone,
                to_phone=twilio_phone,
                message_body="YES"
            )
        
        assert result2.status == "DISPATCH_STARTED"
        assert result2.session_state == "NURSE_DISPATCH"
        assert result2.created_shifts is not None
    
    @pytest.mark.asyncio
    async def test_full_cancelled_flow(self, async_db):
        """Test flow that gets cancelled"""
        agent = ConversationalDispatchAgent(db=async_db)
        
        facility_phone = "+14105550002"
        twilio_phone = "+14105559999"
        
        # Step 1: Initial request
        with patch.object(agent, '_send_sms', return_value="mock-sid-1"):
            result1 = await agent.process_inbound_facility_sms(
                from_phone=facility_phone,
                to_phone=twilio_phone,
                message_body="Need 1 LPN for tomorrow"
            )
        
        assert result1.status == "CONFIRMATION_REQUESTED"
        
        # Step 2: Cancel with NO
        with patch.object(agent, '_send_sms', return_value="mock-sid-2"):
            result2 = await agent.process_inbound_facility_sms(
                from_phone=facility_phone,
                to_phone=twilio_phone,
                message_body="NO nevermind"
            )
        
        assert result2.status == "CANCELLED"
        assert result2.session_state == "COMPLETE"


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_feature_disabled(self, async_db):
        """Test when conversational SMS is disabled"""
        from app.config import settings
        
        # Temporarily disable feature
        original_value = settings.CONVERSATIONAL_SMS_ENABLED
        settings.CONVERSATIONAL_SMS_ENABLED = False
        
        try:
            agent = ConversationalDispatchAgent(db=async_db)
            result = await agent.process_inbound_facility_sms(
                from_phone="+14105550003",
                to_phone="+14105559999",
                message_body="Need help"
            )
            
            assert result.status == "FEATURE_DISABLED"
            assert "disabled" in result.error.lower()
        finally:
            settings.CONVERSATIONAL_SMS_ENABLED = original_value
    
    @pytest.mark.asyncio
    async def test_sms_sending_dry_run(self, async_db):
        """Test SMS sending in dry-run mode"""
        agent = ConversationalDispatchAgent(db=async_db)
        
        # Send SMS in dry-run mode (should not fail)
        sid = await agent._send_sms(
            to_phone="+14105550004",
            message="Test message"
        )
        
        # Dry-run returns None
        assert sid is None


@pytest.mark.asyncio
async def test_process_facility_sms_convenience_function(async_db):
    """Test convenience wrapper function"""
    with patch('app.services.conversational_dispatch_agent.ConversationalDispatchAgent') as mock_agent_class:
        mock_agent = AsyncMock()
        mock_agent.process_inbound_facility_sms = AsyncMock(return_value=DispatchResult(
            status="SUCCESS",
            session_id="test",
            session_state="COMPLETE"
        ))
        mock_agent_class.return_value.__aenter__.return_value = mock_agent
        mock_agent_class.return_value.__aexit__.return_value = AsyncMock()
        
        result = await process_facility_sms(
            from_phone="+14105550005",
            to_phone="+14105559999",
            message_body="Need 1 CNA"
        )
        
        assert result.status == "SUCCESS"
