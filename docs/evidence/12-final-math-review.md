# Final Independent Math Review

**Reviewed source:** `e40c67671aff8889234c4af1dee490eb2da75999` on `codex/final-math`.

**Result:** No new reproducible mathematical defect was found in the bounded metric-verifier and snapshot-causality review. This is not a blanket mathematical certification, an airline-rule sign-off, or hosted L1 acceptance.

## Scope and method

Reviewed the prior baseline findings in `tests/release_math_qa/baseline-report.md`, the remediation record in `docs/evidence/08-qa-remediation.md`, the frozen metric contract, `services/worker/cargopulse_validation/metrics.py`, its `validator.py` caller, and the optimizer's metric and candidate implementations. The validator's eligible-set search is separate code and does not import the optimizer candidate builder.

The added tests use small deterministic snapshots and real solver outputs. They cover zero eligible ULDs, a sole frozen path with a contractual deadline, one- and two-leg timing/handling, path pruning, metric lineage, and missing/unknown/duplicate metric rows. No implementation, contract, API, database, or benchmark artifact was changed. No database, network, or external service was used, and no benchmark solver run was repeated.

## Mathematical checks

- **Eligibility denominator:** The independent depth-first search checks per-unit route feasibility and evidence through each flight arrival, the handling interval and cutoff on every leg, approved connections, position/ULD limits, contractual deadlines, and exact frozen-path identity. For deterministic generated snapshots of 1, 2, and 4 ULDs, its eligible set matched the optimizer's candidate set. With `max_paths_per_unit=1`, the denominator still counted the eligible ULD after path pruning.
- **Zero eligible set:** With no flights, the valid all-escalation plan reports eligible numerator/denominator `0/0`, `value=null`, `status=UNDEFINED`; the all-affected rate remains `0/1`. The independent verifier returns `PASS` for that non-mandatory all-escalation plan. The API separately blocks approving a plan with no assignments.
- **Hard service obligations:** A one-route plan with both an exact frozen path and a contractual latest arrival remains eligible and validates when the route satisfies both. This checks that frozen identity is included in the independent denominator search.
- **Multi-leg semantics:** In a two-leg HKG–SIN–FRA fixture, the 48-hour numerator follows the **first departure**, while weighted delay uses the **final arrival**. With the first leg at +3h, final arrival at +53h, commitment at +10h, and service weight 2, the verifier accepts a numerator of 1 and weighted-delay numerator of 86 hours. Increasing the connection minimum so handling ends after the outbound cutoff removes the route from both independent eligibility and candidate generation.
- **Delay metric versus optimization objective:** For a one-leg proposal with two hours of lateness, service weight 2, handling cost 2 and stability cost 3, the solver objective is 9 while reported `weighted_delay_hours` is 4. This is consistent with `WEIGHTED_DELAY_HOURS`: the metric reports service-weighted lateness and does not silently include handling, churn, or escalation costs.
- **Integrity and lineage:** The verifier recomputes all four emitted plan metrics, hashes, cohort, source IDs, UTC window, statistic, units, and status. Missing, unknown, duplicate, and unbound-source metric rows fail validation. Contract `Literal` types constrain metric method, scenario type, and evidence tier during canonical reparse.
- **Snapshot causality:** A gate proof observed one second after `snapshot.as_of` is excluded even when queried two seconds later; the independent eligibility search also excludes it. This verifies the CP-QA-006 candidate/validator consistency fix in the current checkout.

## Reporting boundary

The checked Recover plan metrics are deliberately labelled proposed first departure, not approved capacity or physical arrival. The 48-hour numerator therefore does not claim the `REPROTECTION_ELIGIBLE_48H` outcome in `specs/16_METRIC_SPEC_AND_REPORTING.md`.

The new verifier validates the four Recover metrics currently emitted by the optimizer. The broader metric catalog in `specs/16` also names separate no-compliant-path, churn, late-delivery, solve-time, and validator-count metrics. They are not separate `SolutionPlan.metrics` rows in this slice. The no-compliant-path count can be derived from all-affected minus eligible denominators and per-unit escalation reasons remain in the plan; other catalog metrics are outside this four-metric calculation. If the full catalog is a release requirement, that remains a reporting-scope decision.

Cold-chain checks remain limited by the contract data: cargo-flight cold-chain proofs and generic handling-equipment proofs carry no machine-readable temperature band or cold-chain ground-handling capability. The synthetic multi-leg test verifies the time/cutoff calculations, not physical temperature continuity.

The archived benchmark results were not rerun or revalidated in this task. `docs/evidence/08-qa-remediation.md` records a separate 90/90 metric revalidation and states that the earlier solver timings predate this metric verifier; those historical timings are not current end-to-end timings.

## Verification commands

Run from `/Users/pie/CargoPulse_Production_Build_Package/.worktrees/final-math`:

```sh
PYTHONPATH=packages/contracts/python:services/api:services/worker:. /Users/pie/CargoPulse_Production_Build_Package/.venv/bin/python -m pytest tests/release_math_final -q
# 9 passed in 0.86s

PYTHONPATH=packages/contracts/python:services/api:services/worker:. /Users/pie/CargoPulse_Production_Build_Package/.venv/bin/python -m pytest tests/optimizer tests/validation -q
# 54 passed in 1.11s

PYTHONPATH=packages/contracts/python:services/api:services/worker:. /Users/pie/CargoPulse_Production_Build_Package/.venv/bin/python -m pytest 'tests/release_math_qa/test_adversarial_math.py::test_metric_tampering_is_rejected_before_plan_is_treated_as_validated_evidence' -q
# 1 passed in 0.62s; the prior metric-tamper reproduction now fails closed.
```

The root's combined 162-test result and 90/90 archive revalidation are referenced from the remediation record; they were not rerun as part of this bounded review.
