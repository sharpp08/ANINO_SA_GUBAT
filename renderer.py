"""
Raycasting renderer - provides pseudo-3D first-person view.

FIXED in this version
  * Sprites (enemies / pickups) were drawn almost fully TRANSPARENT and black:
    the distance shading used BLEND_RGBA_MULT with (0,0,0,alpha), which zeroes the
    RGB channels and multiplies the sprite's alpha down.  Shading now uses
    BLEND_RGB_MULT (colour only, alpha untouched) with a minimum brightness.
  * Trees had dark rectangles around them (a black alpha overlay was blitted onto
    the transparent pixels).  Same fix.
  * The flashlight / darkness / particles / vignette passes ran TWICE per frame,
    which made the scene far too dark.  They now run once.
  * Darkness is now one cached overlay with a soft hole (no per-frame surface
    allocation) and is controlled by AMBIENT.
  * Enemies, pickups and trees are depth-sorted together and stand on the floor
    (same projection formula as the walls).
  * Per-column z-buffer occlusion (a sprite is only hidden by closer walls).
  * Rays that hit nothing no longer draw a fake wall band at MAX_DEPTH.
  * Glowing eyes / pickup halos are drawn AFTER the darkness pass so they are
    visible in the dark.
  * Danger feedback: red pulsing vignette, heartbeat, screen shake near enemies.
  * The leftover chapter_1_after.png debug screenshot was removed.
"""
import os
import math
import random
import heapq
import pygame
import numpy as np
from settings import *
import settings as _settings_mod   # live module: ACTIVE_QUALITY is reassigned when the tier changes
from floor_fast import fill_floor, fill_floor_terrain
from raycast_fast import cast_rays, visible_runs
from weather_fx import WeatherFX
from enemies import DEATH_ANIM_TIME

# Lighting constants (AMBIENT, BEAM_RADIUS, FOG_DISTANCE, ...) live in settings.py

# eye positions in the 64x64 enemy sprites made by asset_generator.py
ENEMY_EYES = {
    'aswang':      (((28, 20), (36, 20)), (255, 40, 40)),
    'manananggal': (((30, 24), (34, 24)), (255, 50, 50)),
    'tikbalang':   (((28, 12), (36, 12)), (255, 190, 30)),
    'kapre':       (((28, 16), (36, 16)), (255, 120, 20)),
    'white_lady':  (((28, 14), (36, 14)), (170, 200, 255)),
    'multo':       (((28, 20), (36, 20)), (150, 180, 255)),
    'sigbin':      (((20, 22), (26, 22)), (255, 80, 20)),
}
ENEMY_AURA = {
    'white_lady': (60, 70, 120),
    'multo': (40, 50, 90),
    'manananggal': (80, 15, 25),
    'kapre': (60, 35, 8),
    'aswang': (50, 8, 12),
}
# height of the enemy relative to a one-tile wall, and whether it floats
ENEMY_SIZE = {
    'aswang': (0.95, 0.0), 'manananggal': (1.0, 0.25), 'tikbalang': (1.25, 0.0),
    'kapre': (1.45, 0.0), 'white_lady': (1.15, 0.08), 'multo': (1.0, 0.18),
    'sigbin': (0.6, 0.0),
}
PICKUP_GLOW = {
    'health': (130, 30, 30), 'ammo_shotgun': (120, 90, 30), 'ammo_revolver': (120, 90, 30),
    'salt': (90, 100, 125), 'garlic': (120, 110, 80), 'battery': (130, 120, 30),
    'faith': (50, 85, 170), 'bible_page': (130, 105, 55),
}


