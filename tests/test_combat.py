"""Focused regression tests for combat, weapon state, and enemy interactions."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import unittest
from unittest.mock import patch

from settings import (
    BOLO_COOLDOWN, EMPTY, REVOLVER_COOLDOWN, REVOLVER_RELOAD_TIME,
    SHOTGUN_COOLDOWN, SHOTGUN_RELOAD_TIME,
)
from player import Player
from enemies import Enemy, EnemyManager, EnemyState
from renderer import Renderer


class FakeMap:
    def __init__(self, wall=None):
        self.wall = wall

    def is_solid(self, x, y):
        return bool(self.wall and self.wall(x, y))

    def get_tile(self, x, y):
        return EMPTY

    def is_water(self, x, y):
        return False

    def is_circle_solid(self, x, y, radius, doors_block=True):
        return False

    def resolve_circle_collision(self, x, y, radius):
        return x, y

    def clamp_position(self, x, y, radius):
        return x, y


class NoKeys:
    def __getitem__(self, key):
        return False


class CombatRegressionTests(unittest.TestCase):
    def test_revolver_hitbox_scales_with_apparent_target_size(self):
        manager = EnemyManager()
        distant = Enemy("aswang", 15.0, 0.0)
        manager.enemies = [distant]
        shot = {"type": "revolver", "damage": 30, "range": 15, "spread": 0}

        self.assertEqual(manager.apply_weapon_hit(0, 0, 0.05, shot), [])
        self.assertEqual(distant.health, distant.max_health)
        self.assertEqual(manager.apply_weapon_hit(0, 0, 0.0, shot), [distant])
        self.assertLess(distant.health, distant.max_health)

        close_manager = EnemyManager()
        close_target = Enemy("aswang", 1.0, 0.2)
        close_manager.enemies = [close_target]
        self.assertEqual(
            close_manager.apply_weapon_hit(0, 0, 0.0, shot), [close_target]
        )

    def test_revolver_hits_only_nearest_aligned_target(self):
        manager = EnemyManager()
        near = Enemy("aswang", 4.0, 0.0)
        far = Enemy("kapre", 8.0, 0.0)
        manager.enemies = [far, near]

        hits = manager.apply_weapon_hit(
            0, 0, 0,
            {"type": "revolver", "damage": 30, "range": 15, "spread": 0},
        )

        self.assertEqual(hits, [near])
        self.assertLess(near.health, near.max_health)
        self.assertEqual(far.health, far.max_health)

    def test_shotgun_pellets_are_not_recounted_for_targets_behind_first_hit(self):
        manager = EnemyManager()
        near = Enemy("aswang", 4.0, 0.0)
        far = Enemy("kapre", 6.0, 0.0)
        manager.enemies = [near, far]
        shot = {
            "type": "shotgun", "damage": 40, "range": 8,
            "spread": 0.1, "pellets": 5,
        }

        with patch("enemies.random.uniform", return_value=0.0):
            hits = manager.apply_weapon_hit(0, 0, 0, shot)

        self.assertEqual(hits, [near])
        self.assertLess(near.health, near.max_health)
        self.assertEqual(far.health, far.max_health)

    def test_all_weapons_are_blocked_by_solid_cover(self):
        wall_map = FakeMap(
            wall=lambda x, y: 0.5 <= x <= 0.7 and abs(y) < 0.5
        )
        cases = (
            (Enemy("aswang", 1.2, 0.0),
             {"type": "bolo", "damage": 25, "range": 1.5, "spread": 0}),
            (Enemy("aswang", 4.0, 0.0),
             {"type": "shotgun", "damage": 40, "range": 8,
              "spread": 0.1, "pellets": 5}),
            (Enemy("aswang", 4.0, 0.0),
             {"type": "revolver", "damage": 30, "range": 15, "spread": 0}),
        )

        for enemy, shot in cases:
            with self.subTest(weapon=shot["type"]):
                manager = EnemyManager()
                manager.enemies = [enemy]
                with patch("enemies.random.uniform", return_value=0.0):
                    hits = manager.apply_weapon_hit(0, 0, 0, shot, wall_map)
                self.assertEqual(hits, [])
                self.assertEqual(enemy.health, enemy.max_health)

    def test_enemy_melee_attack_requires_line_of_sight(self):
        enemy = Enemy("aswang", 1.5, 0.0)
        enemy.state = EnemyState.ATTACK
        manager = EnemyManager()
        manager.enemies = [enemy]
        wall_map = FakeMap(
            wall=lambda x, y: 0.5 <= x <= 0.7 and abs(y) < 0.5
        )

        self.assertEqual(manager.check_attacks(0, 0, wall_map), 0)
        self.assertEqual(manager.check_attacks(0, 0), enemy.damage)

    def test_garlic_zone_damages_each_enemy_once(self):
        manager = EnemyManager()
        enemy = Enemy("aswang", 5.0, 5.0)
        manager.enemies = [enemy]
        manager.add_garlic_zone(5.0, 5.0)

        for _ in range(20):
            manager.update(0.01, 5.0, 5.0, FakeMap())

        self.assertEqual(enemy.health, enemy.max_health - 10)

    def test_spawning_a_chapter_clears_old_combat_zones(self):
        manager = EnemyManager()
        manager.add_salt_zone(2.0, 2.0)
        manager.add_garlic_zone(3.0, 3.0)
        manager.last_attackers = [Enemy("aswang", 4.0, 4.0)]

        manager.spawn_enemies([{"type": "multo", "x": 6.0, "y": 6.0}])

        self.assertEqual(manager.active_effects, [])
        self.assertEqual(manager.last_attackers, [])
        self.assertEqual(len(manager.enemies), 1)

    def test_switching_weapon_cancels_reload_without_transferring_ammo(self):
        player = Player()
        player.current_weapon = 1
        player.shotgun_mag = 0
        player.ammo_shotgun = 4
        self.assertTrue(player.start_reload())

        self.assertTrue(player.switch_weapon(2))
        self.assertFalse(player.reloading)
        self.assertEqual(player.reload_timer, 0)
        self.assertEqual(player.weapon_cooldown, 0.3)

        player.update(
            SHOTGUN_RELOAD_TIME + 0.1, NoKeys(), 0, 0, FakeMap()
        )
        self.assertEqual(player.shotgun_mag, 0)
        self.assertEqual(player.ammo_shotgun, 4)

    def test_fire_input_cancels_reload_even_during_weapon_cooldown(self):
        player = Player()
        player.current_weapon = 1
        player.shotgun_mag = 0
        player.ammo_shotgun = 4
        self.assertTrue(player.start_reload())
        player.weapon_cooldown = 0.2

        self.assertIsNone(player.fire_weapon())
        self.assertFalse(player.reloading)
        self.assertEqual(player.ammo_shotgun, 4)

    def test_shotgun_reload_completion_transfers_only_available_reserve(self):
        player = Player()
        player.current_weapon = 1
        player.shotgun_mag = 0
        player.ammo_shotgun = 1
        self.assertTrue(player.start_reload())

        player.update(
            SHOTGUN_RELOAD_TIME + 0.1, NoKeys(), 0, 0, FakeMap()
        )

        self.assertEqual(player.shotgun_mag, 1)
        self.assertEqual(player.ammo_shotgun, 0)
        self.assertFalse(player.reloading)

    def test_revolver_reload_completion_transfers_reserve(self):
        player = Player()
        player.current_weapon = 2
        player.revolver_mag = 2
        player.ammo_revolver = 5
        self.assertTrue(player.start_reload())

        player.update(
            REVOLVER_RELOAD_TIME + 0.1, NoKeys(), 0, 0, FakeMap()
        )

        self.assertEqual(player.revolver_mag, 6)
        self.assertEqual(player.ammo_revolver, 1)
        self.assertFalse(player.reloading)

    def test_reload_does_not_start_with_full_magazine_or_empty_reserve(self):
        player = Player()
        player.current_weapon = 1
        self.assertFalse(player.start_reload())
        player.shotgun_mag = 0
        player.ammo_shotgun = 0
        self.assertFalse(player.start_reload())
        self.assertFalse(player.reloading)

    def test_shotgun_firing_consumes_one_shell_and_obeys_cooldown(self):
        player = Player()
        player.current_weapon = 1
        player.shotgun_mag = 2

        shot = player.fire_weapon()
        self.assertEqual(shot["type"], "shotgun")
        self.assertEqual(player.shotgun_mag, 1)
        self.assertEqual(player.weapon_cooldown, SHOTGUN_COOLDOWN)
        self.assertIsNone(player.fire_weapon())
        self.assertEqual(player.shotgun_mag, 1)

    def test_revolver_firing_consumes_one_round_and_obeys_cooldown(self):
        player = Player()
        player.current_weapon = 2
        player.revolver_mag = 6

        shot = player.fire_weapon()
        self.assertEqual(shot["type"], "revolver")
        self.assertEqual(player.revolver_mag, 5)
        self.assertEqual(player.weapon_cooldown, REVOLVER_COOLDOWN)
        self.assertIsNone(player.fire_weapon())
        self.assertEqual(player.revolver_mag, 5)

    def test_shotgun_muzzle_flash_does_not_start_revolver_kick(self):
        renderer = Renderer.__new__(Renderer)
        renderer.muzzle_flash = 0.0
        renderer.weapon_recoil = 0.0
        renderer.revolver_fire_timer = 0.0

        renderer.trigger_muzzle_flash()
        self.assertEqual(renderer.revolver_fire_timer, 0.0)
        renderer.trigger_revolver_fire()
        self.assertEqual(renderer.revolver_fire_timer, 0.16)

    def test_bolo_melee_hits_in_range_but_not_out_of_range(self):
        shot = {"type": "bolo", "damage": 25, "range": 1.5, "spread": 0}
        near = Enemy("aswang", 1.0, 0.0)
        manager = EnemyManager()
        manager.enemies = [near]
        self.assertEqual(manager.apply_weapon_hit(0, 0, 0, shot), [near])
        self.assertEqual(near.health, near.max_health - 25)

        far = Enemy("aswang", 1.6, 0.0)
        manager.enemies = [far]
        self.assertEqual(manager.apply_weapon_hit(0, 0, 0, shot), [])
        self.assertEqual(far.health, far.max_health)

    def test_range_limits_are_enforced_for_shotgun_and_revolver(self):
        cases = (
            (Enemy("aswang", 8.1, 0.0),
             {"type": "shotgun", "damage": 40, "range": 8,
              "spread": 0.1, "pellets": 5}),
            (Enemy("aswang", 15.1, 0.0),
             {"type": "revolver", "damage": 30, "range": 15, "spread": 0}),
        )
        for enemy, shot in cases:
            with self.subTest(weapon=shot["type"]):
                manager = EnemyManager()
                manager.enemies = [enemy]
                with patch("enemies.random.uniform", return_value=0.0):
                    self.assertEqual(manager.apply_weapon_hit(0, 0, 0, shot), [])
                self.assertEqual(enemy.health, enemy.max_health)

    def test_bolo_fire_uses_cooldown_without_ammunition(self):
        player = Player()
        player.current_weapon = 0
        shot = player.fire_weapon()
        self.assertEqual(shot["type"], "bolo")
        self.assertEqual(player.weapon_cooldown, BOLO_COOLDOWN)
        self.assertIsNone(player.fire_weapon())

    def test_empty_fire_starts_reload_when_reserve_is_available(self):
        player = Player()
        player.current_weapon = 1
        player.shotgun_mag = 0
        player.ammo_shotgun = 2

        self.assertIsNone(player.fire_weapon())
        self.assertTrue(player.reloading)
        self.assertEqual(player.reload_weapon, 1)
        self.assertEqual(player.ammo_shotgun, 2)

    def test_enemy_health_stops_at_zero_and_death_is_one_way(self):
        enemy = Enemy("aswang", 3.0, 3.0)
        enemy.take_damage(9999, "physical")
        self.assertFalse(enemy.alive)
        self.assertEqual(enemy.health, 0)
        enemy.take_damage(10, "physical")
        self.assertEqual(enemy.health, 0)


if __name__ == "__main__":
    unittest.main()
