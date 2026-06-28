import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Numeric, String, Text
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
    __tablename__ = "provider_profile_embeddings"

    provider_id = Column(UUID(as_uuid=True), ForeignKey("maryland_providers.provider_id"), primary_key=True)
    profile_text = Column(Text, nullable=False)
    # Stored via pgvector; ORM reads/writes through semantic match service raw SQL.
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


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
