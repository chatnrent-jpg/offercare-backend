"""Add Maryland healthcare credentials table - Phase 2: Integrity (Compliance)

Revision ID: 039_healthcare_credentials
Revises: 038_security_hardening_tables
Create Date: 2026-07-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "039_healthcare_credentials"
down_revision: Union[str, None] = "038_security_hardening_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create healthcare_credentials table for Maryland compliance tracking."""
    op.create_table(
        'healthcare_credentials',
        sa.Column('credential_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('license_type', sa.String(length=10), nullable=False),
        sa.Column('license_number', sa.String(length=50), nullable=False),
        sa.Column('expiration_date', sa.Date(), nullable=False),
        sa.Column('is_ohcq_verified', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('background_check_passed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('ohcq_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('background_check_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verification_notes', sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "license_type IN ('CNA', 'GNA', 'LPN', 'RN')",
            name='ck_healthcare_credentials_license_type'
        ),
        sa.CheckConstraint(
            'expiration_date > CURRENT_DATE',
            name='ck_healthcare_credentials_not_expired'
        ),
        sa.ForeignKeyConstraint(
            ['provider_id'],
            ['maryland_providers.provider_id'],
            name='fk_healthcare_credentials_provider_id_maryland_providers',
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('credential_id', name='pk_healthcare_credentials'),
        sa.UniqueConstraint('license_number', name='uq_healthcare_credentials_license_number')
    )
    
    # Create indexes
    op.create_index(
        'idx_healthcare_credentials_provider_license',
        'healthcare_credentials',
        ['provider_id', 'license_type']
    )
    op.create_index(
        'idx_healthcare_credentials_expiration',
        'healthcare_credentials',
        ['expiration_date']
    )
    op.create_index(
        'idx_healthcare_credentials_verification',
        'healthcare_credentials',
        ['is_ohcq_verified', 'background_check_passed']
    )
    op.create_index(
        'ix_healthcare_credentials_provider_id',
        'healthcare_credentials',
        ['provider_id']
    )
    op.create_index(
        'ix_healthcare_credentials_license_number',
        'healthcare_credentials',
        ['license_number'],
        unique=True
    )
    op.create_index(
        'ix_healthcare_credentials_is_ohcq_verified',
        'healthcare_credentials',
        ['is_ohcq_verified']
    )
    op.create_index(
        'ix_healthcare_credentials_background_check_passed',
        'healthcare_credentials',
        ['background_check_passed']
    )


def downgrade() -> None:
    """Drop healthcare_credentials table and all indexes."""
    op.drop_index('ix_healthcare_credentials_background_check_passed', table_name='healthcare_credentials')
    op.drop_index('ix_healthcare_credentials_is_ohcq_verified', table_name='healthcare_credentials')
    op.drop_index('ix_healthcare_credentials_license_number', table_name='healthcare_credentials')
    op.drop_index('ix_healthcare_credentials_provider_id', table_name='healthcare_credentials')
    op.drop_index('idx_healthcare_credentials_verification', table_name='healthcare_credentials')
    op.drop_index('idx_healthcare_credentials_expiration', table_name='healthcare_credentials')
    op.drop_index('idx_healthcare_credentials_provider_license', table_name='healthcare_credentials')
    op.drop_table('healthcare_credentials')
