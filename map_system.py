"""
Map system - defines levels, handles endless procedural forest generation (chunk streaming),
reachability validation, and tile queries.

The world is endless: the 64x64 ``grid`` only holds the hand-authored area (cabin, river,
ponds). Anything outside it is open forest ground. Trees and undergrowth are generated per
CHUNK_SIZE x CHUNK_SIZE chunk, deterministically from (chapter seed, chunk coords), the first
time they are needed and dropped again when the player moves far away.
"""
import math
import random
import numpy as np
from settings import *


class SpatialHash:
    """Spatial hash for fast O(1) collision and tree lookup."""
    def __init__(self, cell_size=2.0):
        self.cell_size = cell_size
        self.cells = {}

    def clear(self):
        self.cells.clear()

    def insert(self, obj, x, y, radius):
        cx, cy = int(x // self.cell_size), int(y // self.cell_size)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                key = (cx + dx, cy + dy)
                if key not in self.cells:
                    self.cells[key] = []
                self.cells[key].append((obj, x, y, radius))

    def query(self, x, y, radius=0.5):
        cx, cy = int(x // self.cell_size), int(y // self.cell_size)
        key = (cx, cy)
        results = []
        if key in self.cells:
            for item in self.cells[key]:
                obj, ox, oy, orad = item
                if math.hypot(ox - x, oy - y) < (orad + radius):
                    results.append(obj)
        return results


# ─── Deterministic hashing / noise (no global RNG state) ─────────────────────
def _hash_int(seed, a, b, salt=0):
    """Mix (seed, a, b, salt) into a 32-bit int. Works for negative a / b."""
    n = (seed * 374761393 + a * 668265263 + b * 2147483647 + salt * 1274126177) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    n ^= n >> 16
    return n


def _hash01(seed, a, b, salt=0):
    return _hash_int(seed, a, b, salt) / 4294967296.0


def _value_noise(seed, x, y, scale):
    """Smooth 2D value noise in [0, 1], feature size ~scale tiles."""
    fx, fy = x / scale, y / scale
    x0, y0 = math.floor(fx), math.floor(fy)
    tx, ty = fx - x0, fy - y0
    tx = tx * tx * (3 - 2 * tx)
    ty = ty * ty * (3 - 2 * ty)
    a = _hash01(seed, x0, y0, 1)
    b = _hash01(seed, x0 + 1, y0, 1)
    c = _hash01(seed, x0, y0 + 1, 1)
    d = _hash01(seed, x0 + 1, y0 + 1, 1)
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty


class GameMap:
    """Endless outdoor forest: authored grid (cabin, river, ponds) + streamed tree/plant chunks."""

    def __init__(self, chapter_num=1):
        self.width = MAP_SIZE      # size of the authored grid, NOT the size of the world
        self.height = MAP_SIZE
        self.grid = [[EMPTY for _ in range(self.width)] for _ in range(self.height)]
        self._chunks = {}
        self.protected = []        # (x, y) points that must never be covered by a tree
        self.pickups = []
        self.enemies = []
        self.checkpoints = []
        self.exit_pos = (58.5, 58.5)
        self.player_start = (4.5, 4.5)
        self.player_start_angle = 0.785
        self.chapter_num = chapter_num
        self.max_chapters = 2
        self.seed = 42 + chapter_num
        self.validation_errors = []
        self.load_chapter(chapter_num)

    # ─── Level construction ──────────────────────────────────────────────
    def load_chapter(self, chapter_num):
        self.chapter_num = chapter_num
        self.seed = 42 + chapter_num
        self.validation_errors = []
        self.checkpoints = []
        self._chunks = {}
        self.protected = []

        # Authored area: open ground + cabin. No boundary wall - the world is endless.
        for y in range(self.height):
            for x in range(self.width):
                self.grid[y][x] = EMPTY

        for y in range(28, 38):
            for x in range(28, 38):
                if (x == 32 or x == 33) and y == 37:
                    self.grid[y][x] = DOOR
                elif x == 28 or x == 37 or y == 28 or y == 37:
                    self.grid[y][x] = WALL_WOOD

        for y in range(2, self.height - 2):
            fx = int(25.0 + 12.0 * math.sin(y * 0.12) + 6.0 * math.cos(y * 0.05))
            fx = max(3, min(self.width - 4, fx))
            for dx in range(-1, 2):
                nx = fx + dx
                if 0 < nx < self.width - 1:
                    self.grid[y][nx] = WATER

        if chapter_num == 2:
            pond_centers = [(15, 15), (48, 48), (20, 50)]
            for (px, py) in pond_centers:
                for dy in range(-4, 5):
                    for dx in range(-4, 5):
                        nx, ny = px + dx, py + dy
                        if 1 <= nx < self.width - 1 and 1 <= ny < self.height - 1:
                            if dx * dx + dy * dy <= 16:
                                self.grid[ny][nx] = WATER

        self.player_start = (4.5, 4.5)
        self.player_start_angle = 0.785
        if chapter_num == 1:
            self._place_chapter1_entities()
        else:
            self._place_chapter2_entities()

        self._validate_and_fix_reachability()

        # Trees are generated lazily; make sure the area around the start exists up front
        self.update_streaming(*self.player_start)

    def _place_chapter1_entities(self):
        self.pickups = [
            {'type': 'ammo_shotgun', 'x': 8.5, 'y': 8.5, 'amount': 6, 'active': True},
            {'type': 'ammo_revolver', 'x': 20.5, 'y': 10.5, 'amount': 6, 'active': True},
            {'type': 'health', 'x': 15.5, 'y': 15.5, 'amount': 25, 'active': True},
            {'type': 'battery', 'x': 18.5, 'y': 16.5, 'amount': 30, 'active': True},
            {'type': 'salt', 'x': 32.5, 'y': 25.5, 'amount': 3, 'active': True},
            {'type': 'faith', 'x': 14.5, 'y': 20.5, 'amount': 20, 'active': True},
            {'type': 'ammo_shotgun', 'x': 40.5, 'y': 30.5, 'amount': 4, 'active': True},
            {'type': 'health', 'x': 10.5, 'y': 35.5, 'amount': 20, 'active': True},
            {'type': 'garlic', 'x': 16.5, 'y': 32.5, 'amount': 2, 'active': True},
            {'type': 'bible_page', 'x': 33.5, 'y': 33.5, 'amount': 1, 'active': True},
            {'type': 'ammo_revolver', 'x': 45.5, 'y': 45.5, 'amount': 6, 'active': True},
            {'type': 'health', 'x': 50.5, 'y': 50.5, 'amount': 25, 'active': True},
            {'type': 'salt', 'x': 8.5, 'y': 4.8, 'amount': 2, 'active': True},
            {'type': 'battery', 'x': 11.5, 'y': 3.6, 'amount': 30, 'active': True},
            {'type': 'faith', 'x': 9.5, 'y': 6.0, 'amount': 20, 'active': True},
        ]
        self.enemies = [
            {'type': 'aswang', 'x': 17.5, 'y': 6.0},
            {'type': 'multo', 'x': 15.5, 'y': 40.5},
            {'type': 'aswang', 'x': 45.5, 'y': 25.5},
            {'type': 'sigbin', 'x': 25.5, 'y': 50.5},
            {'type': 'white_lady', 'x': 36.5, 'y': 44.5},
        ]
        self.checkpoints.append({'x': 32.5, 'y': 32.5})
        self.exit_pos = (58.5, 58.5)

    def _place_chapter2_entities(self):
        self.pickups = [
            {'type': 'ammo_shotgun', 'x': 10.5, 'y': 8.5, 'amount': 6, 'active': True},
            {'type': 'health', 'x': 25.5, 'y': 15.5, 'amount': 30, 'active': True},
            {'type': 'salt', 'x': 35.5, 'y': 10.5, 'amount': 3, 'active': True},
            {'type': 'garlic', 'x': 45.5, 'y': 8.5, 'amount': 3, 'active': True},
            {'type': 'faith', 'x': 33.5, 'y': 33.5, 'amount': 25, 'active': True},
            {'type': 'battery', 'x': 18.5, 'y': 25.5, 'amount': 40, 'active': True},
            {'type': 'ammo_revolver', 'x': 50.5, 'y': 20.5, 'amount': 6, 'active': True},
            {'type': 'bible_page', 'x': 32.5, 'y': 32.5, 'amount': 1, 'active': True},
            {'type': 'health', 'x': 55.5, 'y': 45.5, 'amount': 25, 'active': True},
        ]
        self.enemies = [
            {'type': 'aswang', 'x': 20.5, 'y': 15.5},
            {'type': 'aswang', 'x': 45.5, 'y': 12.5},
            {'type': 'manananggal', 'x': 40.5, 'y': 30.5},
            {'type': 'multo', 'x': 15.5, 'y': 35.5},
            {'type': 'sigbin', 'x': 52.5, 'y': 40.5},
            {'type': 'tikbalang', 'x': 32.5, 'y': 45.5},
            {'type': 'kapre', 'x': 30.5, 'y': 20.5},
        ]
        self.checkpoints.append({'x': 32.5, 'y': 32.5})
        self.exit_pos = (58.5, 58.5)

    # ─── Endless tree / undergrowth streaming ────────────────────────────
    def _tree_types(self):
        if self.chapter_num == 2:
            return ['balete', 'bamboo', 'mahogany', 'dead', 'banana', 'palm']
        return ['balete', 'bamboo', 'mahogany', 'dead']

    def _spot_free_of_features(self, x, y):
        """True if (x, y) is not in water, the cabin zone or the start clearing."""
        if self.get_tile(x, y) == WATER:
            return False
        if 27 <= x <= 38 and 27 <= y <= 38:
            return False
        if math.hypot(x - self.player_start[0], y - self.player_start[1]) < 5.0:
            return False
        return True

    def _generate_chunk(self, cx, cy):
        """Build the trees and plants of one chunk. Pure function of (seed, cx, cy, protected)."""
        S = CHUNK_SIZE
        rng = random.Random(_hash_int(self.seed, cx, cy, 7))
        cells = max(1, int(round(S / TREE_CELL)))
        cs = S / cells
        margin = 0.55
        types = self._tree_types()
        trees = []

        for i in range(cells):
            for j in range(cells):
                ox = cx * S + i * cs
                oy = cy * S + j * cs
                # Always draw the same numbers so the chunk is stable no matter what is filtered
                r_keep = rng.random()
                r_jx = rng.random()
                r_jy = rng.random()
                r_type = rng.random()
                r_scale = rng.random()
                r_tint = rng.random()

                density = TREE_DENSITY_MIN + (TREE_DENSITY_MAX - TREE_DENSITY_MIN) * \
                    _value_noise(self.seed, ox, oy, 14.0)
                if r_keep > density:
                    continue
                x = ox + margin + r_jx * (cs - 2 * margin)
                y = oy + margin + r_jy * (cs - 2 * margin)
                if not self._spot_free_of_features(x, y):
                    continue
                scale = 0.7 + r_scale * 0.8
                radius = 0.25 * scale + 0.15
                blocked = False
                for (px, py) in self.protected:
                    if abs(px - x) < 2.0 and abs(py - y) < 2.0 and math.hypot(px - x, py - y) < radius + 0.5:
                        blocked = True
                        break
                if blocked:
                    continue
                trees.append({
                    'x': x, 'y': y, 'type': types[int(r_type * len(types)) % len(types)],
                    'scale': scale, 'tint': 200 + int(r_tint * 55), 'radius': radius,
                })

        plants = []
        prng = random.Random(_hash_int(self.seed, cx, cy, 99))
        plant_types = ['fern', 'mushroom', 'rock', 'bush', 'log', 'stump', 'boulder', 'sapling']
        for t in trees:
            r_has = prng.random()
            ang = prng.uniform(0, math.pi * 2)
            dist = prng.uniform(0.6, 1.4)
            p_type = prng.choice(plant_types)
            p_scale = prng.uniform(0.6, 1.3)
            p_tint = prng.randint(180, 255)
            if r_has > UNDERGROWTH_PER_TREE:
                continue
            px = t['x'] + math.cos(ang) * dist
            py = t['y'] + math.sin(ang) * dist
            if not self._spot_free_of_features(px, py):
                continue
            plants.append({'x': px, 'y': py, 'type': p_type, 'scale': p_scale, 'tint': p_tint})

        return {'trees': trees, 'plants': plants}

    def _get_chunk(self, cx, cy):
        key = (cx, cy)
        chunk = self._chunks.get(key)
        if chunk is None:
            chunk = self._generate_chunk(cx, cy)
            self._chunks[key] = chunk
        return chunk

    def update_streaming(self, px, py):
        """Generate chunks around (px, py) and drop chunks that are far away."""
        pcx, pcy = int(math.floor(px / CHUNK_SIZE)), int(math.floor(py / CHUNK_SIZE))
        r = CHUNK_LOAD_RADIUS
        for cx in range(pcx - r, pcx + r + 1):
            for cy in range(pcy - r, pcy + r + 1):
                self._get_chunk(cx, cy)
        keep = CHUNK_KEEP_RADIUS
        if len(self._chunks) > (2 * keep + 1) ** 2:
            for key in [k for k in self._chunks if abs(k[0] - pcx) > keep or abs(k[1] - pcy) > keep]:
                del self._chunks[key]

    def _chunks_in_range(self, x0, y0, x1, y1):
        S = CHUNK_SIZE
        for cx in range(int(math.floor(x0 / S)), int(math.floor(x1 / S)) + 1):
            for cy in range(int(math.floor(y0 / S)), int(math.floor(y1 / S)) + 1):
                yield self._get_chunk(cx, cy)

    def _items_near(self, kind, x, y, max_dist):
        out = []
        m2 = max_dist * max_dist
        for chunk in self._chunks_in_range(x - max_dist, y - max_dist, x + max_dist, y + max_dist):
            for it in chunk[kind]:
                dx = it['x'] - x
                dy = it['y'] - y
                if dx * dx + dy * dy <= m2:
                    out.append(it)
        return out

    def trees_near(self, x, y, max_dist):
        return self._items_near('trees', x, y, max_dist)

    def plants_near(self, x, y, max_dist):
        return self._items_near('plants', x, y, max_dist)

    @property
    def trees(self):
        """All currently loaded trees (compat / debugging)."""
        return [t for c in self._chunks.values() for t in c['trees']]

    @property
    def undergrowth(self):
        return [p for c in self._chunks.values() for p in c['plants']]

    @property
    def tree_count(self):
        return sum(len(c['trees']) for c in self._chunks.values())

    # ─── Validation ──────────────────────────────────────────────────────
    def _validate_and_fix_reachability(self):
        all_targets = [(e['x'], e['y'], 'enemy', e) for e in self.enemies] + \
                      [(p['x'], p['y'], 'pickup', p) for p in self.pickups] + \
                      [(c['x'], c['y'], 'checkpoint', c) for c in self.checkpoints] + \
                      [(self.exit_pos[0], self.exit_pos[1], 'exit', None)]

        # Entities standing in water are nudged out (same rule as before)
        for (x, y, kind, obj) in all_targets:
            if kind in ('pickup', 'enemy') and self.get_tile(x, y) == WATER:
                obj['x'] += 1.0

        # Flood-fill from the player start over the authored grid; relocate or flag anything unreachable
        reachable = self._reachable_cells()
        for (x, y, kind, obj) in all_targets:
            if kind == 'checkpoint' or (int(x), int(y)) in reachable:
                continue
            if obj is not None:
                spot = self._nearest_reachable(x, y, reachable)
                if spot:
                    obj['x'], obj['y'] = spot
                    continue
            self.validation_errors.append(f"{kind} at ({x:.1f},{y:.1f}) is unreachable")

        # Trees never grow on top of entities: protect their final positions, then regenerate lazily
        self.protected = [(e['x'], e['y']) for e in self.enemies] + \
                         [(p['x'], p['y']) for p in self.pickups] + \
                         [(c['x'], c['y']) for c in self.checkpoints] + \
                         [self.exit_pos]
        self._chunks = {}

    def _reachable_cells(self):
        """Cells of the authored grid reachable from the player start.
        Closed doors count as passable (they can be opened)."""
        sx, sy = int(self.player_start[0]), int(self.player_start[1])
        seen = {(sx, sy)}
        stack = [(sx, sy)]
        while stack:
            cx, cy = stack.pop()
            for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if (nx, ny) in seen or not (0 <= nx < self.width and 0 <= ny < self.height):
                    continue
                if self.grid[ny][nx] in (EMPTY, DOOR, WATER):
                    seen.add((nx, ny))
                    stack.append((nx, ny))
        return seen

    def _nearest_reachable(self, x, y, reachable, max_r=6):
        for r in range(1, max_r + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    cx, cy = int(x) + dx, int(y) + dy
                    if (cx, cy) in reachable and self.grid[cy][cx] == EMPTY:
                        return (cx + 0.5, cy + 0.5)
        return None

    # ─── Queries ─────────────────────────────────────────────────────────
    def is_tree_solid(self, x, y, radius=0.3):
        reach = radius + 0.6          # largest tree radius is ~0.53
        for chunk in self._chunks_in_range(x - reach, y - reach, x + reach, y + reach):
            for t in chunk['trees']:
                dx = t['x'] - x
                if dx > reach or dx < -reach:
                    continue
                lim = t['radius'] + radius
                if dx * dx + (t['y'] - y) ** 2 < lim * lim:
                    return True
        return False

    def get_tile(self, x, y):
        """Tile at a world position. Outside the authored grid the world is open ground."""
        ix, iy = int(math.floor(x)), int(math.floor(y))
        if 0 <= ix < self.width and 0 <= iy < self.height:
            return self.grid[iy][ix]
        return EMPTY

    def is_wall(self, x, y):
        return self.get_tile(x, y) != EMPTY

    def is_solid(self, x, y, doors_block=True):
        """True if (x, y) blocks movement. Closed doors block unless doors_block=False;
        opened doors become EMPTY tiles and are always passable."""
        tile = self.get_tile(x, y)
        if tile == DOOR:
            return doors_block
        if tile != EMPTY and tile != WATER:
            return True
        return self.is_tree_solid(x, y, radius=0.25)

    def open_door(self, x, y):
        ix, iy = int(math.floor(x)), int(math.floor(y))
        if 0 <= ix < self.width and 0 <= iy < self.height:
            if self.grid[iy][ix] == DOOR:
                self.grid[iy][ix] = EMPTY
                return True
        return False

    def get_nearby_pickups(self, px, py, radius=0.6):
        result = []
        for pickup in self.pickups:
            if not pickup['active']:
                continue
            dx = pickup['x'] - px
            dy = pickup['y'] - py
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < radius:
                result.append(pickup)
        return result
