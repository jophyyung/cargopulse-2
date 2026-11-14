# Production deployment procedure

Status: **prepared, not executed or approved**. Public L1 remains blocked by
`RELEASE_REPORT.md`, including image findings and independent review. The local
Compose file always enables explicit development identities and must never be used
as a public production deployment. Use the separate production configuration.

## Prerequisites and configuration

Obtain owner-approved hosting/region/cost/domain, real OIDC/MFA, legal/retention
review, operations ownership and a signed release decision. Provision encrypted
managed PostgreSQL with tested backups/PITR, scoped TLS Redis, a private encrypted
S3-compatible bucket and an HTTPS telemetry collector with delivered alerts.
Use workload identity for object access. Deny airline operational egress.

Publish the reviewed API/web images and select a reviewed Caddy edge image only
after explicit registry/deployment authorization. Scan/sign every image and use
immutable `@sha256:` references in `API_IMAGE`, `WEB_IMAGE`, `EDGE_IMAGE`. Local
image IDs are evidence of local builds, not published registry digests.

Inject configuration from the target secrets manager according to
`infra/production.env.example`. Do not commit a populated env file or print
resolved Compose configuration. Runtime database/Redis URLs must use verified
TLS. OIDC issuer, redirect URI, client ID and required MFA context must match the
registered production application. `OIDC_TENANT_ID` is a provisioned local UUID.
No role/tenant grant is accepted from arbitrary token claims.

```sh
docker compose -f compose.production.yaml config --quiet
```

This checks configuration syntax only. It does not test TLS, secrets, images,
provider credentials, network policy or service availability.

## Migrations and initial authority

Take and verify the intended-environment backup first. Inject a separate schema
owner credential as `DATABASE_ADMIN_URL` only for the approved maintenance step:

```sh
test -n "$DATABASE_ADMIN_URL"
docker compose -f compose.production.yaml --profile maintenance run --rm migrate
```

Do not run `infra/bootstrap.py` in production. It is explicitly development-only.
Provision a non-owner, non-BYPASSRLS app role. Grant schema USAGE and operational
SELECT/INSERT/UPDATE/DELETE, then revoke UPDATE/DELETE on snapshots/decisions/audit,
revoke INSERT/UPDATE/DELETE on tenants/identities, and revoke metadata-table access.
Database triggers additionally preserve immutable payloads. Verify these exact
privileges against an isolated test tenant before serving users.

Through the controlled database administration process, insert the approved tenant
and identity records from `services/api/cargopulse_api/tables.py`. Each identity
needs a unique UUID/string ID, tenant UUID, exact HTTPS issuer, exact provider `sub`,
approved role list and enabled flag. Provision two distinct human managers for
initial synthetic-policy author/reviewer duties. Keep an administrative approval
record; do not provision defaults or derive grants from self-asserted claims.

Sign in through the real IdP and verify privileged MFA, disabled-identity behavior,
cookie flags, revocation, role/tenant denials and key rotation. Create the first
synthetic RuleSet as a DRAFT through the authenticated policy API/UI and publish it
with the other manager. The offline fixture generator can supply the synthetic
RuleSet JSON shape; importing it never grants publication authority. Production
does not automatically trust or publish the development seed. Only after a policy
is genuinely published can synthetic source/scenario evaluation proceed.

## Start, verify and promote

Start only after migration/grant/policy prerequisites and release approval:

```sh
docker compose -f compose.production.yaml up -d api worker web edge
```

Only the edge publishes ports. Apply the approved firewall/WAF/egress controls and
verify domain/TLS from an external network. Run full browser/API/data Recover
acceptance with synthetic labels, all negative authorization cases, intended-
environment load/cold-start checks and an isolated cloud restore exercise. Observe
trace continuity and deliberately deliver alerts to the named on-call owner.
Record availability, image digests, migration head and reviewer decisions. No
operational write or airline connection is enabled by this procedure.

## Rollback and database image changes

Keep the previous reviewed image digest and pre-change verified backups. Migration
0005 retains nullable legacy assurance and adds account-disable revocation; it
deliberately refuses downgrade. New readiness requires its column. Legacy NULL
does not authorize privileged OIDC use: require fresh verified MFA sign-in.
Directory operators require tenant-scoped session DELETE rights for the invoker
revocation trigger; a missing grant fails and rolls back the disable operation.
Do not restore an old image that bypasses the new assurance checks. Prefer a
forward fix or a separately reviewed compatible fixed image.

Changing a PostgreSQL image's OS may change libc/ICU collation behavior even within
the same PostgreSQL major. Back up first, quiesce traffic, inspect recorded/actual
collation versions, rebuild affected indexes and refresh database collation
versions before readiness/approval resumes. This was actually exercised for the
isolated local Debian 12-to-13 update (`docs/evidence/collation-maintenance.json`).
Do not apply that local measurement or a physical volume copy as production
migration/restore approval. Follow the intended managed provider's documented
upgrade/rollback process and verify preserved data and source-object hashes.

The local PostgreSQL runtime now uses patched Alpine/musl and a distinct
`postgres_alpine` volume. Existing Debian/glibc clusters must use logical
dump/restore into a new initialized cluster, not physical-volume reuse. The owned
workspace migration helper exercises old-volume rollback before allowing new
writes. After any new writer starts, it preserves the new volume on failure;
automatic old-volume rollback could discard accepted writes and is forbidden.
See `docs/evidence/runtime-migration-20261111.json` and the fault-injection report.
Those local drills do not authorize migration of a managed production database.
