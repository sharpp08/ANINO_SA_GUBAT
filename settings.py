"""
ANINO SA GUBAT: Mga Bulong ng Dilim
Game Settings and Configuration (Enhanced - Phases 1 to 5)
"""
import json
import os

BUILD_VERSION = "BUILD 2026.10.27-FOREST"

# Display
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
INTERNAL_WIDTH = 640
INTERNAL_HEIGHT = 360
FPS = 60
TITLE = "ANINO SA GUBAT: Mga Bulong ng Dilim"
FULLSCREEN = True

# Performance & Effect Toggles
DEBUG = True
ENABLE_BLOOM = True
ENABLE_FILM_GRAIN = True
ENABLE_FOG = True
ENABLE_PARTICLES = True
ENABLE_DYNAMIC_LIGHTS = True
ENABLE_INTRO = True
ENABLE_AUDIO_SYNTH = True
ENABLE_SANITY = True
ENABLE_STEALTH_NOISE = True
DEBUG_OVERLAY = False

# Animation & Physics Toggles
ENABLE_ANIMATIONS = True
ENABLE_SPRING_PHYSICS = True
ENABLE_PARTICLE_PHYSICS = True
ENABLE_VERLET_ROPES = True
ENABLE_CAMERA_SHAKE = True
ENABLE_WEAPON_INERTIA = True
ENABLE_ENEMIES_ANIM = True
ENABLE_ENV_ANIM = True
ENABLE_UI_ANIM = True
ENABLE_GAME_FEEL = True

# HDR / PBR Graphics Settings
ENABLE_HDR = True
ENABLE_PBR = True
ENABLE_NORMAL_MAPPING = True
ENABLE_SSAO = True
ENABLE_GOD_RAYS = True
ENABLE_COLOR_GRADING = True
ENABLE_CHROMATIC_ABERRATION = True


# Quality Tier Presets
QUALITY_TIER = 'medium'  # 'low', 'medium', 'high'; overridden by "quality_tier" in settings.json at startup

# Performance-optimized quality presets with measurable differences.
# Each tier is the single source of truth for all renderer feature flags.
# User overrides (from settings.json "graphics_overrides") take precedence
# over these values; legacy ENABLE_* constants are the final fallback.
QUALITY_PRESETS = {
    'low': {
        'internal_width': 320, 'internal_height': 180,
        'enable_hdr': False, 'enable_pbr': False, 'enable_normal_mapping': False,
        'enable_ssao': False, 'enable_bloom': False, 'enable_god_rays': False,
        'enable_particles': False, 'enable_dynamic_lights': False,
        'enable_aurora': False, 'enable_enhanced_floor': False,
        'max_render_trees': 80, 'max_particles': 50, 'max_enemies': 4,
        # Renderer pass parameters
        'bloom_threshold': 0.85, 'bloom_intensity': 0.3, 'bloom_blur_passes': 1,
        'god_ray_samples': 0, 'god_ray_intensity': 0.0, 'god_ray_decay': 0.85,
        'hdr_exposure': 1.0, 'tone_mapping': 'reinhard',
        'ssao_samples': 0, 'ssao_radius': 0.5, 'ssao_strength': 0.0,
        'water_speed_multiplier': 0.4,
    },
    'medium': {
        'internal_width': 640, 'internal_height': 360,
        'enable_hdr': False, 'enable_pbr': False, 'enable_normal_mapping': False,
        'enable_ssao': False, 'enable_bloom': True, 'enable_god_rays': False,
        'enable_particles': True, 'enable_dynamic_lights': False,
        'enable_aurora': True, 'enable_enhanced_floor': True,
        'max_render_trees': 150, 'max_particles': 150, 'max_enemies': 6,
        'bloom_threshold': 0.72, 'bloom_intensity': 0.45, 'bloom_blur_passes': 2,
        'god_ray_samples': 0, 'god_ray_intensity': 0.0, 'god_ray_decay': 0.85,
        'hdr_exposure': 1.0, 'tone_mapping': 'reinhard',
        'ssao_samples': 0, 'ssao_radius': 0.5, 'ssao_strength': 0.0,
        'water_speed_multiplier': 0.4,
    },
    'high': {
        'internal_width': 640, 'internal_height': 360,
        'enable_hdr': True, 'enable_pbr': False, 'enable_normal_mapping': False,
        'enable_ssao': False, 'enable_bloom': True, 'enable_god_rays': True,
        'enable_particles': True, 'enable_dynamic_lights': True,
        'enable_aurora': True, 'enable_enhanced_floor': True,
        'max_render_trees': 220, 'max_particles': 300, 'max_enemies': 8,
        'bloom_threshold': 0.65, 'bloom_intensity': 0.6, 'bloom_blur_passes': 3,
        'god_ray_samples': 40, 'god_ray_intensity': 0.35, 'god_ray_decay': 0.88,
        'hdr_exposure': 1.1, 'tone_mapping': 'aces',
        'ssao_samples': 0, 'ssao_radius': 0.5, 'ssao_strength': 0.0,
        'water_speed_multiplier': 0.4,
    }
}

