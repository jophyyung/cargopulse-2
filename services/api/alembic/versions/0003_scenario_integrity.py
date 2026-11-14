"""Protect immutable scenario revision identity and all plan content fields."""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""
        CREATE OR REPLACE FUNCTION cargopulse_scenario_revision_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          IF TG_OP = 'DELETE' OR NEW.id <> OLD.id OR NEW.tenant_id <> OLD.tenant_id
             OR NEW.snapshot_id <> OLD.snapshot_id OR NEW.snapshot_hash <> OLD.snapshot_hash
             OR NEW.policy_hash <> OLD.policy_hash OR NEW.version <> OLD.version
             OR NEW.parent_id IS DISTINCT FROM OLD.parent_id
             OR NEW.quality_issues IS DISTINCT FROM OLD.quality_issues
             OR NEW.created_at <> OLD.created_at
          THEN RAISE EXCEPTION 'scenario revision is immutable'; END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER scenarios_revision_immutable BEFORE UPDATE OR DELETE ON scenarios
        FOR EACH ROW EXECUTE FUNCTION cargopulse_scenario_revision_immutable();
        CREATE OR REPLACE FUNCTION cargopulse_plan_payload_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          IF TG_OP = 'DELETE' OR NEW.id <> OLD.id OR NEW.payload IS DISTINCT FROM OLD.payload
             OR NEW.plan_hash <> OLD.plan_hash OR NEW.job_id <> OLD.job_id
             OR NEW.tenant_id <> OLD.tenant_id OR NEW.scenario_id <> OLD.scenario_id
             OR NEW.scenario_version <> OLD.scenario_version OR NEW.policy_name <> OLD.policy_name
             OR NEW.created_at <> OLD.created_at
          THEN RAISE EXCEPTION 'plan content is immutable'; END IF;
          RETURN NEW;
        END $$;
    """)


def downgrade():
    raise RuntimeError("Immutable revision downgrade is unsafe; restore into a separate database")
