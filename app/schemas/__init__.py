from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.services.care_taxonomy import (
    credential_label,
    facility_type_label,
    normalize_credential_type,
    normalize_shift_role,
    requires_npi,
    shift_role_label,
    shift_templates_for_facility_type,
    synthetic_npi_for_caregiver,
)


class FacilityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    facility_type: str = Field(min_length=2, max_length=100)
    county: str = Field(min_length=2, max_length=100)
    state: str = Field(default="MD", min_length=2, max_length=2)
    vms_integration_type: str = "SCRAPE"


class FacilityRead(FacilityCreate):
    model_config = ConfigDict(from_attributes=True)

    facility_id: UUID
    external_source: str | None = None
    external_id: str | None = None
    address: str | None = None
    city: str | None = None
    zip_code: str | None = None
    phone: str | None = None


class ProviderCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    phone_number: str = Field(min_length=10, max_length=20)
    npi_number: str = Field(min_length=10, max_length=10)
    md_license_number: str = Field(min_length=2, max_length=50)
    state: str = Field(default="MD", min_length=2, max_length=2)
    credential_type: str = Field(default="RN", min_length=2, max_length=20)
    service_lines: str = Field(default="ALL", min_length=2, max_length=100)
    license_status: str = "UNVERIFIED"
    min_hourly_rate: float = Field(ge=0)
    response_propensity: float = Field(ge=0, le=1, default=0.5)
    fatigue_score: float = Field(ge=0, default=0)

    @model_validator(mode="after")
    def normalize_provider_fields(self) -> "ProviderCreate":
        self.credential_type = normalize_credential_type(self.credential_type)
        return self


class ProviderRead(ProviderCreate):
    model_config = ConfigDict(from_attributes=True)

    provider_id: UUID
    last_verified_timestamp: datetime | None = None
    applied_at: datetime | None = None
    verification_notes: str | None = None
    consent_signed_at: datetime | None = None


class OfferCreate(BaseModel):
    facility_id: UUID
    shift_role: str = Field(min_length=2, max_length=100)
    hourly_pay_rate: float = Field(gt=0)
    shift_starts_at: datetime | None = None
    shift_ends_at: datetime | None = None


class OfferRead(OfferCreate):
    model_config = ConfigDict(from_attributes=True)

    offer_id: UUID
    compliance_lock_status: str
    shift_starts_at: datetime | None = None
    shift_ends_at: datetime | None = None
    created_at: datetime | None = None


class RankedProviderOut(BaseModel):
    provider_id: UUID
    full_name: str
    phone_number: str
    credential_type: str | None = None
    rank: int
    priority_score: float
    rate_delta: float


class EliminatedProviderOut(BaseModel):
    provider_id: UUID
    full_name: str
    reason: str
    rate_delta: float


class OfferRankResponse(BaseModel):
    offer_id: UUID
    facility_name: str
    shift_role: str
    hourly_pay_rate: float
    notify_order: list[UUID]
    ranked: list[RankedProviderOut]
    eliminated: list[EliminatedProviderOut]
    fill_probability_90s: float
    facility_state: str = "MD"
    shift_starts_at: datetime | None = None
    shift_ends_at: datetime | None = None


class NotifyRequest(BaseModel):
    max_recipients: int = Field(default=1, ge=1, le=5)
    reply_keyword: str = "YES"


class SmsDeliveryOut(BaseModel):
    provider_id: UUID
    phone_number: str
    status: str
    mode: str
    message_body: str
    twilio_sid: str | None = None


class EmailDeliveryOut(BaseModel):
    provider_id: UUID
    email_address: str
    status: str
    mode: str
    subject: str
    message_body: str
    message_id: str | None = None


class PushDeliveryOut(BaseModel):
    provider_id: UUID
    subscription_id: UUID
    endpoint: str
    status: str
    mode: str
    title: str
    message_body: str
    receipt_id: str | None = None


class NotifyResponse(OfferRankResponse):
    deliveries: list[SmsDeliveryOut]
    email_deliveries: list[EmailDeliveryOut] = Field(default_factory=list)
    push_deliveries: list[PushDeliveryOut] = Field(default_factory=list)


class CascadeRecipientOut(BaseModel):
    provider_id: UUID
    full_name: str
    phone_number: str
    rank: int
    notified_at: datetime | None = None


class CascadeStatusResponse(BaseModel):
    offer_id: UUID
    offer_status: str
    cascade_enabled: bool
    timeout_seconds: int
    notified_count: int
    max_recipients: int
    last_notified_at: datetime | None = None
    next_eligible_at: datetime | None = None
    seconds_until_eligible: int
    notified: list[CascadeRecipientOut]
    next_candidate: CascadeRecipientOut | None = None
    can_advance: bool


class CascadeAdvanceRequest(BaseModel):
    reply_keyword: str = "YES"
    force: bool = False


class CascadeAdvanceResponse(BaseModel):
    status: str
    message: str
    delivery: SmsDeliveryOut | None = None
    cascade: CascadeStatusResponse


class SimulateReplyRequest(BaseModel):
    phone_number: str = Field(min_length=10, max_length=20)
    body: str = "YES"


class ShiftLockResponse(BaseModel):
    status: str
    message: str
    offer_id: UUID | None = None
    provider_id: UUID | None = None
    placement_id: UUID | None = None
    facility_name: str | None = None
    shift_role: str | None = None
    shift_starts_at: datetime | None = None
    shift_ends_at: datetime | None = None
    hourly_pay_rate: float | None = None
    provider_license: str | None = None
    journey_steps: list[dict] = Field(default_factory=list)


class FacilityScrapePreviewRow(BaseModel):
    external_id: str
    name: str
    facility_type: str
    county: str
    state: str = "MD"
    city: str | None = None
    address: str | None = None
    phone: str | None = None


class FacilityScrapePreviewResponse(BaseModel):
    source: str
    state: str | None = None
    fetched: int
    facilities: list[FacilityScrapePreviewRow]


class FacilityScrapeRequest(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=500)
    county: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default="MD", min_length=2, max_length=2)
    auto_create_shifts: bool = False


class FacilityScrapeResponse(BaseModel):
    source: str
    state: str | None = None
    fetched: int
    created: int
    updated: int
    skipped: int
    errors: list[str] = Field(default_factory=list)
    shifts_facilities_processed: int = 0
    shifts_created: int = 0
    matched_push_alerts_sent: int = 0


class ExpansionScrapeResponse(BaseModel):
    fetched: int
    created: int
    updated: int
    skipped: int
    errors: list[str] = Field(default_factory=list)
    pennsylvania: FacilityScrapeResponse
    delaware: FacilityScrapeResponse
    new_jersey: FacilityScrapeResponse


class PostAcuteExpansionScrapeResponse(BaseModel):
    fetched: int
    created: int
    updated: int
    skipped: int
    errors: list[str] = Field(default_factory=list)
    shifts_facilities_processed: int = 0
    shifts_created: int = 0
    matched_push_alerts_sent: int = 0
    nursing_homes: FacilityScrapeResponse
    home_health: FacilityScrapeResponse


class PostAcuteDemoSeedItem(BaseModel):
    state: str
    facility_type: str
    facility_id: UUID
    offer_id: UUID


class PostAcuteDemoSeedResponse(BaseModel):
    count: int
    states: list[str]
    demos: list[PostAcuteDemoSeedItem]


class DemoSeedBatchOut(BaseModel):
    count: int
    states: list[str]
    demos: list[PostAcuteDemoSeedItem]


class DemoPortalAccountsResponse(BaseModel):
    clinician_count: int
    created: int
    updated: int
    password_hint: str
    demo_status: DemoEnvironmentStatusResponse | None = None


class DemoPushSubscriptionsResponse(BaseModel):
    clinician_count: int
    created: int
    existing: int
    demo_status: DemoEnvironmentStatusResponse | None = None


class MidAtlanticDemoSeedResponse(BaseModel):
    count: int
    states: list[str]
    hospital: DemoSeedBatchOut
    post_acute: DemoSeedBatchOut
    portal_accounts: DemoPortalAccountsResponse


class DemoOfferStatusOut(BaseModel):
    facility_name: str
    state: str
    facility_type: str
    shift_role: str
    offer_id: str | None
    loaded: bool
    resettable: bool = False
    compliance_lock_status: str | None
    matched_clinician_count: int
    push_ready_count: int
    portal_deep_link: str | None = None
    demo_clinician_email: str | None = None
    demo_clinician_name: str | None = None


class DemoPortalLinkOut(BaseModel):
    facility_name: str
    state: str
    shift_role: str
    offer_id: str
    portal_url: str
    demo_clinician_email: str | None = None
    demo_clinician_name: str | None = None


class DemoPortalHintResponse(BaseModel):
    offer_id: str
    facility_name: str
    shift_role: str
    clinician_email: str
    clinician_name: str
    portal_password_hint: str


class DemoPortalHintCheckResponse(BaseModel):
    offer_id: str
    facility_name: str
    shift_role: str
    expected_clinician_email: str
    expected_clinician_name: str
    signed_in_email: str
    signed_in_name: str
    matches: bool
    message: str


class DemoLinksResponse(BaseModel):
    portal_login_url: str
    portal_password_hint: str
    sample_clinician_email: str
    offers: list[DemoPortalLinkOut]


class DemoClinicianOut(BaseModel):
    email: str
    full_name: str
    state: str
    credential_type: str
    portal_enabled: bool = False
    push_enabled: bool = False


class DemoHealthOut(BaseModel):
    status: str
    label: str
    summary: str
    issues: list[str]
    present_facility_count: int | None = None
    broadcasting_facility_count: int | None = None
    expected_facility_count: int | None = None
    gate_hints: list[str] = []
    active_gates: list[str] = []
    gate_count: int = 0
    demo_admin_action_count: int = 0


