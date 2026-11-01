"""Checks raycast_fast against the original scalar implementations.

Pure numpy: runs anywhere, no pygame needed.   python tests/test_raycast_fast.py
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from raycast_fast import cast_rays, visible_runs  # noqa: E402

MAX_DEPTH = 35
EMPTY = 0


def ref_dda(px, py, cos_a, sin_a, grid, w, h):
    """Verbatim port of the original Renderer._dda_cast."""
    if cos_a == 0:
        cos_a = 0.00001
    if sin_a == 0:
        sin_a = 0.00001
    x_step = 1 if cos_a > 0 else -1
    y_step = 1 if sin_a > 0 else -1
    map_x = int(px)
    map_y = int(py)
    x_dist = (map_x + 1 - px) / cos_a if cos_a > 0 else (map_x - px) / cos_a
    y_dist = (map_y + 1 - py) / sin_a if sin_a > 0 else (map_y - py) / sin_a
    dx = abs(1 / cos_a)
    dy = abs(1 / sin_a)
    hit = False
    side = 0
    wall_type = 1
    for _ in range(MAX_DEPTH * 4):
        if (x_dist if x_dist < y_dist else y_dist) > MAX_DEPTH:
            break
        if x_dist < y_dist:
            x_dist += dx
            map_x += x_step
            side = 0
        else:
            y_dist += dy
            map_y += y_step
            side = 1
        if map_x < 0 or map_x >= w or map_y < 0 or map_y >= h:
            break
        tile = grid[map_y][map_x]
        if tile != EMPTY:
            wall_type = tile
            hit = True
            break
    if not hit:
        return MAX_DEPTH, 1, 0, 0, False
    if side == 0:
        dist = (map_x - px + (1 - x_step) / 2) / cos_a
        hit_y = py + dist * sin_a
        frac = hit_y - int(hit_y)
    else:
        dist = (map_y - py + (1 - y_step) / 2) / sin_a
        hit_x = px + dist * cos_a
        frac = hit_x - int(hit_x)
    if dist < 0:
        dist = 0.01
    return dist, wall_type, frac, side, True


def test_cast_rays_matches_reference():
    rng = np.random.default_rng(7)
    checked = 0
    for trial in range(60):
        w, h = int(rng.integers(20, 90)), int(rng.integers(20, 90))
        density = rng.choice([0.0, 0.01, 0.05, 0.2])
        grid_np = np.where(rng.random((h, w)) < density, rng.integers(1, 7, (h, w)), 0).astype(np.int32)
        if trial % 5 == 0:  # solid border like the real maps
            grid_np[0, :] = grid_np[-1, :] = 1
            grid_np[:, 0] = grid_np[:, -1] = 1
        grid = grid_np.tolist()
        px, py = float(rng.uniform(1, w - 1)), float(rng.uniform(1, h - 1))
        grid_np[int(py), int(px)] = 0
        grid = grid_np.tolist()
        pa = float(rng.uniform(0, 2 * math.pi))
        offs = (np.arange(640) / 640 - 0.5) * math.radians(60)
        ang = pa + offs
        # include exact axis-aligned rays (cos or sin == 0 path)
        ang[0], ang[1], ang[2], ang[3] = 0.0, math.pi / 2, math.pi, 3 * math.pi / 2
        cos_a, sin_a = np.cos(ang), np.sin(ang)
        cos_a[0], sin_a[1] = 1.0, 1.0
        sin_a[0], cos_a[1] = 0.0, 0.0
        cos_a[2], sin_a[2] = -1.0, 0.0
        cos_a[3], sin_a[3] = 0.0, -1.0

        dist, tile, frac, side, hit = cast_rays(grid_np, w, h, px, py, cos_a, sin_a, MAX_DEPTH, EMPTY)
        for i in range(len(ang)):
            rd, rt, rf, rs, rh = ref_dda(px, py, float(cos_a[i]), float(sin_a[i]), grid, w, h)
            assert bool(hit[i]) == rh, (trial, i, hit[i], rh)
            assert abs(dist[i] - rd) < 1e-9, (trial, i, dist[i], rd)
            if rh:
                assert int(tile[i]) == rt and int(side[i]) == rs, (trial, i)
                assert abs(frac[i] - rf) < 1e-9, (trial, i, frac[i], rf)
            checked += 1
    print(f"cast_rays: {checked} rays match the scalar DDA")


def ref_runs(zb, col_to_ray, x0, x1, dist):
    """Original _blit_zbuf run-finding loop."""
    runs, run = [], None
    for col in range(x0, x1 + 1):
        vis = col < x1 and zb[col_to_ray[col]] > dist
        if vis:
            if run is None:
                run = col
        elif run is not None:
            runs.append((run, col))
            run = None
    return runs


def test_visible_runs_matches_reference():
    rng = np.random.default_rng(3)
    w, nr = 640, 640
    col_to_ray = (np.arange(w) * nr // w).astype(np.int64)
    for _ in range(500):
        zb = rng.uniform(0, 40, nr)
        if rng.random() < 0.3:
            zb[:] = 36.0
        x0 = int(rng.integers(0, w - 1))
        x1 = int(rng.integers(x0, w + 1))
        dist = float(rng.uniform(0, 40))
        assert visible_runs(zb, col_to_ray, x0, x1, dist) == ref_runs(zb, col_to_ray, x0, x1, dist)
    print("visible_runs: matches the per-column loop")


if __name__ == '__main__':
    test_cast_rays_matches_reference()
    test_visible_runs_matches_reference()
    print("[PASS] raycast_fast")
