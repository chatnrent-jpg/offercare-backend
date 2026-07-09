"""Conversational SMS dispatch tables — omnichannel text-to-book facility requests."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "028_conversational_sms_tables"
down_revision: Union[str, None] = "027_facility_billing_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Table 1: conversational_sms_sessions
    if not _has_table(inspector, "conversational_sms_sessions"):
        op.create_table(
            "conversational_sms_sessions",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("session_id", sa.String(64), unique=True, nullable=False),
            sa.Column("facility_id", UUID(as_uuid=True), nullable=True),
            sa.Column("facility_phone", sa.String(20), nullable=False),
            sa.Column("session_state", sa.String(32), nullable=False),
            sa.Column("intent_data", JSONB, nullable=True),
            sa.Column("created_shifts", sa.ARRAY(UUID(as_uuid=True)), nullable=True),
            sa.Column("message_count", sa.Integer, default=0),
            sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_conv_sms_session_facility", "conversational_sms_sessions", ["facility_id"])
        op.create_index("ix_conv_sms_session_state", "conversational_sms_sessions", ["session_state"])
        op.create_index("ix_conv_sms_session_phone", "conversational_sms_sessions", ["facility_phone"])
    
    # Table 2: conversational_sms_messages
    if not _has_table(inspector, "conversational_sms_messages"):
        op.create_table(
            "conversational_sms_messages",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("session_id", sa.String(64), nullable=False),
            sa.Column("direction", sa.String(10), nullable=False),
            sa.Column("from_phone", sa.String(20), nullable=False),
            sa.Column("to_phone", sa.String(20), nullable=False),
            sa.Column("message_body", sa.Text(), nullable=False),
            sa.Column("intent_classification", JSONB, nullable=True),
            sa.Column("twilio_message_sid", sa.String(64), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_conv_sms_message_session", "conversational_sms_messages", ["session_id"])
        op.create_index("ix_conv_sms_message_direction", "conversational_sms_messages", ["direction"])
        op.create_index("ix_conv_sms_message_timestamp", "conversational_sms_messages", ["sent_at"])
    
    # Table 3: nurse_sms_dispatch_log
    if not _has_table(inspector, "nurse_sms_dispatch_log"):
        op.create_table(
            "nurse_sms_dispatch_log",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("shift_id", UUID(as_uuid=True), nullable=True),
            sa.Column("provider_id", UUID(as_uuid=True), nullable=True),
            sa.Column("wave_number", sa.Integer, nullable=False),
            sa.Column("dispatch_priority", sa.Integer, nullable=True),
            sa.Column("message_body", sa.Text(), nullable=False),
            sa.Column("twilio_message_sid", sa.String(64), nullable=True),
            sa.Column("dispatched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("response_intent", sa.String(32), nullable=True),
            sa.Column("response_message", sa.Text(), nullable=True),
        )
        op.create_index("ix_nurse_dispatch_shift", "nurse_sms_dispatch_log", ["shift_id"])
        op.create_index("ix_nurse_dispatch_provider", "nurse_sms_dispatch_log", ["provider_id"])
        op.create_index("ix_nurse_dispatch_wave", "nurse_sms_dispatch_log", ["wave_number"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    if _has_table(inspector, "nurse_sms_dispatch_log"):
        op.drop_index("ix_nurse_dispatch_wave", table_name="nurse_sms_dispatch_log")
        op.drop_index("ix_nurse_dispatch_provider", table_name="nurse_sms_dispatch_log")
        op.drop_index("ix_nurse_dispatch_shift", table_name="nurse_sms_dispatch_log")
        op.drop_table("nurse_sms_dispatch_log")
    
    if _has_table(inspector, "conversational_sms_messages"):
        op.drop_index("ix_conv_sms_message_timestamp", table_name="conversational_sms_messages")
        op.drop_index("ix_conv_sms_message_direction", table_name="conversational_sms_messages")
        op.drop_index("ix_conv_sms_message_session", table_name="conversational_sms_messages")
        op.drop_table("conversational_sms_messages")
    
    if _has_table(inspector, "conversational_sms_sessions"):
        op.drop_index("ix_conv_sms_session_phone", table_name="conversational_sms_sessions")
        op.drop_index("ix_conv_sms_session_state", table_name="conversational_sms_sessions")
        op.drop_index("ix_conv_sms_session_facility", table_name="conversational_sms_sessions")
        op.drop_table("conversational_sms_sessions")
