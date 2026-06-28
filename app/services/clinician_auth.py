"""Clinician portal accounts and login."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.models import ClinicianPortalAccount, LicenseVerificationLog, MarylandProvider


def create_portal_account(
    db: Session,
    provider_id: UUID,
    password: str,
    *,
    commit: bool = True,
) -> ClinicianPortalAccount:
    existing = (
        db.query(ClinicianPortalAccount)
        .filter(ClinicianPortalAccount.provider_id == provider_id)
        .first()
    )
    if existing is not None:
        raise ValueError("portal_account_exists")
    account = ClinicianPortalAccount(
        provider_id=provider_id,
        password_hash=hash_password(password),
    )
    db.add(account)
    try:
        if commit:
            db.commit()
        else:
            db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("portal_account_exists") from exc
    db.refresh(account)
    return account


def authenticate_clinician(db: Session, *, email: str, password: str) -> MarylandProvider:
    normalized_email = str(email).strip().lower()
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email.ilike(normalized_email))
        .first()
    )
    if provider is None:
        raise ValueError("invalid_credentials")
    account = (
        db.query(ClinicianPortalAccount)
        .filter(ClinicianPortalAccount.provider_id == provider.provider_id)
        .first()
    )
    if account is None or not verify_password(password, account.password_hash):
        raise ValueError("invalid_credentials")
    return provider


def get_clinician_application_status(db: Session, provider_id: UUID) -> dict:
    provider = db.query(MarylandProvider).filter(MarylandProvider.provider_id == provider_id).first()
    if provider is None:
        raise ValueError("provider_not_found")
    history = (
        db.query(LicenseVerificationLog)
        .filter(LicenseVerificationLog.provider_id == provider_id)
        .order_by(LicenseVerificationLog.created_at.asc())
        .all()
    )
    portal = (
        db.query(ClinicianPortalAccount)
        .filter(ClinicianPortalAccount.provider_id == provider_id)
        .first()
    )
    return {
        "provider": provider,
        "portal_enabled": portal is not None,
        "verification_history": history,
    }
