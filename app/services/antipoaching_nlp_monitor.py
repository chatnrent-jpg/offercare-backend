"""
Anti-Poaching NLP Monitor — Revenue Protection

Sprint: VCAI-TIER3-SPRINT-2026-07-07
Purpose: Detect off-platform hiring attempts to protect agency revenue.

Detection Patterns:
- Phone number exchanges
- "Hire me directly" language
- Cash payment offers
- "Cut out the middleman" phrases
- Personal contact info sharing
- Direct employment discussions

Risk Scoring:
- 0-30: Low risk (normal conversation)
- 31-70: Medium risk (monitor closely)
- 71-100: High risk (immediate action required)

Actions:
- Flag account for review
- Send warning to facility
- Trigger placement fee invoice
- Suspend messaging temporarily
"""

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import PoachingDetectionLog


@dataclass
class PoachingAnalysis:
    """Result of poaching risk analysis."""
    risk_detected: bool
    risk_score: float
    indicators: List[str]
    recommended_action: str


class AntiPoachingNLPMonitor:
    """
    NLP-based anti-poaching detection system.
    
    Main entry point: analyze_message(message, provider_id, facility_id)
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
    
    async def analyze_message(
        self,
        message: str,
        provider_id: Optional[UUID] = None,
        facility_id: Optional[UUID] = None,
        message_source: str = "SMS"
    ) -> PoachingAnalysis:
        """
        Analyze message for poaching indicators.
        
        Args:
            message: Message text
            provider_id: Provider UUID (if known)
            facility_id: Facility UUID (if known)
            message_source: SMS, APP_CHAT, EMAIL
        
        Returns:
            PoachingAnalysis with risk score and recommendations
        """
        if not settings.ANTIPOACHING_ENABLED:
            return PoachingAnalysis(
                risk_detected=False,
                risk_score=0.0,
                indicators=[],
                recommended_action="NONE"
            )
        
        indicators = []
        risk_score = 0.0
        
        # Pattern 1: Phone number exchange
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        if re.search(phone_pattern, message):
            indicators.append("PHONE_NUMBER_SHARED")
            risk_score += 25.0
        
        # Pattern 2: Direct hiring language
        direct_hire_keywords = [
            r'hire\s+(?:me|you)\s+directly',
            r'work\s+directly',
            r'cut\s+out\s+the\s+middleman',
            r'avoid\s+the\s+agency',
            r'save\s+(?:money|fees)',
            r'personal\s+arrangement'
        ]
        for pattern in direct_hire_keywords:
            if re.search(pattern, message, re.IGNORECASE):
                indicators.append("DIRECT_HIRE_LANGUAGE")
                risk_score += 30.0
                break
        
        # Pattern 3: Cash payment mentions
        cash_keywords = [r'cash', r'under\s+the\s+table', r'off\s+the\s+books']
        for pattern in cash_keywords:
            if re.search(pattern, message, re.IGNORECASE):
                indicators.append("CASH_PAYMENT_MENTION")
                risk_score += 20.0
                break
        
        # Pattern 4: Personal contact info
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        if re.search(email_pattern, message):
            indicators.append("EMAIL_ADDRESS_SHARED")
            risk_score += 15.0
        
        # Pattern 5: "Let's talk offline"
        offline_keywords = [
            r'talk\s+offline',
            r'discuss\s+privately',
            r'off\s+the\s+app',
            r'outside\s+(?:of\s+)?(?:the\s+)?platform'
        ]
        for pattern in offline_keywords:
            if re.search(pattern, message, re.IGNORECASE):
                indicators.append("OFFLINE_DISCUSSION")
                risk_score += 20.0
                break
        
        # Cap at 100
        risk_score = min(100.0, risk_score)
        
        # Determine action
        if risk_score >= settings.ANTIPOACHING_RISK_THRESHOLD:
            recommended_action = "FLAG_AND_ALERT"
        elif risk_score >= 40:
            recommended_action = "MONITOR"
        else:
            recommended_action = "NONE"
        
        # Log if risk detected
        if risk_score > 0:
            await self._log_detection(
                provider_id=provider_id,
                facility_id=facility_id,
                message_source=message_source,
                message_content=message,
                indicators=indicators,
                risk_score=risk_score,
                action_taken=recommended_action
            )
        
        risk_detected = risk_score >= settings.ANTIPOACHING_RISK_THRESHOLD
        
        if risk_detected:
            print(f"[ANTIPOACHING] High risk detected (score: {risk_score:.1f}): {indicators}")
        
        return PoachingAnalysis(
            risk_detected=risk_detected,
            risk_score=risk_score,
            indicators=indicators,
            recommended_action=recommended_action
        )
    
    async def _log_detection(
        self,
        provider_id: Optional[UUID],
        facility_id: Optional[UUID],
        message_source: str,
        message_content: str,
        indicators: List[str],
        risk_score: float,
        action_taken: str
    ):
        """Log poaching detection."""
        log = PoachingDetectionLog(
            provider_id=provider_id,
            facility_id=facility_id,
            message_source=message_source,
            message_content=message_content[:500],  # Truncate
            poaching_indicators=json.dumps(indicators),
            risk_score=Decimal(str(risk_score)),
            action_taken=action_taken
        )
        self.db.add(log)
        await self.db.commit()


# Convenience function
async def check_message_for_poaching(message: str, provider_id: UUID = None) -> PoachingAnalysis:
    """Check message for poaching (convenience wrapper)."""
    async with AntiPoachingNLPMonitor() as monitor:
        return await monitor.analyze_message(message, provider_id)
