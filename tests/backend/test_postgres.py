"""Real PostgreSQL/non-owner RLS tests; enabled with BACKEND_TEST_DATABASE_URL.

The database must be an isolated, migrated synthetic test database, never production.
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from cargopulse_api.config import Settings
from cargopulse_api.db import TENANT_A, TENANT_B, scope, utcnow
from cargopulse_api.main import create_app
from cargopulse_api.tables import AuditRow, JobRow, OutboxRow, PlanRow, SnapshotRow
from cargopulse_api.worker import claim_job, process_one, publish_hints
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, DBAPIError

from .conftest import login, post, scenario

pytestmark = pytest.mark.integration


def isolated_database_urls(raw):
    """Fence destructive resets to the documented dedicated loopback database."""
    try:
        parsed = make_url(raw)
    except ArgumentError:
        raise ValueError("Refuse a URL outside the isolated backend test database") from None
    if (
        parsed.drivername != "postgresql+psycopg"
        or parsed.host != "127.0.0.1"
        or parsed.port != 55432
        or parsed.database != "cargopulse_backend_test"
        or parsed.username != "cargopulse_app"
        or parsed.password is not None
        or parsed.query
    ):
        raise ValueError("Refuse a URL outside the isolated backend test database")
    return raw, parsed.set(username="cargopulse").render_as_string(hide_password=False)


@pytest.fixture
def pg(tmp_path):
    url = os.getenv("BACKEND_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Real PostgreSQL test database is not configured")
    url, owner_url = isolated_database_urls(url)
    owner = create_engine(owner_url)
    with owner.begin() as db:
        db.execute(text("TRUNCATE tenants, oidc_flows RESTART IDENTITY CASCADE"))
    settings = Settings(
        environment="development",
        development_auth=True,
        database_url=url,
        object_root=str(tmp_path),
        app_base_url="http://testserver",
        redis_url="redis://127.0.0.1:56379/0",
    )
    with TestClient(create_app(settings)) as client:
        yield client, owner
    owner.dispose()


def test_nonowner_rls_and_immutable_history(pg):
    client, owner = pg
    record, _ = scenario(client)
    with client.app.state.factory() as db:
        role = db.execute(
            text(
                "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user"
            )
        ).one()
        assert role[0] == "cargopulse_app" and not role[1] and not role[2]
        assert not list(db.scalars(select(SnapshotRow)))  # No tenant context means no rows.
        scope(db, TENANT_B)
        assert not list(db.scalars(select(SnapshotRow)))
        scope(db, TENANT_A)
        snapshot = db.scalar(select(SnapshotRow))
        assert snapshot is not None
        with pytest.raises(DBAPIError):
            db.execute(
                text("UPDATE snapshots SET content_hash=repeat('f',64) WHERE id=:id"),
                {"id": snapshot.id},
            )
        db.rollback()
    with owner.begin() as db:
        with pytest.raises(DBAPIError):
            db.execute(text("UPDATE audit_events SET outcome='TAMPERED'"))
    with owner.begin() as db:
        with pytest.raises(DBAPIError):
            db.execute(
                text("UPDATE scenarios SET version=version+1 WHERE id=:id"), {"id": record["id"]}
            )
    login(client, "controller-b")
    assert client.get(f"/api/v1/scenarios/{record['id']}").status_code == 404


def test_commands_and_worker_do_not_need_tenant_directory_update(pg):
    """Deployment grants keep the tenant/identity directory read-only to the app."""
    client, owner = pg
    with owner.begin() as db:
        db.execute(text("REVOKE INSERT, UPDATE, DELETE ON tenants, identities FROM cargopulse_app"))
    try:
        record, _ = scenario(client)
        job = post(
            client,
            f"/scenarios/{record['id']}/solve",
            {"max_wall_seconds": 10, "compare_baselines": False},
            "readonly-directory",
            record["etag"],
        ).json()
        assert process_one(client.app.state.factory, "readonly-directory-worker")
        result = client.get(f"/api/v1/jobs/{job['id']}")
        assert result.json()["status"] == "COMPLETED", result.text
    finally:
        with owner.begin() as db:
            # Other test fixtures deliberately re-seed their isolated database.
            db.execute(
                text(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON tenants, identities TO cargopulse_app"
                )
            )


def test_worker_rotates_between_tenants_with_fifo_within_each(pg, monkeypatch):
    """A continuously busy tenant cannot take every turn on one worker."""
    from uuid import UUID

    from cargopulse_api.db import DEV_IDENTITIES, seed_development
    from sqlalchemy.orm import sessionmaker

    from packages.domain_fixtures.generator import make_snapshot

    client, owner = pg
    monkeypatch.setitem(DEV_IDENTITIES, "queue-manager-b", (TENANT_B, ["manager"]))
    seed_development(sessionmaker(owner, expire_on_commit=False))

    def queue(identity, tenant, number):
        login(client, identity)
        payload = make_snapshot(8, tenant_id=UUID(tenant)).model_dump(mode="json")
        payload["event_id"] = f"fair-queue-{number}"
        payload["policy"] = client.get("/api/v1/fixtures/recover").json()["policy"]
        batch = post(client, "/imports/validate", {"snapshot": payload}, f"fair-import-{number}")
        assert batch.status_code == 202
        receipt = post(client, f"/imports/{batch.json()['id']}/commit", key=f"fair-commit-{number}")
        record = post(
            client,
            "/scenarios",
            {"source_snapshot_id": receipt.json()["snapshot_id"]},
            f"fair-scenario-{number}",
        ).json()
        job = post(
            client, f"/scenarios/{record['id']}/solve", {}, f"fair-solve-{number}", record["etag"]
        )
        assert job.status_code == 202
        return job.json()["id"]

    first = queue("manager", TENANT_A, 1)
    second = queue("manager", TENANT_A, 2)
    other = queue("queue-manager-b", TENANT_B, 3)
    factory = client.app.state.factory
    assert claim_job(factory, "round-robin-worker") == (TENANT_A, first)
    assert claim_job(factory, "round-robin-worker") == (TENANT_B, other)
    assert claim_job(factory, "round-robin-worker") == (TENANT_A, second)


def test_durable_jobs_broker_loss_and_expired_lease(pg):
    client, _ = pg
    record, _ = scenario(client)
    job = post(client, f"/scenarios/{record['id']}/solve", {}, "solve", record["etag"]).json()
    first = claim_job(client.app.state.factory, "crashed-worker")
    assert first == (TENANT_A, job["id"])
    assert claim_job(client.app.state.factory, "second-worker") is None
    with client.app.state.factory.begin() as db:
        scope(db, TENANT_A)
        row = db.scalar(select(JobRow).where(JobRow.tenant_id == TENANT_A, JobRow.id == job["id"]))
        row.lease_until = utcnow() - timedelta(seconds=1)
    reclaimed = claim_job(client.app.state.factory, "replacement-worker")
    assert reclaimed == first
    with client.app.state.factory() as db:
        scope(db, TENANT_A)
        row = db.scalar(select(JobRow).where(JobRow.tenant_id == TENANT_A, JobRow.id == job["id"]))
        assert row.attempt == 2 and row.lease_owner == "replacement-worker"
        assert (
            db.scalar(select(OutboxRow).where(OutboxRow.tenant_id == TENANT_A)).published_at is None
        )


def test_live_worker_approval_race_and_exports(pg):
    pytest.importorskip("cargopulse_optimizer")
    pytest.importorskip("cargopulse_validation")
    client, _ = pg
    record, _ = scenario(client)
    job = post(client, f"/scenarios/{record['id']}/solve", {}, "solve", record["etag"]).json()
    # The broker is not read by process_one. Losing every Redis hint cannot lose this job.
    publish_hints(client.app.state.factory, "redis://127.0.0.1:56379/0")
    import redis

    broker = redis.Redis.from_url("redis://127.0.0.1:56379/0")
    assert job["id"].encode() in broker.lrange("cargopulse:solve:hints", 0, -1)
    broker.lrem("cargopulse:solve:hints", 0, job["id"])
    assert process_one(client.app.state.factory, "live-integration-worker")
    result = client.get(f"/api/v1/jobs/{job['id']}")
    assert result.json()["status"] == "COMPLETED", result.text
    plan_response = client.get(f"/api/v1/plans/{result.json()['plan_id']}")
    assert plan_response.status_code == 200, plan_response.text
    plan = plan_response.json()
    assert plan["approvable"], plan["blockers"]
    assert plan["plan"]["independent_validation"]["status"] == "PASS"
    with client.app.state.factory() as db:
        scope(db, TENANT_A)
        with pytest.raises(DBAPIError):
            db.execute(
                text("UPDATE solution_plans SET plan_hash=repeat('f',64) WHERE id=:id"),
                {"id": plan["id"]},
            )
        db.rollback()
    alternatives = client.get(f"/api/v1/plans/{plan['id']}/alternatives")
    assert len(alternatives.json()["items"]) == 2
    barrier = threading.Barrier(2)
    body = {
        "action": "APPROVE_IN_APP",
        "reason_code": "REVIEWED_SYNTHETIC",
        "comment": "Reviewed synthetic plan",
        "expected_snapshot_hash": record["snapshot_hash"],
        "expected_plan_hash": plan["plan_hash"],
    }

    def approve(index):
        # Separate HTTP clients/sessions/controllers exercise actual concurrent DB transactions.
        actor = TestClient(client.app)
        login(actor, "controller" if index == 1 else "manager")
        barrier.wait(timeout=10)
        return post(actor, f"/plans/{plan['id']}/decisions", body, f"race-{index}", plan["etag"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(approve, [1, 2]))
    assert sorted(r.status_code for r in results) == [201, 409], [r.text for r in results]
    winner = next(r for r in results if r.status_code == 201)
    assert winner.json()["external_write_performed"] is False
    for format in ("json", "csv", "pdf"):
        exported = client.get(f"/api/v1/reports/{plan['id']}/export?format={format}")
        assert exported.status_code == 200, exported.text
        assert "SYNTHETIC" in exported.text or "synthetic" in exported.text
        if format == "pdf":
            assert exported.content.startswith(b"%PDF-")
    with client.app.state.factory() as db:
        scope(db, TENANT_A)
        assert len(list(db.scalars(select(PlanRow).where(PlanRow.tenant_id == TENANT_A)))) == 3
        assert list(
            db.scalars(
                select(AuditRow).where(AuditRow.tenant_id == TENANT_A, AuditRow.outcome == "DENIED")
            )
        )
    assert process_one(client.app.state.factory, "duplicate-poll") is False


def small_ready_plan(client):
    from packages.domain_fixtures.generator import make_snapshot

    login(client)
    snapshot = make_snapshot(8).model_dump(mode="json")
    snapshot["policy"] = client.get("/api/v1/fixtures/recover").json()["policy"]
    batch = post(client, "/imports/validate", {"snapshot": snapshot}, "small-import").json()
    receipt = post(client, f"/imports/{batch['id']}/commit", key="small-commit").json()
    record = post(
        client, "/scenarios", {"source_snapshot_id": receipt["snapshot_id"]}, "small-scenario"
    ).json()
    job = post(
        client,
        f"/scenarios/{record['id']}/solve",
        {"max_wall_seconds": 10, "compare_baselines": False},
        "small-solve",
        record["etag"],
    ).json()
    assert process_one(client.app.state.factory, "small-worker")
    result = client.get(f"/api/v1/jobs/{job['id']}").json()
    assert result["status"] == "COMPLETED", result
    plan = client.get(f"/api/v1/plans/{result['plan_id']}").json()
    return snapshot, record, plan


def test_new_source_version_invalidates_approval(pg):
    pytest.importorskip("cargopulse_optimizer")
    client, _ = pg
    snapshot, record, plan = small_ready_plan(client)
    assert plan["approvable"], plan
    snapshot["source_version"] += 1
    snapshot["title"] = "New synthetic source version"
    batch = post(client, "/imports/validate", {"snapshot": snapshot}, "new-import").json()
    assert post(client, f"/imports/{batch['id']}/commit", key="new-commit").status_code == 201
    result = post(
        client,
        f"/plans/{plan['id']}/decisions",
        {
            "action": "APPROVE_IN_APP",
            "reason_code": "REVIEWED",
            "comment": "Attempt old proposal",
            "expected_snapshot_hash": record["snapshot_hash"],
            "expected_plan_hash": plan["plan_hash"],
        },
        "stale-decision",
        plan["etag"],
    )
    assert result.status_code == 409 and result.json()["code"] == "STALE_PLAN"
    assert client.get(f"/api/v1/scenarios/{record['id']}").json()["current"] is False
    assert any(x["outcome"] == "DENIED" for x in client.get("/api/v1/audit").json()["items"])


def test_invalid_solver_output_is_quarantined(pg, monkeypatch):
    optimizer = pytest.importorskip("cargopulse_optimizer")
    original = optimizer.run_solver

    def corrupt(snapshot, max_wall_seconds):
        plan = original(snapshot, max_wall_seconds=max_wall_seconds)
        assert plan.assignments
        return plan.model_copy(update={"assignments": plan.assignments + [plan.assignments[0]]})

    monkeypatch.setattr(optimizer, "run_solver", corrupt)
    client, _ = pg
    _, record, plan = small_ready_plan(client)
    assert plan["state"] == "QUARANTINED" and not plan["approvable"]
    assert plan["plan"]["independent_validation"]["status"] == "FAIL"
    job = client.get(f"/api/v1/jobs/{plan['job_id']}").json()
    assert job["error_code"] == "INDEPENDENT_VALIDATION_FAILED"
    assert client.get(f"/api/v1/scenarios/{record['id']}").json()["state"] == "SOLVER_ERROR"
