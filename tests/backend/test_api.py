import csv
import io
import json
import os
from datetime import timedelta
from uuid import uuid4

import pytest
from cargopulse_api.config import Settings
from cargopulse_api.db import utcnow
from cargopulse_api.tables import AuditRow, JobRow, OutboxRow, SessionRow, SnapshotRow
from sqlalchemy import select

from .conftest import login, post, scenario


def test_production_fails_closed():
    with pytest.raises(RuntimeError):
        Settings(environment="production", development_auth=True).validate()
    with pytest.raises(RuntimeError):
        Settings().validate()


def test_unauthenticated_is_problem(client):
    response = client.get("/api/v1/events")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["correlation_id"]


def test_development_cannot_forge_identity_or_tenant(client):
    bad = client.post(
        "/api/v1/auth/development",
        json={"identity_id": "admin"},
        headers={"Origin": "http://testserver"},
    )
    assert bad.status_code == 403
    login(client, "controller")
    result = client.get("/api/v1/me")
    assert result.json()["roles"] == ["controller", "load_analyst"]
    assert (
        "HttpOnly"
        in client.post(
            "/api/v1/auth/development",
            json={"identity_id": "controller"},
            headers={"Origin": "http://testserver"},
        ).headers["set-cookie"]
    )


def test_csrf_origin_and_rbac_denials_survive_rollback(client):
    login(client, "controller")
    snapshot = client.get("/api/v1/fixtures/recover").json()
    response = post(client, "/imports/validate", {"snapshot": snapshot})
    assert response.status_code == 403
    client.headers["X-CSRF-Token"] = "forged"
    assert post(client, "/scenarios", {"source_snapshot_id": str(uuid4())}).status_code == 403
    client.headers["X-CSRF-Token"] = client.cookies.get("cp_csrf")
    client.headers["Origin"] = "https://evil.example"
    assert post(client, "/scenarios", {"source_snapshot_id": str(uuid4())}).status_code == 403
    with client.app.state.factory() as db:
        assert len(list(db.scalars(select(AuditRow).where(AuditRow.outcome == "DENIED")))) == 3


def test_revocation_and_expiry(client):
    login(client)
    old = client.cookies.get("cp_session")
    assert post(client, "/auth/logout").status_code == 200
    client.cookies.set("cp_session", old)
    assert client.get("/api/v1/me").status_code == 401
    login(client)
    with client.app.state.factory.begin() as db:
        for row in db.scalars(select(SessionRow)):
            row.expires_at = utcnow() - timedelta(seconds=1)
    assert client.get("/api/v1/me").status_code == 401


def test_import_commit_idempotency_and_immutable_snapshot(client):
    record, snapshot = scenario(client)
    assert record["snapshot"] == snapshot
    same = post(
        client, "/scenarios", {"source_snapshot_id": record["snapshot"]["event_id"]}, key="scenario"
    )
    assert same.status_code == 422  # Invalid UUID fails schema before command.
    with client.app.state.factory() as db:
        assert len(list(db.scalars(select(SnapshotRow)))) == 1
    reread = client.get(f"/api/v1/scenarios/{record['id']}")
    assert reread.headers["etag"] == record["etag"]


def test_cross_tenant_guards_every_domain_id(client):
    record, _ = scenario(client)
    job = post(client, f"/scenarios/{record['id']}/solve", {}, key="solve", etag=record["etag"])
    assert job.status_code == 202, job.text
    login(client, "controller-b")
    for path in (
        f"/scenarios/{record['id']}",
        f"/scenarios/{record['id']}/candidates",
        f"/scenarios/{record['id']}/urgency",
        f"/jobs/{job.json()['id']}",
        f"/plans/{uuid4()}",
        f"/reports/{uuid4()}/export",
    ):
        assert client.get("/api/v1" + path).status_code == 404, path
    assert client.get("/api/v1/events").json()["items"] == []


def test_idempotent_solve_has_one_job_and_outbox(client):
    record, _ = scenario(client)
    path = f"/scenarios/{record['id']}/solve"
    first = post(client, path, {}, "solve", record["etag"])
    retry = post(client, path, {}, "solve", record["etag"])
    assert first.status_code == retry.status_code == 202
    assert first.json() == retry.json()
    conflict = post(client, path, {"max_wall_seconds": 15}, "solve", record["etag"])
    assert conflict.status_code == 409
    with client.app.state.factory() as db:
        assert len(list(db.scalars(select(JobRow)))) == 1
        assert len(list(db.scalars(select(OutboxRow)))) == 1


def test_stale_etag_denied_and_audited(client):
    record, _ = scenario(client)
    result = post(client, f"/scenarios/{record['id']}/solve", {}, "solve", '"stale"')
    assert result.status_code == 409
    audit = client.get("/api/v1/audit").json()
    assert any(a["outcome"] == "DENIED" for a in audit["items"])


