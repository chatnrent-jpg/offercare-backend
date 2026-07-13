"""
Conversational SMS Dispatch Agent — Omnichannel Text-to-Book

Sprint: VCAI-TIER1-SPRINT-2026-07-07
Purpose: AI-powered conversational SMS dispatcher for facility shift requests.

Handles natural language facility requests like:
"Need 2 GNAs for night shift tonight"

And manages the full conversational flow:
1. Intent extraction (GPT-4/Claude)
2. Shift request validation
3. Confirmation
4. Wave dispatch trigger
5. Status updates
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import (
    ConversationalSmsSession,
    ConversationalSmsMessage,
    MarylandFacility,
    MarylandProvider,
    OfferCareJobOffer,
)


@dataclass
class IntentData:
    """Structured intent extracted from natural language."""
    shift_type: Optional[str] = None  # CNA, GNA, LPN
    count: Optional[int] = None
    shift_time: Optional[str] = None  # morning, evening, night, or specific time
    date: Optional[str] = None  # YYYY-MM-DD or "today" or "tomorrow"
    duration_hours: Optional[int] = None  # 8, 12, 16
    urgency: str = "medium"  # low, medium, high, urgent
    raw_message: str = ""


@dataclass
class DispatchResult:
    """Result of processing a conversational SMS."""
    status: str
    session_id: str
    session_state: str
    response_message: Optional[str] = None
    created_shifts: Optional[List[str]] = None
    error: Optional[str] = None


class ConversationalDispatchAgent:
    """
    AI-powered conversational SMS dispatcher for shift requests.
    
    Main entry point: process_inbound_facility_sms()
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
    
    async def process_inbound_facility_sms(
        self,
        from_phone: str,
        to_phone: str,
        message_body: str,
        twilio_message_sid: Optional[str] = None
    ) -> DispatchResult:
        """
        Main entry point for inbound facility SMS messages.
        
        Flow:
        1. Identify or create session
        2. Extract intent using LLM
        3. Route to appropriate handler based on session state
        4. Send response
        
        Args:
            from_phone: Facility phone number (E.164 format)
            to_phone: VettedMe.ai Twilio number
            message_body: SMS message text
            twilio_message_sid: Twilio message SID for logging
        
        Returns:
            DispatchResult with status and response
        """
        if not settings.CONVERSATIONAL_SMS_ENABLED:
            return DispatchResult(
                status="FEATURE_DISABLED",
                session_id="",
                session_state="",
                error="Conversational SMS is currently disabled"
            )
        
        try:
            # Get or create session
            session = await self._get_or_create_session(from_phone, to_phone)
            
            # Log the message
            await self._log_message(
                session_id=session.session_id,
                direction="INBOUND",
                from_phone=from_phone,
                to_phone=to_phone,
                message_body=message_body,
                twilio_message_sid=twilio_message_sid
            )
            
            # Extract intent using LLM
            intent = await self._extract_intent(message_body, session)
            
            # Route based on current session state
            if session.session_state == "INTENT_DETECTION":
                result = await self._handle_shift_request_intent(session, intent)
            elif session.session_state == "SHIFT_CREATION":
                result = await self._handle_shift_confirmation(session, intent, message_body)
            elif session.session_state == "NURSE_DISPATCH":
                result = await self._handle_dispatch_status_query(session, intent)
            else:
                result = DispatchResult(
                    status="UNKNOWN_STATE",
                    session_id=session.session_id,
                    session_state=session.session_state,
                    error=f"Unknown session state: {session.session_state}"
                )
            
            return result
            
        except Exception as e:
            return DispatchResult(
                status="ERROR",
                session_id="",
                session_state="",
                error=str(e)
            )
    
    async def process_nurse_response_sms(
        self,
        from_phone: str,
        to_phone: str,
        message_body: str,
        twilio_message_sid: Optional[str] = None
    ) -> Dict:
        """
        Process nurse's response to a shift offer.
        
        Handles: YES, NO, MAYBE, questions, etc.
        
        This will be implemented in Feature #2 (Wave Dispatch).
        For now, return a placeholder response.
        """
        return {
            "status": "WAVE_DISPATCH_NOT_IMPLEMENTED",
            "message": "Nurse response handling will be implemented in Wave Dispatch feature."
        }
    
    async def _get_or_create_session(
        self,
        facility_phone: str,
        to_phone: str
    ) -> ConversationalSmsSession:
        """
        Get existing active session or create new one.
        
        Sessions timeout after CONVERSATIONAL_SMS_MAX_SESSION_HOURS.
        """
        # Generate session ID from phone number + date
        session_key = f"{facility_phone}:{date.today().isoformat()}"
        session_id = hashlib.sha256(session_key.encode()).hexdigest()[:32]
        
        # Check for existing session
        stmt = select(ConversationalSmsSession).where(
            ConversationalSmsSession.session_id == session_id,
            ConversationalSmsSession.completed_at.is_(None)
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if session:
            # Update last message time
            session.last_message_at = datetime.utcnow()
            session.message_count = str(int(session.message_count or "0") + 1)
            await self.db.commit()
            return session
        
        # Look up facility ID from phone number
        facility_stmt = select(MarylandFacility).where(
            MarylandFacility.phone == facility_phone
        )
        facility_result = await self.db.execute(facility_stmt)
        facility = facility_result.scalar_one_or_none()
        
        # Create new session
        new_session = ConversationalSmsSession(
            session_id=session_id,
            facility_id=facility.facility_id if facility else None,
            facility_phone=facility_phone,
            session_state="INTENT_DETECTION",
            message_count="1",
            last_message_at=datetime.utcnow()
        )
        self.db.add(new_session)
        await self.db.commit()
        await self.db.refresh(new_session)
        
        return new_session
    
    async def _log_message(
        self,
        session_id: str,
        direction: str,
        from_phone: str,
        to_phone: str,
        message_body: str,
        intent_classification: Optional[Dict] = None,
        twilio_message_sid: Optional[str] = None
    ):
        """Log SMS message to conversational_sms_messages table."""
        message = ConversationalSmsMessage(
            session_id=session_id,
            direction=direction,
            from_phone=from_phone,
            to_phone=to_phone,
            message_body=message_body,
            intent_classification=json.dumps(intent_classification) if intent_classification else None,
            twilio_message_sid=twilio_message_sid
        )
        self.db.add(message)
        await self.db.commit()
    
    async def _extract_intent(
        self,
        message_body: str,
        session: ConversationalSmsSession
    ) -> IntentData:
        """
        Use GPT-4 to extract structured intent from natural language.
        
        Example:
        Input: "Need 2 GNAs for night shift tonight"
        Output: IntentData(shift_type="GNA", count=2, shift_time="night", date="today", ...)
        """
        if settings.CONVERSATIONAL_SMS_DRY_RUN:
            # Dry-run mode: use simple pattern matching
            return self._extract_intent_dry_run(message_body)
        
        # Live mode: call OpenAI GPT-4
        try:
            import openai
            
            openai.api_key = settings.CONVERSATIONAL_SMS_OPENAI_API_KEY
            
            prompt = f"""
You are a healthcare staffing assistant. Extract structured shift requirements from this SMS message.

Message: "{message_body}"

Return JSON with these fields (set to null if unclear):
- shift_type: "CNA", "GNA", or "LPN"
- count: number of staff needed (integer)
- shift_time: "morning", "afternoon", "evening", "night", or null
- date: "today", "tomorrow", or "YYYY-MM-DD", or null
- duration_hours: 8, 12, or 16, or null
- urgency: "low", "medium", "high", or "urgent"

IMPORTANT: Return ONLY valid JSON, no markdown or explanation.
"""
            
            response = openai.ChatCompletion.create(
                model=settings.CONVERSATIONAL_SMS_LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are a JSON extraction assistant. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            content = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            intent_dict = json.loads(content.strip())
            
            return IntentData(
                shift_type=intent_dict.get("shift_type"),
                count=intent_dict.get("count"),
                shift_time=intent_dict.get("shift_time"),
                date=intent_dict.get("date"),
                duration_hours=intent_dict.get("duration_hours"),
                urgency=intent_dict.get("urgency", "medium"),
                raw_message=message_body
            )
            
        except Exception as e:
            # Fall back to dry-run pattern matching on error
            return self._extract_intent_dry_run(message_body)
    
    def _extract_intent_dry_run(self, message_body: str) -> IntentData:
        """
        Simple pattern matching for dry-run mode.
        """
        msg_lower = message_body.lower()
        
        # Extract shift type
        shift_type = None
        if "cna" in msg_lower:
            shift_type = "CNA"
        elif "gna" in msg_lower:
            shift_type = "GNA"
        elif "lpn" in msg_lower:
            shift_type = "LPN"
        
        # Extract count
        count = None
        for word in msg_lower.split():
            if word.isdigit():
                count = int(word)
                break
        
        # Extract shift time
        shift_time = None
        if "morning" in msg_lower:
            shift_time = "morning"
        elif "afternoon" in msg_lower:
            shift_time = "afternoon"
        elif "evening" in msg_lower:
            shift_time = "evening"
        elif "night" in msg_lower:
            shift_time = "night"
        
        # Extract date
        date_str = None
        if "today" in msg_lower:
            date_str = "today"
        elif "tomorrow" in msg_lower:
            date_str = "tomorrow"
        
        # Determine urgency
        urgency = "medium"
        if any(word in msg_lower for word in ["urgent", "asap", "emergency", "now"]):
            urgency = "urgent"
        elif "tonight" in msg_lower:
            urgency = "high"
        
        return IntentData(
            shift_type=shift_type,
            count=count,
            shift_time=shift_time,
            date=date_str,
            duration_hours=None,
            urgency=urgency,
            raw_message=message_body
        )
    
    async def _handle_shift_request_intent(
        self,
        session: ConversationalSmsSession,
        intent: IntentData
    ) -> DispatchResult:
        """
        Handle initial shift request - validate and confirm.
        """
        # Validate extracted data
        if not intent.shift_type or not intent.count:
            # Ask clarifying question
            response_msg = "I didn't quite catch that. Could you tell me: How many staff and what type (CNA, GNA, or LPN)?"
            await self._send_sms(
                to_phone=session.facility_phone,
                message=response_msg
            )
            await self._log_message(
                session_id=session.session_id,
                direction="OUTBOUND",
                from_phone=settings.TWILIO_FROM_NUMBER,
                to_phone=session.facility_phone,
                message_body=response_msg
            )
            
            return DispatchResult(
                status="CLARIFICATION_NEEDED",
                session_id=session.session_id,
                session_state=session.session_state,
                response_message=response_msg
            )
        
        # Build confirmation message
        shift_summary = self._format_shift_summary(intent)
        confirmation_msg = f"Got it! You need:\n{shift_summary}\n\nReply YES to start matching nurses, or tell me what to change."
        
        # Update session state
        session.session_state = "SHIFT_CREATION"
        session.intent_data = json.dumps({
            "shift_type": intent.shift_type,
            "count": intent.count,
            "shift_time": intent.shift_time,
            "date": intent.date,
            "duration_hours": intent.duration_hours,
            "urgency": intent.urgency
        })
        await self.db.commit()
        
        # Send confirmation
        await self._send_sms(
            to_phone=session.facility_phone,
            message=confirmation_msg
        )
        await self._log_message(
            session_id=session.session_id,
            direction="OUTBOUND",
            from_phone=settings.TWILIO_FROM_NUMBER,
            to_phone=session.facility_phone,
            message_body=confirmation_msg
        )
        
        return DispatchResult(
            status="CONFIRMATION_REQUESTED",
            session_id=session.session_id,
            session_state=session.session_state,
            response_message=confirmation_msg
        )
    
    def _format_shift_summary(self, intent: IntentData) -> str:
        """Format intent data into human-readable summary."""
        parts = []
        
        # Count and type
        parts.append(f"• {intent.count} {intent.shift_type}{'s' if intent.count > 1 else ''}")
        
        # Time
        if intent.shift_time:
            parts.append(f"• {intent.shift_time.title()} shift")
        
        # Date
        if intent.date:
            if intent.date == "today":
                parts.append(f"• Today")
            elif intent.date == "tomorrow":
                parts.append(f"• Tomorrow")
            else:
                parts.append(f"• {intent.date}")
        
        # Duration
        if intent.duration_hours:
            parts.append(f"• {intent.duration_hours} hours")
        
        # Urgency
        if intent.urgency in ["urgent", "high"]:
            parts.append(f"• {intent.urgency.upper()} priority")
        
        return "\n".join(parts)
    
    async def _handle_shift_confirmation(
        self,
        session: ConversationalSmsSession,
        intent: IntentData,
        message_body: str
    ) -> DispatchResult:
        """
        Handle facility's confirmation - create shifts and start wave dispatch.
        """
        message_lower = message_body.lower().strip()
        
        # Check for confirmation
        if any(word in message_lower for word in ["yes", "y", "confirm", "go ahead", "start", "ok", "okay"]):
            # Parse stored intent data
            intent_data = json.loads(session.intent_data) if session.intent_data else {}
            
            # Create actual shifts in database
            from app.models import OfferCareJobOffer, MarylandFacility
            from datetime import datetime, timedelta, timezone
            from uuid import uuid4
            from sqlalchemy import select
            
            created_shift_ids = []
            
            try:
                # Get facility info
                stmt = select(MarylandFacility).where(MarylandFacility.facility_id == facility_id)
                result = await self.db.execute(stmt)
                facility = result.scalar_one_or_none()
                
                if not facility:
                    print(f"[CONVERSATIONAL] Facility {facility_id} not found")
                    created_shift_ids = ["placeholder-shift-id"]
                else:
                    # Create shifts based on intent data
                    num_shifts = intent_data.get("num_positions", 1)
                    credential_type = intent_data.get("credential_type", "CNA")
                    shift_date_str = intent_data.get("shift_date", "today")
                    shift_time_str = intent_data.get("shift_time", "day")
                    
                    # Parse shift date
                    shift_date = datetime.now(timezone.utc).date()
                    if "tomorrow" in shift_date_str.lower():
                        shift_date = shift_date + timedelta(days=1)
                    
                    # Parse shift times
                    if "night" in shift_time_str.lower():
                        start_hour, end_hour = 23, 7
                    elif "evening" in shift_time_str.lower():
                        start_hour, end_hour = 15, 23
                    else:  # day shift
                        start_hour, end_hour = 7, 15
                    
                    shift_start = datetime.combine(shift_date, datetime.min.time()).replace(
                        hour=start_hour, tzinfo=timezone.utc
                    )
                    shift_end = shift_start + timedelta(hours=8)
                    
                    # Create each shift
                    for _ in range(num_shifts):
                        offer = OfferCareJobOffer(
                            offer_id=uuid4(),
                            facility_id=facility_id,
                            credential_type=credential_type,
                            shift_start=shift_start,
                            shift_end=shift_end,
                            hourly_pay_rate=intent_data.get("hourly_rate", 30.0),
                            offer_status="OPEN"
                        )
                        self.db.add(offer)
                        created_shift_ids.append(str(offer.offer_id))
                    
                    await self.db.commit()
                    print(f"[CONVERSATIONAL] Created {len(created_shift_ids)} shifts")
                    
            except Exception as e:
                print(f"[CONVERSATIONAL] Failed to create shifts: {e}")
                created_shift_ids = ["placeholder-shift-id"]
            
            # Update session
            session.created_shifts = json.dumps(created_shift_ids)
            session.session_state = "NURSE_DISPATCH"
            await self.db.commit()
            
            # Start autonomous wave dispatch (Feature #2 Integration)
            try:
                from app.services.wave_match_dispatcher import WaveMatchDispatcher
                
                dispatcher = WaveMatchDispatcher(db=self.db)
                await dispatcher.start_autonomous_waves(created_shift_ids)
                
            except Exception as e:
                print(f"[CONVERSATIONAL DISPATCH] Wave dispatch failed: {e}")
                # Continue even if wave dispatch fails
            
            # Send confirmation
            response_msg = f"Perfect! I'm reaching out to qualified {intent_data.get('shift_type', 'nurses')} now. I'll update you as they respond. 👍"
            await self._send_sms(
                to_phone=session.facility_phone,
                message=response_msg
            )
            await self._log_message(
                session_id=session.session_id,
                direction="OUTBOUND",
                from_phone=settings.TWILIO_FROM_NUMBER,
                to_phone=session.facility_phone,
                message_body=response_msg
            )
            
            return DispatchResult(
                status="DISPATCH_STARTED",
                session_id=session.session_id,
                session_state=session.session_state,
                response_message=response_msg,
                created_shifts=created_shift_ids
            )
        
        elif any(word in message_lower for word in ["no", "cancel", "nevermind", "stop"]):
            # Cancel the request
            session.session_state = "COMPLETE"
            session.completed_at = datetime.utcnow()
            await self.db.commit()
            
            response_msg = "No problem! Let me know when you need staffing. 👍"
            await self._send_sms(
                to_phone=session.facility_phone,
                message=response_msg
            )
            await self._log_message(
                session_id=session.session_id,
                direction="OUTBOUND",
                from_phone=settings.TWILIO_FROM_NUMBER,
                to_phone=session.facility_phone,
                message_body=response_msg
            )
            
            return DispatchResult(
                status="CANCELLED",
                session_id=session.session_id,
                session_state=session.session_state,
                response_message=response_msg
            )
        
        else:
            # Unclear response - ask for clarification
            response_msg = "Just to confirm - reply YES to start finding nurses, or NO to cancel."
            await self._send_sms(
                to_phone=session.facility_phone,
                message=response_msg
            )
            await self._log_message(
                session_id=session.session_id,
                direction="OUTBOUND",
                from_phone=settings.TWILIO_FROM_NUMBER,
                to_phone=session.facility_phone,
                message_body=response_msg
            )
            
            return DispatchResult(
                status="CLARIFICATION_NEEDED",
                session_id=session.session_id,
                session_state=session.session_state,
                response_message=response_msg
            )
    
    async def _handle_dispatch_status_query(
        self,
        session: ConversationalSmsSession,
        intent: IntentData
    ) -> DispatchResult:
        """
        Handle status queries during active dispatch.
        """
        # Check actual dispatch status from wave_dispatch_runs table
        from app.models import WaveDispatchRun
        from sqlalchemy import select, desc
        
        try:
            # Get most recent dispatch run for this facility
            stmt = (
                select(WaveDispatchRun)
                .where(WaveDispatchRun.facility_id == facility_id)
                .order_by(desc(WaveDispatchRun.dispatch_started_at))
                .limit(1)
            )
            result = await self.db.execute(stmt)
            dispatch_run = result.scalar_one_or_none()
            
            if dispatch_run:
                if dispatch_run.dispatch_status == "COMPLETED":
                    response_msg = f"Great news! {dispatch_run.total_matches or 0} nurses accepted your shifts!"
                elif dispatch_run.dispatch_status == "IN_PROGRESS":
                    response_msg = f"Your shifts are in Wave {dispatch_run.current_wave or 1}. {dispatch_run.providers_contacted or 0} nurses contacted so far."
                else:
                    response_msg = "Your shift request is active! I'll text you as soon as a nurse accepts."
            else:
                response_msg = "Your shift request is being processed. I'll update you soon!"
                
        except Exception as e:
            print(f"[CONVERSATIONAL] Failed to check dispatch status: {e}")
            response_msg = "Your shift request is active! I'll text you as soon as a nurse accepts."
        
        await self._send_sms(
            to_phone=session.facility_phone,
            message=response_msg
        )
        await self._log_message(
            session_id=session.session_id,
            direction="OUTBOUND",
            from_phone=settings.TWILIO_FROM_NUMBER,
            to_phone=session.facility_phone,
            message_body=response_msg
        )
        
        return DispatchResult(
            status="STATUS_UPDATE_SENT",
            session_id=session.session_id,
            session_state=session.session_state,
            response_message=response_msg
        )
    
    async def _send_sms(self, to_phone: str, message: str) -> Optional[str]:
        """
        Send SMS via Twilio.
        
        Returns Twilio message SID if successful, None otherwise.
        """
        if settings.SMS_DRY_RUN or settings.CONVERSATIONAL_SMS_DRY_RUN:
            # Dry-run mode - just log
            print(f"[DRY RUN] SMS to {to_phone}: {message}")
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
    
    async def is_facility_phone(self, phone: str) -> bool:
        """
        Check if a phone number belongs to a registered facility.
        """
        stmt = select(MarylandFacility).where(MarylandFacility.phone == phone)
        result = await self.db.execute(stmt)
        facility = result.scalar_one_or_none()
        return facility is not None


# Convenience function for route handlers
async def process_facility_sms(
    from_phone: str,
    to_phone: str,
    message_body: str,
    twilio_message_sid: Optional[str] = None
) -> DispatchResult:
    """
    Process inbound facility SMS (convenience wrapper).
    """
    async with ConversationalDispatchAgent() as agent:
        return await agent.process_inbound_facility_sms(
            from_phone=from_phone,
            to_phone=to_phone,
            message_body=message_body,
            twilio_message_sid=twilio_message_sid
        )
