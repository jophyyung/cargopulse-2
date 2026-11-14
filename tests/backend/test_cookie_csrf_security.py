"""ASGI cookie flags and CSRF behavior; not real TLS, browser or enterprise IdP acceptance.

The fixture starts an isolated SQLite development app, then selects production
request settings for cookie tests. It does not validate production infrastructure.
OIDC uses the existing recorded transport and actual RSA-signed JWTs.
"""

from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie

import pytest
from cargopulse_api.security import digest
from cargopulse_api.tables import SessionRow
from fastapi.testclient import TestClient
from sqlalchemy import select

from .conftest import login
from .test_oidc import begin
from .test_oidc import provider as provider


@pytest.fixture
def production_mode(client, provider):
    settings = client.app.state.settings
    object.__setattr__(settings, "environment", "production")
    object.__setattr__(settings, "development_auth", False)
    object.__setattr__(settings, "app_base_url", "https://testserver")
    object.__setattr__(settings, "oidc_redirect_uri", "https://testserver/api/v1/auth/callback")
    client.base_url = "https://testserver"
    return client


def cookies(response):
    result = {}
    for header in response.headers.get_list("set-cookie"):
        parsed = SimpleCookie()
        parsed.load(header)
        result.update(parsed)
    return result


def finish_login(client, provider):
    state = begin(client, provider)
    result = client.get(
        "https://testserver/api/v1/auth/callback",
        params={"code": "recorded-code", "state": state},
        follow_redirects=False,
    )
    assert result.status_code == 302, result.text
    return result


def csrf_hash(client):
    with client.app.state.factory() as db:
        return db.scalar(select(SessionRow)).csrf_hash


def test_production_cookie_prefixes_flags_and_logout_deletion(production_mode, provider):
    client = production_mode
    result = finish_login(client, provider)
    issued = cookies(result)
    for name, httponly, samesite in (
        ("__Host-cp_session", True, "lax"),
        ("__Host-cp_csrf", False, "strict"),
    ):
        cookie = issued[name]
        assert cookie["secure"] is True
        assert bool(cookie["httponly"]) is httponly
        assert cookie["path"] == "/" and cookie["domain"] == ""
        assert cookie["samesite"] == samesite
        assert int(cookie["max-age"]) > 0
    deleted_binding = issued["__Secure-cp_oidc_binding"]
    assert deleted_binding["secure"] is True and deleted_binding["httponly"] is True
    assert deleted_binding["path"] == "/api/v1/auth/callback"
    assert deleted_binding["domain"] == "" and deleted_binding["max-age"] == "0"
    assert client.get("/api/v1/me").status_code == 200
    token = client.get("/api/v1/auth/csrf").json()["csrf"]
    response = client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "https://testserver", "X-CSRF-Token": token},
    )
    assert response.status_code == 200, response.text
    deleted = cookies(response)
    for name in ("__Host-cp_session", "__Host-cp_csrf"):
        assert deleted[name]["secure"] is True
        assert deleted[name]["path"] == "/" and deleted[name]["domain"] == ""
        assert deleted[name]["max-age"] == "0"
    assert deleted["__Host-cp_session"]["httponly"] is True
    assert client.get("/api/v1/me").status_code == 401


def test_production_rejects_unprefixed_session_fallback(production_mode, provider):
    client = production_mode
    finish_login(client, provider)
    token = client.cookies.get("__Host-cp_session")
    client.cookies.clear()
    response = client.get("/api/v1/me", headers={"Cookie": "cp_session=" + token})
    assert response.status_code == 401


def test_production_oidc_binding_prefix_and_no_unprefixed_fallback(production_mode, provider):
    client = production_mode
    state = begin(client, provider)
    binding = next(cookie for cookie in client.cookies.jar if cookie.name == "__Secure-cp_oidc_binding")
    assert binding.secure is True
    assert binding.path == "/api/v1/auth/callback"
    assert binding.domain_specified is False
    assert binding.has_nonstandard_attr("HttpOnly")
    value = binding.value
    client.cookies.clear()
    denied = client.get(
        "/api/v1/auth/callback",
        params={"code": "recorded-code", "state": state},
        headers={"Cookie": "cp_oidc_binding=" + value},
        follow_redirects=False,
    )
    assert denied.status_code == 401
    assert provider["exchanges"] == 0


