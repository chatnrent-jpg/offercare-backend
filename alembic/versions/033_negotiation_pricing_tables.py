"""Negotiation and pricing tables — dynamic rates and surge pricing."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "033_negotiation_pricing_tables"
down_revision: Union[str, None] = "032_incident_handling_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Table 1: facility_rate_configs
    if not _has_table(inspector, "facility_rate_configs"):
        op.create_table(
            "facility_rate_configs",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("facility_id", UUID(as_uuid=True), nullable=False, unique=True),
            sa.Column("base_hourly_rate_cna", sa.Numeric(10, 2), default=25.00),
            sa.Column("base_hourly_rate_gna", sa.Numeric(10, 2), default=28.00),
            sa.Column("base_hourly_rate_lpn", sa.Numeric(10, 2), default=35.00),
            sa.Column("base_hourly_rate_rn", sa.Numeric(10, 2), default=45.00),
            sa.Column("max_hourly_rate_cna", sa.Numeric(10, 2), default=40.00),
            sa.Column("max_hourly_rate_gna", sa.Numeric(10, 2), default=45.00),
            sa.Column("max_hourly_rate_lpn", sa.Numeric(10, 2), default=60.00),
            sa.Column("max_hourly_rate_rn", sa.Numeric(10, 2), default=80.00),
            sa.Column("auto_negotiate_enabled", sa.Boolean, default=True),
            sa.Column("surge_pricing_enabled", sa.Boolean, default=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_rate_config_facility", "facility_rate_configs", ["facility_id"])
    
    # Table 2: rate_negotiation_history
    if not _has_table(inspector, "rate_negotiation_history"):
        op.create_table(
            "rate_negotiation_history",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("shift_id", UUID(as_uuid=True), nullable=False),
            sa.Column("facility_id", UUID(as_uuid=True), nullable=False),
            sa.Column("original_rate", sa.Numeric(10, 2), nullable=False),
            sa.Column("negotiated_rate", sa.Numeric(10, 2), nullable=False),
            sa.Column("rate_increase_pct", sa.Numeric(5, 2), nullable=False),
            sa.Column("urgency_score", sa.Numeric(5, 2), nullable=True),
            sa.Column("time_until_shift_minutes", sa.Integer, nullable=True),
            sa.Column("negotiation_trigger", sa.String(64), nullable=True),
            sa.Column("approved_by", sa.String(32), default="AUTO_NEGOTIATOR"),
            sa.Column("shift_filled_after_increase", sa.Boolean, default=False),
            sa.Column("negotiated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_negotiation_shift", "rate_negotiation_history", ["shift_id"])
        op.create_index("ix_negotiation_facility", "rate_negotiation_history", ["facility_id"])
        op.create_index("ix_negotiation_filled", "rate_negotiation_history", ["shift_filled_after_increase"])
    
    # Table 3: surge_pricing_events
    if not _has_table(inspector, "surge_pricing_events"):
        op.create_table(
            "surge_pricing_events",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("event_type", sa.String(32), nullable=False),
            sa.Column("surge_multiplier", sa.Numeric(5, 2), nullable=False),
            sa.Column("trigger_reason", sa.Text(), nullable=True),
            sa.Column("affected_regions", JSONB, nullable=True),
            sa.Column("affected_credential_types", JSONB, nullable=True),
            sa.Column("unfilled_shifts_count", sa.Integer, nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_surge_event_type", "surge_pricing_events", ["event_type"])
        op.create_index("ix_surge_active", "surge_pricing_events", ["started_at", "ended_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    if _has_table(inspector, "surge_pricing_events"):
        op.drop_index("ix_surge_active", table_name="surge_pricing_events")
        op.drop_index("ix_surge_event_type", table_name="surge_pricing_events")
        op.drop_table("surge_pricing_events")
    
    if _has_table(inspector, "rate_negotiation_history"):
        op.drop_index("ix_negotiation_filled", table_name="rate_negotiation_history")
        op.drop_index("ix_negotiation_facility", table_name="rate_negotiation_history")
        op.drop_index("ix_negotiation_shift", table_name="rate_negotiation_history")
        op.drop_table("rate_negotiation_history")
    
    if _has_table(inspector, "facility_rate_configs"):
        op.drop_index("ix_rate_config_facility", table_name="facility_rate_configs")
        op.drop_table("facility_rate_configs")
