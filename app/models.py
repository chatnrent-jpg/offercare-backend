import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
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
    consent_signed_at = Column(DateTime(timezone=True), nullable=True)


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


class ClinicianOAuthIdentity(Base):
    __tablename__ = "clinician_oauth_identities"

    identity_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maryland_providers.provider_id"),
        nullable=False,
    )
    oauth_provider = Column(String(32), nullable=False)
    oauth_subject = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("oauth_provider", "oauth_subject", name="uq_clinician_oauth_provider_subject"),
    )


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


class FacilityContract(Base):
    __tablename__ = "facility_contracts"

    contract_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("maryland_facilities.facility_id"), nullable=False)
    external_contract_id = Column(String(120), nullable=False)
    vms_source = Column(String(50), nullable=False, default="MSA_UPLOAD")
    contract_name = Column(String(255), nullable=True)
    source_filename = Column(String(255), nullable=True)
    bill_rate_hourly = Column(Numeric(8, 2), nullable=True)
    pay_rate_hourly = Column(Numeric(8, 2), nullable=True)
    margin_dollars = Column(Numeric(8, 2), nullable=True)
    margin_pct = Column(Numeric(6, 4), nullable=True)
    cancellation_policy_text = Column(Text, nullable=True)
    cancellation_notice_hours = Column(Numeric(5, 0), nullable=True)
    credential_requirements_json = Column(Text, nullable=True)
    review_status = Column(String(40), nullable=False, default="ACTIVE")
    dispatch_halted = Column(String(5), nullable=False, default="false")
    review_reason = Column(String(500), nullable=True)
    raw_text_excerpt = Column(Text, nullable=True)
    staffing_role = Column(String(20), nullable=True)
    md_regional_bill_floor = Column(Numeric(8, 2), nullable=True)
    parsed_at = Column(DateTime(timezone=True), server_default=func.now())


class B2BRawLead(Base):
    __tablename__ = "b2b_raw_leads"

    lead_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_name = Column(String(255), nullable=False)
    contact_role = Column(String(120), nullable=False)
    email_domain = Column(String(255), nullable=False)
    procurement_urgency = Column(String(50), nullable=False)
    source_url = Column(String(500), nullable=False)
    contact_name = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=True)
    state = Column(String(2), nullable=False, default="MD")
    county = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    manus_run_id = Column(String(128), nullable=True)
    source = Column(String(30), nullable=False, default="manus")
    imported_at = Column(DateTime(timezone=True), server_default=func.now())
    facility_type = Column(String(10), nullable=True)
    md_license_status = Column(String(40), nullable=True)
    decision_maker_name = Column(String(255), nullable=True)
    decision_maker_title = Column(String(120), nullable=True)
    direct_email = Column(String(255), nullable=True)
    facility_county = Column(String(100), nullable=True)
    outreach_payload_json = Column(Text, nullable=True)
    outreach_ready = Column(String(5), nullable=False, default="false")


class CaregiverIntakeQueue(Base):
    """Text-to-apply and lightweight landing leads awaiting full credential onboarding."""

    __tablename__ = "caregiver_intake_queue"

    intake_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_number = Column(String(20), nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    credential_type = Column(String(20), nullable=False, default="CNA")
    home_zip = Column(String(20), nullable=True)
    landing_slug = Column(String(120), nullable=False, default="baltimore-instant-pay-cna")
    market = Column(String(80), nullable=False, default="Baltimore")
    queue_status = Column(String(30), nullable=False, default="QUEUED")
    sms_consent = Column(String(5), nullable=False, default="true")
    consent_version = Column(String(20), nullable=False)
    client_ip = Column(String(64), nullable=True)
    notes = Column(Text, nullable=True)
    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maryland_providers.provider_id", ondelete="SET NULL"),
        nullable=True,
    )
    queued_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class MdProviderLicensure(Base):
    __tablename__ = "md_provider_licensure"

    profile_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maryland_providers.provider_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    cna_license_number = Column(String(50), nullable=True)
    gna_endorsement_status = Column(Boolean, nullable=False, default=False)
    mbon_status_last_checked = Column(DateTime(timezone=True), nullable=True)
    mbon_last_status = Column(String(40), nullable=True)
    mbon_expires_on = Column(DateTime(timezone=True), nullable=True)
    ohcq_sanction_flag = Column(Boolean, nullable=False, default=False)
    compact_multistate = Column(Boolean, nullable=False, default=False)
    facility_county = Column(String(100), nullable=True)
    verification_payload_json = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class MdOutreachPayload(Base):
    __tablename__ = "md_outreach_payloads"

    payload_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("b2b_raw_leads.lead_id"), nullable=True)
    facility_contact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("facility_contacts.contact_id", ondelete="SET NULL"),
        nullable=True,
    )
    facility_name = Column(String(255), nullable=False)
    decision_maker_name = Column(String(255), nullable=True)
    decision_maker_title = Column(String(120), nullable=True)
    direct_email = Column(String(255), nullable=True)
    facility_county = Column(String(100), nullable=True)
    facility_type = Column(String(10), nullable=True)
    email_subject = Column(String(500), nullable=False)
    email_body = Column(Text, nullable=False)
    sms_body = Column(String(320), nullable=True)
    channel = Column(String(20), nullable=False, default="EMAIL")
    status = Column(String(30), nullable=False, default="READY")
    generated_at = Column(DateTime(timezone=True), server_default=func.now())


