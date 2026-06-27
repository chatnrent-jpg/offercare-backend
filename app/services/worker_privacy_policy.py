"""VettedCare clinician Privacy Policy — versioned for /join apply flow."""

from __future__ import annotations

WORKER_PRIVACY_VERSION = "2026-06-21"
WORKER_PRIVACY_EFFECTIVE_DATE = "June 21, 2026"
WORKER_PRIVACY_TITLE = "VettedCare.ai Clinician Privacy Policy"

WORKER_PRIVACY_SECTIONS: tuple[tuple[str, str], ...] = (
    (
        "1. Who we are",
        "VettedCare.ai operates a Maryland nursing home per-diem staffing platform. "
        "This policy explains how we collect, use, and protect clinician information when you apply at /join.",
    ),
    (
        "2. Information we collect",
        "Application data includes your name, email, mobile phone, credential type, Maryland license number, "
        "NPI (when required), home ZIP, minimum pay rate, and portal password. We also store credentialing "
        "results, shift dispatch history, SMS reply logs, and portal activity.",
    ),
    (
        "3. How we use information",
        "We use your data to verify licenses, match you to local open shifts, send shift offers by SMS/email/push, "
        "record shift locks and placements, maintain COMAR compliance audit trails, and improve dispatch quality.",
    ),
    (
        "4. SMS and communications",
        "With your explicit consent, we send automated shift-offer texts. Reply STOP to opt out or YES to accept "
        "a shift. Message and data rates may apply. We do not sell your phone number to third-party recruiters.",
    ),
    (
        "5. Credential verification",
        "You authorize automated checks against MBON, OIG LEIE, and Maryland judiciary exclusion sources. "
        "Results are stored for compliance and may be shared with assigned facilities when you lock a shift.",
    ),
    (
        "6. Sharing",
        "We share necessary placement data with nursing homes where you accept shifts and with payroll/compliance "
        "vendors under contract. We do not sell personal information.",
    ),
    (
        "7. Retention & security",
        "Records are retained as required for staffing, tax, and regulatory purposes. Access is restricted to "
        "authorized operations and compliance staff.",
    ),
    (
        "8. Your choices",
        "Reply STOP to end marketing/shift-offer texts. Contact compliance@vettedcare.ai to request access, "
        "correction, or deletion where applicable law allows.",
    ),
    (
        "9. Changes",
        "We may update this policy by posting a new version on /join. Material changes require re-acceptance on apply.",
    ),
    (
        "10. Contact",
        "Privacy questions: compliance@vettedcare.ai",
    ),
)

CONSENT_PRIVACY_POLICY = (
    f"I have read and agree to the VettedCare.ai Clinician Privacy Policy "
    f"(version {WORKER_PRIVACY_VERSION}, effective {WORKER_PRIVACY_EFFECTIVE_DATE})."
)


def build_worker_privacy_policy() -> dict:
    return {
        "title": WORKER_PRIVACY_TITLE,
        "version": WORKER_PRIVACY_VERSION,
        "effective_date": WORKER_PRIVACY_EFFECTIVE_DATE,
        "sections": [{"heading": h, "body": b} for h, b in WORKER_PRIVACY_SECTIONS],
    }
