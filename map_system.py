"""
Map system - defines levels, handles map loading, and provides tile queries.
"""
import math
import random
from settings import *


class GameMap:
    """Outdoor forest map system with tree billboards, boundaries, cabins, and paths."""

    def __init__(self, chapter_num=1):
        self.width = MAP_SIZE  # 64
        self.height = MAP_SIZE  # 64
        self.grid = [[EMPTY for _ in range(self.width)] for _ in range(self.height)]
        self.trees = []
        self.undergrowth = []
        self.pickups = []
        self.enemies = []
        self.checkpoints = []
        self.exit_pos = (58.5, 58.5)
        self.chapter_num = chapter_num
        self.max_chapters = 2
        self.validation_errors = []
        self.load_chapter(chapter_num)

    def load_chapter(self, chapter_num):
        self.chapter_num = chapter_num
        self.validation_errors = []  # Count only real warnings
        self.checkpoints = []        # was appended to on every load -> duplicates
        for y in range(self.height):
            for x in range(self.width):
                if x == 0 or x == self.width - 1 or y == 0 or y == self.height - 1:
                    self.grid[y][x] = WALL_STONE
                else:
                    self.grid[y][x] = EMPTY

        for y in range(28, 38):
            for x in range(28, 38):
                # Door must be checked FIRST: it sits on the y == 37 wall row, so the old
                # order made the door branch unreachable and sealed the cabin completely
                # (the Bible page / checkpoint inside it could never be reached).
                if (x == 32 or x == 33) and y == 37:
                    self.grid[y][x] = DOOR
                elif x == 28 or x == 37 or y == 28 or y == 37:
                    self.grid[y][x] = WALL_WOOD

        rng_map = random.Random(42 + chapter_num)
        self.trees = []
        tree_types = ['balete', 'bamboo', 'mahogany', 'dead']
        count = TREE_COUNT_CH1 if chapter_num == 1 else TREE_COUNT_CH2

        while len(self.trees) < count:
            tx = rng_map.uniform(3.0, float(self.width - 3))
            ty = rng_map.uniform(3.0, float(self.height - 3))
            if math.hypot(tx - 4.5, ty - 4.5) < 4.0:
                continue
            if 27 <= tx <= 38 and 27 <= ty <= 38:
                continue
            
            too_close = False
            for t in self.trees:
                if math.hypot(t['x'] - tx, t['y'] - ty) < 2.2:
                    too_close = True
                    break
            if not too_close:
                t_type = rng_map.choice(tree_types)
                self.trees.append({
                    'x': tx, 'y': ty, 'type': t_type,
                    'scale': rng_map.uniform(0.8, 1.4), 'tint': rng_map.randint(200, 255)
                })

        # Generate dense legitimate forest undergrowth (ferns, mushrooms, rocks, bushes)
        self.undergrowth = []
        plant_types = ['fern', 'mushroom', 'rock', 'bush']
        p_count = UNDERGROWTH_DENSITY
        while len(self.undergrowth) < p_count:
            px = rng_map.uniform(2.0, float(self.width - 2))
            py = rng_map.uniform(2.0, float(self.height - 2))
            if math.hypot(px - 4.5, py - 4.5) < 3.0:
                continue
            if 27 <= px <= 38 and 27 <= py <= 38:
                continue
            in_tree = False
            for t in self.trees:
                if math.hypot(t['x'] - px, t['y'] - py) < 0.9 * t['scale']:
                    in_tree = True
                    break
            if in_tree:
                continue
            p_type = rng_map.choice(plant_types)
            self.undergrowth.append({
                'x': px, 'y': py, 'type': p_type,
                'scale': rng_map.uniform(0.7, 1.3)
            })

        if chapter_num == 1:
            self.player_start = (4.5, 4.5)
            self.player_start_angle = 0
            self._place_chapter1_entities()
        else:
            self.player_start = (4.5, 4.5)
            self.player_start_angle = 0
            self._place_chapter2_entities()

        # Trees are placed randomly BEFORE entities, so some enemies, pickups and the exit
        # ended up inside tree trunks. A trapped enemy can never be killed, which means
        # "all enemies defeated" never fires and the next chapter never loads.
        self._clear_trees_near_entities()
        self._validate_entities()

    def _entity_points(self):
        pts = [(e['x'], e['y'], 'enemy ' + e['type']) for e in self.enemies]
        pts += [(p['x'], p['y'], 'pickup ' + p['type']) for p in self.pickups]
        pts += [(c['x'], c['y'], 'checkpoint') for c in self.checkpoints]
        pts.append((self.exit_pos[0], self.exit_pos[1], 'exit'))
        pts.append((self.player_start[0], self.player_start[1], 'player start'))
        return pts

    def _clear_trees_near_entities(self, clearance=1.4):
        pts = self._entity_points()
        before = len(self.trees)
        self.trees = [
            t for t in self.trees
            if all(math.hypot(t['x'] - px, t['y'] - py) >= clearance + 0.45 * t['scale']
                   for px, py, _ in pts)
        ]
        removed = before - len(self.trees)
        if removed:
            print(f"[MAP] chapter {self.chapter_num}: removed {removed} tree(s) blocking enemies/pickups/exit")

    def _validate_entities(self):
        for x, y, name in self._entity_points():
            if self.is_wall(x, y) and self.get_tile(x, y) != DOOR:
                self.validation_errors.append(f"{name} at ({x:.1f},{y:.1f}) is inside a wall")
            elif self.is_tree_solid(x, y, radius=0.25):
                self.validation_errors.append(f"{name} at ({x:.1f},{y:.1f}) is inside a tree")


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
            # a few items right in front of the start so you can see them immediately
            {'type': 'salt', 'x': 8.5, 'y': 4.8, 'amount': 2, 'active': True},
            {'type': 'battery', 'x': 11.5, 'y': 3.6, 'amount': 30, 'active': True},
            {'type': 'faith', 'x': 9.5, 'y': 6.0, 'amount': 20, 'active': True},
        ]
        self.enemies = [
            {'type': 'aswang', 'x': 17.5, 'y': 6.0},   # moved from (32.5, 15.5): now in view at the start
            {'type': 'multo', 'x': 15.5, 'y': 40.5},
            {'type': 'aswang', 'x': 45.5, 'y': 25.5},
            {'type': 'sigbin', 'x': 25.5, 'y': 50.5},
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
        ]
        self.checkpoints.append({'x': 32.5, 'y': 32.5})
        self.exit_pos = (58.5, 58.5)

    def is_tree_solid(self, x, y, radius=0.3):
        for t in self.trees:
            if math.hypot(t['x'] - x, t['y'] - y) < (0.45 * t['scale'] + radius):
                return True
        return False

    def is_wall(self, x, y):
        ix, iy = int(x), int(y)
        if ix < 0 or ix >= self.width or iy < 0 or iy >= self.height:
            return True
        return self.grid[iy][ix] != EMPTY

    def is_solid(self, x, y):
        ix, iy = int(x), int(y)
        if ix < 0 or ix >= self.width or iy < 0 or iy >= self.height:
            return True
        tile = self.grid[iy][ix]
        if tile != EMPTY and tile != DOOR:
            return True
        return self.is_tree_solid(x, y, radius=0.25)

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
