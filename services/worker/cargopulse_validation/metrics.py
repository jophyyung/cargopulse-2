"""Independent metric and lineage checks; no optimizer imports or candidate reuse."""

from collections import defaultdict
from datetime import timedelta
from decimal import ROUND_CEILING, Decimal

from cargopulse_contracts import Violation, canonical_hash

MICRO = Decimal("0.000001")


def eligible_units(snapshot):
    """Search for one compliant individual route per unit, independently.

    This uses a bounded depth-first physical traversal rather than the optimizer's
    ranked/pruned candidate list. Global competition is intentionally excluded
    from the *eligible ULD* denominator. An exhausted search fails verification.
    """
    at, policy = snapshot.as_of, snapshot.policy
    by_origin, by_airport = defaultdict(list), defaultdict(list)
    for flight in snapshot.flights:
        by_origin[flight.origin].append(flight)
    for window in snapshot.handling_windows:
        by_airport[window.airport].append(window)
    permissions = {(p.cargo_unit_id, p.flight_id): p for p in snapshot.route_permissions}
    connections = {(c.inbound_flight_id, c.outbound_flight_id): c for c in snapshot.connections}

    def verified(proof, until):
        return (
            proof.state == "PASS"
            and proof.observed_at <= at < proof.valid_until
            and until < proof.valid_until
            and (at - proof.observed_at).total_seconds() <= policy.source_max_age_seconds
        )

    eligible = set()
    for unit in snapshot.cargo_units:
        explored = 0

        def walk(airport, ready, previous, legs, visited):
            nonlocal explored
            if len(legs) >= policy.max_legs:
                return False
            for flight in by_origin[airport]:
                if flight.status != "SCHEDULED" or flight.destination in visited:
                    continue
                if unit.dg_class == "FREIGHTER_ONLY" and not flight.is_freighter:
                    continue
                if (
                    flight.free_mass_kg is None
                    or flight.free_volume_m3 is None
                    or flight.free_mass_kg < unit.actual_mass_kg
                    or flight.free_volume_m3 < unit.actual_volume_m3
                ):
                    continue
                permission = permissions.get((unit.id, flight.id))
                if permission is None or not all(
                    verified(p, flight.arrival_at)
                    for p in (
                        unit.serviceability,
                        unit.security,
                        flight.capacity_verification,
                        permission.dg,
                        permission.customs,
                        permission.cold_chain,
                        permission.load_control,
                    )
                ):
                    continue
                available = max(ready, at)
                if previous is not None:
                    connection = connections.get((previous.id, flight.id))
                    if connection is None or not verified(
                        connection.verification, flight.departure_at
                    ):
                        continue
                    available = previous.arrival_at + timedelta(
                        seconds=connection.min_transfer_seconds
                    )
                for position in flight.positions:
                    if (
                        unit.uld_type.upper() == "UNKNOWN"
                        or unit.contour.upper() == "UNKNOWN"
                        or unit.uld_type not in position.allowed_uld_types
                        or unit.contour not in position.allowed_contours
                        or unit.actual_mass_kg > position.max_unit_mass_kg
                        or unit.actual_volume_m3 > position.max_unit_volume_m3
                        or position.free_mass_kg is None
                        or position.free_volume_m3 is None
                        or position.slot_count is None
                        or position.slot_count < 1
                        or unit.actual_mass_kg > position.free_mass_kg
                        or unit.actual_volume_m3 > position.free_volume_m3
                        or not verified(position.envelope_verification, flight.arrival_at)
                    ):
                        continue
                    for window in by_airport[airport]:
                        explored += 1
                        if explored > 20000:
                            raise ValueError("INDEPENDENT_ELIGIBILITY_SEARCH_LIMIT")
                        finish = max(available, at, window.start_at) + timedelta(
                            seconds=policy.handling_seconds
                        )
                        if (
                            window.capacity_units < 1
                            or finish > window.end_at
                            or finish > flight.cutoff_at
                            or not verified(window.equipment_verification, finish)
                        ):
                            continue
                        path = legs + [
                            {
                                "flight_id": flight.id,
                                "position_id": position.id,
                                "handling_window_id": window.id,
                            }
                        ]
                        if flight.destination == unit.destination:
                            if (
                                unit.contractual_latest_arrival
                                and flight.arrival_at > unit.contractual_latest_arrival
                            ):
                                continue
                            path_id = (
                                "P-" + canonical_hash({"cargo_unit_id": unit.id, "legs": path})[:24]
                            )
                            if unit.frozen_path_id and unit.frozen_path_id != path_id:
                                continue
                            return True
                        if walk(
                            flight.destination,
                            flight.arrival_at,
                            flight,
                            path,
                            visited | {flight.destination},
                        ):
                            return True
            return False

        if walk(unit.origin, unit.ready_at, None, [], {unit.origin}):
            eligible.add(unit.id)
    return eligible


