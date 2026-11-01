"""Procedural ground terrain for the raycaster floor (pure numpy, no pygame).

The old floor was ONE grass texture, multiplied by a flat colour per biome, with
hard square edges where biomes met.  This module replaces that with:

  * one purpose-built, seamlessly tiling texture per terrain type, with baked
    bump lighting:  forest leaf-litter, packed dirt trail, cracked village clay,
    algae swamp mud with puddles, mossy root grove, limestone slabs and
    shallow water with caustics
  * an organic biome map: noise-warped (jagged, natural) biome boundaries, a
    soft "edge" band for transitions / shorelines, and large-scale brightness
    patches that hide the texture repeating

Runtime sampling is ``floor_fast.fill_floor_terrain``.  Everything here is
deterministic for a given seed and cached to disk after the first bake.

Terrain ids match ``GameMap.terrain_grid``:
    0 forest, 1 trail, 2 village, 3 swamp, 4 grove, 5 limestone, 6 water
"""
import os

import numpy as np

TERRAIN_NAMES = ('forest', 'trail', 'village', 'swamp', 'grove', 'limestone', 'water')
WATER_ID = 6
FINE_PER_TILE = 8          # biome-map cells per world tile (== floor texels per tile)
ATLAS_VERSION = 1          # bump to invalidate cached atlases when art changes

_F32 = np.float32


# --------------------------------------------------------------------------
# Tileable noise
# --------------------------------------------------------------------------
def _smooth(f):
    return f * f * (3.0 - 2.0 * f)


def _value_noise(n, cells, rng):
    """Seamlessly tiling value noise, shape (n, n), range ~[0, 1]."""
    g = rng.random((cells, cells), dtype=_F32)
    c = np.arange(n, dtype=_F32) * (cells / float(n))
    i0 = np.floor(c).astype(np.intp)
    f = _smooth(c - i0).astype(_F32)
    i1 = (i0 + 1) % cells
    fx = f[None, :]
    fy = f[:, None]
    a = g[i0][:, i0]
    b = g[i0][:, i1]
    c0 = g[i1][:, i0]
    d = g[i1][:, i1]
    top = a + (b - a) * fx
    bot = c0 + (d - c0) * fx
    return top + (bot - top) * fy


def _fbm(n, rng, base=4, octaves=5, gain=0.5):
    """Tileable fractal noise normalised to [0, 1]."""
    total = np.zeros((n, n), dtype=_F32)
    amp, norm, cells = 1.0, 0.0, base
    for _ in range(octaves):
        if cells > n:
            break
        total += amp * _value_noise(n, cells, rng)
        norm += amp
        amp *= gain
        cells *= 2
    total /= norm
    lo, hi = float(total.min()), float(total.max())
    return (total - lo) / max(hi - lo, 1e-6)


def _voronoi(n, grid, rng):
    """Tileable jittered-grid Voronoi: (nearest dist, 2nd nearest dist, cell index)."""
    cell = n / float(grid)
    gy, gx = np.mgrid[0:grid, 0:grid]
    px = ((gx + rng.random((grid, grid)) * 0.9 + 0.05) * cell).ravel().astype(_F32)
    py = ((gy + rng.random((grid, grid)) * 0.9 + 0.05) * cell).ravel().astype(_F32)
    X = np.arange(n, dtype=_F32)[None, :]
    Y = np.arange(n, dtype=_F32)[:, None]
    d1 = np.full((n, n), 1e9, dtype=_F32)
    d2 = np.full((n, n), 1e9, dtype=_F32)
    idx = np.zeros((n, n), dtype=np.int32)
    for i in range(px.size):
        dx = np.abs(X - px[i])
        dx = np.minimum(dx, n - dx)
        dy = np.abs(Y - py[i])
        dy = np.minimum(dy, n - dy)
        d = np.sqrt(dx * dx + dy * dy)
        closer = d < d1
        d2 = np.where(closer, d1, np.minimum(d2, d))
        idx = np.where(closer, i, idx)
        d1 = np.where(closer, d, d1)
    return d1, d2, idx


