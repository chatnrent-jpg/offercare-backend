"""
Shift lock service - handles shift assignments and SMS lock replies.
Minimal implementation to support demo environment and SMS workflows.
"""

from sqlalchemy.orm import Session
from uuid import UUID


def normalize_phone(phone: str) -> str:
    """
    Normalize phone number to E.164 format.
    Removes non-digit characters and ensures proper formatting.
    """
    # Remove all non-digit characters
    digits = ''.join(c for c in phone if c.isdigit())
    
    # If starts with 1 and is 11 digits, it's already good
    if len(digits) == 11 and digits[0] == '1':
        return f"+{digits}"
    
    # If 10 digits, assume US and prepend +1
    if len(digits) == 10:
        return f"+1{digits}"
    
    # Otherwise return with + prefix
    return f"+{digits}" if not digits.startswith('+') else digits


def lock_shift_for_provider(
    db: Session,
    shift_id: UUID,
    provider_id: UUID,
    *,
    lock_method: str = "ADMIN_DEMO",
) -> dict:
    """
    Lock a shift for a specific provider.
    Used primarily in demo/admin workflows.
    
    Args:
        db: Database session
        shift_id: Shift UUID to lock
        provider_id: Provider UUID to assign shift to
        lock_method: Source of lock (ADMIN_DEMO, SMS_REPLY, etc.)
    
    Returns:
        dict with success status and details
    """
    # Minimal stub implementation
    # TODO: Implement full shift locking logic with:
    # - Shift availability check
    # - Provider eligibility validation
    # - Transaction creation
    # - Notification dispatch
    
    return {
        "success": True,
        "shift_id": str(shift_id),
        "provider_id": str(provider_id),
        "lock_method": lock_method,
        "message": "Shift lock stub - full implementation pending",
    }


def lock_shift_from_sms_reply(
    db: Session,
    phone_number: str,
    shift_id: UUID | None = None,
) -> dict:
    """
    Lock a shift based on SMS reply (e.g., replying YES to a shift offer).
    
    Args:
        db: Database session
        phone_number: Phone number that sent the reply
        shift_id: Optional specific shift ID (if known from context)
    
    Returns:
        dict with lock result and status
    """
    # Normalize phone number
    normalized_phone = normalize_phone(phone_number)
    
    # Minimal stub implementation
    # TODO: Implement full SMS lock logic with:
    # - Phone number -> provider lookup
    # - Recent shift offers for this provider
    # - Lock the most recent unlocked shift
    # - Send confirmation SMS
    
    return {
        "success": True,
        "phone_number": normalized_phone,
        "shift_id": str(shift_id) if shift_id else None,
        "message": "SMS lock stub - full implementation pending",
    }
