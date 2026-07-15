"""
VettedMe Passport - API Router

This module implements the developer-first API for the VettedMe Passport system.

Key Endpoints:
- POST /passport/create - Create a new passport
- POST /passport/issue-badge - Issue a credential badge
- POST /passport/revoke-badge - Revoke a credential badge
- POST /passport/verify - Verify a passport (external platforms)
- POST /passport/api-keys - Create an API key (platform onboarding)
- GET /passport/{passport_id} - Get passport details
- GET /passport/{passport_id}/badges - List all badges
- GET /passport/verification-logs - View verification audit trail

Revenue Model:
- Free Tier: 100 verifications/hour ($0)
- Growth Tier: 10,000 verifications/hour ($0.50 per verification)
- Enterprise: Unlimited (custom pricing)
"""

import hashlib
import secrets
from typing import List, Optional
from uuid import UUID
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.passport import Passport, CredentialBadge, APIKey, VerificationLog
from app.schemas import (
    PassportCreate,
    PassportResponse,
    BadgeIssueRequest,
    BadgeResponse,
    BadgeRevocationRequest,
    VerificationRequest,
    VerificationResponse,
    APIKeyCreateRequest,
    APIKeyResponse,
    VerificationLogResponse
)
from app.services.passport_engine import (
    PassportIssuanceEngine,
    PassportVerificationEngine
)

router = APIRouter(
    prefix="/api/v1/passport",
    tags=["VettedMe Passport - W3C Verifiable Credentials"]
)


# ============================================================================
# Authentication Helper
# ============================================================================

def get_api_key_from_header(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> APIKey:
    """
    Extract and validate API key from Authorization header.
    
    Format: Authorization: Bearer vettedme_live_abc123
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Format: 'Bearer vettedme_live_<key>'"
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization format. Expected: 'Bearer vettedme_live_<key>'"
        )
    
    api_key_string = authorization.replace("Bearer ", "").strip()
    
    # Hash the API key
    key_hash = hashlib.sha256(api_key_string.encode()).hexdigest()
    
    # Lookup API key
    api_key = db.query(APIKey).filter_by(key_hash=key_hash).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    if not api_key.is_active():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API key is {api_key.status.lower()}"
        )
    
    # Record usage
    api_key.record_usage()
    db.commit()
    
    return api_key


# ============================================================================
# Passport Management Endpoints
# ============================================================================

@router.post(
    "/create",
    response_model=PassportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new passport for a user"
)
async def create_passport(
    payload: PassportCreate,
    db: Session = Depends(get_db)
):
    """
    Issue a new VettedMe Passport for a user.
    
    A passport is a cryptographic container for verified credentials.
    Each user can have exactly ONE passport.
    
    **Requirements:**
    - User must not already have a passport
    - Optional biometric data can be provided for enhanced security
    
    **Response:**
    - Returns the newly created passport with unique ID and public key
    """
    try:
        engine = PassportIssuanceEngine(db)
        
        # Decode biometric data if provided
        biometric_bytes = None
        if payload.biometric_data:
            import base64
            biometric_bytes = base64.b64decode(payload.biometric_data)
        
        passport = engine.create_passport(
            user_id=payload.user_id,
            biometric_data=biometric_bytes
        )
        
        return PassportResponse(
            id=passport.id,
            user_id=passport.user_id,
            status=passport.status,
            issued_at=passport.issued_at,
            expires_at=passport.expires_at,
            trust_score=passport.trust_score,
            badge_count=len(passport.badges)
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create passport: {str(e)}"
        )


@router.get(
    "/{passport_id}",
    response_model=PassportResponse,
    summary="Get passport details"
)
async def get_passport(
    passport_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Retrieve detailed information about a specific passport.
    
    **Returns:**
    - Passport metadata (ID, status, trust score, expiration)
    - Badge count (number of verified credentials)
    """
    passport = db.query(Passport).filter_by(id=passport_id).first()
    
    if not passport:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Passport {passport_id} not found"
        )
    
    return PassportResponse(
        id=passport.id,
        user_id=passport.user_id,
        status=passport.status,
        issued_at=passport.issued_at,
        expires_at=passport.expires_at,
        trust_score=passport.trust_score,
        badge_count=len(passport.get_active_badges())
    )


# ============================================================================
# Badge Management Endpoints
# ============================================================================

