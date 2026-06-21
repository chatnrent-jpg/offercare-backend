"""Add sms_opt_out flag to maryland_providers."""

from alembic import op
import sqlalchemy as sa

revision = "012_sms_opt_out"
down_revision = "011_postgis_geo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "maryland_providers",
        sa.Column("sms_opt_out", sa.String(length=5), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("maryland_providers", "sms_opt_out")
