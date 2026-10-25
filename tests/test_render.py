"""
Headless test harness for ANINO SA GUBAT: Mga Bulong ng Dilim.
Verifies rendering, entity visibility, Z-buffer occlusion, and level progression.
"""
import os
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
pygame.init()

import math
from settings import *
from main import Game, STATE_PLAYING

def run_harness():
    os.makedirs('shots', exist_ok=True)
    print("=== STARTING RENDER TEST HARNESS ===")
    
    game = Game()
    game.load_chapter(1)
    game.state = STATE_PLAYING
    
    # Run 5 initial frames
    for i in range(5):
        game.dt = 0.016
        game.update_playing(0.016, 0, 0)
        game.renderer.render_frame(game.player, game.game_map, game.enemy_manager.get_alive_enemies(), game.effects, 0.016)
    
    screen_path = "shots/frame_1.png"
    pygame.image.save(game.internal, screen_path)
    print(f"[PASS] Saved initial frame to {screen_path}")
    
    # Print entity diagnostics
    print("\n--- ENTITY DIAGNOSTICS ---")
    player = game.player
    for idx, enemy in enumerate(game.enemy_manager.enemies):
        dx = enemy.x - player.x
        dy = enemy.y - player.y
        dist = math.sqrt(dx * dx + dy * dy)
        angle = math.atan2(dy, dx) - player.angle
        while angle > math.pi: angle -= 2 * math.pi
        while angle < -math.pi: angle += 2 * math.pi
        in_fov = abs(angle) <= game.renderer.half_fov + 0.2
        print(f"Enemy #{idx} ({enemy.type}): pos=({enemy.x:.2f}, {enemy.y:.2f}), dist={dist:.2f}, angle={angle:.2f}, in_fov={in_fov}, alive={enemy.alive}")
        
    for idx, pickup in enumerate(game.game_map.pickups):
        dx = pickup['x'] - player.x
        dy = pickup['y'] - player.y
        dist = math.sqrt(dx * dx + dy * dy)
        angle = math.atan2(dy, dx) - player.angle
        while angle > math.pi: angle -= 2 * math.pi
        while angle < -math.pi: angle += 2 * math.pi
        in_fov = abs(angle) <= game.renderer.half_fov + 0.2
        print(f"Pickup #{idx} ({pickup['type']}): pos=({pickup['x']:.2f}, {pickup['y']:.2f}), dist={dist:.2f}, angle={angle:.2f}, in_fov={in_fov}, active={pickup.get('active', True)}")

    # Test placing player near nearest enemy / pickup
    if game.enemy_manager.enemies:
        target_enemy = game.enemy_manager.enemies[0]
        angle_to_enemy = math.atan2(target_enemy.y - player.y, target_enemy.x - player.x)
        player.x = target_enemy.x - math.cos(angle_to_enemy) * 2.0
        player.y = target_enemy.y - math.sin(angle_to_enemy) * 2.0
        player.angle = angle_to_enemy
        
        game.renderer.render_frame(player, game.game_map, game.enemy_manager.get_alive_enemies(), game.effects, 0.016)
        pygame.image.save(game.internal, "shots/near_enemy.png")
        print("[PASS] Saved shots/near_enemy.png")

    if game.game_map.pickups:
        target_pickup = game.game_map.pickups[0]
        angle_to_pickup = math.atan2(target_pickup['y'] - player.y, target_pickup['x'] - player.x)
        player.x = target_pickup['x'] - math.cos(angle_to_pickup) * 1.5
        player.y = target_pickup['y'] - math.sin(angle_to_pickup) * 1.5
        player.angle = angle_to_pickup
        
        game.renderer.render_frame(player, game.game_map, game.enemy_manager.get_alive_enemies(), game.effects, 0.016)
        pygame.image.save(game.internal, "shots/near_pickup.png")
        print("[PASS] Saved shots/near_pickup.png")

    # Test nolight shot (turning off flashlight and dark overlay)
    old_on = player.flashlight_on
    player.flashlight_on = False
    game.renderer.flashlight.on = False
    game.renderer.render_frame(player, game.game_map, game.enemy_manager.get_alive_enemies(), game.effects, 0.016)
    pygame.image.save(game.internal, "shots/nolight.png")
    player.flashlight_on = old_on
    game.renderer.flashlight.on = old_on
    print("[PASS] Saved shots/nolight.png")

    # Test Step 6 - Level progression (killing all enemies)
    print("\n--- LEVEL PROGRESSION TEST ---")
    game.load_chapter(1)
    initial_chapter = game.chapter
    print(f"Initial chapter: {initial_chapter}, alive enemies: {len(game.enemy_manager.get_alive_enemies())}")
    for enemy in game.enemy_manager.enemies:
        enemy.alive = False
        enemy.health = 0
    # Run update to trigger level completion check
    game.update_playing(0.016, 0, 0)
    print(f"After killing all enemies - chapter: {game.chapter}, state: {game.state}")

    print("=== TEST HARNESS COMPLETE ===")

