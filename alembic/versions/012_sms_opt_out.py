"""SMS opt-out support.

Revision ID: 012_sms_opt_out
Revises: 011_postgis_geo
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "012_sms_opt_out"
down_revision: Union[str, None] = "011_postgis_geo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add SMS opt-out support to maryland_providers table."""
    # This migration was already applied manually or is a placeholder
    pass


def downgrade() -> None:
    """Remove SMS opt-out support."""
    pass