class MdMarketFacility(Base):
    __tablename__ = "facilities"

    facility_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name = Column(String(255), nullable=False)
    facility_type = Column(String(10), nullable=False)
    md_license_number = Column(String(64), nullable=True, unique=True)
    md_license_status = Column(String(40), nullable=False, default="UNKNOWN")
    md_county = Column(String(100), nullable=False)
    state = Column(String(2), nullable=False, default="MD")
    address_line = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    zip_code = Column(String(20), nullable=True)
    phone = Column(String(30), nullable=True)
    maryland_facility_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maryland_facilities.facility_id", ondelete="SET NULL"),
        nullable=True,
    )
    source = Column(String(40), nullable=False, default="ohcq")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MdFacilityContact(Base):
    __tablename__ = "facility_contacts"

    contact_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_id = Column(
        UUID(as_uuid=True),
        ForeignKey("facilities.facility_id", ondelete="CASCADE"),
        nullable=False,
    )
    full_name = Column(String(255), nullable=False)
    contact_role = Column(String(20), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(30), nullable=True)
    outreach_status = Column(String(20), nullable=False, default="PENDING")
    last_contacted_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MdProviderCompliance(Base):
    __tablename__ = "md_provider_compliance"

    compliance_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maryland_providers.provider_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    credential_type = Column(String(10), nullable=False)
    license_number = Column(String(50), nullable=False)
    has_gna_endorsement = Column(Boolean, nullable=False, default=False)
    license_expires_on = Column(DateTime(timezone=True), nullable=True)
    compliance_status = Column(String(20), nullable=False, default="PENDING")
    mbon_status_last_checked = Column(DateTime(timezone=True), nullable=True)
    mbon_last_status = Column(String(40), nullable=True)
    ohcq_sanction_flag = Column(Boolean, nullable=False, default=False)
    compact_multistate = Column(Boolean, nullable=False, default=False)
    home_county = Column(String(100), nullable=True)
    verification_payload_json = Column(Text, nullable=True)
    rejection_reason = Column(String(500), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class IngestedOpenShift(Base):
    __tablename__ = "ingested_open_shifts"

    ingest_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    composite_hash = Column(String(64), nullable=False, unique=True)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("maryland_facilities.facility_id"), nullable=False)
    offer_id = Column(UUID(as_uuid=True), ForeignKey("offercare_job_offers.offer_id"), nullable=True)
    source = Column(String(30), nullable=False, default="manus_vms")
    shift_date = Column(String(20), nullable=False)
    unit_dept = Column(String(120), nullable=False)
    start_time = Column(String(20), nullable=False)
    shift_role = Column(String(100), nullable=False)
    hourly_pay_rate = Column(Numeric(8, 2), nullable=False)
    payload_json = Column(Text, nullable=True)
    match_payload_json = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="INGESTED")
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())


