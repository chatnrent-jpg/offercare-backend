"""Instant pay tables — created even when pgvector extension is unavailable."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.dialects.postgresql import UUID

revision: str = "019_instant_pay_tables"
down_revision: Union[str, None] = "018_pgvector_instant_pay"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1536


def _pgvector_available(bind) -> bool:
    bind.execute(text("SAVEPOINT vetted_pgvector_probe_019"))
    try:
        bind.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        version = bind.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")).scalar()
        bind.execute(text("RELEASE SAVEPOINT vetted_pgvector_probe_019"))
        return bool(version)
    except Exception:
        bind.execute(text("ROLLBACK TO SAVEPOINT vetted_pgvector_probe_019"))
        return False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "provider_stripe_payout_accounts" not in tables:
        op.create_table(
            "provider_stripe_payout_accounts",
            sa.Column(
                "provider_id",
                UUID(as_uuid=True),
                sa.ForeignKey("maryland_providers.provider_id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("stripe_connect_account_id", sa.String(length=128), nullable=False),
            sa.Column("stripe_debit_card_id", sa.String(length=128), nullable=False),
            sa.Column("instant_payout_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )

    if "shift_timesheet_payouts" not in tables:
        op.create_table(
            "shift_timesheet_payouts",
            sa.Column("payout_id", UUID(as_uuid=True), primary_key=True),
            sa.Column("timesheet_id", UUID(as_uuid=True), nullable=False, unique=True),
            sa.Column(
                "provider_id",
                UUID(as_uuid=True),
                sa.ForeignKey("maryland_providers.provider_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("gross_pay_amount", sa.Numeric(10, 2), nullable=False),
            sa.Column("supervisor_name", sa.String(length=255), nullable=False),
            sa.Column("supervisor_signed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("payout_eligible_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("payout_status", sa.String(length=30), nullable=False, server_default="PENDING"),
            sa.Column("stripe_payout_id", sa.String(length=128), nullable=True),
            sa.Column("stripe_mode", sa.String(length=30), nullable=True),
            sa.Column("failure_reason", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_shift_timesheet_payouts_status_eligible",
            "shift_timesheet_payouts",
            ["payout_status", "payout_eligible_at"],
        )

    if _pgvector_available(bind):
        tables = set(inspect(bind).get_table_names())
        if "provider_profile_embeddings" not in tables:
            op.execute(
                f"""
                CREATE TABLE provider_profile_embeddings (
                    provider_id UUID PRIMARY KEY
                        REFERENCES maryland_providers(provider_id) ON DELETE CASCADE,
                    profile_text TEXT NOT NULL,
                    embedding vector({EMBEDDING_DIM}) NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            op.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_provider_profile_embeddings_cosine
                ON provider_profile_embeddings
                USING hnsw (embedding vector_cosine_ops)
                """
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "shift_timesheet_payouts" in tables:
        op.drop_index("ix_shift_timesheet_payouts_status_eligible", table_name="shift_timesheet_payouts")
        op.drop_table("shift_timesheet_payouts")
    if "provider_stripe_payout_accounts" in tables:
        op.drop_table("provider_stripe_payout_accounts")
