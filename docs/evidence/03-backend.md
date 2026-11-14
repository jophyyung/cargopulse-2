# Backend engineering evidence

Status: implemented and locally verified synthetic engineering; hosted L1 release,
enterprise OIDC acceptance and operational airline validation remain unapproved.

## Scope and contracts

The actual runtime is `cargopulse_api.main:app`; worker entry is
`python -m cargopulse_api.worker`. The frozen canonical DTOs and initial ORM tables
were not modified. Lead-approved additive endpoints cover authentication, controlled
CSV upload, urgency curves, policy draft inspection/publication and report exports.
The lead owns actual OpenAPI/TypeScript regeneration and final integration.

Additive migration 0002 adds browser-bound one-time OIDC flow state, PostgreSQL RLS
and immutable snapshot/decision/audit/published-policy/plan-content controls. Migration
0003 protects immutable scenario revisions and plan ids while allowing lifecycle
state/current/latest-job/latest-plan changes. Both local databases reached revision
0003 using schema-owner migration credentials. Application/worker tests used the
separate `cargopulse_app` role with NOSUPERUSER/NOBYPASSRLS and no table ownership.

## Actual checks

Final command (with the optimizer worktree's `services/worker` temporarily appended
to PYTHONPATH; the independent validator was cherry-picked from the approved lead
commit into this worktree):

```sh
BACKEND_TEST_DATABASE_URL=postgresql+psycopg://cargopulse_app@127.0.0.1:55432/cargopulse_backend_test \
PYTHONPATH=packages/contracts/python:services/api:services/worker:.:<optimizer-worktree>/services/worker \
  <repository-venv>/bin/python -m pytest tests/backend tests/contracts tests/validation -q
```

Result: **66 passed**, one upstream Starlette/httpx deprecation warning, exit 0,
22.88 seconds. The warning recommends httpx2; the approved lock was not changed.
`python -m ruff check services/api tests/backend --fix` completed exit 0 with all
checks passing after import cleanup. `git diff --check` completed exit 0.

Earlier targeted results were 15 fast tests, then 18 combined backend checks, then
41/43 expanded backend+contract checks. The final 66-pass command supersedes those
partial results. The suite includes five tests against real PostgreSQL 18.6 and
Redis 8.2.3, not SQLite substitutes for RLS/concurrency claims. Only the isolated
`cargopulse_backend_test` database is truncated by integration fixtures.

Verified behaviors:

- Unauthenticated/malformed/forbidden requests return bounded problem details.
  Cookie sessions are hashed at rest, revocable/expiring, HttpOnly and use local
  approved role grants. CSRF/Origin failures and role/object denials persist audit
  records after rejected command rollback. Production rejects development auth.
- Eleven OIDC tests use real RSA signing/verification and a recorded discovery/token/
  JWKS transport: S256 verifier, one-time state, browser binding, nonce, issuer,
  audience/azp, expiry/expired state, invalid signature, JWKS key rotation, privileged
  MFA context and unknown local subject. This proves the tested code/crypto paths,
  not a live enterprise IdP or production MFA setup.
- Cross-tenant direct scenario/candidate/urgency/job/plan/export requests are denied.
  A non-owner DB role sees no snapshots with absent context or another tenant's
  context. Snapshot UPDATE is denied by grants; even ordinary owner DML cannot
  modify audit history/scenario revisions. Plan hash mutation is blocked by trigger.
- JSON validate/commit/create preserve immutable canonical snapshots, reject binary
  float measurements/cross-tenant imports, quarantine unknown capacity, enforce
  monotonic source versions and idempotency. Controlled CSV accepts a complete
  140-row fixture, rejects formula cells/malformed schema and writes private 0600
  local artifacts. Arc-specific unknown evidence is explicit review information;
  it does not authorize that arc or discard unrelated safe candidates.
- One solve retry yields one DB job and transactional outbox. Live Redis publication
  was observed; deleting that job's Redis hint did not prevent DB worker completion.
  A crashed owner's unexpired lease prevents another claim; expiry allows reclamation.
  A terminal job cannot be processed twice.
- A fresh 140-ULD fixture ran through the real optimizer, two real reference
  baselines and independently recomputed validation. It persisted three plans.
  Two independent HTTP actors racing to approve produced exactly 201 and 409, with
  one immutable in-app decision and no external write. JSON/CSV/PDF exports returned
  private authenticated attachments with synthetic labels. PDF structure/header was
  tested; rendered visual quality was not reviewed.
- A new committed source version immediately invalidated an old proposal and its
  approval attempt. Deliberately duplicated solver assignments failed independent
  validation, quarantined the plan, recorded the failure and prevented approval.
- A policy author cannot self-publish. A second fixed development manager can fetch
  the scoped draft, review and publish it with a different actor and new content hash.
  Disabled ONE Record skeleton cannot fetch or normalize live data.

## Corrected failures

Initial candidate route evaluation imported an unavailable solver before checking the
object tenant, returning 503 instead of the expected hidden-object 404; lookup now
precedes module loading. PostgreSQL returned timestamptz values in the server's
Asia/Hong_Kong zone; all database timestamps now normalize to UTC before frozen DTO
construction. An initial approval-race test incorrectly entered concurrent lifespans
on one app and timed out at its barrier; independent HTTP clients now share the
already-running app lifespan and exercise concurrent real DB transactions.
These failures were corrected before the final successful run.

## Material limits and handoff

- SQLite fast tests do not establish RLS, PostgreSQL triggers or concurrent safety.
  The explicit PostgreSQL tests supply those limited local claims.
- PostgreSQL/Redis use isolated passwordless loopback test services. This is not
  production TLS, secret management, object-store IAM or hosted deployment evidence.
- The S3 adapter requests private-bucket access and AES256 encryption; no actual
  S3-compatible service was provisioned/tested in this backend turn. Local private
  artifact permissions were tested. Bucket policies, WORM, malware scanner service,
  backup/restore and retention need deployment/owner verification.
- Full OpenTelemetry dashboards, staging p95/load/SLA, container build/security
  scanning, enterprise IdP login/MFA, egress firewall and production restore targets
  are not established by these checks. Structured redacted request/worker logs and
  dependency health probes are implemented.
- Worker leases fence stale writes; deployment process/container limits must stop a
  hung numerical library. Polling uses the non-owner app role with explicit per-tenant
  context, while tenant inventory itself is an internal unscoped reference read.
- Imports only accept synthetic data. Imported policy author/reviewer records are
  synthetic provenance, never an airline policy sign-off. Reports count whole ULDs
  and preserve metric denominators/windows; no AWB conversion or arrival promise is
  inferred.
- Production OIDC requires pre-provisioned issuer/subject/tenant grants, configured
  OIDC_TENANT_ID, HTTPS/MFA/client settings and a real accepted identity tenant.
  Fixed development identities cannot run outside explicit development mode.
- Rollback uses the prior image plus a reconciled backup restored into a separate
  database. Security/history migration downgrades intentionally fail.

See `services/api/README.md` for exact bootstrap, grants, auth, upload, worker,
report and operations instructions. Final release acceptance remains lead/user-owned.
