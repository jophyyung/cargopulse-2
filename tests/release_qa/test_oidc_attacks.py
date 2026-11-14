"""Additional crypto-backed OIDC attacks using recorded provider transport."""

from tests.backend.test_oidc import begin
from tests.backend.test_oidc import provider as oidc_provider  # noqa: F401 - pytest fixture


def test_single_audience_wrong_authorized_party_is_rejected(client, oidc_provider):  # noqa: F811 - imported pytest fixture
    state = begin(client, oidc_provider)
    oidc_provider["mutations"] = {"azp": "different-client"}
    response = client.get(
        "https://testserver/api/v1/auth/callback",
        params={"code": "recorded", "state": state},
        follow_redirects=False,
    )
    assert response.status_code in (401, 403), response.text


def test_claimed_tenant_roles_and_disabled_local_grants_never_authorize(client, oidc_provider):  # noqa: F811 - imported pytest fixture
    from cargopulse_api.tables import Identity

    state = begin(client, oidc_provider)
    oidc_provider["mutations"] = {
        "roles": ["tenant_admin", "controller"],
        "tenant_id": "10000000-0000-4000-8000-000000000002",
    }
    response = client.get(
        "https://testserver/api/v1/auth/callback",
        params={"code": "recorded", "state": state},
        follow_redirects=False,
    )
    assert response.status_code == 302, response.text
    principal = client.get("/api/v1/me").json()
    assert principal["tenant_id"] == "10000000-0000-4000-8000-000000000001"
    assert principal["roles"] == ["manager"]
    with client.app.state.factory.begin() as db:
        db.get(Identity, "manager").enabled = False
    assert client.get("/api/v1/me").status_code == 401
    state = begin(client, oidc_provider)
    response = client.get(
        "https://testserver/api/v1/auth/callback",
        params={"code": "recorded", "state": state},
        follow_redirects=False,
    )
    assert response.status_code == 403
