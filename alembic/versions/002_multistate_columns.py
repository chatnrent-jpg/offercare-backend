"""Add state columns for multi-state facility and clinician grids."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "002_multistate"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    facility_cols = {col["name"] for col in inspector.get_columns("maryland_facilities")}
    provider_cols = {col["name"] for col in inspector.get_columns("maryland_providers")}

    if "state" not in facility_cols:
        op.add_column(
            "maryland_facilities",
            sa.Column("state", sa.String(length=2), nullable=False, server_default="MD"),
        )
    if "state" not in provider_cols:
        op.add_column(
            "maryland_providers",
            sa.Column("state", sa.String(length=2), nullable=False, server_default="MD"),
        )

    op.execute("CREATE INDEX IF NOT EXISTS ix_maryland_facilities_state ON maryland_facilities (state)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_maryland_providers_state ON maryland_providers (state)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_maryland_providers_state")
    op.execute("DROP INDEX IF EXISTS ix_maryland_facilities_state")
    bind = op.get_bind()
    inspector = inspect(bind)
    facility_cols = {col["name"] for col in inspector.get_columns("maryland_facilities")}
    provider_cols = {col["name"] for col in inspector.get_columns("maryland_providers")}
    if "state" in provider_cols:
        op.drop_column("maryland_providers", "state")
    if "state" in facility_cols:
        op.drop_column("maryland_facilities", "state")
