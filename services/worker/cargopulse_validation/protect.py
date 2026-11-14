"""Independent re-check of a Protect sandbox load plan from the raw booking list.

Deliberately does not import the planner: totals are recomputed from the shipment rows.
"""

from __future__ import annotations


def check_protect_load(
    rows: list[dict], loaded_ids: set[str], payload_kg: int, volume_m3: float
) -> list[str]:
    """Return findings; an empty list means PASS."""
    findings = []
    known = {r["id"] for r in rows}
    if loaded_ids - known:
        findings.append("UNKNOWN_SHIPMENT_LOADED")
    weight = sum(int(r["weight_kg"]) for r in rows if r["id"] in loaded_ids)
    volume = sum(float(r["volume_m3"]) for r in rows if r["id"] in loaded_ids)
    if weight > payload_kg:
        findings.append("PAYLOAD_MASS_EXCEEDED")
    if volume > volume_m3 + 1e-9:
        findings.append("HOLD_VOLUME_EXCEEDED")
    if any(r["guaranteed"] and r["id"] not in loaded_ids for r in rows):
        findings.append("GUARANTEED_SHIPMENT_OFFLOADED")
    return findings