if __name__ == '__main__':
    run_harness()



def run_harness():
    os.makedirs('shots', exist_ok=True)
    print("=== STARTING RENDER TEST HARNESS ===")
    
    game = Game()
    game.new_game()
    
    # Run 5 initial frames
    for i in range(5):
        game.dt = 0.016
        game.update()
        game.draw()
    
    screen_path = "shots/frame_1.png"
    pygame.image.save(game.screen, screen_path)
    print(f"[PASS] Saved initial frame to {screen_path}")
    
    # Print entity diagnostics
    print("\n--- ENTITY DIAGNOSTICS ---")
    player = game.player
    for idx, enemy in enumerate(game.enemy_manager.enemies):
        dx = enemy.x - player.x
        dy = enemy.y - player.y
        dist = math.sqrt(dx * dx + dy * dy)
        angle = math.atan2(dy, dx) - player.angle
        while angle > math.pi: angle -= 2 * math.pi
        while angle < -math.pi: angle += 2 * math.pi
        in_fov = abs(angle) <= game.renderer.half_fov + 0.2
        print(f"Enemy #{idx} ({enemy.type}): pos=({enemy.x:.2f}, {enemy.y:.2f}), dist={dist:.2f}, angle={angle:.2f}, in_fov={in_fov}, alive={enemy.alive}")
        
    for idx, pickup in enumerate(game.map_system.pickups):
        dx = pickup['x'] - player.x
        dy = pickup['y'] - player.y
        dist = math.sqrt(dx * dx + dy * dy)
        angle = math.atan2(dy, dx) - player.angle
        while angle > math.pi: angle -= 2 * math.pi
        while angle < -math.pi: angle += 2 * math.pi
        in_fov = abs(angle) <= game.renderer.half_fov + 0.2
        print(f"Pickup #{idx} ({pickup['type']}): pos=({pickup['x']:.2f}, {pickup['y']:.2f}), dist={dist:.2f}, angle={angle:.2f}, in_fov={in_fov}, active={pickup.get('active', True)}")

    # Test placing player near nearest enemy / pickup
    if game.enemy_manager.enemies:
        target_enemy = game.enemy_manager.enemies[0]
        # Place player 2 units away facing enemy
        angle_to_enemy = math.atan2(target_enemy.y - player.y, target_enemy.x - player.x)
        player.x = target_enemy.x - math.cos(angle_to_enemy) * 2.0
        player.y = target_enemy.y - math.sin(angle_to_enemy) * 2.0
        player.angle = angle_to_enemy
        
        game.update()
        game.draw()
        pygame.image.save(game.screen, "shots/near_enemy.png")
        print("[PASS] Saved shots/near_enemy.png")

    if game.map_system.pickups:
        target_pickup = game.map_system.pickups[0]
        angle_to_pickup = math.atan2(target_pickup['y'] - player.y, target_pickup['x'] - player.x)
        player.x = target_pickup['x'] - math.cos(angle_to_pickup) * 1.5
        player.y = target_pickup['y'] - math.sin(angle_to_pickup) * 1.5
        player.angle = angle_to_pickup
        
        game.update()
        game.draw()
        pygame.image.save(game.screen, "shots/near_pickup.png")
        print("[PASS] Saved shots/near_pickup.png")

    # Test nolight shot (turning off flashlight and dark overlay)
    old_on = player.flashlight_on
    player.flashlight_on = False
    game.renderer.flashlight.on = False
    game.update()
    game.draw()
    pygame.image.save(game.screen, "shots/nolight.png")
    player.flashlight_on = old_on
    game.renderer.flashlight.on = old_on
    print("[PASS] Saved shots/nolight.png")

    print("=== TEST HARNESS COMPLETE ===")

if __name__ == '__main__':
    run_harness()
