"""Document extraction tables — smart OCR for credential processing."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "030_document_extraction_tables"
down_revision: Union[str, None] = "029_wave_dispatch_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Table: document_extraction_logs
    if not _has_table(inspector, "document_extraction_logs"):
        op.create_table(
            "document_extraction_logs",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("provider_id", UUID(as_uuid=True), nullable=False),
            sa.Column("document_type", sa.String(32), nullable=False),
            sa.Column("uploaded_file_path", sa.Text(), nullable=False),
            sa.Column("ocr_service", sa.String(32), nullable=True),
            sa.Column("extracted_text", sa.Text(), nullable=True),
            sa.Column("extracted_entities", JSONB, nullable=True),
            sa.Column("expiration_date", sa.Date(), nullable=True),
            sa.Column("quality_score", sa.Numeric(5, 2), nullable=True),
            sa.Column("fraud_flags", JSONB, nullable=True),
            sa.Column("extraction_status", sa.String(32), nullable=False),
            sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_doc_extract_provider", "document_extraction_logs", ["provider_id"])
        op.create_index("ix_doc_extract_type", "document_extraction_logs", ["document_type"])
        op.create_index("ix_doc_extract_status", "document_extraction_logs", ["extraction_status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    if _has_table(inspector, "document_extraction_logs"):
        op.drop_index("ix_doc_extract_status", table_name="document_extraction_logs")
        op.drop_index("ix_doc_extract_type", table_name="document_extraction_logs")
        op.drop_index("ix_doc_extract_provider", table_name="document_extraction_logs")
        op.drop_table("document_extraction_logs")
