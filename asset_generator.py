"""
Procedural asset generator - creates pixel art textures and sprites at runtime.
"""
import pygame
import math
import random
import os
from typing import Optional

import sys

if getattr(sys, 'frozen', False):
    ASSET_DIR = os.path.join(os.path.dirname(sys.executable), 'assets')
else:
    ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')


def _ensure_dirs():
    for sub in ('textures', 'sprites', 'audio', 'fonts'):
        p = os.path.join(ASSET_DIR, sub)
        os.makedirs(p, exist_ok=True)


def generate_fbm_noise(width=64, height=64, octaves=4, seed=42):
    import numpy as np
    np.random.seed(seed)
    grid = np.zeros((height, width), dtype=np.float32)
    for i in range(octaves):
        freq = 2 ** i
        sub_w, sub_h = max(2, width // freq), max(2, height // freq)
        rand = np.random.rand(sub_h, sub_w).astype(np.float32)
        rep_y = int(math.ceil(height / sub_h))
        rep_x = int(math.ceil(width / sub_w))
        layer = np.kron(rand, np.ones((rep_y, rep_x), dtype=np.float32))[:height, :width]
        grid += layer * (0.5 ** i)
    mn, mx = grid.min(), grid.max()
    if mx - mn > 1e-5:
        grid = (grid - mn) / (mx - mn)
    return grid


def generate_wall_texture(width=64, height=64, base_color=(60, 40, 25), variation=15, style='stone'):
    """Generate high-fidelity wall texture with fBm noise and ambient occlusion."""
    import numpy as np
    surf = pygame.Surface((width, height))
    noise = generate_fbm_noise(width, height, octaves=4, seed=abs(hash(str(base_color)) + hash(style)) % 10000)
    base = np.array(base_color, dtype=np.float32)

    arr = np.zeros((height, width, 3), dtype=np.float32)
    for y in range(height):
        for x in range(width):
            n = noise[y, x]
            if style == 'stone':
                by = y // 8
                bx = (x + (16 if by % 2 == 1 else 0)) % width
                is_mortar = (y % 8 == 0) or (bx % 32 == 0)
                col = np.array([25, 25, 20], dtype=np.float32) + n * 10 if is_mortar else np.clip(base + (n - 0.5) * 45, 0, 255)
            elif style == 'wood':
                plank_y = y % 16
                is_gap = (plank_y == 0 or plank_y == 15)
                col = np.array([20, 12, 8], dtype=np.float32) if is_gap else np.clip(base + math.sin(x * 0.4) * 12 + (n - 0.5) * 30, 0, 255)
            elif style == 'bamboo':
                is_node = (y % 16 < 3)
                col = np.array([40, 60, 25], dtype=np.float32) + n * 15 if is_node else np.clip(base + math.cos(x / width * math.pi) * 25 + (n - 0.5) * 20, 0, 255)
            elif style == 'balete':
                twist = math.sin(y * 0.2 + x * 0.15)
                col = np.clip(base + twist * 25 + (n - 0.5) * 35, 0, 255)
            else:
                col = np.clip(base + (n - 0.5) * 35, 0, 255)
            arr[y, x] = col

    # Ambient Occlusion: Darken top and bottom rows
    ao = np.linspace(0.72, 1.0, height)[:, None]
    ao_v = np.linspace(1.0, 0.72, height)[:, None]
    arr = np.clip(arr * (ao * 0.5 + ao_v * 0.5), 0, 255)
    pygame.surfarray.blit_array(surf, arr.astype(np.uint8).swapaxes(0, 1))
    return surf


def generate_floor_texture(width=64, height=64, base_color=(25, 18, 12)):
    """Generate fractal noise ground texture with pebbles and twigs."""
    import numpy as np
    surf = pygame.Surface((width, height))
    noise = generate_fbm_noise(width, height, octaves=5, seed=777)
    base = np.array(base_color, dtype=np.float32)
    arr = np.clip(base[None, None, :] + (noise[:, :, None] - 0.5) * 50, 0, 255)
    pygame.surfarray.blit_array(surf, arr.astype(np.uint8).swapaxes(0, 1))
    return surf


def generate_weapon_sprite(weapon_type='bolo', width=128, height=128):
    """Generate a simple weapon sprite for HUD display."""
    surf = pygame.Surface((width, height), pygame.SRCALPHA)

    if weapon_type == 'bolo':
        handle_color = (100, 60, 30)
        blade_color = (180, 180, 190)
        pygame.draw.rect(surf, handle_color, (50, 70, 12, 58))
        pygame.draw.polygon(surf, blade_color, [
            (40, 20), (72, 20), (76, 30), (68, 70), (44, 70), (36, 30)
        ])
        pygame.draw.polygon(surf, (150, 150, 160), [
            (42, 22), (70, 22), (74, 30), (66, 68), (46, 68), (38, 30)
        ])
        pygame.draw.rect(surf, (80, 50, 25), (46, 68, 20, 6))

    elif weapon_type == 'shotgun':
        barrel_color = (60, 60, 65)
        stock_color = (90, 55, 30)
        pygame.draw.rect(surf, stock_color, (45, 80, 40, 48))
        pygame.draw.polygon(surf, stock_color, [(45, 100), (30, 128), (55, 128), (55, 100)])
        pygame.draw.rect(surf, barrel_color, (50, 20, 14, 65))
        pygame.draw.rect(surf, barrel_color, (48, 20, 18, 65))
        pygame.draw.rect(surf, (50, 50, 55), (52, 18, 10, 4))
        pygame.draw.rect(surf, (70, 45, 25), (46, 78, 22, 6))

    elif weapon_type == 'revolver':
        body_color = (70, 70, 75)
        grip_color = (85, 50, 25)
        pygame.draw.rect(surf, body_color, (40, 55, 50, 18))
        pygame.draw.rect(surf, body_color, (42, 38, 8, 20))
        cylinder = (55, 64)
        pygame.draw.circle(surf, (80, 80, 85), cylinder, 10)
        pygame.draw.circle(surf, (60, 60, 65), cylinder, 8)
        pygame.draw.rect(surf, body_color, (65, 52, 35, 10))
        pygame.draw.rect(surf, (50, 50, 55), (98, 54, 6, 6))
        pygame.draw.polygon(surf, grip_color, [(42, 72), (56, 72), (60, 110), (38, 110)])
        for i in range(4):
            pygame.draw.line(surf, (70, 40, 20), (42, 80 + i * 6), (56, 80 + i * 6))

    return surf


RIM_COLORS = {
    'aswang': (150, 25, 35), 'manananggal': (180, 35, 70), 'tikbalang': (210, 130, 25),
    'kapre': (180, 95, 25), 'white_lady': (200, 220, 255), 'multo': (160, 180, 235),
    'sigbin': (210, 70, 15),
}


def _horror_finish(surf, rim_color, seed=1):
    """Give an enemy sprite a jagged glowing rim and dripping edges so its silhouette
    reads clearly against the dark forest."""
    w, h = surf.get_size()
    rng = random.Random(seed)
    mask = pygame.mask.from_surface(surf, 40)
    # ragged rim light
    for (x, y) in mask.outline():
        if 0 <= x < w and 0 <= y < h and rng.random() < 0.6:
            surf.set_at((x, y), rim_color)
    # dark-red drips hanging from the lowest edge of the body
    for x in range(1, w - 1):
        if rng.random() > 0.12:
            continue
        low = -1
        for y in range(h - 1, -1, -1):
            if mask.get_at((x, y)):
                low = y
                break
        if 0 <= low < h - 3:
            for k in range(1, rng.randint(2, 6)):
                if low + k < h:
                    surf.set_at((x, low + k), (140, 8, 14, max(60, 220 - k * 35)))
    return surf


def generate_enemy_sprite(enemy_type='aswang', width=64, height=64, state='idle'):
    """Generate enemy sprite supporting all animation states."""
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    is_atk = (state in ('attack', 'lunge'))
    is_crawl = (state in ('crawl', 'crouch', 'stalk'))
    is_move = (state in ('walk', 'run', 'sprint'))
    is_dead = (state == 'death')
    is_hov = (state in ('hover', 'float'))

    if enemy_type == 'aswang':
        bc, ec = (40, 30, 35), (255, 30, 30) if is_atk else (220, 30, 30)
        if is_dead:
            pygame.draw.ellipse(surf, (25, 18, 22), (10, 46, 44, 16))
        elif is_crawl:
            pygame.draw.ellipse(surf, bc, (12, 24, 40, 26))
            pygame.draw.circle(surf, ec, (22, 32), 3)
            pygame.draw.circle(surf, ec, (30, 32), 3)
            pygame.draw.line(surf, bc, (16, 36), (8, 52), 3)
            pygame.draw.line(surf, bc, (44, 36), (52, 52), 3)
        else:
            y_o = 4 if is_move else 0
            pygame.draw.ellipse(surf, bc, (16, 8 + y_o, 32, 48))
            pygame.draw.ellipse(surf, (50, 35, 40), (20, 12 + y_o, 24, 20))
            pygame.draw.circle(surf, ec, (28, 20 + y_o), 4 if is_atk else 3)
            pygame.draw.circle(surf, ec, (36, 20 + y_o), 4 if is_atk else 3)
            pygame.draw.line(surf, bc, (18, 28 + y_o), (6 if is_atk else 10, 50), 3)
            pygame.draw.line(surf, bc, (46, 28 + y_o), (58 if is_atk else 54, 50), 3)
            pygame.draw.polygon(surf, (235, 230, 215), [(29, 30), (31, 30), (30, 35)])
            pygame.draw.polygon(surf, (235, 230, 215), [(33, 30), (35, 30), (34, 35)])

    elif enemy_type == 'manananggal':
        bc, wc = (50, 25, 35), (70, 20, 30)
        h_o = 8 if is_hov or is_atk else 0
        if is_dead:
            pygame.draw.ellipse(surf, (30, 15, 20), (18, 46, 28, 16))
        else:
            pygame.draw.ellipse(surf, bc, (20, 16 - h_o, 24, 32))
            pygame.draw.ellipse(surf, (65, 35, 45), (24, 18 - h_o, 16, 14))
            pygame.draw.circle(surf, (255, 40, 40), (30, 24 - h_o), 2)
            pygame.draw.circle(surf, (255, 40, 40), (34, 24 - h_o), 2)
            pygame.draw.polygon(surf, wc, [(20, 20 - h_o), (0, 8), (8, 36)])
            pygame.draw.polygon(surf, wc, [(44, 20 - h_o), (64, 8), (56, 36)])
            pygame.draw.line(surf, (180, 30, 30), (24, 48 - h_o), (20, 60), 2)
            pygame.draw.line(surf, (180, 30, 30), (40, 48 - h_o), (44, 60), 2)

    elif enemy_type == 'tikbalang':
        bc = (80, 60, 40)
        if is_dead:
            pygame.draw.rect(surf, (40, 30, 20), (12, 44, 40, 18))
        else:
            pygame.draw.ellipse(surf, bc, (18, 4, 28, 20))
            pygame.draw.polygon(surf, (90, 70, 45), [(26, 2), (32, 0), (38, 2), (36, 8), (28, 8)])
            pygame.draw.circle(surf, (255, 180, 0), (28, 12), 2)
            pygame.draw.circle(surf, (255, 180, 0), (36, 12), 2)
            pygame.draw.ellipse(surf, bc, (16, 22, 32, 28))
            pygame.draw.line(surf, bc, (22, 48), (14, 64), 4)
            pygame.draw.line(surf, bc, (42, 48), (50, 64), 4)

    elif enemy_type == 'kapre':
        bc = (45, 35, 25)
        if is_dead:
            pygame.draw.ellipse(surf, (25, 20, 15), (8, 48, 48, 14))
        else:
            pygame.draw.ellipse(surf, bc, (10, 4, 44, 56))
            pygame.draw.ellipse(surf, (55, 42, 30), (18, 8, 28, 18))
            pygame.draw.circle(surf, (200, 100, 0), (28, 16), 3)
            pygame.draw.circle(surf, (200, 100, 0), (36, 16), 3)
            pygame.draw.rect(surf, (120, 80, 40), (40, 24, 18, 4))

    elif enemy_type == 'white_lady':
        h_o = 6 if is_hov or is_crawl else 0
        if is_dead:
            pygame.draw.ellipse(surf, (150, 150, 160, 100), (16, 48, 32, 14))
        else:
            pygame.draw.ellipse(surf, (220, 220, 230, 160), (16, 4 - h_o, 32, 56))
            pygame.draw.ellipse(surf, (240, 240, 250, 180), (20, 6 - h_o, 24, 18))
            pygame.draw.circle(surf, (0, 0, 0), (28, 14 - h_o), 2)
            pygame.draw.circle(surf, (0, 0, 0), (36, 14 - h_o), 2)

    elif enemy_type == 'multo':
        h_o = 10 if is_hov or is_atk else 0
        if is_dead:
            pygame.draw.ellipse(surf, (120, 120, 140, 80), (16, 50, 32, 12))
        else:
            for i in range(3):
                alpha = 80 - i * 20
                pygame.draw.ellipse(surf, (180, 180, 200, alpha),
                                    (14 - i * 3, 8 - h_o - i * 2, 36 + i * 6, 48 + i * 4))
            pygame.draw.circle(surf, (100, 100, 120, 150), (28, 20 - h_o), 2)
            pygame.draw.circle(surf, (100, 100, 120, 150), (36, 20 - h_o), 2)

    elif enemy_type == 'sigbin':
        bc = (50, 40, 45)
        if is_dead:
            pygame.draw.ellipse(surf, (30, 25, 25), (10, 46, 44, 16))
        else:
            pygame.draw.ellipse(surf, bc, (8, 24, 48, 24))
            pygame.draw.ellipse(surf, (60, 45, 50), (12, 16, 20, 14))
            ec = (255, 100, 0) if is_atk else (255, 60, 0)
            pygame.draw.circle(surf, ec, (20, 22), 2)
            pygame.draw.circle(surf, ec, (26, 22), 2)
            pygame.draw.line(surf, bc, (14, 44), (8, 60), 3)
            pygame.draw.line(surf, bc, (50, 44), (56, 60), 3)

    _horror_finish(surf, RIM_COLORS.get(enemy_type, (150, 30, 30)), seed=sum(map(ord, enemy_type)) + (7 if is_atk else 0))
    return surf


def generate_pickup_sprite(pickup_type='health', size=32):
    """Generate pickup item sprites."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2

    if pickup_type == 'health':
        pygame.draw.rect(surf, (200, 40, 40), (4, 4, size - 8, size - 8), border_radius=4)
        pygame.draw.rect(surf, (255, 255, 255), (cx - 2, cy - 8, 4, 16))
        pygame.draw.rect(surf, (255, 255, 255), (cx - 8, cy - 2, 16, 4))
    elif pickup_type == 'ammo_shotgun':
        pygame.draw.rect(surf, (180, 140, 40), (8, 6, 16, 20), border_radius=2)
        pygame.draw.rect(surf, (200, 50, 50), (10, 4, 12, 6))
    elif pickup_type == 'ammo_revolver':
        for i in range(6):
            angle = i * math.pi / 3
            bx = cx + int(math.cos(angle) * 8)
            by = cy + int(math.sin(angle) * 8)
            pygame.draw.circle(surf, (180, 140, 40), (bx, by), 3)
            pygame.draw.circle(surf, (200, 50, 50), (bx, by), 2)
    elif pickup_type == 'salt':
        pygame.draw.rect(surf, (220, 220, 220), (8, 8, 16, 18), border_radius=2)
        pygame.draw.rect(surf, (180, 180, 180), (8, 8, 16, 5))
        for _ in range(8):
            px = random.randint(10, 22)
            py = random.randint(14, 24)
            surf.set_at((px, py), (240, 240, 240))
    elif pickup_type == 'garlic':
        pygame.draw.circle(surf, (230, 220, 200), (cx, cy), 10)
        pygame.draw.circle(surf, (210, 200, 180), (cx, cy), 8)
        pygame.draw.line(surf, (180, 170, 150), (cx, cy - 8), (cx, cy + 8))
        pygame.draw.arc(surf, (100, 140, 60), (cx - 4, cy - 14, 8, 8), 0, math.pi, 2)
    elif pickup_type == 'battery':
        pygame.draw.rect(surf, (60, 60, 70), (10, 8, 12, 20), border_radius=2)
        pygame.draw.rect(surf, (80, 80, 90), (12, 4, 8, 6))
        pygame.draw.rect(surf, (255, 220, 50), (12, 12, 8, 12))
    elif pickup_type == 'faith':
        pygame.draw.circle(surf, (80, 120, 220, 150), (cx, cy), 12)
        pygame.draw.circle(surf, (120, 160, 255, 200), (cx, cy), 6)
        for i in range(8):
            angle = i * math.pi / 4
            ex = cx + int(math.cos(angle) * 14)
            ey = cy + int(math.sin(angle) * 14)
            pygame.draw.line(surf, (100, 140, 240, 100), (cx, cy), (ex, ey))
    elif pickup_type == 'bible_page':
        pygame.draw.rect(surf, (220, 200, 160), (6, 4, 20, 26), border_radius=1)
        for i in range(5):
            pygame.draw.line(surf, (100, 80, 50), (9, 10 + i * 4), (23, 10 + i * 4))

    return surf



def generate_tree_billboard(tree_type='balete', width=64, height=256, seed=42):
    """Generate tall procedural tree billboards with bark, roots, branches, canopies.

    Billboards are tall (256px) so they read as towering from first-person.
    Each species has a distinct silhouette: balete has massive buttress roots
    and a dense drooping canopy; mahogany is straight and tall with a high
    umbrella crown; bamboo is slender with segmented nodes; dead trees are
    bare skeletal branches; banana/palm have tropical frond canopies.
    """
    import numpy as np
    rng = random.Random(seed)
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    cx = width // 2
    # (trunk_height_frac, trunk_width, canopy_height_frac, root_spread)
    ARCHETYPES = {
        'balete':       (0.42, 18, 0.38, 24),
        'mahogany':     (0.55, 12, 0.28, 16),
        'bamboo':       (0.72, 5,  0.12, 0),
        'dead':         (0.50, 14, 0.20, 18),
        'banana':       (0.48, 9,  0.40, 0),
        'palm':         (0.62, 7,  0.26, 0),
        'supernatural': (0.40, 22, 0.34, 26),
        # New Philippine tropical species
        'akasya':       (0.35, 14, 0.42, 12),     # broad umbrella-crown rain tree
        'narra':        (0.45, 10, 0.35, 14),     # spreading narra-style tree
        'tree_fern':    (0.65, 4,  0.15, 0),      # tall tree fern understory
        'strangler':    (0.40, 16, 0.38, 20),     # strangler fig / balete variant
    }
    th, tw, ch, rs = ARCHETYPES.get(tree_type, ARCHETYPES['balete'])
    trunk_top = int(height * (1.0 - th))
    trunk_base = height - 4
    is_sup = (tree_type == 'supernatural')
    is_dead = (tree_type == 'dead')
    is_bam = (tree_type == 'bamboo')
    is_trop = tree_type in ('banana', 'palm')
    tcb = (55, 38, 25) if not is_sup else (35, 20, 28)
    if is_bam:
        tcb = (90, 120, 70)

    # --- Buttress roots (flared base) ---
    if rs > 0:
        rcol = (35, 25, 18) if not is_sup else (25, 15, 20)
        rcol_dark = tuple(max(0, c - 10) for c in rcol)
        for side in (-1, 1):
            for i in range(4):
                rx = cx + side * (tw // 2 + i * 4 + rng.randint(-2, 2))
                ry_t = trunk_base - 6 - i * 5
                ry_b = trunk_base + 2
                pts = [(cx + side * tw // 2, ry_t), (rx, ry_t - 2),
                       (rx + side * 2, ry_b), (cx + side * tw // 2, ry_b)]
                pygame.draw.polygon(surf, rcol, pts)
                # Root highlight
                pygame.draw.line(surf, rcol_dark, pts[1], pts[2], 1)

    # --- Trunk with tapering and natural curvature ---
    # The trunk leans slightly and tapers from base to top, giving organic shape.
    lean_offset = rng.uniform(-3, 3)  # slight curve
    for y in range(trunk_top, trunk_base):
        t = (y - trunk_top) / max(1, trunk_base - trunk_top)
        # Taper: wider at base, narrower at top
        taper = 1.0 - 0.18 * (1.0 - t)
        tw2 = max(2, int(tw * taper))
        # Slight curvature: offset x by a sine function of height
        curve = int(lean_offset * math.sin(t * math.pi))
        x0 = cx - tw2 // 2 + curve
        shade = 0.78 + 0.22 * math.sin(y * 0.12 + seed * 0.01)
        col = tuple(max(0, int(c * shade)) for c in tcb)
        pygame.draw.line(surf, col, (x0, y), (x0 + tw2, y))
        # Bark texture: vertical striations
        if y % 3 == 0 and not is_bam:
            for gx in range(x0 + 2, x0 + tw2 - 1, 3):
                gcol = tuple(max(0, c - 18) for c in col)
                pygame.draw.line(surf, gcol, (gx, y), (gx + rng.randint(-1, 1), y + 2), 1)
        # Bamboo nodes
        if is_bam and y % 16 < 2:
            ncol = tuple(max(0, c - 25) for c in col)
            pygame.draw.line(surf, ncol, (x0, y), (x0 + tw2, y), 1)

    # --- Moss patches on trunk ---
    if not is_bam and not is_dead:
        for _ in range(rng.randint(4, 8)):
            mx = cx + rng.randint(-tw // 2 + 2, tw // 2 - 2)
            my = rng.randint(trunk_top + 10, trunk_base - 5)
            mr = rng.randint(2, 5)
            mc = (25 + rng.randint(0, 15), 55 + rng.randint(0, 25), 25 + rng.randint(0, 10), 180)
            pygame.draw.circle(surf, mc, (mx, my), mr)

    # --- Branches ---
    if not is_bam:
        bcol = tuple(max(0, c - 10) for c in tcb)
        nb = 4 if not is_dead else 2
        for i in range(nb):
            by = trunk_top + int((trunk_base - trunk_top) * (0.20 + i * 0.18))
            side = 1 if i % 2 == 0 else -1
            bx_s = cx + side * tw // 2
            bx_e = cx + side * (tw + rng.randint(14, 26))
            by_e = by - rng.randint(4, 14)
            pygame.draw.line(surf, bcol, (bx_s, by), (bx_e, by_e), 2)
            # Sub-branches
            if rng.random() > 0.3:
                sx = bx_e + side * rng.randint(2, 8)
                sy = by_e - rng.randint(2, 8)
                pygame.draw.line(surf, bcol, (bx_e, by_e), (sx, sy), 1)
                # Tiny twigs
                if rng.random() > 0.5:
                    pygame.draw.line(surf, bcol, (sx, sy),
                                     (sx + side * rng.randint(2, 5), sy - rng.randint(2, 5)), 1)

    canopy_top = int(height * (1.0 - th - ch))
    canopy_bot = trunk_top

    # --- Hanging Vines / Lianas (Tropical Jungle Atmosphere) ---
    if not is_dead and not is_bam and rng.random() > 0.2:
        vcol = (30, 65, 35)
        for _ in range(rng.randint(2, 5)):
            vx = cx + rng.randint(-tw, tw)
            vy = rng.randint(trunk_top, trunk_top + 30)
            v_len = rng.randint(15, 35)
            pygame.draw.line(surf, vcol, (vx, vy), (vx + rng.randint(-3, 3), vy + v_len), 1)

    # --- Extra foliage clusters for denser canopy (used by variant seeds) ---
    if not is_bam and not is_dead:
        extra_clumps = rng.randint(3, 7)
        for _ in range(extra_clumps):
            fx = cx + rng.randint(-tw * 2, tw * 2)
            fy = rng.randint(canopy_top, canopy_bot)
            fr = rng.randint(3, 8)
            fc = (20 + rng.randint(0, 15), 50 + rng.randint(0, 25), 20 + rng.randint(0, 10))
            pygame.draw.circle(surf, fc, (fx, fy), fr)

    # --- Canopy: layered, asymmetrical, species-specific ---

    if is_dead:
        # Bare skeletal branches reaching upward
        for i in range(6):
            ang = rng.uniform(-math.pi, math.pi)
            length = rng.randint(10, 20)
            bx2 = cx + math.cos(ang) * length
            by2 = canopy_bot - rng.randint(0, 18) + math.sin(ang) * length * 0.3
            pygame.draw.line(surf, (40, 30, 25), (cx, canopy_bot - 5), (bx2, by2), 2)
            # A few dead leaves clinging on
            if rng.random() > 0.6:
                pygame.draw.circle(surf, (60, 45, 25), (int(bx2), int(by2)), 2)
    elif is_bam:
        # Bamboo: sparse leaf clusters at the top
        for i in range(4):
            lx = cx + rng.randint(-12, 12)
            ly = canopy_bot - rng.randint(0, 18)
            pygame.draw.circle(surf, (50, 100, 50), (lx, ly), rng.randint(3, 6))
            pygame.draw.circle(surf, (65, 120, 55), (lx + 1, ly - 1), max(1, rng.randint(2, 4)))
    elif is_trop:
        # Tropical fronds: banana/palm fan-shaped leaves
        fcol = (45, 95, 40) if not is_sup else (30, 50, 25)
        nf = 7 if tree_type == 'palm' else 6
        for i in range(nf):
            ang = -math.pi / 2 + (i - nf / 2) * 0.38
            fx = cx + math.cos(ang) * rng.randint(22, 32)
            fy = canopy_top + math.sin(ang) * rng.randint(12, 22)
            pygame.draw.line(surf, fcol, (cx, canopy_top + 5), (fx, fy), 3)
            for j in range(4):
                lj = j + 1
                px = cx + (fx - cx) * lj / 5
                py = canopy_top + 5 + (fy - canopy_top - 5) * lj / 5
                pygame.draw.line(surf, (55, 115, 45), (px, py), (px + rng.randint(-5, 5), py - 5), 1)
    else:
        # Dense layered canopy: multiple overlapping circles for depth.
        # Dark base layer, mid-tone, and highlight layer give a 3D feel.
        if not is_sup:
            ccols = [(18, 42, 18), (25, 55, 25), (15, 35, 15)]
            hcols = [(35, 75, 35), (45, 90, 40)]
        else:
            ccols = [(15, 25, 20), (20, 30, 25), (10, 15, 15)]
            hcols = [(25, 40, 30), (30, 50, 35)]
        # Base layer: large dark circles
        for i in range(rng.randint(10, 16)):
            ox = rng.randint(-22, 22)
            oy = rng.randint(canopy_top, canopy_bot - 5)
            r = rng.randint(12, 24)
            col = rng.choice(ccols)
            col = tuple(max(0, min(255, c + rng.randint(-5, 5))) for c in col)
            pygame.draw.circle(surf, col, (cx + ox, oy), r)
        # Shadow detail layer
        for i in range(rng.randint(6, 10)):
            ox = rng.randint(-18, 18)
            oy = rng.randint(canopy_top + 3, canopy_bot - 8)
            r = rng.randint(8, 16)
            col = ccols[2]
            col = tuple(max(0, c - 5) for c in col)
            pygame.draw.circle(surf, col, (cx + ox + 2, oy + 3), r)
        # Highlight layer: lighter green on top-facing parts
        for i in range(rng.randint(5, 9)):
            ox = rng.randint(-16, 16)
            oy = rng.randint(canopy_top, canopy_bot - 10)
            r = rng.randint(6, 12)
            col = rng.choice(hcols)
            col = tuple(max(0, min(255, c + rng.randint(-5, 5))) for c in col)
            pygame.draw.circle(surf, col, (cx + ox - 1, oy - 1), r)
        # Scattered lighter leaf highlights at the very top
        for i in range(rng.randint(3, 6)):
            hx = cx + rng.randint(-14, 14)
            hy = canopy_top + rng.randint(0, 12)
            pygame.draw.circle(surf, (35, 70, 35), (hx, hy), rng.randint(3, 6))

    # --- Supernatural dark aura ---
    if is_sup:
        for i in range(5):
            r = 20 + i * 4
            pygame.draw.circle(surf, (60, 10, 40, 30), (cx, trunk_top + 10), r, 1)

    return surf

def generate_undergrowth_sprite(plant_type='fern', width=32, height=32, seed=42):
    random.seed(seed)
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    cx, cy = width // 2, height // 2

    if plant_type == 'fern':
        # Enhanced fern with more natural branching
        main_stem = height - 8
        for branch in range(4):
            branch_y = main_stem - branch * 6
            direction = 1 if branch % 2 == 0 else -1
            pygame.draw.line(surf, (35, 95, 35), (cx, branch_y), (cx + direction * 8, branch_y - 8), 2)
            for leaf in range(3):
                leaf_y = branch_y - 2 - leaf * 3
                pygame.draw.line(surf, (55, 140, 50), 
                                (cx + direction * 8, branch_y - 8),
                                (cx + direction * 12, leaf_y), 1)
    elif plant_type == 'mushroom':
        # Enhanced mushroom with gills and texturing
        pygame.draw.rect(surf, (200, 180, 150), (cx - 5, cy + 2, 10, 14))
        # Stem details
        pygame.draw.line(surf, (170, 150, 130), (cx - 2, cy + 2), (cx - 2, cy + 16), 1)
        pygame.draw.line(surf, (170, 150, 130), (cx + 2, cy + 2), (cx + 2, cy + 16), 1)
        # Cap texture
        cap_surf = pygame.Surface((width, height), pygame.SRCALPHA)
        for i in range(8):
            angle = math.pi + i * math.pi / 6
            dx = cx + math.cos(angle) * 12
            dy = cy + 6 + math.sin(angle) * 12
            pygame.draw.circle(cap_surf, (190, 60, 60, 40), (int(dx), int(dy)), 3)
        surf.blit(cap_surf, (0, 0))
        pygame.draw.arc(surf, (220, 40, 40), (cx - 10, cy - 8, 20, 12), 0, math.pi, 6)
    elif plant_type == 'rock':
        # Enhanced rock with depth and texture
        base = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.ellipse(base, (90, 95, 100), (2, height - 18, 28, 16))
        # Add shadow
        shadow = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (50, 55, 60, 60), (4, height - 14, 24, 12))
        surf.blit(shadow, (0, 0))
        surf.blit(base, (0, 0))
        # Texture details
        for i in range(5):
            tx = random.randint(8, 24)
            ty = random.randint(height - 14, height - 6)
            pygame.draw.circle(surf, (70, 75, 80), (tx, ty), random.randint(1, 2))
    elif plant_type == 'log':
        # Fallen log with bark texture and moss
        log_surf = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.ellipse(log_surf, (70, 50, 30), (2, height - 10, 28, 8))
        pygame.draw.ellipse(log_surf, (55, 40, 25), (4, height - 8, 24, 5))
        # Bark lines
        for i in range(4):
            ly = height - 9 + i * 2
            pygame.draw.line(log_surf, (45, 35, 25), (4, ly), (28, ly), 1)
        # Moss on one end
        pygame.draw.circle(log_surf, (30, 60, 30, 150), (6, height - 6), 3)
        pygame.draw.circle(log_surf, (40, 70, 35, 120), (26, height - 6), 2)
        surf.blit(log_surf, (0, 0))
    elif plant_type == 'stump':
        # Tree stump with rings
        pygame.draw.ellipse(surf, (65, 50, 35), (4, height - 14, 24, 12))
        pygame.draw.ellipse(surf, (50, 38, 25), (6, height - 12, 20, 9))
        for r in range(3):
            pygame.draw.ellipse(surf, (70 + r * 5, 55 + r * 3, 38 + r * 2),
                                (8 + r * 2, height - 11 - r * 2, 16 - r * 4, 6 - r * 2))
        # Dark center
        pygame.draw.ellipse(surf, (30, 22, 15), (12, height - 9, 8, 4))
    elif plant_type == 'boulder':
        # Large mossy boulder
        base = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.ellipse(base, (75, 80, 85), (1, height - 22, 30, 18))
        shadow = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (45, 50, 55, 50), (3, height - 18, 26, 14))
        surf.blit(shadow, (0, 0))
        surf.blit(base, (0, 0))
        # Moss on top
        for _ in range(4):
            mx = random.randint(6, 24)
            my = random.randint(height - 20, height - 10)
            pygame.draw.circle(surf, (30, 55, 30, 120), (mx, my), random.randint(2, 4))
    elif plant_type == 'sapling':
        # Small tree sapling with thin trunk and small canopy
        trunk_col = (60, 45, 30)
        pygame.draw.line(surf, trunk_col, (cx, height - 4), (cx, height - 20), 2)
        # Small canopy circles
        for _ in range(3):
            ox = random.randint(-6, 6)
            oy = random.randint(-28, -20)
            r = random.randint(4, 7)
            pygame.draw.circle(surf, (35, 70, 35), (cx + ox, height + oy), r)
            pygame.draw.circle(surf, (50, 90, 45), (cx + ox + 1, height + oy - 1), max(1, r - 2))
    else:  # bush
        # Enhanced bush with layered foliage
        layers = 3
        for layer in range(layers):
            size = 14 - layer * 3
            offset = layer * 4
            base_color = (30 + layer * 15, 75 + layer * 15, 35 + layer * 10)
            top_color = (40 + layer * 15, 95 + layer * 15, 45 + layer * 10)
            cx_layer = cx + (layer - 1) * 4
            pygame.draw.circle(surf, base_color, (cx_layer - 5, cy + 4 + offset), size)
            pygame.draw.circle(surf, top_color, (cx_layer + 5, cy + 2 + offset), size)
            # Highlight
            pygame.draw.circle(surf, (80, 130, 70, 80), (cx_layer - 3, cy + offset), size // 2)

    return surf


def generate_crosshair(size=16):
    """Generate a simple crosshair."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    gap = 2
    length = 5
    color = (255, 255, 255, 180)
    pygame.draw.line(surf, color, (cx, cy - gap - length), (cx, cy - gap), 1)
    pygame.draw.line(surf, color, (cx, cy + gap), (cx, cy + gap + length), 1)
    pygame.draw.line(surf, color, (cx - gap - length, cy), (cx - gap, cy), 1)
    pygame.draw.line(surf, color, (cx + gap, cy), (cx + gap + length, cy), 1)
    return surf


def generate_all_textures():
    """Generate and return all wall textures."""
    textures = {
        'stone': generate_wall_texture(64, 64, (70, 55, 40), 12, 'stone'),
        'wood': generate_wall_texture(64, 64, (90, 60, 30), 10, 'wood'),
        'bamboo': generate_wall_texture(64, 64, (100, 130, 60), 15, 'bamboo'),
        'balete': generate_wall_texture(64, 64, (50, 45, 30), 12, 'balete'),
        'door': generate_wall_texture(64, 64, (80, 50, 25), 8, 'wood'),
        'floor': generate_floor_texture(64, 64, (25, 18, 12)),
    }
    return textures


# Where the bolo's handle sits inside its 128x128 viewmodel surface, as fractions
# of the surface. The renderer pivots the swing on `pivot` and draws the hand at
# `grip`. Defaults match the procedural bolo; the custom sprite overrides them.
BOLO_ANCHORS = {'pivot': (0.47, 1.0), 'grip': (0.47, 0.85)}
# Hand positions on the custom shotgun viewmodel, as fractions of its 128px surface.
# Empty until the custom sprite loads (the renderer then uses its default hand spots).
SHOTGUN_ANCHORS = {}


def _load_custom_bolo_sprite(size=128) -> Optional[pygame.Surface]:
    """Load assets/sprites/weapons/bolo/bolo_fpv.png as the bolo viewmodel.

    The art is already drawn for a right-handed first-person view (handle at the
    bottom-right, blade pointing up-left), so it is only cropped to its visible
    pixels, smooth-scaled to fit size x size (aspect preserved) and anchored to
    the bottom-right. Returns None if the file is missing or can't be loaded so
    the procedural bolo is used instead.
    """
    path = os.path.join(ASSET_DIR, 'sprites', 'weapons', 'bolo', 'bolo_fpv.png')
    try:
        if not os.path.exists(path):
            return None
        img = pygame.image.load(path).convert_alpha()
        bbox = img.get_bounding_rect()
        if bbox.width == 0 or bbox.height == 0:
            return None
        img = img.subsurface(bbox).copy()
        k = min(size / img.get_width(), size / img.get_height())
        new_w = max(1, int(img.get_width() * k))
        new_h = max(1, int(img.get_height() * k))
        # smoothscale keeps the 2px-wide blade from breaking up when shrunk
        img = pygame.transform.smoothscale(img, (new_w, new_h))
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        # Anchor bottom-right so the handle sits at the corner the hand grips
        ox, oy = size - new_w, size - new_h
        surf.blit(img, (ox, oy))
        # Handle end / grip positions measured on the 640px source art
        # (handle end ~ (585, 520), grip ~ (520, 480) inside the 40..600 x 85..555 bbox)
        def frac(sx, sy):
            return ((ox + (sx - bbox.x) * k) / size, (oy + (sy - bbox.y) * k) / size)
        BOLO_ANCHORS['pivot'] = frac(585, 520)
        BOLO_ANCHORS['grip'] = frac(520, 480)
        return surf
    except Exception:
        return None


def _load_custom_shotgun_sprite(size=128) -> Optional[pygame.Surface]:
    """Load assets/sprites/weapons/shotgun/shotgun_hero.png as the shotgun viewmodel.

    The pack art has the stock at the top-left and the barrel pointing down-right.
    Like the bolo, it is rotated 180 degrees so the stock sits at the bottom-right
    and the barrel points up-left for a right-handed first-person view, then
    cropped to its visible pixels, smooth-scaled to fit size x size (aspect
    preserved) and anchored bottom-right. Returns None if the file is missing or
    can't be loaded so the procedural shotgun is used instead.
    """
    path = os.path.join(ASSET_DIR, 'sprites', 'weapons', 'shotgun', 'shotgun_hero.png')
    try:
        if not os.path.exists(path):
            return None
        img = pygame.image.load(path).convert_alpha()
        img = pygame.transform.rotate(img, 180)
        bbox = img.get_bounding_rect()
        if bbox.width == 0 or bbox.height == 0:
            return None
        img = img.subsurface(bbox).copy()
        k = min(size / img.get_width(), size / img.get_height())
        new_w = max(1, int(img.get_width() * k))
        new_h = max(1, int(img.get_height() * k))
        img = pygame.transform.smoothscale(img, (new_w, new_h))
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        ox, oy = size - new_w, size - new_h
        surf.blit(img, (ox, oy))

        # Hand spots measured on the rotated 640px art: right hand on the
        # receiver / wrist behind the pump, left hand on the pump forend.
        def frac(sx, sy):
            return ((ox + (sx - bbox.x) * k) / size, (oy + (sy - bbox.y) * k) / size)
        SHOTGUN_ANCHORS['right'] = frac(425, 365)
        SHOTGUN_ANCHORS['left'] = frac(300, 320)
        return surf
    except Exception:
        return None


def generate_all_weapons():
    """Generate all weapon sprites."""
    bolo = _load_custom_bolo_sprite(128)
    return {
        'bolo': bolo or generate_weapon_sprite('bolo', 128, 128),
        'shotgun': _load_custom_shotgun_sprite(128) or generate_weapon_sprite('shotgun', 128, 128),
        'revolver': generate_weapon_sprite('revolver', 128, 128),
    }


# Custom sprite cache: loaded once per type
_CUSTOM_ENEMY_SPRITES_CACHE = {}

# Map animation states to file names
def _state_to_filename(enemy_type: str, state: str) -> str:
    """Map game state to PNG filename pattern."""
    if state == 'death':
        return f'{enemy_type}_idle.png'
    elif state in ('attack', 'lunge', 'run', 'sprint'):
        return f'{enemy_type}_attack.png'
    else:  # idle, walk, stalk, crawl, crouch, hover, stagger
        return f'{enemy_type}_idle.png'


def _load_custom_sprite(enemy_type: str, state: str) -> Optional[pygame.Surface]:
    """Load a custom sprite PNG if available, return None to fall back to procedural."""
    global _CUSTOM_ENEMY_SPRITES_CACHE
    
    filename = _state_to_filename(enemy_type, state)
    filepath = os.path.join(ASSET_DIR, 'sprites', 'enemies', filename)
    
    # Check cache first
    cache_key = (enemy_type, state)
    if cache_key in _CUSTOM_ENEMY_SPRITES_CACHE:
        return _CUSTOM_ENEMY_SPRITES_CACHE[cache_key]
    
    # Try to load
    try:
        if os.path.exists(filepath):
            surf = pygame.image.load(filepath).convert_alpha()
            # Scale to 64x64 with nearest-neighbor for crisp pixel art
            surf = pygame.transform.scale(surf, (64, 64))
            _CUSTOM_ENEMY_SPRITES_CACHE[cache_key] = surf
            return surf
    except Exception:
        pass
    
    return None


def generate_all_enemies():
    """Generate all enemy sprites, preferring animated packs over static PNGs."""
    import os
    from settings import USE_CUSTOM_ENEMY_SPRITES, BASE_PATH
    from animation_core import get_enemy_animation_system
    
    # Try to load the animation pack first
    anim_sys = get_enemy_animation_system()
    pack_dir = os.path.join(BASE_PATH, 'enemy_animations_pack')
    
    if USE_CUSTOM_ENEMY_SPRITES and os.path.exists(pack_dir):
        print(f'[ASSETS] Attempting to load enemy animation pack from: {pack_dir}')
        if anim_sys.load_from_pack(pack_dir, target_size=64):
            print('[ASSETS] ✓ Loaded animated enemy sprite sheets successfully!')
            # Return a compatible dict structure using the first frame of each animation
            enemies = {}
            for etype in anim_sys.frames:
                enemies[etype] = {}
                for sheet_name, frame_list in anim_sys.frames[etype].items():
                    if frame_list:
                        # Map sheet names back to game states
                        if sheet_name == 'run':
                            for state in ['idle', 'walk', 'run', 'sprint', 'hover']:
                                enemies[etype][state] = frame_list[0]
                        elif sheet_name == 'crawl':
                            for state in ['crawl', 'stalk', 'crouch']:
                                enemies[etype][state] = frame_list[0]
                        elif sheet_name == 'attack':
                            for state in ['attack', 'lunge', 'stagger', 'death']:
                                enemies[etype][state] = frame_list[0]
                        # Unique moves
                        enemies[etype][sheet_name] = frame_list[0]
            return enemies
    
    # Fallback to static PNGs or procedural generation
    enemies = {}
    types = ['aswang', 'manananggal', 'tikbalang', 'kapre', 'white_lady', 'multo', 'sigbin']
    states = ['idle', 'walk', 'run', 'sprint', 'crawl', 'stalk', 'crouch', 'lunge', 'attack', 'stagger', 'death', 'hover']
    
    for t in types:
        enemies[t] = {}
        used_custom = False
        for s in states:
            if USE_CUSTOM_ENEMY_SPRITES:
                custom_surf = _load_custom_sprite(t, s)
                if custom_surf is not None:
                    rim = RIM_COLORS.get(t, (255, 255, 255))
                    _horror_finish(custom_surf, rim, seed=abs(hash(f'{t}_{s}')) % 10000)
                    enemies[t][s] = custom_surf
                    used_custom = True
                    continue
            enemies[t][s] = generate_enemy_sprite(t, 64, 64, s)
        
        status = 'custom PNGs' if used_custom else 'procedural fallback'
        print(f'[ASSETS] Enemy "{t}": using {status}')
    
    return enemies


def generate_all_pickups():
    """Generate all pickup sprites."""
    pickup_types = ['health', 'ammo_shotgun', 'ammo_revolver', 'salt', 'garlic',
                    'battery', 'faith', 'bible_page']
    return {t: generate_pickup_sprite(t, 32) for t in pickup_types}


def generate_world_ground_texture(width=1024, height=1024, chapter=1):
    """Bake a dense grassy-knoll forest ground texture."""
    import settings as _s
    cache_filename = getattr(_s, 'GROUND_CACHE_FILENAME', 'world_ground_knoll_v1.npy')
    cache_path = os.path.join(ASSET_DIR, 'cache', cache_filename)
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    import numpy as np
    if os.path.exists(cache_path):
        try:
            arr = np.load(cache_path)
            surf = pygame.Surface((width, height))
            pygame.surfarray.blit_array(surf, arr)
            return surf
        except Exception:
            pass

    base_soil = np.array([22, 28, 20], dtype=np.float32)
    n_base = generate_fbm_noise(width, height, octaves=6, seed=999 + chapter)
    n_mound = generate_fbm_noise(width, height, octaves=4, seed=777 + chapter)
    warp_x = generate_fbm_noise(width, height, octaves=3, seed=555 + chapter) * 40.0
    warp_y = generate_fbm_noise(width, height, octaves=3, seed=333 + chapter) * 40.0
    xs = np.arange(width, dtype=np.float32)
    ys = np.arange(height, dtype=np.float32)
    xx, yy = np.meshgrid(xs, ys)
    wx = np.clip(((xx + warp_x) % width).astype(np.int32), 0, width-1)
    wy = np.clip(((yy + warp_y) % height).astype(np.int32), 0, height-1)
    mounds = n_mound[wy, wx]
    undulation = 0.6 * n_base + 0.4 * mounds
    arr = base_soil[np.newaxis, np.newaxis, :] + (undulation[:, :, np.newaxis] - 0.5) * 28.0
    shadow_olive = np.array([48, 48, 16], dtype=np.float32) * 0.42
    dark_moss = np.array([48, 80, 16], dtype=np.float32) * 0.42
    mid_olive = np.array([80, 80, 48], dtype=np.float32) * 0.42
    mid_green = np.array([80, 112, 48], dtype=np.float32) * 0.42
    muted_sage = np.array([112, 144, 80], dtype=np.float32) * 0.42
    dry_yellow_green = np.array([112, 112, 48], dtype=np.float32) * 0.42
    moonlit_tip = np.array([180, 195, 170], dtype=np.float32) * 0.55

    grass_layers = min(6, max(2, int(getattr(_s, 'ACTIVE_QUALITY', {}).get('ground_grass_blade_layers', 4))))
    blade_rng = np.random.RandomState(1000 + chapter)
    for layer in range(grass_layers):
        num_blades = 8000 + layer * 3000
        bx = blade_rng.randint(0, width, num_blades)
        by = blade_rng.randint(0, height, num_blades)
        bangle = blade_rng.uniform(-0.8, 0.8, num_blades)
        blen = blade_rng.uniform(2, 6, num_blades)
        if layer < 2:
            colors = np.vstack([shadow_olive, dark_moss])
        elif layer < 4:
            colors = np.vstack([mid_olive, mid_green, muted_sage])
        else:
            colors = np.vstack([muted_sage, dry_yellow_green, moonlit_tip])
        bc = colors[blade_rng.randint(0, len(colors), num_blades)]
        dx = np.cos(bangle) * blen
        dy = -np.sin(bangle) * blen
        for i in range(num_blades):
            x0, y0 = bx[i], by[i]
            x1, y1 = int(x0 + dx[i]), int(y0 + dy[i])
            cx0, cy0 = max(0, min(width-1, x0)), max(0, min(height-1, y0))
            cx1, cy1 = max(0, min(width-1, x1)), max(0, min(height-1, y1))
            steps = max(abs(cx1-cx0), abs(cy1-cy0), 1)
            for s in range(steps + 1):
                t = s / max(1, steps)
                px = int(cx0 + (cx1-cx0)*t)
                py = int(cy0 + (cy1-cy0)*t)
                if 0 <= px < width and 0 <= py < height:
                    arr[py, px] = arr[py, px] * 0.7 + bc[i] * 0.3

    clump_noise = generate_fbm_noise(width, height, octaves=5, seed=888 + chapter)
    clump_mask = (clump_noise > 0.45).astype(np.float32)
    arr = arr * (0.65 + 0.35 * clump_mask[:, :, np.newaxis])

    if getattr(_s, 'ACTIVE_QUALITY', {}).get('ground_enable_clover', True):
        clover_noise = generate_fbm_noise(width, height, octaves=4, seed=7771 + chapter)
        clover_mask = (clover_noise > 0.6).astype(np.float32)
        clover_color = np.array([60, 90, 50], dtype=np.float32) * 0.45
        for _ in range(300):
            cx = blade_rng.randint(5, width-5)
            cy = blade_rng.randint(5, height-5)
            if clover_mask[cy, cx] > 0.5:
                y0, y1 = max(0, cy-2), min(height, cy+3)
                x0, x1 = max(0, cx-2), min(width, cx+3)
                arr[y0:y1, x0:x1] = arr[y0:y1, x0:x1] * 0.7 + clover_color * 0.3

    if getattr(_s, 'ACTIVE_QUALITY', {}).get('ground_enable_flowers', True):
        for _ in range(100):
            fx = blade_rng.randint(5, width-5)
            fy = blade_rng.randint(5, height-5)
            y0, y1 = max(0, fy-1), min(height, fy+2)
            x0, x1 = max(0, fx-1), min(width, fx+2)
            arr[y0:y1, x0:x1] = np.clip(arr[y0:y1, x0:x1] * 0.6 + moonlit_tip * 0.4, 0, 255)

    trail_noise = generate_fbm_noise(width, height, octaves=3, seed=6666 + chapter)
    trail_mask = (trail_noise > 0.65).astype(np.float32)
    trail_color = np.array([35, 30, 22], dtype=np.float32)
    arr = arr * (1.0 - trail_mask[:, :, np.newaxis] * 0.4) + trail_color[np.newaxis, np.newaxis, :] * trail_mask[:, :, np.newaxis] * 0.4

    if getattr(_s, 'ACTIVE_QUALITY', {}).get('ground_enable_roots', True):
        for _ in range(50):
            rx = blade_rng.randint(0, width)
            ry = blade_rng.randint(0, height)
            rlen = blade_rng.randint(15, 50)
            angle = blade_rng.uniform(0, math.pi * 2)
            for i in range(rlen):
                px = int(rx + math.cos(angle) * i)
                py = int(ry + math.sin(angle) * i)
                if 0 <= px < width and 0 <= py < height:
                    arr[py, px] *= 0.82

    gray = arr.mean(axis=2, keepdims=True)
    arr = arr * 0.7 + gray * 0.3
    arr[:, :, 2] = np.clip(arr[:, :, 2] * 1.08 + 3.0, 0, 255)
    arr[:, :, 1] = np.clip(arr[:, :, 1] * 1.04, 0, 255)
    arr = np.clip(arr, 0, 255).astype(np.uint8)

    np.save(cache_path, arr)
    print(f"[ASSET] Ground texture cached to {cache_path}")
    return pygame.surfarray.make_surface(arr.transpose((1, 0, 2)))
