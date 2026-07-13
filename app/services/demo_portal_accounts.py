"""Ensure demo and local test clinicians can sign in at /portal."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import ClinicianPortalAccount, MarylandProvider
from app.services.clinician_auth import create_portal_account

DEMO_PORTAL_PASSWORD = "SecretPass1"
SAMPLE_DEMO_PORTAL_EMAIL = "nj.snf.cna.a@offercare.demo"

_PORTAL_EMAIL_SUFFIXES = (
    "%@offercare.demo",
    "%@vettedme.slice",
)

_DEMO_SEED_GROUPS: tuple[tuple[frozenset[str], str], ...] = (
    (
        frozenset(
            {
                "nurse.a@offercare.demo",
                "nurse.b@offercare.demo",
                "nurse.c@offercare.demo",
            }
        ),
        "seed_saint_judes_demo",
    ),
    (
        frozenset({"va.nurse.a@offercare.demo", "va.nurse.b@offercare.demo"}),
        "seed_inova_fairfax_demo",
    ),
    (
        frozenset({"nj.nurse.a@offercare.demo", "nj.nurse.b@offercare.demo"}),
        "seed_hackensack_demo",
    ),
    (
        frozenset(
            {
                "snf.lpn.a@offercare.demo",
                "snf.cna.a@offercare.demo",
                "snf.gna.a@offercare.demo",
            }
        ),
        "seed_nursing_home_demo",
    ),
    (
        frozenset({"dc.snf.gna.a@offercare.demo", "dc.snf.cna.a@offercare.demo"}),
        "seed_dc_nursing_home_demo",
    ),
    (
        frozenset({"va.snf.lpn.a@offercare.demo", "va.snf.cna.a@offercare.demo"}),
        "seed_va_nursing_home_demo",
    ),
    (
        frozenset({"pa.snf.lpn.a@offercare.demo", "pa.snf.cna.a@offercare.demo"}),
        "seed_pa_nursing_home_demo",
    ),
    (
        frozenset({"de.snf.lpn.a@offercare.demo", "de.snf.cna.a@offercare.demo"}),
        "seed_de_nursing_home_demo",
    ),
    (
        frozenset({"nj.snf.lpn.a@offercare.demo", "nj.snf.cna.a@offercare.demo"}),
        "seed_nj_nursing_home_demo",
    ),
    (
        frozenset(
            {
                "hh.rn.a@offercare.demo",
                "hh.lpn.a@offercare.demo",
                "hh.cna.a@offercare.demo",
            }
        ),
        "seed_home_health_demo",
    ),
)


def _demo_seed_runner(seed_name: str) -> Callable[[Session], dict]:
    from app import seed as seed_mod

    runner = getattr(seed_mod, seed_name, None)
    if runner is None:
        raise ValueError(f"unknown_demo_seed:{seed_name}")
    return runner


def ensure_demo_seed_clinician(db: Session, email: str) -> bool:
    """Create a walkthrough demo clinician when the DB has portal accounts but not the seed row."""
    normalized = _normalize_portal_email(email)
    if not normalized.endswith("@offercare.demo"):
        return False
    exists = (
        db.query(MarylandProvider.provider_id)
        .filter(MarylandProvider.email.ilike(normalized))
        .first()
    )
    if exists is not None:
        return True
    for emails, seed_name in _DEMO_SEED_GROUPS:
        if normalized not in emails:
            continue
        _demo_seed_runner(seed_name)(db)
        ensure_demo_portal_accounts(db)
        return (
            db.query(MarylandProvider.provider_id)
            .filter(MarylandProvider.email.ilike(normalized))
            .first()
            is not None
        )
    return False


def ensure_portal_sample_clinician(db: Session) -> dict:
    ready = ensure_demo_seed_clinician(db, SAMPLE_DEMO_PORTAL_EMAIL)
    return {"sample_clinician_ready": ready, "sample_email": SAMPLE_DEMO_PORTAL_EMAIL}

def _portal_eligible_providers(db: Session) -> list[MarylandProvider]:
    return (
        db.query(MarylandProvider)
        .filter(
            or_(*[MarylandProvider.email.like(suffix) for suffix in _PORTAL_EMAIL_SUFFIXES])
        )
        .order_by(MarylandProvider.email.asc())
        .all()
    )


def ensure_demo_portal_account_for_email(
    db: Session,
    email: str,
    *,
    password: str = DEMO_PORTAL_PASSWORD,
) -> bool:
    """Ensure one demo clinician can sign in without scanning the whole demo roster."""
    normalized = _normalize_portal_email(email)
    if not normalized.endswith("@offercare.demo"):
        return False
    ensure_demo_seed_clinician(db, normalized)
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email.ilike(normalized))
        .first()
    )
    if provider is None:
        return False
    password_hash = hash_password(password)
    account = (
        db.query(ClinicianPortalAccount)
        .filter(ClinicianPortalAccount.provider_id == provider.provider_id)
        .first()
    )
    if account is None:
        create_portal_account(db, provider.provider_id, password, commit=True)
    else:
        account.password_hash = password_hash
        db.commit()
    return True


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
            if ensure_demo_seed_clinician(db, normalized):
                ensure_demo_portal_account_for_email(db, normalized, password=password)
                return authenticate_clinician(db, email=normalized, password=password)
            raise ValueError("demo_clinician_not_seeded") from exc
        ensure_demo_portal_account_for_email(db, normalized, password=password)
        return authenticate_clinician(db, email=normalized, password=password)
