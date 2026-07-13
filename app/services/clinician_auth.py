"""
VettedMe Enterprise Engine - Clinician Authentication Service
Portal account management for Maryland providers with secure authentication.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.models import ClinicianPortalAccount, MarylandProvider


def create_portal_account(
    db: Session,
    provider_id: UUID,
    password: str,
    *,
    commit: bool = True,
) -> ClinicianPortalAccount:
    """
    Create a new clinician portal account for a Maryland provider.
    
    Args:
        db: Database session
        provider_id: UUID of the Maryland provider
        password: Plain text password (will be hashed)
        commit: Whether to commit the transaction (default True)
    
    Returns:
        Created ClinicianPortalAccount instance
    
    Raises:
        ValueError: If provider doesn't exist or account already exists
    """
    # Verify provider exists
    provider = db.query(MarylandProvider).filter(
        MarylandProvider.provider_id == provider_id
    ).first()
    
    if provider is None:
        raise ValueError(f"provider_not_found:{provider_id}")
    
    # Check if account already exists
    existing_account = db.query(ClinicianPortalAccount).filter(
        ClinicianPortalAccount.provider_id == provider_id
    ).first()
    
    if existing_account is not None:
        raise ValueError(f"portal_account_exists:{provider_id}")
    
    # Create new portal account
    password_hash = hash_password(password)
    
    account = ClinicianPortalAccount(
        provider_id=provider_id,
        password_hash=password_hash,
    )
    
    db.add(account)
    
    if commit:
        db.commit()
        db.refresh(account)
    
    return account


def authenticate_clinician(
    db: Session,
    *,
    email: str,
    password: str,
) -> MarylandProvider:
    """
    Authenticate a clinician using email and password.
    
    Args:
        db: Database session
        email: Provider email address
        password: Plain text password
    
    Returns:
        Authenticated MarylandProvider instance
    
    Raises:
        ValueError: If credentials are invalid
    """
    # Find provider by email
    provider = db.query(MarylandProvider).filter(
        MarylandProvider.email.ilike(email.strip())
    ).first()
    
    if provider is None:
        raise ValueError("invalid_credentials")
    
    # Find portal account
    account = db.query(ClinicianPortalAccount).filter(
        ClinicianPortalAccount.provider_id == provider.provider_id
    ).first()
    
    if account is None:
        raise ValueError("invalid_credentials")
    
    # Verify password
    if not verify_password(password, account.password_hash):
        raise ValueError("invalid_credentials")
    
    return provider


def get_clinician_application_status(
    db: Session,
    provider_id: UUID,
) -> dict:
    """
    Get application status for a clinician.
    
    Args:
        db: Database session
        provider_id: Provider UUID
    
    Returns:
        dict with application status details
    """
    # Query provider
    provider = db.query(MarylandProvider).filter(
        MarylandProvider.provider_id == provider_id
    ).first()
    
    if provider is None:
        raise ValueError(f"provider_not_found:{provider_id}")
    
    # Minimal stub implementation
    # TODO: Implement full application status logic with:
    # - Application stage (pending, approved, rejected)
    # - Required documents status
    # - Compliance checks status
    # - Onboarding progress
    
    return {
        "provider_id": str(provider_id),
        "application_status": "PENDING",
        "stage": "INITIAL_SCREENING",
        "documents_complete": False,
        "compliance_cleared": False,
        "message": "Application status stub - full implementation pending",
    }
