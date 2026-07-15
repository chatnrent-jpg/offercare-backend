"""
VettedMe Webhook Delivery Engine

Handles webhook event creation, delivery, retries, and failure handling.

Features:
- HMAC SHA256 signature verification
- Exponential backoff retry (max 5 attempts)
- Dead letter queue for permanent failures
- Concurrent delivery to multiple endpoints
- Delivery statistics and monitoring

Event Types:
- credential.issued: New badge added
- credential.revoked: Badge revoked
- credential.expiring: Badge expires in 30 days
- credential.expired: Badge has expired
- passport.created: New passport issued
- passport.suspended: Passport suspended
- verification.completed: Verification API call processed
"""

import hmac
import hashlib
import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from uuid import UUID
import httpx
from sqlalchemy.orm import Session

from app.models.webhook import WebhookSubscription, WebhookDelivery, WebhookEvent
from app.models.passport import Passport, CredentialBadge


class WebhookDeliveryEngine:
    """
    Core engine for delivering webhook events to external endpoints.
    
    Handles:
    1. Event creation
    2. Endpoint discovery (which subscriptions care about this event?)
    3. Payload construction
    4. HMAC signature generation
    5. HTTP delivery
    6. Retry logic with exponential backoff
    7. Failure tracking
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.timeout = 30  # 30 second timeout per request
        self.max_retries = 5
    
    async def create_event(
        self,
        event_type: str,
        event_data: Dict,
        passport_id: Optional[UUID] = None,
        badge_id: Optional[UUID] = None
    ) -> WebhookEvent:
        """
        Create a webhook event and queue it for delivery.
        
        Args:
            event_type: Type of event (e.g., "credential.issued")
            event_data: Event payload data
            passport_id: Optional passport ID
            badge_id: Optional badge ID
        
        Returns:
            Created WebhookEvent instance
        """
        # Create event record
        event = WebhookEvent(
            event_type=event_type,
            event_data=event_data,
            passport_id=passport_id,
            badge_id=badge_id,
            status="PENDING"
        )
        
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        
        # Queue for delivery (in background)
        asyncio.create_task(self._process_event(event.id))
        
        return event
    
    async def _process_event(self, event_id: UUID):
        """
        Process a webhook event - find subscriptions and deliver.
        
        Args:
            event_id: UUID of the event to process
        """
        # Fetch event
        event = self.db.query(WebhookEvent).filter_by(id=event_id).first()
        if not event:
            return
        
        # Mark as processing
        event.status = "PROCESSING"
        self.db.commit()
        
        # Find subscriptions for this event type
        subscriptions = self.db.query(WebhookSubscription).filter(
            WebhookSubscription.status == "ACTIVE"
        ).all()
        
        # Filter subscriptions that care about this event
        interested_subscriptions = [
            sub for sub in subscriptions
            if sub.subscribes_to(event.event_type)
        ]
        
        event.total_subscriptions = len(interested_subscriptions)
        self.db.commit()
        
        if not interested_subscriptions:
            # No subscriptions, mark as completed
            event.status = "COMPLETED"
            event.processed_at = datetime.now(timezone.utc)
            self.db.commit()
            return
        
        # Deliver to all subscriptions concurrently
        delivery_tasks = [
            self._deliver_to_subscription(event, subscription)
            for subscription in interested_subscriptions
        ]
        
        results = await asyncio.gather(*delivery_tasks, return_exceptions=True)
        
        # Update event stats
        event.successful_deliveries = sum(1 for r in results if r is True)
        event.failed_deliveries = sum(1 for r in results if r is not True)
        event.status = "COMPLETED"
        event.processed_at = datetime.now(timezone.utc)
        self.db.commit()
    
    async def _deliver_to_subscription(
        self,
        event: WebhookEvent,
        subscription: WebhookSubscription
    ) -> bool:
        """
        Deliver an event to a specific webhook subscription.
        
        Args:
            event: WebhookEvent to deliver
            subscription: WebhookSubscription to deliver to
        
        Returns:
            bool: True if delivery succeeded, False otherwise
        """
        # Build payload
        payload = self._build_payload(event, subscription)
        
        # Generate signature
        signature = self._generate_signature(payload, subscription.secret)
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "VettedMe-Webhook/1.0",
            "X-VettedMe-Event": event.event_type,
            "X-VettedMe-Signature": signature,
            "X-VettedMe-Delivery": str(event.id)
        }
        
        # Create delivery record
        delivery = WebhookDelivery(
            subscription_id=subscription.id,
            event_id=event.id,
            attempt_number=1,
            status="PENDING",
            request_body=payload,
            request_headers=headers
        )
        
        self.db.add(delivery)
        self.db.commit()
        self.db.refresh(delivery)
        
        # Attempt delivery
        success = await self._attempt_delivery(delivery, subscription.url, payload, headers)
        
        # Update subscription stats
        subscription.total_deliveries += 1
        subscription.last_delivery_at = datetime.now(timezone.utc)
        
        if success:
            subscription.successful_deliveries += 1
            subscription.last_success_at = datetime.now(timezone.utc)
        else:
            subscription.failed_deliveries += 1
            subscription.last_failure_at = datetime.now(timezone.utc)
        
        self.db.commit()
        
        return success
    
    async def _attempt_delivery(
        self,
        delivery: WebhookDelivery,
        url: str,
        payload: Dict,
        headers: Dict
    ) -> bool:
        """
        Attempt to deliver a webhook to an endpoint.
        
        Args:
            delivery: WebhookDelivery record
            url: Endpoint URL
            payload: JSON payload
            headers: HTTP headers
        
        Returns:
            bool: True if delivery succeeded (2xx response), False otherwise
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers
                )
                
                end_time = datetime.now(timezone.utc)
                response_time_ms = int((end_time - start_time).total_seconds() * 1000)
                
                # Update delivery record
                delivery.response_code = response.status_code
                delivery.response_body = response.text[:10000]  # Truncate to 10KB
                delivery.response_time_ms = response_time_ms
                delivery.delivered_at = end_time
                
                # Check if successful (2xx status code)
                if 200 <= response.status_code < 300:
                    delivery.status = "SUCCESS"
                    self.db.commit()
                    return True
                else:
                    # Non-2xx response, treat as failure
                    delivery.status = "FAILED"
                    delivery.error_message = f"HTTP {response.status_code}: {response.text[:500]}"
                    
                    # Schedule retry if applicable
                    if delivery.attempt_number < self.max_retries:
                        delivery.will_retry = True
                        delay_seconds = self._calculate_retry_delay(delivery.attempt_number)
                        delivery.retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
                    else:
                        delivery.status = "DEAD_LETTER"
                    
                    self.db.commit()
                    return False
        
        except Exception as e:
            # Network error, timeout, etc.
            end_time = datetime.now(timezone.utc)
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            delivery.status = "FAILED"
            delivery.error_message = f"Exception: {str(e)}"
            delivery.response_time_ms = response_time_ms
            
            # Schedule retry if applicable
            if delivery.attempt_number < self.max_retries:
                delivery.will_retry = True
                delay_seconds = self._calculate_retry_delay(delivery.attempt_number)
                delivery.retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
            else:
                delivery.status = "DEAD_LETTER"
            
            self.db.commit()
            return False
    
    def _build_payload(self, event: WebhookEvent, subscription: WebhookSubscription) -> Dict:
        """
        Build the JSON payload to send to the webhook endpoint.
        
        Args:
            event: WebhookEvent to send
            subscription: WebhookSubscription receiving the event
        
        Returns:
            Dict: JSON payload
        """
        return {
            "event_id": str(event.id),
            "event_type": event.event_type,
            "timestamp": event.created_at.isoformat(),
            "data": event.event_data,
            "passport_id": str(event.passport_id) if event.passport_id else None,
            "badge_id": str(event.badge_id) if event.badge_id else None
        }
    
    def _generate_signature(self, payload: Dict, secret: str) -> str:
        """
        Generate HMAC SHA256 signature for payload verification.
        
        Args:
            payload: JSON payload dict
            secret: HMAC secret key
        
        Returns:
            str: Hex-encoded signature
        """
        # Serialize payload to canonical JSON (sorted keys)
        canonical_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        
        # Generate HMAC
        signature = hmac.new(
            secret.encode('utf-8'),
            canonical_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _calculate_retry_delay(self, attempt_number: int) -> int:
        """
        Calculate retry delay using exponential backoff.
        
        Formula: min(60 * 2^attempt, 3600) seconds
        
        Delays:
        - Attempt 1: 2 minutes
        - Attempt 2: 4 minutes
        - Attempt 3: 8 minutes
        - Attempt 4: 16 minutes
        - Attempt 5: 32 minutes (max 1 hour)
        
        Args:
            attempt_number: Current attempt number (1-indexed)
        
        Returns:
            int: Delay in seconds
        """
        delay = min(60 * (2 ** attempt_number), 3600)
        return delay
    
    async def retry_failed_deliveries(self):
        """
        Background task to retry failed webhook deliveries.
        
        Should be called periodically (e.g., every minute) by a cron job.
        """
        now = datetime.now(timezone.utc)
        
        # Find deliveries ready for retry
        retryable_deliveries = self.db.query(WebhookDelivery).filter(
            WebhookDelivery.status == "FAILED",
            WebhookDelivery.will_retry == True,
            WebhookDelivery.retry_at <= now
        ).all()
        
        for delivery in retryable_deliveries:
            # Increment attempt number
            delivery.attempt_number += 1
            delivery.status = "PENDING"
            self.db.commit()
            
            # Get subscription and event
            subscription = self.db.query(WebhookSubscription).filter_by(id=delivery.subscription_id).first()
            event = self.db.query(WebhookEvent).filter_by(id=delivery.event_id).first()
            
            if not subscription or not event:
                continue
            
            # Rebuild payload and signature
            payload = self._build_payload(event, subscription)
            signature = self._generate_signature(payload, subscription.secret)
            
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "VettedMe-Webhook/1.0",
                "X-VettedMe-Event": event.event_type,
                "X-VettedMe-Signature": signature,
                "X-VettedMe-Delivery": str(event.id),
                "X-VettedMe-Retry": str(delivery.attempt_number)
            }
            
            # Attempt delivery
            await self._attempt_delivery(delivery, subscription.url, payload, headers)


