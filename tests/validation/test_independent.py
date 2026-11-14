"""Adversarial tests authored independently from the optimizer implementation."""

from datetime import datetime, timedelta, timezone
from decimal import ROUND_CEILING, Decimal

import pytest
from cargopulse_contracts import (
    Assignment,
    MetricValue,
    ScenarioSnapshot,
    SolutionPlan,
    SolverTelemetry,
    ValidationResult,
    canonical_hash,
)
from cargopulse_validation import validate_solution_independently
from hypothesis import given, settings
from hypothesis import strategies as st

from packages.domain_fixtures.generator import make_snapshot

NOW = datetime(2026, 11, 10, 0, 0, tzinfo=timezone.utc)


def legal_plan(snapshot=None):
    snapshot = snapshot or make_snapshot(size=1, as_of=NOW)
    unit = snapshot.cargo_units[0]
    flight = snapshot.flights[0]
    legs = [dict(flight_id=flight.id, position_id="POOL", handling_window_id="H-" + flight.id)]
    path_id = "P-" + canonical_hash(dict(cargo_unit_id=unit.id, legs=legs))[:24]
    delay = (
        Decimal(str(max((flight.arrival_at - unit.commitment_at).total_seconds(), 0)))
        / Decimal(3600)
    ).quantize(Decimal("0.000001"), rounding=ROUND_CEILING)
    weighted = (delay * unit.service_weight).quantize(Decimal("0.000001"), rounding=ROUND_CEILING)
    metrics = [
        MetricValue(
            name=name,
            value=value,
            unit=measure,
            numerator=value,
            denominator="1",
            cohort_id=snapshot.event_id,
            window_start_utc=snapshot.as_of,
            window_end_utc=snapshot.as_of + timedelta(hours=48),
            event_as_of_utc=snapshot.as_of,
            data_source_ids=[snapshot.provenance.source_id],
            snapshot_hash=canonical_hash(snapshot),
            policy_hash=canonical_hash(snapshot.policy),
            baseline_policy_version="EARLIEST_FEASIBLE-v1; matched candidates and resources",
            statistic=statistic,
            status="COMPUTED",
        )
        for name, value, measure, statistic in [
            (
                "proposed_departure_48h_eligible_uld_rate",
                "1",
                "ratio",
                "proposed_first_departure_within_48h_not_approved_capacity",
            ),
            (
                "proposed_departure_48h_all_affected_uld_rate",
                "1",
                "ratio",
                "proposed_first_departure_within_48h_not_approved_capacity",
            ),
            (
                "weighted_delay_hours",
                weighted,
                "weighted_hours",
                "proposed_assigned_cargo_weighted_hours",
            ),
            ("unassigned_uld_count", "0", "ULD", "explicit_escalated_whole_uld_count"),
        ]
    ]
    plan = SolutionPlan(
        snapshot_hash=canonical_hash(snapshot),
        policy_hash=canonical_hash(snapshot.policy),
        solver=SolverTelemetry(
            engine="EARLIEST_FEASIBLE",
            version="test-independent-v1",
            status="FEASIBLE",
            wall_time_ms="0",
            time_limit_seconds=30,
            objective_value=None,
            best_bound=None,
            optimality_gap=None,
            variable_count=1,
            candidate_count=1,
            termination_reason="Independent verifier test",
        ),
        assignments=[
            Assignment(
                cargo_unit_id=unit.id,
                path_id=path_id,
                legs=legs,
                arrival_at=flight.arrival_at,
                delay_hours=delay,
                weighted_delay_hours=weighted,
                changed_from_previous=False,
                reason_codes=["VERIFIER_TEST"],
            )
        ],
        unassigned=[],
        metrics=metrics,
        independent_validation=ValidationResult(
            status="PASS",
            checked_gates=[],
            violations=[],
            snapshot_hash=canonical_hash(snapshot),
            policy_hash=canonical_hash(snapshot.policy),
        ),
        model_scope="SYNTHETIC_CONSERVATIVE_ENVELOPE",
    )
    return snapshot, plan


def codes(snapshot, plan, now=None):
    r = validate_solution_independently(snapshot, plan, now)
    return r, {v.code for v in r.violations}


def test_accepts_genuine_feasible_proposal_and_ignores_embedded_validation():
    s, p = legal_plan()
    r = validate_solution_independently(s, p)
    assert r.status == "PASS"
    assert r.checked_gates == list("ABCDEFGH") + ["CONTRACT"]
    p = p.model_copy(
        update={
            "independent_validation": p.independent_validation.model_copy(update={"status": "FAIL"})
        }
    )
    assert validate_solution_independently(s, p).status == "PASS"


