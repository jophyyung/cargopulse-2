# 13 — Engineering Roadmap and Quality Gates

## Interpretation
This is a **dependency-driven roadmap**, not a claim that the whole system will be delivered in a specific number of days. The presentation's 12-week timeline describes a **proposed airline read-only pilot**, not the time budget for developing and certifying the entire product. User asked for a real publishable web service, so release gates replace “ready for demo” checklists.

| Phase | Work | Demonstrable deliverables | Gate |
|---|---|---|---|
| **P0 Evidence/spec freeze** | read source, record risks, clarify data boundaries, choose stack | signed scope, API/OpenAPI baseline, data dictionary, ADRs, threat model | no ambiguity in units, operator authority, baseline provenance |
| **P1 Foundation** | monorepo, Next.js, FastAPI, auth, DB, migrations, queue, CI, observability | secure running app with OIDC and role guards, migrations/health, test pipeline | cross-tenant and secret-leak tests pass |
| **P2 Canonical intake** | domain tables, synthetic fixture generator, signed import, quality and snapshots | usable import validation UI/API; immutable snapshots and source lineage | corrupt/missing critical inputs fail closed |
| **P3 Recover vertical slice** | candidate builder, MILP, independent validator, job progress, decision UI | actual end-to-end Recover with real stored scenarios | 24-vs-8, cold chain, DG, no route, stale and concurrency tests pass |
| **P4 Production L1** | replay/metrics, baseline comparison, plan approval, reporting, hardened deployment | externally hosted authenticated L1 using clearly labelled synthetic data, backup/restore, monitoring | **L1 release gates** pass, no false live-data claims |
| **P5 Protect + deeper analytics** | build-up/load proposals, signed obligations, policy frontier, robust test suite | integrated Protect workflow and transparent constraints | independent validation + contractual priority cases pass |
| **P6 Authorised airline pilot preparation** | approved connectors, runbook, data sharing, policy signoff, history mapping | L2 shadow-run environment, partner approval pack | data owner/security/ops signoffs and 12-week pilot readiness |
| **P7 Live-ops integration (future)** | maker/checker, sandbox write-back and rollback/reconciliation | separately reviewed production change | explicit carrier authorisation + external operational safety approval |

## Must not be parallelised initially
- Schema/metrics definitions, API response shapes, auth/tenant boundaries and solver result status semantics. One lead agent freezes these before assigning work.
- Airline rule implementation and legal/security approvals cannot be delegated to AI based on unsourced guesses.

## Efficient independent parallel work after contract freeze
- **Optimiser:** pure candidate generator, HiGHS adapter, validator tests and benchmark runner. Does not own DB migrations or frontend.
- **Backend/data:** Postgres schema, import pipeline, OpenAPI, OIDC, durable jobs, persistence and connectors. Depends on signed canonical model.
- **Frontend/UX:** Next.js operations desk, scenario and review screens, generated API types, charts, i18n, accessibility. Uses MSW synthetic contract fixtures until backend available.
- **Independent QA:** threat model, mutation fixtures, accessibility, penetration-test prep and test evidence; does not decide product claims.

## Milestone completion criteria
All phases require a real working branch, reproducible local startup, migration up/down strategy, tests, docs, screenshots, CI green, no placeholder “TODO business logic”, no production secrets and a lead-reviewed PR. Quality is measured by executable gates; polished visuals cannot substitute for solving a real scenario.

## First build slice (for rapid tangible results)
Within the first vertical slice, user can login, load one complete synthetic recovery event from JSON, see exact unavailable routes, run a bounded MILP on 140 cargo units, inspect an independently validated plan, compare two fair baselines and record an in-app decision. This is **real functional code**, not a demonstration dashboard. It should be built early for feedback while preserving full production architecture.

## Final deployment policy
The application may be made publicly accessible for evaluation at L1 if it only uses authorised synthetic/public data, production authentication and valid licences. A public URL does not mean Cathay has endorsed the system. No production airline data or write-back until L2/L3 gates explicitly satisfied.
