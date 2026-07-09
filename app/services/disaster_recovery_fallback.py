"""
Off-Grid Disaster Recovery Fallback Service.

Feature: Advanced Feature #11
Purpose: SMS-only failover mode when main platform is down.
"""

import logging
from datetime import datetime, timezone
from typing import Dict

import httpx
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)


class DisasterRecoveryFallbackService:
    """SMS-only emergency mode for platform outages."""
    
    def __init__(self, db: Session):
        self.db = db
        self.enabled = getattr(settings, "DISASTER_RECOVERY_ENABLED", True)
        self.health_check_url = getattr(settings, "PLATFORM_HEALTH_CHECK_URL", None)
    
    async def check_platform_health(self) -> bool:
        """Check if main platform is operational."""
        if not self.health_check_url:
            return True  # Assume healthy
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.health_check_url)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"[DR] Health check failed: {e}")
            return False
    
    async def activate_sms_only_mode(self) -> Dict:
        """Activate emergency SMS-only coordination mode."""
        logger.critical("[DR] ACTIVATING SMS-ONLY EMERGENCY MODE")
        
        try:
            from app.services.sms import send_sms
            
            # Alert coordinators
            coordinator_numbers = getattr(settings, "EMERGENCY_COORDINATOR_PHONES", [])
            
            for phone in coordinator_numbers:
                send_sms(
                    phone,
                    "🚨 EMERGENCY: VettedPulse platform is down. "
                    "SMS-only mode activated. Check emergency playbook."
                )
            
            return {
                "status": "SMS_ONLY_MODE_ACTIVE",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "coordinators_alerted": len(coordinator_numbers)
            }
            
        except Exception as e:
            logger.error(f"[DR] Error activating failover: {e}")
            return {"status": "ERROR", "error": str(e)}
    
    async def monitor_and_failover(self) -> Dict:
        """Continuous monitoring with auto-failover."""
        is_healthy = await self.check_platform_health()
        
        if not is_healthy:
            return await self.activate_sms_only_mode()
        
        return {"status": "PLATFORM_HEALTHY"}
