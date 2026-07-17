-- ============================================================================
-- VettedMe zkTLS Platform - Database Schema
-- Phase 1: Free Badges (LinkedIn + Healthcare)
-- Phase 2: B2B Developer API with Stripe Billing
-- ============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- Core User Tables
-- ============================================================================

-- Users: Core authentication and profile
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    username VARCHAR(50) UNIQUE, -- For public profile URLs (vettedme.ai/@username)
    profile_image_url TEXT,
    stripe_customer_id VARCHAR(255), -- Phase 2: Stripe integration
    is_email_verified BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_stripe ON users(stripe_customer_id);

-- ============================================================================
-- Developer API Tables (Phase 2)
-- ============================================================================

-- Developer Profiles: API key management and rate limiting
CREATE TABLE developer_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    api_key_prefix VARCHAR(20) NOT NULL, -- First 8 chars for display (e.g., "sk_live_abc123...")
    api_key_hash VARCHAR(64) UNIQUE NOT NULL, -- SHA256 hash of full API key
    api_key_name VARCHAR(100), -- User-defined name for the key
    rate_limit_rpm INT DEFAULT 60, -- Requests per minute
    rate_limit_daily INT DEFAULT 10000, -- Daily request limit
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE -- Optional expiration
);

CREATE INDEX idx_dev_profiles_user ON developer_profiles(user_id);
CREATE INDEX idx_dev_profiles_key_hash ON developer_profiles(api_key_hash);
CREATE INDEX idx_dev_profiles_active ON developer_profiles(is_active);

-- ============================================================================
-- Credential Badge Tables (Phase 1)
-- ============================================================================

-- Credentials: Issued zkTLS badges and proofs
CREATE TABLE credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    
    -- Provider Information
    provider_type VARCHAR(50) NOT NULL, -- 'LINKEDIN', 'MBON_HEALTHCARE', 'UBER', 'STRIPE'
    reclaim_provider_id VARCHAR(100) NOT NULL, -- Reclaim Protocol provider ID
    
    -- Proof Data
    proof_data JSONB NOT NULL, -- Full zkTLS proof from Reclaim Protocol
    proof_hash VARCHAR(64) NOT NULL, -- SHA256 hash for verification
    
    -- Extracted Claims (for display)
    claims JSONB, -- Extracted user-readable claims (e.g., {"account_age": "5 years", "connections": "500+"})
    
    -- Verification Status
    is_valid BOOLEAN DEFAULT TRUE,
    verified_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE, -- Some credentials expire (e.g., nursing licenses)
    revoked_at TIMESTAMP WITH TIME ZONE, -- User can revoke badges
    
    -- Visibility
    is_public BOOLEAN DEFAULT TRUE, -- Show on public profile?
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_credentials_user ON credentials(user_id);
CREATE INDEX idx_credentials_provider ON credentials(provider_type);
CREATE INDEX idx_credentials_valid ON credentials(is_valid);
CREATE INDEX idx_credentials_public ON credentials(is_public);
CREATE INDEX idx_credentials_hash ON credentials(proof_hash);

-- ============================================================================
-- API Usage Tables (Phase 2)
-- ============================================================================

-- Usage Logs: Track API calls for metered billing
CREATE TABLE usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    developer_id UUID REFERENCES developer_profiles(id) ON DELETE SET NULL,
    
    -- Request Information
    endpoint VARCHAR(100) NOT NULL, -- e.g., '/api/v1/verify/linkedin'
    method VARCHAR(10) NOT NULL, -- GET, POST, etc.
    status_code INT NOT NULL,
    response_time_ms INT, -- Response time in milliseconds
    
    -- Billing
    is_billable BOOLEAN DEFAULT TRUE, -- Some calls are free (e.g., errors)
    cost_cents INT DEFAULT 10, -- $0.10 = 10 cents
    
    -- Metadata
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_usage_logs_dev ON usage_logs(developer_id);
CREATE INDEX idx_usage_logs_created ON usage_logs(created_at);
CREATE INDEX idx_usage_logs_billable ON usage_logs(is_billable);

-- ============================================================================
-- Billing Tables (Phase 2)
-- ============================================================================

