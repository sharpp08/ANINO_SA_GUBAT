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



def generate_tree_billboard(tree_type='balete', width=64, height=128, seed=42):
    """Generate detailed procedural tree billboards with bark shading, roots, moss, and canopy."""
    import numpy as np
    random.seed(seed)
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    cx = width // 2

    if tree_type == 'balete':
        for rx in range(-20, 21, 4):
            rx_pos = cx + rx
            ry_base = height - 10
            ry_top = height - 40 - abs(rx) * 0.8
            pygame.draw.line(surf, (45, 30, 20), (cx + rx // 2, ry_base), (rx_pos, int(ry_top)), 5)
        pygame.draw.rect(surf, (55, 38, 25), (cx - 14, height - 70, 28, 60))
        for bx in range(cx - 12, cx + 12, 4):
            pygame.draw.line(surf, (35, 22, 15), (bx, height - 68), (bx + random.randint(-2, 2), height - 15), 2)
        for _ in range(5):
            mx = cx + random.randint(-12, 8)
            my = random.randint(height - 50, height - 20)
            pygame.draw.circle(surf, (30, 60, 30, 200), (mx, my), random.randint(3, 6))
        for i in range(7):
            ox = random.randint(-22, 22)
            oy = random.randint(10, 50 - i * 5)
            cr = random.randint(18, 30)
            col = (20 + random.randint(0, 20), 45 + random.randint(0, 25), 20 + random.randint(0, 15))
            pygame.draw.circle(surf, col, (cx + ox, height - oy - 55), cr)
            pygame.draw.circle(surf, (10, 25, 10, 180), (cx + ox + 2, height - oy - 53), cr - 3)

    elif tree_type == 'bamboo':
        for b_idx in range(5):
            bx = cx - 16 + b_idx * 8 + random.randint(-2, 2)
            b_height = height - random.randint(10, 30)
            pygame.draw.line(surf, (110, 140, 80), (bx, height - 5), (bx + random.randint(-2, 2), height - b_height), 5)
            for ny in range(height - 15, height - b_height, 14):
                pygame.draw.line(surf, (80, 100, 50), (bx - 3, ny), (bx + 3, ny), 2)
            for lx in range(-12, 14, 6):
                pygame.draw.line(surf, (90, 130, 60), (bx, height - b_height), (bx + lx, height - b_height - 15), 2)

    elif tree_type == 'banana' or tree_type == 'palm':
        for ty in range(height - 20, height - 80, -2):
            tx_off = int(math.sin(ty * 0.05) * 4)
            pygame.draw.rect(surf, (70, 80, 50), (cx - 6 + tx_off, ty, 12, 3))
        fy = height - 85
        for angle_deg in range(-70, 75, 25):
            rad = math.radians(angle_deg)
            fx = cx + int(math.cos(rad) * 35)
            f_end_y = fy + int(math.sin(rad) * 25) - 15
            pygame.draw.line(surf, (50, 110, 40), (cx, fy), (fx, f_end_y), 4)
            pygame.draw.line(surf, (70, 140, 50), (cx + (fx - cx)//2, fy + (f_end_y - fy)//2), (fx + 5, f_end_y - 8), 2)

    elif tree_type == 'pine':
        # Enhanced pine with layered needles and texture
        pygame.draw.rect(surf, (60, 45, 30), (cx - 5, height - 40, 10, 40))
        # Textured trunk
        pygame.draw.line(surf, (45, 35, 25), (cx - 2, height - 35), (cx - 2, height - 5), 2)
        pygame.draw.line(surf, (45, 35, 25), (cx + 2, height - 35), (cx + 2, height - 5), 2)
        for layer in range(5):
            ly = height - 40 - layer * 20
            lw = 32 - layer * 6
            # Main needle polygon
            pts = [(cx, ly - 22), (cx - lw, ly), (cx + lw, ly)]
            base_color = 20 + layer * 4
            light_color = 55 + layer * 8
            dark_color = 15 + layer * 3
            pygame.draw.polygon(surf, (base_color, light_color, dark_color), pts)
            # Inner highlight for depth
            highlight_pts = [(cx, ly - 18), (cx - lw // 2, ly - 4), (cx + lw // 2, ly - 4)]
            pygame.draw.polygon(surf, (base_color + 15, light_color + 20, dark_color + 10), highlight_pts)

    else:
        pygame.draw.rect(surf, (60, 55, 50), (cx - 8, height - 80, 16, 75))
        pygame.draw.line(surf, (50, 45, 40), (cx, height - 50), (cx - 25, height - 85), 4)
        pygame.draw.line(surf, (50, 45, 40), (cx, height - 60), (cx + 22, height - 90), 4)

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


def generate_all_weapons():
    """Generate all weapon sprites."""
    return {
        'bolo': generate_weapon_sprite('bolo', 128, 128),
        'shotgun': generate_weapon_sprite('shotgun', 128, 128),
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


def generate_world_ground_texture(width=1024, height=1024):
    """Bake a large world-sized ground texture with fBm noise, moss, mud, and paths, with disk caching."""
    cache_path = os.path.join(ASSET_DIR, 'cache', 'world_ground.npy')
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

    noise = generate_fbm_noise(width, height, octaves=6, seed=999)
    base = np.array([25, 18, 12], dtype=np.float32)
    arr = np.zeros((height, width, 3), dtype=np.float32)

    for y in range(height):
        for x in range(width):
            n = noise[y, x]
            if n > 0.65:
                col = np.array([35, 55, 30], dtype=np.float32) + (n - 0.65) * 30
            elif n < 0.35:
                col = np.array([18, 12, 8], dtype=np.float32) + n * 25
            else:
                col = base + (n - 0.5) * 40
            arr[y, x] = np.clip(col, 0, 255)

    uint_arr = arr.astype(np.uint8)
    np.save(cache_path, uint_arr)
    surf = pygame.Surface((width, height))
    pygame.surfarray.blit_array(surf, uint_arr)
    return surf