# Active quality settings (applied from presets)
ACTIVE_QUALITY = QUALITY_PRESETS['medium'].copy()


def apply_quality_preset(tier):
    """Apply a quality preset and return the settings dict.

    Must run before any module does ``from settings import *`` (main.py does
    this first), because resolution-dependent values are copied at import.

    Applies all renderer feature flags from the preset.  User overrides in
    ``settings.json`` (``graphics_overrides`` dict) take precedence for any
    key they specify; legacy ENABLE_* constants are the final fallback.
    """
    global ACTIVE_QUALITY, QUALITY_TIER, INTERNAL_WIDTH, INTERNAL_HEIGHT
    global NUM_RAYS, WALL_HEIGHT_SCALE, MAX_RENDER_TREES
    global ENABLE_PARTICLES, ENABLE_DYNAMIC_LIGHTS
    global ENABLE_BLOOM, ENABLE_HDR, ENABLE_PBR, ENABLE_SSAO, ENABLE_GOD_RAYS
    global BLOOM_THRESHOLD, BLOOM_INTENSITY, BLOOM_BLUR_PASSES
    global GOD_RAY_SAMPLES, GOD_RAY_INTENSITY, GOD_RAY_DECAY
    global HDR_EXPOSURE, TONE_MAPPING
    global SSAO_SAMPLES, SSAO_RADIUS, SSAO_STRENGTH
    global WATER_SPEED_MULTIPLIER
    if tier not in QUALITY_PRESETS:
        tier = 'medium'
    QUALITY_TIER = tier
    ACTIVE_QUALITY = QUALITY_PRESETS[tier].copy()
    # Resolution-dependent render settings
    INTERNAL_WIDTH = ACTIVE_QUALITY['internal_width']
    INTERNAL_HEIGHT = ACTIVE_QUALITY['internal_height']
    NUM_RAYS = INTERNAL_WIDTH
    WALL_HEIGHT_SCALE = INTERNAL_HEIGHT * TILE_SIZE
    # Feature toggles driven by the preset (AND with legacy defaults so
    # a user who disabled particles globally stays disabled)
    MAX_RENDER_TREES = ACTIVE_QUALITY['max_render_trees']
    ENABLE_PARTICLES = ENABLE_PARTICLES and ACTIVE_QUALITY['enable_particles']
    ENABLE_DYNAMIC_LIGHTS = ENABLE_DYNAMIC_LIGHTS and ACTIVE_QUALITY['enable_dynamic_lights']
    ENABLE_BLOOM = ACTIVE_QUALITY['enable_bloom']
    ENABLE_HDR = ACTIVE_QUALITY['enable_hdr']
    ENABLE_PBR = ACTIVE_QUALITY['enable_pbr']
    ENABLE_SSAO = ACTIVE_QUALITY['enable_ssao']
    ENABLE_GOD_RAYS = ACTIVE_QUALITY['enable_god_rays']
    # Renderer pass parameters
    BLOOM_THRESHOLD = ACTIVE_QUALITY['bloom_threshold']
    BLOOM_INTENSITY = ACTIVE_QUALITY['bloom_intensity']
    BLOOM_BLUR_PASSES = ACTIVE_QUALITY['bloom_blur_passes']
    GOD_RAY_SAMPLES = ACTIVE_QUALITY['god_ray_samples']
    GOD_RAY_INTENSITY = ACTIVE_QUALITY['god_ray_intensity']
    GOD_RAY_DECAY = ACTIVE_QUALITY['god_ray_decay']
    HDR_EXPOSURE = ACTIVE_QUALITY['hdr_exposure']
    TONE_MAPPING = ACTIVE_QUALITY['tone_mapping']
    SSAO_SAMPLES = ACTIVE_QUALITY['ssao_samples']
    SSAO_RADIUS = ACTIVE_QUALITY['ssao_radius']
    SSAO_STRENGTH = ACTIVE_QUALITY['ssao_strength']
    WATER_SPEED_MULTIPLIER = ACTIVE_QUALITY['water_speed_multiplier']
    return ACTIVE_QUALITY


