# Security remediation integration milestone

Date: 2026-11-12. **Implemented and locally verified; public L1 remains BLOCKED.**
Source baseline: `1b003eb22427c784fe1b59fff6bfe650be120909` plus the integrated
security changes. This milestone changes actual application/runtime source; it
must not be described as unchanged e40c676 application bytes.

## Phase completed and implementation

The previous failing image gate was addressed with a real minimal Debian runtime
closure for API/web and patched official Alpine PostgreSQL. Copied OS libraries
retain original package/version/license metadata, CA/NSS/timezone/account support;
no shell/package manager is shipped by API/web. No ignore-unfixed or hidden-package
metadata technique is used. PostgreSQL starts nonroot with dropped capabilities.
The active database was logically restored into a new Alpine volume, not physically
reused; old-volume rollback ran before writes. A separate failure probe proves
post-start writes remain on the new volume. Old data volume/private backups remain.

Independent ASVS base triage reproduced CP-ASVS-001 weak-session privilege promotion
and CP-ASVS-002 disabled-session revival. Both are fixed. Verified issuer/ACR hashes
are retained/rechecked per privileged request; nullable legacy rows are not MFA.
Migration0005 revokes sessions transactionally on disable, sharing the creation
lock and respecting invoker permissions/RLS/rollback. Unsafe downgrade is refused.

Production cookie prefixes, stable read-only HMAC CSRF, expiry metadata forwarded
by Next, private-DOM removal and truthful logout failures are integrated. CSV
filename/extension rules, no-referrer/CSP and strict owned S3 SDK protocol XML
boundaries have actual regression evidence. No Python/npm package version,
canonical DTO or optimizer/independent verifier algorithm was changed. OS runtime
package changes are captured by the image-specific inventories/SBOMs.

## Commands executed and results

- Full native Python3.12.16 suite with BACKEND_TEST_DATABASE_URL,
  OBSERVABILITY_TEST_DATABASE_URL and CARGOPULSE_QA_WEB_URL=http://localhost:3113:
  **263 passed**, zero failures/skips/xfails, **87.16s**; one upstream warning.
  Raw `security-final/pytest.txt` and `pytest.xml` include 83 new backend cases.
- `CARGOPULSE_BROWSER_CHANNEL=chrome CARGOPULSE_E2E_URL=http://localhost:3000 npm run e2e`:
  **14 passed**, CLI **1.0m**, actual final main container stack. Five original
  Recover cases use real services; eight session cases label their failure/TTL/
  event/provider-navigation injections; one checks actual Chrome CSP/referrer.
  `security-final/browser-main.txt` is the full output.
- After saving source commit `97cc22cfe7f3cd3b2e560b3c02555b0dbce3d2f2`,
  the lead repeated all263 Python cases from a clean exact Git worktree:
  **263 passed,91.52s**, zero failure/error/skip and one upstream warning. Imports
  resolved to that worktree and it stayed clean before/after. Existing locked
  dependencies/isolated services were reused, not freshly installed. All31
  runtime Python/45 web inputs/packaging hashes bind that commit to the same
  deployed images. Raw evidence is in `security-final/clean-checkout`.
- Actual API/web Docker builds succeeded. Final API source hashes match all31
  Python files, migrations/contracts/generator/bootstrap. Forty-five web build
  inputs and packaging hashes are recorded in `runtime-source-hashes.json`.
- Trivy0.76.2 refreshed its database at 2026-11-12T05:30Z, then full/gate/SBOM
  commands on each exact final image returned0. The DB UpdatedAt is
  2026-11-12T01:03:48Z. `security-final/image-scan-verification.json` binds exits,
  identities, report digests and package detection; all ignore lists are empty.
- Fresh pip-audit and npm audit reported no known advisories in their checked
  environment/package scopes. Lock/SBOM scope remains separate from image scans.
- Standard and selected security Ruff, TypeScript, runtime contract export and
  generated TS comparison, local actionlint and all-profile production Compose
  configuration assertions passed. Production parsing used reserved placeholders
  and started nothing; hosted CI is unverified.

Exact final runtime identities:

- API/worker/migrate: `sha256:9cf0c09fa13a647693567599f5451ca519cf2047efe104c0c753d4ef3693be34`.
- Web: `sha256:863d7eced8da07b5970629c6dbcad1c466ae456b985af5abc122d09e99139d8f`.
- PostgreSQL: `sha256:07b174247e8b27ee2c6e66c8edd418b3f1d3de6907c27634f3e8ffb12bb1e1d3`.
- Redis: `sha256:fe9daae35cd4fd6ec22416aa4fe0cf6b3e36741e06ff45b9986253fe2a81c041`.

