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
import pygame
import numpy as np
from settings import *

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
        """Precompute everything once at startup."""
        w, h = self.w, self.h
        mw, mh = w * 2, h * 2
        rx = max(1.0, w * BEAM_RADIUS)
        ry = rx * 0.85
        ys, xs = np.ogrid[:mh, :mw]
        r = np.sqrt(((xs - w) / rx) ** 2 + ((ys - h) / ry) ** 2)   # shape (mh, mw)

        # Darkness: 0 in the beam centre -> full darkness outside the beam
        t = np.clip((r - 0.15) / 0.85, 0.0, 1.0)
        t = t * t * (3.0 - 2.0 * t)                                # smoothstep
        dark_alpha = int((1.0 - AMBIENT) * 255)
        self.dark_mask = pygame.Surface((mw, mh), pygame.SRCALPHA)
        self.dark_mask.fill((DARK_TINT[0], DARK_TINT[1], DARK_TINT[2], 255))
        av = pygame.surfarray.pixels_alpha(self.dark_mask)
        av[:, :] = (t * dark_alpha).T.astype(np.uint8)
        del av

        # Warm glow (additive)
        f = np.clip(1.0 - r, 0.0, 1.0) ** 2
        rgb = np.zeros((mw, mh, 3), dtype=np.uint8)
        for c in range(3):
            rgb[:, :, c] = (f * BEAM_GLOW[c]).T.astype(np.uint8)
        self.glow_mask = pygame.Surface((mw, mh))
        pygame.surfarray.blit_array(self.glow_mask, rgb)

        self.dark_off = pygame.Surface((w, h), pygame.SRCALPHA)
        self.dark_off.fill((0, 0, 0, 255))
        self.dark_flicker = pygame.Surface((w, h), pygame.SRCALPHA)
        self.dark_flicker.fill((DARK_TINT[0], DARK_TINT[1], DARK_TINT[2], 70))

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
            surf.fill((0, 0, 0))
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

        # Precompute ray angles
        self.fov_rad = math.radians(FOV)
        self.half_fov = self.fov_rad / 2
        self.num_rays = NUM_RAYS
        self.ray_angles = []
        for i in range(self.num_rays):
            angle_offset = (i / self.num_rays - 0.5) * self.fov_rad
            self.ray_angles.append(angle_offset)

        # Z-buffer for sprite occlusion (one entry per ray)
        self.z_buffer = [0.0] * self.num_rays

        # Floor/ceiling cache & procedural forest assets
        from asset_generator import generate_tree_billboard, generate_undergrowth_sprite, generate_world_ground_texture
        self.tree_sprites = {}
        for tname in ['balete', 'bamboo', 'mahogany', 'dead', 'banana', 'palm', 'supernatural', 'akasya', 'narra', 'tree_fern', 'strangler']:
            self.tree_sprites[tname] = [generate_tree_billboard(tname, 64, 256, seed=42 + v * 333) for v in range(5)]
        self._TREE_HEIGHT_MULT = {
            'balete': 3.6, 'mahogany': 4.2, 'bamboo': 3.4, 'dead': 3.0,
            'banana': 2.8, 'palm': 3.6, 'supernatural': 3.8,
            'akasya': 3.9, 'narra': 4.0, 'tree_fern': 2.5, 'strangler': 3.7,
        }
        self.undergrowth_sprites = {
            'fern': generate_undergrowth_sprite('fern', 32, 32),
            'mushroom': generate_undergrowth_sprite('mushroom', 32, 32),
            'rock': generate_undergrowth_sprite('rock', 32, 32),
            'bush': generate_undergrowth_sprite('bush', 32, 32),
            'log': generate_undergrowth_sprite('log', 32, 32),
            'stump': generate_undergrowth_sprite('stump', 32, 32),
            'boulder': generate_undergrowth_sprite('boulder', 32, 32),
            'sapling': generate_undergrowth_sprite('sapling', 32, 32),
        }
        self.world_ground_tex = generate_world_ground_texture(GROUND_TEX_SIZE, GROUND_TEX_SIZE)
        self._ground_arr = pygame.surfarray.array3d(self.world_ground_tex)
        self.frame_counter = 0

        self.floor_surf = pygame.Surface((self.w, self.h // 2))
        self._generate_floor_gradient()

        # Weapon animation
        self.weapon_bob = 0
        self.weapon_recoil = 0
        self.muzzle_flash = 0

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
        self.moon_surf = moon_surf
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
        # Pre-rendered particle surfaces (cached per size) to avoid per-frame allocation
        self._particle_cache = {}

        # Debug overlay (F3)
        self.show_debug = True
        self.fps_history = []
        self.frame_times = []  # For percentile tracking
        self.timings = {'rays': 0.0, 'sprites': 0.0, 'darkness': 0.0, 'post': 0.0, 'total': 0.0, 'animation': 0.0}
        self.dbg_font = pygame.font.SysFont('consolas', 12)

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
        for ttype, spr_list in self.tree_sprites.items():
            for idx, spr in enumerate(spr_list):
                all_assets.append((f"tree_{ttype}_{idx}", spr))
        for utype, spr in self.undergrowth_sprites.items():
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
        return surf

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
        return vig

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
            self._glow_cache[key] = s
        return s

    # ─── Frame ────────────────────────────────────────────────────────────
    def render_frame(self, player, game_map, enemies, effects, dt):
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
        t_ticks = pygame.time.get_ticks()

        pitch_offset = int(player.pitch * self.h)
        half_h = self.h // 2
        horizon_y = max(0, half_h + pitch_offset)

        # 1. Sky Gradient (SKY_COLOR to blue-green haze (24,34,42))
        for y in range(horizon_y):
            t = y / max(1, horizon_y)
            r = int(SKY_COLOR[0] * (1 - t) + 24 * t)
            g = int(SKY_COLOR[1] * (1 - t) + 34 * t)
            b = int(SKY_COLOR[2] * (1 - t) + 42 * t)
            pygame.draw.line(self.surface, (r, g, b), (0, y), (self.w, y))

        if horizon_y > 0:
            # Stars (260 stars, local Random(999))
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

            # Moon (fixed world azimuth pi/4, elevation 0.42)
            moon_world_az = math.pi / 4
            moon_world_el = 0.42
            az_diff = moon_world_az - player.angle
            while az_diff > math.pi: az_diff -= 2 * math.pi
            while az_diff < -math.pi: az_diff += 2 * math.pi
            moon_screen_x = int(self.w // 2 + (az_diff / self.fov_rad) * self.w)
            moon_screen_y = int(horizon_y - moon_world_el * (0.8 * self.h))

            if -80 <= moon_screen_x <= self.w + 80 and 0 <= moon_screen_y <= horizon_y + 40:
                self.surface.blit(self.moon_surf, (moon_screen_x - self.moon_size // 2, moon_screen_y - self.moon_size // 2))

            # Enhanced atmospheric clouds with layered depth
            cloud_t = t_ticks * 0.0008
            for c_idx in range(6):
                cx = int((c_idx * 180 + cloud_t * (25 if c_idx < 4 else 15)) % (self.w + 300) - 150)
                cy = int(horizon_y * (0.15 + c_idx * 0.12))
                alpha = max(30, 80 - c_idx * 15)
                if 0 <= cy < horizon_y:
                    cloud_surf = pygame.Surface((180, 40), pygame.SRCALPHA)
                    pygame.draw.ellipse(cloud_surf, (40 + c_idx * 10, 45 + c_idx * 8, 60 + c_idx * 5, alpha), (0, 0, 180, 40))
                    self.surface.blit(cloud_surf, (cx, cy))

            # Subtle aurora borealis effect at horizon
            if ENABLE_ANIMATIONS and ENABLE_ENV_ANIM:
                aurora_t = t_ticks * 0.0003
                for a_idx in range(3):
                    aurora_x = int((a_idx * 250 + aurora_t * 50) % (self.w + 200) - 100)
                    aurora_w = 60 + a_idx * 20
                    aurora_alpha = max(5, 25 - a_idx * 5)
                    aurora_surf = pygame.Surface((aurora_w, 30), pygame.SRCALPHA)
                    pygame.draw.ellipse(aurora_surf, (40, 80 + a_idx * 30, 100, aurora_alpha), (0, 0, aurora_w, 30))
                    self.surface.blit(aurora_surf, (aurora_x, max(5, horizon_y - 50 + a_idx * 10)))

        # 2. Floor with perspective texture mapping of self.world_ground_tex and exp-squared fog
        floor_h = self.h - horizon_y
        if floor_h > 0 and hasattr(self, '_ground_arr'):
            mist_phase = t_ticks * 0.0003
            arr_3d = pygame.surfarray.pixels3d(self.surface)
            gw, gh, _ = self._ground_arr.shape
            px, py, pa = player.x, player.y, player.angle
            
            ray_dx = np.cos(pa + np.array(self.ray_angles, dtype=np.float32) if hasattr(self, 'ray_angles') else np.linspace(-0.5, 0.5, self.w))
            ray_dy = np.sin(pa + np.array(self.ray_angles, dtype=np.float32) if hasattr(self, 'ray_angles') else np.linspace(-0.5, 0.5, self.w))
            
            for y in range(horizon_y, self.h):
                row_y = y - half_h - pitch_offset
                if row_y <= 0:
                    continue
                dist = (self.h * 0.5) / row_y
                wx = px + dist * ray_dx
                wy = py + dist * ray_dy
                
                tx = np.clip(np.abs((wx * 8.0) % gw).astype(np.int32), 0, gw - 1)
                ty = np.clip(np.abs((wy * 8.0) % gh).astype(np.int32), 0, gh - 1)
                
                tex_cols = self._ground_arr[tx, ty] # shape (w, 3)
                
                fog = 1.0 - math.exp(-((dist * 0.07) ** 2))
                shade = max(0.08, 1.0 - fog)
                
                shaded_cols = (tex_cols.astype(np.float32) * shade).astype(np.uint8)
                
                floor_t = (y - horizon_y) / max(1, floor_h)
                if floor_t < 0.45:
                    mist_strength = (0.45 - floor_t) / 0.45
                    mist_wave = math.sin(mist_phase + y * 0.08) * 0.5 + 0.5
                    mist_alpha = mist_strength * mist_wave * 0.25
                    shaded_cols = (shaded_cols.astype(np.float32) * (1 - mist_alpha) + np.array([30, 40, 38], dtype=np.float32) * mist_alpha).astype(np.uint8)
                
                arr_3d[:, y, :] = shaded_cols
            del arr_3d

        # 3. Cast rays and draw walls (also fills the z-buffer)
        t_rays = pygame.time.get_ticks()
        self._cast_rays(player, game_map)
        self.timings['rays'] = pygame.time.get_ticks() - t_rays

        # 4. Trees + undergrowth + enemies + pickups: ONE depth-sorted pass
        self._draw_world_sprites(player, enemies, game_map)

        # 5. Darkness + flashlight (ONCE).  F4 shows the raw, unlit scene.
        self.flashlight.update(dt, abs(player.bob_amount) > 0.5, 0, player.flashlight_battery)
        if not self.debug_f4:
            self.flashlight.draw(self.surface, player)

        # 6. Glowing eyes / halos: drawn AFTER darkness so they show in the dark
        self._draw_emissive()

        # 7. Particles (fireflies / dust / spores)
        if ENABLE_PARTICLES:
            for p in self.particles:
                p['x'] = (p['x'] + p['vx']) % self.w
                p['y'] = (p['y'] + p['vy']) % self.h
                p['phase'] += dt * 2
                # Dust motes are dimmer and slower-pulsing than fireflies
                if p.get('kind') == 'dust':
                    alpha = int(abs(math.sin(p['phase'] * 0.5)) * 60)
                else:
                    alpha = int(abs(math.sin(p['phase'])) * 180)
                if alpha < 5:
                    continue
                psize = int(p['size'])
                key = (psize, p['color'])
                psurf = self._particle_cache.get(key)
                if psurf is None:
                    psurf = pygame.Surface((psize * 2, psize * 2), pygame.SRCALPHA)
                    pygame.draw.circle(psurf, (*p['color'], 255), (psize, psize), psize)
                    self._particle_cache[key] = psurf
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
            blood_vig = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            alpha = int(urgency * 120 + math.sin(pygame.time.get_ticks() * 0.006) * 30)
            pygame.draw.rect(blood_vig, (180, 0, 0, max(0, min(200, alpha))), (0, 0, self.w, self.h), max(1, int(20 * urgency)))
            self.surface.blit(blood_vig, (0, 0))

        # Ward effects
        if self.ward_effect_timer > 0:
            self._draw_ward_effect(dt)

        # Damage flash
        if player.damage_flash > 0:
            flash = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            alpha = max(0, min(255, int(player.damage_flash * 120)))
            flash.fill((200, 0, 0, alpha))
            self.surface.blit(flash, (0, 0))

        # Muzzle flash
        if self.muzzle_flash > 0:
            self._draw_muzzle_flash()
            self.muzzle_flash -= dt * 8

        # Draw player viewmodel (hands, sleeves, weapon)
        self._draw_player_viewmodel(player, dt)

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
        if not self.show_debug:
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
        for e in enemies:
            d = math.hypot(e.x - player.x, e.y - player.y)
            if nearest is None or d < nearest:
                nearest = d

        lines = [
            f"ANINO SA GUBAT - DEBUG (F3)  [F4 = raw scene + markers]",
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

        for idx, line in enumerate(lines):
            col = (0, 255, 100) if "OK" in line or idx == 0 else (255, 100, 100) if "Warnings" in line else (220, 220, 220)
            txt = font.render(line, True, col)
            self.surface.blit(txt, (8, 8 + idx * 14))

    # ─── Walls ────────────────────────────────────────────────────────────
    def _cast_rays(self, player, game_map):
        """Cast rays for wall rendering."""
        px, py = player.x, player.y
        pa = player.angle
        pitch_offset = int(player.pitch * self.h)
        far = float(MAX_DEPTH) + 1.0

        for i in range(self.num_rays):
            ray_angle = pa + self.ray_angles[i]
            sin_a = math.sin(ray_angle)
            cos_a = math.cos(ray_angle)

            # DDA raycasting
            dist, wall_type, hit_x_frac, side = self._dda_cast(px, py, cos_a, sin_a, game_map)

            # Ray hit nothing within MAX_DEPTH: no wall to draw, sprites are never hidden
            if dist >= MAX_DEPTH:
                self.z_buffer[i] = far
                continue

            # Fish-eye correction
            cos_diff = math.cos(self.ray_angles[i])
            corrected_dist = dist * cos_diff

            self.z_buffer[i] = corrected_dist

            if corrected_dist < 0.01:
                continue

            # Wall height
            wall_h = int(WALL_HEIGHT_SCALE / (corrected_dist * TILE_SIZE))
            if wall_h > self.h * 3:
                wall_h = self.h * 3

            draw_start = self.h // 2 - wall_h // 2 + pitch_offset
            draw_end = draw_start + wall_h

            # Texture mapping
            tex = self._get_wall_texture(wall_type)
            if tex:
                cols = self._wall_columns(tex)
                tex_x = int(hit_x_frac * len(cols)) % len(cols)
                # Scale the pre-sliced column, then shade it with a multiply-fill
                # (distance fog + darker side faces) instead of allocating overlays.
                shaded = pygame.transform.scale(cols[tex_x], (1, max(1, wall_h)))
                shade = max(0.15, 1.0 - corrected_dist / MAX_DEPTH)
                dark_a = min(255, int((1 - shade) * 220) + (35 if side == 1 else 0))
                v = 255 - dark_a
                shaded.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)

                self.surface.blit(shaded, (i, max(0, draw_start)),
                                  (0, max(0, -draw_start), 1, min(wall_h, self.h - max(0, draw_start))))
            else:
                # Fallback solid color
                color = self._get_wall_color(wall_type, corrected_dist)
                if draw_start < self.h and draw_end > 0:
                    ds = max(0, draw_start)
                    de = min(self.h, draw_end)
                    pygame.draw.line(self.surface, color, (i, ds), (i, de))

    def _wall_columns(self, tex):
        """Return the 1px-wide column subsurfaces of a wall texture (sliced once, zero-copy)."""
        cols = self._wall_col_cache.get(id(tex))
        if cols is None:
            h = tex.get_height()
            cols = [tex.subsurface((x, 0, 1, h)) for x in range(tex.get_width())]
            self._wall_col_cache[id(tex)] = cols
        return cols

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
        zb = self.z_buffer
        nr = self.num_rays
        w = self.w
        run = None
        drawn = 0
        for col in range(x0, x1 + 1):
            vis = False
            if col < x1:
                zi = col * nr // w
                vis = zb[zi] > dist
            if vis:
                if run is None:
                    run = col
            elif run is not None:
                self.surface.blit(img, (run, y), (run - x, 0, col - run, ih))
                drawn += col - run
                run = None
        return drawn

    def _col_visible(self, col, dist):
        if col < 0 or col >= self.w:
            return False
        return self.z_buffer[col * self.num_rays // self.w] > dist

    def _light_sprite(self, img, dist):
        """Distance-darken a sprite WITHOUT touching its alpha channel."""
        shade = max(MIN_SPRITE_LIGHT, 1.0 - 0.55 * min(1.0, dist / max(1.0, float(MAX_DEPTH))))
        v = int(255 * shade)
        img.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
        return img

    def _draw_world_sprites(self, player, enemies, game_map):
        """Collect everything billboarded, sort far -> near, and draw."""
        items = []
        stats = {'trees': 0, 'enemies_view': 0, 'pickups_view': 0, 'drawn': 0}
        margin = self.half_fov + 0.5

        def consider(kind, obj, x, y, max_dist):
            dx = x - player.x
            dy = y - player.y
            dist = math.sqrt(dx * dx + dy * dy)
            # Only cull when dist < 0.05 (essentially on top of the object).
            # The old 0.3 threshold was too aggressive: with PLAYER_SIZE=0.3 and
            # tree radii around 0.2-0.5, the player naturally stands within 0.3
            # units of a trunk, causing trees to vanish on approach.
            if dist < 0.05 or dist > max_dist:
                return False
            angle = self._norm_angle(math.atan2(dy, dx) - player.angle)
            if abs(angle) > margin:
                return False
            items.append((dist, angle, kind, obj))
            return True

        for t in getattr(game_map, 'trees', []):
            if consider('tree', t, t['x'], t['y'], MAX_DEPTH):
                stats['trees'] += 1
        for u in (getattr(game_map, 'undergrowth', None) or getattr(game_map, 'plants', None) or []):
            try:
                consider('plant', u, u['x'], u['y'], MAX_DEPTH * 0.6)
            except Exception:
                pass
        for enemy in enemies:
            if not enemy.alive:
                continue
            if consider('enemy', enemy, enemy.x, enemy.y, MAX_DEPTH):
                stats['enemies_view'] += 1
        for pickup in getattr(game_map, 'pickups', []):
            if not pickup.get('active', True):
                continue
            if consider('pickup', pickup, pickup['x'], pickup['y'], MAX_DEPTH):
                stats['pickups_view'] += 1

        # limit trees to the nearest MAX_RENDER_TREES
        trees_only = sorted((it for it in items if it[2] == 'tree'), key=lambda s: s[0])
        if len(trees_only) > MAX_RENDER_TREES:
            drop = set(id(it) for it in trees_only[MAX_RENDER_TREES:])
            items = [it for it in items if id(it) not in drop]

        items.sort(key=lambda s: s[0], reverse=True)

        pitch_offset = int(player.pitch * self.h)
        horizon = self.h // 2 + pitch_offset
        t_ticks = pygame.time.get_ticks()

        for dist, angle, kind, obj in items:
            screen_x = int((angle / self.fov_rad + 0.5) * self.w)
            unit = self._unit_h(dist)
            floor_y = horizon + unit / 2.0          # where this distance meets the ground

            if kind == 'tree':
                img_list = self.tree_sprites.get(obj.get('type'), self.tree_sprites['balete'])
                variant_idx = obj.get('canopy_seed', 0) % len(img_list)
                img = img_list[variant_idx]
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
                img = self.undergrowth_sprites.get(obj.get('type'), self.undergrowth_sprites['bush'])
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

    def _draw_one(self, img, cx, bottom, sw, sh, dist, stats):
        """Scale, light and depth-test-blit one billboard. Returns columns drawn."""
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
        scaled = pygame.transform.scale(img, (max(1, sw), max(1, sh)))
        self._light_sprite(scaled, dist)
        x = int(cx - sw / 2)
        y = int(bottom - sh)
        n = self._blit_zbuf(scaled, x, y, dist)
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

        if getattr(self, 'enemy_animator', None) is not None and not is_dead:
            tr = self.enemy_animator.transform(enemy, t_ticks * 0.001)
            breathe = tr['breathe']
            sway = tr['sway'] * unit * 0.05
            hover = tr['hover'] * unit
            jitter = tr['jitter']
        else:
            breath_freq = 0.003 if etype in ('kapre', 'tikbalang') else (0.006 if etype in ('sigbin', 'aswang') else 0.004)
            phase = (id(enemy) % 628) / 100.0
            breathe = 1.0 + 0.035 * math.sin(t_ticks * breath_freq + phase)
            if is_dead:
                breathe = 0.28
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
            sway = math.sin(t_ticks * 0.004 + phase) * sw * sway_amp
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

        sh = unit * (0.28 if is_dead else (0.52 if is_crawl else 0.85)) * size_mul * breathe
        sw = sh * img.get_width() / img.get_height()
        bottom = floor_y - hover

        if enemy.hit_flash > 0 or enemy.bound or anim_state == 'stagger':
            img = img.copy()
            if enemy.hit_flash > 0 or anim_state == 'stagger':
                v = max(0, min(220, int(max(enemy.hit_flash, 0.5) * 200)))
                img.fill((v, v // 2, v // 2), special_flags=pygame.BLEND_RGB_ADD)
            if enemy.bound:
                img.fill((60, 20, 120), special_flags=pygame.BLEND_RGB_ADD)

        n = self._draw_one(img, screen_x + sway, bottom, sw, sh, dist, stats)

        cx = screen_x + sway
        top = bottom - sh
        left = cx - sw / 2.0

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

    def _debug_marker(self, x, y, color, label):
        x = int(x)
        y = int(y)
        pygame.draw.circle(self.surface, color, (x, y), 8, 2)
        try:
            self.surface.blit(self.dbg_font.render(label, True, color), (x + 10, y - 6))
        except Exception:
            pass

    def _draw_player_viewmodel(self, player, dt):
        """Draw immersive first-person procedural hands, forearms, sleeves, and weapon viewmodel."""
        weapon_names = ['bolo', 'shotgun', 'revolver']
        wname = weapon_names[player.current_weapon] if 0 <= player.current_weapon < len(weapon_names) else 'bolo'

        sprite = self.weapon_sprites.get(wname)
        if sprite is None:
            return

        scale = 3
        sw = sprite.get_width() * scale
        sh = sprite.get_height() * scale
        scaled = pygame.transform.scale(sprite, (sw, sh))

        # Base screen position (shifted to right arm perspective)
        base_x = self.w // 2 - sw // 3 + 50
        base_y = self.h - sh + 30

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

        # Recoil
        recoil_y = int(self.weapon_recoil * 18)
        if self.weapon_recoil > 0:
            self.weapon_recoil -= dt * 6

        # Reload animation
        reload_offset = 0
        reload_rot = 0
        if player.reloading:
            reload_offset = int(math.sin(player.reload_timer * 4) * 35)
            reload_rot = -10

        # Damage / Death
        if not player.alive:
            reload_offset += 80
            reload_rot += 30
        elif player.damage_flash > 0:
            recoil_y += 10

        final_x = base_x + bob_x + sprint_off_x
        final_y = base_y + bob_y + recoil_y + reload_offset

        # Rotate viewmodel if sprinting, reloading, or dying
        total_rot = sprint_tilt + reload_rot
        if total_rot != 0:
            draw_surf = pygame.transform.rotate(scaled, total_rot)
        else:
            draw_surf = scaled

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

        # Draw weapon viewmodel surface
        self.surface.blit(draw_surf, (final_x, final_y))

        # Draw visible gripping hands / knuckles
        if player.alive:
            # Right hand knuckles / fingers on grip
            pygame.draw.circle(self.surface, skin_color, (int(rh_x - 15), int(rh_y + 10)), 8)
            pygame.draw.circle(self.surface, glove_color, (int(rh_x - 18), int(rh_y + 12)), 6)
            # Left hand support grip (especially for shotgun / rifle)
            if wname == 'shotgun':
                pygame.draw.circle(self.surface, skin_color, (int(lh_x + 10), int(lh_y + 20)), 7)
                pygame.draw.circle(self.surface, glove_color, (int(lh_x + 8), int(lh_y + 22)), 5)
            elif wname == 'revolver':
                pygame.draw.circle(self.surface, skin_color, (int(lh_x + 20), int(lh_y + 25)), 6)

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