class ProviderProfileEmbedding(Base):
    """
    Provider semantic embeddings for Component 2 (SemanticMatcher).
    
    Stores 1536-dimension vectors for AI-powered caregiver-shift matching.
    Uses pgvector extension with HNSW indexing for fast similarity search.
    """
    __tablename__ = "provider_profile_embeddings"

    provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), primary_key=True)
    profile_text = Column(Text, nullable=False)
    # embedding_vector stored via pgvector extension — accessed through raw SQL
    # Column definition: embedding_vector vector(1536)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ShiftEmbedding(Base):
    """
    Shift requirement embeddings for Component 2 (SemanticMatcher).
    
    Stores 1536-dimension vectors for facility shift requirements.
    Enables semantic matching between caregiver skills and shift needs.
    """
    __tablename__ = "shift_embeddings"

    shift_id = Column(UUID(as_uuid=True), primary_key=True)
    shift_description = Column(Text, nullable=False)
    required_license = Column(String(20), nullable=False)
    # embedding_vector stored via pgvector extension — accessed through raw SQL
    # Column definition: embedding_vector vector(1536)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class HB1106BiasLedger(Base):
    """
    Maryland HB 1106 tamper-evident bias audit ledger (Component 3).
    
    Blockchain-style hash-chained ledger for algorithmic employment decisions.
    Each record contains SHA-256 hash of previous record, forming immutable chain.
    
    Compliance: MD HB 1106 § 3-601 — Bias Audit and Record Retention (2024).
    """
    __tablename__ = "hb1106_bias_ledger"
    __table_args__ = (
        UniqueConstraint("block_hash", name="uq_hb1106_block_hash"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id = Column(String(255), nullable=False, index=True)
    parent_hash = Column(String(64), nullable=False)  # Previous block's hash or genesis
    block_hash = Column(String(64), nullable=False)  # This block's SHA-256 hash
    serialized_payload = Column(Text, nullable=False)  # Canonical JSON (sorted keys)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class VMSShiftIngest(Base):
    """
    VMS (Vendor Management System) shift ingest table (Component 4).
    
    High-throughput shift data ingestion with concurrency guards.
    Supports ShiftWise, Fieldglass, and custom facility VMS feeds.
    
    Features:
    - Time-overlap conflict detection
    - Crisis rate flagging (hourly_rate > $120)
    - Status tracking (PENDING, ACTIVE, CONFLICT_OVERLAP, CANCELLED)
    """
    __tablename__ = "vms_shifts_ingest"
    __table_args__ = (
        # Check constraints for data integrity
        # valid_time_range already exists in creation SQL
        # valid_hourly_rate already exists in creation SQL
    )

    shift_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vms_source = Column(String(50), nullable=False)  # ShiftWise, Fieldglass, Manual
    facility_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    shift_start = Column(DateTime(timezone=True), nullable=False, index=True)
    shift_end = Column(DateTime(timezone=True), nullable=False, index=True)
    required_license = Column(String(20), nullable=False, index=True)  # RN, LPN, CNA, GNA, NA
    hourly_rate = Column(Numeric(8, 2), nullable=False)
    shift_description = Column(Text, nullable=True)
    crisis_rate = Column(Boolean, default=False, nullable=False)
    status = Column(String(30), nullable=False, default="PENDING", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ComplianceAuditLedger(Base):
    """
    Compliance audit ledger for Component 1 (CircuitBreaker) intercept logging.
    
    Records circuit breaker intercepts, external API failures, and fallback routes.
    Provides audit trail for compliance review and system health monitoring.
    """
    __tablename__ = "compliance_audit_ledger"

    audit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False, index=True)  # CIRCUIT_BREAKER_INTERCEPT, etc.
    provider_id = Column(UUID(as_uuid=True), nullable=True)
    facility_id = Column(UUID(as_uuid=True), nullable=True)
    match_id = Column(String(255), nullable=True, index=True)
    error_type = Column(String(50), nullable=True)  # TIMEOUT, UPSTREAM_EXCEPTION, etc.
    error_detail = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)  # Additional context as JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class ProviderStripePayoutAccount(Base):
    __tablename__ = "provider_stripe_payout_accounts"

    provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), primary_key=True)
    stripe_connect_account_id = Column(String(128), nullable=False)
    stripe_debit_card_id = Column(String(128), nullable=False)
    instant_payout_enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ShiftTimesheetPayout(Base):
    __tablename__ = "shift_timesheet_payouts"

    payout_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timesheet_id = Column(UUID(as_uuid=True), nullable=False, unique=True)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=False)
    gross_pay_amount = Column(Numeric(10, 2), nullable=False)
    supervisor_name = Column(String(255), nullable=False)
    supervisor_signed_at = Column(DateTime(timezone=True), nullable=False)
    payout_eligible_at = Column(DateTime(timezone=True), nullable=False)
    payout_status = Column(String(30), nullable=False, default="PENDING")
    stripe_payout_id = Column(String(128), nullable=True)
    stripe_mode = Column(String(30), nullable=True)
    failure_reason = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)


