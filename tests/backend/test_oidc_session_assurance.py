"""Verified RSA OIDC assurance survives role changes; transport is recorded, not live."""

import runpy
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from cargopulse_api.tables import Identity, SessionRow
from cargopulse_contracts import canonical_hash
from sqlalchemy import select, text

from .test_oidc import ISSUER, begin
from .test_oidc import provider as provider

PRIVILEGED = ("controller", "manager", "data_steward", "tenant_admin")


def set_roles(client, roles):
    with client.app.state.factory.begin() as db:
        db.get(Identity, "manager").roles = roles


def sign_in(client, provider):
    state = begin(client, provider)
    response = client.get(
        "https://testserver/api/v1/auth/callback",
        params={"code": "recorded-code", "state": state},
        follow_redirects=False,
    )
    assert response.status_code == 302, response.text
    return client.cookies.get("cp_session")


def draft(client, policy, key):
    return client.post(
        "/api/v1/policies/drafts",
        json={"policy": policy},
        headers={
            "Origin": "http://testserver",
            "X-CSRF-Token": client.cookies.get("cp_csrf"),
            "Idempotency-Key": key,
        },
    )


@pytest.mark.parametrize("role", PRIVILEGED)
def test_weak_session_role_promotion_requires_strong_reauthentication(client, provider, role):
    set_roles(client, ["load_analyst"])
    provider["mutations"] = {"acr": "password-only"}
    old_cookie = sign_in(client, provider)
    policy = client.get("/api/v1/fixtures/recover").json()["policy"]
    assert draft(client, policy, "before-promotion").status_code == 403

    set_roles(client, [role])
    denied = draft(client, policy, "after-promotion")
    assert denied.status_code == 401, denied.text
    assert denied.json()["code"] == "MFA_REQUIRED"
    assert client.cookies.get("cp_session") == old_cookie
    assert provider["exchanges"] == 1
    assert client.get("/api/v1/me").status_code == 401

    # A new verified strong exchange rotates the cookie and restores the live role.
    provider["mutations"] = {}
    assert sign_in(client, provider) != old_cookie
    assert provider["exchanges"] == 2
    assert client.get("/api/v1/me").json()["roles"] == [role]
    # Only the manager grant authorizes this particular write.
    expected = 201 if role == "manager" else 403
    assert draft(client, policy, "after-reauthentication").status_code == expected
    with client.app.state.factory() as db:
        rows = list(db.scalars(select(SessionRow)))
        assert len(rows) == 1
        assert rows[0].authentication_context_hash == canonical_hash(
            {"issuer": ISSUER, "acr": "urn:approved:mfa"}
        )


def test_already_strong_nonprivileged_session_can_be_promoted(client, provider):
    set_roles(client, ["load_analyst"])
    old_cookie = sign_in(client, provider)
    policy = client.get("/api/v1/fixtures/recover").json()["policy"]
    set_roles(client, ["manager"])
    assert draft(client, policy, "strong-promotion").status_code == 201
    assert client.cookies.get("cp_session") == old_cookie
    assert provider["exchanges"] == 1


def test_legacy_null_context_privileged_session_requires_reauthentication(client, provider):
    sign_in(client, provider)
    with client.app.state.factory.begin() as db:
        db.scalar(select(SessionRow)).authentication_context_hash = None
    denied = client.get("/api/v1/me")
    assert denied.status_code == 401
    assert denied.json()["code"] == "MFA_REQUIRED"
    assert provider["exchanges"] == 1


@pytest.mark.parametrize(
    "setting,value",
    [
        ("oidc_required_acr", "urn:approved:stronger-mfa"),
        ("oidc_required_acr", ""),
        ("oidc_issuer", "https://replacement-idp.example"),
    ],
)
def test_changed_oidc_policy_rejects_stale_privileged_assurance(client, provider, setting, value):
    sign_in(client, provider)
    object.__setattr__(client.app.state.settings, setting, value)
    denied = client.get("/api/v1/me")
    assert denied.status_code == 401
    assert denied.json()["code"] == "MFA_REQUIRED"
    assert provider["exchanges"] == 1


