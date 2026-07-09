# Tier 1 Features — Technical Implementation Specifications
**Sprint ID:** VCAI-TIER1-SPRINT-2026-07-07  
**Purpose:** Build critical Phase 2 conversational engine and compliance automation features  
**Target Completion:** 30 days from 2026-07-07

---

## Overview

Tier 1 features represent the highest-value development priorities for VettedMe, focusing on:
1. **Conversational SMS dispatch** to eliminate dashboard friction
2. **Autonomous wave matching** to maximize shift fill rates
3. **Computer vision document processing** for compliance automation
4. **Background MBON verification** for continuous compliance monitoring

These features directly address the Phase 2 "Conversational Engine" roadmap and critical compliance gaps.

---

## Feature 1: Omnichannel Text-to-Book (Conversational SMS Dispatch)

### Business Objective
Enable facilities to text simple shift requests (e.g., "Need 2 GNAs for night shift tonight") and have the AI handle the entire dispatch, negotiation, and confirmation process via SMS without human intervention.

### Technical Architecture

#### 1.1 Conversational State Machine

```
┌──────────────────┐
│ Inbound SMS      │
│ from Facility    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Intent Detection │ ← OpenAI GPT-4 / Claude
│ & Entity Extract │    - Shift type (CNA/GNA/LPN)
└────────┬─────────┘    - Count (1, 2, 3...)
         │              - Time (tonight, tomorrow, specific date)
         │              - Duration (8hr, 12hr, etc.)
         ▼
┌──────────────────┐
│ Shift Creation   │
│ & Validation     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Wave Match       │ → Dynamic SMS waves to qualified nurses
│ Dispatcher       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Nurse Response   │ ← "Yes", "I'm available", "Can't make it"
│ Processing       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Confirmation &   │
│ Shift Lock       │
└──────────────────┘
```

#### 1.2 Database Schema (Alembic 028)

**New Table: `conversational_sms_sessions`**

```sql
CREATE TABLE conversational_sms_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(64) UNIQUE NOT NULL,
    facility_id UUID REFERENCES facilities(id),
    facility_phone VARCHAR(20) NOT NULL,
    session_state VARCHAR(32) NOT NULL, -- INTENT_DETECTION, SHIFT_CREATION, NURSE_DISPATCH, CONFIRMATION, COMPLETE
    intent_data JSONB,                  -- Extracted shift requirements
    created_shifts UUID[],              -- Array of shift IDs created from this session
    message_count INTEGER DEFAULT 0,
    last_message_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    INDEX idx_session_facility (facility_id),
    INDEX idx_session_state (session_state),
    INDEX idx_session_phone (facility_phone)
);

CREATE TABLE conversational_sms_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(64) REFERENCES conversational_sms_sessions(session_id),
    direction VARCHAR(10) NOT NULL,    -- INBOUND, OUTBOUND
    from_phone VARCHAR(20) NOT NULL,
    to_phone VARCHAR(20) NOT NULL,
    message_body TEXT NOT NULL,
    intent_classification JSONB,      -- AI's understanding of the message
    twilio_message_sid VARCHAR(64),
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_message_session (session_id),
    INDEX idx_message_direction (direction),
    INDEX idx_message_timestamp (sent_at)
);
```

**New Table: `nurse_sms_dispatch_log`**

```sql
CREATE TABLE nurse_sms_dispatch_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shift_id UUID REFERENCES shifts(id),
    provider_id UUID REFERENCES providers(id),
    wave_number INTEGER NOT NULL,      -- 1st wave, 2nd wave, etc.
    dispatch_priority INTEGER,         -- Rank within the wave
    message_body TEXT NOT NULL,
    twilio_message_sid VARCHAR(64),
    dispatched_at TIMESTAMPTZ DEFAULT NOW(),
    responded_at TIMESTAMPTZ,
    response_intent VARCHAR(32),       -- ACCEPT, DECLINE, UNCLEAR, NO_RESPONSE
    response_message TEXT,
    INDEX idx_dispatch_shift (shift_id),
    INDEX idx_dispatch_provider (provider_id),
    INDEX idx_dispatch_wave (wave_number)
);
```

#### 1.3 Service Module: `app/services/conversational_dispatch_agent.py`

**Core Functions:**

