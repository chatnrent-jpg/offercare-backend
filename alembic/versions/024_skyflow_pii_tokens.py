"""Skyflow PII token columns on caregiver profile tables."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "024_skyflow_pii_tokens"
down_revision: Union[str, None] = "023_caregiver_intake_queue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector, table: str, column: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return column in {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _has_column(inspector, "caregiver_profiles", "skyflow_vault_record_id"):
        op.add_column(
            "caregiver_profiles",
            sa.Column("skyflow_vault_record_id", sa.String(length=128), nullable=True),
        )
    if not _has_column(inspector, "caregiver_profiles", "skyflow_ssn_token"):
        op.add_column(
            "caregiver_profiles",
            sa.Column("skyflow_ssn_token", sa.String(length=128), nullable=True),
        )
    if not _has_column(inspector, "caregiver_profiles", "skyflow_dob_token"):
        op.add_column(
            "caregiver_profiles",
            sa.Column("skyflow_dob_token", sa.String(length=128), nullable=True),
        )
    if not _has_column(inspector, "caregiver_w2_employee_accounts", "skyflow_stripe_routing_token"):
        op.add_column(
            "caregiver_w2_employee_accounts",
            sa.Column("skyflow_stripe_routing_token", sa.String(length=128), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if _has_column(inspector, "caregiver_w2_employee_accounts", "skyflow_stripe_routing_token"):
        op.drop_column("caregiver_w2_employee_accounts", "skyflow_stripe_routing_token")
    if _has_column(inspector, "caregiver_profiles", "skyflow_dob_token"):
        op.drop_column("caregiver_profiles", "skyflow_dob_token")
    if _has_column(inspector, "caregiver_profiles", "skyflow_ssn_token"):
        op.drop_column("caregiver_profiles", "skyflow_ssn_token")
    if _has_column(inspector, "caregiver_profiles", "skyflow_vault_record_id"):
        op.drop_column("caregiver_profiles", "skyflow_vault_record_id")
