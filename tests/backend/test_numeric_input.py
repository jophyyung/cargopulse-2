"""Malformed decimal strings must stay inside the normal validation boundary."""

from pathlib import Path
from uuid import uuid4

import pytest
from cargopulse_api.db import development_policy
from cargopulse_api.tables import IdempotencyRow, ImportBatch, SnapshotRow
from cargopulse_contracts import ScenarioSnapshot
from pydantic import ValidationError
from sqlalchemy import select

from packages.domain_fixtures.generator import make_snapshot

from .conftest import login, post


@pytest.mark.parametrize("value", ["not-a-number", "", "1.2.3", "1e", "1\x00"])
def test_malformed_decimal_is_a_contract_validation_error(value):
    snapshot = make_snapshot(1).model_dump(mode="json")
    snapshot["cargo_units"][0]["actual_mass_kg"] = value
    with pytest.raises(ValidationError):
        ScenarioSnapshot.model_validate(snapshot)


@pytest.mark.parametrize(
    "path",
    [
        ("cargo_units", 0, "actual_mass_kg"),
        ("cargo_units", 0, "pieces", 0, "volume_m3"),
        ("flights", 0, "free_mass_kg"),
        ("policy", "handling_penalty_weighted_hours"),
    ],
)
def test_json_import_invalid_decimal_is_private_validation_problem(client, caplog, path):
    login(client, "steward")
    snapshot = make_snapshot(3).model_dump(mode="json")
    snapshot["policy"] = development_policy().model_dump(mode="json")
    canary = "PRIVATE_INVALID_NUMBER_" + uuid4().hex
    target = snapshot
    for field in path[:-1]:
        target = target[field]
    target[path[-1]] = canary
    response = post(client, "/imports/validate", {"snapshot": snapshot}, "invalid-number")
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "INVALID_REQUEST"
    assert canary not in response.text and canary not in caplog.text
    with client.app.state.factory() as db:
        assert db.scalar(select(ImportBatch)) is None
        assert db.scalar(select(SnapshotRow)) is None
        assert db.scalar(select(IdempotencyRow)) is None
    assert not any(
        path.is_file() for path in Path(client.app.state.settings.object_root).rglob("*")
    )
