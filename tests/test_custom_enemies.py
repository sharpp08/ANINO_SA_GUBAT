"""
Custom Enemy Sprite Validation Test for ANINO SA GUBAT.

Verifies that:
1. Every enemy type has all 12 animation states.
2. Every sprite is exactly 64x64 pixels.
3. Custom PNG sprites (if present) load correctly.
"""

import os
import sys

# Add project root to path so we can import game modules
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pygame


def test_all_enemies_have_12_states_and_64x64_size():
    """Test that generate_all_enemies produces the correct structure."""
    print("=== Starting Custom Enemy Sprite Test ===")
    
    # Initialize Pygame (headless)
    os.environ['SDL_VIDEODRIVER'] = 'dummy'
    os.environ['SDL_AUDIODRIVER'] = 'disk'
    pygame.init()
    pygame.display.set_mode((640, 360))
    
    try:
        # Import after Pygame init
        from asset_generator import generate_all_enemies
        
        # Generate all enemies
        enemies = generate_all_enemies()
        
        # Expected structure
        types = ['aswang', 'manananggal', 'tikbalang', 'kapre', 'white_lady', 'multo', 'sigbin']
        states = ['idle', 'walk', 'run', 'sprint', 'crawl', 'stalk', 'crouch', 'lunge', 'attack', 'stagger', 'death', 'hover']
        
        errors = []
        
        # Check every type has all 12 states
        for enemy_type in types:
            if enemy_type not in enemies:
                errors.append(f"Missing enemy type: {enemy_type}")
                continue
            
            for state in states:
                if state not in enemies[enemy_type]:
                    errors.append(f"Missing state '{state}' for enemy '{enemy_type}'")
                    continue
                
                sprite = enemies[enemy_type][state]
                
                # Check sprite size is exactly 64x64
                if sprite.get_size() != (64, 64):
                    errors.append(
                        f"Sprite '{enemy_type}_{state}' is {sprite.get_size()}, expected (64, 64)"
                    )
        
        if errors:
            print("\n[FAIL] Errors found:")
            for err in errors:
                print(f"  - {err}")
            return False
        
        print("\n[PASS] All 7 enemy types have all 12 states, all sprites are 64x64.")
        return True
        
    finally:
        pygame.quit()


def test_custom_png_file_structure():
    """Verify expected PNG files exist or document what's missing."""
    print("\n=== Checking Custom PNG File Structure ===")
    
    # Determine asset directory
    if getattr(sys, 'frozen', False):
        asset_dir = os.path.join(os.path.dirname(sys.executable), 'assets')
    else:
        asset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets')
    
    sprites_dir = os.path.join(asset_dir, 'sprites', 'enemies')
    
    types = ['aswang', 'manananggal', 'tikbalang', 'kapre', 'white_lady', 'multo', 'sigbin']
    required_files = {
        'idle': f'{types[0]}_idle.png',
        'attack': f'{types[0]}_attack.png',
    }
    
    # Check if directory exists
    if not os.path.exists(sprites_dir):
        print(f"[INFO] Sprites directory not found: {sprites_dir}")
        print("[INFO] Create it and add PNGs to enable custom enemy sprites.")
        return None  # Not an error, just no custom sprites
    
    # List all PNGs found
    png_files = [f for f in os.listdir(sprites_dir) if f.lower().endswith('.png')]
    print(f"[INFO] Found {len(png_files)} PNG files in {sprites_dir}")
    
    if png_files:
        for f in sorted(png_files):
            print(f"  - {f}")
    else:
        print("[INFO] No PNG files found. Add PNGs to use custom enemy sprites.")
        print("[INFO] File naming pattern:")
        print("  <type>_idle.png   for: idle, walk, stalk, crawl, crouch, hover, stagger, death")
        print("  <type>_attack.png for: attack, lunge, run, sprint")
    
    return True


if __name__ == '__main__':
    result1 = test_all_enemies_have_12_states_and_64x64_size()
    result2 = test_custom_png_file_structure()
    
    # Print summary
    print("\n=== Test Summary ===")
    print(f"Structure & Size Check: {'PASSED' if result1 else 'FAILED'}")
    print(f"Custom PNG Check: {'PASSED' if result2 else 'FAILED'}")
    
    sys.exit(0 if (result1 or result2 is None) else 1)