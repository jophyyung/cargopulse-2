# Independent minimal-runtime artifact review

Date: 2026-11-11. Result: **PASS within the artifact checks below**.
No new material artifact defect was found. This is not a complete security
assessment, vulnerability-scan verdict, release approval or application E2E test.

## Exact inputs and isolation

The review used these immutable local image IDs directly, without resolving a
mutable tag:

- API: `sha256:6965d4eb375c0d1d24b68d040e7cab3b8344d91913ab5e26c8975eb15fd3e62b`.
- Web: `sha256:0fa03daf4fefd8cbcd6a4b4223cdddbd52706faed77110c2a03638e0b1eb0952`.

The root assembler source was read only and matched SHA-256
`afc35320e1c0c0b305620438bc0c2a49e05fdd12baef94d3e2b34e92c337bae1`.
It collects the copyright-package dependency closure to a fixed point before
emitting the selected original Debian status blocks.

For each fixed image, the reviewer created a uniquely named container on network
`none`, inspected its image binding and `created`/not-running state, and exported
its filesystem. Neither container was started. All review-created containers were
removed afterward. Existing services, volumes, data and root source were untouched.
The earlier review's mutable-tag-derived API artifact was not reused.

## Actual results

- **API:** all **9,251** regular-file hashes listed in
  `/usr/share/cargopulse/runtime-files.json` matched the exported bytes, after
  resolving filesystem links. Its **68** symlinks/hardlinks were checked.
  All **18** `system_packages` had corresponding installed Debian status records,
  including license-only `gcc-14-base`. All 19 manifest entries under `/lib` and
  `/usr/lib` had a retained Debian package origin and status record.
- **Web:** all **1,868** manifest regular-file hashes matched. Its **59** links
  were checked. All **9** `system_packages` had corresponding installed Debian
  status records, including `gcc-14-base`. All 9 manifest entries under `/lib`
  and `/usr/lib` had a retained Debian package origin and status record.
- Every package origin named by either manifest resolved to a status record with
  its package name, version and architecture. Copyright files were present for
  every selected system package. Python's installed `LICENSE.txt`, installed
  package license files and Node's `/usr/local/LICENSE` remain in their respective
  runtime artifacts. This review found no copied OS library whose original
  package/version metadata had been discarded.
- `/bin`, `/sbin` and `/lib` resolve to `usr/bin`, `usr/sbin` and `usr/lib`.
  API's `python -> python3 -> python3.12` chain resolves completely.
  The only link whose target is outside the exported image is the expected
  `/etc/mtab -> /proc/mounts` in each export. It requires the normal container
  runtime proc mount; there are no unexplained dangling image-file links.
- Both exports contain the CA certificate bundle, OpenSSL configuration,
  `UTC`/`Etc/UTC` zoneinfo, passwd/group and NSS configuration. NSS explicitly
  selects `files dns` for hosts. The bundle is nonempty and exceeds 100 KB.
- API is configured as `10001:10001`; web is configured as `node`, mapped to
  UID/GID 1000 in its passwd/group files. All exported regular files and their
  parent directories permit the configured runtime user to read/search them.
  `/tmp` is `1777`; `/var/lib/cargopulse/objects` is `0700`, owned by
  `10001:10001`. Web does not receive access to that API-only private directory.
- No executable command named `sh`, `ash`, `bash`, `dash`, `busybox`, `apt`,
  `apt-get`, `apt-cache`, `dpkg`, `npm`, `npx`, `corepack`, `yarn`, `yarnpkg`,
  `pip`, `pip3` or `pip3.12` was found anywhere in either exported filesystem.
  Python's `pip` package/module was absent as well. Absence of these maintenance
  tools does not prevent Python/Node from executing code and does not establish
  complete security certification.

The initial validator treated `/etc/mtab`'s proc target as an ordinary missing
image file. Its raw report is retained. The validator was corrected to classify
that exact runtime-mount link explicitly, then both fixed artifacts were exported
and checked again; no runtime source or image was changed for that correction.

## Evidence and reproduction

Ignored machine evidence lives in the review worktree:
`.local/minimal-runtime-review/minimal-runtime-review.json`. It records the exact
image IDs, Docker command exit codes, never-started container state, removal
commands, export hashes, manifest/status hashes, package/version records, link
targets, library origins, permissions and check results. The initial proc-link
classification is retained as
`minimal-runtime-review-initial-proc-classification.json`.

The local checker is `.local/verify-minimal-artifacts.py`; its exported filesystem
inputs are `api-rootfs.tar` and `web-rootfs.tar` in that evidence directory.
It reads `docker image inspect <fixed-id>`, creates an unstarted review container,
uses `docker export`, verifies the archive without extracting it into the host
filesystem, and removes only its own container in a `finally` block.

## Explicit limits

This review verifies manifest-listed bytes and their artifact metadata. The
manifest does not hash itself, generated account/NSS/status files, or API source
copied after assembly; those generated files were inspected separately where
described above. Hash agreement proves consistency with the embedded manifest,
not independent authenticity of every upstream source. Language-distribution and
wheel/npm provenance still depends on the pinned build inputs and lockfile/build
evidence.

No container was started, so ELF loading, dynamic `dlopen` paths, DNS, HTTPS,
calculation, image decoding, application E2E, database compatibility and restore
behavior were not rerun here. The lead separately reported real API and Node
runtime probes; those are separate evidence and are not counted as this review's
execution. No new vulnerability scan was performed in this review, and retained
Debian metadata alone is not a scanner-clean claim. Other release gates remain
separate.
