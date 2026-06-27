"""VettedCare clinician Terms of Service — versioned worker agreement for /join apply flow."""

from __future__ import annotations

WORKER_TERMS_VERSION = "2026-06-21"
WORKER_TERMS_EFFECTIVE_DATE = "June 21, 2026"
WORKER_TERMS_TITLE = "VettedCare.ai Clinician Terms of Service"

WORKER_TERMS_SECTIONS: tuple[tuple[str, str], ...] = (
    (
        "1. Agreement & eligibility",
        "By applying through VettedCare.ai you agree to these Terms of Service. "
        "You must be at least 18, legally authorized to work in the United States, and hold an "
        "active Maryland CNA, GNA, or LPN credential (as selected on your application). "
        "You apply voluntarily — VettedCare does not recruit you from scraped contact lists.",
    ),
    (
        "2. W-2 employment & shift model",
        "VettedCare classifies matched floor staff as W-2 employees for per-diem nursing home shifts, "
        "not 1099 independent contractors. Shifts are offered on a per-diem basis; accepting a shift "
        "does not guarantee future assignments. You set your minimum hourly rate; facilities may offer "
        "rates at or above that minimum.",
    ),
    (
        "3. Accurate information",
        "You agree that all application information — name, contact details, license number, NPI (if "
        "required), and work history — is truthful and complete. Misrepresentation may result in "
        "immediate suspension and referral to regulatory authorities.",
    ),
    (
        "4. Credential & exclusion screening",
        "You authorize VettedCare to verify your Maryland license through MBON, screen you against the "
        "federal OIG LEIE exclusion list, and run Maryland judiciary exclusion checks before and during "
        "engagement. You consent to periodic re-screening required for COMAR-compliant SNF staffing.",
    ),
    (
        "5. Shift dispatch & SMS",
        "When a local nursing home needs coverage, VettedCare may contact you by SMS, email, and/or "
        "portal push with shift details. Message and data rates may apply. Reply YES to lock an offered "
        "shift or STOP to opt out of marketing texts (service-critical messages may still be sent for "
        "active placements). You must maintain a working mobile number on file.",
    ),
    (
        "6. Workplace conduct & COMAR compliance",
        "On assignment you must follow facility policies, resident safety rules, infection control "
        "protocols, and Maryland COMAR staffing requirements. You are responsible for arriving on time, "
        "remaining fit for duty, and reporting incidents to the facility DON and VettedCare operations.",
    ),
    (
        "7. Pay & taxes",
        "Pay rates are shown before you lock a shift. W-2 wages are subject to payroll withholding. "
        "VettedCare does not guarantee minimum hours, shift volume, or annual income.",
    ),
    (
        "8. Suspension & termination",
        "VettedCare may suspend or terminate your portal access for failed credential checks, exclusion "
        "matches, no-shows, safety incidents, falsified timesheets, or violation of these Terms. "
        "You may stop using the platform at any time; outstanding pay for completed shifts will still "
        "be processed per payroll policy.",
    ),
    (
        "9. Privacy",
        "VettedCare stores your application, credentialing results, shift history, and communications "
        "to operate the staffing platform and meet regulatory obligations. We do not sell your personal "
        "information to third-party recruiters.",
    ),
    (
        "10. Limitation of liability",
        "VettedCare connects licensed clinicians with facilities needing coverage. Facilities control "
        "on-site supervision and clinical direction. To the fullest extent permitted by law, VettedCare "
        "is not liable for facility acts, resident outcomes, or indirect damages arising from shift "
        "assignments.",
    ),
    (
        "11. Changes",
        "We may update these Terms by posting a new version on the apply page. Continued use after "
        "notice requires acceptance of the updated version on your next application or portal login "
        "where prompted.",
    ),
    (
        "12. Contact",
        "Questions about these Terms: compliance@vettedcare.ai. Maryland operations: share your application "
        "ID from the clinician portal when contacting support.",
    ),
)

CONSENT_TERMS_OF_SERVICE = (
    f"I have read and agree to the VettedCare.ai Clinician Terms of Service "
    f"(version {WORKER_TERMS_VERSION}, effective {WORKER_TERMS_EFFECTIVE_DATE})."
)


def build_worker_terms_of_service() -> dict:
    return {
        "title": WORKER_TERMS_TITLE,
        "version": WORKER_TERMS_VERSION,
        "effective_date": WORKER_TERMS_EFFECTIVE_DATE,
        "sections": [{"heading": heading, "body": body} for heading, body in WORKER_TERMS_SECTIONS],
    }
