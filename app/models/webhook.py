"""
VettedMe Webhook System - Database Models

Provides real-time event notifications to external platforms.

Events:
- credential.issued: New badge added to passport
- credential.revoked: Badge revoked
- credential.expiring: Badge expiring in 30 days
- credential.expired: Badge expired
- passport.created: New passport created
- passport.suspended: Passport status changed
- verification.completed: Verification request processed

Security:
- HMAC SHA256 signatures
- Retry with exponential backoff
- Dead letter queue for failed deliveries
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Integer, Boolean, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from app.database import Base


class WebhookSubscription(Base):
    """
    Webhook endpoint subscription configuration.
    
    External platforms register webhook URLs to receive real-time
    notifications about credential changes.
    """
    __tablename__ = "webhook_subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=False)
    url = Column(String(2048), nullable=False, doc="HTTPS endpoint to receive webhooks")
    secret = Column(String(64), nullable=False, doc="HMAC secret for signature verification")
    events = Column(JSONB, nullable=False, doc="List of subscribed event types")
    description = Column(String(255), nullable=True, doc="Human-readable description")
    
    # Status & metadata
    status = Column(String(20), nullable=False, default="ACTIVE", doc="ACTIVE, PAUSED, or DISABLED")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Delivery stats
    total_deliveries = Column(Integer, default=0, nullable=False)
    successful_deliveries = Column(Integer, default=0, nullable=False)
    failed_deliveries = Column(Integer, default=0, nullable=False)
    last_delivery_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    deliveries = relationship("WebhookDelivery", back_populates="subscription", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<WebhookSubscription(id={self.id}, url={self.url}, status={self.status})>"
    
    def is_active(self) -> bool:
        """Check if subscription is active and should receive events."""
        return self.status == "ACTIVE"
    
    def subscribes_to(self, event_type: str) -> bool:
        """Check if subscription wants this event type."""
        return event_type in self.events


class WebhookDelivery(Base):
    """
    Individual webhook delivery attempt.
    
    Tracks every attempt to deliver an event to a webhook endpoint,
    including retries, response codes, and error details.
    """
    __tablename__ = "webhook_deliveries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"), nullable=False)
    event_id = Column(UUID(as_uuid=True), ForeignKey("webhook_events.id", ondelete="CASCADE"), nullable=False)
    
    # Delivery details
    attempt_number = Column(Integer, nullable=False, default=1, doc="1-indexed attempt number (max 5)")
    status = Column(String(20), nullable=False, default="PENDING", doc="PENDING, SUCCESS, FAILED, or DEAD_LETTER")
    
    # Request/response
    request_body = Column(JSONB, nullable=False, doc="Full webhook payload")
    request_headers = Column(JSONB, nullable=True, doc="HTTP headers sent")
    response_code = Column(Integer, nullable=True, doc="HTTP status code received")
    response_body = Column(Text, nullable=True, doc="Response body (truncated to 10KB)")
    response_time_ms = Column(Integer, nullable=True, doc="Response time in milliseconds")
    
    # Error tracking
    error_message = Column(Text, nullable=True, doc="Error message if delivery failed")
    will_retry = Column(Boolean, default=False, nullable=False, doc="Whether this delivery will be retried")
    retry_at = Column(DateTime(timezone=True), nullable=True, doc="When to retry (exponential backoff)")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    delivered_at = Column(DateTime(timezone=True), nullable=True, doc="When delivery succeeded")
    
    # Relationships
    subscription = relationship("WebhookSubscription", back_populates="deliveries")
    event = relationship("WebhookEvent", back_populates="deliveries")
    
    def __repr__(self):
        return f"<WebhookDelivery(id={self.id}, status={self.status}, attempt={self.attempt_number})>"
    
    def is_retryable(self) -> bool:
        """Check if this delivery can be retried."""
        return (
            self.status == "FAILED" and
            self.attempt_number < 5 and
            self.will_retry
        )


class WebhookEvent(Base):
    """
    Webhook event to be delivered.
    
    Represents a single event (credential change, verification, etc.)
    that needs to be sent to all subscribed webhooks.
    """
    __tablename__ = "webhook_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False, doc="Event type (e.g., 'credential.issued')")
    event_data = Column(JSONB, nullable=False, doc="Full event payload")
    
    # Related entities
    passport_id = Column(UUID(as_uuid=True), nullable=True, doc="Related passport ID (if applicable)")
    badge_id = Column(UUID(as_uuid=True), nullable=True, doc="Related badge ID (if applicable)")
    
    # Status
    status = Column(String(20), nullable=False, default="PENDING", doc="PENDING, PROCESSING, COMPLETED, or FAILED")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Stats
    total_subscriptions = Column(Integer, default=0, nullable=False, doc="Number of webhooks to notify")
    successful_deliveries = Column(Integer, default=0, nullable=False)
    failed_deliveries = Column(Integer, default=0, nullable=False)
    
    # Relationships
    deliveries = relationship("WebhookDelivery", back_populates="event", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<WebhookEvent(id={self.id}, type={self.event_type}, status={self.status})>"
    
    def is_complete(self) -> bool:
        """Check if all deliveries have been attempted."""
        return self.status == "COMPLETED" or self.status == "FAILED"
