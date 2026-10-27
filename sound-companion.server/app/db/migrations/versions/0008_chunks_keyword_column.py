"""chunks: generated keyword column and GIN index for hybrid search

Revision ID: 0008
Revises: 0007

The chunks table belongs to langchain-postgres and is made by `scripts.setup_chunks`, which can run
after this migration on a fresh database. So the migration does nothing when the table is missing,
and `setup_chunks` adds the same column and index (`ensure_keyword_index`).
"""
from alembic import op
from sqlalchemy import inspect

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not inspect(op.get_bind()).has_table("chunks"):
        return
    op.execute(
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS content_tsv TSVECTOR "
        "GENERATED ALWAYS AS (to_tsvector('english', content)) STORED"
    )
    op.execute("CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (content_tsv)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS chunks_tsv_idx")
    if inspect(op.get_bind()).has_table("chunks"):
        op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS content_tsv")