```python
from typing import Dict, List, Optional
from uuid import UUID
import openai  # or anthropic for Claude
from datetime import datetime, timedelta

class ConversationalDispatchAgent:
    """
    AI-powered conversational SMS dispatcher for shift requests.
    """
    
    async def process_inbound_facility_sms(
        self,
        from_phone: str,
        to_phone: str,
        message_body: str
    ) -> Dict:
        """
        Main entry point for inbound facility SMS messages.
        
        Flow:
        1. Identify or create session
        2. Extract intent using LLM
        3. Route to appropriate handler
        4. Send response
        """
        session = await self._get_or_create_session(from_phone, to_phone)
        
        # Log the message
        await self._log_message(
            session_id=session.session_id,
            direction="INBOUND",
            from_phone=from_phone,
            to_phone=to_phone,
            message_body=message_body
        )
        
        # Extract intent using GPT-4
        intent = await self._extract_intent(message_body, session)
        
        # Route based on current session state
        if session.session_state == "INTENT_DETECTION":
            return await self._handle_shift_request_intent(session, intent)
        elif session.session_state == "SHIFT_CREATION":
            return await self._handle_shift_confirmation(session, intent)
        elif session.session_state == "NURSE_DISPATCH":
            return await self._handle_dispatch_status_query(session, intent)
        
    async def _extract_intent(
        self,
        message_body: str,
        session: ConversationalSmsSession
    ) -> Dict:
        """
        Use GPT-4 to extract structured intent from natural language.
        
        Example prompt:
        "Extract shift requirements from: 'Need 2 GNAs for night shift tonight'"
        
        Returns:
        {
            "shift_type": "GNA",
            "count": 2,
            "shift_time": "night",
            "date": "2026-07-07",
            "duration_hours": 12,
            "urgency": "high"
        }
        """
        prompt = f"""
You are a healthcare staffing assistant. Extract structured shift requirements from this message.

Message: "{message_body}"

Return JSON with:
- shift_type: CNA, GNA, or LPN
- count: number of staff needed
- shift_time: morning, evening, night, or specific time
- date: YYYY-MM-DD or "today" or "tomorrow"
- duration_hours: 8, 12, or 16
- urgency: low, medium, high, urgent

If anything is unclear, mark it as null.
"""
        
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a JSON extraction assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        intent_data = response.choices[0].message.content
        return json.loads(intent_data)
    
    async def _handle_shift_request_intent(
        self,
        session: ConversationalSmsSession,
        intent: Dict
    ) -> Dict:
        """
        Handle initial shift request - validate and confirm.
        """
        # Validate extracted data
        if not intent.get("shift_type") or not intent.get("count"):
            # Ask clarifying question
            await self._send_sms(
                to_phone=session.facility_phone,
                message="I didn't quite catch that. Could you tell me: How many staff and what type (CNA, GNA, or LPN)?"
            )
            return {"status": "clarification_needed"}
        
        # Build confirmation message
        shift_summary = self._format_shift_summary(intent)
        confirmation_msg = f"Got it! You need:\n{shift_summary}\n\nShould I start matching nurses? Reply YES to confirm."
        
        # Update session
        session.session_state = "SHIFT_CREATION"
        session.intent_data = intent
        await session.save()
        
        await self._send_sms(
            to_phone=session.facility_phone,
            message=confirmation_msg
        )
        
        return {"status": "confirmation_requested", "intent": intent}
    
    async def _handle_shift_confirmation(
        self,
        session: ConversationalSmsSession,
        intent: Dict
    ) -> Dict:
        """
        Handle facility's confirmation - create shifts and start wave dispatch.
        """
        message_lower = intent.get("original_message", "").lower()
        
        if "yes" in message_lower or "confirm" in message_lower or "go ahead" in message_lower:
            # Create the shift(s)
            shift_ids = await self._create_shifts_from_intent(session.intent_data, session.facility_id)
            session.created_shifts = shift_ids
            session.session_state = "NURSE_DISPATCH"
            await session.save()
            
            # Start wave dispatch
            from .wave_match_dispatcher import WaveMatchDispatcher
            wave_dispatcher = WaveMatchDispatcher()
            await wave_dispatcher.start_autonomous_waves(shift_ids)
            
            await self._send_sms(
                to_phone=session.facility_phone,
                message=f"Perfect! I'm reaching out to qualified nurses now. I'll update you as they respond."
            )
            
            return {"status": "dispatch_started", "shift_ids": shift_ids}
        else:
            await self._send_sms(
                to_phone=session.facility_phone,
                message="No problem! Let me know if you need anything else."
            )
            session.session_state = "COMPLETE"
            session.completed_at = datetime.utcnow()
            await session.save()
            
            return {"status": "cancelled"}
    
    async def _send_sms(self, to_phone: str, message: str) -> str:
        """
        Send SMS via Twilio.
        """
        from twilio.rest import Client
        
        client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN")
        )
        
        msg = client.messages.create(
            body=message,
            from_=os.getenv("TWILIO_PHONE_NUMBER"),
            to=to_phone
        )
        
        return msg.sid
```

#### 1.4 API Endpoints

**New Route: `/api/v1/webhooks/twilio/sms-inbound`**

```python
# app/routers/twilio_webhooks.py

from fastapi import APIRouter, Form, Request
from app.services.conversational_dispatch_agent import ConversationalDispatchAgent

router = APIRouter()

@router.post("/webhooks/twilio/sms-inbound")
async def handle_inbound_sms(
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(...)
):
    """
    Twilio webhook for inbound SMS messages.
    
    Handles both facility shift requests and nurse responses.
    """
    agent = ConversationalDispatchAgent()
    
    # Check if this is from a facility or a nurse
    is_facility = await agent.is_facility_phone(From)
    
    if is_facility:
        result = await agent.process_inbound_facility_sms(
            from_phone=From,
            to_phone=To,
            message_body=Body
        )
    else:
        # Process as nurse response
        result = await agent.process_nurse_response_sms(
            from_phone=From,
            to_phone=To,
            message_body=Body
        )
    
    return {"status": "processed", "result": result}
```

#### 1.5 Configuration Variables

```bash
# .env additions
CONVERSATIONAL_SMS_ENABLED=true
CONVERSATIONAL_SMS_LLM_MODEL=gpt-4  # or claude-3-5-sonnet
CONVERSATIONAL_SMS_OPENAI_API_KEY=sk-...
CONVERSATIONAL_SMS_MAX_SESSION_HOURS=24
CONVERSATIONAL_SMS_AUTO_TIMEOUT_MINUTES=30
```

#### 1.6 Test Coverage

**File: `tests/test_conversational_dispatch_agent.py`**

```python
import pytest
from app.services.conversational_dispatch_agent import ConversationalDispatchAgent

@pytest.mark.asyncio
async def test_extract_intent_simple_request():
    agent = ConversationalDispatchAgent()
    intent = await agent._extract_intent(
        "Need 2 GNAs for night shift tonight",
        session=mock_session
    )
    assert intent["shift_type"] == "GNA"
    assert intent["count"] == 2
    assert intent["shift_time"] == "night"

@pytest.mark.asyncio
async def test_handle_shift_request_intent():
    agent = ConversationalDispatchAgent()
    result = await agent._handle_shift_request_intent(
        session=mock_session,
        intent={"shift_type": "CNA", "count": 1, "date": "2026-07-08"}
    )
    assert result["status"] == "confirmation_requested"

@pytest.mark.asyncio
async def test_facility_confirmation_yes():
    agent = ConversationalDispatchAgent()
    result = await agent._handle_shift_confirmation(
        session=mock_session_with_intent,
        intent={"original_message": "Yes, go ahead"}
    )
    assert result["status"] == "dispatch_started"
    assert len(result["shift_ids"]) > 0
```

**Expected test count:** 8 tests covering intent extraction, confirmation flows, error handling

---

## Feature 2: Dynamic Wave Match Logic

### Business Objective
Implement autonomous SMS waves that blast shift opportunities to qualified nurses in priority tiers, with intelligent retry patterns and real-time acceptance handling.

### Technical Architecture

#### 2.1 Wave Matching Strategy

```
Wave 1 (0-5 minutes):
  ├─ Top 5 nurses (highest reliability score, closest proximity)
  └─ Wait 5 minutes for responses

Wave 2 (5-10 minutes):
  ├─ Next 10 nurses (good reliability, reasonable proximity)
  └─ Wait 5 minutes for responses

Wave 3 (10-20 minutes):
  ├─ Expanded pool (all qualified, willing to travel)
  └─ Wait 10 minutes for responses

Wave 4 (20+ minutes):
  ├─ Premium rate increase (+$5/hr)
  └─ Re-ping Wave 1 & 2 with bonus incentive
```

