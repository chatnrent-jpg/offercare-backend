"""Facility crisis indicator scoring for Maryland nursing home outreach."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import FacilityCrisisSignal, JobBoardCrisisListing, MarylandFacility, OfferCareJobOffer
from app.services.job_board_crisis_scraper import fetch_job_board_listings, match_facility_name

def scan_facility_crisis_signals(db: Session) -> dict:
    created = 0
    facilities = db.query(MarylandFacility).filter(MarylandFacility.state == "MD").all()
    for facility in facilities:
        open_shift_count = (
            db.query(func.count(OfferCareJobOffer.offer_id))
            .filter(
                OfferCareJobOffer.facility_id == facility.facility_id,
                OfferCareJobOffer.compliance_lock_status == "BROADCASTING",
            )
            .scalar()
            or 0
        )
        if open_shift_count < 3:
            continue
        severity = "HIGH" if open_shift_count >= 8 else "MEDIUM" if open_shift_count >= 5 else "LOW"
        summary = (
            f"{facility.name} has {open_shift_count} open broadcasting shifts — "
            "potential COMAR 1:15 staffing pressure."
        )
        db.add(
            FacilityCrisisSignal(
                facility_id=facility.facility_id,
                signal_type="OPEN_SHIFT_SURGE",
                severity=severity,
                score=open_shift_count,
                summary=summary,
                source="INTERNAL_SHIFT_ENGINE",
            )
        )
        created += 1
    db.commit()
    return {"signals_created": created}


def list_facility_crisis_signals(db: Session, *, limit: int = 50) -> list[dict]:
    rows = (
        db.query(FacilityCrisisSignal, MarylandFacility)
        .join(MarylandFacility, MarylandFacility.facility_id == FacilityCrisisSignal.facility_id)
        .order_by(FacilityCrisisSignal.detected_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "signal_id": str(signal.signal_id),
            "facility_id": str(facility.facility_id),
            "facility_name": facility.name,
            "county": facility.county,
            "signal_type": signal.signal_type,
            "severity": signal.severity,
            "score": float(signal.score),
            "summary": signal.summary,
            "detected_at": signal.detected_at.isoformat() if signal.detected_at else None,
        }
        for signal, facility in rows
    ]


def scan_job_board_crisis_leads(db: Session) -> dict:
    now = datetime.now(timezone.utc)
    min_days = int(settings.JOB_BOARD_CRISIS_MIN_DAYS)
    scraped = fetch_job_board_listings()
    facilities = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.state == "MD", MarylandFacility.facility_type == "NURSING_HOME")
        .all()
    )

    upserted = 0
    crisis_count = 0
    signals_created = 0
    for row in scraped:
        listing = (
            db.query(JobBoardCrisisListing)
            .filter(
                JobBoardCrisisListing.source == row.source,
                JobBoardCrisisListing.external_id == row.external_id,
            )
            .first()
        )
        matched = match_facility_name(row.facility_name, facilities)
        is_crisis = row.days_open >= min_days
        if listing is None:
            first_seen = now - timedelta(days=max(row.days_open, 0))
            listing = JobBoardCrisisListing(
                source=row.source,
                external_id=row.external_id,
                facility_name=row.facility_name,
                city=row.city,
                county=row.county,
                state=row.state,
                shift_role=row.shift_role,
                job_title=row.job_title,
                job_url=row.job_url,
                first_seen_at=first_seen,
                last_seen_at=now,
                days_open=row.days_open,
                is_crisis="true" if is_crisis else "false",
                facility_id=matched.facility_id if matched else None,
            )
            db.add(listing)
            upserted += 1
        else:
            listing.facility_name = row.facility_name
            listing.city = row.city
            listing.county = row.county
            listing.shift_role = row.shift_role
            listing.job_title = row.job_title
            listing.job_url = row.job_url
            listing.last_seen_at = now
            listing.days_open = row.days_open
            listing.is_crisis = "true" if is_crisis else "false"
            if matched:
                listing.facility_id = matched.facility_id

        if is_crisis:
            crisis_count += 1
            if matched:
                severity = "HIGH" if row.days_open >= 45 else "MEDIUM"
                summary = (
                    f"{matched.name} has had a {row.shift_role} posting on {row.source} "
                    f"for {row.days_open} days — chronic aide shortage indicator."
                )
                db.add(
                    FacilityCrisisSignal(
                        facility_id=matched.facility_id,
                        signal_type="PERSISTENT_JOB_POSTING",
                        severity=severity,
                        score=row.days_open,
                        summary=summary,
                        source=row.source,
                    )
                )
                signals_created += 1

    db.commit()
    return {
        "listings_scraped": len(scraped),
        "listings_upserted": upserted,
        "crisis_listings": crisis_count,
        "signals_created": signals_created,
        "min_days_threshold": min_days,
    }


def list_job_board_crisis_listings(db: Session, *, limit: int = 50) -> list[dict]:
    rows = (
        db.query(JobBoardCrisisListing, MarylandFacility)
        .outerjoin(MarylandFacility, MarylandFacility.facility_id == JobBoardCrisisListing.facility_id)
        .order_by(JobBoardCrisisListing.days_open.desc(), JobBoardCrisisListing.last_seen_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "listing_id": str(listing.listing_id),
            "source": listing.source,
            "external_id": listing.external_id,
            "facility_name": listing.facility_name,
            "matched_facility_id": str(facility.facility_id) if facility else None,
            "matched_facility_name": facility.name if facility else None,
            "city": listing.city,
            "county": listing.county,
            "state": listing.state,
            "shift_role": listing.shift_role,
            "job_title": listing.job_title,
            "job_url": listing.job_url,
            "days_open": int(listing.days_open or 0),
            "is_crisis": listing.is_crisis == "true",
            "first_seen_at": listing.first_seen_at.isoformat() if listing.first_seen_at else None,
            "last_seen_at": listing.last_seen_at.isoformat() if listing.last_seen_at else None,
        }
        for listing, facility in rows
    ]
