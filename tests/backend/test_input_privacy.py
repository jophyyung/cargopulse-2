"""Actual upload-name enforcement and callback response/telemetry privacy."""

import csv
import io
import logging
from uuid import uuid4

import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from .conftest import login


def upload(client, filename):
    login(client)
    snapshot = client.get("/api/v1/fixtures/recover").json()
    units = snapshot.pop("cargo_units")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=units[0])
    writer.writeheader()
    import json

    for unit in units:
        writer.writerow({k: json.dumps(v) if isinstance(v, (dict, list, bool)) else v for k, v in unit.items()})
    return client.post(
        "/api/v1/imports/upload-csv",
        files={"file": (filename, output.getvalue(), "text/csv")},
        data={"metadata": json.dumps(snapshot)},
        headers={"Idempotency-Key": str(uuid4())},
    )


@pytest.mark.parametrize("filename", [
    "cargo.exe", "cargo", "cargo.csv.txt", "../cargo.csv", r"..\cargo.csv",
    "cargo.csv ", ".csv", "a" * 256 + ".csv",
])
def test_csv_rejects_unsupported_or_ambiguous_filenames(client, filename):
    assert upload(client, filename).status_code == 422


@pytest.mark.parametrize("filename", ["cargo.csv", "cargo.CSV", "flight.units.CsV", "香港.csv"])
def test_csv_accepts_valid_basename_and_case_insensitive_extension(client, filename):
    response = upload(client, filename)
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "READY"


def test_callback_query_canaries_do_not_reach_application_logs_or_spans(client):
    code, state = "CODE_CANARY_" + uuid4().hex, "STATE_CANARY_" + uuid4().hex
    exporter = InMemorySpanExporter()
    client.app.state.telemetry.traces.add_span_processor(SimpleSpanProcessor(exporter))
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    logger = logging.getLogger("cargopulse.telemetry")
    handler = Capture()
    logger.addHandler(handler)
    try:
        result = client.get("/api/v1/auth/callback", params={"code": code, "state": state})
    finally:
        logger.removeHandler(handler)
    assert result.status_code == 401
    assert result.headers.get("Referrer-Policy") == "no-referrer"
    spans = exporter.get_finished_spans()
    assert spans and records
    assert any(s.attributes.get("http.route") == "/api/v1/auth/callback" for s in spans)
    emitted = " ".join(records) + " ".join(s.to_json() for s in spans)
    assert code not in emitted and state not in emitted
    assert code not in result.text and state not in result.text


def test_early_boundary_errors_also_prevent_referrer_forwarding(client):
    result = client.get("/api/v1/health/live", headers={"Content-Length": "9000000"})
    assert result.status_code == 413
    assert result.headers.get("Referrer-Policy") == "no-referrer"
