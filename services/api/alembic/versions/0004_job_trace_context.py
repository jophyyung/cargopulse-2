"""Persist optional W3C trace context across the durable job boundary."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "solve_jobs",
        sa.Column("trace_context", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=True),
    )


def downgrade():
    op.drop_column("solve_jobs", "trace_context")
