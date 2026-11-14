"""Independent release-math attacks; these tests do not modify implementation."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from cargopulse_contracts import ScenarioSnapshot, SolutionPlan, canonical_hash
from cargopulse_optimizer import build_feasible_paths, compute_urgency_delta, run_solver
from cargopulse_validation import validate_solution_independently

from packages.domain_fixtures.generator import make_snapshot

NOW = datetime(2026, 11, 10, tzinfo=timezone.utc)


def iso(hours: float) -> str:
    return (NOW + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


def snapshot_with(size: int = 1, seed: int = 2026) -> ScenarioSnapshot:
    return make_snapshot(size=size, seed=seed, as_of=NOW)


def rebind_plan(plan: SolutionPlan, snapshot: ScenarioSnapshot) -> SolutionPlan:
    """Re-sign the plan after a source mutation to avoid hash-only false positives."""
    raw = plan.model_dump(mode="json")
    snapshot_hash = canonical_hash(snapshot)
    policy_hash = canonical_hash(snapshot.policy)
    raw["snapshot_hash"] = snapshot_hash
    raw["policy_hash"] = policy_hash
    raw["independent_validation"]["snapshot_hash"] = snapshot_hash
    raw["independent_validation"]["policy_hash"] = policy_hash
    for metric in raw["metrics"]:
        metric["snapshot_hash"] = snapshot_hash
        metric["policy_hash"] = policy_hash
    return SolutionPlan.model_validate(raw)


def change_snapshot(snapshot: ScenarioSnapshot, mutate) -> ScenarioSnapshot:
    raw = snapshot.model_dump(mode="json")
    mutate(raw)
    return ScenarioSnapshot.model_validate(raw)


def solve(snapshot: ScenarioSnapshot) -> SolutionPlan:
    plan = run_solver(snapshot, max_wall_seconds=10)
    assert plan.assignments, "fixture must produce a concrete proposal"
    assert plan.independent_validation.status == "PASS"
    return plan


def violation_codes(result) -> set[str]:
    return {item.code for item in result.violations}


@pytest.mark.parametrize("state", ["FAIL", "UNKNOWN"])
@pytest.mark.parametrize("gate", ["dg", "customs", "cold_chain", "load_control"])
def test_each_nonpass_route_gate_rejects_the_preserved_assignment(gate, state):
    snapshot = snapshot_with()
    plan = solve(snapshot)
    assignment = plan.assignments[0]

    def mutate(raw):
        permission = next(
            item
            for item in raw["route_permissions"]
            if item["cargo_unit_id"] == assignment.cargo_unit_id
            and item["flight_id"] == assignment.legs[0].flight_id
        )
        permission[gate]["state"] = state

    changed = change_snapshot(snapshot, mutate)
    checked = validate_solution_independently(changed, rebind_plan(plan, changed))
    assert checked.status == "FAIL"
    assert "UNVERIFIED_GATE" in violation_codes(checked)


def test_freighter_only_dg_on_passenger_aircraft_is_rejected():
    snapshot = snapshot_with()
    plan = solve(snapshot)
    assignment = plan.assignments[0]
    flight_id = assignment.legs[0].flight_id

    def mutate(raw):
        next(u for u in raw["cargo_units"] if u["id"] == assignment.cargo_unit_id)["dg_class"] = (
            "FREIGHTER_ONLY"
        )
        next(f for f in raw["flights"] if f["id"] == flight_id)["is_freighter"] = False

    changed = change_snapshot(snapshot, mutate)
    checked = validate_solution_independently(changed, rebind_plan(plan, changed))
    assert checked.status == "FAIL"
    assert "DG_AIRCRAFT_INCOMPATIBLE" in violation_codes(checked)


def test_aggregate_flight_capacity_rejects_an_existing_physical_assignment():
    snapshot = snapshot_with()
    plan = solve(snapshot)
    assignment = plan.assignments[0]
    mass = next(u.actual_mass_kg for u in snapshot.cargo_units if u.id == assignment.cargo_unit_id)
    flight_id = assignment.legs[0].flight_id

    def mutate(raw):
        flight = next(f for f in raw["flights"] if f["id"] == flight_id)
        flight["free_mass_kg"] = str(mass - Decimal("0.000001"))

    changed = change_snapshot(snapshot, mutate)
    checked = validate_solution_independently(changed, rebind_plan(plan, changed))
    assert checked.status == "FAIL"
    assert "FLIGHT_MASS_EXCEEDED" in violation_codes(checked)


def multileg_snapshot() -> ScenarioSnapshot:
    source = snapshot_with(seed=101)
    raw = source.model_dump(mode="json")
    base_flight = deepcopy(raw["flights"][0])
    inbound = deepcopy(base_flight)
    inbound.update(
        id="IN",
        destination="SIN",
        departure_at=iso(3),
        cutoff_at=iso(2.25),
        arrival_at=iso(7),
    )
    outbound = deepcopy(base_flight)
    outbound.update(
        id="OUT",
        origin="SIN",
        destination=raw["cargo_units"][0]["destination"],
        departure_at=iso(9),
        cutoff_at=iso(8.25),
        arrival_at=iso(13),
    )
    first_window = next(w for w in raw["handling_windows"] if w["id"] == "H-F-FRA-1")
    first_window = deepcopy(first_window)
    first_window["id"] = "H-IN"
    second_window = deepcopy(first_window)
    second_window.update(id="H-OUT", airport="SIN", start_at=iso(7), end_at=iso(8.25))
    permission = next(
        p
        for p in raw["route_permissions"]
        if p["cargo_unit_id"] == raw["cargo_units"][0]["id"] and p["flight_id"] == "F-FRA-1"
    )
    inbound_permission, outbound_permission = deepcopy(permission), deepcopy(permission)
    inbound_permission["flight_id"] = "IN"
    outbound_permission["flight_id"] = "OUT"
    connection_proof = deepcopy(inbound["capacity_verification"])
    raw.update(
        flights=[inbound, outbound],
        handling_windows=[first_window, second_window],
        route_permissions=[inbound_permission, outbound_permission],
        connections=[
            {
                "inbound_flight_id": "IN",
                "outbound_flight_id": "OUT",
                "min_transfer_seconds": 1800,
                "verification": connection_proof,
            }
        ],
    )
    return ScenarioSnapshot.model_validate(raw)


def test_multileg_connection_cutoff_and_connection_evidence_expiry_fail_closed():
    snapshot = multileg_snapshot()
    plan = solve(snapshot)
    assert len(plan.assignments[0].legs) == 2

    too_long = change_snapshot(
        snapshot,
        lambda raw: raw["connections"][0].update(min_transfer_seconds=18000),
    )
    checked = validate_solution_independently(too_long, rebind_plan(plan, too_long))
    assert checked.status == "FAIL"
    assert "MISSED_HANDLING_OR_CUTOFF" in violation_codes(checked)
    assert not build_feasible_paths(too_long).paths

    expires_at_departure = change_snapshot(
        snapshot,
        lambda raw: raw["connections"][0]["verification"].update(valid_until=iso(9)),
    )
    checked = validate_solution_independently(
        expires_at_departure, rebind_plan(plan, expires_at_departure)
    )
    assert checked.status == "FAIL"
    assert "EVIDENCE_NOT_VALID" in violation_codes(checked)
    assert not build_feasible_paths(expires_at_departure).paths


def test_future_gate_evidence_and_future_published_policy_are_not_usable():
    snapshot = snapshot_with()
    plan = solve(snapshot)
    assignment = plan.assignments[0]
    future_proof = change_snapshot(
        snapshot,
        lambda raw: next(
            p
            for p in raw["route_permissions"]
            if p["cargo_unit_id"] == assignment.cargo_unit_id
            and p["flight_id"] == assignment.legs[0].flight_id
        )["dg"].update(observed_at=(NOW + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")),
    )
    checked = validate_solution_independently(future_proof, rebind_plan(plan, future_proof))
    assert checked.status == "FAIL"
    assert "EVIDENCE_NOT_VALID" in violation_codes(checked)
    default_candidates = build_feasible_paths(future_proof)
    assert not any(
        path.cargo_unit_id == assignment.cargo_unit_id
        and any(leg.flight_id == assignment.legs[0].flight_id for leg in path.legs)
        for path in default_candidates.paths
    )
    later = NOW + timedelta(seconds=2)
    later_candidates = build_feasible_paths(future_proof, decision_time=later)
    assert not any(
        path.cargo_unit_id == assignment.cargo_unit_id
        and any(leg.flight_id == assignment.legs[0].flight_id for leg in path.legs)
        for path in later_candidates.paths
    )
    checked_at_later = validate_solution_independently(
        future_proof, rebind_plan(plan, future_proof), decision_time=later
    )
    assert checked_at_later.status == "FAIL"
    assert "EVIDENCE_NOT_VALID" in violation_codes(checked_at_later)

    future_policy = change_snapshot(snapshot, lambda raw: raw["policy"].update(published_at=iso(1)))
    checked = validate_solution_independently(future_policy, rebind_plan(plan, future_policy))
    assert checked.status == "FAIL"
    assert "FUTURE_POLICY" in violation_codes(checked)
    assert not build_feasible_paths(future_policy).paths


def test_frozen_path_obligation_cannot_be_reassigned_or_dropped():
    snapshot = snapshot_with()
    plan = solve(snapshot)
    assignment = plan.assignments[0]
    frozen = change_snapshot(
        snapshot,
        lambda raw: next(
            u for u in raw["cargo_units"] if u["id"] == assignment.cargo_unit_id
        ).update(frozen_path_id="P-a-different-path"),
    )
    checked = validate_solution_independently(frozen, rebind_plan(plan, frozen))
    assert checked.status == "FAIL"
    assert "FROZEN_ASSIGNMENT_CHANGED" in violation_codes(checked)


def test_urgency_replay_is_invariant_to_milp_candidate_pruning():
    raw = snapshot_with(seed=101).model_dump(mode="json")
    raw["policy"].update(source_max_age_seconds=604800, max_paths_per_unit=1)
    raw["valid_until"] = iso(48)
    pruned_limit = ScenarioSnapshot.model_validate(raw)
    raw["policy"]["max_paths_per_unit"] = 100
    unpruned_limit = ScenarioSnapshot.model_validate(raw)
    times = [NOW, NOW + timedelta(hours=2), NOW + timedelta(hours=8), NOW + timedelta(hours=20)]

    assert build_feasible_paths(pruned_limit).pruned_path_count > 0
    assert compute_urgency_delta(pruned_limit, times) == compute_urgency_delta(
        unpruned_limit, times
    )


def test_metric_tampering_is_rejected_before_plan_is_treated_as_validated_evidence():
    snapshot = snapshot_with()
    plan = solve(snapshot)
    raw = plan.model_dump(mode="json")
    raw["metrics"][0].update(
        value="0.873",
        numerator="873",
        denominator="1000",
        cohort_id="FORGED-COHORT",
        snapshot_hash="0" * 64,
        policy_hash="f" * 64,
        data_source_ids=[],
        statistic="verified_live_success",
        status="COMPUTED",
    )
    corrupted = SolutionPlan.model_validate(raw)
    checked = validate_solution_independently(snapshot, corrupted)

    assert checked.status == "FAIL", (
        "plan-level evidence verification accepted fabricated metric content; "
        "physical assignment validity alone must not validate/export KPI evidence"
    )