# --------------------------------------------------------------------------
# Stamping helpers (all wrap around, so textures stay seamless)
# --------------------------------------------------------------------------
def _disc(r):
    R = int(np.ceil(r))
    dy, dx = np.mgrid[-R:R + 1, -R:R + 1]
    d = np.sqrt(dx * dx + dy * dy)
    m = d <= r
    w = 1.0 - 0.5 * (d[m] / max(r, 0.5))
    return dx[m].astype(np.intp), dy[m].astype(np.intp), w.astype(_F32)


def _ellipse(length, width, ang):
    R = int(np.ceil(max(length, width)))
    dy, dx = np.mgrid[-R:R + 1, -R:R + 1].astype(_F32)
    c, s = np.cos(ang), np.sin(ang)
    u = dx * c + dy * s
    v = -dx * s + dy * c
    d = (u / length) ** 2 + (v / width) ** 2
    m = d <= 1.0
    return dx[m].astype(np.intp), dy[m].astype(np.intp), (1.0 - 0.45 * d[m]).astype(_F32)


def _paint(rgb, xs, ys, offs, colors, alpha):
    n = rgb.shape[0]
    dxs, dys, ws = offs
    colors = np.asarray(colors, dtype=_F32)
    a0 = np.broadcast_to(np.asarray(alpha, dtype=_F32), xs.shape)
    for dx, dy, w in zip(dxs, dys, ws):
        yy = (ys + dy) % n
        xx = (xs + dx) % n
        a = (a0 * w)[:, None]
        rgb[yy, xx] = rgb[yy, xx] * (1.0 - a) + colors * a


def _raise(h, xs, ys, offs, val):
    n = h.shape[0]
    dxs, dys, ws = offs
    val = np.asarray(val, dtype=_F32)
    for dx, dy, w in zip(dxs, dys, ws):
        yy = (ys + dy) % n
        xx = (xs + dx) % n
        h[yy, xx] = np.maximum(h[yy, xx], val * w)


def _scatter(rgb, h, rng, n, palette, len_rng, wid_rng, alpha, hval, mask=None, buckets=8):
    """Scatter n randomly rotated ellipses (leaves, flakes, straw...)."""
    S = rgb.shape[0]
    xs = rng.integers(0, S, n)
    ys = rng.integers(0, S, n)
    if mask is not None:
        keep = mask[ys, xs] > 0.5
        xs, ys = xs[keep], ys[keep]
        n = xs.size
    if n == 0:
        return
    palette = np.asarray(palette, dtype=_F32)
    cols = palette[rng.integers(0, len(palette), n)] * rng.uniform(0.8, 1.2, (n, 1)).astype(_F32)
    bucket = rng.integers(0, buckets, n)
    cls = rng.integers(0, 3, n)
    lens = np.linspace(len_rng[0], len_rng[1], 3)
    wids = np.linspace(wid_rng[0], wid_rng[1], 3)
    for b in range(buckets):
        for c in range(3):
            sel = (bucket == b) & (cls == c)
            if not sel.any():
                continue
            offs = _ellipse(lens[c], wids[c], b * np.pi / buckets)
            _paint(rgb, xs[sel], ys[sel], offs, cols[sel], alpha)
            if h is not None and hval:
                _raise(h, xs[sel], ys[sel], offs, hval * rng.uniform(0.6, 1.0, int(sel.sum())))


def _strokes(rgb, h, rng, x0, y0, ang, length, colors, alpha, disc, hval=0.0, drift=0.0):
    """Walk n polylines (twigs, blades, roots) with optional wandering angle."""
    x = np.asarray(x0, dtype=_F32).copy()
    y = np.asarray(y0, dtype=_F32).copy()
    ang = np.asarray(ang, dtype=_F32).copy()
    colors = np.asarray(colors, dtype=_F32)
    alpha = np.asarray(alpha, dtype=_F32)
    for step in range(int(length.max())):
        act = length > step
        if not act.any():
            break
        px = np.rint(x[act]).astype(np.intp)
        py = np.rint(y[act]).astype(np.intp)
        col = colors if colors.ndim == 1 else colors[act]
        al = alpha if alpha.ndim == 0 else alpha[act]
        _paint(rgb, px, py, disc, col, al)
        if h is not None and hval:
            _raise(h, px, py, disc, hval)
        x += np.cos(ang)
        y += np.sin(ang)
        if drift:
            ang += rng.normal(0.0, drift, ang.shape).astype(_F32)


