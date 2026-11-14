# 12 — Testing, Scientific Evidence and Independent Validation

## Principle
Build **testable operational correctness** before refining graphics. The competition PDFs contain detailed synthetic benchmark claims, but their source simulator and logs were not supplied; never assert those outcomes until reproducible evidence is generated in the app repository.

## Test pyramid
1. **Unit tests:** formulas, time zones, service-weight interpretation, volume/mass conversions, consistent denominators, R-VaR cliffs, policy publication.
2. **Property-based/mutation tests:** assignment uniqueness, monotonic capacity, feasibility, no double AWB/ULD counting, cold-chain/DG exclusion, solver output corruption detection.
3. **Independent validator tests:** use independently written constraint checks (not a wrapper around solver model) and intentionally illegal candidates/answers.
4. **Contract tests:** OpenAPI generated clients and server matching; auth/tenant object boundaries, stale concurrency and idempotency.
5. **Integration tests:** PostgreSQL, object storage, queue, REST + worker, outbox retries, failure recovery and connector sanitisation with synthetic data.
6. **E2E UX:** actual authenticated browser journey through ingest→scenario→solve→plan→approval, including keyboard and Chinese locale.
7. **Replay science:** fixed seeds and published synthetic generator distributions; compare matched baseline policies, store raw output and calculate metrics from raw data each run.
8. **Performance:** realistic sizes 50/140/400/800/1,200 ULDs at varied route densities and cold-chain/ground capacity constraints, 30+ seeds, concurrent jobs, cold and warm DB, p50/p95/p99/max, feasible/optimal status, gap and wall budget.
9. **Operations/security:** backup restore, failover, OWASP API abuse tests, load tests, logging redaction, pen test (L2 gate).

## Independent validation must check
- One ULD/group allocated to ≤1 mutually exclusive physical service; no duplicate constituent AWBs/pieces.
- Each flight/hold position residual mass, volume, slot, contour and approved aircraft limits.
- Connection windows: arrival, minimum transfer, handling readiness, flight cutoff, departure and timezone.
- DG/safety/temperature/customs/security requirements and signed verification status.
- ULD location/availability and build-up resource/time-window overlaps.
- Frozen assignments, contractual guarantees and approved policy version.
- Every unassigned item has reason and escalation state; zero silent dropping.
- Input hash matches scenario, policy and flight capacity version; plan cannot be approved if stale.

## Scientific benchmarking (no cherry-picking)
- **Define cohort first**: identical flights, incident timestamps, cargo set, feasible paths and hard gates across all policies. Reveal unassigned count and reason separately.
- **Baselines**: earliest-feasible reference, priority-first reference, optional human-approved historical shadow; never call baselines Cathay current policy absent evidence.
- **Per-case** outputs: time to solve, bound/gap, weighted delay hours, 48h eligible ULD recovered, all-affected ULD denominator, missed connections, P95 tail, frozen reassignments, infeasible/no-path count, validator checks, throughput and costs.
- **Aggregation**: publish (a) mean of per-case percent improvements and (b) improvement from aggregate means, *as separate metrics*. Explicitly separate −8.5% vs approx −8.4% when source numbers dictate.
- **Uncertainty**: bootstrap confidence intervals on matched incident cohort, seed list, skew and policy sensitivity; label exploratory when sample sparse. Do not invent 95% confidence ranges.
- **Negative controls**: test an event with no available flights; a case where naive priority-first is optimal; high DG/cold chain blocking; low capacity and no solutions; new data worsening outcomes.
- **Reproduction bundle**: code revision, dependencies, deterministic seeds, generator config, input hashes, raw plan logs, validator output, analysis notebook/script, CPU/OS/solver version, computed aggregate JSON, generated plots.
- **No forced outcome**: benchmark failure does not trigger changing generator assumptions until outcome matches the pitch; document discrepancy and update product claims.

## Required reports
- Unit/E2E coverage, incident regression, solver infeasibility and time-limit handling.
- Comparison table for all valid data with reproducible numerator/denominator.
- Test report listing all rejected illegal plans and mismatch detector sensitivity.
- Performance profile at scale and consistency across cold/warm runs.
- Data-quality drop rate and effect on solution quality; missingness reported.
- Accessibility audit and screenshot evidence on all core screens.
- Dependency inventory/SBOM and security status.

## Release acceptance
**L1:** tests pass and real hosted application works on labelled synthetic data; all plans pass independent validator, approval remains in-app, data boundaries enforced. **L2:** authorised airline datasets and operational rules, offline historical replay, paired shadow run, domain policy signoff and external security review. **L3:** contract and write-back change control plus safety owner; separate release.
