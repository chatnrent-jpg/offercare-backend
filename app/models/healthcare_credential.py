"""
Healthcare Credential Compliance Model - Phase 2: Integrity (Compliance)
SQLAlchemy model for tracking Maryland nursing credentials with OHCQ verification.

Links to MarylandProvider table for complete credential tracking.
"""

import uuid

from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, String, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


# Maryland License Type Constants
LICENSE_TYPE_CNA = "CNA"
LICENSE_TYPE_GNA = "GNA"
LICENSE_TYPE_LPN = "LPN"
LICENSE_TYPE_RN = "RN"
MARYLAND_LICENSE_TYPES = (LICENSE_TYPE_CNA, LICENSE_TYPE_GNA, LICENSE_TYPE_LPN, LICENSE_TYPE_RN)


class HealthcareCredential(Base):
    """
    Maryland healthcare credential compliance tracking.
    
    Links to MarylandProvider and enforces:
    - Valid Maryland license types (CNA, GNA, LPN, RN)
    - MBON license number tracking
    - Expiration date monitoring (must be future date)
    - OHCQ registry verification status
    - Background check clearance status
    
    Supports the Integrity pillar of the Intelgritty formula.
    """
    __tablename__ = "healthcare_credentials"
    
    # Table constraints and indexes
    __table_args__ = (
        CheckConstraint(
            f"license_type IN ('{LICENSE_TYPE_CNA}', '{LICENSE_TYPE_GNA}', "
            f"'{LICENSE_TYPE_LPN}', '{LICENSE_TYPE_RN}')",
            name="ck_healthcare_credentials_license_type",
        ),
        CheckConstraint(
            "expiration_date > CURRENT_DATE",
            name="ck_healthcare_credentials_not_expired",
        ),
        # Composite indexes for common queries
        Index("idx_healthcare_credentials_provider_license", "provider_id", "license_type"),
        Index("idx_healthcare_credentials_expiration", "expiration_date"),
        Index("idx_healthcare_credentials_verification", "is_ohcq_verified", "background_check_passed"),
    )
    
    # Primary key (UUID to match project conventions)
    credential_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Foreign key to MarylandProvider (cascade delete when provider removed)
    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maryland_providers.provider_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Credential details (matching Pydantic schema)
    license_type = Column(
        String(10),
        nullable=False,
    )
    
    license_number = Column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )
    
    expiration_date = Column(
        Date,
        nullable=False,
        index=True,
    )
    
    # Verification status flags (matching Pydantic schema)
    is_ohcq_verified = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    
    background_check_passed = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    
    # Audit timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    # Optional: verification audit trail
    ohcq_verified_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    background_check_completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Optional: Additional compliance metadata
    verification_notes = Column(
        String(1000),
        nullable=True,
    )
    
    def __repr__(self):
        return (
            f"<HealthcareCredential("
            f"credential_id={self.credential_id}, "
            f"provider_id={self.provider_id}, "
            f"license_type={self.license_type}, "
            f"license_number={self.license_number}, "
            f"expires={self.expiration_date}, "
            f"ohcq_verified={self.is_ohcq_verified}, "
            f"background_cleared={self.background_check_passed})>"
        )


# Alias for backward compatibility
HealthcareCredentialModel = HealthcareCredential
