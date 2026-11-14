"""Seeded whole-ULD recovery events with explicit synthetic evidence.

Distributions are engineering test profiles, not calibrated airline traffic. Each
unit has one physical piece and tare; AWB splits are covered by dedicated tests.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from uuid import UUID

from cargopulse_contracts import ScenarioSnapshot

TENANT_A = UUID("10000000-0000-4000-8000-000000000001")
TENANT_B = UUID("10000000-0000-4000-8000-000000000002")


def make_snapshot(
    size: int = 140, seed: int = 101, as_of: datetime | None = None, tenant_id: UUID = TENANT_A
) -> ScenarioSnapshot:
    rng = random.Random(seed)
    t = (as_of or datetime.now(timezone.utc)).replace(microsecond=0)

    def iso(x):
        return x.isoformat().replace("+00:00", "Z")

    def proof(state="PASS"):
        return dict(
            state=state,
            source_record_id=f"synthetic-rule-{seed}",
            observed_at=iso(t),
            valid_until=iso(t + timedelta(hours=72)),
            rule_revision="synthetic-v1",
        )

    destinations = ["FRA", "AMS", "LHR", "LAX", "SYD", "DXB", "BOM", "SIN"]
    zones = [
        "Europe/Berlin",
        "Europe/Amsterdam",
        "Europe/London",
        "America/Los_Angeles",
        "Australia/Sydney",
        "Asia/Dubai",
        "Asia/Kolkata",
        "Asia/Singapore",
    ]
    flights, windows = [], []
    for i, dest in enumerate(destinations):
        for k in range(4):
            fid = f"F-{dest}-{k + 1}"
            departure = t + timedelta(hours=3 + k * 12 + i / 4)
            cutoff = departure - timedelta(minutes=45)
            slots = max(1, size // 32 + rng.randint(0, 2))
            flights.append(
                dict(
                    id=fid,
                    flight_number=f"SYN{i + 1}{k + 1}",
                    origin="HKG",
                    destination=dest,
                    departure_at=iso(departure),
                    arrival_at=iso(departure + timedelta(hours=4 + i)),
                    cutoff_at=iso(cutoff),
                    origin_timezone="Asia/Hong_Kong",
                    destination_timezone=zones[i],
                    aircraft_variant="SYNTHETIC-ENVELOPE",
                    is_freighter=k % 2 == 0,
                    status="SCHEDULED",
                    free_mass_kg=str(slots * 1400),
                    free_volume_m3=str(slots * 6),
                    positions=[
                        dict(
                            id="POOL",
                            free_mass_kg=str(slots * 1400),
                            free_volume_m3=str(slots * 6),
                            slot_count=slots,
                            max_unit_mass_kg="2500",
                            max_unit_volume_m3="12",
                            allowed_uld_types=["AKE", "PMC", "RKN"],
                            allowed_contours=["SYN-A"],
                            envelope_verification=proof(),
                        )
                    ],
                    capacity_verification=proof(),
                )
            )
            windows.append(
                dict(
                    id=f"H-{fid}",
                    airport="HKG",
                    start_at=iso(cutoff - timedelta(hours=2)),
                    end_at=iso(cutoff),
                    capacity_units=slots,
                    equipment_verification=proof(),
                )
            )
    units, permissions = [], []
    classes = ["GENERAL", "PRIORITY", "PHARMA", "PERISHABLE", "DG"]
    for i in range(size):
        uid = f"U-{i + 1:04}"
        service = rng.choices(classes, weights=[50, 20, 10, 15, 5])[0]
        dest = destinations[i % len(destinations)]
        mass = rng.randint(600, 1800)
        volume = rng.randint(2, 8)
        units.append(
            dict(
                id=uid,
                uld_code=f"SYN-{i + 1:04}",
                uld_type="RKN" if service == "PHARMA" else "AKE",
                contour="SYN-A",
                origin="HKG",
                destination=dest,
                actual_mass_kg=str(mass),
                actual_volume_m3=str(volume),
                tare_mass_kg="50",
                pieces=[
                    dict(
                        piece_id=f"P-{i + 1:04}",
                        awb_id=f"AWB-{i + 1:04}",
                        mass_kg=str(mass - 50),
                        volume_m3=str(volume),
                    )
                ],
                service_class=service,
                service_weight="2.5" if service in ("PRIORITY", "PHARMA") else "1",
                ready_at=iso(t),
                commitment_at=iso(t + timedelta(hours=rng.randint(8, 30))),
                requires_cold_chain=service in ("PHARMA", "PERISHABLE"),
                dg_class="FREIGHTER_ONLY" if service == "DG" else "NONE",
                serviceability=proof(),
                security=proof(),
            )
        )
        for f in flights:
            if f["destination"] != dest:
                continue
            # Every eleventh unit is a negative control with no verified customs clearance.
            permissions.append(
                dict(
                    cargo_unit_id=uid,
                    flight_id=f["id"],
                    dg=proof(),
                    customs=proof("FAIL" if i % 11 == 10 else "PASS"),
                    cold_chain=proof(
                        "UNKNOWN" if service == "PHARMA" and f["id"].endswith("2") else "PASS"
                    ),
                    load_control=proof(),
                )
            )
    return ScenarioSnapshot.model_validate(
        dict(
            tenant_id=str(tenant_id),
            event_id=f"synthetic-recover-{seed}-{t.strftime('%Y%m%dT%H%M%S')}",
            source_version=1,
            title=f"Synthetic hub disruption / {size} ULDs / seed {seed}",
            as_of=iso(t),
            valid_until=iso(t + timedelta(hours=1)),
            provenance=dict(
                source_id="seeded-synthetic-generator-v1",
                source_record_ids=[f"seed-{seed}"],
                observed_at=iso(t),
                effective_at=iso(t),
                ingested_at=iso(t),
                evidence_tier="TEAM_SYNTHETIC_UNVERIFIED",
            ),
            policy=dict(
                id="synthetic-recover-v1",
                version="1.0.0",
                state="PUBLISHED",
                authored_by="synthetic-policy-author",
                approved_by="synthetic-policy-reviewer",
                published_at=iso(t),
                handling_seconds=900,
                max_legs=3,
                max_paths_per_unit=20,
                unassigned_penalty_weighted_hours="96",
                handling_penalty_weighted_hours="0.1",
                stability_penalty_weighted_hours="2",
                source_max_age_seconds=3600,
                model_scope="SYNTHETIC_CONSERVATIVE_ENVELOPE",
            ),
            cargo_units=units,
            flights=flights,
            handling_windows=windows,
            route_permissions=permissions,
            connections=[],
        )
    )


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    p = argparse.ArgumentParser()
    p.add_argument("--size", type=int, default=140)
    p.add_argument("--seed", type=int, default=101)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(make_snapshot(args.size, args.seed).model_dump_json(indent=2) + "\n")
