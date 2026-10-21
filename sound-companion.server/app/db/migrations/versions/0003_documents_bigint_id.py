"""documents.id as BIGINT

Migration 0002 created the id as INTEGER, but the schema (docs/DATABASE-SCHEMA.md) says BIGSERIAL
and the development database already had BIGINT. A database that has it is left unchanged.

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("documents", "id", existing_type=sa.Integer(), type_=sa.BigInteger())


def downgrade() -> None:
    op.alter_column("documents", "id", existing_type=sa.BigInteger(), type_=sa.Integer())
