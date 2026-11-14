# ADR-002: HiGHS, bounded objectives and independent checking

Status: accepted for synthetic engineering.

Use highspy 1.15.1 (MIT), one solver thread, fixed seed, explicit wall-time budget.
No pitch performance numbers are acceptance thresholds or generated results.
The first objective preserves verified contractual/frozen obligations and minimises
unassigned units; the second minimises weighted lateness, handling, churn and the
explicit policy escalation penalty multiplied by each unassigned unit's service
weight, at the best first-stage assignment count. Solver bounds and status must disclose incomplete
optimality at either stage. A contractually impossible instance escalates and cannot
be approved. Do not label an all-unassigned answer as a successful recovery.

RF-01 uses a shared immediate flight and later alternatives: selecting B leaves A
with 2 * 4 = 8 weighted delay hours; selecting A leaves B with 1 * 24 = 24.
Equal assignment counts therefore choose B. Both baselines use the same candidates
and aggregate resources; neither represents an airline's actual policy.

Decimal kg/m3 are scaled to exact bounded integers before passing coefficients to
HiGHS doubles, with exact-range checks. Independent validation uses Decimal arithmetic.
Time-limit incumbents require independent PASS and explicit time-limit labelling.
