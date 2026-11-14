"""Owned OTel runtimes with allowlisted telemetry and W3C-only job propagation.

Providers are deliberately not global: repeated application lifespans and API /
worker instances can coexist without leaking exporters or resetting SDK globals.
No exporter is constructed until a collector endpoint is explicitly configured.
"""

import json
import logging
import re
import time
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

from opentelemetry import propagate, trace
from opentelemetry.context import Context
from opentelemetry.metrics import NoOpMeterProvider
from opentelemetry.propagators.textmap import Getter, Setter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind, Status, StatusCode

logger = logging.getLogger("cargopulse.telemetry")
TRACEPARENT = re.compile(r"00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$")
IDENTIFIER = re.compile(r"[0-9a-f-]{36}$|[0-9a-f]{64}$")
OPERATIONS = frozenset(
    {
        "http.request",
        "ingest.validate",
        "snapshot.commit",
        "scenario.create",
        "job.enqueue",
        "job.process",
        "solve",
        "independent_validate",
    }
)
COUNT_KEYS = frozenset({"cargo.count", "assignment.count", "job.attempt"})
ID_KEYS = frozenset({"job.id", "scenario.id", "snapshot.hash", "policy.hash", "correlation.id"})
_operation_attributes = ContextVar("cargopulse_operation_attributes", default=None)
METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})


class TraceParentGetter(Getter):
    def get(self, carrier, key):
        value = carrier.get("traceparent", "") if key == "traceparent" else ""
        return [value] if isinstance(value, str) and TRACEPARENT.fullmatch(value) else None

    def keys(self, carrier):
        return ["traceparent"]


class TraceParentSetter(Setter):
    def set(self, carrier, key, value):
        if key == "traceparent" and TRACEPARENT.fullmatch(value):
            carrier[key] = value


def capture_trace_context():
    """Drop baggage and tracestate, even if an SDK global propagator adds them."""
    carrier = {}
    propagate.inject(carrier, setter=TraceParentSetter())
    return carrier or None


def extract_trace_context(carrier):
    # Start from an empty context so a worker never accidentally inherits a poller's
    # unrelated span or baggage. Invalid/legacy/null carriers create a new root.
    return propagate.extract(carrier or {}, context=Context(), getter=TraceParentGetter())


def safe_attributes(values):
    clean = {}
    for key, value in values.items():
        if key in ID_KEYS and isinstance(value, str) and IDENTIFIER.fullmatch(value):
            clean[key] = value
        elif key in COUNT_KEYS and type(value) is int and value >= 0:
            clean[key] = value
        elif (
            key == "engine.version"
            and isinstance(value, str)
            and re.fullmatch(r"[0-9.]{1,30}", value)
        ):
            clean[key] = value
        elif key == "http.request.method" and value in METHODS:
            clean[key] = value
        elif key == "http.response.status_code" and type(value) is int and 100 <= value <= 599:
            clean[key] = value
        elif (
            key == "http.route"
            and isinstance(value, str)
            and (value == "unmatched" or re.fullmatch(r"/api/v1/[a-z/{}-]+", value))
        ):
            clean[key] = value
        elif key == "outcome" and value in {
            "success",
            "failure",
            "rejected",
            "abandoned",
            "quarantined",
        }:
            clean[key] = value
        elif key == "solver.status" and value in {
            "OPTIMAL",
            "FEASIBLE",
            "TIME_LIMIT_WITH_FEASIBLE",
            "NO_FEASIBLE_PLAN",
            "INFEASIBLE",
            "ERROR",
            "UNKNOWN",
            "TIME_LIMIT_NO_FEASIBLE",
        }:
            clean[key] = value
    return clean


def annotate(**values):
    clean = safe_attributes(values)
    active = _operation_attributes.get()
    if active is not None:
        active.update(clean)
    trace.get_current_span().set_attributes(clean)


