"""
Enemy AI - Implements enemy behaviors, states, and combat interactions.
"""
import math
import random
from settings import *
# Tunable Lighting & Horror Constants
AMBIENT = 0.35
FOG_DISTANCE = 35.0
BEAM_RADIUS = 0.45
ENEMY_EYE_GLOW = True




class EnemyState:
    IDLE = 'idle'
    PATROL = 'patrol'
    INVESTIGATE = 'investigate'
    STALK = 'stalk'
    ATTACK = 'attack'
    RECOVER = 'recover'
    RETREAT = 'retreat'
    DEFEATED = 'defeated'


ENEMY_STATS = {
    'aswang': {
        'health': ASWANG_HEALTH, 'damage': ASWANG_DAMAGE, 'speed': ASWANG_SPEED,
        'attack_range': 1.5, 'detect_range': 8, 'attack_cooldown': 1.2,
        'vulnerabilities': ['repel', 'garlic'], 'resistances': [],
    },
    'manananggal': {
        'health': MANANANGGAL_HEALTH, 'damage': MANANANGGAL_DAMAGE, 'speed': MANANANGGAL_SPEED,
        'attack_range': 2.0, 'detect_range': 10, 'attack_cooldown': 1.5,
        'vulnerabilities': ['repel', 'cross'], 'resistances': ['bind'],
    },
    'tikbalang': {
        'health': TIKBALANG_HEALTH, 'damage': TIKBALANG_DAMAGE, 'speed': TIKBALANG_SPEED,
        'attack_range': 2.0, 'detect_range': 7, 'attack_cooldown': 2.0,
        'vulnerabilities': ['shield'], 'resistances': ['repel'],
    },
    'kapre': {
        'health': KAPRE_HEALTH, 'damage': KAPRE_DAMAGE, 'speed': KAPRE_SPEED,
        'attack_range': 2.5, 'detect_range': 6, 'attack_cooldown': 2.5,
        'vulnerabilities': ['banish'], 'resistances': ['bind', 'repel'],
    },
    'white_lady': {
        'health': WHITE_LADY_HEALTH, 'damage': WHITE_LADY_DAMAGE, 'speed': WHITE_LADY_SPEED,
        'attack_range': 3.0, 'detect_range': 12, 'attack_cooldown': 3.0,
        'vulnerabilities': ['bind'], 'resistances': ['banish'],
    },
    'multo': {
        'health': MULTO_HEALTH, 'damage': MULTO_DAMAGE, 'speed': MULTO_SPEED,
        'attack_range': 2.0, 'detect_range': 8, 'attack_cooldown': 2.0,
        'vulnerabilities': ['banish'], 'resistances': [],
    },
    'sigbin': {
        'health': SIGBIN_HEALTH, 'damage': SIGBIN_DAMAGE, 'speed': SIGBIN_SPEED,
        'attack_range': 1.5, 'detect_range': 7, 'attack_cooldown': 0.8,
        'vulnerabilities': ['bind'], 'resistances': [],
    },
}


