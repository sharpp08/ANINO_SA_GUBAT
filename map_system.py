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
        self.pickups = []
        self.enemies = []
        self.checkpoints = []
        self.exit_pos = (58.5, 58.5)
        self.chapter_num = chapter_num
        self.validation_errors = []
        self.load_chapter(chapter_num)

    def load_chapter(self, chapter_num):
        self.chapter_num = chapter_num
        self.validation_errors = []  # Count only real warnings
        for y in range(self.height):
            for x in range(self.width):
                if x == 0 or x == self.width - 1 or y == 0 or y == self.height - 1:
                    self.grid[y][x] = WALL_STONE
                else:
                    self.grid[y][x] = EMPTY

        for y in range(28, 38):
            for x in range(28, 38):
                if x == 28 or x == 37 or y == 28 or y == 37:
                    self.grid[y][x] = WALL_WOOD
                elif (x == 32 or x == 33) and y == 37:
                    self.grid[y][x] = DOOR

        random.seed(42 + chapter_num)
        self.trees = []
        tree_types = ['balete', 'bamboo', 'mahogany', 'dead']
        count = TREE_COUNT_CH1 if chapter_num == 1 else TREE_COUNT_CH2

        while len(self.trees) < count:
            tx = random.uniform(3.0, float(self.width - 3))
            ty = random.uniform(3.0, float(self.height - 3))
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
                t_type = random.choice(tree_types)
                self.trees.append({
                    'x': tx, 'y': ty, 'type': t_type,
                    'scale': random.uniform(0.8, 1.4), 'tint': random.randint(200, 255)
                })

        if chapter_num == 1:
            self.player_start = (4.5, 4.5)
            self.player_start_angle = 0
            self._place_chapter1_entities()
        else:
            self.player_start = (4.5, 4.5)
            self.player_start_angle = 0
            self._place_chapter2_entities()


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
        ]
        self.enemies = [
            {'type': 'aswang', 'x': 32.5, 'y': 15.5},
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
