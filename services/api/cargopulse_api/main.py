"""Real synthetic-only CargoPulse API. No external operational write routes exist."""

import hashlib
import io
import json
import logging
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from cargopulse_contracts import (
    AuditPage,
    CandidateSet,
    CreateScenario,
    DecisionReceipt,
    DecisionRequest,
    Health,
    ImportRecord,
    ImportRequest,
    JobRecord,
    MetricsPage,
    PlanList,
    PlanRecord,
    PolicyPage,
    Principal,
    Problem,
    ProtectPlan,
    RuleSet,
    ScenarioPage,
    ScenarioRecord,
    ScenarioSnapshot,
    SnapshotReceipt,
    SolveRequest,
    UrgencyPoint,
    canonical_hash,
)
from fastapi import Depends, FastAPI, File, Form, Header, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from opentelemetry.trace import SpanKind
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import domain as d
from .config import Settings
from .controlled_csv import ControlledCSVError, SpreadsheetCSVWriter, parse_controlled_csv
from .db import DEV_IDENTITIES, aware, configure, scope, seed_development, utcnow
from .observability import (
    Telemetry,
    annotate,
    configure_logging,
    extract_trace_context,
    safe_attributes,
)
from .security import (
    AppError,
    audit,
    authenticate,
    cookie_name,
    create_session,
    csrf_cookie,
    csrf_guard,
    existing_csrf,
    oidc_callback,
    oidc_login,
    require,
)
from .storage import PrivateObjects
from .tables import (
    AuditRow,
    DecisionRow,
    Identity,
    ImportBatch,
    JobRow,
    PlanRow,
    PolicyRow,
    ScenarioRow,
)

logger = logging.getLogger("cargopulse.api")
ERRORS = {code: {"model": Problem} for code in (400, 401, 403, 404, 409, 422, 429, 503)}


class DevelopmentLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identity_id: str = Field(min_length=1, max_length=30)


class CsrfToken(BaseModel):
    csrf: str


class PolicyDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy: RuleSet


class PolicyRecord(BaseModel):
    id: UUID
    state: str
    policy_hash: str
    policy: RuleSet
    authored_by: str
    reviewed_by: str | None


def database(request: Request):
    with request.app.state.factory() as db:
        request.state.db = db
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


def principal(request: Request, db=Depends(database, scope="function")):
    p = authenticate(request, db)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        csrf_guard(request, request.state.session)
    return p


def read_principal(p=Depends(principal)):
    require(p, "controller", "load_analyst", "manager", "auditor", "data_steward", "tenant_admin")
    return p


def tenant(p):
    return str(p.tenant_id)


def command(db, request, p, key, op, body, status, fn):
    return d.idempotent(db, request, p, key, op, body, status, fn)


