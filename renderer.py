"""
Raycasting renderer - provides pseudo-3D first-person view.
"""
import math
import random
import pygame
import numpy as np
from settings import *


class Renderer:
    """Raycasting-based pseudo-3D renderer."""

    def __init__(self, internal_surface, textures, weapon_sprites, enemy_sprites, pickup_sprites):
        self.surface = internal_surface
        self.w = INTERNAL_WIDTH
        self.h = INTERNAL_HEIGHT
        self.textures = textures
        self.weapon_sprites = weapon_sprites
        self.enemy_sprites = enemy_sprites
        self.pickup_sprites = pickup_sprites
        self.crosshair = None

        # Precompute ray angles
        self.fov_rad = math.radians(FOV)
        self.half_fov = self.fov_rad / 2
        self.num_rays = NUM_RAYS
        self.ray_angles = []
        for i in range(self.num_rays):
            angle_offset = (i / self.num_rays - 0.5) * self.fov_rad
            self.ray_angles.append(angle_offset)

        # Z-buffer for sprite occlusion
        self.z_buffer = [0.0] * self.num_rays

        # Floor/ceiling cache & procedural forest assets
        from asset_generator import generate_tree_billboard, generate_undergrowth_sprite, generate_world_ground_texture
        self.tree_sprites = {
            'balete': generate_tree_billboard('balete', 64, 128),
            'bamboo': generate_tree_billboard('bamboo', 64, 128),
            'banana': generate_tree_billboard('banana', 64, 128),
            'pine': generate_tree_billboard('pine', 64, 128),
            'dead': generate_tree_billboard('dead', 64, 128),
            'palm': generate_tree_billboard('palm', 64, 128),
        }
        self.undergrowth_sprites = {
            'fern': generate_undergrowth_sprite('fern', 32, 32),
            'mushroom': generate_undergrowth_sprite('mushroom', 32, 32),
            'rock': generate_undergrowth_sprite('rock', 32, 32),
            'bush': generate_undergrowth_sprite('bush', 32, 32),
        }
        self.world_ground_tex = generate_world_ground_texture(GROUND_TEX_SIZE, GROUND_TEX_SIZE)
        self.screenshot_saved = False
        self.frame_counter = 0

        self.floor_surf = pygame.Surface((self.w, self.h // 2))
        self._generate_floor_gradient()

        # Weapon animation
        self.weapon_bob = 0
        self.weapon_recoil = 0
        self.muzzle_flash = 0

        # Screen effects
        self.screen_shake = 0
        self.vignette = self._generate_vignette()

        # Particles (Fireflies, dust motes)
        self.particles = []
        for _ in range(35):
            self.particles.append({
                'x': random.uniform(0, self.w),
                'y': random.uniform(0, self.h),
                'vx': random.uniform(-0.5, 0.5),
                'vy': random.uniform(-0.3, 0.3),
                'size': random.uniform(1.0, 2.5),
                'phase': random.uniform(0, math.pi * 2),
                'color': (random.randint(180, 255), random.randint(200, 255), random.randint(100, 180))
            })

        # Debug overlay (F3)
        self.show_debug = True
        self.timings = {'rays': 0.0, 'post': 0.0, 'total': 0.0}

        # Ward visual effects
        self.ward_effect_timer = 0
        self.ward_effect_type = None

    def _generate_floor_gradient(self):
        """Generate gradient for floor rendering."""
        for y in range(self.h // 2):
            t = y / (self.h // 2)
            r = int(FLOOR_COLOR[0] * t * 0.8)
            g = int(FLOOR_COLOR[1] * t * 0.8)
            b = int(FLOOR_COLOR[2] * t * 0.8)
            pygame.draw.line(self.floor_surf, (r, g, b), (0, y), (self.w, y))

    def _generate_vignette(self):
        """Generate a vignette overlay."""
        vig = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        cx, cy = self.w // 2, self.h // 2
        max_dist = math.sqrt(cx * cx + cy * cy)
        for ring in range(0, int(max_dist), 4):
            alpha = int((ring / max_dist) ** 2 * 180)
            alpha = min(180, alpha)
            pygame.draw.circle(vig, (0, 0, 0, alpha), (cx, cy), int(max_dist) - ring, 4)
        return vig

    def render_frame(self, player, game_map, enemies, effects, dt):
        """Render a complete frame."""
        t_start = pygame.time.get_ticks()
        self.surface.fill(SKY_COLOR)

        # Draw ceiling with colored fog gradient
        pitch_offset = int(player.pitch * self.h)
        half_h = self.h // 2
        for y in range(max(0, half_h + pitch_offset)):
            t = y / max(1, half_h + pitch_offset)
            r = int(SKY_COLOR[0] * (1 - t) + FOG_COLOR[0] * t)
            g = int(SKY_COLOR[1] * (1 - t) + FOG_COLOR[1] * t)
            b = int(SKY_COLOR[2] * (1 - t) + FOG_COLOR[2] * t)
            pygame.draw.line(self.surface, (r, g, b), (0, y), (self.w, y))

        # Draw floor
        self.surface.blit(self.floor_surf, (0, max(0, half_h + pitch_offset)))

        # Cast rays and draw walls
        t_rays = pygame.time.get_ticks()
        self._cast_rays(player, game_map)
        self.timings['rays'] = pygame.time.get_ticks() - t_rays

        # Draw procedural forest tree billboards
        self._draw_trees(player, game_map)

        # Draw sprites (enemies and pickups)
        self._draw_sprites(player, enemies, game_map)

        # Screenshot capture for chapter comparison
        self.frame_counter += 1
        if self.frame_counter == 30 and not self.screenshot_saved:
            os.makedirs('screenshots', exist_ok=True)
            pygame.image.save(self.surface, 'screenshots/chapter_1_after.png')
            self.screenshot_saved = True

        # Draw flashlight cone effect
        if player.flashlight_on and player.flashlight_battery > 0:
            self._draw_flashlight(player)

        # Particles (Fireflies and dust motes)
        if ENABLE_PARTICLES:
            for p in self.particles:
                p['x'] = (p['x'] + p['vx']) % self.w
                p['y'] = (p['y'] + p['vy']) % self.h
                p['phase'] += dt * 2
                alpha = int(abs(math.sin(p['phase'])) * 180)
                psurf = pygame.Surface((int(p['size'] * 2), int(p['size'] * 2)), pygame.SRCALPHA)
                pygame.draw.circle(psurf, (*p['color'], alpha), (int(p['size']), int(p['size'])), int(p['size']))
                self.surface.blit(psurf, (int(p['x']), int(p['y'])))

        # Vignette and Sanity / Low HP blood vignette
        self.surface.blit(self.vignette, (0, 0))
        if player.health < 35 or (ENABLE_SANITY and player.sanity < 30):
            urgency = max((35 - player.health) / 35.0, (30 - player.sanity) / 30.0)
            blood_vig = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            alpha = int(urgency * 120 + math.sin(pygame.time.get_ticks() * 0.006) * 30)
            pygame.draw.rect(blood_vig, (180, 0, 0, max(0, min(200, alpha))), (0, 0, self.w, self.h), int(20 * urgency))
            self.surface.blit(blood_vig, (0, 0))

        # Ward effects
        if self.ward_effect_timer > 0:
            self._draw_ward_effect(dt)

        # Damage flash
        if player.damage_flash > 0:
            flash = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            alpha = int(player.damage_flash * 120)
            flash.fill((200, 0, 0, alpha))
            self.surface.blit(flash, (0, 0))

        # Muzzle flash
        if self.muzzle_flash > 0:
            self._draw_muzzle_flash()
            self.muzzle_flash -= dt * 8

        # Draw weapon
        self._draw_weapon(player, dt)

        # Draw crosshair
        if self.crosshair:
            cx = self.w // 2 - self.crosshair.get_width() // 2
            cy = self.h // 2 - self.crosshair.get_height() // 2
            self.surface.blit(self.crosshair, (cx, cy))

    def _cast_rays(self, player, game_map):
        """Cast rays for wall rendering."""
        px, py = player.x, player.y
        pa = player.angle
        pitch_offset = int(player.pitch * self.h)

        for i in range(self.num_rays):
            ray_angle = pa + self.ray_angles[i]
            sin_a = math.sin(ray_angle)
            cos_a = math.cos(ray_angle)

            # DDA raycasting
            dist, wall_type, hit_x_frac = self._dda_cast(px, py, cos_a, sin_a, game_map)

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
                tex_x = int(hit_x_frac * tex.get_width()) % tex.get_width()
                # Get texture column
                tex_col = pygame.Surface((1, tex.get_height()), pygame.SRCALPHA)
                tex_col.blit(tex, (0, 0), (tex_x, 0, 1, tex.get_height()))
                scaled_col = pygame.transform.scale(tex_col, (1, max(1, wall_h)))

                # Distance shading
                shade = max(0.15, 1.0 - corrected_dist / MAX_DEPTH)
                shaded = scaled_col.copy()
                dark = pygame.Surface((1, max(1, wall_h)), pygame.SRCALPHA)
                dark.fill((0, 0, 0, int((1 - shade) * 220)))
                shaded.blit(dark, (0, 0))

                self.surface.blit(shaded, (i, max(0, draw_start)),
                                  (0, max(0, -draw_start), 1, min(wall_h, self.h - max(0, draw_start))))
            else:
                # Fallback solid color
                color = self._get_wall_color(wall_type, corrected_dist)
                if draw_start < self.h and draw_end > 0:
                    ds = max(0, draw_start)
                    de = min(self.h, draw_end)
                    pygame.draw.line(self.surface, color, (i, ds), (i, de))

    def _dda_cast(self, px, py, cos_a, sin_a, game_map):
        """Digital Differential Analyzer raycasting."""
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
            return MAX_DEPTH, WALL_STONE, 0

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

        return dist, wall_type, hit_frac

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

    def _draw_trees(self, player, game_map):
        """Draw procedural forest tree billboards with Z-buffer occlusion, culling, and sorting."""
        tree_list = []
        for t in game_map.trees:
            dx = t['x'] - player.x
            dy = t['y'] - player.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 0.4 or dist > MAX_DEPTH:
                continue
            angle = math.atan2(dy, dx) - player.angle
            while angle > math.pi:
                angle -= 2 * math.pi
            while angle < -math.pi:
                angle += 2 * math.pi
            if abs(angle) > self.half_fov + 0.3:
                continue
            tree_list.append({
                'dist': dist, 'angle': angle, 'tree': t
            })

        tree_list.sort(key=lambda s: s['dist'], reverse=True)
        tree_list = tree_list[:MAX_RENDER_TREES]

        pitch_offset = int(player.pitch * self.h)

        for item in tree_list:
            dist = item['dist']
            angle = item['angle']
            t_data = item['tree']

            screen_x = int((angle / self.fov_rad + 0.5) * self.w)
            tree_h = int(self.h * 1.2 * t_data['scale'] / dist)
            tree_w = int(tree_h * 0.5)

            if tree_h < 4:
                continue

            img = self.tree_sprites.get(t_data['type'], self.tree_sprites['balete'])
            scaled = pygame.transform.scale(img, (max(2, tree_w), max(2, tree_h)))

            shade = max(0.15, 1.0 - dist / MAX_DEPTH)
            dark = pygame.Surface(scaled.get_size(), pygame.SRCALPHA)
            dark.fill((0, 0, 0, int((1 - shade) * 180)))
            scaled.blit(dark, (0, 0))

            draw_x = screen_x - tree_w // 2
            draw_y = self.h // 2 - tree_h // 2 + pitch_offset + int(tree_h * 0.1)

            start_col = max(0, draw_x)
            end_col = min(self.w, draw_x + tree_w)
            visible = False
            step = max(1, (end_col - start_col) // 6)
            for col in range(start_col, end_col, step):
                if col < len(self.z_buffer) and self.z_buffer[col] > dist:
                    visible = True
                    break

            if visible:
                self.surface.blit(scaled, (draw_x, draw_y))

    def _draw_sprites(self, player, enemies, game_map):
        """Draw enemy and pickup sprites using billboard rendering."""
        sprite_list = []

        # Add enemies
        for enemy in enemies:
            if not enemy.alive:
                continue
            dx = enemy.x - player.x
            dy = enemy.y - player.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 0.3 or dist > MAX_DEPTH:
                continue
            angle = math.atan2(dy, dx) - player.angle
            while angle > math.pi:
                angle -= 2 * math.pi
            while angle < -math.pi:
                angle += 2 * math.pi
            if abs(angle) > self.half_fov + 0.2:
                continue
            sprite_list.append({
                'dist': dist, 'angle': angle,
                'type': 'enemy', 'data': enemy,
            })

        # Add pickups
        for pickup in game_map.pickups:
            if not pickup.get('active', True):
                continue
            dx = pickup['x'] - player.x
            dy = pickup['y'] - player.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 0.3 or dist > MAX_DEPTH:
                continue
            angle = math.atan2(dy, dx) - player.angle
            while angle > math.pi:
                angle -= 2 * math.pi
            while angle < -math.pi:
                angle += 2 * math.pi
            if abs(angle) > self.half_fov + 0.2:
                continue
            sprite_list.append({
                'dist': dist, 'angle': angle,
                'type': 'pickup', 'data': pickup,
            })

        # Sort back to front
        sprite_list.sort(key=lambda s: s['dist'], reverse=True)

        pitch_offset = int(player.pitch * self.h)

        for sprite in sprite_list:
            dist = sprite['dist']
            angle = sprite['angle']

            # Screen position
            screen_x = int((angle / self.fov_rad + 0.5) * self.w)

            # Sprite size based on distance
            sprite_h = int(self.h * 0.6 / dist)
            sprite_w = sprite_h

            if sprite_h < 2:
                continue

            # Get sprite image
            if sprite['type'] == 'enemy':
                enemy = sprite['data']
                state = 'attack' if enemy.state == 'attack' else 'idle'
                if enemy.type in self.enemy_sprites:
                    img = self.enemy_sprites[enemy.type].get(state,
                          self.enemy_sprites[enemy.type].get('idle'))
                else:
                    img = None

                if img is None:
                    # Fallback colored rectangle
                    img = pygame.Surface((32, 32), pygame.SRCALPHA)
                    pygame.draw.rect(img, (200, 50, 50), (4, 4, 24, 24))

                # Hit flash
                if enemy.hit_flash > 0:
                    flash_img = img.copy()
                    flash_surf = pygame.Surface(img.get_size(), pygame.SRCALPHA)
                    flash_surf.fill((255, 255, 255, int(enemy.hit_flash * 180)))
                    flash_img.blit(flash_surf, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
                    img = flash_img

                # Bound effect
                if enemy.bound:
                    bound_img = img.copy()
                    bound_surf = pygame.Surface(img.get_size(), pygame.SRCALPHA)
                    bound_surf.fill((100, 50, 200, 80))
                    bound_img.blit(bound_surf, (0, 0))
                    img = bound_img
            elif sprite['type'] == 'pickup':
                pickup = sprite['data']
                ptype = pickup['type']
                if ptype in self.pickup_sprites:
                    img = self.pickup_sprites[ptype]
                else:
                    img = None
                if img is None:
                    img = pygame.Surface((32, 32), pygame.SRCALPHA)
                    pygame.draw.rect(img, (255, 255, 0), (8, 8, 16, 16))

            scaled = pygame.transform.scale(img, (max(1, sprite_w), max(1, sprite_h)))

            # Distance shading
            shade_factor = max(0.2, 1.0 - dist / MAX_DEPTH)
            dark = pygame.Surface(scaled.get_size(), pygame.SRCALPHA)
            dark.fill((0, 0, 0, int((1 - shade_factor) * 200)))
            scaled.blit(dark, (0, 0))

            draw_x = screen_x - sprite_w // 2
            draw_y = self.h // 2 - sprite_h // 2 + pitch_offset

            # Z-buffer occlusion check
            start_col = max(0, draw_x)
            end_col = min(self.w, draw_x + sprite_w)
            visible = False
            for col in range(start_col, end_col, max(1, (end_col - start_col) // 8)):
                if col < len(self.z_buffer) and self.z_buffer[col] > dist:
                    visible = True
                    break

            if visible:
                self.surface.blit(scaled, (draw_x, draw_y))

    def _draw_flashlight(self, player):
        """Draw flashlight cone effect."""
        flash = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        cx, cy = self.w // 2, self.h // 2
        # Flashlight cone
        cone_radius = int(self.w * 0.25)
        flicker = 0
        if player.flashlight_battery < 20:
            import random
            flicker = random.randint(0, 30)
        alpha = max(0, min(60, int(40 - flicker)))
        pygame.draw.circle(flash, (255, 240, 200, alpha), (cx, cy), cone_radius)
        # Outer darkening
        for ring in range(cone_radius, max(self.w, self.h), 2):
            a = min(100, (ring - cone_radius) // 2)
            pygame.draw.circle(flash, (0, 0, 0, a), (cx, cy), ring, 2)
        self.surface.blit(flash, (0, 0))

    def _draw_weapon(self, player, dt):
        """Draw the current weapon sprite at bottom of screen."""
        weapon_names = ['bolo', 'shotgun', 'revolver']
        wname = weapon_names[player.current_weapon]

        if wname in self.weapon_sprites:
            sprite = self.weapon_sprites[wname]
        else:
            return

        # Scale weapon sprite
        scale = 3
        sw = sprite.get_width() * scale
        sh = sprite.get_height() * scale
        scaled = pygame.transform.scale(sprite, (sw, sh))

        # Position (shifted to right arm perspective)
        base_x = self.w // 2 - sw // 3 + 45
        base_y = self.h - sh + 25

        # Bob
        bob_x = int(math.sin(self.weapon_bob) * 3)
        bob_y = int(abs(math.cos(self.weapon_bob)) * 4)
        self.weapon_bob += dt * 4 if (abs(player.bob_amount) > 0.5) else 0

        # Recoil
        recoil_y = int(self.weapon_recoil * 15)
        if self.weapon_recoil > 0:
            self.weapon_recoil -= dt * 5

        # Reload animation
        reload_offset = 0
        if player.reloading:
            reload_offset = int(math.sin(player.reload_timer * 3) * 30)

        final_x = base_x + bob_x
        final_y = base_y + bob_y + recoil_y + reload_offset

        self.surface.blit(scaled, (final_x, final_y))

    def _draw_muzzle_flash(self):
        """Draw muzzle flash effect."""
        cx, cy = self.w // 2, self.h // 2 + 20
        radius = int(self.muzzle_flash * 30)
        if radius > 0:
            flash = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            pygame.draw.circle(flash, (255, 220, 100, int(self.muzzle_flash * 200)),
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
        self.screen_shake = amount