def _blades(rgb, rng, n, palette, len_rng, alpha=0.8, mask=None):
    S = rgb.shape[0]
    xs = rng.integers(0, S, n)
    ys = rng.integers(0, S, n)
    if mask is not None:
        keep = mask[ys, xs] > 0.5
        xs, ys = xs[keep], ys[keep]
        n = xs.size
    if n == 0:
        return
    palette = np.asarray(palette, dtype=_F32)
    cols = palette[rng.integers(0, len(palette), n)] * rng.uniform(0.85, 1.15, (n, 1)).astype(_F32)
    ang = -np.pi / 2 + rng.uniform(-0.8, 0.8, n)
    length = rng.integers(len_rng[0], len_rng[1] + 1, n)
    _strokes(rgb, None, rng, xs, ys, ang, length, cols, alpha, _disc(0.5), drift=0.05)


def _pebbles(rgb, h, rng, n, palette, r_rng):
    S = rgb.shape[0]
    xs = rng.integers(0, S, n)
    ys = rng.integers(0, S, n)
    palette = np.asarray(palette, dtype=_F32)
    cols = palette[rng.integers(0, len(palette), n)] * rng.uniform(0.8, 1.2, (n, 1)).astype(_F32)
    cls = rng.integers(0, 3, n)
    for c, r in enumerate(np.linspace(r_rng[0], r_rng[1], 3)):
        sel = cls == c
        if not sel.any():
            continue
        offs = _disc(r)
        _paint(rgb, xs[sel] + 1, ys[sel] + 1, offs, (18, 16, 12), 0.45)      # contact shadow
        _paint(rgb, xs[sel], ys[sel], offs, cols[sel], 0.95)
        _raise(h, xs[sel], ys[sel], offs, 0.9)


def _blend(rgb, mask, colour, strength=1.0):
    m = (np.clip(mask, 0.0, 1.0) * strength)[..., None]
    return rgb * (1.0 - m) + np.asarray(colour, dtype=_F32) * m


def _bump(rgb, h, strength=2.6, lo=0.55, hi=1.5):
    """Bake directional (upper-left) lighting from a height map into the colour."""
    gx = np.roll(h, -1, 1) - np.roll(h, 1, 1)
    gy = np.roll(h, -1, 0) - np.roll(h, 1, 0)
    lit = np.clip(1.0 + (gx + gy) * 0.5 * strength * 4.0, lo, hi)
    return rgb * lit[..., None]


