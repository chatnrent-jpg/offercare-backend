import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class MarylandFacility(Base):
    __tablename__ = "maryland_facilities"

    facility_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    facility_type = Column(String(100), nullable=False)  # e.g., 'HOSPITAL', 'URGENT_CARE'
    county = Column(String(100), nullable=False)  # e.g., 'Baltimore County', 'Montgomery'
    state = Column(String(2), nullable=False, default="MD")
    vms_integration_type = Column(String(50), default="SCRAPE")
    external_source = Column(String(50), nullable=True)
    external_id = Column(String(50), nullable=True)
    address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    zip_code = Column(String(20), nullable=True)
    phone = Column(String(30), nullable=True)
    latitude = Column(Numeric(9, 6), nullable=True)
    longitude = Column(Numeric(9, 6), nullable=True)


class MarylandProvider(Base):
    __tablename__ = "maryland_providers"

    provider_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone_number = Column(String(20), unique=True, nullable=False)
    npi_number = Column(String(10), unique=True, nullable=False)
    md_license_number = Column(String(50), unique=True, nullable=False)
    state = Column(String(2), nullable=False, default="MD")
    credential_type = Column(String(20), nullable=False, default="RN")  # RN, LPN, CNA, GNA, NA
    service_lines = Column(String(100), nullable=False, default="ALL")
    license_status = Column(String(50), default="UNVERIFIED")  # 'VERIFIED', 'EXPIRED'
    min_hourly_rate = Column(Numeric(6, 2), nullable=False, default=0)
    response_propensity = Column(Numeric(4, 3), nullable=False, default=0.5)
    fatigue_score = Column(Numeric(4, 2), nullable=False, default=0)
    last_verified_timestamp = Column(DateTime(timezone=True), onupdate=func.now())
    applied_at = Column(DateTime(timezone=True), server_default=func.now())
    verification_notes = Column(String(500), nullable=True)
    home_zip = Column(String(20), nullable=True)
    latitude = Column(Numeric(9, 6), nullable=True)
    longitude = Column(Numeric(9, 6), nullable=True)
    dispatch_status = Column(String(20), nullable=False, default="ACTIVE")  # ACTIVE, SUSPENDED
    license_expires_on = Column(DateTime(timezone=True), nullable=True)
    sms_opt_out = Column(String(5), nullable=False, default="false")
    vetted_status = Column(String(30), nullable=False, default="ACTION_NEEDED")
    vetted_status_updated_at = Column(DateTime(timezone=True), nullable=True)


class LicenseVerificationLog(Base):
    __tablename__ = "license_verification_log"

    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=False)
    event_type = Column(String(30), nullable=False)
    check_result = Column(String(30), nullable=True)
    notes = Column(String(500), nullable=True)
    reviewer = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OfferCareJobOffer(Base):
    __tablename__ = "offercare_job_offers"

    offer_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("maryland_facilities.facility_id"))
    shift_role = Column(String(100), nullable=False)  # e.g., 'ICU_RN', 'ER_MD'
    hourly_pay_rate = Column(Numeric(6, 2), nullable=False)
    compliance_lock_status = Column(String(50), default="BROADCASTING")  # 'LOCKED', 'FILLED'
    assigned_provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=True)
    broadcast_wave_id = Column(UUID(as_uuid=True), nullable=True)
    shift_starts_at = Column(DateTime(timezone=True), nullable=True)
    shift_ends_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ShiftNotificationLog(Base):
    __tablename__ = "shift_notification_log"

    notification_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    offer_id = Column(UUID(as_uuid=True), ForeignKey("offercare_job_offers.offer_id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=False)
    channel = Column(String(20), nullable=False, default="SMS")
    status = Column(String(20), nullable=False)
    message_body = Column(String(1000), nullable=False)
    broadcast_wave_id = Column(UUID(as_uuid=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())


class ClinicalPlacementLedger(Base):
    __tablename__ = "clinical_placements_ledger"

    placement_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    offer_id = Column(UUID(as_uuid=True), ForeignKey("offercare_job_offers.offer_id"), nullable=False)
    facility_name = Column(String(255), nullable=False)
    clinical_unit = Column(String(100), nullable=False)
    hourly_bill_rate = Column(Numeric(6, 2), nullable=False)
    assigned_clinician_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=False)
    compliance_snapshot_token = Column(String(64), nullable=False)
    outbound_payload_timestamp = Column(DateTime(timezone=True), server_default=func.now())
    vms_submission_status = Column(String(50), default="PENDING")
    vms_external_ref = Column(String(100), nullable=True)
    vms_submitted_at = Column(DateTime(timezone=True), nullable=True)


class ClinicianPortalAccount(Base):
    __tablename__ = "clinician_portal_accounts"

    account_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maryland_providers.provider_id"),
        nullable=False,
        unique=True,
    )
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ClinicianPushSubscription(Base):
    __tablename__ = "clinician_push_subscriptions"

    subscription_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maryland_providers.provider_id"),
        nullable=False,
    )
    endpoint = Column(String(500), nullable=False, unique=True)
    p256dh_key = Column(String(255), nullable=False)
    auth_key = Column(String(255), nullable=False)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)