#### 2.2 Database Schema (Alembic 029)

**New Table: `wave_dispatch_configs`**

```sql
CREATE TABLE wave_dispatch_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID REFERENCES facilities(id),
    wave_1_size INTEGER DEFAULT 5,
    wave_1_delay_seconds INTEGER DEFAULT 300,  -- 5 minutes
    wave_2_size INTEGER DEFAULT 10,
    wave_2_delay_seconds INTEGER DEFAULT 300,
    wave_3_size INTEGER DEFAULT 20,
    wave_3_delay_seconds INTEGER DEFAULT 600,  -- 10 minutes
    bonus_enabled BOOLEAN DEFAULT true,
    bonus_amount_per_hour DECIMAL(10,2) DEFAULT 5.00,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE wave_dispatch_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shift_id UUID REFERENCES shifts(id),
    current_wave INTEGER DEFAULT 1,
    total_dispatched INTEGER DEFAULT 0,
    total_accepted INTEGER DEFAULT 0,
    total_declined INTEGER DEFAULT 0,
    run_state VARCHAR(32) NOT NULL,  -- ACTIVE, FILLED, CANCELLED, TIMEOUT
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    INDEX idx_wave_run_shift (shift_id),
    INDEX idx_wave_run_state (run_state)
);
```

#### 2.3 Service Module: `app/services/wave_match_dispatcher.py`

**Core Functions:**

```python
from typing import List, Dict
from uuid import UUID
from datetime import datetime, timedelta
import asyncio

class WaveMatchDispatcher:
    """
    Autonomous SMS wave dispatcher for shift matching.
    """
    
    async def start_autonomous_waves(self, shift_ids: List[UUID]):
        """
        Start wave dispatching for one or more shifts.
        
        This runs as a background task and manages the entire wave lifecycle.
        """
        for shift_id in shift_ids:
            # Create wave run record
            wave_run = await self._create_wave_run(shift_id)
            
            # Launch background wave processor
            asyncio.create_task(self._execute_wave_sequence(wave_run))
    
    async def _execute_wave_sequence(self, wave_run: WaveDispatchRun):
        """
        Execute the full wave sequence until shift is filled or timeout.
        """
        shift = await Shift.get(wave_run.shift_id)
        config = await WaveDispatchConfig.get_for_facility(shift.facility_id)
        
        # Wave 1
        wave_1_nurses = await self._get_wave_candidates(shift, wave=1, size=config.wave_1_size)
        await self._dispatch_wave(wave_run, wave_1_nurses, wave_number=1)
        await asyncio.sleep(config.wave_1_delay_seconds)
        
        if await self._is_shift_filled(shift):
            return await self._complete_wave_run(wave_run, status="FILLED")
        
        # Wave 2
        wave_2_nurses = await self._get_wave_candidates(shift, wave=2, size=config.wave_2_size)
        await self._dispatch_wave(wave_run, wave_2_nurses, wave_number=2)
        await asyncio.sleep(config.wave_2_delay_seconds)
        
        if await self._is_shift_filled(shift):
            return await self._complete_wave_run(wave_run, status="FILLED")
        
        # Wave 3
        wave_3_nurses = await self._get_wave_candidates(shift, wave=3, size=config.wave_3_size)
        await self._dispatch_wave(wave_run, wave_3_nurses, wave_number=3)
        await asyncio.sleep(config.wave_3_delay_seconds)
        
        if await self._is_shift_filled(shift):
            return await self._complete_wave_run(wave_run, status="FILLED")
        
        # Wave 4 (bonus round)
        if config.bonus_enabled:
            await self._dispatch_bonus_wave(wave_run, wave_1_nurses + wave_2_nurses, config.bonus_amount_per_hour)
    
    async def _get_wave_candidates(
        self,
        shift: Shift,
        wave: int,
        size: int
    ) -> List[Provider]:
        """
        Get qualified nurses for this wave using existing matching engine.
        """
        from app.services.unified_matching_engine import UnifiedMatchingEngine
        
        matcher = UnifiedMatchingEngine()
        
        # Get all qualified candidates
        candidates = await matcher.get_qualified_candidates(
            shift_id=shift.id,
            license_type=shift.license_type_required,
            facility_id=shift.facility_id
        )
        
        # Score and rank
        scored_candidates = []
        for candidate in candidates:
            score = await self._calculate_wave_priority_score(candidate, shift, wave)
            scored_candidates.append((candidate, score))
        
        # Sort by score descending
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        
        # Return top N for this wave
        return [c[0] for c in scored_candidates[:size]]
    
    async def _calculate_wave_priority_score(
        self,
        provider: Provider,
        shift: Shift,
        wave: int
    ) -> float:
        """
        Calculate priority score for wave ordering.
        
        Factors:
        - Reliability score (40%)
        - Proximity to facility (30%)
        - Recent activity (20%)
        - Historical facility rating (10%)
        """
        from app.services.geo_matching import calculate_haversine_distance
        
        # Reliability score (0-100)
        reliability = await self._get_reliability_score(provider.id) or 50.0
        
        # Distance (miles)
        distance = calculate_haversine_distance(
            provider.latitude, provider.longitude,
            shift.facility.latitude, shift.facility.longitude
        )
        # Convert to score (closer = higher, max 50 miles for full points)
        proximity_score = max(0, 100 - (distance / 50.0 * 100))
        
        # Recent activity (shifts in last 7 days)
        recent_shifts = await self._count_recent_shifts(provider.id, days=7)
        activity_score = min(100, recent_shifts * 20)  # Cap at 100
        
        # Historical facility rating
        facility_rating = await self._get_facility_rating(provider.id, shift.facility_id) or 3.0
        facility_score = (facility_rating / 5.0) * 100
        
        # Weighted sum
        total_score = (
            reliability * 0.40 +
            proximity_score * 0.30 +
            activity_score * 0.20 +
            facility_score * 0.10
        )
        
        return total_score
    
    async def _dispatch_wave(
        self,
        wave_run: WaveDispatchRun,
        nurses: List[Provider],
        wave_number: int
    ):
        """
        Send SMS to all nurses in this wave.
        """
        shift = await Shift.get(wave_run.shift_id)
        
        for i, nurse in enumerate(nurses):
            message = self._build_shift_offer_sms(shift, nurse, wave_number)
            
            # Send via Twilio
            message_sid = await self._send_sms(
                to_phone=nurse.phone_number,
                message=message
            )
            
            # Log dispatch
            await NurseSmsDispatchLog.create(
                shift_id=shift.id,
                provider_id=nurse.id,
                wave_number=wave_number,
                dispatch_priority=i + 1,
                message_body=message,
                twilio_message_sid=message_sid
            )
            
            wave_run.total_dispatched += 1
        
        await wave_run.save()
    
    def _build_shift_offer_sms(
        self,
        shift: Shift,
        nurse: Provider,
        wave_number: int
    ) -> str:
        """
        Build personalized shift offer message.
        """
        return f"""Hi {nurse.first_name}! 👋

{shift.facility.name} needs a {shift.license_type_required} for:
📅 {shift.start_time.strftime('%a, %b %d')}
⏰ {shift.start_time.strftime('%I:%M %p')} - {shift.end_time.strftime('%I:%M %p')}
💰 ${shift.hourly_rate}/hr
📍 {shift.facility.city}, MD ({self._format_distance(nurse, shift.facility)} mi)

Reply YES to accept or NO to decline.
"""

    async def process_nurse_response_sms(
        self,
        from_phone: str,
        message_body: str
    ):
        """
        Process nurse's response to a shift offer.
        
        Handles: YES, NO, MAYBE, questions, etc.
        """
        # Find the nurse
        nurse = await Provider.get_by_phone(from_phone)
        if not nurse:
            return {"status": "unknown_nurse"}
        
        # Find most recent dispatch for this nurse
        recent_dispatch = await NurseSmsDispatchLog.get_most_recent_pending(nurse.id)
        if not recent_dispatch:
            await self._send_sms(
                to_phone=from_phone,
                message="Sorry, I don't have any active shift offers for you right now."
            )
            return {"status": "no_active_offer"}
        
        # Parse response intent
        message_lower = message_body.lower().strip()
        
        if any(word in message_lower for word in ["yes", "accept", "take it", "i'm in", "sounds good"]):
            return await self._handle_acceptance(recent_dispatch, nurse)
        
        elif any(word in message_lower for word in ["no", "decline", "can't", "cannot", "pass"]):
            return await self._handle_decline(recent_dispatch, nurse)
        
        else:
            # Unclear response - ask for clarification
            await self._send_sms(
                to_phone=from_phone,
                message="Just to confirm - are you saying YES to accept the shift, or NO to decline?"
            )
            return {"status": "clarification_needed"}
    
    async def _handle_acceptance(
        self,
        dispatch_log: NurseSmsDispatchLog,
        nurse: Provider
    ):
        """
        Handle nurse accepting the shift.
        """
        shift = await Shift.get(dispatch_log.shift_id)
        
        # Check if shift is still available
        if shift.status != "OPEN":
            await self._send_sms(
                to_phone=nurse.phone_number,
                message="Sorry, this shift was just filled by another nurse. I'll reach out about the next one!"
            )
            dispatch_log.response_intent = "ACCEPT_TOO_LATE"
            await dispatch_log.save()
            return {"status": "shift_already_filled"}
        
        # Lock the shift
        from app.services.shift_lock import lock_shift_for_provider
        lock_result = await lock_shift_for_provider(shift.id, nurse.id)
        
        if lock_result["success"]:
            # Send confirmation
            await self._send_sms(
                to_phone=nurse.phone_number,
                message=f"🎉 You got it! Shift confirmed at {shift.facility.name}. Check your portal for details and directions."
            )
            
            # Notify facility
            await self._notify_facility_shift_filled(shift, nurse)
            
            # Update dispatch log
            dispatch_log.response_intent = "ACCEPT"
            dispatch_log.responded_at = datetime.utcnow()
            await dispatch_log.save()
            
            # Complete the wave run
            wave_run = await WaveDispatchRun.get_by_shift(shift.id)
            await self._complete_wave_run(wave_run, status="FILLED")
            
            return {"status": "accepted", "shift_id": shift.id}
        else:
            # Lock failed (race condition)
            await self._send_sms(
                to_phone=nurse.phone_number,
                message="Looks like this shift was just claimed. I'll ping you for the next one!"
            )
            return {"status": "lock_failed"}
    
    async def _handle_decline(
        self,
        dispatch_log: NurseSmsDispatchLog,
        nurse: Provider
    ):
        """
        Handle nurse declining the shift.
        """
        await self._send_sms(
            to_phone=nurse.phone_number,
            message="No problem! Thanks for letting me know. 👍"
        )
        
        dispatch_log.response_intent = "DECLINE"
        dispatch_log.responded_at = datetime.utcnow()
        await dispatch_log.save()
        
        # Update wave run stats
        wave_run = await WaveDispatchRun.get_by_shift(dispatch_log.shift_id)
        wave_run.total_declined += 1
        await wave_run.save()
        
        return {"status": "declined"}
```

