"""Ensure @offercare.demo clinicians can sign in at /portal."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import ClinicianPortalAccount, MarylandProvider
from app.services.clinician_auth import create_portal_account

DEMO_PORTAL_PASSWORD = "SecretPass1"


def ensure_demo_portal_accounts(
    db: Session,
    *,
    password: str = DEMO_PORTAL_PASSWORD,
    commit: bool = True,
) -> dict:
    providers = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email.like("%@offercare.demo"))
        .order_by(MarylandProvider.email.asc())
        .all()
    )
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