def validate_metrics(snapshot, plan):
    problems = []

    def fail(code, name, detail):
        problems.append(Violation(gate="CONTRACT", code=code, entity_id=name, detail=detail))

    try:
        eligible = eligible_units(snapshot)
    except ValueError:
        fail(
            "METRIC_ELIGIBILITY_UNVERIFIED",
            "metrics",
            "Independent denominator search exceeded its bound",
        )
        return problems
    units = {u.id: u for u in snapshot.cargo_units}
    flights = {f.id: f for f in snapshot.flights}
    horizon = snapshot.as_of + timedelta(hours=48)
    assigned = {a.cargo_unit_id: a for a in plan.assignments if a.cargo_unit_id in units}
    departures, weighted = 0, Decimal(0)
    for uid, assignment in assigned.items():
        first = flights.get(assignment.legs[0].flight_id)
        last = flights.get(assignment.legs[-1].flight_id)
        if first and first.departure_at <= horizon:
            departures += 1
        if last:
            late = max(last.arrival_at - units[uid].commitment_at, timedelta(0))
            seconds = Decimal(late.days * 86400 + late.seconds) + Decimal(
                late.microseconds
            ) / Decimal(1000000)
            delay = (seconds / Decimal(3600)).quantize(MICRO, rounding=ROUND_CEILING)
            weighted += (delay * units[uid].service_weight).quantize(MICRO, rounding=ROUND_CEILING)
    definitions = {
        "proposed_departure_48h_eligible_uld_rate": (
            Decimal(departures),
            Decimal(len(eligible)),
            "ratio",
            "proposed_first_departure_within_48h_not_approved_capacity",
        ),
        "proposed_departure_48h_all_affected_uld_rate": (
            Decimal(departures),
            Decimal(len(units)),
            "ratio",
            "proposed_first_departure_within_48h_not_approved_capacity",
        ),
        "weighted_delay_hours": (
            weighted,
            Decimal(1),
            "weighted_hours",
            "proposed_assigned_cargo_weighted_hours",
        ),
        "unassigned_uld_count": (
            Decimal(len(units) - len(assigned)),
            Decimal(1),
            "ULD",
            "explicit_escalated_whole_uld_count",
        ),
    }
    seen = set()
    for metric in plan.metrics:
        name = metric.name
        if name in seen:
            fail("DUPLICATE_METRIC", name, "Each defined metric must occur once")
        seen.add(name)
        if name not in definitions:
            fail(
                "UNKNOWN_COMPUTED_METRIC",
                name,
                "No independently verified metric definition exists",
            )
            continue
        num, den, unit, statistic = definitions[name]
        expected = (num / den).quantize(MICRO) if den else None
        if (
            metric.numerator != num
            or metric.denominator != den
            or metric.value != expected
            or metric.unit != unit
            or metric.statistic != statistic
            or metric.status != ("COMPUTED" if den else "UNDEFINED")
        ):
            fail(
                "METRIC_VALUE_MISMATCH",
                name,
                "Independent counts, units, scope or formula do not match",
            )
        if (
            metric.snapshot_hash != canonical_hash(snapshot)
            or metric.policy_hash != canonical_hash(snapshot.policy)
            or metric.cohort_id != snapshot.event_id
            or metric.data_source_ids != [snapshot.provenance.source_id]
            or metric.window_start_utc != snapshot.as_of
            or metric.window_end_utc != horizon
            or metric.event_as_of_utc != snapshot.as_of
            or metric.baseline_policy_version
            != f"{plan.solver.engine}-v1; matched candidates and resources"
        ):
            fail(
                "METRIC_LINEAGE_MISMATCH",
                name,
                "Metric lineage does not match immutable plan inputs",
            )
    for name in definitions.keys() - seen:
        fail(
            "MISSING_REQUIRED_METRIC",
            name,
            "Required evidence is absent; no validated export is possible",
        )
    return problems
