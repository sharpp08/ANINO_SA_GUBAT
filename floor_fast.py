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


_GLINT = np.array([34.0, 58.0, 62.0], dtype=np.float32)
_FOAM = np.array([46.0, 62.0, 60.0], dtype=np.float32)


def fill_floor_terrain(arr_3d, atlas, far_atlas, packed, fine, map_w, map_h,
                       px, py, ray_dx, ray_dy, h, half_h, horizon_y, pitch_offset,
                       mist_phase, time_s=0.0, brightness=1.0, far_dist=12.0,
                       water_id=6):
    """Enhanced floor: per-biome textures from ``terrain_gen`` (see that module).

    Same contract as ``fill_floor`` plus:
      atlas / far_atlas  uint8 (terrains, size, size, 3) indexed [id, x, y]
      packed / fine      biome map from ``terrain_gen.build_terrain_maps``
                         (id + edge strength + brightness patch per cell)
      time_s             seconds; animates water glints and shoreline foam
      far_dist           beyond this distance the softened atlas is used so the
                         far ground does not shimmer
    """
    y0 = max(horizon_y, half_h + pitch_offset + 1)
    if y0 >= h:
        return
    size = atlas.shape[1]
    floor_h = h - horizon_y

    ys = np.arange(y0, h)
    row = (ys - half_h - pitch_offset).astype(np.float64)
    dist = (h * 0.5) / row                                         # (rows,) far -> near

    wx = px + dist[:, None] * np.asarray(ray_dx, dtype=np.float64)[None, :]   # (rows, w)
    wy = py + dist[:, None] * np.asarray(ray_dy, dtype=np.float64)[None, :]

    tx = np.minimum(np.mod(wx * 8.0, size).astype(np.intp), size - 1)
    ty = np.minimum(np.mod(wy * 8.0, size).astype(np.intp), size - 1)
    fx = np.clip((wx * fine).astype(np.intp), 0, map_w * fine - 1)
    fy = np.clip((wy * fine).astype(np.intp), 0, map_h * fine - 1)

    p = packed[fy, fx]                                             # one gather: id | edge | shade
    ids = (p & 15).astype(np.intp)

    tex = np.empty(wx.shape + (3,), dtype=np.float32)
    n_far = int(np.count_nonzero(dist > far_dist))                 # leading rows are the far ones
    if n_far:
        tex[:n_far] = far_atlas[ids[:n_far], tx[:n_far], ty[:n_far]]
    if n_far < dist.size:
        tex[n_far:] = atlas[ids[n_far:], tx[n_far:], ty[n_far:]]

    edge = ((p >> 4) & 15).astype(np.float32) * (1.0 / 15.0)
    shade = (p >> 8).astype(np.float32) * (brightness / 128.0)
    is_water = ids == water_id
    # Land darkens slightly where biomes meet (damp ecotone); water gets foam instead.
    shade *= 1.0 - np.where(is_water, 0.0, 0.22).astype(np.float32) * edge
    tex *= shade[:, :, None]

    if is_water.any():
        ri, ci = np.nonzero(is_water)
        xw, yw = wx[ri, ci], wy[ri, ci]
        r = np.sin(xw * 5.3 + time_s * 1.6) * np.sin(yw * 4.7 - time_s * 1.2) \
            + 0.5 * np.sin((xw + yw) * 9.1 + time_s * 2.1)
        r += 0.35 * np.sin(xw * 17.0 + yw * 13.0 + time_s * 3.1)            # fine shimmer so glints never read as flat quads
        glint = (np.clip((r - 0.35) / 1.1, 0.0, 1.0) ** 2 * 0.55).astype(np.float32)
        foam = (edge[ri, ci] * (0.55 + 0.45 * np.sin(xw * 7.0 - yw * 5.0 + time_s * 1.3))).astype(np.float32)
        tex[ri, ci] += glint[:, None] * _GLINT + foam[:, None] * _FOAM

    # Same exp-squared fog and low mist as fill_floor.
    fog = 1.0 - np.exp(-((dist * 0.07) ** 2))
    fshade = np.maximum(0.08, 1.0 - fog).astype(np.float32)
    tex *= fshade[:, None, None]

    floor_t = (ys - horizon_y) / max(1, floor_h)
    mist_strength = np.clip((0.45 - floor_t) / 0.45, 0.0, None)
    mist_wave = np.sin(mist_phase + ys * 0.08) * 0.5 + 0.5
    ma = (mist_strength * mist_wave * 0.25).astype(np.float32)
    if ma.any():
        tex *= (1.0 - ma)[:, None, None]
        tex += (ma[:, None] * MIST_COLOR[None, :])[:, None, :]

    np.clip(tex, 0.0, 255.0, out=tex)
    arr_3d[:, y0:h, :] = tex.astype(np.uint8).transpose(1, 0, 2)
