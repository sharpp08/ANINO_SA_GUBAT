"""Enemy loot-drop checks (headless).   python tests/test_enemy_drops.py"""
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from enemies import Enemy, EnemyManager, DROP_TABLE, roll_drop  # noqa: E402


class FakePlayer:
    health = 100
    ammo_shotgun = 16
    ammo_revolver = 24
    flashlight_battery = 100
    faith_energy = 100
    salt_count = 10
    garlic_count = 8


class FakeMap:
    def __init__(self, solid=False):
        self.pickups = [{'type': 'health', 'x': 1, 'y': 1, 'amount': 5, 'active': False, 'drop': True},
                        {'type': 'bible_page', 'x': 2, 'y': 2, 'amount': 1, 'active': False}]
        self._solid = solid

    def is_solid(self, x, y):
        return self._solid and abs(x - 5.0) < 0.01 and abs(y - 5.0) < 0.01


def test_roll_distribution():
    rng = random.Random(1)
    counts, none = {}, 0
    for _ in range(4000):
        r = roll_drop('aswang', None, rng)
        if r is None:
            none += 1
            continue
        item, amount = r
        lo, hi = DROP_TABLE[item][1:]
        assert lo <= amount <= hi
        assert item != 'bible_page'
        counts[item] = counts.get(item, 0) + 1
    assert 0.3 < none / 4000 < 0.5, none           # ~40% of kills drop nothing
    assert set(counts) == set(DROP_TABLE), counts   # every item type can drop
    print("roll_drop distribution OK:", counts, "none:", none)


def test_need_weighting():
    rng = random.Random(2)
    p = FakePlayer()
    p.health = 100                 # full: must never drop health
    p.ammo_shotgun = 1             # nearly out: boosted
    got = [roll_drop('kapre', p, rng) for _ in range(3000)]
    items = [g[0] for g in got if g]
    assert 'health' not in items
    assert items.count('ammo_shotgun') > items.count('ammo_revolver') * 1.4
    print("need weighting OK")


def test_collect_drops():
    random.seed(5)
    mgr = EnemyManager()
    mgr.enemies = [Enemy('kapre', 5.0, 5.0) for _ in range(40)]
    for e in mgr.enemies:
        e.take_damage(99999)
    gm = FakeMap(solid=True)
    drops = mgr.collect_drops(gm, FakePlayer())
    assert 20 < len(drops) <= 40, len(drops)                    # kapre ~85%
    assert all(d['active'] and d['drop'] for d in drops)
    assert all((d['x'], d['y']) != (5.0, 5.0) for d in drops)   # nudged out of the solid tile
    # old picked-up drop removed, the story pickup kept
    assert not any(p['x'] == 1 for p in gm.pickups)
    assert any(p['type'] == 'bible_page' for p in gm.pickups)
    # each death is only rolled once
    assert mgr.collect_drops(gm, FakePlayer()) == []
    print(f"collect_drops OK: {len(drops)}/40 kills dropped loot")


if __name__ == '__main__':
    test_roll_distribution()
    test_need_weighting()
    test_collect_drops()
    print("[PASS] enemy drops")
