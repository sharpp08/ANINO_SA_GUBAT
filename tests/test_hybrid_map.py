"""
Regression checks for the 256x256 hybrid forest replacement map.
"""
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
import sys
import math
import numpy as np
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from settings import MAP_WIDTH, MAP_HEIGHT, EMPTY, DOOR, WALL_WOOD, WALL_STONE
from map_system import GameMap


def test_hybrid_dimensions_and_landmarks():
    for chapter in (1, 2):
        gm = GameMap(chapter)
        assert (gm.width, gm.height) == (256, 256)
        names = {item['name'] for item in gm.landmarks}
        assert {'Survivor Camp', 'Abandoned Village', 'Ancient Balete Grove',
                'Sunken Swampland', 'Limestone Cave', 'Forgotten Shrine'} <= names
        assert gm.terrain_grid.shape == (256, 256)
        assert set(np.unique(gm.terrain_grid)) >= {0, 1, 2, 3, 4, 5, 6}
        expected_trees = 5200 if chapter == 1 else 6500
        assert sum(1 for tree in gm.trees if tree.get('biome') != 'edge_ring') == expected_trees
        assert len([p for p in gm.pickups if p['type'] == 'bible_page']) >= 3
        assert gm.exit_pos == (242.5, 128.5)


def test_handcrafted_buildings_and_doorways():
    gm = GameMap(1)
    assert sum(row.count(WALL_WOOD) for row in gm.grid) >= 40
    assert sum(row.count(WALL_STONE) for row in gm.grid) >= 100
    assert sum(row.count(DOOR) for row in gm.grid) >= 5
    # All doors can be opened through the existing map API.
    doors = [(x, y) for y, row in enumerate(gm.grid) for x, tile in enumerate(row) if tile == DOOR]
    for x, y in doors:
        assert gm.open_door(x, y)
        assert gm.grid[y][x] == EMPTY


def test_hybrid_chunk_loader_does_not_erase_map():
    gm = GameMap(1)
    before_trees = len(gm.trees)
    before_landmarks = list(gm.landmarks)
    before_grid = sum(tile != EMPTY for row in gm.grid for tile in row)
    gm.world_engine.update_world_chunks(*gm.player_start, gm)
    assert len(gm.trees) == before_trees
    assert gm.landmarks == before_landmarks
    assert sum(tile != EMPTY for row in gm.grid for tile in row) == before_grid


def test_water_is_walkable_but_classified():
    gm = GameMap(1)
    positions = np.argwhere(gm.terrain_grid == 6)
    assert len(positions) > 0
    y, x = positions[len(positions) // 2]
    assert gm.is_water(x + 0.5, y + 0.5)
    assert not gm.is_solid(x + 0.5, y + 0.5)


def test_tree_border_and_collision_hash_survive():
    gm = GameMap(1)
    assert gm._edge_ring
    assert all(tree in gm.trees for tree in gm._edge_ring)
    for tree in gm._edge_ring[::max(1, len(gm._edge_ring) // 20)]:
        assert tree in gm.spatial_hash.query(tree['x'], tree['y'], radius=0.1)
    assert gm.clamp_position(-100, -100, 0.3) == (5.8, 5.8)


if __name__ == '__main__':
    tests = [test_hybrid_dimensions_and_landmarks, test_handcrafted_buildings_and_doorways,
             test_hybrid_chunk_loader_does_not_erase_map, test_water_is_walkable_but_classified,
             test_tree_border_and_collision_hash_survive]
    for test in tests:
        test()
        print('[PASS]', test.__name__)
    print('Hybrid map tests passed.')
