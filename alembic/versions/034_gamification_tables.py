"""Gamification tables — nurse retention and engagement."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "034_gamification_tables"
down_revision: Union[str, None] = "033_negotiation_pricing_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Table 1: provider_achievement_logs
    if not _has_table(inspector, "provider_achievement_logs"):
        op.create_table(
            "provider_achievement_logs",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("provider_id", UUID(as_uuid=True), nullable=False),
            sa.Column("achievement_type", sa.String(64), nullable=False),
            sa.Column("achievement_tier", sa.String(16), nullable=True),
            sa.Column("reward_unlocked", sa.Text(), nullable=True),
            sa.Column("earned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_achievement_provider", "provider_achievement_logs", ["provider_id"])
        op.create_index("ix_achievement_type", "provider_achievement_logs", ["achievement_type"])
    
    # Table 2: provider_tier_status
    if not _has_table(inspector, "provider_tier_status"):
        op.create_table(
            "provider_tier_status",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("provider_id", UUID(as_uuid=True), nullable=False, unique=True),
            sa.Column("current_tier", sa.String(16), nullable=False, default="BRONZE"),
            sa.Column("tier_points", sa.Integer, default=0),
            sa.Column("total_shifts_completed", sa.Integer, default=0),
            sa.Column("perfect_attendance_streak", sa.Integer, default=0),
            sa.Column("perks_unlocked", JSONB, nullable=True),
            sa.Column("last_tier_change", sa.DateTime(timezone=True), nullable=True),
            sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_tier_provider", "provider_tier_status", ["provider_id"])
        op.create_index("ix_tier_current", "provider_tier_status", ["current_tier"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    if _has_table(inspector, "provider_tier_status"):
        op.drop_index("ix_tier_current", table_name="provider_tier_status")
        op.drop_index("ix_tier_provider", table_name="provider_tier_status")
        op.drop_table("provider_tier_status")
    
    if _has_table(inspector, "provider_achievement_logs"):
        op.drop_index("ix_achievement_type", table_name="provider_achievement_logs")
        op.drop_index("ix_achievement_provider", table_name="provider_achievement_logs")
        op.drop_table("provider_achievement_logs")
