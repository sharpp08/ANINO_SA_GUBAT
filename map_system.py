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


class ProceduralWorldEngine:
    """Minecraft-style infinite chunk-based procedural world engine for ANINO SA GUBAT.
    Generates deterministic chunks based on world seed, elevation noise, biomes,
    trees, undergrowth, and landmarks.
    """
    def __init__(self, world_seed=1337, chunk_size=32):
        self.world_seed = world_seed
        self.chunk_size = chunk_size
        self.chunks = {}  # (cx, cy) -> Chunk data

    def set_seed(self, seed):
        self.world_seed = seed
        self.chunks.clear()

    def get_chunk(self, cx, cy):
        key = (cx, cy)
        if key in self.chunks:
            return self.chunks[key]
        
        # Generate chunk deterministically
        chunk = self._generate_chunk(cx, cy)
        self.chunks[key] = chunk
        return chunk

    def _generate_chunk(self, cx, cy):
        # Deterministic RNG for chunk based on world seed and chunk coords
        chunk_seed = self.world_seed ^ (cx * 73856093) ^ (cy * 19349663)
        rng = random.Random(chunk_seed)
        np_rng = np.random.RandomState(chunk_seed & 0xFFFFFFFF)

        trees = []
        undergrowth = []
        tiles = [[EMPTY for _ in range(self.chunk_size)] for _ in range(self.chunk_size)]

        # Biome determination based on chunk position noise
        biome_val = math.sin(cx * 0.3) * math.cos(cy * 0.3)
        if biome_val < -0.4:
            biome = 'dead_forest'
            tree_weights = {'dead': 50, 'balete': 15, 'strangler': 15, 'bamboo': 20}
        elif biome_val < -0.1:
            biome = 'swamp'
            tree_weights = {'balete': 40, 'tree_fern': 30, 'dead': 20, 'bamboo': 10}
        elif biome_val < 0.2:
            biome = 'pine_forest'
            tree_weights = {'bamboo': 45, 'mahogany': 25, 'akasya': 20, 'dead': 10}
        elif biome_val < 0.5:
            biome = 'ancient_grove'
            tree_weights = {'balete': 50, 'mahogany': 30, 'supernatural': 10, 'narra': 10}
        else:
            biome = 'clearing'
            tree_weights = {'akasya': 40, 'narra': 30, 'banana': 20, 'palm': 10}

        # Generate rivers/water in swamp or low elevation
        if biome == 'swamp' or (cx + cy) % 7 == 0:
            stream_y = rng.randint(5, self.chunk_size - 6)
            for x in range(self.chunk_size):
                for dy in (-1, 0, 1):
                    ny = stream_y + dy
                    if 0 <= ny < self.chunk_size:
                        tiles[ny][x] = WATER

        tree_types = list(tree_weights.keys())
        weights = list(tree_weights.values())

        # Extreme Tree Population Density per chunk based on biome
        if biome == 'ancient_grove':
            tree_count = rng.randint(45, 65)
        elif biome in ('dense_forest', 'pine_forest'):
            tree_count = rng.randint(35, 55)
        elif biome == 'dead_forest':
            tree_count = rng.randint(25, 40)
        elif biome == 'swamp':
            tree_count = rng.randint(20, 35)
        else:
            tree_count = rng.randint(8, 18)

        for _ in range(tree_count):
            local_x = rng.uniform(2.0, float(self.chunk_size - 2))
            local_y = rng.uniform(2.0, float(self.chunk_size - 2))
            world_x = cx * self.chunk_size + local_x
            world_y = cy * self.chunk_size + local_y

            if tiles[int(local_y)][int(local_x)] == WATER:
                continue

            t_type = rng.choices(tree_types, weights=weights, k=1)[0]
            scale = rng.uniform(0.7, 1.8) if biome != 'ancient_grove' else rng.uniform(1.4, 2.3)
            trunk_fraction = 0.18 if t_type in ('bamboo', 'tree_fern', 'banana', 'palm') else 0.22
            radius = max(0.18, scale * trunk_fraction + 0.08)

            trees.append({
                'x': world_x, 'y': world_y, 'type': t_type,
                'scale': scale, 'tint': rng.randint(180, 255),
                'radius': radius, 'canopy_seed': rng.randint(0, 99999),
                'lean': rng.uniform(-0.08, 0.08), 'biome': biome
            })

        # Undergrowth generation
        plant_types = ['fern', 'mushroom', 'rock', 'bush', 'log', 'stump', 'boulder', 'sapling']
        plant_count = rng.randint(10, 25)
        for _ in range(plant_count):
            local_x = rng.uniform(1.0, float(self.chunk_size - 1))
            local_y = rng.uniform(1.0, float(self.chunk_size - 1))
            world_x = cx * self.chunk_size + local_x
            world_y = cy * self.chunk_size + local_y

            if tiles[int(local_y)][int(local_x)] == WATER:
                continue

            p_type = rng.choice(plant_types)
            undergrowth.append({
                'x': world_x, 'y': world_y, 'type': p_type,
                'scale': rng.uniform(0.6, 1.3), 'tint': rng.randint(170, 255)
            })

        return {
            'cx': cx, 'cy': cy, 'biome': biome,
            'tiles': tiles, 'trees': trees, 'undergrowth': undergrowth
        }

    def update_world_chunks(self, player_x, player_y, game_map):
        """Dynamically load and populate chunks around the player for infinite exploration."""
        p_cx = int(player_x // self.chunk_size)
        p_cy = int(player_y // self.chunk_size)
        
        # Load chunks within CHUNK_LOAD_RADIUS
        needed_chunks = set()
        for dcx in range(-CHUNK_LOAD_RADIUS, CHUNK_LOAD_RADIUS + 1):
            for dcy in range(-CHUNK_LOAD_RADIUS, CHUNK_LOAD_RADIUS + 1):
                needed_chunks.add((p_cx + dcx, p_cy + dcy))

        # Check if surrounding trees need update
        current_loaded_keys = set(self.loaded_chunk_keys) if hasattr(self, 'loaded_chunk_keys') else set()
        if needed_chunks != current_loaded_keys:
            self.loaded_chunk_keys = needed_chunks
            game_map.trees = []
            game_map.undergrowth = []
            
            for (cx, cy) in needed_chunks:
                chunk = self.get_chunk(cx, cy)
                game_map.trees.extend(chunk['trees'])
                game_map.undergrowth.extend(chunk['undergrowth'])

            # Preserve the perimeter tree-line (invisible wall) across
            # chunk rebuilds so the border never disappears.
            if hasattr(game_map, '_edge_ring'):
                game_map.trees.extend(game_map._edge_ring)

            # Rebuild spatial hash for efficient O(1) collision queries
            game_map.spatial_hash.clear()
            for t in game_map.trees:
                game_map.spatial_hash.insert(t, t['x'], t['y'], t['radius'])



class GameMap:
    """Outdoor forest map system with advanced biomes, trails, stream, ponds, ruins, spatial hashing, and reachability validation."""

    def __init__(self, chapter_num=1):
        self.width = MAP_WIDTH
        self.height = MAP_HEIGHT
        self.grid = [[EMPTY for _ in range(self.width)] for _ in range(self.height)]
        # Minecraft-style procedural world engine instance
        self.world_engine = ProceduralWorldEngine(world_seed=ACTIVE_WORLD_SEED, chunk_size=CHUNK_SIZE)

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
        cs_x, cs_y = self.width // 2, self.height // 2
        for y in range(cs_y - 5, cs_y + 6):
            for x in range(cs_x - 5, cs_x + 6):
                if (x == cs_x or x == cs_x + 1) and y == cs_y + 5:
                    self.grid[y][x] = DOOR
                elif x == cs_x - 5 or x == cs_x + 5 or y == cs_y - 5 or y == cs_y + 5:
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
        if chapter_num == 2:
            tree_types = ['balete', 'mahogany', 'bamboo', 'dead', 'banana', 'palm', 'akasya', 'narra', 'tree_fern', 'strangler', 'supernatural']
            weights    = [14,       14,         9,        8,      8,        8,     11,       9,         9,           8,           2]
        else:
            tree_types = ['balete', 'mahogany', 'bamboo', 'dead', 'akasya', 'narra', 'tree_fern', 'supernatural']
            weights    = [18,       18,         14,       10,     14,       10,      13,          3]
        count = TREE_COUNT_CH1 if chapter_num == 1 else TREE_COUNT_CH2

        grid_step = max(2.2, math.sqrt((self.width * self.height) / max(1, count)))
        for gy in range(2, self.height - 2, int(grid_step)):
            for gx in range(2, self.width - 2, int(grid_step)):
                if len(self.trees) >= count:
                    break
                tx = gx + rng_map.uniform(0.1, grid_step - 0.1)
                ty = gy + rng_map.uniform(0.1, grid_step - 0.1)
                if math.hypot(tx - 4.5, ty - 4.5) < 6.0:
                    continue
                if cs_x - 10 <= tx <= cs_x + 10 and cs_y - 10 <= ty <= cs_y + 10:
                    continue
                if self.grid[int(ty)][int(tx)] == WATER:
                    continue

                t_type = rng_map.choices(tree_types, weights=weights, k=1)[0]
                layer_roll = rng_map.random()
                if layer_roll < 0.45:
                    scale = rng_map.uniform(1.2, 1.8)
                elif layer_roll < 0.80:
                    scale = rng_map.uniform(0.7, 1.1)
                else:
                    scale = rng_map.uniform(0.4, 0.7)

                trunk_fraction = 0.18 if t_type in ('bamboo', 'tree_fern', 'banana', 'palm') else 0.22
                radius = max(0.18, scale * trunk_fraction + 0.08)
                canopy_seed = rng_map.randint(0, 99999)
                self.trees.append({
                    'x': tx, 'y': ty, 'type': t_type,
                    'scale': scale, 'tint': rng_map.randint(200, 255),
                    'radius': radius,
                    'canopy_seed': canopy_seed,
                    'lean': rng_map.uniform(-0.08, 0.08),
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
            if cs_x - 8 <= px <= cs_x + 8 and cs_y - 8 <= py <= cs_y + 8:
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

        # Dense forest tree-line boundary on ALL FOUR edges (invisible wall)
        self._spawn_edge_ring(rng_map)
        # Keep the ring in self.trees so the renderer sees it and chunk
        # rebuilds (update_world_chunks) preserve it.
        self.trees.extend(self._edge_ring)
        self.spatial_hash.clear()
        for t in self.trees:
            self.spatial_hash.insert(t, t['x'], t['y'], t['radius'])

        if chapter_num == 1:
            self.player_start = (4.5, 4.5)
            self.player_start_angle = 0.785
            self._place_chapter1_entities()
        else:
            self.player_start = (4.5, 4.5)
            self.player_start_angle = 0.785
            self._place_chapter2_entities()

        self._validate_and_fix_reachability()

    def _spawn_edge_ring(self, rng_map):
        """Dense full-perimeter tree line: the forest acts as an invisible wall.

        Three staggered tiers per side plus reinforced corners:
          * margin 1.5  — outer "wall" tier: oversized balete trunks, 1.0
            spacing, 95% fill.  Trunk radius 0.48–0.61, so two neighbours'
            collider circles (sum ≥ 0.96 + player diameter 0.6 = 1.56
            guaranteed block) span every gap in the row (max gap 1.3):
            the outer tier alone mathematically blocks the player.
          * margin 3.0  — mid tier: mixed species, 1.0 spacing, 85% fill.
          * margin 4.5  — inner tier: smaller trunks, 1.2 spacing, 75%
            fill, backfilling visual gaps so the wall reads as a natural
            forest edge rather than a row of hedges.
        Left/right edges are ringed the same as top/bottom, closing the
        previously open world borders.
        """
        self._edge_ring = []
        w, h = self.width, self.height
        mix_types = ['balete', 'mahogany', 'akasya', 'banana', 'bamboo', 'dead']
        mix_weights = [30, 22, 18, 12, 10, 8]

        def add_tree(x, y, t_type, scale):
            trunk_fraction = 0.18 if t_type in ('bamboo', 'banana', 'palm', 'tree_fern') else 0.22
            radius = max(0.25, scale * trunk_fraction + 0.08)
            self._edge_ring.append({
                'x': x, 'y': y, 'type': t_type,
                'scale': scale, 'tint': rng_map.randint(170, 220),
                'radius': radius,
                'canopy_seed': rng_map.randint(0, 99999),
                'lean': rng_map.uniform(-0.05, 0.05),
                'biome': 'edge_ring',
            })

        def tier_sides(margin, step, fill, type_fn, scale_fn, jitter):
            # horizontal sides (top / bottom)
            for x in range(2, w - 1, int(step)):
                for ty in (margin, h - margin):
                    if rng_map.random() < fill:
                        add_tree(x + rng_map.uniform(-jitter, jitter),
                                 ty + rng_map.uniform(-jitter, jitter),
                                 type_fn(), scale_fn())
            # vertical sides (left / right)
            for y in range(2, h - 1, int(step)):
                for tx in (margin, w - margin):
                    if rng_map.random() < fill:
                        add_tree(tx + rng_map.uniform(-jitter, jitter),
                                 y + rng_map.uniform(-jitter, jitter),
                                 type_fn(), scale_fn())

        # Outer wall tier — dense, oversized balete
        tier_sides(1.5, 1.0, 0.95, lambda: 'balete',
                   lambda: rng_map.uniform(1.9, 2.4), 0.15)
        # Mid tier — mixed species
        tier_sides(3.0, 1.0, 0.85,
                   lambda: rng_map.choices(mix_types, weights=mix_weights, k=1)[0],
                   lambda: rng_map.uniform(1.2, 1.9), 0.3)
        # Inner tier — backfill depth
        tier_sides(4.5, 1.2, 0.75,
                   lambda: rng_map.choices(mix_types, weights=mix_weights, k=1)[0],
                   lambda: rng_map.uniform(0.9, 1.5), 0.4)

        # Corner reinforcement — 2x2 clusters at each corner
        for cx in (2.5, 4.0):
            for cy in (2.5, 4.0):
                for (px, py) in ((cx, cy), (w - cx, cy), (cx, h - cy), (w - cx, h - cy)):
                    add_tree(px + rng_map.uniform(-0.2, 0.2),
                             py + rng_map.uniform(-0.2, 0.2),
                             'balete', rng_map.uniform(2.0, 2.4))

    def _place_chapter1_entities(self):
        self.pickups = [
            {'type': 'ammo_shotgun', 'x': 25.5, 'y': 20.5, 'amount': 6, 'active': True},
            {'type': 'ammo_revolver', 'x': 52.5, 'y': 30.5, 'amount': 6, 'active': True},
            {'type': 'health', 'x': 80.5, 'y': 45.5, 'amount': 25, 'active': True},
            {'type': 'bible_page', 'x': 90.5, 'y': 60.5, 'amount': 1, 'active': True},
            {'type': 'battery', 'x': 110.5, 'y': 48.5, 'amount': 30, 'active': True},
            {'type': 'salt', 'x': 140.5, 'y': 80.5, 'amount': 3, 'active': True},
            {'type': 'bible_page', 'x': 160.5, 'y': 50.5, 'amount': 1, 'active': True},
            {'type': 'faith', 'x': 180.5, 'y': 60.5, 'amount': 20, 'active': True},
            {'type': 'ammo_shotgun', 'x': 220.5, 'y': 90.5, 'amount': 4, 'active': True},
            {'type': 'bible_page', 'x': 250.5, 'y': 70.5, 'amount': 1, 'active': True},
            {'type': 'health', 'x': 270.5, 'y': 105.5, 'amount': 20, 'active': True},
            {'type': 'garlic', 'x': 290.5, 'y': 96.5, 'amount': 2, 'active': True},
            {'type': 'ammo_revolver', 'x': 320.5, 'y': 110.5, 'amount': 6, 'active': True},
            {'type': 'bible_page', 'x': 340.5, 'y': 64.5, 'amount': 1, 'active': True},
            {'type': 'health', 'x': 360.5, 'y': 100.5, 'amount': 25, 'active': True},
        ]
        self.enemies = [
            {'type': 'aswang', 'x': 75.5, 'y': 40.0},
            {'type': 'multo', 'x': 130.5, 'y': 85.5},
            {'type': 'aswang', 'x': 210.5, 'y': 55.5},
            {'type': 'sigbin', 'x': 280.5, 'y': 90.5},
            {'type': 'white_lady', 'x': 340.5, 'y': 70.5},
        ]
        self.checkpoints.append({'x': 192.5, 'y': 64.5})
        self.exit_pos = (374.5, 64.5)

    def _place_chapter2_entities(self):
        self.pickups = [
            {'type': 'ammo_shotgun', 'x': 30.5, 'y': 25.5, 'amount': 6, 'active': True},
            {'type': 'bible_page', 'x': 70.5, 'y': 40.5, 'amount': 1, 'active': True},
            {'type': 'health', 'x': 105.5, 'y': 30.5, 'amount': 30, 'active': True},
            {'type': 'garlic', 'x': 135.5, 'y': 24.5, 'amount': 3, 'active': True},
            {'type': 'bible_page', 'x': 170.5, 'y': 80.5, 'amount': 1, 'active': True},
            {'type': 'faith', 'x': 200.5, 'y': 60.5, 'amount': 25, 'active': True},
            {'type': 'battery', 'x': 240.5, 'y': 75.5, 'amount': 40, 'active': True},
            {'type': 'bible_page', 'x': 280.5, 'y': 50.5, 'amount': 1, 'active': True},
            {'type': 'ammo_revolver', 'x': 310.5, 'y': 60.5, 'amount': 6, 'active': True},
            {'type': 'bible_page', 'x': 340.5, 'y': 90.5, 'amount': 1, 'active': True},
            {'type': 'health', 'x': 365.5, 'y': 115.5, 'amount': 25, 'active': True},
        ]
        self.enemies = [
            {'type': 'aswang', 'x': 80.5, 'y': 45.5},
            {'type': 'aswang', 'x': 150.5, 'y': 36.5},
            {'type': 'manananggal', 'x': 210.5, 'y': 90.5},
            {'type': 'multo', 'x': 120.5, 'y': 105.5},
            {'type': 'sigbin', 'x': 286.5, 'y': 120.5},
            {'type': 'tikbalang', 'x': 320.5, 'y': 55.5},
            {'type': 'kapre', 'x': 340.5, 'y': 60.5},
        ]
        self.checkpoints.append({'x': 192.5, 'y': 64.5})
        self.exit_pos = (374.5, 64.5)

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
        if x < 0 or x >= self.width:
            cx, cy = int(math.floor(x / 2.0)), int(math.floor(y / 2.0))
            h = abs(hash((cx, cy, WORLD_SEED))) % 1000
            if h < 90:
                rng_p = random.Random(hash((cx, cy, WORLD_SEED, 99)))
                tx = (cx + rng_p.uniform(0.2, 1.8)) * 2.0
                ty = (cy + rng_p.uniform(0.2, 1.8)) * 2.0
                if math.hypot(tx - x, ty - y) < (0.4 + radius):
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

    def clamp_position(self, x, y, radius):
        """Hard invisible-wall clamp: keep a circle fully inside the playable box.

        Backstop for the perimeter tree-line — even if a gap ever appears in
        the forest ring, the entity can never leave the intended map.
        The margin leaves the tree-line visible in front of the player.
        """
        m = EDGE_RING_PLAYABLE_MARGIN + radius
        cx = max(m, min(x, self.width - m))
        cy = max(m, min(y, self.height - m))
        return cx, cy

    def is_wall(self, x, y):
        ix, iy = int(x), int(y)
        if iy < 0 or iy >= self.height:
            return True
        if ix < 0 or ix >= self.width:
            return False
        return self.grid[iy][ix] != EMPTY

    def is_solid(self, x, y, doors_block=True):
        """True if (x, y) blocks movement. Closed doors block unless doors_block=False;
        opened doors become EMPTY tiles and are always passable.
        All four boundaries are bounded: a dense perimeter tree-line plus the
        hard clamp_position() backstop keep entities inside the playable area."""
        ix, iy = int(x), int(y)
        if iy < 0 or iy >= self.height:
            return True
        tile = self.get_tile(x, y)
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
        """Return tile at position. Out-of-bounds left/right still resolves to
        forest (the perimeter tree-line + clamp keep entities inside);
        top/bottom out-of-bounds are bounded by natural canopy."""
        ix, iy = int(x), int(y)
        if iy < 0 or iy >= self.height:
            return WALL_STONE
        if ix < 0 or ix >= self.width:
            return EMPTY
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
