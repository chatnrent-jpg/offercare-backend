"""Maryland AEDT 30-day disclosure — consent_signed_at on provider profiles."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "025_maryland_aedt_consent"
down_revision: Union[str, None] = "024_skyflow_pii_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector, table: str, column: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return column in {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not _has_column(inspector, "maryland_providers", "consent_signed_at"):
        op.add_column(
            "maryland_providers",
            sa.Column(
                "consent_signed_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="Maryland AEDT / HB 1106 automated shift-routing consent timestamp",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if _has_column(inspector, "maryland_providers", "consent_signed_at"):
        op.drop_column("maryland_providers", "consent_signed_at")
