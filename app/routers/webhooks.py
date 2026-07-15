"""
VettedMe Webhook Management API

Allows API customers to:
- Subscribe to webhook events
- Manage webhook endpoints
- View delivery logs
- Test webhooks
- Regenerate secrets

Security:
- Only API key owners can manage their webhooks
- Secrets are generated cryptographically
- HMAC signatures prevent tampering
"""

import secrets
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, HttpUrl, Field

from app.database import get_db
from app.models.webhook import WebhookSubscription, WebhookDelivery, WebhookEvent
from app.models.passport import APIKey
from app.routers.passport import get_api_key_from_header

router = APIRouter(
    prefix="/api/v1/webhooks",
    tags=["Webhook Management"]
)


# ============================================================================
# Pydantic Schemas
# ============================================================================

class WebhookSubscriptionCreate(BaseModel):
    """Request schema for creating a webhook subscription."""
    url: HttpUrl = Field(description="HTTPS endpoint to receive webhooks (must be HTTPS)")
    events: List[str] = Field(description="List of event types to subscribe to", min_items=1)
    description: Optional[str] = Field(default=None, max_length=255, description="Optional description")


class WebhookSubscriptionResponse(BaseModel):
    """Response schema for webhook subscription details."""
    id: UUID
    url: str
    secret: str | None = Field(default=None, description="Only returned on creation")
    events: List[str]
    description: str | None
    status: str
    created_at: str
    total_deliveries: int
    successful_deliveries: int
    failed_deliveries: int
    last_delivery_at: str | None
    last_success_at: str | None
    last_failure_at: str | None


class WebhookSubscriptionUpdate(BaseModel):
    """Request schema for updating a webhook subscription."""
    url: Optional[HttpUrl] = None
    events: Optional[List[str]] = Field(default=None, min_items=1)
    description: Optional[str] = Field(default=None, max_length=255)
    status: Optional[str] = Field(default=None, pattern="^(ACTIVE|PAUSED|DISABLED)$")


class WebhookDeliveryResponse(BaseModel):
    """Response schema for webhook delivery details."""
    id: UUID
    subscription_id: UUID
    event_id: UUID
    attempt_number: int
    status: str
    request_body: dict
    response_code: int | None
    response_body: str | None
    response_time_ms: int | None
    error_message: str | None
    will_retry: bool
    retry_at: str | None
    created_at: str
    delivered_at: str | None


class WebhookEventResponse(BaseModel):
    """Response schema for webhook event details."""
    id: UUID
    event_type: str
    event_data: dict
    passport_id: str | None
    badge_id: str | None
    status: str
    created_at: str
    processed_at: str | None
    total_subscriptions: int
    successful_deliveries: int
    failed_deliveries: int


class WebhookTestPayload(BaseModel):
    """Request schema for testing a webhook."""
    event_type: str = Field(default="webhook.test", description="Event type for test")
    test_data: dict = Field(default_factory=dict, description="Custom test data")


# ============================================================================
# Webhook Subscription Management
# ============================================================================

