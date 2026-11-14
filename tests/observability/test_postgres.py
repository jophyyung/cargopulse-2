"""Real PostgreSQL migration history and cross-process durable trace continuity.

Only OBSERVABILITY_TEST_DATABASE_URL explicitly pointing to this lane's disposable
observability_backend_test database enables destructive schema reset in these tests.
"""

import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from cargopulse_api.config import Settings
from cargopulse_api.db import TENANT_A, scope, utcnow
from cargopulse_api.main import create_app
from cargopulse_api.observability import Telemetry
from cargopulse_api.tables import Base, JobRow, ScenarioRow, SnapshotRow, Tenant
from cargopulse_api.worker import observe_queue
from cargopulse_contracts import canonical_hash
from fastapi.testclient import TestClient
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from sqlalchemy import create_engine, insert, inspect, select, text
from sqlalchemy.engine import make_url

from packages.domain_fixtures.generator import make_snapshot
from tests.backend.conftest import login, post

from .conftest import attributes, metrics, spans

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def database_urls():
    url = os.getenv("OBSERVABILITY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Isolated observability PostgreSQL database is not configured")
    parsed = make_url(url)
    if (
        parsed.database != "cargopulse_observability_backend_test"
        or parsed.username != "cargopulse_app"
        or parsed.host != "127.0.0.1"
        or parsed.port != 55432
    ):
        raise RuntimeError("Refuse any database outside this isolated observability lane")
    return url, url.replace("cargopulse_app@", "cargopulse@")


def migrate(owner_url, revision, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", owner_url)
    command.upgrade(Config(str(ROOT / "services/api/alembic.ini")), revision)


def grant_application(owner):
    with owner.begin() as db:
        db.execute(text("GRANT USAGE ON SCHEMA public TO cargopulse_app"))
        db.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO cargopulse_app"
            )
        )


@pytest.mark.parametrize("existing", [False, True])
def test_frozen_0001_and_upgrade_existing_0003(database_urls, monkeypatch, existing):
    _, owner_url = database_urls
    owner = create_engine(owner_url)
    with owner.begin() as db:
        db.execute(text("DROP SCHEMA public CASCADE"))
        db.execute(text("CREATE SCHEMA public AUTHORIZATION cargopulse"))
    migrate(owner_url, "0001", monkeypatch)
    initial = inspect(owner)
    assert "trace_context" not in {c["name"] for c in initial.get_columns("solve_jobs")}
    assert "oidc_flows" not in initial.get_table_names()
    # Every historical column/index/unique key is explicit and remains aligned
    # with the baseline contract while the ORM includes later additive columns.
    later_columns = {
        "solve_jobs": {"trace_context"},
        "sessions": {"authentication_context_hash"},
    }
    for table in Base.metadata.sorted_tables:
        if table.name == "oidc_flows":
            continue
        expected = set(table.columns.keys()) - later_columns.get(table.name, set())
        assert {c["name"] for c in initial.get_columns(table.name)} == expected
        assert {
            i["name"] for i in initial.get_indexes(table.name) if not i.get("duplicates_constraint")
        } == {i.name for i in table.indexes}
    migrate(owner_url, "0003", monkeypatch)
    assert "trace_context" not in {c["name"] for c in inspect(owner).get_columns("solve_jobs")}
    assert "oidc_flows" in inspect(owner).get_table_names()
    if existing:
        snapshot = make_snapshot(8)
        now = utcnow()
        with owner.begin() as db:
            db.execute(
                insert(Tenant), [{"id": TENANT_A, "name": "Synthetic", "synthetic_only": True}]
            )
            db.execute(
                insert(SnapshotRow),
                [
                    {
                        "id": "10000000-0000-4000-9000-000000000001",
                        "tenant_id": TENANT_A,
                        "source_id": "synthetic",
                        "event_id": "synthetic",
                        "source_version": 1,
                        "content_hash": canonical_hash(snapshot),
                        "payload": snapshot.model_dump(mode="json"),
                        "created_at": now,
                    }
                ],
            )
            db.execute(
                insert(ScenarioRow),
                [
                    {
                        "id": "10000000-0000-4000-9000-000000000002",
                        "tenant_id": TENANT_A,
                        "snapshot_id": "10000000-0000-4000-9000-000000000001",
                        "version": 1,
                        "snapshot_hash": canonical_hash(snapshot),
                        "policy_hash": canonical_hash(snapshot.policy),
                        "state": "SOLVING",
                        "current": True,
                        "quality_issues": [],
                        "created_at": now,
                    }
                ],
            )
            db.execute(
                insert(JobRow),
                [
                    {
                        "id": "10000000-0000-4000-9000-000000000003",
                        "tenant_id": TENANT_A,
                        "scenario_id": "10000000-0000-4000-9000-000000000002",
                        "scenario_version": 1,
                        "snapshot_hash": canonical_hash(snapshot),
                        "policy_hash": canonical_hash(snapshot.policy),
                        "requested_by": "synthetic",
                        "status": "QUEUED",
                        "progress": 0,
                        "attempt": 0,
                        "max_wall_seconds": 10,
                        "compare_baselines": False,
                        "created_at": now,
                    }
                ],
            )
    migrate(owner_url, "head", monkeypatch)
    columns = {c["name"]: c for c in inspect(owner).get_columns("solve_jobs")}
    assert columns["trace_context"]["nullable"] and str(columns["trace_context"]["type"]) == "JSONB"
    session_columns = {c["name"]: c for c in inspect(owner).get_columns("sessions")}
    assert session_columns["authentication_context_hash"]["nullable"]
    assert session_columns["authentication_context_hash"]["type"].length == 64
    with owner.connect() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0005"
        if existing:
            assert db.execute(text("SELECT status, trace_context FROM solve_jobs")).one() == (
                "QUEUED",
                None,
            )
        assert (
            db.scalar(text("SELECT count(*) FROM pg_policies WHERE policyname='tenant_isolation'"))
            == 12
        )
    grant_application(owner)
    owner.dispose()


