"""add_webhook_system

Revision ID: 041_webhook_system
Revises: 040_passport_infrastructure
Create Date: 2026-07-14 16:51:00

This migration creates the Webhook system tables for real-time event notifications:
- webhook_subscriptions: Customer webhook endpoint configurations
- webhook_events: Events to be delivered (credential changes, verifications, etc.)
- webhook_deliveries: Individual delivery attempts with retry tracking

Features:
- HMAC SHA256 signature verification
- Exponential backoff retry (max 5 attempts)
- Dead letter queue for permanent failures
- Delivery statistics and monitoring
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '041_webhook_system'
down_revision = '040_passport_infrastructure'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create webhook_subscriptions table
    op.create_table(
        'webhook_subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('api_key_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('api_keys.id', ondelete='CASCADE'), nullable=False),
        sa.Column('url', sa.String(2048), nullable=False, comment='HTTPS endpoint to receive webhooks'),
        sa.Column('secret', sa.String(64), nullable=False, comment='HMAC secret for signature verification'),
        sa.Column('events', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='List of subscribed event types'),
        sa.Column('description', sa.String(255), nullable=True, comment='Human-readable description'),
        sa.Column('status', sa.String(20), nullable=False, server_default='ACTIVE', comment='ACTIVE, PAUSED, or DISABLED'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('total_deliveries', sa.Integer, nullable=False, server_default='0'),
        sa.Column('successful_deliveries', sa.Integer, nullable=False, server_default='0'),
        sa.Column('failed_deliveries', sa.Integer, nullable=False, server_default='0'),
        sa.Column('last_delivery_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_failure_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('idx_webhook_subscriptions_api_key', 'webhook_subscriptions', ['api_key_id'])
    op.create_index('idx_webhook_subscriptions_status', 'webhook_subscriptions', ['status'])

    # Create webhook_events table
    op.create_table(
        'webhook_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('event_type', sa.String(50), nullable=False, comment='Event type (e.g., "credential.issued")'),
        sa.Column('event_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='Full event payload'),
        sa.Column('passport_id', postgresql.UUID(as_uuid=True), nullable=True, comment='Related passport ID'),
        sa.Column('badge_id', postgresql.UUID(as_uuid=True), nullable=True, comment='Related badge ID'),
        sa.Column('status', sa.String(20), nullable=False, server_default='PENDING', comment='PENDING, PROCESSING, COMPLETED, FAILED'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_subscriptions', sa.Integer, nullable=False, server_default='0'),
        sa.Column('successful_deliveries', sa.Integer, nullable=False, server_default='0'),
        sa.Column('failed_deliveries', sa.Integer, nullable=False, server_default='0')
    )
    op.create_index('idx_webhook_events_type', 'webhook_events', ['event_type'])
    op.create_index('idx_webhook_events_status', 'webhook_events', ['status'])
    op.create_index('idx_webhook_events_passport', 'webhook_events', ['passport_id'])
    op.create_index('idx_webhook_events_badge', 'webhook_events', ['badge_id'])

    # Create webhook_deliveries table
    op.create_table(
        'webhook_deliveries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('webhook_subscriptions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('webhook_events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('attempt_number', sa.Integer, nullable=False, server_default='1', comment='1-indexed attempt number (max 5)'),
        sa.Column('status', sa.String(20), nullable=False, server_default='PENDING', comment='PENDING, SUCCESS, FAILED, DEAD_LETTER'),
        sa.Column('request_body', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='Full webhook payload'),
        sa.Column('request_headers', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='HTTP headers sent'),
        sa.Column('response_code', sa.Integer, nullable=True, comment='HTTP status code received'),
        sa.Column('response_body', sa.Text, nullable=True, comment='Response body (truncated to 10KB)'),
        sa.Column('response_time_ms', sa.Integer, nullable=True, comment='Response time in milliseconds'),
        sa.Column('error_message', sa.Text, nullable=True, comment='Error message if delivery failed'),
        sa.Column('will_retry', sa.Boolean, nullable=False, server_default='false', comment='Whether this delivery will be retried'),
        sa.Column('retry_at', sa.DateTime(timezone=True), nullable=True, comment='When to retry (exponential backoff)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True, comment='When delivery succeeded')
    )
    op.create_index('idx_webhook_deliveries_subscription', 'webhook_deliveries', ['subscription_id'])
    op.create_index('idx_webhook_deliveries_event', 'webhook_deliveries', ['event_id'])
    op.create_index('idx_webhook_deliveries_status', 'webhook_deliveries', ['status'])
    op.create_index('idx_webhook_deliveries_retry', 'webhook_deliveries', ['retry_at'], postgresql_where=sa.text("will_retry = true AND status = 'FAILED'"))


def downgrade() -> None:
    # Drop tables in reverse order (respecting foreign key constraints)
    op.drop_table('webhook_deliveries')
    op.drop_table('webhook_events')
    op.drop_table('webhook_subscriptions')
