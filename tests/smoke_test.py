"""
Headless Smoke Test Suite for ANINO SA GUBAT: Mga Bulong ng Dilim
"""
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import sys
import time
import json
import pygame
import numpy as np

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
sys.path.insert(0, os.getcwd())

from settings import *
from player import Player
from map_system import GameMap
from enemies import EnemyManager
from renderer import Renderer
from audio_synth import audio_mgr
from asset_generator import generate_all_textures, generate_all_weapons, generate_all_enemies, generate_all_pickups, generate_crosshair
from main import Game, save_game, load_game, STATE_MENU, STATE_PLAYING, STATE_PAUSED, STATE_GAMEOVER, STATE_WIN


def run_smoke_tests():
    print("=== STARTING SMOKE TEST SUITE ===")
    passed = 0
    failed = 0

    def test_case(name, fn):
        nonlocal passed, failed
        try:
            fn()
            print(f"[PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    def test_imports():
        import main, player, enemies, map_system, renderer, asset_generator, audio_synth, settings
        pygame.init()
        screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        assert screen is not None
    test_case("Module Imports & Pygame Headless Init", test_imports)

    def test_assets():
        t0 = time.time()
        textures = generate_all_textures()
        weapons = generate_all_weapons()
        enemy_sprites = generate_all_enemies()
        pickups = generate_all_pickups()
        cross = generate_crosshair()
        dt = time.time() - t0
        assert dt < 5.0, f"Asset generation too slow: {dt}s"
        assert len(textures) > 0 and len(weapons) > 0 and len(enemy_sprites) > 0 and len(pickups) > 0
    test_case("Procedural Asset Generation (< 5s)", test_assets)

    def test_gameplay():
        game = Game()
        game.start_new_game()
        assert game.chapter == 1
        for frame in range(300):
            dt = 1.0 / 60.0
            game.update_playing(dt, 1.0 if frame % 10 == 0 else 0.0, 0.5 if frame % 20 == 0 else 0.0)
            game.render(dt)
            if frame == 30:
                game.player.current_weapon = 1
                game._fire()
            elif frame == 60:
                game.player.current_weapon = 2
                game._fire()
            elif frame == 90:
                game.player.start_reload()
            elif frame == 120:
                game._use_salt()
            elif frame == 150:
                game._use_garlic()
            elif frame == 180:
                game.player.wards_unlocked[0] = True
                game.player.selected_ward = 0
                game._cast_selected_ward()
            elif frame == 210:
                game._interact()

        game.load_chapter(2)
        assert game.chapter == 2
        for frame in range(100):
            game.update_playing(1.0/60.0, 0.0, 0.0)
            game.render(1.0/60.0)
    test_case("Game Initialization & Multi-Chapter Simulation", test_gameplay)

    def test_ai():
        game = Game()
        game.start_new_game()
        for enemy in game.enemy_manager.enemies:
            for st in ['idle', 'patrol', 'investigate', 'stalk', 'attack']:
                enemy.state = st
                enemy.update(0.016, game.player.x, game.player.y, game.game_map)
            enemy.take_damage(999, 'physical')
            assert not enemy.alive
    test_case("Enemy AI States & Lifecycle", test_ai)

    def test_state_machine():
        game = Game()
        assert game.state == STATE_MENU
        game.start_new_game()
        assert game.state == STATE_PLAYING
        game.state = STATE_PAUSED
        game.state = STATE_PLAYING
        game.player.health = 0
        game.player.alive = False
        game.state = STATE_GAMEOVER
        game.player.respawn()
        assert game.player.alive
        game.state = STATE_WIN
        game.state = STATE_MENU
        assert game.state == STATE_MENU
    test_case("Game State Machine Transitions", test_state_machine)

    def test_save_load():
        game = Game()
        game.start_new_game()
        game.player.health = 77.0
        save_game(game.player, game.chapter, 0)
        game.load_saved_game()
        assert abs(game.player.health - 77.0) < 1e-3

        os.makedirs(SAVE_DIR, exist_ok=True)
        old_save = os.path.join(SAVE_DIR, "save_0.json")
        with open(old_save, 'w') as f:
            json.dump({'chapter': 1}, f)
        game.load_saved_game()

        with open(old_save, 'w') as f:
            f.write("{ invalid json")
        assert load_game(0) is None

        missing = os.path.join(SAVE_DIR, "save_99.json")
        if os.path.exists(missing):
            os.remove(missing)
        assert load_game(99) is None

        with open(old_save, 'w') as f:
            f.write("")
        assert load_game(0) is None
    test_case("Save & Load Robustness", test_save_load)

    print(f"=== SMOKE TEST COMPLETE: {passed} PASSED, {failed} FAILED ===")
    return failed == 0


if __name__ == '__main__':
    success = run_smoke_tests()
    sys.exit(0 if success else 1)
