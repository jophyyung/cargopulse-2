# 01 — Product Charter and Operating Model

## One-sentence mission
CargoPulse helps authorised air-cargo recovery teams choose **feasible, explainable, time-sensitive, network-aware** recovery actions when flights or load capacity change, while extending the same constraint discipline upstream to reduce preventable offloads.

## Users (RBAC identities, not marketing segments)
| Persona | Responsibilities | May do | Must not do |
|---|---|---|---|
| Recovery Controller | handle offloads, cancellations, missed connections | review affected ULDs, compare alternatives, approve in-app decision record, escalate | push load or bookings to airline systems by default |
| Load Planning Analyst | pre-departure Protect planning | inspect capacity, create load proposals, compare baseline and policy variants | override aircraft safety/load-control authority |
| Duty Manager | approval oversight, high-risk exceptions | second-level approval, override with reason, freeze scenario | silently alter historical decisions |
| Data Steward | input and mapping quality | import, validate, reconcile and mark freshness | approve recovery allocation by default |
| Auditor/Observer | governance and historical replay | view redacted event history and decisions | change inputs or approve plans |
| Tenant Admin | users and tenant settings | access policy, retention, rule configuration subject to controls | bypass independent validator or enter airline credentials without authorisation |
| Partner Integrator | consented source integration | configure scoped connectors, monitor mapping | assume API access or operational permissions |

## Real tasks, not decorative dashboards
1. Incoming offload/flight event: controller sees affected cargo, source times, feasibility uncertainty and **last actionable moments**.
2. Event snapshot is locked and validated; bad input is highlighted. Insufficient confidence means NEEDS_VERIFICATION, not hidden default values.
3. Controller requests feasible solution; engine removes physically/legally impossible candidate assignments first.
4. Engine compares earliest-feasible and priority-first **reference heuristics** with optimised network allocation on identical valid candidates; these reference heuristics are **not claimed to be Cathay's actual policy**.
5. Controller reviews why each ULD was moved, feasible alternatives, status (OPTIMAL/FEASIBLE/TIMEOUT/INFEASIBLE), expected weighted delay and operational impact.
6. Controller can approve proposal **inside CargoPulse**, reject or escalate. Approval records a decision but **does not write to airline operations** at L1/L2.
7. New event creates a new immutable snapshot and proposes a change-minimising re-plan; never silently overwrite an approved or frozen plan.
8. Replay and evaluation compare matched events, denominators and capacity rules; export a provenance-aware performance report.

## Product surfaces
- **Recovery Desk:** live/read-only event queue, severity, data freshness, SLA clock, last-viable connection and alerts.
- **Scenario Workspace:** event details, affected ULDs/AWBs and routes, constraints, alternatives, assignment matrix.
- **Network & Timeline:** flights/connection graph; route path and times in airport-local time plus UTC; true geodata only if supplied.
- **Decision Review:** reason codes, trade-off deltas, required approvals and escalation queue.
- **Protect Planner:** flight-specific packing/loading candidate view with weight, volume, position and service constraints; proposed vs baseline.
- **Evidence Lab:** historical replay, deterministic synthetic suite, comparisons, confidence/distribution labels, baseline provenance.
- **Admin & Governance:** policy versioning, role assignment, source connectors, audit, retention, model metrics.

## Status model
`DETECTED → INGESTING → NEEDS_VERIFICATION | READY → SOLVING → PLAN_READY | NO_FEASIBLE_PLAN | SOLVER_ERROR → IN_REVIEW → APPROVED | REJECTED | ESCALATED → CLOSED`.
- Every transition stamped UTC, actor, role, tenant and snapshot_id.
- If new input arrives while a plan is in review, label STALE and require revalidation before approval.
- Approved decisions are immutable; corrections produce a superseding event.

## KPIs with exact units
- **Recovery:** 48-hour re-protection rate **among affected ULDs with a compliant path**, plus separate *all-affected* denominator and unavoidable-no-path count; weighted delayed-hours; connection misses per incident; P95 delay; time-to-decision; number of changed ULD assignments; exception rate.
- **Protect:** offloaded AWBs / booked AWBs under an explicitly defined observation window; offloaded ULDs separately; on-time build-up; carried chargeable weight; hard-rule failures; service obligation breaches; aircraft flight/hold fit.
- **Product quality:** data staleness, ineligible/unknown candidate count, model feasibility, validator mismatch, approval time, user accept/override rate, runtime p50/p95/p99, queue latency and task failure rate.
- **Business:** validated incremental contribution *only when authorised financial data exists*; avoided handling costs; shadow vs actual operational outcome; do not equate chargeable-weight increase with booked revenue.

## Priorities
**P0:** ingestion and provenance; Recover candidate generation; immutable scenarios; hard-rule validator; asynchronous solver; review workflow; audit; OIDC/RBAC; tests and production deployment. **P1:** Protect planning, stress testing and replay. **P2:** authorised ONE Record connector and airline-specific policies. **P3:** signed write-back integration subject to external authorisation.

## Constraints and explicit non-goals
- Do not invent Cathay cargo data, policy approvals, regulated dangerous-goods requirements or aircraft load distribution data.
- Never represent synthetic data as live. Do not add “AI predictions” without dataset, evaluation, drift monitors and operator explanation.
- Do not claim a guaranteed recovery, a 5% real offload rate, zero real-world incidents or sub-second runtime under all loads.
- Prioritise reliable enterprise desktop web workflow over animations and 3D graphics. No Streamlit, no static dashboard as the final product.
- Read-only in the first authorised airline environment; Cathay systems remain the system of record.

## Acceptance at a glance
A real user can log in, import validated input, see actionable alerts, request a solver job, receive a feasible and independently checked plan, inspect why it is recommended, approve/reject/escalate with traceability, compare policies, replay events and audit all changes. It is deployed using production containers with TLS, monitoring, backup/recovery and reproducible CI evidence.
