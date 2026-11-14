"""Frozen initial tenant-scoped storage contract.

Keep this historical DDL independent of runtime ORM metadata. New columns belong
in later migrations, so a fresh database follows the same history as an upgrade.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("synthetic_only", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "audit_events",
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=200), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=100), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_events_tenant_id"), "audit_events", ["tenant_id"], unique=False)
    op.create_table(
        "idempotency_keys",
        sa.Column("actor", sa.String(length=200), nullable=False),
        sa.Column("operation", sa.String(length=200), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "response",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "actor", "operation", "key"),
    )
    op.create_index(
        op.f("ix_idempotency_keys_tenant_id"), "idempotency_keys", ["tenant_id"], unique=False
    )
    op.create_table(
        "identities",
        sa.Column("issuer", sa.String(length=300), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column(
            "roles",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "issuer", "subject"),
    )
    op.create_index(op.f("ix_identities_tenant_id"), "identities", ["tenant_id"], unique=False)
    op.create_table(
        "ingest_batches",
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=100), nullable=False),
        sa.Column("object_key", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "quality_issues",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "row_errors",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "content_sha256"),
    )
    op.create_index(
        op.f("ix_ingest_batches_tenant_id"), "ingest_batches", ["tenant_id"], unique=False
    )
    op.create_table(
        "policy_sets",
        sa.Column("policy_hash", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("authored_by", sa.String(length=200), nullable=False),
        sa.Column("reviewed_by", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "policy_hash"),
    )
    op.create_index(op.f("ix_policy_sets_tenant_id"), "policy_sets", ["tenant_id"], unique=False)
    op.create_table(
        "snapshots",
        sa.Column("source_id", sa.String(length=100), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "source_id", "event_id", "source_version"),
    )
    op.create_index(op.f("ix_snapshots_tenant_id"), "snapshots", ["tenant_id"], unique=False)
    op.create_table(
        "scenarios",
        sa.Column("snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("policy_hash", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("current", sa.Boolean(), nullable=False),
        sa.Column(
            "quality_issues",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("latest_job_id", sa.String(length=36), nullable=True),
        sa.Column("latest_plan_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["scenarios.id"],
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["snapshots.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "snapshot_id"),
    )
    op.create_index(op.f("ix_scenarios_tenant_id"), "scenarios", ["tenant_id"], unique=False)
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("identity_id", sa.String(length=36), nullable=False),
        sa.Column("csrf_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("auth_mode", sa.String(length=20), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["identity_id"],
            ["identities.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_sessions_tenant_id"), "sessions", ["tenant_id"], unique=False)
    op.create_table(
        "solve_jobs",
        sa.Column("scenario_id", sa.String(length=36), nullable=False),
        sa.Column("scenario_version", sa.Integer(), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("policy_hash", sa.String(length=64), nullable=False),
        sa.Column("requested_by", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("max_wall_seconds", sa.Integer(), nullable=False),
        sa.Column("compare_baselines", sa.Boolean(), nullable=False),
        sa.Column("lease_owner", sa.String(length=100), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("plan_id", sa.String(length=36), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenarios.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_solve_jobs_scenario_id"), "solve_jobs", ["scenario_id"], unique=False)
    op.create_index(op.f("ix_solve_jobs_status"), "solve_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_solve_jobs_tenant_id"), "solve_jobs", ["tenant_id"], unique=False)
    op.create_table(
        "outbox_events",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_attempts", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["solve_jobs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index(
        op.f("ix_outbox_events_tenant_id"), "outbox_events", ["tenant_id"], unique=False
    )
    op.create_table(
        "solution_plans",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("scenario_id", sa.String(length=36), nullable=False),
        sa.Column("scenario_version", sa.Integer(), nullable=False),
        sa.Column("policy_name", sa.String(length=40), nullable=False),
        sa.Column("plan_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["solve_jobs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenarios.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "policy_name"),
    )
    op.create_index(op.f("ix_solution_plans_job_id"), "solution_plans", ["job_id"], unique=False)
    op.create_index(
        op.f("ix_solution_plans_tenant_id"), "solution_plans", ["tenant_id"], unique=False
    )
    op.create_table(
        "plan_decisions",
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("scenario_id", sa.String(length=36), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["solution_plans.id"],
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenarios.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id"),
        sa.UniqueConstraint("scenario_id"),
    )
    op.create_index(
        op.f("ix_plan_decisions_tenant_id"), "plan_decisions", ["tenant_id"], unique=False
    )


def downgrade():
    op.drop_index(op.f("ix_plan_decisions_tenant_id"), table_name="plan_decisions")
    op.drop_table("plan_decisions")
    op.drop_index(op.f("ix_solution_plans_tenant_id"), table_name="solution_plans")
    op.drop_index(op.f("ix_solution_plans_job_id"), table_name="solution_plans")
    op.drop_table("solution_plans")
    op.drop_index(op.f("ix_outbox_events_tenant_id"), table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_index(op.f("ix_solve_jobs_tenant_id"), table_name="solve_jobs")
    op.drop_index(op.f("ix_solve_jobs_status"), table_name="solve_jobs")
    op.drop_index(op.f("ix_solve_jobs_scenario_id"), table_name="solve_jobs")
    op.drop_table("solve_jobs")
    op.drop_index(op.f("ix_sessions_tenant_id"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_index(op.f("ix_scenarios_tenant_id"), table_name="scenarios")
    op.drop_table("scenarios")
    op.drop_index(op.f("ix_snapshots_tenant_id"), table_name="snapshots")
    op.drop_table("snapshots")
    op.drop_index(op.f("ix_policy_sets_tenant_id"), table_name="policy_sets")
    op.drop_table("policy_sets")
    op.drop_index(op.f("ix_ingest_batches_tenant_id"), table_name="ingest_batches")
    op.drop_table("ingest_batches")
    op.drop_index(op.f("ix_identities_tenant_id"), table_name="identities")
    op.drop_table("identities")
    op.drop_index(op.f("ix_idempotency_keys_tenant_id"), table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
    op.drop_index(op.f("ix_audit_events_tenant_id"), table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("tenants")
