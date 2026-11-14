# CargoPulse API and durable worker

This runtime serves synthetic Recover decision support only. Approval records an
in-app decision; no airline connector, arbitrary URL fetcher, Protect execution or
external operational write endpoint exists. A synthetic model is not aviation
certification, a confirmed transport booking or a physical arrival promise.

## Run locally

Use the repository's locked Python 3.12 environment. Start PostgreSQL 18 and Redis,
then migrate once as the database schema owner:

```sh
export PYTHONPATH=packages/contracts/python:services/api:services/worker:.
DATABASE_URL=postgresql+psycopg://SCHEMA_OWNER@localhost:55432/cargopulse \
  .venv/bin/alembic -c services/api/alembic.ini upgrade head
```

Provision a distinct application role with `NOSUPERUSER NOBYPASSRLS` and no schema
ownership. Grant schema usage and table SELECT/INSERT/UPDATE/DELETE, then revoke
UPDATE/DELETE on snapshots, plan_decisions and audit_events. Immutable triggers
also protect those tables against ordinary schema-owner DML. A superuser can alter
or bypass the controls; hash chaining does not defeat a privileged DB operator.
Do not grant application CREATE privileges on the schema. Use the application role
for both API and worker. Both explicitly set the transaction-local tenant context;
the worker enumerates only the synthetic tenant inventory before scoped polling.

```sql
CREATE ROLE cargopulse_app LOGIN NOSUPERUSER NOBYPASSRLS;
GRANT USAGE ON SCHEMA public TO cargopulse_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO cargopulse_app;
REVOKE UPDATE, DELETE ON snapshots, plan_decisions, audit_events FROM cargopulse_app;
REVOKE INSERT, UPDATE, DELETE ON tenants, identities FROM cargopulse_app;
REVOKE ALL ON alembic_version FROM cargopulse_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO cargopulse_app;
```

Use secret-manager credentials/TLS in deployed environments. Passwordless loopback
trust is solely an isolated local test configuration. Copy `.env.example` values
into the process environment; the runtime does not implicitly read `.env` files.

```sh
export APP_ENV=development ENABLE_DEVELOPMENT_AUTH=true
export DATABASE_URL=postgresql+psycopg://cargopulse_app@localhost:55432/cargopulse
export REDIS_URL=redis://localhost:56379/0 APP_BASE_URL=http://localhost:3000
.venv/bin/uvicorn cargopulse_api.main:app --host 127.0.0.1 --port 8000 --no-access-log
# In a second process, with the same environment:
.venv/bin/python -m cargopulse_api.worker
```

Development identities are exactly `controller`, `steward`, `manager`, `manager-reviewer`, `auditor`
and `controller-b`; the last belongs to a different synthetic tenant. Browser
requests use relative `/api/v1` through the Next.js proxy. That proxy forwards
Cookie and Set-Cookie. Mutations send the configured Origin and the `cp_csrf`
cookie value as `X-CSRF-Token`. Commands also send Idempotency-Key; solve,
supersession and decisions send the exact quoted ETag from the record. Session
cookies are HttpOnly, revocable and secure outside development. GET `/auth/csrf`
returns the current session's stable token as `{ "csrf": "..." }`; it neither
rotates that token nor renews the session.

## Production identity

Development auth outside `APP_ENV=development` fails startup. Production requires
PostgreSQL, HTTPS application/callback/issuer, private object bucket, client id and
mandatory privileged MFA context. Set `OIDC_TENANT_ID` to the deployment tenant.
Pre-provision Identity rows for the exact issuer, subject, tenant and approved local
roles. Token roles and token tenant claims never create grants. The authorization
code flow checks state, browser binding, S256 PKCE, nonce, issuer, audience, expiry,
signature and configured privileged `acr`. One-time flow state is consumed before
token exchange. OIDC endpoints/JWKS are loaded only from configured issuer discovery.
OIDC callback tests use real RSA verification with recorded transport; no enterprise
IdP, hosted TLS, MFA enrollment or partner identity tenant has been accepted yet.

## Imports and storage

JSON validate/commit follows the frozen DTOs. Canonical snapshot content is hashed.
Malformed decimal strings return validation errors rather than server errors in
both JSON and CSV intake. Public field and OpenAPI schemas are unchanged.
Source event versions must increase. New versions stale existing proposals before
approval. Missing capacity or stale provenance quarantines imports. Immutable
snapshots preserve explicit piece/AWB/ULD mapping. Raw artifacts are written under
private tenant prefixes with content digests. On POSIX, local development objects
have mode 0600 under a 0700 directory. These modes do not verify Windows ACLs;
Windows tests report the POSIX permission check as skipped. S3 writes request
AES256 server-side encryption.
Bucket public-access blocking, IAM, retention, WORM, malware-scanning service and
restore exercises remain deployment responsibilities, not verified local claims.
No presigned public URL is issued by this runtime.