def _finish(rgb, h=None, bump=2.6):
    if h is not None:
        rgb = _bump(rgb, h, bump)
    gray = rgb.mean(axis=2, keepdims=True)
    rgb = rgb * 0.9 + gray * 0.1                     # slightly desaturated, moody
    rgb[..., 2] *= 1.03                              # faint cool cast
    return np.clip(rgb, 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------
# Terrain textures: each returns uint8 (S, S, 3) indexed [y, x]
# --------------------------------------------------------------------------
def _tex_forest(S, rng):
    k = (S / 512.0) ** 2
    m = _fbm(S, rng, 4, 5)
    fine = _fbm(S, rng, 32, 3)
    rgb = np.array([26, 22, 15], dtype=_F32) * (0.7 + 0.7 * m[..., None]) * (0.9 + 0.2 * fine[..., None])
    h = 0.20 * m + 0.08 * fine
    moss = _fbm(S, rng, 6, 4)
    rgb = _blend(rgb, (moss - 0.55) / 0.15, (32, 50, 24), 0.65)
    h += 0.05 * np.clip(moss - 0.55, 0, 1)

    leaves = [(66, 46, 22), (80, 58, 26), (54, 40, 20), (46, 52, 22), (72, 66, 30), (40, 30, 18)]
    _scatter(rgb, h, rng, int(5200 * k), leaves, (2.2, 4.2), (1.0, 1.8), 0.85, 0.35)
    greens = [(30, 48, 20), (40, 62, 26), (54, 78, 34), (28, 40, 20), (96, 112, 76)]
    _blades(rgb, rng, int(15000 * k), greens, (2, 5), 0.8)
    twig_n = int(140 * k)
    _strokes(rgb, h, rng, rng.integers(0, S, twig_n), rng.integers(0, S, twig_n),
             rng.uniform(0, 2 * np.pi, twig_n), rng.integers(8, 26, twig_n),
             (58, 42, 26), 0.9, _disc(0.9), hval=0.55, drift=0.10)
    _pebbles(rgb, h, rng, int(260 * k), [(74, 70, 62), (62, 60, 54), (82, 76, 64)], (1.2, 2.4))
    return _finish(rgb, h)


def _tex_trail(S, rng):
    k = (S / 512.0) ** 2
    m = _fbm(S, rng, 4, 5)
    fine = _fbm(S, rng, 48, 3)
    speck = rng.normal(0.0, 5.0, (S, S, 1)).astype(_F32)
    rgb = np.array([66, 50, 33], dtype=_F32) * (0.75 + 0.5 * m[..., None]) * (0.92 + 0.16 * fine[..., None]) + speck
    h = 0.10 * m + 0.08 * fine
    d1, d2, _ = _voronoi(S, 9, rng)                       # hairline dry cracks
    rgb = _blend(rgb, 1.0 - (d2 - d1) / 1.6, (30, 22, 15), 0.45)
    ruts = int(70 * k)
    _scatter(rgb, h, rng, ruts, [(40, 30, 20)], (9.0, 16.0), (2.0, 3.4), 0.30, 0.0)   # trodden hollows
    _scatter(rgb, h, rng, int(1800 * k), [(86, 66, 44), (74, 58, 40), (58, 44, 30)], (1.4, 2.6), (0.9, 1.5), 0.8, 0.30)
    _pebbles(rgb, h, rng, int(900 * k), [(88, 82, 72), (74, 68, 60), (96, 84, 66), (62, 58, 52)], (1.0, 2.2))
    _blades(rgb, rng, int(1800 * k), [(40, 54, 24), (58, 70, 34)], (2, 4), 0.7, mask=(fine > 0.62))
    return _finish(rgb, h, 2.2)


def _tex_village(S, rng):
    k = (S / 512.0) ** 2
    m = _fbm(S, rng, 4, 5)
    fine = _fbm(S, rng, 40, 3)
    d1, d2, idx = _voronoi(S, 7, rng)
    plate = rng.uniform(0.82, 1.14, idx.max() + 1).astype(_F32)[idx]
    rgb = np.array([72, 58, 42], dtype=_F32) * (0.8 + 0.4 * m[..., None]) * plate[..., None] * (0.93 + 0.14 * fine[..., None])
    dd = d2 - d1
    h = np.clip(dd / 6.0, 0, 1) * 0.5 + 0.08 * fine
    rgb = _blend(rgb, 1.0 - dd / 2.2, (28, 21, 15), 0.9)                          # deep cracks
    rgb = _blend(rgb, 1.0 - np.abs(dd - 3.2) / 1.2, (96, 80, 60), 0.15)          # curled plate lips
    ash = _fbm(S, rng, 5, 4)
    rgb = _blend(rgb, (ash - 0.6) / 0.12, (28, 26, 24), 0.55)                     # burnt / ash smears
    _scatter(rgb, h, rng, int(900 * k), [(124, 108, 62), (104, 90, 52), (90, 78, 48)], (3.0, 5.0), (0.5, 0.8), 0.85, 0.25)   # straw
    _pebbles(rgb, h, rng, int(300 * k), [(86, 78, 66), (70, 64, 56)], (1.0, 2.0))
    _scatter(rgb, h, rng, int(120 * k), [(22, 20, 18)], (1.6, 3.2), (0.8, 1.6), 0.8, 0.2)  # charcoal
    return _finish(rgb, h, 2.2)


def _tex_swamp(S, rng):
    k = (S / 512.0) ** 2
    m = _fbm(S, rng, 4, 5)
    fine = _fbm(S, rng, 40, 3)
    rgb = np.array([32, 36, 27], dtype=_F32) * (0.7 + 0.6 * m[..., None]) * (0.9 + 0.2 * fine[..., None])
    h = 0.12 * m + 0.06 * fine
    algae = _fbm(S, rng, 6, 4)
    rgb = _blend(rgb, (algae - 0.52) / 0.15, (38, 66, 36), 0.65)
    _blades(rgb, rng, int(6000 * k), [(34, 54, 28), (46, 70, 34), (26, 40, 24)], (2, 4), 0.75, mask=(algae > 0.5))
    pn = _fbm(S, rng, 5, 4)
    pm = np.clip((pn - 0.60) / 0.07, 0, 1)                                         # puddles
    rgb = _blend(rgb, pm, (14, 22, 22), 0.95)
    contour = (np.abs(np.sin(_fbm(S, rng, 8, 3) * 34.0)) < 0.10).astype(_F32) * pm  # sheen ripples
    rgb = _blend(rgb, contour, (50, 72, 76), 0.30)
    h *= (1.0 - 0.9 * pm)
    rn = int(70 * k)
    _strokes(rgb, h, rng, rng.integers(0, S, rn), rng.integers(0, S, rn), rng.uniform(0, 2 * np.pi, rn),
             rng.integers(10, 30, rn), (22, 26, 18), 0.9, _disc(1.0), hval=0.5, drift=0.18)
    _scatter(rgb, h, rng, int(1500 * k), [(52, 44, 26), (44, 40, 22)], (2.0, 3.6), (1.0, 1.6), 0.8, 0.2, mask=(1.0 - pm))
    return _finish(rgb, h, 1.6)


def _tex_grove(S, rng):
    k = (S / 512.0) ** 2
    m = _fbm(S, rng, 4, 5)
    fine = _fbm(S, rng, 48, 3)
    rgb = np.array([27, 38, 23], dtype=_F32) * (0.7 + 0.8 * m[..., None]) * (0.9 + 0.2 * fine[..., None])
    h = 0.14 * m + 0.10 * fine
    n = int(24000 * k)
    xs, ys = rng.integers(0, S, n), rng.integers(0, S, n)
    _paint(rgb, xs, ys, _disc(0.5), np.array([46, 68, 40], dtype=_F32) * rng.uniform(0.7, 1.2, (n, 1)).astype(_F32), 0.45)  # moss fuzz
    _scatter(rgb, h, rng, int(1300 * k), [(68, 52, 24), (54, 44, 22), (44, 56, 24)], (2.0, 3.6), (1.0, 1.6), 0.8, 0.3)
    # Wandering buttress roots, painted in three passes along the same walk
    # (shadow, bark, highlight) by re-seeding the drift so the passes align.
    nc = 18
    cx, cy = rng.integers(0, S, nc), rng.integers(0, S, nc)
    cang = rng.uniform(0, 2 * np.pi, nc)
    clen = rng.integers(int(60 * S / 512), int(140 * S / 512), nc)
    seed = int(rng.integers(0, 2**31))
    for r, col, a, hv, ox in ((3.0, (20, 16, 12), 0.7, 0.0, 0), (2.0, (56, 42, 30), 1.0, 1.0, 0),
                              (0.9, (84, 64, 46), 0.8, 1.0, -1)):
        _strokes(rgb, h, np.random.default_rng(seed), cx + ox, cy + ox, cang, clen, col, a, _disc(r),
                 hval=hv, drift=0.12)
    fn = 44
    fx, fy = rng.integers(0, S, fn), rng.integers(0, S, fn)
    _paint(rgb, fx, fy, _disc(3.0), (24, 56, 50), 0.35)                            # faint glow halo
    _paint(rgb, fx, fy, _disc(1.2), (66, 150, 128), 0.9)                           # fungus dot
    return _finish(rgb, h, 2.8)


def _tex_limestone(S, rng):
    k = (S / 512.0) ** 2
    grain = _fbm(S, rng, 16, 5)
    d1, d2, idx = _voronoi(S, 5, rng)
    slab = rng.uniform(0.86, 1.08, idx.max() + 1).astype(_F32)[idx]
    tint = rng.uniform(-2.5, 2.5, (idx.max() + 1, 3)).astype(_F32)[idx]
    rgb = (np.array([62, 60, 54], dtype=_F32) + tint) * slab[..., None] * (0.72 + 0.56 * grain[..., None])
    dd = np.maximum(d2 - d1 + (grain - 0.5) * 5.0, 0.0)          # ragged, hand-hewn slab edges
    h = np.clip(dd / 7.0, 0, 1) * 0.6 + 0.12 * grain
    rgb = _blend(rgb, 1.0 - dd / 3.0, (20, 20, 19), 0.9)                           # cracks between slabs
    rgb = _blend(rgb, 1.0 - np.abs(dd - 4.5) / 1.6, (92, 88, 80), 0.18)           # worn slab edges
    lichen = _fbm(S, rng, 6, 4)
    rgb = _blend(rgb, (lichen - 0.62) / 0.1, (50, 64, 42), 0.45)
    _scatter(rgb, h, rng, int(900 * k), [(100, 96, 86), (74, 72, 66), (112, 104, 90)], (1.2, 2.4), (0.8, 1.4), 0.8, 0.25)
    _pebbles(rgb, h, rng, int(260 * k), [(104, 100, 92), (80, 78, 72)], (1.0, 2.0))
    return _finish(rgb, h, 2.6)


def _tex_water(S, rng):
    m = _fbm(S, rng, 4, 5)
    fine = _fbm(S, rng, 24, 3)
    rgb = np.array([18, 42, 48], dtype=_F32) * (0.7 + 0.7 * m[..., None]) * (0.9 + 0.2 * fine[..., None])
    bed = _fbm(S, rng, 5, 4)
    rgb = _blend(rgb, (bed - 0.58) / 0.14, (40, 64, 58), 0.55)                      # silt showing through
    for grid, strength, col in ((7, 0.75, (84, 150, 146)), (11, 0.50, (66, 124, 124))):
        d1, d2, _ = _voronoi(S, grid, rng)
        line = np.clip(1.0 - (d2 - d1) / 5.0, 0, 1) ** 2                             # caustic network
        rgb = _blend(rgb, line, col, strength)
    algae = _fbm(S, rng, 6, 4)
    rgb = _blend(rgb, (algae - 0.62) / 0.1, (30, 62, 40), 0.5)
    return _finish(rgb, None)


_BUILDERS = (_tex_forest, _tex_trail, _tex_village, _tex_swamp, _tex_grove, _tex_limestone, _tex_water)


# --------------------------------------------------------------------------
# Atlas
# --------------------------------------------------------------------------
def bake_terrain_atlas(size=512, seed=1337):
    """Bake every terrain texture.

    Returns ``(atlas, far_atlas)``, both uint8 ``(terrains, size, size, 3)`` indexed
    ``[terrain_id, x, y, channel]`` (x first, matching ``floor_fast``).  ``far_atlas``
    is a softened copy used at distance so the far ground does not shimmer.
    """
    texs = []
    for tid, build in enumerate(_BUILDERS):
        rng = np.random.default_rng(seed * 1000 + tid * 101 + 7)
        texs.append(build(size, rng))
    atlas = np.ascontiguousarray(np.stack(texs).transpose(0, 2, 1, 3))
    f = atlas.astype(_F32)
    blur = np.zeros_like(f)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            blur += np.roll(np.roll(f, dx, axis=1), dy, axis=2)
    blur /= 9.0
    mean = f.mean(axis=(1, 2), keepdims=True)
    far = np.clip(blur * 0.65 + mean * 0.35, 0, 255).astype(np.uint8)
    return atlas, far


def load_or_bake_atlas(cache_dir, size=512, seed=1337, force=False):
    """Load the cached atlas, baking (and caching) it on the first run."""
    path = os.path.join(cache_dir, 'terrain_atlas_v%d_%d_%d.npz' % (ATLAS_VERSION, size, seed))
    if not force and os.path.exists(path):
        try:
            with np.load(path) as z:
                return z['atlas'], z['far']
        except Exception:
            pass
    atlas, far = bake_terrain_atlas(size, seed)
    try:
        os.makedirs(cache_dir, exist_ok=True)
        np.savez(path, atlas=atlas, far=far)
    except OSError:
        pass
    return atlas, far


# --------------------------------------------------------------------------
# Biome map
# --------------------------------------------------------------------------
def _upsample(a, fine):
    """Bilinear upsample of a 2D float array by an integer factor."""
    def axis_idx(count):
        c = (np.arange(count * fine, dtype=_F32) + 0.5) / fine - 0.5
        i0 = np.clip(np.floor(c).astype(np.intp), 0, count - 1)
        i1 = np.clip(i0 + 1, 0, count - 1)
        f = np.clip(c - np.floor(c), 0.0, 1.0).astype(_F32)
        return i0, i1, f
    H, W = a.shape
    y0, y1, fy = axis_idx(H)
    rows = a[y0] * (1.0 - fy)[:, None] + a[y1] * fy[:, None]
    x0, x1, fx = axis_idx(W)
    return rows[:, x0] * (1.0 - fx)[None, :] + rows[:, x1] * fx[None, :]


def build_terrain_maps(terrain_grid, seed=1337, fine=FINE_PER_TILE):
    """Turn the tile-level ``terrain_grid`` into an organic fine-resolution map.

    Returns a dict:
      ``packed``  uint16 (H*fine, W*fine): bits 0-3 terrain id, bits 4-7 edge
                  strength (0-15), bits 8-15 brightness patch (128 == 1.0)
      ``fine``, ``w``, ``h``  map geometry
    """
    tg = np.asarray(terrain_grid, dtype=np.uint8)
    H, W = tg.shape
    FH, FW = H * fine, W * fine
    n = max(FH, FW)
    rng = np.random.default_rng(seed + 4242)

    # Each terrain becomes a smooth weight field (bilinear upsample of its tile mask)
    # plus noise; the highest weight wins.  That turns the tile staircase into
    # curved, wandering boundaries instead of warped squares.
    coarse = _fbm(n, rng, 6, 4)
    ragged = _fbm(n, rng, max(8, n // 8), 2)
    ids = np.zeros((FH, FW), dtype=np.uint8)
    best = np.full((FH, FW), -1e9, dtype=_F32)
    for t in np.unique(tg):
        w = _upsample(((tg == t) * 1.0).astype(_F32), fine)
        shift = int(t) * 257
        w += (np.roll(coarse, shift, 0)[:FH, :FW] - 0.5) * 0.9
        w += (np.roll(ragged, shift, 1)[:FH, :FW] - 0.5) * 0.45
        win = w > best
        best = np.where(win, w, best)
        ids = np.where(win, np.uint8(t), ids)

    diff = np.zeros((FH, FW), dtype=_F32)
    for s in (1, 2, 4, 6):
        for ax in (0, 1):
            diff += ids != np.roll(ids, s, ax)
            diff += ids != np.roll(ids, -s, ax)
    edge = np.clip(diff / 8.0, 0.0, 1.0)
    # np.roll wraps the map borders around; fade the wrapped seam out.
    edge[:6, :] = edge[-6:, :] = 0.0
    edge[:, :6] = edge[:, -6:] = 0.0

    macro = 0.80 + 0.40 * _fbm(n, rng, 3, 4)[:FH, :FW]
    shade8 = np.clip(np.rint(macro * 128.0), 0, 255).astype(np.uint16)
    edge4 = np.rint(edge * 15.0).astype(np.uint16)
    packed = (shade8 << 8) | (edge4 << 4) | ids.astype(np.uint16)
    return {'packed': np.ascontiguousarray(packed), 'fine': fine, 'w': W, 'h': H}
