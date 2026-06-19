"""Initial OfferCare.ai schema.

Revision ID: 001_initial
Revises:
Create Date: 2026-06-10
"""

from typing import Sequence, Union

from alembic import op

import app.models  # noqa: F401
from app.database import Base

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_maryland_facilities_external
        ON maryland_facilities (external_source, external_id)
        WHERE external_source IS NOT NULL AND external_id IS NOT NULL
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
