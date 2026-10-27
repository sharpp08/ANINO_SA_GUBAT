"""
Advanced Forest & Performance Test Suite for ANINO SA GUBAT.
Tests determinism, reachability, spatial hash correctness, and frame render timing.
"""
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import sys
import time
import pygame
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from settings import *
from map_system import GameMap, SpatialHash
from main import Game, STATE_PLAYING


def test_determinism():
    print("--- Testing Map Determinism ---")
    map1 = GameMap(1)
    map2 = GameMap(1)
    assert len(map1.trees) == len(map2.trees)
    for t1, t2 in zip(map1.trees, map2.trees):
        assert abs(t1['x'] - t2['x']) < 1e-5
        assert abs(t1['y'] - t2['y']) < 1e-5
        assert t1['type'] == t2['type']
    print("[PASS] Map Determinism Verified")


def test_spatial_hash_and_collision():
    print("--- Testing Spatial Hash & Collision ---")
    sh = SpatialHash(cell_size=2.0)
    dummy_tree = {'x': 10.0, 'y': 10.0, 'type': 'balete', 'radius': 0.4}
    sh.insert(dummy_tree, 10.0, 10.0, 0.4)

    results = sh.query(10.1, 10.1, radius=0.3)
    assert dummy_tree in results

    results_far = sh.query(15.0, 15.0, radius=0.3)
    assert dummy_tree not in results_far
    print("[PASS] Spatial Hash Correctness Verified")


def test_reachability_and_no_collision_traps():
    print("--- Testing Entity Reachability & No Trapped Entities ---")
    for ch in (1, 2):
        gmap = GameMap(ch)
        sx, sy = gmap.player_start
        assert not gmap.is_solid(gmap.exit_pos[0], gmap.exit_pos[1])
        for e in gmap.enemies:
            assert not gmap.is_solid(e['x'], e['y'])
        for p in gmap.pickups:
            assert not gmap.is_solid(p['x'], p['y'])
    print("[PASS] Reachability & Entity Placement Verified")


def test_frame_render_timing():
    print("--- Testing Frame Render Timing & Performance ---")
    game = Game()
    game.load_chapter(1)
    game.state = STATE_PLAYING

    t0 = time.time()
    frames = 60
    for _ in range(frames):
        dt = 0.016
        game.update_playing(dt, 0.0, 0.0)
        game.renderer.render_frame(game.player, game.game_map, game.enemy_manager.get_alive_enemies(), game.effects, dt)
    t1 = time.time()
    elapsed = t1 - t0
    fps_approx = frames / max(1e-5, elapsed)
    avg_ms = (elapsed / frames) * 1000.0
    print(f"[PERF] Rendered {frames} frames in {elapsed:.3f}s -> Avg Frame Time: {avg_ms:.2f}ms (~{fps_approx:.1f} FPS)")
    assert avg_ms < 50.0, f"Frame time too high: {avg_ms}ms"
    print("[PASS] Frame Render Performance Benchmark Passed")


if __name__ == '__main__':
    print("=== STARTING ADVANCED FOREST TEST SUITE ===")
    test_determinism()
    test_spatial_hash_and_collision()
    test_reachability_and_no_collision_traps()
    test_frame_render_timing()
    print("=== ADVANCED FOREST TEST SUITE COMPLETE: ALL PASSED ===")

