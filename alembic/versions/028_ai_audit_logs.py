"""Add AI audit logs table for Phase 1 AI infrastructure

Revision ID: 028_ai_audit_logs
Revises: 027_facility_billing_audit
Create Date: 2026-07-08 18:53:00

This migration creates the ai_audit_logs table to support:
- AI-powered resume parsing operations
- Comprehensive audit trail for all AI decisions
- Cost tracking and performance metrics
- Compliance and explainability requirements
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '028_ai_audit_logs'
down_revision = '027_facility_billing_audit'
branch_labels = None
depends_on = None


def upgrade():
    """Create ai_audit_logs table with proper indexes."""
    op.create_table(
        'ai_audit_logs',
        sa.Column('audit_id', sa.String(50), primary_key=True, nullable=False),
        sa.Column('operation_type', sa.String(100), nullable=False),
        sa.Column('model_used', sa.String(50), nullable=False),
        sa.Column('user_id', sa.String(50), nullable=True),
        sa.Column('input_hash', sa.String(64), nullable=False),
        sa.Column('input_preview', sa.Text, nullable=True),
        sa.Column('output_data', sa.Text, nullable=False),
        sa.Column('confidence_score', sa.Float, nullable=True),
        sa.Column('tokens_used', sa.Integer, nullable=True),
        sa.Column('cost_usd', sa.Float, nullable=True),
        sa.Column('elapsed_ms', sa.Integer, nullable=True),
        sa.Column('status', sa.String(30), nullable=False, server_default='SUCCESS'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # Create indexes for common query patterns
    op.create_index('ix_ai_audit_logs_audit_id', 'ai_audit_logs', ['audit_id'])
    op.create_index('ix_ai_audit_logs_operation_type', 'ai_audit_logs', ['operation_type'])
    op.create_index('ix_ai_audit_logs_user_id', 'ai_audit_logs', ['user_id'])
    op.create_index('ix_ai_audit_logs_input_hash', 'ai_audit_logs', ['input_hash'])
    op.create_index('ix_ai_audit_logs_created_at', 'ai_audit_logs', ['created_at'])
    
    # Composite indexes for complex queries
    op.create_index('idx_ai_audit_operation_created', 'ai_audit_logs', ['operation_type', 'created_at'])
    op.create_index('idx_ai_audit_user_created', 'ai_audit_logs', ['user_id', 'created_at'])
    op.create_index('idx_ai_audit_status_created', 'ai_audit_logs', ['status', 'created_at'])


def downgrade():
    """Drop ai_audit_logs table and all indexes."""
    op.drop_index('idx_ai_audit_status_created', table_name='ai_audit_logs')
    op.drop_index('idx_ai_audit_user_created', table_name='ai_audit_logs')
    op.drop_index('idx_ai_audit_operation_created', table_name='ai_audit_logs')
    op.drop_index('ix_ai_audit_logs_created_at', table_name='ai_audit_logs')
    op.drop_index('ix_ai_audit_logs_input_hash', table_name='ai_audit_logs')
    op.drop_index('ix_ai_audit_logs_user_id', table_name='ai_audit_logs')
    op.drop_index('ix_ai_audit_logs_operation_type', table_name='ai_audit_logs')
    op.drop_index('ix_ai_audit_logs_audit_id', table_name='ai_audit_logs')
    op.drop_table('ai_audit_logs')