#### 2.4 Background Worker Integration

**File: `app/workers/wave_dispatcher_worker.py`**

```python
from celery import Celery
from app.services.wave_match_dispatcher import WaveMatchDispatcher

app = Celery('wave_dispatcher')

@app.task
async def process_wave_dispatch(shift_ids: List[str]):
    """
    Celery task for autonomous wave dispatching.
    """
    dispatcher = WaveMatchDispatcher()
    await dispatcher.start_autonomous_waves(shift_ids)
```

#### 2.5 Configuration

```bash
WAVE_DISPATCH_ENABLED=true
WAVE_DISPATCH_DEFAULT_WAVE_1_SIZE=5
WAVE_DISPATCH_DEFAULT_WAVE_2_SIZE=10
WAVE_DISPATCH_DEFAULT_WAVE_3_SIZE=20
WAVE_DISPATCH_BONUS_ENABLED=true
WAVE_DISPATCH_BONUS_AMOUNT=5.00
```

#### 2.6 Test Coverage

**File: `tests/test_wave_match_dispatcher.py`**

Expected: 10 tests covering wave sequencing, priority scoring, acceptance/decline handling

---

## Feature 3: Smart Document Extraction (Computer Vision)

### Business Objective
Automate credential document processing using computer vision OCR to extract expiration dates from CPR cards, TB tests, driver's licenses, and flag fraudulent or expired documents.

### Technical Architecture

#### 3.1 Document Processing Pipeline

```
┌──────────────────┐
│ Document Upload  │ ← Mobile photo or PDF
│ (Provider Portal)│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Image Quality    │ ← Blur detection, resolution check
│ Validation       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ OCR Extraction   │ ← AWS Textract / Google Vision
│ (Text + Dates)   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Entity Parsing   │ ← Extract expiration dates, license numbers
│ & Validation     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Fraud Detection  │ ← Metadata analysis, pattern matching
│ Heuristics       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Credential       │
│ Record Update    │
└──────────────────┘
```