# ============================================================================
# Event Helpers
# ============================================================================

async def emit_credential_issued(
    db: Session,
    badge: CredentialBadge
):
    """
    Emit webhook event when a credential is issued.
    
    Args:
        db: Database session
        badge: Newly created CredentialBadge
    """
    engine = WebhookDeliveryEngine(db)
    
    await engine.create_event(
        event_type="credential.issued",
        event_data={
            "badge_id": str(badge.id),
            "passport_id": str(badge.passport_id),
            "badge_type": badge.badge_type,
            "verified_at": badge.verified_at.isoformat(),
            "expires_at": badge.expires_at.isoformat() if badge.expires_at else None
        },
        passport_id=badge.passport_id,
        badge_id=badge.id
    )


async def emit_credential_revoked(
    db: Session,
    badge: CredentialBadge,
    reason: str
):
    """
    Emit webhook event when a credential is revoked.
    
    Args:
        db: Database session
        badge: Revoked CredentialBadge
        reason: Revocation reason
    """
    engine = WebhookDeliveryEngine(db)
    
    await engine.create_event(
        event_type="credential.revoked",
        event_data={
            "badge_id": str(badge.id),
            "passport_id": str(badge.passport_id),
            "badge_type": badge.badge_type,
            "revoked_at": badge.revoked_at.isoformat() if badge.revoked_at else datetime.now(timezone.utc).isoformat(),
            "reason": reason
        },
        passport_id=badge.passport_id,
        badge_id=badge.id
    )


async def emit_passport_created(
    db: Session,
    passport: Passport
):
    """
    Emit webhook event when a passport is created.
    
    Args:
        db: Database session
        passport: Newly created Passport
    """
    engine = WebhookDeliveryEngine(db)
    
    await engine.create_event(
        event_type="passport.created",
        event_data={
            "passport_id": str(passport.id),
            "user_id": str(passport.user_id),
            "issued_at": passport.issued_at.isoformat(),
            "expires_at": passport.expires_at.isoformat(),
            "trust_score": passport.trust_score
        },
        passport_id=passport.id
    )
