"""Two-stage bounded-integer MILP and matched greedy reference policies."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from time import monotonic

import highspy
from cargopulse_contracts import (
    Assignment,
    CandidateSet,
    MetricValue,
    ScenarioSnapshot,
    SolutionPlan,
    SolverStatus,
    SolverTelemetry,
    Unassigned,
    ValidationResult,
    canonical_hash,
)

from .candidates import MICRO, SCOPE, build_feasible_paths

EXACT_LIMIT = 2**52


def scale_exact(values):
    """Scale each Decimal exactly; bound sums to the exactly representable domain."""
    values = [Decimal(v) for v in values]
    power = max((max(0, -v.as_tuple().exponent) for v in values), default=0)
    scale = 10**power
    integers = [int(v * scale) for v in values]
    if any(Decimal(i) != v * scale for i, v in zip(integers, values, strict=True)):
        raise ValueError("NONEXACT_SCALING")
    if sum(abs(i) for i in integers) >= EXACT_LIMIT:
        raise ValueError("INTEGER_EXACT_RANGE_EXCEEDED")
    return integers, Decimal(scale)


def path_cost(p):
    return p.weighted_delay_hours + p.handling_cost + p.stability_cost


def unassigned_cost(snapshot, unit):
    return (snapshot.policy.unassigned_penalty_weighted_hours * unit.service_weight).quantize(
        MICRO, rounding=ROUND_CEILING
    )


def total_secondary_cost(snapshot, selected):
    assigned = {p.cargo_unit_id for p in selected}
    return sum((path_cost(p) for p in selected), Decimal(0)) + sum(
        (unassigned_cost(snapshot, u) for u in snapshot.cargo_units if u.id not in assigned),
        Decimal(0),
    )


def resources(snapshot, path):
    units = {u.id: u for u in snapshot.cargo_units}
    u = units[path.cargo_unit_id]
    result = defaultdict(Decimal)
    for leg in path.legs:
        for prefix in (("flight", leg.flight_id), ("position", leg.flight_id, leg.position_id)):
            result[prefix + ("mass",)] += u.actual_mass_kg
            result[prefix + ("volume",)] += u.actual_volume_m3
        result[("position", leg.flight_id, leg.position_id, "slots")] += 1
        result[("handling", leg.handling_window_id)] += 1
    return result


def capacities(snapshot):
    result = {}
    for f in snapshot.flights:
        if f.free_mass_kg is not None:
            result[("flight", f.id, "mass")] = f.free_mass_kg
        if f.free_volume_m3 is not None:
            result[("flight", f.id, "volume")] = f.free_volume_m3
        for p in f.positions:
            for name, value in (
                ("mass", p.free_mass_kg),
                ("volume", p.free_volume_m3),
                ("slots", p.slot_count),
            ):
                if value is not None:
                    result[("position", f.id, p.id, name)] = Decimal(value)
    result.update(
        {("handling", w.id): Decimal(w.capacity_units) for w in snapshot.handling_windows}
    )
    return result


@dataclass
class Milp:
    highs: object
    paths: list
    path_columns: list[int]
    unassigned_columns: list[int]
    cost_scale: Decimal
    integer_costs: list[int]
    integer_unassigned_costs: list[int]


def build_milp(snapshot: ScenarioSnapshot, candidates: CandidateSet | None = None) -> Milp:
    candidates = candidates or build_feasible_paths(snapshot)
    h = highspy.Highs()
    for key, value in {
        "output_flag": False,
        "threads": 1,
        "random_seed": 0,
        "mip_rel_gap": 0.0,
        "mip_abs_gap": 0.0,
        "mip_feasibility_tolerance": 1e-9,
        "primal_feasibility_tolerance": 1e-9,
    }.items():
        h.setOptionValue(key, value)
    paths = candidates.paths
    all_costs, cost_scale = scale_exact(
        [path_cost(p) for p in paths] + [unassigned_cost(snapshot, u) for u in snapshot.cargo_units]
    )
    costs = all_costs[: len(paths)]
    unassigned_costs = all_costs[len(paths) :]
    path_columns = []
    by_unit = defaultdict(list)
    by_resource = defaultdict(dict)
    for i, p in enumerate(paths):
        h.addVar(0, 1)
        h.changeColIntegrality(i, highspy.HighsVarType.kInteger)
        path_columns.append(i)
        by_unit[p.cargo_unit_id].append(i)
        for key, value in resources(snapshot, p).items():
            by_resource[key][i] = value
    zcols = []
    for u in snapshot.cargo_units:
        j = h.getNumCol()
        mandatory = bool(u.frozen_path_id or u.contractual_latest_arrival)
        h.addVar(0, 0 if mandatory else 1)
        h.changeColIntegrality(j, highspy.HighsVarType.kInteger)
        h.changeColCost(j, 1)
        zcols.append(j)
        cols = by_unit[u.id] + [j]
        h.addRow(1, 1, len(cols), cols, [1.0] * len(cols))
    limits = capacities(snapshot)
    for key, coefficients in by_resource.items():
        if key not in limits:
            raise ValueError("RESOURCE_CAPACITY_UNKNOWN")
        scaled, _ = scale_exact(list(coefficients.values()) + [limits[key]])
        h.addRow(-highspy.kHighsInf, scaled[-1], len(coefficients), list(coefficients), scaled[:-1])
    return Milp(h, paths, path_columns, zcols, cost_scale, costs, unassigned_costs)


def _finite(value, rounding=ROUND_CEILING):
    return Decimal(str(value)).quantize(MICRO, rounding=rounding) if math.isfinite(value) else None


def _validation_placeholder(snapshot):
    # Required only to construct the immutable DTO; immediately replaced by real validation.
    return ValidationResult(
        status="FAIL",
        checked_gates=[],
        violations=[],
        snapshot_hash=canonical_hash(snapshot),
        policy_hash=canonical_hash(snapshot.policy),
    )


def _metrics(snapshot, candidates, selected, engine):
    sh, ph = canonical_hash(snapshot), canonical_hash(snapshot.policy)
    eligible = {p.cargo_unit_id for p in candidates.paths}
    horizon = snapshot.as_of + timedelta(hours=48)
    flights = {f.id: f for f in snapshot.flights}
    recovered = sum(flights[p.legs[0].flight_id].departure_at <= horizon for p in selected)
    specs = [
        (
            "proposed_departure_48h_eligible_uld_rate",
            Decimal(recovered),
            Decimal(len(eligible)),
            "ratio",
        ),
        (
            "proposed_departure_48h_all_affected_uld_rate",
            Decimal(recovered),
            Decimal(len(snapshot.cargo_units)),
            "ratio",
        ),
        (
            "weighted_delay_hours",
            sum((p.weighted_delay_hours for p in selected), Decimal(0)),
            Decimal(1),
            "weighted_hours",
        ),
        (
            "unassigned_uld_count",
            Decimal(len(snapshot.cargo_units) - len(selected)),
            Decimal(1),
            "ULD",
        ),
    ]
    return [
        MetricValue(
            name=name,
            value=(num / den).quantize(MICRO) if den else None,
            unit=unit,
            numerator=num,
            denominator=den,
            cohort_id=snapshot.event_id,
            window_start_utc=snapshot.as_of,
            window_end_utc=horizon,
            event_as_of_utc=snapshot.as_of,
            data_source_ids=[snapshot.provenance.source_id],
            snapshot_hash=sh,
            policy_hash=ph,
            baseline_policy_version=f"{engine}-v1; matched candidates and resources",
            statistic=(
                "proposed_first_departure_within_48h_not_approved_capacity"
                if name.startswith("proposed_departure_")
                else "proposed_assigned_cargo_weighted_hours"
                if name == "weighted_delay_hours"
                else "explicit_escalated_whole_uld_count"
            ),
            status="COMPUTED" if den else "UNDEFINED",
        )
        for name, num, den, unit in specs
    ]


def _plan(snapshot, candidates, selected, telemetry):
    ids = {p.cargo_unit_id for p in selected}
    units = {u.id: u for u in snapshot.cargo_units}
    plan = SolutionPlan(
        snapshot_hash=canonical_hash(snapshot),
        policy_hash=canonical_hash(snapshot.policy),
        solver=telemetry,
        assignments=[
            Assignment(
                cargo_unit_id=p.cargo_unit_id,
                path_id=p.id,
                legs=p.legs,
                arrival_at=p.arrival_at,
                delay_hours=p.delay_hours,
                weighted_delay_hours=p.weighted_delay_hours,
                changed_from_previous=bool(
                    units[p.cargo_unit_id].previous_path_id
                    and units[p.cargo_unit_id].previous_path_id != p.id
                ),
                reason_codes=p.reason_codes + ["GLOBAL_RESOURCE_ALLOCATION"],
            )
            for p in selected
        ],
        unassigned=[
            Unassigned(
                cargo_unit_id=u.id,
                reason_codes=(
                    ["UNRESOLVED_HARD_OBLIGATION"]
                    if u.frozen_path_id or u.contractual_latest_arrival
                    else ["SHARED_RESOURCE_TRADEOFF"]
                    if any(p.cargo_unit_id == u.id for p in candidates.paths)
                    else sorted(
                        {
                            r
                            for e in candidates.excluded
                            if e.cargo_unit_id == u.id
                            for r in e.reason_codes
                        }
                    )
                    or ["NO_COMPLIANT_PATH"]
                ),
            )
            for u in snapshot.cargo_units
            if u.id not in ids
        ],
        independent_validation=_validation_placeholder(snapshot),
        metrics=_metrics(snapshot, candidates, selected, telemetry.engine),
        model_scope=SCOPE,
    )
    from cargopulse_validation import validate_solution_independently

    validation = validate_solution_independently(snapshot, plan, decision_time=snapshot.as_of)
    plan = plan.model_copy(update={"independent_validation": validation})
    if validation.status != "PASS" and telemetry.status not in {
        SolverStatus.INFEASIBLE,
        SolverStatus.ERROR,
    }:
        plan = plan.model_copy(
            update={
                "solver": telemetry.model_copy(
                    update={
                        "status": SolverStatus.ERROR,
                        "termination_reason": "INDEPENDENT_VALIDATION_FAILED; quarantined",
                    }
                )
            }
        )
    return plan


def _solve_stage(h, remaining):
    h.setOptionValue("time_limit", max(0.000001, remaining))
    h.run()
    return h.getModelStatus(), h.getSolution(), h.getInfo()


def run_solver(snapshot: ScenarioSnapshot, max_wall_seconds: int = 30) -> SolutionPlan:
    if (
        not isinstance(max_wall_seconds, int)
        or isinstance(max_wall_seconds, bool)
        or not 1 <= max_wall_seconds <= 60
    ):
        raise ValueError("max_wall_seconds must be an integer from 1 to 60")
    started = monotonic()
    candidates = build_feasible_paths(snapshot)
    model = None
    selected = []
    objective = bound = gap = None
    status = SolverStatus.ERROR
    reason = "MODEL_NOT_SOLVED"
    try:
        model = build_milp(snapshot, candidates)
        h = model.highs
        remaining = max_wall_seconds - (monotonic() - started)
        if remaining <= 0:
            status, reason = (
                SolverStatus.TIME_LIMIT_NO_FEASIBLE,
                "PREPARATION_EXHAUSTED_WALL_BUDGET",
            )
        else:
            stage1, solution1, info1 = _solve_stage(h, remaining)
            if stage1 == highspy.HighsModelStatus.kInfeasible:
                status, reason = SolverStatus.INFEASIBLE, "HARD_OBLIGATIONS_OR_RESOURCES_INFEASIBLE"
            elif solution1.value_valid:
                chosen = solution1
                status = SolverStatus.FEASIBLE
                reason = "STAGE1_UNASSIGNED_COUNT_NOT_PROVEN; incumbent_secondary_cost; bound/gap omitted"
                if stage1 == highspy.HighsModelStatus.kOptimal:
                    minimum = round(sum(solution1.col_value[j] for j in model.unassigned_columns))
                    h.addRow(
                        minimum,
                        minimum,
                        len(model.unassigned_columns),
                        model.unassigned_columns,
                        [1] * len(model.unassigned_columns),
                    )
                    for j, cost in zip(
                        model.unassigned_columns, model.integer_unassigned_costs, strict=True
                    ):
                        h.changeColCost(j, cost)
                    for j, cost in zip(model.path_columns, model.integer_costs, strict=True):
                        h.changeColCost(j, cost)
                    remaining = max_wall_seconds - (monotonic() - started)
                    if remaining > 0:
                        stage2, solution2, info2 = _solve_stage(h, remaining)
                        if solution2.value_valid:
                            chosen = solution2
                            bound = _finite(
                                info2.mip_dual_bound / float(model.cost_scale), ROUND_FLOOR
                            )
                            gap = _finite(info2.mip_gap)
                        if stage2 == highspy.HighsModelStatus.kOptimal and solution2.value_valid:
                            status, reason = (
                                SolverStatus.OPTIMAL,
                                f"LEXICOGRAPHIC_OPTIMAL; unassigned={minimum}; retained_paths_only",
                            )
                        elif stage2 in {
                            highspy.HighsModelStatus.kInterrupt,
                            highspy.HighsModelStatus.kHighsInterrupt,
                        }:
                            status, reason = SolverStatus.CANCELLED, "SOLVER_INTERRUPTED"
                        elif stage2 == highspy.HighsModelStatus.kTimeLimit:
                            status, reason = (
                                SolverStatus.TIME_LIMIT_WITH_FEASIBLE,
                                "STAGE2_WALL_LIMIT; validated incumbent",
                            )
                        else:
                            status, reason = (
                                SolverStatus.FEASIBLE,
                                f"STAGE2_{stage2.name}; stage1 count proven",
                            )
                    else:
                        status, reason = (
                            SolverStatus.TIME_LIMIT_WITH_FEASIBLE,
                            "WALL_BUDGET_EXHAUSTED_AFTER_STAGE1",
                        )
                elif stage1 == highspy.HighsModelStatus.kTimeLimit:
                    status = SolverStatus.TIME_LIMIT_WITH_FEASIBLE
                elif stage1 in {
                    highspy.HighsModelStatus.kInterrupt,
                    highspy.HighsModelStatus.kHighsInterrupt,
                }:
                    status, reason = SolverStatus.CANCELLED, "SOLVER_INTERRUPTED"
                values = list(chosen.col_value)
                if len(values) != h.getNumCol() or any(
                    not math.isfinite(v) or abs(v - round(v)) > 1e-7 or not -1e-7 <= v <= 1 + 1e-7
                    for v in values
                ):
                    raise ValueError("CORRUPT_NONBINARY_SOLVER_OUTPUT")
                selected = [
                    p
                    for p, j in zip(model.paths, model.path_columns, strict=True)
                    if values[j] > 0.5
                ]
                objective = total_secondary_cost(snapshot, selected)
            elif stage1 == highspy.HighsModelStatus.kTimeLimit:
                status, reason = (
                    SolverStatus.TIME_LIMIT_NO_FEASIBLE,
                    "STAGE1_WALL_LIMIT_NO_INCUMBENT",
                )
            elif stage1 in {
                highspy.HighsModelStatus.kInterrupt,
                highspy.HighsModelStatus.kHighsInterrupt,
            }:
                status, reason = SolverStatus.CANCELLED, "SOLVER_INTERRUPTED_NO_INCUMBENT"
            else:
                status, reason = SolverStatus.ERROR, f"SOLVER_{stage1.name}"
    except (ValueError, RuntimeError, OverflowError) as exc:
        selected = []
        objective = bound = gap = None
        status, reason = SolverStatus.ERROR, f"MODEL_REJECTED: {exc}"
    if not selected:
        reason += "; NO_RECOVERY_ASSIGNMENTS"
    telemetry = SolverTelemetry(
        engine="HiGHS",
        version=highspy.Highs().version(),
        status=status,
        wall_time_ms=Decimal(str((monotonic() - started) * 1000)).quantize(MICRO),
        time_limit_seconds=max_wall_seconds,
        objective_value=objective,
        best_bound=bound,
        optimality_gap=gap,
        variable_count=model.highs.getNumCol() if model else 0,
        candidate_count=len(candidates.paths),
        termination_reason=reason,
    )
    plan = _plan(snapshot, candidates, selected, telemetry)
    return plan.model_copy(
        update={
            "solver": plan.solver.model_copy(
                update={
                    "wall_time_ms": Decimal(str((monotonic() - started) * 1000)).quantize(MICRO)
                }
            )
        }
    )


def _baseline(snapshot, priority):
    started = monotonic()
    candidates = build_feasible_paths(snapshot)
    options = defaultdict(list)
    for p in candidates.paths:
        options[p.cargo_unit_id].append(p)
    used = defaultdict(Decimal)
    limits = capacities(snapshot)
    # Immutable/hard obligations go first for both reference policies.
    order = sorted(
        snapshot.cargo_units,
        key=lambda u: (
            not bool(u.frozen_path_id or u.contractual_latest_arrival),
            -u.service_weight
            if priority
            else min((p.arrival_at.timestamp() for p in options[u.id]), default=float("inf")),
            u.commitment_at,
            u.id,
        ),
    )
    selected = []
    for u in order:
        for p in sorted(options[u.id], key=lambda p: (p.arrival_at, path_cost(p), p.id)):
            consumption = resources(snapshot, p)
            if all(used[k] + v <= limits[k] for k, v in consumption.items()):
                selected.append(p)
                for k, v in consumption.items():
                    used[k] += v
                break
    assigned = {p.cargo_unit_id for p in selected}
    unresolved = any(
        (u.frozen_path_id or u.contractual_latest_arrival) and u.id not in assigned
        for u in snapshot.cargo_units
    )
    telemetry = SolverTelemetry(
        engine="PRIORITY_FIRST" if priority else "EARLIEST_FEASIBLE",
        version="reference-v1",
        status=SolverStatus.ERROR if unresolved else SolverStatus.FEASIBLE,
        wall_time_ms=Decimal(str((monotonic() - started) * 1000)).quantize(MICRO),
        time_limit_seconds=30,
        objective_value=total_secondary_cost(snapshot, selected),
        best_bound=None,
        optimality_gap=None,
        variable_count=0,
        candidate_count=len(candidates.paths),
        termination_reason="GREEDY_REFERENCE_NO_OPTIMALITY_CLAIM"
        + ("; UNRESOLVED_HARD_OBLIGATION_NO_INFEASIBILITY_PROOF" if unresolved else ""),
    )
    return _plan(snapshot, candidates, selected, telemetry)


def run_baseline_earliest(snapshot: ScenarioSnapshot) -> SolutionPlan:
    return _baseline(snapshot, False)


def run_baseline_priority(snapshot: ScenarioSnapshot) -> SolutionPlan:
    return _baseline(snapshot, True)


def explain_plan(snapshot, plan):
    """Structured explanations retain every alternative and explicit trade-off."""
    candidates = build_feasible_paths(snapshot)
    assigned = {a.cargo_unit_id: a.path_id for a in plan.assignments}
    return {
        u.id: {
            "selected_path_id": assigned.get(u.id),
            "alternatives": [
                {
                    "path_id": p.id,
                    "arrival_at": p.arrival_at.isoformat(),
                    "weighted_delay_hours": str(p.weighted_delay_hours),
                    "handling_cost": str(p.handling_cost),
                    "stability_cost": str(p.stability_cost),
                    "actionable_cutoff_at": p.cutoff_at.isoformat(),
                }
                for p in candidates.paths
                if p.cargo_unit_id == u.id
            ],
            "exclusions": [
                e.model_dump(mode="json") for e in candidates.excluded if e.cargo_unit_id == u.id
            ],
            "interpretation": "Alternatives are individually feasible; shared-resource allocation may prevent simultaneous use",
        }
        for u in snapshot.cargo_units
    }
