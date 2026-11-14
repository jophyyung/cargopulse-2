# Final fresh-volume installation/runbook acceptance

Date: 2026-11-12. Result: **PASS for the bounded local installation and journeys
below, after the preserved operator-harness corrections**. Public release,
enterprise identity and hosted operations acceptance are not established.

This is second-person installation/runbook operator evidence for the lead's
backend/runtime integration. The operator also authored the frontend session
boundary, so the Chrome supplement is actual runtime execution, **not an
independent security review of that operator's own frontend implementation**.

## Exact application and isolation

The application tested was the following immutable local images, not mutable tags
or an assertion that the reviewer worktree base contains every final change:

- API, worker and migrate:
  `sha256:9cf0c09fa13a647693567599f5451ca519cf2047efe104c0c753d4ef3693be34`.
- Web:
  `sha256:863d7eced8da07b5970629c6dbcad1c466ae456b985af5abc122d09e99139d8f`.
- PostgreSQL:
  `sha256:07b174247e8b27ee2c6e66c8edd418b3f1d3de6907c27634f3e8ffb12bb1e1d3`.
- Redis:
  `sha256:fe9daae35cd4fd6ec22416aa4fe0cf6b3e36741e06ff45b9986253fe2a81c041`.

Docker inspection confirmed the running image identity exactly matched each
requested ID. The successful fresh initialization used project
`cargopulse-final-install-2`, `APP_BASE_URL=http://localhost:3116`, and only
`127.0.0.1:3116 -> web:3000/tcp` published. API, PostgreSQL, Redis and worker had no
published host ports. Before initialization, the project, network, project volumes
and port were absent; a local IPv4 bind probe also confirmed port availability.

The root `compose.yaml` was copied into a private reviewer directory without
editing its bytes. SHA-256:
`9e5a7bbdaff9bd7ffe4227fe07fe39afdc69d2d50aaf9437179699f4bf60adfb`.
An image-only override pinned all six services. Every Compose command used an
explicit project, project directory, private `--env-file`, copied Compose file and
image override. Startup used `up --no-build --pull never --wait -d`.

The first attempt used the worktree's `scripts/configure_local.py` to generate
private credentials. Its existing `.env` was not read or overwritten for the
second attempt: a unique private env file was generated using
`secrets.token_urlsafe(36)`. Both passwords differ from the first attempt; the
second env file is mode 0600. No main/candidate env file or secret was inspected.
Docker context overrides were removed only from the subprocess environment; no
user Docker context was activated or changed.

The official Redis image also creates an anonymous `/data` volume. The second
attempt permitted **only** that destination on its own new Redis container,
required a 64-hex anonymous name, and checked that the name was absent from the
complete metadata-only preflight volume-name snapshot. All other volume mounts
had to be the new project's exact PostgreSQL/object names; host bind mounts were
rejected. No existing volume was mounted or deleted.

Existing Docker/Colima and cached prebuilt images were used. This is not a cold
download, source-image build, new-machine setup or production hosting exercise.
The worktree supplied the unchanged frozen contracts/8-ULD fixture generator as
an HTTP client harness; the immutable images above identify the actual application.

## Fresh bootstrap and real HTTP results

- The migration service exited 0. PostgreSQL reported **migration0005**, all
  **15 public tables**, the new `authentication_context_hash` session column,
  the account-disable session-revocation trigger, **12 FORCE RLS tables**, and no
  invalid/unready public indexes. Ingest batches, scenarios and sessions were
  empty before the first login, confirming fresh business state rather than a
  reused database.
- PostgreSQL initialized/runs as Linux `postgres`, UID **70**; password encryption
  is SCRAM-SHA-256. A SQLAlchemy query executed inside the actual API container
  reported database user `cargopulse_app`, `rolsuper=false`, `rolbypassrls=false`,
  and **zero application-owned public tables**.
- Real HTTP development login as the pre-provisioned synthetic manager succeeded.
  Two JSON CSRF reads returned the same value. The real Next proxy forwarded
  positive `X-Session-Expires-In` metadata. The harness fetched JSON CSRF before
  authenticated POSTs and did not read a CSRF cookie name.
- A current **8-ULD** synthetic source used the real fixture endpoint's registered
  published policy. Validation returned **202**, commit **201**, scenario creation
  **201**, candidate read **200**, and solve admission **202**. The separate worker
  completed the durable job using HiGHS with a ten-second configured limit and
  baselines disabled. Returned solver status was **OPTIMAL**, independent validator
  status **PASS**, and the proposal was approvable. The client independently
  recomputed the canonical plan hash and matched the server's recorded hash.
- An authenticated manager `APPROVE_IN_APP` command returned **201** and
  `external_write_performed=false`. This was a harness-submitted record through
  the human-decision endpoint; it is not an actual human safety approval, airline
  dispatch or external operational write.
- JSON, CSV and PDF exports returned **200**, attachment dispositions and expected
  media types. JSON retained the same canonical plan hash; CSV carried the
  synthetic notice; PDF began `%PDF-`. Actual sizes were **8,223 / 3,088 / 4,810
  bytes**, respectively. Hashes and content types are in the JSON evidence; PDF
  layout was not visually reviewed.
- A separate `controller-b` session received **404 for eight real known-ID GETs**:
  scenario, candidates, job, plan, alternatives and JSON/CSV/PDF exports. Its
  decision POST for the known plan also returned **404**. Import read returned
  **403 at the role gate**; that result alone is not claimed as object isolation.