class DemoEnvironmentStatusResponse(BaseModel):
    loaded: bool
    facility_count: int
    present_facility_count: int
    expected_facility_count: int
    portal_account_count: int
    portal_ready: bool
    push_subscription_count: int
    push_subscriptions_ready: bool
    demo_portal_password_hint: str
    health: DemoHealthOut
    offers: list[DemoOfferStatusOut]
    clinicians: list[DemoClinicianOut]
    next_steps: list[str]
    demo_gates: DemoGatesResponse | None = None
    demo_admin_actions: list[DemoAdminActionOut] = []
    demo_admin_action_count: int = 0


class DemoNotifyMatchedResponse(BaseModel):
    offer_count: int
    matched_push_alerts_sent: int
    demo_status: DemoEnvironmentStatusResponse | None = None


class DemoNotifyMatchedOfferResponse(BaseModel):
    offer_id: str
    facility_name: str
    shift_role: str
    matched_push_alerts_sent: int
    message: str
    demo_status: DemoEnvironmentStatusResponse | None = None


class DemoResetResponse(BaseModel):
    offer_count: int
    offers_reset: int
    placements_cleared: int
    status: DemoEnvironmentStatusResponse | None = None


class DemoResetOfferResponse(BaseModel):
    offer_id: str
    facility_name: str
    shift_role: str
    offers_reset: int
    placements_cleared: int
    message: str
    offer_row: DemoOfferStatusOut | None = None
    status: DemoEnvironmentStatusResponse | None = None


class DemoSetupResponse(BaseModel):
    reset: DemoResetResponse
    seed: MidAtlanticDemoSeedResponse
    push_subscriptions: DemoPushSubscriptionsResponse
    matched_push: DemoNotifyMatchedResponse
    status: DemoEnvironmentStatusResponse


class DemoReadyGateResponse(BaseModel):
    ready: bool
    health_status: str
    health_label: str
    summary: str
    issues: list[str]
    warning: str | None = None


class DemoGateOut(BaseModel):
    id: str
    action: str
    confirm_when: str
    active: bool


class DemoWalkthroughResponse(BaseModel):
    markdown: str
    offer_count: int
    demo_ready: bool
    demo_ready_warning: str | None = None
    health_status: str
    health_label: str


class DemoLockSmokeTestResponse(BaseModel):
    ok: bool
    status: str
    message: str
    facility_name: str | None = None
    shift_role: str | None = None
    offer_id: str | None = None
    clinician_email: str | None = None
    clinician_name: str | None = None
    compliance_lock_status: str | None = None
    placement_id: str | None = None
    placement_verified: bool = False
    vms_submission_status: str | None = None
    offer_row: DemoOfferStatusOut | None = None
    demo_status: DemoEnvironmentStatusResponse | None = None


class ClinicianApplyRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    phone_number: str = Field(min_length=10, max_length=20)
    npi_number: str | None = Field(default=None, min_length=10, max_length=10)
    md_license_number: str = Field(min_length=2, max_length=50)
    state: str = Field(default="MD", min_length=2, max_length=2)
    credential_type: str = Field(default="RN", min_length=2, max_length=20)
    service_lines: str | None = Field(default=None, min_length=2, max_length=100)
    min_hourly_rate: float = Field(ge=0)
    response_propensity: float = Field(ge=0, le=1, default=0.5)
    fatigue_score: float = Field(ge=0, default=0)
    password: str | None = Field(default=None, min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_credential_and_npi(self) -> "ClinicianApplyRequest":
        from app.services.care_taxonomy import credential_valid_in_state, normalize_credential_type, requires_npi
        from app.services.states import normalize_state

        self.credential_type = normalize_credential_type(self.credential_type)
        if requires_npi(self.credential_type) and not str(self.npi_number or "").strip():
            raise ValueError("npi_required_for_credential")
        if not credential_valid_in_state(self.credential_type, normalize_state(self.state)):
            raise ValueError("credential_not_valid_in_state")
        return self


class ClinicianApplyResponse(BaseModel):
    provider: ProviderRead
    auto_check_result: str
    message: str


class ClinicianVerifyRequest(BaseModel):
    action: str = Field(pattern="^(VERIFY|REJECT|EXPIRE)$")
    notes: str | None = Field(default=None, max_length=500)
    reviewer: str = Field(default="admin", min_length=2, max_length=100)


class LicenseVerificationLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    log_id: UUID
    provider_id: UUID
    event_type: str
    check_result: str | None = None
    notes: str | None = None
    reviewer: str | None = None
    created_at: datetime | None = None


class ClinicianVerifyResponse(BaseModel):
    provider: ProviderRead
    log: LicenseVerificationLogRead


class ClinicianLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class ClinicianLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    provider: ProviderRead


class PortalAuthProvidersResponse(BaseModel):
    google: bool = False
    facebook: bool = False
    demo: bool = True
    api_base: str = "http://127.0.0.1:8000"


class ClinicianApplicationStatusResponse(BaseModel):
    provider: ProviderRead
    portal_enabled: bool
    verification_history: list[LicenseVerificationLogRead]


class ClinicianSafetyStatusResponse(BaseModel):
    provider_id: str
    full_name: str
    vetted_status: str
    computed_status: str
    dispatch_eligible: bool
    license_status: str
    dispatch_status: str
    message: str
    vetted_status_updated_at: str | None = None
    documents: list[dict] = Field(default_factory=list)
    screenings: list[dict] = Field(default_factory=list)


class ClinicianPreferencesOut(BaseModel):
    min_hourly_rate: float
    service_lines: str
    service_line_options: list[TaxonomyOptionOut]


class ClinicianPreferencesUpdateRequest(BaseModel):
    min_hourly_rate: float | None = Field(default=None, ge=0)
    service_lines: str | list[str] | None = None


class ClinicianPlacementOut(BaseModel):
    placement_id: UUID
    offer_id: UUID
    facility_name: str
    clinical_unit: str
    hourly_bill_rate: float
    vms_submission_status: str
    vms_status_label: str | None = None
    vms_external_ref: str | None = None
    vms_submitted_at: datetime | None = None
    shift_starts_at: datetime | None = None
    shift_ends_at: datetime | None = None
    outbound_payload_timestamp: datetime | None = None


class ClinicianPaymentOut(BaseModel):
    payout_id: UUID
    timesheet_id: UUID
    placement_id: UUID
    facility_name: str
    shift_role: str | None = None
    hourly_rate: float | None = None
    gross_pay_amount: float
    payout_status: str
    payout_status_label: str | None = None
    payout_eligible_at: datetime
    paid_at: datetime | None = None
    stripe_payout_id: str | None = None
    shift_starts_at: datetime | None = None
    shift_ends_at: datetime | None = None


class ClinicianPaymentReceiptOut(BaseModel):
    receipt_id: str
    payout_id: UUID
    placement_id: UUID
    clinician_name: str
    clinician_email: str
    facility_name: str
    shift_role: str | None = None
    gross_pay_amount: float
    paid_at: datetime | None = None
    stripe_payout_id: str | None = None
    payout_status: str
    receipt_filename: str
    receipt_text: str


class ClinicianActivityOut(BaseModel):
    event_id: str
    event_type: str
    label: str
    detail: str | None = None
    amount: float | None = None
    reference: str | None = None
    occurred_at: datetime | None = None
    status: str = "done"


class ClinicianEarningsOut(BaseModel):
    week_paid_amount: float
    lifetime_paid_amount: float
    pending_payroll_amount: float
    shifts_paid_count: int
    last_paid_at: datetime | None = None
    currency: str = "USD"


class ClinicianAlertOut(BaseModel):
    alert_id: str
    alert_type: str
    channel: str
    title: str
    body: str | None = None
    reference: str | None = None
    amount: float | None = None
    sent_at: datetime | None = None
    status: str = "DELIVERED"


class ClinicianNextShiftOut(BaseModel):
    offer_id: UUID
    facility_name: str | None = None
    shift_role: str | None = None
    hourly_pay_rate: float | None = None
    shift_starts_at: datetime | None = None
    shift_ends_at: datetime | None = None


class ClinicianJourneyStatusOut(BaseModel):
    phase: str
    phase_label: str
    next_action: str
    lockable_count: int
    paid_shifts_count: int
    lifetime_paid_amount: float
    can_repeat_journey: bool
    next_lockable_shift: ClinicianNextShiftOut | None = None


class ClinicianJourneyExportOut(BaseModel):
    filename: str
    export_text: str
    phase: str
    phase_label: str
    lockable_count: int
    paid_shifts_count: int
    lifetime_paid_amount: float


class DemoPortalAutopilotOut(BaseModel):
    ok: bool
    message: str | None = None
    reason: str | None = None
    repaired_placements: int = 0
    vms_dispatched: int = 0
    payments_created: int = 0
    payouts_completed: int = 0
    shifts_replenished: int = 0
    lockable_count: int = 0


class ClinicianScheduleEventOut(BaseModel):
    event_id: UUID
    event_type: str
    shift_id: str | None = None
    start_time: datetime
    end_time: datetime
    facility_name: str | None = None
    shift_role: str | None = None
    created_at: datetime | None = None


class ClinicianScheduleResponse(BaseModel):
    provider_id: UUID
    calendar_token: str
    total: int
    events: list[ClinicianScheduleEventOut]


class ClinicianScheduleBlockCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=64)
    start_time: datetime
    end_time: datetime


class ClinicianScheduleBlockDeleteResponse(BaseModel):
    ok: bool = True
    event_id: UUID


class VmsSubmitResponse(BaseModel):
    placement_id: UUID
    status: str
    mode: str
    external_ref: str | None = None
    message: str


class VmsBatchSubmitResponse(BaseModel):
    submitted: int
    results: list[VmsSubmitResponse]


