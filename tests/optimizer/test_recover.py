from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import highspy
import pytest
from cargopulse_contracts import ScenarioSnapshot
from cargopulse_optimizer import (
    build_feasible_paths,
    compute_urgency_delta,
    run_baseline_earliest,
    run_baseline_priority,
    run_solver,
    solver,
)
from cargopulse_optimizer.solver import scale_exact
from conftest import NOW, edit, iso, weighted_snapshot
from hypothesis import given, settings
from hypothesis import strategies as st


def first(plan):
    return {a.cargo_unit_id: a.legs[0].flight_id for a in plan.assignments}


def test_RF01_weighted24_vs8_same_assignment_count(weighted):
    plan = run_solver(weighted)
    assert plan.solver.status == "OPTIMAL"
    assert first(plan) == {"U-0001": "A-LATER", "U-0002": "NOW"}
    assert plan.solver.objective_value == 8
    assert plan.solver.best_bound == 8
    assert plan.solver.optimality_gap == 0
    assert plan.independent_validation.status == "PASS"
    assert first(run_baseline_priority(weighted)) == {"U-0001": "NOW", "U-0002": "B-LATER"}
    assert run_baseline_earliest(weighted).independent_validation.status == "PASS"


def test_RF02_contractual_hard_priority(weighted):
    s = edit(weighted, lambda d: d["cargo_units"][0].update(contractual_latest_arrival=iso(4)))
    assert first(run_solver(s))["U-0001"] == "NOW"
    impossible = edit(s, lambda d: d.update(route_permissions=[]))
    p = run_solver(impossible)
    assert p.solver.status == "INFEASIBLE"
    assert not p.assignments
    assert p.independent_validation.status == "FAIL"


def test_RF03_cold_unknown_blocks_and_explains(weighted):
    def mutate(d):
        d["cargo_units"][0].update(service_class="PHARMA", requires_cold_chain=True)
        for p in d["route_permissions"]:
            if p["cargo_unit_id"] == "U-0001":
                p["cold_chain"]["state"] = "UNKNOWN"

    s = edit(weighted, mutate)
    c = build_feasible_paths(s)
    assert all(p.cargo_unit_id != "U-0001" for p in c.paths)
    assert any(e.gate == "F" for e in c.excluded)
    assert any(q.entity_id == "U-0001" and q.blocking for q in c.quality_issues)
    assert any(u.cargo_unit_id == "U-0001" for u in run_solver(s).unassigned)


def test_RF04_dg_restriction(weighted):
    def mutate(d):
        d["cargo_units"][0]["dg_class"] = "FREIGHTER_ONLY"
        for f in d["flights"]:
            f["is_freighter"] = False

    c = build_feasible_paths(edit(weighted, mutate))
    assert all(p.cargo_unit_id != "U-0001" for p in c.paths)
    assert any("DG_AIRCRAFT_INCOMPATIBLE" in e.reason_codes for e in c.excluded)


@pytest.mark.parametrize(
    "scope,field,value",
    [
        ("flight", "free_volume_m3", "3"),
        ("flight", "free_mass_kg", "999"),
        ("position", "slot_count", 0),
        ("position", "free_mass_kg", "999"),
        ("position", "free_volume_m3", "3"),
        ("handling", "capacity_units", 0),
    ],
)
def test_RF05_physical_capacity_fail_closed(weighted, scope, field, value):
    def mutate(d):
        for f in d["flights"]:
            if scope == "flight":
                f[field] = value
            if scope == "position":
                f["positions"][0][field] = value
        if scope == "handling":
            for w in d["handling_windows"]:
                w[field] = value

    p = run_solver(edit(weighted, mutate))
    assert not p.assignments
    assert len(p.unassigned) == 2
    assert p.independent_validation.status == "PASS"
    assert "NO_RECOVERY_ASSIGNMENTS" in p.solver.termination_reason


def test_RF06_contour_fail_closed(weighted):
    s = edit(weighted, lambda d: d["cargo_units"][0].update(contour="OTHER"))
    c = build_feasible_paths(s)
    assert all(p.cargo_unit_id != "U-0001" for p in c.paths)
    assert any(e.gate == "B" for e in c.excluded)


