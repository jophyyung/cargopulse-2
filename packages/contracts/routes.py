"""HTTP contract registry used to freeze the initial OpenAPI surface.

The running API must match this registry. This module never serves application traffic.
"""

from uuid import UUID

from cargopulse_contracts.models import (
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
    ScenarioPage,
    ScenarioRecord,
    ScenarioSnapshot,
    SnapshotReceipt,
    SolveRequest,
)
from fastapi import FastAPI, Header, Query


def contract_app() -> FastAPI:
    app = FastAPI(title="CargoPulse API", version="1.0.0")
    responses = {code: {"model": Problem} for code in (400, 401, 403, 404, 409, 422, 429, 503)}

    def add(method: str, path: str, model: type, status: int = 200, body: type | None = None):
        # Signature construction keeps the exact body models in the OpenAPI registry.
        import inspect

        async def endpoint(**kwargs):
            raise RuntimeError("Contract registry is not an application server")

        params = []
        for segment in path.split("/"):
            if segment.startswith("{"):
                params.append(
                    inspect.Parameter(
                        segment[1:-1], inspect.Parameter.KEYWORD_ONLY, annotation=UUID
                    )
                )
        if body:
            params.append(
                inspect.Parameter("body", inspect.Parameter.KEYWORD_ONLY, annotation=body)
            )
        if method == "POST":
            params.append(
                inspect.Parameter(
                    "idempotency_key",
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=str,
                    default=Header(alias="Idempotency-Key"),
                )
            )
        if path.endswith(("/solve", "/decisions", "/supersede")):
            params.append(
                inspect.Parameter(
                    "if_match",
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=str,
                    default=Header(alias="If-Match"),
                )
            )
        if path in ("/events", "/audit"):
            params += [
                inspect.Parameter(
                    "limit",
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=int,
                    default=Query(default=50, ge=1, le=100),
                ),
                inspect.Parameter(
                    "cursor", inspect.Parameter.KEYWORD_ONLY, annotation=str | None, default=None
                ),
            ]
        endpoint.__signature__ = inspect.Signature(params)
        endpoint.__name__ = method.lower() + path.replace("/", "_").replace("{", "").replace(
            "}", ""
        )
        app.add_api_route(
            "/api/v1" + path,
            endpoint,
            methods=[method],
            response_model=model,
            status_code=status,
            responses=responses,
        )

    for method, path, model, status, body in [
        ("GET", "/me", Principal, 200, None),
        ("GET", "/events", ScenarioPage, 200, None),
        ("POST", "/imports/validate", ImportRecord, 202, ImportRequest),
        ("GET", "/imports/{id}", ImportRecord, 200, None),
        ("POST", "/imports/{id}/commit", SnapshotReceipt, 201, None),
        ("POST", "/scenarios", ScenarioRecord, 201, CreateScenario),
        ("GET", "/scenarios/{id}", ScenarioRecord, 200, None),
        ("GET", "/scenarios/{id}/candidates", CandidateSet, 200, None),
        ("POST", "/scenarios/{id}/solve", JobRecord, 202, SolveRequest),
        ("POST", "/scenarios/{id}/supersede", ScenarioRecord, 201, CreateScenario),
        ("GET", "/jobs/{id}", JobRecord, 200, None),
        ("GET", "/plans/{id}", PlanRecord, 200, None),
        ("GET", "/plans/{id}/alternatives", PlanList, 200, None),
        ("POST", "/plans/{id}/decisions", DecisionReceipt, 201, DecisionRequest),
        ("GET", "/policies", PolicyPage, 200, None),
        ("GET", "/metrics", MetricsPage, 200, None),
        ("GET", "/audit", AuditPage, 200, None),
        ("GET", "/fixtures/recover", ScenarioSnapshot, 200, None),
        ("GET", "/health/live", Health, 200, None),
        ("GET", "/health/ready", Health, 200, None),
    ]:
        add(method, path, model, status, body)
    return app