class FacilityBillingAuditLedger(Base):
    """B2B facility invoice audit trail — markup + employer FICA per completed shift."""

    __tablename__ = "facility_billing_audit_ledger"

    audit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timesheet_id = Column(UUID(as_uuid=True), nullable=True)
    provider_id = Column(UUID(as_uuid=True), nullable=True)
    facility_id = Column(UUID(as_uuid=True), nullable=True)
    offer_id = Column(UUID(as_uuid=True), nullable=True)
    hours_worked = Column(Numeric(8, 2), nullable=False)
    gross_caregiver_pay_rate = Column(Numeric(8, 2), nullable=False)
    margin_pct = Column(Numeric(6, 4), nullable=False)
    employer_fica_rate = Column(Numeric(6, 4), nullable=False)
    gross_pay = Column(Numeric(10, 2), nullable=False)
    platform_margin = Column(Numeric(10, 2), nullable=False)
    employer_taxes = Column(Numeric(10, 2), nullable=False)
    total_facility_bill = Column(Numeric(10, 2), nullable=False)
    invoice_payload_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


def _load_clinician_calendar_module():
    """Register clinician calendar ORM once (file lives under app/models/ but app.models is models.py)."""
    import importlib.util
    import sys
    from pathlib import Path

    module_name = "app._models_clinician_calendar"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached

    module_path = Path(__file__).resolve().parent / "models" / "clinician_calendar.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError("clinician_calendar model module unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_clinician_calendar = _load_clinician_calendar_module()
ClinicianCalendarEvent = _clinician_calendar.ClinicianCalendarEvent
CALENDAR_EVENT_TYPES = _clinician_calendar.CALENDAR_EVENT_TYPES
EVENT_TYPE_SHIFT_COMMITMENT = _clinician_calendar.EVENT_TYPE_SHIFT_COMMITMENT
EVENT_TYPE_SOFT_BLOCK_PREFERENCE = _clinician_calendar.EVENT_TYPE_SOFT_BLOCK_PREFERENCE
EVENT_TYPE_BLACKOUT_UNAVAILABLE = _clinician_calendar.EVENT_TYPE_BLACKOUT_UNAVAILABLE


def _load_caregiver_accounts_module():
    """Register dual-account caregiver ORM (module lives under app/models/)."""
    import importlib.util
    import sys
    from pathlib import Path

    module_name = "app._models_caregiver_accounts"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached

    module_path = Path(__file__).resolve().parent / "models" / "caregiver_accounts.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError("caregiver_accounts model module unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_caregiver_accounts = _load_caregiver_accounts_module()
CaregiverProfile = _caregiver_accounts.CaregiverProfile
CaregiverW2EmployeeAccount = _caregiver_accounts.CaregiverW2EmployeeAccount
Caregiver1099ContractorAccount = _caregiver_accounts.Caregiver1099ContractorAccount
EMPLOYMENT_TIER_W2 = _caregiver_accounts.EMPLOYMENT_TIER_W2
EMPLOYMENT_TIER_1099 = _caregiver_accounts.EMPLOYMENT_TIER_1099
EMPLOYMENT_TIERS = _caregiver_accounts.EMPLOYMENT_TIERS
EIN_VALIDATION_UNVALIDATED = _caregiver_accounts.EIN_VALIDATION_UNVALIDATED
EIN_VALIDATION_PENDING = _caregiver_accounts.EIN_VALIDATION_PENDING
EIN_VALIDATION_VALIDATED = _caregiver_accounts.EIN_VALIDATION_VALIDATED
EIN_VALIDATION_REJECTED = _caregiver_accounts.EIN_VALIDATION_REJECTED
EIN_VALIDATION_STATUSES = _caregiver_accounts.EIN_VALIDATION_STATUSES


# ═══════════════════════════════════════════════════════════════════
# CONVERSATIONAL SMS DISPATCH — TIER 1 FEATURE
# Sprint: VCAI-TIER1-SPRINT-2026-07-07
# Migration: 028_conversational_sms_tables
# ═══════════════════════════════════════════════════════════════════

