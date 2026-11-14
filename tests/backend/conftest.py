"""Isolated file-backed SQLite tests are not PostgreSQL/RLS/concurrency proof."""
import pytest
from cargopulse_api.config import Settings
from cargopulse_api.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    settings = Settings(environment="development", development_auth=True, auto_create=True,
        # Concurrent requests need independent connections. An in-memory StaticPool
        # shares one transaction across threads and can produce spurious auth failures.
        database_url=f"sqlite:///{tmp_path / 'backend.sqlite'}", object_root=str(tmp_path / "objects"),
        app_base_url="http://testserver", redis_url="redis://127.0.0.1:56379/0")
    with TestClient(create_app(settings)) as c:
        yield c


def login(client, identity="manager"):
    result = client.post("/api/v1/auth/development", json={"identity_id": identity},
                         headers={"Origin": "http://testserver"})
    assert result.status_code == 200, result.text
    client.headers.update({"Origin": "http://testserver",
        "X-CSRF-Token": client.cookies.get("cp_csrf")})
    return result.json()


def post(client, path, body=None, key="test-key", etag=None):
    headers = {"Idempotency-Key": key}
    if etag:
        headers["If-Match"] = etag
    return client.post("/api/v1" + path, json=body, headers=headers)


def scenario(client):
    login(client)
    snapshot = client.get("/api/v1/fixtures/recover").json()
    result = post(client, "/imports/validate", {"snapshot": snapshot})
    assert result.status_code == 202, result.text
    receipt = post(client, f"/imports/{result.json()['id']}/commit", key="commit")
    assert receipt.status_code == 201, receipt.text
    result = post(client, "/scenarios", {"source_snapshot_id": receipt.json()["snapshot_id"]}, key="scenario")
    assert result.status_code == 201, result.text
    return result.json(), snapshot
