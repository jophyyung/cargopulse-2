"""Controlled CSV ambiguity, resource and privacy regressions through the API."""

import csv
import io
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from cargopulse_api.controlled_csv import SpreadsheetCSVWriter
from cargopulse_api.db import development_policy
from cargopulse_api.tables import AuditRow, IdempotencyRow, ImportBatch, SnapshotRow
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy import select

from packages.domain_fixtures.generator import make_snapshot

from .conftest import login, post


@pytest.fixture
def csv_payload(client):
    login(client, "steward")
    snapshot = make_snapshot(3).model_dump(mode="json")
    snapshot["policy"] = development_policy().model_dump(mode="json")
    units = snapshot.pop("cargo_units")
    rows = [
        {
            key: json.dumps(value) if isinstance(value, (dict, list, bool)) else value
            for key, value in unit.items()
        }
        for unit in units
    ]
    return snapshot, list(rows[0]), [[row[field] for field in rows[0]] for row in rows]


def csv_bytes(fields, rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(fields)
    writer.writerows(rows)
    return output.getvalue().encode()


def upload(client, metadata, raw, key=None):
    return client.post(
        "/api/v1/imports/upload-csv",
        files={"file": ("cargo.csv", raw, "text/csv")},
        data={"metadata": metadata if isinstance(metadata, str) else json.dumps(metadata)},
        headers={"Idempotency-Key": key or str(uuid4())},
    )


def assert_rejected_without_import(client, response):
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "INVALID_CSV"
    with client.app.state.factory() as db:
        assert db.scalar(select(ImportBatch)) is None
        assert db.scalar(select(SnapshotRow)) is None
        assert db.scalar(select(IdempotencyRow)) is None
        denial = db.scalar(select(AuditRow).where(AuditRow.outcome == "DENIED"))
        assert denial is not None and denial.details == "INVALID_CSV"
    assert not any(
        path.is_file() for path in Path(client.app.state.settings.object_root).rglob("*")
    )


@pytest.mark.parametrize("field", ["id", "actual_mass_kg", "security"])
def test_duplicate_columns_cannot_silently_replace_a_value(client, csv_payload, field):
    metadata, fields, rows = csv_payload
    # A differing first value must not disappear when the repeated header is read.
    fields = [field, *fields]
    rows = [["UNTRUSTED_FIRST_VALUE", *row] for row in rows]
    assert_rejected_without_import(client, upload(client, metadata, csv_bytes(fields, rows)))


@pytest.mark.parametrize("extra", ["", "unexpected_column", " id", "ID"])
def test_empty_or_unknown_columns_cannot_be_ignored(client, csv_payload, extra):
    metadata, fields, rows = csv_payload
    assert_rejected_without_import(
        client, upload(client, metadata, csv_bytes([*fields, extra], [row + [""] for row in rows]))
    )


@pytest.mark.parametrize("control", ["\t", "\r", "\n", "\x00", "\x0b", "\x0c", "\x1f", "\x7f"])
def test_control_characters_are_rejected_before_numeric_coercion(client, csv_payload, control):
    metadata, fields, rows = csv_payload
    index = fields.index("actual_mass_kg")
    rows[0][index] = control + rows[0][index]
    result = upload(client, metadata, csv_bytes(fields, rows))
    assert_rejected_without_import(client, result)
    assert "control character" in result.json()["detail"]


@pytest.mark.parametrize("control", ["\t", "\r", "\n", "\x00", "\x7f"])
def test_json_escapes_cannot_bypass_csv_control_checks(client, csv_payload, control):
    metadata, fields, rows = csv_payload
    index = fields.index("pieces")
    pieces = json.loads(rows[0][index])
    pieces[0]["mass_kg"] = control + pieces[0]["mass_kg"]
    rows[0][index] = json.dumps(pieces)
    result = upload(client, metadata, csv_bytes(fields, rows))
    assert_rejected_without_import(client, result)
    assert "control character" in result.json()["detail"]


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "＝", "＋", "－", "＠"])
def test_formula_prefixes_are_rejected_with_leading_whitespace(client, csv_payload, prefix):
    metadata, fields, rows = csv_payload
    rows[0][fields.index("id")] = "  " + prefix + "FORMULA_CANARY"
    result = upload(client, metadata, csv_bytes(fields, rows))
    assert_rejected_without_import(client, result)
    assert "unsafe formula" in result.json()["detail"]
    assert "FORMULA_CANARY" not in result.text


