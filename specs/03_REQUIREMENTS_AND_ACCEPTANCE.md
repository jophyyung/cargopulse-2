# 03 — Prioritised Requirements and Acceptance Criteria

Each ID corresponds to a test, issue and traceable release gate. P0 means required for L1; P1 for the expanded pilot-capable product; P2 partner-dependent.

## P0 Functional
- **F-001 Identity:** OIDC login + MFA policy enforcement by IdP; named accounts and effective roles. Acceptance: unauthenticated APIs 401; wrong tenant 404/403; audit role transitions.
- **F-002 Tenant isolation:** all domain data requires tenant_id enforced at repository and DB policy where practical. Acceptance: cross-tenant ID tampering rejected across all endpoints and exports.
- **F-003 Scenario intake:** typed JSON and controlled CSV import with preview, row errors, dry-run and idempotent commit. Acceptance: malformed units, timestamps and duplicate source events rejected with line-level reason.
- **F-004 Evidence and freshness:** provenance and stale-state badges on *every* decision. Acceptance: missing capacity/cold-chain/DG clearance yields NEEDS_VERIFICATION and prevents unsafe “ready” state.
- **F-005 Recovery candidate generator:** eligible ULD–flight arcs with hard gates. Acceptance: impossible assignment absent before solve; explanatory exclusion reason code is visible.
- **F-006 Recover optimise:** asynchronous job with snapshot version, solver termination status, time budget and reproducible output. Acceptance: deterministic fixture, no over-allocation; an impossible case yields safe escalation.
- **F-007 Independent validation:** server-side validator re-evaluates all hard gates and aggregate constraints without trusting solver variables. Acceptance: mutate one solution to exceed capacity → validator fails, prevents approval.
- **F-008 Operator review:** compare plan, alternative route and baseline, all changed assignments, reason trace and no-path list. Acceptance: each change has evidence and at least one reason code.
- **F-009 Human decision:** authorised approval/rejection/escalation with reason and optimistic concurrency. Acceptance: approval cannot mutate external systems at L1/L2; stale solution rejected with 409.
- **F-010 Replan:** new event snapshot creates immutable run with stability penalty and respects freeze windows. Acceptance: old decisions remain queryable; invalid prior assignment not blindly retained.
- **F-011 Baselines:** fair earliest-feasible and priority-first references share the **same** constraints and data snapshot. Acceptance: metrics have consistent denominators, policy version and comparison scope.
- **F-012 Audit:** append-only actor/action/resource/version/timestamp and integrity metadata. Acceptance: all approvals, policy changes, imports and connector secret changes logged, including denials.
- **F-013 Operations UI:** event queue, plan detail, charted risk and decisions accessible at 1280px desktop, keyboard navigable, live job progress.
- **F-014 Export:** export redacted report JSON/CSV/PDF with source claims and synthetic labels. Acceptance: permissions enforced; exported unit labels and benchmark provenance clear.
- **F-015 Config:** versioned rules, service weights and cutoffs; safe default fail-closed. Acceptance: policy edit needs review/publish and future solve references precise published revision.
- **F-016 Production platform:** Dockerized build, automated migrations, health checks, tracing, backups, security scanning, staging and CI/CD. Acceptance: documented clean deploy and restore drill.

## P1 Expanded capabilities
- **F-017 Protect load proposals:** weight, volume, slot, contour, service commitments and chargeable weight; no blind claims of aircraft load/balance compliance.
- **F-018 Arrival/volume uncertainty:** uncertainty flagged in forecast and monitored against scans; proposals can use conservative margins approved by controllers.
- **F-019 Scenario replay:** historical event timeline, versioned replay on matching inputs, shadow-versus-human comparison with no operational writes.
- **F-020 Policy frontier:** multi-policy solve runs with explicit weights and trade-offs; non-dominated feasible options, no “AI confidence” fiction.
- **F-021 Operational handover:** structured approved plan export only to a manual/download destination, with explicit acknowledgement by an authorised operator.
- **F-022 Incident reporting:** missing feed, capacity discrepancy, solver overload and validation mismatch alert.
- **F-023 Retention:** per-tenant retention schedules, deletion requests and legal hold with owner approval.
- **F-024 English + Traditional Chinese:** configurable UI labels; all dates/times, units and legal status unambiguous.

## P2 Partner-dependent
- **F-025 ONE Record adapter:** negotiated scope, versioned JSON-LD mapping, subscription verification, token handling.
- **F-026 Cathay authorised adapter:** only after contract/sandbox credentials and verified endpoint schemas.
- **F-027 Live write-back:** new architectural/security review, signed plan version, maker/checker, compensating action and rollback plan; entirely disabled by default.

## Nonfunctional acceptance targets (initial engineering targets, not claimed achieved)
- Availability target for L1 evaluation ≥99.5% measured monthly, excluding planned maintenance; pilot SLA only with partner agreement.
- API read p95 ≤500ms under defined non-solver workload, measured in staging; solve jobs asynchronous; job progress must not hold HTTP request open.
- Solver practical target: 140 ULD event completes within configurable 30s end-to-end; 1,200-ULD scale measured with p50/p95/p99 and worst-case, no hard guarantee. Default solve wall-time budget 30s, configurable 10–60s; return best *validated* feasible solution or safe manual fallback.
- Every approved plan passes independent validator; target 0 validator-detected hard-rule violations, alert and block when any exists.
- Recovery point objective ≤15 min and restoration objective ≤4h **as design targets**, demonstrated in exercise before sign-off.
- Accessibility WCAG 2.2 AA target, including focus order, contrast, non-colour status and accessible charts.
- Secrets never appear in client bundles, source control, exported reports or trace payloads.
- Reproducible environment: one-command local stack, pinned lockfiles, test fixtures, migrations and versioned rules.

## Definition of done, every feature
API/schema documented; input validation; RBAC/tenant checks; model and UI tests; errors and empty/loading states; audit/provenance; observability; no hidden external writes; operator-friendly reason messages; docs and rollback; review by a non-author agent or teammate.
