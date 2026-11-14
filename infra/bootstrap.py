"""One-shot local Compose migration/role bootstrap, never a production installer."""

import os
import subprocess
import sys

from cargopulse_api.db import seed_development
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

if os.environ.get("APP_ENV") != "development":
    raise SystemExit("Production bootstrap requires the separately reviewed provisioning runbook")
subprocess.run(
    [sys.executable, "-m", "alembic", "-c", "services/api/alembic.ini", "upgrade", "head"],
    check=True,
)
engine = create_engine(os.environ["DATABASE_URL"])
seed_development(sessionmaker(engine, expire_on_commit=False))
with engine.begin() as conn:
    # Psycopg SQL composables quote the random password without emitting it.
    from psycopg import sql

    if not conn.scalar(text("SELECT 1 FROM pg_roles WHERE rolname='cargopulse_app'")):
        conn.exec_driver_sql("CREATE ROLE cargopulse_app LOGIN NOSUPERUSER NOBYPASSRLS")
    conn.connection.driver_connection.cursor().execute(
        sql.SQL("ALTER ROLE cargopulse_app PASSWORD {} ").format(
            sql.Literal(os.environ["POSTGRES_PASSWORD"])
        )
    )
    conn.exec_driver_sql("GRANT USAGE ON SCHEMA public TO cargopulse_app")
    conn.exec_driver_sql(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO cargopulse_app"
    )
    conn.exec_driver_sql(
        "REVOKE UPDATE, DELETE ON snapshots, plan_decisions, audit_events FROM cargopulse_app"
    )
    conn.exec_driver_sql("REVOKE INSERT, UPDATE, DELETE ON tenants, identities FROM cargopulse_app")
    conn.exec_driver_sql("REVOKE ALL ON alembic_version FROM cargopulse_app")
engine.dispose()
print("Migrated and provisioned the synthetic development stack; credentials were not logged.")
