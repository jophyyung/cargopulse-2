"""Tenant-scoped commands and wire serializers for the frozen contract."""

import json
from datetime import timedelta
from importlib import import_module

from cargopulse_contracts import (
    ImportRecord,
    JobRecord,
    PlanRecord,
    QualityIssue,
    ScenarioRecord,
    ScenarioSnapshot,
    SolutionPlan,
    canonical_hash,
)
from sqlalchemy import func, select

from .db import aware, development_policy, lock_tenant, scope, utcnow
from .observability import annotate, capture_trace_context, observed
from .security import AppError, audit
from .tables import (
    AuditRow,
    IdempotencyRow,
    ImportBatch,
    JobRow,
    OutboxRow,
    PlanRow,
    PolicyRow,
    ScenarioRow,
    SnapshotRow,
    Tenant,
)


def get(db, model, id, tenant, lock=False):
    stmt = select(model).where(model.id == str(id), model.tenant_id == str(tenant))
    row = db.scalar(stmt.with_for_update() if lock else stmt)
    if row is None:
        raise AppError(404, "NOT_FOUND", "Resource is not visible in this tenant", id)
    return row


def solver():
    try:
        return import_module("cargopulse_optimizer")
    except ImportError:
        raise AppError(
            503, "SOLVER_UNAVAILABLE", "The optimizer runtime is not installed"
        ) from None


def validate(snapshot, plan, decision_time=None):
    try:
        module = import_module("cargopulse_validation")
    except ImportError:
        raise AppError(
            503, "VALIDATOR_UNAVAILABLE", "Independent validator is unavailable"
        ) from None
    return module.validate_solution_independently(snapshot, plan, decision_time=decision_time)


def freshness(snapshot, at=None):
    at = at or utcnow()
    blockers = []
    if not snapshot.as_of <= at < snapshot.valid_until:
        blockers.append("STALE_SNAPSHOT")
    if not (
        snapshot.provenance.observed_at <= at
        and snapshot.provenance.effective_at <= at
        and snapshot.provenance.ingested_at <= at
    ):
        blockers.append("FUTURE_PROVENANCE")
    if at - snapshot.provenance.observed_at > timedelta(
        seconds=snapshot.policy.source_max_age_seconds
    ):
        blockers.append("STALE_SOURCE")
    return blockers


def quality(snapshot):
    # Full feasibility validation remains owned by the optimizer/independent validator.
    issues = []
    for code in freshness(snapshot):
        issues.append(
            QualityIssue(
                code=code,
                severity="BLOCKING",
                entity_type="snapshot",
                entity_id=snapshot.event_id,
                field="provenance",
                remediation="Import a current source version",
                blocking=True,
            )
        )
    for flight in snapshot.flights:
        if (
            flight.free_mass_kg is None
            or flight.free_volume_m3 is None
            or any(
                p.free_mass_kg is None or p.free_volume_m3 is None or p.slot_count is None
                for p in flight.positions
            )
        ):
            issues.append(
                QualityIssue(
                    code="MISSING_PAYLOAD",
                    severity="BLOCKING",
                    entity_type="flight",
                    entity_id=flight.id,
                    field="capacity",
                    remediation="Supply verified position and flight capacity",
                    blocking=True,
                )
            )
    # Arc-specific unknowns remain explicit review issues; candidate/independent gates
    # exclude the affected arc without discarding unrelated verified alternatives.
    at = utcnow()
    proofs = []
    for unit in snapshot.cargo_units:
        proofs += [
            ("cargo_unit", unit.id, "serviceability", unit.serviceability),
            ("cargo_unit", unit.id, "security", unit.security),
        ]
    for permission in snapshot.route_permissions:
        for name in ("dg", "customs", "cold_chain", "load_control"):
            proofs.append(
                (
                    "route_permission",
                    permission.cargo_unit_id + ":" + permission.flight_id,
                    name,
                    getattr(permission, name),
                )
            )
    for entity_type, entity_id, field, proof in proofs:
        if proof.state != "PASS" or proof.observed_at > snapshot.as_of or proof.valid_until <= at:
            issues.append(
                QualityIssue(
                    code="UNVERIFIED_EVIDENCE",
                    severity="REVIEW_REQUIRED",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    field=field,
                    remediation="Verify the affected unit or route; this proof cannot authorize an assignment",
                    blocking=False,
                )
            )
    return issues