class VmsSubmissionLog(Base):
    __tablename__ = "vms_submission_log"

    submission_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    placement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clinical_placements_ledger.placement_id"),
        nullable=False,
    )
    status = Column(String(30), nullable=False)
    mode = Column(String(20), nullable=False)
    request_payload = Column(String(4000), nullable=False)
    response_message = Column(String(500), nullable=True)
    external_ref = Column(String(100), nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())


class ClinicianComplianceDocument(Base):
    __tablename__ = "clinician_compliance_documents"

    document_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=False)
    document_type = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")
    expires_on = Column(DateTime(timezone=True), nullable=True)
    source = Column(String(50), nullable=True)
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ExclusionScreening(Base):
    __tablename__ = "exclusion_screenings"

    screening_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=False)
    source = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False)
    checked_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_on = Column(DateTime(timezone=True), nullable=True)
    payload_json = Column(Text, nullable=True)


class FacilityCrisisSignal(Base):
    __tablename__ = "facility_crisis_signals"

    signal_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("maryland_facilities.facility_id"), nullable=False)
    signal_type = Column(String(40), nullable=False)
    severity = Column(String(20), nullable=False)
    score = Column(Numeric(5, 2), nullable=False, default=0)
    summary = Column(String(500), nullable=False)
    source = Column(String(50), nullable=True)
    detected_at = Column(DateTime(timezone=True), server_default=func.now())


class JobBoardCrisisListing(Base):
    __tablename__ = "job_board_crisis_listings"

    listing_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(30), nullable=False)
    external_id = Column(String(100), nullable=False)
    facility_name = Column(String(255), nullable=False)
    city = Column(String(100), nullable=True)
    county = Column(String(100), nullable=True)
    state = Column(String(2), nullable=False, default="MD")
    shift_role = Column(String(20), nullable=False)
    job_title = Column(String(255), nullable=False)
    job_url = Column(String(500), nullable=True)
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    days_open = Column(Numeric(5, 0), nullable=False, default=0)
    is_crisis = Column(String(5), nullable=False, default="false")
    facility_id = Column(UUID(as_uuid=True), ForeignKey("maryland_facilities.facility_id"), nullable=True)


class VmsShiftIngestionLog(Base):
    __tablename__ = "vms_shift_ingestion_log"

    ingest_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(30), nullable=False)
    external_id = Column(String(100), nullable=False)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("maryland_facilities.facility_id"), nullable=True)
    offer_id = Column(UUID(as_uuid=True), ForeignKey("offercare_job_offers.offer_id"), nullable=True)
    status = Column(String(30), nullable=False)
    shift_role = Column(String(100), nullable=True)
    hourly_pay_rate = Column(Numeric(6, 2), nullable=True)
    payload_json = Column(Text, nullable=True)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())


class FacilityOutreachContact(Base):
    __tablename__ = "facility_outreach_contacts"

    contact_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("maryland_facilities.facility_id"), nullable=False)
    full_name = Column(String(255), nullable=False)
    title = Column(String(120), nullable=False)
    email = Column(String(255), nullable=False)
    source = Column(String(30), nullable=False)
    enriched_at = Column(DateTime(timezone=True), server_default=func.now())


class OutreachEmailLog(Base):
    __tablename__ = "outreach_email_log"

    email_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("maryland_facilities.facility_id"), nullable=False)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("facility_outreach_contacts.contact_id"), nullable=True)
    recipient_name = Column(String(255), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(20), nullable=False)
    mode = Column(String(30), nullable=False)
    crisis_context = Column(String(500), nullable=True)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())


class OpsAuditLog(Base):
    __tablename__ = "ops_audit_log"

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False)
    actor = Column(String(100), nullable=True)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    summary = Column(String(500), nullable=False)
    metadata_json = Column(String(2000), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class VettedCareAuditLog(Base):
    __tablename__ = "vettedcare_audit_log"

    audit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=True)
    event_type = Column(String(50), nullable=False)
    actor = Column(String(100), nullable=True)
    previous_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=True)
    summary = Column(String(500), nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CredentialSafetyAlert(Base):
    __tablename__ = "credential_safety_alerts"

    alert_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=False)
    channel = Column(String(20), nullable=False)
    alert_type = Column(String(30), nullable=False)
    vetted_status = Column(String(30), nullable=False)
    message_body = Column(String(1000), nullable=False)
    delivery_status = Column(String(20), nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())


class ManusVettingRun(Base):
    __tablename__ = "manus_vetting_runs"

    run_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_run_id = Column(String(128), nullable=True)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=True)
    status = Column(String(20), nullable=False, default="RECEIVED")
    checks_count = Column(Numeric(5, 0), nullable=False, default=0)
    summary = Column(String(500), nullable=True)
    payload_json = Column(Text, nullable=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    applied_at = Column(DateTime(timezone=True), nullable=True)
