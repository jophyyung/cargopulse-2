"""Initial storage contract. Immutable graph snapshots retain exact piece mappings.

PostgreSQL is the release database. SQLite is permitted only for fast unit tests;
its passing results do not establish PostgreSQL concurrency or RLS behavior.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    DDL,
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

Payload = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    synthetic_only: Mapped[bool] = mapped_column(Boolean, default=True)


class Scoped:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)


class Identity(Scoped, Base):
    __tablename__ = "identities"
    __table_args__ = (UniqueConstraint("tenant_id", "issuer", "subject"),)
    issuer: Mapped[str] = mapped_column(String(300))
    subject: Mapped[str] = mapped_column(String(200))
    roles: Mapped[list] = mapped_column(Payload)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class SessionRow(Scoped, Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    identity_id: Mapped[str] = mapped_column(ForeignKey("identities.id"))
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    auth_mode: Mapped[str] = mapped_column(String(20))
    authentication_context_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


# Metadata creation is a development/test adapter. Production installs the same
# transactional revocation semantics through the immutable 0005 migration.
event.listen(
    Base.metadata,
    "after_create",
    DDL("""
        CREATE TRIGGER IF NOT EXISTS identities_revoke_disabled_sessions
        AFTER UPDATE OF enabled ON identities
        FOR EACH ROW WHEN OLD.enabled = 1 AND NEW.enabled = 0
        BEGIN
          DELETE FROM sessions WHERE identity_id = OLD.id AND tenant_id = OLD.tenant_id;
        END;
    """).execute_if(dialect="sqlite"),
)
event.listen(
    Base.metadata,
    "after_create",
    DDL("""
        CREATE OR REPLACE FUNCTION public.cargopulse_revoke_disabled_identity_sessions()
        RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog AS $$
        BEGIN
          PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(OLD.tenant_id, 0));
          DELETE FROM public.sessions WHERE identity_id = OLD.id AND tenant_id = OLD.tenant_id;
          RETURN NEW;
        END $$;
        CREATE OR REPLACE TRIGGER identities_revoke_disabled_sessions
        AFTER UPDATE OF enabled ON public.identities
        FOR EACH ROW WHEN (OLD.enabled IS TRUE AND NEW.enabled IS FALSE)
        EXECUTE FUNCTION public.cargopulse_revoke_disabled_identity_sessions();
    """).execute_if(dialect="postgresql"),
)


class ImportBatch(Scoped, Base):
    __tablename__ = "ingest_batches"
    __table_args__ = (UniqueConstraint("tenant_id", "content_sha256"),)
    content_sha256: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[str] = mapped_column(String(100))
    object_key: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict] = mapped_column(Payload)
    quality_issues: Mapped[list] = mapped_column(Payload)
    row_errors: Mapped[list] = mapped_column(Payload)
    snapshot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SnapshotRow(Scoped, Base):
    __tablename__ = "snapshots"
    __table_args__ = (UniqueConstraint("tenant_id", "source_id", "event_id", "source_version"),)
    source_id: Mapped[str] = mapped_column(String(100))
    event_id: Mapped[str] = mapped_column(String(100))
    source_version: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(Payload)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PolicyRow(Scoped, Base):
    __tablename__ = "policy_sets"
    __table_args__ = (UniqueConstraint("tenant_id", "policy_hash"),)
    policy_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict] = mapped_column(Payload)
    authored_by: Mapped[str] = mapped_column(String(200))
    reviewed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ScenarioRow(Scoped, Base):
    __tablename__ = "scenarios"
    __table_args__ = (UniqueConstraint("tenant_id", "snapshot_id"),)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.id"))
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("scenarios.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer)
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    policy_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(30))
    current: Mapped[bool] = mapped_column(Boolean, default=True)
    quality_issues: Mapped[list] = mapped_column(Payload)
    latest_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    latest_plan_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class JobRow(Scoped, Base):
    __tablename__ = "solve_jobs"
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenarios.id"), index=True)
    scenario_version: Mapped[int] = mapped_column(Integer)
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    policy_hash: Mapped[str] = mapped_column(String(64))
    requested_by: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), index=True)
    progress: Mapped[int] = mapped_column(Integer)
    attempt: Mapped[int] = mapped_column(Integer)
    max_wall_seconds: Mapped[int] = mapped_column(Integer)
    compare_baselines: Mapped[bool] = mapped_column(Boolean)
    lease_owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    plan_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    trace_context: Mapped[dict | None] = mapped_column(Payload, nullable=True)


class PlanRow(Scoped, Base):
    __tablename__ = "solution_plans"
    __table_args__ = (UniqueConstraint("job_id", "policy_name"),)
    job_id: Mapped[str] = mapped_column(ForeignKey("solve_jobs.id"), index=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenarios.id"))
    scenario_version: Mapped[int] = mapped_column(Integer)
    policy_name: Mapped[str] = mapped_column(String(40))
    plan_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(Payload)
    state: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DecisionRow(Scoped, Base):
    __tablename__ = "plan_decisions"
    plan_id: Mapped[str] = mapped_column(ForeignKey("solution_plans.id"), unique=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenarios.id"), unique=True)
    payload: Mapped[dict] = mapped_column(Payload)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OutboxRow(Scoped, Base):
    __tablename__ = "outbox_events"
    job_id: Mapped[str] = mapped_column(ForeignKey("solve_jobs.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_attempts: Mapped[int] = mapped_column(Integer, default=0)


class IdempotencyRow(Scoped, Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("tenant_id", "actor", "operation", "key"),)
    actor: Mapped[str] = mapped_column(String(200))
    operation: Mapped[str] = mapped_column(String(200))
    key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(Payload)
    status_code: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditRow(Scoped, Base):
    __tablename__ = "audit_events"
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(30))
    correlation_id: Mapped[str] = mapped_column(String(100))
    previous_hash: Mapped[str] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64))
    details: Mapped[str] = mapped_column(Text, default="")
