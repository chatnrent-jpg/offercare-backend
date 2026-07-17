"""VettedPay multi-rail payout tracking

Revision ID: 043_vettedpay_payouts
Revises: 042_zktls_platform_schema
Create Date: 2026-07-17 09:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = '043_vettedpay_payouts'
down_revision: Union[str, None] = '042_zktls_platform_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # VettedPay payout transactions table
    op.create_table(
        'vettedpay_payouts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('idempotency_key', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('provider_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('destination', sa.String(255), nullable=False),
        sa.Column('rail', sa.String(50), nullable=False, index=True),
        sa.Column('status', sa.String(50), nullable=False, index=True),
        sa.Column('transaction_id', sa.String(255), nullable=True, index=True),
        sa.Column('provider_reference', sa.String(255), nullable=True),
        sa.Column('compliance_packet_id', sa.String(255), nullable=False),
        sa.Column('compliance_verified', sa.Boolean, nullable=False, default=False),
        sa.Column('fees', sa.Numeric(10, 2), nullable=True),
        sa.Column('estimated_arrival', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_code', sa.String(100), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('metadata', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
    )
    
    # Compliance packets table (encrypted PII never stored in readable form)
    op.create_table(
        'vettedpay_compliance_packets',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('packet_id', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('provider_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('version', sa.String(20), nullable=False),
        sa.Column('zk_proof_hash', sa.String(64), nullable=False),
        sa.Column('zk_proof_signature', sa.String(64), nullable=False),
        sa.Column('encrypted_payload', sa.Text, nullable=False),
        sa.Column('encryption_algorithm', sa.String(50), nullable=False),
        sa.Column('recipient_key_fingerprint', sa.String(16), nullable=False),
        sa.Column('packet_signature', sa.String(64), nullable=False),
        sa.Column('recipient_bank_id', sa.String(50), nullable=False),
        sa.Column('sanction_check_result', sa.String(20), nullable=False, index=True),
        sa.Column('verification_method', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    
    # Payment rail health status
    op.create_table(
        'vettedpay_rail_health',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('rail', sa.String(50), nullable=False, unique=True),
        sa.Column('is_healthy', sa.Boolean, nullable=False, default=True),
        sa.Column('circuit_status', sa.String(20), nullable=False, default='CLOSED'),
        sa.Column('failure_count', sa.Integer, nullable=False, default=0),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_failure_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('circuit_opened_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
    )
    
    # Indexes for common queries
    op.create_index('ix_payouts_provider_status', 'vettedpay_payouts', ['provider_id', 'status'])
    op.create_index('ix_payouts_created_at', 'vettedpay_payouts', ['created_at'])
    op.create_index('ix_compliance_provider_created', 'vettedpay_compliance_packets', ['provider_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_compliance_provider_created', table_name='vettedpay_compliance_packets')
    op.drop_index('ix_payouts_created_at', table_name='vettedpay_payouts')
    op.drop_index('ix_payouts_provider_status', table_name='vettedpay_payouts')
    op.drop_table('vettedpay_rail_health')
    op.drop_table('vettedpay_compliance_packets')
    op.drop_table('vettedpay_payouts')
