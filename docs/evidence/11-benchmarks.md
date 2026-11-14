# Current synthetic benchmark evidence

Actual native Python 3.12.16 / HiGHS 1.15.1, one solver thread, Darwin arm64 runs.
Five sizes (50, 140, 400, 800, 1200 ULD) each use 30 fixed mixed-profile seeds
101-130 and three matched policies: 450 complete plans. Three negative-control
profiles (low density, capacity shortage, cold/DG blocks), five sizes and three
seeds each add 135 plans. **585/585 plans passed the independent physical and
metric verifier during the actual runs.** No solver run is simulated here.

The 195 MILP runs include 150 OPTIMAL and 45 TIME_LIMIT_WITH_FEASIBLE results;
390 greedy reference plans report FEASIBLE. No time-limited result is called optimal.
A 10-second solver budget excludes some setup/final verification; measured wrapper
wall time can exceed 10 seconds. Budget is not an API end-to-end latency SLA.

## Mixed-profile measured HiGHS wall time

Each line reports 30 samples; milliseconds, linear-interpolated sample quantiles.

- 50 ULD: p50 667.955, p95 7564.205, p99 10030.013, max 10033.086; statuses {'OPTIMAL': 28, 'TIME_LIMIT_WITH_FEASIBLE': 2}.
- 140 ULD: p50 10056.552, p95 10079.059, p99 10081.187, max 10081.622; statuses {'OPTIMAL': 8, 'TIME_LIMIT_WITH_FEASIBLE': 22}.
- 400 ULD: p50 1891.623, p95 10228.447, p99 10240.694, max 10245.612; statuses {'OPTIMAL': 24, 'TIME_LIMIT_WITH_FEASIBLE': 6}.
- 800 ULD: p50 2852.976, p95 5168.078, p99 9164.652, max 10488.385; statuses {'OPTIMAL': 29, 'TIME_LIMIT_WITH_FEASIBLE': 1}.
- 1200 ULD: p50 4703.749, p95 5862.225, p99 5990.446, max 6037.056; statuses {'OPTIMAL': 30}.

These are synthetic single-process warm-library measurements, not hosted, cold-
database or concurrent-user distributions. API/worker, DB/object verification,
network time, browser rendering and hosted workload latency are outside this
native harness. The container browser scenario used a 30-second solve budget and
can return a validated incumbent at that limit. No 0.7-second production claim is
supported. Three control seeds do not establish tail distributions.

The optimiser first minimises unassigned ULD count. Weighted delay totals are
conditional on assigned cargo; showing fewer hours by leaving cargo unassigned is
not a fair service improvement claim. Compare assigned/unassigned counts, identical
cohorts/gates/resources, denominator definitions and solver status together. The
recorded rate measures proposed first departure within 48 hours, not approval,
booked capacity, physical arrival, an AWB rate, offload reduction or revenue.

## Reproduction and artifact binding

`tests/optimizer/benchmark-current` and `benchmark-current-controls` contain raw
CSV, environment/configuration, sample summaries and `plans.tar.gz` with every
complete JSON plan. `docs/evidence/benchmark-manifest.json` records archive and
per-plan SHA-256. Every archive was decoded and byte hashes compared with the
original outputs before raw files were moved to ignored `.local/benchmark-raw`.
The compressed archives retain all original records.

The mixed run started with Git base `fb49d02` and controls with `9a92fc1` while
working compute files already contained later fixes. These base revisions alone
are not run-version identifiers. All eight recorded compute/generator/contract
source fingerprints were explicitly checked against the final working files and
matched. Lockfiles describe dependencies. API, web and infrastructure changes do
not turn these into hosted latency evidence.

```sh
PYTHONPATH=packages/contracts/python:services/worker:. python -m cargopulse_optimizer.benchmark \
  --output tmp/current-benchmark --sizes 50 140 400 800 1200 \
  --seeds {101..130} --profiles mixed --max-wall-seconds 10
PYTHONPATH=packages/contracts/python:services/worker:. python -m cargopulse_optimizer.benchmark \
  --output tmp/current-controls --sizes 50 140 400 800 1200 \
  --seeds 101 102 103 --profiles low-density capacity-shortage cold-dg-blocked \
  --max-wall-seconds 10
```

Use Bash/Zsh for brace expansion or supply the 30 integers explicitly. Repeated
wall times need not match. Original 90-run archives remain historical and were
separately revalidated after the metric-integrity fix; they are not merged into the
current timing cohort. No supplied PDF headline or airline performance is claimed.
