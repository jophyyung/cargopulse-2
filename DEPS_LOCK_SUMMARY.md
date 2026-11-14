# Dependency and lock summary

Selected production runtime patches: Python 3.12.16 and Node 24.22.2. Python
requirements and npm workspace dependencies are exact-pinned; `uv.lock` resolves
platform wheels/sdists and `requirements.lock` exports production hashes for pip
`--require-hashes`. `package-lock.json` captures npm integrity/resolution. The
native test environment includes development tools; it is not the runtime image.

## Lock SHA-256

- `uv.lock`: `6cf85ec6567e4df1e6653971afd646926e70c986308804fd5c9b6a7f232bf248`.
- `requirements.lock`: `8af6fc3e1f738a7cf283ed74b5e3c7a1701f00ccb8cfbf4e610857be5f3e10e3`.
- `package-lock.json`: `cd68d52cb0ff9d4f170105366a40f075cea0d03df3980c7659261dd1866b64e8`.

The npm lock change restores missing libc metadata on 16 sharp optional-package
entries against each exact official registry version/integrity. No package version
or integrity changed. Linux builds explicitly select glibc; actual sharp PNG
processing was tested in the minimal runtime. See the retained metadata report.

`SBOM.json` inventories 176 Python-environment/npm-lock components, including
explicit development dependencies. The four `SBOM.*.cdx.json` files inventory the
actual API/web/PostgreSQL/Redis images, separately bound to image identities.
They are dependency inventories, not a guarantee of complete vendored-binary
coverage, licence clearance or absence of vulnerabilities.

OCI base indexes are pinned in Dockerfiles/Compose. Available OS updates are
applied during builds; OS package versions are captured by the image SBOM. A later
rebuild can receive newer distribution packages and must be rescanned/reviewed.
Promote the same approved immutable image digest rather than claiming every rebuild
is bit-for-bit identical. No registry image was published by this task.

Important licence boundaries: psycopg is LGPL-3.0-only; Redis 8.x offers
RSAL/SSPL/AGPLv3 alternatives; development Hypothesis and axe-core use MPL-2.0.
HiGHS, web frameworks and the Python libraries retain their upstream terms.
Distribution/hosting obligations require owner review before release. No licensed
aviation standards or official airline rule corpus is embedded.

Dependency sources, task-local tool hashes and runtime remediation are documented
in `docs/DEPENDENCIES.md`. Package audits and built-image reports have separate
scopes. All four current exact-image HIGH/CRITICAL gates pass, with lower findings
retained; the gate still blocks any future HIGH/CRITICAL result. Minimal-runtime
package/ELF/license retention is independently checked in evidence22. The runtime
contains PostgreSQL-only Python bindings, not general-purpose SQLite/Tk/curses/
readline support. Private SDK XML hooks require review before boto3/botocore upgrades.
