"""Add one-time OIDC flows, immutable records and tenant row security.

Run as schema owner, then run the application as a separate non-owner role.
A database superuser/owner can bypass or alter these controls.
"""
from alembic import op
from cargopulse_api.runtime_tables import OIDCFlow

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SCOPED = ["identities", "sessions", "ingest_batches", "snapshots", "policy_sets", "scenarios",
          "solve_jobs", "solution_plans", "plan_decisions", "outbox_events", "idempotency_keys", "audit_events"]


def upgrade():
    bind = op.get_bind()
    OIDCFlow.__table__.create(bind=bind, checkfirst=True)
    if bind.dialect.name != "postgresql":
        return
    op.execute("""
        CREATE OR REPLACE FUNCTION cargopulse_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'immutable CargoPulse record'; END $$;
    """)
    for table in ("snapshots", "plan_decisions", "audit_events"):
        op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
                   "FOR EACH ROW EXECUTE FUNCTION cargopulse_immutable()")
    op.execute("""
        CREATE OR REPLACE FUNCTION cargopulse_published_policy_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          IF OLD.state = 'PUBLISHED' THEN RAISE EXCEPTION 'published policy is immutable'; END IF;
          IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER policy_sets_immutable BEFORE UPDATE OR DELETE ON policy_sets
        FOR EACH ROW EXECUTE FUNCTION cargopulse_published_policy_immutable();
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION cargopulse_plan_payload_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          IF TG_OP = 'DELETE' OR NEW.payload IS DISTINCT FROM OLD.payload
             OR NEW.plan_hash <> OLD.plan_hash OR NEW.job_id <> OLD.job_id
             OR NEW.tenant_id <> OLD.tenant_id OR NEW.scenario_id <> OLD.scenario_id
             OR NEW.scenario_version <> OLD.scenario_version OR NEW.policy_name <> OLD.policy_name
             OR NEW.created_at <> OLD.created_at
          THEN RAISE EXCEPTION 'plan content is immutable'; END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER solution_plans_payload_immutable BEFORE UPDATE OR DELETE ON solution_plans
        FOR EACH ROW EXECUTE FUNCTION cargopulse_plan_payload_immutable();
    """)
    for table in SCOPED:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {table} USING "
                   "(tenant_id = current_setting('app.current_tenant', true)) WITH CHECK "
                   "(tenant_id = current_setting('app.current_tenant', true))")
    # Roles are intentionally provisioned outside migration: never grant privileged role creation
    # to a production application. Example grants are in the backend runbook.


def downgrade():
    raise RuntimeError("Security/immutable-history downgrade is unsafe; restore into a separate database")