def create_app(settings: Settings | None = None):
    config = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        config.validate()
        configure_logging()
        telemetry = Telemetry(config, "cargopulse-api")
        engine = None
        try:
            engine, factory = configure(config, telemetry)
            app.state.telemetry = telemetry
            app.state.engine, app.state.factory = engine, factory
            app.state.objects = PrivateObjects(config)
            if config.development_auth:
                seed_development(factory)
            yield
        finally:
            if engine is not None:
                engine.dispose()
            telemetry.shutdown()

    app = FastAPI(title="CargoPulse API", version="1.0.0", lifespan=lifespan)
    app.state.settings = config

    async def boundary_response(request, call_next):
        request.state.correlation_id = str(uuid4())
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > config.max_body_bytes):
            return problem_response(
                request, 413, "PAYLOAD_TOO_LARGE", "Request body exceeds the bounded limit"
            )
        # Count streamed chunks as well; Content-Length is not a trust boundary.
        received = 0
        original_receive = request._receive

        async def bounded_receive():
            nonlocal received
            message = await original_receive()
            received += len(message.get("body", b""))
            if received > config.max_body_bytes:
                raise AppError(413, "PAYLOAD_TOO_LARGE", "Request body exceeds the bounded limit")
            return message

        request._receive = bounded_receive
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = request.state.correlation_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.middleware("http")
    async def boundaries(request, call_next):
        telemetry = request.app.state.telemetry
        status = 500
        with telemetry.operation(
            "http.request", context=extract_trace_context(request.headers), kind=SpanKind.SERVER
        ) as span:
            try:
                response = await boundary_response(request, call_next)
                response.headers["Referrer-Policy"] = "no-referrer"
                status = response.status_code
                return response
            finally:
                route = request.scope.get("route")
                template = route.path if route else "unmatched"
                method = (
                    request.method
                    if request.method
                    in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
                    else "OTHER"
                )
                annotate(
                    **{
                        "http.request.method": method,
                        "http.route": template,
                        "http.response.status_code": status,
                        "correlation.id": getattr(request.state, "correlation_id", ""),
                    }
                )
                # The path comes from the matched server route, never the URL.
                safe_route = safe_attributes({"http.route": template}).get(
                    "http.route", "unmatched"
                )
                span.update_name(f"{method} {safe_route}")

    def problem_response(request, status, code, detail, issues=None):
        return JSONResponse(
            Problem(
                type=f"urn:cargopulse:problem:{code.lower()}",
                title=code,
                status=status,
                detail=detail,
                code=code,
                correlation_id=request.state.correlation_id,
                quality_issues=issues or [],
            ).model_dump(mode="json"),
            status_code=status,
            media_type="application/problem+json",
            headers={"Retry-After": "30"} if status == 429 else None,
        )

    @app.exception_handler(AppError)
    async def app_error(request, error):
        db = getattr(request.state, "db", None)
        if db:
            db.rollback()
        p = getattr(request.state, "principal", None)
        if p:
            # Independent transaction makes denial survive the rejected command rollback.
            with app.state.factory.begin() as deny:
                audit(
                    deny,
                    tenant(p),
                    p.subject,
                    request.method
                    + " "
                    + (
                        request.scope.get("route").path if request.scope.get("route") else "unknown"
                    ),
                    error.resource,
                    "DENIED",
                    request.state.correlation_id,
                    error.code,
                )
        return problem_response(request, error.status, error.code, error.detail, error.issues)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        details = "; ".join(
            ".".join(str(x) for x in e["loc"]) + ": " + e["type"] for e in error.errors()[:20]
        )
        return await app_error(request, AppError(422, "INVALID_REQUEST", details))

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, error):
        return await app_error(
            request, AppError(error.status_code, "HTTP_ERROR", "Request could not be processed")
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request, error):
        logger.error(
            "request_failed correlation_id=%s exception_type=%s",
            request.state.correlation_id,
            type(error).__name__,
        )
        return problem_response(request, 500, "INTERNAL_ERROR", "Unexpected server failure")

    @app.exception_handler(IntegrityError)
    async def integrity_error(request, error):
        return await app_error(
            request,
            AppError(409, "VERSION_CONFLICT", "Concurrent command or immutable record conflict"),
        )

    @app.exception_handler(OperationalError)
    async def operational_error(request, error):
        return problem_response(request, 503, "DEPENDENCY_NOT_READY", "Database is unavailable")

    def route(method, path, model=None, status=200):
        return app.api_route(
            "/api/v1" + path,
            methods=[method],
            response_model=model,
            status_code=status,
            responses=ERRORS,
        )

    @route("POST", "/auth/development", Principal)
    def development(
        body: DevelopmentLogin,
        request: Request,
        response: Response,
        db=Depends(database, scope="function"),
    ):
        if not config.development_auth or config.environment != "development":
            raise AppError(404, "NOT_FOUND", "Development identity adapter is disabled")
        if request.headers.get("origin") != config.app_base_url:
            raise AppError(
                403, "ORIGIN_REJECTED", "Development login requires the configured Origin"
            )
        if body.identity_id not in DEV_IDENTITIES:
            raise AppError(403, "FORBIDDEN", "Unknown fixed development identity")
        tid = DEV_IDENTITIES[body.identity_id][0]
        scope(db, tid)
        identity = d.get(db, Identity, body.identity_id, tid)
        if not identity.enabled:
            raise AppError(403, "FORBIDDEN", "Identity is disabled")
        p = create_session(
            db,
            identity,
            "development",
            response,
            config,
            request.cookies.get(cookie_name(config, "session"), ""),
        )
        audit(
            db,
            tid,
            p.subject,
            "auth.development",
            identity.id,
            "SUCCESS",
            request.state.correlation_id,
        )
        return p

    @route("GET", "/auth/csrf", CsrfToken)
    def csrf(
        request: Request,
        response: Response,
        db=Depends(database, scope="function"),
        p=Depends(principal),
    ):
        value = existing_csrf(request, request.state.session)
        csrf_cookie(response, value, config)
        response.headers["X-Session-Expires-In"] = str(
            max(0, int((aware(request.state.session.expires_at) - utcnow()).total_seconds()))
        )
        return {"csrf": value}

    @route("GET", "/auth/login")
    def login(request: Request, db=Depends(database, scope="function")):
        return oidc_login(request, db)

    @route("GET", "/auth/callback")
    def callback(request: Request, code: str, state: str, db=Depends(database, scope="function")):
        return oidc_callback(request, db, code, state)

    @route("POST", "/auth/logout")
    def logout(
        request: Request,
        response: Response,
        db=Depends(database, scope="function"),
        p=Depends(principal),
    ):
        db.delete(request.state.session)
        response.delete_cookie(
            cookie_name(config, "session"),
            path="/",
            secure=config.environment != "development",
            httponly=True,
            samesite="lax",
        )
        response.delete_cookie(
            cookie_name(config, "csrf"),
            path="/",
            secure=config.environment != "development",
            samesite="strict",
        )
        audit(
            db,
            tenant(p),
            p.subject,
            "auth.logout",
            "session",
            "SUCCESS",
            request.state.correlation_id,
        )
        return {"revoked": True}

    @route("GET", "/me", Principal)
    def me(p=Depends(principal)):
        return p

    @route("GET", "/fixtures/recover", ScenarioSnapshot)
    def fixture(db=Depends(database, scope="function"), p=Depends(read_principal)):
        from packages.domain_fixtures.generator import make_snapshot

        row = db.scalar(
            select(PolicyRow)
            .where(PolicyRow.tenant_id == tenant(p), PolicyRow.state == "PUBLISHED")
            .order_by(PolicyRow.created_at.desc())
            .limit(1)
        )
        if not row:
            raise AppError(
                409,
                "POLICY_NOT_PUBLISHED",
                "Publish reviewed synthetic rules before creating fixtures",
            )
        rules = RuleSet.model_validate(row.payload)
        d.require_published_policy(db, tenant(p), rules)
        return make_snapshot(140, tenant_id=p.tenant_id).model_copy(update={"policy": rules})

    @route("POST", "/imports/validate", ImportRecord, 202)
    def import_validate(
        body: ImportRequest,
        request: Request,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        db=Depends(database, scope="function"),
        p=Depends(principal),
    ):
        require(p, "data_steward", "manager")
        return command(
            db,
            request,
            p,
            idempotency_key,
            "imports.validate",
            body.model_dump(mode="json"),
            202,
            lambda: d.validate_import(db, request, p, body.snapshot),
        )

    @route("GET", "/imports/{id}", ImportRecord)
    def import_get(id: UUID, db=Depends(database, scope="function"), p=Depends(principal)):
        require(p, "data_steward", "manager")
        return d.import_wire(d.get(db, ImportBatch, id, tenant(p)))

    @route("POST", "/imports/{id}/commit", SnapshotReceipt, 201)
    def import_commit(
        id: UUID,
        request: Request,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        db=Depends(database, scope="function"),
        p=Depends(principal),
    ):
        require(p, "data_steward", "manager")
        return command(
            db,
            request,
            p,
            idempotency_key,
            f"imports.{id}.commit",
            {},
            201,
            lambda: d.commit_import(db, id, tenant(p)),
        )

    @route("POST", "/imports/upload-csv", ImportRecord, 202)
    def upload_csv(
        request: Request,
        file: UploadFile = File(...),
        metadata: str = Form(...),
        idempotency_key: str = Header(alias="Idempotency-Key"),
        db=Depends(database, scope="function"),
        p=Depends(principal),
    ):
        """Controlled ULD CSV: metadata is a full snapshot excluding cargo_units; nested cells are JSON."""
        require(p, "data_steward", "manager")
        filename = file.filename or ""
        if (
            not 1 <= len(filename) <= 255
            or filename.casefold() == ".csv"
            or not filename.casefold().endswith(".csv")
            or any(character in filename for character in ("/", "\\"))
            or any(ord(character) < 32 or ord(character) == 127 for character in filename)
        ):
            raise AppError(422, "INVALID_CSV", "Choose a .csv file with a valid filename")
        if file.content_type not in ("text/csv", "application/csv"):
            raise AppError(422, "INVALID_CSV", "Only UTF-8 controlled CSV is accepted")
        raw = file.file.read(config.max_body_bytes + 1)
        if len(raw) > config.max_body_bytes:
            raise AppError(413, "PAYLOAD_TOO_LARGE", "CSV exceeds upload limit")
        try:
            snapshot = parse_controlled_csv(raw, metadata)
        except ControlledCSVError as exc:
            raise AppError(
                422, "INVALID_CSV", "Controlled CSV failed validation: " + str(exc)
            ) from None
        return command(
            db,
            request,
            p,
            idempotency_key,
            "imports.upload_csv",
            {"snapshot_hash": canonical_hash(snapshot), "raw_hash": hashlib.sha256(raw).hexdigest()},
            202,
            lambda: d.validate_import(db, request, p, snapshot, raw),
        )

    @route("GET", "/events", ScenarioPage)
    def events(
        limit: int = Query(50, ge=1, le=100),
        cursor: str | None = None,
        db=Depends(database, scope="function"),
        p=Depends(read_principal),
    ):
        stmt = select(ScenarioRow).where(ScenarioRow.tenant_id == tenant(p))
        if cursor:
            stmt = stmt.where(ScenarioRow.id > cursor)
        rows = list(db.scalars(stmt.order_by(ScenarioRow.id).limit(limit + 1)))
        return ScenarioPage(
            items=[d.scenario_wire(db, row) for row in rows[:limit]],
            next_cursor=rows[limit - 1].id if len(rows) > limit else None,
        )

    @route("POST", "/scenarios", ScenarioRecord, 201)
    def scenario_create(
        body: CreateScenario,
        request: Request,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        db=Depends(database, scope="function"),
        p=Depends(principal),
    ):
        require(p, "controller", "manager")
        return command(
            db,
            request,
            p,
            idempotency_key,
            "scenarios.create",
            body.model_dump(mode="json"),
            201,
            lambda: d.create_scenario(db, tenant(p), body),
        )

    @route("GET", "/scenarios/{id}", ScenarioRecord)
    def scenario_get(
        id: UUID,
        response: Response,
        db=Depends(database, scope="function"),
        p=Depends(read_principal),
    ):
        result = d.scenario_wire(db, d.get(db, ScenarioRow, id, tenant(p)))
        response.headers["ETag"] = result.etag
        return result

    @route("GET", "/scenarios/{id}/candidates", CandidateSet)
    def candidates(id: UUID, db=Depends(database, scope="function"), p=Depends(read_principal)):
        snapshot = d.snapshot_for(db, d.get(db, ScenarioRow, id, tenant(p)))
        return d.solver().build_feasible_paths(snapshot, decision_time=utcnow())

    urgency_cache: dict[tuple[str, str, str, str], list] = {}

    @route("GET", "/scenarios/{id}/urgency", list[UrgencyPoint])
    def urgency(
        id: UUID,
        evidence: str = Query("current", pattern="^(current|hold)$"),
        db=Depends(database, scope="function"),
        p=Depends(read_principal),
    ):
        """`evidence=hold` is a visual what-if: evidence judged as of the snapshot."""
        from datetime import timedelta

        require(p, "controller", "load_analyst", "manager")
        snapshot = d.snapshot_for(db, d.get(db, ScenarioRow, id, tenant(p)))
        times = sorted(
            {
                snapshot.as_of,
                *[
                    f.cutoff_at + timedelta(microseconds=1)
                    for f in snapshot.flights
                    if f.cutoff_at >= snapshot.as_of
                ],
            }
        )
        # Snapshots are immutable, so a per-tenant/scenario/hash cache is exact and safe.
        key = (str(tenant(p)), str(id), canonical_hash(snapshot), evidence)
        if key not in urgency_cache:
            if len(urgency_cache) >= 32:
                urgency_cache.pop(next(iter(urgency_cache)))
            urgency_cache[key] = d.solver().compute_urgency_delta(
                snapshot, decision_times=times, hold_evidence=evidence == "hold"
            )
        return urgency_cache[key]

    @route("GET", "/protect/sandbox", ProtectPlan)
    def protect_sandbox(
        seed: int = Query(109, ge=1, le=1_000_000),
        shipments: int = Query(45, ge=10, le=150),
        demand: float = Query(1.5, ge=1.0, le=2.5),
        p=Depends(read_principal),
    ):
        """Stateless synthetic pre-cutoff load plan; no persistence, connector or write."""
        require(p, "controller", "load_analyst", "manager")
        try:
            from cargopulse_protect import (
                SCOPE,
                VOLUMETRIC_KG_PER_M3,
                make_flight,
                plan_priority_fill,
                plan_with_optimizer,
            )
            from cargopulse_validation.protect import check_protect_load
        except ImportError:
            raise AppError(503, "SOLVER_UNAVAILABLE", "The optimizer runtime is not installed")
        flight = make_flight(seed, shipments, demand)
        optimized, opt_info = plan_with_optimizer(flight)
        filled, fill_info = plan_priority_fill(flight)
        rows = [
            {
                "id": s.id,
                "service_class": s.service_class,
                "guaranteed": s.guaranteed,
                "weight_kg": s.weight_kg,
                "volume_m3": s.volume_m3,
                "density_kg_m3": round(s.density, 1),
                "chargeable_kg": s.chargeable_kg,
                "loaded_optimized": s.id in optimized,
                "loaded_priority_fill": s.id in filled,
            }
            for s in flight.shipments
        ]

        def summary(policy, loaded, info):
            on = [r for r in rows if r["id"] in loaded]
            off = [r for r in rows if r["id"] not in loaded]
            weight = sum(r["weight_kg"] for r in on)
            volume = round(sum(r["volume_m3"] for r in on), 2)
            findings = check_protect_load(rows, loaded, flight.payload_kg, flight.volume_m3)
            return {
                "policy": policy,
                "status": info["status"],
                "solve_ms": round(info["solve_ms"], 3),
                "loaded_count": len(on),
                "offloaded_count": len(off),
                "offloaded_priority_count": sum(r["service_class"] != "GENERAL" for r in off),
                "weight_used_kg": weight,
                "volume_used_m3": volume,
                "weight_utilization": min(1.0, round(weight / flight.payload_kg, 4)),
                "volume_utilization": min(1.0, round(volume / flight.volume_m3, 4)),
                "chargeable_carried_kg": sum(r["chargeable_kg"] for r in on),
                "offloaded_weight_kg": sum(r["weight_kg"] for r in off),
                "independent_check": "FAIL" if findings else "PASS",
                "check_findings": findings,
            }

        return ProtectPlan(
            scope=SCOPE,
            synthetic=True,
            seed=seed,
            flight_number=flight.flight_number,
            payload_kg=flight.payload_kg,
            volume_m3=flight.volume_m3,
            volumetric_kg_per_m3=VOLUMETRIC_KG_PER_M3,
            shipments=rows,
            results=[
                summary("CARGOPULSE_LOAD_OPTIMIZER", optimized, opt_info),
                summary("PRIORITY_FILL", filled, fill_info),
            ],
            has_external_write_permission=False,
        )

    @route("POST", "/scenarios/{id}/supersede", ScenarioRecord, 201)
    def supersede(
        id: UUID,
        body: CreateScenario,
        request: Request,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        if_match: str = Header(alias="If-Match"),
        db=Depends(database, scope="function"),
        p=Depends(principal),
    ):
        require(p, "controller", "manager")

        def execute():
            parent = d.get(db, ScenarioRow, id, tenant(p), True)
            if d.scenario_wire(db, parent).etag != if_match:
                raise AppError(409, "VERSION_CONFLICT", "Scenario ETag is stale", id)
            return d.create_scenario(db, tenant(p), body, parent)

        return command(
            db,
            request,
            p,
            idempotency_key,
            f"scenarios.{id}.supersede",
            body.model_dump(mode="json"),
            201,
            execute,
        )

    @route("POST", "/scenarios/{id}/solve", JobRecord, 202)
    def solve(
        id: UUID,
        body: SolveRequest,
        request: Request,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        if_match: str = Header(alias="If-Match"),
        db=Depends(database, scope="function"),
        p=Depends(principal),
    ):
        require(p, "controller", "manager")
        return command(
            db,
            request,
            p,
            idempotency_key,
            f"scenarios.{id}.solve",
            body.model_dump(mode="json"),
            202,
            lambda: d.queue_solve(db, tenant(p), id, body, if_match, p.subject),
        )

    @route("GET", "/jobs/{id}", JobRecord)
    def job_get(id: UUID, db=Depends(database, scope="function"), p=Depends(read_principal)):
        return d.job_wire(d.get(db, JobRow, id, tenant(p)))

    @route("GET", "/plans/{id}", PlanRecord)
    def plan_get(
        id: UUID,
        response: Response,
        db=Depends(database, scope="function"),
        p=Depends(read_principal),
    ):
        result = d.plan_wire(db, d.get(db, PlanRow, id, tenant(p)))
        response.headers["ETag"] = result.etag
        return result

    @route("GET", "/plans/{id}/alternatives", PlanList)
    def alternatives(id: UUID, db=Depends(database, scope="function"), p=Depends(read_principal)):
        plan = d.get(db, PlanRow, id, tenant(p))
        rows = db.scalars(
            select(PlanRow)
            .where(
                PlanRow.tenant_id == tenant(p), PlanRow.job_id == plan.job_id, PlanRow.id != plan.id
            )
            .order_by(PlanRow.policy_name)
        )
        return PlanList(items=[d.plan_wire(db, row) for row in rows])

    @route("POST", "/plans/{id}/decisions", DecisionReceipt, 201)
    def decision(
        id: UUID,
        body: DecisionRequest,
        request: Request,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        if_match: str = Header(alias="If-Match"),
        db=Depends(database, scope="function"),
        p=Depends(principal),
    ):
        require(p, "controller", "manager")

        def execute():
            plan = d.get(db, PlanRow, id, tenant(p), True)
            scenario = d.get(db, ScenarioRow, plan.scenario_id, tenant(p), True)
            if f'"plan-{plan.id}-{plan.plan_hash}"' != if_match:
                raise AppError(409, "VERSION_CONFLICT", "Plan ETag is stale", id)
            if (
                body.expected_snapshot_hash != scenario.snapshot_hash
                or body.expected_plan_hash != plan.plan_hash
            ):
                raise AppError(
                    409, "STALE_PLAN", "Decision hashes differ from current immutable inputs", id
                )
            if (
                not scenario.current
                or scenario.latest_plan_id != plan.id
                or plan.state != "PROPOSED"
            ):
                raise AppError(409, "STALE_PLAN", "Plan is stale or already decided", id)
            if body.action == "APPROVE_IN_APP":
                blockers = d.plan_blockers(db, plan)
                if blockers:
                    raise AppError(409, "STALE_PLAN", ", ".join(blockers), id)
            action_state = {
                "APPROVE_IN_APP": "APPROVED",
                "REJECT": "REJECTED",
                "ESCALATE": "ESCALATED",
            }
            receipt = DecisionReceipt(
                id=uuid4(),
                plan_id=plan.id,
                action=body.action,
                actor=p.subject,
                reason_code=body.reason_code,
                recorded_at=utcnow(),
                snapshot_hash=scenario.snapshot_hash,
                plan_hash=plan.plan_hash,
            )
            db.add(
                DecisionRow(
                    id=str(receipt.id),
                    tenant_id=tenant(p),
                    plan_id=plan.id,
                    scenario_id=scenario.id,
                    payload={**receipt.model_dump(mode="json"), "comment": body.comment},
                    recorded_at=receipt.recorded_at,
                )
            )
            plan.state = scenario.state = action_state[body.action]
            db.flush()
            return receipt

        return command(
            db,
            request,
            p,
            idempotency_key,
            f"plans.{id}.decisions",
            body.model_dump(mode="json"),
            201,
            execute,
        )

    @route("GET", "/policies", PolicyPage)
    def policies(db=Depends(database, scope="function"), p=Depends(read_principal)):
        rows = db.scalars(
            select(PolicyRow).where(
                PolicyRow.tenant_id == tenant(p), PolicyRow.state == "PUBLISHED"
            )
        )
        return PolicyPage(items=[RuleSet.model_validate(row.payload) for row in rows])

    def policy_wire(row):
        return PolicyRecord(
            id=row.id,
            state=row.state,
            policy_hash=row.policy_hash,
            policy=row.payload,
            authored_by=row.authored_by,
            reviewed_by=row.reviewed_by,
        )

    @route("GET", "/policies/{id}", PolicyRecord)
    def policy_get(id: UUID, db=Depends(database, scope="function"), p=Depends(principal)):
        require(p, "manager", "tenant_admin")
        return policy_wire(d.get(db, PolicyRow, id, tenant(p)))

    @route("POST", "/policies/drafts", PolicyRecord, 201)
    def draft(
        body: PolicyDraft,
        request: Request,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        db=Depends(database, scope="function"),
        p=Depends(principal),
    ):
        require(p, "manager")

        def execute():
            proposed = body.policy.model_copy(update={"published_at": utcnow()})
            row = PolicyRow(
                tenant_id=tenant(p),
                policy_hash=canonical_hash(proposed),
                state="DRAFT",
                payload=proposed.model_dump(mode="json"),
                authored_by=p.subject,
                reviewed_by=None,
                created_at=utcnow(),
            )
            db.add(row)
            db.flush()
            return policy_wire(row)

        return command(
            db,
            request,
            p,
            idempotency_key,
            "policies.draft",
            body.model_dump(mode="json"),
            201,
            execute,
        )

    @route("POST", "/policies/{id}/publish", PolicyRecord, 201)
    def publish(
        id: UUID,
        request: Request,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        db=Depends(database, scope="function"),
        p=Depends(principal),
    ):
        require(p, "manager")

        def execute():
            row = d.get(db, PolicyRow, id, tenant(p), True)
            if row.state != "DRAFT" or row.authored_by == p.subject:
                raise AppError(
                    409, "FOUR_EYES_REQUIRED", "A different manager must review the draft", id
                )
            policy = RuleSet.model_validate(
                {
                    **row.payload,
                    "authored_by": row.authored_by,
                    "approved_by": p.subject,
                    "published_at": utcnow(),
                }
            )
            row.payload, row.policy_hash = policy.model_dump(mode="json"), canonical_hash(policy)
            row.reviewed_by, row.state = p.subject, "PUBLISHED"
            return policy_wire(row)

        return command(db, request, p, idempotency_key, f"policies.{id}.publish", {}, 201, execute)

    @route("GET", "/metrics", MetricsPage)
    def metrics(db=Depends(database, scope="function"), p=Depends(read_principal)):
        rows = db.scalars(
            select(PlanRow)
            .where(PlanRow.tenant_id == tenant(p), PlanRow.policy_name == "optimized")
            .order_by(PlanRow.created_at.desc())
            .limit(50)
        )
        return MetricsPage(items=[item for row in rows for item in row.payload.get("metrics", [])])

    @route("GET", "/audit", AuditPage)
    def audit_get(
        limit: int = Query(50, ge=1, le=100),
        cursor: str | None = None,
        db=Depends(database, scope="function"),
        p=Depends(principal),
    ):
        require(p, "auditor", "manager")
        stmt = select(AuditRow).where(AuditRow.tenant_id == tenant(p))
        if cursor:
            stmt = stmt.where(AuditRow.id > cursor)
        rows = list(db.scalars(stmt.order_by(AuditRow.id).limit(limit + 1)))
        return AuditPage(
            items=[
                dict(
                    id=row.id,
                    occurred_at=d.aware(row.occurred_at),
                    actor=row.actor,
                    action=row.action,
                    resource_id=row.resource_id,
                    outcome=row.outcome,
                    correlation_id=row.correlation_id,
                    previous_hash=row.previous_hash,
                    event_hash=row.event_hash,
                )
                for row in rows[:limit]
            ],
            next_cursor=rows[limit - 1].id if len(rows) > limit else None,
        )

    @route("GET", "/reports/{id}/export")
    def export(
        id: UUID,
        request: Request,
        format: str = Query("json", pattern="^(json|csv|pdf)$"),
        db=Depends(database, scope="function"),
        p=Depends(read_principal),
    ):
        plan = d.plan_wire(db, d.get(db, PlanRow, id, tenant(p)))
        data = plan.model_dump(mode="json")
        scenario = d.get(db, ScenarioRow, plan.scenario_id, tenant(p))
        snapshot = d.snapshot_for(db, scenario)
        checked = d.validate(snapshot, plan.plan)
        if checked.status != "PASS":
            raise AppError(
                409,
                "EVIDENCE_REVALIDATION_FAILED",
                "Stored proposal evidence failed independent verification",
            )
        data["source_provenance"] = snapshot.provenance.model_dump(mode="json")
        data["event_as_of_utc"] = snapshot.as_of.isoformat()
        data["model_scope_notice"] = (
            "Synthetic conservative envelope; no aviation certification or external write"
        )
        audit(
            db,
            tenant(p),
            p.subject,
            "reports.export",
            id,
            "SUCCESS",
            request.state.correlation_id,
            format,
        )
        headers = {"Content-Disposition": f'attachment; filename="synthetic-plan-{id}.{format}"'}
        if format == "json":
            return JSONResponse(data, headers=headers)
        if format == "csv":
            buffer = io.StringIO()
            writer = SpreadsheetCSVWriter(buffer)
            writer.writerow(
                ["SYNTHETIC", "TEAM_SYNTHETIC_UNVERIFIED", "No external write permission"]
            )
            writer.writerow(
                [
                    "snapshot_hash",
                    data["plan"]["snapshot_hash"],
                    "policy_hash",
                    data["plan"]["policy_hash"],
                ]
            )
            writer.writerow(
                ["cargo_unit_id", "path_id", "arrival_at_utc", "weighted_delay_hours", "state"]
            )
            for row in data["plan"]["assignments"]:
                values = [
                    row["cargo_unit_id"],
                    row["path_id"],
                    row["arrival_at"],
                    row["weighted_delay_hours"],
                    data["state"],
                ]
                writer.writerow(values)
            writer.writerow([])
            writer.writerow(["plan_hash", plan.plan_hash, "plan_state", plan.state])
            metric_fields = list(plan.plan.metrics[0].model_dump(mode="json"))
            writer.writerow(metric_fields)
            for metric in plan.plan.metrics:
                data_fields = metric.model_dump(mode="json")
                writer.writerow(
                    [
                        json.dumps(data_fields[field], ensure_ascii=False)
                        if isinstance(data_fields[field], list)
                        else data_fields[field]
                        for field in metric_fields
                    ]
                )
            return Response(buffer.getvalue(), media_type="text/csv", headers=headers)
        # Minimal standards-compliant PDF text report, deliberately no untrusted rich markup.
        lines = [
            "CargoPulse SYNTHETIC decision report",
            "TEAM_SYNTHETIC_UNVERIFIED - no external write",
            f"Plan: {id}",
            f"State: {plan.state}; external write: NO",
            f"Plan SHA-256: {plan.plan_hash}",
            "Proposal metrics describe proposed first departure, not approved or booked capacity.",
            f"Snapshot: {plan.plan.snapshot_hash}",
            f"Policy: {plan.plan.policy_hash}",
            f"Assigned whole ULDs: {len(plan.plan.assignments)}",
            f"Unassigned whole ULDs: {len(plan.plan.unassigned)}",
            "Model: synthetic conservative envelope",
        ]
        lines += [
            f"Source: {snapshot.provenance.source_id}; event as-of UTC: {snapshot.as_of.isoformat()}"
        ]
        for m in plan.plan.metrics:
            lines += [
                f"Metric: {m.name}; value: {m.value}; status: {m.status}",
                f"Numerator: {m.numerator}; denominator: {m.denominator}; unit: {m.unit}",
                f"Method: {m.metric_method_version}; statistic: {m.statistic}",
                f"Scenario: {m.scenario_type}; cohort: {m.cohort_id}; tier: {m.evidence_tier}",
                f"UTC window: {m.window_start_utc.isoformat()} to {m.window_end_utc.isoformat()}",
                f"Event as-of UTC: {m.event_as_of_utc.isoformat()}; baseline: {m.baseline_policy_version}",
                f"Source IDs: {json.dumps(m.data_source_ids, ensure_ascii=False)}",
                f"Snapshot SHA-256: {m.snapshot_hash}",
                f"Policy SHA-256: {m.policy_hash}",
                "",
            ]
        return Response(build_pdf(lines), media_type="application/pdf", headers=headers)

    @route("GET", "/health/live", Health)
    def live():
        return Health(status="ok", dependencies={"runtime": "ok"})

    @route("GET", "/health/ready", Health)
    def ready(response: Response, db=Depends(database, scope="function")):
        dependencies = {}
        try:
            db.execute(text("SELECT 1"))
            # A reachable database with missing release tables/columns is not ready.
            db.execute(text("SELECT trace_context FROM solve_jobs LIMIT 0"))
            db.execute(text("SELECT authentication_context_hash FROM sessions LIMIT 0"))
            dependencies[
                "postgresql" if db.bind.dialect.name == "postgresql" else "sqlite_development"
            ] = "ok"
        except Exception:
            db.rollback()
            dependencies["database"] = "unavailable"
        try:
            import redis

            redis.Redis.from_url(
                config.redis_url, socket_connect_timeout=1, socket_timeout=1
            ).ping()
            dependencies["redis_hint_broker"] = "ok"
        except Exception:
            dependencies["redis_hint_broker"] = "degraded_durable_database_polling"
        try:
            dependencies["private_object_store"] = app.state.objects.probe()
        except Exception:
            dependencies["private_object_store"] = "unavailable"
        import importlib.util

        for module in ("cargopulse_optimizer", "cargopulse_validation"):
            dependencies[module] = "ok" if importlib.util.find_spec(module) else "unavailable"
        required_ok = dependencies.get("database") != "unavailable" and all(
            value != "unavailable" for value in dependencies.values()
        )
        app.state.telemetry.readiness.set(1 if required_ok else 0)
        if not required_ok:
            response.status_code = 503
        return Health(status="ok" if required_ok else "unavailable", dependencies=dependencies)

    return app