@pytest.mark.parametrize("missing_claim", [False, True])
def test_no_acr_nonprivileged_session_reads_but_cannot_gain_privilege(
    client, provider, monkeypatch, missing_claim
):
    set_roles(client, ["load_analyst"])
    provider["mutations"] = {"acr": None}
    if missing_claim:
        # Preserve real signing while omitting the claim from the recorded token.
        from cargopulse_api import security

        encode = security.jwt.encode

        def without_acr(claims, *args, **kwargs):
            claims = {key: value for key, value in claims.items() if key != "acr"}
            return encode(claims, *args, **kwargs)

        monkeypatch.setattr(security.jwt, "encode", without_acr)
    sign_in(client, provider)
    assert client.get("/api/v1/me").status_code == 200
    with client.app.state.factory() as db:
        assert db.scalar(select(SessionRow)).authentication_context_hash == canonical_hash(
            {"issuer": ISSUER, "acr": None}
        )
    set_roles(client, ["manager"])
    denied = client.get("/api/v1/me")
    assert denied.status_code == 401
    assert denied.json()["code"] == "MFA_REQUIRED"


def test_token_claim_roles_and_tenant_do_not_grant_local_privileges(client, provider):
    set_roles(client, ["load_analyst"])
    provider["mutations"] = {
        "acr": "password-only",
        "roles": ["tenant_admin", "manager"],
        "tenant_id": "20000000-0000-4000-8000-000000000002",
    }
    sign_in(client, provider)
    me = client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["roles"] == ["load_analyst"]
    assert me.json()["tenant_id"] == "10000000-0000-4000-8000-000000000001"


def test_missing_assurance_column_is_not_ready_and_upgrade_keeps_legacy_null(client, provider):
    sign_in(client, provider)
    # Only this fixture's in-memory SQLite database is changed. This does not
    # establish PostgreSQL migration, RLS or production readiness behavior.
    with client.app.state.factory.begin() as db:
        db.execute(text("DROP TRIGGER identities_revoke_disabled_sessions"))
        db.execute(text("ALTER TABLE sessions DROP COLUMN authentication_context_hash"))
    ready = client.get("/api/v1/health/ready")
    assert ready.status_code == 503
    assert ready.json()["dependencies"]["database"] == "unavailable"

    migration = runpy.run_path(
        str(Path(__file__).resolve().parents[2] / "services/api/alembic/versions/0005_session_assurance.py")
    )
    with client.app.state.factory.begin() as db:
        with Operations.context(MigrationContext.configure(db.connection())):
            migration["upgrade"]()
        assert db.scalar(select(SessionRow)).authentication_context_hash is None
    ready = client.get("/api/v1/health/ready")
    assert ready.status_code == 200, ready.text
    assert client.get("/api/v1/me").json()["code"] == "MFA_REQUIRED"
    with client.app.state.factory.begin() as db:
        update_enabled(db, False)
        assert db.scalar(select(SessionRow)) is None
    with pytest.raises(RuntimeError, match="downgrade is unsafe"):
        migration["downgrade"]()


@pytest.mark.parametrize("acr", [2, 2.5, True, ["mfa"], {"method": "mfa"}])
def test_nonstring_acr_cannot_collide_with_configured_string_after_promotion(client, provider, acr):
    set_roles(client, ["load_analyst"])
    provider["mutations"] = {"acr": acr}
    sign_in(client, provider)
    assert client.get("/api/v1/me").status_code == 200
    object.__setattr__(client.app.state.settings, "oidc_required_acr", str(acr))
    set_roles(client, ["manager"])
    denied = client.get("/api/v1/me")
    assert denied.status_code == 401, denied.text
    assert denied.json()["code"] == "MFA_REQUIRED"
    with client.app.state.factory() as db:
        assert db.scalar(select(SessionRow)).authentication_context_hash == canonical_hash(
            {"issuer": ISSUER, "acr": None}
        )


def update_enabled(db, enabled):
    db.execute(
        text("UPDATE identities SET enabled=:enabled WHERE id=:identity AND tenant_id=:tenant"),
        {
            "enabled": enabled,
            "identity": "manager",
            "tenant": "10000000-0000-4000-8000-000000000001",
        },
    )