@router.post(
    "/subscriptions",
    response_model=WebhookSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create webhook subscription"
)
async def create_webhook_subscription(
    payload: WebhookSubscriptionCreate,
    api_key: APIKey = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    Subscribe to webhook events.
    
    **Available Event Types:**
    - `credential.issued`: New badge added to passport
    - `credential.revoked`: Badge revoked
    - `credential.expiring`: Badge expiring in 30 days
    - `credential.expired`: Badge has expired
    - `passport.created`: New passport issued
    - `passport.suspended`: Passport suspended
    - `verification.completed`: Verification API call processed
    
    **Security:**
    - Webhook secret is generated automatically
    - Use secret to verify HMAC SHA256 signature
    - Signature is in `X-VettedMe-Signature` header
    
    **Example:**
    ```python
    import hmac
    import hashlib
    import json
    
    def verify_webhook(payload, signature, secret):
        canonical_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        expected = hmac.new(
            secret.encode('utf-8'),
            canonical_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected)
    ```
    """
    # Validate URL is HTTPS
    if not str(payload.url).startswith('https://'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook URL must use HTTPS for security"
        )
    
    # Generate secret
    webhook_secret = secrets.token_urlsafe(32)
    
    # Create subscription
    subscription = WebhookSubscription(
        api_key_id=api_key.id,
        url=str(payload.url),
        secret=webhook_secret,
        events=payload.events,
        description=payload.description,
        status="ACTIVE"
    )
    
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    
    return WebhookSubscriptionResponse(
        id=subscription.id,
        url=subscription.url,
        secret=webhook_secret,  # Only returned on creation!
        events=subscription.events,
        description=subscription.description,
        status=subscription.status,
        created_at=subscription.created_at.isoformat(),
        total_deliveries=subscription.total_deliveries,
        successful_deliveries=subscription.successful_deliveries,
        failed_deliveries=subscription.failed_deliveries,
        last_delivery_at=subscription.last_delivery_at.isoformat() if subscription.last_delivery_at else None,
        last_success_at=subscription.last_success_at.isoformat() if subscription.last_success_at else None,
        last_failure_at=subscription.last_failure_at.isoformat() if subscription.last_failure_at else None
    )


@router.get(
    "/subscriptions",
    response_model=List[WebhookSubscriptionResponse],
    summary="List webhook subscriptions"
)
async def list_webhook_subscriptions(
    api_key: APIKey = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    List all webhook subscriptions for your API key.
    
    **Returns:**
    - All webhook endpoints registered to your API key
    - Delivery statistics
    - Current status (ACTIVE, PAUSED, DISABLED)
    """
    subscriptions = db.query(WebhookSubscription).filter_by(api_key_id=api_key.id).all()
    
    return [
        WebhookSubscriptionResponse(
            id=sub.id,
            url=sub.url,
            secret=None,  # Never returned after creation
            events=sub.events,
            description=sub.description,
            status=sub.status,
            created_at=sub.created_at.isoformat(),
            total_deliveries=sub.total_deliveries,
            successful_deliveries=sub.successful_deliveries,
            failed_deliveries=sub.failed_deliveries,
            last_delivery_at=sub.last_delivery_at.isoformat() if sub.last_delivery_at else None,
            last_success_at=sub.last_success_at.isoformat() if sub.last_success_at else None,
            last_failure_at=sub.last_failure_at.isoformat() if sub.last_failure_at else None
        )
        for sub in subscriptions
    ]


@router.get(
    "/subscriptions/{subscription_id}",
    response_model=WebhookSubscriptionResponse,
    summary="Get webhook subscription"
)
async def get_webhook_subscription(
    subscription_id: UUID,
    api_key: APIKey = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """Get details of a specific webhook subscription."""
    subscription = db.query(WebhookSubscription).filter_by(
        id=subscription_id,
        api_key_id=api_key.id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook subscription {subscription_id} not found"
        )
    
    return WebhookSubscriptionResponse(
        id=subscription.id,
        url=subscription.url,
        secret=None,
        events=subscription.events,
        description=subscription.description,
        status=subscription.status,
        created_at=subscription.created_at.isoformat(),
        total_deliveries=subscription.total_deliveries,
        successful_deliveries=subscription.successful_deliveries,
        failed_deliveries=subscription.failed_deliveries,
        last_delivery_at=subscription.last_delivery_at.isoformat() if subscription.last_delivery_at else None,
        last_success_at=subscription.last_success_at.isoformat() if subscription.last_success_at else None,
        last_failure_at=subscription.last_failure_at.isoformat() if subscription.last_failure_at else None
    )


@router.patch(
    "/subscriptions/{subscription_id}",
    response_model=WebhookSubscriptionResponse,
    summary="Update webhook subscription"
)
async def update_webhook_subscription(
    subscription_id: UUID,
    payload: WebhookSubscriptionUpdate,
    api_key: APIKey = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    Update a webhook subscription.
    
    **Updatable Fields:**
    - `url`: Change webhook endpoint
    - `events`: Change subscribed event types
    - `description`: Update description
    - `status`: ACTIVE, PAUSED, or DISABLED
    """
    subscription = db.query(WebhookSubscription).filter_by(
        id=subscription_id,
        api_key_id=api_key.id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook subscription {subscription_id} not found"
        )
    
    # Update fields
    if payload.url:
        if not str(payload.url).startswith('https://'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Webhook URL must use HTTPS for security"
            )
        subscription.url = str(payload.url)
    
    if payload.events is not None:
        subscription.events = payload.events
    
    if payload.description is not None:
        subscription.description = payload.description
    
    if payload.status:
        subscription.status = payload.status
    
    db.commit()
    db.refresh(subscription)
    
    return WebhookSubscriptionResponse(
        id=subscription.id,
        url=subscription.url,
        secret=None,
        events=subscription.events,
        description=subscription.description,
        status=subscription.status,
        created_at=subscription.created_at.isoformat(),
        total_deliveries=subscription.total_deliveries,
        successful_deliveries=subscription.successful_deliveries,
        failed_deliveries=subscription.failed_deliveries,
        last_delivery_at=subscription.last_delivery_at.isoformat() if subscription.last_delivery_at else None,
        last_success_at=subscription.last_success_at.isoformat() if subscription.last_success_at else None,
        last_failure_at=subscription.last_failure_at.isoformat() if subscription.last_failure_at else None
    )


@router.delete(
    "/subscriptions/{subscription_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete webhook subscription"
)
async def delete_webhook_subscription(
    subscription_id: UUID,
    api_key: APIKey = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """Delete a webhook subscription."""
    subscription = db.query(WebhookSubscription).filter_by(
        id=subscription_id,
        api_key_id=api_key.id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook subscription {subscription_id} not found"
        )
    
    db.delete(subscription)
    db.commit()
    
    return {
        "success": True,
        "message": f"Webhook subscription {subscription_id} deleted successfully"
    }


@router.post(
    "/subscriptions/{subscription_id}/regenerate-secret",
    response_model=WebhookSubscriptionResponse,
    summary="Regenerate webhook secret"
)
async def regenerate_webhook_secret(
    subscription_id: UUID,
    api_key: APIKey = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    Regenerate the HMAC secret for a webhook subscription.
    
    **Use Cases:**
    - Secret was compromised
    - Rotating secrets as security best practice
    - Lost the original secret
    
    **Warning:** After regenerating, update your webhook handler to use the new secret.
    """
    subscription = db.query(WebhookSubscription).filter_by(
        id=subscription_id,
        api_key_id=api_key.id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook subscription {subscription_id} not found"
        )
    
    # Generate new secret
    new_secret = secrets.token_urlsafe(32)
    subscription.secret = new_secret
    db.commit()
    
    return WebhookSubscriptionResponse(
        id=subscription.id,
        url=subscription.url,
        secret=new_secret,  # Returned ONLY when regenerating
        events=subscription.events,
        description=subscription.description,
        status=subscription.status,
        created_at=subscription.created_at.isoformat(),
        total_deliveries=subscription.total_deliveries,
        successful_deliveries=subscription.successful_deliveries,
        failed_deliveries=subscription.failed_deliveries,
        last_delivery_at=subscription.last_delivery_at.isoformat() if subscription.last_delivery_at else None,
        last_success_at=subscription.last_success_at.isoformat() if subscription.last_success_at else None,
        last_failure_at=subscription.last_failure_at.isoformat() if subscription.last_failure_at else None
    )


# ============================================================================
# Webhook Delivery Logs
# ============================================================================

@router.get(
    "/subscriptions/{subscription_id}/deliveries",
    response_model=List[WebhookDeliveryResponse],
    summary="List webhook deliveries"
)
async def list_webhook_deliveries(
    subscription_id: UUID,
    limit: int = 100,
    api_key: APIKey = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    View delivery logs for a webhook subscription.
    
    **Returns:**
    - All delivery attempts (including retries)
    - Response codes and times
    - Error messages
    - Retry schedules
    """
    # Verify subscription belongs to API key
    subscription = db.query(WebhookSubscription).filter_by(
        id=subscription_id,
        api_key_id=api_key.id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook subscription {subscription_id} not found"
        )
    
    deliveries = db.query(WebhookDelivery).filter_by(
        subscription_id=subscription_id
    ).order_by(WebhookDelivery.created_at.desc()).limit(min(limit, 1000)).all()
    
    return [
        WebhookDeliveryResponse(
            id=delivery.id,
            subscription_id=delivery.subscription_id,
            event_id=delivery.event_id,
            attempt_number=delivery.attempt_number,
            status=delivery.status,
            request_body=delivery.request_body,
            response_code=delivery.response_code,
            response_body=delivery.response_body,
            response_time_ms=delivery.response_time_ms,
            error_message=delivery.error_message,
            will_retry=delivery.will_retry,
            retry_at=delivery.retry_at.isoformat() if delivery.retry_at else None,
            created_at=delivery.created_at.isoformat(),
            delivered_at=delivery.delivered_at.isoformat() if delivery.delivered_at else None
        )
        for delivery in deliveries
    ]


# ============================================================================
# Webhook Testing
# ============================================================================

@router.post(
    "/subscriptions/{subscription_id}/test",
    status_code=status.HTTP_200_OK,
    summary="Test webhook"
)
async def test_webhook(
    subscription_id: UUID,
    payload: WebhookTestPayload,
    api_key: APIKey = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    Send a test webhook to verify your endpoint is working.
    
    **Use Cases:**
    - Testing webhook handler implementation
    - Verifying signature validation
    - Debugging delivery issues
    
    **Test Event:**
    ```json
    {
      "event_id": "test-12345",
      "event_type": "webhook.test",
      "timestamp": "2026-07-14T20:51:00Z",
      "data": {
        "message": "This is a test webhook",
        ...your custom test_data...
      }
    }
    ```
    """
    from app.services.webhook_engine import WebhookDeliveryEngine
    
    # Verify subscription
    subscription = db.query(WebhookSubscription).filter_by(
        id=subscription_id,
        api_key_id=api_key.id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook subscription {subscription_id} not found"
        )
    
    # Create test event
    test_event_data = {
        "message": "This is a test webhook from VettedMe",
        **payload.test_data
    }
    
    engine = WebhookDeliveryEngine(db)
    event = await engine.create_event(
        event_type=payload.event_type,
        event_data=test_event_data
    )
    
    return {
        "success": True,
        "message": "Test webhook queued for delivery",
        "event_id": str(event.id),
        "subscription_id": str(subscription_id)
    }
