"""Real JWT cryptography with recorded OIDC transport. This is not a live IdP test."""
from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cargopulse_api import security
from cargopulse_api.db import utcnow
from cargopulse_api.runtime_tables import OIDCFlow
from cargopulse_api.tables import Identity
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

ISSUER = "https://approved-idp.example"


@pytest.fixture
def provider(client, monkeypatch):
    settings = client.app.state.settings
    for name, value in {"oidc_issuer": ISSUER, "oidc_client_id": "cargo-client",
                         "oidc_required_acr": "urn:approved:mfa"}.items():
        object.__setattr__(settings, name, value)
    monkeypatch.setenv("OIDC_TENANT_ID", "10000000-0000-4000-8000-000000000001")
    metadata = {"issuer": ISSUER, "authorization_endpoint": ISSUER + "/authorize",
                "token_endpoint": ISSUER + "/token", "jwks_uri": ISSUER + "/keys"}
    monkeypatch.setattr(security, "oidc_metadata", lambda _: metadata)
    with client.app.state.factory.begin() as db:
        row = db.get(Identity, "manager")
        row.issuer = ISSUER
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    public.update(kid="rotation-1", alg="RS256", use="sig")
    state = {"key": key, "public": public, "mutations": {}, "exchanges": 0}
    real_jwk = jwt.PyJWKClient

    class RecordedJWKS(real_jwk):
        def fetch_data(self):
            return {"keys": [state["public"]]}
    monkeypatch.setattr(security.jwt, "PyJWKClient", RecordedJWKS)

    class RecordedTransport:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, data, auth):
            assert url == metadata["token_endpoint"]
            with client.app.state.factory() as db:
                assert db.scalar(select(OIDCFlow)) is None  # State consumed before exchange.
            assert data["code_verifier"] == state["verifier"]
            now = utcnow()
            claims = {"iss": ISSUER, "sub": "manager", "aud": "cargo-client", "iat": now,
                      "exp": now + timedelta(minutes=5), "nonce": state["nonce"],
                      "acr": "urn:approved:mfa", **state["mutations"]}
            token = jwt.encode(claims, state["key"], algorithm="RS256", headers={"kid": state["public"]["kid"]})
            state["exchanges"] += 1
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"id_token": token})
    monkeypatch.setattr(security.httpx, "Client", RecordedTransport)
    return state


def begin(client, provider):
    response = client.get("https://testserver/api/v1/auth/login", follow_redirects=False)
    assert response.status_code == 302
    args = parse_qs(urlparse(response.headers["location"]).query)
    assert args["code_challenge_method"] == ["S256"]
    assert args["acr_values"] == ["urn:approved:mfa"]
    with client.app.state.factory() as db:
        flow = db.scalar(select(OIDCFlow))
        provider["nonce"], provider["verifier"] = flow.nonce, flow.verifier
    return args["state"][0]


def test_oidc_signature_pkce_nonce_locally_provisioned_roles_and_replay(client, provider):
    state = begin(client, provider)
    response = client.get("https://testserver/api/v1/auth/callback", params={"code": "recorded-code", "state": state},
                          follow_redirects=False)
    assert response.status_code == 302, response.text
    me = client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["auth_mode"] == "oidc" and me.json()["roles"] == ["manager"]
    replay = client.get("https://testserver/api/v1/auth/callback", params={"code": "recorded-code", "state": state},
                        follow_redirects=False)
    assert replay.status_code == 401 and provider["exchanges"] == 1


@pytest.mark.parametrize("mutation", [
    {"nonce": "forged"}, {"aud": "other-client"}, {"iss": "https://untrusted.example"},
    {"exp": 1}, {"acr": "password-only"}, {"sub": "not-provisioned"},
    {"aud": ["cargo-client", "other"], "azp": "other"},
])
def test_oidc_invalid_tokens_fail_closed(client, provider, mutation):
    state = begin(client, provider)
    provider["mutations"] = mutation
    result = client.get("https://testserver/api/v1/auth/callback", params={"code": "recorded-code", "state": state},
                        follow_redirects=False)
    assert result.status_code in (401, 403), result.text
    assert client.get("/api/v1/me").status_code == 401


def test_oidc_browser_binding_and_state_fail_closed(client, provider):
    state = begin(client, provider)
    client.cookies.delete("cp_oidc_binding")
    result = client.get("https://testserver/api/v1/auth/callback", params={"code": "recorded-code", "state": state},
                        follow_redirects=False)
    assert result.status_code == 401
    assert provider["exchanges"] == 0


def test_oidc_key_rotation_accepts_new_jwks_key(client, provider):
    for index in range(2):
        if index:
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            public = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
            public.update(kid="rotation-2", alg="RS256", use="sig")
            provider.update(key=key, public=public)
        state = begin(client, provider)
        result = client.get("https://testserver/api/v1/auth/callback", params={"code": "recorded-code", "state": state},
                            follow_redirects=False)
        assert result.status_code == 302, result.text


def test_oidc_bad_signature_and_expired_state(client, provider):
    state = begin(client, provider)
    provider["key"] = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    result = client.get("https://testserver/api/v1/auth/callback", params={"code": "recorded-code", "state": state},
                        follow_redirects=False)
    assert result.status_code == 401
    state = begin(client, provider)
    with client.app.state.factory.begin() as db:
        flow = db.scalar(select(OIDCFlow))
        flow.expires_at = utcnow() - timedelta(seconds=1)
    before = provider["exchanges"]
    result = client.get("https://testserver/api/v1/auth/callback", params={"code": "recorded-code", "state": state},
                        follow_redirects=False)
    assert result.status_code == 401 and provider["exchanges"] == before
