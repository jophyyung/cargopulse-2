"""Reproducible exploratory benchmarks; never advertised as airline performance.

Run: python -m cargopulse_optimizer.benchmark --output tests/optimizer/benchmark-results
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from time import perf_counter

import highspy
from cargopulse_contracts import ScenarioSnapshot, canonical_hash

from packages.domain_fixtures.generator import make_snapshot

from . import build_feasible_paths, run_baseline_earliest, run_baseline_priority, run_solver

PROFILES = ("mixed", "low-density", "capacity-shortage", "cold-dg-blocked")


def generate(size, seed, profile, as_of):
    """Distributions derive from the versioned generator plus declared negative controls."""
    snapshot = make_snapshot(size=size, seed=seed, as_of=as_of)
    if profile == "mixed":
        return snapshot
    d = snapshot.model_dump(mode="json")
    if profile == "low-density":
        d["flights"] = [f for f in d["flights"] if f["id"].endswith(("1", "4"))]
        ids = {f["id"] for f in d["flights"]}
        d["route_permissions"] = [p for p in d["route_permissions"] if p["flight_id"] in ids]
    elif profile == "capacity-shortage":
        for f in d["flights"]:
            f["free_mass_kg"] = str(Decimal(f["free_mass_kg"]) / 4)
            f["free_volume_m3"] = str(Decimal(f["free_volume_m3"]) / 4)
            for p in f["positions"]:
                p["slot_count"] //= 2
        for w in d["handling_windows"]:
            w["capacity_units"] //= 2
    elif profile == "cold-dg-blocked":
        units = {u["id"]: u for u in d["cargo_units"]}
        for p in d["route_permissions"]:
            u = units[p["cargo_unit_id"]]
            if u["requires_cold_chain"]:
                p["cold_chain"]["state"] = "UNKNOWN"
            if u["dg_class"] != "NONE":
                p["dg"]["state"] = "FAIL"
    else:
        raise ValueError("Unknown profile")
    return ScenarioSnapshot.model_validate(d)


def percentile(values, q):
    """Linear interpolation; sparse samples remain explicitly exploratory."""
    values = sorted(values)
    i = (len(values) - 1) * q
    lower, upper = int(i), min(int(i) + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (i - lower)


def run(output, sizes, seeds, profiles, max_wall_seconds):
    output.mkdir(parents=True, exist_ok=True)
    at = datetime(2026, 11, 10, tzinfo=timezone.utc)
    rows = []
    import cargopulse_validation.validator as independent_validator

    source_hashes = {
        p.name: sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob("*.py")
    }
    source_hashes["independent_validator"] = sha256(
        Path(independent_validator.__file__).read_bytes()
    ).hexdigest()
    import cargopulse_contracts.models as contract_models
    import cargopulse_validation.metrics as independent_metrics

    source_hashes["independent_metrics"] = sha256(
        Path(independent_metrics.__file__).read_bytes()
    ).hexdigest()
    source_hashes["contract_models"] = sha256(
        Path(contract_models.__file__).read_bytes()
    ).hexdigest()
    source_hashes["domain_generator"] = sha256(
        Path(
            __import__("packages.domain_fixtures.generator", fromlist=["make_snapshot"]).__file__
        ).read_bytes()
    ).hexdigest()
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    environment = {
        "python": platform.python_version(),
        "logical_cpu_count": os.cpu_count(),
        "base_revision": revision,
        "source_sha256": source_hashes,
        "os": platform.system(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "solver": highspy.Highs().version(),
        "solver_threads": 1,
        "scope": "exploratory synthetic single-process warm-library; no production SLA, no concurrency",
        "quantile_method": "linear interpolation",
        "as_of": at.isoformat(),
        "generator": "packages.domain_fixtures.generator-v1 plus benchmark.generate-v1",
        "seeds": seeds,
        "sizes": sizes,
        "profiles": profiles,
        "max_wall_seconds": max_wall_seconds,
    }
    (output / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    for size in sizes:
        for seed in seeds:
            for profile in profiles:
                snapshot = generate(size, seed, profile, at)
                candidates = build_feasible_paths(snapshot)
                eligible = len({p.cargo_unit_id for p in candidates.paths})
                for name, policy in [
                    ("highs", lambda s: run_solver(s, max_wall_seconds)),
                    ("earliest", run_baseline_earliest),
                    ("priority", run_baseline_priority),
                ]:
                    start = perf_counter()
                    plan = policy(snapshot)
                    elapsed = (perf_counter() - start) * 1000
                    row = {
                        "size": size,
                        "seed": seed,
                        "profile": profile,
                        "policy": name,
                        "wall_ms": elapsed,
                        "status": plan.solver.status.value,
                        "validation": plan.independent_validation.status,
                        "weighted_delay_hours": str(
                            sum((a.weighted_delay_hours for a in plan.assignments), Decimal(0))
                        ),
                        "objective": str(plan.solver.objective_value)
                        if plan.solver.objective_value is not None
                        else None,
                        "best_bound": str(plan.solver.best_bound)
                        if plan.solver.best_bound is not None
                        else None,
                        "gap": str(plan.solver.optimality_gap)
                        if plan.solver.optimality_gap is not None
                        else None,
                        "assigned": len(plan.assignments),
                        "unassigned": len(plan.unassigned),
                        "recoverable_uld_denominator": eligible,
                        "all_affected_uld_denominator": size,
                        "candidate_count": len(candidates.paths),
                        "pruned_paths": candidates.pruned_path_count,
                        "snapshot_hash": canonical_hash(snapshot),
                        "policy_hash": canonical_hash(snapshot.policy),
                    }
                    stem = f"{size}-{seed}-{profile}-{name}"
                    # Retain complete plans and a compact raw row for every run.
                    (output / f"{stem}.json").write_text(
                        json.dumps({"run": row, "plan": plan.model_dump(mode="json")}, indent=2)
                        + "\n"
                    )
                    rows.append(row)
    with (output / "raw.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summaries = []
    for size in sizes:
        for profile in profiles:
            for name in ("highs", "earliest", "priority"):
                selected = [
                    r
                    for r in rows
                    if r["size"] == size and r["profile"] == profile and r["policy"] == name
                ]
                values = [r["wall_ms"] for r in selected]
                summaries.append(
                    {
                        "size": size,
                        "profile": profile,
                        "policy": name,
                        "sample_count": len(values),
                        "p50_ms": percentile(values, 0.5),
                        "p95_ms": percentile(values, 0.95),
                        "p99_ms": percentile(values, 0.99),
                        "max_ms": max(values),
                        "validator_failures": sum(r["validation"] != "PASS" for r in selected),
                        "statuses": {
                            status: sum(r["status"] == status for r in selected)
                            for status in sorted({r["status"] for r in selected})
                        },
                    }
                )
    (output / "summary.json").write_text(json.dumps(summaries, indent=2) + "\n")
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sizes", type=int, nargs="+", default=[50, 140, 400, 800, 1200])
    parser.add_argument("--seeds", type=int, nargs="+", default=[101])
    parser.add_argument("--profiles", choices=PROFILES, nargs="+", default=["mixed"])
    parser.add_argument("--max-wall-seconds", type=int, default=30)
    args = parser.parse_args()
    summaries = run(args.output, args.sizes, args.seeds, args.profiles, args.max_wall_seconds)
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