@router.post(
    "/issue-badge",
    response_model=BadgeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue a new credential badge"
)
async def issue_badge(
    payload: BadgeIssueRequest,
    db: Session = Depends(get_db)
):
    """
    Issue a new credential badge and attach it to a passport.
    
    **Badge Types:**
    - `IDENTITY`: Government ID + biometric verification
    - `HEALTHCARE`: State nursing licenses (RN/LPN/CNA)
    - `EMPLOYMENT`: Verified work history
    - `EDUCATION`: Verified degrees/certifications
    - `COMPLIANCE`: Background check + criminal record
    - `DEVELOPER`: GitHub + technical assessments
    - `PROFESSIONAL`: CPA, EA, Bar admission, etc.
    
    **Security:**
    - Badge is cryptographically signed with Ed25519
    - Signature prevents tampering and enables offline verification
    - Trust score is automatically recalculated
    """
    try:
        engine = PassportIssuanceEngine(db)
        
        badge = engine.issue_badge(
            passport_id=payload.passport_id,
            badge_type=payload.badge_type,
            credential_data=payload.credential_data,
            verification_method=payload.verification_method,
            expires_at=payload.expires_at
        )
        
        return BadgeResponse(
            id=badge.id,
            passport_id=badge.passport_id,
            badge_type=badge.badge_type,
            credential_data=badge.credential_data,
            verification_method=badge.verification_method,
            verified_at=badge.verified_at,
            expires_at=badge.expires_at,
            revoked=badge.revoked,
            issuer_signature=badge.issuer_signature
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to issue badge: {str(e)}"
        )


@router.get(
    "/{passport_id}/badges",
    response_model=List[BadgeResponse],
    summary="List all badges for a passport"
)
async def list_badges(
    passport_id: UUID,
    include_revoked: bool = False,
    db: Session = Depends(get_db)
):
    """
    List all credential badges attached to a passport.
    
    **Parameters:**
    - `include_revoked`: If true, includes revoked badges (default: false)
    
    **Returns:**
    - List of badges with full credential data and signatures
    """
    passport = db.query(Passport).filter_by(id=passport_id).first()
    
    if not passport:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Passport {passport_id} not found"
        )
    
    if include_revoked:
        badges = passport.badges
    else:
        badges = passport.get_active_badges()
    
    return [
        BadgeResponse(
            id=badge.id,
            passport_id=badge.passport_id,
            badge_type=badge.badge_type,
            credential_data=badge.credential_data,
            verification_method=badge.verification_method,
            verified_at=badge.verified_at,
            expires_at=badge.expires_at,
            revoked=badge.revoked,
            issuer_signature=badge.issuer_signature
        )
        for badge in badges
    ]


@router.post(
    "/revoke-badge",
    status_code=status.HTTP_200_OK,
    summary="Revoke a credential badge"
)
async def revoke_badge(
    payload: BadgeRevocationRequest,
    db: Session = Depends(get_db)
):
    """
    Revoke a credential badge.
    
    **Use Cases:**
    - License expired or suspended
    - Employment ended
    - Fraud detected
    - User requested deletion
    
    **Effect:**
    - Badge is marked as revoked (cannot be un-revoked)
    - Trust score is recalculated
    - External platforms will be notified via webhook (if configured)
    """
    try:
        engine = PassportIssuanceEngine(db)
        engine.revoke_badge(
            badge_id=payload.badge_id,
            reason=payload.reason
        )
        
        return {
            "success": True,
            "message": f"Badge {payload.badge_id} revoked successfully"
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke badge: {str(e)}"
        )


# ============================================================================
# Verification API (Revenue Engine)
# ============================================================================