#### 3.2 Database Schema (Alembic 030)

**New Table: `document_extraction_logs`**

```sql
CREATE TABLE document_extraction_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID REFERENCES providers(id),
    document_type VARCHAR(32) NOT NULL,  -- CPR_CARD, TB_TEST, DRIVERS_LICENSE, NURSING_LICENSE
    uploaded_file_path TEXT NOT NULL,
    ocr_service VARCHAR(32),             -- AWS_TEXTRACT, GOOGLE_VISION, TESSERACT
    extracted_text TEXT,
    extracted_entities JSONB,            -- Structured data (expiration dates, numbers, etc.)
    expiration_date DATE,
    quality_score DECIMAL(5,2),          -- 0-100
    fraud_flags JSONB,                   -- Array of fraud indicators
    extraction_status VARCHAR(32),       -- SUCCESS, BLUR_DETECTED, FRAUD_FLAGGED, EXPIRED, PARSING_FAILED
    processed_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_extraction_provider (provider_id),
    INDEX idx_extraction_type (document_type),
    INDEX idx_extraction_status (extraction_status)
);
```

**Update Table: `license_verification_logs`**

```sql
ALTER TABLE license_verification_logs
ADD COLUMN document_extraction_id UUID REFERENCES document_extraction_logs(id);
```

#### 3.3 Service Module: `app/services/smart_document_extractor.py`

**Core Functions:**

```python
import boto3
from PIL import Image
import io
from datetime import datetime, date
import re
from typing import Dict, Optional, List

class SmartDocumentExtractor:
    """
    Computer vision-powered document extraction and validation.
    """
    
    def __init__(self):
        self.textract_client = boto3.client('textract', region_name='us-east-1')
    
    async def process_document(
        self,
        provider_id: UUID,
        document_type: str,
        file_path: str
    ) -> Dict:
        """
        Main entry point for document processing.
        
        Returns:
        {
            "success": bool,
            "expiration_date": date or None,
            "fraud_flags": List[str],
            "quality_score": float,
            "extraction_log_id": UUID
        }
        """
        # Step 1: Image quality validation
        quality_result = await self._validate_image_quality(file_path)
        if not quality_result["passed"]:
            return await self._log_extraction_failure(
                provider_id, document_type, file_path,
                status="BLUR_DETECTED",
                fraud_flags=["LOW_QUALITY_IMAGE"]
            )
        
        # Step 2: OCR extraction
        extracted_text = await self._extract_text_aws_textract(file_path)
        
        # Step 3: Parse entities
        entities = await self._parse_document_entities(extracted_text, document_type)
        
        # Step 4: Fraud detection
        fraud_flags = await self._detect_fraud_indicators(file_path, extracted_text, entities)
        
        # Step 5: Validate expiration
        expiration_date = entities.get("expiration_date")
        if expiration_date and expiration_date < date.today():
            fraud_flags.append("DOCUMENT_EXPIRED")
        
        # Step 6: Log extraction
        extraction_log = await self._log_extraction(
            provider_id=provider_id,
            document_type=document_type,
            file_path=file_path,
            extracted_text=extracted_text,
            entities=entities,
            quality_score=quality_result["score"],
            fraud_flags=fraud_flags,
            status="FRAUD_FLAGGED" if fraud_flags else "SUCCESS"
        )
        
        # Step 7: Update credential records if successful
        if not fraud_flags and expiration_date:
            await self._update_credential_record(provider_id, document_type, expiration_date, extraction_log.id)
        
        return {
            "success": len(fraud_flags) == 0,
            "expiration_date": expiration_date,
            "fraud_flags": fraud_flags,
            "quality_score": quality_result["score"],
            "extraction_log_id": extraction_log.id
        }
    
    async def _validate_image_quality(self, file_path: str) -> Dict:
        """
        Detect blur and low resolution.
        
        Uses Laplacian variance for blur detection.
        """
        import cv2
        import numpy as np
        
        # Load image
        image = cv2.imread(file_path)
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Compute Laplacian variance (blur metric)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        # Threshold: below 100 is considered blurry
        is_blurry = laplacian_var < 100
        
        # Check resolution
        height, width = image.shape[:2]
        is_low_res = width < 800 or height < 600
        
        # Calculate overall quality score
        blur_score = min(100, laplacian_var / 5.0)  # Normalize to 0-100
        res_score = min(100, (width * height) / 10000.0)
        quality_score = (blur_score * 0.6) + (res_score * 0.4)
        
        return {
            "passed": not is_blurry and not is_low_res,
            "score": quality_score,
            "blur_detected": is_blurry,
            "low_resolution": is_low_res,
            "laplacian_variance": laplacian_var
        }
    
    async def _extract_text_aws_textract(self, file_path: str) -> str:
        """
        Extract text using AWS Textract.
        """
        with open(file_path, 'rb') as document:
            image_bytes = document.read()
        
        response = self.textract_client.detect_document_text(
            Document={'Bytes': image_bytes}
        )
        
        # Concatenate all detected text
        lines = []
        for block in response['Blocks']:
            if block['BlockType'] == 'LINE':
                lines.append(block['Text'])
        
        return '\n'.join(lines)
    
    async def _parse_document_entities(
        self,
        extracted_text: str,
        document_type: str
    ) -> Dict:
        """
        Parse structured entities from extracted text.
        
        Entities by document type:
        - CPR_CARD: expiration_date, issuing_org (AHA, Red Cross)
        - TB_TEST: test_date, result (negative/positive)
        - DRIVERS_LICENSE: license_number, expiration_date, dob
        - NURSING_LICENSE: license_number, expiration_date, license_type
        """
        entities = {}
        
        # Extract dates (MM/DD/YYYY or MM-DD-YYYY or similar)
        date_patterns = [
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',  # 12/31/2024 or 12-31-24
            r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',    # 2024-12-31
            r'([A-Za-z]{3,}\s+\d{1,2},?\s+\d{4})'  # December 31, 2024
        ]
        
        dates_found = []
        for pattern in date_patterns:
            matches = re.findall(pattern, extracted_text, re.IGNORECASE)
            dates_found.extend(matches)
        
        # Parse and find expiration date
        parsed_dates = []
        for date_str in dates_found:
            try:
                # Try multiple formats
                for fmt in ['%m/%d/%Y', '%m-%d-%Y', '%Y-%m-%d', '%m/%d/%y', '%B %d, %Y']:
                    try:
                        parsed = datetime.strptime(date_str, fmt).date()
                        parsed_dates.append(parsed)
                        break
                    except:
                        continue
            except:
                pass
        
        # Find the most likely expiration date (future date closest to today)
        future_dates = [d for d in parsed_dates if d > date.today()]
        if future_dates:
            entities["expiration_date"] = min(future_dates)
        elif parsed_dates:
            # If no future dates, take the latest date (might be expired)
            entities["expiration_date"] = max(parsed_dates)
        
        # Document-specific parsing
        if document_type == "CPR_CARD":
            if "american heart" in extracted_text.lower() or "aha" in extracted_text.lower():
                entities["issuing_org"] = "AHA"
            elif "red cross" in extracted_text.lower():
                entities["issuing_org"] = "Red Cross"
        
        elif document_type == "TB_TEST":
            if "negative" in extracted_text.lower():
                entities["result"] = "negative"
            elif "positive" in extracted_text.lower():
                entities["result"] = "positive"
        
        elif document_type in ["DRIVERS_LICENSE", "NURSING_LICENSE"]:
            # Extract license number (pattern: letters + numbers)
            license_patterns = [
                r'([A-Z]{1,2}\d{5,8})',  # MD format: M123456789
                r'(\d{7,10})'             # Numeric only
            ]
            for pattern in license_patterns:
                match = re.search(pattern, extracted_text)
                if match:
                    entities["license_number"] = match.group(1)
                    break
        
        return entities
    
    async def _detect_fraud_indicators(
        self,
        file_path: str,
        extracted_text: str,
        entities: Dict
    ) -> List[str]:
        """
        Detect potential fraud indicators.
        
        Checks:
        - Image metadata (edited in Photoshop, etc.)
        - Suspicious text patterns
        - Missing expected fields
        - Duplicate submissions
        """
        flags = []
        
        # Check image metadata for editing software
        from PIL import Image
        from PIL.ExifTags import TAGS
        
        try:
            image = Image.open(file_path)
            exif_data = image._getexif()
            
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag == "Software":
                        software_lower = str(value).lower()
                        if any(editor in software_lower for editor in ["photoshop", "gimp", "illustrator"]):
                            flags.append("IMAGE_EDITED_WITH_SOFTWARE")
        except:
            pass
        
        # Check for suspicious text patterns
        suspicious_keywords = ["sample", "specimen", "example", "template", "not valid"]
        for keyword in suspicious_keywords:
            if keyword in extracted_text.lower():
                flags.append(f"SUSPICIOUS_TEXT_{keyword.upper()}")
        
        # Check for missing expiration date
        if not entities.get("expiration_date"):
            flags.append("NO_EXPIRATION_DATE_FOUND")
        
        return flags
    
    async def _update_credential_record(
        self,
        provider_id: UUID,
        document_type: str,
        expiration_date: date,
        extraction_log_id: UUID
    ):
        """
        Update the provider's credential records.
        """
        from app.models import Provider, LicenseVerificationLog
        
        provider = await Provider.get(provider_id)
        
        # Map document type to credential field
        credential_mapping = {
            "CPR_CARD": "cpr_expiration",
            "TB_TEST": "tb_test_expiration",
            "DRIVERS_LICENSE": "drivers_license_expiration",
            "NURSING_LICENSE": "license_expiration"
        }
        
        field_name = credential_mapping.get(document_type)
        if field_name:
            setattr(provider, field_name, expiration_date)
            await provider.save()
        
        # Create verification log entry
        await LicenseVerificationLog.create(
            provider_id=provider_id,
            verification_type=f"DOCUMENT_EXTRACTION_{document_type}",
            status="VERIFIED",
            expiration_date=expiration_date,
            document_extraction_id=extraction_log_id,
            verified_at=datetime.utcnow()
        )
```

