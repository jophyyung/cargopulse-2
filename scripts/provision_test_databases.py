"""Provision only the explicitly isolated loopback PostgreSQL test databases."""

import os

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql

DATABASES = (
    "cargopulse_backend_test",
    "cargopulse_releaseqa_test",
    "cargopulse_observability_backend_test",
)
with psycopg.connect(
    "host=127.0.0.1 port=55432 dbname=postgres user=cargopulse", autocommit=True
) as conn:
    if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname='cargopulse_app'").fetchone():
        conn.execute("CREATE ROLE cargopulse_app LOGIN NOSUPERUSER NOBYPASSRLS")
    for name in DATABASES:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
            conn.execute(
                sql.SQL("CREATE DATABASE {} OWNER cargopulse").format(sql.Identifier(name))
            )
for name in DATABASES:
    os.environ["DATABASE_URL"] = f"postgresql+psycopg://cargopulse@127.0.0.1:55432/{name}"
    command.upgrade(Config("services/api/alembic.ini"), "head")
    with psycopg.connect(f"host=127.0.0.1 port=55432 dbname={name} user=cargopulse") as conn:
        conn.execute("GRANT USAGE ON SCHEMA public TO cargopulse_app")
        conn.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO cargopulse_app"
        )
print("Prepared three isolated test databases; no application database was modified.")
