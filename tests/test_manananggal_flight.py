"""
Headless tests for the Manananggal flight behaviour (manananggal_flight.py)
and its Enemy integration.

Run: python tests/test_manananggal_flight.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
from manananggal_flight import (
    FlightController, make_flight_controller,
    CHASE, LOITER, FLEE, DESCEND, STRIKE, FLYING_TYPES,
)


class FlatMap:
    width = 120
    height = 120

    def is_solid(self, x, y):
        return False

    def resolve_circle_collision(self, x, y, radius):
        return x, y

    def clamp_position(self, x, y, radius):
        m = 2.0 + radius
        return max(m, min(x, self.width - m)), max(m, min(y, self.height - m))


class ReliefMap(FlatMap):
    """Terrain height rises toward the far side so altitude has something to track."""

    def __init__(self):
        xg = np.linspace(0.0, 4.0, self.width)
        base = 2.0 * np.sin(xg * 0.9) ** 2
        self.terrain_height = np.tile(base[None, :], (self.height, 1))


def test_factory_type_gating():
    assert make_flight_controller('manananggal', 2.5) is not None
    assert make_flight_controller('aswang', 2.0) is None
    assert make_flight_controller('kapre', 1.2) is None
    assert 'manananggal' in FLYING_TYPES


def test_altitude_never_exceeds_cap_on_flat_terrain():
    m = FlatMap()
    fc = make_flight_controller('manananggal', 2.5)
    fc.set_origin(60, 60)
    for _ in range(900):
        fc.update(1.0 / 60.0, 60, 60, CHASE, m)
        assert fc.altitude <= fc.altitude_max + 1e-9, fc.altitude
        assert fc.altitude >= fc.altitude_min - 1e-9, fc.altitude


def test_altitude_tracks_terrain_relief():
    m = ReliefMap()
    fc = make_flight_controller('manananggal', 2.5)
    fc.set_origin(30, 60)
    spans = set()
    for _ in range(2000):
        fc.update(1.0 / 60.0, 0.0, 0.0, LOITER, m)
        loft = fc.altitude - fc.terrain_height
        assert fc.altitude_min - 1e-9 <= loft <= fc.altitude_max + 1e-9, (loft, fc.altitude)
        spans.add(round(fc.terrain_height, 2))
    # Loitering across the relief must sample *different* ground heights, proving
    # the altitude is terrain-relative (the valley shows through).
    assert len(spans) > 1, spans


def test_flee_stays_on_far_side_of_threat():
    m = FlatMap()
    fc = make_flight_controller('manananggal', 4.0)
    fc.set_origin(60, 60)
    threat = (80, 60)
    for _ in range(400):
        fc.update(1.0 / 60.0, threat[0], threat[1], FLEE, m)
    dist = ((fc.x - threat[0]) ** 2 + (fc.y - threat[1]) ** 2) ** 0.5
    assert dist > fc.flee_radius * 0.5, dist


def test_stays_inside_playable_box():
    m = FlatMap()
    fc = make_flight_controller('manananggal', 8.0)
    fc.set_origin(60, 3)
    for _ in range(600):
        x, y = fc.update(1.0 / 60.0, 60, 3, LOITER, m)
        assert 2.4 - 1e-9 <= x <= 117.6 + 1e-9
        assert 2.4 - 1e-9 <= y <= 117.6 + 1e-9


def test_descend_keeps_medium_band():
    m = FlatMap()
    fc = make_flight_controller('manananggal', 2.5)
    fc.set_origin(60, 60)
    for _ in range(500):
        fc.update(1.0 / 60.0, 60, 60, DESCEND, m)
        assert fc.altitude_min - 1e-9 <= fc.altitude <= fc.altitude_max + 1e-9


def test_strike_dives_low_then_climbs_back():
    m = FlatMap()
    fc = make_flight_controller('manananggal', 2.5)
    fc.set_origin(60, 60)
    # Establish the high cruising altitude first.
    for _ in range(200):
        fc.update(1.0 / 60.0, 60, 60, CHASE, m)
    high = fc.altitude
    assert high >= fc.altitude_min, high
    # STRIKE: it dives down to the low strike band to attack the player.
    for _ in range(300):
        fc.update(1.0 / 60.0, 60, 60, STRIKE, m)
    low = fc.altitude
    assert low < fc.strike_altitude + fc.strike_min + 1e-6, low
    assert low < high, (low, high)                 # it genuinely descended
    # Back to cruising: it climbs back up to the high band.
    for _ in range(300):
        fc.update(1.0 / 60.0, 60, 60, CHASE, m)
    assert fc.altitude > low, (fc.altitude, low)   # and it climbed back up


def test_enemy_integration():
    from enemies import Enemy, EnemyState
    flier = Enemy('manananggal', 60.0, 60.0)
    grounded = Enemy('aswang', 60.0, 60.0)
    assert flier.flight is not None
    assert grounded.flight is None
    assert grounded.flight_lift == 0.0

    m = FlatMap()
    # Not engaged, cruising from spawn: it flies HIGH (well above the ground).
    flier.frenzy = False
    flier.state = EnemyState.IDLE
    for _ in range(120):
        flier.update(1.0 / 60.0, 120.0, 120.0, m)   # player far away -> LOITER
    assert flier.flight_lift >= flier.flight.altitude_min - 1e-6, flier.flight_lift

    # Now actively attacking the player up close: it DIVES to the low strike band.
    flier.state = EnemyState.ATTACK
    flier.frenzy = False
    for _ in range(300):
        flier.update(1.0 / 60.0, flier.x + 1.0, flier.y, m)   # player right on it
    assert flier.flight_lift < flier.flight.strike_altitude + flier.flight.strike_min + 1e-6, flier.flight_lift


def main():
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in fns:
        fn()
        print(f'  [ok] {fn.__name__}')
    print(f'All {len(fns)} manananggal-flight tests passed.')


if __name__ == '__main__':
    main()