#### 3.4 API Endpoint

```python
# app/routers/credentials.py

@router.post("/api/v1/providers/{provider_id}/documents/upload")
async def upload_credential_document(
    provider_id: UUID,
    document_type: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Upload and process credential document with smart extraction.
    """
    # Save file temporarily
    file_path = f"/tmp/{provider_id}_{document_type}_{file.filename}"
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    # Process with smart extractor
    extractor = SmartDocumentExtractor()
    result = await extractor.process_document(
        provider_id=provider_id,
        document_type=document_type,
        file_path=file_path
    )
    
    # Clean up temp file
    os.remove(file_path)
    
    return result
```

#### 3.5 Configuration

```bash
SMART_DOCUMENT_EXTRACTION_ENABLED=true
SMART_DOCUMENT_OCR_SERVICE=AWS_TEXTRACT  # or GOOGLE_VISION
AWS_TEXTRACT_REGION=us-east-1
AWS_TEXTRACT_ACCESS_KEY=...
AWS_TEXTRACT_SECRET_KEY=...
SMART_DOCUMENT_BLUR_THRESHOLD=100.0
SMART_DOCUMENT_MIN_RESOLUTION_WIDTH=800
```

#### 3.6 Test Coverage

**File: `tests/test_smart_document_extractor.py`**

Expected: 12 tests covering OCR extraction, date parsing, fraud detection, quality validation

---

## Feature 4: Weekly MBON Auto-Sweeps

### Business Objective
Implement background verification sweeps that automatically check all active provider licenses against MBON disciplinary logs weekly, auto-suspending any revoked or restricted licenses.

### Technical Architecture

#### 4.1 Verification Sweep Pipeline

```
┌──────────────────────┐
│ Weekly Cron Trigger  │ ← Every Sunday at 2 AM
│ (Celery Beat)        │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Fetch All Active     │
│ Provider Licenses    │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Batch MBON API       │ ← Check 100 licenses at a time
│ Verification Calls   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Compare Against      │
│ Disciplinary Logs    │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Flag Changed         │
│ Statuses             │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Auto-Suspend         │
│ Revoked Licenses     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Send Alert Emails    │
│ to Affected Nurses   │
└──────────────────────┘
```

#### 4.2 Database Schema (Alembic 031)

**New Table: `mbon_sweep_runs`**

