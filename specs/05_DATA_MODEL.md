# 05 — Canonical Data Model, Invariants and Migration Rules

## General conventions
- IDs: UUIDv7 or UUIDv4; all DB rows include `tenant_id` unless truly global read-only reference table. Use a schema-qualified table for policy metadata if needed.
- All timestamps ISO-8601 in **UTC**, `timestamptz` in PostgreSQL; local zone IANA ID recorded for flights. Store original timezone/offset separately for input traceability. Preserve DST ambiguity.
- Measurements are **decimal** (not binary float): `mass_kg`, `volume_m3`, `chargeable_weight_kg`, `duration_seconds`, `delay_weighted_hours`. For consistency, solver transforms to bounded integer gram/cm³/seconds units or controlled rational scaling with overflow checks.
- No implicit default for missing safety-critical fields. `null` means unknown, not zero. Never parse a missing `dg_approved` as false and then quietly exclude it without surfacing quality reason. Use `UNKNOWN`, `VERIFIED_TRUE`, `VERIFIED_FALSE` with evidence.
- Schema changes via Alembic, expand/migrate/contract for non-backwards-compatible changes; seeded sample data is tagged `SYNTHETIC`.

## Core entities and table suggestions
| Entity | Key fields | Rules |
|---|---|---|
| `tenants` | id, name, region_policy, retention_policy_id | neutral organisation names; do not use airline endorsement without permission |
| `users` | id, tenant_id, oidc_sub, email, status | OIDC subject immutable; email is not the unique auth principal |
| `role_grants` | user_id, role, resource_scope, approved_by, effective/expires | explicit least privilege |
| `source_connections` | id, tenant_id, connector_type, endpoint_id, status, schema_version, secret_ref | credentials stored in secret manager, not DB plaintext |
| `ingest_batches` | id, source, object_uri, content_sha256, import_idempotency_key, validation_summary, received_utc | imported raw artefact immutable and access-controlled |
| `source_records` | source_system, external_id, external_version, event_utc, observed_utc, raw_ref | detect duplicates and out-of-order updates |
| `awbs` | id, awb_identifier, booking_status, service_class, stated_weight_kg, declared_volume_m3 | AWB is document; not equivalent to ULD |
| `pieces` | id, awb_id, piece_no, mass_kg, volume_m3, handling_requirements | original pieces and status |
| `ulds` | id, uld_code, type, contour, equipment_status, tare_mass_kg, serviceability, owner | separate physical unit from contents |
| `uld_contents` | uld_id, piece_id, quantity/weight share, effective_from/to, build_version | many-to-many mapping with explicit assignment; no double counting |
| `flights` | id, carrier, flight_no, origin, destination, scheduled/actual departures/arrivals_utc, aircraft_variant, status | route identity includes date and leg; IATA codes validated |
| `capacity_snapshots` | flight_id, observed_utc, hold/position_id, free_payload_kg, free_volume_m3, slot_count, contour_compatibility, source_ref, version | position-specific limit, not just global flight weight |
| `handling_resources` | location, time_window, build_capacity, team_status, equipment_type | do not assume unlimited breakdown/build-up capacity |
| `connections` | inbound_leg, outbound_leg, min_transfer_seconds, cutoff_utc, customs_status | explicitly feasible, not inferred from distance |
| `commitments` | cargo_id, service_weight, latest_delivery_utc, guaranteed_or_contractual, revenue_eligible | hard contract constraints distinguished from soft priority weights |
| `restrictions` | cargo_id, DG details/reference, temperature band, verified_status, flight compatibility, customs/security | provenance and signed rule revision required |
| `operational_events` | id, event_type, effective_utc, affected_entity, message_id, source_version | dedup and replay;
| `scenarios` | id, type, snapshot_version, immutable_snapshot_sha256, evidence_tier, owner, state | each scenario is a bounded event analysis |
| `policy_sets` | id, semver, state(draft/published/retired), published_by, hash, effect_date | policies versioned; hard gates distinguish from preferences |
| `candidate_assignments` | scenario_id, cargo_unit_id, flight_id, eligibility, rejection_codes, computed_utc | immutable per scenario; persisted for explanation |
| `solve_jobs` | id, scenario_id, snapshot_hash, policy_hash, requested_by, attempt, status, time_limit_s, error_code | durable jobs; idempotency |
| `solution_plans` | id, job_id, solver_status, objective_value, units, bound, gap, elapsed_ms, validator_status, plan_hash | no solution may become approvable before validator pass |
| `plan_assignments` | plan_id, cargo_unit_id, flight_id|null, handling_slot|null, reason_code, delay_hours, changed_from_previous | null = explicit escalation/unassigned |
| `plan_decisions` | id, plan_id, actor_id, approval_type, decision_reason, at_utc, replaced_plan_id | append-only, immutable after commit |
| `metric_values` | id, run_id, metric_name, numerator, denominator, units, cohort, methodology_version, evidence_tier | chart values never lose denominator |
| `audit_events` | id, occurred_utc, actor, tenant, action, resource_version, before/after digest, outcome, correlation_id | append-only, confidentiality-safe |
| `outbox_events` | id, aggregate, type, payload_ref, published_utc, delivery_attempts | transactional outbox |

