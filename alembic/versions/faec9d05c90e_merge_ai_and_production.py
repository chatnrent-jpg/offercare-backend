"""merge_ai_and_production

Revision ID: faec9d05c90e
Revises: 028_ai_audit_logs, 038_security_hardening_tables
Create Date: 2026-07-08 21:54:32.557663

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'faec9d05c90e'
down_revision: Union[str, None] = ('028_ai_audit_logs', '038_security_hardening_tables')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
