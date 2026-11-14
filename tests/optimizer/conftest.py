"""Deterministic adversarial Recover fixtures, independent of optimizer internals."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from cargopulse_contracts import ScenarioSnapshot

from packages.domain_fixtures.generator import make_snapshot

NOW = datetime(2026, 11, 10, tzinfo=timezone.utc)


def iso(hour):
    return (NOW + timedelta(hours=hour)).isoformat()


def weighted_snapshot():
    d = make_snapshot(size=2, seed=1, as_of=NOW).model_dump(mode="json")
    d["valid_until"] = iso(30)
    d["policy"]["source_max_age_seconds"] = 604800
    d["policy"]["handling_penalty_weighted_hours"] = "0"
    d["policy"]["stability_penalty_weighted_hours"] = "0"
    base_f, base_w, base_perm = d["flights"][0], d["handling_windows"][0], d["route_permissions"][0]
    flights, windows = [], []
    for fid, departure, arrival in [("NOW", 2, 4), ("A-LATER", 6, 8), ("B-LATER", 26, 28)]:
        f = deepcopy(base_f)
        f.update(
            id=fid,
            destination="FRA",
            departure_at=iso(departure),
            arrival_at=iso(arrival),
            cutoff_at=iso(departure - 0.5),
            free_mass_kg="2000",
            free_volume_m3="10",
        )
        f["positions"][0].update(slot_count=1, free_mass_kg="2000", free_volume_m3="10")
        flights.append(f)
        w = deepcopy(base_w)
        w.update(
            id="H-" + fid,
            start_at=iso(departure - 1),
            end_at=iso(departure - 0.5),
            capacity_units=1,
        )
        windows.append(w)
    for i, u in enumerate(d["cargo_units"]):
        u.update(
            destination="FRA",
            service_weight="2" if i == 0 else "1",
            commitment_at=iso(4),
            service_class="GENERAL",
            requires_cold_chain=False,
            dg_class="NONE",
            actual_mass_kg="1000",
            actual_volume_m3="4",
        )
        u["pieces"][0].update(mass_kg="950", volume_m3="4")
    permissions = []
    for uid, fids in [("U-0001", ["NOW", "A-LATER"]), ("U-0002", ["NOW", "B-LATER"])]:
        for fid in fids:
            p = deepcopy(base_perm)
            p.update(cargo_unit_id=uid, flight_id=fid)
            permissions.append(p)
    d.update(flights=flights, handling_windows=windows, route_permissions=permissions)
    return ScenarioSnapshot.model_validate(d)


def edit(snapshot, mutate):
    d = snapshot.model_dump(mode="json")
    mutate(d)
    return ScenarioSnapshot.model_validate(d)


@pytest.fixture
def weighted():
    return weighted_snapshot()
