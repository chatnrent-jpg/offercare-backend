"""
VettedMe zkTLS Platform - SQLAlchemy Models

Phase 1: Free Badges (LinkedIn + Healthcare)
Phase 2: B2B Developer API with Stripe Billing

All models for the new zkTLS credential verification platform.
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Integer, DateTime, Text, 
    ForeignKey, JSON, CHAR
)
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base


# ============================================================================
# Core User Models
# ============================================================================

class User(Base):
    """
    Core user account with authentication.
    
    Phase 1: Email/password authentication
    Phase 2: OAuth (Google, GitHub) + Stripe integration
    """
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    username = Column(String(50), unique=True, index=True)  # Public profile URL
    profile_image_url = Column(Text)
    
    # Phase 2: Stripe
    stripe_customer_id = Column(String(255), index=True)
    
    # Status
    is_email_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    credentials = relationship("Credential", back_populates="user", cascade="all, delete-orphan")
    developer_profile = relationship("DeveloperProfile", back_populates="user", uselist=False)
    public_profile = relationship("PublicProfile", back_populates="user", uselist=False)
    reclaim_sessions = relationship("ReclaimSession", back_populates="user")


class PublicProfile(Base):
    """
    Public shareable profile with credential badges.
    
    Example: vettedme.ai/@johndoe
    Shows all public badges, bio, social links
    """
    __tablename__ = "public_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    
    # Display Settings
    display_name = Column(String(255))
    bio = Column(Text)
    website_url = Column(Text)
    twitter_handle = Column(String(50))
    linkedin_url = Column(Text)
    
    # Badge Display Order (array of credential IDs)
    badge_order = Column(JSONB)
    
    # Visibility
    is_public = Column(Boolean, default=True, index=True)
    
    # Analytics
    view_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="public_profile")


# ============================================================================
# Credential Badge Models (Phase 1)
# ============================================================================

class Credential(Base):
    """
    zkTLS credential badge issued via Reclaim Protocol.
    
    Phase 1 Providers:
    - LINKEDIN: Account age, connections, employment
    - MBON_HEALTHCARE: Nurse license verification
    
    Phase 3 Providers:
    - UBER: Driver rating
    - STRIPE: Merchant status
    - GITHUB: Contribution history
    """
    __tablename__ = "credentials"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Provider Information
    provider_type = Column(String(50), nullable=False, index=True)  # LINKEDIN, MBON_HEALTHCARE
    reclaim_provider_id = Column(String(100), nullable=False)
    
    # Proof Data
    proof_data = Column(JSONB, nullable=False)  # Full Reclaim Protocol proof
    proof_hash = Column(String(64), nullable=False, index=True)  # SHA256 for verification
    
    # Extracted Claims (user-readable)
    claims = Column(JSONB)  # {"account_age": "5 years", "connections": "500+"}
    
    # Verification Status
    is_valid = Column(Boolean, default=True, index=True)
    verified_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))  # Some credentials expire
    revoked_at = Column(DateTime(timezone=True))
    
    # Visibility
    is_public = Column(Boolean, default=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="credentials")
    views = relationship("BadgeView", back_populates="credential")


class ReclaimSession(Base):
    """
    Track ongoing Reclaim Protocol proof generation sessions.
    
    Flow:
    1. User clicks "Verify LinkedIn"
    2. Backend creates ReclaimSession with status=PENDING
    3. User redirected to Reclaim Protocol
    4. Reclaim Protocol calls webhook with proof
    5. Backend updates session with proof_data, status=COMPLETED
    """
    __tablename__ = "reclaim_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    
    # Reclaim Data
    reclaim_session_id = Column(String(255), nullable=False, index=True)
    provider_type = Column(String(50), nullable=False)
    
    # Status: PENDING, IN_PROGRESS, COMPLETED, FAILED
    status = Column(String(50), default="PENDING", index=True)
    callback_url = Column(Text)
    
    # Result
    proof_data = Column(JSONB)
    error_message = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="reclaim_sessions")


# ============================================================================
# Developer API Models (Phase 2)
# ============================================================================

class DeveloperProfile(Base):
    """
    Developer API key and rate limiting configuration.
    
    Phase 2: B2B API monetization
    - Generate API keys (sk_live_xxx or sk_test_xxx)
    - Rate limiting (60 req/min, 10k req/day)
    - Usage tracking for billing
    """
    __tablename__ = "developer_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    
    # API Key
    api_key_prefix = Column(String(20), nullable=False)  # First 8 chars for display
    api_key_hash = Column(String(64), unique=True, nullable=False, index=True)  # SHA256 hash
    api_key_name = Column(String(100))  # User-defined name
    
    # Rate Limiting
    rate_limit_rpm = Column(Integer, default=60)  # Requests per minute
    rate_limit_daily = Column(Integer, default=10000)  # Daily limit
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    last_used_at = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="developer_profile")
    usage_logs = relationship("UsageLog", back_populates="developer")
    billing_periods = relationship("BillingPeriod", back_populates="developer")


class UsageLog(Base):
    """
    Track API calls for metered billing.
    
    Phase 2: Usage-based billing
    - Log every API call
    - Track billable vs non-billable
    - Calculate monthly charges
    """
    __tablename__ = "usage_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    developer_id = Column(UUID(as_uuid=True), ForeignKey("developer_profiles.id", ondelete="SET NULL"), index=True)
    
    # Request Information
    endpoint = Column(String(100), nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Integer)
    
    # Billing
    is_billable = Column(Boolean, default=True, index=True)
    cost_cents = Column(Integer, default=10)  # $0.10 = 10 cents
    
    # Metadata
    ip_address = Column(INET)
    user_agent = Column(Text)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    developer = relationship("DeveloperProfile", back_populates="usage_logs")


class BillingPeriod(Base):
    """
    Monthly billing cycles and Stripe invoices.
    
    Phase 2: Stripe integration
    - Create monthly billing periods
    - Calculate usage charges
    - Generate Stripe invoices
    """
    __tablename__ = "billing_periods"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    developer_id = Column(UUID(as_uuid=True), ForeignKey("developer_profiles.id", ondelete="CASCADE"), index=True)
    
    # Period
    period_start = Column(DateTime(timezone=True), nullable=False, index=True)
    period_end = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Usage
    total_requests = Column(Integer, default=0)
    billable_requests = Column(Integer, default=0)
    
    # Billing
    amount_cents = Column(Integer, default=0)  # Total in cents
    stripe_invoice_id = Column(String(255))
    paid_at = Column(DateTime(timezone=True))
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    developer = relationship("DeveloperProfile", back_populates="billing_periods")


# ============================================================================
# Analytics Models
# ============================================================================

class BadgeView(Base):
    """
    Track badge impressions for analytics.
    
    Analytics:
    - How many times was this badge viewed?
    - Where are viewers coming from?
    - Which badges are most popular?
    """
    __tablename__ = "badge_views"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    credential_id = Column(UUID(as_uuid=True), ForeignKey("credentials.id", ondelete="CASCADE"), index=True)
    
    # Viewer Information
    viewer_ip = Column(INET)
    viewer_country = Column(CHAR(2))  # ISO country code
    referrer = Column(Text)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    credential = relationship("Credential", back_populates="views")
