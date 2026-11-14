# Recover optimizer engineering evidence

Status: implemented for synthetic engineering. This is not hosted L1 acceptance,
airline approval, certified loading clearance, or production performance evidence.
Protect remains disabled and was not implemented.

## Scope and integration

Owned implementation: `services/worker/cargopulse_optimizer/`. Canonical models in
`packages/contracts/python/cargopulse_contracts/models.py` are unchanged. The public
functions in `docs/CONTRACTS.md` return canonical DTOs. Additional pure helpers expose
the time-expanded arcs, MILP construction, and per-unit alternative explanations.

Every solver/reference-policy result invokes the separately owned
`cargopulse_validation.validate_solution_independently`. No validator implementation
or validator constraint builder is included in this package. Missing validator
installation fails the call; it never manufactures PASS. A temporary FAIL DTO is
needed to construct the immutable plan before real validation; that placeholder is
never returned. Any invalid incumbent is returned as quarantined ERROR with the
actual independent violations. Backend approval must independently revalidate again.

## Candidate safety and mathematical scope

- Whole physical ULDs are atomic. All canonical pieces remain in the denominator.
- Every leg requires explicit current PASS for DG applicability, security,
  serviceability, aircraft-position envelope/load control, physical capacity,
  customs, cold-chain applicability, and ground equipment. Non-cold cargo still
  requires explicit N/A-as-PASS cold-chain evidence.
- PASS evidence must be observed no later than decision time, no older than
  `source_max_age_seconds`, and valid strictly beyond the resource usage endpoint.
  Flight/position/ULD/security/route evidence extends through arrival; ground
  equipment extends through actual handling completion. Expiry uses a half-open
  interval. Unknown capacity, permissions, or envelope values create no feasible arc.
- Every departure requires a continuous `policy.handling_seconds` interval entirely
  inside a verified ground window, after readiness or the prior leg's arrival plus
  an explicit approved connection minimum, and ending no later than flight cutoff.
  Minimum transfer and handling are additive. No implicit connection is inferred.
- Candidate `cutoff_at` is the first leg's actionable deadline:
  `min(flight.cutoff_at, handling_window.end_at) - handling_seconds`. A decision
  exactly at the deadline can finish handling exactly at cutoff; later decisions
  cannot use it. UTC comparisons preserve midnight/DST chronology; airport IANA
  zones remain input provenance rather than replacing UTC with ambiguous wall time.
- Frozen paths are exact immutable structural identities. Contractual latest arrival
  is a hard gate. Mandatory frozen/contractual ULDs cannot use unassigned variables.
- The canonical structural path identifier is `P-` followed by the first 24 hex
  digits of `canonical_hash({'cargo_unit_id': uid, 'legs': canonical_leg_dicts})`.
- Candidate enumeration stops with an explicit error above 20,000 explored
  leg-position-window combinations per ULD. Published top-K limits retain the latest
  actionable-cutoff option as well as best total-cost choices when K permits both.
  With K=1 the latest-cutoff option wins. Pruning is counted and disclosed; OPTIMAL
  means the retained mathematical instance, not an unenumerated full network.
- Urgency uses unpruned feasible weighted-lateness minima within the enumeration
  bound, independently of total-cost candidate ranking. A lost final option returns
  NO_COMPLIANT_PATH and null delta rather than an infinite score. If a unit lacked
  an initial feasible path, a later newly available path has undefined/null delta.
  R-VaR is incremental operational loss from waiting, not statistical VaR or money.

## Objective, arithmetic, statuses, and references

The actual HiGHS MILP first minimizes unassigned ULD count and fixes its proven
optimum. It then minimizes policy-weighted lateness plus per-leg handling plus
changed-path stability plus the explicit cost of escalation. Each unassigned ULD
costs `policy.unassigned_penalty_weighted_hours * cargo.service_weight`, rounded
upward to six decimal places. This secondary severity preference cannot increase
the proven first-stage minimum unassigned count. Both solver and reference-policy
telemetry report the complete secondary cost including unassigned penalties.
No unbounded big-M trades hard safety for cost.

All Decimal measurements/costs are scaled exactly by powers of ten to integers;
the sum of absolute scaled values must be below `2**52`. Out-of-range instances
fail closed with ERROR. Physical constraints cover shared flight kg/m3, each position
pool's kg/m3/slots and every handling window's unit throughput across all legs.
These are conservative synthetic envelope/throughput constraints, not certified
packing, balance, temperature physics, DG segregation, or concurrent team scheduling.

The frozen DTO permits six decimal places. `delay_hours` is seconds/3600 rounded
upward to 0.000001 hour; weighted delay multiplies that value by service weight and
rounds upward again to six places. MILP costs exactly match those canonical numbers.
Reported incumbent objective is recomputed with Decimal. Nonoptimal lower bounds
are rounded downward. No count-stage bound is mislabeled as a second-stage
weighted-hours bound when count optimality is unproven.

HiGHS 1.15.1 runs with one thread, fixed random seed, zero configured MIP gaps and
explicit time budget shared across candidate/model preparation and both solves.
The final required plan construction/metrics/independent validation can add time
beyond that optimization budget; end-to-end runtime is measured separately. There
is no strict whole-function deadline, memory sandbox, or production latency SLA.
The per-ULD enumeration bound and exact coefficient limit are resource guards.

Actual solver statuses are preserved: time-limit incumbents are explicitly
TIME_LIMIT_WITH_FEASIBLE; no incumbent is TIME_LIMIT_NO_FEASIBLE. Native HiGHS
interrupt statuses map to CANCELLED. External worker-process cancellation wiring
has not been exercised by this package. Fractional/nonfinite/corrupt raw solver
vectors fail closed. A mathematically optimal all-escalation instance retains actual
OPTIMAL status and includes NO_RECOVERY_ASSIGNMENTS; the API must expose no recovery
and must not offer approval. Impossible mandatory obligations produce actual solver
INFEASIBLE. A greedy reference failing a mandatory obligation reports ERROR without
claiming a proof of infeasibility.

Both greedy baselines use the identical frozen snapshot, policy, candidate function,
and aggregate resource consumption. Frozen/contractual obligations are considered
first, then earliest arrival or service priority respectively. They are reference
policies, not descriptions of an airline's historical practice. Greedy policies do
not claim global assignment-count or cost optimality. Explanations list alternative
costs, deadlines, and excluded gates and warn that individually feasible alternatives
may compete for the same global resources; they do not manufacture counterfactual
full-network solutions or binding-constraint certification.

HiGHS API reference used during implementation:
[official Python modeling documentation](https://ergo-code.github.io/HiGHS/dev/interfaces/python/model-py/),
[official Python examples](https://github.com/ERGO-Code/HiGHS/blob/master/examples/call_highs_from_python.py).
Installed API/version probes and executable solver tests, rather than documentation
alone, establish behavior for the installed 1.15.1 build. No dependencies were added
or installed by this workstream; highspy was already locked by the lead.

## Metric meaning

`proposed_departure_48h_eligible_uld_rate` uses the number of proposed assigned ULDs
whose **first leg departure** is no later than snapshot as-of +48h, divided by the
number of affected ULDs with a compliant individual candidate. The corresponding
`proposed_departure_48h_all_affected_uld_rate` uses every affected ULD as denominator.
Their statistic is `proposed_first_departure_within_48h_not_approved_capacity`.
Neither is approved re-protection/reservation, guaranteed arrival, or an AWB rate.

Weighted delay is the sum over proposed assigned ULDs, with statistic
`proposed_assigned_cargo_weighted_hours`. Unassigned ULD count is explicitly separate,
with statistic `explicit_escalated_whole_uld_count`. Each metric retains source,
cohort, window, evidence tier, method version, numerator, denominator and input hashes.
No claimed 87.3%, -8.5%, 0.7-second or 1.1-second headline is seeded as a result.

## Verification and reproduction

From repository root with the lead's installed project environment:

```sh
PYTHONPATH=packages/contracts/python:services/api:services/worker:. python -m pytest tests/optimizer tests/contracts -q
ruff check services/worker/cargopulse_optimizer tests/optimizer
python -m cargopulse_optimizer.benchmark --output tests/optimizer/benchmark-results --seeds 101 102 103 --profiles mixed --max-wall-seconds 10
python -m cargopulse_optimizer.benchmark --output tests/optimizer/benchmark-controls --seeds 101 --profiles low-density capacity-shortage cold-dg-blocked --max-wall-seconds 10
```

Optimizer fixtures cover RF-01..RF-12 algorithm semantics, multiple-flight network
routes, explicit connection/ground failures, cold chain, DG, contour, all physical
resource types, unknown/future/expired evidence, frozen/contractual obligations,
UTC midnight/DST, exact scaling, actionable deadline cliffs, shared budgets,
nonbinary output and independent-validation quarantine. RF-11/12 deterministic
termination tests inject termination status through a small solver adapter; the
RF-11 incumbent is actually solved by HiGHS. They are not claimed as workload-driven
timeout experiments. Raw performance controls separately retain actual time limits
when the solver encounters them. Hypothesis checks shared-resource limits and full
ULD accounting. RF-10 tests immutable new-capacity hash and replan; persistence,
audit retention and stale-approval behavior belong to backend/integration tests.

Raw reports are under `tests/optimizer/benchmark-results/` and
`tests/optimizer/benchmark-controls/`: every seed/profile/policy includes full plan,
independent validator output and a raw row; CSV rows, machine/runtime/source hashes,
and p50/p95/p99/max JSON summaries are retained. Source hashes bind the optimizer,
shared generator, and separately owned validator source used in each run. Replays
use deterministic fixed UTC as-of and the committed generator/profile transforms.

The mixed cohort has three seeds per size (101, 102, 103), and each control profile
has one (101), for 90 plans across 50/140/400/800/1200 ULDs. Percentiles use linear
interpolation and expose sample count; one-sample p50/p95/p99/max are all the same
observation. These are sparse exploratory statistics, not credible population tail
estimates or confidence intervals. No 30-seed/concurrent/cold-database experiment,
bootstrap uncertainty estimate, live airline replay, certified rule signoff,
production resource isolation, or hosted user acceptance is asserted. Performance
fixtures currently use direct flights; real multi-leg correctness is covered by
separate regression fixtures, not scale-performance proof for dense three-leg graphs.

## Final executed results

- Optimizer plus contracts: **45 passed** (34 optimizer tests including parametrized
  cases/property tests, 11 frozen contract tests). Ruff check passed.
- Optimizer + contracts + the lead-owned independent-validator suite, imported from
  the shared lead workspace: **65 passed in 1.21s**. This last cross-worktree check
  used the project Python 3.12.14 environment and appended the lead worker module
  directory to PYTHONPATH. The validator implementation/tests were not copied or
  modified in this branch.
- Retained final benchmark: **90/90 independent PASS**, 60 greedy FEASIBLE reference
  plans and 30 actual HiGHS runs. Of the HiGHS runs, 20 were OPTIMAL and 10 were
  TIME_LIMIT_WITH_FEASIBLE; incomplete solves remain explicitly labeled, with
  count-stage bounds omitted where secondary optimality has no valid bound.
- Mixed profile, 1,200 ULDs, seeds 101/102/103: p50 **4.638426s**, p95 **4.715472s**,
  p99 **4.722321s**, max **4.724033s**; all three OPTIMAL. These sparse observed
  quantiles do not establish distribution tails or a universal latency guarantee.
- Single-seed 1,200-ULD controls: low-density **3.888157s** OPTIMAL;
  capacity-shortage **11.092629s** TIME_LIMIT_WITH_FEASIBLE; cold-DG-blocked
  **3.844442s** OPTIMAL. The shortage run exceeds the 10-second optimization
  budget due to required finalization/independent checking, as disclosed above.
- Environment: Darwin 27.2.0, arm64, 12 logical CPUs, Python 3.12.14, HiGHS 1.15.1,
  one solver thread. The host was not isolated from other development activity.
- These timings differ materially from the supplied slide's 0.7s p50 / ~1.1s
  1,200-ULD reference. No claim is made that the unpublished original simulator,
  objective, gate density, hardware, or denominator has been reproduced.

CSV artifacts use normalized LF line endings in the repository; numeric records
are unchanged from the standard-library CSV output. Final benchmark source
fingerprints are retained in each environment JSON. They
include the final complete secondary objective (weighted escalation costs) and the
corrected proposed-first-departure metrics. Earlier exploratory timings were replaced
by this final-code reproduction and are not presented as final implementation results.
