"""PBJ reporting tables — CMS Payroll-Based Journal compliance."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "036_pbj_reporting_tables"
down_revision: Union[str, None] = "035_ehr_integration_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Table: pbj_report_exports
    if not _has_table(inspector, "pbj_report_exports"):
        op.create_table(
            "pbj_report_exports",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("facility_id", UUID(as_uuid=True), nullable=False),
            sa.Column("report_period_start", sa.Date(), nullable=False),
            sa.Column("report_period_end", sa.Date(), nullable=False),
            sa.Column("cms_provider_id", sa.String(16), nullable=True),
            sa.Column("total_hours_worked", sa.Numeric(10, 2), nullable=True),
            sa.Column("total_shifts_reported", sa.Integer, nullable=True),
            sa.Column("export_format", sa.String(16), default="CSV"),
            sa.Column("export_file_path", sa.Text(), nullable=True),
            sa.Column("export_status", sa.String(32), nullable=False),
            sa.Column("exported_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_pbj_facility", "pbj_report_exports", ["facility_id"])
        op.create_index("ix_pbj_period", "pbj_report_exports", ["report_period_start", "report_period_end"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    if _has_table(inspector, "pbj_report_exports"):
        op.drop_index("ix_pbj_period", table_name="pbj_report_exports")
        op.drop_index("ix_pbj_facility", table_name="pbj_report_exports")
        op.drop_table("pbj_report_exports")
