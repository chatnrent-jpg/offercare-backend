"""merge_multiple_heads

Revision ID: 3d1719ece552
Revises: 039_healthcare_credentials, faec9d05c90e
Create Date: 2026-07-13 18:30:47.132276

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3d1719ece552'
down_revision: Union[str, None] = ('039_healthcare_credentials', 'faec9d05c90e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
