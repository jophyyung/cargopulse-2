# Backup and restore evidence

**Final local schema0005 drill: PASS. Production cloud RPO/RTO: NOT VERIFIED.**

On 2026-11-12 (Hong Kong), the lead quiesced the owned synthetic web/API/worker,
captured a mode0600 PostgreSQL custom-format backup and private object archive,
and restored into the NEW database `cargopulse_restore_drill_20261111_173403`.
The application database was preserved and services restarted afterward.

All 15 table row counts/digests matched before reconciliation. All 11 private
source objects matched their SHA-256 keys, and all 11 referenced imports had
restored objects. Restored sessions/OIDC flows were deleted, scenarios made
non-current and proposed plans stale; historical decisions, audit, snapshots,
policies and imports retained their digests. This run had zero pending jobs, so
its cancellation count is explicitly zero. The earlier 2026-11-10 run cancelled
one real queued job; it is retained separately, not recounted as a new result.

Measured backup: 11.256s; restore and initial verification: 1.147s; timed total
through reconciliation: 13.230s. These are quiesced local measurements excluding
subsequent application restart/readiness, not production RTO or PITR/online RPO.
The separate final Redis-outage/API/worker restart drill passed in 26.563s with
session, durable job, independent validation, exact decision and idempotency intact.

A subsequent actual ASGI TestClient application ran from the final API image,
using the restored PostgreSQL through its nonowner role and a NEW temporary volume
populated only from the restored archive. Neither probe container mounted the
original source-object volume. Anonymous access returned401; fresh development
login read 11 historical scenarios across both tenants, and all 23 stored plans
were non-approvable with STALE_PLAN and without missing-artifact/hash blockers.
The temporary volume was removed; the private host archive/extracted files and
restored database remain for inspection. Fresh login/audit writes occurred only
in that restored database after the original-history comparison.

An initial probe mistakenly used unsupported GET/scenarios and received405. Its
failure is preserved; the corrected probe uses the documented events feed. It
was a probe error, not an application fix or a passing security check.

Machine evidence: `docs/evidence/restore-drill.json`, `restored-api-probe.json`,
`runtime-durability.json` and raw outputs under `docs/evidence/security-final`.
The old reports remain as `*-20261110.json` and `*-initial.json`. Reproduce only
against an isolated development Compose project:

```sh
uv run python scripts/restore_drill.py
```

The tool temporarily stops the selected stack, creates a new database and keeps
private mode0600 backups under ignored `.local/backups` in a private directory.
The minimal API runtime uses Python tarfile rather than a shell/tar CLI. Local
private plaintext files do not establish encrypted managed backup compliance.
Never commit or distribute those backups or populated environment files.

The earlier glibc-to-musl local database migration is separate evidence: logical
restore into a new Alpine volume, identical history/object hashes and old-volume
rollback before any new writes. A later fault probe proved that post-start failure
retains accepted new session/audit rows on the new volume. The original glibc
volume remains preserved; never automatically roll it back after new writes.
Schema0005 subsequently migrated normally with all legacy session values retained
and no invented MFA context. See `security-final/local-schema-promotion.json`.

Production must use encrypted full backups plus managed PITR and an isolated
intended-region restore, verify source objects/history/permissions, revoke sessions,
reconcile work/outbox, require refreshed sources and route traffic only after
accountable acceptance. Targets remain RPO <=15 minutes and RTO <=4 hours until
measured there. This local ASGI probe is not external hosted HTTP acceptance,
managed cloud recovery, a physical-host reboot or a public release.
