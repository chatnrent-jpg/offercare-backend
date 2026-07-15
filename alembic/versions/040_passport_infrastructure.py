"""add_vettedme_passport_infrastructure

Revision ID: 040_passport_infrastructure
Revises: 039_healthcare_credentials
Create Date: 2026-07-14 16:30:00

This migration creates the VettedMe Passport infrastructure tables:
- passports: Core passport entity with cryptographic public keys
- credential_badges: Modular verifiable credentials (W3C standard)
- verification_logs: Audit trail for all verification API requests
- api_keys: API key management for external platform integrations

Security: Uses Ed25519 digital signatures for tamper-proof credentials.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '040_passport_infrastructure'
down_revision = '039_healthcare_credentials'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create passports table
    op.create_table(
        'passports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('public_key', sa.Text, nullable=False, comment='Ed25519 public key for cryptographic verification'),
        sa.Column('status', sa.String(20), nullable=False, server_default='ACTIVE', comment='ACTIVE, SUSPENDED, or REVOKED'),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False, comment='Passport renewal cycle (typically 2 years)'),
        sa.Column('biometric_hash', sa.Text, nullable=True, comment='Secure hash of facial biometric for liveness checks'),
        sa.Column('trust_score', sa.Integer, nullable=False, server_default='0', comment='Algorithmic trust rating (0-100)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint('trust_score >= 0 AND trust_score <= 100', name='trust_score_range')
    )
    op.create_index('idx_passports_status', 'passports', ['status'])
    op.create_index('idx_passports_user_id', 'passports', ['user_id'])

    # Create credential_badges table
    op.create_table(
        'credential_badges',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('passport_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('passports.id', ondelete='CASCADE'), nullable=False),
        sa.Column('badge_type', sa.String(50), nullable=False, comment='Type of credential (IDENTITY, HEALTHCARE, etc.)'),
        sa.Column('credential_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='Flexible schema containing credential details'),
        sa.Column('issuer_signature', sa.Text, nullable=False, comment='Ed25519 cryptographic signature from VettedMe'),
        sa.Column('verification_method', sa.String(50), nullable=False, comment='Method used to verify (MBON_SCRAPER, MANUAL_REVIEW, OCR_AI)'),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True, comment='Credential-specific expiration (if applicable)'),
        sa.Column('revoked', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revocation_reason', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )
    op.create_index('idx_badges_passport', 'credential_badges', ['passport_id'])
    op.create_index('idx_badges_type', 'credential_badges', ['badge_type'])
    op.create_index('idx_badges_expiration', 'credential_badges', ['expires_at'], postgresql_where=sa.text('NOT revoked'))

    # Create verification_logs table (audit trail)
    op.create_table(
        'verification_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('passport_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('passports.id', ondelete='CASCADE'), nullable=False),
        sa.Column('requesting_platform', sa.String(255), nullable=False, comment='Domain or name of requesting platform'),
        sa.Column('api_key_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('api_keys.id', ondelete='CASCADE'), nullable=False),
        sa.Column('requested_badges', postgresql.ARRAY(sa.String), nullable=False, comment='List of badge types requested'),
        sa.Column('verification_result', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='Full verification response payload'),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('ip_address', postgresql.INET, nullable=True),
        sa.Column('user_agent', sa.Text, nullable=True)
    )
    op.create_index('idx_verification_logs_passport', 'verification_logs', ['passport_id'])
    op.create_index('idx_verification_logs_timestamp', 'verification_logs', ['timestamp'])
    op.create_index('idx_verification_logs_platform', 'verification_logs', ['requesting_platform'])

    # Create api_keys table (platform authentication)
    op.create_table(
        'api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('organization_name', sa.String(255), nullable=False),
        sa.Column('key_hash', sa.Text, nullable=False, unique=True, comment='SHA256 hash of the API key'),
        sa.Column('key_prefix', sa.String(20), nullable=False, comment='First 8 chars for identification (e.g., "vettedme_")'),
        sa.Column('tier', sa.String(20), nullable=False, server_default='FREE', comment='FREE, GROWTH, or ENTERPRISE'),
        sa.Column('rate_limit_per_hour', sa.Integer, nullable=False, server_default='100'),
        sa.Column('status', sa.String(20), nullable=False, server_default='ACTIVE', comment='ACTIVE, SUSPENDED, or REVOKED'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('idx_api_keys_hash', 'api_keys', ['key_hash'])
    op.create_index('idx_api_keys_status', 'api_keys', ['status'])


def downgrade() -> None:
    # Drop tables in reverse order (respecting foreign key constraints)
    op.drop_table('verification_logs')
    op.drop_table('credential_badges')
    op.drop_table('api_keys')
    op.drop_table('passports')
