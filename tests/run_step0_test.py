import os
import sys
import pygame
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from main import Game, STATE_PLAYING
from settings import BUILD_VERSION

def run_test():
    os.makedirs(os.path.abspath(os.path.join(os.path.dirname(__file__), '../screenshots')), exist_ok=True)
    print(f"=== RUNNING STEP 0 TEST ({BUILD_VERSION}) ===")
    game = Game()
    game.load_chapter(1)
    game.state = STATE_PLAYING
    game.renderer.show_debug = True

    dt = 0.016
    frame_times = []
    
    # Run 120 frames
    for i in range(120):
        t0 = pygame.time.get_ticks()
        game.update_playing(dt, 0, 0)
        alive_enemies = game.enemy_manager.get_alive_enemies()
        game.renderer.render_frame(game.player, game.game_map, alive_enemies, game.effects, dt)
        t1 = pygame.time.get_ticks()
        frame_times.append(t1 - t0)

    # Capture final frame surface
    surf = game.internal
    arr = pygame.surfarray.array3d(surf)  # shape (w, h, 3)
    # arr is transposed in pygame surfarray: axis 0 is x, axis 1 is y
    # transpose to (h, w, 3) for numpy analysis
    arr_hw = np.transpose(arr, (1, 0, 2))
    
    h, w, _ = arr_hw.shape
    sky_region = arr_hw[0:int(h*0.3), :, :]
    wall_region = arr_hw[int(h*0.3):int(h*0.7), :, :]
    floor_region = arr_hw[int(h*0.7):h, :, :]

    mean_sky = float(np.mean(sky_region))
    mean_wall = float(np.mean(wall_region))
    mean_floor = float(np.mean(floor_region))
    mean_frame_time = float(np.mean(frame_times))

    print(f"Mean Sky Brightness: {mean_sky:.2f}")
    print(f"Mean Wall Brightness: {mean_wall:.2f}")
    print(f"Mean Floor Brightness: {mean_floor:.2f}")
    print(f"Mean Frame Time: {mean_frame_time:.2f} ms ({1000.0 / max(1.0, mean_frame_time):.1f} FPS)")

    shot_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../screenshots/step0.png'))
    pygame.image.save(surf, shot_path)
    print(f"Screenshot saved to: {shot_path}")
    print("STEP 0 TEST COMPLETE.")

if __name__ == '__main__':
    run_test()
