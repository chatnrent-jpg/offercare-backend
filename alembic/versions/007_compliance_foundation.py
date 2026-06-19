"""Maryland credentialing, compliance documents, exclusion screenings, geo columns."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "007_compliance_foundation"
down_revision: Union[str, None] = "006_service_lines"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector, table: str, column: str) -> bool:
    return column in {col["name"] for col in inspector.get_columns(table)}


def _has_table(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _has_table(inspector, "maryland_facilities"):
        for col, col_type in (
            ("latitude", sa.Numeric(9, 6)),
            ("longitude", sa.Numeric(9, 6)),
        ):
            if not _has_column(inspector, "maryland_facilities", col):
                op.add_column("maryland_facilities", sa.Column(col, col_type, nullable=True))

    if _has_table(inspector, "maryland_providers"):
        for col, col_type, default in (
            ("home_zip", sa.String(length=20), None),
            ("latitude", sa.Numeric(9, 6), None),
            ("longitude", sa.Numeric(9, 6), None),
            ("dispatch_status", sa.String(length=20), "ACTIVE"),
            ("license_expires_on", sa.DateTime(timezone=True), None),
        ):
            if not _has_column(inspector, "maryland_providers", col):
                kwargs = {"nullable": True}
                if default is not None and col == "dispatch_status":
                    kwargs = {"nullable": False, "server_default": default}
                op.add_column("maryland_providers", sa.Column(col, col_type, **kwargs))

    if not _has_table(inspector, "clinician_compliance_documents"):
        op.create_table(
            "clinician_compliance_documents",
            sa.Column("document_id", sa.UUID(), nullable=False),
            sa.Column("provider_id", sa.UUID(), nullable=False),
            sa.Column("document_type", sa.String(length=30), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
            sa.Column("expires_on", sa.DateTime(timezone=True), nullable=True),
            sa.Column("source", sa.String(length=50), nullable=True),
            sa.Column("notes", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["provider_id"], ["maryland_providers.provider_id"]),
            sa.PrimaryKeyConstraint("document_id"),
        )

    inspector = inspect(bind)
    if not _has_table(inspector, "exclusion_screenings"):
        op.create_table(
            "exclusion_screenings",
            sa.Column("screening_id", sa.UUID(), nullable=False),
            sa.Column("provider_id", sa.UUID(), nullable=False),
            sa.Column("source", sa.String(length=30), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.Column("expires_on", sa.DateTime(timezone=True), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["provider_id"], ["maryland_providers.provider_id"]),
            sa.PrimaryKeyConstraint("screening_id"),
        )

    inspector = inspect(bind)
    if not _has_table(inspector, "facility_crisis_signals"):
        op.create_table(
            "facility_crisis_signals",
            sa.Column("signal_id", sa.UUID(), nullable=False),
            sa.Column("facility_id", sa.UUID(), nullable=False),
            sa.Column("signal_type", sa.String(length=40), nullable=False),
            sa.Column("severity", sa.String(length=20), nullable=False),
            sa.Column("score", sa.Numeric(5, 2), nullable=False, server_default="0"),
            sa.Column("summary", sa.String(length=500), nullable=False),
            sa.Column("source", sa.String(length=50), nullable=True),
            sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.ForeignKeyConstraint(["facility_id"], ["maryland_facilities.facility_id"]),
            sa.PrimaryKeyConstraint("signal_id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    for table in (
        "facility_crisis_signals",
        "exclusion_screenings",
        "clinician_compliance_documents",
    ):
        if _has_table(inspector, table):
            op.drop_table(table)
