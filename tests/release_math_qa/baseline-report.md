# Independent Release Math QA Report

**Baseline:** `069c9d43e7c271ac351dd35829e0fb7a5a52206f` (detached worktree)

**QA STATUS: BLOCK on this baseline.** The principal blocker is a reproducible metric-integrity gap: a schema-valid plan with unchanged, independently feasible assignments and forged computed metrics still receives validator `PASS`. A second, medium-severity mismatch lets a future-dated gate proof appear in a live candidate list even though the independent validator rejects it.

This review did not modify implementation or contract files. The only added files are this report and the two tests in `tests/release_math_qa/`. No database, hosted service, external account, or operational write was used.

## Findings

### CP-QA-005 — High: forged metrics pass plan validation

**Finding and reproduction:** Solve a one-ULD synthetic snapshot, retain every physical assignment, then change one metric to `value=0.873`, `numerator=873`, `denominator=1000`, `cohort_id=FORGED-COHORT`, mismatched snapshot/policy hashes, empty `data_source_ids`, `statistic=verified_live_success`, and `status=COMPUTED`. `SolutionPlan.model_validate` accepts this payload. `validate_solution_independently(snapshot, plan)` returns `PASS` with no violations.

**Expected invariant:** A plan with inconsistent or incomplete metric provenance and arithmetic must not count as validated KPI evidence or be exported as such. Every displayed value must be recomputed against the immutable snapshot, plan, cohort, and metric definition, or explicitly marked incomplete and withheld from validated-evidence export.

**Observed behavior:** The independent validator recomputes physical assignments and gates but does not inspect `plan.metrics`. `MetricValue` requires field types but does not enforce value/numerator/denominator arithmetic, non-empty source IDs, or equality of metric hashes to plan hashes. The worker's quarantine condition is based on independent-validation status; the plan blocker path checks hashes, feasibility status, and assignments but does not recalculate metric semantics. JSON, CSV, and PDF reports serialize stored plan metrics. Relevant code: `services/worker/cargopulse_validation/validator.py`, `services/api/cargopulse_api/worker.py:166`, `services/api/cargopulse_api/domain.py:190-245`, and `services/api/cargopulse_api/main.py:536-548`. The metric contract requires missing metadata to be `INCOMPLETE` and ineligible for validated-evidence export (`specs/16_METRIC_SPEC_AND_REPORTING.md:6-7`).

**Gate impacted:** L0 safety/math metric integrity and validated-evidence export. This finding concerns metric truth and evidence provenance; the reproduced physical assignments remained valid. This test did not itself exercise database persistence, API approval, or report download.

**Remediation required:** Add an independent metric verifier/recomputer at the persisted-plan boundary. It must bind metric hashes, cohort, source IDs, method, statistic, units, UTC window, numerator, denominator, and value to the same snapshot and assignments. Reject or mark incomplete inconsistent metrics, and prevent them from being exported as validated evidence or contributing to approval claims.

### CP-QA-006 — Medium: candidate builder accepts evidence newer than the snapshot

**Finding and reproduction:** Set a route-permission DG proof's `observed_at` to `snapshot.as_of + 1 second`. At the default decision time (`snapshot.as_of`) the target flight is excluded. At `decision_time=snapshot.as_of + 2 seconds`, `build_feasible_paths` includes the target flight because its proof is now older than the query time. The independent validator called at that same later decision time rejects the same assignment with `EVIDENCE_NOT_VALID`, because it requires proof observation no later than `snapshot.as_of`. The API candidate endpoint passes `utcnow()` (`services/api/cargopulse_api/main.py:361-363`), so the difference is reachable when a still-current snapshot contains a proof observed after its as-of time.

**Expected invariant:** Evidence for an immutable snapshot must not become usable merely because a later query time passes its observation timestamp. Candidate generation and independent validation should apply the same snapshot-causality rule.

**Observed behavior:** Candidate `valid()` checks `proof.observed_at <= decision_time` (`services/worker/cargopulse_optimizer/candidates.py:30-36`); validator proof checks `proof.observed_at <= source.as_of` (`services/worker/cargopulse_validation/validator.py:106-121`). The normal solver calls candidate generation at snapshot as-of, and the validator blocks approval of a plan that uses the future proof. I found no path from this mismatch to an approvable solver assignment; the demonstrated impact is a misleading candidate listing and inconsistent API semantics.

**Gate impacted:** L0 future-evidence handling and candidate correctness.

**Remediation required:** Reject evidence observed after `snapshot.as_of` during candidate generation for every decision time, matching the independent validator. Add a regression that checks the later-time candidate API path.

## Passed adversarial checks

The added independent mutations passed for:

- `FAIL` and `UNKNOWN` DG, customs, cold-chain, and load-control proofs.
- Freighter-only DG cargo assigned to a passenger aircraft.
- Assignment exceeding residual flight mass.
- Multi-leg route whose minimum transfer misses the outbound cutoff.
- Connection evidence expiring exactly at outbound departure.
- Future gate evidence at default snapshot time and future-published policy.
- Frozen assignment reassignment.
- Urgency output remaining invariant when the MILP's top-K path cap changes.

These are bounded synthetic fixtures. They do not certify airline rules, aircraft loading, or real cold-chain continuity. In particular, the model's generic handling-window equipment proof has no machine-readable temperature range or cold-chain ground-equipment capability; this review cannot establish physical cold-chain continuity across real transfer handling.

## Archived benchmark review

I parsed all 90 saved run JSONs and their `raw.csv`, `summary.json`, and `environment.json` files: 45 mixed-profile runs and 45 control-profile runs. The audit regenerated the deterministic input snapshots from archived size/seed/profile metadata and recomputed the first-departure-within-48h numerator from the saved assignments; it did **not** rerun any of the 90 solver jobs.

- All 90 run rows match their JSON run metadata for cohort, policy, hashes, status, counts, denominators, candidate counts, and pruning counts. All 90 embedded plans have matching input hashes, zero independent-validation violations, and `PASS`.
- The 90 plan assignment/unassigned counts and weighted-delay totals agree with the run rows. Metric names, denominator fields, first-departure numerators, statistic labels, hashes, evidence tier, and method version are internally consistent in the saved records. Eligible denominators are cross-checked against the run row but are not independently recalculated by rebuilding all candidate sets. The archive test recomputes the stored percentile summaries from each raw timing cohort.
- Status mix is 30 HiGHS runs (20 `OPTIMAL`, 10 `TIME_LIMIT_WITH_FEASIBLE`) plus 60 greedy reference runs (`FEASIBLE`). None of the 90 are hosted L1 evidence.
- At 1,200 ULD in the three mixed samples, HiGHS wall times are 4.638426s, 4.620760s, and 4.724033s, all `OPTIMAL`. Three observations do not establish population tail latency. The single-seed capacity-shortage control at 1,200 ULD is `TIME_LIMIT_WITH_FEASIBLE` at 11.092629s.
- Both environment manifests name base revision `a8192318fcdbf72faac72838fe2d1a0de0c9b7b2`, not this baseline. All six recorded source fingerprints for optimizer, independent validator, and fixture generator match the corresponding files at this baseline. The contract model source is not included in those fingerprints. Treat the archive as code-file-hash-bound evidence, not a run identified by the current Git SHA.
- In 60 greedy run rows, undefined `best_bound` and `gap` are serialized as the string `"None"`; the full plan JSON stores JSON `null`. Their meaning is consistent but their types differ. The audit normalizes that representation for semantic comparison; this is a low-severity metadata-format issue.

The checked-in evidence documents these as sparse synthetic explorations, explicitly disclaims reproduction of the supplied `87.3%`, `−8.5%`, `0.7s`, and `~1.1s` source headlines, and states that local results are not hosted L1 acceptance. I found no claim that the local benchmark is hosted L1 `PASS`.

## Commands and results

From `/Users/pie/CargoPulse_Production_Build_Package/.worktrees/release-math-qa`:

```sh
PYTHONPATH=packages/contracts/python:services/api:services/worker:. /Users/pie/CargoPulse_Production_Build_Package/.venv/bin/python -m pytest tests/optimizer tests/contracts tests/validation -q
# 65 passed in 1.16s

PYTHONPATH=packages/contracts/python:services/api:services/worker:. /Users/pie/CargoPulse_Production_Build_Package/.venv/bin/python -m pytest tests/release_math_qa/test_benchmark_archive.py -q
# 1 passed in 11.93s

PYTHONPATH=packages/contracts/python:services/api:services/worker:. /Users/pie/CargoPulse_Production_Build_Package/.venv/bin/python -m pytest tests/optimizer tests/contracts tests/validation tests/release_math_qa -q
# 80 passed, 1 failed in 12.22s
# Expected invariant failure: metric tampering is accepted by the baseline validator.
```

**Limits:** This report is against the exact baseline SHA above. It does not assess subsequent fixes, hosted configuration, authentication-provider behavior, live airline inputs, physical load-control safety, or runtime performance outside the archived synthetic sample set. No `L1 PASS` is asserted.