```sql
CREATE TABLE mbon_sweep_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_started_at TIMESTAMPTZ DEFAULT NOW(),
    run_completed_at TIMESTAMPTZ,
    total_licenses_checked INTEGER DEFAULT 0,
    total_suspensions INTEGER DEFAULT 0,
    total_warnings INTEGER DEFAULT 0,
    total_errors INTEGER DEFAULT 0,
    run_status VARCHAR(32) NOT NULL,  -- IN_PROGRESS, COMPLETED, FAILED
    error_message TEXT,
    INDEX idx_sweep_run_status (run_status),
    INDEX idx_sweep_run_date (run_started_at)
);

CREATE TABLE mbon_sweep_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sweep_run_id UUID REFERENCES mbon_sweep_runs(id),
    provider_id UUID REFERENCES providers(id),
    license_number VARCHAR(64),
    previous_status VARCHAR(32),
    new_status VARCHAR(32),
    action_taken VARCHAR(32),  -- SUSPENDED, WARNING_SENT, NO_ACTION
    mbon_api_response JSONB,
    checked_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_sweep_result_run (sweep_run_id),
    INDEX idx_sweep_result_provider (provider_id),
    INDEX idx_sweep_result_action (action_taken)
);
```

#### 4.3 Service Module: `app/services/mbon_auto_sweeper.py`

**Core Functions:**

```python
from typing import List, Dict
from uuid import UUID
from datetime import datetime
import asyncio

class MBONAutoSweeper:
    """
    Weekly automated MBON license verification sweeps.
    """
    
    async def run_weekly_sweep(self) -> Dict:
        """
        Execute full weekly MBON verification sweep.
        
        Returns summary of sweep results.
        """
        # Create sweep run record
        sweep_run = await MBONSweepRun.create(
            run_status="IN_PROGRESS"
        )
        
        try:
            # Get all active providers with Maryland licenses
            active_providers = await self._get_active_maryland_providers()
            
            # Batch process (100 at a time to avoid rate limits)
            batch_size = 100
            for i in range(0, len(active_providers), batch_size):
                batch = active_providers[i:i + batch_size]
                await self._process_provider_batch(batch, sweep_run)
                
                # Rate limit delay (1 second between batches)
                await asyncio.sleep(1)
            
            # Complete sweep
            sweep_run.run_status = "COMPLETED"
            sweep_run.run_completed_at = datetime.utcnow()
            await sweep_run.save()
            
            # Send summary report
            await self._send_sweep_summary_report(sweep_run)
            
            return {
                "success": True,
                "sweep_run_id": sweep_run.id,
                "total_checked": sweep_run.total_licenses_checked,
                "total_suspensions": sweep_run.total_suspensions,
                "total_warnings": sweep_run.total_warnings
            }
            
        except Exception as e:
            sweep_run.run_status = "FAILED"
            sweep_run.error_message = str(e)
            sweep_run.run_completed_at = datetime.utcnow()
            await sweep_run.save()
            
            # Alert ops team
            await self._send_sweep_failure_alert(sweep_run, str(e))
            
            raise
    
    async def _get_active_maryland_providers(self) -> List[Provider]:
        """
        Get all providers with active Maryland licenses.
        """
        from app.models import Provider
        
        providers = await Provider.filter(
            state="MD",
            is_active=True,
            license_number__isnull=False
        ).all()
        
        return providers
    
    async def _process_provider_batch(
        self,
        providers: List[Provider],
        sweep_run: MBONSweepRun
    ):
        """
        Process a batch of providers.
        """
        from app.services.credentialing_pipeline import CredentialCheckEngine
        
        credential_engine = CredentialCheckEngine()
        
        for provider in providers:
            try:
                # Call MBON API
                mbon_result = await credential_engine.verify_mbon_license(
                    license_number=provider.license_number,
                    license_type=provider.license_type
                )
                
                # Check if status changed
                previous_status = provider.license_status
                new_status = mbon_result.get("status", "UNKNOWN")
                
                action_taken = "NO_ACTION"
                
                # Auto-suspend if license is revoked, expired, or restricted
                if new_status in ["REVOKED", "EXPIRED", "RESTRICTED", "DISCIPLINARY"]:
                    if previous_status not in ["REVOKED", "EXPIRED", "RESTRICTED", "DISCIPLINARY"]:
                        # Status changed to bad - suspend provider
                        await self._suspend_provider(provider, new_status)
                        action_taken = "SUSPENDED"
                        sweep_run.total_suspensions += 1
                        
                        # Send alert email to nurse
                        await self._send_license_suspension_alert(provider, new_status, mbon_result)
                
                elif new_status == "EXPIRING_SOON":
                    # Warn if license expires within 30 days
                    await self._send_license_expiration_warning(provider, mbon_result.get("expiration_date"))
                    action_taken = "WARNING_SENT"
                    sweep_run.total_warnings += 1
                
                # Log sweep result
                await MBONSweepResult.create(
                    sweep_run_id=sweep_run.id,
                    provider_id=provider.id,
                    license_number=provider.license_number,
                    previous_status=previous_status,
                    new_status=new_status,
                    action_taken=action_taken,
                    mbon_api_response=mbon_result
                )
                
                # Update provider's license status
                if new_status != previous_status:
                    provider.license_status = new_status
                    provider.license_last_verified = datetime.utcnow()
                    await provider.save()
                
                sweep_run.total_licenses_checked += 1
                
            except Exception as e:
                # Log error but continue processing
                await MBONSweepResult.create(
                    sweep_run_id=sweep_run.id,
                    provider_id=provider.id,
                    license_number=provider.license_number,
                    action_taken="ERROR",
                    mbon_api_response={"error": str(e)}
                )
                sweep_run.total_errors += 1
        
        await sweep_run.save()
    
    async def _suspend_provider(self, provider: Provider, reason: str):
        """
        Suspend provider and cancel all future shifts.
        """
        from app.models import Offer, Placement
        from app.services.compliance_audit_ledger import write_audit_event
        
        # Mark provider as suspended
        provider.is_active = False
        provider.suspension_reason = reason
        provider.suspended_at = datetime.utcnow()
        await provider.save()
        
        # Cancel all future offers and placements
        await Offer.filter(
            provider_id=provider.id,
            status="PENDING"
        ).update(status="CANCELLED", cancelled_reason="LICENSE_SUSPENDED")
        
        await Placement.filter(
            provider_id=provider.id,
            status="CONFIRMED",
            shift__start_time__gte=datetime.utcnow()
        ).update(status="CANCELLED", cancelled_reason="LICENSE_SUSPENDED")
        
        # Write to compliance audit ledger
        await write_audit_event(
            event_type="LICENSE_SUSPENSION",
            event_reason=reason,
            provider_id=provider.id,
            license_number=provider.license_number,
            payload={
                "suspension_reason": reason,
                "suspended_at": provider.suspended_at.isoformat(),
                "mbon_status": reason
            }
        )
    
    async def _send_license_suspension_alert(
        self,
        provider: Provider,
        new_status: str,
        mbon_result: Dict
    ):
        """
        Send email alert to suspended nurse.
        """
        from app.services.email_service import send_email
        
        subject = "URGENT: Your nursing license status has changed"
        body = f"""
Dear {provider.first_name},

Our weekly verification with the Maryland Board of Nursing shows your license status has changed to: {new_status}

License Number: {provider.license_number}
New Status: {new_status}
Verified: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}

Your account has been temporarily suspended until this issue is resolved.

Please contact the Maryland Board of Nursing immediately to resolve this issue. Once resolved, contact VettedMe support to reactivate your account.

MBON Contact: (410) 585-1900
MBON Website: https://mbon.maryland.gov

Thank you,
VettedMe Compliance Team
"""
        
        await send_email(
            to=provider.email,
            subject=subject,
            body=body
        )
    
    async def _send_license_expiration_warning(
        self,
        provider: Provider,
        expiration_date: date
    ):
        """
        Send warning about upcoming license expiration.
        """
        from app.services.email_service import send_email
        
        subject = "⚠️ Your nursing license expires soon"
        body = f"""
Dear {provider.first_name},

Your Maryland nursing license will expire on {expiration_date.strftime('%B %d, %Y')}.

License Number: {provider.license_number}
Expiration: {expiration_date.strftime('%B %d, %Y')}
Days Remaining: {(expiration_date - date.today()).days}

Please renew your license with the Maryland Board of Nursing as soon as possible to avoid suspension.

Renew online: https://mbon.maryland.gov

Thank you,
VettedMe Compliance Team
"""
        
        await send_email(
            to=provider.email,
            subject=subject,
            body=body
        )
    
    async def _send_sweep_summary_report(self, sweep_run: MBONSweepRun):
        """
        Send summary report to ops team.
        """
        from app.services.email_service import send_email
        
        subject = f"Weekly MBON Sweep Complete: {sweep_run.total_licenses_checked} licenses checked"
        body = f"""
Weekly MBON License Verification Sweep Completed

Run ID: {sweep_run.id}
Started: {sweep_run.run_started_at.strftime('%Y-%m-%d %H:%M')}
Completed: {sweep_run.run_completed_at.strftime('%Y-%m-%d %H:%M')}
Status: {sweep_run.run_status}

Results:
- Total Licenses Checked: {sweep_run.total_licenses_checked}
- Suspensions: {sweep_run.total_suspensions}
- Warnings Sent: {sweep_run.total_warnings}
- Errors: {sweep_run.total_errors}

View detailed results in the admin dashboard.
"""
        
        await send_email(
            to=os.getenv("OPS_TEAM_EMAIL"),
            subject=subject,
            body=body
        )
```

