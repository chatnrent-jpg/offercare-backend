-- Migration: V002__evolution_additions.sql
-- Description: Core schema additions for VettedMe.ai scale enhancements mapped to canonical public tables

BEGIN;

-- 1. Compliance Extensions: MBON Tracking & OHCQ Audit Logging
ALTER TABLE public.caregiver_profiles 
  ADD COLUMN IF NOT EXISTS mbon_license_number VARCHAR(64) UNIQUE,
  ADD COLUMN IF NOT EXISTS mbon_license_status VARCHAR(32) DEFAULT 'PENDING',
  ADD COLUMN IF NOT EXISTS mbon_last_verified_at TIMESTAMP WITH TIME ZONE,
  ADD COLUMN IF NOT EXISTS license_expires_at TIMESTAMP WITH TIME ZONE NULL;

CREATE TABLE IF NOT EXISTS public.ohcq_audit_ledgers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merkle_root_hash CHARACTER(64) NOT NULL,
    exported_by_user_id UUID NOT NULL,
    export_metadata JSONB NOT NULL,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    cryptographic_signature TEXT NOT NULL
);

-- 2. Multi-Facility Structure & Internal Float Pool Configuration
ALTER TABLE public.facilities 
  ADD COLUMN IF NOT EXISTS parent_organization_id UUID NULL,
  ADD COLUMN IF NOT EXISTS credit_score_status VARCHAR(32) DEFAULT 'GOOD',
  ADD COLUMN IF NOT EXISTS requires_deposit_on_file BOOLEAN DEFAULT FALSE;

ALTER TABLE public.ingested_open_shifts 
  ADD COLUMN IF NOT EXISTS internal_pool_only_until TIMESTAMP WITH TIME ZONE NULL,
  ADD COLUMN IF NOT EXISTS max_budget_hourly_rate NUMERIC(6, 2) NOT NULL DEFAULT 0.00,
  ADD COLUMN IF NOT EXISTS current_escalated_rate NUMERIC(6, 2) NOT NULL DEFAULT 0.00,
  ADD COLUMN IF NOT EXISTS last_price_escalation_at TIMESTAMP WITH TIME ZONE NULL;

-- 3. High-Performance Multi-Facility Overtime Validation Index
CREATE INDEX IF NOT EXISTS idx_shifts_facility_date_lookup 
ON public.ingested_open_shifts (facility_id, shift_date);

COMMIT;
