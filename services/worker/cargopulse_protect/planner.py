"""Deterministic synthetic flight generator, two-stage HiGHS load planner and priority fill."""

from __future__ import annotations

import random
from dataclasses import dataclass
from time import monotonic

import highspy

SCOPE = (
    "SYNTHETIC_PROTECT_SANDBOX; one belly flight; aggregate payload mass and volume only; "
    "no positions, balance, DG segregation or load-control approval"
)
VOLUMETRIC_KG_PER_M3 = 167
SERVICE_WEIGHT = {"GENERAL": 1, "PRIORITY": 2, "EXPRESS": 3}


@dataclass(frozen=True)
class Shipment:
    id: str
    service_class: str
    guaranteed: bool
    weight_kg: int
    volume_m3: float

    @property
    def priority_weight(self) -> int:
        return SERVICE_WEIGHT[self.service_class]

    @property
    def chargeable_kg(self) -> int:
        return max(self.weight_kg, round(VOLUMETRIC_KG_PER_M3 * self.volume_m3))

    @property
    def density(self) -> float:
        return self.weight_kg / self.volume_m3


@dataclass(frozen=True)
class SandboxFlight:
    seed: int
    flight_number: str
    payload_kg: int
    volume_m3: float
    shipments: tuple[Shipment, ...]


def make_flight(seed: int, shipments: int = 45, demand: float = 1.5) -> SandboxFlight:
    """Seeded synthetic bookings whose total volume is `demand` x the hold volume."""
    rng = random.Random(seed)  # noqa: S311 - reproducible synthetic fixture, not security.
    payload_kg, volume_m3 = 20_000, 120.0
    raw = [rng.uniform(0.6, 6.0) for _ in range(shipments)]
    scale = demand * volume_m3 / sum(raw)
    items = []
    for index, size in enumerate(raw, start=1):
        volume = round(max(0.2, size * scale), 2)
        density = rng.uniform(85, 320)
        roll = rng.random()
        service = "EXPRESS" if roll < 0.12 else "PRIORITY" if roll < 0.35 else "GENERAL"
        items.append(
            Shipment(
                id=f"AWB-{seed % 1000:03d}-{index:03d}",
                service_class=service,
                guaranteed=service == "EXPRESS" and rng.random() < 0.4,
                weight_kg=max(10, round(volume * density)),
                volume_m3=volume,
            )
        )
    # Guaranteed bookings must themselves fit; otherwise the sandbox would be infeasible.
    used_w = used_v = 0.0
    feasible = []
    for s in items:
        if s.guaranteed and (
            used_w + s.weight_kg > 0.5 * payload_kg or used_v + s.volume_m3 > 0.5 * volume_m3
        ):
            s = Shipment(s.id, s.service_class, False, s.weight_kg, s.volume_m3)
        if s.guaranteed:
            used_w, used_v = used_w + s.weight_kg, used_v + s.volume_m3
        feasible.append(s)
    return SandboxFlight(seed, f"SYN{seed % 900 + 100}", payload_kg, volume_m3, tuple(feasible))


def plan_priority_fill(flight: SandboxFlight) -> tuple[set[str], dict]:
    """Reference rule: guaranteed first, then priority, then booking order; skip misfits."""
    order = sorted(
        flight.shipments,
        key=lambda s: (not s.guaranteed, -s.priority_weight, s.id),
    )
    loaded: set[str] = set()
    weight = volume = 0.0
    for s in order:
        if weight + s.weight_kg <= flight.payload_kg and volume + s.volume_m3 <= flight.volume_m3:
            loaded.add(s.id)
            weight += s.weight_kg
            volume += s.volume_m3
    return loaded, {"status": "GREEDY_REFERENCE", "solve_ms": 0.0}


def _highs(flight: SandboxFlight) -> highspy.Highs:
    h = highspy.Highs()
    for key, value in {
        "output_flag": False,
        "threads": 1,
        "random_seed": 0,
        "mip_rel_gap": 0.0,
        "mip_abs_gap": 0.0,
        "time_limit": 5.0,
    }.items():
        h.setOptionValue(key, value)
    n = len(flight.shipments)
    for i, s in enumerate(flight.shipments):
        h.addVar(1 if s.guaranteed else 0, 1)
        h.changeColIntegrality(i, highspy.HighsVarType.kInteger)
    cols = list(range(n))
    h.addRow(0, flight.payload_kg, n, cols, [float(s.weight_kg) for s in flight.shipments])
    h.addRow(0, flight.volume_m3, n, cols, [float(s.volume_m3) for s in flight.shipments])
    h.changeObjectiveSense(highspy.ObjSense.kMaximize)
    return h


def plan_with_optimizer(flight: SandboxFlight) -> tuple[set[str], dict]:
    """Stage 1: most priority-weighted shipments. Stage 2: hold it, maximise chargeable kg."""
    started = monotonic()
    h = _highs(flight)
    n = len(flight.shipments)
    for i, s in enumerate(flight.shipments):
        h.changeColCost(i, float(s.priority_weight))
    h.run()
    status = h.getModelStatus()
    if status == highspy.HighsModelStatus.kInfeasible:
        return set(), {"status": "INFEASIBLE", "solve_ms": (monotonic() - started) * 1000}
    stage1_optimal = status == highspy.HighsModelStatus.kOptimal
    best = round(h.getInfo().objective_function_value)
    if stage1_optimal:
        h.addRow(best, highspy.kHighsInf, n, list(range(n)),
                 [float(s.priority_weight) for s in flight.shipments])
        for i, s in enumerate(flight.shipments):
            h.changeColCost(i, float(s.chargeable_kg))
        h.run()
        status = h.getModelStatus()
    solution = h.getSolution()
    if not solution.value_valid:
        return set(), {"status": "TIME_LIMIT", "solve_ms": (monotonic() - started) * 1000}
    loaded = {s.id for s, x in zip(flight.shipments, solution.col_value, strict=True) if x > 0.5}
    label = (
        "OPTIMAL"
        if stage1_optimal and status == highspy.HighsModelStatus.kOptimal
        else "FEASIBLE"
    )
    return loaded, {"status": label, "solve_ms": (monotonic() - started) * 1000}
