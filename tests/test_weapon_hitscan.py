"""
Headless tests for the geometric hitscan weapon resolution (no display needed).

Run: python tests/test_weapon_hitscan.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from enemies import Enemy, EnemyManager


class DummyMap:
    """Minimal stand-in for GameMap: only the is_solid queries hitscan performs."""

    def __init__(self, solid_fn):
        self._solid_fn = solid_fn

    def is_solid(self, x, y):
        return self._solid_fn(x, y)

    def is_solid_no_door(self, x, y):
        return self._solid_fn(x, y)


OPEN = DummyMap(lambda x, y: False)
WALL = DummyMap(lambda x, y: abs(x - 3.0) < 0.5)   # solid wall tile at x=3


def make_manager(enemies):
    mgr = EnemyManager()
    mgr.enemies = list(enemies)
    return mgr


def revolver_shot():
    return {'type': 'revolver', 'damage': 30, 'range': 15, 'spread': 0}


def shotgun_shot():
    return {'type': 'shotgun', 'damage': 40, 'range': 8, 'spread': 0.1, 'pellets': 5}


def bolo_shot():
    return {'type': 'bolo', 'damage': 25, 'range': 1.5, 'spread': 0}


def test_shots_do_not_penetrate_walls():
    enemy = Enemy('aswang', 5.0, 1.0)
    hp0 = enemy.health
    mgr = make_manager([enemy])
    hits = mgr.apply_weapon_hit(1.0, 1.0, 0.0, revolver_shot(), WALL)
    assert hits == [], "revolver must not hit an enemy behind a wall"
    assert enemy.health == hp0

    enemy2 = Enemy('aswang', 2.0, 1.0)      # in front of the wall
    mgr2 = make_manager([enemy2])
    hits2 = mgr2.apply_weapon_hit(1.0, 1.0, 0.0, revolver_shot(), WALL)
    assert len(hits2) == 1, "enemy with clear sightline must take the shot"


def test_revolver_misses_off_axis_and_behind():
    off = Enemy('aswang', 5.0, 3.0)         # 3 tiles off the aim ray
    behind = Enemy('aswang', -5.0, 0.0)      # behind the player
    mgr = make_manager([off, behind])
    hits = mgr.apply_weapon_hit(1.0, 1.0, 0.0, revolver_shot(), OPEN)
    assert hits == []

    on = Enemy('aswang', 5.0, 1.0)          # dead on the ray
    assert len(make_manager([on]).apply_weapon_hit(1.0, 1.0, 0.0, revolver_shot(), OPEN)) == 1


def test_shotgun_pellet_fan_is_deterministic():
    results = []
    for _ in range(3):
        enemy = Enemy('aswang', 2.0, 1.0)    # 1 tile ahead, centred
        hp0 = enemy.health
        mgr = make_manager([enemy])
        mgr.apply_weapon_hit(1.0, 1.0, 0.0, shotgun_shot(), OPEN)
        results.append(hp0 - enemy.health)
    assert results[0] > 0, "centred point-blank shot must land"
    assert results[0] == results[1] == results[2], f"pellet damage flickered: {results}"
    # All 5 pellets of a 0.1 rad fan cover a 0.3-r enemy at forward=1
    # (half-width asin(0.3) ~= 0.3046 > 0.1), so full shot damage with the
    # 1 - forward/range falloff: 40 * 1.0 * max(0.3, 1 - 1/8).
    expected = 40.0 * (1.0 - 1.0 / 8.0)
    assert abs(results[0] - expected) < 1e-6, f"expected {expected}, got {results[0]}"


def test_shotgun_does_not_hit_outside_the_fan():
    enemy = Enemy('aswang', 2.0, 1.0 + math.tan(0.5))        # forward 1, ~0.5 rad right of the ray
    mgr = make_manager([enemy])
    assert mgr.apply_weapon_hit(1.0, 1.0, 0.0, shotgun_shot(), OPEN) == []


def test_bolo_reach_and_wall_blocking():
    near = Enemy('aswang', 2.4, 1.0)         # forward 1.4, inside the 1.5 reach
    far = Enemy('aswang', 3.5, 1.0)          # forward 2.5, past the reach
    mgr = make_manager([near, far])
    hits = mgr.apply_weapon_hit(1.0, 1.0, 0.0, bolo_shot(), OPEN)
    assert hits == [near], f"only the near enemy should be within bolo reach, got {hits}"

    walled = Enemy('aswang', 3.0, 1.0)
    assert make_manager([walled]).apply_weapon_hit(1.0, 1.0, 0.0, bolo_shot(), WALL) == []


def test_no_map_keeps_legacy_open_field_behavior():
    on = Enemy('aswang', 5.0, 1.0)
    mgr = make_manager([on])
    assert len(mgr.apply_weapon_hit(1.0, 1.0, 0.0, revolver_shot())) == 1  # game_map=None


if __name__ == '__main__':
    test_shots_do_not_penetrate_walls()
    test_revolver_misses_off_axis_and_behind()
    test_shotgun_pellet_fan_is_deterministic()
    test_shotgun_does_not_hit_outside_the_fan()
    test_bolo_reach_and_wall_blocking()
    test_no_map_keeps_legacy_open_field_behavior()
    print("All weapon hitscan tests passed.")
