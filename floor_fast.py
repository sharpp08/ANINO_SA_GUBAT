"""Vectorised perspective floor fill for the raycaster (pure numpy, no pygame).

The old renderer looped over every floor row and issued ~20 small numpy calls
per row.  This computes the whole floor in a handful of 2D array operations.
"""
import math
import numpy as np

MIST_COLOR = np.array([30.0, 40.0, 38.0], dtype=np.float32)

# ─── Module-level cache for pitch-dependent constants ────────────────────────
# dist, fog, shade, mist_strength depend only on (h, horizon_y, pitch_offset),
# not on player position or frame time.  Reuse them when pitch is stable.
_floor_const_cache = {}


def _get_floor_constants(h, horizon_y, pitch_offset, mist_phase):
    """Return cached (dist, fog, fshade, mist_strength) + per-frame mist."""
    key = (h, horizon_y, pitch_offset)
    cached = _floor_const_cache.get(key)
    if cached is not None:
        dist, dist_f32, fog, fshade, mist_strength, ys = cached
    else:
        floor_h = h - horizon_y
        y0 = max(horizon_y, h // 2 + pitch_offset + 1)
        ys = np.arange(y0, h)
        row = (ys - h // 2 - pitch_offset).astype(np.float64)
        dist = (h * 0.5) / row
        # Both floor paths use float32 world coordinates. Cache this conversion with
        # the pitch constants instead of allocating/casting the distance vector every frame.
            fog = 1.0 - np.exp(-((dist * 0.07) ** 2))
        fshade = np.maximum(0.08, 1.0 - fog).astype(np.float32)
        floor_t = (ys - horizon_y) / max(1, floor_h)
        mist_strength = np.clip((0.45 - floor_t) / 0.45, 0.0, None)
        _floor_const_cache.clear()
        _floor_const_cache[key] = (dist, dist_f32, fog, fshade, mist_strength, ys)
    # mist_wave changes every frame; recompute it cheaply.
    mist_wave = np.sin(mist_phase + ys * 0.08) * 0.5 + 0.5
    ma = (mist_strength * mist_wave * 0.25).astype(np.float32)
    return dist, dist_f32, fog, fshade, mist_strength, ma


def fill_floor(arr_3d, ground_arr, tint_lut, terrain_grid, map_w, map_h,
               px, py, ray_dx, ray_dy, h, half_h, horizon_y, pitch_offset,
               mist_phase):
    """Write the textured, fogged and misted floor into ``arr_3d`` (shape (w, h, 3))."""
    y0 = max(horizon_y, half_h + pitch_offset + 1)
    if y0 >= h:
        return
    gw, gh, _ = ground_arr.shape

    dist, dist_f32, fog, fshade, mist_strength, ma = _get_floor_constants(
        h, horizon_y, pitch_offset, mist_phase)
    n_rows = len(dist)

    ray_dx_f32 = np.asarray(ray_dx, dtype=np.float32)
    ray_dy_f32 = np.asarray(ray_dy, dtype=np.float32)
    wx = px + dist_f32[:, None] * ray_dx_f32[None, :]
    wy = py + dist_f32[:, None] * ray_dy_f32[None, :]

    tx = np.minimum(np.mod(wx * 8.0, gw).astype(np.int32), gw - 1)
    ty = np.minimum(np.mod(wy * 8.0, gh).astype(np.int32), gh - 1)
    tex = ground_arr[tx, ty].astype(np.float32)

    if terrain_grid is not None:
        mx = np.clip(np.floor(wx).astype(np.int32), 0, map_w - 1)
        my = np.clip(np.floor(wy).astype(np.int32), 0, map_h - 1)
        ids = np.clip(terrain_grid[my, mx], 0, len(tint_lut) - 1)
        tex *= tint_lut[ids]
        np.minimum(tex, 255.0, out=tex)

    # Combine fog + mist into one multiply-add (same as fill_floor_terrain).
    fog_mist = (fshade * (1.0 - ma)).astype(np.float32)
    mist_add = (ma[:, None] * MIST_COLOR[None, :])
    tex *= fog_mist[:, None, None]
    tex += mist_add[:, None, :]

    arr_3d[:, y0:y0 + n_rows, :] = tex.astype(np.uint8).transpose(1, 0, 2)


_GLINT = np.array([34.0, 58.0, 62.0], dtype=np.float32)
_FOAM = np.array([46.0, 62.0, 60.0], dtype=np.float32)


def fill_floor_terrain(arr_3d, atlas, far_atlas, packed, fine, map_w, map_h,
                       px, py, ray_dx, ray_dy, h, half_h, horizon_y, pitch_offset,
                       mist_phase, time_s=0.0, brightness=1.0, far_dist=12.0,
                       water_id=6):
    """Enhanced floor: per-biome textures from ``terrain_gen``."""
    y0 = max(horizon_y, half_h + pitch_offset + 1)
    if y0 >= h:
        return
    size = atlas.shape[1]

    dist, dist_f32, fog, fshade, mist_strength, ma = _get_floor_constants(
        h, horizon_y, pitch_offset, mist_phase)
    n_rows = len(dist)

    ray_dx_f32 = np.asarray(ray_dx, dtype=np.float32)
    ray_dy_f32 = np.asarray(ray_dy, dtype=np.float32)
    wx = px + dist_f32[:, None] * ray_dx_f32[None, :]
    wy = py + dist_f32[:, None] * ray_dy_f32[None, :]

    tx = np.minimum(np.mod(wx * 8.0, size).astype(np.intp), size - 1)
    ty = np.minimum(np.mod(wy * 8.0, size).astype(np.intp), size - 1)
    fx = np.clip((wx * fine).astype(np.intp), 0, map_w * fine - 1)
    fy = np.clip((wy * fine).astype(np.intp), 0, map_h * fine - 1)

    p = packed[fy, fx]
    ids = (p & 15).astype(np.intp)

    tex = np.empty(wx.shape + (3,), dtype=np.float32)
    n_far = int(np.count_nonzero(dist > far_dist))
    if n_far:
        tex[:n_far] = far_atlas[ids[:n_far], tx[:n_far], ty[:n_far]]
    if n_far < n_rows:
        tex[n_far:] = atlas[ids[n_far:], tx[n_far:], ty[n_far:]]

    edge = ((p >> 4) & 15).astype(np.float32) * (1.0 / 15.0)
    shade = (p >> 8).astype(np.float32) * (brightness / 128.0)
    is_water = ids == water_id
    shade *= 1.0 - (0.22 * (~is_water).astype(np.float32)) * edge
    tex *= shade[:, :, None]

    if is_water.any():
        ri, ci = np.nonzero(is_water)
        xw, yw = wx[ri, ci], wy[ri, ci]
        r = np.sin(xw * 5.3 + time_s * 1.6) * np.sin(yw * 4.7 - time_s * 1.2) \
            + 0.5 * np.sin((xw + yw) * 9.1 + time_s * 2.1)
        r += 0.35 * np.sin(xw * 17.0 + yw * 13.0 + time_s * 3.1)
        glint = (np.clip((r - 0.35) / 1.1, 0.0, 1.0) ** 2 * 0.55).astype(np.float32)
        foam = (edge[ri, ci] * (0.55 + 0.45 * np.sin(xw * 7.0 - yw * 5.0 + time_s * 1.3))).astype(np.float32)
        tex[ri, ci] += glint[:, None] * _GLINT + foam[:, None] * _FOAM

    # Combine fog + mist into one multiply-add on the full (rows, w, 3) array.
    #   final = tex * fshade * (1-ma) + ma * MIST_COLOR
    #         = tex * (fshade * (1-ma)) + ma * MIST_COLOR
    # Pre-compute the per-row factors (tiny arrays) so the big op is one
    # multiply + one add instead of three separate passes.
    fog_mist = (fshade * (1.0 - ma)).astype(np.float32)
    mist_add = (ma[:, None] * MIST_COLOR[None, :])
    tex *= fog_mist[:, None, None]
    tex += mist_add[:, None, :]

    np.clip(tex, 0.0, 255.0, out=tex)
    arr_3d[:, y0:y0 + n_rows, :] = tex.astype(np.uint8).transpose(1, 0, 2)