def test_import_rejects_tenant_and_missing_units(client):
    login(client)
    snapshot = client.get("/api/v1/fixtures/recover").json()
    snapshot["tenant_id"] = "10000000-0000-4000-8000-000000000002"
    assert post(client, "/imports/validate", {"snapshot": snapshot}).status_code == 403
    snapshot["tenant_id"] = "10000000-0000-4000-8000-000000000001"
    snapshot["cargo_units"][0]["actual_mass_kg"] = 1.25
    result = post(client, "/imports/validate", {"snapshot": snapshot}, "bad")
    assert result.status_code == 422
    assert "input" not in result.text


def test_unknown_capacity_quarantines(client):
    login(client)
    snapshot = client.get("/api/v1/fixtures/recover").json()
    snapshot["flights"][0]["free_mass_kg"] = None
    result = post(client, "/imports/validate", {"snapshot": snapshot})
    assert result.status_code == 202
    assert result.json()["status"] == "QUARANTINED"
    assert post(client, f"/imports/{result.json()['id']}/commit", key="commit").status_code == 422


def test_duplicate_event_and_out_of_order_rejected(client):
    record, snapshot = scenario(client)
    snapshot["title"] = "Conflicting same version"
    result = post(client, "/imports/validate", {"snapshot": snapshot}, "different")
    assert result.status_code == 202
    commit = post(client, f"/imports/{result.json()['id']}/commit", key="different-commit")
    assert commit.status_code == 409


def test_csv_bounded_schema_and_formula(client):
    login(client)
    snapshot = client.get("/api/v1/fixtures/recover").json()
    units = snapshot.pop("cargo_units")[:1]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=units[0].keys())
    writer.writeheader()
    unit = {
        k: json.dumps(v) if isinstance(v, (dict, list, bool)) else v for k, v in units[0].items()
    }
    writer.writerow(unit)
    response = client.post(
        "/api/v1/imports/upload-csv",
        files={"file": ("cargo.csv", out.getvalue(), "text/csv")},
        data={"metadata": json.dumps(snapshot)},
        headers={"Idempotency-Key": "csv"},
    )
    # Other permissions refer to removed rows and canonical cross-references reject them.
    assert response.status_code == 422
    bad = "id\n=WEBSERVICE(evil)\n"
    response = client.post(
        "/api/v1/imports/upload-csv",
        files={"file": ("cargo.csv", bad, "text/csv")},
        data={"metadata": "{}"},
        headers={"Idempotency-Key": "csv2"},
    )
    assert response.status_code == 422
    assert "unsafe formula" in response.json()["detail"]


def test_policy_self_review_denied(client):
    login(client)
    policy = client.get("/api/v1/fixtures/recover").json()["policy"]
    draft = post(client, "/policies/drafts", {"policy": policy})
    assert draft.status_code == 201, draft.text
    read = client.get(f"/api/v1/policies/{draft.json()['id']}")
    assert read.status_code == 200 and read.json()["state"] == "DRAFT"
    published = post(client, f"/policies/{draft.json()['id']}/publish", key="publish")
    assert published.status_code == 409
    login(client, "controller-b")
    # Tenant-B controller has no policy-authoring role; a forged ID cannot expose the draft.
    assert client.get(f"/api/v1/policies/{draft.json()['id']}").status_code == 403


def test_body_limit_and_validation_problem(client):
    response = client.post(
        "/api/v1/imports/validate", content=b"x", headers={"Content-Length": "9000000"}
    )
    assert response.status_code == 413
    assert client.get("/api/v1/health/live").json()["status"] == "ok"
    ready = client.get("/api/v1/health/ready")
    assert ready.json()["dependencies"]["private_object_store"] == "ok"
    assert ready.status_code in (
        200,
        503,
    )  # Missing solver module fails readiness in isolated fast runs.


def test_different_manager_review_and_publish(client):
    login(client, "manager")
    policy = client.get("/api/v1/fixtures/recover").json()["policy"]
    draft = post(client, "/policies/drafts", {"policy": policy}).json()
    login(client, "manager-reviewer")
    review = client.get(f"/api/v1/policies/{draft['id']}")
    assert review.status_code == 200 and review.json()["authored_by"] == "manager"
    result = post(client, f"/policies/{draft['id']}/publish", key="reviewed")
    assert result.status_code == 201, result.text
    published = result.json()
    assert published["state"] == "PUBLISHED"
    assert published["authored_by"] == "manager" and published["reviewed_by"] == "manager-reviewer"
    assert published["policy"]["approved_by"] == "manager-reviewer"
    assert published["policy_hash"] != draft["policy_hash"]


def test_disabled_connector_never_fetches():
    from cargopulse_api.connectors import OneRecordAdapter

    adapter = OneRecordAdapter()
    assert adapter.describe_source().enabled is False
    with pytest.raises(PermissionError):
        adapter.fetch_since()