class ShiftAutoCreateRequest(BaseModel):
    limit: int = Field(default=25, ge=1, le=200)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    county: str | None = Field(default=None, max_length=100)
    icu_rate: float = Field(default=120.0, gt=0)
    er_rate: float = Field(default=110.0, gt=0)
    med_surg_rate: float = Field(default=95.0, gt=0)


class ShiftAutoCreateFacilityResult(BaseModel):
    facility_id: UUID
    facility_name: str
    created_offers: list[UUID]
    skipped_roles: list[str]


class ShiftAutoCreateResponse(BaseModel):
    facilities_processed: int
    offers_created: int
    matched_push_alerts_sent: int = 0
    results: list[ShiftAutoCreateFacilityResult]


class OpenShiftOut(BaseModel):
    offer_id: UUID
    facility_id: UUID
    facility_name: str
    facility_type: str
    facility_type_label: str
    county: str
    state: str
    shift_role: str
    shift_role_label: str
    hourly_pay_rate: float
    compliance_lock_status: str
    shift_starts_at: datetime | None = None
    shift_ends_at: datetime | None = None
    created_at: datetime | None = None


class MatchedShiftOut(OpenShiftOut):
    rate_delta: float


class ClinicianOpenShiftOut(OpenShiftOut):
    lock_eligible: bool = False
    lock_preview: str | None = None
    rate_delta: float | None = None
    vault_review_recommended: bool = False


class ShiftFilterOptionsResponse(BaseModel):
    states: list[str]
    counties: list[str]
    shift_roles: list[str]
    facility_types: list[str]


class ShiftScheduleUpdateRequest(BaseModel):
    shift_starts_at: datetime
    shift_ends_at: datetime


class PlacementOut(BaseModel):
    placement_id: UUID
    offer_id: UUID
    facility_name: str
    clinical_unit: str
    hourly_bill_rate: float
    assigned_clinician_id: UUID
    clinician_name: str | None = None
    vms_submission_status: str
    vms_external_ref: str | None = None
    outbound_payload_timestamp: datetime | None = None


class IntegrationChannelStatus(BaseModel):
    configured: bool
    dry_run: bool
    live_ready: bool
    detail: str


class TwilioIntegrationStatus(IntegrationChannelStatus):
    signature_validation: bool
    inbound_webhook_url: str | None = None


class VmsIntegrationStatus(IntegrationChannelStatus):
    submission_url: str | None = None


class EmailIntegrationStatus(IntegrationChannelStatus):
    from_address: str | None = None
    smtp_host: str | None = None


class PushIntegrationStatus(IntegrationChannelStatus):
    vapid_public_key: str | None = None


class IntegrationsStatusResponse(BaseModel):
    twilio: TwilioIntegrationStatus
    email: EmailIntegrationStatus
    vms: VmsIntegrationStatus
    push: PushIntegrationStatus


class TestSmsRequest(BaseModel):
    phone_number: str = Field(min_length=10, max_length=20)
    message: str = Field(default="VettedMe.ai integration test", max_length=320)


class TestSmsResponse(BaseModel):
    status: str
    mode: str
    twilio_sid: str | None = None
    error: str | None = None


class TwilioSmsProductionCheckOut(BaseModel):
    id: str
    title: str
    status: str
    detail: str
    action: str | None = None


class TwilioLockReplySmokeRequest(BaseModel):
    phone_number: str | None = None


class TwilioLockReplySmokeResponse(BaseModel):
    ok: bool
    status: str
    message: str
    offer_id: str | None = None
    provider_id: str | None = None
    placement_id: str | None = None
    phone_number: str
    reply_keyword: str
    facility_name: str
    compliance_lock_status: str | None = None
    inbound_webhook_url: str | None = None


class TestEmailRequest(BaseModel):
    email_address: EmailStr
    subject: str = Field(default="VettedMe.ai integration test", max_length=200)
    message: str = Field(default="VettedMe.ai email alert test", max_length=2000)


class TestEmailResponse(BaseModel):
    status: str
    mode: str
    message_id: str | None = None
    error: str | None = None


class TestVmsResponse(BaseModel):
    status: str
    mode: str
    external_ref: str | None = None
    message: str


class PushConfigResponse(BaseModel):
    enabled: bool
    dry_run: bool
    public_key: str | None = None


class PushSubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=255)
    auth: str = Field(min_length=10, max_length=255)


class PushSubscriptionRegisterRequest(BaseModel):
    endpoint: str = Field(min_length=10, max_length=500)
    keys: PushSubscriptionKeys
    user_agent: str | None = Field(default=None, max_length=500)


class PushSubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subscription_id: UUID
    endpoint: str
    created_at: datetime | None = None
    last_used_at: datetime | None = None


class TestPushRequest(BaseModel):
    endpoint: str = Field(min_length=10, max_length=500)
    p256dh_key: str = Field(min_length=10, max_length=255)
    auth_key: str = Field(min_length=10, max_length=255)
    title: str = Field(default="VettedMe.ai push test", max_length=200)
    message: str = Field(default="VettedMe push alert test", max_length=500)


class TestPushResponse(BaseModel):
    status: str
    mode: str
    receipt_id: str | None = None
    error: str | None = None


class SniperScoreOut(BaseModel):
    provider_id: UUID
    response_propensity: float
    fatigue_score: float
    notifications_total: int
    acceptances_total: int
    notifications_recent: int


class SniperRelearnResponse(BaseModel):
    updated: int
    providers: list[SniperScoreOut]


class SniperClinicianScoreOut(SniperScoreOut):
    full_name: str
    license_status: str
    phone_number: str


class OpsMetricsResponse(BaseModel):
    pending_clinicians: int
    verified_clinicians: int
    open_shifts: int
    locked_shifts: int
    total_sms_sent: int
    total_emails_sent: int
    total_placements: int
    vms_pending: int
    vms_submitted: int
    facilities: int
    audit_events_24h: int
    lock_rate: float


class OpsAuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: UUID
    event_type: str
    actor: str | None = None
    entity_type: str | None = None
    entity_id: UUID | None = None
    summary: str
    metadata_json: str | None = None
    created_at: datetime | None = None


class CascadeWorkerStatusResponse(BaseModel):
    enabled: bool
    cascade_enabled: bool
    interval_seconds: int
    timeout_seconds: int
    running: bool


class CascadeWorkerTickResultOut(BaseModel):
    offer_id: UUID
    status: str
    message: str
    phone_number: str | None = None


class CascadeWorkerTickResponse(BaseModel):
    advanced: int
    results: list[CascadeWorkerTickResultOut]


class StaffingSchedulerStatusResponse(BaseModel):
    vms_enabled: bool
    vms_interval_seconds: int
    vms_running: bool
    vms_last_run_at: datetime | None = None
    job_board_enabled: bool
    job_board_interval_seconds: int
    job_board_running: bool
    job_board_last_run_at: datetime | None = None


class ComplianceSchedulerStatusResponse(BaseModel):
    enabled: bool
    interval_seconds: int
    running: bool
    last_run_at: datetime | None = None
    last_documents_checked: int | None = None
    last_suspended_count: int | None = None


class ProductionOpsCheckOut(BaseModel):
    id: str
    title: str
    status: str
    detail: str
    action: str | None = None


class ProductionOpsDashboardResponse(BaseModel):
    production_ops_ready: bool
    summary: dict
    checks: list[ProductionOpsCheckOut]
    steps: list[str]
    health: dict
    metrics: OpsMetricsResponse
    workers: dict
    integrations: dict
    live_scrapers: dict
    launch: dict
    scraper_probes: list[dict] = []
    audit_events: list[dict] = []


class ProductionOpsRefreshRequest(BaseModel):
    probe_scrapers: bool = True
    audit_limit: int = Field(default=25, ge=1, le=200)


class LiveScraperChannelOut(BaseModel):
    name: str
    dry_run: bool
    configured: bool
    live_ready: bool
    detail: str
    config_hint: str | None = None
    endpoint: str | None = None


class LiveScraperProbeOut(BaseModel):
    channel_id: str
    status: str
    endpoint: str | None = None
    latency_ms: int | None = None
    message: str


class LiveScraperProbeResponse(BaseModel):
    probes: list[LiveScraperProbeOut]


class LiveScraperGoLiveChannelOut(BaseModel):
    id: str
    name: str
    dry_run: bool
    configured: bool
    live_ready: bool
    endpoint: str | None = None
    adapter_path: str | None = None
    config_hint: str | None = None


class LiveScraperGoLiveProfileResponse(BaseModel):
    gateway_base_url: str | None = None
    mock_adapters_enabled: bool
    total_channels: int
    live_ready_count: int
    all_live: bool
    env_snippet: str
    channels: list[LiveScraperGoLiveChannelOut]
    steps: list[str]


class LiveScrapersStatusResponse(BaseModel):
    total_channels: int
    live_ready_count: int
    dry_run_count: int
    all_live: bool
    channels: dict[str, LiveScraperChannelOut]


class DeployCheckItemOut(BaseModel):
    id: str
    title: str
    status: str
    detail: str
    action: str | None = None


# ============================================================================
# OHCQ Compliance Base Components (Maryland Department of Health)
# Must be declared ABOVE DeployChecklistSummary to prevent NameError
# ============================================================================

class DemoGatesResponse(BaseModel):
    gates_active: bool
    bypassed_gates: list[str] = []
    enforced_gates: list[str] = []


class DemoAdminActionOut(BaseModel):
    id: str
    action_type: str
    description: str
    executed: bool
    executed_at: str | None = None


class MarylandProductionCheckOut(BaseModel):
    id: str
    name: str  # e.g., "MBON Registry Connection"
    layer: str  # e.g., "OHCQ / MBON Validation"
    status: str  # "PASSED", "WARNING", "BLOCKED"
    checked_at: str
    passed: bool