-- Billing Periods: Monthly billing cycles
CREATE TABLE billing_periods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    developer_id UUID REFERENCES developer_profiles(id) ON DELETE CASCADE,
    
    -- Period
    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Usage
    total_requests INT DEFAULT 0,
    billable_requests INT DEFAULT 0,
    
    -- Billing
    amount_cents INT DEFAULT 0, -- Total amount in cents
    stripe_invoice_id VARCHAR(255), -- Stripe invoice ID
    paid_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_billing_periods_dev ON billing_periods(developer_id);
CREATE INDEX idx_billing_periods_dates ON billing_periods(period_start, period_end);

-- ============================================================================
-- Public Profile Tables (Phase 1)
-- ============================================================================

-- Public Profiles: Shareable badge portfolios
CREATE TABLE public_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    
    -- Display Settings
    display_name VARCHAR(255),
    bio TEXT,
    website_url TEXT,
    twitter_handle VARCHAR(50),
    linkedin_url TEXT,
    
    -- Badge Display Order
    badge_order JSONB, -- Array of credential IDs in display order
    
    -- Visibility
    is_public BOOLEAN DEFAULT TRUE,
    
    -- Metadata
    view_count INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_public_profiles_user ON public_profiles(user_id);
CREATE INDEX idx_public_profiles_public ON public_profiles(is_public);

-- ============================================================================
-- Reclaim Protocol Session Tracking (Phase 1)
-- ============================================================================

-- Reclaim Sessions: Track ongoing proof generation sessions
CREATE TABLE reclaim_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    
    -- Reclaim Data
    reclaim_session_id VARCHAR(255) NOT NULL,
    provider_type VARCHAR(50) NOT NULL,
    
    -- Status
    status VARCHAR(50) DEFAULT 'PENDING', -- PENDING, IN_PROGRESS, COMPLETED, FAILED
    callback_url TEXT, -- URL to redirect user after proof
    
    -- Result
    proof_data JSONB, -- Stored after completion
    error_message TEXT,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_reclaim_sessions_user ON reclaim_sessions(user_id);
CREATE INDEX idx_reclaim_sessions_status ON reclaim_sessions(status);
CREATE INDEX idx_reclaim_sessions_reclaim_id ON reclaim_sessions(reclaim_session_id);

-- ============================================================================
-- Analytics Tables (Future)
-- ============================================================================

-- Badge Views: Track badge impressions
CREATE TABLE badge_views (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    credential_id UUID REFERENCES credentials(id) ON DELETE CASCADE,
    viewer_ip INET,
    viewer_country VARCHAR(2), -- ISO country code
    referrer TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_badge_views_credential ON badge_views(credential_id);
CREATE INDEX idx_badge_views_created ON badge_views(created_at);

-- ============================================================================
-- Updated_at Trigger Function
-- ============================================================================

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to tables with updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_credentials_updated_at BEFORE UPDATE ON credentials
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_public_profiles_updated_at BEFORE UPDATE ON public_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

-- Composite indexes for common queries
CREATE INDEX idx_credentials_user_provider ON credentials(user_id, provider_type);
CREATE INDEX idx_credentials_user_valid ON credentials(user_id, is_valid);
CREATE INDEX idx_usage_logs_dev_created ON usage_logs(developer_id, created_at);

-- ============================================================================
-- Comments for Documentation
-- ============================================================================

COMMENT ON TABLE users IS 'Core user accounts with authentication and Stripe integration';
COMMENT ON TABLE developer_profiles IS 'Developer API keys and rate limiting configuration';
COMMENT ON TABLE credentials IS 'zkTLS credential badges issued via Reclaim Protocol';
COMMENT ON TABLE usage_logs IS 'API usage tracking for metered billing';
COMMENT ON TABLE billing_periods IS 'Monthly billing cycles and Stripe invoices';
COMMENT ON TABLE public_profiles IS 'Public shareable badge portfolios';
COMMENT ON TABLE reclaim_sessions IS 'Track ongoing Reclaim Protocol proof generation';
COMMENT ON TABLE badge_views IS 'Analytics for badge impressions';