class Telemetry:
    def __init__(self, settings, service_name, *, span_exporter=None, metric_reader=None):
        resource = Resource(
            attributes={
                "service.name": service_name,
                "service.version": "0.1.0",
                "deployment.environment.name": settings.environment,
            }
        )
        self.service_name = service_name
        self.traces = TracerProvider(resource=resource, shutdown_on_exit=False)
        readers = [metric_reader] if metric_reader else []
        endpoint = settings.otel_endpoint
        if endpoint:
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

            # An explicit base URL is required. SDK signal-specific environment
            # variables cannot silently opt tests/default runtimes into export.
            span_exporter = span_exporter or OTLPSpanExporter(
                endpoint=endpoint.rstrip("/") + "/v1/traces",
                timeout=3,
                headers={},
                meter_provider=NoOpMeterProvider(),
            )
            if not metric_reader:
                readers.append(
                    PeriodicExportingMetricReader(
                        OTLPMetricExporter(
                            endpoint=endpoint.rstrip("/") + "/v1/metrics",
                            timeout=3,
                            headers={},
                            meter_provider=NoOpMeterProvider(),
                        ),
                        export_interval_millis=30_000,
                        export_timeout_millis=5_000,
                    )
                )
        if span_exporter:
            self.traces.add_span_processor(BatchSpanProcessor(span_exporter))
        self.metrics = MeterProvider(
            resource=resource, metric_readers=readers, shutdown_on_exit=False
        )
        self.tracer = self.traces.get_tracer("cargopulse.runtime", "1.0.0")
        meter = self.metrics.get_meter("cargopulse.runtime", "1.0.0")
        self.operations = meter.create_counter("cargopulse.operations", unit="{operation}")
        self.failures = meter.create_counter("cargopulse.failures", unit="{failure}")
        self.duration = meter.create_histogram("cargopulse.operation.duration", unit="s")
        self.http_duration = meter.create_histogram("http.server.request.duration", unit="s")
        self.queue_depth = meter.create_gauge("cargopulse.queue.jobs", unit="{job}")
        self.queue_age = meter.create_gauge("cargopulse.queue.oldest_age", unit="s")
        self.queue_wait = meter.create_histogram("cargopulse.queue.wait", unit="s")
        self.readiness = meter.create_gauge("cargopulse.readiness", unit="1")

    @contextmanager
    def operation(self, name, *, context=None, kind=SpanKind.INTERNAL, attributes=None):
        if name not in OPERATIONS:
            raise ValueError("Unknown telemetry operation")
        started = time.monotonic()
        operation_attributes = safe_attributes(attributes or {})
        token = _operation_attributes.set(operation_attributes)
        with self.tracer.start_as_current_span(
            name,
            context=context,
            kind=kind,
            attributes=operation_attributes,
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            failed = False
            try:
                yield span
            except BaseException:
                failed = True
                span.set_status(Status(StatusCode.ERROR))
                # Never record exception messages/stack locals: they can contain
                # request bodies, database parameters, tokens or cargo fields.
                raise
            finally:
                elapsed = time.monotonic() - started
                attrs = operation_attributes
                _operation_attributes.reset(token)
                code = attrs.get("http.response.status_code", 200)
                failed = failed or code >= 500 or attrs.get("outcome") in {"failure", "quarantined"}
                if failed:
                    span.set_status(Status(StatusCode.ERROR))
                labels = {"operation": name, "outcome": "failure" if failed else "success"}
                self.operations.add(1, labels)
                self.duration.record(elapsed, labels)
                if failed:
                    self.failures.add(1, {"operation": name})
                if name == "http.request":
                    self.http_duration.record(
                        elapsed,
                        {
                            key: attrs[key]
                            for key in (
                                "http.route",
                                "http.request.method",
                                "http.response.status_code",
                            )
                            if key in attrs
                        },
                    )
                ctx = span.get_span_context()
                logger.info(
                    json.dumps(
                        {
                            "event": "operation",
                            "service": self.service_name,
                            **labels,
                            "elapsed_ms": round(elapsed * 1000, 3),
                            "trace_id": f"{ctx.trace_id:032x}",
                            "span_id": f"{ctx.span_id:016x}",
                            **safe_attributes(attrs),
                        },
                        sort_keys=True,
                    )
                )

    def flush(self):
        self.traces.force_flush(timeout_millis=5_000)
        self.metrics.force_flush(timeout_millis=5_000)

    def shutdown(self):
        self.traces.shutdown()
        self.metrics.shutdown(timeout_millis=5_000)


def observed(name):
    """Instrument domain commands through their session's owned runtime."""

    def decorate(fn):
        @wraps(fn)
        def wrapped(db, *args, **kwargs):
            telemetry = db.info.get("telemetry")
            if telemetry is None:
                return fn(db, *args, **kwargs)
            with telemetry.operation(name):
                return fn(db, *args, **kwargs)

        return wrapped

    return decorate


def configure_logging():
    """One JSON-only handler for runtime events; no unbounded application extras."""
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)
    logger.propagate = False