class Enemy:
    """Individual enemy entity with AI state machine."""

    def __init__(self, enemy_type, x, y):
        self.type = enemy_type
        self.x = x
        self.y = y
        stats = ENEMY_STATS.get(enemy_type, ENEMY_STATS['aswang'])
        self.max_health = stats['health']
        self.health = self.max_health
        self.damage = stats['damage']
        self.speed = stats['speed']
        self.attack_range = stats['attack_range']
        self.detect_range = stats['detect_range']
        self.attack_cooldown_max = stats['attack_cooldown']
        self.vulnerabilities = stats['vulnerabilities']
        self.resistances = stats['resistances']

        self.state = EnemyState.IDLE
        self.attack_cooldown = 0
        self.state_timer = 0
        self.target_x = x
        self.target_y = y
        self.facing_angle = random.uniform(0, math.pi * 2)
        self.patrol_angle = random.uniform(0, math.pi * 2)
        self.size = 0.3
        self.alive = True
        self.hit_flash = 0
        self.stalk_timer = 0

        # Bind effect
        self.bound = False
        self.bound_timer = 0

        # Repel effect
        self.repelled = False
        self.repel_timer = 0

        # Shield debuff (takes more damage)
        self.shield_debuff = False
        self.shield_debuff_timer = 0

        # Spawn position for respawning logic
        self.spawn_x = x
        self.spawn_y = y
        self.animation_state = 'idle'
        self.anim_time = random.random() * 10.0
        self.anim_frame = random.randint(0, 5)  # Current frame in 6-frame animation
        
        # Animation springs for organic movement
        if ENABLE_ANIMATIONS and ENABLE_ENEMIES_ANIM:
            from animation_core import SpringScalar
            self.spring_y = SpringScalar(0.0, 180.0, 18.0)  # Hover/float spring
            self.spring_x = SpringScalar(0.0, 100.0, 12.0)  # Sway spring
            self.spring_scale = SpringScalar(1.0, 80.0, 10.0)  # Breathing spring
            self.stalk_spring = SpringScalar(0.0, 60.0, 8.0)  # Stalking sway
        else:
            self.spring_y = None
            self.spring_x = None
            self.spring_scale = None
            self.stalk_spring = None

    def distance_to(self, px, py):
        dx = self.x - px
        dy = self.y - py
        return math.sqrt(dx * dx + dy * dy)

    def angle_to(self, px, py):
        return math.atan2(py - self.y, px - self.x)

    def _try_move(self, game_map, new_x, new_y, angle, speed):
        if not game_map.is_solid(new_x, new_y):
            self.x = new_x
            self.y = new_y
            return True
        slide_x = self.x + math.cos(angle) * speed
        if not game_map.is_solid(slide_x, self.y):
            self.x = slide_x
            return True
        slide_y = self.y + math.sin(angle) * speed
        if not game_map.is_solid(self.x, slide_y):
            self.y = slide_y
            return True
        for offset in (0.6, -0.6, 1.2, -1.2):
            deflected = angle + offset
            dx = math.cos(deflected) * speed
            dy = math.sin(deflected) * speed
            if not game_map.is_solid(self.x + dx, self.y + dy):
                self.x += dx
                self.y += dy
                return True
        return False

    def update(self, dt, player_x, player_y, game_map):
        """Update enemy AI state machine."""
        if not self.alive:
            return

        # Update effects
        if self.bound:
            self.bound_timer -= dt
            if self.bound_timer <= 0:
                self.bound = False
            return  # Can't act while bound

        if self.repelled:
            self.repel_timer -= dt
            if self.repel_timer <= 0:
                self.repelled = False
            else:
                # Move away from player
                angle = self.angle_to(player_x, player_y) + math.pi
                move_speed = self.speed * 1.5 * dt
                new_x = self.x + math.cos(angle) * move_speed
                new_y = self.y + math.sin(angle) * move_speed
                self._try_move(game_map, new_x, new_y, angle, move_speed)
                return

        if self.shield_debuff:
            self.shield_debuff_timer -= dt
            if self.shield_debuff_timer <= 0:
                self.shield_debuff = False

        if self.hit_flash > 0:
            self.hit_flash -= dt * 4

        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt

        dist = self.distance_to(player_x, player_y)
        self.state_timer -= dt

        self.anim_time += dt
        
        # Update animation frame (14 FPS cycle)
        frame_time = 1.0 / 14.0
        if self.anim_time >= frame_time:
            self.anim_time -= frame_time
            self.anim_frame = (self.anim_frame + 1) % 6
        if not self.alive:
            self.animation_state = 'death'
        elif self.hit_flash > 0:
            self.animation_state = 'stagger'
        elif self.bound:
            self.animation_state = 'crouch'
        elif self.state == EnemyState.IDLE:
            self.animation_state = 'hover' if self.type in ('manananggal', 'multo', 'white_lady') else 'idle'
        elif self.state == EnemyState.PATROL:
            self.animation_state = 'crawl' if self.type in ('sigbin',) else 'walk'
        elif self.state == EnemyState.INVESTIGATE:
            self.animation_state = 'crawl' if self.type in ('sigbin',) else ('stalk' if self.type == 'aswang' else 'walk')
        elif self.state == EnemyState.STALK:
            self.animation_state = 'stalk'
        elif self.state == EnemyState.ATTACK:
            if dist <= self.attack_range * 1.2:
                self.animation_state = 'attack'
            else:
                self.animation_state = 'lunge' if self.type in ('aswang', 'tikbalang', 'sigbin') else ('sprint' if self.speed > 2.0 else 'run')
        elif self.state == EnemyState.RETREAT:
            self.animation_state = 'run'
        elif self.state == EnemyState.RECOVER:
            self.animation_state = 'crouch'
        else:
            self.animation_state = 'idle'

        if self.state == EnemyState.IDLE:
            if dist < self.detect_range:
                if self.type == 'aswang':
                    self.state = EnemyState.STALK
                    self.state_timer = 3.0 + random.random() * 2
                else:
                    self.state = EnemyState.INVESTIGATE
                    self.state_timer = 2.0
            elif self.state_timer <= 0:
                self.state = EnemyState.PATROL
                self.patrol_angle = random.uniform(0, math.pi * 2)
                self.state_timer = 3.0 + random.random() * 3

        elif self.state == EnemyState.PATROL:
            move_speed = self.speed * 0.3 * dt
            new_x = self.x + math.cos(self.patrol_angle) * move_speed
            new_y = self.y + math.sin(self.patrol_angle) * move_speed
            if not self._try_move(game_map, new_x, new_y, self.patrol_angle, move_speed):
                self.patrol_angle = random.uniform(0, math.pi * 2)

            if dist < self.detect_range:
                self.state = EnemyState.INVESTIGATE
                self.state_timer = 1.5
            elif self.state_timer <= 0:
                self.state = EnemyState.IDLE
                self.state_timer = 2.0 + random.random() * 3

        elif self.state == EnemyState.INVESTIGATE:
            angle = self.angle_to(player_x, player_y)
            self.facing_angle = angle
            move_speed = self.speed * 0.6 * dt
            new_x = self.x + math.cos(angle) * move_speed
            new_y = self.y + math.sin(angle) * move_speed
            self._try_move(game_map, new_x, new_y, angle, move_speed)

            if dist < self.attack_range:
                self.state = EnemyState.ATTACK
                self.state_timer = 0.5
            elif dist > self.detect_range * 1.5:
                self.state = EnemyState.IDLE
                self.state_timer = 3.0

        elif self.state == EnemyState.STALK:
            angle = self.angle_to(player_x, player_y)
            self.facing_angle = angle
            # Stalk: move toward but try to stay at medium range
            desired_dist = self.detect_range * 0.5
            if dist > desired_dist + 1:
                move_speed = self.speed * 0.4 * dt
                new_x = self.x + math.cos(angle) * move_speed
                new_y = self.y + math.sin(angle) * move_speed
                self._try_move(game_map, new_x, new_y, angle, move_speed)
            elif dist < desired_dist - 1:
                move_speed = self.speed * 0.3 * dt
                new_x = self.x - math.cos(angle) * move_speed
                new_y = self.y - math.sin(angle) * move_speed
                self._try_move(game_map, new_x, new_y, angle, move_speed)
            else:
                # Strafe around player
                strafe_angle = angle + math.pi / 2
                move_speed = self.speed * 0.3 * dt
                new_x = self.x + math.cos(strafe_angle) * move_speed
                new_y = self.y + math.sin(strafe_angle) * move_speed
                self._try_move(game_map, new_x, new_y, angle, move_speed)

            self.stalk_timer += dt
            if self.stalk_timer > 5.0 or dist < self.attack_range * 1.5:
                self.state = EnemyState.ATTACK if dist < self.attack_range * 2 else EnemyState.INVESTIGATE
                self.stalk_timer = 0
                self.state_timer = 0.5

        elif self.state == EnemyState.ATTACK:
            angle = self.angle_to(player_x, player_y)
            self.facing_angle = angle

            if dist > self.attack_range:
                # Chase
                move_speed = self.speed * dt
                new_x = self.x + math.cos(angle) * move_speed
                new_y = self.y + math.sin(angle) * move_speed
                self._try_move(game_map, new_x, new_y, angle, move_speed)

            if dist > self.detect_range * 2:
                self.state = EnemyState.IDLE
                self.state_timer = 3.0

            # Check for retreat if low health
            if self.health < self.max_health * 0.25 and self.type in ('aswang', 'sigbin'):
                self.state = EnemyState.RETREAT
                self.state_timer = 3.0

        elif self.state == EnemyState.RECOVER:
            if self.state_timer <= 0:
                self.state = EnemyState.ATTACK if dist < self.detect_range else EnemyState.IDLE
                self.state_timer = 1.0

        elif self.state == EnemyState.RETREAT:
            angle = self.angle_to(player_x, player_y) + math.pi
            move_speed = self.speed * dt
            new_x = self.x + math.cos(angle) * move_speed
            new_y = self.y + math.sin(angle) * move_speed
            self._try_move(game_map, new_x, new_y, angle, move_speed)

            if self.state_timer <= 0 or dist > self.detect_range * 2:
                if self.type == 'aswang':
                    self.state = EnemyState.STALK
                    self.stalk_timer = 0
                else:
                    self.state = EnemyState.IDLE
                self.state_timer = 3.0

    def can_attack(self, player_x, player_y):
        """Check if enemy can attack the player."""
        if not self.alive or self.bound or self.repelled:
            return False
        if self.attack_cooldown > 0:
            return False
        if self.state not in (EnemyState.ATTACK,):
            return False
        dist = self.distance_to(player_x, player_y)
        return dist <= self.attack_range

    def perform_attack(self):
        """Perform attack and return damage."""
        self.attack_cooldown = self.attack_cooldown_max
        self.state_timer = 0.5
        return self.damage

    def take_damage(self, amount, damage_type='physical'):
        """Apply damage to enemy."""
        if not self.alive:
            return

        # Check shield debuff (takes extra damage)
        if self.shield_debuff:
            amount *= 1.5

        self.health -= amount
        self.hit_flash = 1.0

        if self.health <= 0:
            self.health = 0
            self.alive = False
            self.state = EnemyState.DEFEATED
        else:
            # Stagger
            if self.state != EnemyState.RETREAT:
                self.state = EnemyState.RECOVER
                self.state_timer = 0.5

    def apply_ward_effect(self, ward_type):
        """Apply a sacred ward effect to this enemy."""
        if ward_type in self.resistances:
            return False

        is_vulnerable = ward_type in self.vulnerabilities

        if ward_type == 'repel':
            self.repelled = True
            self.repel_timer = 3.0 if is_vulnerable else 1.5
            if is_vulnerable:
                self.take_damage(15, 'sacred')
            return True
        elif ward_type == 'shield':
            self.shield_debuff = True
            self.shield_debuff_timer = 10.0 if is_vulnerable else 5.0
            return True
        elif ward_type == 'banish':
            self.repelled = True
            self.repel_timer = 4.0 if is_vulnerable else 2.0
            if is_vulnerable:
                self.take_damage(20, 'sacred')
            return True
        elif ward_type == 'bind':
            self.bound = True
            self.bound_timer = 5.0 if is_vulnerable else 2.5
            return True
        elif ward_type == 'ultimate':
            self.repelled = True
            self.repel_timer = 5.0
            self.take_damage(30 if is_vulnerable else 15, 'sacred')
            return True

        return False

    def apply_garlic(self):
        """React to garlic."""
        if self.type in ('aswang', 'manananggal'):
            self.repelled = True
            self.repel_timer = 4.0
            self.take_damage(10, 'sacred')
            return True
        return False

    def apply_salt(self):
        """React to salt circle."""
        if self.type in ('aswang', 'multo', 'white_lady', 'sigbin'):
            self.repelled = True
            self.repel_timer = 3.0
            return True
        return False

    def get_state(self):
        """Get serializable state."""
        return {
            'type': self.type,
            'x': self.x, 'y': self.y,
            'health': self.health,
            'alive': self.alive,
            'state': self.state,
        }


