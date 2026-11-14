"""Urgency what-if: holding evidence at snapshot time isolates genuine route cliffs."""

from datetime import timedelta

from cargopulse_optimizer import compute_urgency_delta

from packages.domain_fixtures.generator import make_snapshot


def test_default_urgency_still_closes_everything_after_snapshot_expiry():
    s = make_snapshot(8)
    after = s.valid_until + timedelta(minutes=1)
    points = compute_urgency_delta(s, [s.as_of, after])
    later = [p for p in points if p.decision_at == after]
    assert later and all(p.status == "NO_COMPLIANT_PATH" for p in later)


def test_hold_evidence_keeps_routes_until_their_own_cutoffs():
    s = make_snapshot(8)
    after = s.valid_until + timedelta(minutes=1)
    points = compute_urgency_delta(s, [s.as_of, after], hold_evidence=True)
    later = {p.cargo_unit_id: p for p in points if p.decision_at == after}
    # Flights with cutoffs after `after` remain usable in the what-if.
    assert any(p.status == "COMPLIANT_PATH" for p in later.values())
    # Past every cutoff, nothing remains even when evidence is held.
    last = max(f.cutoff_at for f in s.flights) + timedelta(microseconds=1)
    exhausted = compute_urgency_delta(s, [last], hold_evidence=True)
    assert all(p.status == "NO_COMPLIANT_PATH" for p in exhausted)


def test_hold_evidence_matches_default_inside_the_validity_window():
    s = make_snapshot(8)
    inside = [s.as_of, s.as_of + timedelta(minutes=10)]
    assert compute_urgency_delta(s, inside) == compute_urgency_delta(s, inside, hold_evidence=True)