@pytest.mark.parametrize("legacy_context", [False, True])
def test_real_api_worker_process_trace_and_actual_queue(
    database_urls, tmp_path, collector, legacy_context
):
    app_url, owner_url = database_urls
    owner = create_engine(owner_url)
    with owner.begin() as db:
        db.execute(text("TRUNCATE tenants, oidc_flows CASCADE"))
    endpoint, received = collector
    settings = Settings(
        environment="development",
        development_auth=True,
        database_url=app_url,
        app_base_url="http://testserver",
        object_root=str(tmp_path),
        redis_url="redis://127.0.0.1:56379/0",
        otel_endpoint=endpoint,
    )
    known_trace = "1234567890abcdef1234567890abcdef"
    with TestClient(create_app(settings)) as client:
        ready = client.get("/api/v1/health/ready")
        assert ready.status_code == 200 and ready.json()["status"] == "ok"
        login(client)
        body = make_snapshot(8).model_dump(mode="json")
        body["policy"] = client.get("/api/v1/fixtures/recover").json()["policy"]
        body["title"] = "SECRET_CARGO_DESCRIPTION"
        batch = post(client, "/imports/validate", {"snapshot": body}, "import").json()
        receipt = post(client, f"/imports/{batch['id']}/commit", key="commit").json()
        result = post(
            client, "/scenarios", {"source_snapshot_id": receipt["snapshot_id"]}, "scenario"
        )
        assert result.status_code == 201, result.text
        record = result.json()
        client.headers["traceparent"] = f"00-{known_trace}-1234567890abcdef-01"
        queued = post(
            client,
            f"/scenarios/{record['id']}/solve",
            {"max_wall_seconds": 10, "compare_baselines": False},
            "solve",
            record["etag"],
        )
        assert queued.status_code == 202, queued.text
        job = queued.json()
        assert "trace_context" not in job
        with client.app.state.factory.begin() as db:
            scope(db, TENANT_A)
            row = db.scalar(select(JobRow).where(JobRow.id == job["id"]))
            saved = dict(row.trace_context)
            assert set(saved) == {"traceparent"} and known_trace in saved["traceparent"]
            row.created_at = utcnow() - timedelta(seconds=20)
            if legacy_context:
                row.trace_context = None
        reader = InMemoryMetricReader()
        measurement = Telemetry(
            Settings(environment="development"), "cargopulse-worker", metric_reader=reader
        )
        observe_queue(client.app.state.factory, measurement)
        observed = reader.get_metrics_data()
        measures = {
            m.name: m
            for rm in observed.resource_metrics
            for sm in rm.scope_metrics
            for m in sm.metrics
        }
        queued_point = next(
            p
            for p in measures["cargopulse.queue.jobs"].data.data_points
            if p.attributes["status"] == "QUEUED"
        )
        assert queued_point.value == 1
        assert measures["cargopulse.queue.oldest_age"].data.data_points[0].value >= 20
        measurement.shutdown()
        client.app.state.telemetry.flush()
    # Producer API lifespan is gone. A separate Python worker loads trace context
    # from PostgreSQL using a new non-owner engine; Redis hints are not needed.
    script = """import os
from cargopulse_api.config import Settings
from cargopulse_api.db import configure
from cargopulse_api.observability import Telemetry, configure_logging
from cargopulse_api.worker import observe_queue, process_one
settings = Settings(environment="development", database_url=os.environ["OBSERVABILITY_TEST_DATABASE_URL"],
                    otel_endpoint=os.environ["TEST_OTLP_ENDPOINT"], object_root=os.environ["TEST_OBJECT_ROOT"])
settings.validate()
configure_logging()
runtime = Telemetry(settings, "cargopulse-worker")
engine, factory = configure(settings, runtime)
try:
    assert process_one(factory, "observability-test-worker")
    assert not process_one(factory, "duplicate-worker")
    observe_queue(factory, runtime)
    runtime.flush()
finally:
    engine.dispose()
    runtime.shutdown()
"""
    env = {
        **os.environ,
        "TEST_OTLP_ENDPOINT": endpoint,
        "TEST_OBJECT_ROOT": str(tmp_path),
        "PYTHONPATH": os.pathsep.join(
            str(ROOT / p)
            for p in ("packages/contracts/python", "services/api", "services/worker", ".")
        ),
    }
    executed = subprocess.run(  # noqa: S603 - fixed Python executable/script, no shell or request input.
        [sys.executable, "-c", script],
        env=env,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert executed.returncode == 0, executed.stdout + executed.stderr
    with owner.connect() as db:
        result = db.execute(
            text("SELECT status, plan_id, error_code FROM solve_jobs WHERE id=:id"),
            {"id": job["id"]},
        ).one()
        assert result.status == "COMPLETED" and result.plan_id and result.error_code is None
        payload = db.scalar(
            text("SELECT payload FROM solution_plans WHERE id=:id"), {"id": result.plan_id}
        )
        assert payload["independent_validation"]["status"] == "PASS"
    emitted = spans(received)
    enqueue = next(s for _, s in emitted if s.name == "job.enqueue")
    process = next(s for _, s in emitted if s.name == "job.process")
    assert enqueue.trace_id.hex() == known_trace
    if legacy_context:
        assert process.trace_id != enqueue.trace_id and not process.parent_span_id
    else:
        assert process.trace_id == enqueue.trace_id and process.parent_span_id == enqueue.span_id
    worker_spans = [
        s
        for resource, s in emitted
        if attributes(resource.attributes)["service.name"] == "cargopulse-worker"
    ]
    assert {s.name for s in worker_spans} == {"job.process", "solve", "independent_validate"}
    assert all(s.trace_id == process.trace_id for s in worker_spans)
    assert all(s.parent_span_id == process.span_id for s in worker_spans if s.name != "job.process")
    assert "SECRET_CARGO_DESCRIPTION" not in str(received) + executed.stderr
    assert {"ingest.validate", "snapshot.commit", "scenario.create"} <= {s.name for _, s in emitted}
    readiness = next(m for m in metrics(received) if m.name == "cargopulse.readiness")
    assert readiness.gauge.data_points[0].as_int == 1
    metric = next(m for m in metrics(received) if m.name == "cargopulse.queue.jobs")
    completed = next(
        p for p in metric.gauge.data_points if attributes(p.attributes)["status"] == "COMPLETED"
    )
    assert completed.as_int == 1
    owner.dispose()
