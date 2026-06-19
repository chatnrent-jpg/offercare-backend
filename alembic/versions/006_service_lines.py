"""Add clinician service_lines for hospital vs post-acute matching."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "006_service_lines"
down_revision: Union[str, None] = "005_credential_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    provider_cols = {col["name"] for col in inspector.get_columns("maryland_providers")}
    if "service_lines" not in provider_cols:
        op.add_column(
            "maryland_providers",
            sa.Column("service_lines", sa.String(length=100), nullable=False, server_default="ALL"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    provider_cols = {col["name"] for col in inspector.get_columns("maryland_providers")}
    if "service_lines" in provider_cols:
        op.drop_column("maryland_providers", "service_lines")