def multileg(weighted, minimum=1800):
    d = weighted.model_dump(mode="json")
    d["cargo_units"] = d["cargo_units"][:1]
    inbound = deepcopy(d["flights"][0])
    outbound = deepcopy(d["flights"][1])
    inbound.update(id="IN", destination="SIN", arrival_at=iso(3))
    outbound.update(
        id="OUT", origin="SIN", departure_at=iso(5), cutoff_at=iso(4.5), arrival_at=iso(8)
    )
    w1, w2 = deepcopy(d["handling_windows"][0]), deepcopy(d["handling_windows"][1])
    w1["id"] = "H-IN"
    w2.update(id="H-OUT", airport="SIN", start_at=iso(3), end_at=iso(4.5))
    proof = deepcopy(inbound["capacity_verification"])
    p1, p2 = deepcopy(d["route_permissions"][0]), deepcopy(d["route_permissions"][0])
    p1["flight_id"], p2["flight_id"] = "IN", "OUT"
    d.update(
        flights=[inbound, outbound],
        handling_windows=[w1, w2],
        route_permissions=[p1, p2],
        connections=[
            dict(
                inbound_flight_id="IN",
                outbound_flight_id="OUT",
                min_transfer_seconds=minimum,
                verification=proof,
            )
        ],
    )
    return ScenarioSnapshot.model_validate(d)


def test_RF07_multileg_requires_explicit_connection_and_handling(weighted):
    s = multileg(weighted)
    p = run_solver(s)
    assert len(p.assignments[0].legs) == 2
    assert p.independent_validation.status == "PASS"
    assert not build_feasible_paths(edit(s, lambda d: d.update(connections=[]))).paths
    assert not build_feasible_paths(multileg(weighted, minimum=7200)).paths
    assert not build_feasible_paths(
        edit(s, lambda d: d.update(handling_windows=d["handling_windows"][:1]))
    ).paths


def test_RF08_urgency_actionable_deadline(weighted):
    c = build_feasible_paths(weighted)
    cutoff = min(p.cutoff_at for p in c.paths)
    points = compute_urgency_delta(weighted, [cutoff, cutoff + timedelta(microseconds=1)])
    a = [p for p in points if p.cargo_unit_id == "U-0001"]
    assert a[0].delta_weighted_hours == 0
    assert a[1].delta_weighted_hours == 8
    exhausted = compute_urgency_delta(weighted, [NOW + timedelta(hours=29)])
    assert all(
        p.status == "NO_COMPLIANT_PATH" and p.delta_weighted_hours is None for p in exhausted
    )


def test_RF09_no_path_no_fabricated_recovery(weighted):
    p = run_solver(edit(weighted, lambda d: d.update(flights=[], route_permissions=[])))
    assert not p.assignments and len(p.unassigned) == 2
    assert p.independent_validation.status == "PASS"
    assert p.solver.status == "OPTIMAL"  # Actual all-escalation mathematical optimum.


def test_RF10_new_capacity_cut_changes_hash_and_plan(weighted):
    original = run_solver(weighted)

    def mutate(d):
        d["source_version"] += 1
        d["flights"][0]["free_mass_kg"] = "0"

    cut = run_solver(edit(weighted, mutate))
    assert original.snapshot_hash != cut.snapshot_hash
    assert all(a.legs[0].flight_id != "NOW" for a in cut.assignments)
    assert original.independent_validation.status == "PASS"


def test_RF11_timeout_with_real_incumbent_is_not_optimal(weighted, monkeypatch):
    actual = solver._solve_stage
    calls = []

    def time_limit(h, budget):
        status, solution, info = actual(h, budget)
        calls.append(budget)
        return highspy.HighsModelStatus.kTimeLimit, solution, info

    monkeypatch.setattr(solver, "_solve_stage", time_limit)
    p = run_solver(weighted)
    assert p.solver.status == "TIME_LIMIT_WITH_FEASIBLE"
    assert p.independent_validation.status == "PASS"
    assert p.solver.best_bound is None  # Count-stage bound is not a service-cost bound.
    assert len(calls) == 1


def test_RF12_timeout_without_incumbent(weighted, monkeypatch):
    monkeypatch.setattr(
        solver,
        "_solve_stage",
        lambda h, t: (
            highspy.HighsModelStatus.kTimeLimit,
            SimpleNamespace(value_valid=False),
            SimpleNamespace(),
        ),
    )
    p = run_solver(weighted)
    assert p.solver.status == "TIME_LIMIT_NO_FEASIBLE"
    assert not p.assignments
    assert len(p.unassigned) == 2


@pytest.mark.parametrize("field", ["dg", "customs", "cold_chain", "load_control"])
def test_expired_during_route_not_just_decision(weighted, field):
    def mutate(d):
        for p in d["route_permissions"]:
            p[field]["valid_until"] = iso(3)

    assert not build_feasible_paths(edit(weighted, mutate)).paths


def test_frozen_approved_path_atomic(weighted):
    chosen = run_solver(weighted).assignments[0]

    def mutate(d):
        u = next(u for u in d["cargo_units"] if u["id"] == chosen.cargo_unit_id)
        u["frozen_path_id"] = chosen.path_id

    p = run_solver(edit(weighted, mutate))
    assert (
        next(a for a in p.assignments if a.cargo_unit_id == chosen.cargo_unit_id).path_id
        == chosen.path_id
    )
    impossible = edit(weighted, lambda d: d["cargo_units"][0].update(frozen_path_id="NONEXISTENT"))
    assert run_solver(impossible).solver.status == "INFEASIBLE"


