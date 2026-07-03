from pathlib import Path

from pydantic_settings import BaseSettings

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    DATABASE_URL: str
    PROJECT_NAME: str

    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""
    SMS_DRY_RUN: bool = True
    PUBLIC_BASE_URL: str = ""

    SNIPER_WEIGHT_COMPLIANCE: float = 100.0
    SNIPER_WEIGHT_RATE_DELTA: float = 10.0
    SNIPER_WEIGHT_RESPONSE_PROPENSITY: float = 25.0
    SNIPER_WEIGHT_FATIGUE: float = 5.0
    PLACEMENT_P_MAX: float = 0.95
    PLACEMENT_DECAY_LAMBDA: float = 0.35
    TWILIO_REPLY_KEYWORD: str = "YES"

    MARYLAND_HOSPITALS_API_URL: str = (
        "https://opendata.maryland.gov/resource/c4hm-nhk7.json"
    )
    PA_HOSPITALS_API_URL: str = (
        "https://mapservices.pasda.psu.edu/server/rest/services/pasda/DepHealth/MapServer/6/query"
    )
    DE_HOSPITALS_API_URL: str = (
        "https://data.cms.gov/provider-data/api/1/datastore/query/xubh-q36u/0"
    )
    CMS_HOSPITALS_API_URL: str = (
        "https://data.cms.gov/provider-data/api/1/datastore/query/xubh-q36u/0"
    )
    CMS_NURSING_HOMES_API_URL: str = (
        "https://data.cms.gov/provider-data/api/1/datastore/query/4pq5-n9py/0"
    )
    CMS_HOME_HEALTH_API_URL: str = (
        "https://data.cms.gov/provider-data/api/1/datastore/query/6jpm-sxkc/0"
    )
    NJ_HOSPITALS_API_URL: str = (
        "https://data.cms.gov/provider-data/api/1/datastore/query/xubh-q36u/0"
    )
    FACILITY_SCRAPE_SOURCE: str = "MD_OPENDATA"
    SUPPORTED_STATES: str = "MD,VA,DC,PA,DE,NJ"
    LICENSE_VERIFY_DRY_RUN: bool = True

    MBON_VERIFY_DRY_RUN: bool = True
    MBON_VERIFY_URL: str = ""
    MBON_VERIFY_TIMEOUT_SECONDS: float = 20.0

    OIG_SCREEN_DRY_RUN: bool = True
    OIG_LEIE_SEARCH_URL: str = ""
    OIG_SCREEN_TIMEOUT_SECONDS: float = 20.0

    MD_JUDICIARY_DRY_RUN: bool = True
    MD_JUDICIARY_SEARCH_URL: str = ""
    MD_JUDICIARY_TIMEOUT_SECONDS: float = 20.0

    GEO_MATCH_RADIUS_MILES: float = 30.0
    GEO_MATCH_USE_POSTGIS: bool = True

    STAFFING_VMS_WORKER_ENABLED: bool = True
    STAFFING_VMS_WORKER_INTERVAL_SECONDS: int = 900
    STAFFING_JOB_BOARD_WORKER_ENABLED: bool = True
    STAFFING_JOB_BOARD_WORKER_INTERVAL_SECONDS: int = 86400

    COMPLIANCE_MONITOR_WORKER_ENABLED: bool = True
    COMPLIANCE_MONITOR_WORKER_INTERVAL_SECONDS: int = 3600

    LIVE_SCRAPER_GATEWAY_BASE_URL: str = ""
    LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED: bool = False

    COMPLIANCE_ALERT_DAYS: int = 14
    CREDENTIALING_AUTO_SCREEN_ON_APPLY: bool = False

    VMS_INGEST_DRY_RUN: bool = True
    VMS_INGEST_URL: str = ""
    VMS_INGEST_TIMEOUT_SECONDS: float = 25.0
    VMS_INGEST_PLAYWRIGHT_ENABLED: bool = False
    VMS_INGEST_PORTAL_URL: str = ""
    VMS_INGEST_PORTAL_USER: str = ""
    VMS_INGEST_PORTAL_PASSWORD: str = ""
    VMS_INGEST_PLAYWRIGHT_TIMEOUT_SECONDS: float = 45.0
    VMS_INGEST_PORTAL_USER_SELECTOR: str = "input[name='username']"
    VMS_INGEST_PORTAL_PASSWORD_SELECTOR: str = "input[name='password']"
    VMS_INGEST_PORTAL_SUBMIT_SELECTOR: str = "button[type='submit']"
    VMS_INGEST_PORTAL_SHIFTS_SELECTOR: str = "#vms-open-shifts-json"

    JOB_BOARD_SCRAPE_DRY_RUN: bool = True
    JOB_BOARD_SCRAPE_URL: str = ""
    JOB_BOARD_SCRAPE_TIMEOUT_SECONDS: float = 25.0
    JOB_BOARD_CRISIS_MIN_DAYS: int = 30

    CONTACT_ENRICH_DRY_RUN: bool = True
    APOLLO_SEARCH_URL: str = ""
    APOLLO_API_KEY: str = ""
    ZOOMINFO_SEARCH_URL: str = ""
    ZOOMINFO_API_KEY: str = ""
    CONTACT_ENRICH_TIMEOUT_SECONDS: float = 20.0

    CLAY_TABLE_WEBHOOK_URL: str = ""
    CLAY_TABLE_ID: str = ""
    CLAY_TABLE_VIEW_ID: str = ""
    CLAY_SESSION_COOKIE: str = ""
    CLAY_ENRICHMENT_DRY_RUN: bool = True

    HEYREACH_API_KEY: str = ""
    HEYREACH_LIST_ID: str = ""
    HEYREACH_CAMPAIGN_ID: str = ""
    HEYREACH_SENDER_ACCOUNT_IDS: str = ""
    HEYREACH_OUTREACH_DRY_RUN: bool = True

    WORKSTREAM_API_BASE: str = "https://public-api.workstream.us"
    WORKSTREAM_CLIENT_ID: str = ""
    WORKSTREAM_CLIENT_SECRET: str = ""
    WORKSTREAM_ACCESS_TOKEN: str = ""
    WORKSTREAM_WEBHOOK_BEARER_TOKEN: str = ""
    WORKSTREAM_JOB_DISTRIBUTION_DRY_RUN: bool = True

    OUTREACH_EMAIL_ENABLED: bool = True
    OUTREACH_EMAIL_DRY_RUN: bool = True
    OUTREACH_LLM_DRY_RUN: bool = True
    OUTREACH_LLM_URL: str = ""
    OUTREACH_LLM_API_KEY: str = ""
    OUTREACH_LLM_MODEL: str = "gpt-4o-mini"
    OUTREACH_LLM_TIMEOUT_SECONDS: float = 30.0
    OUTREACH_SENDER_NAME: str = "Henry Okojie"
    OUTREACH_AGENCY_NAME: str = "VettedCare.ai"

    JWT_SECRET_KEY: str = "offercare-dev-secret-change-in-production"
    JWT_EXPIRE_MINUTES: int = 60 * 24

    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: str = ""
    FACEBOOK_APP_ID: str = ""
    FACEBOOK_APP_SECRET: str = ""
    PORTAL_OAUTH_REDIRECT_BASE: str = ""

    VMS_SUBMISSION_URL: str = ""
    VMS_DRY_RUN: bool = True
    VMS_SUBMISSION_TIMEOUT_SECONDS: float = 20.0
    VMS_AUTH_HEADER: str = "Authorization"
    VMS_AUTH_TOKEN: str = ""

    ADMIN_API_KEY: str = ""
    MANUS_API_KEY: str = ""
    MANUS_WORK_QUEUE_DEFAULT_LIMIT: int = 25
    MANUS_STALE_CLEAR_DAYS: int = 30
    MANUS_MIN_RERUN_HOURS: int = 24
    VETTED_ALERTS_ENABLED: bool = True
    VETTED_ADMIN_ALERT_EMAIL: str = ""
    VETTED_TAGLINE: str = "AI credential verification — safety before placement"
    TWILIO_VALIDATE_SIGNATURES: bool = False

    EMAIL_ALERTS_ENABLED: bool = True
    EMAIL_DRY_RUN: bool = True
    EMAIL_FROM: str = "alerts@offercare.ai"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True

    PUSH_ALERTS_ENABLED: bool = True
    PUSH_DRY_RUN: bool = True
    MATCHED_SHIFT_PUSH_ON_AUTO_CREATE: bool = True
    UNIFIED_MATCH_MATRIX_BROKER_ENABLED: bool = True
    SCHEDULE_FATIGUE_CAP_ENABLED: bool = True
    SCHEDULE_FATIGUE_SOFT_WARN_THRESHOLD: float = 2.5
    SCHEDULE_FATIGUE_HARD_BLOCK_THRESHOLD: float = 4.0
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = "mailto:alerts@offercare.ai"

    SNIPER_LEARNING_ENABLED: bool = True
    SNIPER_FATIGUE_WINDOW_HOURS: int = 24
    SNIPER_FATIGUE_PER_SMS: float = 0.25
    SNIPER_FATIGUE_MAX: float = 5.0
    SNIPER_PROPENSITY_PRIOR: float = 0.5
    SNIPER_PROPENSITY_PRIOR_WEIGHT: float = 2.0

    SNIPER_CASCADE_ENABLED: bool = True
    SNIPER_CASCADE_TIMEOUT_SECONDS: int = 90
    SNIPER_CASCADE_MAX_RECIPIENTS: int = 5
    SNIPER_CASCADE_WORKER_ENABLED: bool = True
    SNIPER_CASCADE_WORKER_INTERVAL_SECONDS: int = 15

    OPS_AUDIT_ENABLED: bool = True

    MD_MONTGOMERY_SNF_CNA_LIVE_DISPATCH: bool = True

    SEMANTIC_EMBEDDING_MODEL: str = "text-embedding-3-small"
    SEMANTIC_EMBEDDING_DIMENSIONS: int = 1536

    STRIPE_SECRET_KEY: str = ""
    STRIPE_INSTANT_PAYOUT_DRY_RUN: bool = True
    INSTANT_PAY_WINDOW_MINUTES: int = 30
    INSTANT_PAY_WORKER_ENABLED: bool = True
    INSTANT_PAY_WORKER_INTERVAL_SECONDS: int = 60

    PAYROLL_TAX_INTERCEPT_ENABLED: bool = True
    PAYROLL_TAX_PROVIDER: str = "local"  # local | gusto | checkhq
    INSTANT_PAY_FEDERAL_INCOME_EFFECTIVE_RATE: float = 0.12
    INSTANT_PAY_MD_STATE_EFFECTIVE_RATE: float = 0.0575
    GUSTO_API_TOKEN: str = ""
    GUSTO_COMPANY_ID: str = ""
    GUSTO_API_BASE: str = "https://api.gusto-demo.com"
    GUSTO_API_VERSION: str = "2024-04-01"
    CHECKHQ_API_KEY: str = ""
    CHECKHQ_API_BASE: str = "https://sandbox.checkhq.com"
    CHECKHQ_COMPANY_ID: str = ""
    CHECKHQ_DEFAULT_WORKPLACE_ID: str = ""

    PAYROLL_ONBOARDING_SYNC_ENABLED: bool = True
    PAYROLL_ONBOARDING_DRY_RUN: bool = True
    PAYROLL_ONBOARDING_TIMEOUT_SECONDS: float = 30.0

    COMPLIANCE_SENTINEL_ENABLED: bool = True
    COMPLIANCE_SENTINEL_HB1106_REQUIRED: bool = True
    COMPLIANCE_SENTINEL_MBON_MAX_AGE_HOURS: int = 24

    BIAS_AUDITOR_ENABLED: bool = True
    BIAS_AUDITOR_DRY_RUN: bool = True
    BIAS_AUDITOR_LLM_MODEL: str = "claude-3-5-sonnet-20241022"
    BIAS_AUDITOR_ANTHROPIC_API_KEY: str = ""
    BIAS_AUDITOR_LLM_TIMEOUT_SECONDS: float = 30.0
    BIAS_AUDITOR_LOG_PATH: str = "maryland_hb1106_audit.log"

    SKYFLOW_VAULT_ENABLED: bool = True
    SKYFLOW_VAULT_DRY_RUN: bool = True
    SKYFLOW_VAULT_ID: str = ""
    SKYFLOW_VAULT_URL: str = ""
    SKYFLOW_VAULT_TABLE: str = "caregivers"
    SKYFLOW_BEARER_TOKEN: str = ""
    SKYFLOW_VAULT_TIMEOUT_SECONDS: float = 30.0
    SKYFLOW_DRY_VAULT_PATH: str = "logs/skyflow_dry_vault.json"

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 10
    RATE_LIMIT_APPLY_PER_MINUTE: int = 5
    RATE_LIMIT_TWILIO_PER_MINUTE: int = 60
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 120

    SECURITY_HEADERS_ENABLED: bool = True
    LOG_LEVEL: str = "INFO"
    SHIFT_CALENDAR_DURATION_HOURS: float = 12.0

    # Facility recruitment / contract engine
    CONTRACT_MIN_MARGIN_PCT: float = 0.18
    CONTRACT_BASELINE_MIN_PAY_RATE: float = 28.0

    # Maryland LTC regional bill-rate floors (MSA margin gate)
    MD_LPN_MIN_BILL_RATE: float = 38.0
    MD_CNA_MIN_BILL_RATE: float = 28.0
    MD_GNA_MIN_BILL_RATE: float = 30.0
    MD_LPN_MIN_MARGIN_PCT: float = 0.18
    MD_CNA_MIN_MARGIN_PCT: float = 0.16
    MD_GNA_MIN_MARGIN_PCT: float = 0.16
    MD_MBON_RECHECK_STALE_DAYS: int = 7

    B2B_INVOICING_ENABLED: bool = True
    B2B_INVOICE_MARGIN_PCT: float = 0.40

    class Config:
        env_file = str(_ENV_FILE)
        extra = "ignore"

    @property
    def twilio_configured(self) -> bool:
        return bool(self.TWILIO_ACCOUNT_SID and self.TWILIO_AUTH_TOKEN and self.TWILIO_FROM_NUMBER)

    @property
    def admin_auth_enforced(self) -> bool:
        return bool(str(self.ADMIN_API_KEY or "").strip())

    @property
    def vms_configured(self) -> bool:
        return bool(str(self.VMS_SUBMISSION_URL or "").strip())

    @property
    def email_configured(self) -> bool:
        return bool(str(self.SMTP_HOST or "").strip() and str(self.EMAIL_FROM or "").strip())

    @property
    def push_configured(self) -> bool:
        return bool(str(self.VAPID_PUBLIC_KEY or "").strip() and str(self.VAPID_PRIVATE_KEY or "").strip())


settings = Settings()
