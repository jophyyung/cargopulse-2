# Independent QA remediation

The independent second-layer review found five reproducible issues against commit
069c9d4. Its failing outputs are preserved in `tests/release_qa/`; they are baseline
failures, not the status of the corrected implementation.

- CP-QA-001: imports could publish arbitrary uploaded policies. Validation/commit,
  solve/worker and approval now require an exact registered policy plus authenticated
  independent publication audit. Legacy auto-published rows without that provenance
  fail closed. Only explicitly enabled development profiles accept the fixed
  code-owned synthetic seed; production never auto-publishes it. Fixture downloads
  select registered rules; drafts and reviewer publication remain separate commands.
- CP-QA-002: a lost source artifact did not block approval. Private object existence
  and a bounded SHA-256 read are checked before commit, work and approval. Missing,
  replaced or unverifiable objects block; the JSONB snapshot/history is preserved.
- CP-QA-003: exhausted leases stranded a scenario in SOLVING. Exhaustion now marks
  the current scenario SOLVER_ERROR, clears the lease and permits a new job without
  overwriting the failed job or decisions.
- CP-QA-004: single-audience tokens with an inconsistent authorized party were
  accepted. Any present `azp` must equal the configured client; multiple audiences
  additionally require it. Existing RSA/issuer/audience/nonce/MFA checks remain.
- CP-QA-005: legitimate assignments could carry forged COMPUTED metrics. The
  independent verifier now performs a separate bounded depth-first route search
  for the eligible ULD denominator and independently recomputes all four metric
  formulas, unit/scope/statistic and lineage. It does not call the optimizer's
  candidate builder or metric function. Unknown/missing/duplicate metrics fail
  validation. Eight individually mutated metric attributes are tested separately.

Additional resource controls: pending solves are capped per tenant (default 8,
configurable 1-128), admitted under the same transaction lock. A repeated command
with the same idempotency key returns the original job. Excess work returns 429
and Retry-After. A worker-local round-robin cursor rotates tenant polling; a process
restart resets this cursor, so this is not a global scheduling SLA.

Actual integrated verification before observability integration:

- Full Python suite with real PostgreSQL, Redis and live standalone boundary tests:
  **122 passed**, 53.95s, one upstream test-client deprecation warning.
- Focused optimizer/validator/QA semantic suites: **70 passed**, 3.20s.
- Independent revalidation of every archived benchmark proposal: **90/90 PASS**,
  21.403s total. This did not rerun the solver. Original benchmark latency predates
  the added metric verification and must not be presented as current runtime.
- Pending quota/idempotent retry has a separate actual HTTP regression; its output
  is included in the final integrated run. No simulated load test is claimed.

The review subagent stopped after its delivered evidence when the platform flagged
the subsequent resource-test turn as a possible cybersecurity risk. The delivered
findings remain valid; the lead continues functional regression tests directly.
This is not a completed external penetration assessment or a blanket L1 sign-off.


Final lead additions:

- CP-QA-006 (third-layer independent math review): a later candidate query could
  admit evidence observed after the immutable snapshot as-of. Candidate enumeration
  now requires proof observation and source provenance no later than snapshot time,
  matching the independent verifier. The later-query reproduction now passes.
- CP-QA-007 (lead configuration-transition reproduction): issued development
  sessions remained usable after the adapter was disabled or the application
  environment changed. Authentication now rejects those sessions immediately.
  Two original failing cases are preserved in development-session-baseline.txt.
- Readiness now fails on a reachable but unmigrated database; an empty-schema
  regression passes. The error path rolls back failed PostgreSQL transactions.
- Keyboard skip navigation now focuses the main landmark before sequential focus
  continues. A genuine failing browser reproduction was retained and corrected.
  Native macOS select-popup keyboard automation is outside Playwright control;
  focus/text/custom-tab keys are tested directly and native selection uses the
  documented selectOption API. This is not a full assistive-technology audit.

The final combined counts and actual outputs are in TEST_REPORT.md; the earlier
122-test/90-archive results above retain their original historical scope.
