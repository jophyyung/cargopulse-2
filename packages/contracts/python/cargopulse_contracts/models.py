"""Versioned, fail-closed CargoPulse L1 contracts.

All measurements cross the wire as decimal strings. Every PASS is evidence-bound;
it is a synthetic model assertion, never an aviation compliance certification.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, DecimalException
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, Decimal)):
        raise ValueError("Measurements must be finite decimal strings, never binary floats")
    try:
        d = Decimal(value)
    except DecimalException:
        # Pydantic translates ValueError into a normal request validation error;
        # a raw decimal exception would escape the HTTP validation boundary.
        raise ValueError("Measurements must be valid finite decimal strings") from None
    if not d.is_finite() or d.as_tuple().exponent < -6:
        raise ValueError("Finite decimals with at most six decimal places are required")
    return d


Number = Annotated[Decimal, BeforeValidator(_decimal, json_schema_input_type=str)]
Nonnegative = Annotated[Number, Field(ge=0, le=Decimal("1000000000"))]
Positive = Annotated[Number, Field(gt=0, le=Decimal("1000000000"))]
Identifier = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Airport = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    @field_validator("*", mode="after")
    @classmethod
    def utc_only(cls, value: object) -> object:
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Timestamp must include an explicit UTC offset")
            if value.utcoffset().total_seconds() != 0:
                raise ValueError("Canonical timestamps must be UTC (Z or +00:00)")
            return value.astimezone(timezone.utc)
        return value


class EvidenceTier(StrEnum):
    PUBLIC_VERIFIED = "PUBLIC_VERIFIED"
    ORGANISER_SNAPSHOT = "ORGANISER_SNAPSHOT"
    TEAM_SYNTHETIC_UNVERIFIED = "TEAM_SYNTHETIC_UNVERIFIED"
    LIVE_AUTHORISED = "LIVE_AUTHORISED"


class GateResult(StrEnum):
    PASS = "PASS"  # noqa: S105 - safety-gate outcome, not a credential.
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class Role(StrEnum):
    CONTROLLER = "controller"
    LOAD_ANALYST = "load_analyst"
    MANAGER = "manager"
    DATA_STEWARD = "data_steward"
    AUDITOR = "auditor"
    TENANT_ADMIN = "tenant_admin"
    INTEGRATION_SERVICE = "integration_service"


class ScenarioState(StrEnum):
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"
    READY = "READY"
    SOLVING = "SOLVING"
    PLAN_READY = "PLAN_READY"
    NO_FEASIBLE_PLAN = "NO_FEASIBLE_PLAN"
    SOLVER_ERROR = "SOLVER_ERROR"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"
    STALE = "STALE"
    CLOSED = "CLOSED"


class SolverStatus(StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    TIME_LIMIT_WITH_FEASIBLE = "TIME_LIMIT_WITH_FEASIBLE"
    TIME_LIMIT_NO_FEASIBLE = "TIME_LIMIT_NO_FEASIBLE"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class Provenance(Contract):
    source_id: Identifier
    source_record_ids: list[Identifier] = Field(min_length=1, max_length=20000)
    observed_at: datetime
    effective_at: datetime
    ingested_at: datetime
    schema_version: Literal["1.0.0"] = "1.0.0"
    evidence_tier: EvidenceTier


class Verification(Contract):
    state: GateResult
    source_record_id: Identifier
    observed_at: datetime
    valid_until: datetime
    rule_revision: Identifier

    @model_validator(mode="after")
    def valid_interval(self) -> Verification:
        if self.valid_until <= self.observed_at:
            raise ValueError("Verification expiry must follow observation")
        return self


class PieceAssociation(Contract):
    piece_id: Identifier
    awb_id: Identifier
    mass_kg: Nonnegative
    volume_m3: Nonnegative


class CargoUnit(Contract):
    id: Identifier
    uld_code: Identifier
    uld_type: Identifier
    contour: Identifier
    origin: Airport
    destination: Airport
    actual_mass_kg: Positive
    actual_volume_m3: Positive
    tare_mass_kg: Nonnegative
    pieces: list[PieceAssociation] = Field(min_length=1, max_length=1000)
    service_class: Literal["GENERAL", "PRIORITY", "PHARMA", "PERISHABLE", "DG"]
    service_weight: Positive
    ready_at: datetime
    commitment_at: datetime
    requires_cold_chain: bool
    dg_class: Literal["NONE", "DECLARED", "FREIGHTER_ONLY"]
    serviceability: Verification
    security: Verification
    contractual_latest_arrival: datetime | None = None
    previous_path_id: Identifier | None = None
    frozen_path_id: Identifier | None = None
    atomic_whole_uld: Literal[True] = True

    @model_validator(mode="after")
    def physical_mapping(self) -> CargoUnit:
        if self.origin == self.destination:
            raise ValueError("Origin and destination must differ")
        if sum((p.mass_kg for p in self.pieces), self.tare_mass_kg) != self.actual_mass_kg:
            raise ValueError("Piece mass plus ULD tare must equal physical manifest mass")
        if sum((p.volume_m3 for p in self.pieces), Decimal(0)) != self.actual_volume_m3:
            raise ValueError("Piece volume must equal declared physical volume")
        if len({p.piece_id for p in self.pieces}) != len(self.pieces):
            raise ValueError("Duplicate physical piece in ULD")
        return self


class FlightPosition(Contract):
    id: Identifier
    free_mass_kg: Nonnegative | None
    free_volume_m3: Nonnegative | None
    slot_count: int | None = Field(ge=0, le=5000)
    max_unit_mass_kg: Positive
    max_unit_volume_m3: Positive
    allowed_uld_types: list[Identifier] = Field(min_length=1, max_length=30)
    allowed_contours: list[Identifier] = Field(min_length=1, max_length=30)
    envelope_verification: Verification


class FlightCapacity(Contract):
    id: Identifier
    flight_number: Identifier
    origin: Airport
    destination: Airport
    departure_at: datetime
    arrival_at: datetime
    cutoff_at: datetime
    origin_timezone: str = Field(max_length=80)
    destination_timezone: str = Field(max_length=80)
    aircraft_variant: Identifier
    is_freighter: bool
    status: Literal["SCHEDULED", "CANCELLED"]
    free_mass_kg: Nonnegative | None
    free_volume_m3: Nonnegative | None
    positions: list[FlightPosition] = Field(min_length=1, max_length=100)
    capacity_verification: Verification

    @model_validator(mode="after")
    def chronology(self) -> FlightCapacity:
        if not self.cutoff_at <= self.departure_at < self.arrival_at:
            raise ValueError("Flight requires cutoff <= departure < arrival")
        if self.origin == self.destination:
            raise ValueError("Flight leg must connect different airports")
        for zone in (self.origin_timezone, self.destination_timezone):
            try:
                ZoneInfo(zone)
            except (KeyError, ValueError) as exc:
                raise ValueError("Use a valid IANA airport timezone") from exc
        if len({p.id for p in self.positions}) != len(self.positions):
            raise ValueError("Duplicate position identifier")
        return self


class HandlingWindow(Contract):
    id: Identifier
    airport: Airport
    start_at: datetime
    end_at: datetime
    capacity_units: int = Field(ge=0, le=10000)
    equipment_verification: Verification

    @model_validator(mode="after")
    def chronology(self) -> HandlingWindow:
        if self.end_at <= self.start_at:
            raise ValueError("Handling window requires start < end")
        return self


class RoutePermission(Contract):
    cargo_unit_id: Identifier
    flight_id: Identifier
    dg: Verification
    customs: Verification
    cold_chain: Verification
    load_control: Verification


class Connection(Contract):
    inbound_flight_id: Identifier
    outbound_flight_id: Identifier
    min_transfer_seconds: int = Field(ge=0, le=86400)
    verification: Verification


class RuleSet(Contract):
    id: Identifier
    version: Identifier
    state: Literal["PUBLISHED"]
    authored_by: Identifier
    approved_by: Identifier
    published_at: datetime
    handling_seconds: int = Field(ge=1, le=86400)
    max_legs: int = Field(ge=1, le=3)
    max_paths_per_unit: int = Field(ge=1, le=100)
    unassigned_penalty_weighted_hours: Positive
    handling_penalty_weighted_hours: Nonnegative
    stability_penalty_weighted_hours: Nonnegative
    source_max_age_seconds: int = Field(ge=1, le=604800)
    model_scope: Literal["SYNTHETIC_CONSERVATIVE_ENVELOPE"]

    @model_validator(mode="after")
    def four_eyes(self) -> RuleSet:
        if self.authored_by == self.approved_by:
            raise ValueError("Published policy requires a different reviewer")
        return self


class ScenarioSnapshot(Contract):
    schema_version: Literal["1.0.0"] = "1.0.0"
    tenant_id: UUID
    event_id: Identifier
    source_version: int = Field(ge=1, le=1000000)
    title: str = Field(min_length=1, max_length=200)
    kind: Literal["RECOVER"] = "RECOVER"
    as_of: datetime
    valid_until: datetime
    synthetic: Literal[True] = True
    evidence_tier: Literal["TEAM_SYNTHETIC_UNVERIFIED"] = "TEAM_SYNTHETIC_UNVERIFIED"
    provenance: Provenance
    policy: RuleSet
    cargo_units: list[CargoUnit] = Field(min_length=1, max_length=1200)
    flights: list[FlightCapacity] = Field(max_length=300)
    handling_windows: list[HandlingWindow] = Field(max_length=1000)
    route_permissions: list[RoutePermission] = Field(max_length=50000)
    connections: list[Connection] = Field(max_length=10000)

    @model_validator(mode="after")
    def references(self) -> ScenarioSnapshot:
        if self.valid_until <= self.as_of:
            raise ValueError("Snapshot validity must extend past decision time")
        if self.provenance.evidence_tier != EvidenceTier.TEAM_SYNTHETIC_UNVERIFIED:
            raise ValueError("L1 only accepts explicitly synthetic provenance")
        for records in (self.cargo_units, self.flights, self.handling_windows):
            if len({r.id for r in records}) != len(records):
                raise ValueError("Duplicate canonical entity identifier")
        piece_ids = [p.piece_id for u in self.cargo_units for p in u.pieces]
        if len(set(piece_ids)) != len(piece_ids):
            raise ValueError("A physical piece cannot occur in more than one ULD")
        ulds = [u.uld_code for u in self.cargo_units]
        if len(set(ulds)) != len(ulds):
            raise ValueError("Duplicate physical ULD")
        units = {u.id for u in self.cargo_units}
        flights = {f.id for f in self.flights}
        pairs = [(p.cargo_unit_id, p.flight_id) for p in self.route_permissions]
        if len(set(pairs)) != len(pairs):
            raise ValueError("Conflicting duplicate route permission")
        if any(u not in units or f not in flights for u, f in pairs):
            raise ValueError("Route permission references unknown entity")
        conns = [(c.inbound_flight_id, c.outbound_flight_id) for c in self.connections]
        if len(set(conns)) != len(conns) or any(
            a not in flights or b not in flights for a, b in conns
        ):
            raise ValueError("Duplicate or unknown connection reference")
        return self


class QualityIssue(Contract):
    code: Identifier
    severity: Literal["BLOCKING", "REVIEW_REQUIRED", "INFORMATIONAL"]
    entity_type: Identifier
    entity_id: str
    field: str
    remediation: str
    blocking: bool


class PathLeg(Contract):
    flight_id: Identifier
    position_id: Identifier
    handling_window_id: Identifier


class CandidatePath(Contract):
    id: Identifier
    cargo_unit_id: Identifier
    legs: list[PathLeg] = Field(min_length=1, max_length=3)
    arrival_at: datetime
    cutoff_at: datetime
    delay_hours: Nonnegative
    weighted_delay_hours: Nonnegative
    handling_cost: Nonnegative
    stability_cost: Nonnegative
    reason_codes: list[Identifier] = Field(min_length=1)


class ExcludedArc(Contract):
    cargo_unit_id: Identifier
    flight_id: Identifier | None
    gate: Literal["A", "B", "C", "D", "E", "F", "G", "H"]
    reason_codes: list[Identifier] = Field(min_length=1)


class CandidateSet(Contract):
    snapshot_hash: Digest
    policy_hash: Digest
    paths: list[CandidatePath]
    excluded: list[ExcludedArc]
    quality_issues: list[QualityIssue]
    pruned_path_count: int = Field(ge=0)
    model_scope: str


class Assignment(Contract):
    cargo_unit_id: Identifier
    path_id: Identifier
    legs: list[PathLeg] = Field(min_length=1, max_length=3)
    arrival_at: datetime
    delay_hours: Nonnegative
    weighted_delay_hours: Nonnegative
    changed_from_previous: bool
    reason_codes: list[Identifier] = Field(min_length=1)


class Unassigned(Contract):
    cargo_unit_id: Identifier
    reason_codes: list[Identifier] = Field(min_length=1)
    action: Literal["ESCALATE"] = "ESCALATE"


class Violation(Contract):
    gate: Literal["A", "B", "C", "D", "E", "F", "G", "H", "CONTRACT"]
    code: Identifier
    entity_id: str
    detail: str


class ValidationResult(Contract):
    status: Literal["PASS", "FAIL"]
    version: Literal["independent-v1"] = "independent-v1"
    checked_gates: list[str]
    violations: list[Violation]
    snapshot_hash: Digest
    policy_hash: Digest


class SolverTelemetry(Contract):
    engine: Literal["HiGHS", "EARLIEST_FEASIBLE", "PRIORITY_FIRST"]
    version: str
    status: SolverStatus
    wall_time_ms: Nonnegative
    time_limit_seconds: int = Field(ge=1, le=60)
    objective_value: Number | None
    best_bound: Number | None
    optimality_gap: Nonnegative | None
    variable_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    termination_reason: str


class MetricValue(Contract):
    name: Identifier
    value: Number | None
    unit: str
    numerator: Number | None
    denominator: Number | None
    cohort_id: str
    window_start_utc: datetime
    window_end_utc: datetime
    event_as_of_utc: datetime
    scenario_type: Literal["RECOVER"] = "RECOVER"
    metric_method_version: Literal["metrics-v1"] = "metrics-v1"
    evidence_tier: Literal["TEAM_SYNTHETIC_UNVERIFIED"] = "TEAM_SYNTHETIC_UNVERIFIED"
    data_source_ids: list[str]
    snapshot_hash: Digest
    policy_hash: Digest
    baseline_policy_version: str
    statistic: str
    status: Literal["COMPUTED", "PROPOSED", "UNDEFINED"]


class SolutionPlan(Contract):
    schema_version: Literal["1.0.0"] = "1.0.0"
    snapshot_hash: Digest
    policy_hash: Digest
    synthetic: Literal[True] = True
    evidence_tier: Literal["TEAM_SYNTHETIC_UNVERIFIED"] = "TEAM_SYNTHETIC_UNVERIFIED"
    solver: SolverTelemetry
    assignments: list[Assignment]
    unassigned: list[Unassigned]
    independent_validation: ValidationResult
    metrics: list[MetricValue]
    model_scope: str
    has_external_write_permission: Literal[False] = False


class UrgencyPoint(Contract):
    cargo_unit_id: Identifier
    decision_at: datetime
    delta_weighted_hours: Nonnegative | None
    status: Literal["COMPLIANT_PATH", "NO_COMPLIANT_PATH"]
    last_cutoff_at: datetime | None


class Principal(Contract):
    subject: str
    tenant_id: UUID
    roles: list[Role]
    auth_mode: Literal["oidc", "development"]


class Problem(Contract):
    type: str
    title: str
    status: int
    detail: str
    code: str
    correlation_id: str
    quality_issues: list[QualityIssue] = []


class CreateScenario(Contract):
    source_snapshot_id: UUID
    title: str | None = Field(default=None, max_length=200)
    allow_external_write: Literal[False] = False


class ScenarioRecord(Contract):
    id: UUID
    version: int
    snapshot_hash: Digest
    policy_hash: Digest
    state: ScenarioState
    snapshot: ScenarioSnapshot
    quality_issues: list[QualityIssue]
    created_at: datetime
    current: bool
    latest_job_id: UUID | None
    latest_plan_id: UUID | None
    etag: str


class ScenarioPage(Contract):
    items: list[ScenarioRecord]
    next_cursor: str | None


class SolveRequest(Contract):
    max_wall_seconds: int = Field(default=30, ge=10, le=60)
    compare_baselines: bool = True


class JobRecord(Contract):
    id: UUID
    scenario_id: UUID
    scenario_version: int
    snapshot_hash: Digest
    status: Literal["QUEUED", "RUNNING", "VALIDATING", "COMPLETED", "FAILED", "CANCELLED"]
    progress: int = Field(ge=0, le=100)
    attempt: int = Field(ge=0)
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    plan_id: UUID | None
    error_code: str | None
    poll_url: str


class PlanRecord(Contract):
    id: UUID
    job_id: UUID
    scenario_id: UUID
    scenario_version: int
    plan_hash: Digest
    plan: SolutionPlan
    state: Literal["PROPOSED", "APPROVED", "REJECTED", "ESCALATED", "STALE", "QUARANTINED"]
    approvable: bool
    blockers: list[str]
    created_at: datetime
    etag: str


class PlanList(Contract):
    items: list[PlanRecord]


class DecisionRequest(Contract):
    action: Literal["APPROVE_IN_APP", "REJECT", "ESCALATE"]
    reason_code: Identifier
    comment: str = Field(min_length=1, max_length=500)
    expected_snapshot_hash: Digest
    expected_plan_hash: Digest


class DecisionReceipt(Contract):
    id: UUID
    plan_id: UUID
    action: Literal["APPROVE_IN_APP", "REJECT", "ESCALATE"]
    actor: str
    reason_code: str
    recorded_at: datetime
    snapshot_hash: Digest
    plan_hash: Digest
    external_write_performed: Literal[False] = False


class ImportRequest(Contract):
    snapshot: ScenarioSnapshot


class ImportRecord(Contract):
    id: UUID
    status: Literal["READY", "QUARANTINED", "COMMITTED"]
    content_sha256: Digest
    snapshot_id: UUID | None
    quality_issues: list[QualityIssue]
    row_errors: list[str]
    created_at: datetime


class SnapshotReceipt(Contract):
    snapshot_id: UUID
    snapshot_hash: Digest
    synthetic: Literal[True] = True


class AuditEntry(Contract):
    id: UUID
    occurred_at: datetime
    actor: str
    action: str
    resource_id: str
    outcome: str
    correlation_id: str
    previous_hash: str
    event_hash: Digest


class AuditPage(Contract):
    items: list[AuditEntry]
    next_cursor: str | None


class PolicyPage(Contract):
    items: list[RuleSet]


class MetricsPage(Contract):
    items: list[MetricValue]


class ProtectShipment(Contract):
    """One synthetic booked AWB in the Protect sandbox (aggregate mass/volume only)."""

    id: Identifier
    service_class: Literal["GENERAL", "PRIORITY", "EXPRESS"]
    guaranteed: bool
    weight_kg: int = Field(ge=1, le=1_000_000)
    volume_m3: float = Field(gt=0, le=10_000)
    density_kg_m3: float = Field(gt=0, le=100_000)
    chargeable_kg: int = Field(ge=1, le=10_000_000)
    loaded_optimized: bool
    loaded_priority_fill: bool


class ProtectPolicyResult(Contract):
    policy: Literal["CARGOPULSE_LOAD_OPTIMIZER", "PRIORITY_FILL"]
    status: Literal["OPTIMAL", "FEASIBLE", "TIME_LIMIT", "INFEASIBLE", "GREEDY_REFERENCE"]
    solve_ms: float = Field(ge=0)
    loaded_count: int = Field(ge=0)
    offloaded_count: int = Field(ge=0)
    offloaded_priority_count: int = Field(ge=0)
    weight_used_kg: int = Field(ge=0)
    volume_used_m3: float = Field(ge=0)
    weight_utilization: float = Field(ge=0, le=1)
    volume_utilization: float = Field(ge=0, le=1)
    chargeable_carried_kg: int = Field(ge=0)
    offloaded_weight_kg: int = Field(ge=0)
    independent_check: Literal["PASS", "FAIL"]
    check_findings: list[Identifier]


class ProtectPlan(Contract):
    """Synthetic, stateless Protect sandbox result. Nothing is stored or sent."""

    scope: str
    synthetic: Literal[True]
    seed: int
    flight_number: Identifier
    payload_kg: int
    volume_m3: float
    volumetric_kg_per_m3: int
    shipments: list[ProtectShipment]
    results: list[ProtectPolicyResult]
    has_external_write_permission: Literal[False]


class Health(Contract):
    status: Literal["ok", "unavailable"]
    dependencies: dict[str, str]


def canonical_hash(value: BaseModel | dict) -> str:
    data = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
