# Ops 02 — Formal Release and Pilot Gates

## Gate L0 → L1: publishable software (synthetic data)
**Fail any red-line item and do not publish.**

### Product
- [ ] Accessible authenticated Next.js web frontend with complete navigation and key operations.
- [ ] Real FastAPI services, durable database, solver jobs and immutable decisions; no fake state or static hard-coded scorecards.
- [ ] `SYNTHETIC/NOT CONNECTED` badges on all simulated operational screens and exports.
- [ ] Controller can create/read/solve/review/approve-in-app/reject/escalate; no external writes.
- [ ] Data Steward can validate/import safely; audit reports and policy revision visible.
- [ ] Recover full flow passes e2e; Protect may be feature-flagged until ready and must not be advertised if unfinished.

### Safety and math
- [ ] No unsafe candidate admitted when gate FAIL/UNKNOWN.
- [ ] Independent validator passes across standard/mutated property test suite; corrupted answers are blocked.
- [ ] Solver explicitly differentiates OPTIMAL vs FEASIBLE vs NO_FEASIBLE vs ERROR, tracks wall time and gap.
- [ ] R-VaR correctly labelled operational marginal urgency, not a statistical VaR estimate.
- [ ] All KPIs include correct AWB/ULD denominator, time window, evidence tier and source; all percentage claims recomputed.
- [ ] No unverified synthetic performance copied from pitch as actual program output.

### Security
- [ ] OIDC, auth/role/tenant enforcement tested, no default credentials in prod.
- [ ] TLS, secrets manager, object storage private, data encryption, no raw PII in logs.
- [ ] OWASP ASVS 5.0.0-based checklist and API BOLA tests reviewed, scanner findings triaged.
- [ ] Public synthetic deployment contains **no** unauthorised airline data, logos or connections.
- [ ] User privacy/terms/data handling content published and appropriate legal review done.

### Operations
- [ ] CI green, reproducible lockfiles, migrations, image SBOM and vulnerability report.
- [ ] Staging load, Playwright and accessibility smoke pass; backup/restore exercise logged.
- [ ] Monitoring/alerting works, on-call ownership and incident rollback documented.
- [ ] Domain and product availability publicly verified using intended hosting.
- [ ] Deployment README tested by second person/agent following from scratch.

## Gate L1 → L2: authorised read-only airline pilot
- [ ] Signed sponsor/data-owner permission, security/privacy/DPA and region decisions.
- [ ] Confirmed source credentials and documented API/data fields, scoped read-only.
- [ ] Air cargo domain sign-off on aircraft/ULD, DG, cold chain, customs, handling and final load-control responsibilities.
- [ ] Historical replay with real permitted de-identified events and **time-causal** cutoffs; compare existing actual processes fairly.
- [ ] Pilot quantitative targets agreed (e.g. increase re-protection of eligible ULDs +3 percentage points, reduce controllable offloads ≥20% with no lower chargeable weight), not presented as historical fact.
- [ ] Security assessment, independent validation, operational training and rollback drills completed.
- [ ] Shadow-only UI labels and notification suppression verified; controller remains final authority.

## Gate L2 → L3: any operational write-back
- [ ] Explicit technical and legal operational authorisation; provider supports scoped write endpoints.
- [ ] Independent safety and security review; load-control/dispatch signoff and defined liability.
- [ ] Maker/checker authority, optimistic concurrency, provider idempotency, response acknowledgement, reconciliation and compensating actions.
- [ ] Rollback/recovery for partial operations, no duplicate bookings or physical load requests.
- [ ] Approval by partner change board in production window; monitored limited rollout with kill switch.

## Evidence to include with release
`RELEASE_NOTES.md`, `TEST_REPORT.md`, `EVIDENCE_CLAIMS.md`, `SECURITY_REVIEW.md`, `SBOM.json`, `DEPS_LOCK_SUMMARY.md`, `PILOT_SCOPE.md` (where applicable), `RESTORE_DRILL.md`, screenshots, JSON benchmark raw files, policy/solver hashes and signed reviewer decisions.
