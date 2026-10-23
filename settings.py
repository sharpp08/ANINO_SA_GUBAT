"""
ANINO SA GUBAT: Mga Bulong ng Dilim
Game Settings and Configuration (Enhanced - Phases 1 to 5)
"""
import json
import os

# Display
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
INTERNAL_WIDTH = 640
INTERNAL_HEIGHT = 360
FPS = 60
TITLE = "ANINO SA GUBAT: Mga Bulong ng Dilim"
FULLSCREEN = False

# Performance & Effect Toggles (Phases 1-5)
ENABLE_BLOOM = True
ENABLE_FILM_GRAIN = True
ENABLE_FOG = True
ENABLE_PARTICLES = True
ENABLE_DYNAMIC_LIGHTS = True
ENABLE_AUDIO_SYNTH = True
ENABLE_SANITY = True
ENABLE_STEALTH_NOISE = True
DEBUG_OVERLAY = True

# Raycasting
FOV = 60
HALF_FOV = FOV / 2
NUM_RAYS = INTERNAL_WIDTH
MAX_DEPTH = 20
TILE_SIZE = 64
WALL_HEIGHT_SCALE = INTERNAL_HEIGHT * TILE_SIZE

# Player
PLAYER_SPEED = 3.0
PLAYER_SPRINT_SPEED = 5.0
PLAYER_ROT_SPEED = 0.002
PLAYER_MAX_HEALTH = 100
PLAYER_MAX_ARMOR = 50
PLAYER_SIZE = 0.3
STAMINA_MAX = 100.0
STAMINA_DRAIN_RATE = 35.0
STAMINA_REGEN_RATE = 25.0

# Sanity / Fear (Phase 4)
SANITY_MAX = 100.0
SANITY_DRAIN_DARK = 4.0
SANITY_DRAIN_ENEMY = 8.0
SANITY_REGEN_LIGHT = 6.0

# Weapons (Rebalanced Phase 5)
BOLO_DAMAGE = 25
BOLO_RANGE = 1.5
BOLO_COOLDOWN = 0.4
BOLO_NOISE = 1.0

SHOTGUN_DAMAGE = 40
SHOTGUN_RANGE = 8
SHOTGUN_SPREAD = 0.1
SHOTGUN_PELLETS = 5
SHOTGUN_COOLDOWN = 0.8
SHOTGUN_MAX_AMMO = 16  # Rebalanced
SHOTGUN_RELOAD_TIME = 1.5
SHOTGUN_MAG_SIZE = 2
SHOTGUN_NOISE = 8.0

REVOLVER_DAMAGE = 30
REVOLVER_RANGE = 15
REVOLVER_COOLDOWN = 0.5
REVOLVER_MAX_AMMO = 24  # Rebalanced
REVOLVER_RELOAD_TIME = 1.2
REVOLVER_MAG_SIZE = 6
REVOLVER_NOISE = 6.0

RELOAD_NOISE = 4.0

# Flashlight
FLASHLIGHT_MAX_BATTERY = 100
FLASHLIGHT_DRAIN_RATE = 2
FLASHLIGHT_RECHARGE_RATE = 0.5

# Sacred Wards
FAITH_ENERGY_MAX = 100
FAITH_ENERGY_REGEN = 0.5
WARD_1_COST = 20
WARD_1_COOLDOWN = 8.0
WARD_2_COST = 25
WARD_2_COOLDOWN = 15.0
WARD_3_COST = 30
WARD_3_COOLDOWN = 12.0
WARD_4_COST = 20
WARD_4_COOLDOWN = 10.0
WARD_5_COST = 50
WARD_5_COOLDOWN = 30.0

SALT_MAX = 10
GARLIC_MAX = 8

# Enemies
ASWANG_HEALTH = 80
ASWANG_DAMAGE = 15
ASWANG_SPEED = 2.0

MANANANGGAL_HEALTH = 100
MANANANGGAL_DAMAGE = 20
MANANANGGAL_SPEED = 2.5

TIKBALANG_HEALTH = 150
TIKBALANG_DAMAGE = 30
TIKBALANG_SPEED = 1.8

KAPRE_HEALTH = 200
KAPRE_DAMAGE = 35
KAPRE_SPEED = 1.2

WHITE_LADY_HEALTH = 60
WHITE_LADY_DAMAGE = 10
WHITE_LADY_SPEED = 1.5

