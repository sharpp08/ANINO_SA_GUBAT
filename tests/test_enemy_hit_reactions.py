"""Hit-reaction / death-animation logic checks (headless).   python tests/test_enemy_hit_reactions.py"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from enemies import Enemy, EnemyManager, DEATH_ANIM_TIME  # noqa: E402
from anim_integration import RealisticEnemyAnimator  # noqa: E402


class OpenMap:
    def is_solid(self, x, y):
        return False

    # extras the enemy AI may touch
    width = height = 100
    grid = [[0] * 100 for _ in range(100)]


class WallMap(OpenMap):
    def is_solid(self, x, y):
        return x > 10.5


def test_hit_data_and_knockback():
    e = Enemy('aswang', 10.0, 10.0)
    e.spawn_x, e.spawn_y = 10.0, 10.0
    e.take_damage(30, 'physical', (8.0, 10.0))      # shot from the west
    assert e.hit_seq == 1 and 0.25 <= e.hit_strength <= 1.0 and e.hit_side in (-1, 1)
    assert e.kb_vx > 0 and abs(e.kb_vy) < 1e-9       # pushed east, away from the shooter
    assert e.hit_stop > 0
    x0 = e.x
    gm = OpenMap()
    for _ in range(30):
        e._apply_knockback(1 / 60, gm)
    assert e.x > x0 + 0.1 and e.kb_vx == 0.0 or abs(e.kb_vx) < 0.05
    # walls stop the shove
    w = Enemy('aswang', 10.4, 10.0)
    w.take_damage(30, 'physical', (8.0, 10.0))
    for _ in range(30):
        w._apply_knockback(1 / 60, WallMap())
    assert w.x <= 10.5
    # sacred damage: no knockback
    s = Enemy('aswang', 10.0, 10.0)
    s.take_damage(15, 'sacred', (8.0, 10.0))
    assert s.kb_vx == 0.0
    print("hit data + knockback OK")


def test_hit_stop_slows_enemy():
    e = Enemy('aswang', 20.0, 20.0)
    e.take_damage(10, 'physical')
    before = e.hit_stop
    e.update(0.02, 40.0, 40.0, OpenMap())
    assert e.hit_stop < before
    print("hit stop OK")


def test_death_lifecycle():
    e = Enemy('kapre', 10.0, 10.0)
    mgr = EnemyManager()
    mgr.enemies = [e]
    e.take_damage(99999, 'physical', (5.0, 10.0))
    assert not e.alive and e.animation_state == 'death' and e.dying
    assert mgr.get_alive_enemies() == [] and mgr.get_renderable_enemies() == [e]
    t = 0.0
    while t < DEATH_ANIM_TIME + 0.2:
        mgr.update(1 / 60, 50.0, 50.0, OpenMap())
        t += 1 / 60
    assert not e.dying and mgr.get_renderable_enemies() == []
    print("death lifecycle OK")


def test_animator_springs_fire_once_per_hit():
    anim = RealisticEnemyAnimator()
    e = Enemy('aswang', 10.0, 10.0)
    e.spawn_x, e.spawn_y = 10.0, 10.0
    anim.update_all([e], 1 / 60)
    quiet = anim.transform(e, 0.0)
    assert abs(quiet['flinch']) < 1e-6 and abs(quiet['tilt']) < 1e-6
    e.take_damage(40, 'physical', (5.0, 10.0))
    peak_f = peak_t = 0.0
    for i in range(40):
        anim.update_all([e], 1 / 60)
        tr = anim.transform(e, i / 60)
        peak_f = max(peak_f, abs(tr['flinch']))
        peak_t = max(peak_t, abs(tr['tilt']))
    assert peak_f > 0.02 and 1.0 < peak_t < 25.0, (peak_f, peak_t)
    for i in range(200):                      # settles back, does not re-fire
        anim.update_all([e], 1 / 60)
    tr = anim.transform(e, 5.0)
    assert abs(tr['flinch']) < 0.01 and abs(tr['tilt']) < 0.5, tr
    print(f"animator OK (peak flinch {peak_f:.2f}, peak tilt {peak_t:.1f} deg)")


if __name__ == '__main__':
    test_hit_data_and_knockback()
    test_hit_stop_slows_enemy()
    test_death_lifecycle()
    test_animator_springs_fire_once_per_hit()
    print("[PASS] enemy hit reactions")
