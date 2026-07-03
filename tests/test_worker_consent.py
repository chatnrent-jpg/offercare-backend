from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models import LicenseVerificationLog, MarylandProvider
from app.services.care_taxonomy import synthetic_npi_for_caregiver
from app.services.worker_consent import (
    WORKER_CONSENT_VERSION,
    provider_has_sms_dispatch_consent,
    record_apply_consents,
)


def test_worker_inflow_summary_requires_admin() -> None:
    public_client = TestClient(app)
    assert public_client.get("/api/landing/maryland/inflow-summary").status_code == 401


def test_worker_inflow_summary_counts_opt_in_applicants(client: TestClient) -> None:
    token = uuid4().hex[:10]
    client.post(
        "/api/landing/maryland/apply",
        json={
            "full_name": "Inflow Summary CNA",
            "email": f"inflow.{token}@example.com",
            "phone_number": f"410560{token[:4]}",
            "md_license_number": f"CNA-MD-INF{token[:6].upper()}",
            "credential_type": "CNA",
            "min_hourly_rate": 24.0,
            "password": "testpass123",
            "consent_version": WORKER_CONSENT_VERSION,
            "consent_credential_screening": True,
            "consent_sms_dispatch": True,
            "consent_privacy_policy": True,
            "consent_terms_of_service": True,
            "consent_aedt_30_day": True,
        },
    )
    summary = client.get("/api/landing/maryland/inflow-summary").json()
    assert summary["legal_model"] == "opt_in_apply_only"
    assert summary["opt_in_applicants"] >= 1
    assert summary["join_url"] == "/join"
    assert summary["terms_accepted"] >= 1
    assert summary["terms_of_service_version"] == WORKER_CONSENT_VERSION


def test_record_apply_consents_persists_audit_log() -> None:
    db = SessionLocal()
    try:
        email = f"consent.{uuid4().hex[:8]}@example.com"
        provider = MarylandProvider(
            full_name="Consent Audit CNA",
            email=email,
            phone_number=f"410561{uuid4().hex[:4]}",
            npi_number=synthetic_npi_for_caregiver(email),
            md_license_number=f"CNA-MD-{uuid4().hex[:8].upper()}",
            credential_type="CNA",
            min_hourly_rate=22.0,
        )
        db.add(provider)
        db.commit()
        db.refresh(provider)

        record_apply_consents(db, provider.provider_id, consent_version=WORKER_CONSENT_VERSION, commit=True)
        rows = (
            db.query(LicenseVerificationLog)
            .filter(LicenseVerificationLog.provider_id == provider.provider_id)
            .order_by(LicenseVerificationLog.event_type.asc())
            .all()
        )
        event_types = {row.event_type for row in rows}
        assert event_types == {
            "CONSENT_CREDENTIAL_SCREENING",
            "CONSENT_SMS_DISPATCH",
            "CONSENT_TERMS_OF_SERVICE",
            "CONSENT_PRIVACY_POLICY",
        }
        assert provider_has_sms_dispatch_consent(db, provider.provider_id, email=provider.email) is True
    finally:
        db.close()