class ConversationalSmsSession(Base):
    """
    SMS conversation session for facility shift requests.
    
    Tracks the state machine for conversational text-to-book dispatch.
    """
    __tablename__ = "conversational_sms_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("maryland_facilities.facility_id"), nullable=True, index=True)
    facility_phone = Column(String(20), nullable=False, index=True)
    session_state = Column(String(32), nullable=False, default="INTENT_DETECTION", index=True)
    intent_data = Column(Text, nullable=True)
    created_shifts = Column(Text, nullable=True)
    message_count = Column(String(10), default="0")
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class ConversationalSmsMessage(Base):
    """
    Individual SMS messages within a conversational session.
    
    Logs all inbound and outbound messages with AI intent classification.
    """
    __tablename__ = "conversational_sms_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(64), nullable=False, index=True)
    direction = Column(String(10), nullable=False, index=True)
    from_phone = Column(String(20), nullable=False)
    to_phone = Column(String(20), nullable=False)
    message_body = Column(Text, nullable=False)
    intent_classification = Column(Text, nullable=True)
    twilio_message_sid = Column(String(64), nullable=True)
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class NurseSmsDispatchLog(Base):
    """
    SMS dispatch log for wave-based nurse notifications.
    
    Tracks each SMS sent to nurses with wave number and response tracking.
    """
    __tablename__ = "nurse_sms_dispatch_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shift_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=True, index=True)
    wave_number = Column(String(10), nullable=False, index=True)
    dispatch_priority = Column(String(10), nullable=True)
    message_body = Column(Text, nullable=False)
    twilio_message_sid = Column(String(64), nullable=True)
    dispatched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    responded_at = Column(DateTime(timezone=True), nullable=True)
    response_intent = Column(String(32), nullable=True)
    response_message = Column(Text, nullable=True)


# ═══════════════════════════════════════════════════════════════════
# WAVE DISPATCH LOGIC — TIER 1 FEATURE #2
# Sprint: VCAI-TIER1-SPRINT-2026-07-07
# Migration: 029_wave_dispatch_tables
# ═══════════════════════════════════════════════════════════════════