def test_rejects_duplicate_assignment_even_when_forged_validation_says_pass():
    s, p = legal_plan()
    p = p.model_copy(update={"assignments": p.assignments * 2})
    r, c = codes(s, p)
    assert r.status == "FAIL"
    assert {"ASSIGNMENT_CARDINALITY", "DUPLICATE_PHYSICAL_PIECE"} <= c


@pytest.mark.parametrize(
    "mutate,expected",
    [
        (lambda d: d["flights"][0].update(free_mass_kg="1"), "FLIGHT_MASS_EXCEEDED"),
        (lambda d: d["flights"][0].update(free_volume_m3="0"), "FLIGHT_VOLUME_EXCEEDED"),
        (lambda d: d["flights"][0]["positions"][0].update(slot_count=0), "POSITION_SLOTS_EXCEEDED"),
        (
            lambda d: d["flights"][0]["positions"][0].update(free_mass_kg=None),
            "POSITION_MASS_EXCEEDED",
        ),
        (
            lambda d: d["flights"][0]["positions"][0].update(allowed_contours=["OTHER"]),
            "ULD_CONTOUR_INCOMPATIBLE",
        ),
        (lambda d: d["handling_windows"][0].update(capacity_units=0), "HANDLING_CAPACITY_EXCEEDED"),
        (
            lambda d: d["route_permissions"][0]["cold_chain"].update(state="UNKNOWN"),
            "UNVERIFIED_GATE",
        ),
        (lambda d: d["route_permissions"][0]["dg"].update(state="FAIL"), "UNVERIFIED_GATE"),
        (lambda d: d["route_permissions"][0]["customs"].update(state="UNKNOWN"), "UNVERIFIED_GATE"),
        (
            lambda d: d["route_permissions"][0]["load_control"].update(
                valid_until="2026-11-10T01:00:00Z"
            ),
            "EVIDENCE_NOT_VALID",
        ),
        (
            lambda d: d["cargo_units"][0].update(frozen_path_id="P-another-frozen-route"),
            "FROZEN_ASSIGNMENT_CHANGED",
        ),
        (
            lambda d: d["cargo_units"][0].update(contractual_latest_arrival="2026-11-10T01:00:00Z"),
            "CONTRACTUAL_DEADLINE_BREACH",
        ),
        (
            lambda d: d["cargo_units"][0].update(ready_at="2026-11-10T04:00:00Z"),
            "MISSED_HANDLING_OR_CUTOFF",
        ),
        (
            lambda d: d["provenance"].update(observed_at="2026-11-10T01:00:00Z"),
            "FUTURE_SOURCE_RECORD",
        ),
    ],
)
def test_mutated_source_cannot_be_authorized_by_old_solver_flags(mutate, expected):
    s, p = legal_plan()
    d = s.model_dump(mode="json")
    mutate(d)
    changed = ScenarioSnapshot.model_validate(d)
    # Even a compromised worker that rewrites the input hashes cannot hide the
    # physical violation. This specifically avoids relying only on hash mismatch.
    p = p.model_copy(
        update={
            "snapshot_hash": canonical_hash(changed),
            "policy_hash": canonical_hash(changed.policy),
        }
    )
    r, c = codes(changed, p)
    assert r.status == "FAIL" and expected in c


def test_wrong_arrival_delay_and_path_hash_rejected():
    s, p = legal_plan()
    bad = p.assignments[0].model_copy(
        update={"arrival_at": NOW, "delay_hours": Decimal("999"), "path_id": "forged-path"}
    )
    r, c = codes(s, p.model_copy(update={"assignments": [bad]}))
    assert r.status == "FAIL"
    assert {"ARRIVAL_MISMATCH", "DELAY_METRIC_MISMATCH", "PATH_ID_MISMATCH"} <= c


def test_expired_snapshot_rejected_at_actual_approval_time():
    s, p = legal_plan()
    r, c = codes(s, p, NOW + timedelta(hours=2))
    assert r.status == "FAIL" and "STALE_SNAPSHOT" in c


def test_constituent_piece_duplication_in_memory_is_reparsed():
    s = make_snapshot(size=2, as_of=NOW)
    s.cargo_units[1].pieces.append(s.cargo_units[0].pieces[0])
    _, p = legal_plan()
    assert "MALFORMED_CANONICAL_DATA" in codes(s, p)[1]


@given(st.integers(min_value=1, max_value=50))
@settings(max_examples=25, deadline=None)
def test_any_duplicate_count_fails_uniqueness(extra):
    s, p = legal_plan()
    bad = p.model_copy(update={"assignments": p.assignments * (extra + 1)})
    assert "ASSIGNMENT_CARDINALITY" in codes(s, bad)[1]
