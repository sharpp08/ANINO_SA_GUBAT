"""Slice the 7x2 enemy sprite sheet into <type>_idle.png / <type>_attack.png.

Usage: python3 slice_sheet.py SHEET OUT_DIR
Sheet layout: 7 columns (224 px each), top row idle, bottom row attack.
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

TYPES = ['aswang', 'manananggal', 'tikbalang', 'kapre', 'white_lady', 'multo', 'sigbin']
CELL_W = 224
OUT_SIZE = 128
THRESH = 40      # colour distance from background that counts as sprite
PAD = 20         # extra px read on each side of a cell (arms spill over)
MARGIN = 4       # transparent margin around the sprite in the final frame


def cell_mask(rgb, bg, x0, x1, y0, y1):
    """Return (mask, ox, oy) for the sprite whose cell is [x0,x1) x [y0,y1)."""
    ex0, ex1 = max(0, x0 - PAD), min(rgb.shape[1], x1 + PAD)
    crop = rgb[y0:y1, ex0:ex1]
    d = np.abs(crop - bg).sum(2)
    m = d > THRESH
    lab, n = ndi.label(ndi.binary_dilation(m, iterations=3))
    keep = np.zeros_like(m)
    for i, sl in enumerate(ndi.find_objects(lab), start=1):
        cx = ex0 + (sl[1].start + sl[1].stop) / 2
        area = (lab[sl] == i).sum()
        # keep components whose centre lies inside this cell (drops neighbours' arm tips)
        if x0 <= cx < x1 and area > 40:
            keep |= (lab == i)
    mask = m & keep
    # hard-clip to this cell: neighbouring sprites touch at the edges
    mask[:, :max(0, x0 - ex0)] = False
    mask[:, x1 - ex0:] = False
    mask = ndi.binary_fill_holes(mask)
    return mask, ex0, y0, crop


def main(sheet_path, out_dir):
    img = Image.open(sheet_path).convert('RGB')
    rgb = np.array(img).astype(int)
    bg = np.median(rgb.reshape(-1, 3), axis=0)
    h = rgb.shape[0] // 2
    os.makedirs(out_dir, exist_ok=True)

    for col, name in enumerate(TYPES):
        x0, x1 = col * CELL_W, (col + 1) * CELL_W
        frames = {}
        for row, state in enumerate(('idle', 'attack')):
            y0, y1 = row * h, (row + 1) * h
            mask, ox, oy, crop = cell_mask(rgb, bg, x0, x1, y0, y1)
            rgba = np.zeros(crop.shape[:2] + (4,), dtype=np.uint8)
            rgba[..., :3] = crop.astype(np.uint8)
            rgba[..., 3] = (mask * 255).astype(np.uint8)
            frames[state] = (rgba, mask)

        # one shared square window per enemy so idle <-> attack never jump
        boxes = []
        for rgba, mask in frames.values():
            ys, xs = np.where(mask)
            boxes.append((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
        bx0 = min(b[0] for b in boxes)
        by0 = min(b[1] for b in boxes)
        bx1 = max(b[2] for b in boxes)
        by1 = max(b[3] for b in boxes)
        side = max(bx1 - bx0, by1 - by0)
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        sx0, sy0 = int(round(cx - side / 2)), int(round(cy - side / 2))

        for state, (rgba, mask) in frames.items():
            canvas = Image.new('RGBA', (side, side), (0, 0, 0, 0))
            tile = Image.fromarray(rgba, 'RGBA')
            canvas.paste(tile, (-sx0, -sy0))
            inner = OUT_SIZE - 2 * MARGIN
            # premultiply alpha so the dark background never bleeds into edges
            arr = np.array(canvas).astype(np.float32)
            arr[..., :3] *= arr[..., 3:4] / 255.0
            pm = Image.fromarray(arr.astype(np.uint8), 'RGBA').resize((inner, inner), Image.LANCZOS)
            a = np.array(pm).astype(np.float32)
            alpha = a[..., 3:4]
            a[..., :3] = np.where(alpha > 0, a[..., :3] * 255.0 / np.maximum(alpha, 1), 0)
            a[..., 3] = np.where(a[..., 3] > 96, 255, 0)  # crisp, binary edge
            final = Image.new('RGBA', (OUT_SIZE, OUT_SIZE), (0, 0, 0, 0))
            final.paste(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), 'RGBA'), (MARGIN, MARGIN))
            path = os.path.join(out_dir, f'{name}_{state}.png')
            final.save(path)
            print('wrote', path)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
