"""
VettedMe zkTLS Platform - Pydantic Schemas

API request/response validation for Phase 1 & 2
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, validator
from uuid import UUID


# ============================================================================
# User Schemas
# ============================================================================

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    username: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: UUID
    profile_image_url: Optional[str] = None
    is_email_verified: bool
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserProfile(UserResponse):
    """Extended user profile with stats"""
    credential_count: int = 0
    public_profile_url: Optional[str] = None


# ============================================================================
# Public Profile Schemas
# ============================================================================

class PublicProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=500)
    website_url: Optional[str] = None
    twitter_handle: Optional[str] = None
    linkedin_url: Optional[str] = None
    is_public: Optional[bool] = None


class PublicProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    display_name: Optional[str]
    bio: Optional[str]
    website_url: Optional[str]
    twitter_handle: Optional[str]
    linkedin_url: Optional[str]
    is_public: bool
    view_count: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# Credential Badge Schemas
# ============================================================================

class CredentialBase(BaseModel):
    provider_type: str = Field(..., description="Provider type: LINKEDIN, MBON_HEALTHCARE, UBER, STRIPE")
    claims: Optional[Dict[str, Any]] = Field(None, description="User-readable claims extracted from proof")


class CredentialCreate(CredentialBase):
    proof_data: Dict[str, Any] = Field(..., description="Full Reclaim Protocol proof")
    reclaim_provider_id: str


class CredentialResponse(CredentialBase):
    id: UUID
    user_id: UUID
    reclaim_provider_id: str
    proof_hash: str
    is_valid: bool
    verified_at: datetime
    expires_at: Optional[datetime]
    is_public: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class CredentialWithUser(CredentialResponse):
    """Credential with user info for public profiles"""
    user: UserResponse


# ============================================================================
# Reclaim Protocol Session Schemas
# ============================================================================

class ReclaimSessionCreate(BaseModel):
    provider_type: str = Field(..., description="LINKEDIN, MBON_HEALTHCARE, etc.")
    callback_url: Optional[str] = None


class ReclaimSessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    reclaim_session_id: str
    provider_type: str
    status: str  # PENDING, IN_PROGRESS, COMPLETED, FAILED
    callback_url: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ReclaimSessionWebhook(BaseModel):
    """
    Webhook payload from Reclaim Protocol when proof is generated.
    
    This is what Reclaim sends to our /api/v1/reclaim/webhook endpoint.
    """
    session_id: str
    status: str  # COMPLETED or FAILED
    proof_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


# ============================================================================
# Developer API Schemas (Phase 2)
# ============================================================================

class DeveloperProfileCreate(BaseModel):
    api_key_name: Optional[str] = Field(None, description="Human-readable name for this API key")


class DeveloperProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    api_key_prefix: str  # Show only first 8 chars (e.g., "sk_live_abc123...")
    api_key_name: Optional[str]
    rate_limit_rpm: int
    rate_limit_daily: int
    is_active: bool
    last_used_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class APIKeyResponse(BaseModel):
    """
    Response when creating a new API key.
    
    CRITICAL: We only show the full API key ONCE when it's created.
    After that, we only show the prefix.
    """
    api_key: str  # Full key (shown only once)
    api_key_prefix: str
    developer_profile: DeveloperProfileResponse


# ============================================================================
# API Verification Request Schemas (Phase 2)
# ============================================================================

class LinkedInVerificationRequest(BaseModel):
    """
    Request to verify a LinkedIn profile via zkTLS.
    
    Developer sends this to: POST /api/v1/verify/linkedin
    """
    linkedin_url: str = Field(..., description="LinkedIn profile URL or username")
    claims_to_verify: List[str] = Field(
        default=["account_age", "connections", "current_employment"],
        description="Which claims to extract from the proof"
    )


class HealthcareVerificationRequest(BaseModel):
    """
    Request to verify a nurse license via MBON.
    
    Developer sends this to: POST /api/v1/verify/healthcare
    """
    license_number: str = Field(..., description="Nurse license number")
    license_type: str = Field(..., description="RN, LPN, CNA, GNA")
    state: str = Field(default="MD", description="State (currently only Maryland)")
    first_name: str
    last_name: str


class VerificationResponse(BaseModel):
    """
    Response for any verification request.
    
    This is what developers get back from /api/v1/verify/* endpoints.
    """
    success: bool
    verification_id: UUID
    provider_type: str
    claims: Dict[str, Any]  # Verified claims
    proof_hash: str  # For audit trail
    verified_at: datetime
    cost_cents: int = 10  # $0.10 per verification


# ============================================================================
# Usage & Billing Schemas (Phase 2)
# ============================================================================

class UsageStatsResponse(BaseModel):
    """Developer usage statistics"""
    total_requests: int
    billable_requests: int
    total_cost_cents: int
    current_month_requests: int
    current_month_cost_cents: int


class BillingPeriodResponse(BaseModel):
    """Monthly billing period"""
    id: UUID
    period_start: datetime
    period_end: datetime
    total_requests: int
    billable_requests: int
    amount_cents: int
    stripe_invoice_id: Optional[str]
    paid_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ============================================================================
# Public Badge Display Schemas
# ============================================================================

class BadgeDisplayResponse(BaseModel):
    """
    Public badge display for sharing.
    
    Example: vettedme.ai/badge/{credential_id}
    Shows a beautiful badge card that can be embedded anywhere.
    """
    credential_id: UUID
    provider_type: str
    claims: Dict[str, Any]
    verified_at: datetime
    is_valid: bool
    user: Optional[UserResponse] = None


class PublicProfileWithBadges(PublicProfileResponse):
    """
    Complete public profile with all badges.
    
    Example: vettedme.ai/@username
    """
    user: UserResponse
    credentials: List[CredentialResponse]


# ============================================================================
# Analytics Schemas
# ============================================================================

class BadgeAnalytics(BaseModel):
    """Badge view analytics"""
    credential_id: UUID
    total_views: int
    views_this_week: int
    views_this_month: int
    top_referrers: List[Dict[str, Any]]


# ============================================================================
# Error Response Schema
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: Optional[str] = None
    error_code: Optional[str] = None


# ============================================================================
# Success Response Schema
# ============================================================================

class SuccessResponse(BaseModel):
    """Standard success response"""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None
