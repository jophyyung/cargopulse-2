# PostgreSQL runtime remediation

Date: 2026-11-11. Source base: `1b003eb22427c784fe1b59fff6bfe650be120909`.
Scope: `infra/Dockerfile.postgres`, isolated local image/security/runtime probes,
and this report. No application contracts, Compose files or historical security
reports were changed. No existing application database/volume was mounted, no
host SQL port was published, and no remote publication/deployment was performed.

## Image provenance and change

The Dockerfile now uses the official PostgreSQL 18.6 Alpine 3.24 image, pinned to
OCI index `sha256:123b17998ccaf47e53b502e8c6a1e79afd8f579c6f3eec83c563da026f957395`.
The tested Linux ARM64 manifest is
`sha256:c935aff069a7bbe5c286411a08e9678850d79be7848b190a0e4637b266478626`.
The registry metadata points to official-image source revision
`e00e1bd34ec5c8a8e7ad89b273b3d42efaf6d5bc`, directory `18/alpine3.24`.

The unmodified package set in that pinned base was not scanner-clean. The first
derived image (only removing gosu) had 53 detected Alpine packages and 18 HIGH,
0 CRITICAL, 7 MEDIUM and 1 UNKNOWN findings. The raw initial report is retained.
The Dockerfile applies available Alpine updates with `apk upgrade --no-cache`:

- `krb5-libs`: `1.22.2-r1` to `1.22.3-r0`.
- `libxslt`: `1.1.43-r3` to `1.1.43-r4`.
- `zlib`: `1.3.2-r1` to `1.4-r0`.

These versions match the official Alpine 3.24 security database. Package updates
use the Alpine repositories configured in the pinned base. Their contents can
change on later builds: the base digest alone does not reproduce the final image.
Bind deployment and rescanning to the built ImageID/registry digest and retained
package inventory; do not infer scan equivalence from the Dockerfile or tag.

`USER postgres` remains explicit. The unused standalone gosu binary and `/bin/su`
command link are removed. BusyBox itself remains, including compiled applets;
removing the link does not remove BusyBox's internal `su` implementation. The
runtime inspection checks that BusyBox is not setuid and the database process
runs as UID/GID 70 with no effective capabilities under `no-new-privileges`.

## Actual scan and runtime evidence

Final image: `cargopulse-pg-remediation:18.6-alpine3.24`.
Final ImageID: **sha256:07b174247e8b27ee2c6e66c8edd418b3f1d3de6907c27634f3e8ffb12bb1e1d3**.

Trivy 0.76.2 actually scanned the final local image and detected Alpine 3.24.4 and
53 installed APK packages. Full-severity vulnerability output has **0 findings**;
the separate HIGH/CRITICAL gate with `--exit-code 1` exited 0. Scans use an empty
ignore file (`--ignorefile /dev/null`), with no `--ignore-unfixed`, severity waiver
or suppression. The database metadata records `UpdatedAt`
`2026-11-10T19:01:23.081219346Z` and download time
`2026-11-11T11:09:32.528963Z`.

`libxml2` is still installed and detected as `2.13.9-r2`. The final Alpine scan
does not report the historical Debian `CVE-2026-6653` finding. This is a bounded
scanner result using Alpine advisory data, not independent proof that every
upstream libxml2 issue is fixed. PostgreSQL is compiled from official upstream
source in this image; APK package detection is not exhaustive coverage of that
source or every compiled binary. No language-specific package files were detected.
This result does not clear API/web images or the remaining release gates.

Actual runtime probes used a unique internal Docker network, fresh named volumes,
no published host port, capability drop `ALL`, and `no-new-privileges:true`:

- The official entrypoint initialized a clean volume while already running as
  `postgres` (UID/GID 70); PID 1 and database child processes were nonroot.
- PostgreSQL, `psql`, `pg_dump` and `pg_restore` reported version 18.6.
- The stored administrator password verifier and the remote-all host HBA rule
  were SCRAM-SHA-256. An actual network-alias TCP connection with the correct
  password succeeded; missing and incorrect passwords were rejected. Default
  Unix-socket/loopback trust rules are still present in the official initdb
  configuration; the test does not claim local socket password enforcement.
- The existing API image
  `sha256:9f098864022455d0f7d9889554a5fe71382ad3a13eef07e5da88906d5f4e3861`
  executed the real development bootstrap against the isolated Alpine server.
  Migrations reached `0004`, development seeding succeeded, `cargopulse_app` was
  non-superuser/non-BYPASSRLS, and all 12 tenant tables had forced RLS enabled.