- The newly written private object was read inside the actual API container:
  **one file**, SHA-256 content equal to its content-addressed filename, mode
  **0600**. The source body and credentials were not logged.
- A full stop/start of this isolated project preserved the manager session,
  job-produced plan hash and **byte-identical exports in all three formats**.
  No schema reset, privileged app role or mutable image tag was used.

Snapshot hash:
`972a562c148ae63ab1e661fdd762c596ac6fefa368987042cfcce8d0f246b5e3`.
Plan hash:
`b63901d70787c5f3d61285640652867a03dd756781250fd56a7bf31de9ef305d`.
The scoped JSON retains the actual import/scenario/job/plan/decision identifiers
and method/path/status observations.

## Chrome supplement and timings

One real Chrome test passed on **http://localhost:3116**, reported as
**1 passed (6.3s)**. It signed in, viewed the console, checked that both tabs'
private draft nodes detached after sign-out, verified the server rejected the
revoked session, preserved unrelated storage, and confirmed fresh sign-in worked.
Its queued-storage-notification subcase explicitly injects a `StorageEvent`;
that subcase is not native BFCache acceptance. A separate disposable Chrome test
profile was used, with trace recording disabled. The lead's full 14-test run was
not rerun or added to this operator's test count.

Fresh initialization, SQL/HTTP journey, persistence drill and the first CLI
selection attempt took **47.047s**. The corrected Chrome-only start/test/stop
phase took **27.910s**, giving **74.957s active execution** across those two phases.
The observed second-project start to final stop was **277.765s**, including manual
diagnosis pauses. These are acceptance-drill durations, not solver benchmarks,
throughput results or an SLA.

## Preserved failures and corrections

No functional application source was changed during this acceptance task.

1. The first fresh project, `cargopulse-final-install` on port 3115, initialized
   but the operator's overly strict mount assertion rejected the official Redis
   image's newly created anonymous `/data` volume. **No HTTP business journey was
   executed in that attempt.** Its services were stopped. Its original FAIL JSON
   is published unchanged as `23-final-independent-install-initial.json`, SHA-256
   `4613976f27ab83495e876d933c84bc0bc5e12ef86b047288c46f2d67b3421493`.
   The revised harness required the precise new anonymous-volume ownership checks
   described above and used the absent second project/port; it did not reuse or
   delete the first project's volumes.
2. The second project's complete HTTP/DB/persistence acceptance passed, then the
   optional Chrome command returned `No tests found`. The `--grep` expression was
   anchored against a scenario name while Playwright searches a longer full test
   title. No browser test ran in that CLI attempt. Its FAIL JSON and output were
   preserved before correction. A corrected `--list` selected exactly one case.
3. The Chrome-only completion helper initially compared Docker's default short
   container IDs with full inspected IDs. That read-only guard stopped before
   starting any service. Its raw FAIL/output were preserved. Adding `--no-trunc`
   made the ownership comparison valid. Only the already-owned second stack was
   then started for the successful Chrome case and stopped again.

These are operator-harness errors, not application failures, and none is counted
as a passing check. The final PASS includes only the subsequently executed,
successful observations. Historical FAIL files were not edited into success.

## Final disposition and reproducible evidence

Both review projects are stopped. All six volumes created by these attempts were
confirmed still present: each project's `postgres_alpine` and `objects`, plus
its new Redis anonymous `/data` volume. `down --volumes`, volume deletion and
mounting existing data were never used. Main port 3000, candidate port 3113,
native test databases, and existing database roles were not operated or reset.
Database role/schema provisioning occurred only inside each fresh review database.
No commit, push, external service setup or public deployment occurred.

Primary evidence:

- `docs/evidence/23-final-independent-install.json`: final observations, exact image
  IDs, compose hash, selected container/mount metadata, SQL results, HTTP statuses,
  export hashes, Chrome result, history pointers and stopped/preserved disposition.
- `docs/evidence/23-final-independent-install-initial.json`: untouched first FAIL.
- Ignored `.local/final-install/20261112T053255Z/`: copied Compose/image override,
  mode-0600 private env, sanitized operation logs, export bytes, first Chrome
  selector failure, read-only ID guard failure and corrected Chrome output.
- The first attempt's private directory is recorded by its original JSON and
  retains its original result, traceback and original harness.
- Ignored `.local/final-install/accept.py` and `complete-chrome.py`: finite scoped
  harnesses. `chrome-corrected-list.txt` records one selected test before execution.
  `final-evidence-manifest.json` binds the final report and preserved raw evidence.

Every Compose command used the copied private configuration and explicit project
boundary, for example:

```sh
CARGOPULSE_PORT=3116 docker-compose \
  --project-directory /path/to/review-worktree \
  --env-file /private/attempt/install.env \
  -p cargopulse-final-install-2 \
  -f /private/attempt/compose.yaml -f /private/attempt/images.json \
  up --no-build --pull never --wait -d
```

Use the same prefix for `exec`, `stop` and `start`. The exact actual command arrays
are in the JSON; the display above intentionally contains no credential values.
Raw published JSON and selected logs were checked against both attempts' private
password values; neither password appears. Private env files and export contents
are not public release artifacts and should not be shared as generic project data.

No new image vulnerability scan, external penetration assessment, hosted CI,
real enterprise OIDC/MFA, production TLS/WAF, cloud storage/backup/monitoring,
intended-environment load, legal/retention acceptance or aviation certification
was performed. Those remain separate, unverified release conditions. Passing
this synthetic local install check does not authorize L1 public release or L2/L3
airline integration/write-back.
