"""
Clinician journey status service - stub implementation
Tracks the onboarding and application status of clinicians
"""

from typing import Optional
from sqlalchemy.orm import Session


async def build_clinician_journey_status(
    db: Session,
    clinician_id: str
) -> dict:
    """
    Stub implementation for building clinician journey status.
    
    Args:
        db: Database session
        clinician_id: Unique clinician identifier
    
    Returns:
        Dictionary containing journey status information
    """
    # TODO: Implement actual journey status logic
    # This is a stub to unblock test suite execution
    return {
        "clinician_id": clinician_id,
        "status": "pending",
        "steps_completed": [],
        "steps_remaining": []
    }
