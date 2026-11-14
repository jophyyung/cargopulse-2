# Ops 03 — Implementation Backlog, Dependencies and Review Ownership

## Roles
**Lead:** interface freeze, repo ownership, integration, release. **Solver:** optimisation and independent validator harness. **API/Data:** schemas, DB, auth, ingestion, jobs, endpoints. **Web:** user workflow, visual analytics, accessibility. **QA:** adversarial acceptance/security, no feature ownership. Each issue has a lead reviewer from another role.

| Ticket | Priority | Title | Owner | Depends on | Acceptance proof |
|---|---|---|---|---|---|
| CP-001 | P0 | bootstrap monorepo, pnpm/Python env, Docker, CI | Lead | none | clean install/build/test |
| CP-002 | P0 | data glossary and OpenAPI contract baseline | Lead + API + Solver | source audit | schema peer review and generated types |
| CP-003 | P0 | tenants, OIDC roles, DB migrations | API | CP-002 | tenant tests and login |
| CP-004 | P0 | controlled synthetic data generator with evidence tags | Solver | CP-002 | reproducible seed and schema tests |
| CP-005 | P0 | import validation/persistence/provenance | API | CP-003/4 | bad input blocked and traceable |
| CP-006 | P0 | scenario immutability and versioning | API | CP-005 | stale and race tests |
| CP-007 | P0 | Recover hard-feasible candidate generation | Solver | CP-002 | fixture reason codes and unknown fails closed |
| CP-008 | P0 | HiGHS Recover MILP and explicit status | Solver | CP-007 | 24/8, no-route, capacity tests |
| CP-009 | P0 | independent solution validator | Solver + QA independent | CP-007/8 | mutation suite rejects illegal plans |
| CP-010 | P0 | durable solver job/outbox and API persistence | API | CP-006/8 | retry, timeout and duplicate job test |
| CP-011 | P0 | operations event queue | Web | CP-002 + API mock | Playwright keyboard/data freshness |
| CP-012 | P0 | scenario/detail/plan view and explanations | Web | CP-002 + solver schemas | useful validation/reason displays |
| CP-013 | P0 | approval/reject/escalation transactions | API + Web | CP-009/12 | stale-plan rejection, no external writes |
| CP-014 | P0 | policy versioning/approval | API | CP-003 | policies immutable and reviewer checks |
| CP-015 | P0 | baseline engines and analytics metrics | Solver + API | CP-008 | same gates/cohort and denominators |
| CP-016 | P0 | audit, masking and reports | API + Web | CP-013/15 | privacy checks and evidence export |
| CP-017 | P0 | E2E regression, security scans, observability | QA + Lead | CP-010–16 | documented acceptance run |
| CP-018 | P0 | staging+L1 production release | Lead | CP-017 | all L1 gates, monitored deploy |
| CP-019 | P1 | Protect candidate/build-up MILP | Solver | CP-008 | mixed dimension and commitment tests |
| CP-020 | P1 | Protect UI/policy frontier | Web | CP-019 | correct units and synthetic labels |
| CP-021 | P1 | historical event replay & outcome matching | API+Solver | CP-015 | no future leakage, provenance |
| CP-022 | P1 | performance experiments and evidence package | QA | CP-021 | raw logs, seeds, p50/p95/p99 |
| CP-023 | P2 | ONE Record read-only integration | API | sponsor permissions | provider contract and sandbox verified |
| CP-024 | P2 | airline/ground rule registration | Domain owner + API | signed rules | controlled safety gate review |
| CP-025 | P2 | read-only shadow pilot | Lead + partner | CP-023/24, L2 gate | authorised outcome reporting |
| CP-026 | P3 | any write-back | Partner and security owner | L3 gate | signed and independently reviewed |

## Board protocol
`BACKLOG → READY (contracts frozen) → IN_PROGRESS → REVIEW → INTEGRATED → VERIFIED → RELEASED`. No direct merge to main from AI agents. Every PR includes task ID, files changed, test commands and results, evidence screenshots, risk review and rollback considerations. Changes to schema/API require lead approval and generated client update.

## Branch and merge process
Use isolated worktrees or PR branches. Avoid editing another agent's owned directory. Solver and backend contracts may initially use shared fixtures committed by lead. Conflict resolution occurs in lead branch only. Run full integrated tests after every merge, not just at the end. If agents cannot share exact git state, switch to serial single-agent execution rather than pasting incompatible code.