def snapshot_for(db, scenario):
    return ScenarioSnapshot.model_validate(
        get(db, SnapshotRow, scenario.snapshot_id, scenario.tenant_id).payload
    )


def scenario_wire(db, row):
    return ScenarioRecord(
        id=row.id,
        version=row.version,
        snapshot_hash=row.snapshot_hash,
        policy_hash=row.policy_hash,
        state=row.state,
        snapshot=snapshot_for(db, row),
        quality_issues=row.quality_issues,
        created_at=aware(row.created_at),
        current=row.current,
        latest_job_id=row.latest_job_id,
        latest_plan_id=row.latest_plan_id,
        etag=f'"scenario-{row.id}-v{row.version}"',
    )


def job_wire(row):
    return JobRecord(
        id=row.id,
        scenario_id=row.scenario_id,
        scenario_version=row.scenario_version,
        snapshot_hash=row.snapshot_hash,
        status=row.status,
        progress=row.progress,
        attempt=row.attempt,
        created_at=aware(row.created_at),
        started_at=aware(row.started_at) if row.started_at else None,
        finished_at=aware(row.finished_at) if row.finished_at else None,
        plan_id=row.plan_id,
        error_code=row.error_code,
        poll_url=f"/api/v1/jobs/{row.id}",
    )


def plan_blockers(db, row, revalidate=True):
    scenario = get(db, ScenarioRow, row.scenario_id, row.tenant_id)
    snapshot = snapshot_for(db, scenario)
    plan = SolutionPlan.model_validate(row.payload)
    blockers = freshness(snapshot)
    try:
        verify_source_artifact(db, scenario.snapshot_id, row.tenant_id)
    except AppError as error:
        blockers.append(error.code)
    if (
        not scenario.current
        or row.scenario_version != scenario.version
        or scenario.latest_plan_id != row.id
    ):
        blockers.append("STALE_PLAN")
    if (
        plan.snapshot_hash != scenario.snapshot_hash
        or plan.policy_hash != scenario.policy_hash
        or canonical_hash(snapshot) != scenario.snapshot_hash
        or canonical_hash(snapshot.policy) != scenario.policy_hash
        or canonical_hash(plan) != row.plan_hash
    ):
        blockers.append("HASH_MISMATCH")
    policy = db.scalar(
        select(PolicyRow).where(
            PolicyRow.tenant_id == row.tenant_id, PolicyRow.policy_hash == scenario.policy_hash
        )
    )
    if (
        not policy
        or policy.state != "PUBLISHED"
        or policy.payload != snapshot.policy.model_dump(mode="json")
    ):
        blockers.append("POLICY_NOT_PUBLISHED")
    else:
        try:
            require_published_policy(db, row.tenant_id, snapshot.policy)
        except AppError as error:
            blockers.append(error.code)
    if row.state != "PROPOSED":
        blockers.append("PLAN_NOT_PROPOSED")
    if plan.independent_validation.status != "PASS":
        blockers.append("VALIDATION_FAILED")
    if not plan.assignments:
        blockers.append("NO_FEASIBLE_PLAN")
    if plan.solver.status not in ("OPTIMAL", "FEASIBLE", "TIME_LIMIT_WITH_FEASIBLE"):
        blockers.append("SOLVER_NOT_FEASIBLE")
    if revalidate:
        result = validate(snapshot, plan, utcnow())
        if result.status != "PASS":
            blockers.append("CURRENT_VALIDATION_FAILED")
    return list(dict.fromkeys(blockers))


def plan_wire(db, row):
    blockers = plan_blockers(db, row)
    return PlanRecord(
        id=row.id,
        job_id=row.job_id,
        scenario_id=row.scenario_id,
        scenario_version=row.scenario_version,
        plan_hash=row.plan_hash,
        plan=SolutionPlan.model_validate(row.payload),
        state=row.state,
        approvable=not blockers,
        blockers=blockers,
        created_at=aware(row.created_at),
        etag=f'"plan-{row.id}-{row.plan_hash}"',
    )


