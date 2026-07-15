"""
VettedMe Passport - Core Database Models

This module defines the passport and credential badge infrastructure
for the W3C Verifiable Credentials system.
"""

import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, String, DateTime, Integer, Boolean, Text, ForeignKey, CheckConstraint, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from app.database import Base


class Passport(Base):
    """
    Core passport entity. Each user has ONE passport containing multiple credential badges.
    
    The passport acts as a cryptographic container for verified credentials,
    enabling instant, tamper-proof verification across platforms.
    """
    __tablename__ = "passports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    public_key = Column(Text, nullable=False, doc="Ed25519 public key for cryptographic verification")
    status = Column(String(20), nullable=False, default="ACTIVE", doc="ACTIVE, SUSPENDED, or REVOKED")
    issued_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False, doc="Passport renewal cycle (typically 2 years)")
    biometric_hash = Column(Text, nullable=True, doc="Secure hash of facial biometric for liveness checks")
    trust_score = Column(Integer, default=0, nullable=False, doc="Algorithmic trust rating (0-100)")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    badges = relationship("CredentialBadge", back_populates="passport", cascade="all, delete-orphan")
    verification_logs = relationship("VerificationLog", back_populates="passport", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("trust_score >= 0 AND trust_score <= 100", name="trust_score_range"),
    )
    
    def __repr__(self):
        return f"<Passport(id={self.id}, user_id={self.user_id}, status={self.status}, trust_score={self.trust_score})>"
    
    def is_active(self) -> bool:
        """Check if passport is active and not expired."""
        return (
            self.status == "ACTIVE" and
            self.expires_at > datetime.now(timezone.utc)
        )
    
    def get_active_badges(self) -> list:
        """Return all active (non-revoked, non-expired) badges."""
        now = datetime.now(timezone.utc)
        return [
            badge for badge in self.badges
            if not badge.revoked and (badge.expires_at is None or badge.expires_at > now)
        ]


class CredentialBadge(Base):
    """
    Modular credential badge attached to a passport.
    
    Each badge represents a specific verified credential (identity, employment, education, etc.)
    with cryptographic signature for tamper-proof verification.
    
    Badge Types:
    - IDENTITY: Government ID + biometric liveness
    - EMPLOYMENT: Verified work history
    - EDUCATION: Verified degrees/certifications
    - COMPLIANCE: Background check + criminal record
    - HEALTHCARE: State nursing licenses (RN/LPN/CNA)
    - DEVELOPER: GitHub + technical assessments
    - PROFESSIONAL: CPA, EA, Bar admission, etc.
    """
    __tablename__ = "credential_badges"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    passport_id = Column(UUID(as_uuid=True), ForeignKey("passports.id", ondelete="CASCADE"), nullable=False)
    badge_type = Column(String(50), nullable=False, doc="Type of credential (IDENTITY, HEALTHCARE, etc.)")
    credential_data = Column(JSONB, nullable=False, doc="Flexible schema containing credential details")
    issuer_signature = Column(Text, nullable=False, doc="Ed25519 cryptographic signature from VettedMe")
    verification_method = Column(String(50), nullable=False, doc="Method used to verify (MBON_SCRAPER, MANUAL_REVIEW, OCR_AI)")
    verified_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=True, doc="Credential-specific expiration (if applicable)")
    revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revocation_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    passport = relationship("Passport", back_populates="badges")
    
    def __repr__(self):
        return f"<CredentialBadge(id={self.id}, badge_type={self.badge_type}, revoked={self.revoked})>"
    
    def is_valid(self) -> bool:
        """Check if badge is valid (not revoked and not expired)."""
        if self.revoked:
            return False
        if self.expires_at and self.expires_at < datetime.now(timezone.utc):
            return False
        return True
    
    def revoke(self, reason: str):
        """Revoke this credential badge."""
        self.revoked = True
        self.revoked_at = datetime.now(timezone.utc)
        self.revocation_reason = reason


class VerificationLog(Base):
    """
    Audit trail for all verification API requests.
    
    Logs every external platform's verification request for compliance,
    security monitoring, and usage analytics.
    """
    __tablename__ = "verification_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    passport_id = Column(UUID(as_uuid=True), ForeignKey("passports.id", ondelete="CASCADE"), nullable=False)
    requesting_platform = Column(String(255), nullable=False, doc="Domain or name of requesting platform")
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=False)
    requested_badges = Column(ARRAY(String), nullable=False, doc="List of badge types requested")
    verification_result = Column(JSONB, nullable=False, doc="Full verification response payload")
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Relationships
    passport = relationship("Passport", back_populates="verification_logs")
    api_key = relationship("APIKey", back_populates="verification_logs")
    
    def __repr__(self):
        return f"<VerificationLog(id={self.id}, platform={self.requesting_platform}, timestamp={self.timestamp})>"


class APIKey(Base):
    """
    API key management for external platforms integrating VettedMe verification.
    
    Supports tiered pricing model with rate limiting:
    - Free: 100 verifications/hour
    - Growth: 10,000 verifications/hour
    - Enterprise: Unlimited
    """
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_name = Column(String(255), nullable=False)
    key_hash = Column(Text, nullable=False, unique=True, doc="SHA256 hash of the API key")
    key_prefix = Column(String(20), nullable=False, doc="First 8 chars for identification (e.g., 'vettedme_')")
    tier = Column(String(20), nullable=False, default="FREE", doc="FREE, GROWTH, or ENTERPRISE")
    rate_limit_per_hour = Column(Integer, nullable=False, default=100)
    status = Column(String(20), nullable=False, default="ACTIVE", doc="ACTIVE, SUSPENDED, or REVOKED")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    verification_logs = relationship("VerificationLog", back_populates="api_key")
    
    def __repr__(self):
        return f"<APIKey(id={self.id}, organization={self.organization_name}, tier={self.tier}, status={self.status})>"
    
    def is_active(self) -> bool:
        """Check if API key is active and not expired."""
        if self.status != "ACTIVE":
            return False
        if self.expires_at and self.expires_at < datetime.now(timezone.utc):
            return False
        return True
    
    def record_usage(self):
        """Update last_used_at timestamp."""
        self.last_used_at = datetime.now(timezone.utc)