class MarylandLaunchCapstoneCheckOut(BaseModel):
    id: str
    gate_name: str  # e.g., "HB 1106 AEDT Disclosure Consent"
    status: str
    passed: bool
    critical: bool = True


class TwilioSmsProductionRunbookResponse(BaseModel):
    sms_ready: bool
    account_sid_configured: bool
    webhook_secure: bool
    steps: list[str] = []
    env_snippet: str
    metrics: dict[str, Any] = {}


# ============================================================================
# End OHCQ Base Components
# ============================================================================


# ============================================================================
# NOTE: Operations, Governance & Ceremony Capstone schemas are defined
# in their comprehensive form later in this file (lines ~1400+).
# The comprehensive versions include additional fields for production readiness
# checks, steps, summaries, and nested runbook integration.
# ============================================================================


class DeployChecklistSummary(BaseModel):
    ready: int
    warnings: int
    blocked: int
    live_sms_ready: bool
    demo_health_status: str | None = None
    demo_health_label: str | None = None
    demo_present_facility_count: int | None = None
    demo_broadcasting_count: int | None = None
    demo_expected_facility_count: int | None = None
    demo_walkthrough_intact: bool | None = None
    demo_active_gates: list[str] = []
    demo_gate_count: int | None = None
    demo_admin_action_count: int | None = None
    docker_compose_command: str
    health_url: str
    admin_url: str
    maryland_production_ready: bool | None = None
    maryland_production_ready_count: int | None = None
    maryland_production_warning_count: int | None = None
    maryland_production_blocked_count: int | None = None
    live_scrapers_all_live: bool | None = None
    live_sms_ready: bool | None = None
    twilio_sms_production_ready: bool | None = None
    maryland_launch_ready: bool | None = None
    maryland_launch_ready_count: int | None = None
    maryland_launch_warning_count: int | None = None
    maryland_launch_blocked_count: int | None = None
    production_ops_ready: bool | None = None
    production_ops_ready_count: int | None = None
    production_ops_warning_count: int | None = None
    production_ops_blocked_count: int | None = None
    production_perfection_ready: bool | None = None
    production_perfection_ready_count: int | None = None
    production_perfection_warning_count: int | None = None
    production_perfection_blocked_count: int | None = None
    production_launch_ceremony_ready: bool | None = None
    production_launch_ceremony_ready_count: int | None = None
    production_launch_ceremony_warning_count: int | None = None
    production_launch_ceremony_blocked_count: int | None = None
    production_go_live_record_ready: bool | None = None
    production_go_live_record_ready_count: int | None = None
    production_go_live_record_warning_count: int | None = None
    production_go_live_record_blocked_count: int | None = None
    production_launch_attestation_ready: bool | None = None
    production_launch_attestation_ready_count: int | None = None
    production_launch_attestation_warning_count: int | None = None
    production_launch_attestation_blocked_count: int | None = None
    production_launch_perfection_ready: bool | None = None
    production_launch_perfection_ready_count: int | None = None
    production_launch_perfection_warning_count: int | None = None
    production_launch_perfection_blocked_count: int | None = None
    production_launch_archive_ready: bool | None = None
    production_launch_archive_ready_count: int | None = None
    production_launch_archive_warning_count: int | None = None
    production_launch_archive_blocked_count: int | None = None
    production_launch_finale_ready: bool | None = None
    production_launch_finale_ready_count: int | None = None
    production_launch_finale_warning_count: int | None = None
    production_launch_finale_blocked_count: int | None = None
    production_launch_bundle_verified_ready: bool | None = None
    production_launch_bundle_verified_ready_count: int | None = None
    production_launch_bundle_verified_warning_count: int | None = None
    production_launch_bundle_verified_blocked_count: int | None = None


class MarylandProductionRunbookResponse(BaseModel):
    production_ready: bool
    summary: dict
    checks: list[MarylandProductionCheckOut]
    steps: list[str]
    env_snippet: str
    launch_urls: dict[str, str]
    probes: list[dict] = []


class MarylandLaunchCapstoneResponse(BaseModel):
    launch_ready: bool
    maryland_production_ready: bool
    twilio_sms_production_ready: bool
    live_sms_ready: bool
    live_scrapers_all_live: bool
    summary: dict
    checks: list[MarylandLaunchCapstoneCheckOut]
    steps: list[str]
    env_snippet: str
    launch_urls: dict[str, str]
    probes: list[dict] = []
    maryland_production_runbook: MarylandProductionRunbookResponse | None = None
    twilio_sms_production_runbook: TwilioSmsProductionRunbookResponse | None = None


class MarylandLaunchSmokeRequest(BaseModel):
    phone_number: str | None = None
    probe_scrapers: bool = True


class MarylandLaunchSmokeResponse(BaseModel):
    ok: bool
    launch_ready: bool
    scraper_probes_ok: bool
    lock_reply_smoke_ok: bool
    scraper_probes: list[dict] = []
    lock_reply_smoke: TwilioLockReplySmokeResponse
    facility_name: str | None = None
    placement_id: str | None = None
    message: str


class ProductionPerfectionCheckOut(BaseModel):
    id: str
    title: str
    status: str
    detail: str
    action: str | None = None


class ProductionPerfectionCapstoneResponse(BaseModel):
    production_perfection_ready: bool
    production_ops_ready: bool
    maryland_launch_ready: bool
    summary: dict
    checks: list[ProductionPerfectionCheckOut]
    steps: list[str]
    env_snippet: str
    launch_urls: dict[str, str]
    production_ops_dashboard: ProductionOpsDashboardResponse | None = None
    maryland_launch_capstone: MarylandLaunchCapstoneResponse | None = None


class ProductionPerfectionCheckRequest(BaseModel):
    phone_number: str | None = None
    probe_scrapers: bool = True


class ProductionPerfectionCheckResponse(BaseModel):
    ok: bool
    production_perfection_ready: bool
    production_ops_ready: bool
    maryland_launch_ready: bool
    launch_smoke_ok: bool
    ops_refresh_ok: bool
    launch_smoke: MarylandLaunchSmokeResponse
    ops_refresh_summary: dict
    scraper_probes: list[dict] = []
    facility_name: str | None = None
    placement_id: str | None = None
    message: str


class ProductionLaunchCeremonyCheckOut(BaseModel):
    id: str
    title: str
    status: str
    detail: str
    action: str | None = None


class ProductionLaunchCeremonyResponse(BaseModel):
    launch_ceremony_ready: bool
    production_perfection_ready: bool
    production_ops_ready: bool
    maryland_launch_ready: bool
    summary: dict
    checks: list[ProductionLaunchCeremonyCheckOut]
    steps: list[str]
    signoff_markdown: str
    launch_urls: dict[str, str]
    bundle_artifacts: list[str] = []
    production_perfection_capstone: ProductionPerfectionCapstoneResponse | None = None


class ProductionLaunchCeremonyRunRequest(BaseModel):
    phone_number: str | None = None
    probe_scrapers: bool = True


class ProductionLaunchCeremonyRunResponse(BaseModel):
    ok: bool
    launch_ceremony_ready: bool
    production_perfection_ready: bool
    perfection_check_ok: bool
    perfection_check: ProductionPerfectionCheckResponse
    signoff_markdown: str
    deploy_bundle_filename: str
    deploy_bundle_file_count: int
    facility_name: str | None = None
    placement_id: str | None = None
    message: str


class ProductionGoLiveRecordCheckOut(BaseModel):
    id: str
    title: str
    status: str
    detail: str
    action: str | None = None


class ProductionGoLiveRecordResponse(BaseModel):
    production_go_live_record_ready: bool
    launch_ceremony_ready: bool
    production_perfection_ready: bool
    production_ops_ready: bool
    maryland_launch_ready: bool
    sealed: bool
    immutable: bool
    record_id: str | None = None
    sealed_at: str | None = None
    summary: dict
    checks: list[ProductionGoLiveRecordCheckOut]
    steps: list[str]
    launch_urls: dict[str, str]
    bundle_artifacts: list[str] = []
    health_snapshot: dict
    production_launch_ceremony: ProductionLaunchCeremonyResponse | None = None
    sealed_record: dict | None = None


class ProductionGoLiveRecordSealRequest(BaseModel):
    phone_number: str | None = None
    probe_scrapers: bool = True


class ProductionGoLiveRecordSealResponse(BaseModel):
    ok: bool
    already_sealed: bool
    production_go_live_record_ready: bool
    launch_ceremony_ready: bool
    perfection_check_ok: bool | None = None
    ceremony_run: ProductionLaunchCeremonyRunResponse | None = None
    health_snapshot: dict | None = None
    record_id: str | None = None
    sealed_at: str | None = None
    deploy_bundle_filename: str
    deploy_bundle_file_count: int
    facility_name: str | None = None
    placement_id: str | None = None
    message: str


class ProductionLaunchAttestationCheckOut(BaseModel):
    id: str
    title: str
    status: str
    detail: str
    action: str | None = None


class ProductionLaunchAttestationResponse(BaseModel):
    production_launch_attestation_ready: bool
    production_go_live_record_ready: bool
    launch_ceremony_ready: bool
    production_perfection_ready: bool
    production_ops_ready: bool
    maryland_launch_ready: bool
    attested: bool
    digest_valid: bool
    attestation_id: str | None = None
    attested_at: str | None = None
    record_id: str | None = None
    digest_sha256: str | None = None
    summary: dict
    checks: list[ProductionLaunchAttestationCheckOut]
    steps: list[str]
    attestation_markdown: str
    launch_urls: dict[str, str]
    bundle_artifacts: list[str] = []
    production_go_live_record: ProductionGoLiveRecordResponse | None = None
    attestation_subject: dict | None = None
    attestation_record: dict | None = None


