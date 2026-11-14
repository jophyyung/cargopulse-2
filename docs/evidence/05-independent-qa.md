# Independent release QA

QA STATUS: BLOCK (baseline; remediation/retest pending).

Review baseline: `069c9d43e7c271ac351dd35829e0fb7a5a52206f` on isolated
`review/l1-gates`. This reviewer did not author implementation changes. Only
`tests/release_qa/` and this report were changed. A separate third-layer maths
review was requested on another clean worktree at the same SHA after its
11 contract tests passed; its pending results are not counted here.

## Executed verification

The independent suite adds adversarial cases rather than treating the lead's
101 passing tests or browser flow as independent acceptance. Command:

```sh
CARGOPULSE_QA_WEB_URL=http://localhost:3000 \
PYTHONPATH=packages/contracts/python:services/api:services/worker:. \
"$QA_PYTHON" -m pytest tests/release_qa -q --tb=short
```

`QA_PYTHON` is the existing shared Python 3.12 virtual environment executable.
On 2026-11-10 the command exited 1: **4 failed, 8 passed**, 17.60 seconds,
one upstream Starlette/httpx deprecation warning. Full baseline output is
`tests/release_qa/baseline-output.txt`. Failures are required-invariant assertions,
not expected-failure markers. They must actually pass after remediation.

The two durable-job tests ran against PostgreSQL 18.6 using non-owner
`cargopulse_app` with tenant-directory writes revoked. Only the dedicated
`cargopulse_releaseqa_test` database on local port 55432 was truncated. It was
created separately and migrated to `0003`; neither the main application database
nor `cargopulse_backend_test` was modified. Other API tests use ephemeral SQLite,
which does not prove RLS or concurrent-transaction behavior. OIDC tests use real
JWT signatures with the existing recorded provider fixture, not an enterprise IdP.

The three live-web tests target the running Next standalone server on localhost
port 3000. Oversized and incomplete bodies are rejected before import, and the
suite creates no operational records in that main database. It verified seven
console routes in ordinary HTML and normal RSC requests require login, proxy
allowlisted methods/routes, >8 MiB chunked upload rejection (413), and an unfinished
chunked body's actual approximately 15-second deadline (408). A fresh connection
still obtained health 200. Partial prefetch shells can contain public route metadata;
these are not evidence of an authenticated page. Initial test assumptions about
Next prefetch redirects and reuse of a deliberately cancelled upload connection
were corrected after observing the actual protocol; those test-development
failures are not reported as product vulnerabilities.

Passing new cases additionally verify session-bound CSRF; immediate local-role
and identity revocation; inability to authorize with forged role/tenant headers or
OIDC claims; actual known import, policy, scenario, job and plan identifiers across
tenants including mutations and JSON/CSV/PDF exports; decision hash substitution;
and PostgreSQL lease fencing after a different worker reclaims an expired job.
The reclaimed worker wrote zero plans; a later valid owner completed exactly one.

## Findings

### CP-QA-001 — High — Import bypasses two-person policy publication

- Reproduction: `test_import_cannot_publish_arbitrary_unreviewed_policy`.
- Expected invariant: imported snapshots reference a tenant policy actually
  published through the approved review process. Supplied actor names cannot be
  treated as authenticated publication authority.
- Observed: a data steward supplies a new policy ID/version, `handling_seconds=1`,
  `authored_by=forged-author`, `approved_by=forged-reviewer`. Validation succeeds;
  commit returns **201** and creates a **PUBLISHED** policy row with those names.
  Neither a manager nor the second-manager publish route is used. The separate
  draft/publish self-review guard therefore does not protect this entry point.
- Impact: `domain.commit_import`, `/imports/{id}/commit`, policy registry and
  downstream approval policy checks. This is a synthetic-model authorization
  failure, not evidence of a real airline action.
- Required remediation: match imports against exact pre-published tenant policy
  hash/content; bootstrap only a code-owned development fixture policy; never
  auto-publish client-submitted policies as an import side effect.
- Gate: L1 security and policy governance. Blocks acceptance until retested.

### CP-QA-002 — Medium — Missing raw source artifact does not block approval

- Reproduction: `test_deleted_source_artifact_blocks_approval`.
- Expected invariant: missing or corrupted required source evidence is detected
  before approval, with a visible blocker.
- Observed: create/solve an eight-ULD synthetic scenario, delete the private raw
  import object, then approve with correct ETag and hashes. Response is **201**.
- Impact: private-object evidence retention and `domain.plan_blockers`.
  Immutable JSONB still contains the snapshot; this test does **not** establish
  corrupted physical assignments or complete loss of the source data.
- Required remediation: approval checks source-object existence and digest,
  failing closed on missing, corrupted or unavailable required evidence.
- Gate: L1 evidence/operational integrity.

### CP-QA-003 — Medium — Exhausted leases strand a scenario in SOLVING

- Reproduction: real-PG
  `test_exhausted_lease_retries_leave_scenario_recoverable`.
- Expected invariant: retry exhaustion yields a terminal visible failure and a
  supported safe retry, with no stale worker able to overwrite it.
