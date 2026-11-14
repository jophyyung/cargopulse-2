"""Read-only consistency audit of the 90 archived synthetic benchmark runs.

These checks parse saved artifacts and recompute summary/statistic consistency; they
do not rerun the optimizer or claim hosted L1 validation.
"""

import csv
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from cargopulse_contracts import canonical_hash
from cargopulse_optimizer.benchmark import generate

ROOT = Path(__file__).resolve().parents[2]
FOLDERS = (ROOT / "tests/optimizer/benchmark-results", ROOT / "tests/optimizer/benchmark-controls")
AS_OF = datetime(2026, 11, 10, tzinfo=timezone.utc)
MICRO = Decimal("0.000001")


def load_runs(folder: Path):
    files = sorted(
        p for p in folder.glob("*.json") if p.name not in {"summary.json", "environment.json"}
    )
    raw_rows = list(csv.DictReader((folder / "raw.csv").open(newline="")))
    raw_by_key = {
        (int(row["size"]), int(row["seed"]), row["profile"], row["policy"]): row for row in raw_rows
    }
    run_by_key = {}
    for file in files:
        bundle = json.loads(file.read_text())
        run = bundle["run"]
        key = (int(run["size"]), int(run["seed"]), run["profile"], run["policy"])
        assert key not in run_by_key
        run_by_key[key] = (run, bundle["plan"], file.name)
    return files, raw_rows, raw_by_key, run_by_key


def dec(value):
    return Decimal(str(value))


