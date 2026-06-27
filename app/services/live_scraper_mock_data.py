"""Mock adapter payloads for local live-scraper go-live."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def mock_mbon_verify_payload(*, license_number: str) -> dict:
    expires = (datetime.now(timezone.utc) + timedelta(days=365)).date().isoformat()
    status = "EXPIRED" if license_number.endswith("X") else "ACTIVE"
    token = str(license_number or "").upper()
    gna_endorsement = token.startswith("GNA") or (token.startswith("CNA") and not token.endswith("NOGNA"))
    return {
        "status": status,
        "license_number": license_number,
        "expires_on": None if status == "EXPIRED" else expires,
        "disciplinary_action": license_number.endswith("D"),
        "gna_endorsement": gna_endorsement,
        "compact_status": "ACTIVE" if token.startswith("LPN") or token.startswith("PN") else None,
        "source": "MOCK_ADAPTER",
    }


def mock_oig_search_payload(*, full_name: str) -> dict:
    excluded = "EXCLUDED" in str(full_name or "").upper()
    return {
        "matches": [{"name": full_name}] if excluded else [],
        "source": "MOCK_ADAPTER",
    }


def mock_judiciary_search_payload(*, full_name: str) -> dict:
    flagged = "FLAGGED" in str(full_name or "").upper()
    return {
        "cases": [{"caption": f"State v. {full_name}"}] if flagged else [],
        "source": "MOCK_ADAPTER",
    }


def mock_job_board_payload() -> dict:
    listings = [
        {
            "external_id": "indeed-futurecare-northpoint-cna",
            "facility_name": "FutureCare Northpoint",
            "city": "Baltimore",
            "county": "Baltimore",
            "state": "MD",
            "shift_role": "CNA",
            "title": "Certified Nursing Assistant (CNA) — Immediate Openings",
            "url": "https://www.indeed.com/viewjob?jk=futurecare-northpoint-cna",
            "days_open": 47,
            "source": "INDEED",
        },
        {
            "external_id": "zip-genesis-baltimore-lpn",
            "facility_name": "Genesis HealthCare Baltimore Center",
            "city": "Baltimore",
            "county": "Baltimore",
            "state": "MD",
            "shift_role": "LPN",
            "title": "Licensed Practical Nurse (LPN) — Full Time & Per Diem",
            "url": "https://www.ziprecruiter.com/jobs/genesis-baltimore-lpn",
            "days_open": 38,
            "source": "ZIPRECRUITER",
        },
        {
            "external_id": "indeed-communicare-silver-spring-cna",
            "facility_name": "CommuniCare Silver Spring",
            "city": "Silver Spring",
            "county": "Montgomery",
            "state": "MD",
            "shift_role": "CNA",
            "title": "CNA / Floor Aide — Sign-On Bonus",
            "url": "https://www.indeed.com/viewjob?jk=communicare-ss-cna",
            "days_open": 52,
            "source": "INDEED",
        },
        {
            "external_id": "zip-futurecare-landover-gna",
            "facility_name": "FutureCare Landover",
            "city": "Landover",
            "county": "Prince George's",
            "state": "MD",
            "shift_role": "GNA",
            "title": "Geriatric Nursing Assistant (GNA)",
            "url": "https://www.ziprecruiter.com/jobs/futurecare-landover-gna",
            "days_open": 19,
            "source": "ZIPRECRUITER",
        },
    ]
    return {"listings": listings, "source": "MOCK_ADAPTER"}


def mock_vms_shifts_payload() -> dict:
    now = datetime.now(timezone.utc)
    tonight = (now + timedelta(hours=6)).isoformat()
    return {
        "shifts": [
            {
                "external_id": "mock-shiftwise-fc-northpoint-cna",
                "facility_name": "FutureCare Northpoint",
                "shift_role": "CNA",
                "hourly_pay_rate": 34.0,
                "shift_starts_at": tonight,
                "source": "SHIFTWISE",
            },
            {
                "external_id": "mock-fieldglass-genesis-baltimore-lpn",
                "facility_name": "Genesis HealthCare Baltimore Center",
                "shift_role": "LPN",
                "hourly_pay_rate": 46.0,
                "shift_starts_at": (now + timedelta(hours=18)).isoformat(),
                "source": "FIELDGLASS",
            },
            {
                "external_id": "mock-shiftwise-communicare-cna",
                "facility_name": "CommuniCare Silver Spring",
                "shift_role": "CNA",
                "hourly_pay_rate": 31.5,
                "shift_starts_at": (now + timedelta(hours=12)).isoformat(),
                "source": "SHIFTWISE",
            },
        ],
        "source": "MOCK_ADAPTER",
    }
