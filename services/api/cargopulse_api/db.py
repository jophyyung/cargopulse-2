"""Database transactions and tenant context. PostgreSQL is the authority."""

from datetime import datetime, timezone
from functools import lru_cache

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from . import runtime_tables  # noqa: F401
from .tables import Base, Identity, PolicyRow, Tenant

TENANT_A = "10000000-0000-4000-8000-000000000001"
TENANT_B = "10000000-0000-4000-8000-000000000002"
DEV_IDENTITIES = {
    "controller": (TENANT_A, ["controller", "load_analyst"]),
    "steward": (TENANT_A, ["data_steward"]),
    "manager": (TENANT_A, ["manager"]),
    "manager-reviewer": (TENANT_A, ["manager"]),
    "auditor": (TENANT_A, ["auditor"]),
    "controller-b": (TENANT_B, ["controller", "load_analyst"]),
}


def utcnow():
    return datetime.now(timezone.utc)


def aware(value):
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def configure(settings, telemetry=None):
    opts = {"pool_pre_ping": True}
    if settings.database_url.startswith("sqlite"):
        opts["connect_args"] = {"check_same_thread": False}
        if ":memory:" in settings.database_url:
            opts["poolclass"] = StaticPool
    engine = create_engine(settings.database_url, **opts)
    from .storage import PrivateObjects

    factory = sessionmaker(
        engine,
        expire_on_commit=False,
        info={
            "objects": PrivateObjects(settings),
            "telemetry": telemetry,
            "max_pending_jobs": settings.max_pending_jobs,
            "development_seed_allowed": settings.environment == "development",
        },
    )
    if settings.auto_create:
        if settings.environment != "development":
            raise RuntimeError("Schema auto-create is development-only; run Alembic")
        Base.metadata.create_all(engine)
    return engine, factory


def scope(db, tenant_id):
    db.info["tenant_id"] = str(tenant_id)
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT set_config('app.current_tenant', :tenant, true)"),
            {"tenant": str(tenant_id)},
        )


def lock_tenant(db, tenant_id):
    """Serialize tenant command/audit chains without granting tenant-table UPDATE.

    Hash collisions cause unnecessary serialization only. The lock is transactional
    and independent of canonical data, so a read-only tenant directory remains safe.
    SQLite's transaction behavior is used only by the fast test profile.
    """
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:tenant, 0))"),
            {"tenant": str(tenant_id)},
        )


@lru_cache(maxsize=1)
def development_policy():
    from packages.domain_fixtures.generator import make_snapshot

    return make_snapshot(1, as_of=datetime(2026, 11, 9, tzinfo=timezone.utc)).policy


def seed_development(factory):
    with factory.begin() as db:
        for tenant in (TENANT_A, TENANT_B):
            if not db.get(Tenant, tenant):
                db.add(Tenant(id=tenant, name="Synthetic " + tenant[-1], synthetic_only=True))
        db.flush()
        # Fixed code-owned development rules, never derived from an upload.
        # Production has no automatic policy publication or development seed.
        from cargopulse_contracts import canonical_hash

        policy = development_policy()
        for tenant in (TENANT_A, TENANT_B):
            scope(db, tenant)
            existing = db.scalar(
                select(PolicyRow).where(
                    PolicyRow.tenant_id == tenant, PolicyRow.policy_hash == canonical_hash(policy)
                )
            )
            if not existing:
                db.add(
                    PolicyRow(
                        tenant_id=tenant,
                        policy_hash=canonical_hash(policy),
                        state="PUBLISHED",
                        payload=policy.model_dump(mode="json"),
                        authored_by=policy.authored_by,
                        reviewed_by=policy.approved_by,
                        created_at=utcnow(),
                    )
                )
        db.flush()
        for name, (tenant, roles) in DEV_IDENTITIES.items():
            scope(db, tenant)
            if not db.get(Identity, name):
                db.add(
                    Identity(
                        id=name,
                        tenant_id=tenant,
                        issuer="development",
                        subject=name,
                        roles=roles,
                        enabled=True,
                    )
                )