POST `/imports/upload-csv` accepts multipart `file` (UTF-8 text/csv) and `metadata`
(JSON snapshot excluding cargo_units). Headers must be unique, nonempty, exact
CargoUnit field names and include all required fields. Nested
pieces/serviceability/security cells contain JSON with unique keys, booleans are
`true`/`false`, and optional null fields are empty. UTF-8 BOM and reordered columns
are supported. At most 1,200 rows and 8 MB total request body are accepted; parsing
stops at the first excess row. Formula prefixes (including full-width variants)
and control characters inside CSV cells are rejected, including escaped controls
after decoding nested JSON cells. Metadata cannot contain a
second cargo_units manifest. Malformed inputs return bounded row/schema diagnostics
without echoing uploaded values. JSON and CSV are parsed as data and never executed.
Idempotency binds the exact uploaded bytes, including a BOM, as well as the
canonical snapshot. Reusing a key for different bytes returns a conflict.

## Jobs, review and reports

The command transaction inserts job and outbox rows together. The worker polls
PostgreSQL regardless of Redis. Redis carries only bounded advisory job ids.
Claims use row locking, a 300-second lease, owner fencing and at most three lease
claims. Expired jobs can be reclaimed; a stale owner cannot write a terminal
result. At most one plan per job/policy is stored. Each plan is independently
validated at wall-clock decision time before persistence and again before reading
its approvability or approving it. Any invalid optimized/baseline output quarantines
the entire solve. All-unassigned output is not a ready recovery plan. Failed jobs
retain sanitized error codes and audit records.

The optimizer must be installed as `cargopulse_optimizer`; no fake fallback exists.
Large calculations run only in the worker. Process/container CPU/memory ceilings
and kill/restart supervision must be configured by the deployment. A lease fences
late writes but does not itself interrupt a hung numerical library.

Approval serializes tenant/scenario/plan updates, compares ETag/current version,
hashes, source freshness, published policy and newly recomputed independent
validation, then writes one immutable decision and its audit event. Denials use a
separate audit transaction after rollback. Policy drafts require a different locally
provisioned manager to publish; GET `/policies/{id}` allows manager/tenant_admin to
inspect the scoped draft first. Imported published policy provenance is explicitly
synthetic and is not airline sign-off.

GET `/reports/{plan_id}/export?format=json|csv|pdf` checks the same tenant/role as
plan reads, records an export event and streams a private attachment. JSON includes
source provenance; CSV quotes every cell, prefixes formula-leading text with an
apostrophe, visibly escapes control characters, and includes metric denominators,
UTC windows and method. JSON is the lossless evidence format; report CSV is a
presentation format. Subsequent spreadsheet edits/save/reopen behavior is not
verified. PDF is a plain paginated text report with synthetic labels,
source/policy hashes and metric metadata. The PDF generator has structural tests;
publication typography and independent rendered visual QA are not claimed.

## Health, operations and limits

`/health/live` checks process liveness. `/health/ready` checks DB, private object-store
access and optimizer/validator installation, and reports Redis
hint degradation without losing durable job readiness. Structured request logs
include route template, status, latency and random correlation id, not payloads.
Worker errors log job id and exception type, not cargo text or token contents.
Full exported tracing dashboards, hosted alerts, load/SLA/security scans, production
bucket verification and a timed backup/restore drill are not established by tests.

Migrations 0002/0003 are additive. Scenario identity/input hashes and plan content
are immutable while lifecycle state pointers may change. Its downgrade deliberately fails because removing
immutable-history/security guarantees is unsafe; rollback uses the prior image and
restores an encrypted backup to a separate database after reconciliation. SQLite is
only a fast test adapter and provides no RLS/trigger/concurrency release evidence.

## Verification

```sh
PYTHONPATH=packages/contracts/python:services/api:services/worker:. \
  .venv/bin/python -m pytest tests/backend tests/contracts -q
BACKEND_TEST_DATABASE_URL=postgresql+psycopg://cargopulse_app@127.0.0.1:55432/cargopulse_backend_test \
  .venv/bin/python -m pytest tests/backend -q
```

The PostgreSQL suite requires the exact `cargopulse_backend_test` database,
`cargopulse_app` user, loopback `127.0.0.1:55432`, and no password/query overrides.
It truncates only that explicitly isolated database. Migrate it first with schema-owner permissions and
grant the non-owner app role as above. Never point it at a shared/deployed database.

## Container builds

The canonical hash-locked API/worker build is `infra/Dockerfile.api`, invoked by
root `compose.yaml`. There is no separate service-local Docker build. Production
configuration and bootstrap/grants are documented in
`docs/PRODUCTION_DEPLOYMENT.md`; the development Compose bootstrap is not a
production provisioning command.
