"""Ensure demo and local test clinicians can sign in at /portal."""

from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import ClinicianPortalAccount, MarylandProvider
from app.services.clinician_auth import create_portal_account

DEMO_PORTAL_PASSWORD = "SecretPass1"

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
