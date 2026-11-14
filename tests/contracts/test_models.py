import json
from datetime import datetime, timezone

import pytest
from cargopulse_contracts import ScenarioSnapshot, canonical_hash
from pydantic import ValidationError

from packages.contracts.routes import contract_app
from packages.domain_fixtures.generator import make_snapshot

NOW = datetime(2026, 11, 10, 0, 0, tzinfo=timezone.utc)


def test_seeded_snapshot_roundtrip_and_hash():
    a = make_snapshot(as_of=NOW)
    b = make_snapshot(as_of=NOW)
    assert len(a.cargo_units) == 140
    assert canonical_hash(a) == canonical_hash(b)
    assert ScenarioSnapshot.model_validate_json(a.model_dump_json()) == a
    assert isinstance(json.loads(a.model_dump_json())["cargo_units"][0]["actual_mass_kg"], str)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(synthetic=False),
        lambda d: d.update(allow_external_write=True),
        lambda d: d.update(as_of="2026-11-10T00:00:00"),
        lambda d: d["cargo_units"][0].update(actual_mass_kg=1000.01),
        lambda d: d["cargo_units"][0].pop("security"),
        lambda d: d["cargo_units"][1]["pieces"][0].update(piece_id="P-0001"),
        lambda d: d["policy"].update(approved_by="synthetic-policy-author"),
        lambda d: d["flights"][0].update(origin_timezone="Mars/City"),
        lambda d: d["flights"][0].update(arrival_at=d["as_of"]),
    ],
)
def test_fail_closed_contract(mutate):
    d = make_snapshot(size=4, as_of=NOW).model_dump(mode="json")
    mutate(d)
    with pytest.raises(ValidationError):
        ScenarioSnapshot.model_validate(d)


def test_openapi_has_real_unit_and_status_contracts():
    api = contract_app().openapi()
    assert api["openapi"].startswith("3.1.")
    assert "/api/v1/scenarios/{id}/solve" in api["paths"]
    assert "202" in api["paths"]["/api/v1/scenarios/{id}/solve"]["post"]["responses"]
    assert (
        api["components"]["schemas"]["SolutionPlan"]["properties"]["has_external_write_permission"][
            "const"
        ]
        is False
    )
    assert "TIME_LIMIT_WITH_FEASIBLE" in api["components"]["schemas"]["SolverStatus"]["enum"]
