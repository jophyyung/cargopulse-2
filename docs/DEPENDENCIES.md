# Dependency and image provenance

Versions were resolved from official package registries on 2026-11-10 after reading
official framework documentation. `uv.lock`, hash-checked `requirements.lock` and
`package-lock.json` are canonical. Do not install floating production dependencies.

Python 3.12.16, Node 24.22.2, Next.js 16.4.6, React 19.3.1, FastAPI 0.162.2,
Pydantic 2.14.3, SQLAlchemy 2.1.8, Alembic 1.20.1 and highspy 1.15.1 are the
selected compatible matrix. Exact transitive versions and hashes are in lockfiles.
Framework documentation was checked against current APIs; an unsupported FastAPI
constructor argument was caught and fixed by the contract test.

Python/FastAPI/Pydantic/SQLAlchemy/HiGHS/Next/React use permissive licenses;
psycopg is LGPL-3.0-only, Hypothesis (development) MPL-2.0 and Authlib BSD-3-Clause.
The generated SBOM includes the actual installed distributions rather than an
invented package count. Redis 8.x has an RSAL/SSPL/AGPLv3 choice; the native 8.2.3
fixture is separate from the current pinned 8.2.11 container. Distribution/hosting licensing needs owner review
before release. No licensed airline safety manuals are embedded.

Official OCI index digests were fetched from Docker Registry on 2026-11-10 for
Python, Node, PostgreSQL, Redis and Caddy. Dockerfiles/Compose pin those digests.
Digest existence is not a successful image build, container vulnerability scan,
signature verification or proof that a running deployment uses the image.

Local PostgreSQL: official Postgres.app v2.9.6 PostgreSQL 18.6 downloaded from
https://github.com/PostgresApp/PostgresApp/releases/download/v2.9.6/Postgres-2.9.6-18.dmg
and extracted under ignored `.local/tools`. Redis source:
https://download.redis.io/releases/redis-8.2.3.tar.gz . Both bind loopback only.
The private local development database uses trust authentication and is not a
production configuration. No machine-wide application or service was installed.

Sources: https://nextjs.org/docs/app/getting-started/installation ,
https://fastapi.tiangolo.com/release-notes/ ,
https://docs.sqlalchemy.org/en/21/intro.html ,
https://ergo-code.github.io/HiGHS/dev/interfaces/python/example-py/ ,
https://pyjwt.readthedocs.io/en/stable/usage.html .

## Runtime remediation after actual image scans

The first images used Python 3.12.14/Node 24.14.0 on Debian 12. Actual Trivy
0.76.2 scans identified OS and bundled package-manager findings. The runtime
images now pin official Python 3.12.16/Node 24.22.2 Debian 13 indexes, apply
available distribution updates, and omit npm/Corepack/Yarn from the web runtime.
Build dependencies remain locked; a scanner report is bound to its ImageID, not
just a mutable local tag. Initial reports are preserved with `-initial` names.
Those initial Debian HIGH/CRITICAL findings are preserved as historical reports.
The later exact-image gates pass after the minimal-runtime/Alpine changes below;
any new HIGH/CRITICAL result continues to block the gate.

Official runtime references: https://www.python.org/downloads/release/python-31216/
and https://nodejs.org/dist/index.json . Image index digests are in Dockerfiles.
The local Node download was checked against the official SHASUMS256.txt. Python
3.12.16 was downloaded from Astral python-build-standalone release 20261026 with
SHA-256 `fbf4afef53c2a6b72bb741bc06d5671a9dfaf87bd84e5aa73ac9b3d0d589f14e`.
The installed uv 0.12.19 does not yet resolve that macOS patch automatically;
`uv sync --frozen --python /path/to/python3.12` uses an installed interpreter.

Docker was actually built and run using a task-local Colima 0.10.3/Lima 2.3.0
virtual machine (2 CPUs, 3 GiB RAM, no host project mount or SSH agent). The VM
created its Docker socket under `~/.colima/default` and a normal Colima cache;
CLI configuration and downloaded tools are isolated under ignored `.local/`.
This is local container evidence, not production infrastructure verification.

## Final minimal-runtime profile

`infra/assemble_runtime.py` copies the actual Python/Node ELF closure, retained
language packages/web standalone files, CA/NSS/timezone/account data, licenses and
original Debian package status records into a scratch final image. The API is
PostgreSQL-only: sqlite3, Tk, curses/readline and unused _uuid native bindings are
not included; uuid's Python fallback was actually tested. No shell, pip/npm or
package-management command is shipped in the API/web runtime. Maintenance uses
Python tooling and separate database commands; this is not a general Python image.
The original package inventory stays visible to Trivy instead of deleting scanner
metadata. The independent final hash/link/ELF review is evidence22.

PostgreSQL pins official 18.6-alpine3.24 and applies available APK fixes. It starts
as UID70 with dropped capabilities; standalone gosu and the su link are removed,
but BusyBox's compiled applets remain. The old glibc data directory was not reused:
logical restore initialized a new `postgres_alpine` volume, with the original kept.
See evidence13 and the actual local migration/failure-preservation reports.

Current pip/npm audits, full image scans, separate HIGH/CRITICAL gates and image
CycloneDX files are under `docs/evidence/security-final`. Four gate exits are zero
without ignored or unfixed waivers; lower findings and scanner coverage limits
remain explicit. DB metadata and exact ImageIDs bind the reports. Any future rebuild
or SDK update must repeat the relevant source/transport/runtime/security checks.


The test-created Lima home was later moved atomically from /tmp into ignored
`.local/lima`, preserving the disk inode and verified DB/object hashes across an
actual VM restart. `scripts/start_local_runtime.py` now uses this persistent home
and private Docker CLI configuration. A transient inactive user Docker context
created during the relocation was removed; the user's active context stayed
`default`. This is not a physical-host reboot test or production deployment.
