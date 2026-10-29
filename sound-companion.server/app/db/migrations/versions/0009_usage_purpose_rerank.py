"""usage_log purpose accepts 'rerank' (the cheap model that picks the chunks of a search)

Revision ID: 0009
Revises: 0008
"""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("usage_log_purpose_check", "usage_log")
    op.create_check_constraint(
        "usage_log_purpose_check", "usage_log", "purpose IN ('answer','rewrite','rerank','embed','eval')"
    )


def downgrade() -> None:
    op.drop_constraint("usage_log_purpose_check", "usage_log")
    op.create_check_constraint("usage_log_purpose_check", "usage_log", "purpose IN ('answer','rewrite','embed','eval')")
