"""New adversarial tests, intentionally asserting required security invariants."""

from decimal import Decimal
from pathlib import Path

import pytest
from cargopulse_api.tables import ImportBatch, PolicyRow
from sqlalchemy import select

from .conftest import decision, login, post, ready


def test_import_cannot_publish_arbitrary_unreviewed_policy(client):
    login(client, "steward")
    from packages.domain_fixtures.generator import make_snapshot

    snapshot = make_snapshot(8).model_dump(mode="json")
    snapshot["policy"].update(
        id="unreviewed-policy",
        version="qa-bypass",
        authored_by="forged-author",
        approved_by="forged-reviewer",
        handling_seconds=1,
    )
    batch = post(client, "/imports/validate", {"snapshot": snapshot}, "unreviewed")
    if batch.status_code in (403, 409, 422):
        return
    assert batch.status_code == 202, batch.text
    receipt = post(client, f"/imports/{batch.json()['id']}/commit", key="unreviewed-commit")
    with client.app.state.factory() as db:
        published = [
            p
            for p in db.scalars(select(PolicyRow).where(PolicyRow.state == "PUBLISHED"))
            if p.payload["id"] == "unreviewed-policy"
        ]
    assert receipt.status_code in (403, 409, 422) or not published, {
        "commit_status": receipt.status_code,
        "published": [
            (p.authored_by, p.reviewed_by, p.payload["handling_seconds"]) for p in published
        ],
    }


def test_deleted_source_artifact_blocks_approval(client):
    record, plan = ready(client)
    with client.app.state.factory() as db:
        batch = db.scalar(select(ImportBatch))
        artifact = Path(client.app.state.settings.object_root) / batch.object_key
    assert artifact.exists()
    artifact.unlink()
    response = decision(client, record, plan)
    assert response.status_code in (409, 422, 503), response.text


def test_decision_does_not_allow_hash_or_csrf_substitution(client):
    record, plan = ready(client)
    response = decision(client, record, plan, expected_plan_hash="f" * 64)
    assert response.status_code == 409
    client.headers["X-CSRF-Token"] = "forged"
    assert decision(client, record, plan, key="csrf").status_code == 403
    client.headers["X-CSRF-Token"] = client.cookies.get("cp_csrf")
    client.headers["Origin"] = "https://evil.example"
    assert decision(client, record, plan, key="origin").status_code == 403
    client.headers["Origin"] = "http://testserver"
    assert decision(client, record, plan, key="valid").status_code == 201


def test_live_local_grant_revocation_and_csrf_are_session_bound(client):
    from cargopulse_api.tables import Identity

    login(client, "manager")
    old_csrf = client.cookies.get("cp_csrf")
    old_session = client.cookies.get("cp_session")
    login(client, "manager")
    client.headers["X-CSRF-Token"] = old_csrf
    assert post(client, "/auth/logout", key="cross-session").status_code == 403
    client.headers["X-CSRF-Token"] = client.cookies.get("cp_csrf")
    with client.app.state.factory.begin() as db:
        row = db.get(Identity, "manager")
        row.roles = ["auditor"]
    response = client.post(
        "/api/v1/policies/drafts",
        json={"policy": client.get("/api/v1/fixtures/recover").json()["policy"]},
        headers={"Idempotency-Key": "revoked-role", "X-Role": "manager", "X-Tenant-ID": "other"},
    )
    assert response.status_code == 403
    with client.app.state.factory.begin() as db:
        db.get(Identity, "manager").enabled = False
    assert client.get("/api/v1/me").status_code == 401
    client.cookies.clear()
    client.cookies.set("cp_session", old_session)
    assert client.get("/api/v1/me").status_code == 401