class WaveDispatchConfig(Base):
    """
    Configuration for facility-specific wave dispatch strategies.
    
    Controls wave sizes, delays, and bonus rounds.
    """
    __tablename__ = "wave_dispatch_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("maryland_facilities.facility_id"), nullable=True, index=True)
    wave_1_size = Column(String(10), default="5")
    wave_1_delay_seconds = Column(String(10), default="300")
    wave_2_size = Column(String(10), default="10")
    wave_2_delay_seconds = Column(String(10), default="300")
    wave_3_size = Column(String(10), default="20")
    wave_3_delay_seconds = Column(String(10), default="600")
    wave_4_bonus_enabled = Column(Boolean, default=True)
    wave_4_bonus_amount_per_hour = Column(Numeric(10, 2), default=5.00)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WaveDispatchRun(Base):
    """
    Active wave dispatch run for a shift.
    
    Tracks progress through waves and completion status.
    """
    __tablename__ = "wave_dispatch_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shift_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    current_wave = Column(String(10), default="1")
    total_dispatched = Column(String(10), default="0")
    total_accepted = Column(String(10), default="0")
    total_declined = Column(String(10), default="0")
    run_state = Column(String(32), nullable=False, default="ACTIVE", index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    completion_reason = Column(String(64), nullable=True)


class ProviderReliabilityScore(Base):
    """
    Calculated reliability score for wave prioritization.
    
    Tracks on-time rate, cancellations, response rate, and facility ratings.
    """
    __tablename__ = "provider_reliability_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=False, unique=True, index=True)
    reliability_score = Column(Numeric(5, 2), default=50.0, index=True)
    on_time_rate = Column(Numeric(5, 4), default=1.0)
    cancellation_rate = Column(Numeric(5, 4), default=0.0)
    response_rate = Column(Numeric(5, 4), default=1.0)
    avg_facility_rating = Column(Numeric(3, 2), default=3.0)
    total_shifts_completed = Column(String(10), default="0")
    last_shift_date = Column(DateTime(timezone=True), nullable=True)
    calculated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ═══════════════════════════════════════════════════════════════════
# SMART DOCUMENT EXTRACTION — TIER 1 FEATURE #3
# Sprint: VCAI-TIER1-SPRINT-2026-07-07
# Migration: 030_document_extraction_tables
# ═══════════════════════════════════════════════════════════════════

class DocumentExtractionLog(Base):
    """
    Document extraction log with OCR and fraud detection results.
    
    Tracks credential document processing with computer vision.
    """
    __tablename__ = "document_extraction_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=False, index=True)
    document_type = Column(String(32), nullable=False, index=True)
    uploaded_file_path = Column(Text, nullable=False)
    ocr_service = Column(String(32), nullable=True)
    extracted_text = Column(Text, nullable=True)
    extracted_entities = Column(Text, nullable=True)
    expiration_date = Column(String(20), nullable=True)
    quality_score = Column(Numeric(5, 2), nullable=True)
    fraud_flags = Column(Text, nullable=True)
    extraction_status = Column(String(32), nullable=False, index=True)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ═══════════════════════════════════════════════════════════════════
# MBON AUTO-SWEEPS — TIER 1 FEATURE #4
# Sprint: VCAI-TIER1-SPRINT-2026-07-07
# Migration: 031_mbon_sweep_tables
# ═══════════════════════════════════════════════════════════════════

class MBONSweepRun(Base):
    """
    Weekly MBON verification sweep run record.
    
    Tracks batch license verification execution.
    """
    __tablename__ = "mbon_sweep_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    run_completed_at = Column(DateTime(timezone=True), nullable=True)
    total_licenses_checked = Column(String(10), default="0")
    total_suspensions = Column(String(10), default="0")
    total_warnings = Column(String(10), default="0")
    total_errors = Column(String(10), default="0")
    run_status = Column(String(32), nullable=False, default="IN_PROGRESS", index=True)
    error_message = Column(Text, nullable=True)


class MBONSweepResult(Base):
    """
    Individual license verification result within a sweep run.
    
    Records status changes and actions taken.
    """
    __tablename__ = "mbon_sweep_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sweep_run_id = Column(UUID(as_uuid=True), ForeignKey("mbon_sweep_runs.id"), nullable=False, index=True)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=False, index=True)
    license_number = Column(String(64), nullable=True)
    previous_status = Column(String(32), nullable=True)
    new_status = Column(String(32), nullable=True)
    action_taken = Column(String(32), nullable=True, index=True)
    mbon_api_response = Column(Text, nullable=True)
    checked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ═══════════════════════════════════════════════════════════════════
# 24/7 INCIDENT HANDLING — TIER 2 FEATURE #5
# Sprint: VCAI-TIER2-SPRINT-2026-07-07
# Migration: 032_incident_handling_tables
# ═══════════════════════════════════════════════════════════════════

class ShiftIncidentLog(Base):
    """
    Shift incident log for cancellations, emergencies, and issues.
    
    Tracks automated response and backup dispatch.
    """
    __tablename__ = "shift_incident_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shift_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=False, index=True)
    incident_type = Column(String(32), nullable=False, index=True)
    incident_severity = Column(String(16), nullable=False, index=True)
    reported_via = Column(String(16), nullable=False)
    incident_details = Column(Text, nullable=True)
    extracted_intent = Column(Text, nullable=True)
    automated_actions_taken = Column(Text, nullable=True)
    backup_dispatched = Column(String(10), default="0")
    reliability_penalty_applied = Column(Numeric(5, 2), nullable=True)
    reported_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class BackupDispatchRun(Base):
    """
    Backup dispatch run triggered by incident.
    
    Tracks emergency wave dispatch for canceled shifts.
    """
    __tablename__ = "backup_dispatch_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("shift_incident_logs.id"), nullable=False, index=True)
    shift_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    original_provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=False)
    backup_wave_number = Column(String(10), default="1")
    total_dispatched = Column(String(10), default="0")
    backup_secured = Column(String(10), default="0", index=True)
    backup_provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=True)
    minutes_before_shift = Column(String(10), nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)


# ═══════════════════════════════════════════════════════════════════
# AUTO-NEGOTIATION & SURGE PRICING — TIER 2 FEATURES #6 & #7
# Sprint: VCAI-TIER2-SPRINT-2026-07-07
# Migration: 033_negotiation_pricing_tables
# ═══════════════════════════════════════════════════════════════════