- Observed: claim and expire the same job three times, then claim once more.
  Job becomes FAILED/LEASE_RETRY_EXHAUSTED, but scenario remains **SOLVING**.
  A new solve returns **409 SCENARIO_NOT_READY** permanently for that snapshot.
- Impact: `worker.claim_job`, scenario state/recovery.
- Required remediation: clear lease and mark the current/latest owning scenario
  SOLVER_ERROR when retries are exhausted, allowing an explicit new solve.
- Gate: L1 durable job recovery.

### CP-QA-004 — Medium — Wrong azp accepted with a single audience

- Reproduction: `test_single_audience_wrong_authorized_party_is_rejected`.
- Expected invariant: when an ID token contains an authorized-party claim, it
  matches the configured client, including a scalar audience.
- Observed: a valid signed token with `aud=cargo-client` and
  `azp=different-client` produces **302** and a server session. Only multi-audience
  tokens receive an azp check.
- Required remediation: check azp whenever present; continue requiring it for
  multiple audiences. This is a stricter validation/conformance gap, not proof
  that an arbitrary unsigned token or unknown issuer authenticates.
- Basis: [OpenID Connect Core 1.0, section 3.1.3.7](https://openid.net/specs/openid-connect-core-1_0.html#IDTokenValidation)
  recommends validating any present azp against client_id.
- Gate: L1 production identity verification.

### CP-QA-005 — High — Fabricated computed metrics survive validation and approval

- Reproduction: `test_false_computed_metrics_cannot_reach_approvable_export`.
- Expected invariant: COMPUTED indicators, denominators and lineage match actual
  assignments and immutable input. A physically valid plan cannot authenticate
  invented computed evidence.
- Observed: intercept only the optimizer return value, retaining all valid
  eight-ULD assignments. Change its first metric to value `0.873`, numerator
  `873`, denominator `1000`, an unrelated all-f snapshot hash, no data-source IDs
  and `invented-cohort`, retaining status COMPUTED. The independent validator
  returns **PASS**, plan remains **approvable**, JSON export returns **200** with
  the invented COMPUTED metric, and approval returns **201**. The actual cohort
  contains eight ULDs and the original numerator/denominator was 8/8.
- Impact: validator metric coverage, worker result persistence, plan review and
  all exports that serialize solver-supplied metrics. This demonstrates evidence
  corruption, not physically unsafe assignments or an external airline write.
- Required remediation: independently recompute/check supported metric formulas
  and input lineage before accepting computed evidence; reject/quarantine invalid
  output. Sharing the optimizer's calculation alone is not independent checking.
- Gate: L1 all-KPI recomputation and evidence integrity.

The extended suite, including this additional mutation and fixture-policy lookup
compatible with a reviewed registry, exited 1: **5 failed, 8 passed**, 17.45 seconds.
See `tests/release_qa/extended-baseline-output.txt`. Original 12-test results above
are retained as earlier evidence, not relabelled as a successful run.

A subsequent targeted expansion isolates eight metric mutations to prevent a
partial lineage-only fix from masking incorrect arithmetic: invented counts,
incorrect ratio alone, wrong snapshot hash, wrong policy hash, absent sources,
invented cohort, unsupported COMPUTED metric name, and AWB unit substituted into
an eligible-ULD rate. **All eight failed** on the baseline in 1.95 seconds; each
remained approvable and exportable as COMPUTED. See
`tests/release_qa/metric-mutation-output.txt`. No claim is made that the expanded
20-case entire suite was rerun in this targeted step.

## Additional review gaps and release boundary

`queue_solve` has no configured per-tenant pending-job cap or rate limiter in the
baseline, despite the API/security specifications requiring quotas. The tenant
advisory lock serializes commands but does not bound stored work. Fixed tenant
iteration in `claim_job` also admits potential starvation if the first tenant
remains continuously busy. These are static findings; this review has not measured
a production DoS, queue fairness distribution or load limit, and does not invent
an acceptance threshold. Explicit bounded quotas and adversarial load evidence
remain required.

The lead's local full-stack flow, production build, dependency audit and benchmark
results are recorded in `06-integration.md`; they are prior integration evidence,
not independently reproduced merely by linking that report. Container builds,
restores, telemetry and accessibility screenshots are separate lead-owned work.

No hosted L1 PASS is issued. Real enterprise OIDC/MFA, domain/TLS, cloud object
permissions/encryption, deployment load/accessibility, legal content review,
actual on-call ownership and intended-host availability remain external red lines.
L2 airline data/approved operational rules and L3 write-back authorization are
outside this synthetic local review. No external connection or airline write was
performed.

## Upgrade and seeded-tenant regression refinement

A further independent upgrade regression inserts a pre-existing PUBLISHED policy
with forged author/reviewer and no authenticated publication audit, representing
the old import path's persisted rows. On the baseline, re-import commits **201**;
`test_legacy_published_label_without_authenticated_review_is_rejected` therefore
fails. Matching a PUBLISHED row alone is insufficient publication authority after
an upgrade. The revised cross-tenant test also creates an actual uniquely named
A-only policy through separate manager publication, and checks that B cannot see
it while allowing B's own code-owned default seed. That case passes on baseline.
The targeted command executed these two cases: **1 failed, 1 passed**, 0.81s.
