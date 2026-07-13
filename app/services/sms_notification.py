"""
Twilio SMS Notification Template Engine
Handles compliance text notifications and audit-trail logging for OHCQ placement verification

Maryland Department of Health compliance notification system
"""

import logging
from typing import Any
from twilio.rest import Client
from pydantic import BaseModel

logger = logging.getLogger("SMS_Engine")


class SMSPayload(BaseModel):
    """
    Structured payload for compliance SMS notifications.
    
    Fields:
        phone_number: Recipient phone number (E.164 format)
        professional_name: Healthcare professional full name
        license_type: License classification (RN, LPN, CNA, GNA)
        license_number: State-issued license number
        facility_name: Placement facility name
    """
    phone_number: str
    professional_name: str
    license_type: str
    license_number: str
    facility_name: str


class TwilioComplianceEngine:
    """
    Production-grade Twilio SMS engine for OHCQ compliance notifications.
    
    Features:
    - MBON verification status notifications
    - Audit-trail logging for compliance tracking
    - Sandbox mode for testing without live sends
    - Maryland state workforce placement mandate compliance
    """
    
    def __init__(self, account_sid: str, auth_token: str, messaging_service_sid: str):
        """
        Initialize Twilio client with credentials.
        
        Args:
            account_sid: Twilio account SID
            auth_token: Twilio auth token
            messaging_service_sid: Twilio messaging service SID
        """
        self.client = Client(account_sid, auth_token) if account_sid and auth_token else None
        self.messaging_service_sid = messaging_service_sid

    def build_ohcq_placement_template(self, data: SMSPayload) -> str:
        """
        Generates mandatory compliance notification text matching 
        Maryland state workforce placement mandates.
        
        Template includes:
        - Professional identification
        - License verification status
        - MBON registry confirmation
        - Facility placement details
        - OHCQ audit trail reference
        
        Args:
            data: SMSPayload with notification details
        
        Returns:
            Formatted compliance notification message
        """
        return (
            f"VettedMe Alert: Professional {data.professional_name} "
            f"({data.license_type} #{data.license_number}) "
            f"has been verified through the MBON live registry and cleared for placement at {data.facility_name}. "
            f"OHCQ compliant audit record logged."
        )

    async def send_compliance_notification(self, payload: SMSPayload) -> dict[str, Any]:
        """
        Dispatches an audit-tracked SMS notification via the Twilio platform.
        
        Features:
        - Live Twilio API integration
        - Sandbox mode fallback for testing
        - Error handling and logging
        - Return includes SID for audit trail
        
        Args:
            payload: SMSPayload with notification data
        
        Returns:
            Dictionary with:
            - sid: Message SID (or mock ID in sandbox)
            - status: Message status (queued, sent, failed)
            - body: Message text sent
            - error: Error message if failed (optional)
        """
        message_body = self.build_ohcq_placement_template(payload)
        
        if not self.client:
            logger.warning(f"[SANDBOX MODE] Compliance SMS output: {message_body}")
            return {
                "sid": "mock_sms_sid_12345",
                "status": "queued",
                "body": message_body
            }

        try:
            message = self.client.messages.create(
                messaging_service_sid=self.messaging_service_sid,
                to=payload.phone_number,
                body=message_body
            )
            logger.info(
                f"SMS sent successfully to {payload.phone_number} | SID: {message.sid}"
            )
            return {
                "sid": message.sid,
                "status": message.status,
                "body": message_body
            }
        except Exception as e:
            logger.error(f"Failed to dispatch Twilio Compliance SMS: {str(e)}")
            return {
                "sid": None,
                "status": "failed",
                "error": str(e)
            }


def create_compliance_sms_engine(
    account_sid: str = None,
    auth_token: str = None,
    messaging_service_sid: str = None
) -> TwilioComplianceEngine:
    """
    Factory function to create a TwilioComplianceEngine instance.
    
    Args:
        account_sid: Twilio account SID (optional, defaults to sandbox)
        auth_token: Twilio auth token (optional, defaults to sandbox)
        messaging_service_sid: Messaging service SID (optional)
    
    Returns:
        Configured TwilioComplianceEngine instance
    """
    return TwilioComplianceEngine(
        account_sid=account_sid or "",
        auth_token=auth_token or "",
        messaging_service_sid=messaging_service_sid or ""
    )
