"""Recompute hard feasibility from canonical source, without solver constraints.

The same mathematical specification is implemented through a direct traversal,
Decimal resource ledgers and source-evidence checks. Candidate PASS flags, path
costs, solver variables and an embedded validation result are never trusted.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, Decimal

from cargopulse_contracts import (
    ScenarioSnapshot,
    SolutionPlan,
    ValidationResult,
    Verification,
    Violation,
    canonical_hash,
)
from pydantic import ValidationError

from .metrics import validate_metrics

QUANTUM = Decimal("0.000001")


def validate_solution_independently(
    snapshot: ScenarioSnapshot,
    plan: SolutionPlan,
    decision_time: datetime | None = None,
) -> ValidationResult:
    """Check every physical assignment and obligation; fail closed on bad source.

    Pure offline solving defaults to the snapshot's decision time. Runtime approval
    must pass the actual current UTC time to reject expired or no-longer-actionable
    proposals. Six-place hour fields use explicit upward rounding to avoid
    understating lateness; mass and volume comparisons are exact Decimal sums.
    """
    errors: list[Violation] = []
    snapshot_hash = canonical_hash(snapshot)
    policy_hash = canonical_hash(snapshot.policy)

    def fail(gate: str, code: str, entity: str, detail: str):
        errors.append(Violation(gate=gate, code=code, entity_id=entity, detail=detail))

    def result():
        return ValidationResult(
            status="FAIL" if errors else "PASS",
            checked_gates=list("ABCDEFGH") + ["CONTRACT"],
            violations=errors,
            snapshot_hash=snapshot_hash,
            policy_hash=policy_hash,
        )

    # Frozen BaseModel objects still contain mutable nested lists. Reparse to
    # catch accidental/malicious in-memory changes and re-run graph invariants.
    try:
        source = ScenarioSnapshot.model_validate_json(snapshot.model_dump_json())
        proposal = SolutionPlan.model_validate_json(plan.model_dump_json())
    except (ValidationError, ValueError, TypeError):
        fail(
            "CONTRACT",
            "MALFORMED_CANONICAL_DATA",
            "snapshot",
            "Canonical schema or graph invariant failed",
        )
        return result()

    now = decision_time or source.as_of
    if now.tzinfo is None or now.utcoffset() is None or now.utcoffset().total_seconds() != 0:
        fail(
            "CONTRACT", "INVALID_DECISION_TIME", source.event_id, "UTC decision timestamp required"
        )
        return result()
    if proposal.snapshot_hash != snapshot_hash or proposal.policy_hash != policy_hash:
        fail(
            "CONTRACT",
            "INPUT_HASH_MISMATCH",
            source.event_id,
            "Plan references different immutable inputs",
        )
    if now < source.as_of or now >= source.valid_until:
        fail(
            "CONTRACT",
            "STALE_SNAPSHOT",
            source.event_id,
            "Snapshot is not valid at this decision time",
        )
    provenance = source.provenance
    if (
        provenance.observed_at > source.as_of
        or provenance.effective_at > source.as_of
        or provenance.ingested_at > now
    ):
        fail(
            "CONTRACT",
            "FUTURE_SOURCE_RECORD",
            source.event_id,
            "Future observations are not available to this decision",
        )
    if (now - provenance.observed_at).total_seconds() > source.policy.source_max_age_seconds:
        fail("CONTRACT", "STALE_SOURCE", provenance.source_id, "Source freshness policy exceeded")
    if source.policy.published_at > source.as_of:
        fail("CONTRACT", "FUTURE_POLICY", source.policy.id, "Policy did not exist at snapshot time")

    def proof(p: Verification, gate: str, entity: str, usage_until: datetime):
        if p.state != "PASS":
            fail(
                gate, "UNVERIFIED_GATE", entity, f"Evidence is {p.state}; explicit PASS is required"
            )
        if (
            p.observed_at > source.as_of
            or p.valid_until <= now
            or p.valid_until <= usage_until
            or (now - p.observed_at).total_seconds() > source.policy.source_max_age_seconds
        ):
            fail(
                gate,
                "EVIDENCE_NOT_VALID",
                entity,
                "Evidence is future-dated or expires before resource use",
            )

    units = {u.id: u for u in source.cargo_units}
    flights = {f.id: f for f in source.flights}
    windows = {w.id: w for w in source.handling_windows}
    permissions = {(p.cargo_unit_id, p.flight_id): p for p in source.route_permissions}
    connections = {(c.inbound_flight_id, c.outbound_flight_id): c for c in source.connections}
    assigned_count = Counter(a.cargo_unit_id for a in proposal.assignments)
    unassigned_count = Counter(u.cargo_unit_id for u in proposal.unassigned)
    flight_mass = defaultdict(Decimal)
    flight_volume = defaultdict(Decimal)
    position_mass = defaultdict(Decimal)
    position_volume = defaultdict(Decimal)
    position_slots = Counter()
    handling_usage = Counter()
    assigned_physical_pieces = set()

    for uid in assigned_count.keys() | unassigned_count.keys():
        if uid not in units:
            fail("H", "UNKNOWN_CARGO_UNIT", uid, "Solution refers to an unknown cargo unit")
    for uid, unit in units.items():
        if assigned_count[uid] + unassigned_count[uid] != 1:
            fail(
                "H",
                "ASSIGNMENT_CARDINALITY",
                uid,
                "Exactly one assignment or explicit escalation is required",
            )
        if unassigned_count[uid] and (unit.contractual_latest_arrival or unit.frozen_path_id):
            fail(
                "H",
                "UNSATISFIED_HARD_OBLIGATION",
                uid,
                "A hard obligation is uncovered; escalate for authority review",
            )

    for assignment in proposal.assignments:
        uid = assignment.cargo_unit_id
        unit = units.get(uid)
        if unit is None:
            continue
        expected_path_id = (
            "P-"
            + canonical_hash(
                {
                    "cargo_unit_id": uid,
                    "legs": [leg.model_dump(mode="json") for leg in assignment.legs],
                }
            )[:24]
        )
        if assignment.path_id != expected_path_id:
            fail(
                "CONTRACT",
                "PATH_ID_MISMATCH",
                uid,
                "Path identifier does not match its physical legs",
            )
        if unit.frozen_path_id and assignment.path_id != unit.frozen_path_id:
            fail(
                "H", "FROZEN_ASSIGNMENT_CHANGED", uid, "Frozen commitment cannot be silently moved"
            )
        expected_changed = bool(
            unit.previous_path_id and unit.previous_path_id != assignment.path_id
        )
        if assignment.changed_from_previous != expected_changed:
            fail(
                "CONTRACT",
                "CHURN_FLAG_MISMATCH",
                uid,
                "Changed-assignment flag does not match prior path",
            )
        if len(assignment.legs) > source.policy.max_legs:
            fail("E", "PATH_LEG_LIMIT", uid, "Path exceeds the published leg count")
        for piece in unit.pieces:
            if piece.piece_id in assigned_physical_pieces:
                fail(
                    "H", "DUPLICATE_PHYSICAL_PIECE", piece.piece_id, "Physical piece assigned twice"
                )
            assigned_physical_pieces.add(piece.piece_id)

        location = unit.origin
        available = max(unit.ready_at, now)
        previous = None
        visited = {location}
        used_flights = set()
        last_arrival = None
        for index, leg in enumerate(assignment.legs):
            flight = flights.get(leg.flight_id)
            window = windows.get(leg.handling_window_id)
            if flight is None or window is None:
                fail(
                    "E", "UNKNOWN_ROUTE_RESOURCE", uid, "Unknown flight or ground handling resource"
                )
                continue
            position = next((p for p in flight.positions if p.id == leg.position_id), None)
            if position is None:
                fail("B", "UNKNOWN_POSITION", uid, "Unknown hold/position envelope")
                continue
            if flight.id in used_flights or flight.destination in visited:
                fail("H", "CYCLIC_ROUTE", uid, "A physical route cannot reuse a flight or airport")
            used_flights.add(flight.id)
            visited.add(flight.destination)
            if location != flight.origin:
                fail(
                    "E",
                    "LOCATION_DISCONTINUITY",
                    uid,
                    "ULD is not located at the departure airport",
                )
            if window.airport != flight.origin:
                fail(
                    "G",
                    "WRONG_HANDLING_AIRPORT",
                    uid,
                    "Handling resource is at a different airport",
                )
            if flight.status != "SCHEDULED":
                fail(
                    "E",
                    "FLIGHT_NOT_AVAILABLE",
                    flight.id,
                    "Cancelled flight cannot carry a proposal",
                )

            if previous is not None:
                connection = connections.get((previous.id, flight.id))
                if connection is None:
                    fail(
                        "E",
                        "MISSING_CONNECTION",
                        uid,
                        "Each transfer requires an explicit approved connection",
                    )
                else:
                    proof(connection.verification, "E", uid, flight.departure_at)
                    available = previous.arrival_at + timedelta(
                        seconds=connection.min_transfer_seconds
                    )

            start = max(available, now, window.start_at)
            finish = start + timedelta(seconds=source.policy.handling_seconds)
            if finish > window.end_at or finish > flight.cutoff_at:
                fail(
                    "E",
                    "MISSED_HANDLING_OR_CUTOFF",
                    uid,
                    "Ready/transfer plus handling does not finish before closeout",
                )
            if flight.departure_at < finish:
                fail(
                    "E", "DEPARTURE_BEFORE_READY", uid, "Flight departs before handling completion"
                )
            proof(window.equipment_verification, "G", window.id, finish)
            proof(position.envelope_verification, "B", flight.id, flight.arrival_at)
            proof(flight.capacity_verification, "C", flight.id, flight.arrival_at)
            proof(unit.serviceability, "B", uid, flight.arrival_at)
            proof(unit.security, "A", uid, flight.arrival_at)
            clearance = permissions.get((uid, flight.id))
            if clearance is None:
                fail(
                    "A",
                    "ROUTE_PERMISSION_MISSING",
                    uid,
                    "No cargo-specific verified route permission",
                )
            else:
                proof(clearance.dg, "A", uid, flight.arrival_at)
                proof(clearance.customs, "D", uid, flight.arrival_at)
                proof(clearance.load_control, "B", uid, flight.arrival_at)
                # Non-cold cargo also needs an explicit modelled N/A PASS record.
                proof(clearance.cold_chain, "F", uid, flight.arrival_at)
            if unit.dg_class == "FREIGHTER_ONLY" and not flight.is_freighter:
                fail(
                    "A",
                    "DG_AIRCRAFT_INCOMPATIBLE",
                    uid,
                    "Freighter-only cargo proposed on passenger aircraft",
                )
            if (
                unit.uld_type not in position.allowed_uld_types
                or unit.contour not in position.allowed_contours
            ):
                fail(
                    "B",
                    "ULD_CONTOUR_INCOMPATIBLE",
                    uid,
                    "ULD type or contour is outside the approved envelope",
                )
            if unit.uld_type.upper() == "UNKNOWN" or unit.contour.upper() == "UNKNOWN":
                fail(
                    "B",
                    "ULD_CONTOUR_UNKNOWN",
                    uid,
                    "Unknown physical geometry is not verified compatibility",
                )
            if (
                unit.actual_mass_kg > position.max_unit_mass_kg
                or unit.actual_volume_m3 > position.max_unit_volume_m3
            ):
                fail("B", "UNIT_ENVELOPE_EXCEEDED", uid, "ULD exceeds the per-unit envelope")
            flight_mass[flight.id] += unit.actual_mass_kg
            flight_volume[flight.id] += unit.actual_volume_m3
            key = (flight.id, position.id)
            position_mass[key] += unit.actual_mass_kg
            position_volume[key] += unit.actual_volume_m3
            position_slots[key] += 1
            handling_usage[window.id] += 1
            location = flight.destination
            available = flight.arrival_at
            last_arrival = flight.arrival_at
            previous = flight

        if location != unit.destination:
            fail(
                "E",
                "DESTINATION_NOT_REACHED",
                uid,
                "Proposed path does not reach the cargo destination",
            )
        if last_arrival is not None:
            if assignment.arrival_at != last_arrival:
                fail(
                    "CONTRACT",
                    "ARRIVAL_MISMATCH",
                    uid,
                    "Plan arrival differs from the physical final leg",
                )
            if unit.contractual_latest_arrival and last_arrival > unit.contractual_latest_arrival:
                fail(
                    "H",
                    "CONTRACTUAL_DEADLINE_BREACH",
                    uid,
                    "Proposed arrival violates a hard service commitment",
                )
            late = max(last_arrival - unit.commitment_at, timedelta(0))
            seconds = Decimal(late.days * 86400 + late.seconds) + Decimal(
                late.microseconds
            ) / Decimal(1000000)
            delay = (seconds / Decimal(3600)).quantize(QUANTUM, rounding=ROUND_CEILING)
            weighted = (delay * unit.service_weight).quantize(QUANTUM, rounding=ROUND_CEILING)
            if assignment.delay_hours != delay or assignment.weighted_delay_hours != weighted:
                fail(
                    "CONTRACT",
                    "DELAY_METRIC_MISMATCH",
                    uid,
                    "Delay fields do not match independently recomputed UTC lateness",
                )

    for fid, mass in flight_mass.items():
        flight = flights[fid]
        if flight.free_mass_kg is None or mass > flight.free_mass_kg:
            fail("C", "FLIGHT_MASS_EXCEEDED", fid, "Missing or exceeded residual flight mass")
        if flight.free_volume_m3 is None or flight_volume[fid] > flight.free_volume_m3:
            fail("C", "FLIGHT_VOLUME_EXCEEDED", fid, "Missing or exceeded residual flight volume")
    for (fid, pid), mass in position_mass.items():
        pos = next(p for p in flights[fid].positions if p.id == pid)
        if pos.free_mass_kg is None or mass > pos.free_mass_kg:
            fail("C", "POSITION_MASS_EXCEEDED", f"{fid}:{pid}", "Missing or exceeded position mass")
        if pos.free_volume_m3 is None or position_volume[(fid, pid)] > pos.free_volume_m3:
            fail(
                "C",
                "POSITION_VOLUME_EXCEEDED",
                f"{fid}:{pid}",
                "Missing or exceeded position volume",
            )
        if pos.slot_count is None or position_slots[(fid, pid)] > pos.slot_count:
            fail(
                "B",
                "POSITION_SLOTS_EXCEEDED",
                f"{fid}:{pid}",
                "Missing or exceeded physical position slots",
            )
    for wid, count in handling_usage.items():
        if count > windows[wid].capacity_units:
            fail("G", "HANDLING_CAPACITY_EXCEEDED", wid, "Ground handling throughput exceeded")
    errors.extend(validate_metrics(source, proposal))
    return result()