class Flashlight:
    """Flashlight: one cached darkness overlay with a soft hole + warm additive glow."""

    def __init__(self, screen_w, screen_h):
        self.w = screen_w
        self.h = screen_h
        self.on = True
        self.sway_x = 0.0
        self.sway_y = 0.0
        self.target_sway_x = 0.0
        self.target_sway_y = 0.0
        self.dark_mask = None     # 2w x 2h, soft hole in the middle
        self.glow_mask = None     # 2w x 2h, additive warm light
        self.dark_off = None      # full-screen darkness when the light is off
        self.dark_flicker = None  # extra darkness used for low-battery flicker
        self._init_mask()

    def _init_mask(self):
        """Precompute perfectly circular tactical flashlight beam masks (Hotspot, Main Beam, Penumbra, Spill)."""
        w, h = self.w, self.h
        mw, mh = w * 2, h * 2
        ys, xs = np.ogrid[:mh, :mw]
        
        dx = (xs - w).astype(np.float32)
        dy = (ys - h).astype(np.float32)
        
        # Euclidean distance from the exact center of the beam
        dist_px = np.sqrt(dx * dx + dy * dy)
        
        # Radi1 based on tactical tuning targets (Main beam 12 deg ~ radius R, Hotspot ~ R * 0.25, Spill ~ R * 1.8)
        R_main = float(w * BEAM_RADIUS * 0.9)
        R_hotspot = R_main * 0.25
        R_spill = R_main * 1.8
        
        # Normalized radial distance [0, 1] for main beam & penumbra
        r = np.clip(dist_px / R_main, 0.0, 1.0)
        
        # Smooth penumbra transition using smoothstep
        penumbra = np.clip((dist_px - (R_main - w * 0.04)) / (w * 0.08), 0.0, 1.0)
        penumbra = penumbra * penumbra * (3.0 - 2.0 * penumbra)
        
        dark_alpha = int((1.0 - FLASHLIGHT_AMBIENT_LEVEL) * 255)
        self.dark_mask = pygame.Surface((mw, mh), pygame.SRCALPHA)
        self.dark_mask.fill((DARK_TINT[0], DARK_TINT[1], DARK_TINT[2], 255))
        av = pygame.surfarray.pixels_alpha(self.dark_mask)
        # Outside main beam + penumbra, reach full dark alpha; inside, clear to transparent
        mask_t = np.clip(penumbra, 0.0, 1.0)
        av[:, :] = (mask_t * dark_alpha).T.astype(np.uint8)
        del av

        # Perfectly circular main beam and outer spill (hotspot circle removed for uniform illumination)
        main_beam = (1.0 - r * r) ** 1.8
        main_beam = np.where(dist_px <= R_main, main_beam, 0.0)
        
        spill_r = np.clip(dist_px / R_spill, 0.0, 1.0)
        spill = (1.0 - spill_r) * FLASHLIGHT_SPILL_INTENSITY
        spill = np.where(dist_px <= R_spill, spill, 0.0)

        rgb = np.zeros((mw, mh, 3), dtype=np.uint8)
        for c in range(3):
            ch_val = (
                main_beam * BEAM_GLOW[c] * 0.85 +
                spill * PERIPHERAL_SPILL[c] * 0.35
            )
            rgb[:, :, c] = np.clip(ch_val, 0, 255).T.astype(np.uint8)
            
        self.glow_mask = pygame.Surface((mw, mh))
        pygame.surfarray.blit_array(self.glow_mask, rgb)

        # .convert_alpha() matches these overlays to the display pixel format
        # so the per-frame blits use the fast SDL blitter.
        self.dark_mask = self.dark_mask.convert_alpha()
        self.glow_mask = self.glow_mask.convert()
        self.dark_off = pygame.Surface((w, h), pygame.SRCALPHA)
        self.dark_off.fill((DARK_TINT[0], DARK_TINT[1], DARK_TINT[2],
                            int((1.0 - 0.05) * 255)))
        self.dark_flicker = pygame.Surface((w, h), pygame.SRCALPHA)
        self.dark_flicker.fill((DARK_TINT[0], DARK_TINT[1], DARK_TINT[2], 90))
        try:
            self.dark_off = self.dark_off.convert_alpha()
            self.dark_flicker = self.dark_flicker.convert_alpha()
        except Exception:
            pass

    def toggle(self):
        self.on = not self.on
        from audio_synth import audio_mgr
        try:
            audio_mgr.play('flashlight_click')
        except Exception:
            pass

    def update(self, dt, player_moving, mouse_dx, battery_pct):
        if not self.on or battery_pct <= 0:
            return
        self.target_sway_x = -mouse_dx * 2.0
        self.target_sway_y = 0.0
        if player_moving:
            self.target_sway_y += math.sin(pygame.time.get_ticks() * 0.01) * 6.0
        self.sway_x += (self.target_sway_x - self.sway_x) * min(1.0, dt * 10)
        self.sway_y += (self.target_sway_y - self.sway_y) * min(1.0, dt * 10)
        self.target_sway_x *= 0.9
        self.target_sway_y *= 0.9

    def brightness_at(self, screen_x, dist, player):
        if not player.flashlight_on or player.flashlight_battery <= 0:
            return 0.15
        beam_center_x = self.w // 2 + int(self.sway_x)
        dx = abs(screen_x - beam_center_x)
        max_dx = self.w * 0.35 * max(0.3, (1.0 - dist / 12.0))
        if dx > max_dx:
            return 0.15
        angular_falloff = max(0.0, 1.0 - (dx / max(1.0, max_dx)))
        dist_falloff = 1.0 / (1.0 + dist * 0.25)
        batt_factor = player.flashlight_battery / 100.0
        flicker = 1.0
        if player.flashlight_battery < 20:
            flicker = random.uniform(0.5, 1.1) if random.random() < 0.3 else 1.0
        intensity = 0.15 + 0.85 * angular_falloff * dist_falloff * batt_factor * flicker
        return max(0.15, min(1.0, intensity))

    def draw(self, surf, player):
        """Draw the darkness overlay (called ONCE per frame)."""
        if not player.flashlight_on or player.flashlight_battery <= 0:
            surf.blit(self.dark_off, (0, 0))
            return

        cx = int(self.w // 2 + self.sway_x)
        cy = int(self.h // 2 + player.pitch * self.h + self.sway_y)
        cx = max(0, min(self.w, cx))     # keep the 2w x 2h mask covering the screen
        cy = max(0, min(self.h, cy))
        pos = (cx - self.w, cy - self.h)

        flicker = player.flashlight_battery < 20 and random.random() < 0.3
        surf.blit(self.dark_mask, pos)
        if flicker:
            surf.blit(self.dark_flicker, (0, 0))
        else:
            surf.blit(self.glow_mask, pos, special_flags=pygame.BLEND_RGB_ADD)


class Renderer:
    """Raycasting-based pseudo-3D renderer."""

    def __init__(self, internal_surface, textures, weapon_sprites, enemy_sprites, pickup_sprites):
        self.surface = internal_surface
        self.w = INTERNAL_WIDTH
        self.h = INTERNAL_HEIGHT
        self.textures = textures
        self._wall_col_cache = {}
        self._wall_col_lit_cache = {}  # quantised scale+light buckets (bounded)
        for _tex in self.textures.values():  # pre-slice wall columns once at startup
            self._wall_columns(_tex)
        self.weapon_sprites = weapon_sprites
        self.enemy_sprites = enemy_sprites
        self.pickup_sprites = pickup_sprites
        self.crosshair = None
        self.clock = None
        self.flashlight = Flashlight(self.w, self.h)

        try:
            from anim_integration import get_enemy_animator
            self.enemy_animator = get_enemy_animator()
        except Exception:
            self.enemy_animator = None

        from shader_renderer import ShaderRenderer
        self.shader_renderer = ShaderRenderer(self.w, self.h)

        from animation_core import ParticleSystem, CameraShake
        self.physics_particles = ParticleSystem(400)
        self.camera_shake = CameraShake()
        
        # ─── Advanced Visual Enhancements ─────────────────────────────────────
        from visual_enhancements import DynamicLights, Fog, Grain, Grader, Particles
        self.dynamic_lights = DynamicLights()
        self.volumetric_fog = Fog()
        self.film_grain = Grain()
        self.color_grader = Grader()
        self.atmosphere_particles = Particles(max_p=150)

        # Wind system for tree/plant animation
        self.wind_time = 0.0
        self.wind_strength = 0.3
        self.wind_gust_timer = 0.0

        # Storm weather (weather_fx.py): three-layer rain with wind slant, ground splashes, mist,
        # lightning (flash + bolt + cloud glow) and the thunder that follows it.
        _low = getattr(_settings_mod, 'QUALITY_TIER', 'medium') == 'low'
        self.weather = WeatherFX(
            self.w, self.h, math.radians(FOV),
            rain=getattr(_settings_mod, 'ENABLE_RAIN', True),
            lightning=getattr(_settings_mod, 'ENABLE_LIGHTNING', True),
            rain_density=getattr(_settings_mod, 'RAIN_DENSITY', 1.0) * (0.6 if _low else 1.0),
            flash_strength=getattr(_settings_mod, 'LIGHTNING_FLASH_STRENGTH', 1.0))
        self.sunrise_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)

        # Precompute ray angles
        self.fov_rad = math.radians(FOV)
        self.half_fov = self.fov_rad / 2
        self.num_rays = NUM_RAYS
        self.ray_angles = []
        for i in range(self.num_rays):
            angle_offset = (i / self.num_rays - 0.5) * self.fov_rad
            self.ray_angles.append(angle_offset)
        # Cached ray vectors avoid rebuilding NumPy arrays every frame.
        self._ray_angle_array = np.asarray(self.ray_angles, dtype=np.float32)
        self._ray_cos = np.cos(self._ray_angle_array)
        self._ray_sin = np.sin(self._ray_angle_array)
        # float64 copies for the wall raycaster (same precision as the old scalar loop)
        self._ray_ang64 = np.asarray(self.ray_angles, dtype=np.float64)
        self._ray_cos64 = np.cos(self._ray_ang64)

        # Coarse spatial buckets avoid scanning the entire forest each frame.
        self._sprite_bucket_size = 8.0
        self._sprite_bucket_cache_key = None
        self._tree_buckets = {}
        self._plant_buckets = {}
        self._sprite_lit_cache = {}  # bounded cache of scaled+lit billboards

        # Z-buffer for sprite occlusion (one entry per ray)
        self.z_buffer = np.zeros(self.num_rays, dtype=np.float64)
        # screen column -> z-buffer index, so sprite depth tests are one numpy lookup
        self._col_to_ray = (np.arange(self.w) * self.num_rays // self.w).astype(np.int64)
        # numpy view of the tile grid for the vectorised raycaster (rebuilt when the map changes)
        self._grid_np = None
        self._grid_src = None
        self._grid_rev = -1
        # reusable full-screen overlay surfaces (allocated once, not every frame)
        self._flash_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA).convert_alpha()
        self._blood_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA).convert_alpha()
        # Depth-fog overlay: one pre-allocated alpha surface, reused every frame.
        # The fog colour comes from settings.FOG_COLOR; the alpha pattern is
        # rebuilt each frame from the z-buffer (per-column wall depth) blended
        # with a cached vertical bell curve (concentrates fog near the horizon).
        self._fog_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA).convert_alpha()
        # Pre-fill the RGB channels once; only the alpha channel is updated
        # per frame via pixels_alpha (the RGB never changes).
        self._fog_surf.fill((FOG_COLOR[0], FOG_COLOR[1], FOG_COLOR[2], 0))
        self._fog_vkey = None   # cache key for the vertical bell curve
        self._dbg_key = None
        self._dbg_surf = None
        self.hit_fx = []  # small blood / ectoplasm / spark particles spawned on enemy hits

        # Floor/ceiling cache & procedural forest assets
        from asset_generator import generate_tree_billboard, generate_undergrowth_sprite, generate_world_ground_texture
        # ── Procedural visual streaming ──────────────────────────────────
        # Tree billboards and undergrowth sprites are generated LAZILY:
        # a (species, variant) is only generated the first time that
        # species+variant enters the camera's visible region.  Generation
        # is fully seeded (deterministic), so evicted assets regenerate
        # pixel-identical when the player looks at that area again.
        # A small "active" set is kept so recently-seen variants do not
        # regenerate; when it overflows the least-recently-used variants
        # are dropped (bounded memory, no per-frame regeneration).
        self._generate_tree_billboard = generate_tree_billboard
        self._generate_undergrowth_sprite = generate_undergrowth_sprite
        self._tree_sprite_cache = {}   # (type, variant) -> surface  (bounded LRU)
        self._undergrowth_cache = {}  # type -> surface            (bounded LRU)
        self._TREE_SPRITE_VARIANTS = 5
        # 11 species x 5 variants = 55 max combinations; a cache of 24 thrashes
        # and regenerates ~12 billboards per frame (each costs ~1.3 ms).
        # 64 covers all combinations with headroom (~4 MB at 64x256x4 bytes).
        self._TREE_CACHE_LIMIT = 64
        self._UNDERGROWTH_CACHE_LIMIT = 16
        self._TREE_HEIGHT_MULT = {
            'balete': 4.5, 'mahogany': 5.25, 'bamboo': 4.25, 'dead': 3.75,
            'banana': 3.5, 'palm': 4.5, 'supernatural': 4.75,
            'akasya': 4.875, 'narra': 5.0, 'tree_fern': 3.125, 'strangler': 4.625,
        }
        # 25% taller than the original set: balete 3.6, mahogany 4.2, bamboo 3.4,
        # dead 3.0, banana 2.8, palm 3.6, supernatural 3.8, akasya 3.9,
        # narra 4.0, tree_fern 2.5, strangler 3.7.
        self.world_ground_tex = generate_world_ground_texture(GROUND_TEX_SIZE, GROUND_TEX_SIZE)
        self._ground_arr = pygame.surfarray.array3d(self.world_ground_tex)
        # Multipliers tint the shared procedural ground texture by map terrain.
        # IDs match GameMap.terrain_grid: forest, trail, village, swamp,
        # grove, limestone, shallow water.
        self._terrain_tint_lut = np.asarray([
            (0.72, 0.88, 0.70), (1.05, 0.88, 0.68),
            (0.96, 0.80, 0.64), (0.56, 0.72, 0.68),
            (0.68, 0.80, 0.66), (0.78, 0.77, 0.72),
            (0.48, 0.72, 0.82),
        ], dtype=np.float32)
        # Enhanced per-biome ground (terrain_gen.py).  The atlas bakes once and is
        # cached on disk; the biome map is rebuilt when the chapter's terrain_grid changes.
        self._terrain_atlas = None
        self._terrain_far = None
        self._terrain_maps = None
        self._terrain_maps_for = None
        self.frame_counter = 0

        self.floor_surf = pygame.Surface((self.w, self.h // 2)).convert()
        self._generate_floor_gradient()

        # Pre-generate and convert cloud + aurora surfaces at init so they
        # never allocate mid-frame and always use the fast SDL blitter.
        self._sky_fx_cache = {}
        for c_idx in range(6):
            alpha = max(30, 80 - c_idx * 15)
            cloud_surf = pygame.Surface((180, 40), pygame.SRCALPHA)
            pygame.draw.ellipse(cloud_surf, (40 + c_idx * 10, 45 + c_idx * 8, 60 + c_idx * 5, alpha), (0, 0, 180, 40))
            self._sky_fx_cache[('cloud', c_idx)] = cloud_surf.convert_alpha()
        for a_idx in range(3):
            aurora_w = 60 + a_idx * 20
            aurora_alpha = max(5, 25 - a_idx * 5)
            aurora_surf = pygame.Surface((aurora_w, 30), pygame.SRCALPHA)
            pygame.draw.ellipse(aurora_surf, (40, 80 + a_idx * 30, 100, aurora_alpha), (0, 0, aurora_w, 30))
            self._sky_fx_cache[('aurora', a_idx)] = aurora_surf.convert_alpha()

        # Weapon animation
        self.weapon_bob = 0
        self.weapon_recoil = 0
        self.muzzle_flash = 0
        self.bolo_swing_timer = 0.0   # >0 while the bolo slash is playing
        self.shotgun_fire_timer = 0.0  # >0 while the shotgun fire animation is playing
        self.revolver_fire_timer = 0.0

        # Screen effects
        self.screen_shake = 0

        # Precompute stars (260 stars, local Random(999))
        rng_stars = random.Random(999)
        self.stars = []
        for _ in range(260):
            s_az = rng_stars.uniform(0, math.pi * 2)
            s_el = rng_stars.uniform(0.04, 1.0)
            phase = rng_stars.uniform(0, math.pi * 2)
            big = rng_stars.random() < 0.15
            self.stars.append((s_az, s_el, phase, big))

        # Precompute moon surface (56 px disc with halo & craters)
        moon_size = 56
        moon_surf = pygame.Surface((moon_size, moon_size), pygame.SRCALPHA)
        for r in range(moon_size // 2, 12, -4):
            alpha = int(12 * (1.0 - r / (moon_size / 2)))
            pygame.draw.circle(moon_surf, (210, 225, 255, alpha), (moon_size // 2, moon_size // 2), r)
        pygame.draw.circle(moon_surf, (232, 238, 252), (moon_size // 2, moon_size // 2), 22)
        pygame.draw.circle(moon_surf, (190, 202, 225), (moon_size // 2 - 5, moon_size // 2 - 4), 7)
        pygame.draw.circle(moon_surf, (200, 210, 235), (moon_size // 2 + 7, moon_size // 2 + 6), 5)
        pygame.draw.circle(moon_surf, (210, 218, 240), (moon_size // 2 - 6, moon_size // 2 + 8), 4)
        self.moon_surf = moon_surf.convert_alpha()
        self.moon_size = moon_size

        self.vignette = self._generate_vignette()
        self.red_vig = self._generate_edge_surface((150, 0, 0), 230)

        # Particles (Fireflies, dust motes, spores)
        self.particles = []
        rng_p = random.Random(777)
        for _ in range(50):
            self.particles.append({
                'x': rng_p.uniform(0, self.w),
                'y': rng_p.uniform(0, self.h),
                'vx': rng_p.uniform(-0.5, 0.5),
                'vy': rng_p.uniform(-0.3, 0.3),
                'size': rng_p.uniform(1.0, 2.5),
                'phase': rng_p.uniform(0, math.pi * 2),
                'color': (rng_p.randint(180, 255), rng_p.randint(200, 255), rng_p.randint(100, 180)),
                'kind': 'firefly' if rng_p.random() < 0.4 else 'dust',
            })
        # Pre-rendered particle surfaces (cached per size) to avoid per-frame allocation.
        # Pre-build them at init so they're converted to display format for fast blits.
        self._particle_cache = {}
        for p in self.particles:
            psize = int(p['size'])
            key = (psize, p['color'])
            if key not in self._particle_cache:
                psurf = pygame.Surface((psize * 2, psize * 2), pygame.SRCALPHA)
                pygame.draw.circle(psurf, (*p['color'], 255), (psize, psize), psize)
                self._particle_cache[key] = psurf.convert_alpha()
        # _sky_fx_cache is already pre-built (clouds + auroras) above the star init.
        self._viewmodel_cache = {}   # scaled / rotated weapon surfaces

        # Debug overlay (F3)
        self.debug_mode = 1   # 0 = off, 1 = compact (default), 2 = full; F3 cycles
        self.fps_history = []
        self.frame_times = []  # For percentile tracking
        self.timings = {'rays': 0.0, 'sprites': 0.0, 'darkness': 0.0, 'post': 0.0, 'total': 0.0, 'animation': 0.0}
        self.dbg_font = pygame.font.SysFont('consolas', 10)

        self.debug_f4 = False          # raw scene: no darkness + markers on every entity
        self.last_console_print = 0.0
        self.level_enemy_total = 0     # set by main.py for the F3 panel

        # Performance tracking
        self._last_frame_time = pygame.time.get_ticks()
        
        # Per-frame sprite stats (shown on the F3 panel)
        self.stats = {'trees': 0, 'enemies_view': 0, 'pickups_view': 0, 'drawn': 0}

        # Emissive effects (eyes / halos) drawn after the darkness pass
        self._emissive = []
        self._glow_cache = {}

        # Heartbeat / danger
        self.heart_phase = 0.0
        self.danger = 0.0

        # Asset load failure / zero alpha / fully black warnings
        all_assets = []
        for name, tex in self.textures.items():
            all_assets.append((f"texture_{name}", tex))
        for name, spr in self.weapon_sprites.items():
            all_assets.append((f"weapon_{name}", spr))
        for etype, states in self.enemy_sprites.items():
            for st, spr in states.items():
                all_assets.append((f"enemy_{etype}_{st}", spr))
        for ptype, spr in self.pickup_sprites.items():
            all_assets.append((f"pickup_{ptype}", spr))
        for key, spr in self._tree_sprite_cache.items():
            all_assets.append((f"tree_{key[0]}_{key[1]}", spr))
        for utype, spr in self._undergrowth_cache.items():
            all_assets.append((f"undergrowth_{utype}", spr))

        for name, surf in all_assets:
            if surf is None:
                print(f"[WARNING] Asset failed to load / is None: {name}")
            else:
                try:
                    arr = pygame.surfarray.array3d(surf)
                    alpha_arr = pygame.surfarray.array_alpha(surf) if (surf.get_flags() & pygame.SRCALPHA) else None
                    if alpha_arr is not None and alpha_arr.sum() == 0:
                        print(f"[WARNING] Asset has zero alpha (fully transparent): {name}")
                    if arr.max() <= 5:
                        print(f"[WARNING] Asset is fully black: {name}")
                except Exception:
                    pass

        # Ward visual effects
        self.ward_effect_timer = 0
        self.ward_effect_type = None

    def emit_casing(self, x, y, vx, vy):
        if ENABLE_ANIMATIONS and ENABLE_PARTICLE_PHYSICS:
            try:
                self.physics_particles.emit(x, y, vx, vy, life=1.5, size=2, color=(220, 200, 100))
            except Exception:
                pass

    def emit_smoke(self, x, y, vx, vy):
        if ENABLE_ANIMATIONS and ENABLE_PARTICLE_PHYSICS:
            try:
                self.physics_particles.emit(x, y, vx, vy, life=0.8, size=4, color=(150, 150, 150))
            except Exception:
                pass

    def emit_sparks(self, x, y, count=10):
        if ENABLE_ANIMATIONS and ENABLE_PARTICLE_PHYSICS:
            try:
                for _ in range(count):
                    angle = random.uniform(0, math.pi * 2)
                    speed = random.uniform(50, 150)
                    self.physics_particles.emit(x, y, math.cos(angle)*speed, math.sin(angle)*speed, life=0.5, size=1, color=(255, 230, 100))
            except Exception:
                pass

    def emit_blood(self, x, y, count=15):
        if ENABLE_ANIMATIONS and ENABLE_PARTICLE_PHYSICS:
            try:
                for _ in range(count):
                    angle = random.uniform(-math.pi, 0)
                    speed = random.uniform(30, 120)
                    self.physics_particles.emit(x, y, math.cos(angle)*speed, math.sin(angle)*speed, life=1.2, size=2, color=(180, 20, 20))
            except Exception:
                pass

    # ─── Cached surfaces ──────────────────────────────────────────────────
    def _enhanced_terrain_ready(self, game_map):
        """True when the enhanced per-biome ground can be drawn for this map.

        Bakes/loads the texture atlas once and (re)builds the biome map whenever the
        map's terrain_grid changes (new chapter).  Any failure permanently falls back
        to the original floor so a terrain bug can never take the game down.
        """
        if self._terrain_atlas is False:
            return False
        grid = getattr(game_map, 'terrain_grid', None)
        if grid is None:
            return False
        if self._terrain_atlas is None:
            quality = getattr(_settings_mod, 'ACTIVE_QUALITY', {})
            if not (getattr(_settings_mod, 'ENHANCED_TERRAIN', True)
                    and quality.get('enable_enhanced_floor', True)):
                self._terrain_atlas = False
                return False
        try:
            import terrain_gen
            if self._terrain_atlas is None:
                from asset_generator import ASSET_DIR
                self._terrain_atlas, self._terrain_far = terrain_gen.load_or_bake_atlas(
                    os.path.join(ASSET_DIR, 'cache'),
                    int(getattr(_settings_mod, 'TERRAIN_TEX_SIZE', 512)),
                    int(getattr(_settings_mod, 'WORLD_SEED', 1337)))
            if self._terrain_maps_for is not grid:
                self._terrain_maps = terrain_gen.build_terrain_maps(
                    grid, int(getattr(_settings_mod, 'WORLD_SEED', 1337)))
                self._terrain_maps_for = grid
        except Exception as exc:                      # never let the ground crash the game
            print('[TERRAIN] enhanced ground disabled, using legacy floor:', exc)
            self._terrain_atlas = False
            return False
        return True

    def _generate_floor_gradient(self):
        """Generate gradient for floor rendering."""
        for y in range(self.h // 2):
            t = y / (self.h // 2)
            r = int(FLOOR_COLOR[0] * t * 0.8)
            g = int(FLOOR_COLOR[1] * t * 0.8)
            b = int(FLOOR_COLOR[2] * t * 0.8)
            pygame.draw.line(self.floor_surf, (r, g, b), (0, y), (self.w, y))

    def _generate_edge_surface(self, color, max_alpha):
        """Vignette-shaped surface: clear centre, `color` at `max_alpha` in the corners."""
        surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        surf.fill((color[0], color[1], color[2], 255))
        cx, cy = self.w // 2, self.h // 2
        max_dist = math.sqrt(cx * cx + cy * cy)
        inner_r = max_dist * 0.35
        y_indices, x_indices = np.ogrid[:self.h, :self.w]
        d = np.sqrt((x_indices - cx) ** 2 + (y_indices - cy) ** 2)
        t = np.clip((d - inner_r) / max(1.0, max_dist - inner_r), 0.0, 1.0)
        alpha_arr = (t ** 2) * max_alpha
        av = pygame.surfarray.pixels_alpha(surf)
        av[:, :] = alpha_arr.T.astype(np.uint8)
        del av
        return surf.convert_alpha()

    def _generate_vignette(self):
        """Generate a proper vignette overlay (clear center, alpha ~170 at corners)."""
        vig = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        cx, cy = self.w // 2, self.h // 2
        max_dist = math.sqrt(cx * cx + cy * cy)
        inner_r = max_dist * 0.35

        y_indices, x_indices = np.ogrid[:self.h, :self.w]
        dist_from_center = np.sqrt((x_indices - cx) ** 2 + (y_indices - cy) ** 2)

        alpha_arr = np.zeros((self.h, self.w), dtype=np.float32)
        mask = dist_from_center > inner_r
        t = (dist_from_center[mask] - inner_r) / max(1.0, max_dist - inner_r)
        alpha_arr[mask] = np.clip((t ** 2) * 170, 0, 170)

        alpha_view = pygame.surfarray.pixels_alpha(vig)
        alpha_view[:, :] = alpha_arr.T.astype(np.uint8)
        del alpha_view
        return vig.convert_alpha()

    def _glow_sprite(self, radius, color):
        """Cached soft round glow (RGB, meant for BLEND_RGB_ADD)."""
        radius = max(2, min(64, int(radius)))
        color = (int(color[0]), int(color[1]), int(color[2]))
        key = (radius, color)
        s = self._glow_cache.get(key)
        if s is None:
            size = radius * 2 + 1
            ys, xs = np.ogrid[-radius:radius + 1, -radius:radius + 1]
            d = np.sqrt(xs * xs + ys * ys) / float(radius)
            f = np.clip(1.0 - d, 0.0, 1.0) ** 2
            arr = np.zeros((size, size, 3), dtype=np.uint8)
            for c in range(3):
                arr[:, :, c] = (f * color[c]).astype(np.uint8)
            s = pygame.Surface((size, size))
            pygame.surfarray.blit_array(s, arr)
            s = s.convert()  # display-format for fast additive blits
            self._glow_cache[key] = s
        return s

    # ─── Frame ────────────────────────────────────────────────────────────
    def render_frame(self, player, game_map, enemies, effects, dt, sunrise_progress=0.0):
        """Render a complete frame with correct pipeline order."""
        t_anim_start = pygame.time.get_ticks()
        
        # Update animation systems
        if ENABLE_ANIMATIONS and ENABLE_PARTICLE_PHYSICS:
            try:
                self.physics_particles.update(dt)
            except Exception:
                pass
        if ENABLE_ANIMATIONS and ENABLE_CAMERA_SHAKE:
            shx, shy = self.camera_shake.update(dt)
            if shx != 0 or shy != 0:
                self.screen_shake = max(self.screen_shake, max(abs(shx), abs(shy)))
        if ENABLE_ANIMATIONS and getattr(self, 'enemy_animator', None) is not None:
            self.enemy_animator.update_all(enemies, dt)
        
        # Update wind system for natural tree/plant movement
        if ENABLE_ANIMATIONS and ENABLE_ENV_ANIM:
            self.wind_time += dt
            self.wind_gust_timer -= dt
            if self.wind_gust_timer <= 0:
                self.wind_gust_timer = random.uniform(3.0, 8.0)
                self.wind_strength = random.uniform(0.2, 0.6)
        
        self.timings['animation'] = pygame.time.get_ticks() - t_anim_start

        self.surface.fill(SKY_COLOR)
        self.frame_counter += 1
        self._emissive = []
        # Single time query per frame; reused everywhere instead of 15+ calls.
        t_ticks = pygame.time.get_ticks()

        pitch_offset = int(player.pitch * self.h)
        half_h = self.h // 2
        horizon_y = max(0, half_h + pitch_offset)

        # 1. Sky Gradient (SKY_COLOR to blue-green haze (24,34,42))
        # One vectorised write instead of ~180 draw.line calls per frame.
        sky_rows = min(horizon_y, self.h)
        if sky_rows > 0:
            t = np.arange(sky_rows, dtype=np.float32) / max(1, horizon_y)
            sky_cols = np.empty((sky_rows, 3), dtype=np.uint8)
            for c, haze in enumerate((24, 34, 42)):
                sky_cols[:, c] = (SKY_COLOR[c] * (1 - t) + haze * t).astype(np.uint8)
            sky_arr = pygame.surfarray.pixels3d(self.surface)
            sky_arr[:, :sky_rows, :] = sky_cols[None, :, :]
            del sky_arr

        if horizon_y > 0:
            # Stars (260 stars, local Random(999))
            # Lock once for the whole loop: set_at() locks/unlocks per call,
            # which is the slow path.  One lock amortises it across all stars.
            self.surface.lock()
            if sunrise_progress < 0.98:
                for s_az, s_el, phase, big in self.stars:
                    az_diff = s_az - player.angle
                    while az_diff > math.pi: az_diff -= 2 * math.pi
                    while az_diff < -math.pi: az_diff += 2 * math.pi
                    if abs(az_diff) < self.half_fov + 0.3:
                        sx = int(self.w // 2 + (az_diff / self.fov_rad) * self.w)
                        sy = int(horizon_y - s_el * (0.8 * self.h))
                        if 0 <= sx < self.w and 0 <= sy < horizon_y:
                            twinkle = int(185 + 55 * math.sin(t_ticks * 0.003 + phase))
                            col = (twinkle, twinkle, min(255, twinkle + 30))
                            if big:
                                pygame.draw.rect(self.surface, col, (sx, sy, 2, 2))
                            else:
                                self.surface.set_at((sx, sy), col)
            self.surface.unlock()

            # Moon (fixed world azimuth pi/4, elevation 0.42)
            moon_world_az = math.pi / 4
            moon_world_el = 0.42
            az_diff = moon_world_az - player.angle
            while az_diff > math.pi: az_diff -= 2 * math.pi
            while az_diff < -math.pi: az_diff += 2 * math.pi
            moon_screen_x = int(self.w // 2 + (az_diff / self.fov_rad) * self.w)
            moon_screen_y = int(horizon_y - moon_world_el * (0.8 * self.h))

            if sunrise_progress < 0.82 and -80 <= moon_screen_x <= self.w + 80 and 0 <= moon_screen_y <= horizon_y + 40:
                self.surface.blit(self.moon_surf, (moon_screen_x - self.moon_size // 2, moon_screen_y - self.moon_size // 2))

            # Enhanced atmospheric clouds with layered depth
            cloud_t = t_ticks * 0.0008
            for c_idx in range(6):
                cx = int((c_idx * 180 + cloud_t * (25 if c_idx < 4 else 15)) % (self.w + 300) - 150)
                cy = int(horizon_y * (0.15 + c_idx * 0.12))
                if 0 <= cy < horizon_y:
                    # Surfaces are pre-built and converted at init time.
                    self.surface.blit(self._sky_fx_cache[('cloud', c_idx)], (cx, cy))

            # Subtle aurora borealis effect at horizon
            if ENABLE_ANIMATIONS and ENABLE_ENV_ANIM:
                aurora_t = t_ticks * 0.0003
                for a_idx in range(3):
                    aurora_x = int((a_idx * 250 + aurora_t * 50) % (self.w + 200) - 100)
                    self.surface.blit(self._sky_fx_cache[('aurora', a_idx)],
                                      (aurora_x, max(5, horizon_y - 50 + a_idx * 10)))

        # Lightning glow + bolt sit in the sky, so terrain and trees drawn next cut across them.
        self.weather.draw_sky(self.surface, player.angle, horizon_y)

        # 2. Floor with perspective texture mapping of self.world_ground_tex and exp-squared fog
        floor_h = self.h - horizon_y
        if floor_h > 0 and hasattr(self, '_ground_arr'):
            mist_phase = t_ticks * 0.0003
            arr_3d = pygame.surfarray.pixels3d(self.surface)
            px, py, pa = player.x, player.y, player.angle

            cos_pa = math.cos(pa)
            sin_pa = math.sin(pa)
            ray_dx = self._ray_cos * cos_pa - self._ray_sin * sin_pa
            ray_dy = self._ray_sin * cos_pa + self._ray_cos * sin_pa

            # Whole floor in one vectorised pass (see floor_fast.py).
            if self._enhanced_terrain_ready(game_map):
                fill_floor_terrain(arr_3d, self._terrain_atlas, self._terrain_far,
                                   self._terrain_maps['packed'], self._terrain_maps['fine'],
                                   game_map.width, game_map.height,
                                   px, py, ray_dx, ray_dy,
                                   self.h, half_h, horizon_y, pitch_offset, mist_phase,
                                   time_s=t_ticks * 0.001,
                                   brightness=getattr(_settings_mod, 'TERRAIN_BRIGHTNESS', 1.0),
                                   far_dist=getattr(_settings_mod, 'TERRAIN_FAR_DIST', 12.0))
            else:
                fill_floor(arr_3d, self._ground_arr, self._terrain_tint_lut,
                           getattr(game_map, 'terrain_grid', None),
                           game_map.width, game_map.height,
                           px, py, ray_dx, ray_dy,
                           self.h, half_h, horizon_y, pitch_offset, mist_phase)
            del arr_3d

        # 3. Cast rays and draw walls (also fills the z-buffer)
        t_rays = pygame.time.get_ticks()
        self._cast_rays(player, game_map)
        self.timings['rays'] = pygame.time.get_ticks() - t_rays

        # 4. Trees + undergrowth + enemies + pickups: ONE depth-sorted pass
        self._draw_world_sprites(player, enemies, game_map)

        # 4b. Atmospheric depth-fog: drawn after sprites so distant trees/walls
        # get hazed, but before the flashlight so the beam cuts through it.
        if not self.debug_f4:
            self._draw_depth_fog(player, game_map)

        # 5. Darkness + flashlight (ONCE).  F4 shows the raw, unlit scene.
        self.flashlight.update(dt, abs(player.bob_amount) > 0.5, getattr(player, '_last_mouse_dx', 0.0), player.flashlight_battery)
        if not self.debug_f4:
            self.flashlight.draw(self.surface, player)

        # 6. Glowing eyes / halos: drawn AFTER darkness so they show in the dark
        self._draw_emissive()
        self._update_draw_hit_fx(dt)

        # 7. Particles (fireflies / dust / spores)
        if ENABLE_PARTICLES:
            _particle_cache = self._particle_cache  # local ref avoids attribute lookups
            _w = self.w
            _h = self.h
            for p in self.particles:
                p['x'] = (p['x'] + p['vx']) % _w
                p['y'] = (p['y'] + p['vy']) % _h
                p['phase'] += dt * 2
                # Dust motes are dimmer and slower-pulsing than fireflies
                if p.get('kind') == 'dust':
                    alpha = int(abs(math.sin(p['phase'] * 0.5)) * 60)
                else:
                    alpha = int(abs(math.sin(p['phase'])) * 180)
                if alpha < 5:
                    continue
                psurf = _particle_cache.get((int(p['size']), p['color']))
                if psurf is not None:
                    psurf.set_alpha(alpha)
                    self.surface.blit(psurf, (int(p['x']), int(p['y'])))

        if ENABLE_ANIMATIONS and ENABLE_PARTICLE_PHYSICS:
            try:
                self.physics_particles.draw(self.surface)
            except Exception:
                pass

        # 8. Vignette, low-HP / sanity blood vignette, enemy-proximity horror
        self.surface.blit(self.vignette, (0, 0))
        self._danger_effects(player, enemies, dt)
        if player.health < 35 or (ENABLE_SANITY and player.sanity < 30):
            urgency = max((35 - player.health) / 35.0, (30 - player.sanity) / 30.0)
            urgency = max(0.0, min(1.0, urgency))
            blood_vig = self._blood_surf
            blood_vig.fill((0, 0, 0, 0))
            alpha = int(urgency * 120 + math.sin(pygame.time.get_ticks() * 0.006) * 30)
            pygame.draw.rect(blood_vig, (180, 0, 0, max(0, min(200, alpha))), (0, 0, self.w, self.h), max(1, int(20 * urgency)))
            self.surface.blit(blood_vig, (0, 0))

        # Ward effects
        if self.ward_effect_timer > 0:
            self._draw_ward_effect(dt)

        # Damage flash
        if player.damage_flash > 0:
            flash = self._flash_surf
            alpha = max(0, min(255, int(player.damage_flash * 120)))
            flash.fill((200, 0, 0, alpha))
            self.surface.blit(flash, (0, 0))

        # Muzzle flash
        if self.muzzle_flash > 0:
            self._draw_muzzle_flash()
            self.muzzle_flash -= dt * 8

        # Rain and sunrise are composited before the viewmodel so weapon/hands stay crisp.
        self._draw_rain_and_sunrise(dt, sunrise_progress, horizon_y)

        # Draw player viewmodel (hands, sleeves, weapon)
        self._draw_player_viewmodel(player, dt)

        # Lightning lights up everything, hands and weapon included, so it goes on last.
        self.weather.draw_flash(self.surface)

        # Draw crosshair
        if self.crosshair:
            cx = self.w // 2 - self.crosshair.get_width() // 2
            cy = self.h // 2 - self.crosshair.get_height() // 2
            self.surface.blit(self.crosshair, (cx, cy))

        # F3 Debug Overlay
        self._draw_debug_overlay(player, game_map, enemies)

        # Screen shake (triggered by hits / nearby enemies)
        if self.screen_shake > 0.3:
            s = int(self.screen_shake)
            if s > 0 and self.w > s * 2 and self.h > s * 2:
                self.surface.scroll(random.randint(-s, s), random.randint(-s, s))
            self.screen_shake = max(0.0, self.screen_shake - dt * 20)

    def update_weather(self, player, dt, sunrise_progress):
        """Advance rain and lightning one played frame (the game loop skips this while paused)
        and play any thunder that has just arrived."""
        events = self.weather.update(dt, sunrise_progress, player.angle, player.pitch,
                                     self.wind_strength)
        for ev in events:
            try:
                from audio_synth import audio_mgr
                audio_mgr.play_thunder(ev['kind'], ev['volume'], ev['pan'])
            except Exception:
                pass
            if ev['shake'] > 0:
                self.trigger_screen_shake(ev['shake'])

    def _draw_rain_and_sunrise(self, dt, sunrise_progress, horizon_y=None):
        """Draw the storm's rain and a gradual warm dawn."""
        progress = max(0.0, min(1.0, sunrise_progress))
        if horizon_y is None:
            horizon_y = self.h // 2
        # Rain (with mist and ground splashes) eases out as daylight arrives.  A splash is
        # hidden when a wall is closer than the ground point it lands on.
        self.weather.draw_rain(self.surface, horizon_y, self._col_visible)
        # Slow, cinematic exposure shift: cold blue night -> warm golden dawn.
        if progress > 0.0:
            dawn_alpha = int(185 * (progress ** 1.35))
            self.sunrise_surf.fill((255, 190, 125, dawn_alpha))
            self.surface.blit(self.sunrise_surf, (0, 0))

    # ─── Horror feedback ──────────────────────────────────────────────────
    def _danger_effects(self, player, enemies, dt):
        """Red pulsing vignette + heartbeat + shake when an enemy is close."""
        nearest = None
        for e in enemies:
            if not getattr(e, 'alive', True):
                continue
            d = math.hypot(e.x - player.x, e.y - player.y)
            if nearest is None or d < nearest:
                nearest = d
        if nearest is None or nearest >= DANGER_RANGE:
            self.danger = max(0.0, self.danger - dt * 1.5)
        else:
            target = 1.0 - nearest / DANGER_RANGE
            self.danger += (target - self.danger) * min(1.0, dt * 6)
        if self.danger <= 0.02:
            return
        bpm = 60.0 + 110.0 * self.danger
        self.heart_phase += dt * (bpm / 60.0) * 2.0 * math.pi
        pulse = max(0.0, math.sin(self.heart_phase)) ** 6
        a = int(255 * self.danger * (0.35 + 0.65 * pulse))
        self.red_vig.set_alpha(max(0, min(255, a)))
        self.surface.blit(self.red_vig, (0, 0))
        if self.danger > 0.6:
            self.screen_shake = max(self.screen_shake, 1.0 + 1.5 * (self.danger - 0.6))

    def _draw_emissive(self):
        """Draw eye glows and pickup halos on top of the darkness overlay."""
        for kind, x, y, radius, color in self._emissive:
            if x < -80 or x > self.w + 80 or y < -80 or y > self.h + 80:
                continue
            g = self._glow_sprite(radius, color)
            self.surface.blit(g, (int(x) - g.get_width() // 2, int(y) - g.get_height() // 2),
                              special_flags=pygame.BLEND_RGB_ADD)
            if kind == 'eye':
                core = max(1, int(radius * 0.32))
                pygame.draw.circle(self.surface, (255, 240, 235), (int(x), int(y)), core)

    # ─── Debug overlay ────────────────────────────────────────────────────
    def _draw_debug_overlay(self, player, game_map, enemies):
        if not self.debug_mode:
            return
        font = self.dbg_font
        fps = 0.0
        if self.clock:
            try:
                curr_fps = self.clock.get_fps()
                self.fps_history.append(curr_fps)
                if len(self.fps_history) > 30:
                    self.fps_history.pop(0)
                fps = sum(self.fps_history) / len(self.fps_history)
            except Exception:
                pass
        pickups = getattr(game_map, 'pickups', [])
        pickups_active = sum(1 for p in pickups if p.get('active', True))
        nearest = None
        enemies = [e for e in enemies if e.alive]
        for e in enemies:
            d = math.hypot(e.x - player.x, e.y - player.y)
            if nearest is None or d < nearest:
                nearest = d

        has_warn = bool(getattr(game_map, 'validation_errors', None))
        if self.debug_mode == 1:
            # Compact: two short lines in the corner (F3 for the full readout)
            near = f" near {nearest:.0f}" if nearest is not None else ""
            lines = [
                f"{BUILD_VERSION.replace('BUILD ', '')}  {fps:.0f}fps",
                f"({int(player.x)},{int(player.y)}) EN {len(enemies)}/{self.level_enemy_total}{near}"
                f"  DNG {self.danger:.1f}" + ("  MAP WARN" if has_warn else ""),
            ]
            self._blit_debug_lines(lines, font, warn_idx=1 if has_warn else None)
            return

        lines = [
            f"DEBUG (F3 cycles)  F4 = raw scene",
            f"{BUILD_VERSION}",
            f"Chapter: {getattr(game_map, 'chapter_num', 1)}",
            f"Player Tile: ({int(player.x)}, {int(player.y)}) | Pos: ({player.x:.2f}, {player.y:.2f})",
            f"Enemies alive/total: {len(enemies)}/{self.level_enemy_total}"
            + (f" | nearest {nearest:.1f}" if nearest is not None else ""),
            f"Pickups active: {pickups_active} | Trees: {len(getattr(game_map, 'trees', []))}",
            f"In view -> enemies:{self.stats['enemies_view']} pickups:{self.stats['pickups_view']} drawn:{self.stats['drawn']}",
            f"Danger: {self.danger:.2f}",
            f"Anim timing: {self.timings.get('animation', 0.0):.1f}ms | Particles: {self.physics_particles.count}",
            f"FPS (30f avg): {fps:.1f}",
        ]
        if hasattr(game_map, 'validation_errors') and game_map.validation_errors:
            lines.append(f"Validation Warnings ({len(game_map.validation_errors)}):")
            for err in game_map.validation_errors[:3]:
                lines.append(f"  - {err}")
        else:
            lines.append("Map Validation: OK (Pass)")

        self._blit_debug_lines(lines, font)

    def _blit_debug_lines(self, lines, font, warn_idx=None):
        """Draw debug text top-left on a translucent backing so it stays readable but small.

        The composite is cached and only rebuilt when the text changes.
        """
        key = (tuple(lines), warn_idx)
        if key != self._dbg_key:
            step = font.get_linesize()
            rendered = []
            for idx, line in enumerate(lines):
                if idx == warn_idx or "Warnings" in line:
                    col = (255, 100, 100)
                elif "OK" in line or idx == 0:
                    col = (0, 255, 100)
                else:
                    col = (220, 220, 220)
                rendered.append(font.render(line, True, col))
            w = max(t.get_width() for t in rendered) + 8
            surf = pygame.Surface((w + 4, step * len(rendered) + 4), pygame.SRCALPHA)
            surf.fill((0, 0, 0, 120), (0, 0, w, step * len(rendered) + 4))
            for idx, txt in enumerate(rendered):
                surf.blit(txt, (4, 2 + idx * step))
            self._dbg_key = key
            self._dbg_surf = surf
        self.surface.blit(self._dbg_surf, (4, 4))

    # ─── Walls ────────────────────────────────────────────────────────────
    def _grid_array(self, game_map):
        """int32 numpy view of the tile grid, rebuilt only when the map changes."""
        grid = game_map.grid
        rev = getattr(game_map, 'grid_rev', 0)
        if self._grid_np is None or grid is not self._grid_src or rev != self._grid_rev:
            self._grid_np = np.asarray(grid, dtype=np.int32)
            self._grid_src = grid
            self._grid_rev = rev
        return self._grid_np

    def _cast_rays(self, player, game_map):
        """Cast rays for wall rendering (all rays walk the grid together in numpy)."""
        px, py = player.x, player.y
        pitch_offset = int(player.pitch * self.h)
        far = float(MAX_DEPTH) + 1.0
        h = self.h

        ang = player.angle + self._ray_ang64
        dist, tile, frac, side, hit = cast_rays(
            self._grid_array(game_map), game_map.width, game_map.height,
            px, py, np.cos(ang), np.sin(ang), MAX_DEPTH, EMPTY)

        # Fish-eye correction + z-buffer. Rays that hit nothing within MAX_DEPTH
        # draw no wall and never hide a sprite.
        corrected = dist * self._ray_cos64
        seen = hit & (dist < MAX_DEPTH)
        zb = self.z_buffer
        zb[:] = far
        zb[seen] = corrected[seen]

        drawable = seen & (corrected >= 0.01)
        if not drawable.any():
            return

        # Per-ray wall geometry and lighting buckets, computed for all rays at once.
        safe = np.maximum(corrected, 1e-9)
        wall_h = np.minimum((WALL_HEIGHT_SCALE / (safe * TILE_SIZE)).astype(np.int64), h * 3)
        draw_start = h // 2 - wall_h // 2 + pitch_offset
        # Quantised scale + lighting buckets: the same (tex, column, height
        # bucket, light bucket, face) reuses a cached surface, so we avoid 640
        # pygame.transform.scale calls + full-column fills per frame.
        wh_q = np.maximum(4, (wall_h + 3) // 4 * 4)
        shade = np.maximum(0.15, 1.0 - corrected / MAX_DEPTH)
        dark_a = np.minimum(255, ((1.0 - shade) * 220).astype(np.int64) + np.where(side == 1, 35, 0))
        v_q = np.minimum(255, (255 - dark_a + 8) // 16 * 16)

        cols_idx = np.flatnonzero(drawable).tolist()
        tiles = tile.tolist()
        fracs = frac.tolist()
        starts = draw_start.tolist()
        whs = wh_q.tolist()
        vqs = v_q.tolist()
        sides = side.tolist()
        dists = corrected.tolist()
        ends = (draw_start + wall_h).tolist()

        cache = self._wall_col_lit_cache
        tex_for = {}
        blits = []
        for i in cols_idx:
            wt = tiles[i]
            entry = tex_for.get(wt)
            if entry is None:
                tex = self._get_wall_texture(wt)
                entry = (tex, self._wall_columns(tex) if tex else None)
                tex_for[wt] = entry
            tex, cols = entry
            ds = starts[i]
            if tex:
                y0 = ds if ds > 0 else 0
                if y0 >= h:
                    continue
                ncols = len(cols)
                tex_x = int(fracs[i] * ncols) % ncols
                wq = whs[i]
                lit_key = (id(tex), tex_x, wq, vqs[i], sides[i])
                shaded = cache.get(lit_key)
                if shaded is None:
                    v = vqs[i]
                    shaded = pygame.transform.scale(cols[tex_x], (1, wq))
                    shaded.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
                    shaded = shaded.convert()  # display-format for fast blits
                    cache[lit_key] = shaded
                    if len(cache) > 8192:
                        cache.clear()
                blits.append((shaded, (i, y0), (0, y0 - ds, 1, min(wq, h - y0))))
            else:
                # Fallback solid color
                if ds < h and ends[i] > 0:
                    color = self._get_wall_color(wt, dists[i])
                    pygame.draw.line(self.surface, color, (i, max(0, ds)), (i, min(h, ends[i])))
        if blits:
            self.surface.blits(blits, False)

    def _wall_columns(self, tex):
        """Return the 1px-wide column subsurfaces of a wall texture (sliced once, zero-copy)."""
        cols = self._wall_col_cache.get(id(tex))
        if cols is None:
            h = tex.get_height()
            cols = [tex.subsurface((x, 0, 1, h)) for x in range(tex.get_width())]
            self._wall_col_cache[id(tex)] = cols
        return cols

    def _draw_depth_fog(self, player, game_map):
        """Subtle atmospheric depth-fog overlay.

        Combines two depth cues into one cheap alpha blit:

        1. **Per-column depth** from the z-buffer: each screen column's wall
           distance maps to a fog alpha (0 up close, max at FOG_FAR).  Columns
           where no wall was hit stay at the far-distance alpha, so open sky
           gaps and distant tree lines get a natural haze.

        2. **Vertical bell curve** centered on the horizon: fog concentrates
           where distant geometry appears (near the horizon), tapering to
           zero at the top and bottom of the screen.  The curve is cached and
           only rebuilt when the horizon shifts.

        The result is written to a pre-allocated alpha surface (RGB set once
        at init, only the alpha channel is updated per frame) and blitted
        with a normal alpha blend.  The flashlight pass runs *after* this, so
        the beam naturally cuts through the fog.

        Cost: one numpy outer product + one alpha-channel write per frame.
        No per-pixel Python loops, no surface allocations.
        """
        if not getattr(_settings_mod, 'ENABLE_FOG', True):
            return

        h = self.h
        w = self.w
        pitch_offset = int(player.pitch * h)
        horizon = h // 2 + pitch_offset

        # ── Per-column fog alpha from the z-buffer ────────────────────────
        # z_buffer has one entry per ray; map screen columns to ray indices.
        zb = self.z_buffer
        col_depth = zb[self._col_to_ray]      # (w,) float64 in tile units

        # Normalise to [0, 1]:  0 at FOG_NEAR (clear), 1 at FOG_FAR (max fog).
        # Columns where no wall was hit (z == MAX_DEPTH+1) map to 1.0.
        t = np.clip((col_depth - FOG_NEAR) / max(0.1, FOG_FAR - FOG_NEAR), 0.0, 1.0)
        # Smooth curve so fog ramps gently, not a hard step.
        col_alpha = (t * t * (3.0 - 2.0 * t)).astype(np.float32)  # smoothstep

        # ── Vertical bell curve (cached, rebuilt only when horizon moves) ─
        vkey = horizon
        v_profile = None
        if self._fog_vkey == vkey:
            v_profile = self._fog_vcurve
        if v_profile is None:
            ys = np.arange(h, dtype=np.float32)
            # Gaussian centred on the horizon, sigma ≈ 0.22 * h.
            sigma = max(1.0, h * 0.22)
            dy = ys - float(horizon)
            v_profile = np.exp(-(dy * dy) / (2.0 * sigma * sigma))
            self._fog_vcurve = v_profile
            self._fog_vkey = vkey

        # ── Combine: outer product of (rows,) × (cols,) → (h, w) ──────────
        # Convert to the alpha value, clipped to FOG_MAX_ALPHA.
        fog_alpha = (v_profile[:, None] * col_alpha[None, :]) * FOG_MAX_ALPHA
        fog_alpha = np.clip(fog_alpha, 0, 255).astype(np.uint8)   # (h, w)

        # ── Write to the pre-allocated surface's alpha channel ────────────
        # pygame surfarray uses (width, height) ordering, so transpose.
        av = pygame.surfarray.pixels_alpha(self._fog_surf)
        av[:, :] = fog_alpha.T
        del av

        self.surface.blit(self._fog_surf, (0, 0))

    def _dda_cast(self, px, py, cos_a, sin_a, game_map):
        """Digital Differential Analyzer raycasting. Returns (dist, wall_type, hit_frac, side)."""
        # Determine step direction
        if cos_a == 0:
            cos_a = 0.00001
        if sin_a == 0:
            sin_a = 0.00001

        x_step = 1 if cos_a > 0 else -1
        y_step = 1 if sin_a > 0 else -1

        # Initial distances to grid lines
        map_x = int(px)
        map_y = int(py)

        if cos_a > 0:
            x_dist = (map_x + 1 - px) / cos_a
        else:
            x_dist = (map_x - px) / cos_a

        if sin_a > 0:
            y_dist = (map_y + 1 - py) / sin_a
        else:
            y_dist = (map_y - py) / sin_a

        dx = abs(1 / cos_a)
        dy = abs(1 / sin_a)

        hit = False
        side = 0  # 0 = vertical wall (x), 1 = horizontal wall (y)
        wall_type = WALL_STONE

        for _ in range(MAX_DEPTH * 4):
            # Past view distance nothing can be drawn: stop instead of walking
            # the grid out to 4x MAX_DEPTH on rays that hit nothing.
            if (x_dist if x_dist < y_dist else y_dist) > MAX_DEPTH:
                break
            if x_dist < y_dist:
                x_dist += dx
                map_x += x_step
                side = 0
            else:
                y_dist += dy
                map_y += y_step
                side = 1

            if map_x < 0 or map_x >= game_map.width or map_y < 0 or map_y >= game_map.height:
                break

            tile = game_map.grid[map_y][map_x]
            if tile != EMPTY:
                wall_type = tile
                hit = True
                break

        if not hit:
            return MAX_DEPTH, WALL_STONE, 0, 0

        # Calculate exact distance and texture coordinate
        if side == 0:
            dist = (map_x - px + (1 - x_step) / 2) / cos_a
            hit_y = py + dist * sin_a
            hit_frac = hit_y - int(hit_y)
        else:
            dist = (map_y - py + (1 - y_step) / 2) / sin_a
            hit_x = px + dist * cos_a
            hit_frac = hit_x - int(hit_x)

        if dist < 0:
            dist = 0.01

        return dist, wall_type, hit_frac, side

    def _get_wall_texture(self, wall_type):
        """Get texture for wall type."""
        tex_map = {
            WALL_STONE: 'stone',
            WALL_WOOD: 'wood',
            WALL_BAMBOO: 'bamboo',
            WALL_BALETE: 'balete',
            DOOR: 'door',
        }
        name = tex_map.get(wall_type)
        if name and name in self.textures:
            return self.textures[name]
        return None

    def _get_wall_color(self, wall_type, dist):
        """Fallback wall color."""
        shade = max(0.15, 1.0 - dist / MAX_DEPTH)
        colors = {
            WALL_STONE: (70, 55, 40),
            WALL_WOOD: (90, 60, 30),
            WALL_BAMBOO: (80, 110, 50),
            WALL_BALETE: (50, 45, 30),
            DOOR: (80, 50, 25),
        }
        base = colors.get(wall_type, (60, 60, 60))
        return tuple(int(c * shade) for c in base)

    # ─── Sprites (trees, undergrowth, enemies, pickups) ───────────────────
    def _unit_h(self, dist):
        """Pixel height of a one-tile wall at this distance (same formula as the walls)."""
        h = WALL_HEIGHT_SCALE / (max(dist, 0.05) * TILE_SIZE)
        return min(h, self.h * 3.0)

    @staticmethod
    def _norm_angle(a):
        while a > math.pi:
            a -= 2 * math.pi
        while a < -math.pi:
            a += 2 * math.pi
        return a

    def _blit_zbuf(self, img, x, y, dist):
        """Blit img at (x, y); each screen column is hidden only by a CLOSER wall."""
        iw, ih = img.get_size()
        x0 = max(0, x)
        x1 = min(self.w, x + iw)
        if x1 <= x0:
            return 0
        runs = visible_runs(self.z_buffer, self._col_to_ray, x0, x1, dist)
        if not runs:
            return 0
        surface = self.surface
        if len(runs) == 1:
            a, b = runs[0]
            surface.blit(img, (a, y), (a - x, 0, b - a, ih))
            return b - a
        surface.blits([(img, (a, y), (a - x, 0, b - a, ih)) for a, b in runs], False)
        return sum(b - a for a, b in runs)

    def _col_visible(self, col, dist):
        if col < 0 or col >= self.w:
            return False
        return bool(self.z_buffer[self._col_to_ray[col]] > dist)

    def _light_sprite(self, img, dist):
        """Distance-darken a sprite WITHOUT touching its alpha channel."""
        shade = max(MIN_SPRITE_LIGHT, 1.0 - 0.55 * min(1.0, dist / max(1.0, float(MAX_DEPTH))))
        v = int(255 * shade)
        img.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
        return img

    # ─── Procedural visual streaming (lazy, bounded, deterministic) ─────
    def _tree_sprite(self, ttype, variant_idx):
        """Return the billboard for (species, variant), generating it only
        on first use.  Deterministic seed => re-generates identically after
        eviction.  Bounded LRU so memory stays capped."""
        key = (ttype, variant_idx)
        img = self._tree_sprite_cache.get(key)
        if img is None:
            img = self._generate_tree_billboard(ttype, 64, 256, seed=42 + variant_idx * 333)
            img = img.convert_alpha()  # display-format for fast per-frame blits
            self._tree_sprite_cache[key] = img
            while len(self._tree_sprite_cache) > self._TREE_CACHE_LIMIT:
                self._tree_sprite_cache.pop(next(iter(self._tree_sprite_cache)))
        else:
            # refresh LRU position
            self._tree_sprite_cache[key] = self._tree_sprite_cache.pop(key)
        return img

    def _undergrowth_sprite(self, ptype):
        """Same lazy/bounded pattern for environment decorations."""
        img = self._undergrowth_cache.get(ptype)
        if img is None:
            img = self._generate_undergrowth_sprite(ptype, 32, 32)
            img = img.convert_alpha()  # display-format for fast per-frame blits
            self._undergrowth_cache[ptype] = img
            while len(self._undergrowth_cache) > self._UNDERGROWTH_CACHE_LIMIT:
                self._undergrowth_cache.pop(next(iter(self._undergrowth_cache)))
        else:
            self._undergrowth_cache[ptype] = self._undergrowth_cache.pop(ptype)
        return img

    def _lit_sprite(self, img, sw, sh, dist):
        """Cached scaled+distance-lit surface.  Sizes are quantised to 4px
        buckets and light values to 1/32 steps, so unchanged sprites never
        pay the pygame.transform.scale + full-surface lighting cost again."""
        qsw = max(1, (sw + 3) // 4 * 4)
        qsh = max(1, (sh + 3) // 4 * 4)
        shade = max(MIN_SPRITE_LIGHT, 1.0 - 0.55 * min(1.0, dist / max(1.0, float(MAX_DEPTH))))
        v = int(255 * shade)
        v = min(255, (v + 8) // 16 * 16)  # quantise light bucket
        key = (id(img), qsw, qsh, v)
        cached = self._sprite_lit_cache.get(key)
        if cached is not None:
            self._sprite_lit_cache[key] = self._sprite_lit_cache.pop(key)  # LRU refresh
            return cached, qsw, qsh
        scaled = pygame.transform.scale(img, (qsw, qsh))
        scaled.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
        scaled = scaled.convert_alpha()  # display-format for fast per-frame blits
        self._sprite_lit_cache[key] = scaled
        if len(self._sprite_lit_cache) > 600:  # bounded: no unbounded growth
            self._sprite_lit_cache.pop(next(iter(self._sprite_lit_cache)))
        return scaled, qsw, qsh

    def _get_sprite_candidates(self, game_map, px, py, max_dist):
        """Query cached coarse buckets instead of scanning every forest object."""
        trees = getattr(game_map, 'trees', [])
        plants = (getattr(game_map, 'undergrowth', None)
                  or getattr(game_map, 'plants', None) or [])
        cache_key = (id(trees), len(trees), id(plants), len(plants))
        if cache_key != self._sprite_bucket_cache_key:
            size = self._sprite_bucket_size
            tree_buckets = {}
            plant_buckets = {}
            for obj in trees:
                key = (int(obj['x'] // size), int(obj['y'] // size))
                tree_buckets.setdefault(key, []).append(obj)
            for obj in plants:
                key = (int(obj['x'] // size), int(obj['y'] // size))
                plant_buckets.setdefault(key, []).append(obj)
            self._tree_buckets = tree_buckets
            self._plant_buckets = plant_buckets
            self._sprite_bucket_cache_key = cache_key
        size = self._sprite_bucket_size
        min_cx = int(math.floor((px - max_dist) / size))
        max_cx = int(math.floor((px + max_dist) / size))
        min_cy = int(math.floor((py - max_dist) / size))
        max_cy = int(math.floor((py + max_dist) / size))
        nearby_trees = []
        nearby_plants = []
        for cy in range(min_cy, max_cy + 1):
            for cx in range(min_cx, max_cx + 1):
                key = (cx, cy)
                nearby_trees.extend(self._tree_buckets.get(key, ()))
                nearby_plants.extend(self._plant_buckets.get(key, ()))
        return nearby_trees, nearby_plants

    def _draw_world_sprites(self, player, enemies, game_map):
        """Collect nearby billboards, sort far -> near, and draw."""
        items = []
        stats = {'trees': 0, 'enemies_view': 0, 'pickups_view': 0, 'drawn': 0}
        # Actual camera FOV half-width + small edge margin so nothing visible
        # pops in; the old +0.5 rad wasted work on off-screen billboards.
        margin_tree = self.half_fov + 0.12
        margin_small = self.half_fov + 0.08

        def consider(kind, obj, x, y, max_dist):
            dx = x - player.x
            dy = y - player.y
            dist_sq = dx * dx + dy * dy
            if dist_sq < 0.0025 or dist_sq > max_dist * max_dist:
                return False
            dist = math.sqrt(dist_sq)
            angle = self._norm_angle(math.atan2(dy, dx) - player.angle)
            lim = margin_tree if kind == 'tree' else margin_small
            if abs(angle) > lim:
                return False
            items.append((dist, angle, kind, obj))
            return True

        tree_candidates, plant_candidates = self._get_sprite_candidates(
            game_map, player.x, player.y, MAX_DEPTH)
        for tree in tree_candidates:
            if consider('tree', tree, tree['x'], tree['y'], MAX_DEPTH):
                stats['trees'] += 1
        for plant in plant_candidates:
            consider('plant', plant, plant['x'], plant['y'], MAX_DEPTH * 0.6)
        for enemy in enemies:
            if not enemy.alive and not getattr(enemy, 'dying', False):
                continue
            if consider('enemy', enemy, enemy.x, enemy.y, MAX_DEPTH):
                stats['enemies_view'] += 1
        for pickup in getattr(game_map, 'pickups', []):
            if not pickup.get('active', True):
                continue
            if consider('pickup', pickup, pickup['x'], pickup['y'], MAX_DEPTH):
                stats['pickups_view'] += 1

        # Select only the nearest visible trees without sorting the full list.
        trees_only = heapq.nsmallest(MAX_RENDER_TREES,
                                     (it for it in items if it[2] == 'tree'),
                                     key=lambda item: item[0])
        if len(trees_only) < stats['trees']:
            items = [it for it in items if it[2] != 'tree'] + trees_only
        items.sort(key=lambda item: item[0], reverse=True)

        pitch_offset = int(player.pitch * self.h)
        horizon = self.h // 2 + pitch_offset
        t_ticks = pygame.time.get_ticks()

        for dist, angle, kind, obj in items:
            screen_x = int((angle / self.fov_rad + 0.5) * self.w)
            unit = self._unit_h(dist)
            floor_y = horizon + unit / 2.0          # where this distance meets the ground

            if kind == 'tree':
                variant_idx = obj.get('canopy_seed', 0) % self._TREE_SPRITE_VARIANTS
                img = self._tree_sprite(obj.get('type', 'balete'), variant_idx)
                height_mult = self._TREE_HEIGHT_MULT.get(obj.get('type'), 2.5)
                sh = unit * height_mult * obj.get('scale', 1.0)
                sw = sh * img.get_width() / img.get_height()
                
                # Enhanced wind animation with gusts
                if ENABLE_ANIMATIONS and ENABLE_ENV_ANIM:
                    base_wind = math.sin(self.wind_time * 0.8 + obj['x'] * 1.7) * self.wind_strength
                    gust = math.sin(self.wind_time * 2.5 + obj['y'] * 0.3) * 0.15
                    tree_stiffness = 0.7 if obj.get('type') == 'balete' else 1.0
                    sway = (base_wind + gust) * sw * 0.025 / tree_stiffness
                else:
                    sway = math.sin(t_ticks * 0.0012 + obj['x'] * 1.7) * sw * 0.015
                
                bottom = floor_y
                self._draw_one(img, screen_x + sway, bottom, sw, sh, dist, stats)

            elif kind == 'plant':
                img = self._undergrowth_sprite(obj.get('type', 'bush'))
                sh = unit * 0.35 * obj.get('scale', 1.0)
                sw = sh * img.get_width() / img.get_height()
                
                # React to player proximity
                if ENABLE_ANIMATIONS and ENABLE_ENV_ANIM:
                    dx_plant = obj['x'] - player.x
                    dy_plant = obj['y'] - player.y
                    dist_to_player = math.hypot(dx_plant, dy_plant)
                    if dist_to_player < 2.0:
                        push_dir = math.atan2(dy_plant, dx_plant) - player.angle
                        push_amount = (2.0 - dist_to_player) * 3.0
                        screen_x += math.cos(push_dir) * push_amount
                
                self._draw_one(img, screen_x, floor_y, sw, sh, dist, stats)

            elif kind == 'pickup':
                ptype = obj.get('type')
                img = self.pickup_sprites.get(ptype)
                if img is None:
                    img = pygame.Surface((32, 32), pygame.SRCALPHA)
                    pygame.draw.rect(img, (255, 255, 0), (8, 8, 16, 16))
                sh = unit * 0.32
                sw = sh * img.get_width() / img.get_height()
                bob = math.sin(t_ticks * 0.004 + obj['x'] * 3.1 + obj['y']) * unit * 0.03
                lift = unit * 0.07 + bob
                bottom = floor_y - lift
                drawn = self._draw_one(img, screen_x, bottom, sw, sh, dist, stats)
                # soft halo so pickups can be found in the dark
                gcol = PICKUP_GLOW.get(ptype, (110, 110, 60))
                pulse = 0.75 + 0.25 * math.sin(t_ticks * 0.005 + obj['x'])
                gc = (int(gcol[0] * pulse), int(gcol[1] * pulse), int(gcol[2] * pulse))
                cy = bottom - sh * 0.5
                if self._col_visible(screen_x, dist):
                    self._emissive.append(('halo', screen_x, cy, max(6, int(sh * 0.9)), gc))
                if self.debug_f4:
                    self._debug_marker(screen_x, cy, (255, 255, 0), f"{ptype} {dist:.1f}")

            elif kind == 'enemy':
                self._draw_enemy(obj, screen_x, floor_y, unit, dist, t_ticks, stats)

        self.stats = stats

    def _draw_one(self, img, cx, bottom, sw, sh, dist, stats, cache=True, alpha=255):
        """Scale, light and depth-test-blit one billboard. Returns columns drawn.

        cache=False is for one-off frames (hit flashes, tilted or fading sprites) so they
        don't churn the shared scaled-sprite cache."""
        sw = int(sw)
        sh = int(sh)
        # Clamp oversized sprites instead of culling them.
        # With taller trees (height_mult up to 4.2, scale up to 1.8), a close
        # tree can project taller than 3× screen height.  Culling it makes the
        # trunk disappear as the player approaches.  Clamping keeps the visible
        # lower portion (which is correct — up close you only see the trunk).
        MAX_SPRITE_H = self.h * 12
        if sh > MAX_SPRITE_H:
            aspect = sw / max(1, sh)
            sh = MAX_SPRITE_H
            sw = max(1, int(sh * aspect))
        if sh < 2 or sw < 1:
            return 0
        if sh > self.h * 2 or sw > self.w * 2:
            return self._draw_one_cropped(img, cx, bottom, sw, sh, dist, stats)
        if cache:
            scaled, qsw, qsh = self._lit_sprite(img, sw, sh, dist)
        else:
            qsw, qsh = sw, sh
            scaled = pygame.transform.scale(img, (qsw, qsh))
            shade = max(MIN_SPRITE_LIGHT, 1.0 - 0.55 * min(1.0, dist / max(1.0, float(MAX_DEPTH))))
            v = min(255, (int(255 * shade) + 8) // 16 * 16)
            scaled.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
            if alpha < 255:
                scaled.set_alpha(max(0, alpha))
        x = int(cx - qsw / 2)
        y = int(bottom - qsh)
        n = self._blit_zbuf(scaled, x, y, dist)
        stats['drawn'] += 1 if n > 0 else 0
        return n

    def _draw_one_cropped(self, img, cx, bottom, sw, sh, dist, stats):
        """Draw a sprite much larger than the screen (a tree right next to the player).

        Scaling the whole billboard to e.g. 4000px tall and caching it would
        allocate and light megapixels per frame as the player walks, so only
        the part that lands on screen is cropped out of the source and scaled.
        """
        iw, ih = img.get_size()
        x = int(cx - sw / 2)
        y = int(bottom - sh)
        vx0, vx1 = max(0, x), min(self.w, x + sw)
        vy0, vy1 = max(0, y), min(self.h, y + sh)
        if vx1 <= vx0 or vy1 <= vy0:
            return 0
        # source rectangle covering the visible destination area (rounded outwards)
        sx0 = max(0, int((vx0 - x) * iw / sw))
        sx1 = min(iw, int(math.ceil((vx1 - x) * iw / sw)))
        sy0 = max(0, int((vy0 - y) * ih / sh))
        sy1 = min(ih, int(math.ceil((vy1 - y) * ih / sh)))
        if sx1 <= sx0 or sy1 <= sy0:
            return 0
        cw = max(1, int(round((sx1 - sx0) * sw / iw)))
        ch = max(1, int(round((sy1 - sy0) * sh / ih)))
        crop = pygame.transform.scale(img.subsurface((sx0, sy0, sx1 - sx0, sy1 - sy0)), (cw, ch))
        shade = max(MIN_SPRITE_LIGHT, 1.0 - 0.55 * min(1.0, dist / max(1.0, float(MAX_DEPTH))))
        v = min(255, (int(255 * shade) + 8) // 16 * 16)
        crop.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
        n = self._blit_zbuf(crop, x + int(sx0 * sw / iw), y + int(sy0 * sh / ih), dist)
        stats['drawn'] += 1 if n > 0 else 0
        return n

    def _draw_enemy(self, enemy, screen_x, floor_y, unit, dist, t_ticks, stats):
        etype = enemy.type
        anim_state = getattr(enemy, 'animation_state', 'idle')
        frame_index = getattr(enemy, 'anim_frame', 0)
        
        # Try to get animated frame first
        img = None
        try:
            from animation_core import get_enemy_animation_system
            anim_sys = get_enemy_animation_system()
            if anim_sys.loaded:
                img = anim_sys.get_frame(etype, anim_state, frame_index)
        except Exception:
            pass
        
        # Fallback to static sprite dict
        if img is None:
            frames = self.enemy_sprites.get(etype)
            if frames:
                img = frames.get(anim_state, frames.get('idle', frames.get('attack')))
        
        # Ultimate fallback: red square
        if img is None:
            img = pygame.Surface((32, 32), pygame.SRCALPHA)
            pygame.draw.rect(img, (200, 50, 50), (4, 4, 24, 24))

        # ─── Extreme Procedural Horror Animation & Weight Physics ─────────────────────
        size_mul, float_mul = ENEMY_SIZE.get(etype, (1.0, 0.0))
        phase = (id(enemy) % 628) / 100.0
        is_crawl = (anim_state in ('crawl', 'crouch', 'stalk'))
        is_atk = (anim_state in ('attack', 'lunge'))
        is_dead = (anim_state == 'death')
        is_hov = (anim_state in ('hover', 'float')) or (float_mul > 0 and anim_state == 'idle')
        is_run = (anim_state in ('run', 'sprint'))

        breathe = 1.0
        sway = 0.0
        hover = 0.0
        jitter = 0.0
        flinch = 0.0   # lateral hit recoil, fraction of sprite width
        tilt = 0.0     # hit recoil tilt, degrees

        # Death collapse progress (0 -> 1) and eased value: fast drop, slow settle
        death_p = min(1.0, getattr(enemy, 'death_t', 0.0) / DEATH_ANIM_TIME) if is_dead else 0.0
        death_e = 1.0 - (1.0 - death_p) ** 3

        if getattr(self, 'enemy_animator', None) is not None:
            tr = self.enemy_animator.transform(enemy, t_ticks * 0.001)
            breathe = tr['breathe']
            sway = tr['sway'] * unit * 0.05
            hover = tr['hover'] * unit
            jitter = tr['jitter']
            flinch = tr.get('flinch', 0.0)
            tilt = tr.get('tilt', 0.0)
        else:
            breath_freq = 0.003 if etype in ('kapre', 'tikbalang') else (0.006 if etype in ('sigbin', 'aswang') else 0.004)
            phase = (id(enemy) % 628) / 100.0
            breathe = 1.0 + 0.035 * math.sin(t_ticks * breath_freq + phase)
            if is_dead:
                breathe = 1.0
            elif is_atk:
                attack_pulse = math.sin(t_ticks * 0.02 + phase)
                breathe *= (1.18 + 0.08 * attack_pulse)
            elif is_run:
                gait = abs(math.sin(t_ticks * 0.015 + phase))
                breathe *= (1.0 + 0.06 * gait)
            elif is_crawl:
                breathe *= 0.72 + 0.04 * math.sin(t_ticks * 0.008 + phase)
            elif is_hov:
                breathe *= 1.0 + 0.04 * math.sin(t_ticks * 0.0035 + phase)

            sway_amp = 0.05 if is_run else (0.025 if is_crawl else 0.035)
            sway = math.sin(t_ticks * 0.004 + phase) * unit * 0.5 * sway_amp
            if is_atk:
                sway += math.sin(t_ticks * 0.03) * 3.0 + random.uniform(-1.0, 1.0)
            elif is_run:
                sway += math.sin(t_ticks * 0.02) * 2.0

            if is_hov or float_mul > 0:
                hover = unit * (float_mul + 0.07 * math.sin(t_ticks * 0.0035 + phase))
            elif is_crawl:
                hover = -unit * 0.18
            elif is_dead:
                hover = -unit * 0.25

        if is_dead:
            # collapse: shrink toward the ground, sink, and lean to the side the last hit came from
            body = 0.85 * (1.0 - 0.72 * death_e)
            hover = hover * (1.0 - death_e) - unit * 0.10 * death_e
        else:
            body = 0.52 if is_crawl else 0.85
        sh = unit * body * size_mul * breathe
        sw = sh * img.get_width() / img.get_height()
        bottom = floor_y - hover
        if is_dead:
            sway += getattr(enemy, 'hit_side', 1) * sw * 0.22 * death_e
            tilt += -getattr(enemy, 'hit_side', 1) * 38.0 * death_e
        sway += flinch * sw

        # Impact colouring: white-hot first frames, then a tint that fades out.
        tint = None
        hf = enemy.hit_flash
        if hf > 0 and not is_dead:
            white = max(0.0, (hf - 0.6) / 0.4)
            base = (210, 170, 60) if getattr(enemy, 'last_damage_type', 'physical') == 'sacred' else (210, 36, 28)
            k = min(1.0, hf) * 0.8
            tint = tuple(min(255, int(base[i] * k + 255 * white * 0.9)) for i in range(3))
        if enemy.bound and not is_dead:
            tint = (60, 20, 120) if tint is None else tuple(min(255, tint[i] + (60, 20, 120)[i]) for i in range(3))

        alpha = 255
        if is_dead:
            alpha = int(255 * (1.0 - max(0.0, (death_p - 0.55) / 0.45)))

        # Anything other than the plain cached frame is drawn through the uncached path.
        special = tint is not None or abs(tilt) > 0.4 or alpha < 255
        if special:
            img = img.copy()
            if tint is not None:
                img.fill(tint, special_flags=pygame.BLEND_RGB_ADD)
            if abs(tilt) > 0.4:
                ow, oh = img.get_size()
                img = pygame.transform.rotate(img, tilt)
                rw, rh = img.get_size()
                sw_r, sh_r = sw * rw / ow, sh * rh / oh
                bottom += (sh_r - sh) * 0.5   # rotate about the body centre, not the feet
                sw, sh = sw_r, sh_r
        n = self._draw_one(img, screen_x + sway, bottom, sw, sh, dist, stats,
                           cache=not special, alpha=alpha)

        cx = screen_x + sway
        top = bottom - sh
        left = cx - sw / 2.0

        # One burst of particles per hit, spawned where the enemy is on screen right now.
        seq = getattr(enemy, 'hit_seq', 0)
        if seq != getattr(enemy, '_fx_seq', 0):
            enemy._fx_seq = seq
            if n > 0 and enemy.hit_flash > 0.5:
                self._emit_hit_fx(cx, top + sh * 0.42, enemy, sh)

        if ENEMY_EYE_GLOW and n > 0 and not is_dead:
            pulse = 0.7 + 0.3 * math.sin(t_ticks * 0.007 + phase)
            if is_atk:
                pulse = 0.9 + 0.3 * math.sin(t_ticks * 0.02)
            aura = ENEMY_AURA.get(etype)
            if aura is not None:
                ac = (int(aura[0] * pulse), int(aura[1] * pulse), int(aura[2] * pulse))
                self._emissive.append(('aura', cx, top + sh * 0.45, max(8, int(sh * 0.8)), ac))
            eyes = ENEMY_EYES.get(etype)
            if eyes is not None:
                (e1, e2), ecol = eyes
                iw, ih = img.get_size()
                er = max(3, int(sh * (0.14 if is_atk else 0.10)))
                if random.random() < 0.02:
                    er = max(1, er // 2)
                for ex, ey in (e1, e2):
                    px = left + ex / float(iw) * sw
                    py = top + ey / float(ih) * sh
                    if self._col_visible(int(px), dist):
                        self._emissive.append(('eye', px, py, er, ecol))

        if self.debug_f4:
            self._debug_marker(cx, top + sh * 0.5, (255, 0, 255), f"{etype}:{anim_state} {dist:.1f}")

    def _emit_hit_fx(self, x, y, enemy, sh):
        """Spawn a spray of blood (or ectoplasm / holy sparks) from a hit enemy."""
        strength = getattr(enemy, 'hit_strength', 0.6)
        ghost = enemy.type in ('multo', 'white_lady')
        sacred = getattr(enemy, 'last_damage_type', 'physical') == 'sacred'
        count = int(6 + 18 * strength)
        spread = max(4.0, sh * 0.12)
        side = getattr(enemy, 'hit_side', 1)
        for _ in range(count):
            ang = random.uniform(-math.pi * 0.95, -math.pi * 0.05)
            spd = random.uniform(35.0, 150.0) * (0.55 + strength)
            if sacred:
                col = random.choice(((255, 226, 130), (255, 244, 200)))
            elif ghost:
                col = random.choice(((170, 205, 235), (215, 232, 255)))
            else:
                col = random.choice(((150, 14, 14), (112, 10, 12), (186, 26, 20)))
            life = random.uniform(0.35, 0.75)
            self.hit_fx.append([x + random.uniform(-spread, spread), y + random.uniform(-spread, spread) * 0.5,
                                math.cos(ang) * spd + side * random.uniform(0.0, 45.0), math.sin(ang) * spd,
                                life, life, 2 if random.random() < 0.3 else 1, col, sacred or ghost])
        if len(self.hit_fx) > 220:
            del self.hit_fx[:len(self.hit_fx) - 220]

    def _update_draw_hit_fx(self, dt):
        """Advance and draw hit particles (gravity, fade). Cheap: tens of 1-2px fills."""
        fx = self.hit_fx
        if not fx:
            return
        surf = self.surface
        w, h = self.w, self.h
        alive = []
        for p in fx:
            p[4] -= dt
            if p[4] <= 0:
                continue
            p[2] *= (1.0 - 1.5 * dt)
            p[3] += 300.0 * dt
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            x, y = int(p[0]), int(p[1])
            if 0 <= x < w and 0 <= y < h:
                r = p[4] / p[5]
                col = p[7] if p[8] else tuple(int(c * (0.45 + 0.55 * r)) for c in p[7])
                surf.fill(col, (x, y, p[6], p[6]))
            alive.append(p)
        self.hit_fx = alive

    def _debug_marker(self, x, y, color, label):
        x = int(x)
        y = int(y)
        pygame.draw.circle(self.surface, color, (x, y), 8, 2)
        try:
            self.surface.blit(self.dbg_font.render(label, True, color), (x + 10, y - 6))
        except Exception:
            pass

    def _vm_scaled(self, key, surf, size):
        """Cached pygame.transform.scale for viewmodel art (same inputs every frame)."""
        ck = ('scale', key, size)
        got = self._viewmodel_cache.get(ck)
        if got is None:
            got = pygame.transform.scale(surf, size)
            self._viewmodel_cache[ck] = got
            if len(self._viewmodel_cache) > 400:
                self._viewmodel_cache.pop(next(iter(self._viewmodel_cache)))
        return got

    def _vm_rotated(self, key, surf, angle):
        """Cached rotate, angle quantised to 0.5 degree (invisible, but reusable)."""
        q = round(angle * 2.0) / 2.0
        ck = ('rot', key, q)
        got = self._viewmodel_cache.get(ck)
        if got is None:
            got = pygame.transform.rotate(surf, q)
            self._viewmodel_cache[ck] = got
            if len(self._viewmodel_cache) > 400:
                self._viewmodel_cache.pop(next(iter(self._viewmodel_cache)))
        return got

    def _draw_player_viewmodel(self, player, dt):
        """Draw immersive first-person procedural hands, forearms, sleeves, and weapon viewmodel."""
        weapon_names = ['bolo', 'shotgun', 'revolver']
        wname = weapon_names[player.current_weapon] if 0 <= player.current_weapon < len(weapon_names) else 'bolo'

        sprite = self.weapon_sprites.get(wname)
        if sprite is None:
            return

        # The custom bolo / shotgun art fills its whole surface, so size it to the
        # screen height (works at any internal resolution); other weapons keep 3x.
        from asset_generator import SHOTGUN_ANCHORS, REVOLVER_ANCHORS
        custom_shotgun = (wname == 'shotgun' and bool(SHOTGUN_ANCHORS))
        custom_revolver = (wname == 'revolver' and bool(REVOLVER_ANCHORS))
        sprite = self.weapon_sprites.get(wname)
        if wname == 'bolo' or custom_shotgun:
            scale = self.h * 0.85 / sprite.get_height()
        elif custom_revolver:
            # A sidearm: about half the screen height, tucked in the lower right so
            # the crosshair and the view ahead stay clear (the old 3x procedural
            # sprite was taller than the whole 360px screen).
            scale = self.h * 0.5 / sprite.get_height()
        else:
            scale = 3
        sw = int(sprite.get_width() * scale)
        sh = int(sprite.get_height() * scale)
        vm_key = (wname, id(sprite))
        scaled = self._vm_scaled(vm_key, sprite, (sw, sh))

        # Base screen position (shifted to right arm perspective)
        base_x = self.w // 2 - sw // 3 + 50
        base_y = self.h - sh + 30
        # The revolver art is drawn as a three-quarter view (front of the
        # cylinder and bore visible, barrel up toward the crosshair).  Anchor
        # its grip near bottom-center so it reads as a held gun.
        if wname == 'revolver' and not custom_revolver:
            base_x = self.w // 2 - sw // 2 + 8
            base_y = self.h - int(sh * 0.82)

        # Animation calculations
        t_ticks = pygame.time.get_ticks()
        is_moving = abs(getattr(player, 'bob_amount', 0)) > 0.1
        is_sprinting = getattr(player, 'is_sprinting', False)

        # Idle breathing
        breathe = math.sin(t_ticks * 0.003) * 2.0

        # Walking bob
        bob_x = int(math.sin(self.weapon_bob) * 4) if is_moving else 0
        bob_y = int(abs(math.cos(self.weapon_bob)) * 5) if is_moving else int(breathe)
        if is_moving:
            self.weapon_bob += dt * 6

        # Sprinting posture
        sprint_tilt = 0
        sprint_off_x = 0
        if is_sprinting:
            sprint_tilt = -15
            sprint_off_x = 25
            bob_y += int(math.sin(t_ticks * 0.015) * 8)

        # Recoil (the shotgun's own fire frames already carry the kick, so skip the
        # procedural offset while they play to avoid a double kick)
        shotgun_anim_playing = (wname == 'shotgun' and self.shotgun_fire_timer > 0
                                and bool(SHOTGUN_ANCHORS))
        recoil_y = 0 if shotgun_anim_playing else int(self.weapon_recoil * 18)
        if self.weapon_recoil > 0:
            self.weapon_recoil -= dt * 6

        # Reload animation
        reload_offset = 0
        reload_rot = 0
        if player.reloading:
            reload_offset = int(math.sin(player.reload_timer * 4) * 35)
            reload_rot = -10

        # Revolver: crisp backward kick, muzzle lift, and quick return.
        revolver_kick_x = revolver_kick_y = revolver_tilt = 0
        if wname == 'revolver' and self.revolver_fire_timer > 0:
            fire_p = max(0.0, min(1.0, self.revolver_fire_timer / 0.16))
            kick = math.sin(fire_p * math.pi) ** 0.7
            revolver_kick_x = int(12 * kick)
            revolver_kick_y = int(25 * kick)
            revolver_tilt = -7.0 * kick
            self.revolver_fire_timer = max(0.0, self.revolver_fire_timer - dt)

        # Damage / Death
        if not player.alive:
            reload_offset += 80
            reload_rot += 30
        elif player.damage_flash > 0:
            recoil_y += 10

        final_x = base_x + bob_x + sprint_off_x - revolver_kick_x
        final_y = base_y + bob_y + recoil_y + reload_offset + revolver_kick_y

        # Revolver reload: lower and cant the gun as the cylinder is serviced.
        if wname == 'revolver' and player.reloading:
            reload_p = max(0.0, min(1.0, 1.0 - player.reload_timer / max(0.01, REVOLVER_RELOAD_TIME)))
            reload_wave = math.sin(reload_p * math.pi)
            final_y += int(22 * reload_wave)
            reload_rot -= 18.0 * reload_wave

        # Rotate viewmodel if sprinting, reloading, or dying
        total_rot = sprint_tilt + reload_rot + revolver_tilt
        if total_rot != 0:
            draw_surf = self._vm_rotated(vm_key, scaled, total_rot)
        else:
            draw_surf = scaled

        # Bolo: rotate about the handle end so the blade sweeps while the grip
        # stays in the hand. Faded ghost copies of the blade give the slash a trail.
        bolo_grip = None
        bolo_ghosts = []
        if wname == 'bolo':
            from asset_generator import BOLO_ANCHORS
            hk = self.h / 360.0   # pose offsets are authored for a 360px-tall view
            pre_x, pre_y = final_x, final_y
            piv_x, piv_y = BOLO_ANCHORS['pivot'][0] * sw, BOLO_ANCHORS['pivot'][1] * sh
            grp_x, grp_y = BOLO_ANCHORS['grip'][0] * sw, BOLO_ANCHORS['grip'][1] * sh

            def place(angle, dx, dy):
                """Surface + blit position + grip point for the bolo at a given pose."""
                theta = math.radians(angle + total_rot)
                sin_t, cos_t = math.sin(theta), math.cos(theta)

                def rot(vx, vy):
                    # rotate a vector counter-clockwise by theta (screen coords, y down)
                    return vx * cos_t + vy * sin_t, -vx * sin_t + vy * cos_t

                pivot_x = pre_x + piv_x + dx * hk
                pivot_y = pre_y + piv_y + dy * hk
                surf = self._vm_rotated(vm_key, scaled, angle + total_rot)
                # the pivot sits (piv - center) from the sprite center; rotate that
                # offset to find where the rotated surface must be blitted
                off_x, off_y = rot(piv_x - sw / 2, piv_y - sh / 2)
                bx = int(pivot_x - off_x - surf.get_width() / 2)
                by = int(pivot_y - off_y - surf.get_height() / 2)
                g_x, g_y = rot(grp_x - piv_x, grp_y - piv_y)
                return surf, bx, by, (int(pivot_x + g_x), int(pivot_y + g_y))

            swing_pose = (0.0, 0.0, 0.0)
            if self.bolo_swing_timer > 0:
                prog = max(0.0, min(1.0, 1.0 - self.bolo_swing_timer / BOLO_COOLDOWN))
                swing_pose = self._bolo_swing_pose(prog)
                # trail: older poses of the slash, progressively fainter
                if 0.25 <= prog < 0.75:
                    for lag, alpha in ((0.035, 110), (0.07, 70), (0.105, 38)):
                        gp = max(0.25, prog - lag)
                        g_surf, gx_, gy_, _ = place(*self._bolo_swing_pose(gp))
                        g_surf = g_surf.copy()
                        g_surf.set_alpha(alpha)
                        bolo_ghosts.append((g_surf, gx_, gy_))
                self.bolo_swing_timer = max(0.0, self.bolo_swing_timer - dt)
            draw_surf, final_x, final_y, bolo_grip = place(*swing_pose)

        # Shotgun: play the pump sheet (flash, kick, settle) while firing
        shotgun_hands = None
        if custom_shotgun and self.shotgun_fire_timer > 0:
            from asset_generator import SHOTGUN_FIRE_FRAMES, SHOTGUN_FIRE_WEIGHTS
            if SHOTGUN_FIRE_FRAMES:
                prog = max(0.0, min(1.0, 1.0 - self.shotgun_fire_timer / SHOTGUN_COOLDOWN))
                idx, acc = len(SHOTGUN_FIRE_FRAMES) - 1, 0.0
                for i, wgt in enumerate(SHOTGUN_FIRE_WEIGHTS[:len(SHOTGUN_FIRE_FRAMES)]):
                    acc += wgt
                    if prog < acc / sum(SHOTGUN_FIRE_WEIGHTS[:len(SHOTGUN_FIRE_FRAMES)]):
                        idx = i
                        break
                f_surf, f_dest, f_right, f_left = SHOTGUN_FIRE_FRAMES[idx]
                kx = sw / sprite.get_width()
                ky = sh / sprite.get_height()
                draw_surf = self._vm_scaled(
                    ('shotgun_fire', idx), f_surf,
                    (int(f_surf.get_width() * kx), int(f_surf.get_height() * ky)))
                base_x, base_y = final_x, final_y
                final_x = base_x + int(f_dest[0] * kx)
                final_y = base_y + int(f_dest[1] * ky)
                shotgun_hands = (
                    (int(base_x + f_right[0] * sw), int(base_y + f_right[1] * sh)),
                    (int(base_x + f_left[0] * sw), int(base_y + f_left[1] * sh)))
            self.shotgun_fire_timer = max(0.0, self.shotgun_fire_timer - dt)

        # ── Procedural First-Person Hands & Sleeves ──────────────────────────────
        skin_color = (210, 175, 150)
        sleeve_color = (45, 52, 62)
        glove_color = (35, 38, 45)

        # Right Hand (main grip)
        rh_x = final_x + sw // 2
        rh_y = final_y + sh // 2
        # Left Hand (support grip)
        lh_x = final_x + 15
        lh_y = final_y + sh // 3

        # Draw sleeves extending from bottom corners
        pygame.draw.polygon(self.surface, sleeve_color, [
            (self.w + 10, self.h + 10), (self.w - 120, self.h - 40), (self.w - 80, self.h + 10)
        ])
        pygame.draw.polygon(self.surface, sleeve_color, [
            (-10, self.h + 10), (80, self.h - 30), (40, self.h + 10)
        ])

        # Draw weapon viewmodel surface (slash trail first, then the bolo itself)
        for g_surf, gx_, gy_ in bolo_ghosts:
            self.surface.blit(g_surf, (gx_, gy_))
        self.surface.blit(draw_surf, (final_x, final_y))

        # Draw visible gripping hands / knuckles
        if player.alive and bolo_grip is not None:
            # Right hand wraps the bolo handle and follows the swing
            pygame.draw.circle(self.surface, skin_color, bolo_grip, 9)
            pygame.draw.circle(self.surface, glove_color, (bolo_grip[0] - 3, bolo_grip[1] + 3), 6)
        elif player.alive and custom_shotgun:
            # Hands sit on the custom shotgun art: right on the receiver, left on the pump
            if shotgun_hands is not None:
                (rx, ry), (lx, ly) = shotgun_hands
            else:
                rx = int(final_x + SHOTGUN_ANCHORS['right'][0] * sw)
                ry = int(final_y + SHOTGUN_ANCHORS['right'][1] * sh)
                lx = int(final_x + SHOTGUN_ANCHORS['left'][0] * sw)
                ly = int(final_y + SHOTGUN_ANCHORS['left'][1] * sh)
            pygame.draw.circle(self.surface, skin_color, (rx, ry), 9)
            pygame.draw.circle(self.surface, glove_color, (rx - 3, ry + 3), 6)
            pygame.draw.circle(self.surface, skin_color, (lx, ly), 8)
            pygame.draw.circle(self.surface, glove_color, (lx - 3, ly + 3), 5)
        elif player.alive and custom_revolver:
            # One-handed: the hand wraps the wooden grip of the custom art
            rx = int(final_x + REVOLVER_ANCHORS['right'][0] * sw)
            ry = int(final_y + REVOLVER_ANCHORS['right'][1] * sh)
            pygame.draw.circle(self.surface, skin_color, (rx, ry), 9)
            pygame.draw.circle(self.surface, glove_color, (rx - 3, ry + 3), 6)
        elif player.alive:
            # Right hand knuckles / fingers on grip
            pygame.draw.circle(self.surface, skin_color, (int(rh_x - 15), int(rh_y + 10)), 8)
            pygame.draw.circle(self.surface, glove_color, (int(rh_x - 18), int(rh_y + 12)), 6)
            # Left hand support grip (especially for shotgun / rifle)
            if wname == 'shotgun':
                pygame.draw.circle(self.surface, skin_color, (int(lh_x + 10), int(lh_y + 20)), 7)
                pygame.draw.circle(self.surface, glove_color, (int(lh_x + 8), int(lh_y + 22)), 5)
            elif wname == 'revolver':
                # Three-quarter art: hands track relative to the scaled sprite
                # so they stay on the grip / frame at any internal resolution.
                gy_x = int(rh_x + sh * 0.10)
                gy_y = int(rh_y + sh * 0.36)
                pygame.draw.circle(self.surface, skin_color, (gy_x, gy_y), 8)
                pygame.draw.circle(self.surface, glove_color, (gy_x - 4, gy_y + 4), 6)
                pygame.draw.circle(self.surface, skin_color, (int(lh_x + 20), int(lh_y + 18)), 6)

    def _draw_muzzle_flash(self):
        """Draw muzzle flash effect."""
        cx, cy = self.w // 2, self.h // 2 + 20
        radius = int(self.muzzle_flash * 30)
        if radius > 0:
            flash = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            pygame.draw.circle(flash, (255, 220, 100, max(0, min(255, int(self.muzzle_flash * 200)))),
                               (cx, cy), radius)
            self.surface.blit(flash, (0, 0))

    def trigger_muzzle_flash(self):
        self.muzzle_flash = 1.0
        self.weapon_recoil = 1.0
        # Short, sharp revolver kick; animation is applied only while equipped.
        self.revolver_fire_timer = 0.16
        self.muzzle_flash = 1.0
        self.weapon_recoil = 1.0

    def trigger_shotgun_fire(self):
        """Start the shotgun fire animation (lasts as long as the shotgun cooldown)."""
        self.shotgun_fire_timer = SHOTGUN_COOLDOWN

    def trigger_bolo_swing(self):
        """Start the bolo slash animation (lasts as long as the bolo cooldown)."""
        self.bolo_swing_timer = BOLO_COOLDOWN

    @staticmethod
    def _bolo_swing_pose(p):
        """Return (angle_deg, dx, dy) for swing progress p in [0, 1].

        Offsets are authored for a 360px-tall view. The bolo pivots on its handle:
        a high windup pulled back to the right, a fast slash that carries the blade
        across the screen to the left with the handle lifting to mid-screen, a short
        follow-through, then a recovery to the rest pose. Positive angle rotates the
        blade counter-clockwise (toward the left).
        """
        def smooth(u):
            return u * u * (3 - 2 * u)

        def lerp(a, b, u):
            return a + (b - a) * u

        if p < 0.25:                      # windup: blade rises, hand pulls back right
            u = 1 - (1 - p / 0.25) ** 2
            return lerp(0, -35, u), lerp(0, 35, u), lerp(0, 25, u)
        if p < 0.55:                      # slash: fast, accelerating across the screen
            u = ((p - 0.25) / 0.30) ** 1.6
            return (lerp(-35, 45, u), lerp(35, -90, u),
                    lerp(25, -140, u) - math.sin(math.pi * u) * 20)
        if p < 0.68:                      # follow-through: a little overshoot
            u = smooth((p - 0.55) / 0.13)
            return lerp(45, 52, u), lerp(-90, -100, u), lerp(-140, -135, u)
        u = smooth((p - 0.68) / 0.32)     # recover to the rest pose
        return lerp(52, 0, u), lerp(-100, 0, u), lerp(-135, 0, u)

    def trigger_ward_effect(self, ward_type, duration=1.5):
        self.ward_effect_timer = duration
        self.ward_effect_type = ward_type

    def _draw_ward_effect(self, dt):
        """Draw sacred ward visual effects."""
        self.ward_effect_timer -= dt
        t = self.ward_effect_timer

        effect = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        cx, cy = self.w // 2, self.h // 2

        if self.ward_effect_type == 'repel':
            radius = int((1.5 - t) * self.w * 0.4)
            alpha = int(max(0, min(255, t / 1.5 * 150)))
            pygame.draw.circle(effect, (255, 215, 0, alpha), (cx, cy), radius, 3)
            pygame.draw.circle(effect, (255, 255, 200, max(0, min(255, alpha // 2))), (cx, cy), max(0, radius - 10), 2)
        elif self.ward_effect_type == 'shield':
            alpha = int(max(0, min(255, t / 1.5 * 80)))
            pygame.draw.rect(effect, (100, 150, 255, alpha), (0, 0, self.w, self.h))
            pygame.draw.rect(effect, (150, 200, 255, max(0, min(255, alpha + 20))),
                             (10, 10, self.w - 20, self.h - 20), 3)
        elif self.ward_effect_type == 'banish':
            radius = int((1.5 - t) * self.w * 0.5)
            alpha = int(max(0, min(255, t / 1.5 * 180)))
            pygame.draw.circle(effect, (255, 255, 220, alpha), (cx, cy), radius, 4)
        elif self.ward_effect_type == 'bind':
            alpha = int(max(0, min(255, t / 1.5 * 120)))
            for i in range(5):
                r = 20 + i * 15
                pygame.draw.circle(effect, (120, 60, 200, alpha), (cx, cy), r, 2)
        elif self.ward_effect_type == 'ultimate':
            alpha = int(max(0, min(255, t / 1.5 * 200)))
            effect.fill((255, 255, 200, min(alpha, 100)))
            radius = int((1.5 - t) * self.w * 0.6)
            pygame.draw.circle(effect, (255, 215, 0, alpha), (cx, cy), radius, 5)

        self.surface.blit(effect, (0, 0))

    def trigger_screen_shake(self, amount=5):
        self.screen_shake = max(self.screen_shake, amount)
