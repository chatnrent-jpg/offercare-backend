"""EHR integration tables — MatrixCare/PointClickCare deep hooks."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "035_ehr_integration_tables"
down_revision: Union[str, None] = "034_gamification_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Table 1: ehr_integration_configs
    if not _has_table(inspector, "ehr_integration_configs"):
        op.create_table(
            "ehr_integration_configs",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("facility_id", UUID(as_uuid=True), nullable=False, unique=True),
            sa.Column("ehr_system", sa.String(32), nullable=False),
            sa.Column("ehr_api_endpoint", sa.Text(), nullable=True),
            sa.Column("ehr_api_key", sa.Text(), nullable=True),
            sa.Column("ehr_facility_id", sa.String(64), nullable=True),
            sa.Column("sync_enabled", sa.Boolean, default=True),
            sa.Column("sync_direction", sa.String(32), default="BIDIRECTIONAL"),
            sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_ehr_config_facility", "ehr_integration_configs", ["facility_id"])
        op.create_index("ix_ehr_config_system", "ehr_integration_configs", ["ehr_system"])
    
    # Table 2: ehr_shift_sync_log
    if not _has_table(inspector, "ehr_shift_sync_log"):
        op.create_table(
            "ehr_shift_sync_log",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("facility_id", UUID(as_uuid=True), nullable=False),
            sa.Column("ehr_system", sa.String(32), nullable=False),
            sa.Column("shift_id", UUID(as_uuid=True), nullable=True),
            sa.Column("ehr_shift_id", sa.String(64), nullable=True),
            sa.Column("sync_direction", sa.String(16), nullable=False),
            sa.Column("sync_status", sa.String(32), nullable=False),
            sa.Column("shift_data", JSONB, nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_ehr_sync_facility", "ehr_shift_sync_log", ["facility_id"])
        op.create_index("ix_ehr_sync_shift", "ehr_shift_sync_log", ["shift_id"])
        op.create_index("ix_ehr_sync_status", "ehr_shift_sync_log", ["sync_status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    if _has_table(inspector, "ehr_shift_sync_log"):
        op.drop_index("ix_ehr_sync_status", table_name="ehr_shift_sync_log")
        op.drop_index("ix_ehr_sync_shift", table_name="ehr_shift_sync_log")
        op.drop_index("ix_ehr_sync_facility", table_name="ehr_shift_sync_log")
        op.drop_table("ehr_shift_sync_log")
    
    if _has_table(inspector, "ehr_integration_configs"):
        op.drop_index("ix_ehr_config_system", table_name="ehr_integration_configs")
        op.drop_index("ix_ehr_config_facility", table_name="ehr_integration_configs")
        op.drop_table("ehr_integration_configs")
