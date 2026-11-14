"""Durable leased DB worker. Redis messages are advisory and may all be lost."""

import logging
import os
import time
from contextlib import nullcontext
from datetime import timedelta
from uuid import uuid4

from cargopulse_contracts import ScenarioSnapshot, SolutionPlan, canonical_hash
from sqlalchemy import func, or_, select

from . import domain as d
from .config import Settings
from .db import aware, configure, lock_tenant, scope, utcnow
from .observability import Telemetry, annotate, configure_logging, extract_trace_context
from .security import AppError, audit
from .tables import JobRow, OutboxRow, PlanRow, ScenarioRow, SnapshotRow, Tenant

logger = logging.getLogger("cargopulse.worker")


def publish_hints(factory, redis_url):
    """Publication may repeat after a crash; SQL rows remain the complete queue."""
    import redis

    broker = redis.Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
    with factory() as inventory:
        tenants = list(inventory.scalars(select(Tenant.id)))
    for tenant in tenants:
        with factory.begin() as db:
            scope(db, tenant)
            rows = list(
                db.scalars(
                    select(OutboxRow)
                    .where(OutboxRow.tenant_id == tenant, OutboxRow.published_at.is_(None))
                    .order_by(OutboxRow.created_at)
                    .with_for_update(skip_locked=True)
                    .limit(100)
                )
            )
            for row in rows:
                row.delivery_attempts += 1
                try:
                    broker.lpush("cargopulse:solve:hints", row.job_id)
                    broker.ltrim("cargopulse:solve:hints", 0, 9999)
                except redis.RedisError:
                    return
                row.published_at = utcnow()