class ProductionLaunchAttestationAttestResponse(BaseModel):
    ok: bool
    already_attested: bool
    production_launch_attestation_ready: bool
    production_go_live_record_ready: bool
    record_id: str | None = None
    attestation_id: str | None = None
    attested_at: str | None = None
    digest_sha256: str | None = None
    deploy_bundle_filename: str
    deploy_bundle_file_count: int
    message: str


class ProductionLaunchPerfectionSealCheckOut(BaseModel):
    id: str
    title: str
    status: str
    detail: str
    action: str | None = None


class ProductionLaunchPerfectionSealResponse(BaseModel):
    production_launch_perfection_ready: bool
    production_perfection_ready: bool
    production_launch_attestation_ready: bool
    production_go_live_record_ready: bool
    launch_ceremony_ready: bool
    production_ops_ready: bool
    maryland_launch_ready: bool
    sealed: bool
    immutable: bool
    seal_id: str | None = None
    sealed_at: str | None = None
    record_id: str | None = None
    attestation_id: str | None = None
    digest_sha256: str | None = None
    summary: dict
    checks: list[ProductionLaunchPerfectionSealCheckOut]
    steps: list[str]
    launch_urls: dict[str, str]
    bundle_artifacts: list[str] = []
    production_launch_attestation: ProductionLaunchAttestationResponse | None = None
    production_perfection_capstone: ProductionPerfectionCapstoneResponse | None = None
    perfection_seal_record: dict | None = None


class ProductionLaunchPerfectionSealSealRequest(BaseModel):
    phone_number: str | None = None
    probe_scrapers: bool = True


class ProductionLaunchPerfectionSealSealResponse(BaseModel):
    ok: bool
    already_sealed: bool
    production_launch_perfection_ready: bool
    production_perfection_ready: bool
    production_launch_attestation_ready: bool
    production_go_live_record_ready: bool
    launch_ceremony_ready: bool
    seal_id: str | None = None
    sealed_at: str | None = None
    record_id: str | None = None
    attestation_id: str | None = None
    digest_sha256: str | None = None
    deploy_bundle_filename: str
    deploy_bundle_file_count: int
    facility_name: str | None = None
    placement_id: str | None = None
    message: str


class ProductionLaunchArchiveCheckOut(BaseModel):
    id: str
    title: str
    status: str
    detail: str
    action: str | None = None


class ProductionLaunchArchiveManifestEntryOut(BaseModel):
    filename: str
    sha256: str
    byte_count: int


class ProductionLaunchArchiveResponse(BaseModel):
    production_launch_archive_ready: bool
    production_launch_perfection_ready: bool
    production_launch_attestation_ready: bool
    production_go_live_record_ready: bool
    launch_ceremony_ready: bool
    production_perfection_ready: bool
    archived: bool
    digest_valid: bool
    archive_id: str | None = None
    archived_at: str | None = None
    manifest_digest: str | None = None
    artifact_count: int
    summary: dict
    checks: list[ProductionLaunchArchiveCheckOut]
    steps: list[str]
    launch_urls: dict[str, str]
    bundle_artifacts: list[str] = []
    manifest: list[ProductionLaunchArchiveManifestEntryOut] = []
    production_launch_perfection_seal: ProductionLaunchPerfectionSealResponse | None = None
    archive_record: dict | None = None


class ProductionLaunchArchiveArchiveResponse(BaseModel):
    ok: bool
    already_archived: bool
    production_launch_archive_ready: bool
    production_launch_perfection_ready: bool
    archive_id: str | None = None
    archived_at: str | None = None
    manifest_digest: str | None = None
    artifact_count: int
    deploy_bundle_filename: str
    deploy_bundle_file_count: int
    message: str


class ProductionLaunchFinaleCheckOut(BaseModel):
    id: str
    title: str
    status: str
    detail: str
    action: str | None = None


class ProductionLaunchFinaleResponse(BaseModel):
    production_launch_finale_ready: bool
    production_launch_archive_ready: bool
    production_launch_perfection_ready: bool
    production_launch_attestation_ready: bool
    production_go_live_record_ready: bool
    launch_ceremony_ready: bool
    production_perfection_ready: bool
    completed: bool
    immutable: bool
    finale_id: str | None = None
    completed_at: str | None = None
    manifest_digest: str | None = None
    artifact_count: int | None = None
    summary: dict
    checks: list[ProductionLaunchFinaleCheckOut]
    steps: list[str]
    launch_urls: dict[str, str]
    bundle_artifacts: list[str] = []
    production_launch_archive: ProductionLaunchArchiveResponse | None = None
    production_perfection_capstone: ProductionPerfectionCapstoneResponse | None = None
    finale_record: dict | None = None


class ProductionLaunchFinaleRunRequest(BaseModel):
    phone_number: str | None = None
    probe_scrapers: bool = True


class ProductionLaunchFinaleRunResponse(BaseModel):
    ok: bool
    already_completed: bool
    production_launch_finale_ready: bool
    production_launch_archive_ready: bool
    production_launch_perfection_ready: bool
    production_perfection_ready: bool
    finale_id: str | None = None
    completed_at: str | None = None
    manifest_digest: str | None = None
    artifact_count: int | None = None
    deploy_bundle_filename: str
    deploy_bundle_file_count: int
    facility_name: str | None = None
    placement_id: str | None = None
    message: str


class ProductionLaunchBundleVerificationEntryOut(BaseModel):
    filename: str
    expected_sha256: str | None = None
    actual_sha256: str | None = None
    byte_count: int
    status: str
    in_archive_manifest: bool


class ProductionLaunchPerfectionManifestCheckOut(BaseModel):
    id: str
    title: str
    status: str
    detail: str
    action: str | None = None


class ProductionLaunchPerfectionManifestResponse(BaseModel):
    production_launch_bundle_verified_ready: bool
    production_launch_finale_ready: bool
    production_launch_archive_ready: bool
    production_launch_perfection_ready: bool
    production_perfection_ready: bool
    verified: bool
    verification_id: str | None = None
    verified_at: str | None = None
    manifest_digest: str | None = None
    current_manifest_digest: str | None = None
    digest_valid: bool
    matched_count: int
    mismatched_count: int
    missing_count: int
    supplemental_count: int
    bundle_file_count: int
    summary: dict
    checks: list[ProductionLaunchPerfectionManifestCheckOut]
    steps: list[str]
    launch_urls: dict[str, str]
    bundle_artifacts: list[str] = []
    verification_entries: list[ProductionLaunchBundleVerificationEntryOut] = []
    production_launch_finale: ProductionLaunchFinaleResponse | None = None
    verification_record: dict | None = None


class ProductionLaunchBundleVerifyResponse(BaseModel):
    ok: bool
    already_verified: bool
    production_launch_bundle_verified_ready: bool
    production_launch_finale_ready: bool
    production_launch_archive_ready: bool
    verification_id: str | None = None
    verified_at: str | None = None
    manifest_digest: str | None = None
    matched_count: int
    mismatched_count: int
    missing_count: int
    supplemental_count: int
    bundle_file_count: int
    deploy_bundle_filename: str
    deploy_bundle_file_count: int
    message: str


class DeployChecklistResponse(BaseModel):
    summary: DeployChecklistSummary
    demo_gates: DemoGatesResponse | None = None
    demo_admin_actions: list[DemoAdminActionOut] = []
    twilio_console_steps: list[str]
    portal_steps: list[str] = []
    hospital_steps: list[str] = []
    post_acute_steps: list[str] = []
    maryland_platform_steps: list[str] = []
    maryland_production_steps: list[str] = []
    maryland_production_runbook: MarylandProductionRunbookResponse | None = None
    live_sms_production_steps: list[str] = []
    twilio_sms_production_runbook: TwilioSmsProductionRunbookResponse | None = None
    maryland_launch_capstone_steps: list[str] = []
    maryland_launch_capstone: MarylandLaunchCapstoneResponse | None = None
    production_ops_dashboard_steps: list[str] = []
    production_ops_dashboard: ProductionOpsDashboardResponse | None = None
    production_perfection_steps: list[str] = []
    production_perfection_capstone: ProductionPerfectionCapstoneResponse | None = None
    production_launch_ceremony_steps: list[str] = []
    production_launch_ceremony: ProductionLaunchCeremonyResponse | None = None
    production_go_live_record_steps: list[str] = []
    production_go_live_record: ProductionGoLiveRecordResponse | None = None
    production_launch_attestation_steps: list[str] = []
    production_launch_attestation: ProductionLaunchAttestationResponse | None = None
    production_launch_perfection_seal_steps: list[str] = []
    production_launch_perfection_seal: ProductionLaunchPerfectionSealResponse | None = None
    production_launch_archive_steps: list[str] = []
    production_launch_archive: ProductionLaunchArchiveResponse | None = None
    production_launch_finale_steps: list[str] = []
    production_launch_finale: ProductionLaunchFinaleResponse | None = None
    production_launch_bundle_verification_steps: list[str] = []
    production_launch_bundle_verification: ProductionLaunchPerfectionManifestResponse | None = None
    demo_steps: list[str] = []
    export_steps: list[str] = []
    items: list[DeployCheckItemOut]


class TaxonomyOptionOut(BaseModel):
    code: str
    label: str


class ShiftTemplateOut(BaseModel):
    shift_role: str
    hourly_pay_rate: float


class CareTaxonomyResponse(BaseModel):
    facility_types: list[TaxonomyOptionOut]
    credential_types: list[TaxonomyOptionOut]
    shift_roles: list[TaxonomyOptionOut]
    shift_templates_by_facility_type: dict[str, list[ShiftTemplateOut]]
    state_credential_rules: dict[str, object] = Field(default_factory=dict)


