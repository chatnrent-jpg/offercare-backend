-- VettedMe.ai — Maryland LTC market expansion (reference SQL)
-- Segments: SNF · ALF · HHA  |  Clinicians: CNA · GNA · LPN
-- Integrates with scheduling spine: maryland_facilities · maryland_providers

-- ---------------------------------------------------------------------------
-- ENUM types (idempotent)
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'facility_type_enum') THEN
        CREATE TYPE facility_type_enum AS ENUM ('SNF', 'ALF', 'HHA');
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'facility_contact_role_enum') THEN
        CREATE TYPE facility_contact_role_enum AS ENUM (
            'ADMINISTRATOR',
            'DON',
            'HR_HEAD'
        );
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'outreach_status_enum') THEN
        CREATE TYPE outreach_status_enum AS ENUM (
            'PENDING',
            'READY',
            'CONTACTED',
            'RESPONDED',
            'OPT_OUT',
            'BOUNCED'
        );
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'md_credential_type_enum') THEN
        CREATE TYPE md_credential_type_enum AS ENUM ('CNA', 'GNA', 'LPN');
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'md_compliance_status_enum') THEN
        CREATE TYPE md_compliance_status_enum AS ENUM (
            'PENDING',
            'COMPLIANT',
            'NON_COMPLIANT',
            'EXPIRING',
            'REJECTED'
        );
    END IF;
END$$;

-- ---------------------------------------------------------------------------
-- Maryland licensed facility registry (OHCQ / Manus sourcing target list)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS facilities (
    facility_id         UUID PRIMARY KEY,
    company_name        VARCHAR(255) NOT NULL,
    facility_type       facility_type_enum NOT NULL,
    md_license_number   VARCHAR(64),
    md_license_status   VARCHAR(40) NOT NULL DEFAULT 'UNKNOWN',
    md_county           VARCHAR(100) NOT NULL,
    state               CHAR(2) NOT NULL DEFAULT 'MD',
    address_line        VARCHAR(255),
    city                VARCHAR(100),
    zip_code            VARCHAR(20),
    phone               VARCHAR(30),
    -- Optional bridge to existing scheduling / shift-matching spine
    maryland_facility_id UUID REFERENCES maryland_facilities(facility_id) ON DELETE SET NULL,
    source              VARCHAR(40) NOT NULL DEFAULT 'ohcq',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_facilities_md_license UNIQUE (md_license_number)
);

CREATE INDEX IF NOT EXISTS ix_facilities_md_county
    ON facilities (md_county);

CREATE INDEX IF NOT EXISTS ix_facilities_facility_type
    ON facilities (facility_type);

CREATE INDEX IF NOT EXISTS ix_facilities_maryland_facility_id
    ON facilities (maryland_facility_id)
    WHERE maryland_facility_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- B2B decision-maker profiles (Administrator · DON · HR Head)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS facility_contacts (
    contact_id          UUID PRIMARY KEY,
    facility_id         UUID NOT NULL REFERENCES facilities(facility_id) ON DELETE CASCADE,
    full_name           VARCHAR(255) NOT NULL,
    contact_role        facility_contact_role_enum NOT NULL,
    email               VARCHAR(255),
    phone               VARCHAR(30),
    outreach_status     outreach_status_enum NOT NULL DEFAULT 'PENDING',
    last_contacted_at   TIMESTAMPTZ,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_facility_contact_email UNIQUE (facility_id, email)
);

CREATE INDEX IF NOT EXISTS ix_facility_contacts_outreach_status
    ON facility_contacts (outreach_status);

CREATE INDEX IF NOT EXISTS ix_facility_contacts_role
    ON facility_contacts (contact_role);

CREATE INDEX IF NOT EXISTS ix_facility_contacts_facility_id
    ON facility_contacts (facility_id);

-- ---------------------------------------------------------------------------
-- Maryland provider compliance (MBON / GNA endorsement / regional matching)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS md_provider_compliance (
    compliance_id           UUID PRIMARY KEY,
    provider_id             UUID NOT NULL UNIQUE REFERENCES maryland_providers(provider_id) ON DELETE CASCADE,
    credential_type         md_credential_type_enum NOT NULL,
    license_number          VARCHAR(50) NOT NULL,
    has_gna_endorsement     BOOLEAN NOT NULL DEFAULT false,
    license_expires_on      TIMESTAMPTZ,
    compliance_status       md_compliance_status_enum NOT NULL DEFAULT 'PENDING',
    mbon_status_last_checked TIMESTAMPTZ,
    mbon_last_status        VARCHAR(40),
    ohcq_sanction_flag      BOOLEAN NOT NULL DEFAULT false,
    compact_multistate      BOOLEAN NOT NULL DEFAULT false,
    home_county             VARCHAR(100),
    verification_payload_json TEXT,
    rejection_reason        VARCHAR(500),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Regional lookahead shift matching: county + compliance status hot path
CREATE INDEX IF NOT EXISTS ix_md_provider_compliance_home_county
    ON md_provider_compliance (home_county);

CREATE INDEX IF NOT EXISTS ix_md_provider_compliance_status
    ON md_provider_compliance (compliance_status);

CREATE INDEX IF NOT EXISTS ix_md_provider_compliance_status_county
    ON md_provider_compliance (compliance_status, home_county);

CREATE INDEX IF NOT EXISTS ix_md_provider_compliance_credential_status
    ON md_provider_compliance (credential_type, compliance_status);

CREATE INDEX IF NOT EXISTS ix_md_provider_compliance_gna_flag
    ON md_provider_compliance (has_gna_endorsement)
    WHERE credential_type IN ('CNA', 'GNA');

-- ---------------------------------------------------------------------------
-- Cross-reference notes
-- ---------------------------------------------------------------------------
-- facilities.md_county           → regional HHA travel + county-based matching
-- facility_contacts              → Manus B2B outreach sequencer input
-- md_provider_compliance         → compliance/md_licensure_validator.py gate
-- maryland_facilities (existing) → offer broadcast + ingested_open_shifts FK spine