def test_exact_decimal_scaling_no_float_defaults():
    integers, factor = scale_exact([Decimal("0.000001"), Decimal("1000.000001")])
    assert all(
        Decimal(i) / factor == v
        for i, v in zip(integers, [Decimal("0.000001"), Decimal("1000.000001")])
    )
    with pytest.raises(ValueError, match="EXACT_RANGE"):
        scale_exact([Decimal("1000000000.000001"), Decimal("0.000001")] * 6)


@given(st.integers(min_value=0, max_value=2), st.integers(min_value=0, max_value=2))
@settings(max_examples=12, deadline=None)
def test_property_shared_resources_never_overrun(slots, handling):
    s = weighted_snapshot()

    def mutate(d):
        d["flights"] = d["flights"][:1]
        d["flights"][0]["positions"][0]["slot_count"] = slots
        d["handling_windows"] = d["handling_windows"][:1]
        d["handling_windows"][0]["capacity_units"] = handling
        d["route_permissions"] = [p for p in d["route_permissions"] if p["flight_id"] == "NOW"]

    p = run_solver(edit(s, mutate))
    assert len(p.assignments) <= min(slots, handling)
    assert len(p.assignments) + len(p.unassigned) == 2
    assert p.independent_validation.status == "PASS"


def test_stage2_timeout_budget_is_shared(weighted, monkeypatch):
    actual = solver._solve_stage
    budgets = []
    # Account for a known stage duration independently of host clock resolution.
    clock = [100.0]
    monkeypatch.setattr(solver, "monotonic", lambda: clock[0])

    def capped(h, budget):
        budgets.append(budget)
        status, solution, info = actual(h, budget)
        clock[0] += 0.25
        if len(budgets) == 2:
            return highspy.HighsModelStatus.kTimeLimit, solution, info
        return status, solution, info

    monkeypatch.setattr(solver, "_solve_stage", capped)
    p = run_solver(weighted, max_wall_seconds=2)
    assert p.solver.status == "TIME_LIMIT_WITH_FEASIBLE"
    assert p.independent_validation.status == "PASS"
    assert budgets == pytest.approx([2, 1.75])
    assert p.solver.best_bound == 8


def test_native_solver_interrupt_status(weighted, monkeypatch):
    actual = solver._solve_stage

    def interrupted(h, budget):
        status, solution, info = actual(h, budget)
        return highspy.HighsModelStatus.kInterrupt, solution, info

    monkeypatch.setattr(solver, "_solve_stage", interrupted)
    p = run_solver(weighted)
    assert p.solver.status == "CANCELLED"
    assert p.independent_validation.status == "PASS"


def test_corrupt_fractional_solver_output_rejected(weighted, monkeypatch):
    actual = solver._solve_stage

    def corrupted(h, budget):
        status, solution, info = actual(h, budget)
        values = list(solution.col_value)
        values[0] = 0.75
        return (
            highspy.HighsModelStatus.kTimeLimit,
            SimpleNamespace(value_valid=True, col_value=values),
            info,
        )

    monkeypatch.setattr(solver, "_solve_stage", corrupted)
    p = run_solver(weighted)
    assert p.solver.status == "ERROR"
    assert not p.assignments
    assert "CORRUPT_NONBINARY" in p.solver.termination_reason


def test_independent_validator_quarantines_corrupt_resource_allocation(weighted, monkeypatch):
    actual = solver._solve_stage

    def corrupted(h, budget):
        status, solution, info = actual(h, budget)
        candidates = build_feasible_paths(weighted)
        values = [0.0] * h.getNumCol()
        # Assign both ULDs to the single-slot immediate resource.
        for i, p in enumerate(candidates.paths):
            if p.legs[0].flight_id == "NOW":
                values[i] = 1.0
        return (
            highspy.HighsModelStatus.kTimeLimit,
            SimpleNamespace(value_valid=True, col_value=values),
            info,
        )

    monkeypatch.setattr(solver, "_solve_stage", corrupted)
    p = run_solver(weighted)
    assert p.solver.status == "ERROR"
    assert p.independent_validation.status == "FAIL"
    assert "quarantined" in p.solver.termination_reason


def test_future_stale_and_unknown_no_defaults(weighted):
    future = edit(weighted, lambda d: d["provenance"].update(ingested_at=iso(1)))
    assert not build_feasible_paths(future).paths
    missing = edit(weighted, lambda d: d["flights"][0].update(free_mass_kg=None))
    c = build_feasible_paths(missing)
    assert all(p.legs[0].flight_id != "NOW" for p in c.paths)
    assert any(q.code == "MISSING_PAYLOAD" for q in c.quality_issues)
    security = edit(weighted, lambda d: d["cargo_units"][0]["security"].update(valid_until=iso(3)))
    assert all(p.cargo_unit_id != "U-0001" for p in build_feasible_paths(security).paths)


