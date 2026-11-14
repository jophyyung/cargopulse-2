"""Synthetic Protect sandbox: pre-cutoff AWB load planning for one belly flight.

Scope: aggregate payload-mass and volume envelope only. No hold positions, ULD build-up,
balance, DG segregation or airline approval are modelled. Nothing is persisted or sent.
"""

from .planner import (
    SCOPE,
    VOLUMETRIC_KG_PER_M3,
    SandboxFlight,
    Shipment,
    make_flight,
    plan_priority_fill,
    plan_with_optimizer,
)

__all__ = [
    "SCOPE",
    "VOLUMETRIC_KG_PER_M3",
    "SandboxFlight",
    "Shipment",
    "make_flight",
    "plan_priority_fill",
    "plan_with_optimizer",
]
