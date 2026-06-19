"""Add clinician Web Push subscription table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "004_push_subscriptions"
down_revision: Union[str, None] = "003_shift_schedule"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("clinician_push_subscriptions"):
        return

    op.create_table(
        "clinician_push_subscriptions",
        sa.Column("subscription_id", sa.UUID(), nullable=False),
        sa.Column("provider_id", sa.UUID(), nullable=False),
        sa.Column("endpoint", sa.String(length=500), nullable=False),
        sa.Column("p256dh_key", sa.String(length=255), nullable=False),
        sa.Column("auth_key", sa.String(length=255), nullable=False),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["provider_id"], ["maryland_providers.provider_id"]),
        sa.PrimaryKeyConstraint("subscription_id"),
        sa.UniqueConstraint("endpoint"),
    )
    op.create_index(
        "ix_clinician_push_subscriptions_provider_id",
        "clinician_push_subscriptions",
        ["provider_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("clinician_push_subscriptions"):
        return
    op.drop_index("ix_clinician_push_subscriptions_provider_id", table_name="clinician_push_subscriptions")
    op.drop_table("clinician_push_subscriptions")
