# Runtime observability and stable migration history

Status: DONE for this bounded engineering lane; integration/release approval remains
with the lead. Base: `069c9d43e7c271ac351dd35829e0fb7a5a52206f`;
branch: `feature/runtime-observability`.

## Implemented scope

- Frozen `0001_initial.py` now contains explicit Alembic table/index/constraint DDL
  for the original 13 operational tables. It imports no current ORM metadata.
  `oidc_flows` remains a `0002` addition; `0003` immutable triggers are unchanged.
- Additive `0004_job_trace_context.py` adds nullable JSONB `solve_jobs.trace_context`
  on PostgreSQL (JSON in development SQLite). Existing rows remain NULL. The HTTP
  DTOs, endpoint definitions, permissions, optimizer and validator are unchanged.
- API and worker own separate SDK tracer/meter providers with service names
  `cargopulse-api` and `cargopulse-worker`. Providers are not set globally, are
  shut down per lifespan, and tolerate repeated TestClient lifespans. Startup
  failure also shuts down a newly created telemetry runtime.
- HTTP server, ingest validation, snapshot commit, scenario creation, job enqueue,
  durable worker execution, solve/baselines and independent validation have real
  SDK spans. HTTP records the matched route template, bounded method and status.
  Worker solve spans include numeric engine version, solver status and counts.
- `propagate.inject` stores only the allowlisted W3C `traceparent` in the job's DB
  row. A new worker process reloads that row and `propagate.extract` creates the
  parent context. Baggage and tracestate are excluded on injection and extraction.
  Legacy NULL contexts create independent roots. The standard random flag (`03`)
  is accepted alongside sampled/unsampled flags.
- JSON operation logs contain service/operation/outcome, elapsed milliseconds,
  trace/span IDs, generated correlation UUIDs and allowlisted identifiers/counts.
  Exception messages, stack locals, identities, tokens, headers, raw URLs/query
  strings, AWBs, cargo content, payloads and comments are not recorded by this
  telemetry implementation. Exceptions mark a span ERROR without recording an
  exception event or description. Privacy checks use explicit sentinel strings;
  they are bounded tests, not proof against every possible future caller.

## Metrics and configuration

An explicit `OTEL_EXPORTER_OTLP_ENDPOINT` **base URL** enables OTLP/HTTP protobuf
export to `<base>/v1/traces` and `<base>/v1/metrics`. Production requires HTTPS;
HTTP is accepted only for development loopback (`localhost`, `127.0.0.1`, `::1`).
Credentials embedded in URLs, query strings and fragments are rejected. The
exporters use three-second request timeouts, trace batching and 30-second metric
exports. Normal shutdown/explicit flush exports buffered measurements. An empty
endpoint constructs no exporter: tests with ordinary explicit Settings do not
inherit signal-specific cloud exporter URLs. Configure a private collector; no
new public metrics endpoint or changed HTTP permission is introduced.

The implemented SDK instruments are:

- `cargopulse.operations`: completed operation counts by bounded operation/outcome.
- `cargopulse.failures`: operation exceptions, HTTP 5xx and quarantined validation
  outcomes; operation labels permit distinguishing nested observations.
- `cargopulse.operation.duration` and `http.server.request.duration`: measured
  latency histograms; HTTP template/method/status permit actual request/error-rate
  aggregation. HTTP 4xx remain distinguishable by status rather than being counted
  as service failures.
- `cargopulse.queue.jobs`: real PostgreSQL inventory by QUEUED/RUNNING/VALIDATING/
  COMPLETED/FAILED, measured through tenant-scoped queries during worker polling.
  Terminal counts represent retained DB history, not a rolling time window.
- `cargopulse.queue.oldest_age`: oldest currently queued creation age, zero only
  after an observed empty queue; `cargopulse.queue.wait`: created-to-claim age per
  actual claim, including retries.
- `cargopulse.readiness`: last actual `/health/ready` result (1 or 0), not a
  background liveness assertion. No readiness sample exists before that check.

Metrics omit job/scenario/tenant/identity labels; IDs remain confined to spans and
logs. Queue measurement queries scan retained job inventory once per poll and
should be profiled/tuned against production retention and volume before scaling.
No fabricated job counts or runtime KPIs are supplied by the application.

## Verification

Runtime: Python 3.12.14; PostgreSQL 18.6 on loopback port 55432; application role
`cargopulse_app` is separate from schema owner `cargopulse`; Redis on port 56379.
All destructive test operations were confined to the separately created database
`cargopulse_observability_backend_test`. Neither the running `cargopulse` database
nor the lead's `cargopulse_backend_test` was migrated or truncated by this lane.

Commands were run from this branch's worktree using the lead's shared virtualenv:

```sh
PY=/Users/pie/CargoPulse_Production_Build_Package/.venv/bin/python
TEST_DB=postgresql+psycopg://cargopulse_app@127.0.0.1:55432/cargopulse_observability_backend_test
BACKEND_TEST_DATABASE_URL="$TEST_DB" OBSERVABILITY_TEST_DATABASE_URL="$TEST_DB" \
  "$PY" -m pytest -q --tb=short
"$PY" -m ruff check .
"$PY" -m ruff check --select S --ignore S101 \
  services/api/cargopulse_api/observability.py \
  services/api/alembic/versions/0001_initial.py \
  services/api/alembic/versions/0004_job_trace_context.py tests/observability
git diff --check
```

The full suite passed **118 tests**, no skips, in **41.10 seconds**. After small
startup-cleanup/test-hardening edits, the focused suite passed **17 tests** in
**8.13 seconds**, followed by the final full suite: **118 passed**, no skips, in
**42.63 seconds** (exit 0). Ruff correctness
and the bounded security checks exited 0. S101 is excluded only because these are
pytest assertions; the one S603 exception describes a fixed Python executable
and literal test script with no shell or request-derived arguments.

Meaningful new evidence includes:

1. Fresh `0001` is inspected while the current ORM already has `trace_context`:
   the column is absent, original columns/indexes match, and OIDC is not created
   early. Fresh upgrade to `0004` and a populated existing `0003` upgrade both
   succeed, retain rows, and preserve all 12 tenant RLS policies.
2. A real local HTTP receiver accepts requests from the pinned OTLP exporter and
   decodes `ExportTraceServiceRequest`/`ExportMetricsServiceRequest` protobuf.
   It checks actual service resource, spans, counter, histogram and gauge values.
3. A non-owner API performs ingest/commit/scenario/enqueue, persists traceparent,
   and ends its lifespan. A **separate Python worker process** opens a new engine,
   reloads the DB job and runs the real HiGHS optimizer plus independent validator.
   The completed plan passes validation; duplicate processing finds no work.
   Decoded OTLP proves matching trace IDs and exact enqueue→worker→solve/validator
   parent relationships. This is repeated with a legacy NULL carrier.
4. Queue depth/oldest age are compared with the real queued DB row; completed
   inventory is checked after worker execution. Readiness comes from the actual
   dependency probe. Failure counters/logs are checked against a raised operation.
5. Invalid paths/query tokens, authorization headers, cargo-title sentinels,
   exception messages and baggage are absent from emitted telemetry. Repeated
   lifespans produce distinct providers without global-provider override warnings.
   Unsampled inbound requests still return 200 and record correct HTTP metrics.

Earlier probes exposed a too-restrictive trace-flags filter (SDK emits `03`) and
a PostgreSQL inspector assertion that also included constraint-backed indexes.
Both were corrected. A later test-only missing `make_url` import produced four
setup errors before being fixed. These failed runs are not passing evidence.
Existing warnings are upstream Starlette/httpx test-client deprecation and six
Alembic `path_separator` configuration deprecations; no provider-reset warning
was observed.

## Dependency and source evidence

The lead approved `opentelemetry-exporter-otlp-proto-http==1.45.2`. Official
[PyPI release metadata](https://pypi.org/pypi/opentelemetry-exporter-otlp-proto-http/1.45.2/json)
was checked on 2026-11-10: version 1.45.2, not yanked, Apache-2.0, SDK compatibility
`~=1.45.2`. `pyproject.toml` and `uv.lock` pin the dependency and transitive hashes.
Seven packages, including the approved exporter and six missing dependencies,
were installed in the shared virtualenv; the lead was informed before installation.

Implementation references are the official [Python exporters documentation](https://opentelemetry.io/docs/languages/python/exporters/),
[Python propagation documentation](https://opentelemetry.io/docs/languages/python/propagation/),
and [W3C Trace Context Level 2 format/flags](https://www.w3.org/TR/trace-context-2/).
Installed SDK/exporter signatures and actual wire messages were also inspected.

## Integration and limits

The lead must merge the session factory's `telemetry` info with its independent
artifact-storage info; main/domain/worker changes can overlap the lead's separate
policy/artifact/lease fixes. This lane deliberately leaves those baseline areas
unchanged. The lead owns requirements-lock generation, generated contract
artifacts, merged full-suite/browser reruns and container checks.

Rollback can use the previous image while retaining the nullable column. Remove
OTLP configuration to disable outbound export; telemetry records are not canonical
business data. `0004` can drop only the new column after stopping new code;
`0002`/`0003` history/security downgrade restrictions remain unchanged. Take the
normal approved backup before schema changes and preserve immutable decisions.

This verifies local synthetic telemetry and migration behavior only. No hosted
collector/dashboard, alert delivery, on-call ownership, Sentry sink, TLS collector,
production collector access control, operational SLA or L1 release is verified.
No web files, shared HTTP contracts, optimizer/validator implementation or root
infrastructure were modified. No push or publication was performed.
