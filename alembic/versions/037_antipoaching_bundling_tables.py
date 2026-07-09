"""Anti-poaching and shift bundling tables — revenue protection and optimization."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "037_antipoaching_bundling_tables"
down_revision: Union[str, None] = "036_pbj_reporting_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Table 1: poaching_detection_logs
    if not _has_table(inspector, "poaching_detection_logs"):
        op.create_table(
            "poaching_detection_logs",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("provider_id", UUID(as_uuid=True), nullable=True),
            sa.Column("facility_id", UUID(as_uuid=True), nullable=True),
            sa.Column("message_source", sa.String(32), nullable=False),
            sa.Column("message_content", sa.Text(), nullable=False),
            sa.Column("poaching_indicators", JSONB, nullable=True),
            sa.Column("risk_score", sa.Numeric(5, 2), nullable=True),
            sa.Column("action_taken", sa.String(32), nullable=True),
            sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_poach_provider", "poaching_detection_logs", ["provider_id"])
        op.create_index("ix_poach_facility", "poaching_detection_logs", ["facility_id"])
        op.create_index("ix_poach_risk", "poaching_detection_logs", ["risk_score"])
    
    # Table 2: shift_bundles
    if not _has_table(inspector, "shift_bundles"):
        op.create_table(
            "shift_bundles",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("bundle_name", sa.String(128), nullable=True),
            sa.Column("provider_id", UUID(as_uuid=True), nullable=True),
            sa.Column("shift_ids", JSONB, nullable=False),
            sa.Column("total_hours", sa.Numeric(5, 2), nullable=True),
            sa.Column("total_earnings", sa.Numeric(10, 2), nullable=True),
            sa.Column("route_optimized", sa.Boolean, default=False),
            sa.Column("bundle_status", sa.String(32), default="PROPOSED"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_bundle_provider", "shift_bundles", ["provider_id"])
        op.create_index("ix_bundle_status", "shift_bundles", ["bundle_status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    if _has_table(inspector, "shift_bundles"):
        op.drop_index("ix_bundle_status", table_name="shift_bundles")
        op.drop_index("ix_bundle_provider", table_name="shift_bundles")
        op.drop_table("shift_bundles")
    
    if _has_table(inspector, "poaching_detection_logs"):
        op.drop_index("ix_poach_risk", table_name="poaching_detection_logs")
        op.drop_index("ix_poach_facility", table_name="poaching_detection_logs")
        op.drop_index("ix_poach_provider", table_name="poaching_detection_logs")
        op.drop_table("poaching_detection_logs")