def import_wire(row):
    return ImportRecord(
        id=row.id,
        status=row.status,
        content_sha256=row.content_sha256,
        snapshot_id=row.snapshot_id,
        quality_issues=row.quality_issues,
        row_errors=row.row_errors,
        created_at=aware(row.created_at),
    )


def idempotent(db, request, principal, key, operation, payload, status, command):
    if not key or len(key) > 100 or any(ord(x) < 33 or ord(x) > 126 for x in key):
        raise AppError(
            400, "INVALID_IDEMPOTENCY_KEY", "A 1-100 character Idempotency-Key is required"
        )
    tenant = str(principal.tenant_id)
    scope(db, tenant)
    # Tenant lock also protects first-use idempotency races and per-tenant quotas.
    lock_tenant(db, tenant)
    request_hash = canonical_hash({"payload": payload, "if_match": request.headers.get("if-match")})
    prior = db.scalar(
        select(IdempotencyRow).where(
            IdempotencyRow.tenant_id == tenant,
            IdempotencyRow.actor == principal.subject,
            IdempotencyRow.operation == operation,
            IdempotencyRow.key == key,
        )
    )
    if prior:
        if prior.request_hash != request_hash:
            raise AppError(
                409, "IDEMPOTENCY_CONFLICT", "Idempotency-Key was used for a different request"
            )
        return prior.response
    result = command()
    data = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
    db.add(
        IdempotencyRow(
            tenant_id=tenant,
            actor=principal.subject,
            operation=operation,
            key=key,
            request_hash=request_hash,
            response=data,
            status_code=status,
            created_at=utcnow(),
        )
    )
    audit(
        db,
        tenant,
        principal.subject,
        operation,
        data.get("id", data.get("snapshot_id", "")),
        "SUCCESS",
        request.state.correlation_id,
    )
    db.flush()
    return data


@observed("ingest.validate")
def validate_import(db, request, principal, snapshot, raw=None):
    annotate(**{"cargo.count": len(snapshot.cargo_units)})
    tenant = str(principal.tenant_id)
    if str(snapshot.tenant_id) != tenant:
        raise AppError(403, "TENANT_MISMATCH", "Import tenant does not match the current session")
    if not get_tenant(db, tenant).synthetic_only:
        raise AppError(403, "SYNTHETIC_ONLY", "This L1 runtime only serves synthetic tenants")
    require_published_policy(db, tenant, snapshot.policy)
    content = snapshot.model_dump(mode="json")
    sha = canonical_hash(snapshot)
    existing = db.scalar(
        select(ImportBatch).where(
            ImportBatch.tenant_id == tenant, ImportBatch.content_sha256 == sha
        )
    )
    if existing:
        return import_wire(existing)
    issues = quality(snapshot)
    object_key = request.app.state.objects.put(tenant, raw or json.dumps(content).encode())
    row = ImportBatch(
        tenant_id=tenant,
        content_sha256=sha,
        source_id=snapshot.provenance.source_id,
        object_key=object_key,
        status="QUARANTINED" if any(x.blocking for x in issues) else "READY",
        payload=content,
        quality_issues=[x.model_dump(mode="json") for x in issues],
        row_errors=[],
        snapshot_id=None,
        created_at=utcnow(),
    )
    db.add(row)
    db.flush()
    return import_wire(row)


def get_tenant(db, tenant):
    row = db.scalar(select(Tenant).where(Tenant.id == tenant))
    if not row:
        raise AppError(403, "TENANT_DISABLED", "Tenant is not provisioned")
    return row


def require_published_policy(db, tenant, policy):
    row = db.scalar(
        select(PolicyRow).where(
            PolicyRow.tenant_id == tenant,
            PolicyRow.policy_hash == canonical_hash(policy),
            PolicyRow.state == "PUBLISHED",
        )
    )
    if (
        not row
        or row.payload != policy.model_dump(mode="json")
        or not row.reviewed_by
        or row.authored_by == row.reviewed_by
    ):
        raise AppError(
            409,
            "POLICY_NOT_PUBLISHED",
            "Import must reference an exact tenant policy already published by its reviewers",
        )
    seeded = db.info.get("development_seed_allowed") and canonical_hash(policy) == canonical_hash(
        development_policy()
    )
    publication = db.scalar(
        select(AuditRow.id)
        .where(
            AuditRow.tenant_id == tenant,
            AuditRow.action == f"policies.{row.id}.publish",
            AuditRow.resource_id == row.id,
            AuditRow.actor == row.reviewed_by,
            AuditRow.outcome == "SUCCESS",
        )
        .limit(1)
    )
    if not seeded and not publication:
        raise AppError(
            409,
            "POLICY_NOT_PUBLISHED",
            "Policy has no authenticated independent publication record",
        )
    return row


