"""Actual SDK spans, privacy boundaries, isolated providers and OTLP transport."""

import json
import logging
from types import SimpleNamespace

import pytest
from cargopulse_api import observability
from cargopulse_api.config import Settings
from cargopulse_api.main import create_app
from cargopulse_api.observability import (
    Telemetry,
    annotate,
    capture_trace_context,
    extract_trace_context,
)
from fastapi.testclient import TestClient
from opentelemetry import baggage, context, trace
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from .conftest import attributes, metrics, spans


@pytest.mark.parametrize(
    "endpoint,environment,valid",
    [
        ("http://127.0.0.1:4318", "development", True),
        ("http://localhost:4318", "development", True),
        ("https://collector.example", "development", True),
        ("http://collector.example:4318", "development", False),
        ("http://127.0.0.1:4318", "production", False),
        ("https://user:secret@collector.example", "development", False),
        ("https://collector.example?token=secret", "development", False),
        ("https://collector.example#secret", "development", False),
    ],
)
def test_endpoint_validation(endpoint, environment, valid):
    settings = Settings(environment=environment, otel_endpoint=endpoint)
    if valid:
        settings.validate()
    else:
        with pytest.raises(RuntimeError, match="OTLP"):
            settings.validate()


def test_real_spans_redact_errors_attributes_and_baggage(caplog, monkeypatch):
    # Python 3.12's Windows monotonic clock can tick only every 15.625 ms.
    # Verify duration accounting without requiring this fast block to span a tick.
    clock = iter([100.0, 100.25])
    monkeypatch.setattr(observability, "time", SimpleNamespace(monotonic=clock.__next__))
    exporter, reader = InMemorySpanExporter(), InMemoryMetricReader()
    runtime = Telemetry(
        Settings(environment="development"),
        "cargopulse-worker",
        span_exporter=exporter,
        metric_reader=reader,
    )
    caplog.set_level(logging.INFO, logger="cargopulse.telemetry")
    telemetry_logger = logging.getLogger("cargopulse.telemetry")
    telemetry_logger.addHandler(caplog.handler)
    token = context.attach(baggage.set_baggage("subject", "secret-person@example.com"))
    try:
        with pytest.raises(ValueError):
            with runtime.operation("solve"):
                annotate(
                    **{
                        "cargo.awb": "123-SECRET",
                        "subject": "secret-person@example.com",
                        "token": "TOKEN_SECRET",
                        "payload": "PAYLOAD_SECRET",
                        "comment": "COMMENT_SECRET",
                        "cargo.count": 8,
                        "scenario.id": "malicious-person@example.com",
                    }
                )
                carrier = capture_trace_context()
                assert set(carrier) == {"traceparent"}
                raise ValueError("TOKEN_SECRET 123-SECRET PAYLOAD_SECRET")
    finally:
        context.detach(token)
    runtime.flush()
    telemetry_logger.removeHandler(caplog.handler)
    logs = [json.loads(r.message) for r in caplog.records if r.name == "cargopulse.telemetry"]
    assert any(r["operation"] == "solve" and r["outcome"] == "failure" for r in logs)
    emitted = exporter.get_finished_spans()
    assert len(emitted) == 1 and emitted[0].attributes == {"cargo.count": 8}
    assert emitted[0].status.status_code == StatusCode.ERROR
    assert not emitted[0].events and not emitted[0].status.description
    serialized = json.dumps([dict(s.attributes) for s in emitted]) + caplog.text
    assert all(
        secret not in serialized
        for secret in (
            "secret-person",
            "TOKEN_SECRET",
            "123-SECRET",
            "PAYLOAD_SECRET",
            "COMMENT_SECRET",
        )
    )
    data = reader.get_metrics_data()
    metric = {
        m.name: m for rm in data.resource_metrics for sm in rm.scope_metrics for m in sm.metrics
    }
    assert metric["cargopulse.failures"].data.data_points[0].value == 1
    histogram = metric["cargopulse.operation.duration"].data.data_points[0]
    assert histogram.count == 1 and histogram.sum == 0.25
    runtime.shutdown()


def test_invalid_or_legacy_context_starts_clean_root():
    assert not trace.get_current_span(extract_trace_context(None)).get_span_context().is_valid
    assert (
        not trace.get_current_span(extract_trace_context({"traceparent": "token-secret"}))
        .get_span_context()
        .is_valid
    )
    assert not baggage.get_all(extract_trace_context({"baggage": "subject=secret"}))


