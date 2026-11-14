# 16 — Metric Contracts and Results Report Schema

## Purpose
Prevent the recurring hackathon issue: visually convincing graphs with ambiguous denominator, simulated numbers presented as measured operating results and solver performance headlines that hide worse cases. This document defines the analytic contract for the production app.

## A metric is not a scalar alone
Each value must have: `name`, `value`, `unit`, `numerator`, `denominator`, `cohort_id`, `window_start_utc`, `window_end_utc`, `event_as_of_utc`, `scenario_type`, `metric_method_version`, `evidence_tier`, `data_source_ids`, `snapshot_hash`, `policy_hash`, `baseline_policy_version`, `statistic` (case mean, ratio of means, median etc) and optional confidence method. Missing metadata means the chart is marked `INCOMPLETE` and cannot be exported as validated evidence.

## Essential metrics
| Code | Formula | Unit / denominator |
|---|---|---|
| `OFFLOAD_AWB_RATE` | offloaded distinct AWB count / booked distinct AWB count | AWB / AWB, fixed flight cohort and period |
| `OFFLOAD_ULD_RATE` | offloaded physical ULD count / planned eligible ULD count | ULD / ULD, not equal to AWB |
| `REPROTECTION_ELIGIBLE_48H` | eligible affected ULD with approved protected capacity inside 48h / eligible affected ULD | eligible ULD, source time and final state documented |
| `REPROTECTION_ALL_48H` | all affected ULD with approved protected capacity inside 48h / all affected ULD | all affected ULD, includes no-path cases |
| `NO_COMPLIANT_PATH_COUNT` | distinct affected ULDs with no compliant route | ULD, explicit reason labels |
| `LATE_DELIVERY_LE_24H` | recovered ULDs arriving not more than 24h after commitment / assessed cohort | clearly defined ULD cohort |
| `WEIGHTED_DELAY_HOURS` | Σ policy_weight × max(0, arrival_utc−commitment_utc) in hours | weighted hours, approved policy revision |
| `REPLAN_CHURN` | distinct changed ULD assignments between two candidate/approved plans | ULD changes, reference plan ID |
| `CARRIED_CHARGEABLE_WEIGHT` | sum tariff-specific chargeable kg for carried pieces/AWBs | billable kg, not actual loaded mass |
| `SOLVE_WALL_TIME_MS` | wall-clock from worker start to solver termination | ms, sample count and p50/p95/p99/max |
| `VALIDATOR_VIOLATION_COUNT` | independently detected hard constraint breaches | per plan and per type |

## Two valid but different improvement formulas
For matched incidents `i`, policy CP vs PF:
- **Mean incident relative improvement** = mean_i [(PF_i − CP_i)/PF_i]. This may correspond to source headline ≈8.5% when actual raw incidents verify it.
- **Ratio of aggregate means** = [mean_i(PF_i) − mean_i(CP_i)] / mean_i(PF_i). Displayed presentation scenario averages imply ≈8.4%. These are **not** the same statistic and cannot silently replace one another.
- Report both if useful, with precise sample, exclusion and weighting. If no raw data, show only *source-reported* values with provenance, not computed claim of verified live performance.

## Evidence reports
For each benchmark experiment output:
```json
{
  "experiment_id": "experiment-uuid",
  "source_tier": "TEAM_SYNTHETIC_UNVERIFIED",
  "generator_revision": "git-sha",
  "seed_list": [101, 102, 103],
  "scenario_count": 450,
  "baseline_definitions": ["earliest_feasible_v1", "priority_first_v1"],
  "hard_gate_policy_hash": "sha256-value",
  "metrics": [{"code":"REPROTECTION_ELIGIBLE_48H", "numerator":null,"denominator":null,"unit":"ULD", "statistic":"mean_of_matched_events", "status":"NOT_YET_COMPUTED"}],
  "solver_distribution": {"p50_ms":null,"p95_ms":null,"p99_ms":null,"max_ms":null},
  "validation": {"plans_checked":null,"hard_rule_violations":null},
  "raw_output_uri": null,
  "notes": "Nulls are intentional until executed. Never insert historical presentation figures as results."
}
```

## Charts with required labels
- 3 policy benchmark chart: matched cohort size, units, who is eligible and whether numbers are synthetic.
- Risk curve: score is *marginal weighted delay from waiting*, not probability or money.
- Solver runtime: p50, p95, p99, max in separate legend and machine hardware.
- Protect frontier: baseline calibrated to October 2025 11.28% *only if data generation document confirms*; plot does not represent measured actual Cathay response.
- Real-life pilot: no “increase in revenue” without validated chargeable weight, tariffs and realised financial attribution.

## Data science rules
Do not use a random train/test split that leaks nearly identical flights between periods; use time-causal evaluation. Report all seeds, sensitivity to policy weights, missing input impact, no-route count and harms to priority/medical cargo. Verify that baseline methods comply with identical hard gates. External airline results only after lawful real-data collection and permissions.
