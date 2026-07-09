"""MBON sweep tables — weekly automated license verification."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "031_mbon_sweep_tables"
down_revision: Union[str, None] = "030_document_extraction_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Table 1: mbon_sweep_runs
    if not _has_table(inspector, "mbon_sweep_runs"):
        op.create_table(
            "mbon_sweep_runs",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("run_started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("run_completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("total_licenses_checked", sa.Integer, default=0),
            sa.Column("total_suspensions", sa.Integer, default=0),
            sa.Column("total_warnings", sa.Integer, default=0),
            sa.Column("total_errors", sa.Integer, default=0),
            sa.Column("run_status", sa.String(32), nullable=False, default="IN_PROGRESS"),
            sa.Column("error_message", sa.Text(), nullable=True),
        )
        op.create_index("ix_mbon_sweep_run_status", "mbon_sweep_runs", ["run_status"])
        op.create_index("ix_mbon_sweep_run_date", "mbon_sweep_runs", ["run_started_at"])
    
    # Table 2: mbon_sweep_results
    if not _has_table(inspector, "mbon_sweep_results"):
        op.create_table(
            "mbon_sweep_results",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("sweep_run_id", UUID(as_uuid=True), nullable=False),
            sa.Column("provider_id", UUID(as_uuid=True), nullable=False),
            sa.Column("license_number", sa.String(64), nullable=True),
            sa.Column("previous_status", sa.String(32), nullable=True),
            sa.Column("new_status", sa.String(32), nullable=True),
            sa.Column("action_taken", sa.String(32), nullable=True),
            sa.Column("mbon_api_response", JSONB, nullable=True),
            sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_mbon_sweep_result_run", "mbon_sweep_results", ["sweep_run_id"])
        op.create_index("ix_mbon_sweep_result_provider", "mbon_sweep_results", ["provider_id"])
        op.create_index("ix_mbon_sweep_result_action", "mbon_sweep_results", ["action_taken"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    if _has_table(inspector, "mbon_sweep_results"):
        op.drop_index("ix_mbon_sweep_result_action", table_name="mbon_sweep_results")
        op.drop_index("ix_mbon_sweep_result_provider", table_name="mbon_sweep_results")
        op.drop_index("ix_mbon_sweep_result_run", table_name="mbon_sweep_results")
        op.drop_table("mbon_sweep_results")
    
    if _has_table(inspector, "mbon_sweep_runs"):
        op.drop_index("ix_mbon_sweep_run_date", table_name="mbon_sweep_runs")
        op.drop_index("ix_mbon_sweep_run_status", table_name="mbon_sweep_runs")
        op.drop_table("mbon_sweep_runs")
