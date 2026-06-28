"""Ensure demo and local test clinicians can sign in at /portal."""

from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import ClinicianPortalAccount, MarylandProvider
from app.services.clinician_auth import create_portal_account

DEMO_PORTAL_PASSWORD = "SecretPass1"
SAMPLE_DEMO_PORTAL_EMAIL = "nj.snf.cna.a@offercare.demo"

_PORTAL_EMAIL_SUFFIXES = (
    "%@offercare.demo",
    "%@vettedcare.slice",
)


def _portal_eligible_providers(db: Session) -> list[MarylandProvider]:
    return (
        db.query(MarylandProvider)
        .filter(
            or_(*[MarylandProvider.email.like(suffix) for suffix in _PORTAL_EMAIL_SUFFIXES])
        )
        .order_by(MarylandProvider.email.asc())
        .all()
    )


def ensure_demo_portal_accounts(
    db: Session,
    *,
    password: str = DEMO_PORTAL_PASSWORD,
    commit: bool = True,
) -> dict:
    providers = _portal_eligible_providers(db)
    created = 0
    updated = 0
    password_hash = hash_password(password)
    for provider in providers:
        account = (
            db.query(ClinicianPortalAccount)
            .filter(ClinicianPortalAccount.provider_id == provider.provider_id)
            .first()
        )
        if account is None:
            create_portal_account(db, provider.provider_id, password, commit=False)
            created += 1
        else:
            account.password_hash = password_hash
            updated += 1

    if commit:
        db.commit()

    return {
        "clinician_count": len(providers),
        "created": created,
        "updated": updated,
        "password_hint": password,
    }


def _normalize_portal_email(email: str) -> str:
    return str(email or "").strip().lower()


def _is_incomplete_demo_email(email: str) -> bool:
    normalized = _normalize_portal_email(email)
    return normalized in {"@offercare.demo", "offercare.demo"} or (
        normalized.startswith("@") and normalized.endswith("offercare.demo")
    )


def authenticate_demo_aware_clinician(db: Session, *, email: str, password: str) -> MarylandProvider:
    """Authenticate portal login; auto-provision @offercare.demo accounts when missing."""
    from app.services.clinician_auth import authenticate_clinician

    normalized = _normalize_portal_email(email)
    if _is_incomplete_demo_email(normalized):
        raise ValueError("demo_email_requires_local_part")

    try:
        return authenticate_clinician(db, email=normalized, password=password)
    except ValueError as exc:
        if str(exc) != "invalid_credentials" or not normalized.endswith("@offercare.demo"):
            raise
        provider = (
            db.query(MarylandProvider)
            .filter(MarylandProvider.email.ilike(normalized))
            .first()
        )
        if provider is None:
            raise ValueError("demo_clinician_not_seeded") from exc
        ensure_demo_portal_accounts(db)
        return authenticate_clinician(db, email=normalized, password=password)
