"""Independent tests use real PostgreSQL with a non-owner app role."""

from datetime import timedelta

from cargopulse_api.db import TENANT_A, scope, utcnow
from cargopulse_api.tables import JobRow, PlanRow
from cargopulse_api.worker import claim_job, process_one
from sqlalchemy import select

from .conftest import login, post


def queued(client):
    from packages.domain_fixtures.generator import make_snapshot

    login(client)
    snapshot = make_snapshot(8).model_dump(mode="json")
    snapshot["policy"] = client.get("/api/v1/fixtures/recover").json()["policy"]
    batch = post(client, "/imports/validate", {"snapshot": snapshot}, "import").json()
    receipt = post(client, f"/imports/{batch['id']}/commit", key="commit").json()
    record = post(
        client, "/scenarios", {"source_snapshot_id": receipt["snapshot_id"]}, "scenario"
    ).json()
    response = post(
        client,
        f"/scenarios/{record['id']}/solve",
        {"max_wall_seconds": 10, "compare_baselines": False},
        "solve",
        record["etag"],
    )
    assert response.status_code == 202, response.text
    return record, response.json()


def expire(factory, job_id):
    with factory.begin() as db:
        scope(db, TENANT_A)
        db.get(JobRow, job_id).lease_until = utcnow() - timedelta(seconds=1)


def test_reclaimed_worker_cannot_persist_after_losing_fence(pg_client, monkeypatch):
    import cargopulse_optimizer

    record, job = queued(pg_client)
    factory = pg_client.app.state.factory
    original = cargopulse_optimizer.run_solver
    triggered = False

    def interrupted(snapshot, max_wall_seconds):
        nonlocal triggered
        result = original(snapshot, max_wall_seconds=max_wall_seconds)
        if not triggered:
            triggered = True
            expire(factory, job["id"])
            assert claim_job(factory, "replacement") == (TENANT_A, job["id"])
        return result

    monkeypatch.setattr(cargopulse_optimizer, "run_solver", interrupted)
    assert process_one(factory, "original")
    with factory() as db:
        scope(db, TENANT_A)
        assert not list(db.scalars(select(PlanRow)))
        assert db.get(JobRow, job["id"]).lease_owner == "replacement"
    expire(factory, job["id"])
    assert process_one(factory, "final")
    with factory() as db:
        scope(db, TENANT_A)
        assert len(list(db.scalars(select(PlanRow)))) == 1
        row = db.get(JobRow, job["id"])
        assert row.status == "COMPLETED" and row.attempt == 3


def test_exhausted_lease_retries_leave_scenario_recoverable(pg_client):
    record, job = queued(pg_client)
    factory = pg_client.app.state.factory
    for index in range(3):
        assert claim_job(factory, f"crash-{index}") == (TENANT_A, job["id"])
        expire(factory, job["id"])
    assert claim_job(factory, "exhausted") is None
    result = pg_client.get(f"/api/v1/jobs/{job['id']}").json()
    assert result["status"] == "FAILED" and result["error_code"] == "LEASE_RETRY_EXHAUSTED"
    scenario = pg_client.get(f"/api/v1/scenarios/{record['id']}").json()
    response = post(
        pg_client,
        f"/scenarios/{record['id']}/solve",
        {"compare_baselines": False},
        "retry",
        scenario["etag"],
    )
    assert response.status_code == 202, {
        "scenario_state": scenario["state"],
        "retry": response.json(),
    }
