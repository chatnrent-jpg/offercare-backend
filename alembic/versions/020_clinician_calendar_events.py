"""Clinician calendar events — provider time vault for shift commitments and availability."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID

revision: str = "020_clinician_calendar_events"
down_revision: Union[str, None] = "019_instant_pay_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "clinician_calendar_events" not in tables:
        op.create_table(
            "clinician_calendar_events",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("provider_id", sa.String(length=128), nullable=False),
            sa.Column("shift_id", sa.String(length=128), nullable=True),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
            sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("metadata_json", sa.Text(), nullable=True),
        )
        op.create_index(
            "ix_clinician_calendar_events_provider_id",
            "clinician_calendar_events",
            ["provider_id"],
        )
        op.create_index(
            "ix_clinician_calendar_events_shift_id",
            "clinician_calendar_events",
            ["shift_id"],
        )
        op.create_index(
            "ix_clinician_calendar_events_provider_overlap",
            "clinician_calendar_events",
            ["provider_id", "start_time", "end_time"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "clinician_calendar_events" in tables:
        op.drop_index(
            "ix_clinician_calendar_events_provider_overlap",
            table_name="clinician_calendar_events",
        )
        op.drop_index(
            "ix_clinician_calendar_events_shift_id",
            table_name="clinician_calendar_events",
        )
        op.drop_index(
            "ix_clinician_calendar_events_provider_id",
            table_name="clinician_calendar_events",
        )
        op.drop_table("clinician_calendar_events")