class StateCredentialsResponse(BaseModel):
    state: str
    gna_available: bool
    credentials: list[TaxonomyOptionOut]


class ComplianceDocumentOut(BaseModel):
    document_type: str
    status: str
    expires_on: str | None = None


class ComplianceScreeningOut(BaseModel):
    source: str
    status: str
    checked_at: str | None = None


class ProviderComplianceStatusResponse(BaseModel):
    provider_id: UUID
    full_name: str
    license_status: str
    dispatch_status: str
    dispatch_eligible: bool
    documents: list[ComplianceDocumentOut]
    screenings: list[ComplianceScreeningOut]


class CredentialingScreenResponse(BaseModel):
    provider_id: UUID
    format_check: str
    mbon_status: str
    oig_status: str
    judiciary_status: str
    license_status: str
    dispatch_status: str
    blocked: bool


class ComplianceMonitorResponse(BaseModel):
    documents_checked: int
    expiring_alerts: list[dict]
    suspended_provider_ids: list[str]


class GeoMatchedProviderOut(BaseModel):
    provider_id: str
    full_name: str
    credential_type: str | None = None
    dispatch_status: str
    distance_miles: float | None = None


class FacilityCrisisSignalOut(BaseModel):
    signal_id: str
    facility_id: str
    facility_name: str
    county: str | None = None
    signal_type: str
    severity: str
    score: float
    summary: str
    detected_at: str | None = None


class CrisisScanResponse(BaseModel):
    signals_created: int


class VmsIngestShiftOut(BaseModel):
    external_id: str
    facility_name: str
    shift_role: str
    hourly_pay_rate: float
    shift_starts_at: datetime
    source: str


class VmsIngestResponse(BaseModel):
    shifts_fetched: int
    offers_created: int
    offers_skipped: int
    skipped_no_facility: int = 0
    created_offer_ids: list[str] = Field(default_factory=list)
    shifts: list[VmsIngestShiftOut]


class VmsIngestLogOut(BaseModel):
    ingest_id: str
    source: str
    external_id: str
    status: str
    shift_role: str | None = None
    hourly_pay_rate: float | None = None
    facility_name: str | None = None
    offer_id: str | None = None
    ingested_at: str | None = None


class ComplianceProviderRowOut(BaseModel):
    provider_id: UUID
    full_name: str
    credential_type: str | None = None
    license_status: str
    dispatch_status: str
    dispatch_eligible: bool
    expiring_documents: int
    license_expires_on: str | None = None


class ComplianceOverviewResponse(BaseModel):
    total_providers: int
    dispatch_active: int
    dispatch_suspended: int
    expiring_document_alerts: int
    crisis_signal_count: int
    geo_match_radius_miles: float
    postgis_enabled: bool = False
    postgis_version: str | None = None
    dry_run_flags: dict[str, bool]
    providers: list[ComplianceProviderRowOut]


class MarylandLandingCredentialOut(BaseModel):
    code: str
    label: str
    typical_hourly_pay: float
    suggested_minimum: float


class MarylandLandingConsentDisclosures(BaseModel):
    version: str
    credential_screening: str
    sms_dispatch: str
    terms_of_service: str
    terms_of_service_version: str
    terms_of_service_effective_date: str
    terms_of_service_url: str
    privacy_policy: str
    privacy_policy_version: str
    privacy_policy_effective_date: str
    privacy_policy_url: str


class WorkerTermsSectionOut(BaseModel):
    heading: str
    body: str


class WorkerTermsOfServiceResponse(BaseModel):
    title: str
    version: str
    effective_date: str
    sections: list[WorkerTermsSectionOut]


class WorkerPrivacyPolicyResponse(BaseModel):
    title: str
    version: str
    effective_date: str
    sections: list[WorkerTermsSectionOut]


class MarylandLandingPageResponse(BaseModel):
    headline: str
    subheadline: str
    value_props: list[str]
    comar_note: str
    credentials: list[MarylandLandingCredentialOut]
    apply_defaults: dict[str, str]
    portal_url: str
    consent_disclosures: MarylandLandingConsentDisclosures
    terms_of_service: WorkerTermsOfServiceResponse
    privacy_policy: WorkerPrivacyPolicyResponse


class MarylandLandingApplyRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    phone_number: str = Field(min_length=10, max_length=20)
    md_license_number: str = Field(min_length=2, max_length=50)
    credential_type: str = Field(default="CNA", min_length=2, max_length=20)
    npi_number: str | None = Field(default=None, min_length=10, max_length=10)
    home_zip: str | None = Field(default=None, min_length=5, max_length=10)
    service_lines: str | None = Field(default="NURSING_HOME", min_length=2, max_length=100)
    min_hourly_rate: float = Field(ge=0)
    response_propensity: float = Field(ge=0, le=1, default=0.7)
    password: str = Field(min_length=8, max_length=128)
    consent_version: str = Field(min_length=5, max_length=20)
    consent_credential_screening: bool
    consent_sms_dispatch: bool
    consent_terms_of_service: bool
    consent_privacy_policy: bool
    consent_aedt_30_day: bool

    @model_validator(mode="after")
    def validate_maryland_floor_staff(self) -> "MarylandLandingApplyRequest":
        from app.services.care_taxonomy import normalize_credential_type, requires_npi
        from app.services.maryland_landing import MARYLAND_LANDING_CREDENTIALS
        from app.services.worker_consent import WORKER_CONSENT_VERSION

        self.credential_type = normalize_credential_type(self.credential_type)
        if self.credential_type not in MARYLAND_LANDING_CREDENTIALS:
            raise ValueError("unsupported_credential")
        if requires_npi(self.credential_type) and not str(self.npi_number or "").strip():
            raise ValueError("npi_required_for_credential")
        if self.consent_version != WORKER_CONSENT_VERSION:
            raise ValueError("consent_version_mismatch")
        if not (
            self.consent_credential_screening
            and self.consent_sms_dispatch
            and self.consent_terms_of_service
            and self.consent_privacy_policy
            and self.consent_aedt_30_day
        ):
            raise ValueError("consent_required")
        return self


class WorkerInflowSummaryResponse(BaseModel):
    join_url: str
    consent_version: str
    terms_of_service_version: str
    privacy_policy_version: str
    opt_in_applicants: int
    pending_review: int
    verified_workers: int
    sms_consent_recorded: int
    terms_accepted: int
    privacy_accepted: int
    sms_opt_out_count: int
    legal_model: str
    playbook: list[str]


class MarylandLandingApplyResponse(BaseModel):
    provider_id: str
    full_name: str
    email: EmailStr
    credential_type: str
    license_status: str
    dispatch_status: str
    auto_check_result: str
    format_check: str
    mbon_status: str
    oig_status: str
    judiciary_status: str
    credentialing_blocked: bool
    message: str
    portal_url: str
    verified_at: str
    consent_signed_at: str | None = None


class BaltimoreInstantPaySellingPointOut(BaseModel):
    id: str
    title: str
    badge: str
    body: str
    icon: str


class BaltimoreInstantPayTextApplyBlockOut(BaseModel):
    headline: str
    subheadline: str
    cta_label: str
    phone_placeholder: str
    consent_label: str


class BaltimoreInstantPayLandingPageResponse(BaseModel):
    slug: str
    market: str
    headline: str
    subheadline: str
    selling_points: list[BaltimoreInstantPaySellingPointOut]
    trust_chips: list[str]
    typical_hourly_pay: float
    apply_defaults: dict[str, str]
    text_apply: BaltimoreInstantPayTextApplyBlockOut
    consent_version: str
    full_apply_url: str
    portal_url: str
    region_slug: str | None = None
    license_slug: str | None = None
    region_label: str | None = None
    county: str | None = None
    credential_type: str | None = None
    license_label: str | None = None
    path: str | None = None
    api_path: str | None = None
    text_apply_api_path: str | None = None
    intake_table: str | None = None
    region_metadata: dict[str, Any] | None = None
    layout: dict[str, Any] | None = None


class BaltimoreInstantPayTextApplyRequest(BaseModel):
    phone_number: str = Field(min_length=10, max_length=20)
    full_name: str | None = Field(default=None, max_length=255)
    credential_type: str = Field(default="CNA", min_length=2, max_length=20)
    home_zip: str | None = Field(default=None, min_length=5, max_length=10)
    consent_version: str = Field(min_length=5, max_length=20)
    consent_sms_dispatch: bool

    @model_validator(mode="after")
    def validate_text_apply(self) -> "BaltimoreInstantPayTextApplyRequest":
        from app.services.care_taxonomy import normalize_credential_type
        from app.services.maryland_landing import MARYLAND_LANDING_CREDENTIALS
        from app.services.worker_consent import WORKER_CONSENT_VERSION

        self.credential_type = normalize_credential_type(self.credential_type)
        if self.credential_type not in MARYLAND_LANDING_CREDENTIALS:
            raise ValueError("unsupported_credential")
        if self.consent_version != WORKER_CONSENT_VERSION:
            raise ValueError("consent_version_mismatch")
        if not self.consent_sms_dispatch:
            raise ValueError("consent_required")
        return self


class BaltimoreInstantPayTextApplyResponse(BaseModel):
    intake_id: str
    queue_status: str
    phone_number_masked: str
    market: str
    credential_type: str
    message: str
    queued_at: str
    full_apply_url: str
    landing_slug: str | None = None
    region_metadata: dict[str, Any] | None = None


class JobBoardListingOut(BaseModel):
    listing_id: str
    source: str
    external_id: str
    facility_name: str
    matched_facility_id: str | None = None
    matched_facility_name: str | None = None
    city: str | None = None
    county: str | None = None
    state: str
    shift_role: str
    job_title: str
    job_url: str | None = None
    days_open: int
    is_crisis: bool
    first_seen_at: str | None = None
    last_seen_at: str | None = None


