# 08 — Protect Engine: Preventive Load Planning

## Scope and guardrails
Protect reduces **avoidable** pre-departure offloads related to build-up and assignment decisions, not weather, flight cancellations, operational cuts or all booked demand. This is a P1 workstream. It extends the Recover platform but should not block Recover from reaching production-quality L1. It produces load proposals, never certified load-control clearance.

## Time windows from source presentation
- **~T−24 h:** arrival/no-show and volume declaration risk scan. Provide an uncertainty interval; do not pretend to know actual receipt data not yet scanned.
- **~T−6 h to cutoff:** after receipt scan, propose which pieces/ULDs to allocate, with physical dimensions and handling compatibility.
- **Final payload revision:** when actual available belly/freighter capacity changes, rebuild candidate and publish new proposed load with an explicit diff. Offloaded cargo routed into Recover under a new immutable event.

## Units matter
An accepted AWB is not automatically a ULD, a ULD is not one AWB, **chargeable** weight is not actual structural mass, aircraft loading weight is not the `max(mass, 167 × volume)` rule. The competition example's volumetric constant 167 kg/m³ is a business tariff convention that must be **configured per tariff/market** rather than silently fixed. A ULD that contains multiple AWBs is managed through explicit build-up mappings; opening/rebuilding units consumes actual time and ground resources.

## Objective priorities
1. Satisfy all hard safety, loading and verified contracted service obligations.
2. Among feasible plans, maximise a declared business utility consistent with signed policies: number of units/committed AWBs protected, lateness avoided, then chargeable weight or contribution subject to finance/revenue authority.
3. Minimise unplanned offloads/rehandling and unnecessary instability near cutoffs.
4. Explain where policies conflict, and show explicit trade-off rather than silently downgrading priority shipments.

## Initial MILP design
Decisions `x_{i,k} ∈ {0,1}` cargo piece/group `i` assigned to approved load slot `k`; for prebuilt immutable ULD, make assignment atomic. `y_i=1` if accepted for carriage under current available capacity; `o_i=1` if held/offloaded. Constraints: exactly one state; actual kg/m³/slot/contour capacity, ULD maximum, verified DG/cold chain; licensed/authorised hold-position compatibility, customs/documents, build-up work windows, freeze and booking commitments. If density/packing geometry is not certified, use an explicitly conservative envelope and require load controller signoff; a single summed volume limit is insufficient to certify physical fit.

For **lexicographic** objectives, first solve priority/contract preservation and fix its optimum within tolerance, then solve secondary carriage/utilisation. Do not assume `max Σx_i(λ w_i + chargeable_weight_i)` preserves priority under all scales. If weights chosen by domain expert, state that choice and test invariants. Solver must include an explicit `UNASSIGNED` outcome with reason.

## Evidence
From user's PDFs: simulation 11.28→6.2% offloaded AWBs under unchanged overbooking with +1.2% carried chargeable weight, and ≈5% under fixed chargeable weight. These are **synthetic, reference calibrated**; do not preload as observed operational KPIs. Full real-world impact depends on percentage of Cathay offloads caused by controllable load planning. Each test must report both number of AWBs and kg offloaded and a separate contractual-priority breach count.

## Examples/acceptance
- Volume-bound aircraft with unused weight: packed plan cannot exceed hold position or ULD geometry; compare feasible allocation and utilisation.
- Priority A and lower-priority B with last connection: if A has a hard guarantee, it cannot be displaced; otherwise human-approved policy may select B if utility higher.
- New 15% payload reduction: old approved snapshot becomes stale, replan; don't operate based on obsolete mass.
- Offloaded AWB split across ULDs: count one AWB offloaded only if corresponding business metric definition explicitly says “fully offloaded”; define partial offload metric separately.
- No actual live data: every Protect chart and “gain” label must show synthetic badge, model version and denominator.

## Feature release gate
Protect enabled for L1 with genuine database input, recomputable solver, comparison and validation; L2 pilot only after airline load-planning authority signs off aircraft/ULD compatibility, accepted booking obligations and required data fields. It cannot claim actual offload reduction until paired operational baseline measurement exists.
