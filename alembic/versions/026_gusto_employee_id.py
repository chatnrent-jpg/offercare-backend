"""Gusto / Check HQ employee ID on Tier 1 W-2 caregiver accounts."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "026_gusto_employee_id"
down_revision: Union[str, None] = "025_maryland_aedt_consent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector, table: str, column: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return column in {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not _has_column(inspector, "caregiver_w2_employee_accounts", "gusto_employee_id"):
        op.add_column(
            "caregiver_w2_employee_accounts",
            sa.Column("gusto_employee_id", sa.String(length=128), nullable=True),
        )
    if not _has_column(inspector, "caregiver_w2_employee_accounts", "payroll_onboarding_error"):
        op.add_column(
            "caregiver_w2_employee_accounts",
            sa.Column("payroll_onboarding_error", sa.String(length=2000), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if _has_column(inspector, "caregiver_w2_employee_accounts", "payroll_onboarding_error"):
        op.drop_column("caregiver_w2_employee_accounts", "payroll_onboarding_error")
    if _has_column(inspector, "caregiver_w2_employee_accounts", "gusto_employee_id"):
        op.drop_column("caregiver_w2_employee_accounts", "gusto_employee_id")
