-- VettedPay Privacy-Compliant Database Schema
-- Logs transaction lifecycle without storing raw bank accounts or identity payloads.
-- Extends existing PostgreSQL foundation for multi-rail payment orchestration.

-- Enums for tracking decoupled transaction states safely
CREATE TYPE payment_rail AS ENUM ('airwallex', 'nium', 'wise', 'stablecoin_usdc', 'fallback_mock');
CREATE TYPE transaction_status AS ENUM ('initiated', 'zk_verified', 'dispatched_to_rail', 'settled', 'failed', 'cancelled');

-- Core Transaction Ledger Table
-- Never stores raw bank accounts, SSNs, or unencrypted PII
CREATE TABLE IF NOT EXISTS vettedpay_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key VARCHAR(64) UNIQUE NOT NULL,
    sender_did VARCHAR(255) NOT NULL,
    recipient_did VARCHAR(255) NOT NULL,
    amount NUMERIC(14, 4) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    active_rail payment_rail NOT NULL,
    status transaction_status NOT NULL DEFAULT 'initiated',
    rail_transaction_id VARCHAR(255) DEFAULT NULL,
    zk_proof_verified BOOLEAN DEFAULT FALSE,
    compliance_packet_id VARCHAR(255) DEFAULT NULL,
    error_log TEXT DEFAULT NULL,
    metadata JSONB DEFAULT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexing for rapid dashboard lookup performance
CREATE INDEX idx_transactions_sender ON vettedpay_transactions(sender_did);
CREATE INDEX idx_transactions_recipient ON vettedpay_transactions(recipient_did);
CREATE INDEX idx_transactions_idempotency ON vettedpay_transactions(idempotency_key);
CREATE INDEX idx_transactions_status ON vettedpay_transactions(status);
CREATE INDEX idx_transactions_rail ON vettedpay_transactions(active_rail);
CREATE INDEX idx_transactions_created ON vettedpay_transactions(created_at DESC);

-- Rail Health Monitoring Table
-- Tracks availability and performance of each payment rail
CREATE TABLE IF NOT EXISTS vettedpay_rail_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rail payment_rail UNIQUE NOT NULL,
    is_healthy BOOLEAN DEFAULT TRUE,
    last_success_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    last_failure_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    failure_count INTEGER DEFAULT 0,
    circuit_status VARCHAR(20) DEFAULT 'CLOSED',
    error_message TEXT DEFAULT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ZK-Proof Verification Log
-- Audit trail of zero-knowledge proof verifications
-- Does NOT store the actual proof (too large), only verification results
CREATE TABLE IF NOT EXISTS vettedpay_zk_verifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID REFERENCES vettedpay_transactions(id) ON DELETE CASCADE,
    sender_did VARCHAR(255) NOT NULL,
    proof_type VARCHAR(50) NOT NULL,
    verification_result BOOLEAN NOT NULL,
    verification_method VARCHAR(100) NOT NULL,
    proof_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    verified_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_zk_verifications_transaction ON vettedpay_zk_verifications(transaction_id);
CREATE INDEX idx_zk_verifications_sender ON vettedpay_zk_verifications(sender_did);

-- Waitlist Table for Landing Page
-- Captures early adopters before full launch
CREATE TABLE IF NOT EXISTS vettedpay_waitlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) DEFAULT NULL,
    organization VARCHAR(255) DEFAULT NULL,
    use_case TEXT DEFAULT NULL,
    referral_source VARCHAR(100) DEFAULT NULL,
    priority_score INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending',
    invited_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_waitlist_email ON vettedpay_waitlist(email);
CREATE INDEX idx_waitlist_status ON vettedpay_waitlist(status);
CREATE INDEX idx_waitlist_priority ON vettedpay_waitlist(priority_score DESC);

-- Automated Timestamp Trigger to keep update states highly accurate
CREATE OR REPLACE FUNCTION update_vettedpay_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_vettedpay_transactions_timestamp
    BEFORE UPDATE ON vettedpay_transactions
    FOR EACH ROW
    EXECUTE FUNCTION update_vettedpay_timestamp();

CREATE TRIGGER trigger_update_vettedpay_rail_health_timestamp
    BEFORE UPDATE ON vettedpay_rail_health
    FOR EACH ROW
    EXECUTE FUNCTION update_vettedpay_timestamp();

-- Insert default rail health records
INSERT INTO vettedpay_rail_health (rail, is_healthy, circuit_status)
VALUES 
    ('airwallex', TRUE, 'CLOSED'),
    ('nium', TRUE, 'CLOSED'),
    ('wise', TRUE, 'CLOSED'),
    ('stablecoin_usdc', TRUE, 'CLOSED'),
    ('fallback_mock', TRUE, 'CLOSED')
ON CONFLICT (rail) DO NOTHING;

-- Grant permissions (adjust role names as needed)
-- GRANT SELECT, INSERT, UPDATE ON vettedpay_transactions TO vettedpay_app;
-- GRANT SELECT, INSERT, UPDATE ON vettedpay_rail_health TO vettedpay_app;
-- GRANT SELECT, INSERT, UPDATE ON vettedpay_zk_verifications TO vettedpay_app;
-- GRANT SELECT, INSERT, UPDATE ON vettedpay_waitlist TO vettedpay_app;

COMMENT ON TABLE vettedpay_transactions IS 'Core transaction ledger - never stores raw bank accounts or unencrypted PII';
COMMENT ON TABLE vettedpay_rail_health IS 'Payment rail health monitoring and circuit breaker state';
COMMENT ON TABLE vettedpay_zk_verifications IS 'Audit trail of ZK-proof verifications';
COMMENT ON TABLE vettedpay_waitlist IS 'Early adopter waitlist for VettedPay launch';

COMMENT ON COLUMN vettedpay_transactions.sender_did IS 'Decentralized identifier - not a real name or SSN';
COMMENT ON COLUMN vettedpay_transactions.compliance_packet_id IS 'Reference to encrypted compliance packet (stored separately)';
COMMENT ON COLUMN vettedpay_transactions.zk_proof_verified IS 'Whether zero-knowledge proof passed verification';