class FacilityRateConfig(Base):
    """
    Facility rate configuration with base and max rates.
    
    Controls auto-negotiation budget caps.
    """
    __tablename__ = "facility_rate_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_id = Column(UUID(as_uuid=True), unique=True, nullable=False, index=True)
    base_hourly_rate_cna = Column(Numeric(10, 2), default=25.00)
    base_hourly_rate_gna = Column(Numeric(10, 2), default=28.00)
    base_hourly_rate_lpn = Column(Numeric(10, 2), default=35.00)
    base_hourly_rate_rn = Column(Numeric(10, 2), default=45.00)
    max_hourly_rate_cna = Column(Numeric(10, 2), default=40.00)
    max_hourly_rate_gna = Column(Numeric(10, 2), default=45.00)
    max_hourly_rate_lpn = Column(Numeric(10, 2), default=60.00)
    max_hourly_rate_rn = Column(Numeric(10, 2), default=80.00)
    auto_negotiate_enabled = Column(String(10), default="1")
    surge_pricing_enabled = Column(String(10), default="1")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RateNegotiationHistory(Base):
    """
    Rate negotiation history for shifts.
    
    Tracks automatic rate increases to fill urgent shifts.
    """
    __tablename__ = "rate_negotiation_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shift_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    facility_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    original_rate = Column(Numeric(10, 2), nullable=False)
    negotiated_rate = Column(Numeric(10, 2), nullable=False)
    rate_increase_pct = Column(Numeric(5, 2), nullable=False)
    urgency_score = Column(Numeric(5, 2), nullable=True)
    time_until_shift_minutes = Column(String(10), nullable=True)
    negotiation_trigger = Column(String(64), nullable=True)
    approved_by = Column(String(32), default="AUTO_NEGOTIATOR")
    shift_filled_after_increase = Column(String(10), default="0", index=True)
    negotiated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SurgePricingEvent(Base):
    """
    Surge pricing event record.
    
    Tracks regional/market-wide surge multipliers.
    """
    __tablename__ = "surge_pricing_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(32), nullable=False, index=True)
    surge_multiplier = Column(Numeric(5, 2), nullable=False)
    trigger_reason = Column(Text, nullable=True)
    affected_regions = Column(Text, nullable=True)
    affected_credential_types = Column(Text, nullable=True)
    unfilled_shifts_count = Column(String(10), nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    ended_at = Column(DateTime(timezone=True), nullable=True, index=True)


# ═══════════════════════════════════════════════════════════════════
# GAMIFICATION & RETENTION — TIER 2 FEATURE #8
# Sprint: VCAI-TIER2-SPRINT-2026-07-07
# Migration: 034_gamification_tables
# ═══════════════════════════════════════════════════════════════════

class ProviderAchievementLog(Base):
    """
    Provider achievement log for gamification.
    
    Tracks badges, milestones, and rewards.
    """
    __tablename__ = "provider_achievement_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=False, index=True)
    achievement_type = Column(String(64), nullable=False, index=True)
    achievement_tier = Column(String(16), nullable=True)
    reward_unlocked = Column(Text, nullable=True)
    earned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProviderTierStatus(Base):
    """
    Provider tier status for loyalty program.
    
    Tracks tier progression and perks.
    """
    __tablename__ = "provider_tier_status"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=False, unique=True, index=True)
    current_tier = Column(String(16), nullable=False, default="BRONZE", index=True)
    tier_points = Column(String(10), default="0")
    total_shifts_completed = Column(String(10), default="0")
    perfect_attendance_streak = Column(String(10), default="0")
    perks_unlocked = Column(Text, nullable=True)
    last_tier_change = Column(DateTime(timezone=True), nullable=True)
    calculated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ═══════════════════════════════════════════════════════════════════
# EHR INTEGRATION — TIER 3 FEATURE #9
# Sprint: VCAI-TIER3-SPRINT-2026-07-07
# Migration: 035_ehr_integration_tables
# ═══════════════════════════════════════════════════════════════════

class EHRIntegrationConfig(Base):
    """
    EHR integration configuration for facilities.
    
    Supports MatrixCare, PointClickCare, and other EHR systems.
    """
    __tablename__ = "ehr_integration_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_id = Column(UUID(as_uuid=True), unique=True, nullable=False, index=True)
    ehr_system = Column(String(32), nullable=False, index=True)
    ehr_api_endpoint = Column(Text, nullable=True)
    ehr_api_key = Column(Text, nullable=True)
    ehr_facility_id = Column(String(64), nullable=True)
    sync_enabled = Column(String(10), default="1")
    sync_direction = Column(String(32), default="BIDIRECTIONAL")
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EHRShiftSyncLog(Base):
    """
    EHR shift synchronization log.
    
    Tracks bidirectional shift sync between VettedCare and EHR systems.
    """
    __tablename__ = "ehr_shift_sync_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    ehr_system = Column(String(32), nullable=False)
    shift_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    ehr_shift_id = Column(String(64), nullable=True)
    sync_direction = Column(String(16), nullable=False)
    sync_status = Column(String(32), nullable=False, index=True)
    shift_data = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ═══════════════════════════════════════════════════════════════════
