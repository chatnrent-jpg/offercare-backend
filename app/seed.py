"""Load Saint Jude's ICU demo clinicians into PostgreSQL."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import MarylandFacility, MarylandProvider, OfferCareJobOffer
from app.services.shift_schedule import apply_default_shift_schedule

DEMO_FACILITY_NAMES: tuple[str, ...] = (
    "Saint Jude's ICU",
    "Inova Fairfax ICU",
    "Hackensack Meridian ICU",
    "Cadia Healthcare Nursing Home",
    "Capitol Hill SNF",
    "Virginia SNF at Arlington",
    "Philadelphia SNF at Center City",
    "Wilmington SNF at Riverfront",
    "Paramus SNF at Bergen",
    "Bayada Home Health Mid-Atlantic",
)

DEMO_SEED_CLINICIAN_EMAILS: frozenset[str] = frozenset(
    {
        "nurse.a@offercare.demo",
        "nurse.b@offercare.demo",
        "nurse.c@offercare.demo",
        "va.nurse.a@offercare.demo",
        "va.nurse.b@offercare.demo",
        "nj.nurse.a@offercare.demo",
        "nj.nurse.b@offercare.demo",
        "snf.lpn.a@offercare.demo",
        "snf.cna.a@offercare.demo",
        "snf.gna.a@offercare.demo",
        "dc.snf.gna.a@offercare.demo",
        "dc.snf.cna.a@offercare.demo",
        "va.snf.lpn.a@offercare.demo",
        "va.snf.cna.a@offercare.demo",
        "pa.snf.lpn.a@offercare.demo",
        "pa.snf.cna.a@offercare.demo",
        "de.snf.lpn.a@offercare.demo",
        "de.snf.cna.a@offercare.demo",
        "nj.snf.lpn.a@offercare.demo",
        "nj.snf.cna.a@offercare.demo",
        "hh.rn.a@offercare.demo",
        "hh.lpn.a@offercare.demo",
        "hh.cna.a@offercare.demo",
    }
)


def seed_saint_judes_demo(db: Session) -> dict[str, str]:
    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.name == "Saint Jude's ICU")
        .first()
    )
    if facility is None:
        facility = MarylandFacility(
            name="Saint Jude's ICU",
            facility_type="HOSPITAL",
            county="Baltimore County",
            state="MD",
            vms_integration_type="SCRAPE",
        )
        db.add(facility)
        db.flush()

    demo_providers = [
        {
            "full_name": "Nurse A",
            "email": "nurse.a@offercare.demo",
            "phone_number": "+14105550001",
            "npi_number": "1000000001",
            "md_license_number": "RN-MD-A001",
            "credential_type": "RN",
            "service_lines": "HOSPITAL",
            "state": "MD",
            "license_status": "VERIFIED",
            "min_hourly_rate": 85.0,
            "response_propensity": 0.85,
            "fatigue_score": 0.0,
        },
        {
            "full_name": "Nurse B",
            "email": "nurse.b@offercare.demo",
            "phone_number": "+14105550002",
            "npi_number": "1000000002",
            "md_license_number": "RN-MD-B002",
            "credential_type": "RN",
            "service_lines": "HOSPITAL",
            "state": "MD",
            "license_status": "VERIFIED",
            "min_hourly_rate": 110.0,
            "response_propensity": 0.95,
            "fatigue_score": 1.0,
        },
        {
            "full_name": "Nurse C",
            "email": "nurse.c@offercare.demo",
            "phone_number": "+14105550003",
            "npi_number": "1000000003",
            "md_license_number": "RN-MD-C003",
            "credential_type": "RN",
            "service_lines": "HOSPITAL",
            "state": "MD",
            "license_status": "VERIFIED",
            "min_hourly_rate": 130.0,
            "response_propensity": 0.80,
            "fatigue_score": 0.0,
        },
    ]

    provider_ids: list[str] = []
    for row in demo_providers:
        provider = db.query(MarylandProvider).filter(MarylandProvider.email == row["email"]).first()
        if provider is None:
            provider = MarylandProvider(**row)
            db.add(provider)
            db.flush()
        else:
            for key, value in row.items():
                setattr(provider, key, value)
        provider_ids.append(str(provider.provider_id))

    offer = (
        db.query(OfferCareJobOffer)
        .filter(
            OfferCareJobOffer.facility_id == facility.facility_id,
            OfferCareJobOffer.shift_role == "ICU_RN",
            OfferCareJobOffer.hourly_pay_rate == 120.0,
        )
        .first()
    )
    if offer is None:
        offer = OfferCareJobOffer(
            facility_id=facility.facility_id,
            shift_role="ICU_RN",
            hourly_pay_rate=120.0,
            compliance_lock_status="BROADCASTING",
        )
        db.add(offer)
        db.flush()
    else:
        offer.compliance_lock_status = "BROADCASTING"
        offer.assigned_provider_id = None
    apply_default_shift_schedule(offer)

    db.commit()
    return {
        "facility_id": str(facility.facility_id),
        "offer_id": str(offer.offer_id),
        "provider_ids": ",".join(provider_ids),
        "facility_type": "HOSPITAL",
        "state": "MD",
    }


def seed_inova_fairfax_demo(db: Session) -> dict[str, str]:
    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.name == "Inova Fairfax ICU")
        .first()
    )
    if facility is None:
        facility = MarylandFacility(
            name="Inova Fairfax ICU",
            facility_type="HOSPITAL",
            county="Fairfax County",
            state="VA",
            vms_integration_type="SCRAPE",
        )
        db.add(facility)
        db.flush()

    demo_providers = [
        {
            "full_name": "Virginia Nurse A",
            "email": "va.nurse.a@offercare.demo",
            "phone_number": "+17035550001",
            "npi_number": "1000000101",
            "md_license_number": "RN-VA-A001",
            "credential_type": "RN",
            "service_lines": "HOSPITAL",
            "state": "VA",
            "license_status": "VERIFIED",
            "min_hourly_rate": 90.0,
            "response_propensity": 0.88,
            "fatigue_score": 0.0,
        },
        {
            "full_name": "Virginia Nurse B",
            "email": "va.nurse.b@offercare.demo",
            "phone_number": "+17035550002",
            "npi_number": "1000000102",
            "md_license_number": "RN-VA-B002",
            "credential_type": "RN",
            "service_lines": "HOSPITAL",
            "state": "VA",
            "license_status": "VERIFIED",
            "min_hourly_rate": 105.0,
            "response_propensity": 0.92,
            "fatigue_score": 0.5,
        },
    ]

    provider_ids: list[str] = []
    for row in demo_providers:
        provider = db.query(MarylandProvider).filter(MarylandProvider.email == row["email"]).first()
        if provider is None:
            provider = MarylandProvider(**row)
            db.add(provider)
            db.flush()
        else:
            for key, value in row.items():
                setattr(provider, key, value)
        provider_ids.append(str(provider.provider_id))

    offer = (
        db.query(OfferCareJobOffer)
        .filter(
            OfferCareJobOffer.facility_id == facility.facility_id,
            OfferCareJobOffer.shift_role == "ICU_RN",
            OfferCareJobOffer.hourly_pay_rate == 118.0,
        )
        .first()
    )
    if offer is None:
        offer = OfferCareJobOffer(
            facility_id=facility.facility_id,
            shift_role="ICU_RN",
            hourly_pay_rate=118.0,
            compliance_lock_status="BROADCASTING",
        )
        db.add(offer)
        db.flush()
    else:
        offer.compliance_lock_status = "BROADCASTING"
        offer.assigned_provider_id = None
    apply_default_shift_schedule(offer)

    db.commit()
    return {
        "facility_id": str(facility.facility_id),
        "offer_id": str(offer.offer_id),
        "provider_ids": ",".join(provider_ids),
        "facility_type": "HOSPITAL",
        "state": "VA",
    }


def seed_hackensack_demo(db: Session) -> dict[str, str]:
    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.name == "Hackensack Meridian ICU")
        .first()
    )
    if facility is None:
        facility = MarylandFacility(
            name="Hackensack Meridian ICU",
            facility_type="HOSPITAL",
            county="Bergen County",
            state="NJ",
            vms_integration_type="SCRAPE",
        )
        db.add(facility)
        db.flush()

    demo_providers = [
        {
            "full_name": "New Jersey Nurse A",
            "email": "nj.nurse.a@offercare.demo",
            "phone_number": "+12015550001",
            "npi_number": "1000000201",
            "md_license_number": "RN-NJ-A001",
            "credential_type": "RN",
            "service_lines": "HOSPITAL",
            "state": "NJ",
            "license_status": "VERIFIED",
            "min_hourly_rate": 95.0,
            "response_propensity": 0.90,
            "fatigue_score": 0.0,
        },
        {
            "full_name": "New Jersey Nurse B",
            "email": "nj.nurse.b@offercare.demo",
            "phone_number": "+12015550002",
            "npi_number": "1000000202",
            "md_license_number": "RN-NJ-B002",
            "credential_type": "RN",
            "service_lines": "HOSPITAL",
            "state": "NJ",
            "license_status": "VERIFIED",
            "min_hourly_rate": 112.0,
            "response_propensity": 0.93,
            "fatigue_score": 0.25,
        },
    ]

    provider_ids: list[str] = []
    for row in demo_providers:
        provider = db.query(MarylandProvider).filter(MarylandProvider.email == row["email"]).first()
        if provider is None:
            provider = MarylandProvider(**row)
            db.add(provider)
            db.flush()
        else:
            for key, value in row.items():
                setattr(provider, key, value)
        provider_ids.append(str(provider.provider_id))

    offer = (
        db.query(OfferCareJobOffer)
        .filter(
            OfferCareJobOffer.facility_id == facility.facility_id,
            OfferCareJobOffer.shift_role == "ICU_RN",
            OfferCareJobOffer.hourly_pay_rate == 122.0,
        )
        .first()
    )
    if offer is None:
        offer = OfferCareJobOffer(
            facility_id=facility.facility_id,
            shift_role="ICU_RN",
            hourly_pay_rate=122.0,
            compliance_lock_status="BROADCASTING",
        )
        db.add(offer)
        db.flush()
    else:
        offer.compliance_lock_status = "BROADCASTING"
        offer.assigned_provider_id = None
    apply_default_shift_schedule(offer)

    db.commit()
    return {
        "facility_id": str(facility.facility_id),
        "offer_id": str(offer.offer_id),
        "provider_ids": ",".join(provider_ids),
        "facility_type": "HOSPITAL",
        "state": "NJ",
    }


def seed_nursing_home_demo(db: Session) -> dict[str, str]:
    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.name == "Cadia Healthcare Nursing Home")
        .first()
    )
    if facility is None:
        facility = MarylandFacility(
            name="Cadia Healthcare Nursing Home",
            facility_type="NURSING_HOME",
            county="Howard County",
            state="MD",
            vms_integration_type="SCRAPE",
        )
        db.add(facility)
        db.flush()

    demo_providers = [
        {
            "full_name": "SNF LPN A",
            "email": "snf.lpn.a@offercare.demo",
            "phone_number": "+14105551001",
            "npi_number": "1000000301",
            "md_license_number": "LPN-MD-A001",
            "credential_type": "LPN",
            "service_lines": "NURSING_HOME",
            "state": "MD",
            "license_status": "VERIFIED",
            "min_hourly_rate": 32.0,
            "response_propensity": 0.91,
            "fatigue_score": 0.0,
        },
        {
            "full_name": "SNF CNA A",
            "email": "snf.cna.a@offercare.demo",
            "phone_number": "+14105551002",
            "npi_number": "1000000302",
            "md_license_number": "CNA-MD-A001",
            "credential_type": "CNA",
            "service_lines": "NURSING_HOME,HOME_HEALTH",
            "state": "MD",
            "license_status": "VERIFIED",
            "min_hourly_rate": 16.0,
            "response_propensity": 0.89,
            "fatigue_score": 0.0,
        },
        {
            "full_name": "SNF GNA A",
            "email": "snf.gna.a@offercare.demo",
            "phone_number": "+14105551003",
            "npi_number": "1000000303",
            "md_license_number": "GNA-MD-A001",
            "credential_type": "GNA",
            "service_lines": "NURSING_HOME",
            "state": "MD",
            "license_status": "VERIFIED",
            "min_hourly_rate": 17.0,
            "response_propensity": 0.87,
            "fatigue_score": 0.0,
        },
    ]

    provider_ids = _upsert_demo_providers(db, demo_providers)
    offer = _upsert_demo_offer(
        db,
        facility_id=facility.facility_id,
        shift_role="LPN",
        hourly_pay_rate=42.0,
    )
    db.commit()
    return {
        "facility_id": str(facility.facility_id),
        "offer_id": str(offer.offer_id),
        "provider_ids": ",".join(provider_ids),
        "facility_type": "NURSING_HOME",
        "state": "MD",
    }


def seed_dc_nursing_home_demo(db: Session) -> dict[str, str]:
    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.name == "Capitol Hill SNF")
        .first()
    )
    if facility is None:
        facility = MarylandFacility(
            name="Capitol Hill SNF",
            facility_type="NURSING_HOME",
            county="District of Columbia",
            state="DC",
            vms_integration_type="SCRAPE",
        )
        db.add(facility)
        db.flush()

    demo_providers = [
        {
            "full_name": "DC SNF GNA A",
            "email": "dc.snf.gna.a@offercare.demo",
            "phone_number": "+12025551001",
            "npi_number": "1000000601",
            "md_license_number": "GNA-DC-A001",
            "credential_type": "GNA",
            "service_lines": "NURSING_HOME",
            "state": "DC",
            "license_status": "VERIFIED",
            "min_hourly_rate": 18.0,
            "response_propensity": 0.9,
            "fatigue_score": 0.0,
        },
        {
            "full_name": "DC SNF CNA A",
            "email": "dc.snf.cna.a@offercare.demo",
            "phone_number": "+12025551002",
            "npi_number": "1000000602",
            "md_license_number": "CNA-DC-A001",
            "credential_type": "CNA",
            "service_lines": "NURSING_HOME",
            "state": "DC",
            "license_status": "VERIFIED",
            "min_hourly_rate": 17.0,
            "response_propensity": 0.87,
            "fatigue_score": 0.0,
        },
    ]

    provider_ids = _upsert_demo_providers(db, demo_providers)
    offer = _upsert_demo_offer(
        db,
        facility_id=facility.facility_id,
        shift_role="GNA",
        hourly_pay_rate=26.0,
    )
    db.commit()
    return {
        "facility_id": str(facility.facility_id),
        "offer_id": str(offer.offer_id),
        "provider_ids": ",".join(provider_ids),
        "facility_type": "NURSING_HOME",
        "state": "DC",
    }


def seed_va_nursing_home_demo(db: Session) -> dict[str, str]:
    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.name == "Virginia SNF at Arlington")
        .first()
    )
    if facility is None:
        facility = MarylandFacility(
            name="Virginia SNF at Arlington",
            facility_type="NURSING_HOME",
            county="Arlington County",
            state="VA",
            vms_integration_type="SCRAPE",
        )
        db.add(facility)
        db.flush()

    demo_providers = [
        {
            "full_name": "VA SNF LPN A",
            "email": "va.snf.lpn.a@offercare.demo",
            "phone_number": "+17035551001",
            "npi_number": "1000000501",
            "md_license_number": "LPN-VA-A001",
            "credential_type": "LPN",
            "service_lines": "NURSING_HOME",
            "state": "VA",
            "license_status": "VERIFIED",
            "min_hourly_rate": 34.0,
            "response_propensity": 0.9,
            "fatigue_score": 0.0,
        },
        {
            "full_name": "VA SNF CNA A",
            "email": "va.snf.cna.a@offercare.demo",
            "phone_number": "+17035551002",
            "npi_number": "1000000502",
            "md_license_number": "CNA-VA-A001",
            "credential_type": "CNA",
            "service_lines": "NURSING_HOME",
            "state": "VA",
            "license_status": "VERIFIED",
            "min_hourly_rate": 17.0,
            "response_propensity": 0.88,
            "fatigue_score": 0.0,
        },
    ]

    provider_ids = _upsert_demo_providers(db, demo_providers)
    offer = _upsert_demo_offer(
        db,
        facility_id=facility.facility_id,
        shift_role="LPN",
        hourly_pay_rate=44.0,
    )
    db.commit()
    return {
        "facility_id": str(facility.facility_id),
        "offer_id": str(offer.offer_id),
        "provider_ids": ",".join(provider_ids),
        "facility_type": "NURSING_HOME",
        "state": "VA",
    }


def seed_pa_nursing_home_demo(db: Session) -> dict[str, str]:
    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.name == "Philadelphia SNF at Center City")
        .first()
    )
    if facility is None:
        facility = MarylandFacility(
            name="Philadelphia SNF at Center City",
            facility_type="NURSING_HOME",
            county="Philadelphia County",
            state="PA",
            vms_integration_type="SCRAPE",
        )
        db.add(facility)
        db.flush()

    demo_providers = [
        {
            "full_name": "PA SNF LPN A",
            "email": "pa.snf.lpn.a@offercare.demo",
            "phone_number": "+12155551001",
            "npi_number": "1000000801",
            "md_license_number": "LPN-PA-A001",
            "credential_type": "LPN",
            "service_lines": "NURSING_HOME",
            "state": "PA",
            "license_status": "VERIFIED",
            "min_hourly_rate": 33.0,
            "response_propensity": 0.89,
            "fatigue_score": 0.0,
        },
        {
            "full_name": "PA SNF CNA A",
            "email": "pa.snf.cna.a@offercare.demo",
            "phone_number": "+12155551002",
            "npi_number": "1000000802",
            "md_license_number": "CNA-PA-A001",
            "credential_type": "CNA",
            "service_lines": "NURSING_HOME",
            "state": "PA",
            "license_status": "VERIFIED",
            "min_hourly_rate": 16.0,
            "response_propensity": 0.88,
            "fatigue_score": 0.0,
        },
    ]

    provider_ids = _upsert_demo_providers(db, demo_providers)
    offer = _upsert_demo_offer(
        db,
        facility_id=facility.facility_id,
        shift_role="GNA",
        hourly_pay_rate=23.0,
    )
    db.commit()
    return {
        "facility_id": str(facility.facility_id),
        "offer_id": str(offer.offer_id),
        "provider_ids": ",".join(provider_ids),
        "facility_type": "NURSING_HOME",
        "state": "PA",
    }


def seed_de_nursing_home_demo(db: Session) -> dict[str, str]:
    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.name == "Wilmington SNF at Riverfront")
        .first()
    )
    if facility is None:
        facility = MarylandFacility(
            name="Wilmington SNF at Riverfront",
            facility_type="NURSING_HOME",
            county="New Castle County",
            state="DE",
            vms_integration_type="SCRAPE",
        )
        db.add(facility)
        db.flush()

    demo_providers = [
        {
            "full_name": "DE SNF LPN A",
            "email": "de.snf.lpn.a@offercare.demo",
            "phone_number": "+13025551001",
            "npi_number": "1000000901",
            "md_license_number": "LPN-DE-A001",
            "credential_type": "LPN",
            "service_lines": "NURSING_HOME",
            "state": "DE",
            "license_status": "VERIFIED",
            "min_hourly_rate": 32.0,
            "response_propensity": 0.88,
            "fatigue_score": 0.0,
        },
        {
            "full_name": "DE SNF CNA A",
            "email": "de.snf.cna.a@offercare.demo",
            "phone_number": "+13025551002",
            "npi_number": "1000000902",
            "md_license_number": "CNA-DE-A001",
            "credential_type": "CNA",
            "service_lines": "NURSING_HOME",
            "state": "DE",
            "license_status": "VERIFIED",
            "min_hourly_rate": 16.0,
            "response_propensity": 0.87,
            "fatigue_score": 0.0,
        },
    ]

    provider_ids = _upsert_demo_providers(db, demo_providers)
    offer = _upsert_demo_offer(
        db,
        facility_id=facility.facility_id,
        shift_role="GNA",
        hourly_pay_rate=23.0,
    )
    db.commit()
    return {
        "facility_id": str(facility.facility_id),
        "offer_id": str(offer.offer_id),
        "provider_ids": ",".join(provider_ids),
        "facility_type": "NURSING_HOME",
        "state": "DE",
    }


def seed_nj_nursing_home_demo(db: Session) -> dict[str, str]:
    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.name == "Paramus SNF at Bergen")
        .first()
    )
    if facility is None:
        facility = MarylandFacility(
            name="Paramus SNF at Bergen",
            facility_type="NURSING_HOME",
            county="Bergen County",
            state="NJ",
            vms_integration_type="SCRAPE",
        )
        db.add(facility)
        db.flush()

    demo_providers = [
        {
            "full_name": "NJ SNF LPN A",
            "email": "nj.snf.lpn.a@offercare.demo",
            "phone_number": "+12015552001",
            "npi_number": "1000001001",
            "md_license_number": "LPN-NJ-A001",
            "credential_type": "LPN",
            "service_lines": "NURSING_HOME",
            "state": "NJ",
            "license_status": "VERIFIED",
            "min_hourly_rate": 34.0,
            "response_propensity": 0.9,
            "fatigue_score": 0.0,
        },
        {
            "full_name": "NJ SNF CNA A",
            "email": "nj.snf.cna.a@offercare.demo",
            "phone_number": "+12015552002",
            "npi_number": "1000001002",
            "md_license_number": "CNA-NJ-A001",
            "credential_type": "CNA",
            "service_lines": "NURSING_HOME",
            "state": "NJ",
            "license_status": "VERIFIED",
            "min_hourly_rate": 17.0,
            "response_propensity": 0.88,
            "fatigue_score": 0.0,
        },
    ]

    provider_ids = _upsert_demo_providers(db, demo_providers)
    offer = _upsert_demo_offer(
        db,
        facility_id=facility.facility_id,
        shift_role="GNA",
        hourly_pay_rate=24.0,
    )
    db.commit()
    return {
        "facility_id": str(facility.facility_id),
        "offer_id": str(offer.offer_id),
        "provider_ids": ",".join(provider_ids),
        "facility_type": "NURSING_HOME",
        "state": "NJ",
    }


def seed_home_health_demo(db: Session) -> dict[str, str]:
    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.name == "Bayada Home Health Mid-Atlantic")
        .first()
    )
    if facility is None:
        facility = MarylandFacility(
            name="Bayada Home Health Mid-Atlantic",
            facility_type="HOME_HEALTH",
            county="Montgomery County",
            state="MD",
            vms_integration_type="SCRAPE",
        )
        db.add(facility)
        db.flush()

    demo_providers = [
        {
            "full_name": "Home Health RN A",
            "email": "hh.rn.a@offercare.demo",
            "phone_number": "+14105552001",
            "npi_number": "1000000401",
            "md_license_number": "RN-MD-HH001",
            "credential_type": "RN",
            "service_lines": "HOME_HEALTH",
            "state": "MD",
            "license_status": "VERIFIED",
            "min_hourly_rate": 48.0,
            "response_propensity": 0.90,
            "fatigue_score": 0.0,
        },
        {
            "full_name": "Home Health LPN A",
            "email": "hh.lpn.a@offercare.demo",
            "phone_number": "+14105552002",
            "npi_number": "1000000402",
            "md_license_number": "LPN-MD-HH001",
            "credential_type": "LPN",
            "service_lines": "HOME_HEALTH,NURSING_HOME",
            "state": "MD",
            "license_status": "VERIFIED",
            "min_hourly_rate": 30.0,
            "response_propensity": 0.88,
            "fatigue_score": 0.0,
        },
        {
            "full_name": "Home Health CNA A",
            "email": "hh.cna.a@offercare.demo",
            "phone_number": "+14105552003",
            "npi_number": "1000000403",
            "md_license_number": "CNA-MD-HH001",
            "credential_type": "CNA",
            "service_lines": "NURSING_HOME,HOME_HEALTH",
            "state": "MD",
            "license_status": "VERIFIED",
            "min_hourly_rate": 15.0,
            "response_propensity": 0.86,
            "fatigue_score": 0.0,
        },
    ]

    provider_ids = _upsert_demo_providers(db, demo_providers)
    offer = _upsert_demo_offer(
        db,
        facility_id=facility.facility_id,
        shift_role="HOME_HEALTH_RN",
        hourly_pay_rate=55.0,
    )
    db.commit()
    return {
        "facility_id": str(facility.facility_id),
        "offer_id": str(offer.offer_id),
        "provider_ids": ",".join(provider_ids),
        "facility_type": "HOME_HEALTH",
        "state": "MD",
    }


def seed_all_post_acute_demos(db: Session) -> dict:
    rows = [
        seed_nursing_home_demo(db),
        seed_va_nursing_home_demo(db),
        seed_dc_nursing_home_demo(db),
        seed_pa_nursing_home_demo(db),
        seed_de_nursing_home_demo(db),
        seed_nj_nursing_home_demo(db),
        seed_home_health_demo(db),
    ]
    demos = [
        {
            "state": row["state"],
            "facility_type": row["facility_type"],
            "facility_id": row["facility_id"],
            "offer_id": row["offer_id"],
        }
        for row in rows
    ]
    states = sorted({row["state"] for row in demos})
    return {"count": len(demos), "states": states, "demos": demos}


def seed_all_hospital_demos(db: Session) -> dict:
    rows = [
        seed_saint_judes_demo(db),
        seed_inova_fairfax_demo(db),
        seed_hackensack_demo(db),
    ]
    demos = [
        {
            "state": row["state"],
            "facility_type": row["facility_type"],
            "facility_id": row["facility_id"],
            "offer_id": row["offer_id"],
        }
        for row in rows
    ]
    states = sorted({row["state"] for row in demos})
    return {"count": len(demos), "states": states, "demos": demos}


def seed_all_mid_atlantic_demos(db: Session) -> dict:
    from app.services.demo_portal_accounts import ensure_demo_portal_accounts

    hospital = seed_all_hospital_demos(db)
    post_acute = seed_all_post_acute_demos(db)
    portal_accounts = ensure_demo_portal_accounts(db)
    states = sorted(set(hospital["states"]) | set(post_acute["states"]))
    return {
        "count": hospital["count"] + post_acute["count"],
        "states": states,
        "hospital": hospital,
        "post_acute": post_acute,
        "portal_accounts": portal_accounts,
    }


def _upsert_demo_providers(db: Session, demo_providers: list[dict]) -> list[str]:
    provider_ids: list[str] = []
    for row in demo_providers:
        provider = db.query(MarylandProvider).filter(MarylandProvider.email == row["email"]).first()
        if provider is None:
            provider = MarylandProvider(**row)
            db.add(provider)
            db.flush()
        else:
            for key, value in row.items():
                setattr(provider, key, value)
        provider_ids.append(str(provider.provider_id))
    return provider_ids


def _upsert_demo_offer(
    db: Session,
    *,
    facility_id,
    shift_role: str,
    hourly_pay_rate: float,
) -> OfferCareJobOffer:
    offer = (
        db.query(OfferCareJobOffer)
        .filter(
            OfferCareJobOffer.facility_id == facility_id,
            OfferCareJobOffer.shift_role == shift_role,
            OfferCareJobOffer.hourly_pay_rate == hourly_pay_rate,
        )
        .first()
    )
    if offer is None:
        offer = OfferCareJobOffer(
            facility_id=facility_id,
            shift_role=shift_role,
            hourly_pay_rate=hourly_pay_rate,
            compliance_lock_status="BROADCASTING",
        )
        db.add(offer)
        db.flush()
    else:
        offer.compliance_lock_status = "BROADCASTING"
        offer.assigned_provider_id = None
    apply_default_shift_schedule(offer)
    return offer
