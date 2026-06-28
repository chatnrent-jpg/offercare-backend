"""Add sms_opt_out flag to maryland_providers."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "012_sms_opt_out"
down_revision = "011_postgis_geo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("maryland_providers")}
    if "sms_opt_out" in columns:
        return
    op.add_column(
        "maryland_providers",
        sa.Column("sms_opt_out", sa.String(length=5), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("maryland_providers", "sms_opt_out")