class JobBoardCrisisScanResponse(BaseModel):
    listings_scraped: int
    listings_upserted: int
    crisis_listings: int
    signals_created: int
    min_days_threshold: int


class OutreachTargetOut(BaseModel):
    facility_id: str
    facility_name: str
    county: str | None = None
    city: str | None = None
    state: str
    crisis_summary: str
    contact_count: int


class OutreachEnrichResponse(BaseModel):
    facility_id: str
    facility_name: str
    contacts_enriched: int
    contacts_created: int


class OutreachCampaignResponse(BaseModel):
    targets: int
    contacts_enriched: int
    emails_drafted: int
    emails_sent: int
    send_enabled: bool


class OutreachEmailLogOut(BaseModel):
    email_id: str
    facility_id: str
    facility_name: str
    recipient_name: str
    recipient_email: str
    subject: str
    status: str
    mode: str
    crisis_context: str | None = None
    sent_at: str | None = None


class VettedProviderRowOut(BaseModel):
    provider_id: UUID
    full_name: str
    credential_type: str | None = None
    vetted_status: str
    license_status: str
    dispatch_status: str
    vetted_status_updated_at: str | None = None


class VettedAuditEventOut(BaseModel):
    audit_id: str
    provider_id: str | None = None
    event_type: str
    actor: str | None = None
    previous_status: str | None = None
    new_status: str | None = None
    summary: str
    metadata: dict = Field(default_factory=dict)
    created_at: str | None = None


class VettedAlertOut(BaseModel):
    alert_id: str
    provider_id: str
    channel: str
    alert_type: str
    vetted_status: str
    delivery_status: str
    sent_at: str | None = None


class VettedMeDashboardResponse(BaseModel):
    product: str
    tagline: str
    safety_first: bool = True
    total_providers: int
    clear_rate_percent: float
    status_counts: dict[str, int]
    manus_runs_total: int
    manus_runs_applied: int
    audit_events_total: int
    alerts_sent_total: int
    providers: list[VettedProviderRowOut]
    recent_audit: list[VettedAuditEventOut]
    recent_alerts: list[VettedAlertOut]
    manus_webhook: str


class VettedProviderProfileResponse(BaseModel):
    provider_id: str
    full_name: str
    credential_type: str | None = None
    email: str
    phone_number: str
    npi_number: str
    md_license_number: str
    license_status: str
    dispatch_status: str
    dispatch_eligible: bool
    vetted_status: str
    computed_status: str
    vetted_status_updated_at: str | None = None
    license_expires_on: str | None = None
    last_verified_timestamp: str | None = None
    documents: list[ComplianceDocumentOut]
    screenings: list[ComplianceScreeningOut]


class ManusCheckIn(BaseModel):
    check_type: str
    result: str
    notes: str | None = None
    source_url: str | None = None
    evidence: str | None = None


class ManusVettingRunIn(BaseModel):
    run_id: str | None = None
    provider_id: UUID | None = None
    npi_number: str | None = None
    email: str | None = None
    md_license_number: str | None = None
    summary: str | None = None
    recommended_status: str | None = None
    run_full_screen: bool = False
    checks: list[ManusCheckIn] = Field(default_factory=list)


class ManusVettingRunResponse(BaseModel):
    run_id: str
    external_run_id: str
    status: str
    provider_id: str | None = None
    checks_applied: int | None = None
    vetted_status: str | None = None
    computed_status: str | None = None
    status_changed: bool | None = None
    error: str | None = None


class ManusRequiredCheckOut(BaseModel):
    check_type: str
    description: str
    lookup: dict = Field(default_factory=dict)


class ManusWorkQueueItemOut(BaseModel):
    provider_id: str
    full_name: str
    credential_type: str | None = None
    state: str
    npi_number: str
    md_license_number: str
    email: str
    vetted_status: str
    license_status: str
    priority_rank: int
    priority: str
    reason: str | None = None
    last_manus_applied_at: str | None = None
    required_checks: list[str]
    work_order_url: str
    submit_url: str


class ManusWorkQueueResponse(BaseModel):
    generated_at: str
    queue: str
    total_due: int
    returned: int
    skipped_recent_runs: int
    status_breakdown_due: dict[str, int]
    items: list[ManusWorkQueueItemOut]
    submit_batch_url: str
    next_steps: list[str]


class ManusSubmitTemplateOut(BaseModel):
    method: str
    url: str
    headers: dict[str, str]
    body_template: dict


class ManusProviderWorkOrderResponse(BaseModel):
    provider_id: str
    full_name: str
    email: str
    phone_number: str
    credential_type: str | None = None
    state: str
    npi_number: str
    md_license_number: str
    license_status: str
    license_expires_on: str | None = None
    vetted_status: str
    priority: str
    last_manus_applied_at: str | None = None
    required_checks: list[ManusRequiredCheckOut]
    submit: ManusSubmitTemplateOut


class ManusIntegrationConfigResponse(BaseModel):
    product: str
    tagline: str
    base_url: str
    auth_header: str
    required_checks: list[str]
    endpoints: dict[str, str]
    limits: dict[str, int]
    operator_note: str


class ManusBatchRunIn(BaseModel):
    runs: list[ManusVettingRunIn] = Field(default_factory=list)
    run_cycle_after: bool = True


class VettedSafetyCycleResponse(BaseModel):
    compliance: ComplianceMonitorResponse
    vetted_sync: dict
    alerts_sent: list[dict]


class VettedInfraCheckOut(BaseModel):
    name: str
    status: str
    detail: str
    level: str


class VettedInfrastructureResponse(BaseModel):
    product: str
    overall: str
    summary: str
    required_pass: int
    required_total: int
    optional_warnings: int
    manus_worker_required: bool
    manus_hook_ready: bool
    checks: list[VettedInfraCheckOut]
    manus_endpoints: dict[str, str]
    next_without_manus: list[str]


class ManusBatchRunResponse(BaseModel):
    submitted: int
    applied: int
    failed: int
    runs: list[ManusVettingRunResponse]
    safety_cycle: VettedSafetyCycleResponse | None = None


class ManusRecruitmentConfigResponse(BaseModel):
    product: str
    architecture: str
    auth_header: str
    endpoints: dict[str, str]
    filesystem_handoff: dict[str, str]
    lead_csv_required_fields: list[str]
    lead_csv_optional_fields: list[str]
    shift_json_required_fields: list[str]
    manus_workflows: list[dict]
    safety_rules: dict[str, str]


class ManusShiftIngestIn(BaseModel):
    shifts: list[dict] = Field(default_factory=list)


class ManusLeadImportIn(BaseModel):
    csv_filename: str = Field(..., min_length=1, max_length=255)


class ManusRecruitmentProcessResponse(BaseModel):
    ok: bool = True
    detail: dict | list | None = None


class RecruitmentDashboardResponse(BaseModel):
    generated_at_utc: str
    summary: dict
    drop_zones: dict
    manus_config: dict
    contracts: list[dict]
    leads: list[dict]
    ingested_shifts: list[dict]


class ManusDeskPipelineRunIn(BaseModel):
    pipeline: str = Field(
        default="full",
        pattern="^(full|booking|callout|penalty)$",
        description="Desk pipeline mode",
    )
    order_id: str | None = Field(default=None, max_length=128)
    evaluation_timestamp: str | None = None
    request_timestamp: str | None = None
    disrupted_shift_id: str | None = Field(default=None, max_length=128)
    original_provider_id: str | None = Field(default=None, max_length=64)
    facility_id: str | None = Field(default=None, max_length=128)
    provider_id: str | None = Field(default=None, max_length=64)
    total_hours_worked: float | None = Field(default=None, ge=0)
    persist: bool = True


class ManusDeskPipelineRunResponse(BaseModel):
    ok: bool = True
    run_id: str
    pipeline: str
    status: str
    live_execution: bool = False
    result: dict
    log_path: str
    handoff_path: str
    mode: str | None = None
    slice_key: str | None = None
    db_source: dict | None = None


class ManusDeskProductionRunIn(BaseModel):
    evaluation_timestamp: str | None = None
    request_timestamp: str | None = None
    persist: bool = True


class ManusDeskLiveCalloutIn(BaseModel):
    original_provider_id: str = Field(default="CNA-MD-88421", max_length=64)


class ManusDeskLiveCalloutResponse(BaseModel):
    ok: bool = True
    live_execution: bool = True
    mode: str = "PRODUCTION_SLICE"
    slice_key: str
    facility: str | None = None
    original_provider_id: str
    dispatch: dict
    notify_cascade: dict | None = None


class ManusDeskBackupCascadeAdvanceIn(BaseModel):
    dispatch_id: str = Field(..., min_length=8, max_length=128)
    force: bool = False


class ManusDeskBackupCascadeAdvanceResponse(BaseModel):
    ok: bool = True
    status: str
    message: str
    dispatch_id: str
    notification: dict | None = None
    cascade: dict | None = None


class ManusDeskHandoffResponse(BaseModel):
    schema_version: str
    product: str
    architecture: str
    live_execution: bool
    operator_workflows: list[dict]
    engine_chain: list[str]
    filesystem_paths: dict[str, str]
    api_endpoints: dict[str, str]
    auth_header: str
    generated_at_utc: str


# ---------------------------------------------------------------------------
# Dual-account caregiver API (Tier 1 W-2 / Tier 2 1099)
# ---------------------------------------------------------------------------

from app.models import EMPLOYMENT_TIER_1099, EMPLOYMENT_TIER_W2, EMPLOYMENT_TIERS  # noqa: E402


class CaregiverProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    caregiver_profile_id: UUID
    mbon_license_number: str
    full_name: str
    email: EmailStr | None = None
    phone_number: str | None = None
    credential_type: str
    employment_tier: str
    provider_id: UUID | None = None
    account_status: str
    skyflow_vault_record_id: str | None = None
    skyflow_ssn_token: str | None = None
    skyflow_dob_token: str | None = None
    created_at: datetime
    updated_at: datetime


class CaregiverW2AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    w2_account_id: UUID
    caregiver_profile_id: UUID
    maryland_residence_county: str
    local_tax_jurisdiction_code: str | None = None
    w4_on_file: bool
    payroll_withholding_status: str
    employee_payroll_number: str | None = None
    gusto_employee_id: str | None = None
    payroll_onboarding_error: str | None = None
    skyflow_stripe_routing_token: str | None = None
    created_at: datetime
    updated_at: datetime


class Caregiver1099AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    contractor_account_id: UUID
    caregiver_profile_id: UUID
    corporate_legal_name: str
    corporate_ein: str
    corporate_ein_validation_status: str
    ein_validated_at: datetime | None = None
    ein_validation_reference: str | None = None
    created_at: datetime
    updated_at: datetime


class CaregiverAccountBundleOut(BaseModel):
    profile: CaregiverProfileOut
    employment_tier: str
    w2_account: CaregiverW2AccountOut | None = None
    contractor_account: Caregiver1099AccountOut | None = None


class CaregiverProfileCreateIn(BaseModel):
    mbon_license_number: str = Field(min_length=2, max_length=50)
    full_name: str = Field(min_length=2, max_length=255)
    employment_tier: str = Field(min_length=8, max_length=20)
    credential_type: str = Field(default="CNA", min_length=2, max_length=20)
    email: EmailStr | None = None
    phone_number: str | None = Field(default=None, min_length=10, max_length=20)
    provider_id: UUID | None = None
    account_status: str = Field(default="ACTIVE", min_length=4, max_length=30)

    @model_validator(mode="after")
    def validate_tier(self) -> "CaregiverProfileCreateIn":
        tier = str(self.employment_tier or "").strip().upper()
        if tier not in EMPLOYMENT_TIERS:
            raise ValueError("invalid_employment_tier")
        self.employment_tier = tier
        return self


class CaregiverW2AccountCreateIn(BaseModel):
    maryland_residence_county: str = Field(min_length=2, max_length=100)
    local_tax_jurisdiction_code: str | None = Field(default=None, max_length=20)
    w4_on_file: bool = False
    payroll_withholding_status: str = Field(default="PENDING_SETUP", max_length=30)
    employee_payroll_number: str | None = Field(default=None, max_length=50)


class Caregiver1099AccountCreateIn(BaseModel):
    corporate_legal_name: str = Field(min_length=2, max_length=255)
    corporate_ein: str = Field(min_length=9, max_length=12)
    corporate_ein_validation_status: str = Field(default="UNVALIDATED", max_length=30)


class CaregiverProvisionIn(BaseModel):
    mbon_license_number: str = Field(min_length=2, max_length=50)
    full_name: str = Field(min_length=2, max_length=255)
    employment_tier: str = Field(min_length=8, max_length=20)
    credential_type: str = Field(default="CNA", min_length=2, max_length=20)
    email: EmailStr | None = None
    phone_number: str | None = Field(default=None, min_length=10, max_length=20)
    provider_id: UUID | None = None
    maryland_residence_county: str | None = Field(default=None, max_length=100)
    local_tax_jurisdiction_code: str | None = Field(default=None, max_length=20)
    w4_on_file: bool = False
    corporate_legal_name: str | None = Field(default=None, max_length=255)
    corporate_ein: str | None = Field(default=None, max_length=12)
    ssn: str | None = Field(default=None, min_length=9, max_length=11)
    date_of_birth: str | None = Field(default=None, max_length=20)
    stripe_routing_token: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def validate_tier_requirements(self) -> "CaregiverProvisionIn":
        tier = str(self.employment_tier or "").strip().upper()
        if tier not in EMPLOYMENT_TIERS:
            raise ValueError("invalid_employment_tier")
        self.employment_tier = tier
        if tier == EMPLOYMENT_TIER_W2 and not str(self.maryland_residence_county or "").strip():
            raise ValueError("maryland_residence_county_required")
        if tier == EMPLOYMENT_TIER_1099:
            if not str(self.corporate_legal_name or "").strip():
                raise ValueError("corporate_legal_name_required")
            if not str(self.corporate_ein or "").strip():
                raise ValueError("corporate_ein_required")
        return self


class CaregiverProvisionFromProviderIn(BaseModel):
    employment_tier: str = Field(min_length=8, max_length=20)
    maryland_residence_county: str | None = Field(default=None, max_length=100)
    local_tax_jurisdiction_code: str | None = Field(default=None, max_length=20)
    corporate_legal_name: str | None = Field(default=None, max_length=255)
    corporate_ein: str | None = Field(default=None, max_length=12)
    ssn: str | None = Field(default=None, min_length=9, max_length=11)
    date_of_birth: str | None = Field(default=None, max_length=20)
    stripe_routing_token: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def validate_tier_requirements(self) -> "CaregiverProvisionFromProviderIn":
        tier = str(self.employment_tier or "").strip().upper()
        if tier not in EMPLOYMENT_TIERS:
            raise ValueError("invalid_employment_tier")
        self.employment_tier = tier
        if tier == EMPLOYMENT_TIER_W2 and not str(self.maryland_residence_county or "").strip():
            raise ValueError("maryland_residence_county_required")
        if tier == EMPLOYMENT_TIER_1099:
            if not str(self.corporate_legal_name or "").strip():
                raise ValueError("corporate_legal_name_required")
            if not str(self.corporate_ein or "").strip():
                raise ValueError("corporate_ein_required")
        return self


class CaregiverLinkProviderIn(BaseModel):
    provider_id: UUID


class CaregiverEinValidationIn(BaseModel):
    status: str = Field(min_length=4, max_length=30)
    validation_reference: str | None = Field(default=None, max_length=100)


# AI Resume Parser Schemas

class ParsedResumeResponse(BaseModel):
    """Response schema for AI resume parsing endpoint."""
    model_config = ConfigDict(from_attributes=True)
    
    audit_id: str
    candidate_name: str
    email: str | None = None
    phone: str | None = None
    skills: list[str] = Field(default_factory=list)
    certifications: list[dict[str, Any]] = Field(default_factory=list)
    work_history: list[dict[str, Any]] = Field(default_factory=list)
    education: list[dict[str, Any]] = Field(default_factory=list)
    confidence_score: float
    verification_flags: dict[str, bool] = Field(default_factory=dict)
    tokens_used: int | None = None
    cost_usd: float | None = None
    elapsed_ms: int | None = None
    is_degraded: bool = False
    warning: str | None = None


class AIAuditLogEntry(BaseModel):
    """Response schema for AI audit log retrieval."""
    model_config = ConfigDict(from_attributes=True)
    
    audit_id: str
    operation_type: str
    model_used: str
    user_id: str | None = None
    input_hash: str
    input_preview: str | None = None
    output_data: dict[str, Any]
    confidence_score: float | None = None
    tokens_used: int | None = None
    cost_usd: float | None = None
    elapsed_ms: int | None = None
    status: str
    error_message: str | None = None
    created_at: datetime


# ============================================================================
# VettedMe Passport API Schemas (Phase 1 - Pure Passport Infrastructure)
# ============================================================================

class PassportCreate(BaseModel):
    """Schema for creating a new VettedMe Passport"""
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, min_length=10, max_length=20)
    date_of_birth: str | None = None
    biometric_data: dict[str, Any] | None = None


class BadgeResponse(BaseModel):
    """Schema for Badge response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    passport_id: UUID
    type: str
    credential_data: dict[str, Any]
    status: str
    issuer_signature: str
    issued_at: datetime
    expires_at: datetime | None = None
    verification_count: int


class PassportResponse(BaseModel):
    """Schema for Passport response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    user_id: UUID
    full_name: str
    email: str
    phone: str | None = None
    passport_number: str
    trust_score: int
    status: str
    issuer_signature: str
    issued_at: datetime
    expires_at: datetime | None = None
    badges: list[BadgeResponse] = Field(default_factory=list)
    verification_count: int
    last_verified_at: datetime | None = None


class BadgeIssueRequest(BaseModel):
    """Schema for issuing a new credential badge"""
    type: str = Field(min_length=2, max_length=100)
    credential_data: dict[str, Any]
    expires_at: datetime | None = None


class BadgeRevocationRequest(BaseModel):
    """Schema for revoking a badge"""
    reason: str = Field(min_length=5, max_length=500)


class VerificationRequest(BaseModel):
    """Schema for verifying a passport"""
    passport_id: str = Field(min_length=5, max_length=100)
    badge_type: str | None = None


class VerificationResponse(BaseModel):
    """Schema for verification result"""
    valid: bool
    passport_id: str
    full_name: str
    trust_score: int
    badges: list[BadgeResponse]
    verified_at: datetime
    signature_valid: bool
    warnings: list[str] = Field(default_factory=list)


class APIKeyCreateRequest(BaseModel):
    """Schema for creating API key"""
    name: str = Field(min_length=2, max_length=255)
    permissions: list[str] = Field(default_factory=lambda: ["verify"])


class APIKeyResponse(BaseModel):
    """Schema for API key response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    key_prefix: str
    permissions: list[str]
    active: bool
    created_at: datetime
    last_used_at: datetime | None = None
    # Only returned on creation:
    api_key: str | None = None


class VerificationLogResponse(BaseModel):
    """Schema for verification log entry"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    passport_id: UUID
    verifier_api_key_id: UUID
    verified_at: datetime
    ip_address: str | None = None
    user_agent: str | None = None
