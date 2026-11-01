"""Vectorised perspective floor fill for the raycaster (pure numpy, no pygame).

The old renderer looped over every floor row and issued ~20 small numpy calls
per row.  This computes the whole floor in a handful of 2D array operations.
"""
import math
import numpy as np

MIST_COLOR = np.array([30.0, 40.0, 38.0], dtype=np.float32)


def fill_floor(arr_3d, ground_arr, tint_lut, terrain_grid, map_w, map_h,
               px, py, ray_dx, ray_dy, h, half_h, horizon_y, pitch_offset,
               mist_phase):
    """Write the textured, fogged and misted floor into ``arr_3d`` (shape (w, h, 3)).

    ``ray_dx`` / ``ray_dy`` are the per-column world-space ray directions.
    Rows at or above the horizon are left untouched.
    """
    # Only rows strictly below the horizon line have a finite floor distance.
    y0 = max(horizon_y, half_h + pitch_offset + 1)
    if y0 >= h:
        return
    gw, gh, _ = ground_arr.shape
    floor_h = h - horizon_y

    ys = np.arange(y0, h)
    row = (ys - half_h - pitch_offset).astype(np.float32)
    dist = (h * 0.5) / row.astype(np.float64)                     # (rows,)

    # World coordinates stay float64: at 8 texels/tile a float32 rounding error
    # is enough to flip a texel index and shimmer the ground.
    dist64 = dist.astype(np.float64)
    wx = px + dist64[:, None] * np.asarray(ray_dx, dtype=np.float64)[None, :]  # (rows, w)
    wy = py + dist64[:, None] * np.asarray(ray_dy, dtype=np.float64)[None, :]

    tx = np.clip(np.mod(wx * 8.0, gw).astype(np.int32), 0, gw - 1)
    ty = np.clip(np.mod(wy * 8.0, gh).astype(np.int32), 0, gh - 1)
    tex = ground_arr[tx, ty].astype(np.float32)                   # (rows, w, 3)

    if terrain_grid is not None:
        mx = np.clip(np.floor(wx).astype(np.int32), 0, map_w - 1)
        my = np.clip(np.floor(wy).astype(np.int32), 0, map_h - 1)
        ids = np.clip(terrain_grid[my, mx], 0, len(tint_lut) - 1)
        tex *= tint_lut[ids]
        np.minimum(tex, 255.0, out=tex)

    # exp-squared distance fog (darkens with distance, never below 8%)
    fog = 1.0 - np.exp(-((dist * 0.07) ** 2))
    shade = np.maximum(0.08, 1.0 - fog).astype(np.float32)
    tex *= shade[:, None, None]

    # Low-lying mist near the horizon: blend toward a dim green-grey.
    floor_t = (ys - horizon_y) / max(1, floor_h)
    mist_strength = np.clip((0.45 - floor_t) / 0.45, 0.0, None)
    mist_wave = np.sin(mist_phase + ys * 0.08) * 0.5 + 0.5
    ma = (mist_strength * mist_wave * 0.25).astype(np.float32)    # (rows,)
    if ma.any():
        tex *= (1.0 - ma)[:, None, None]
        tex += (ma[:, None] * MIST_COLOR[None, :])[:, None, :]

    arr_3d[:, y0:h, :] = tex.astype(np.uint8).transpose(1, 0, 2)