## Required canonical types
```ts
type EvidenceTier = 'PUBLIC_VERIFIED' | 'ORGANISER_SNAPSHOT' | 'TEAM_SYNTHETIC_UNVERIFIED' | 'LIVE_AUTHORISED';
type DataValidity = 'VERIFIED' | 'UNVERIFIED' | 'STALE' | 'UNKNOWN' | 'CONFLICTED';
type SolverStatus = 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE' | 'TIME_LIMIT_WITH_FEASIBLE' | 'TIME_LIMIT_NO_FEASIBLE' | 'ERROR' | 'CANCELLED';
type HardGateResult = 'PASS' | 'FAIL' | 'UNKNOWN';
type Decision = 'APPROVE_IN_APP' | 'REJECT' | 'ESCALATE';
```

## Data graph invariants
- Every piece belongs to exactly one AWB at time `t`. A piece cannot be simultaneously assigned to two ULD positions at the same time.
- A ULD may hold multiple AWBs; an AWB may span ULDs. Every load assignment is referenced to both a ULD configuration and flight departure snapshot.
- Neither AWB-to-ULD nor ULD-to-AWB conversion is proportional by default. For metrics count distinct explicitly declared units.
- Availability at timestamp `t` must use `observed_at ≤ t` and `effective_at ≤ t`, with no information leakage from a future snapshot in replay.
- One active physical flight+hold slot assignment per ULD and conflicting time interval. Each cargo-to-flight connection path must be time-feasible and have required documentation.
- All `approved` plans have `validator_status=PASS`, current scenario version and frozen policy hash.
- No command can overwrite approved actions; supersede them with reason and reviewer identity.

## Data quality interface
`QualityIssue {code, severity, entity_type, entity_id, field, expected, actual, source_record, remediation, blocking}`. Critical example codes: `MISSING_PAYLOAD`, `UNVERIFIED_COLD_CHAIN`, `ULD_CONTOUR_UNKNOWN`, `DG_DECLARATION_MISSING`, `STALE_FLIGHT_STATUS`, `TIMEZONE_AMBIGUOUS`, `AWB_ULD_MAPPING_INCOMPLETE`, `HOLD_SLOT_CONFLICT`, `CUSTOMS_STATUS_UNKNOWN`, `NO_VALID_ROUTE`.

## Metrics without false comparisons
`reprotected_48h_recoverable_uld_rate = count(eligible_ULDs with approved protected assignment ≤48h) / count(eligible_ULDs)`; also `all_affected_ULD_rate`. `offload_AWB_rate = distinct offloaded_AWBs / distinct booked_AWBs` for the same defined period and event cohort. `reassigned_ULD_count` distinct changes from last approved plan. `weighted_delay_hours` sums policy weights × lateness relative to exact commitment with no negative benefit hidden by rounding. One event can be represented in several ratios; never transform its denominator without traceable mapping.

## Database privacy
Use pseudonymised synthetic IDs for development. At L2, encrypt protected columns where required, restrict raw record retention and row-level access, keep operator notes separately from source facts and configure per-tenant deletion (including backups as legally feasible). Hash provenance, but do not claim hash chaining alone prevents DB-owner tampering.