def verify_source_artifact(db, snapshot_id, tenant):
    batch = db.scalar(
        select(ImportBatch).where(
            ImportBatch.tenant_id == tenant, ImportBatch.snapshot_id == snapshot_id
        )
    )
    objects = db.info.get("objects")
    if not batch or objects is None or not objects.verify(tenant, batch.object_key):
        raise AppError(
            409,
            "SOURCE_ARTIFACT_NOT_VERIFIED",
            "The immutable source artifact is missing or its checksum no longer matches",
            snapshot_id,
        )


@observed("snapshot.commit")
def commit_import(db, id, tenant):
    row = get(db, ImportBatch, id, tenant, True)
    if row.snapshot_id:
        snap = get(db, SnapshotRow, row.snapshot_id, tenant)
        return {"snapshot_id": snap.id, "snapshot_hash": snap.content_hash, "synthetic": True}
    if row.status != "READY":
        raise AppError(
            422,
            "MISSING_CRITICAL_DATA",
            "Quarantined imports cannot be committed",
            id,
            row.quality_issues,
        )
    snapshot = ScenarioSnapshot.model_validate(row.payload)
    require_published_policy(db, tenant, snapshot.policy)
    objects = db.info.get("objects")
    if objects is None or not objects.verify(tenant, row.object_key):
        raise AppError(
            409,
            "SOURCE_ARTIFACT_NOT_VERIFIED",
            "Restore the exact source artifact before commit",
            id,
        )
    if freshness(snapshot):
        raise AppError(409, "STALE_SNAPSHOT", "Import expired before commit", id)
    prior = db.scalar(
        select(SnapshotRow)
        .where(
            SnapshotRow.tenant_id == tenant,
            SnapshotRow.source_id == row.source_id,
            SnapshotRow.event_id == snapshot.event_id,
        )
        .order_by(SnapshotRow.source_version.desc())
        .limit(1)
    )
    if prior and prior.source_version >= snapshot.source_version:
        raise AppError(409, "DUPLICATE_EVENT", "Event versions must increase monotonically", id)
    saved = SnapshotRow(
        tenant_id=tenant,
        source_id=row.source_id,
        event_id=snapshot.event_id,
        source_version=snapshot.source_version,
        content_hash=row.content_sha256,
        payload=row.payload,
        created_at=utcnow(),
    )
    db.add(saved)
    db.flush()
    # Any newer source version invalidates existing proposals before it is selected for a scenario.
    old_snapshots = select(SnapshotRow.id).where(
        SnapshotRow.tenant_id == tenant,
        SnapshotRow.source_id == row.source_id,
        SnapshotRow.event_id == snapshot.event_id,
        SnapshotRow.source_version < snapshot.source_version,
    )
    for scenario in db.scalars(
        select(ScenarioRow)
        .where(
            ScenarioRow.tenant_id == tenant,
            ScenarioRow.snapshot_id.in_(old_snapshots),
            ScenarioRow.current.is_(True),
        )
        .with_for_update()
    ):
        scenario.current, scenario.state = False, "STALE"
        for plan in db.scalars(
            select(PlanRow).where(
                PlanRow.tenant_id == tenant,
                PlanRow.scenario_id == scenario.id,
                PlanRow.state == "PROPOSED",
            )
        ):
            plan.state = "STALE"
    row.status, row.snapshot_id = "COMMITTED", saved.id
    return {"snapshot_id": saved.id, "snapshot_hash": saved.content_hash, "synthetic": True}