@pytest.mark.parametrize("field", ["actual_mass_kg", "service_class", "title"])
def test_schema_errors_do_not_echo_private_values(client, csv_payload, caplog, field):
    metadata, fields, rows = csv_payload
    canary = "PRIVATE_CARGO_VALUE_" + uuid4().hex
    if field == "title":
        metadata["title"] = {"private": canary}
    else:
        rows[0][fields.index(field)] = canary
    result = upload(client, metadata, csv_bytes(fields, rows))
    assert_rejected_without_import(client, result)
    assert canary not in result.text
    assert canary not in caplog.text


@pytest.mark.parametrize("location", ["metadata", "nested_cell"])
def test_duplicate_json_keys_cannot_hide_conflicting_source_values(client, csv_payload, location):
    metadata, fields, rows = csv_payload
    if location == "metadata":
        metadata = '{"source_version":999,' + json.dumps(metadata)[1:]
    else:
        index = fields.index("security")
        rows[0][index] = '{"state":"FAIL",' + rows[0][index][1:]
    assert_rejected_without_import(client, upload(client, metadata, csv_bytes(fields, rows)))


def test_metadata_cannot_silently_replace_an_embedded_manifest(client, csv_payload):
    metadata, fields, rows = csv_payload
    metadata["cargo_units"] = [{"id": "CONFLICTING_MANIFEST"}]
    assert_rejected_without_import(client, upload(client, metadata, csv_bytes(fields, rows)))


@pytest.mark.parametrize("location", ["metadata", "nested_cell"])
def test_excessively_nested_json_returns_a_validation_problem(client, csv_payload, location):
    metadata, fields, rows = csv_payload
    nested = "[" * 1500 + "0" + "]" * 1500
    if location == "metadata":
        metadata = nested
    else:
        rows[0][fields.index("pieces")] = nested
    assert_rejected_without_import(client, upload(client, metadata, csv_bytes(fields, rows)))


@pytest.mark.parametrize("change", ["missing", "extra", "unclosed_quote", "invalid_utf8"])
def test_malformed_rows_are_rejected_without_writes(client, csv_payload, change):
    metadata, fields, rows = csv_payload
    if change == "missing":
        rows[0].pop()
    elif change == "extra":
        rows[0].append("EXTRA")
    raw = csv_bytes(fields, rows)
    if change == "unclosed_quote":
        raw += b'"unterminated'
    elif change == "invalid_utf8":
        raw += b"\xff"
    assert_rejected_without_import(client, upload(client, metadata, raw))


def test_csv_row_budget_is_enforced_without_storing_an_artifact(client, csv_payload):
    metadata, fields, rows = csv_payload
    assert_rejected_without_import(
        client, upload(client, metadata, csv_bytes(fields, [rows[0]] * 1201))
    )


def test_bom_reordered_columns_optional_blanks_and_raw_evidence_roundtrip(client, csv_payload):
    metadata, fields, rows = csv_payload
    expected = make_snapshot(3, as_of=datetime.fromisoformat(metadata["as_of"])).model_dump(
        mode="json"
    )
    expected.update(metadata)
    fields = fields[::-1]
    rows = [row[::-1] for row in rows]
    raw = b"\xef\xbb\xbf" + csv_bytes(fields, rows)
    result = upload(client, metadata, raw, "valid-controlled-csv")
    assert result.status_code == 202, result.text
    assert result.json()["status"] == "READY"
    retry = upload(client, metadata, raw, "valid-controlled-csv")
    assert retry.json() == result.json()
    with client.app.state.factory() as db:
        batches = list(db.scalars(select(ImportBatch)))
        assert len(batches) == 1
        assert batches[0].payload == expected
        assert (
            Path(client.app.state.settings.object_root) / batches[0].object_key
        ).read_bytes() == raw
    receipt = post(client, f"/imports/{result.json()['id']}/commit", key="csv-commit")
    assert receipt.status_code == 201, receipt.text


