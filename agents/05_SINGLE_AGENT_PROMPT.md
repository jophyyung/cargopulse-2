# Agent 05 — Single-Agent End-to-End Builder Prompt

Build CargoPulse as a **real production-quality** web application in one repository. You alone are responsible for contracts, data architecture, optimisation correctness, web UI, integration, testing, security and release. Do **not** build Streamlit, a presentation/demo-only page or a static mock-up.

Read the entire `CargoPulse_Production_Build_Package` including `README.md`, all specs and ops docs, then read source PDFs `E275_slides_6(1).pdf` / `E275_onepager(2).pdf` if accessible. Treat competition benchmark figures as **team-reported synthetic/unverified**, not actual observed app performance.

Implement in strict order (complete and test before moving on):
1. Source audit, models and precise denominators; choose current compatible versions; document ADRs and commit OpenAPI contract.
2. Greenfield monorepo Next.js/TypeScript, FastAPI/Python, PostgreSQL/Alembic, Redis durable jobs/outbox, Docker and OIDC, CI and telemetry. Real RBAC and tenant checks.
3. Validated CSV/JSON synthetic data import, immutable evidence-tagged snapshots, versioned hard rules, reproducible generator and tests.
4. Recover feasibility gate A–H, time-expanded candidate path builder, HiGHS MILP, independent solution validator, time-limit/unknown/escalation fallback, duplicate-safe persistence, fair baselines and explainability.
5. Product-quality operations queue, scenario, plan comparison, human in-app approve/reject/escalate, no external writes, audit and reports.
6. End-to-end and adversarial tests including RF-01..20, performance profiling, security/privacy and visual audit. Repair failures.
7. Protect multi-constraint allocation and its tests (when P0 gates passed), policy frontier and properly labelled synthetic analysis.
8. Production containers, migrations, staging, CI/CD, monitoring, backup restore, incident runbooks, release sign-off; deploy L1 if authorised host/credentials/cost acceptance available, otherwise provide exact production runbook and mark external blockers.

Never invent airline rules, API permission, confidential data, test results or observed KPIs. Unknown critical safety data must block candidate selection and require escalation. Approval in CargoPulse never dispatches or writes to external airline systems in L1/L2. Every figure must trace to a real computation/provenance; output solver statuses and validator result, not an unexplained “AI score”.

At each major step report implemented code, actual test commands/output, remaining blockers and next work. Do not stop after producing a roadmap, boilerplate or mock UI. The task is done only when `ops/02_RELEASE_GATES.md` L1 is satisfied or unmet gates are explicitly documented with reproducible evidence. Keep all constraints and tests first-class, and favour safe, maintainable modules over premature microservices.