@observed("scenario.create")
def create_scenario(db, tenant, body, parent=None):
    snapshot_row = get(db, SnapshotRow, body.source_snapshot_id, tenant)
    existing = db.scalar(
        select(ScenarioRow).where(
            ScenarioRow.tenant_id == tenant, ScenarioRow.snapshot_id == snapshot_row.id
        )
    )
    if existing:
        if parent:
            raise AppError(409, "DUPLICATE_EVENT", "Snapshot already has a scenario")
        return scenario_wire(db, existing)
    snapshot = ScenarioSnapshot.model_validate(snapshot_row.payload)
    if parent:
        old = snapshot_for(db, parent)
        if (
            old.event_id != snapshot.event_id
            or old.provenance.source_id != snapshot.provenance.source_id
            or old.source_version >= snapshot.source_version
        ):
            raise AppError(
                409,
                "VERSION_CONFLICT",
                "Supersession requires a newer version of the same source event",
            )
        parent.current, parent.state = False, "STALE"
        for plan in db.scalars(
            select(PlanRow).where(
                PlanRow.tenant_id == tenant,
                PlanRow.scenario_id == parent.id,
                PlanRow.state == "PROPOSED",
            )
        ):
            plan.state = "STALE"
    issues = quality(snapshot)
    row = ScenarioRow(
        tenant_id=tenant,
        snapshot_id=snapshot_row.id,
        parent_id=parent.id if parent else None,
        version=parent.version + 1 if parent else 1,
        snapshot_hash=snapshot_row.content_hash,
        policy_hash=canonical_hash(snapshot.policy),
        state="NEEDS_VERIFICATION" if any(x.blocking for x in issues) else "READY",
        current=True,
        quality_issues=[x.model_dump(mode="json") for x in issues],
        latest_job_id=None,
        latest_plan_id=None,
        created_at=utcnow(),
    )
    db.add(row)
    db.flush()
    return scenario_wire(db, row)


@observed("job.enqueue")
def queue_solve(db, tenant, id, body, if_match, actor):
    row = get(db, ScenarioRow, id, tenant, True)
    if scenario_wire(db, row).etag != if_match:
        raise AppError(409, "VERSION_CONFLICT", "Scenario ETag is stale", id)
    if not row.current or row.state not in (
        "READY",
        "PLAN_READY",
        "SOLVER_ERROR",
        "NO_FEASIBLE_PLAN",
    ):
        raise AppError(
            409, "SCENARIO_NOT_READY", "Scenario is not current and ready for a new solve", id
        )
    if any(issue.blocking for issue in quality(snapshot_for(db, row))):
        raise AppError(
            409, "STALE_SNAPSHOT", "Current source freshness or capacity prevents solve", id
        )
    snapshot = snapshot_for(db, row)
    require_published_policy(db, tenant, snapshot.policy)
    verify_source_artifact(db, row.snapshot_id, tenant)
    pending = db.scalar(
        select(func.count())
        .select_from(JobRow)
        .where(JobRow.tenant_id == tenant, JobRow.status.in_(["QUEUED", "RUNNING", "VALIDATING"]))
    )
    if pending >= db.info.get("max_pending_jobs", 8):
        raise AppError(
            429,
            "RATE_LIMITED",
            "Tenant pending solve quota reached; retry after an active job finishes",
            id,
        )
    job = JobRow(
        tenant_id=tenant,
        scenario_id=row.id,
        scenario_version=row.version,
        snapshot_hash=row.snapshot_hash,
        policy_hash=row.policy_hash,
        requested_by=actor,
        trace_context=capture_trace_context(),
        status="QUEUED",
        progress=0,
        attempt=0,
        max_wall_seconds=body.max_wall_seconds,
        compare_baselines=body.compare_baselines,
        created_at=utcnow(),
        started_at=None,
        finished_at=None,
        lease_owner=None,
        lease_until=None,
        plan_id=None,
        error_code=None,
    )
    db.add(job)
    db.flush()
    db.add(
        OutboxRow(
            tenant_id=tenant,
            job_id=job.id,
            created_at=utcnow(),
            published_at=None,
            delivery_attempts=0,
        )
    )
    annotate(
        **{
            "job.id": job.id,
            "scenario.id": row.id,
            "snapshot.hash": job.snapshot_hash,
            "policy.hash": job.policy_hash,
        }
    )
    row.latest_job_id, row.latest_plan_id, row.state = job.id, None, "SOLVING"
    return job_wire(job)
