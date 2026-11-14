# CargoPulse — Production Engineering Handoff
**Captain Fable · E275 · Build-planning baseline 2026-11-09**

> **Objective:** Build a deployable, secure, auditable cargo decision-support web product with real optimisation, persistence, authentication, operational workflows, reproducible tests, monitoring and a clear path to an authorised airline pilot. **Not** a Streamlit mock-up, screenshot-only dashboard or hackathon-only simulation.

## Read this first
1. `specs/01_PRODUCT_CHARTER.md` — scope, users, success, non-goals.
2. `specs/02_SOURCE_OF_TRUTH.md` — exact distinctions between user materials, public standards and unverified simulation numbers.
3. `specs/03_REQUIREMENTS_AND_ACCEPTANCE.md` — functional requirements and release acceptance.
4. `specs/04_SYSTEM_ARCHITECTURE.md` — chosen technologies and design.
5. `specs/05_DATA_MODEL.md` and `specs/06_API_CONTRACTS.md` — implementation contracts; freeze before parallel work.
6. `specs/07_RECOVER_ENGINE.md` and `specs/08_PROTECT_ENGINE.md` — mathematics, invariants and fallback.
7. All other `specs/`, then `ops/` and `agents/`.
8. To execute: give a coding AI **`agents/00_LEAD_ORCHESTRATOR_PROMPT.md`** plus this entire folder and the original PDFs. For a single coding AI use `agents/05_SINGLE_AGENT_PROMPT.md` instead.

## Current decision
**One lead agent + 3 optional bounded implementers (frontend, API/integrations, optimisation).** A fourth independent QA/security reviewer checks work but does not rewrite features. Lead owns interfaces, migrations, conflict resolution, integration and release. Do **not** launch multiple agents before OpenAPI/data-model contracts are frozen. If the environment cannot safely support separate worktrees/PRs, use one agent following the same work-package sequence.

## What is being built
- **Recover — first production priority:** disruption intake → feasibility gates → R-VaR-style urgency visibility → network allocation MILP → explanation and alternatives → authorised human approve/reject/escalate → audit → operational shadow comparison.
- **Protect — next module, same platform:** pre-cutoff capacity snapshot → multi-constraint load candidate selection → hard commercial/safety obligations → optimiser → controller review → read-only pilot and policy sensitivity.
- **Shared platform:** ingestion, data provenance, configuration, role-based access, scenario management, traceable solve runs, comparison against baselines, deterministic replay, reports, observability.

## What it is NOT
- Not a Cathay-owned or endorsed system. Do not use Cathay's marks or imply integration authorisation absent permission.
- Not a load-control or dispatch authority, DG compliance certification, NOTOC generator or automatic customer-notification service.
- Not permission to import personal, proprietary or confidential data into a public AI service.
- Not proof of the hackathon's synthetic benchmark claims; the code and raw runs have not been supplied.
- Not a promise that every ULD will be recovered, that every solve takes less than a second or that the 5% offload target is achievable in a live network.

## Release ladder
- **L0 Development:** synthetic fixtures, Docker dev and CI; no public claim of live readiness.
- **L1 Publicly hosted evaluation:** real web service, genuine logins, production security controls, isolated synthetic datasets, no real airline feeds or dispatch capabilities.
- **L2 Authorised read-only pilot:** agreements + data access + policies validated with airline teams + historical replay + shadow run; separate deployment/security approval.
- **L3 Controlled operational integration:** only after L2 gate, signed owner approval, independent safety review and an explicitly scoped write-back mechanism. L3 is not assumed or required to complete L1.

## Readiness rule
A fully functional **production-quality L1** is the immediate engineering deliverable; a real Cathay operational application requires external approvals, domain-specific rules and data access which no coding model can invent. No fake APIs, hard-coded benchmark graphs or phantom “live” data to satisfy demos. Synthetic data must remain visibly labelled.

## Documentation map
| File | Purpose |
|---|---|
| `specs/01_PRODUCT_CHARTER.md` | mission, personas, workflows, KPIs and non-goals |
| `specs/02_SOURCE_OF_TRUTH.md` | numeric claims, caveats, proof needed, standards |
| `specs/03_REQUIREMENTS_AND_ACCEPTANCE.md` | prioritised user stories and conditions of satisfaction |
| `specs/04_SYSTEM_ARCHITECTURE.md` | deployment architecture, boundaries, decisions |
| `specs/05_DATA_MODEL.md` | entities, field meanings, status and provenance |
| `specs/06_API_CONTRACTS.md` | endpoints, payload examples, errors, concurrency |
| `specs/07_RECOVER_ENGINE.md` | Recover optimisation design and constraints |
| `specs/08_PROTECT_ENGINE.md` | Protect allocation design and constraints |
| `specs/09_CONNECTORS_AND_DATA_QUALITY.md` | imports, IATA ONE Record, provenance, stale data |
| `specs/10_UX_AND_DESIGN.md` | operator UI, pages, accessibility, design tokens |
| `specs/11_SECURITY_AND_GOVERNANCE.md` | OIDC, access control, privacy, audit and risks |
| `specs/12_TESTING_AND_EVIDENCE.md` | tests, independent validator, benchmarks, evidence |
| `specs/13_DELIVERY_ROADMAP.md` | milestones, gates and dependencies |
| `specs/14_OPEN_DECISIONS.md` | unanswered airline policy/data questions |
| `specs/15_EXTERNAL_REFERENCES.md` | current official/OSS references |
| `specs/16_METRIC_SPEC_AND_REPORTING.md` | rigorous KPI/benchmark reporting schema |
| `ops/01_DEPLOYMENT_AND_OPERATIONS.md` | environments, CI/CD, alerts, recovery |
| `ops/02_RELEASE_GATES.md` | formal launch criteria and sign-offs |
| `ops/03_BACKLOG_AND_OWNERSHIP.md` | task dependency graph and ownership |
| `ops/04_ACCEPTANCE_FIXTURES.md` | machine-testable scenario catalogue |
| `agents/00_LEAD_ORCHESTRATOR_PROMPT.md` | exact prompt to drive implementation |
| `agents/01_OPTIMISER_AGENT_PROMPT.md` | solver owner assignment |
| `agents/02_BACKEND_AGENT_PROMPT.md` | API/data/connectors assignment |
| `agents/03_FRONTEND_AGENT_PROMPT.md` | frontend assignment |
| `agents/04_INDEPENDENT_QA_AGENT_PROMPT.md` | QA/security independent review |
| `agents/05_SINGLE_AGENT_PROMPT.md` | complete one-agent alternative |
| `agents/06_COLLABORATION_PROTOCOL.md` | parallel task/PR/conflict rules |
| `中文使用說明.md` | user-facing Chinese starting instructions |

## Versioning and changes
The specification is the current intended system, not a claim that code exists. Changes require a short Architecture Decision Record (ADR): proposed change, alternative, reasons, migration, impact on API, safety, tests and approver. The source PDFs are reference evidence, not executable acceptance tests.
