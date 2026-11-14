# 06 — REST API, Jobs and Event Contracts

## Contract policy
API root `/api/v1`. FastAPI owns canonical OpenAPI JSON; generated TypeScript types checked into `packages/contracts`. UI must not hand-create incompatible types. All mutating requests require auth, tenant scope, correlation ID, CSRF protection where browser cookies are used and an `Idempotency-Key` for retriable operations. Use RFC 7807-style problem details. Avoid sensitive fields in query strings.

## Essential endpoints
| Method | Route | Authority | Response |
|---|---|---|---|
| GET | `/me` | authenticated | roles, tenant, masked profile |
| GET | `/events?state=&cursor=&limit=` | controller / analyst | paginated event queue |
| POST | `/imports/validate` | data steward | 202 import validation job |
| POST | `/imports/{id}/commit` | data steward | created source snapshot with rejected rows |
| GET | `/imports/{id}` | data steward | status, freshness, field errors |
| POST | `/scenarios` | controller | 201 scenario version/hash |
| GET | `/scenarios/{id}` | scoped user | snapshot, inputs, version, freshness, model scope |
| GET | `/scenarios/{id}/candidates` | controller | accepted and excluded arcs + reasons |
| POST | `/scenarios/{id}/solve` | controller | 202 job_id, scenario_version |
| GET | `/jobs/{id}` | owner/supervisor | QUEUED/RUNNING/VALIDATING/COMPLETED/FAILED, progress, timings |
| GET | `/jobs/{id}/events` | owner/supervisor | SSE read-only, authenticated; bounded and resumable |
| GET | `/plans/{id}` | controller | assignments, options, validator, solver flags |
| GET | `/plans/{id}/alternatives` | controller | comparable feasible plans with policy hashes |
| POST | `/plans/{id}/decisions` | controller/manager | decision event, 409 if stale/mismatch |
| POST | `/scenarios/{id}/supersede` | controller | new immutable snapshot version |
| GET | `/policies` | manager/admin | versioned policy sets and approvals |
| POST | `/policies/{id}/publish` | 2-person reviewer policy | immutable policy version |
| POST | `/replays` | analyst | comparison job with time-causal data selection |
| GET | `/metrics` | scoped user | values with numerator/denominator/evidence tier |
| GET | `/reports/{id}/export` | authorised user | signed expiring download; no PII leakage |
| GET | `/audit` | auditor | pagination + immutable event metadata |
| GET | `/health/live` | orchestrator | liveness only |
| GET | `/health/ready` | orchestrator | checks DB/queue/required dependencies |

## Example POST `/scenarios`
```json
{
  "kind": "RECOVER",
  "source_snapshot_id": "86b74f0b-3cb7-4bbb-8c7f-dc7c44511dba",
  "event_ids": ["98ca75f1-62fd-4dfd-9703-5edc5dc45e7c"],
  "policy_set_id": "policy-recover-v1",
  "event_as_of_utc": "2026-11-09T03:30:00Z",
  "evidence_tier": "TEAM_SYNTHETIC_UNVERIFIED",
  "allow_external_write": false
}
```
Validation includes snapshot checksum and scenario readiness; `allow_external_write` ignored/rejected at L1/L2 rather than accepted as an authorisation.

## Example solve request/response
```http
POST /api/v1/scenarios/3d06aa.../solve
Idempotency-Key: 3b84b5f9-... 
If-Match: "scenario-version-8"
Content-Type: application/json
```
```json
{ "policy_set_id": "published-recover-001", "max_wall_seconds": 30, "compare_baselines": true, "stability_weight": "2.0" }
```
```json
{ "job_id": "5bc4430c-6c57-4f60-aa74-74c76bf76e52", "status": "QUEUED", "snapshot_sha256": "<sha256>", "poll_url": "/api/v1/jobs/5bc4430c-6c57-4f60-aa74-74c76bf76e52" }
```

## Example plan response (illustrative, not airline data)
```json
{
  "id": "plan-123", "scenario_id": "scenario-123", "scenario_version": 8,
  "synthetic": true, "evidence_tier": "TEAM_SYNTHETIC_UNVERIFIED",
  "solver": {"engine": "HiGHS", "status": "OPTIMAL", "time_ms": 289, "optimality_gap": "0", "time_limit_ms": 30000},
  "independent_validation": {"status": "PASS", "checked_gates": ["A", "B", "C", "D", "E", "F", "G", "H"]},
  "metric_definitions": {"weighted_delay_hours": "sum max(actual_arrival - commitment, 0) * service_weight"},
  "assignments": [
    {"uld_id": "U-014", "flight_id": "FLIGHT-HKG-FRA-20261109", "status": "PROPOSED", "reason_codes": ["LAST_FEASIBLE_CONNECTION"], "delay_hours": "4.0", "risk_delta_weighted_hours": "24.0"}
  ],
  "unassigned": [{"uld_id": "U-021", "reason_codes": ["COLD_CHAIN_NOT_VERIFIED"], "action": "ESCALATE"}],
  "approvable": true, "has_external_write_permission": false,
  "policy_hash": "<sha256>", "snapshot_hash": "<sha256>"
}
```

## Approval semantics
`POST /plans/{id}/decisions` with `If-Match` and body `{action:'APPROVE_IN_APP'|'REJECT'|'ESCALATE', reason_code, comment, expected_snapshot_hash, expected_plan_hash}`. Approval checks controller role, scenario current version, no unknown hard gates, validator PASS, policy revision, freeze window and no contradictory approval. API returns `409 STALE_PLAN` when new event superseded snapshot. A retry with same idempotency key returns original decision. Result never calls a third-party operational API at L1/L2.

## Errors
| HTTP | code | Meaning |
|---|---|---|
| 400 | `INVALID_REQUEST` | malformed schema |
| 401 | `UNAUTHENTICATED` | identity not valid |
| 403 | `FORBIDDEN` | action not permitted |
| 404 | `NOT_FOUND` | not visible in tenant |
| 409 | `STALE_PLAN`, `VERSION_CONFLICT`, `DUPLICATE_EVENT` | conflict; return current safe reference |
| 422 | `MISSING_CRITICAL_DATA`, `NO_FEASIBLE_ARCS` | blocked due to quality or model infeasibility |
| 429 | `RATE_LIMITED` | backoff indicated |
| 503 | `SOLVER_UNAVAILABLE`, `DEPENDENCY_NOT_READY` | recoverable unavailable |

Error body: `type`, `title`, `status`, `detail` (not PII), `code`, `correlation_id`, optional `quality_issues[]`.

## Streaming
SSE may show `queued`, `running`, `candidate_count`, `validator_started`, `finished`, `failed`; do not leak sensitive route assignments through unauthorised channels. Support polling fallback and event reconnection cursor. **The UI must never display “optimal” until server confirms solver status and validator pass.**

## Contracts and compatibility
- Shared JSON Schema for `ScenarioSnapshot`, `FlightCapacity`, `CargoUnit`, `RuleSet`, `SolutionPlan`, `MetricValue`, `QualityIssue`; CI diff-check generated TS types.
- OpenAPI change requires agent-reviewed PR, frontend client regeneration, migration notes and a contract test before merge.
- All endpoints enforce paging, quotas and limits. CSV import accepts bounded sizes; no arbitrary URL fetching from user input. When provider payloads are JSON-LD, normalise only after successful schema check and provenance capture.