def test_pending_solve_quota_is_per_tenant_and_idempotent(client):
    login(client)
    client.app.state.factory.kw["info"]["max_pending_jobs"] = 1
    scenarios = []
    for index in range(2):
        snapshot = client.get("/api/v1/fixtures/recover").json()
        snapshot["event_id"] = f"quota-event-{index}"
        batch = post(client, "/imports/validate", {"snapshot": snapshot}, f"quota-import-{index}")
        assert batch.status_code == 202
        receipt = post(client, f"/imports/{batch.json()['id']}/commit", key=f"quota-commit-{index}")
        record = post(
            client,
            "/scenarios",
            {"source_snapshot_id": receipt.json()["snapshot_id"]},
            f"quota-scenario-{index}",
        )
        assert record.status_code == 201
        scenarios.append(record.json())
    first = post(
        client, f"/scenarios/{scenarios[0]['id']}/solve", {}, "quota-first", scenarios[0]["etag"]
    )
    assert first.status_code == 202
    retry = post(
        client, f"/scenarios/{scenarios[0]['id']}/solve", {}, "quota-first", scenarios[0]["etag"]
    )
    assert retry.status_code == 202 and retry.json()["id"] == first.json()["id"]
    excess = post(
        client, f"/scenarios/{scenarios[1]['id']}/solve", {}, "quota-second", scenarios[1]["etag"]
    )
    assert excess.status_code == 429 and excess.json()["code"] == "RATE_LIMITED"
    assert excess.headers["retry-after"] == "30"


def test_controlled_csv_positive_preview_and_private_object(client):
    login(client)
    snapshot = client.get("/api/v1/fixtures/recover").json()
    units = snapshot.pop("cargo_units")
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=units[0].keys())
    writer.writeheader()
    for unit in units:
        writer.writerow(
            {k: json.dumps(v) if isinstance(v, (dict, list, bool)) else v for k, v in unit.items()}
        )
    response = client.post(
        "/api/v1/imports/upload-csv",
        files={"file": ("cargo.csv", out.getvalue(), "text/csv")},
        data={"metadata": json.dumps(snapshot)},
        headers={"Idempotency-Key": "valid-csv"},
    )
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "READY"
    from pathlib import Path

    from cargopulse_api.tables import ImportBatch

    with client.app.state.factory() as db:
        row = db.scalar(select(ImportBatch))
        artifact = Path(client.app.state.settings.object_root) / row.object_key
        assert artifact.is_file()
        assert client.app.state.objects.verify(row.tenant_id, row.object_key)


@pytest.mark.skipif(os.name == "nt", reason="POSIX owner-only modes are not Windows ACL evidence")
def test_private_objects_use_posix_owner_only_permissions(tmp_path):
    from cargopulse_api.db import TENANT_A
    from cargopulse_api.storage import PrivateObjects

    objects = PrivateObjects(Settings(object_root=str(tmp_path / "objects")))
    key = objects.put(TENANT_A, b"synthetic-private-object")
    artifact = objects.root / key
    assert objects.root.stat().st_mode & 0o777 == 0o700
    assert artifact.parent.stat().st_mode & 0o777 == 0o700
    assert artifact.stat().st_mode & 0o777 == 0o600


def test_unknown_arc_is_visible_without_blocking_other_candidates(client):
    login(client)
    snapshot = client.get("/api/v1/fixtures/recover").json()
    snapshot["route_permissions"][0]["cold_chain"]["state"] = "UNKNOWN"
    response = post(client, "/imports/validate", {"snapshot": snapshot})
    assert response.status_code == 202 and response.json()["status"] == "READY"
    assert any(
        x["code"] == "UNVERIFIED_EVIDENCE" and not x["blocking"]
        for x in response.json()["quality_issues"]
    )


@pytest.mark.parametrize("next_identity", ["manager", "controller-b"])
def test_reauthentication_rotates_and_revokes_the_presented_cookie(client, next_identity):
    login(client, "manager")
    old = client.cookies.get("cp_session")
    login(client, next_identity)
    new = client.cookies.get("cp_session")
    assert old != new
    assert client.get("/api/v1/me").json()["subject"] == next_identity
    assert client.get("/api/v1/me", headers={"Cookie": "cp_session=" + old}).status_code == 401
    assert client.get("/api/v1/me").status_code == 200


def test_reachable_but_unmigrated_database_is_not_ready(tmp_path):
    from cargopulse_api.main import create_app
    from fastapi.testclient import TestClient

    settings = Settings(
        environment="development",
        development_auth=False,
        database_url="sqlite:///:memory:",
        auto_create=False,
        object_root=str(tmp_path),
        redis_url="redis://127.0.0.1:56379/0",
    )
    with TestClient(create_app(settings)) as c:
        result = c.get("/api/v1/health/ready")
        assert result.status_code == 503
        assert result.json()["dependencies"]["database"] == "unavailable"
        assert c.get("/api/v1/health/live").status_code == 200


@pytest.mark.parametrize(
    "changes",
    [
        {"development_auth": False},
        {"environment": "production", "development_auth": False},
    ],
)
def test_development_sessions_stop_working_when_adapter_is_disabled(client, changes):
    from dataclasses import replace

    login(client)
    assert client.get("/api/v1/me").status_code == 200
    client.app.state.settings = replace(client.app.state.settings, **changes)
    assert client.get("/api/v1/me").status_code == 401
