"""Facility B2B billing audit ledger — itemized invoice math per completed shift."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID

revision: str = "027_facility_billing_audit"
down_revision: Union[str, None] = "026_gusto_employee_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not _has_table(inspector, "facility_billing_audit_ledger"):
        op.create_table(
            "facility_billing_audit_ledger",
            sa.Column("audit_id", UUID(as_uuid=True), primary_key=True),
            sa.Column("timesheet_id", UUID(as_uuid=True), nullable=True),
            sa.Column("provider_id", UUID(as_uuid=True), nullable=True),
            sa.Column("facility_id", UUID(as_uuid=True), nullable=True),
            sa.Column("offer_id", UUID(as_uuid=True), nullable=True),
            sa.Column("hours_worked", sa.Numeric(8, 2), nullable=False),
            sa.Column("gross_caregiver_pay_rate", sa.Numeric(8, 2), nullable=False),
            sa.Column("margin_pct", sa.Numeric(6, 4), nullable=False),
            sa.Column("employer_fica_rate", sa.Numeric(6, 4), nullable=False),
            sa.Column("gross_pay", sa.Numeric(10, 2), nullable=False),
            sa.Column("platform_margin", sa.Numeric(10, 2), nullable=False),
            sa.Column("employer_taxes", sa.Numeric(10, 2), nullable=False),
            sa.Column("total_facility_bill", sa.Numeric(10, 2), nullable=False),
            sa.Column("invoice_payload_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index(
            "ix_facility_billing_audit_timesheet",
            "facility_billing_audit_ledger",
            ["timesheet_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if _has_table(inspector, "facility_billing_audit_ledger"):
        op.drop_index("ix_facility_billing_audit_timesheet", table_name="facility_billing_audit_ledger")
        op.drop_table("facility_billing_audit_ledger")