class EnemyManager:
    """Manages all enemies in the current level."""

    def __init__(self):
        self.enemies = []
        self.active_effects = []  # Salt/garlic zones

    def spawn_enemies(self, enemy_list):
        """Spawn enemies from map data."""
        self.enemies.clear()
        for edata in enemy_list:
            enemy = Enemy(edata['type'], edata['x'], edata['y'])
            self.enemies.append(enemy)

    def update(self, dt, player_x, player_y, game_map, player=None):
        """Update all enemies with noise sensing, flashlight reaction, and sanity drain."""
        for enemy in self.enemies:
            enemy.update(dt, player_x, player_y, game_map)
            if not enemy.alive:
                continue

            # Stealth & Noise mechanic (Phase 5)
            if player and hasattr(player, 'noise_level') and player.noise_level > 1.5:
                dist = enemy.distance_to(player_x, player_y)
                if dist < player.noise_level * 2.5:
                    if enemy.state in (EnemyState.IDLE, EnemyState.PATROL):
                        enemy.state = EnemyState.INVESTIGATE
                        enemy.investigate_x = player_x
                        enemy.investigate_y = player_y
                        enemy.state_timer = 4.0

            # Proximity sanity drain (Phase 4)
            if player and hasattr(player, 'sanity'):
                dist = enemy.distance_to(player_x, player_y)
                if dist < 4.0:
                    player.sanity = max(0.0, player.sanity - SANITY_DRAIN_ENEMY * dt)

        # Update active effect zones
        expired = []
        for i, effect in enumerate(self.active_effects):
            effect['timer'] -= dt
            if effect['timer'] <= 0:
                expired.append(i)
            else:
                for enemy in self.enemies:
                    if not enemy.alive:
                        continue
                    dist = enemy.distance_to(effect['x'], effect['y'])
                    if dist < effect['radius']:
                        if effect['type'] == 'salt':
                            enemy.apply_salt()
                        elif effect['type'] == 'garlic':
                            enemy.apply_garlic()
        for i in reversed(expired):
            self.active_effects.pop(i)

    def check_attacks(self, player_x, player_y):
        """Check if any enemy attacks the player. Returns total damage."""
        total_damage = 0
        for enemy in self.enemies:
            if enemy.can_attack(player_x, player_y):
                total_damage += enemy.perform_attack()
        return total_damage

    def apply_weapon_hit(self, player_x, player_y, player_angle, weapon_info):
        """Apply weapon damage to enemies in range."""
        hits = []
        w_type = weapon_info['type']
        w_range = weapon_info['range']
        w_damage = weapon_info['damage']
        w_spread = weapon_info.get('spread', 0)
        pellets = weapon_info.get('pellets', 1)

        for enemy in self.enemies:
            if not enemy.alive:
                continue
            dist = enemy.distance_to(player_x, player_y)
            if dist > w_range:
                continue

            angle_to_enemy = math.atan2(enemy.y - player_y, enemy.x - player_x)
            angle_diff = angle_to_enemy - player_angle
            while angle_diff > math.pi:
                angle_diff -= 2 * math.pi
            while angle_diff < -math.pi:
                angle_diff += 2 * math.pi

            if w_type == 'bolo':
                if abs(angle_diff) < 0.5 and dist <= w_range:
                    enemy.take_damage(w_damage, 'physical')
                    hits.append(enemy)
            elif w_type == 'shotgun':
                if abs(angle_diff) < 0.3:
                    # Each pellet has a chance to hit based on spread and distance
                    hit_pellets = 0
                    for _ in range(pellets):
                        pellet_spread = random.uniform(-w_spread, w_spread)
                        if abs(angle_diff + pellet_spread) < 0.25:
                            hit_pellets += 1
                    if hit_pellets > 0:
                        # Damage falloff with distance
                        falloff = max(0.3, 1.0 - dist / w_range)
                        total_dmg = w_damage * hit_pellets / pellets * falloff
                        enemy.take_damage(total_dmg, 'physical')
                        hits.append(enemy)
            elif w_type == 'revolver':
                if abs(angle_diff) < 0.15:
                    falloff = max(0.5, 1.0 - dist / w_range * 0.3)
                    enemy.take_damage(w_damage * falloff, 'physical')
                    hits.append(enemy)

        return hits

    def apply_ward(self, player_x, player_y, ward_info, radius=4.0):
        """Apply a sacred ward effect to nearby enemies."""
        affected = []
        ward_type = ward_info['type']
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            dist = enemy.distance_to(player_x, player_y)
            if dist < radius:
                if enemy.apply_ward_effect(ward_type):
                    affected.append(enemy)
        return affected

    def add_salt_zone(self, x, y):
        """Create a salt protection zone."""
        self.active_effects.append({
            'type': 'salt', 'x': x, 'y': y,
            'radius': 2.0, 'timer': 8.0,
        })

    def add_garlic_zone(self, x, y):
        """Create a garlic zone."""
        self.active_effects.append({
            'type': 'garlic', 'x': x, 'y': y,
            'radius': 2.5, 'timer': 6.0,
        })

    def get_alive_enemies(self):
        return [e for e in self.enemies if e.alive]

    def get_states(self):
        return [e.get_state() for e in self.enemies]
