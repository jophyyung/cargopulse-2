"""Independent release QA: ephemeral SQLite unless a separate PG URL is provided."""

import pytest
from cargopulse_api.config import Settings
from cargopulse_api.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        environment="development",
        development_auth=True,
        auto_create=True,
        database_url="sqlite:///:memory:",
        object_root=str(tmp_path / "objects"),
        app_base_url="http://testserver",
        redis_url="redis://127.0.0.1:56379/0",
    )
    with TestClient(create_app(settings)) as c:
        yield c


def login(client, actor="manager"):
    response = client.post(
        "/api/v1/auth/development",
        json={"identity_id": actor},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200, response.text
    client.headers.update(
        {"Origin": "http://testserver", "X-CSRF-Token": client.cookies.get("cp_csrf")}
    )


def post(client, path, body=None, key="qa", etag=None):
    headers = {"Idempotency-Key": key}
    if etag:
        headers["If-Match"] = etag
    return client.post("/api/v1" + path, json=body, headers=headers)


def ready(client, snapshot=None, require_approvable=True):
    from cargopulse_api.worker import process_one

    from packages.domain_fixtures.generator import make_snapshot

    login(client)
    if snapshot is None:
        snapshot = make_snapshot(8).model_dump(mode="json")
        snapshot["policy"] = client.get("/api/v1/fixtures/recover").json()["policy"]
    batch = post(client, "/imports/validate", {"snapshot": snapshot}, "import")
    assert batch.status_code == 202, batch.text
    receipt = post(client, f"/imports/{batch.json()['id']}/commit", key="commit")
    assert receipt.status_code == 201, receipt.text
    record = post(
        client, "/scenarios", {"source_snapshot_id": receipt.json()["snapshot_id"]}, "scenario"
    ).json()
    job = post(
        client,
        f"/scenarios/{record['id']}/solve",
        {"max_wall_seconds": 10, "compare_baselines": False},
        "solve",
        record["etag"],
    )
    assert job.status_code == 202, job.text
    assert process_one(client.app.state.factory, "independent-qa")
    job = client.get(f"/api/v1/jobs/{job.json()['id']}").json()
    assert job["status"] == "COMPLETED", job
    plan = client.get(f"/api/v1/plans/{job['plan_id']}").json()
    if require_approvable:
        assert plan["approvable"], plan
    return record, plan


def decision(client, record, plan, key="decision", **updates):
    body = {
        "action": "APPROVE_IN_APP",
        "reason_code": "QA_REVIEW",
        "comment": "Synthetic QA only",
        "expected_snapshot_hash": record["snapshot_hash"],
        "expected_plan_hash": plan["plan_hash"],
        **updates,
    }
    return post(client, f"/plans/{plan['id']}/decisions", body, key, plan["etag"])


@pytest.fixture
def pg_client(tmp_path):
    """Only the QA-owned database is truncated; never backend_test or main."""
    from cargopulse_api.db import seed_development
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    owner_url = "postgresql+psycopg://cargopulse@127.0.0.1:55432/cargopulse_releaseqa_test"
    owner = create_engine(owner_url)
    with owner.begin() as db:
        name = db.scalar(text("SELECT current_database()"))
        assert name == "cargopulse_releaseqa_test"
        db.execute(text("TRUNCATE tenants, oidc_flows RESTART IDENTITY CASCADE"))
        db.execute(text("GRANT USAGE ON SCHEMA public TO cargopulse_app"))
        db.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO cargopulse_app"
            )
        )
    seed_development(sessionmaker(owner))
    with owner.begin() as db:
        db.execute(text("REVOKE INSERT, UPDATE, DELETE ON tenants, identities FROM cargopulse_app"))
    settings = Settings(
        environment="development",
        development_auth=True,
        database_url=owner_url.replace("cargopulse@", "cargopulse_app@"),
        object_root=str(tmp_path / "objects"),
        app_base_url="http://testserver",
    )
    with TestClient(create_app(settings)) as c:
        yield c
    owner.dispose()
