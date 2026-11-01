"""Checks the enhanced ground terrain.  Pure numpy: runs anywhere, no pygame needed.

    python tests/test_terrain_gen.py
"""
import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import terrain_gen as tg                      # noqa: E402
from floor_fast import fill_floor, fill_floor_terrain   # noqa: E402

SIZE = 256   # small atlas keeps the test quick; art code scales with size

_cache = {}


def atlas():
    if 'a' not in _cache:
        _cache['a'] = tg.bake_terrain_atlas(SIZE, 1337)
    return _cache['a']


def demo_grid():
    g = np.zeros((64, 64), dtype=np.uint8)
    g[8:24, 8:24] = 3
    g[12:16, 12:20] = 6
    g[30:50, 30:50] = 4
    g[28:34, :] = 1
    g[40:60, 5:20] = 5
    g[5:15, 40:60] = 2
    return g


def test_atlas_shape_and_range():
    a, far = atlas()
    assert a.shape == (len(tg.TERRAIN_NAMES), SIZE, SIZE, 3) and a.dtype == np.uint8
    assert far.shape == a.shape and far.dtype == np.uint8
    for i, name in enumerate(tg.TERRAIN_NAMES):
        m = float(a[i].mean())
        assert 15 < m < 110, '%s has implausible brightness %.1f' % (name, m)
        assert a[i].std() > 4, '%s is flat' % name


def test_terrains_are_distinct():
    a, _ = atlas()
    means = np.array([a[i].reshape(-1, 3).mean(axis=0) for i in range(len(tg.TERRAIN_NAMES))])
    for i in range(len(means)):
        for j in range(i + 1, len(means)):
            assert np.abs(means[i] - means[j]).max() > 3, '%s ~ %s' % (tg.TERRAIN_NAMES[i], tg.TERRAIN_NAMES[j])


def test_seamless_tiling():
    a, _ = atlas()
    for i, name in enumerate(tg.TERRAIN_NAMES):
        t = a[i].astype(np.float32)
        interior = np.abs(t[1:] - t[:-1]).mean()
        seam_x = np.abs(t[0] - t[-1]).mean()
        seam_y = np.abs(t[:, 0] - t[:, -1]).mean()
        assert seam_x < interior * 1.6 + 1.0 and seam_y < interior * 1.6 + 1.0, \
            '%s seam %.2f/%.2f vs interior %.2f' % (name, seam_x, seam_y, interior)


def test_deterministic():
    a1, _ = tg.bake_terrain_atlas(128, 7)
    a2, _ = tg.bake_terrain_atlas(128, 7)
    a3, _ = tg.bake_terrain_atlas(128, 8)
    assert np.array_equal(a1, a2)
    assert not np.array_equal(a1, a3)


def test_cache_roundtrip(tmp_dir=None):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        a1, f1 = tg.load_or_bake_atlas(d, 128, 5)
        assert os.listdir(d)
        a2, f2 = tg.load_or_bake_atlas(d, 128, 5)
        assert np.array_equal(a1, a2) and np.array_equal(f1, f2)


def test_maps_decode():
    g = demo_grid()
    m = tg.build_terrain_maps(g, 1337, fine=4)
    p = m['packed']
    assert p.dtype == np.uint16 and p.shape == (64 * 4, 64 * 4)
    ids = p & 15
    assert set(np.unique(ids)) <= set(range(len(tg.TERRAIN_NAMES)))
    # centres of painted regions keep their terrain id
    for (x, y), want in (((16, 10), 3), ((14, 13), 6), ((40, 40), 4), ((10, 31), 1), ((10, 50), 5), ((50, 10), 2)):
        assert ids[y * 4 + 2, x * 4 + 2] == want, ((x, y), want, ids[y * 4 + 2, x * 4 + 2])
    edge = (p >> 4) & 15
    assert edge.max() > 0 and edge[0, 0] == 0
    shade = (p >> 8).astype(np.float32) / 128.0
    assert 0.75 < shade.min() and shade.max() < 1.25


def _view(maps, a, far, t, px=20.0, py=18.0, ang=0.4, w=160, h=90):
    arr = np.zeros((w, h, 3), dtype=np.uint8)
    cx = np.linspace(-1, 1, w)
    pl = math.tan(math.radians(33))
    rdx = math.cos(ang) - math.sin(ang) * pl * cx
    rdy = math.sin(ang) + math.cos(ang) * pl * cx
    fill_floor_terrain(arr, a, far, maps['packed'], maps['fine'], maps['w'], maps['h'],
                       px, py, rdx, rdy, h, h // 2, h // 2, 0, 0.5, time_s=t)
    return arr


def test_fill_floor_terrain_runs_and_animates_water():
    a, far = atlas()
    maps = tg.build_terrain_maps(demo_grid(), 1337, fine=4)
    # stand beside the pond and look at it
    v0 = _view(maps, a, far, 0.0, px=14.0, py=18.5, ang=-math.pi / 2)
    v1 = _view(maps, a, far, 1.3, px=14.0, py=18.5, ang=-math.pi / 2)
    assert v0.shape == (160, 90, 3)
    assert v0[:, :45].max() == 0, 'rows above the horizon must be untouched'
    assert v0[:, 46:].mean() > 5, 'floor should be drawn'
    assert not np.array_equal(v0, v1), 'water should shimmer over time'


def test_land_only_view_is_static():
    a, far = atlas()
    maps = tg.build_terrain_maps(demo_grid(), 1337, fine=4)
    v0 = _view(maps, a, far, 0.0, px=45.0, py=45.0, ang=0.0)
    v1 = _view(maps, a, far, 5.0, px=45.0, py=45.0, ang=0.0)
    assert np.array_equal(v0, v1), 'land must not animate'


def test_edge_cases_do_not_crash():
    a, far = atlas()
    maps = tg.build_terrain_maps(demo_grid(), 1337, fine=4)
    for px, py in ((0.1, 0.1), (63.9, 63.9), (-3.0, 70.0)):         # at / beyond the map border
        _view(maps, a, far, 0.0, px=px, py=py, ang=2.0)
    arr = np.zeros((160, 90, 3), dtype=np.uint8)                     # horizon at the very bottom -> nothing to draw
    fill_floor_terrain(arr, a, far, maps['packed'], maps['fine'], 64, 64, 20.0, 20.0,
                       np.ones(160), np.zeros(160), 90, 45, 90, 0, 0.0)
    assert arr.max() == 0


def test_speed_is_comparable_to_legacy_floor():
    a, far = atlas()
    maps = tg.build_terrain_maps(demo_grid(), 1337, fine=4)
    w, h = 480, 270
    cx = np.linspace(-1, 1, w)
    rdx = math.cos(0.4) - math.sin(0.4) * 0.65 * cx
    rdy = math.sin(0.4) + math.cos(0.4) * 0.65 * cx
    ground = np.random.default_rng(1).integers(0, 255, (1024, 1024, 3), dtype=np.uint8)
    lut = np.ones((7, 3), dtype=np.float32)
    arr = np.zeros((w, h, 3), dtype=np.uint8)

    def bench(fn, n=12):
        fn()
        t0 = time.perf_counter()
        for _ in range(n):
            fn()
        return (time.perf_counter() - t0) / n * 1000.0

    old = bench(lambda: fill_floor(arr, ground, lut, maps_grid, 64, 64, 20.0, 18.0, rdx, rdy, h, h // 2, h // 2, 0, 0.5))
    new = bench(lambda: fill_floor_terrain(arr, a, far, maps['packed'], maps['fine'], 64, 64, 20.0, 18.0,
                                           rdx, rdy, h, h // 2, h // 2, 0, 0.5, time_s=1.0))
    print('   legacy %.1f ms   terrain %.1f ms   (%dx%d)' % (old, new, w, h))
    assert new < old * 2.5 + 3.0, 'enhanced floor is too slow: %.1f vs %.1f ms' % (new, old)


maps_grid = demo_grid()

if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print('PASS', t.__name__)
        except Exception as exc:                  # noqa: BLE001
            failed += 1
            print('FAIL', t.__name__, '-', exc)
    sys.exit(1 if failed else 0)