def claim_job(factory, owner):
    with factory() as db:
        tenants = list(db.scalars(select(Tenant.id).order_by(Tenant.id)))
    cursor = getattr(factory, "_cargopulse_tenant_cursor", None)
    if cursor in tenants:
        next_index = tenants.index(cursor) + 1
        tenants = tenants[next_index:] + tenants[:next_index]
    for tenant in tenants:
        with factory.begin() as db:
            scope(db, tenant)
            lock_tenant(db, tenant)
            job = db.scalar(
                select(JobRow)
                .where(
                    JobRow.tenant_id == tenant,
                    or_(
                        JobRow.status == "QUEUED",
                        (JobRow.status.in_(["RUNNING", "VALIDATING"]))
                        & (JobRow.lease_until < utcnow()),
                    ),
                )
                .order_by(JobRow.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if not job:
                continue
            if job.attempt >= 3:
                job.status, job.error_code, job.finished_at = (
                    "FAILED",
                    "LEASE_RETRY_EXHAUSTED",
                    utcnow(),
                )
                job.lease_owner, job.lease_until = None, None
                scenario = d.get(db, ScenarioRow, job.scenario_id, tenant, True)
                if scenario.current and scenario.latest_job_id == job.id:
                    scenario.state = "SOLVER_ERROR"
                audit(
                    db,
                    tenant,
                    "service:worker",
                    "solve.failed",
                    job.id,
                    "FAILED",
                    str(uuid4()),
                    job.error_code,
                )
                continue
            job.status, job.progress = "RUNNING", 5
            job.attempt += 1
            job.lease_owner, job.lease_until = owner, utcnow() + timedelta(seconds=300)
            job.started_at = job.started_at or utcnow()
            factory._cargopulse_tenant_cursor = tenant
            return tenant, job.id
    return None


def process_one(factory, owner=None, telemetry=None):
    owner = owner or str(uuid4())
    claimed = claim_job(factory, owner)
    if not claimed:
        return False
    tenant, job_id = claimed
    telemetry = telemetry or factory.kw.get("info", {}).get("telemetry")
    if telemetry is None:
        return _execute_claimed(factory, owner, tenant, job_id, None)
    with factory() as db:
        scope(db, tenant)
        job = d.get(db, JobRow, job_id, tenant)
        parent = extract_trace_context(job.trace_context)
        attributes = {
            "job.id": job.id,
            "scenario.id": job.scenario_id,
            "job.attempt": job.attempt,
            "snapshot.hash": job.snapshot_hash,
            "policy.hash": job.policy_hash,
        }
        telemetry.queue_wait.record(max(0, (utcnow() - aware(job.created_at)).total_seconds()))
    with telemetry.operation("job.process", context=parent, attributes=attributes):
        return _execute_claimed(factory, owner, tenant, job_id, telemetry)


def _execute_claimed(factory, owner, tenant, job_id, telemetry):
    try:
        with factory() as db:
            scope(db, tenant)
            lock_tenant(db, tenant)
            job = d.get(db, JobRow, job_id, tenant)
            scenario = d.get(db, ScenarioRow, job.scenario_id, tenant)
            snapshot = ScenarioSnapshot.model_validate(
                d.get(db, SnapshotRow, scenario.snapshot_id, tenant).payload
            )
            d.verify_source_artifact(db, scenario.snapshot_id, tenant)
            d.require_published_policy(db, tenant, snapshot.policy)
            if (
                canonical_hash(snapshot) != job.snapshot_hash
                or canonical_hash(snapshot.policy) != job.policy_hash
            ):
                raise AppError(
                    409, "IMMUTABLE_INPUT_MISMATCH", "Stored job input hashes do not match"
                )
            max_seconds, compare = job.max_wall_seconds, job.compare_baselines
        optimizer = d.solver()
        with telemetry.operation("solve") if telemetry else nullcontext():
            results = [
                (
                    "optimized",
                    SolutionPlan.model_validate(
                        optimizer.run_solver(snapshot, max_wall_seconds=max_seconds)
                    ),
                )
            ]
            if compare:
                results += [
                    (
                        "earliest",
                        SolutionPlan.model_validate(optimizer.run_baseline_earliest(snapshot)),
                    ),
                    (
                        "priority",
                        SolutionPlan.model_validate(optimizer.run_baseline_priority(snapshot)),
                    ),
                ]
            annotate(
                **{
                    "cargo.count": len(snapshot.cargo_units),
                    "assignment.count": len(results[0][1].assignments),
                    "engine.version": results[0][1].solver.version,
                    "solver.status": results[0][1].solver.status,
                }
            )
        with factory.begin() as db:
            scope(db, tenant)
            lock_tenant(db, tenant)
            job = d.get(db, JobRow, job_id, tenant, True)
            if job.lease_owner != owner or job.status not in ("RUNNING", "VALIDATING"):
                annotate(outcome="abandoned")
                return True  # A reclaimed or terminal job can never be overwritten by this worker.
            if aware(job.lease_until) <= utcnow():
                annotate(outcome="abandoned")
                return True
            job.status, job.progress = "VALIDATING", 80
        with telemetry.operation("independent_validate") if telemetry else nullcontext():
            checked = []
            for name, plan in results:
                result = d.validate(snapshot, plan, utcnow())
                checked.append((name, plan.model_copy(update={"independent_validation": result})))
            annotate(
                outcome="quarantined"
                if any(plan.independent_validation.status != "PASS" for _, plan in checked)
                else "success"
            )
        with factory.begin() as db:
            scope(db, tenant)
            lock_tenant(db, tenant)
            job = d.get(db, JobRow, job_id, tenant, True)
            scenario = d.get(db, ScenarioRow, job.scenario_id, tenant, True)
            if (
                job.lease_owner != owner
                or job.status != "VALIDATING"
                or aware(job.lease_until) <= utcnow()
            ):
                annotate(outcome="abandoned")
                return True
            # Any invalid output quarantines the entire solve, including alternatives.
            invalid = any(plan.independent_validation.status != "PASS" for _, plan in checked)
            stale = (
                not scenario.current
                or scenario.latest_job_id != job_id
                or scenario.version != job.scenario_version
                or bool(d.freshness(snapshot))
            )
            for name, plan in checked:
                existing = db.scalar(
                    select(PlanRow).where(
                        PlanRow.tenant_id == tenant,
                        PlanRow.job_id == job_id,
                        PlanRow.policy_name == name,
                    )
                )
                if existing:
                    continue
                row = PlanRow(
                    tenant_id=tenant,
                    job_id=job.id,
                    scenario_id=scenario.id,
                    scenario_version=job.scenario_version,
                    policy_name=name,
                    plan_hash=canonical_hash(plan),
                    payload=plan.model_dump(mode="json"),
                    state="QUARANTINED" if invalid else "STALE" if stale else "PROPOSED",
                    created_at=utcnow(),
                )
                db.add(row)
                db.flush()
                if name == "optimized":
                    job.plan_id = row.id
                    if not stale:
                        scenario.latest_plan_id = row.id
            job.status, job.progress, job.finished_at = "COMPLETED", 100, utcnow()
            job.lease_until, job.lease_owner = None, None
            if not stale:
                optimized = checked[0][1]
                scenario.state = (
                    "SOLVER_ERROR"
                    if invalid
                    else "PLAN_READY"
                    if (
                        optimized.assignments
                        and optimized.solver.status
                        in ("OPTIMAL", "FEASIBLE", "TIME_LIMIT_WITH_FEASIBLE")
                    )
                    else "NO_FEASIBLE_PLAN"
                )
            annotate(outcome="quarantined" if invalid else "success")
            if invalid:
                job.error_code = "INDEPENDENT_VALIDATION_FAILED"
                logger.error("independent_validation_failed job_id=%s", job.id)
            audit(
                db,
                tenant,
                "service:worker",
                "solve.completed",
                job.id,
                "QUARANTINED" if invalid else "SUCCESS",
                str(uuid4()),
                job.error_code or "",
            )
    except Exception as exc:
        annotate(outcome="failure")
        code = exc.code if isinstance(exc, AppError) else "SOLVER_EXECUTION_FAILED"
        logger.error(
            "solve_failed job_id=%s code=%s exception_type=%s", job_id, code, type(exc).__name__
        )
        with factory.begin() as db:
            scope(db, tenant)
            lock_tenant(db, tenant)
            job = d.get(db, JobRow, job_id, tenant, True)
            if job.lease_owner == owner and job.status in ("RUNNING", "VALIDATING"):
                job.status, job.error_code, job.finished_at = "FAILED", code, utcnow()
                job.lease_owner, job.lease_until = None, None
                scenario = d.get(db, ScenarioRow, job.scenario_id, tenant, True)
                if scenario.current and scenario.latest_job_id == job_id:
                    scenario.state = "SOLVER_ERROR"
                audit(
                    db,
                    tenant,
                    "service:worker",
                    "solve.failed",
                    job.id,
                    "FAILED",
                    str(uuid4()),
                    code,
                )
    return True


def observe_queue(factory, telemetry):
    """Measure real DB inventory under each tenant scope, without tenant labels."""
    totals = {status: 0 for status in ("QUEUED", "RUNNING", "VALIDATING", "COMPLETED", "FAILED")}
    oldest = None
    with factory() as inventory:
        tenants = list(inventory.scalars(select(Tenant.id)))
    for tenant in tenants:
        with factory() as db:
            scope(db, tenant)
            for status, count, created in db.execute(
                select(JobRow.status, func.count(), func.min(JobRow.created_at))
                .where(JobRow.tenant_id == tenant)
                .group_by(JobRow.status)
            ):
                if status in totals:
                    totals[status] += count
                if status == "QUEUED" and created is not None:
                    value = aware(created)
                    oldest = value if oldest is None else min(oldest, value)
    for status, count in totals.items():
        telemetry.queue_depth.set(count, {"status": status})
    telemetry.queue_age.set(max(0, (utcnow() - oldest).total_seconds()) if oldest else 0)


def main():
    settings = Settings.from_env()
    settings.validate()
    configure_logging()
    telemetry = Telemetry(settings, "cargopulse-worker")
    engine, factory = configure(settings, telemetry)
    owner = os.getenv("WORKER_ID") or f"worker-{uuid4()}"
    logger.info("worker_started")
    try:
        while True:
            try:
                observe_queue(factory, telemetry)
                publish_hints(factory, settings.redis_url)
                if not process_one(factory, owner):
                    time.sleep(1)
            except Exception as exc:
                logger.error("worker_poll_failed exception_type=%s", type(exc).__name__)
                time.sleep(2)
    finally:
        engine.dispose()
        telemetry.shutdown()


if __name__ == "__main__":
    main()
