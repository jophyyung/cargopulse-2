# Frozen integration contract v1

Authority: `packages/contracts/python/cargopulse_contracts/models.py`, OpenAPI and
the initial storage migration. Regenerate with `make contracts`; CI compares output.
No implementer may edit shared DTOs without lead review and regenerated TypeScript.

Solver imports `cargopulse_contracts`. Public optimizer interface:

```python
validate_snapshot(snapshot: ScenarioSnapshot, decision_time: datetime | None = None) -> list[QualityIssue]
build_feasible_paths(snapshot: ScenarioSnapshot, decision_time: datetime | None = None) -> CandidateSet
run_solver(snapshot: ScenarioSnapshot, max_wall_seconds: int = 30) -> SolutionPlan
run_baseline_earliest(snapshot: ScenarioSnapshot) -> SolutionPlan
run_baseline_priority(snapshot: ScenarioSnapshot) -> SolutionPlan
compute_urgency_delta(snapshot: ScenarioSnapshot, decision_times: list[datetime]) -> list[UrgencyPoint]
```

Module: `cargopulse_optimizer`. Independent validator (lead-owned):
`cargopulse_validation.validate_solution_independently(snapshot, plan, decision_time=None)`.
The optimizer may call that public function; it may not implement or modify it.
The API and worker must revalidate returned results before marking plans ready.

Backend public worker entry: `python -m cargopulse_api.worker`. Worker claims a DB
lease, resolves optimizer lazily and persists all outputs transactionally. PostgreSQL
is authoritative even if Redis loses every message. Idempotent terminal writes and
expired lease reclamation prevent duplicate plans. Use the ORM contract in
`services/api/cargopulse_api/tables.py`; additions need an additive migration.

Web uses relative `/api/v1` through a Next.js server proxy to private API. HttpOnly
API session cookies pass through that proxy. Authenticated POSTs first read JSON
`csrf` from the read-only `/auth/csrf` endpoint and send it as `X-CSRF-Token`;
the client does not derive it from cookie names. Backend
owns `/auth/login`, `/auth/callback`, `/auth/logout`, `/auth/development` and
`/auth/csrf` under `/api/v1`; development identities are fixed and explicitly labelled.
All commands supply `Idempotency-Key`; solve and decisions supply quoted ETags.

Production session/CSRF cookies use `__Host-cp_session`/`__Host-cp_csrf`, Secure,
Path=/ and no Domain. The callback binding uses `__Secure-cp_oidc_binding` with its
callback path. HTTP development deliberately retains `cp_*` names. Production
never falls back to those unprefixed cookies. CSRF is an HMAC of the random session
secret; GET does not renew expiry or change its stored hash. Valid legacy random
CSRF values may be reused only when their cookie matches the stored digest;
otherwise fresh sign-in is required. The JSON DTO is unchanged.

Migration 0005 adds nullable verified OIDC context hashes and transactional
account-disable revocation. Privileged OIDC requests require current issuer/ACR
assurance even after local role changes; legacy NULL is not fabricated as MFA.
Session creation and account disable serialize on the existing tenant lock. A
directory operator must have the scoped session DELETE grant: the invoker trigger
fails and rolls back the disable when that grant is absent. The application still
cannot modify directory grants. Schema downgrade is deliberately refused.

GET `/auth/csrf` also returns non-renewing `X-Session-Expires-In` metadata, forwarded
by the Next proxy. The client conservatively times private-DOM removal and hides
its console on logout attempts, offline/401/cross-tab and persisted-page events.
It stores only a fixed-size session-boundary marker and one-way fingerprint, never
raw credentials, identities or drafts. This UX boundary does not grant authority
or prove server revocation when the logout request failed.

Operations flow: fetch `/fixtures/recover`, validate import, commit, create scenario,
get candidates, request solve (202), poll durable job, read plan and alternatives,
confirm hash/version in decision sheet, record receipt, inspect audit/export.
JSON bodies are bounded. Controlled CSV uploads use a separate additive upload
endpoint; its schema is generated before the web uses it.

RBAC: controllers/managers create scenarios, solve and decide; data stewards/managers
validate/commit imports; analysts and observers read permitted operational records;
auditor/manager access audit; tenant admins do not automatically approve plans.
Users are pre-provisioned locally against (issuer, subject, tenant) for OIDC.

Contract registry functions throw intentionally and never serve traffic. The actual
API must implement every enabled endpoint; unfinished P1/P2 routes remain absent.