def test_production_oidc_reauthentication_rotates_selected_cookie(production_mode, provider):
    client = production_mode
    finish_login(client, provider)
    old = client.cookies.get("__Host-cp_session")
    finish_login(client, provider)
    assert client.cookies.get("__Host-cp_session") != old
    assert client.get("/api/v1/me", headers={"Cookie": "__Host-cp_session=" + old}).status_code == 401
    assert client.get("/api/v1/me").status_code == 200
    with client.app.state.factory() as db:
        assert len(list(db.scalars(select(SessionRow)))) == 1


def test_development_cookie_exception_keeps_local_names(client, provider):
    response = client.post(
        "/api/v1/auth/development",
        json={"identity_id": "manager"},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200
    issued = cookies(response)
    assert set(issued) == {"cp_session", "cp_csrf"}
    assert issued["cp_session"]["secure"] == ""
    assert issued["cp_csrf"]["secure"] == ""
    assert issued["cp_session"]["httponly"] is True
    begin(client, provider)
    assert client.cookies.get("cp_oidc_binding")
    assert not client.cookies.get("__Secure-cp_oidc_binding")


@pytest.mark.parametrize("production", [False, True])
def test_repeated_csrf_get_is_stable_and_does_not_update_hash(client, provider, production):
    if production:
        object.__setattr__(client.app.state.settings, "environment", "production")
        object.__setattr__(client.app.state.settings, "development_auth", False)
        client.base_url = "https://testserver"
        finish_login(client, provider)
        cookie_name = "__Host-cp_csrf"
    else:
        login(client)
        cookie_name = "cp_csrf"
    original = client.cookies.get(cookie_name)
    before = csrf_hash(client)
    for _ in range(3):
        result = client.get("/api/v1/auth/csrf")
        assert result.status_code == 200
        assert result.json()["csrf"] == original
        assert csrf_hash(client) == before


def test_concurrent_csrf_reads_do_not_invalidate_an_existing_token(client):
    login(client)
    original = client.cookies.get("cp_csrf")
    session = client.cookies.get("cp_session")
    before = csrf_hash(client)

    def read(_):
        actor = TestClient(client.app)
        result = actor.get("/api/v1/auth/csrf", headers={"Cookie": "cp_session=" + session})
        assert result.status_code == 200, result.text
        return result.json()["csrf"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        tokens = list(pool.map(read, range(12)))
    assert tokens == [original] * 12
    assert csrf_hash(client) == before
    policy = client.get("/api/v1/fixtures/recover").json()["policy"]
    result = client.post(
        "/api/v1/policies/drafts",
        json={"policy": policy},
        headers={"Idempotency-Key": "unchanged-csrf", "X-CSRF-Token": original},
    )
    assert result.status_code == 201, result.text


def test_csrf_get_rederives_token_after_cookie_deletion(client):
    login(client)
    original = client.cookies.get("cp_csrf")
    before = csrf_hash(client)
    client.cookies.delete("cp_csrf")
    result = client.get("/api/v1/auth/csrf")
    assert result.status_code == 200
    assert result.json()["csrf"] == original
    assert client.cookies.get("cp_csrf") == original
    assert csrf_hash(client) == before


def test_legacy_random_csrf_is_reused_only_with_matching_cookie(client):
    login(client)
    legacy = "legacy-random-token-not-derived-from-session"
    with client.app.state.factory.begin() as db:
        db.scalar(select(SessionRow)).csrf_hash = digest(legacy)
    before = csrf_hash(client)
    session = client.cookies.get("cp_session")
    result = client.get(
        "/api/v1/auth/csrf",
        headers={"Cookie": "cp_session=" + session + "; cp_csrf=" + legacy},
    )
    assert result.status_code == 200
    assert result.json()["csrf"] == legacy
    assert csrf_hash(client) == before


@pytest.mark.parametrize("cookie", ["", "; cp_csrf=wrong-legacy-token"])
def test_legacy_random_csrf_without_matching_cookie_requires_signin(client, cookie):
    login(client)
    with client.app.state.factory.begin() as db:
        db.scalar(select(SessionRow)).csrf_hash = digest("legacy-random-token")
    before = csrf_hash(client)
    session = client.cookies.get("cp_session")
    denied = client.get("/api/v1/auth/csrf", headers={"Cookie": "cp_session=" + session + cookie})
    assert denied.status_code == 401
    assert csrf_hash(client) == before


def test_anonymous_csrf_read_fails_closed(client):
    assert client.get("/api/v1/auth/csrf").status_code == 401
