"""Security hardening tables — IP whitelist and evidence ledger."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "038_security_hardening_tables"
down_revision: Union[str, None] = "037_antipoaching_bundling_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Table 1: ip_whitelist
    if not _has_table(inspector, "ip_whitelist"):
        op.create_table(
            "ip_whitelist",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("facility_id", UUID(as_uuid=True), nullable=True),
            sa.Column("ip_address", sa.String(45), nullable=False, unique=True),
            sa.Column("ip_range_cidr", sa.String(50), nullable=True),
            sa.Column("whitelist_reason", sa.Text(), nullable=True),
            sa.Column("added_by", sa.String(128), nullable=True),
            sa.Column("is_active", sa.Boolean, default=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_whitelist_ip", "ip_whitelist", ["ip_address"])
        op.create_index("ix_whitelist_active", "ip_whitelist", ["is_active"])
    
    # Table 2: security_evidence_ledger (Merkle-tree chain)
    if not _has_table(inspector, "security_evidence_ledger"):
        op.create_table(
            "security_evidence_ledger",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("block_index", sa.Integer, nullable=False, unique=True),
            sa.Column("evidence_type", sa.String(32), nullable=False),
            sa.Column("evidence_data", JSONB, nullable=False),
            sa.Column("previous_hash", sa.String(64), nullable=True),
            sa.Column("current_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
        )
        op.create_index("ix_evidence_block", "security_evidence_ledger", ["block_index"])
        op.create_index("ix_evidence_type", "security_evidence_ledger", ["evidence_type"])
        op.create_index("ix_evidence_hash", "security_evidence_ledger", ["current_hash"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    if _has_table(inspector, "security_evidence_ledger"):
        op.drop_index("ix_evidence_hash", table_name="security_evidence_ledger")
        op.drop_index("ix_evidence_type", table_name="security_evidence_ledger")
        op.drop_index("ix_evidence_block", table_name="security_evidence_ledger")
        op.drop_table("security_evidence_ledger")
    
    if _has_table(inspector, "ip_whitelist"):
        op.drop_index("ix_whitelist_active", table_name="ip_whitelist")
        op.drop_index("ix_whitelist_ip", table_name="ip_whitelist")
        op.drop_table("ip_whitelist")
