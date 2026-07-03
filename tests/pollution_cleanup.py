"""Remove committed rows from isolated lock tests on the shared local database."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    ClinicalPlacementLedger,
    ClinicianPortalAccount,
    ClinicianPushSubscription,
    LicenseVerificationLog,
    MarylandFacility,
    MarylandProvider,
    OfferCareJobOffer,
    ShiftNotificationLog,
    VmsSubmissionLog,
)


def _delete_clinical_placements_cascade(
    db: Session,
    *,
    offer_ids: list | None = None,
    provider_ids: list | None = None,
) -> None:
    """Purge VMS submission logs before clinical_placements_ledger (FK child-first)."""
    ledger_query = db.query(ClinicalPlacementLedger.placement_id)
    if provider_ids:
        if not provider_ids:
            return
        ledger_query = ledger_query.filter(
            ClinicalPlacementLedger.assigned_clinician_id.in_(provider_ids)
        )
        ledger_filter = ClinicalPlacementLedger.assigned_clinician_id.in_(provider_ids)
    elif offer_ids:
        if not offer_ids:
            return
        ledger_query = ledger_query.filter(ClinicalPlacementLedger.offer_id.in_(offer_ids))
        ledger_filter = ClinicalPlacementLedger.offer_id.in_(offer_ids)
    else:
        return

    placement_ids = [row[0] for row in ledger_query.all()]
    if placement_ids:
        db.query(VmsSubmissionLog).filter(
            VmsSubmissionLog.placement_id.in_(placement_ids)
        ).delete(synchronize_session=False)
    db.query(ClinicalPlacementLedger).filter(ledger_filter).delete(synchronize_session=False)


def _delete_providers(db: Session, provider_ids: list) -> None:
    if not provider_ids:
        return
    db.query(ClinicianPushSubscription).filter(
        ClinicianPushSubscription.provider_id.in_(provider_ids)
    ).delete(synchronize_session=False)
    db.query(ClinicianPortalAccount).filter(
        ClinicianPortalAccount.provider_id.in_(provider_ids)
    ).delete(synchronize_session=False)
    db.query(LicenseVerificationLog).filter(
        LicenseVerificationLog.provider_id.in_(provider_ids)
    ).delete(synchronize_session=False)
    db.query(ShiftNotificationLog).filter(
        ShiftNotificationLog.provider_id.in_(provider_ids)
    ).delete(synchronize_session=False)
    _delete_clinical_placements_cascade(db, provider_ids=provider_ids)
    db.query(OfferCareJobOffer).filter(
        OfferCareJobOffer.assigned_provider_id.in_(provider_ids)
    ).update({OfferCareJobOffer.assigned_provider_id: None}, synchronize_session=False)
    db.query(MarylandProvider).filter(
        MarylandProvider.provider_id.in_(provider_ids)
    ).delete(synchronize_session=False)


def purge_lock_test_pollution(db: Session) -> None:
    stale_providers = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email.like("lock.%@offercare.demo"))
        .all()
    )
    stale_ids = [provider.provider_id for provider in stale_providers]
    _delete_providers(db, stale_ids)

    stale_facilities = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.name.like("Lock Test Hospital %"))
        .all()
    )
    for facility in stale_facilities:
        offer_ids = [
            row.offer_id
            for row in db.query(OfferCareJobOffer)
            .filter(OfferCareJobOffer.facility_id == facility.facility_id)
            .all()
        ]
        if offer_ids:
            db.query(ShiftNotificationLog).filter(
                ShiftNotificationLog.offer_id.in_(offer_ids)
            ).delete(synchronize_session=False)
            _delete_clinical_placements_cascade(db, offer_ids=offer_ids)
            db.query(OfferCareJobOffer).filter(
                OfferCareJobOffer.offer_id.in_(offer_ids)
            ).delete(synchronize_session=False)
        db.delete(facility)

    db.commit()


def purge_post_acute_demo_pollution(db: Session) -> None:
    stale_providers = (
        db.query(MarylandProvider)
        .filter(
            (MarylandProvider.email.in_(
                (
                    "snf.lpn.a@offercare.demo",
                    "snf.cna.a@offercare.demo",
                    "snf.gna.a@offercare.demo",
                    "hh.rn.a@offercare.demo",
                    "hh.lpn.a@offercare.demo",
                    "hh.cna.a@offercare.demo",
                    "va.snf.lpn.a@offercare.demo",
                    "va.snf.cna.a@offercare.demo",
                    "dc.snf.gna.a@offercare.demo",
                    "dc.snf.cna.a@offercare.demo",
                    "pa.snf.lpn.a@offercare.demo",
                    "pa.snf.cna.a@offercare.demo",
                    "de.snf.lpn.a@offercare.demo",
                    "de.snf.cna.a@offercare.demo",
                    "nj.snf.lpn.a@offercare.demo",
                    "nj.snf.cna.a@offercare.demo",
                    "cna.applicant@offercare.demo",
                )
            ))
            | (MarylandProvider.email.like("cna.%@offercare.demo"))
        )
        .all()
    )
    stale_ids = [provider.provider_id for provider in stale_providers]
    _delete_providers(db, stale_ids)

    stale_facilities = (
        db.query(MarylandFacility)
        .filter(
            MarylandFacility.name.in_(
                (
                    "Cadia Healthcare Nursing Home",
                    "Bayada Home Health Mid-Atlantic",
                    "Virginia SNF at Arlington",
                    "Capitol Hill SNF",
                    "Philadelphia SNF at Center City",
                    "Wilmington SNF at Riverfront",
                    "Paramus SNF at Bergen",
                )
            )
        )
        .all()
    )
    for facility in stale_facilities:
        offer_ids = [
            row.offer_id
            for row in db.query(OfferCareJobOffer)
            .filter(OfferCareJobOffer.facility_id == facility.facility_id)
            .all()
        ]
        if offer_ids:
            db.query(ShiftNotificationLog).filter(
                ShiftNotificationLog.offer_id.in_(offer_ids)
            ).delete(synchronize_session=False)
            _delete_clinical_placements_cascade(db, offer_ids=offer_ids)
            db.query(OfferCareJobOffer).filter(
                OfferCareJobOffer.offer_id.in_(offer_ids)
            ).delete(synchronize_session=False)
        db.delete(facility)

    db.commit()


def purge_matched_shift_test_pollution(db: Session) -> None:
    stale_providers = (
        db.query(MarylandProvider)
        .filter(
            MarylandProvider.email.like("hospital.rn.only.%@offercare.demo")
            | MarylandProvider.email.like("md.cna.matcher.%@offercare.demo")
            | MarylandProvider.email.like("portal.cna.matcher.%@offercare.demo")
            | MarylandProvider.email.like("portal.lpn.locker.%@offercare.demo")
            | MarylandProvider.email.like("prefs.tester.%@offercare.demo")
            | MarylandProvider.email.like("unverified.lpn.%@offercare.demo")
            | MarylandProvider.email.like("pa.cna.rank.%@offercare.demo")
        )
        .all()
    )
    stale_ids = [provider.provider_id for provider in stale_providers]
    _delete_providers(db, stale_ids)
    db.commit()
