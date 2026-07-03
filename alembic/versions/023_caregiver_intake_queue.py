"""Caregiver intake queue — text-to-apply landing leads."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID

revision: str = "023_caregiver_intake_queue"
down_revision: Union[str, None] = "022_caregiver_dual_accounts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _has_table(inspector, "caregiver_intake_queue"):
        op.create_table(
            "caregiver_intake_queue",
            sa.Column("intake_id", UUID(as_uuid=True), primary_key=True),
            sa.Column("phone_number", sa.String(length=20), nullable=False),
            sa.Column("full_name", sa.String(length=255), nullable=True),
            sa.Column("credential_type", sa.String(length=20), nullable=False, server_default="CNA"),
            sa.Column("home_zip", sa.String(length=20), nullable=True),
            sa.Column(
                "landing_slug",
                sa.String(length=120),
                nullable=False,
                server_default="baltimore-instant-pay-cna",
            ),
            sa.Column("market", sa.String(length=80), nullable=False, server_default="Baltimore"),
            sa.Column("queue_status", sa.String(length=30), nullable=False, server_default="QUEUED"),
            sa.Column("sms_consent", sa.String(length=5), nullable=False, server_default="true"),
            sa.Column("consent_version", sa.String(length=20), nullable=False),
            sa.Column("client_ip", sa.String(length=64), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "provider_id",
                UUID(as_uuid=True),
                sa.ForeignKey("maryland_providers.provider_id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_caregiver_intake_queue_phone_number", "caregiver_intake_queue", ["phone_number"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if _has_table(inspector, "caregiver_intake_queue"):
        op.drop_index("ix_caregiver_intake_queue_phone_number", table_name="caregiver_intake_queue")
        op.drop_table("caregiver_intake_queue")