At the2026-11-12 scan, lower package findings: API44 medium/19 low/14 unknown; web43 medium/19
low/9 unknown; PostgreSQL none; Redis1 medium. Totals are **88 medium,38 low,
23 unknown**, not unique exploit paths or accepted risk. The refreshed database
added eight unknown-severity package findings compared with the earlier snapshot;
that snapshot is retained in `security-final/scan-20261111`. All149 current lower
findings are listed for accountable triage. The proposed deadline/cadence/ownership
policy remains a draft pending owner acceptance, with no invented due dates.

## Actual migration, recovery and independent evidence

`security-final/local-schema-promotion.json` records ordinary 0004-to-0005 upgrade
in21.590s: all other table digests, old session values/NULL assurance and private
object hashes preserved before new traffic;12 FORCE-RLS tables, nonowner app and
no app directory-update permission. `runtime-migration-20261111.json` separately
records the earlier29.817s logical OS transition, not a production RTO. The
migration fault probe retains accepted session/audit rows after post-start failure.

Final Redis-outage/API/worker restart: **PASS26.563s**, actual durable job/session,
independent PASS and idempotent exact decision preserved. Fresh quiesced restore:
15 table counts/digests and11 object SHA values matched; all11 import references
restored; sessions/transient work reconciled, proposals stale. Current pending-job
count was0 and is not described as a nonzero cancellation. A final-image ASGI app
using the restored DB and only a new restored-object volume read11 scenarios
across two tenants and blocked23 stale plans. See RESTORE_DRILL.md.

Final offline second-agent artifact review checked API9,251 and web1,869 manifest
hashes, all links,150/11 ELF files and381/33 static dependencies,18/9 original
Debian records/licenses, NSS/CA/timezone and nonroot permissions. It found no
missing artifact/dependency or setuid/gid entry and never started a container.
This is separate from actual runtime execution. Safe raw evidence/report22 are
retained; review-created containers were removed. Main/runtime source binding is
independently recorded by the lead, not implied by that manifest review.

Final exact-image fresh-volume install/operator acceptance is in evidence23.
Its author/scope and every harness retry are explicitly identified there; it is
not a claim of hosted/new-host provisioning or independent frontend security
review by that frontend's author. The earlier e40c676 installation/numerical
review remains historical and is not relabelled as current-source acceptance.

## Failed checks and limits

The first full run had259 passes/4 failures from a frozen-migration test's stale
column/head expectations and two downstream schema failures. The corrected test
still checks the entire historical schema, now explicitly excludes later columns
and checks head0005/nullable assurance; all263 pass. The initial candidate browser
run had13 passes/1 failure because Chrome represented no referrer as an empty
string. Requiring no referrer content fixed the harness; final main14 all pass.
The first restore-ASGI probe used unsupported GET/scenarios (405); corrected
events-feed probing passed. Wrong-PYTHONPATH export, missing maintenance-profile
assertion target, optional inspect field, initial native build/copy, runtime CA
and SDK guard-ordering failures are documented; none is counted as a pass.

Two agent usage interruptions and a failed Luna coverage invocation delivered no
completion at those points; resumed work is recorded only where actually executed.
These boundaries are not blanket certification. Browser event/TTL/provider
injection is not native BFCache, full-duration session or live IdP acceptance.
Protocol XML tests use recorded transport; no real S3/IAM/SSE/TLS was accepted.
The original585-plan native synthetic benchmark was not rerun on the new images.
Its unchanged algorithm source and historical measurements remain separately bound.

ASVS triage preserves all345 canonical controls and unique notes:126 bounded,
57 not assessed,119 external,43 not applicable. Bounded partial evidence is not a
passed control. Fresh action-time step-up, adaptive context and the wider local
L2/L3 backlog remain open, as do owner acceptance, real enterprise IdP, intended
hosting/TLS/storage/encryption/egress, delivered alerts, cloud restore/load,
hosted CI, legal/retention and release approval. Protect/external writes remain
disabled. No GitHub push, public deployment, paid account or airline connection.

## Evidence-only follow-up on2026-11-13

The same immutable images were rescanned against refreshed Trivy data:
four HIGH/CRITICAL gates passed again. Refreshed Python/npm package audits found
zero known advisories in their scopes. Current lower package findings total
103 medium,38 low,8 unknown (149 package findings); advisory reclassification
does not represent a source fix or accepted risk. Earlier scan snapshots remain
under `scan-20261111` and `scan-20261112`; the current full scans/SBOMs, DB metadata,
exit results and reconciliation are in `security-final`.

The 2026-11-12 clean Git worktree run remains263 passed/91.52s, with no errors,
failures or skips and one upstream warning. Its import/source/image binding and
clean-before/after status are preserved in `security-final/clean-checkout`.
Application source has not changed since commit97cc22c; this follow-up changes
only reports and evidence. Main login/readiness returned200 and no public-release
or hosted-infrastructure acceptance was performed.
