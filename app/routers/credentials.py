"""
VettedMe Credentials API

Endpoints for managing and viewing user credentials (badges).

Phase 1: User endpoints (view own badges)
Phase 2: Developer endpoints (verify other users' badges via API)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging

from app.database import get_db
from app.models.zktls import User, Credential
from app.schemas.zktls import CredentialResponse
from app.auth import get_current_user, get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/credentials",
    tags=["Credentials"]
)


# ============================================================================
# User Endpoints (View Own Credentials)
# ============================================================================

@router.get(
    "",
    response_model=List[CredentialResponse],
    summary="Get Current User's Credentials",
    description="""
    Get all credentials (badges) for the currently authenticated user.
    
    **Requires Authentication:**
    ```
    Authorization: Bearer <token>
    ```
    
    **Returns:**
    - List of all user's credentials
    - Empty list if user has no badges yet
    
    **Use Cases:**
    - Display badges on user dashboard
    - Check verification status
    - Show verified claims
    """
)
async def get_my_credentials(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all credentials for the current user.
    
    This endpoint is used by the frontend dashboard to display
    the user's verified badges.
    """
    credentials = db.query(Credential).filter(
        Credential.user_id == current_user.id
    ).order_by(
        Credential.verified_at.desc()
    ).all()
    
    logger.info(f"Retrieved {len(credentials)} credentials for user {current_user.id}")
    
    return credentials


@router.get(
    "/{credential_id}",
    response_model=CredentialResponse,
    summary="Get Specific Credential",
    description="""
    Get a specific credential by ID.
    
    **Requires Authentication:**
    User must own the credential OR credential must be public.
    
    **Use Cases:**
    - View detailed badge information
    - Share public badge
    - Verify specific credential
    """
)
async def get_credential(
    credential_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific credential by ID.
    
    Returns credential if:
    - User owns the credential, OR
    - Credential is public
    """
    credential = db.query(Credential).filter(
        Credential.id == credential_id
    ).first()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found"
        )
    
    # Check permissions
    if credential.user_id != current_user.id and not credential.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This credential is private"
        )
    
    return credential


@router.post(
    "/{credential_id}/revoke",
    summary="Revoke Credential",
    description="""
    Revoke (invalidate) a credential.
    
    **Requires Authentication:**
    User must own the credential.
    
    **Use Cases:**
    - Remove outdated badge
    - Revoke compromised credential
    - Update badge with new verification
    
    **Note:** This marks the credential as invalid but doesn't delete it.
    """
)
async def revoke_credential(
    credential_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Revoke a credential (mark as invalid).
    
    User can revoke their own credentials if they want to
    remove them from public display or if they need to re-verify.
    """
    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.user_id == current_user.id
    ).first()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found or you don't own it"
        )
    
    if not credential.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credential is already revoked"
        )
    
    # Mark as invalid
    from datetime import datetime, timezone
    credential.is_valid = False
    credential.revoked_at = datetime.now(timezone.utc)
    
    db.commit()
    
    logger.info(f"User {current_user.id} revoked credential {credential_id}")
    
    return {
        "success": True,
        "message": "Credential revoked successfully",
        "credential_id": str(credential.id)
    }


@router.post(
    "/{credential_id}/visibility",
    summary="Update Credential Visibility",
    description="""
    Make a credential public or private.
    
    **Requires Authentication:**
    User must own the credential.
    
    **Use Cases:**
    - Hide sensitive badge from public profile
    - Show/hide specific badges
    """
)
async def update_credential_visibility(
    credential_id: str,
    is_public: bool,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update whether a credential is publicly visible.
    """
    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.user_id == current_user.id
    ).first()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found or you don't own it"
        )
    
    credential.is_public = is_public
    db.commit()
    
    logger.info(f"User {current_user.id} set credential {credential_id} visibility to {is_public}")
    
    return {
        "success": True,
        "message": f"Credential is now {'public' if is_public else 'private'}",
        "credential_id": str(credential.id),
        "is_public": is_public
    }


# ============================================================================
# Public Endpoints (No Auth Required)
# ============================================================================

@router.get(
    "/public/{credential_id}",
    response_model=CredentialResponse,
    summary="Get Public Credential",
    description="""
    Get a public credential by ID (no authentication required).
    
    **Use Cases:**
    - Embed badge on external website
    - Share badge on social media
    - Third-party verification
    
    **Note:** Only returns credentials marked as public.
    """
)
async def get_public_credential(
    credential_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a public credential (no auth required).
    
    This endpoint is used for public badge sharing and embedding.
    """
    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.is_public == True
    ).first()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Public credential not found"
        )
    
    # Track view (analytics)
    # TODO: Add to badge_views table
    
    return credential


# ============================================================================
# Statistics Endpoints
# ============================================================================

@router.get(
    "/stats/summary",
    summary="Get Credential Statistics",
    description="""
    Get summary statistics for current user's credentials.
    
    **Returns:**
    - Total credentials
    - Credentials by provider type
    - Recently verified badges
    """
)
async def get_credential_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get credential statistics for the current user.
    """
    from sqlalchemy import func
    
    # Total credentials
    total = db.query(func.count(Credential.id)).filter(
        Credential.user_id == current_user.id
    ).scalar()
    
    # Valid credentials
    valid = db.query(func.count(Credential.id)).filter(
        Credential.user_id == current_user.id,
        Credential.is_valid == True
    ).scalar()
    
    # By provider type
    by_provider = db.query(
        Credential.provider_type,
        func.count(Credential.id).label('count')
    ).filter(
        Credential.user_id == current_user.id,
        Credential.is_valid == True
    ).group_by(
        Credential.provider_type
    ).all()
    
    return {
        "total_credentials": total,
        "valid_credentials": valid,
        "revoked_credentials": total - valid,
        "by_provider": {
            provider: count for provider, count in by_provider
        }
    }
