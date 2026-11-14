"""Real PostgreSQL session revocation, least-privilege and transaction ordering."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from cargopulse_api.db import TENANT_A, TENANT_B, scope
from cargopulse_api.security import AppError, create_session
from cargopulse_api.tables import Identity
from fastapi import Response
from psycopg import sql
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from .conftest import login
from .test_postgres import pg as pg

pytestmark = pytest.mark.integration


@pytest.fixture
def directory_readonly(pg):
    client, owner = pg
    with owner.begin() as db:
        db.execute(text("REVOKE INSERT,UPDATE,DELETE ON tenants,identities FROM cargopulse_app"))
    try:
        yield client, owner
    finally:
        with owner.begin() as db:
            # The isolated fixture needs these grants to seed its next empty DB.
            db.execute(text("GRANT SELECT,INSERT,UPDATE,DELETE ON tenants,identities TO cargopulse_app"))


def scoped(connection, tenant=TENANT_A):
    connection.execute(text("SELECT set_config('app.current_tenant',:tenant,true)"), {"tenant": tenant})


def set_enabled(owner, enabled):
    with owner.begin() as db:
        scoped(db)
        db.execute(text("UPDATE identities SET enabled=:value WHERE id='manager'"), {"value": enabled})


def session_counts(owner):
    with owner.connect() as db:
        return dict(db.execute(text("SELECT identity_id,count(*) FROM sessions GROUP BY identity_id")).all())


def waiting_for_advisory(owner, pid):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with owner.connect() as db:
            if db.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_locks WHERE pid=:pid AND locktype='advisory' AND NOT granted)"), {"pid": pid}):
                return True
        time.sleep(0.02)
    return False


def test_real_upgrade_preserves_legacy_null_and_rejects_security_downgrade(pg, monkeypatch):
    client, owner = pg
    login(client)
    with owner.begin() as db:
        scoped(db)
        db.execute(text("UPDATE sessions SET auth_mode='oidc' WHERE identity_id='manager'"))
        db.execute(text("DROP TRIGGER identities_revoke_disabled_sessions ON identities"))
        db.execute(text("DROP FUNCTION public.cargopulse_revoke_disabled_identity_sessions()"))
        db.execute(text("ALTER TABLE sessions DROP COLUMN authentication_context_hash"))
        db.execute(text("UPDATE alembic_version SET version_num='0004'"))
    assert client.get("/api/v1/health/ready").status_code == 503
    monkeypatch.setenv("DATABASE_URL", owner.url.render_as_string(hide_password=False))
    config = Config(str(Path(__file__).resolve().parents[2] / "services/api/alembic.ini"))
    command.upgrade(config, "0005")
    with owner.connect() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0005"
        assert db.scalar(text("SELECT authentication_context_hash FROM sessions WHERE identity_id='manager'")) is None
        function = db.execute(text("SELECT prosecdef,provolatile,proconfig FROM pg_proc WHERE proname='cargopulse_revoke_disabled_identity_sessions'" )).one()
        assert function[0] is False and function[1] == "v"
        assert function[2] == ["search_path=pg_catalog"]
    assert client.get("/api/v1/health/ready").status_code == 200
    assert client.get("/api/v1/me").json()["code"] == "MFA_REQUIRED"
    with pytest.raises(RuntimeError, match="downgrade is unsafe"):
        command.downgrade(config, "0004")
    with owner.connect() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0005"
    login(client)
    assert client.get("/api/v1/me").status_code == 200


def test_raw_sql_disable_terminates_all_sessions_and_is_transactional(directory_readonly):
    client, owner = directory_readonly
    login(client)
    old_cookie = client.cookies.get("cp_session")
    client.cookies.clear()
    login(client)
    client.cookies.clear()
    login(client, "steward")
    client.cookies.clear()
    login(client, "controller-b")
    before = session_counts(owner)
    assert before == {"manager": 2, "steward": 1, "controller-b": 1}
    connection = owner.connect()
    transaction = connection.begin()
    scoped(connection)
    connection.execute(text("UPDATE identities SET enabled=false WHERE id='manager'"))
    assert connection.scalar(text("SELECT count(*) FROM sessions WHERE identity_id='manager'")) == 0
    transaction.rollback()
    connection.close()
    assert session_counts(owner) == before
    set_enabled(owner, False)
    set_enabled(owner, True)  # No authentication request occurs while disabled.
    assert session_counts(owner) == {"steward": 1, "controller-b": 1}
    assert client.get("/api/v1/me").json()["tenant_id"] == TENANT_B
    client.cookies.clear()
    client.cookies.set("cp_session", old_cookie)
    assert client.get("/api/v1/me").status_code == 401
    with client.app.state.factory.begin() as db:
        scope(db, TENANT_A)
        assert db.scalar(text("SELECT has_table_privilege(current_user,'identities','UPDATE')")) is False


def test_invoker_revocation_obeys_operator_privileges_and_rls(directory_readonly):
    client, owner = directory_readonly
    login(client)
    role = "cp_session_operator_" + uuid4().hex
    identifier = sql.Identifier(role).as_string()
    with owner.begin() as db:
        db.exec_driver_sql(f"CREATE ROLE {identifier} NOLOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT")
    try:
        with owner.begin() as db:
            db.exec_driver_sql(f"GRANT USAGE ON SCHEMA public TO {identifier}")
            db.exec_driver_sql(f"GRANT SELECT,UPDATE(enabled) ON identities TO {identifier}")
        with pytest.raises(DBAPIError) as failure:
            with owner.begin() as db:
                db.exec_driver_sql(f"SET LOCAL ROLE {identifier}")
                scoped(db)
                db.execute(text("UPDATE identities SET enabled=false WHERE id='manager'"))
        assert failure.value.orig.sqlstate == "42501"
        assert session_counts(owner)["manager"] == 1
        assert client.get("/api/v1/me").status_code == 200
        with owner.begin() as db:
            db.exec_driver_sql(f"GRANT SELECT,DELETE ON sessions TO {identifier}")
        with owner.begin() as db:
            db.exec_driver_sql(f"SET LOCAL ROLE {identifier}")
            scoped(db, TENANT_B)
            assert db.execute(text("UPDATE identities SET enabled=false WHERE id='manager'")).rowcount == 0
            scoped(db)
            assert db.execute(text("UPDATE identities SET enabled=false WHERE id='manager'")).rowcount == 1
        assert session_counts(owner) == {}
        set_enabled(owner, True)
        assert client.get("/api/v1/me").status_code == 401
    finally:
        with owner.begin() as db:
            db.exec_driver_sql(f"DROP OWNED BY {identifier}")
            db.exec_driver_sql(f"DROP ROLE {identifier}")


@pytest.mark.parametrize("first", ["authentication", "disable"])
def test_session_creation_and_disable_serialize_without_directory_update(directory_readonly, first):
    client, owner = directory_readonly
    held, release, contender_started = threading.Event(), threading.Event(), threading.Event()
    pids = {}

    def authentication():
        with client.app.state.factory.begin() as db:
            scope(db, TENANT_A)
            identity = db.scalar(select(Identity).where(Identity.id == "manager"))
            pids["authentication"] = db.scalar(text("SELECT pg_backend_pid()"))
            assert db.scalar(text("SELECT has_table_privilege(current_user,'identities','UPDATE')")) is False
            if first == "disable":
                assert held.wait(5)
                contender_started.set()
            try:
                create_session(db, identity, "development", Response(), client.app.state.settings)
                db.flush()
            except AppError as error:
                assert first == "disable" and error.status == 401
                return "rejected"
            if first == "authentication":
                held.set()
                assert release.wait(5)
            return "created"

    def disable():
        with owner.begin() as db:
            pids["disable"] = db.scalar(text("SELECT pg_backend_pid()"))
            scoped(db)
            if first == "authentication":
                assert held.wait(5)
                contender_started.set()
            db.execute(text("UPDATE identities SET enabled=false WHERE id='manager'"))
            if first == "disable":
                held.set()
                assert release.wait(5)

    with ThreadPoolExecutor(max_workers=2) as pool:
        leading = pool.submit(authentication if first == "authentication" else disable)
        try:
            assert held.wait(5)
            following = pool.submit(disable if first == "authentication" else authentication)
            assert contender_started.wait(5)
            contender = "disable" if first == "authentication" else "authentication"
            assert waiting_for_advisory(owner, pids[contender])
        finally:
            release.set()
        leading.result(timeout=5)
        following.result(timeout=5)
    assert session_counts(owner).get("manager", 0) == 0
    set_enabled(owner, True)
    assert session_counts(owner).get("manager", 0) == 0