- `pg_dump -Fc` and `pg_restore --exit-on-error` round-tripped that migrated
  database into a separate empty database, retaining revision `0004` and a
  three-row probe including `香港` and `Ångström`.
- A database container restart retained the three probe rows.
- A separate clean-volume initialization without `POSTGRES_PASSWORD` exited 1
  with the official password-required error.
- All probe-created containers, networks and volumes were removed afterward.

The first probe had an incorrect assertion about the number of default loopback
trust HBA rules; PostgreSQL had initialized correctly. The retained failed report
shows this assertion. The corrected probe verifies the remote-all SCRAM rule and
actual missing/wrong-password rejection. The final probes were rerun after the
final image change. The dump/restore test above uses two databases on the candidate
server; it is not an existing-data glibc-to-musl cutover or full application E2E.

## Existing-data migration and rollback

The official PostgreSQL 18 image keeps `PGDATA=/var/lib/postgresql/18/docker` and
the volume at `/var/lib/postgresql`, matching this repository's Compose mount.
Matching paths and major versions do **not** authorize reusing an existing Debian
data directory under Alpine. glibc and musl locale/collation implementations differ;
the Alpine probe databases report libc provider `c`, `en_US.utf8`, and no recorded
collation version. Identical locale names do not establish identical ordering.

For an existing deployment, stop/fence application and worker writes, take a
verified logical dump and record source schema revision, row counts, object hashes,
roles/grants, locale/provider/version and relevant collation-dependent behavior.
Keep the original Debian image and original volume unchanged. Initialize a new
Alpine volume, explicitly review the target database locale/provider, and restore
logically into the new database. Provision/verify the non-owner role separately;
an ordinary database dump does not include global role definitions. Restore
schemas, data and indexes under the target library, fail on restore errors, then
verify RLS, constraints, unique indexes, text ordering and case conversion where
used, application flows, immutable history and object references before cutover.
Refreshing collation metadata alone does not rebuild invalid indexes or validate
changed semantics. Do not use a filesystem copy or mount the old data volume.

Rollback before accepting new writes means restarting the preserved Debian image
against its original volume and restoring the original application wiring. After
new writes, switching back loses those writes unless a separately validated
logical reverse-migration/reconciliation is performed. Retain both volumes and
the private backup until acceptance; this task has not performed the cutover.

## Reproduction and local machine reports

Reports are intentionally ignored local machine artifacts, rooted at
`.local/postgres-remediation/` in the `runtime-postgres` worktree:

- `official-index.json`, `official-index-digest.txt`,
  `image-inspect-official-base.json`, `image-inspect-cargopulse-pg-remediation.json`.
- `build-initial.log`, `build.log`, `package-inventory.txt` and
  `alpine-secdb-main.json`.
- `trivy-postgres-initial.json`, `trivy-postgres-full.json`,
  `trivy-postgres-gate.json`, `postgres.cdx.json`, Trivy logs and
  `trivy-cache/db/metadata.json`.
- `runtime-probe-initial-failed.json`, `runtime-initial-failed.log`,
  `runtime-probe.json`, `runtime-result.json`, `runtime.log` and `probe.py`.
- `evidence-manifest.json` records report hashes and the final image binding.
  The local dump and private generated probe credentials are not release artifacts.
  Intermediate results before the final `/bin/su` link removal use
  `before-su-removal-` names and must not be mistaken for the final image results.

Build: `docker build --pull -f infra/Dockerfile.postgres -t cargopulse-pg-remediation:18.6-alpine3.24 .`.
Full scan: `trivy image --scanners vuln --ignorefile /dev/null --list-all-pkgs --format json --output trivy-postgres-full.json cargopulse-pg-remediation:18.6-alpine3.24`.
Gate: `trivy image --scanners vuln --ignorefile /dev/null --severity HIGH,CRITICAL --exit-code 1 cargopulse-pg-remediation:18.6-alpine3.24`.

Official sources checked on 2026-11-11:

- [Official PostgreSQL image supported tags and usage](https://hub.docker.com/_/postgres).
- [Official image metadata and exact source revision](https://github.com/docker-library/official-images/blob/master/library/postgres).
- [Pinned upstream Alpine 3.24 Dockerfile](https://github.com/docker-library/postgres/blob/e00e1bd34ec5c8a8e7ad89b273b3d42efaf6d5bc/18/alpine3.24/Dockerfile).
- [Official Alpine 3.24 security fixes](https://secdb.alpinelinux.org/v3.24/main.json).
- [PostgreSQL 18 collation support](https://www.postgresql.org/docs/18/collation.html).
