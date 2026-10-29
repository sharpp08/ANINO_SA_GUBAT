"""
Map system - defines levels, handles advanced procedural forest generation, spatial hashing, reachability validation, and tile queries.
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
        """Return all objects whose stored radius overlaps the query circle.

        insert() spreads each object into a 3×3 cell neighbourhood so that a
        single-cell lookup here is sufficient — the inserter already ensured
        every neighbouring cell carries the object.  But if the query circle
        straddles a cell boundary we must also check that boundary's neighbour.
        We therefore scan the 3×3 neighbourhood of the query point, using a
        seen-set to avoid returning duplicates.
        """
        cx, cy = int(x // self.cell_size), int(y // self.cell_size)
        results = []
        seen_ids: set = set()
        for ddx in (-1, 0, 1):
            for ddy in (-1, 0, 1):
                key = (cx + ddx, cy + ddy)
                if key not in self.cells:
                    continue
                for item in self.cells[key]:
                    obj, ox, oy, orad = item
                    oid = id(obj)
                    if oid in seen_ids:
                        continue
                    if math.hypot(ox - x, oy - y) < (orad + radius):
                        seen_ids.add(oid)
                        results.append(obj)
        return results


class GameMap:
    """Outdoor forest map system with advanced biomes, trails, stream, ponds, ruins, spatial hashing, and reachability validation."""

    def __init__(self, chapter_num=1):
        self.width = MAP_SIZE
        self.height = MAP_SIZE
        self.grid = [[EMPTY for _ in range(self.width)] for _ in range(self.height)]
        self.trees = []
        self.undergrowth = []
        self.pickups = []
        self.enemies = []
        self.checkpoints = []
        self.exit_pos = (58.5, 58.5)
        self.player_start = (4.5, 4.5)
        self.player_start_angle = 0.785
        self.chapter_num = chapter_num
        self.max_chapters = 2
        self.validation_errors = []
        self.spatial_hash = SpatialHash(cell_size=3.0)
        self.load_chapter(chapter_num)

    def load_chapter(self, chapter_num):
        self.chapter_num = chapter_num
        self.validation_errors = []
        self.checkpoints = []

        # Open forest world (no stone perimeter walls)
        self.grid = [[EMPTY for _ in range(self.width)] for _ in range(self.height)]

        # Central ruins at world center
        cs = self.width // 2
        for y in range(cs - 5, cs + 6):
            for x in range(cs - 5, cs + 6):
                if (x == cs or x == cs + 1) and y == cs + 5:
                    self.grid[y][x] = DOOR
                elif x == cs - 5 or x == cs + 5 or y == cs - 5 or y == cs + 5:
                    self.grid[y][x] = WALL_WOOD

        seed_val = 42 + chapter_num
        rng_map = random.Random(seed_val)
        np.random.seed(seed_val)

        density_noise = np.random.rand(self.height, self.width)

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
                            if dx*dx + dy*dy <= 16:
                                self.grid[ny][nx] = WATER

        self.trees = []
        # Species mix per chapter.  Chapter 2 adds tropical broadleaf species.
        tree_types = ['balete', 'bamboo', 'mahogany', 'dead', 'banana', 'palm'] if chapter_num == 2 else ['balete', 'bamboo', 'mahogany', 'dead']
        count = TREE_COUNT_CH1 if chapter_num == 1 else TREE_COUNT_CH2

        while len(self.trees) < count:
            tx = rng_map.uniform(3.0, float(self.width - 3))
            ty = rng_map.uniform(3.0, float(self.height - 3))
            
            if math.hypot(tx - 4.5, ty - 4.5) < 5.0:
                continue
            if 27 <= tx <= 38 and 27 <= ty <= 38:
                continue
            if self.grid[int(ty)][int(tx)] == WATER:
                continue

            d_val = density_noise[int(ty) % self.height, int(tx) % self.width]
            # Dense groves allow trees closer together; clearings force wider gaps.
            min_dist = 1.2 if d_val > 0.7 else 2.4

            too_close = False
            for t in self.trees:
                if math.hypot(t['x'] - tx, t['y'] - ty) < min_dist:
                    too_close = True
                    break
            if not too_close:
                t_type = rng_map.choice(tree_types)
                # Scale varies by species: canopy trees are tall, saplings small.
                # Dead and balete can be very large; bamboo is slender and tall.
                if t_type in ('balete', 'mahogany'):
                    scale = rng_map.uniform(0.9, 1.8)
                elif t_type == 'dead':
                    scale = rng_map.uniform(0.8, 1.6)
                elif t_type == 'bamboo':
                    scale = rng_map.uniform(0.8, 1.4)
                else:
                    scale = rng_map.uniform(0.6, 1.3)
                # Collision radius corresponds to the visible trunk only.
                # Trunk width is a fraction of scale; roots add a small margin.
                trunk_fraction = 0.18 if t_type == 'bamboo' else 0.22
                radius = max(0.18, scale * trunk_fraction + 0.08)
                # Store a canopy seed for deterministic per-tree visual variation
                canopy_seed = rng_map.randint(0, 99999)
                self.trees.append({
                    'x': tx, 'y': ty, 'type': t_type,
                    'scale': scale, 'tint': rng_map.randint(200, 255),
                    'radius': radius,
                    'canopy_seed': canopy_seed,
                    'lean': rng_map.uniform(-0.08, 0.08),  # trunk lean angle
                })

        self.spatial_hash.clear()
        for t in self.trees:
            self.spatial_hash.insert(t, t['x'], t['y'], t['radius'])

        self.undergrowth = []
        plant_types = ['fern', 'mushroom', 'rock', 'bush', 'log', 'stump', 'boulder', 'sapling']
        p_count = UNDERGROWTH_DENSITY
        while len(self.undergrowth) < p_count:
            px = rng_map.uniform(2.0, float(self.width - 2))
            py = rng_map.uniform(2.0, float(self.height - 2))
            if math.hypot(px - 4.5, py - 4.5) < 3.0:
                continue
            if 27 <= px <= 38 and 27 <= py <= 38:
                continue
            if self.grid[int(py)][int(px)] == WATER:
                continue

            near_trees = self.spatial_hash.query(px, py, radius=0.4)
            if near_trees:
                p_type = rng_map.choice(plant_types)
                self.undergrowth.append({
                    'x': px, 'y': py, 'type': p_type,
                    'scale': rng_map.uniform(0.6, 1.3),
                    'tint': rng_map.randint(180, 255)
                })

        if chapter_num == 1:
            self.player_start = (4.5, 4.5)
            self.player_start_angle = 0.785
            self._place_chapter1_entities()
        else:
            self.player_start = (4.5, 4.5)
            self.player_start_angle = 0.785
            self._place_chapter2_entities()

        self._validate_and_fix_reachability()

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

    def _validate_and_fix_reachability(self):
        cleared_trees = 0
        all_targets = [(e['x'], e['y'], 'enemy', e) for e in self.enemies] + \
                      [(p['x'], p['y'], 'pickup', p) for p in self.pickups] + \
                      [(c['x'], c['y'], 'checkpoint', c) for c in self.checkpoints] + \
                      [(self.exit_pos[0], self.exit_pos[1], 'exit', None)]

        # Use PLAYER_SIZE as the clearance radius so validation matches the
        # actual is_solid() checks.  The old 0.2 value was too loose: with
        # denser trees some pickups/enemies sat just outside the validation
        # threshold but inside the real collision radius.
        CLEAR_RADIUS = PLAYER_SIZE

        for (x, y, kind, obj) in all_targets:
            while self.is_tree_solid(x, y, radius=CLEAR_RADIUS):
                for t in list(self.trees):
                    if math.hypot(t['x'] - x, t['y'] - y) < (t['radius'] + CLEAR_RADIUS):
                        self.trees.remove(t)
                        cleared_trees += 1
                self.spatial_hash.clear()
                for t in self.trees:
                    self.spatial_hash.insert(t, t['x'], t['y'], t['radius'])

            ix, iy = int(x), int(y)
            if 0 <= ix < self.width and 0 <= iy < self.height:
                if self.grid[iy][ix] == WATER:
                    if kind == 'pickup':
                        obj['x'] += 1.0
                    elif kind == 'enemy':
                        obj['x'] += 1.0

        if cleared_trees > 0:
            print(f"[MAP] chapter {self.chapter_num}: removed {cleared_trees} tree(s) blocking entities/exit")

        # Flood-fill from the player start; relocate or flag anything that cannot be reached
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

    def _reachable_cells(self):
        """Cells reachable from the player start. Closed doors count as passable (they can be opened)."""
        sx, sy = int(self.player_start[0]), int(self.player_start[1])
        seen = {(sx, sy)}
        stack = [(sx, sy)]
        while stack:
            cx, cy = stack.pop()
            for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if (nx, ny) in seen or not (0 < nx < self.width - 1 and 0 < ny < self.height - 1):
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
                    if (cx, cy) in reachable and self.grid[cy][cx] == EMPTY \
                            and not self.is_tree_solid(cx + 0.5, cy + 0.5, radius=PLAYER_SIZE):
                        return (cx + 0.5, cy + 0.5)
        return None

    def is_tree_solid(self, x, y, radius=0.3):
        nearby = self.spatial_hash.query(x, y, radius=radius)
        for t in nearby:
            if math.hypot(t['x'] - x, t['y'] - y) < (t['radius'] + radius):
                return True
        return False

    def resolve_circle_collision(self, x, y, radius):
        """Push a circle out of every overlapping tree trunk.

        Returns the corrected (x, y).  Each tree is treated as a circle of
        ``t['radius']`` centred at ``(t['x'], t['y'])``; the player circle has
        ``radius``.  When the two overlap we push the player along the
        centre-to-centre vector by exactly the penetration depth, which lets
        the player slide smoothly along the trunk because the tangential
        component of movement is never cancelled — only the normal (radial)
        component is corrected.  A small margin prevents jitter while keeping
        the player close enough to feel the trunk.
        """
        margin = 0.02
        for _ in range(2):  # two passes handle the common 2-tree squeeze
            nearby = self.spatial_hash.query(x, y, radius=radius + margin)
            pushed = False
            for t in nearby:
                dx = x - t['x']
                dy = y - t['y']
                dist = math.hypot(dx, dy)
                min_dist = t['radius'] + radius + margin
                if dist < min_dist:
                    if dist < 1e-5:
                        # perfectly overlapping centre — nudge along +X
                        x += min_dist
                        pushed = True
                        continue
                    overlap = min_dist - dist
                    x += (dx / dist) * overlap
                    y += (dy / dist) * overlap
                    pushed = True
            if not pushed:
                break
        return x, y

    def is_wall(self, x, y):
        ix, iy = int(x), int(y)
        if ix < 0 or ix >= self.width or iy < 0 or iy >= self.height:
            return True
        return self.grid[iy][ix] != EMPTY

    def is_solid(self, x, y, doors_block=True):
        """True if (x, y) blocks movement. Closed doors block unless doors_block=False;
        opened doors become EMPTY tiles and are always passable."""
        ix, iy = int(x), int(y)
        if ix < 0 or ix >= self.width or iy < 0 or iy >= self.height:
            return True
        tile = self.grid[iy][ix]
        if tile == DOOR:
            return doors_block
        if tile != EMPTY and tile != WATER:
            return True
        return self.is_tree_solid(x, y, radius=0.25)

    def is_water(self, x, y):
        """Check if the given world position is on a water tile."""
        ix, iy = int(x), int(y)
        if 0 <= ix < self.width and 0 <= iy < self.height:
            return self.grid[iy][ix] == WATER
        return False

    def get_tile(self, x, y):
        ix, iy = int(x), int(y)
        if ix < 0 or ix >= self.width or iy < 0 or iy >= self.height:
            return WALL_STONE
        return self.grid[iy][ix]

    def open_door(self, x, y):
        ix, iy = int(x), int(y)
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
