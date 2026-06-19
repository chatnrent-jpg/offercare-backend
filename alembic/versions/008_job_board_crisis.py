"""Alembic migration for job board crisis listing tracking."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "008_job_board_crisis"
down_revision: Union[str, None] = "007_compliance_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "job_board_crisis_listings" in inspector.get_table_names():
        return
    op.create_table(
        "job_board_crisis_listings",
        sa.Column("listing_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("facility_name", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("county", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=False, server_default="MD"),
        sa.Column("shift_role", sa.String(length=20), nullable=False),
        sa.Column("job_title", sa.String(length=255), nullable=False),
        sa.Column("job_url", sa.String(length=500), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("days_open", sa.Numeric(precision=5, scale=0), nullable=False, server_default="0"),
        sa.Column("is_crisis", sa.String(length=5), nullable=False, server_default="false"),
        sa.Column("facility_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["facility_id"], ["maryland_facilities.facility_id"]),
        sa.PrimaryKeyConstraint("listing_id"),
        sa.UniqueConstraint("source", "external_id", name="uq_job_board_source_external_id"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "job_board_crisis_listings" in inspector.get_table_names():
        op.drop_table("job_board_crisis_listings")
