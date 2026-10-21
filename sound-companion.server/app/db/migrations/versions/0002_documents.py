"""documents

One row per Corpus document: attribution, provenance and the cleaned sections Story 3 chunks.

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("topics", sa.Text(), server_default="", nullable=False),
        sa.Column("aliases", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("url", sa.Text(), nullable=False, unique=True),
        sa.Column("license", sa.Text(), nullable=False),
        sa.Column("revision_id", sa.Text(), nullable=False),
        sa.Column("sections", postgresql.JSONB(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('encyclopedia', 'textbook')", name="documents_source_type_check"
        ),
    )


def downgrade() -> None:
    op.drop_table("documents")
