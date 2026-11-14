# Independent Final Runtime Artifact Review

Date: 2026-11-12. Result: **PASS within the offline artifact checks below**.
No material artifact defect was found. No application/container was executed by
this review; this is not runtime E2E, a vulnerability scan, or release approval.

## Exact inputs and isolation

The review addressed these immutable local image IDs directly:

- API: `sha256:9cf0c09fa13a647693567599f5451ca519cf2047efe104c0c753d4ef3693be34`
- Web: `sha256:863d7eced8da07b5970629c6dbcad1c466ae456b985af5abc122d09e99139d8f`

The root assembler source was read only and matched the required SHA-256
`afc35320e1c0c0b305620438bc0c2a49e05fdd12baef94d3e2b34e92c337bae1`.
Both images identify as Linux/arm64 and declare no image volumes. Docker inspect
output was deliberately filtered to image identity, architecture, runtime user,
volume declaration and the newly created containers' lifecycle/network fields;
no environment values or running-service details were inspected.

For each image, `docker create --network none --pull never <exact-id>` created a
uniquely named temporary container. Both were verified `created`, not running,
PID 0, with zero StartedAt timestamps, network `none` and zero mounts. Their
filesystems were exported and inspected directly as tar archives without host
extraction. No container was started, and no network access, package installation,
database, service, volume, migration or functional source edit occurred.

The review-created container IDs were:

- API: `2b4e715015a144f49578236480bf79a208829576f7b8b8b9ccf9d7998cb28d73`
- Web: `35ff7f989aa6a76a7a1eded9ea47c6b19c01913e829f6fed8d3aae4d31c3262d`

Both were removed by ID in `finally` cleanup. A final Docker listing filtered
only to those two IDs returned no remaining container. Existing containers and
earlier worktrees were untouched.

## Actual results

- **API:** all **9,251** manifest regular-file hashes matched exported bytes after
  link resolution; all **68** symlinks/hardlinks were checked. All **18** selected
  system packages had retained installed Debian records with package/version/
  architecture, and corresponding copyright files. All **150** exported ELF
  regular files were covered by the runtime manifest. Their **381** `DT_NEEDED`
  edges and interpreter paths resolved to exported ELF files using the inspected
  RPATH/RUNPATH and runtime library paths. No extra loader-context inference was
  required and no ELF file lacked manifest coverage.
- **Web:** all **1,869** manifest hashes matched, with **59** checked links and
  **9** selected system-package records/licenses. All **11** exported ELF files
  had manifest coverage; their **33** `DT_NEEDED` edges and interpreter paths
  resolved. No missing static dependency or extra loader-context inference was
  found.
- The API's **18** OS ELF files and web's **8** OS ELF files under the merged
  `/usr/lib` tree each retain a Debian package origin and corresponding original
  status record. Both retained the license-only `gcc-14-base:arm64` record needed
  by the copyright dependency closure. No copied OS ELF was found whose original
  package/version metadata had been omitted.
- All links resolved within the export except the explicitly classified
  `/etc/mtab -> /proc/mounts` in each image. This exact link requires the container
  runtime's normal proc mount; it is not an unexplained dangling image-file link.
  `/bin`, `/sbin`, `/lib` merge into `/usr/bin`, `/usr/sbin`, `/usr/lib`; the API's
  `python -> python3 -> python3.12` chain resolves.
- Both exports retain the CA bundle, OpenSSL configuration, UTC/Etc-UTC zoneinfo,
  passwd/group and NSS configuration. The CA bundle is nonempty and larger than
  100 KB. NSS explicitly uses `files dns` for hosts. The AArch64 ELF interpreter
  `/lib/ld-linux-aarch64.so.1` is present through the merged library path.
- Python's installed `LICENSE.txt`, **72** installed Python package license/
  copying/copyright files, and Node's `/usr/local/LICENSE` are retained. All
  selected Debian package copyright paths resolve. These are artifact-retention
  checks, not independent upstream license/authenticity or legal conclusions.
- API's configured user is `10001:10001`, matching the exported `cargopulse`
  account. Web's configured user is `node`, matching UID/GID **1000:1000**.
  All exported regular files and their parent directories permit the applicable
  nonroot user to read/search them. `/tmp` is `1777`; the private objects directory
  is `0700`, owned by `10001:10001`.
- No setuid/setgid entry was found. No executable command matching the expanded
  shell/package-manager inventory was found, including sh/bash/dash/zsh/busybox,
  apt/dpkg/apk/rpm/dnf/yum, npm/npx/corepack/yarn/pnpm, pip/pipx/uv/poetry/pipenv.
  Python pip and ensurepip modules were absent. The exact checked command names
  and zero-match results are retained in the machine report.

## Reproducible evidence

Safe machine-readable evidence is under the review worktree's
`.local/final-runtime-review/`:

- `review-final.json`: complete final findings, exact image/container IDs,
  filtered Docker command outputs, lifecycle checks, cleanup, link targets,
  package/version records, permissions and ELF dependency/metadata inventories.
- `final-summary.json`: compact final result; `review.json` and `summary.json`
  preserve the initial completed export/check run before the added offline
  command-inventory/account checks.
- `run_review.py` and `archive_checker.py`: the exporter and reused prior review
  semantics; `offline_finalize.py` reruns the added checks against existing tar
  inputs without invoking Docker or executing ELF.
- `api-rootfs.tar`, `web-rootfs.tar`: actual exports; `cleanup-remaining-ids.txt`
  is empty, confirming cleanup of the review IDs.

Export SHA-256 values:

- API: `a138d8fdf89449e3f21f8aeb426e4838df17bd851bd978930a2410d6e3e7432e`
- Web: `9a778e131117eeb68b202c3c1500c16029541eb42b6ca68787e16a389d1dfaf7`

Embedded runtime manifest SHA-256 values:

- API: `a97de047092277fecfd5a3e5d548db1cb432006910c5602264ec281975e36bbf`
- Web: `7aa71dc579a1c700d960177d80004601de99cd90395426659e11de052869d2fc`

The first filtered Docker inspect attempt encountered an absent `Config.Volumes`
map key. No container was created by that failed attempt. The raw error is
retained as `initial-inspect-format-error.json`; the inspection template was
corrected to treat the missing optional key as null. This changed only the local
review tool, not an image or application source.

## Explicit limits

The manifest verifies packaged runtime files and web standalone files where
listed. It does not hash itself or generated account/NSS/status files, and it
does not establish a separate claim covering all API application source copied
after assembly. Generated files were inspected separately above; the integration
lead owns the separate API source-hash verification.

Manifest agreement proves consistency with embedded hashes, not independent
authenticity of every upstream build input. Debian records and language-package
licenses remain present, but this review did not fetch or authenticate upstream
packages, conduct a vulnerability scan, or establish trust-store freshness.

ELF checking was static: no binary was executed, no dynamic `dlopen` behavior,
symbol-version loading, DNS, TLS, Python/Node import, request handling, database
compatibility, application E2E or backup/restore was tested here. The parent's
separate runtime and application tests remain separate evidence. The absence of
maintenance command names is not a complete security assessment of Python/Node
execution capabilities. No commit or push was performed.
