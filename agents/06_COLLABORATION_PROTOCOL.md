# Agent 06 — Multi-Agent Collaboration, Contracts and Integration Protocol

This document is mandatory **only** when using parallel coding agents. Multi-agent is beneficial after a fixed contract, because frontend and optimiser can work in different languages and test independently. It is harmful when each agent invents schema, metrics or access rules. The Lead is the only merge/integration authority.

## Pre-parallel gate
Lead must commit: canonical schema/Pydantic DTOs, initial Alembic schema, OpenAPI endpoint statuses, generated TS types, sample JSON fixtures, scope/RBAC matrix, solver `SolutionPlan` schema, error model and acceptance fixtures. Record exact baseline commit SHA and ADR links. Confirm all agents access the same repository or isolated worktrees at that SHA.

## Branch ownership
| Agent | Owns | Does not modify |
|---|---|---|
| Lead | root config, `packages/contracts`, `infra`, integration tests, ADRs | other worktrees until PR merge |
| Solver | `services/worker/optimizer`, solver test fixtures, benchmark runner | API models/migrations, frontend |
| Backend | `services/api`, migrations, connector tests | solver model, web design |
| Frontend | `apps/web`, UI/i18n/tests | API models/migrations, solver |
| QA | independent test suites, security/visual reports | implementation files unless lead requests a targeted fix |

## Handoff payload each PR
```markdown
# Task CP-### / branch / base SHA
- Scope and status: DONE/BLOCKED
- Changed files and migrations
- Contract impact: none / OpenAPI diff / schema diff
- Invariants implemented, known failure cases
- Verification: exact commands and exit codes/output excerpts
- Screenshots or JSON evidence where appropriate
- Security/privacy and safety review
- New dependency and licence impact
- ADR/update needed
- Rollback or migration plan
- Open issues and precise reproduction steps
```

## Conflict rules
1. Any DTO/API change: author opens contract change proposal, lead approves versioned change, regenerates clients **before** dependent agents update code.
2. Solver and backend disagree on unknown/feasible status: the safe enum in `05_DATA_MODEL` wins, not whichever module is convenient; both update tests.
3. UI requests undocumented “more confidence”: do not add fake score; request a specified metric or quality issue.
4. Metrics disagree across agents: compare raw numerator/denominator, cohort and method. Never silently round to match pitch PDF.
5. When cross-tenant test fails: stop integration, fix before continuing nonessential UI styling.
6. Failed deployment after merge: revert last change safely; preserve evidence in incident issue.

## Merge order
Contract baseline → auth/DB/immutable snapshots → solver pure package + validation → async jobs and API → web interactions → full-stack e2e → QA fixes → Protect → deployment. Agents may independently build but merge in this order. Re-run global tests after *every* merge. Never leave parallel branches unintegrated until deadline.

## Reporting cadence
Provide a concise progress update at each phase/integration gate; updates must include actual files/tests, not unverifiable “90% completed”. An agent cannot claim a feature “working” based on mocked endpoint response. Host deployments require actual URL/health/permission checks and permission to use required accounts.
