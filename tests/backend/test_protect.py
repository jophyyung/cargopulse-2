"""Protect synthetic sandbox: deterministic generator, two-stage MILP, reference rule, API."""

import pytest
from cargopulse_protect import make_flight, plan_priority_fill, plan_with_optimizer
from cargopulse_validation.protect import check_protect_load

from tests.backend.conftest import login


def rows(flight):
    return [
        {"id": s.id, "weight_kg": s.weight_kg, "volume_m3": s.volume_m3, "guaranteed": s.guaranteed}
        for s in flight.shipments
    ]


def score(flight, loaded):
    on = [s for s in flight.shipments if s.id in loaded]
    return sum(s.priority_weight for s in on), sum(s.chargeable_kg for s in on)


def test_generator_is_deterministic_and_bounded():
    a, b = make_flight(109), make_flight(109)
    assert a == b
    assert len(a.shipments) == 45
    assert make_flight(110) != a
    booked = sum(s.volume_m3 for s in a.shipments)
    assert 1.4 * a.volume_m3 < booked < 1.6 * a.volume_m3


@pytest.mark.parametrize("seed", [1, 7, 42, 109, 1234, 99991])
def test_optimizer_is_feasible_and_never_worse_than_priority_fill(seed):
    flight = make_flight(seed, shipments=60, demand=1.8)
    optimized, info = plan_with_optimizer(flight)
    filled, _ = plan_priority_fill(flight)
    assert info["status"] == "OPTIMAL"
    for loaded in (optimized, filled):
        assert check_protect_load(rows(flight), loaded, flight.payload_kg, flight.volume_m3) == []
    # Lexicographic objective: priority-weighted count first, then chargeable weight.
    assert score(flight, optimized) >= score(flight, filled)


def test_guaranteed_shipments_are_always_loaded():
    for seed in range(1, 30):
        flight = make_flight(seed)
        optimized, _ = plan_with_optimizer(flight)
        assert {s.id for s in flight.shipments if s.guaranteed} <= optimized


def test_independent_check_rejects_unsafe_plans():
    flight = make_flight(109)
    everything = {s.id for s in flight.shipments}
    findings = check_protect_load(rows(flight), everything, flight.payload_kg, flight.volume_m3)
    assert "PAYLOAD_MASS_EXCEEDED" in findings or "HOLD_VOLUME_EXCEEDED" in findings
    data = rows(flight)
    data[0]["guaranteed"] = True
    assert "GUARANTEED_SHIPMENT_OFFLOADED" in check_protect_load(
        data, set(), flight.payload_kg, flight.volume_m3
    )
    assert "UNKNOWN_SHIPMENT_LOADED" in check_protect_load(
        data, {"AWB-FORGED"}, flight.payload_kg, flight.volume_m3
    )


def test_sandbox_api_returns_checked_stateless_plan(client):
    login(client, "controller")
    response = client.get("/api/v1/protect/sandbox?seed=109&shipments=45&demand=1.5")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["synthetic"] is True
    assert body["has_external_write_permission"] is False
    assert len(body["shipments"]) == 45
    results = {r["policy"]: r for r in body["results"]}
    assert set(results) == {"CARGOPULSE_LOAD_OPTIMIZER", "PRIORITY_FILL"}
    assert all(r["independent_check"] == "PASS" for r in results.values())
    opt = results["CARGOPULSE_LOAD_OPTIMIZER"]
    assert opt["loaded_count"] + opt["offloaded_count"] == 45
    assert opt["weight_used_kg"] <= body["payload_kg"]
    # Same inputs give the same plan (no hidden state or randomness).
    again = client.get("/api/v1/protect/sandbox?seed=109&shipments=45&demand=1.5").json()
    assert again["shipments"] == body["shipments"]


@pytest.mark.parametrize("identity", ["steward", "auditor"])
def test_sandbox_requires_planning_role(client, identity):
    login(client, identity)
    assert client.get("/api/v1/protect/sandbox").status_code == 403


@pytest.mark.parametrize("query", ["seed=0", "shipments=5", "shipments=500", "demand=9"])
def test_sandbox_rejects_out_of_range_inputs(client, query):
    login(client, "manager")
    assert client.get(f"/api/v1/protect/sandbox?{query}").status_code == 422


def test_sandbox_requires_session(client):
    assert client.get("/api/v1/protect/sandbox").status_code == 401
