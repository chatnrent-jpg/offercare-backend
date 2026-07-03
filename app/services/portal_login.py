"""Shared clinician portal login — email/password and session tokens."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import MarylandProvider
from app.services.demo_portal_lockable import ensure_demo_portal_lockable_shift
from app.services.demo_portal_accounts import (
    DEMO_PORTAL_PASSWORD,
    SAMPLE_DEMO_PORTAL_EMAIL,
    authenticate_demo_aware_clinician,
    ensure_demo_portal_accounts,
    ensure_portal_sample_clinician,
)


def bootstrap_portal_logins(db: Session) -> dict:
    """Ensure walkthrough demo clinician + portal passwords + lockable shift exist on API startup."""
    sample = ensure_portal_sample_clinician(db)
    accounts = ensure_demo_portal_accounts(db)
    lockable = ensure_demo_portal_lockable_shift(db)
    return {**sample, **accounts, **lockable}


def portal_email_password_login(db: Session, *, email: str, password: str) -> tuple[MarylandProvider, str]:
    """Authenticate email/password; auto-repair the signing-in demo account when needed."""
    from app.services.demo_portal_accounts import ensure_demo_portal_account_for_email

    normalized = str(email or "").strip().lower()
    if normalized.endswith("@offercare.demo"):
        ensure_demo_portal_account_for_email(db, normalized, password=password)
        if normalized == SAMPLE_DEMO_PORTAL_EMAIL:
            ensure_demo_portal_lockable_shift(db)
    provider = authenticate_demo_aware_clinician(db, email=normalized, password=password)
    token = create_access_token(provider.provider_id)
    return provider, token


def portal_demo_quick_login(db: Session) -> tuple[MarylandProvider, str]:
    """One-click demo login for portal walkthrough."""
    from app.services.demo_portal_accounts import ensure_demo_portal_account_for_email

    ensure_demo_portal_account_for_email(db, SAMPLE_DEMO_PORTAL_EMAIL)
    ensure_demo_portal_lockable_shift(db)
    return portal_email_password_login(
        db,
        email=SAMPLE_DEMO_PORTAL_EMAIL,
        password=DEMO_PORTAL_PASSWORD,
    )