# Raycasting
FOV = 60
HALF_FOV = FOV / 2
NUM_RAYS = INTERNAL_WIDTH
MAX_DEPTH = 35
TILE_SIZE = 64
WALL_HEIGHT_SCALE = INTERNAL_HEIGHT * TILE_SIZE

# Outdoor Forest Settings (Phases 1-4)
# Large open forest world: 384x128 wide horizontal world with open left/right sides
# and a natural tree-line boundary on top and bottom.
MAP_WIDTH = 384
MAP_HEIGHT = 128
MAP_SIZE = 128
WORLD_SEED = 1337          # master world seed (deterministic terrain)
TREE_COUNT_CH1 = 2600
TREE_COUNT_CH2 = 3600
MAX_RENDER_TREES = 280
GROUND_TEX_SIZE = 1024
UNDERGROWTH_DENSITY = 1600
EDGE_RING_TREES = 420      # dense natural tree-line around top/bottom edges


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
FLASHLIGHT_DRAIN_RATE = 1.0      # % per second while ON (was 0.4) -> ~100 s of light from full
FLASHLIGHT_RECHARGE_RATE = 0.1   # % per second while OFF (was 0.5)

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

# Lighting & Horror Atmosphere Constants
AMBIENT = 0.40            # 0 = pitch black outside the beam, 1 = fully lit
AMBIENT_LIGHT_OFF = 0.20  # brightness when the flashlight is off / dead
DARK_TINT = (6, 10, 24)   # cool moonlit blue for the dark overlay
BEAM_RADIUS = 0.45        # beam radius as a fraction of screen width
BEAM_GLOW = (52, 42, 22)  # warm additive light inside the beam
FOG_DISTANCE = 35.0
ENEMY_EYE_GLOW = True
MIN_SPRITE_LIGHT = 0.45   # sprites never get darker than this from distance shading
DANGER_RANGE = 7.0        # enemies closer than this trigger the horror effects

# ─── Renderer Pass Parameters (overridden by apply_quality_preset) ──────────
# Bloom
BLOOM_THRESHOLD = 0.72    # brightness threshold for bloom extraction (0-1)
BLOOM_INTENSITY = 0.45   # how strongly the blurred bloom is added back
BLOOM_BLUR_PASSES = 2     # number of downsample/upsample blur iterations
# God rays (screen-space radial light scattering)
GOD_RAY_SAMPLES = 0      # 0 = disabled; otherwise number of radial samples
GOD_RAY_INTENSITY = 0.0   # blend strength of the god-ray pass
GOD_RAY_DECAY = 0.85      # per-sample intensity decay (0.7-0.95)
# HDR / tone mapping
HDR_EXPOSURE = 1.0        # scene exposure before tone mapping
TONE_MAPPING = 'reinhard' # 'reinhard' or 'aces'
# SSAO (screen-space ambient occlusion)
SSAO_SAMPLES = 0          # 0 = disabled; otherwise sample count per pixel
SSAO_RADIUS = 0.5         # sampling radius in screen-space units
SSAO_STRENGTH = 0.0       # occlusion darkening strength (0 = none)

# ─── Water Movement ──────────────────────────────────────────────────────────
WATER_SPEED_MULTIPLIER = 0.4   # fraction of normal speed while wading in water

# Custom Enemy Sprites
USE_CUSTOM_ENEMY_SPRITES = True


# Map tiles
EMPTY = 0
WALL_STONE = 1
WALL_WOOD = 2
WALL_BAMBOO = 3
WALL_BALETE = 4
DOOR = 5
WATER = 6
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

# Chapter Page Gate Config
REQUIRE_PAGES_FOR_EXIT = True
PAGES_REQUIRED_CH1 = 3
PAGES_REQUIRED_CH2 = 3
ALLOW_ENEMY_CLEAR_EXIT = False

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
    'alt_fire': '',      # reserved
    'reload': 'r',
    'flashlight': 'f',
    'interact': 'e',
    'sprint': 'lshift',
    'crouch': 'lctrl',
    'jump': '',          # reserved
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

import sys

if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

SAVE_DIR = os.path.join(BASE_PATH, 'saves')
SETTINGS_PATH = os.path.join(BASE_PATH, 'settings.json')


def load_settings(path=SETTINGS_PATH):
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
        'enable_intro': ENABLE_INTRO,
        'debug_overlay': DEBUG_OVERLAY,
        'quality_tier': QUALITY_TIER,
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


def save_settings(settings, path=SETTINGS_PATH):
    """Save user settings to JSON file."""
    try:
        with open(path, 'w') as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass
