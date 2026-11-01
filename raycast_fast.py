"""Vectorised raycasting helpers for the renderer (pure numpy, no pygame).

``cast_rays`` runs the DDA grid walk for *all* rays in lock-step instead of one
Python loop per ray, and ``visible_runs`` finds the screen-column runs of a
billboard that are not hidden behind a closer wall, replacing a per-column
Python loop.  Both are exact drop-in equivalents of the scalar code they
replace (see tests/test_raycast_fast.py, which checks them against reference
scalar implementations).
"""
import numpy as np


def cast_rays(grid, map_w, map_h, px, py, cos_a, sin_a, max_depth, empty=0):
    """DDA-cast every ray at once.

    ``grid`` is an int array indexed ``[y, x]``; ``cos_a`` / ``sin_a`` are
    per-ray direction arrays.  Returns ``(dist, tile, frac, side, hit)``,
    each of shape ``(n,)``.  For rays that hit nothing within ``max_depth``
    ``hit`` is False, ``dist`` is ``max_depth`` and the other fields are 0.
    """
    cos_a = np.where(cos_a == 0, 1e-5, cos_a).astype(np.float64)
    sin_a = np.where(sin_a == 0, 1e-5, sin_a).astype(np.float64)
    n = cos_a.shape[0]

    x_pos = cos_a > 0
    y_pos = sin_a > 0
    x_step = np.where(x_pos, 1, -1).astype(np.int64)
    y_step = np.where(y_pos, 1, -1).astype(np.int64)

    map_x0 = int(px)
    map_y0 = int(py)
    x_dist = np.where(x_pos, (map_x0 + 1 - px) / cos_a, (map_x0 - px) / cos_a)
    y_dist = np.where(y_pos, (map_y0 + 1 - py) / sin_a, (map_y0 - py) / sin_a)
    dx = np.abs(1.0 / cos_a)
    dy = np.abs(1.0 / sin_a)

    hit = np.zeros(n, dtype=bool)
    hit_side = np.zeros(n, dtype=np.int8)
    hit_tile = np.zeros(n, dtype=np.int32)
    hit_mx = np.zeros(n, dtype=np.int64)
    hit_my = np.zeros(n, dtype=np.int64)

    # Active set (compressed every iteration).
    idx = np.arange(n)
    a_xd, a_yd = x_dist, y_dist
    a_dx, a_dy = dx, dy
    a_xs, a_ys = x_step, y_step
    a_mx = np.full(n, map_x0, dtype=np.int64)
    a_my = np.full(n, map_y0, dtype=np.int64)

    for _ in range(int(max_depth) * 4):
        # Past view distance nothing can be drawn: stop walking this ray.
        keep = np.minimum(a_xd, a_yd) <= max_depth
        if not keep.all():
            idx, a_xd, a_yd = idx[keep], a_xd[keep], a_yd[keep]
            a_dx, a_dy, a_xs, a_ys = a_dx[keep], a_dy[keep], a_xs[keep], a_ys[keep]
            a_mx, a_my = a_mx[keep], a_my[keep]
        if idx.size == 0:
            break

        step_x = a_xd < a_yd
        a_xd = np.where(step_x, a_xd + a_dx, a_xd)
        a_yd = np.where(step_x, a_yd, a_yd + a_dy)
        a_mx = a_mx + np.where(step_x, a_xs, 0)
        a_my = a_my + np.where(step_x, 0, a_ys)

        inb = (a_mx >= 0) & (a_mx < map_w) & (a_my >= 0) & (a_my < map_h)
        tile = grid[np.clip(a_my, 0, map_h - 1), np.clip(a_mx, 0, map_w - 1)]
        hit_now = inb & (tile != empty)

        if hit_now.any():
            hi = idx[hit_now]
            hit[hi] = True
            hit_side[hi] = np.where(step_x[hit_now], 0, 1)
            hit_tile[hi] = tile[hit_now]
            hit_mx[hi] = a_mx[hit_now]
            hit_my[hi] = a_my[hit_now]

        keep = inb & ~hit_now
        if not keep.all():
            idx, a_xd, a_yd = idx[keep], a_xd[keep], a_yd[keep]
            a_dx, a_dy, a_xs, a_ys = a_dx[keep], a_dy[keep], a_xs[keep], a_ys[keep]
            a_mx, a_my = a_mx[keep], a_my[keep]

    dist = np.full(n, float(max_depth))
    frac = np.zeros(n, dtype=np.float64)

    sx = hit & (hit_side == 0)
    if sx.any():
        d = (hit_mx[sx] - px + (1 - x_step[sx]) / 2.0) / cos_a[sx]
        hy = py + d * sin_a[sx]
        dist[sx] = d
        frac[sx] = hy - np.trunc(hy)
    sy = hit & (hit_side == 1)
    if sy.any():
        d = (hit_my[sy] - py + (1 - y_step[sy]) / 2.0) / sin_a[sy]
        hx = px + d * cos_a[sy]
        dist[sy] = d
        frac[sy] = hx - np.trunc(hx)

    dist[hit & (dist < 0)] = 0.01
    return dist, hit_tile, frac, hit_side, hit


def visible_runs(z_buffer, col_to_ray, x0, x1, dist):
    """Runs ``[(start, end), ...]`` of screen columns in ``[x0, x1)`` whose
    wall depth is farther than ``dist`` (i.e. where a sprite at ``dist`` is
    visible).  ``col_to_ray`` maps a screen column to its z-buffer index.
    """
    if x1 <= x0:
        return []
    vis = z_buffer[col_to_ray[x0:x1]] > dist
    if not vis.any():
        return []
    if vis.all():
        return [(x0, x1)]
    padded = np.zeros(vis.size + 2, dtype=np.int8)
    padded[1:-1] = vis
    edges = np.diff(padded)
    starts = np.flatnonzero(edges == 1) + x0
    ends = np.flatnonzero(edges == -1) + x0
    return list(zip(starts.tolist(), ends.tolist()))