def test_raw_evidence_change_conflicts_even_when_only_bom_changes(client, csv_payload):
    metadata, fields, rows = csv_payload
    raw = csv_bytes(fields, rows)
    result = upload(client, metadata, raw, "raw-evidence-key")
    assert result.status_code == 202, result.text
    changed = upload(client, metadata, b"\xef\xbb\xbf" + raw, "raw-evidence-key")
    assert changed.status_code == 409, changed.text
    assert changed.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_report_csv_preserves_cells_and_escapes_formulas_and_controls():
    values = [
        '=HYPERLINK("https://invalid.example", "cargo")',
        "  +1",
        "-ULD-1",
        "@SUM(1)",
        "＝1",
        "＋1",
        "－1",
        "＠SUM(1)",
        "\t=1",
        "\r=1",
        "\n=1",
        "A\x00B",
        '香港, "cargo"; data',
        "normal",
        "",
        None,
        Decimal("12.500000"),
    ]
    output = io.StringIO(newline="")
    SpreadsheetCSVWriter(output).writerow(values)
    rows = list(csv.reader(io.StringIO(output.getvalue(), newline="")))
    assert len(rows) == 1 and len(rows[0]) == len(values)
    assert rows[0][:8] == ["'" + value for value in values[:8]]
    assert rows[0][8:12] == ["\\x09=1", "\\x0d=1", "\\x0a=1", "A\\x00B"]
    assert rows[0][12:] == ['香港, "cargo"; data', "normal", "", "", "12.500000"]


@given(st.lists(st.text(max_size=200), max_size=20))
def test_report_csv_roundtrip_cannot_introduce_extra_rows_columns_or_control_prefixes(values):
    output = io.StringIO(newline="")
    SpreadsheetCSVWriter(output).writerow(values)
    rows = list(csv.reader(io.StringIO(output.getvalue(), newline="")))
    assert len(rows) == 1 and len(rows[0]) == len(values)
    for cell in rows[0]:
        assert not cell.lstrip().startswith(("=", "+", "-", "@", "＝", "＋", "－", "＠"))
        assert all(ord(character) >= 32 and ord(character) != 127 for character in cell)


def test_csv_import_worker_and_exports_preserve_lineage_with_safe_spreadsheet_cells(
    client, csv_payload
):
    from cargopulse_api.worker import process_one

    metadata, fields, rows = csv_payload
    metadata["event_id"] = "-RECOVERY-EXPORT"
    batch = upload(client, metadata, csv_bytes(fields, rows))
    assert batch.status_code == 202, batch.text
    receipt = post(client, f"/imports/{batch.json()['id']}/commit", key="commit-csv")
    assert receipt.status_code == 201, receipt.text
    login(client)
    scenario = post(
        client, "/scenarios", {"source_snapshot_id": receipt.json()["snapshot_id"]}, "scenario-csv"
    )
    assert scenario.status_code == 201, scenario.text
    record = scenario.json()
    job = post(
        client,
        f"/scenarios/{record['id']}/solve",
        {"max_wall_seconds": 10, "compare_baselines": False},
        "solve-csv",
        record["etag"],
    )
    assert job.status_code == 202, job.text
    assert process_one(client.app.state.factory, "csv-security-worker")
    solved = client.get(f"/api/v1/jobs/{job.json()['id']}").json()
    assert solved["status"] == "COMPLETED", solved
    report = f"/api/v1/reports/{solved['plan_id']}/export"
    exact = client.get(report + "?format=json")
    assert exact.status_code == 200, exact.text
    assert exact.json()["plan"]["snapshot_hash"] == record["snapshot_hash"]
    assert exact.json()["plan"]["independent_validation"]["status"] == "PASS"
    assert all(
        metric["cohort_id"] == "-RECOVERY-EXPORT" for metric in exact.json()["plan"]["metrics"]
    )
    exported = client.get(report + "?format=csv")
    assert exported.status_code == 200, exported.text
    cells = list(csv.reader(io.StringIO(exported.text, newline="")))
    assert ["plan_hash", exact.json()["plan_hash"], "plan_state", exact.json()["state"]] in cells
    metric_start = next(index for index, row in enumerate(cells) if "cohort_id" in row)
    cohort_column = cells[metric_start].index("cohort_id")
    assert cells[metric_start + 1 :]
    assert all(row[cohort_column] == "'-RECOVERY-EXPORT" for row in cells[metric_start + 1 :])
