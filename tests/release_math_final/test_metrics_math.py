"""Small deterministic challenges for the independent metrics verifier."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from cargopulse_contracts import ScenarioSnapshot
from cargopulse_optimizer import build_feasible_paths, run_solver
from cargopulse_validation import validate_solution_independently
from cargopulse_validation.metrics import eligible_units

from packages.domain_fixtures.generator import make_snapshot

NOW = datetime(2026, 11, 10, tzinfo=timezone.utc)


def iso(hours: float) -> str:
    return (NOW + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


def with_change(snapshot: ScenarioSnapshot, mutate) -> ScenarioSnapshot:
    raw = snapshot.model_dump(mode="json")
    mutate(raw)
    return ScenarioSnapshot.model_validate(raw)


def one_route_snapshot() -> ScenarioSnapshot:
    raw = make_snapshot(size=1, seed=101, as_of=NOW).model_dump(mode="json")
    unit = raw["cargo_units"][0]
    flight = deepcopy(next(f for f in raw["flights"] if f["id"] == "F-FRA-1"))
    window = deepcopy(next(w for w in raw["handling_windows"] if w["id"] == "H-F-FRA-1"))
    permission = deepcopy(
        next(
            p
            for p in raw["route_permissions"]
            if p["cargo_unit_id"] == unit["id"] and p["flight_id"] == "F-FRA-1"
        )
    )
    unit.update(
        commitment_at=iso(5),
        service_weight="2",
        previous_path_id="P-prior-path",
        contractual_latest_arrival=None,
        frozen_path_id=None,
    )
    flight["free_mass_kg"] = "5000"
    flight["free_volume_m3"] = "100"
    flight["positions"][0].update(free_mass_kg="5000", free_volume_m3="100", slot_count=4)
    window["capacity_units"] = 4
    raw["flights"] = [flight]
    raw["handling_windows"] = [window]
    raw["route_permissions"] = [permission]
    raw["connections"] = []
    raw["policy"].update(
        handling_penalty_weighted_hours="2",
        stability_penalty_weighted_hours="3",
        unassigned_penalty_weighted_hours="100",
        source_max_age_seconds=604800,
    )
    return ScenarioSnapshot.model_validate(raw)


def multileg_snapshot() -> ScenarioSnapshot:
    raw = make_snapshot(size=1, seed=101, as_of=NOW).model_dump(mode="json")
    unit = raw["cargo_units"][0]
    unit.update(commitment_at=iso(10), service_weight="2")
    base = next(f for f in raw["flights"] if f["id"] == "F-FRA-1")
    inbound = deepcopy(base)
    inbound.update(
        id="IN",
        destination="SIN",
        destination_timezone="Asia/Singapore",
        departure_at=iso(3),
        cutoff_at=iso(2.25),
        arrival_at=iso(7),
    )
    outbound = deepcopy(base)
    outbound.update(
        id="OUT",
        origin="SIN",
        origin_timezone="Asia/Singapore",
        destination=unit["destination"],
        departure_at=iso(9),
        cutoff_at=iso(8.25),
        arrival_at=iso(53),
    )
    window = next(w for w in raw["handling_windows"] if w["id"] == "H-F-FRA-1")
    inbound_window = deepcopy(window)
    inbound_window["id"] = "H-IN"
    outbound_window = deepcopy(window)
    outbound_window.update(
        id="H-OUT", airport="SIN", start_at=iso(7), end_at=iso(8.25), capacity_units=4
    )
    permission = next(
        p
        for p in raw["route_permissions"]
        if p["cargo_unit_id"] == unit["id"] and p["flight_id"] == "F-FRA-1"
    )
    inbound_permission, outbound_permission = deepcopy(permission), deepcopy(permission)
    inbound_permission["flight_id"] = "IN"
    outbound_permission["flight_id"] = "OUT"
    connection_verification = deepcopy(inbound["capacity_verification"])
    raw.update(
        flights=[inbound, outbound],
        handling_windows=[inbound_window, outbound_window],
        route_permissions=[inbound_permission, outbound_permission],
        connections=[
            {
                "inbound_flight_id": "IN",
                "outbound_flight_id": "OUT",
                "min_transfer_seconds": 1800,
                "verification": connection_verification,
            }
        ],
    )
    raw["policy"]["source_max_age_seconds"] = 604800
    return ScenarioSnapshot.model_validate(raw)


def metric_map(plan):
    return {metric.name: metric for metric in plan.metrics}


def codes(result):
    return {item.code for item in result.violations}


def test_no_eligible_units_are_explicitly_undefined_not_zero_percent():
    snapshot = with_change(
        one_route_snapshot(),
        lambda raw: raw.update(
            flights=[], handling_windows=[], route_permissions=[], connections=[]
        ),
    )
    plan = run_solver(snapshot, max_wall_seconds=10)

    assert plan.assignments == []
    assert len(plan.unassigned) == 1
    assert plan.unassigned[0].reason_codes == ["NO_COMPLIANT_PATH"]
    assert plan.independent_validation.status == "PASS"
    metrics = metric_map(plan)
    eligible = metrics["proposed_departure_48h_eligible_uld_rate"]
    all_affected = metrics["proposed_departure_48h_all_affected_uld_rate"]
    assert (eligible.numerator, eligible.denominator, eligible.value, eligible.status) == (
        Decimal(0),
        Decimal(0),
        None,
        "UNDEFINED",
    )
    assert (all_affected.numerator, all_affected.denominator, all_affected.value) == (
        Decimal(0),
        Decimal(1),
        Decimal(0),
    )
    assert validate_solution_independently(snapshot, plan).status == "PASS"


def test_delay_metric_excludes_handling_and_churn_objective_terms():
    snapshot = one_route_snapshot()
    candidates = build_feasible_paths(snapshot)
    assert len(candidates.paths) == 1
    chosen_path_id = candidates.paths[0].id

    # The sole path is both a frozen obligation and inside its contractual deadline.
    def freeze(raw):
        raw["cargo_units"][0].update(
            frozen_path_id=chosen_path_id,
            contractual_latest_arrival=iso(8),
        )

    snapshot = with_change(snapshot, freeze)
    plan = run_solver(snapshot, max_wall_seconds=10)
    assert plan.independent_validation.status == "PASS"
    assert plan.solver.status == "OPTIMAL"
    assert len(plan.assignments) == 1 and not plan.unassigned

    # (7h arrival - 5h commitment) * weight 2 = 4h; one-leg handling 2 + churn 3.
    assert plan.solver.objective_value == Decimal(9)
    weighted = metric_map(plan)["weighted_delay_hours"]
    assert weighted.numerator == Decimal(4)
    assert weighted.denominator == Decimal(1)
    assert weighted.value == Decimal(4)
    assert weighted.statistic == "proposed_assigned_cargo_weighted_hours"
    assert validate_solution_independently(snapshot, plan).status == "PASS"


def test_multileg_metrics_use_first_departure_for_horizon_and_final_arrival_for_delay():
    snapshot = multileg_snapshot()
    candidates = build_feasible_paths(snapshot)
    assert {unit.id for unit in snapshot.cargo_units if unit.id in eligible_units(snapshot)} == {
        p.cargo_unit_id for p in candidates.paths
    }
    plan = run_solver(snapshot, max_wall_seconds=10)
    assert plan.independent_validation.status == "PASS"
    assert len(plan.assignments) == 1
    assert len(plan.assignments[0].legs) == 2
    assert plan.assignments[0].arrival_at == snapshot.flights[-1].arrival_at

    metrics = metric_map(plan)
    within_48 = metrics["proposed_departure_48h_eligible_uld_rate"]
    assert within_48.numerator == within_48.denominator == Decimal(1)
    assert within_48.value == Decimal(1)
    # The final arrival at +53h is 43h late against a +10h commitment, weighted by 2.
    assert metrics["weighted_delay_hours"].numerator == Decimal(86)
    assert metrics["weighted_delay_hours"].value == Decimal(86)
    assert validate_solution_independently(snapshot, plan).status == "PASS"

    missed_cutoff = with_change(
        snapshot,
        lambda raw: raw["connections"][0].update(min_transfer_seconds=7200),
    )
    assert eligible_units(missed_cutoff) == set()
    assert build_feasible_paths(missed_cutoff).paths == []


def test_validator_rejects_missing_unknown_duplicate_and_unbound_metric_rows():
    snapshot = one_route_snapshot()
    plan = run_solver(snapshot, max_wall_seconds=10)
    assert plan.independent_validation.status == "PASS"

    missing = plan.model_copy(update={"metrics": plan.metrics[:-1]})
    assert "MISSING_REQUIRED_METRIC" in codes(validate_solution_independently(snapshot, missing))

    unknown_metric = plan.metrics[0].model_copy(update={"name": "unknown_metric"})
    unknown = plan.model_copy(update={"metrics": [unknown_metric, *plan.metrics[1:]]})
    assert "UNKNOWN_COMPUTED_METRIC" in codes(validate_solution_independently(snapshot, unknown))

    duplicate = plan.model_copy(update={"metrics": [*plan.metrics, plan.metrics[0]]})
    assert "DUPLICATE_METRIC" in codes(validate_solution_independently(snapshot, duplicate))

    bad_lineage = plan.metrics[0].model_copy(update={"data_source_ids": []})
    changed = plan.model_copy(update={"metrics": [bad_lineage, *plan.metrics[1:]]})
    assert "METRIC_LINEAGE_MISMATCH" in codes(validate_solution_independently(snapshot, changed))


@pytest.mark.parametrize("seed,size", [(101, 1), (202, 2), (707, 4)])
def test_independent_denominator_matches_small_snapshot_candidate_eligibility(seed, size):
    snapshot = make_snapshot(size=size, seed=seed, as_of=NOW)
    candidates = build_feasible_paths(snapshot)
    independently_eligible = eligible_units(snapshot)
    optimizer_eligible = {path.cargo_unit_id for path in candidates.paths}
    assert independently_eligible == optimizer_eligible

    plan = run_solver(snapshot, max_wall_seconds=10)
    assert plan.independent_validation.status == "PASS"
    eligible_metric = metric_map(plan)["proposed_departure_48h_eligible_uld_rate"]
    assert eligible_metric.denominator == Decimal(len(independently_eligible))


def test_denominator_does_not_drop_units_when_optimizer_paths_are_pruned():
    # Add several verified direct options but retain one MILP candidate per ULD.
    raw = make_snapshot(size=1, seed=101, as_of=NOW).model_dump(mode="json")
    unit = raw["cargo_units"][0]
    raw["cargo_units"] = [unit]
    raw["policy"].update(max_paths_per_unit=1, source_max_age_seconds=604800)
    raw["valid_until"] = iso(48)
    snapshot = ScenarioSnapshot.model_validate(raw)
    candidates = build_feasible_paths(snapshot)
    assert candidates.pruned_path_count > 0
    assert {p.cargo_unit_id for p in candidates.paths} == eligible_units(snapshot)

    plan = run_solver(snapshot, max_wall_seconds=10)
    assert plan.independent_validation.status == "PASS"
    metric = metric_map(plan)["proposed_departure_48h_eligible_uld_rate"]
    assert metric.denominator == Decimal(1)


def test_later_candidate_query_does_not_admit_evidence_after_snapshot_as_of():
    snapshot = one_route_snapshot()
    changed = with_change(
        snapshot,
        lambda raw: raw["route_permissions"][0]["dg"].update(
            observed_at=(NOW + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
        ),
    )
    queried_later = NOW + timedelta(seconds=2)

    assert build_feasible_paths(changed, decision_time=queried_later).paths == []
    assert eligible_units(changed) == set()
