"""Seed PostgreSQL with Montgomery SNF CNA production slice (idempotent)."""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.database import SessionLocal
from app.models import (
    MdMarketFacility,
    MdProviderCompliance,
    MarylandFacility,
    MarylandProvider,
    OfferCareJobOffer,
)
from app.services.care_taxonomy import synthetic_npi_for_caregiver
from app.services.compliance_monitor import seed_default_compliance_documents
from app.services.vetted_status import VETTED_CLEAR
from app.services.worker_consent import WORKER_CONSENT_VERSION, provider_has_sms_dispatch_consent, record_apply_consents

SLICE_COUNTY = "Montgomery"
FACILITY_NAME = "Arbor Ridge at Riderwood"
MD_LICENSE = "MD-SNF-215343"

PROVIDERS = [
    {
        "full_name": "Aisha Thompson",
        "email": "aisha.thompson@vettedcare.slice",
        "phone_number": "3015558842",
        "md_license_number": "CNA-MD-88421",
        "has_gna_endorsement": True,
        "home_county": SLICE_COUNTY,
    },
    {
        "full_name": "Nia Patterson",
        "email": "nia.patterson@vettedcare.slice",
        "phone_number": "3015559901",
        "md_license_number": "CNA-MD-99001",
        "has_gna_endorsement": True,
        "home_county": SLICE_COUNTY,
    },
    {
        "full_name": "Jordan Ellis",
        "email": "jordan.ellis@vettedcare.slice",
        "phone_number": "3015559902",
        "md_license_number": "CNA-MD-99002",
        "has_gna_endorsement": True,
        "home_county": SLICE_COUNTY,
    },
]


def _ensure_maryland_facility(db, market: MdMarketFacility) -> MarylandFacility:
    if market.maryland_facility_id:
        linked = db.query(MarylandFacility).filter(MarylandFacility.facility_id == market.maryland_facility_id).first()
        if linked:
            return linked

    row = MarylandFacility(
        name=market.company_name,
        facility_type="NURSING_HOME",
        county=f"{SLICE_COUNTY} County",
        state="MD",
    )
    db.add(row)
    db.flush()
    market.maryland_facility_id = row.facility_id
    db.add(market)
    db.flush()
    return row


def _upsert_provider(db, spec: dict) -> MarylandProvider:
    row = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.md_license_number == spec["md_license_number"])
        .first()
    )
    if row is None:
        row = MarylandProvider(
            full_name=spec["full_name"],
            email=spec["email"],
            phone_number=spec["phone_number"],
            npi_number=synthetic_npi_for_caregiver(spec["email"]),
            md_license_number=spec["md_license_number"],
            state="MD",
            credential_type="CNA",
            service_lines="NURSING_HOME",
            license_status="VERIFIED",
            min_hourly_rate=30.0,
            response_propensity=0.85,
            fatigue_score=0.0,
            dispatch_status="ACTIVE",
            vetted_status=VETTED_CLEAR,
            license_expires_on=datetime.now(timezone.utc) + timedelta(days=365),
        )
        db.add(row)
        db.flush()
        seed_default_compliance_documents(db, row, license_expires_on=row.license_expires_on)
    else:
        row.vetted_status = VETTED_CLEAR
        row.license_status = "VERIFIED"
        row.dispatch_status = "ACTIVE"

    compliance = (
        db.query(MdProviderCompliance)
        .filter(MdProviderCompliance.provider_id == row.provider_id)
        .first()
    )
    if compliance is None:
        compliance = MdProviderCompliance(
            provider_id=row.provider_id,
            credential_type="CNA",
            license_number=spec["md_license_number"],
            has_gna_endorsement=spec["has_gna_endorsement"],
            license_expires_on=row.license_expires_on,
            compliance_status="COMPLIANT",
            home_county=spec["home_county"],
        )
        db.add(compliance)
    else:
        compliance.has_gna_endorsement = spec["has_gna_endorsement"]
        compliance.compliance_status = "COMPLIANT"
        compliance.home_county = spec["home_county"]

    if not provider_has_sms_dispatch_consent(db, row.provider_id, email=row.email, provider=row):
        record_apply_consents(db, row.provider_id, consent_version=WORKER_CONSENT_VERSION, commit=False)
    db.flush()
    return row


def main() -> None:
    db = SessionLocal()
    try:
        market = (
            db.query(MdMarketFacility)
            .filter(MdMarketFacility.md_license_number == MD_LICENSE)
            .first()
        )
        if market is None:
            raise SystemExit(
                "MdMarketFacility MD-SNF-215343 not found. "
                "Run scripts/import_md_facilities_scraped.py first."
            )

        md_facility = _ensure_maryland_facility(db, market)
        providers = [_upsert_provider(db, spec) for spec in PROVIDERS]
        primary = providers[0]

        shift_start = datetime.now(timezone.utc).replace(hour=7, minute=0, second=0, microsecond=0) + timedelta(days=1)
        shift_end = shift_start + timedelta(hours=8)

        offer = (
            db.query(OfferCareJobOffer)
            .filter(OfferCareJobOffer.facility_id == md_facility.facility_id)
            .filter(OfferCareJobOffer.assigned_provider_id == primary.provider_id)
            .first()
        )
        if offer is None:
            offer = OfferCareJobOffer(
                facility_id=md_facility.facility_id,
                shift_role="CNA",
                hourly_pay_rate=30.0,
                compliance_lock_status="LOCKED",
                assigned_provider_id=primary.provider_id,
                shift_starts_at=shift_start,
                shift_ends_at=shift_end,
            )
            db.add(offer)
        else:
            offer.shift_starts_at = shift_start
            offer.shift_ends_at = shift_end
            offer.compliance_lock_status = "LOCKED"

        db.commit()
        print("Montgomery SNF CNA production slice seeded.")
        print(f"  facility: {market.company_name} ({MD_LICENSE})")
        print(f"  providers: {len(providers)} Montgomery GNA CNAs")
        print(f"  active commitment: {primary.md_license_number} -> offer {offer.offer_id}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