MULTO_HEALTH = 50
MULTO_DAMAGE = 12
MULTO_SPEED = 2.0

SIGBIN_HEALTH = 70
SIGBIN_DAMAGE = 18
SIGBIN_SPEED = 3.5

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (200, 30, 30)
DARK_RED = (120, 15, 15)
GREEN = (30, 120, 30)
DARK_GREEN = (15, 60, 15)
BROWN = (100, 70, 40)
DARK_BROWN = (60, 40, 20)
GRAY = (100, 100, 100)
DARK_GRAY = (40, 40, 40)
GOLD = (220, 180, 50)
LIGHT_GOLD = (255, 220, 100)
SKY_COLOR = (5, 5, 15)
FLOOR_COLOR = (25, 18, 12)
FOG_COLOR = (12, 18, 15)
HUD_BG = (20, 20, 20, 180)
BLOOD_RED = (150, 0, 0)
SACRED_GOLD = (255, 215, 0)
SACRED_WHITE = (240, 240, 255)
HEALTH_GREEN = (50, 200, 50)
HEALTH_RED = (200, 50, 50)
AMMO_YELLOW = (220, 200, 50)
FAITH_BLUE = (80, 120, 220)
SANITY_PURPLE = (140, 80, 200)

# Map tiles
EMPTY = 0
WALL_STONE = 1
WALL_WOOD = 2
WALL_BAMBOO = 3
WALL_BALETE = 4
DOOR = 5
PICKUP_HEALTH = 10
PICKUP_AMMO_SHOTGUN = 11
PICKUP_AMMO_REVOLVER = 12
PICKUP_SALT = 13
PICKUP_GARLIC = 14
PICKUP_BATTERY = 15
PICKUP_FAITH = 16
PICKUP_BIBLE_PAGE = 17
SPAWN_ASWANG = 20
SPAWN_MANANANGGAL = 21
SPAWN_TIKBALANG = 22
SPAWN_KAPRE = 23
SPAWN_WHITE_LADY = 24
SPAWN_MULTO = 25
SPAWN_SIGBIN = 26
PLAYER_START = 30
CHECKPOINT = 31
LEVEL_EXIT = 32
INTERACT_OBJECT = 33

# Audio
MASTER_VOLUME = 0.7
MUSIC_VOLUME = 0.4
SFX_VOLUME = 0.8

# Controls (defaults)
CONTROLS = {
    'forward': 'w',
    'backward': 's',
    'strafe_left': 'a',
    'strafe_right': 'd',
    'fire': 'mouse1',
    'alt_fire': 'mouse3',
    'reload': 'r',
    'flashlight': 'f',
    'interact': 'e',
    'sprint': 'lshift',
    'crouch': 'lctrl',
    'jump': 'space',
    'ward_menu': 'q',
    'ward_1': '1',
    'ward_2': '2',
    'ward_3': '3',
    'ward_4': '4',
    'ward_5': '5',
    'salt': 'g',
    'garlic': 'h',
    'rosary': 'v',
    'cross': 'c',
    'pause': 'escape',
    'debug_toggle': 'f3',
}

SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saves')


def load_settings(path='settings.json'):
    """Load user settings from JSON file."""
    defaults = {
        'screen_width': SCREEN_WIDTH,
        'screen_height': SCREEN_HEIGHT,
        'fullscreen': FULLSCREEN,
        'mouse_sensitivity': PLAYER_ROT_SPEED,
        'master_volume': MASTER_VOLUME,
        'music_volume': MUSIC_VOLUME,
        'sfx_volume': SFX_VOLUME,
        'enable_bloom': ENABLE_BLOOM,
        'enable_film_grain': ENABLE_FILM_GRAIN,
        'enable_fog': ENABLE_FOG,
        'enable_particles': ENABLE_PARTICLES,
        'enable_audio_synth': ENABLE_AUDIO_SYNTH,
        'enable_sanity': ENABLE_SANITY,
        'debug_overlay': DEBUG_OVERLAY,
        'controls': CONTROLS.copy(),
    }
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                user = json.load(f)
            defaults.update(user)
        except Exception:
            pass
    return defaults


def save_settings(settings, path='settings.json'):
    """Save user settings to JSON file."""
    try:
        with open(path, 'w') as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass
