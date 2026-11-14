# 07 — Recover Engine: Mathematically Defined, Feasibility First

## Responsibility
Compute a feasible network recovery plan for affected cargo after offloads, cancellations, reduced payload or missed connections. This is **decision support** and produces a plan proposal, not a physical dispatch order. Recovery is the initial challenge-aligned product.

## Correct optimization unit
- Build a `cargo_unit` with exact identity and mapping to physical ULD, constituent AWBs/pieces and handling mode. Use a whole ULD as atomic only if business rules actually forbid splitting; otherwise support approved split/rebuild arcs and resource costs as a later feature.
- An **assignment option** `(u, path, flight slots, terminal handling windows)` must be independently feasible from verified constraints at the given snapshot time. A path can have zero, one or several flight legs; a simple one-leg example is not a full network solution.
- `z_u=1` denotes unassigned/escalated. This is safe and mandatory if no eligible arc exists. Missing capacity or unknown DG permission is not a feasible arc.

## High-level objective
Minimise weighted service lateness + missed connection/service penalties + **explicit cost of escalation/no assignment** + rehandling costs + disruption/replanning stability penalties. Hard constraints cannot be exchanged for score reductions. All weights versioned by signed policy and shown in the UI.

## Baseline MILP sketch
Sets: `U` cargo units, `P_u` precomputed compliant paths for unit u, `F` flight/position resources, `B` handling windows. Variables `x_{u,p} ∈ {0,1}` and `z_u ∈ {0,1}`. Constants `m_u` kg, `v_u` m³, `a_{u,p,f} ∈ {0,1}` path uses flight f, `h_{u,p,b}` handling slot consumption, `d_{u,p}` service lateness hours, `w_u` policy weight, `r_{u,p}` rehandling cost, `c_{u,p}` assignment churn.

```math
min Σ_{u∈U} Σ_{p∈P_u} (w_u d_{u,p} + α r_{u,p} + β c_{u,p}) x_{u,p}
    + Σ_{u∈U} M_u z_u
subject to
Σ_{p∈P_u} x_{u,p} + z_u = 1                 ∀u
Σ_{u,p} m_u a_{u,p,f} x_{u,p} ≤ M_f^{free}      ∀f
Σ_{u,p} v_u a_{u,p,f} x_{u,p} ≤ V_f^{free}      ∀f
Σ_{u,p} s_{u,p,f,k} x_{u,p} ≤ S_{f,k}^{free}    ∀f,k (slot/contour family)
Σ_{u,p} h_{u,p,b} x_{u,p} ≤ H_b^{free}          ∀b
x_{u,p} = 0 if any hard gate not explicitly PASS
```
**Important:** This is a *minimum* implementation specification. Aircraft hold/balance restrictions are not reducible to aggregate kg/m³; the airline-approved position envelope and balance approval remain external **hard gates**. If full certified compatibility data is unavailable, produce only a conservative proposed feasibility status and require human verification; do not claim load clearance.

## Hard gates A–H (all versioned, signed data provenance)
- **A Safety/DG:** applicable dangerous-goods and segregation compatibility, verified declaration, carrier aircraft/cargo hold constraints; unknown -> block and escalate.
- **B ULD/position:** ULD type, aircraft variant, contour, container/pallet orientation and serviceability, hold slot and restraint requirements.
- **C Capacity:** payload, volume, position limits, residual weight/volume over all legs; separate manifest mass and chargeable weight.
- **D Customs/documents:** shipment may transfer and exit/import under approved status and release conditions; unknown blocks transfer.
- **E Cutoffs and connections:** ready-to-load, airport transfer minimum, customs handover, flight closeout, crew/handling timing and conservative buffers.
- **F Cold chain:** validated equipment, temperature range and handling time; unverified chain blocks medical perishable allocations.
- **G Handling resources:** break-down, re-build, forklifts, teams, equipment and time-slot throughput; loading/unloading constraints.
- **H Uniqueness:** no double ULD assignment, AWB piece duplication, frozen commitments or conflicting reservation.

## R-VaR / marginal loss of waiting
For an eligible unit and snapshot time `t`, let `L_u(t)` equal the **minimum feasible policy-weighted lateness** among paths still available if a decision is delayed until `t`. Define `Δ_u(t) = L_u(t) - L_u(t0)`. This is an operational marginal urgency score (may rise discontinuously when the last viable route closes), **not calibrated statistical VaR or money**. When `P_u(t)` is empty, expose `NO_COMPLIANT_PATH` and escalation rather than an infinite bar without explanation. Include ties, time zones, source freshness and uncertainty intervals where known. Risk prioritisation is UI guidance; global MILP determines assignments.

## Lexicographic safety and priorities
1. Apply hard gates; service contractual guarantees are hard only when supplied/approved by business owner.
2. Minimise count/weighted severity of unassigned or uncovered obligations as signed policy dictates; prevent unfair huge penalty from dwarfing constraints through explicit bounded domain.
3. Within remaining feasible options minimise weighted lateness/handling/stability.
4. Return alternatives when the top objective is near-tied; disclose score trade-offs.
5. Operators may override **soft decisions** with reason; hard-gate failures cannot be overridden inside CargoPulse. Escalation to competent domain authority is the only path.

## Execution algorithm
1. Load immutable snapshot `S`, published rule version `R`, approved weights `W` and resource versions.
2. Data quality validator: list missing, contradictory or old fields. Mark scenario blocked until critical fields fixed or explicitly out of scope.
3. Build time-expanded network with documented station handling times; create only hard-feasible candidate paths. Prevent explosion with configurable top-K **without losing required last-connection candidates**; record pruning and quality caveat.
4. Solve MILP via HiGHS, enforce resource/time/memory limits; capture status, objective, primal/dual bound where available, gap, candidate count and wall-clock.
5. Compute **independent** post-solve feasibility from canonical snapshot; do not reuse the exact solver constraint builder as validator. Any mismatch quarantines the plan.
6. If feasible but not optimal, label `FEASIBLE / TIME_LIMIT_WITH_FEASIBLE`, surface gap and approval policy; otherwise safe fallback to validated baseline or ESCALATE.
7. Generate explanation for every change: unique critical path, last cutoff, capacity trade-off, service-weight impact, safety restrictions; include alternatives and constraints binding.
8. Persist canonical run, input hash, solver environment, output, reason codes and audit; no direct operational write.

## Freeze and replanning
For already approved or near-departure loading, the plan is `frozen` unless authorised releasable flag exists. Churn cost is `λ × changed_ULD_count` or a scale-calibrated handling cost with same units as delay objective; no unbounded magic weighting. A superseding event must independently revalidate frozen/previous assignments against new safety conditions; if a previously approved route becomes invalid, escalate immediately.

## Deterministic test cases
- **24 vs 8:** one slot, A weight 2×delay 4h vs B weight 1×delay 24h; assuming no hard service guarantee, optimal should prioritise B. If A is contractually guaranteed or B is DG-incompatible, output changes accordingly.
- **Missing cold-chain:** pharmaceutical ULD to unverified cold chain must NEVER be allocated.
- **DG restriction:** all incompatible candidates blocked, escalation with reason.
- **Oversubscription:** sum mass, volume and slots cannot exceed residual capacity.
- **Last connection:** delayed action closes route at cutoff and R-VaR shows discrete loss at correct timestamp.
- **No feasible path:** model returns escalated unassigned set and 0 violated hard constraints; never invents route.
- **Solver timeout:** last validated feasible incumbent may be used if authorised; unknown or unchecked plans never approvable.
- **Replan churn:** identical snapshot/weights must be deterministic within solver configuration; reopened event cannot overwrite old record.

## Risks to discuss with actual cargo operators
Real aircraft weight-and-balance, station availability, ULD compatibility, quarantine/DG limitations, revenue-management/booking entitlements, rebooking permissions and actual loading cutoff definitions are proprietary and cannot be inferred from the event PDFs. Until approved rule files and ownership are in place, use labelled conservative synthetic constraints and *shadow-only* output.
