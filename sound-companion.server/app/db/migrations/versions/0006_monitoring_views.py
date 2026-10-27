"""monitoring views over app_logs: daily latency and errors, calls per tool

Revision ID: 0006
Revises: 0005
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # one row per request_end: its duration and outcome, per day
    op.execute(
        """
        CREATE VIEW monitoring_daily AS
        SELECT created_at::date AS day,
               count(*) AS requests,
               count(*) FILTER (WHERE data->>'outcome' = 'error') AS errors,
               round(count(*) FILTER (WHERE data->>'outcome' = 'error')::numeric / count(*), 4) AS error_rate,
               round(avg((data->>'duration_ms')::numeric), 1) AS avg_ms,
               round((percentile_cont(0.95) WITHIN GROUP (ORDER BY (data->>'duration_ms')::numeric))::numeric, 1) AS p95_ms
        FROM app_logs
        WHERE event = 'request_end'
        GROUP BY created_at::date
        """
    )
    # calls per tool, with how many failed and how long they took (from the tool_result rows)
    op.execute(
        """
        CREATE VIEW monitoring_tools AS
        SELECT data->>'name' AS tool,
               count(*) AS calls,
               count(*) FILTER (WHERE (data->>'error')::boolean) AS errors,
               round(avg((data->>'duration_ms')::numeric), 1) AS avg_ms
        FROM app_logs
        WHERE event = 'tool_result'
        GROUP BY data->>'name'
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW monitoring_tools")
    op.execute("DROP VIEW monitoring_daily")
