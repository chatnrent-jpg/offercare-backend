"""Add clinician credential type for LPN/CNA/GNA staffing."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "005_credential_type"
down_revision: Union[str, None] = "004_push_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    provider_cols = {col["name"] for col in inspector.get_columns("maryland_providers")}
    if "credential_type" not in provider_cols:
        op.add_column(
            "maryland_providers",
            sa.Column("credential_type", sa.String(length=20), nullable=False, server_default="RN"),
        )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_maryland_providers_credential_type "
        "ON maryland_providers (credential_type)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_maryland_providers_credential_type")
    bind = op.get_bind()
    inspector = inspect(bind)
    provider_cols = {col["name"] for col in inspector.get_columns("maryland_providers")}
    if "credential_type" in provider_cols:
        op.drop_column("maryland_providers", "credential_type")