def test_real_ids_cannot_cross_tenant_read_mutate_or_export(client):
    from cargopulse_api.tables import Identity

    record, plan = ready(client)
    private_policy = {
        **record["snapshot"]["policy"],
        "id": "tenant-a-private-reviewed",
        "version": "qa-a-only",
    }
    draft = post(client, "/policies/drafts", {"policy": private_policy}, "private-policy")
    assert draft.status_code == 201, draft.text
    login(client, "manager-reviewer")
    published = post(client, f"/policies/{draft.json()['id']}/publish", key="private-publish")
    assert published.status_code == 201, published.text
    with client.app.state.factory.begin() as db:
        batch = db.scalar(select(ImportBatch))
        policy = db.scalar(select(PolicyRow))
        batch_id, policy_id, job_id = batch.id, policy.id, plan["job_id"]
        # Locally grant tenant B manager to exercise object checks beyond role denials.
        db.get(Identity, "controller-b").roles = ["manager"]
    login(client, "controller-b")
    for path in (
        f"/imports/{batch_id}",
        f"/policies/{policy_id}",
        f"/scenarios/{record['id']}",
        f"/scenarios/{record['id']}/candidates",
        f"/scenarios/{record['id']}/urgency",
        f"/jobs/{job_id}",
        f"/plans/{plan['id']}",
        f"/plans/{plan['id']}/alternatives",
    ):
        response = client.get("/api/v1" + path)
        assert response.status_code == 404, (path, response.text)
    for fmt in ("json", "csv", "pdf"):
        assert client.get(f"/api/v1/reports/{plan['id']}/export?format={fmt}").status_code == 404
    assert post(client, f"/imports/{batch_id}/commit", key="bola-commit").status_code == 404
    assert post(client, f"/policies/{policy_id}/publish", key="bola-publish").status_code == 404
    assert (
        post(
            client,
            "/scenarios",
            {"source_snapshot_id": record["snapshot"]["tenant_id"]},
            "bola-source",
        ).status_code
        == 404
    )
    assert (
        post(
            client, f"/scenarios/{record['id']}/solve", {}, "bola-solve", record["etag"]
        ).status_code
        == 404
    )
    assert decision(client, record, plan, "bola-decision").status_code == 404
    assert client.get("/api/v1/events").json()["items"] == []
    assert client.get("/api/v1/metrics").json()["items"] == []
    visible_policies = client.get("/api/v1/policies").json()["items"]
    assert all(p["id"] != "tenant-a-private-reviewed" for p in visible_policies)
    assert {p["id"] for p in visible_policies}.issubset({record["snapshot"]["policy"]["id"]})


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param(
            {
                "value": Decimal("0.873"),
                "numerator": Decimal("873"),
                "denominator": Decimal("1000"),
            },
            id="invented-cohort-counts",
        ),
        pytest.param({"value": Decimal("0.873")}, id="false-ratio-only"),
        pytest.param({"snapshot_hash": "f" * 64}, id="wrong-snapshot-lineage"),
        pytest.param({"policy_hash": "f" * 64}, id="wrong-policy-lineage"),
        pytest.param({"data_source_ids": []}, id="missing-source-lineage"),
        pytest.param({"cohort_id": "invented-cohort"}, id="invented-cohort"),
        pytest.param({"name": "invented_validated_wins"}, id="unsupported-computed-claim"),
        pytest.param({"unit": "AWB"}, id="wrong-physical-denominator-unit"),
    ],
)
def test_false_computed_metrics_cannot_reach_approvable_export(client, monkeypatch, mutation):
    """Physically valid assignments must not authenticate fabricated computed KPIs."""
    import cargopulse_optimizer

    original = cargopulse_optimizer.run_solver

    def forged_metrics(snapshot, max_wall_seconds):
        plan = original(snapshot, max_wall_seconds=max_wall_seconds)
        first = plan.metrics[0].model_copy(update=mutation)
        return plan.model_copy(update={"metrics": [first, *plan.metrics[1:]]})

    monkeypatch.setattr(cargopulse_optimizer, "run_solver", forged_metrics)
    record, plan = ready(client, require_approvable=False)
    if not plan["approvable"]:
        return
    exported = client.get(f"/api/v1/reports/{plan['id']}/export?format=json")
    assert exported.status_code == 200
    metric = exported.json()["plan"]["metrics"][0]
    response = decision(client, record, plan, key="false-kpi")
    assert not plan["approvable"] or metric["status"] != "COMPUTED", {
        "validation": plan["plan"]["independent_validation"]["status"],
        "approvable": plan["approvable"],
        "approval_status": response.status_code,
        "exported_computed_metric": metric,
    }


def test_legacy_published_label_without_authenticated_review_is_rejected(client):
    """An upgrade must not trust rows the old import path auto-published."""
    from cargopulse_api.db import utcnow
    from cargopulse_contracts import RuleSet, canonical_hash

    from packages.domain_fixtures.generator import make_snapshot

    login(client, "steward")
    snapshot = make_snapshot(8).model_dump(mode="json")
    snapshot["policy"].update(
        id="legacy-forged-policy",
        version="pre-upgrade",
        authored_by="forged-author",
        approved_by="forged-reviewer",
        handling_seconds=1,
    )
    policy = RuleSet.model_validate(snapshot["policy"])
    with client.app.state.factory.begin() as db:
        db.add(
            PolicyRow(
                tenant_id=snapshot["tenant_id"],
                policy_hash=canonical_hash(policy),
                state="PUBLISHED",
                payload=policy.model_dump(mode="json"),
                authored_by=policy.authored_by,
                reviewed_by=policy.approved_by,
                created_at=utcnow(),
            )
        )
    batch = post(client, "/imports/validate", {"snapshot": snapshot}, "legacy-import")
    if batch.status_code in (403, 409, 422):
        return
    assert batch.status_code == 202, batch.text
    result = post(client, f"/imports/{batch.json()['id']}/commit", key="legacy-commit")
    assert result.status_code in (403, 409, 422), result.text
