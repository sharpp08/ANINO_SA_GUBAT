import os
import sys
import pygame
import numpy as np
import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from main import Game, STATE_PLAYING
from settings import BUILD_VERSION

def run_test():
    screenshots_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../screenshots'))
    os.makedirs(screenshots_dir, exist_ok=True)
    print(f"=== RUNNING STEP A1 DIAGNOSTIC TEST ({BUILD_VERSION}) ===")
    
    game = Game()
    game.load_chapter(1)
    game.state = STATE_PLAYING
    game.renderer.show_debug = True

    dt = 0.016
    frame_times = []
    
    # Run 300 frames (5 seconds at 60 FPS)
    for i in range(300):
        t0 = pygame.time.get_ticks()
        game.update_playing(dt, 0.2, 0.0)  # gentle movement
        alive_enemies = game.enemy_manager.get_alive_enemies()
        game.renderer.render_frame(game.player, game.game_map, alive_enemies, game.effects, dt)
        t1 = pygame.time.get_ticks()
        frame_times.append(t1 - t0)

    surf = game.internal
    shot_path = os.path.abspath(os.path.join(screenshots_dir, 'stepa1.png'))
    pygame.image.save(surf, shot_path)
    print(f"Screenshot saved to: {shot_path}")

    # File LastWriteTimes for verification
    changed_files = ['renderer.py']
    print("--- File Write Times ---")
    for f in changed_files:
        fpath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', f))
        if os.path.exists(fpath):
            mtime = os.path.getmtime(fpath)
            dt_mtime = datetime.datetime.fromtimestamp(mtime)
            print(f"{f}: {dt_mtime}")

    print("STEP A1 DIAGNOSTIC TEST COMPLETE.")

if __name__ == '__main__':
    run_test()