# PBJ REPORTING — TIER 3 FEATURE #10
# Sprint: VCAI-TIER3-SPRINT-2026-07-07
# Migration: 036_pbj_reporting_tables
# ═══════════════════════════════════════════════════════════════════

class PBJReportExport(Base):
    """
    PBJ (Payroll-Based Journal) report export record.
    
    CMS-compliant staffing reports for SNF/nursing homes.
    """
    __tablename__ = "pbj_report_exports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    report_period_start = Column(String(20), nullable=False, index=True)
    report_period_end = Column(String(20), nullable=False, index=True)
    cms_provider_id = Column(String(16), nullable=True)
    total_hours_worked = Column(Numeric(10, 2), nullable=True)
    total_shifts_reported = Column(String(10), nullable=True)
    export_format = Column(String(16), default="CSV")
    export_file_path = Column(Text, nullable=True)
    export_status = Column(String(32), nullable=False)
    exported_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ═══════════════════════════════════════════════════════════════════
# ANTI-POACHING & SHIFT BUNDLING — TIER 3 FEATURES #11 & #12
# Sprint: VCAI-TIER3-SPRINT-2026-07-07
# Migration: 037_antipoaching_bundling_tables
# ═══════════════════════════════════════════════════════════════════

class PoachingDetectionLog(Base):
    """
    Poaching detection log with NLP analysis.
    
    Monitors communications for off-platform hiring attempts.
    """
    __tablename__ = "poaching_detection_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=True, index=True)
    facility_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    message_source = Column(String(32), nullable=False)
    message_content = Column(Text, nullable=False)
    poaching_indicators = Column(Text, nullable=True)
    risk_score = Column(Numeric(5, 2), nullable=True, index=True)
    action_taken = Column(String(32), nullable=True)
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ShiftBundle(Base):
    """
    Shift bundle for multi-facility route optimization.
    
    Groups shifts for maximum nurse hours and facility coverage.
    """
    __tablename__ = "shift_bundles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bundle_name = Column(String(128), nullable=True)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), nullable=True, index=True)
    shift_ids = Column(Text, nullable=False)
    total_hours = Column(Numeric(5, 2), nullable=True)
    total_earnings = Column(Numeric(10, 2), nullable=True)
    route_optimized = Column(String(10), default="0")
    bundle_status = Column(String(32), default="PROPOSED", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ═══════════════════════════════════════════════════════════════════
# SECURITY HARDENING — TIER 4 FINAL HARDENING
# Sprint: VCAI-TIER4-HARDENING-2026-07-07
# Migration: 038_security_hardening_tables
# ═══════════════════════════════════════════════════════════════════

class IPWhitelist(Base):
    """
    IP whitelist for trusted corporate networks.
    
    Prevents false positives from rate limiting legitimate facilities.
    """
    __tablename__ = "ip_whitelist"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_id = Column(UUID(as_uuid=True), nullable=True)
    ip_address = Column(String(45), nullable=False, unique=True, index=True)
    ip_range_cidr = Column(String(50), nullable=True)
    whitelist_reason = Column(Text, nullable=True)
    added_by = Column(String(128), nullable=True)
    is_active = Column(String(10), default="1", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)


class SecurityEvidenceLedger(Base):
    """
    Immutable Merkle-tree evidence ledger for legal proof.
    
    SHA-256 hash chain for court-admissible security violations.
    """
    __tablename__ = "security_evidence_ledger"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    block_index = Column(String(10), nullable=False, unique=True, index=True)
    evidence_type = Column(String(32), nullable=False, index=True)
    evidence_data = Column(Text, nullable=False)
    previous_hash = Column(String(64), nullable=True)
    current_hash = Column(String(64), nullable=False, unique=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)


# Import AI models
from app.models.ai_audit import AIAuditLog  # noqa: E402, F401
