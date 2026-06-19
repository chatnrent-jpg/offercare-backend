"""Alembic migration for VMS shift ingestion audit log."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "009_vms_shift_ingestion"
down_revision: Union[str, None] = "008_job_board_crisis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "vms_shift_ingestion_log" in inspector.get_table_names():
        return
    op.create_table(
        "vms_shift_ingestion_log",
        sa.Column("ingest_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("facility_id", sa.UUID(), nullable=True),
        sa.Column("offer_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("shift_role", sa.String(length=100), nullable=True),
        sa.Column("hourly_pay_rate", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["facility_id"], ["maryland_facilities.facility_id"]),
        sa.ForeignKeyConstraint(["offer_id"], ["offercare_job_offers.offer_id"]),
        sa.PrimaryKeyConstraint("ingest_id"),
        sa.UniqueConstraint("source", "external_id", name="uq_vms_ingest_source_external_id"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "vms_shift_ingestion_log" in inspector.get_table_names():
        op.drop_table("vms_shift_ingestion_log")
