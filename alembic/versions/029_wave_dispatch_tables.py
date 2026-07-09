"""Wave dispatch tables — autonomous SMS wave matching for shift fill optimization."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "029_wave_dispatch_tables"
down_revision: Union[str, None] = "028_conversational_sms_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Table 1: wave_dispatch_configs
    if not _has_table(inspector, "wave_dispatch_configs"):
        op.create_table(
            "wave_dispatch_configs",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("facility_id", UUID(as_uuid=True), nullable=True),
            sa.Column("wave_1_size", sa.Integer, default=5),
            sa.Column("wave_1_delay_seconds", sa.Integer, default=300),
            sa.Column("wave_2_size", sa.Integer, default=10),
            sa.Column("wave_2_delay_seconds", sa.Integer, default=300),
            sa.Column("wave_3_size", sa.Integer, default=20),
            sa.Column("wave_3_delay_seconds", sa.Integer, default=600),
            sa.Column("wave_4_bonus_enabled", sa.Boolean, default=True),
            sa.Column("wave_4_bonus_amount_per_hour", sa.Numeric(10, 2), default=5.00),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_wave_config_facility", "wave_dispatch_configs", ["facility_id"])
    
    # Table 2: wave_dispatch_runs
    if not _has_table(inspector, "wave_dispatch_runs"):
        op.create_table(
            "wave_dispatch_runs",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("shift_id", UUID(as_uuid=True), nullable=True),
            sa.Column("current_wave", sa.Integer, default=1),
            sa.Column("total_dispatched", sa.Integer, default=0),
            sa.Column("total_accepted", sa.Integer, default=0),
            sa.Column("total_declined", sa.Integer, default=0),
            sa.Column("run_state", sa.String(32), nullable=False, default="ACTIVE"),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completion_reason", sa.String(64), nullable=True),
        )
        op.create_index("ix_wave_run_shift", "wave_dispatch_runs", ["shift_id"])
        op.create_index("ix_wave_run_state", "wave_dispatch_runs", ["run_state"])
    
    # Table 3: provider_reliability_scores
    if not _has_table(inspector, "provider_reliability_scores"):
        op.create_table(
            "provider_reliability_scores",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("provider_id", UUID(as_uuid=True), nullable=False),
            sa.Column("reliability_score", sa.Numeric(5, 2), default=50.0),
            sa.Column("on_time_rate", sa.Numeric(5, 4), default=1.0),
            sa.Column("cancellation_rate", sa.Numeric(5, 4), default=0.0),
            sa.Column("response_rate", sa.Numeric(5, 4), default=1.0),
            sa.Column("avg_facility_rating", sa.Numeric(3, 2), default=3.0),
            sa.Column("total_shifts_completed", sa.Integer, default=0),
            sa.Column("last_shift_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_reliability_provider", "provider_reliability_scores", ["provider_id"], unique=True)
        op.create_index("ix_reliability_score", "provider_reliability_scores", ["reliability_score"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    if _has_table(inspector, "provider_reliability_scores"):
        op.drop_index("ix_reliability_score", table_name="provider_reliability_scores")
        op.drop_index("ix_reliability_provider", table_name="provider_reliability_scores")
        op.drop_table("provider_reliability_scores")
    
    if _has_table(inspector, "wave_dispatch_runs"):
        op.drop_index("ix_wave_run_state", table_name="wave_dispatch_runs")
        op.drop_index("ix_wave_run_shift", table_name="wave_dispatch_runs")
        op.drop_table("wave_dispatch_runs")
    
    if _has_table(inspector, "wave_dispatch_configs"):
        op.drop_index("ix_wave_config_facility", table_name="wave_dispatch_configs")
        op.drop_table("wave_dispatch_configs")
