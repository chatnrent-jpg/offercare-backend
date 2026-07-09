"""Incident handling tables — 24/7 automated cancellation and backup dispatch."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "032_incident_handling_tables"
down_revision: Union[str, None] = "031_mbon_sweep_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Table 1: shift_incident_logs
    if not _has_table(inspector, "shift_incident_logs"):
        op.create_table(
            "shift_incident_logs",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("shift_id", UUID(as_uuid=True), nullable=False),
            sa.Column("provider_id", UUID(as_uuid=True), nullable=False),
            sa.Column("incident_type", sa.String(32), nullable=False),
            sa.Column("incident_severity", sa.String(16), nullable=False),
            sa.Column("reported_via", sa.String(16), nullable=False),
            sa.Column("incident_details", sa.Text(), nullable=True),
            sa.Column("extracted_intent", JSONB, nullable=True),
            sa.Column("automated_actions_taken", JSONB, nullable=True),
            sa.Column("backup_dispatched", sa.Boolean, default=False),
            sa.Column("reliability_penalty_applied", sa.Numeric(5, 2), nullable=True),
            sa.Column("reported_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_incident_shift", "shift_incident_logs", ["shift_id"])
        op.create_index("ix_incident_provider", "shift_incident_logs", ["provider_id"])
        op.create_index("ix_incident_type", "shift_incident_logs", ["incident_type"])
        op.create_index("ix_incident_severity", "shift_incident_logs", ["incident_severity"])
    
    # Table 2: backup_dispatch_runs
    if not _has_table(inspector, "backup_dispatch_runs"):
        op.create_table(
            "backup_dispatch_runs",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("incident_id", UUID(as_uuid=True), nullable=False),
            sa.Column("shift_id", UUID(as_uuid=True), nullable=False),
            sa.Column("original_provider_id", UUID(as_uuid=True), nullable=False),
            sa.Column("backup_wave_number", sa.Integer, default=1),
            sa.Column("total_dispatched", sa.Integer, default=0),
            sa.Column("backup_secured", sa.Boolean, default=False),
            sa.Column("backup_provider_id", UUID(as_uuid=True), nullable=True),
            sa.Column("minutes_before_shift", sa.Integer, nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_backup_incident", "backup_dispatch_runs", ["incident_id"])
        op.create_index("ix_backup_shift", "backup_dispatch_runs", ["shift_id"])
        op.create_index("ix_backup_secured", "backup_dispatch_runs", ["backup_secured"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    if _has_table(inspector, "backup_dispatch_runs"):
        op.drop_index("ix_backup_secured", table_name="backup_dispatch_runs")
        op.drop_index("ix_backup_shift", table_name="backup_dispatch_runs")
        op.drop_index("ix_backup_incident", table_name="backup_dispatch_runs")
        op.drop_table("backup_dispatch_runs")
    
    if _has_table(inspector, "shift_incident_logs"):
        op.drop_index("ix_incident_severity", table_name="shift_incident_logs")
        op.drop_index("ix_incident_type", table_name="shift_incident_logs")
        op.drop_index("ix_incident_provider", table_name="shift_incident_logs")
        op.drop_index("ix_incident_shift", table_name="shift_incident_logs")
        op.drop_table("shift_incident_logs")
