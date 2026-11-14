"""Preserve OIDC assurance and revoke sessions transactionally on account disable."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    # Legacy rows deliberately remain NULL: past MFA evidence cannot be fabricated.
    op.add_column(
        "sessions", sa.Column("authentication_context_hash", sa.String(64), nullable=True)
    )
    # Keep migration DDL independent of current ORM model definitions.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
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
        """)
    elif op.get_bind().dialect.name == "sqlite":
        op.execute("""
            CREATE TRIGGER IF NOT EXISTS identities_revoke_disabled_sessions
            AFTER UPDATE OF enabled ON identities
            FOR EACH ROW WHEN OLD.enabled = 1 AND NEW.enabled = 0
            BEGIN
              DELETE FROM sessions WHERE identity_id = OLD.id AND tenant_id = OLD.tenant_id;
            END;
        """)


def downgrade():
    raise RuntimeError(
        "Session assurance downgrade is unsafe; restore into a separate database "
        "and require fresh sign-in"
    )