def test_http_templates_status_and_repeated_lifespans(tmp_path, caplog, monkeypatch):
    # A signal-specific environment value alone must never enable exports.
    monkeypatch.setenv(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "https://must-not-contact.invalid/v1/traces"
    )
    settings = Settings(
        environment="development",
        auto_create=True,
        database_url="sqlite:///:memory:",
        object_root=str(tmp_path),
    )
    app = create_app(settings)
    providers = []
    for _ in range(2):
        exporter = InMemorySpanExporter()
        with TestClient(app) as client:
            providers.append(app.state.telemetry.traces)
            app.state.telemetry.traces.add_span_processor(SimpleSpanProcessor(exporter))
            result = client.get(
                "/api/v1/jobs/SECRET-PERSON?token=TOKEN_SECRET",
                headers={"Authorization": "Bearer SECRET_AUTH"},
            )
            assert result.status_code in (401, 422)
            assert (
                client.get("/api/v1/secret-person@example.com?code=SECRET_CODE").status_code == 404
            )
            assert client.get("/api/v1/health/live").status_code == 200
        emitted = exporter.get_finished_spans()
        assert {s.attributes.get("http.route") for s in emitted} == {
            "/api/v1/jobs/{id}",
            "unmatched",
            "/api/v1/health/live",
        }
        assert all(s.attributes.get("http.response.status_code") for s in emitted)
        serialized = " ".join(s.to_json() for s in emitted)
        assert all(secret not in serialized for secret in ("SECRET", "secret-person", "Bearer"))
    assert providers[0] is not providers[1]
    assert "Overriding of current" not in caplog.text


def test_real_otlp_http_protobuf_spans_and_metrics(collector):
    endpoint, received = collector
    settings = Settings(environment="development", otel_endpoint=endpoint)
    settings.validate()
    runtime = Telemetry(settings, "cargopulse-worker")
    with runtime.operation("solve"):
        annotate(**{"cargo.count": 8, "engine.version": "1.15.1", "token": "SECRET"})
    runtime.queue_depth.set(3, {"status": "QUEUED"})
    runtime.queue_age.set(12.5)
    runtime.readiness.set(1)
    runtime.flush()
    runtime.shutdown()
    emitted = spans(received)
    assert len(emitted) == 1
    resource, span = emitted[0]
    assert attributes(resource.attributes)["service.name"] == "cargopulse-worker"
    assert span.name == "solve" and attributes(span.attributes)["cargo.count"] == 8
    assert "SECRET" not in str(received)
    assert {content_type for _, content_type, _ in received} == {"application/x-protobuf"}
    observed = {m.name: m for m in metrics(received)}
    assert observed["cargopulse.operations"].sum.data_points[0].as_int == 1
    assert observed["cargopulse.queue.jobs"].gauge.data_points[0].as_int == 3
    assert observed["cargopulse.queue.oldest_age"].gauge.data_points[0].as_double == 12.5
    assert observed["cargopulse.operation.duration"].histogram.data_points[0].count == 1


def test_unsampled_request_keeps_http_metrics_and_success(tmp_path, monkeypatch):
    import cargopulse_api.main as main

    reader = InMemoryMetricReader()
    original = main.Telemetry
    monkeypatch.setattr(
        main, "Telemetry", lambda settings, name: original(settings, name, metric_reader=reader)
    )
    settings = Settings(
        environment="development",
        auto_create=True,
        database_url="sqlite:///:memory:",
        object_root=str(tmp_path),
    )
    with TestClient(main.create_app(settings)) as client:
        response = client.get(
            "/api/v1/health/live",
            headers={"traceparent": "00-1234567890abcdef1234567890abcdef-1234567890abcdef-00"},
        )
        assert response.status_code == 200
        observed = reader.get_metrics_data()
        measured = {
            m.name: m
            for rm in observed.resource_metrics
            for sm in rm.scope_metrics
            for m in sm.metrics
        }
        point = measured["http.server.request.duration"].data.data_points[0]
        assert point.count == 1 and point.attributes["http.route"] == "/api/v1/health/live"
        assert point.attributes["http.response.status_code"] == 200
        assert "cargopulse.failures" not in measured