def test_UTC_midnight_DST_does_not_use_local_wall_clock(weighted):
    from datetime import datetime, timezone

    # New York DST fall-back day: UTC chronology stays exact across local ambiguity.
    anchor = datetime(2026, 11, 1, 23, 30, tzinfo=timezone.utc)
    delta = anchor - NOW
    d = weighted.model_dump(mode="json")

    def shift(value):
        if isinstance(value, dict):
            return {k: shift(v) for k, v in value.items()}
        if isinstance(value, list):
            return [shift(v) for v in value]
        if isinstance(value, str) and value.startswith("2026-"):
            return (datetime.fromisoformat(value.replace("Z", "+00:00")) + delta).isoformat()
        return value

    d = shift(d)
    for f in d["flights"]:
        f.update(origin_timezone="America/New_York", destination_timezone="Europe/London")
    p = run_solver(ScenarioSnapshot.model_validate(d))
    assert p.solver.objective_value == 8
    assert p.independent_validation.status == "PASS"


def test_metric_48h_uses_proposed_first_departure_not_arrival(weighted):
    def mutate(d):
        # Departure is within 48h but physical arrival is deliberately outside.
        for f in d["flights"]:
            f["arrival_at"] = iso(55)
        for u in d["cargo_units"]:
            u["commitment_at"] = iso(60)

    p = run_solver(edit(weighted, mutate))
    metrics = {m.name: m for m in p.metrics}
    eligible = metrics["proposed_departure_48h_eligible_uld_rate"]
    assert eligible.numerator == eligible.denominator == 2
    assert eligible.value == 1
    assert eligible.statistic == "proposed_first_departure_within_48h_not_approved_capacity"
    assert metrics["weighted_delay_hours"].statistic == "proposed_assigned_cargo_weighted_hours"
    assert metrics["unassigned_uld_count"].unit == "ULD"


def test_urgency_weighted_minimum_independent_of_total_cost_pruning(weighted):
    def mutate(d):
        d["policy"]["max_paths_per_unit"] = 1

    s = edit(weighted, mutate)
    c = build_feasible_paths(s)
    assert c.pruned_path_count > 0
    # Latest-cutoff preservation may prune the immediate option from MILP candidates;
    # urgency must still use all mathematically feasible policy-weighted lateness paths.
    points = compute_urgency_delta(s, [NOW, NOW + timedelta(hours=2)])
    a = [p for p in points if p.cargo_unit_id == "U-0001"]
    assert a[0].delta_weighted_hours == 0
    assert a[1].delta_weighted_hours == 8


def test_explicit_unassigned_policy_cost_effect_and_baseline_accounting(weighted):
    def mutate(d):
        d["flights"] = d["flights"][:1]
        d["handling_windows"] = d["handling_windows"][:1]
        d["route_permissions"] = [p for p in d["route_permissions"] if p["flight_id"] == "NOW"]
        # Equal count: serving A costs 2 weighted lateness hours, versus B at zero.
        d["cargo_units"][0]["commitment_at"] = iso(3)
        d["policy"]["unassigned_penalty_weighted_hours"] = "1"

    low = edit(weighted, mutate)
    p_low = run_solver(low)
    assert first(p_low) == {"U-0002": "NOW"}
    assert p_low.solver.objective_value == 2  # Unassigned A: weight 2 * penalty 1.
    high = edit(low, lambda d: d["policy"].update(unassigned_penalty_weighted_hours="10"))
    p_high = run_solver(high)
    assert first(p_high) == {"U-0001": "NOW"}
    assert p_high.solver.objective_value == 12  # Assigned A: delay 2; unassigned B: 10.
    assert p_high.solver.best_bound == 12
    baseline = run_baseline_priority(high)
    assert baseline.solver.objective_value == 12
    assert len(p_low.unassigned) == len(p_high.unassigned) == 1


def test_stability_cost_can_preserve_previous_soft_assignments(weighted):
    previous = run_baseline_priority(weighted)
    paths = {a.cargo_unit_id: a.path_id for a in previous.assignments}

    def mutate(d):
        d["policy"]["stability_penalty_weighted_hours"] = "100"
        for u in d["cargo_units"]:
            u["previous_path_id"] = paths[u["id"]]

    s = edit(weighted, mutate)
    first_run, second_run = run_solver(s), run_solver(s)
    assert first(first_run) == first(previous)
    assert first(first_run) == first(second_run)
    assert first_run.solver.objective_value == 24
    assert all(not a.changed_from_previous for a in first_run.assignments)
    assert first_run.independent_validation.status == "PASS"
