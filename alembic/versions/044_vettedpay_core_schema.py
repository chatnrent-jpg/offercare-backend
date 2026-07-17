"""VettedPay core transaction schema

Revision ID: 044_vettedpay_core_schema
Revises: 043_vettedpay_payouts
Create Date: 2026-07-17 09:30:00.000000

Privacy-compliant database schema for VettedPay transactions.
Never stores raw bank accounts, SSNs, or unencrypted PII.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM

# revision identifiers, used by Alembic.
revision: str = '044_vettedpay_core_schema'
down_revision: Union[str, None] = '043_vettedpay_payouts'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create custom ENUM types
    payment_rail_enum = ENUM(
        'airwallex', 'nium', 'wise', 'stablecoin_usdc', 'fallback_mock',
        name='payment_rail',
        create_type=True
    )
    
    transaction_status_enum = ENUM(
        'initiated', 'zk_verified', 'dispatched_to_rail', 'settled', 'failed', 'cancelled',
        name='transaction_status',
        create_type=True
    )
    
    # Create payment_rail and transaction_status types
    payment_rail_enum.create(op.get_bind(), checkfirst=True)
    transaction_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Core Transaction Ledger Table
    op.create_table(
        'vettedpay_transactions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('idempotency_key', sa.String(64), nullable=False, unique=True),
        sa.Column('sender_did', sa.String(255), nullable=False),
        sa.Column('recipient_did', sa.String(255), nullable=False),
        sa.Column('amount', sa.Numeric(14, 4), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('active_rail', payment_rail_enum, nullable=False),
        sa.Column('status', transaction_status_enum, nullable=False, server_default='initiated'),
        sa.Column('rail_transaction_id', sa.String(255), nullable=True),
        sa.Column('zk_proof_verified', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('compliance_packet_id', sa.String(255), nullable=True),
        sa.Column('error_log', sa.Text, nullable=True),
        sa.Column('metadata', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    
    # Indexes for vettedpay_transactions
    op.create_index('idx_transactions_sender', 'vettedpay_transactions', ['sender_did'])
    op.create_index('idx_transactions_recipient', 'vettedpay_transactions', ['recipient_did'])
    op.create_index('idx_transactions_idempotency', 'vettedpay_transactions', ['idempotency_key'])
    op.create_index('idx_transactions_status', 'vettedpay_transactions', ['status'])
    op.create_index('idx_transactions_rail', 'vettedpay_transactions', ['active_rail'])
    op.create_index('idx_transactions_created', 'vettedpay_transactions', [sa.text('created_at DESC')])
    
    # Rail Health Monitoring Table
    op.create_table(
        'vettedpay_rail_health',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('rail', payment_rail_enum, nullable=False, unique=True),
        sa.Column('is_healthy', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_failure_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failure_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('circuit_status', sa.String(20), nullable=False, server_default='CLOSED'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    
    # ZK-Proof Verification Log
    op.create_table(
        'vettedpay_zk_verifications',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('transaction_id', UUID(as_uuid=True), nullable=False),
        sa.Column('sender_did', sa.String(255), nullable=False),
        sa.Column('proof_type', sa.String(50), nullable=False),
        sa.Column('verification_result', sa.Boolean, nullable=False),
        sa.Column('verification_method', sa.String(100), nullable=False),
        sa.Column('proof_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('verified_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['transaction_id'], ['vettedpay_transactions.id'], ondelete='CASCADE'),
    )
    
    op.create_index('idx_zk_verifications_transaction', 'vettedpay_zk_verifications', ['transaction_id'])
    op.create_index('idx_zk_verifications_sender', 'vettedpay_zk_verifications', ['sender_did'])
    
    # Waitlist Table for Landing Page
    op.create_table(
        'vettedpay_waitlist',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('organization', sa.String(255), nullable=True),
        sa.Column('use_case', sa.Text, nullable=True),
        sa.Column('referral_source', sa.String(100), nullable=True),
        sa.Column('priority_score', sa.Integer, nullable=False, server_default='0'),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('invited_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    
    op.create_index('idx_waitlist_email', 'vettedpay_waitlist', ['email'])
    op.create_index('idx_waitlist_status', 'vettedpay_waitlist', ['status'])
    op.create_index('idx_waitlist_priority', 'vettedpay_waitlist', [sa.text('priority_score DESC')])
    
    # Create update timestamp function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_vettedpay_timestamp()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create triggers
    op.execute("""
        CREATE TRIGGER trigger_update_vettedpay_transactions_timestamp
            BEFORE UPDATE ON vettedpay_transactions
            FOR EACH ROW
            EXECUTE FUNCTION update_vettedpay_timestamp();
    """)
    
    op.execute("""
        CREATE TRIGGER trigger_update_vettedpay_rail_health_timestamp
            BEFORE UPDATE ON vettedpay_rail_health
            FOR EACH ROW
            EXECUTE FUNCTION update_vettedpay_timestamp();
    """)
    
    # Insert default rail health records
    op.execute("""
        INSERT INTO vettedpay_rail_health (rail, is_healthy, circuit_status)
        VALUES 
            ('airwallex', TRUE, 'CLOSED'),
            ('nium', TRUE, 'CLOSED'),
            ('wise', TRUE, 'CLOSED'),
            ('stablecoin_usdc', TRUE, 'CLOSED'),
            ('fallback_mock', TRUE, 'CLOSED')
        ON CONFLICT (rail) DO NOTHING;
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute('DROP TRIGGER IF EXISTS trigger_update_vettedpay_rail_health_timestamp ON vettedpay_rail_health;')
    op.execute('DROP TRIGGER IF EXISTS trigger_update_vettedpay_transactions_timestamp ON vettedpay_transactions;')
    
    # Drop function
    op.execute('DROP FUNCTION IF EXISTS update_vettedpay_timestamp();')
    
    # Drop indexes
    op.drop_index('idx_waitlist_priority', table_name='vettedpay_waitlist')
    op.drop_index('idx_waitlist_status', table_name='vettedpay_waitlist')
    op.drop_index('idx_waitlist_email', table_name='vettedpay_waitlist')
    
    op.drop_index('idx_zk_verifications_sender', table_name='vettedpay_zk_verifications')
    op.drop_index('idx_zk_verifications_transaction', table_name='vettedpay_zk_verifications')
    
    op.drop_index('idx_transactions_created', table_name='vettedpay_transactions')
    op.drop_index('idx_transactions_rail', table_name='vettedpay_transactions')
    op.drop_index('idx_transactions_status', table_name='vettedpay_transactions')
    op.drop_index('idx_transactions_idempotency', table_name='vettedpay_transactions')
    op.drop_index('idx_transactions_recipient', table_name='vettedpay_transactions')
    op.drop_index('idx_transactions_sender', table_name='vettedpay_transactions')
    
    # Drop tables
    op.drop_table('vettedpay_waitlist')
    op.drop_table('vettedpay_zk_verifications')
    op.drop_table('vettedpay_rail_health')
    op.drop_table('vettedpay_transactions')
    
    # Drop ENUM types
    op.execute('DROP TYPE IF EXISTS transaction_status;')
    op.execute('DROP TYPE IF EXISTS payment_rail;')