#### 4.4 Celery Beat Scheduler

**File: `app/celery_beat_schedule.py`**

```python
from celery import Celery
from celery.schedules import crontab

app = Celery('vettedcare')

app.conf.beat_schedule = {
    'weekly-mbon-sweep': {
        'task': 'app.tasks.run_mbon_weekly_sweep',
        'schedule': crontab(hour=2, minute=0, day_of_week='sunday'),  # Every Sunday at 2 AM
    },
}
```

**File: `app/tasks.py`**

```python
from celery import Celery
from app.services.mbon_auto_sweeper import MBONAutoSweeper

app = Celery('vettedcare')

@app.task
async def run_mbon_weekly_sweep():
    """
    Celery task for weekly MBON verification sweeps.
    """
    sweeper = MBONAutoSweeper()
    result = await sweeper.run_weekly_sweep()
    return result
```

#### 4.5 Configuration

```bash
MBON_AUTO_SWEEP_ENABLED=true
MBON_AUTO_SWEEP_SCHEDULE_CRON="0 2 * * 0"  # Every Sunday at 2 AM
MBON_AUTO_SWEEP_BATCH_SIZE=100
MBON_AUTO_SWEEP_RATE_LIMIT_SECONDS=1
MBON_AUTO_SUSPEND_ON_REVOKED=true
MBON_AUTO_WARN_EXPIRING_DAYS=30
```

#### 4.6 Test Coverage

**File: `tests/test_mbon_auto_sweeper.py`**

Expected: 8 tests covering sweep execution, suspension logic, warning emails, error handling

---

## Implementation Summary

### Total New Components

| Category | Count |
|----------|-------|
| Alembic Migrations | 4 (028-031) |
| Service Modules | 4 |
| API Endpoints | 3 |
| Background Workers | 2 |
| Database Tables | 9 |
| Test Files | 4 (38 total tests) |

### External Dependencies

```python
# requirements.txt additions
openai>=1.0.0              # or anthropic>=0.5.0
twilio>=8.0.0
boto3>=1.28.0              # AWS Textract
opencv-python>=4.8.0       # Image quality validation
pillow>=10.0.0             # Image processing
celery>=5.3.0              # Background workers
redis>=5.0.0               # Celery broker
```

### Configuration Summary

```bash
# .env additions for Tier 1

# Conversational SMS
CONVERSATIONAL_SMS_ENABLED=true
CONVERSATIONAL_SMS_LLM_MODEL=gpt-4
CONVERSATIONAL_SMS_OPENAI_API_KEY=sk-...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...

# Wave Dispatch
WAVE_DISPATCH_ENABLED=true
WAVE_DISPATCH_BONUS_ENABLED=true
WAVE_DISPATCH_BONUS_AMOUNT=5.00

# Smart Document Extraction
SMART_DOCUMENT_EXTRACTION_ENABLED=true
SMART_DOCUMENT_OCR_SERVICE=AWS_TEXTRACT
AWS_TEXTRACT_REGION=us-east-1
AWS_TEXTRACT_ACCESS_KEY=...
AWS_TEXTRACT_SECRET_KEY=...

# MBON Auto-Sweeps
MBON_AUTO_SWEEP_ENABLED=true
MBON_AUTO_SUSPEND_ON_REVOKED=true
MBON_AUTO_WARN_EXPIRING_DAYS=30

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

---

## Next Steps

1. Review and approve these technical specifications
2. Create Alembic migrations (028-031)
3. Implement service modules sequentially
4. Write comprehensive tests (target: 38 tests passing)
5. Deploy to staging for integration testing
6. Enable features in production with dry-run flags

**Estimated Development Time:** 25-30 days with 1 full-time engineer

Ready to start building? Which feature should we implement first?