def linear_percentile(values, q):
    values = sorted(values)
    index = (len(values) - 1) * q
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def test_all_90_archived_runs_match_raw_rows_plans_metrics_and_summaries():
    assert sum(len(list(folder.glob("*-*.json"))) for folder in FOLDERS) >= 90
    total = 0
    status_counts = {}
    engine_counts = {}
    checked_keys = set()

    for folder in FOLDERS:
        files, raw_rows, raw_by_key, run_by_key = load_runs(folder)
        assert len(files) == len(raw_rows) == len(run_by_key)
        total += len(files)
        assert len(raw_by_key) == len(raw_rows)
        environment = json.loads((folder / "environment.json").read_text())
        assert (
            environment["scope"]
            == "exploratory synthetic single-process warm-library; no production SLA, no concurrency"
        )
        assert environment["quantile_method"] == "linear interpolation"
        assert environment["max_wall_seconds"] == 10

        # These are historical runs. Bind their manifests to the independently
        # audited baseline, rather than treating old timings as current-code runs.
        audited = json.loads((Path(__file__).with_name("archive-source-hashes.json")).read_text())
        assert environment["source_sha256"] == audited["source_sha256"]
        # The generator still regenerates the inputs below, so its current bytes
        # must match the historical generator exactly.
        from hashlib import sha256

        generator = ROOT / "packages/domain_fixtures/generator.py"
        assert (
            sha256(generator.read_bytes()).hexdigest()
            == audited["source_sha256"]["domain_generator"]
        )

        for key, (run, plan, filename) in run_by_key.items():
            checked_keys.add((folder.name, *key))
            raw = raw_by_key[key]
            for field in (
                "size",
                "seed",
                "profile",
                "policy",
                "status",
                "validation",
                "weighted_delay_hours",
                "objective",
                "best_bound",
                "gap",
                "assigned",
                "unassigned",
                "recoverable_uld_denominator",
                "all_affected_uld_denominator",
                "candidate_count",
                "pruned_paths",
                "snapshot_hash",
                "policy_hash",
            ):
                assert str(run[field]) == str(raw[field]), f"{filename}: raw mismatch {field}"

            assert run["validation"] == plan["independent_validation"]["status"] == "PASS"
            assert plan["independent_validation"]["violations"] == []
            assert plan["snapshot_hash"] == run["snapshot_hash"]
            assert plan["policy_hash"] == run["policy_hash"]
            assert plan["solver"]["status"] == run["status"]
            assert dec(plan["solver"]["objective_value"]) == dec(run["objective"])
            # Archived greedy rows use the string "None"; plan JSON uses null.
            assert (None if run["best_bound"] == "None" else run["best_bound"]) == plan["solver"][
                "best_bound"
            ]
            assert (None if run["gap"] == "None" else run["gap"]) == plan["solver"][
                "optimality_gap"
            ]
            assert len(plan["assignments"]) == int(run["assigned"])
            assert len(plan["unassigned"]) == int(run["unassigned"])
            assert int(run["assigned"]) + int(run["unassigned"]) == int(run["size"])
            assert int(run["recoverable_uld_denominator"]) <= int(run["size"])
            assert int(run["candidate_count"]) >= int(run["recoverable_uld_denominator"])
            status_counts[run["status"]] = status_counts.get(run["status"], 0) + 1
            engine_counts[plan["solver"]["engine"]] = (
                engine_counts.get(plan["solver"]["engine"], 0) + 1
            )

            actual_weighted_delay = sum(
                (dec(a["weighted_delay_hours"]) for a in plan["assignments"]), Decimal(0)
            )
            assert actual_weighted_delay == dec(run["weighted_delay_hours"])
            metrics = {metric["name"]: metric for metric in plan["metrics"]}
            assert set(metrics) == {
                "proposed_departure_48h_eligible_uld_rate",
                "proposed_departure_48h_all_affected_uld_rate",
                "weighted_delay_hours",
                "unassigned_uld_count",
            }
            eligible = metrics["proposed_departure_48h_eligible_uld_rate"]
            all_affected = metrics["proposed_departure_48h_all_affected_uld_rate"]
            source = generate(int(run["size"]), int(run["seed"]), run["profile"], AS_OF)
            assert canonical_hash(source) == run["snapshot_hash"]
            flights = {flight.id: flight for flight in source.flights}
            proposed_first_departures = sum(
                flights[assignment["legs"][0]["flight_id"]].departure_at
                <= source.as_of + timedelta(hours=48)
                for assignment in plan["assignments"]
            )
            assert dec(eligible["denominator"]) == int(run["recoverable_uld_denominator"])
            assert dec(all_affected["denominator"]) == int(run["all_affected_uld_denominator"])
            assert dec(all_affected["denominator"]) == int(run["size"])
            assert dec(eligible["numerator"]) == proposed_first_departures
            assert dec(all_affected["numerator"]) == proposed_first_departures
            assert (
                eligible["statistic"]
                == all_affected["statistic"]
                == "proposed_first_departure_within_48h_not_approved_capacity"
            )
            for metric in (eligible, all_affected):
                denominator = dec(metric["denominator"])
                if denominator:
                    assert metric["status"] == "COMPUTED"
                    assert dec(metric["value"]) == (
                        dec(metric["numerator"]) / denominator
                    ).quantize(MICRO)
                else:
                    assert metric["status"] == "UNDEFINED"
                    assert metric["value"] is None
            assert dec(metrics["weighted_delay_hours"]["numerator"]) == actual_weighted_delay
            assert dec(metrics["weighted_delay_hours"]["denominator"]) == 1
            assert dec(metrics["unassigned_uld_count"]["numerator"]) == int(run["unassigned"])
            assert metrics["unassigned_uld_count"]["unit"] == "ULD"
            for metric in metrics.values():
                assert metric["data_source_ids"]
                assert metric["snapshot_hash"] == run["snapshot_hash"]
                assert metric["policy_hash"] == run["policy_hash"]
                assert metric["evidence_tier"] == "TEAM_SYNTHETIC_UNVERIFIED"
                assert metric["metric_method_version"] == "metrics-v1"
                assert metric["scenario_type"] == "RECOVER"

        summaries = json.loads((folder / "summary.json").read_text())
        assert len(summaries) == 15 if folder.name == "benchmark-results" else len(summaries) == 45
        for summary in summaries:
            selected = [
                run
                for run, _, _ in run_by_key.values()
                if run["size"] == summary["size"]
                and run["profile"] == summary["profile"]
                and run["policy"] == summary["policy"]
            ]
            assert len(selected) == summary["sample_count"]
            values = [float(row["wall_ms"]) for row in selected]
            for label, q in (("p50_ms", 0.5), ("p95_ms", 0.95), ("p99_ms", 0.99)):
                assert abs(summary[label] - linear_percentile(values, q)) < 1e-8
            assert summary["max_ms"] == max(values)
            assert summary["validator_failures"] == 0

    assert total == 90
    assert len(checked_keys) == 90
    assert engine_counts == {"EARLIEST_FEASIBLE": 30, "HiGHS": 30, "PRIORITY_FIRST": 30}
    assert status_counts == {
        "FEASIBLE": 60,
        "OPTIMAL": 20,
        "TIME_LIMIT_WITH_FEASIBLE": 10,
    }
