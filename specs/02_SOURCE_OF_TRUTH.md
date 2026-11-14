# 02 — Source of Truth, Statistics and Evidence Boundaries

## Primary supplied source documents
- `E275_slides_6(1).pdf` (20 pages): most recent comprehensive user-supplied cargo project specification (Protect, Recover, interface, scenario data, risk, deployment).
- `E275_onepager(2).pdf` (one A4 page): most recent one-pager; cross-check summary only.
- Previous project roadmap and application answers: contextual vision; if in conflict with these latest files, **do not silently choose**. Create an ADR and flag a policy difference.

## Three evidence tiers
**TIER PUBLIC:** independently published source; cite publisher/date and exact geography/metric. **TIER TEAM-REPORTED SYNTHETIC:** a claim shown in the team's PDF but cannot be independently validated without code/run records. **TIER DESIGN ASSUMPTION:** requirements to implement or illustrative examples; never present as measured results.

## Specific grounded information and how to use it
| Topic | Value | Tier | Engineering rule |
|---|---|---|---|
| Oct 2025 organiser dashboard | 13,599 offloaded AWBs / 120,607 booked AWBs = 11.28% | supplied organiser snapshot | keep original granularity: AWBs, period and reference only; do not equate to ULD rates |
| Organiser target | 5% 'ideal' offload ratio; 48-hour re-protection objective | competition brief | target, not validated airline SLA or guaranteed deliverable |
| Group cargo Sep 2026 | 154,041 tonnes, +14.2% YoY | public release cited in decks | context only, not solver outcome |
| Protect example | 11.28% → 6.2%, +1.2% carried chargeable weight under same overbooking; ≈5% with same chargeable weight | team synthetic | benchmark target, no production claim |
| Recover | 87.3% vs 83.6% within 48 hours **for recoverable ULDs**, in synthetic event suite | team synthetic | segregate denominator; track no-compliant-path separately |
| Recover weighted delay | −8.5% average of per-event relative improvements; ratios of displayed overall means ≈−8.4% | team synthetic | do not combine aggregation methods or claim identical |
| Solver speed | 1,200 ULDs p50 reported 0.7s, worst reported ~1.1s at that size; some other configurations worse | team synthetic | never generalize to always <1s; measure p95/p99 on production hardware |
| Test size | 3 scenarios ×150 incidents ×3 policies = 1,350 plans; Protect 64,500 simulated flights | team synthetic | must be recreated by tests; do not seed UI with results as completed real runs |
| Benchmark hard-rule failures | zero reported in synthetic runs | team synthetic | not safety certification; independent validator mandatory |
| 24 vs 8 weighted delay | one feasible slot; unit A weight 2 delay 4h vs unit B weight 1 delay 24h | illustrative | include as deterministic unit test; not proof of actual Cathay shipment decision |
| Pilot | 12-week read-only, 2–3 HKG routes | proposal | contingent on sponsor/data approval; not a promise of airline participation |

## High-risk metric definitions
1. **AWB** = Air Waybill; one AWB may map to multiple pieces, ULDs or split movements. **ULD** = physical build unit; one ULD can contain multiple consignments/AWBs. Do not aggregate between them without a versioned cargo-to-ULD association table, splitting/weight allocation and documented counting rules.
2. *Eligible / recoverable* ULDs have at least one compliant candidate route **at decision-snapshot time**. “87.3%” cannot be applied to **all** offloaded AWBs or ULDs.
3. If an event has no feasible route, return ESCALATE with reason, not a fabricated flight. Re-protection means an **approved reservation/capacity protection event**, not guaranteed physical arrival.
4. The 2025 reference rate was used to **calibrate synthetic data**; this is not external validation that Cathay uses simplistic priority-first/earliest-feasible baseline.
5. Never convert +1.2% carried chargeable weight into +1.2% revenue without price, yield, booking mix, fees and displacement analysis.
6. R-VaR in the presentation is **a proposed marginal weighted service-risk score**, **not** conventional statistical/financial Value-at-Risk and not an externally validated Cathay KPI.
7. *0 safety violations* is only as meaningful as the encoded candidate rules and independent check; aircraft, DG, balance, handling, cold chain and export requirements need signed expert rules.
8. Solver status `OPTIMAL` refers to the exact mathematical instance and provided constraints, not real-world safety or data correctness; `FEASIBLE` and `TIME_LIMIT` must be separately surfaced.

## Data lineage requirements
Every dashboard value/decision/report contains or links to `{data_source, source_record_ids, as_of_utc, ingestion_time_utc, schema_version, rule_set_version, scenario_snapshot_hash, solver_version, validation_version, evidence_tier, units, denominator, numerator, metric_definition_version}`. Public screenshots must not mislabel synthetic comparisons as actual Cathay performance.

## Input missing from source PDFs
No proprietary operating manual, actual cargo-to-ULD split mapping, authorisation to use Cathay branding, live data credentials, validated capacity envelopes, true route inventory, signed DG rule files, simulator source code, solver logs, benchmark seeds, post-solve validator or signed airline integration contract was supplied. Do **not** fabricate these. Use documented synthetic profiles until separately provided.

## Reproduction protocol for earlier results
Do not preload claimed −8.5% or 87.3% as test output. Recreate public generator parameters with fixed seeds, document exact distributions, solve all policies using identical snapshots and feasibility rules, save runs in versioned files, independently validate assignments, compute confidence intervals/denominators and compare output to reference. If discrepancies persist, report them as discrepancies. Honest performance is more important than matching a slide.
