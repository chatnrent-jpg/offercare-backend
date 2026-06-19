"""Add explicit shift_starts_at and shift_ends_at to job offers."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "003_shift_schedule"
down_revision: Union[str, None] = "002_multistate"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    offer_cols = {col["name"] for col in inspector.get_columns("offercare_job_offers")}

    if "shift_starts_at" not in offer_cols:
        op.add_column(
            "offercare_job_offers",
            sa.Column("shift_starts_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "shift_ends_at" not in offer_cols:
        op.add_column(
            "offercare_job_offers",
            sa.Column("shift_ends_at", sa.DateTime(timezone=True), nullable=True),
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_offercare_job_offers_shift_starts_at "
        "ON offercare_job_offers (shift_starts_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_offercare_job_offers_shift_starts_at")
    bind = op.get_bind()
    inspector = inspect(bind)
    offer_cols = {col["name"] for col in inspector.get_columns("offercare_job_offers")}
    if "shift_ends_at" in offer_cols:
        op.drop_column("offercare_job_offers", "shift_ends_at")
    if "shift_starts_at" in offer_cols:
        op.drop_column("offercare_job_offers", "shift_starts_at")
