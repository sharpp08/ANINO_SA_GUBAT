"""
Player module - handles player state, movement, and collision.
"""
import math
import pygame
from settings import *


class Player:
    """First-person player controller with collision detection."""

    def __init__(self, x=1.5, y=1.5, angle=0):
        self.x = x
        self.y = y
        self.angle = angle
        self.pitch = 0

        # Stats
        self.health = PLAYER_MAX_HEALTH
        self.armor = 0
        self.alive = True
        self.damage_flash = 0
        self.sanity = SANITY_MAX
        self.stamina = STAMINA_MAX
        self.noise_level = 0.0

        # Weapons: 0=bolo, 1=shotgun, 2=revolver
        self.current_weapon = 0
        self.ammo_shotgun = 10
        self.ammo_revolver = 12
        self.shotgun_mag = SHOTGUN_MAG_SIZE
        self.revolver_mag = REVOLVER_MAG_SIZE
        self.weapon_cooldown = 0
        self.reloading = False
        self.reload_timer = 0

        # Flashlight
        self.flashlight_on = True
        self.flashlight_battery = FLASHLIGHT_MAX_BATTERY

        # Sacred items
        self.faith_energy = 50.0
        self.salt_count = 5
        self.garlic_count = 3
        self.rosary_cooldown = 0
        self.cross_cooldown = 0
        self.bible_pages = 0
        self.wards_unlocked = [True, False, False, False, False]
        self.selected_ward = 0
        self.ward_cooldowns = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.ward_menu_open = False

        # Movement state
        self.is_sprinting = False
        self.is_crouching = False
        self.bob_timer = 0
        self.bob_amount = 0

        # Inventory
        self.journal_entries = []
        self.relics = []

        # Chapter/checkpoint
        self.current_chapter = 1
        self.checkpoint_x = x
        self.checkpoint_y = y
        self.checkpoint_angle = angle

        # Animation & Physics Springs
        if ENABLE_ANIMATIONS and ENABLE_SPRING_PHYSICS:
            from animation_core import SpringScalar, Spring2D
            self.spring_bob = SpringScalar(0.0, 150.0, 12.0)
            self.spring_sway = Spring2D(0.0, 0.0, 100.0, 10.0)
        else:
            self.spring_bob = None
            self.spring_sway = None

    def update(self, dt, keys, mouse_dx, mouse_dy, game_map):
        """Update player state each frame."""
        if not self.alive:
            return

        # Mouse look
        self.angle += mouse_dx * PLAYER_ROT_SPEED
        self.angle %= math.pi * 2
        self.pitch -= mouse_dy * PLAYER_ROT_SPEED * 0.5
        self.pitch = max(-0.5, min(0.5, self.pitch))

        # Sprint & Crouch with Stamina
        wants_sprint = keys[pygame.K_LSHIFT] and (keys[pygame.K_w] or keys[pygame.K_s] or keys[pygame.K_a] or keys[pygame.K_d])
        if wants_sprint and self.stamina > 5.0 and not self.is_crouching:
            self.is_sprinting = True
            self.stamina = max(0.0, self.stamina - STAMINA_DRAIN_RATE * dt)
        else:
            self.is_sprinting = False
            self.stamina = min(STAMINA_MAX, self.stamina + STAMINA_REGEN_RATE * dt)

        self.is_crouching = keys[pygame.K_LCTRL]

        # Movement speed
        speed = PLAYER_SPRINT_SPEED if self.is_sprinting else PLAYER_SPEED
        if self.is_crouching:
            speed *= 0.5
        move_x = 0
        move_y = 0

        if keys[pygame.K_w]:
            move_x += math.cos(self.angle) * speed * dt
            move_y += math.sin(self.angle) * speed * dt
        if keys[pygame.K_s]:
            move_x -= math.cos(self.angle) * speed * dt
            move_y -= math.sin(self.angle) * speed * dt
        if keys[pygame.K_a]:
            move_x += math.cos(self.angle - math.pi / 2) * speed * dt
            move_y += math.sin(self.angle - math.pi / 2) * speed * dt
        if keys[pygame.K_d]:
            move_x += math.cos(self.angle + math.pi / 2) * speed * dt
            move_y += math.sin(self.angle + math.pi / 2) * speed * dt

        # Collision detection - separate X and Y
        new_x = self.x + move_x
        new_y = self.y + move_y
        pad = PLAYER_SIZE

        if not game_map.is_solid(new_x + pad, self.y) and not game_map.is_solid(new_x - pad, self.y):
            self.x = new_x
        if not game_map.is_solid(self.x, new_y + pad) and not game_map.is_solid(self.x, new_y - pad):
            self.y = new_y

        # Head bob & footsteps noise
        moving = abs(move_x) > 0.001 or abs(move_y) > 0.001
        if moving:
            bob_speed = 8 if self.is_sprinting else 5
            self.bob_timer += dt * bob_speed
            self.bob_amount = math.sin(self.bob_timer) * (4 if self.is_sprinting else 2)
            if self.is_sprinting:
                self.noise_level = max(self.noise_level, 3.5)
            elif not self.is_crouching:
                self.noise_level = max(self.noise_level, 1.2)
        else:
            self.bob_timer = 0
            self.bob_amount *= 0.8

        # Noise decay
        self.noise_level = max(0.0, self.noise_level - dt * 3.0)

        # Sanity mechanics: drain in dark or low battery, restore in light
        if not self.flashlight_on or self.flashlight_battery < 15:
            self.sanity = max(0.0, self.sanity - SANITY_DRAIN_DARK * dt)
        else:
            self.sanity = min(SANITY_MAX, self.sanity + SANITY_REGEN_LIGHT * dt * 0.5)

        # Weapon cooldown
        if self.weapon_cooldown > 0:
            self.weapon_cooldown -= dt

        # Reload
        if self.reloading:
            self.reload_timer -= dt
            if self.reload_timer <= 0:
                self.reloading = False
                if self.current_weapon == 1:
                    needed = SHOTGUN_MAG_SIZE - self.shotgun_mag
                    transfer = min(needed, self.ammo_shotgun)
                    self.shotgun_mag += transfer
                    self.ammo_shotgun -= transfer
                elif self.current_weapon == 2:
                    needed = REVOLVER_MAG_SIZE - self.revolver_mag
                    transfer = min(needed, self.ammo_revolver)
                    self.revolver_mag += transfer
                    self.ammo_revolver -= transfer

        # Flashlight
        if self.flashlight_on:
            self.flashlight_battery -= FLASHLIGHT_DRAIN_RATE * dt
            if self.flashlight_battery <= 0:
                self.flashlight_battery = 0
                self.flashlight_on = False
        else:
            self.flashlight_battery = min(FLASHLIGHT_MAX_BATTERY,
                                          self.flashlight_battery + FLASHLIGHT_RECHARGE_RATE * dt)

        # Faith energy regen
        self.faith_energy = min(FAITH_ENERGY_MAX,
                                self.faith_energy + FAITH_ENERGY_REGEN * dt)

        # Ward cooldowns
        for i in range(5):
            if self.ward_cooldowns[i] > 0:
                self.ward_cooldowns[i] -= dt

        # Item cooldowns
        if self.rosary_cooldown > 0:
            self.rosary_cooldown -= dt
        if self.cross_cooldown > 0:
            self.cross_cooldown -= dt

        # Damage flash decay
        if self.damage_flash > 0:
            self.damage_flash -= dt * 3

        if ENABLE_ANIMATIONS and ENABLE_SPRING_PHYSICS and self.spring_bob:
            moving = 1.0 if (keys[pygame.K_w] or keys[pygame.K_s] or keys[pygame.K_a] or keys[pygame.K_d]) else 0.0
            self.spring_bob.update(dt, moving * (5.0 if self.is_sprinting else 3.0))
            self.spring_sway.update(dt, mouse_dx * 0.1, mouse_dy * 0.1)

    def fire_weapon(self):
        """Attempt to fire the current weapon. Cancel reload if active. Returns hit info."""
        if self.weapon_cooldown > 0:
            return None

        # Cancel reload if player attacks
        if self.reloading:
            self.reloading = False
            self.reload_timer = 0

        if self.current_weapon == 0:  # Bolo
            self.weapon_cooldown = BOLO_COOLDOWN
            self.noise_level = max(self.noise_level, BOLO_NOISE)
            return {
                'type': 'bolo',
                'damage': BOLO_DAMAGE,
                'range': BOLO_RANGE,
                'spread': 0,
            }
        elif self.current_weapon == 1:  # Shotgun
            if self.shotgun_mag <= 0:
                self.start_reload()
                return None
            self.shotgun_mag -= 1
            self.weapon_cooldown = SHOTGUN_COOLDOWN
            self.noise_level = max(self.noise_level, SHOTGUN_NOISE)
            return {
                'type': 'shotgun',
                'damage': SHOTGUN_DAMAGE,
                'range': SHOTGUN_RANGE,
                'spread': SHOTGUN_SPREAD,
                'pellets': SHOTGUN_PELLETS,
            }
        elif self.current_weapon == 2:  # Revolver
            if self.revolver_mag <= 0:
                self.start_reload()
                return None
            self.revolver_mag -= 1
            self.weapon_cooldown = REVOLVER_COOLDOWN
            self.noise_level = max(self.noise_level, REVOLVER_NOISE)
            return {
                'type': 'revolver',
                'damage': REVOLVER_DAMAGE,
                'range': REVOLVER_RANGE,
                'spread': 0,
            }
        return None

    def start_reload(self):
        """Start reloading the current weapon."""
        if self.reloading:
            return
        if self.current_weapon == 1:
            if self.ammo_shotgun > 0 and self.shotgun_mag < SHOTGUN_MAG_SIZE:
                self.reloading = True
                self.reload_timer = SHOTGUN_RELOAD_TIME
                self.noise_level = max(self.noise_level, RELOAD_NOISE)
        elif self.current_weapon == 2:
            if self.ammo_revolver > 0 and self.revolver_mag < REVOLVER_MAG_SIZE:
                self.reloading = True
                self.reload_timer = REVOLVER_RELOAD_TIME
                self.noise_level = max(self.noise_level, RELOAD_NOISE)

    def switch_weapon(self, weapon_id):
        """Switch to weapon by index."""
        if weapon_id != self.current_weapon:
            self.current_weapon = weapon_id
            self.reloading = False
            self.weapon_cooldown = 0.3

    def take_damage(self, amount):
        """Apply damage to the player."""
        if self.armor > 0:
            armor_absorb = min(self.armor, amount * 0.6)
            self.armor -= armor_absorb
            amount -= armor_absorb
        self.health -= amount
        self.damage_flash = 1.0
        if self.health <= 0:
            self.health = 0
            self.alive = False

    def heal(self, amount):
        self.health = min(PLAYER_MAX_HEALTH, self.health + amount)

    def pickup_item(self, pickup):
        """Process a pickup item."""
        ptype = pickup['type']
        amount = pickup.get('amount', 1)

        if ptype == 'health':
            if self.health >= PLAYER_MAX_HEALTH:
                return False
            self.heal(amount)
        elif ptype == 'ammo_shotgun':
            if self.ammo_shotgun >= SHOTGUN_MAX_AMMO:
                return False
            self.ammo_shotgun = min(SHOTGUN_MAX_AMMO, self.ammo_shotgun + amount)
        elif ptype == 'ammo_revolver':
            if self.ammo_revolver >= REVOLVER_MAX_AMMO:
                return False
            self.ammo_revolver = min(REVOLVER_MAX_AMMO, self.ammo_revolver + amount)
        elif ptype == 'salt':
            if self.salt_count >= SALT_MAX:
                return False
            self.salt_count = min(SALT_MAX, self.salt_count + amount)
        elif ptype == 'garlic':
            if self.garlic_count >= GARLIC_MAX:
                return False
            self.garlic_count = min(GARLIC_MAX, self.garlic_count + amount)
        elif ptype == 'battery':
            if self.flashlight_battery >= FLASHLIGHT_MAX_BATTERY:
                return False
            self.flashlight_battery = min(FLASHLIGHT_MAX_BATTERY,
                                          self.flashlight_battery + amount)
        elif ptype == 'faith':
            if self.faith_energy >= FAITH_ENERGY_MAX:
                return False
            self.faith_energy = min(FAITH_ENERGY_MAX, self.faith_energy + amount)
        elif ptype == 'bible_page':
            self.bible_pages += amount
            # Unlock wards based on pages
            if self.bible_pages >= 1:
                self.wards_unlocked[1] = True
            if self.bible_pages >= 2:
                self.wards_unlocked[2] = True
            if self.bible_pages >= 3:
                self.wards_unlocked[3] = True
            if self.bible_pages >= 5:
                self.wards_unlocked[4] = True
        return True

    def cast_ward(self, ward_index):
        """Attempt to cast a sacred ward. Returns ward info or None."""
        if ward_index < 0 or ward_index >= 5:
            return None
        if not self.wards_unlocked[ward_index]:
            return None
        if self.ward_cooldowns[ward_index] > 0:
            return None

        costs = [WARD_1_COST, WARD_2_COST, WARD_3_COST, WARD_4_COST, WARD_5_COST]
        cooldowns = [WARD_1_COOLDOWN, WARD_2_COOLDOWN, WARD_3_COOLDOWN, WARD_4_COOLDOWN, WARD_5_COOLDOWN]

        if self.faith_energy < costs[ward_index]:
            return None

        self.faith_energy -= costs[ward_index]
        self.ward_cooldowns[ward_index] = cooldowns[ward_index]

        ward_names = [
            'Light of the Almighty',
            'Shield of Faith',
            'Banishment of Darkness',
            'Binding of the Shadow',
            'The Final Benediction',
        ]
        ward_types = ['repel', 'shield', 'banish', 'bind', 'ultimate']

        return {
            'index': ward_index,
            'name': ward_names[ward_index],
            'type': ward_types[ward_index],
        }

    def use_salt(self):
        """Use salt to create protective zone."""
        if self.salt_count > 0:
            self.salt_count -= 1
            return True
        return False

    def use_garlic(self):
        """Throw garlic."""
        if self.garlic_count > 0:
            self.garlic_count -= 1
            return True
        return False

    def use_rosary(self):
        """Activate rosary prayer and restore sanity."""
        if self.rosary_cooldown <= 0:
            self.rosary_cooldown = 8.0
            self.sanity = min(SANITY_MAX, self.sanity + 25.0)
            return True
        return False

    def use_cross(self):
        """Activate cross radiance and restore sanity."""
        if self.cross_cooldown <= 0:
            self.cross_cooldown = 6.0
            self.sanity = min(SANITY_MAX, self.sanity + 35.0)
            return True
        return False

    def set_checkpoint(self, x, y):
        """Set a checkpoint position."""
        self.checkpoint_x = x
        self.checkpoint_y = y
        self.checkpoint_angle = self.angle

    def respawn(self):
        """Respawn at checkpoint."""
        self.x = self.checkpoint_x
        self.y = self.checkpoint_y
        self.angle = self.checkpoint_angle
        self.health = PLAYER_MAX_HEALTH
        self.sanity = SANITY_MAX
        self.stamina = STAMINA_MAX
        self.alive = True
        self.damage_flash = 0

    def get_state(self):
        """Get serializable player state."""
        return {
            'x': self.x, 'y': self.y, 'angle': self.angle,
            'health': self.health, 'armor': self.armor,
            'sanity': self.sanity, 'stamina': self.stamina,
            'current_weapon': self.current_weapon,
            'ammo_shotgun': self.ammo_shotgun,
            'ammo_revolver': self.ammo_revolver,
            'shotgun_mag': self.shotgun_mag,
            'revolver_mag': self.revolver_mag,
            'flashlight_battery': self.flashlight_battery,
            'faith_energy': self.faith_energy,
            'salt_count': self.salt_count,
            'garlic_count': self.garlic_count,
            'bible_pages': self.bible_pages,
            'wards_unlocked': self.wards_unlocked[:],
            'journal_entries': self.journal_entries[:],
            'relics': self.relics[:],
            'current_chapter': self.current_chapter,
            'checkpoint_x': self.checkpoint_x,
            'checkpoint_y': self.checkpoint_y,
        }

    def load_state(self, state):
        """Load player state from dict."""
        self.x = state.get('x', 1.5)
        self.y = state.get('y', 1.5)
        self.angle = state.get('angle', 0)
        self.health = state.get('health', PLAYER_MAX_HEALTH)
        self.armor = state.get('armor', 0)
        self.sanity = state.get('sanity', SANITY_MAX)
        self.stamina = state.get('stamina', STAMINA_MAX)
        self.current_weapon = state.get('current_weapon', 0)
        self.ammo_shotgun = state.get('ammo_shotgun', 10)
        self.ammo_revolver = state.get('ammo_revolver', 12)
        self.shotgun_mag = state.get('shotgun_mag', SHOTGUN_MAG_SIZE)
        self.revolver_mag = state.get('revolver_mag', REVOLVER_MAG_SIZE)
        self.flashlight_battery = state.get('flashlight_battery', FLASHLIGHT_MAX_BATTERY)
        self.faith_energy = state.get('faith_energy', 50)
        self.salt_count = state.get('salt_count', 5)
        self.garlic_count = state.get('garlic_count', 3)
        self.bible_pages = state.get('bible_pages', 0)
        self.wards_unlocked = state.get('wards_unlocked', [True, False, False, False, False])
        self.journal_entries = state.get('journal_entries', [])
        self.relics = state.get('relics', [])
        self.current_chapter = state.get('current_chapter', 1)
        self.checkpoint_x = state.get('checkpoint_x', self.x)
        self.checkpoint_y = state.get('checkpoint_y', self.y)
        self.alive = True
