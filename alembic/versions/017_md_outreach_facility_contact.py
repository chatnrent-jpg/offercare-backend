"""Link md_outreach_payloads to facility_contacts for Manus B2B sequencer."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID

revision = "017_md_outreach_facility_contact"
down_revision = "016_maryland_facility_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "md_outreach_payloads" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("md_outreach_payloads")}
    if "facility_contact_id" not in columns:
        op.add_column(
            "md_outreach_payloads",
            sa.Column(
                "facility_contact_id",
                UUID(as_uuid=True),
                sa.ForeignKey("facility_contacts.contact_id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index(
            "ix_md_outreach_payloads_facility_contact_id",
            "md_outreach_payloads",
            ["facility_contact_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "md_outreach_payloads" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("md_outreach_payloads")}
    if "facility_contact_id" in columns:
        op.drop_index("ix_md_outreach_payloads_facility_contact_id", table_name="md_outreach_payloads")
        op.drop_column("md_outreach_payloads", "facility_contact_id")
