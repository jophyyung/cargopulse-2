# Ops 04 — Scenario Fixtures and Expected Invariants

All fixtures are synthetic and reproducibly generated. Specify UTC times, kg/m³ capacities, exact service policy version, data freshness and reason codes. These are **semantic expected results**, not a promise that arbitrary generated numeric datasets produce the pitch statistics.

| Fixture | Setup | Expected invariant |
|---|---|---|
| RF-01 Weighted last connection | 1 feasible slot; A w=2 delay=4h, B w=1 delay=24h, no guarantees | choose B (remaining cost 8 vs 24) if all gates pass; reproducible comparison |
| RF-02 Contractual priority | same but A has hard protected guarantee | A must not be displaced by B; document rule |
| RF-03 Cold-chain unknown | pharma ULD, only aircraft with unknown certified temp controls | no feasible automatic allocation, quality issue + ESCALATE |
| RF-04 DG incompatible | dangerous goods unit restricted to freighter, passenger belly flight | excluded candidate with `DG_AIRCRAFT_INCOMPATIBLE` |
| RF-05 Dual capacity | 4 ULDs; kg ample, m³ limited | solver never uses more volume than permitted; appropriate choice |
| RF-06 ULD geometry | compatible mass/volume but incompatible ULD contour/position | exclusion despite aggregate fit |
| RF-07 Missed connection | inbound late, minimum transfer + cutoff > outbound close | cannot propose connection, not a negative layover |
| RF-08 Last viable flight | one route closing after 30m, secondary 24h later | R-VaR cliff at actual cutoff, correct airport time zone |
| RF-09 No compliant path | all candidate gates FAIL/UNKNOWN | return unassigned + reason, do not force to random flight |
| RF-10 Flight capacity cut | new event reduces payload after prior plan | old plan marked stale, new snapshot and replan; old audit preserved |
| RF-11 Timeout with incumbent | solver time cap hits, incumbent meets independent validation | status `TIME_LIMIT_WITH_FEASIBLE`; no `OPTIMAL` badge |
| RF-12 Timeout without incumbent | no feasible incumbent or validator fails | no approval, show escalation/baseline if independently validated |
| RF-13 Cross-tenant access | user A knows B scenario UUID | 403/404; no B data in body/metadata/export/SSE |
| RF-14 Duplicate webhook | same provider event delivered 3× | one canonical version, idempotent jobs and decisions |
| RF-15 Concurrent approvals | two authorised controllers act on same plan | one consistent decision, second 409 with new version |
| RF-16 AWB split | AWB mapped to two ULDs and multiple pieces | no ULD rate reported as AWB rate; configurable partial-offload count |
| RF-17 Calibration fraud | synthetic seed produces different result vs pitch | report mismatch truthfully, no hard-coded headline values |
| RF-18 CSV injection | exported note begins `=HYPERLINK(...)` | escaped or neutralised in spreadsheet-ready export |
| RF-19 Replay future leak | event observed 14:00 replay at 13:00 | future event excluded, no impossible foreknowledge |
| RF-20 Invalid plan mutation | forged x assigns same ULD twice or exceeds kg | independent validator fails, blocks approval, triggers alert |
| PF-01 Protect volume-bound load | pieces fill 100% m³ before kg | highest feasible utility respects m³/slots; shows unused kg |
| PF-02 Protect rights conflict | lower-class cargo high weight vs guaranteed-class cargo | contract held as hard constraint; no silent service violation |
| PF-03 Protect rebooking shortage | new payload change + updated scan | new proposal and offloaded cargo passed into Recover, versioned |

## Test implementation protocol
- Place fixtures as versioned `tests/fixtures/*.json` with `scenario_schema_version` and `expected_invariants`.
- For solver assignment choices that have multiple equal-optimum answers, check objective/status/hard constraints, not fragile exact arc order.
- Test properties with seeded data and random adversarial mutations. Save failing seeds to permanent regression suite.
- Store p50/p95/p99 and max runtime separately, by scale and machine profile; **never** turn a median into universal runtime guarantee.
- For a percentage claim supply numerator, denominator, units, cohort, time window and confidence method.