@pytest.mark.parametrize("request_while_disabled", [False, True])
def test_raw_sql_disable_and_reenable_permanently_revokes_old_cookie(
    client, provider, request_while_disabled
):
    old_cookie = sign_in(client, provider)
    with client.app.state.factory.begin() as db:
        update_enabled(db, False)
    if request_while_disabled:
        assert client.get("/api/v1/me").status_code == 401
    with client.app.state.factory.begin() as db:
        update_enabled(db, True)
    assert client.cookies.get("cp_session") == old_cookie
    denied = client.get("/api/v1/me")
    assert denied.status_code == 401, denied.text
    assert denied.json()["code"] == "UNAUTHENTICATED"
    assert provider["exchanges"] == 1
    assert sign_in(client, provider) != old_cookie
    assert client.get("/api/v1/me").status_code == 200


def test_disable_revokes_all_identity_sessions_and_preserves_other_identities_and_tenant(
    client, provider
):
    from cargopulse_api.security import create_session
    from fastapi import Response

    sign_in(client, provider)
    with client.app.state.factory.begin() as db:
        for identity_id in ("manager", "manager", "controller", "controller-b"):
            create_session(
                db, db.get(Identity, identity_id), "development", Response(), client.app.state.settings
            )
    with client.app.state.factory() as db:
        rows = list(db.scalars(select(SessionRow)))
        assert len(rows) == 5
        expected_survivors = {row.id for row in rows if row.identity_id != "manager"}
        assert len(expected_survivors) == 2
    with client.app.state.factory.begin() as db:
        update_enabled(db, False)
        assert {row.id for row in db.scalars(select(SessionRow))} == expected_survivors
    with client.app.state.factory() as db:
        assert {row.id for row in db.scalars(select(SessionRow))} == expected_survivors


def test_disable_session_revocation_rolls_back_atomically(client, provider):
    sign_in(client, provider)
    with client.app.state.factory() as db:
        update_enabled(db, False)
        assert db.scalar(select(SessionRow)) is None
        db.rollback()
    with client.app.state.factory() as db:
        assert db.get(Identity, "manager").enabled is True
        assert db.scalar(select(SessionRow)) is not None
    assert client.get("/api/v1/me").status_code == 200


def test_disabled_identity_cannot_create_a_session_from_a_stale_orm_instance(client):
    from cargopulse_api.security import AppError, create_session
    from fastapi import Response

    with client.app.state.factory.begin() as db:
        stale_identity = db.get(Identity, "manager")
        update_enabled(db, False)
        assert stale_identity.enabled is True
        with pytest.raises(AppError) as denied:
            create_session(
                db, stale_identity, "development", Response(), client.app.state.settings
            )
        assert denied.value.status == 401
        assert db.scalar(select(SessionRow)) is None


@pytest.mark.parametrize("acr", ["password-only", "urn:approved:mfa"])
def test_session_creation_rechecks_fresh_roles_and_oidc_assurance(client, provider, acr):
    from cargopulse_api.security import AppError, create_session
    from fastapi import Response

    set_roles(client, ["load_analyst"])
    with client.app.state.factory.begin() as db:
        stale_identity = db.get(Identity, "manager")
        db.execute(
            text("UPDATE identities SET roles=:roles WHERE id=:identity AND tenant_id=:tenant"),
            {
                "roles": '["manager"]',
                "identity": "manager",
                "tenant": stale_identity.tenant_id,
            },
        )
        assert stale_identity.roles == ["load_analyst"]
        args = (db, stale_identity, "oidc", Response(), client.app.state.settings)
        context = canonical_hash({"issuer": ISSUER, "acr": acr})
        if acr == "password-only":
            with pytest.raises(AppError) as denied:
                create_session(*args, authentication_context_hash=context)
            assert denied.value.status == 401
            assert denied.value.code == "MFA_REQUIRED"
            assert db.scalar(select(SessionRow)) is None
        else:
            principal = create_session(*args, authentication_context_hash=context)
            assert principal.roles == ["manager"]
            db.flush()
            assert db.scalar(select(SessionRow)).authentication_context_hash == context
