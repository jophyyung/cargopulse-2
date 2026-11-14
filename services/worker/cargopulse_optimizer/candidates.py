"""Fail-closed synthetic whole-ULD path enumeration; no operational clearance."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import ROUND_CEILING, Decimal
from itertools import product

from cargopulse_contracts import (
    CandidatePath,
    CandidateSet,
    ExcludedArc,
    GateResult,
    PathLeg,
    QualityIssue,
    ScenarioSnapshot,
    UrgencyPoint,
    canonical_hash,
)

MICRO = Decimal("0.000001")
SCOPE = "SYNTHETIC_CONSERVATIVE_ENVELOPE; whole ULD; explicit per-leg handling; no clearance"


def hours(seconds: Decimal) -> Decimal:
    return (seconds / Decimal(3600)).quantize(MICRO, rounding=ROUND_CEILING)


def issue(code, entity, field, remediation):
    return QualityIssue(
        code=code,
        severity="BLOCKING",
        entity_type="snapshot",
        entity_id=entity,
        field=field,
        remediation=remediation,
        blocking=True,
    )


def decision(snapshot, at):
    at = at or snapshot.as_of
    if at.tzinfo is None or at.utcoffset() != timedelta(0):
        raise ValueError("Decision time must be timezone-aware UTC")
    return at.astimezone(timezone.utc)


def validate_snapshot(
    snapshot: ScenarioSnapshot, decision_time: datetime | None = None
) -> list[QualityIssue]:
    at = decision(snapshot, decision_time)
    p = snapshot.provenance
    issues = []
    if not snapshot.as_of <= at < snapshot.valid_until:
        issues.append(issue("SNAPSHOT_STALE", snapshot.event_id, "valid_until", "Refresh snapshot"))
    if (
        max(p.observed_at, p.effective_at, p.ingested_at) > snapshot.as_of
        or snapshot.policy.published_at > snapshot.as_of
    ):
        issues.append(
            issue("FUTURE_SOURCE", snapshot.event_id, "provenance", "Exclude future evidence")
        )
    if (at - p.observed_at).total_seconds() > snapshot.policy.source_max_age_seconds:
        issues.append(
            issue("SOURCE_STALE", snapshot.event_id, "provenance", "Refresh source records")
        )
    for f in snapshot.flights:
        if f.free_mass_kg is None or f.free_volume_m3 is None:
            issues.append(
                issue("MISSING_PAYLOAD", f.id, "capacity", "Supply verified physical capacity")
            )
        for pos in f.positions:
            if any(v is None for v in (pos.free_mass_kg, pos.free_volume_m3, pos.slot_count)):
                issues.append(
                    issue("MISSING_POSITION_CAPACITY", f.id, pos.id, "Supply position limits")
                )
    return issues


def path_id(uid, legs):
    return (
        "P-"
        + canonical_hash(
            {"cargo_unit_id": uid, "legs": [leg.model_dump(mode="json") for leg in legs]}
        )[:24]
    )


def build_feasible_paths(
    snapshot: ScenarioSnapshot, decision_time: datetime | None = None
) -> CandidateSet:
    return _build_feasible_paths(snapshot, decision_time, prune=True)


def _build_feasible_paths(snapshot, decision_time=None, *, prune, evidence_time=None):
    at = decision(snapshot, decision_time)
    # Evidence freshness is judged at `ev`; route timing (ready/cutoff) always at `at`.
    # Only the urgency what-if passes evidence_time; plans and approvals never do.
    ev = decision(snapshot, evidence_time) if evidence_time else at
    quality = validate_snapshot(snapshot, ev)
    excluded = []
    paths = []
    pruned = 0
    age = snapshot.policy.source_max_age_seconds
    dur = timedelta(seconds=snapshot.policy.handling_seconds)

    def valid(proof, at, until, max_age):
        # A later query cannot add evidence to an immutable historical snapshot.
        return (
            proof.state == GateResult.PASS
            and proof.observed_at <= snapshot.as_of
            and proof.observed_at <= at < proof.valid_until
            and until < proof.valid_until
            and (at - proof.observed_at).total_seconds() <= max_age
        )
    permissions = {(p.cargo_unit_id, p.flight_id): p for p in snapshot.route_permissions}
    conns = {(c.inbound_flight_id, c.outbound_flight_id): c for c in snapshot.connections}
    outgoing = defaultdict(list)
    windows = defaultdict(list)
    for f in sorted(snapshot.flights, key=lambda f: (f.departure_at, f.id)):
        outgoing[f.origin].append(f)
    for w in sorted(snapshot.handling_windows, key=lambda w: (w.start_at, w.id)):
        windows[w.airport].append(w)

    def reject(u, f, gate, code):
        excluded.append(
            ExcludedArc(
                cargo_unit_id=u.id, flight_id=f.id if f else None, gate=gate, reason_codes=[code]
            )
        )

    global_block = any(
        q.code in {"SNAPSHOT_STALE", "SOURCE_STALE", "FUTURE_SOURCE"} for q in quality
    )
    for u in snapshot.cargo_units:
        if global_block:
            reject(u, None, "E", "SNAPSHOT_NOT_CURRENT")
            continue
        unit_paths = []
        enumerated = 0

        def walk(station, available, legs, visited, inbound=None):
            nonlocal enumerated
            if len(legs) >= snapshot.policy.max_legs:
                return
            for f in outgoing[station]:
                if f.id in visited or f.destination == u.origin:
                    continue
                perm = permissions.get((u.id, f.id))
                if not perm or not valid(perm.dg, ev, f.arrival_at, age):
                    reject(u, f, "A", "DG_PERMISSION_NOT_VERIFIED")
                    continue
                if u.dg_class == "FREIGHTER_ONLY" and not f.is_freighter:
                    reject(u, f, "A", "DG_AIRCRAFT_INCOMPATIBLE")
                    continue
                if not valid(u.security, ev, f.arrival_at, age):
                    reject(u, f, "A", "SECURITY_NOT_VERIFIED")
                    continue
                if not valid(u.serviceability, ev, f.arrival_at, age):
                    reject(u, f, "B", "ULD_SERVICEABILITY_NOT_VERIFIED")
                    continue
                if not valid(perm.load_control, ev, f.arrival_at, age):
                    reject(u, f, "B", "LOAD_CONTROL_NOT_VERIFIED")
                    continue
                if f.status != "SCHEDULED" or not valid(
                    f.capacity_verification, ev, f.arrival_at, age
                ):
                    reject(u, f, "C", "FLIGHT_CAPACITY_NOT_VERIFIED")
                    continue
                if (
                    f.free_mass_kg is None
                    or f.free_volume_m3 is None
                    or u.actual_mass_kg > f.free_mass_kg
                    or u.actual_volume_m3 > f.free_volume_m3
                ):
                    reject(u, f, "C", "FLIGHT_CAPACITY_INSUFFICIENT_OR_UNKNOWN")
                    continue
                if not valid(perm.customs, ev, f.arrival_at, age):
                    reject(u, f, "D", "CUSTOMS_NOT_VERIFIED")
                    continue
                # Even non-cold cargo needs an explicit applicability/permission assertion.
                if not valid(perm.cold_chain, ev, f.arrival_at, age):
                    reject(u, f, "F", "COLD_CHAIN_NOT_VERIFIED")
                    continue
                ready = max(available, at)
                if inbound:
                    c = conns.get((inbound.id, f.id))
                    if not c or not valid(c.verification, ev, f.departure_at, age):
                        reject(u, f, "E", "CONNECTION_NOT_VERIFIED")
                        continue
                    ready = max(
                        ready, inbound.arrival_at + timedelta(seconds=c.min_transfer_seconds)
                    )
                if ready + dur > f.cutoff_at:
                    reject(u, f, "E", "CUTOFF_OR_MIN_TRANSFER_MISSED")
                    continue
                positions = []
                for p in f.positions:
                    if (
                        u.uld_type not in p.allowed_uld_types
                        or u.contour not in p.allowed_contours
                        or not valid(p.envelope_verification, ev, f.arrival_at, age)
                        or u.actual_mass_kg > p.max_unit_mass_kg
                        or u.actual_volume_m3 > p.max_unit_volume_m3
                    ):
                        reject(u, f, "B", "ULD_POSITION_ENVELOPE_INCOMPATIBLE")
                        continue
                    if (
                        p.free_mass_kg is None
                        or p.free_volume_m3 is None
                        or p.slot_count is None
                        or p.slot_count < 1
                        or u.actual_mass_kg > p.free_mass_kg
                        or u.actual_volume_m3 > p.free_volume_m3
                    ):
                        reject(u, f, "C", "POSITION_CAPACITY_INSUFFICIENT_OR_UNKNOWN")
                        continue
                    positions.append(p)
                handling = [
                    w
                    for w in windows[f.origin]
                    if w.capacity_units > 0
                    and max(ready, w.start_at) + dur <= min(w.end_at, f.cutoff_at)
                    and valid(w.equipment_verification, ev, max(ready, w.start_at) + dur, age)
                ]
                if not handling:
                    reject(u, f, "G", "HANDLING_WINDOW_NOT_VERIFIED_OR_UNAVAILABLE")
                for p, w in product(positions, handling):
                    enumerated += 1
                    if enumerated > 20000:
                        raise ValueError("CANDIDATE_ENUMERATION_LIMIT: reduce network density")
                    new = legs + [
                        PathLeg(flight_id=f.id, position_id=p.id, handling_window_id=w.id)
                    ]
                    if f.destination == u.destination:
                        pid = path_id(u.id, new)
                        if u.frozen_path_id and u.frozen_path_id != pid:
                            reject(u, f, "H", "FROZEN_PATH_REQUIRED")
                            continue
                        if (
                            u.contractual_latest_arrival
                            and f.arrival_at > u.contractual_latest_arrival
                        ):
                            reject(u, f, "H", "CONTRACTUAL_ARRIVAL_EXCEEDED")
                            continue
                        delay = hours(
                            max(
                                Decimal(0),
                                Decimal(str((f.arrival_at - u.commitment_at).total_seconds())),
                            )
                        )
                        weighted = (delay * u.service_weight).quantize(
                            MICRO, rounding=ROUND_CEILING
                        )
                        unit_paths.append(
                            CandidatePath(
                                id=pid,
                                cargo_unit_id=u.id,
                                legs=new,
                                arrival_at=f.arrival_at,
                                cutoff_at=min(
                                    next(
                                        x.cutoff_at
                                        for x in snapshot.flights
                                        if x.id == new[0].flight_id
                                    ),
                                    next(
                                        x.end_at
                                        for x in snapshot.handling_windows
                                        if x.id == new[0].handling_window_id
                                    ),
                                )
                                - dur,
                                delay_hours=delay,
                                weighted_delay_hours=weighted,
                                handling_cost=snapshot.policy.handling_penalty_weighted_hours
                                * len(new),
                                stability_cost=(
                                    snapshot.policy.stability_penalty_weighted_hours
                                    if u.previous_path_id and u.previous_path_id != pid
                                    else Decimal(0)
                                ),
                                reason_codes=[
                                    "GATES_A_TO_H_VERIFIED",
                                    "WHOLE_ULD_ATOMIC",
                                    "EXPLICIT_HANDLING_EVERY_LEG",
                                ],
                            )
                        )
                    else:
                        walk(f.destination, f.arrival_at, new, visited | {f.id}, f)

        walk(u.origin, u.ready_at, [], set())
        unit_paths.sort(
            key=lambda p: (p.weighted_delay_hours + p.handling_cost + p.stability_cost, p.id)
        )
        cap = snapshot.policy.max_paths_per_unit
        if prune and len(unit_paths) > cap:
            # Retain a latest-decision route as well as the best objective choices.
            latest = max(unit_paths, key=lambda p: (p.cutoff_at, p.id))
            kept = unit_paths[:cap]
            if latest not in kept:
                kept[-1] = latest
            pruned += len(unit_paths) - len(kept)
            unit_paths = kept
        paths.extend(unit_paths)
        if not unit_paths:
            quality.append(
                issue("NO_VALID_ROUTE", u.id, "paths", "Escalate; restore verified route evidence")
            )
    if pruned:
        quality.append(
            QualityIssue(
                code="PATHS_PRUNED",
                severity="REVIEW_REQUIRED",
                entity_type="snapshot",
                entity_id=snapshot.event_id,
                field="paths",
                remediation="Optimality applies to retained paths only",
                blocking=False,
            )
        )
    return CandidateSet(
        snapshot_hash=canonical_hash(snapshot),
        policy_hash=canonical_hash(snapshot.policy),
        paths=paths,
        excluded=excluded,
        quality_issues=quality,
        pruned_path_count=pruned,
        model_scope=SCOPE,
    )


def build_time_expanded_graph(snapshot, decision_time=None):
    """Return explicit feasible path arcs with station/time-labelled vertices."""
    candidates = build_feasible_paths(snapshot, decision_time)
    flights = {f.id: f for f in snapshot.flights}
    return {
        "candidates": candidates,
        "arcs": [
            {
                "path_id": p.id,
                "from": (flights[leg.flight_id].origin, flights[leg.flight_id].departure_at),
                "to": (flights[leg.flight_id].destination, flights[leg.flight_id].arrival_at),
                "leg": leg,
            }
            for p in candidates.paths
            for leg in p.legs
        ],
    }


def compute_urgency_delta(
    snapshot: ScenarioSnapshot, decision_times: list[datetime], *, hold_evidence: bool = False
) -> list[UrgencyPoint]:
    """Weighted-delay increase if the decision waits until each time.

    hold_evidence=True is a what-if for visualising route cliffs: evidence is judged as of
    the snapshot, so only cutoffs/connections close options. It never feeds a plan.
    """
    evidence = snapshot.as_of if hold_evidence else None
    base = _build_feasible_paths(snapshot, prune=False, evidence_time=evidence)
    initial = {}
    for p in base.paths:
        initial[p.cargo_unit_id] = min(
            initial.get(p.cargo_unit_id, p.weighted_delay_hours), p.weighted_delay_hours
        )
    points = []
    for at in decision_times:
        at = decision(snapshot, at)
        if at < snapshot.as_of:
            raise ValueError("Urgency replay cannot precede snapshot availability")
        current = _build_feasible_paths(snapshot, at, prune=False, evidence_time=evidence)
        for u in snapshot.cargo_units:
            options = [p for p in current.paths if p.cargo_unit_id == u.id]
            reference = [p for p in base.paths if p.cargo_unit_id == u.id]
            value = min((p.weighted_delay_hours for p in options), default=None)
            points.append(
                UrgencyPoint(
                    cargo_unit_id=u.id,
                    decision_at=at,
                    delta_weighted_hours=max(Decimal(0), value - initial[u.id])
                    if value is not None and u.id in initial
                    else None,
                    status="COMPLIANT_PATH" if options else "NO_COMPLIANT_PATH",
                    last_cutoff_at=max((p.cutoff_at for p in reference), default=None),
                )
            )
    return points
