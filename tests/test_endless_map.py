"""
Endless-map tests for ANINO SA GUBAT. Pure Python + NumPy: no pygame or display needed.

    python tests/test_endless_map.py
"""
import math
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import settings as S
from map_system import GameMap


def test_determinism_and_chunk_stability():
    for ch in (1, 2):
        a, b = GameMap(ch), GameMap(ch)
        ta = sorted((round(t['x'], 6), round(t['y'], 6), t['type']) for t in a.trees)
        tb = sorted((round(t['x'], 6), round(t['y'], 6), t['type']) for t in b.trees)
        assert ta == tb and len(ta) > 500
    # a chunk that was dropped and regenerated must come back identical
    m = GameMap(1)
    before = sorted((round(t['x'], 6), round(t['y'], 6)) for t in m.trees_near(100, 100, 20))
    m._chunks.clear()
    after = sorted((round(t['x'], 6), round(t['y'], 6)) for t in m.trees_near(100, 100, 20))
    assert before and before == after


def test_entities_never_inside_trees():
    for ch in (1, 2):
        m = GameMap(ch)
        assert not m.validation_errors
        for e in m.enemies:
            assert not m.is_solid(e['x'], e['y'])
        for p in m.pickups:
            assert not m.is_solid(p['x'], p['y'])
        assert not m.is_solid(*m.exit_pos)
        assert not m.is_solid(*m.player_start)


def test_trees_everywhere_with_sane_density():
    m = GameMap(1)
    for (x, y) in [(500, 500), (-300, -200), (0, -1000), (5000, -5000)]:
        density = len(m.trees_near(x, y, 20)) / (math.pi * 20 * 20)
        assert 0.03 < density < 0.2, (x, y, density)


def test_no_boundary_and_features_respected():
    m = GameMap(1)
    assert not m.is_wall(-5, -5) and not m.is_wall(70, 70)      # old stone border is gone
    assert m.is_wall(28.5, 30)                                  # cabin wall is still solid
    assert not any(m.get_tile(t['x'], t['y']) == S.WATER for t in m.trees)
    assert not any(27 <= t['x'] <= 38 and 27 <= t['y'] <= 38 for t in m.trees)


def test_streaming_memory_is_bounded():
    m = GameMap(1)
    for i in range(0, 2000, 2):
        m.update_streaming(i, i * 0.5)
    cap = (2 * S.CHUNK_KEEP_RADIUS + 1) ** 2 + (2 * S.CHUNK_LOAD_RADIUS + 1) ** 2
    assert len(m._chunks) <= cap


if __name__ == '__main__':
    t0 = time.time()
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print(f"[PASS] {name}")
    print(f"=== ENDLESS MAP TESTS PASSED in {time.time() - t0:.2f}s ===")