def build_pdf(lines):
    import textwrap

    # Fixed-pitch text and bounded wrapping preserve long hashes/lineage on page.
    # Escapes retain non-ASCII identifier code points instead of silently losing them.
    rendered = []
    for line in lines:
        value = str(line).encode("ascii", "backslashreplace").decode()
        rendered.extend(textwrap.wrap(value, width=128, break_on_hyphens=False) or [""])
    if any(not str(line).isascii() for line in lines):
        rendered.append(
            "Non-ASCII identifiers use Unicode escapes; JSON retains the original text."
        )

    def escape(value):
        return (
            str(value)
            .encode("ascii", "replace")
            .decode()
            .replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )

    # Keep a metric's provenance together when it fits on a page.
    blocks, block = [], []
    for line in rendered:
        block.append(line)
        if not line:
            blocks.append(block)
            block = []
    if block:
        blocks.append(block)
    chunks, chunk = [], []
    for block in blocks:
        if chunk and len(chunk) + len(block) > 40:
            chunks.append(chunk)
            chunk = []
        while len(block) > 40:
            chunks.append(block[:40])
            block = block[40:]
        chunk.extend(block)
    if chunk or not chunks:
        chunks.append(chunk)
    objects = [b"", b""]
    page_ids = []
    font_id = 3 + len(chunks) * 2
    for page_number, chunk in enumerate(chunks, 1):
        chunk = [
            "CargoPulse - SYNTHETIC / NOT CONNECTED - No external write",
            f"Decision evidence | Page {page_number} of {len(chunks)}",
            "",
            *chunk,
        ]
        page_id = len(objects) + 1
        page_ids.append(page_id)
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 792 612] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {page_id + 1} 0 R >>".encode()
        )
        stream = (
            "BT /F1 9 Tf 35 575 Td 12 TL "
            + " ".join(f"({escape(line)}) Tj T*" for line in chunk)
            + " ET"
        ).encode()
        objects.append(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = (
        "<< /Type /Pages /Kids ["
        + " ".join(f"{i} 0 R" for i in page_ids)
        + f"] /Count {len(page_ids)} >>"
    ).encode()
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(output)


app = create_app()