@router.post(
    "/verify",
    response_model=VerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify a passport (external platforms)",
    description="**⚡ Primary revenue endpoint** - External platforms call this to instantly verify credentials"
)
async def verify_passport(
    payload: VerificationRequest,
    request: Request,
    api_key: APIKey = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    Verify a passport and return requested credential badges.
    
    **Authentication:**
    - Requires valid API key in Authorization header
    - Format: `Authorization: Bearer vettedme_live_<key>`
    
    **Rate Limits:**
    - Free tier: 100 verifications/hour
    - Growth tier: 10,000 verifications/hour
    - Enterprise: Unlimited
    
    **Pricing:**
    - Free tier: $0
    - Growth tier: $0.50 per verification
    - Enterprise: Custom pricing
    
    **Security:**
    - Every verification is logged for audit trail
    - Cryptographic signature validation ensures tamper-proof credentials
    - User controls which badges to share (privacy-preserving)
    
    **Example Request:**
    ```json
    {
      "passport_id": "uuid-12345",
      "required_badges": ["IDENTITY", "HEALTHCARE"],
      "requesting_platform": "upwork.com"
    }
    ```
    
    **Example Response:**
    ```json
    {
      "verified": true,
      "passport_id": "uuid-12345",
      "trust_score": 98,
      "badges": [
        {
          "type": "IDENTITY",
          "verified": true,
          "expires_at": "2028-07-14T00:00:00Z"
        },
        {
          "type": "HEALTHCARE",
          "verified": true,
          "credential": {
            "license_type": "RN",
            "license_number": "R234951",
            "state": "MD"
          },
          "expires_at": "2027-10-31T00:00:00Z"
        }
      ],
      "verification_token": "vtok_1721073600_uuid1234_abc"
    }
    ```
    """
    try:
        engine = PassportVerificationEngine(db)
        
        # Extract IP address and user agent
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")
        
        result = engine.verify_passport(
            passport_id=payload.passport_id,
            required_badges=payload.required_badges,
            api_key_id=api_key.id,
            requesting_platform=payload.requesting_platform,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return VerificationResponse(**result)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {str(e)}"
        )


# ============================================================================
# API Key Management (Platform Onboarding)
# ============================================================================

@router.post(
    "/api-keys",
    response_model=APIKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new API key (platform onboarding)"
)
async def create_api_key(
    payload: APIKeyCreateRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new API key for an external platform.
    
    **Tiers:**
    - `FREE`: 100 verifications/hour, $0
    - `GROWTH`: 10,000 verifications/hour, $0.50 per verification
    - `ENTERPRISE`: Unlimited, custom pricing
    
    **Security:**
    - API key is only shown once during creation
    - Keys are hashed before storage (SHA256)
    - Key prefix is stored for identification
    
    **Returns:**
    - Full API key (only on creation)
    - Key metadata (ID, tier, rate limits, status)
    """
    try:
        # Generate secure API key
        key_suffix = secrets.token_urlsafe(32)
        api_key_string = f"vettedme_live_{key_suffix}"
        
        # Hash for storage
        key_hash = hashlib.sha256(api_key_string.encode()).hexdigest()
        key_prefix = api_key_string[:16]  # "vettedme_live_ab"
        
        # Create API key record
        api_key = APIKey(
            organization_name=payload.organization_name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            tier=payload.tier,
            rate_limit_per_hour=payload.rate_limit_per_hour,
            status="ACTIVE"
        )
        
        db.add(api_key)
        db.commit()
        db.refresh(api_key)
        
        return APIKeyResponse(
            id=api_key.id,
            organization_name=api_key.organization_name,
            key_prefix=api_key.key_prefix,
            api_key=api_key_string,  # Only returned on creation
            tier=api_key.tier,
            rate_limit_per_hour=api_key.rate_limit_per_hour,
            status=api_key.status,
            created_at=api_key.created_at,
            expires_at=api_key.expires_at,
            last_used_at=api_key.last_used_at
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create API key: {str(e)}"
        )


# ============================================================================
# Audit & Analytics Endpoints
# ============================================================================

@router.get(
    "/verification-logs",
    response_model=List[VerificationLogResponse],
    summary="View verification audit trail"
)
async def get_verification_logs(
    passport_id: Optional[UUID] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieve verification audit logs.
    
    **Parameters:**
    - `passport_id`: Filter logs for a specific passport (optional)
    - `limit`: Maximum number of logs to return (default: 100, max: 1000)
    
    **Returns:**
    - List of verification logs with full request/response details
    - Timestamps, IP addresses, and requesting platforms
    """
    query = db.query(VerificationLog)
    
    if passport_id:
        query = query.filter_by(passport_id=passport_id)
    
    logs = query.order_by(VerificationLog.timestamp.desc()).limit(min(limit, 1000)).all()
    
    return [
        VerificationLogResponse(
            id=log.id,
            passport_id=log.passport_id,
            requesting_platform=log.requesting_platform,
            requested_badges=log.requested_badges,
            verification_result=log.verification_result,
            timestamp=log.timestamp,
            ip_address=str(log.ip_address) if log.ip_address else None
        )
        for log in logs
    ]


# ============================================================================
# User Dashboard
# ============================================================================

@router.get(
    "/dashboard",
    response_class=HTMLResponse,
    summary="User Passport Dashboard",
    description="Interactive dashboard for users to view and manage their passports"
)
async def get_passport_dashboard():
    """
    User-facing dashboard for managing VettedMe Passports.
    
    **Features:**
    - View passport details and trust score
    - See all credential badges
    - Generate embeddable widget code
    - Share credentials to LinkedIn, Upwork, etc.
    - Add new badges
    - Revoke credentials
    
    **Access:**
    - Public demo available for testing
    - Production requires user authentication (coming soon)
    """
    dashboard_path = Path(__file__).resolve().parent.parent / "static" / "passport" / "dashboard.html"
    with open(dashboard_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
