-- VettedMe.ai — Facility Recruitment & Contract Sourcing Engine
-- Standalone reference SQL (Alembic head: 014_facility_recruitment)

CREATE TABLE IF NOT EXISTS facility_contracts (
    contract_id UUID PRIMARY KEY,
    facility_id UUID NOT NULL REFERENCES maryland_facilities(facility_id),
    external_contract_id VARCHAR(120) NOT NULL,
    vms_source VARCHAR(50) NOT NULL DEFAULT 'MSA_UPLOAD',
    contract_name VARCHAR(255),
    source_filename VARCHAR(255),
    bill_rate_hourly NUMERIC(8, 2),
    pay_rate_hourly NUMERIC(8, 2),
    margin_dollars NUMERIC(8, 2),
    margin_pct NUMERIC(6, 4),
    cancellation_policy_text TEXT,
    cancellation_notice_hours NUMERIC(5, 0),
    credential_requirements_json TEXT,
    review_status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
    dispatch_halted VARCHAR(5) NOT NULL DEFAULT 'false',
    review_reason VARCHAR(500),
    raw_text_excerpt TEXT,
    parsed_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_facility_contract_external UNIQUE (facility_id, external_contract_id)
);

CREATE INDEX IF NOT EXISTS ix_facility_contracts_facility_id ON facility_contracts (facility_id);
CREATE INDEX IF NOT EXISTS ix_facility_contracts_review_status ON facility_contracts (review_status);

CREATE TABLE IF NOT EXISTS b2b_raw_leads (
    lead_id UUID PRIMARY KEY,
    facility_name VARCHAR(255) NOT NULL,
    contact_role VARCHAR(120) NOT NULL,
    email_domain VARCHAR(255) NOT NULL,
    procurement_urgency VARCHAR(50) NOT NULL,
    source_url VARCHAR(500) NOT NULL,
    contact_name VARCHAR(255),
    contact_email VARCHAR(255),
    state VARCHAR(2) NOT NULL DEFAULT 'MD',
    county VARCHAR(100),
    notes TEXT,
    manus_run_id VARCHAR(128),
    source VARCHAR(30) NOT NULL DEFAULT 'manus',
    imported_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_b2b_raw_leads_facility ON b2b_raw_leads (facility_name);
CREATE INDEX IF NOT EXISTS ix_b2b_raw_leads_urgency ON b2b_raw_leads (procurement_urgency);

CREATE TABLE IF NOT EXISTS ingested_open_shifts (
    ingest_id UUID PRIMARY KEY,
    composite_hash VARCHAR(64) NOT NULL UNIQUE,
    facility_id UUID NOT NULL REFERENCES maryland_facilities(facility_id),
    offer_id UUID REFERENCES offercare_job_offers(offer_id),
    source VARCHAR(30) NOT NULL DEFAULT 'manus_vms',
    shift_date VARCHAR(20) NOT NULL,
    unit_dept VARCHAR(120) NOT NULL,
    start_time VARCHAR(20) NOT NULL,
    shift_role VARCHAR(100) NOT NULL,
    hourly_pay_rate NUMERIC(8, 2) NOT NULL,
    payload_json TEXT,
    match_payload_json TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'INGESTED',
    ingested_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_ingested_open_shifts_facility ON ingested_open_shifts (facility_id);

-- Links recruitment engine to scheduling + compliance spine:
--   facility_contracts.facility_id -> maryland_facilities (master facility)
--   ingested_open_shifts.offer_id -> offercare_job_offers (scheduling broadcast)
--   ingested_open_shifts.facility_id -> facility_crisis_signals / outreach pipeline
--   Contract credential_requirements_json gates lookahead_shift_matcher against
--   clinician_compliance_documents + vetted_status on maryland_providers.
