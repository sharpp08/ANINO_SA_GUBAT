"""Render previews of the enhanced terrain without launching the game (numpy + Pillow).

    python tools/terrain_preview.py [out_dir]

Writes: terrain_atlas.png (all biome textures, 2x2 tiled), terrain_map.png
(top-down biome map) and terrain_view_*.png (first-person floor views).
"""
import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import terrain_gen as tg            # noqa: E402
from floor_fast import fill_floor_terrain   # noqa: E402

W, H = 640, 360


def demo_grid(size=256):
    """Same biome layout as GameMap.load_chapter (ellipses, trails, marsh channel)."""
    g = np.zeros((size, size), dtype=np.uint8)
    yy, xx = np.mgrid[0:size, 0:size]

    def ell(code, cx, cy, rx, ry):
        g[(((xx - cx) / float(rx)) ** 2 + ((yy - cy) / float(ry)) ** 2) <= 1.0] = code

    for code, cx, cy, rx, ry in ((2, 72, 78, 27, 23), (3, 194, 76, 35, 31), (4, 130, 130, 30, 29),
                                 (5, 69, 202, 27, 22), (2, 15, 128, 15, 14), (4, 241, 128, 18, 19)):
        ell(code, cx, cy, rx, ry)
    trails = [((15, 128), (42, 113)), ((42, 113), (58, 94)), ((58, 94), (72, 78)), ((72, 78), (96, 93)),
              ((96, 93), (113, 112)), ((113, 112), (130, 130)), ((130, 130), (153, 112)),
              ((153, 112), (174, 92)), ((174, 92), (194, 76)), ((194, 76), (216, 93)),
              ((216, 93), (241, 128)), ((69, 202), (83, 176)), ((83, 176), (105, 151)),
              ((105, 151), (130, 130))]
    mask = np.zeros_like(g, dtype=bool)
    for (ax, ay), (bx, by) in trails:
        vx, vy = bx - ax, by - ay
        t = np.clip(((xx - ax) * vx + (yy - ay) * vy) / max(1.0, vx * vx + vy * vy), 0, 1)
        mask |= (xx - (ax + t * vx)) ** 2 + (yy - (ay + t * vy)) ** 2 <= 3.2 ** 2
    g[mask] = 1
    swamp = g == 3
    channel_y = 76 + 8 * np.sin((xx - 165) * 0.11) + 3 * np.sin((xx - 165) * 0.29)
    g[swamp & (np.abs(yy - channel_y) < 2.2)] = 6
    for px, py, rx, ry in ((181, 64, 7, 5), (205, 91, 8, 6), (217, 61, 5, 4)):
        g[(((xx - px) / rx) ** 2 + ((yy - py) / ry) ** 2) <= 1.0] = 6
    return g


def render_view(maps, atlas, far, px, py, angle, t=1.0, fov=math.radians(66)):
    arr = np.zeros((W, H, 3), dtype=np.uint8)
    sky = np.linspace((6, 9, 14), (16, 22, 24), H // 2).astype(np.uint8)
    arr[:, :H // 2, :] = sky[None, :, :]
    cx = np.linspace(-1.0, 1.0, W)
    pa = angle
    plane = math.tan(fov / 2)
    rdx = math.cos(pa) - math.sin(pa) * plane * cx
    rdy = math.sin(pa) + math.cos(pa) * plane * cx
    fill_floor_terrain(arr, atlas, far, maps['packed'], maps['fine'], maps['w'], maps['h'],
                       px, py, rdx, rdy, H, H // 2, H // 2, 0, 1.3, time_s=t)
    img = Image.fromarray(arr.transpose(1, 0, 2))
    return img.resize((W * 2, H * 2), Image.NEAREST)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else '.'
    os.makedirs(out, exist_ok=True)
    atlas, far = tg.bake_terrain_atlas(512, 1337)
    maps = tg.build_terrain_maps(demo_grid(), 1337)

    # contact sheet: each texture tiled 2x2 so seams are visible
    tiles = []
    for i in range(len(tg.TERRAIN_NAMES)):
        t = atlas[i].transpose(1, 0, 2)                 # back to [y, x]
        tiles.append(np.tile(t, (2, 2, 1))[::2, ::2])   # 512x512 preview
    blank = np.zeros_like(tiles[0])
    rows = [np.hstack(tiles[0:4]), np.hstack(tiles[4:7] + [blank])]
    Image.fromarray(np.vstack(rows)).save(os.path.join(out, 'terrain_atlas.png'))

    # top-down biome map with edge band + brightness patches
    p = maps['packed']
    ids = (p & 15).astype(np.intp)
    edge = ((p >> 4) & 15) / 15.0
    shade = (p >> 8) / 128.0
    base = np.stack([atlas[i].reshape(-1, 3).mean(axis=0) for i in range(7)])
    top = base[ids] * shade[..., None] * (1.0 - 0.22 * edge[..., None])
    top = np.clip(top * 2.2, 0, 255).astype(np.uint8)
    Image.fromarray(top).save(os.path.join(out, 'terrain_map.png'))

    views = {
        'trail_to_swamp': (176.0, 90.0, math.radians(-55)),
        'swamp_water': (181.0, 73.0, math.radians(-90)),
        'village_edge': (50.0, 90.0, math.radians(-35)),
        'grove_roots': (141.0, 147.0, math.radians(200)),
        'limestone': (75.0, 185.0, math.radians(-70)),
    }
    for name, (x, y, a) in views.items():
        render_view(maps, atlas, far, x, y, a).save(os.path.join(out, 'terrain_view_%s.png' % name))
    print('wrote previews to', out)


if __name__ == '__main__':
    main()
