"""Initial schema: pgvector extension and contracts_documents table

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-11-03 01:32:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Create contracts_documents table
    op.create_table(
        "contracts_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_contracts_documents_content_hash", "contracts_documents", ["content_hash"], unique=True
    )
    op.create_index(
        "ix_contracts_documents_status", "contracts_documents", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_contracts_documents_status", table_name="contracts_documents")
    op.drop_index("ix_contracts_documents_content_hash", table_name="contracts_documents")
    op.drop_table("contracts_documents")
