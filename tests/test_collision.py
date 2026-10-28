"""
Focused collision-resolution tests for ANINO SA GUBAT.
"""
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
import sys, math
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pygame
from settings import *
from map_system import GameMap, SpatialHash
from player import Player

class _FakeKeys:
    def __init__(self):
        self._keys = {}
    def __setitem__(self, k, v):
        self._keys[k] = v
    def __getitem__(self, k):
        return self._keys.get(k, False)
    def __contains__(self, k):
        return k in self._keys

def _fake_keys(forward=False, back=False, left=False, right=False, sprint=False, crouch=False):
    keys = _FakeKeys()
    if forward: keys[pygame.K_w] = True
    if back: keys[pygame.K_s] = True
    if left: keys[pygame.K_a] = True
    if right: keys[pygame.K_d] = True
    if sprint: keys[pygame.K_LSHIFT] = True
    if crouch: keys[pygame.K_LCTRL] = True
    return keys

def _make_player(x, y, angle=0.0):
    p = Player.__new__(Player)
    p.x = x; p.y = y; p.angle = angle; p.pitch = 0
    p.health = PLAYER_MAX_HEALTH; p.armor = 0; p.alive = True
    p.damage_flash = 0; p.sanity = SANITY_MAX; p.stamina = STAMINA_MAX
    p.noise_level = 0.0; p.stunned = False; p.stun_timer = 0.0
    p.current_weapon = 0; p.ammo_shotgun = 10; p.ammo_revolver = 12
    p.shotgun_mag = SHOTGUN_MAG_SIZE; p.revolver_mag = REVOLVER_MAG_SIZE
    p.weapon_cooldown = 0; p.reloading = False; p.reload_timer = 0
    p.flashlight_on = True; p.flashlight_battery = FLASHLIGHT_MAX_BATTERY
    p.faith_energy = 50.0; p.salt_count = 5; p.garlic_count = 3
    p.rosary_cooldown = 0; p.cross_cooldown = 0; p.bible_pages = 0
    p.wards_unlocked = [True, False, False, False, False]; p.selected_ward = 0
    p.ward_cooldowns = [0.0]*5; p.ward_menu_open = False
    p.is_sprinting = False; p.is_crouching = False
    p.bob_timer = 0; p.bob_amount = 0
    p.journal_entries = []; p.relics = []; p.current_chapter = 1
    p.checkpoint_x = x; p.checkpoint_y = y; p.checkpoint_angle = angle
    p.spring_bob = None; p.spring_sway = None
    return p

def test_spatial_hash_neighbor_query():
    print("--- Testing SpatialHash Neighbor Query ---")
    sh = SpatialHash(cell_size=2.0)
    tree = {"x": 1.0, "y": 1.0, "type": "balete", "radius": 0.3}
    sh.insert(tree, 1.0, 1.0, 0.3)
    results = sh.query(2.9, 1.0, radius=2.5)
    assert tree in results, "Query did not find tree in neighbor cell"
    results_far = sh.query(10.0, 10.0, radius=0.3)
    assert tree not in results_far
    print("[PASS] SpatialHash neighbor query finds cross-cell objects")

def test_spatial_hash_dedup():
    print("--- Testing SpatialHash Dedup ---")
    sh = SpatialHash(cell_size=2.0)
    tree = {"x": 2.0, "y": 2.0, "type": "balete", "radius": 0.5}
    sh.insert(tree, 2.0, 2.0, 0.5)
    results = sh.query(2.0, 2.0, radius=0.3)
    count = results.count(tree)
    assert count == 1, f"Tree returned {count} times, expected 1"
    print("[PASS] SpatialHash returns no duplicates")

def test_pushout_resolves_overlap():
    print("--- Testing Circle Pushout ---")
    gm = GameMap(1)
    assert len(gm.trees) > 0, "No trees generated"
    t = gm.trees[0]
    rx, ry = gm.resolve_circle_collision(t["x"], t["y"], PLAYER_SIZE)
    dist = math.hypot(rx - t["x"], ry - t["y"])
    expected = t["radius"] + PLAYER_SIZE + 0.02
    assert dist >= expected - 0.01, f"Player still inside tree: dist={dist:.3f} < {expected:.3f}"
    print(f"[PASS] Pushout resolved overlap (dist={dist:.3f} >= {expected:.3f})")

def test_slide_along_trunk():
    print("--- Testing Wall Sliding ---")
    gm = GameMap(1)
    t = gm.trees[0]
    offset = t["radius"] + PLAYER_SIZE + 0.15
    px = t["x"] + offset; py = t["y"]
    angle = math.atan2(t["y"] - py, t["x"] - px)
    p = _make_player(px, py, angle)
    keys = _fake_keys(forward=True)
    p.update(0.016, keys, 0.0, 0.0, gm)
    dist_after = math.hypot(p.x - t["x"], p.y - t["y"])
    assert dist_after >= t["radius"] + PLAYER_SIZE - 0.05, f"Player tunneled: dist={dist_after:.3f}"
    strafe_angle = angle + math.pi / 2
    p2 = _make_player(px, py, strafe_angle)
    keys2 = _fake_keys(forward=True)
    p2.update(0.016, keys2, 0.0, 0.0, gm)
    moved = math.hypot(p2.x - px, p2.y - py)
    assert moved > 0.01, f"Player did not slide (moved={moved:.4f})"
    print(f"[PASS] Player slides along trunk (moved {moved:.3f} units)")

def test_diagonal_no_extra_speed():
    print("--- Testing Diagonal Speed ---")
    gm = GameMap(1)
    px, py = 4.5, 4.5
    p1 = _make_player(px, py, 0.0)
    p1.update(0.5, _fake_keys(forward=True), 0.0, 0.0, gm)
    d_card = math.hypot(p1.x - px, p1.y - py)
    p2 = _make_player(px, py, 0.0)
    p2.update(0.5, _fake_keys(forward=True, right=True), 0.0, 0.0, gm)
    d_diag = math.hypot(p2.x - px, p2.y - py)
    ratio = d_diag / max(0.001, d_card)
    assert 0.9 < ratio < 1.1, f"Diagonal speed {ratio:.2f}x cardinal"
    print(f"[PASS] Diagonal speed normalized (ratio={ratio:.2f})")

def test_release_after_collision():
    print("--- Testing Release After Collision ---")
    gm = GameMap(1)
    t = gm.trees[0]
    offset = t["radius"] + PLAYER_SIZE + 0.1
    px = t["x"] + offset; py = t["y"]
    angle = math.atan2(t["y"] - py, t["x"] - px)
    p = _make_player(px, py, angle)
    for _ in range(10):
        p.update(0.016, _fake_keys(forward=True), 0.0, 0.0, gm)
    pos_after = (p.x, p.y)
    p.update(0.016, _fake_keys(), 0.0, 0.0, gm)
    p.angle = angle + math.pi
    for _ in range(10):
        p.update(0.016, _fake_keys(forward=True), 0.0, 0.0, gm)
    dist = math.hypot(p.x - pos_after[0], p.y - pos_after[1])
    assert dist > 0.05, f"Player stuck after release (moved {dist:.4f})"
    print(f"[PASS] Player can move away after collision (moved {dist:.3f})")

def test_no_permanent_stick():
    print("--- Testing Dense Grove No-Stick ---")
    gm = GameMap(1)
    import random as _r
    rng = _r.Random(123)
    p = _make_player(10.0, 10.0, 0.0)
    stuck = 0
    for step in range(300):
        p.angle = rng.uniform(0, math.pi * 2)
        keys = _fake_keys(forward=True, sprint=rng.random() > 0.5)
        old = (p.x, p.y)
        p.update(0.033, keys, 0.0, 0.0, gm)
        for t in gm.trees:
            d = math.hypot(p.x - t["x"], p.y - t["y"])
            assert d >= t["radius"] + PLAYER_SIZE - 0.1, f"Step {step}: embedded dist={d:.3f}"
        moved = math.hypot(p.x - old[0], p.y - old[1])
        stuck = stuck + 1 if moved < 0.001 else 0
        assert stuck < 20, f"Player stuck {stuck} steps"
    print("[PASS] Player navigated 300 steps without permanent stick")

def test_trees_block_movement():
    print("--- Testing Trees Still Block ---")
    gm = GameMap(1)
    t = gm.trees[0]
    offset = t["radius"] + PLAYER_SIZE + 0.05
    px = t["x"] - offset; py = t["y"]
    angle = math.atan2(t["y"] - py, t["x"] - px)
    p = _make_player(px, py, angle)
    for _ in range(30):
        p.update(0.016, _fake_keys(forward=True, sprint=True), 0.0, 0.0, gm)
    dist = math.hypot(p.x - t["x"], p.y - t["y"])
    assert dist >= t["radius"] + PLAYER_SIZE - 0.1, f"Player walked through: dist={dist:.3f}"
    assert p.x < t["x"] + 0.5, f"Player passed tree center"
    print(f"[PASS] Tree blocks player at dist {dist:.3f}")

def test_two_close_trees():
    print("--- Testing Two Close Trees ---")
    gm = GameMap(1)
    gm.trees = []; gm.spatial_hash.clear()
    gm.trees.append({"x":10.0,"y":10.0,"type":"balete","scale":1.0,"tint":255,"radius":0.35,"canopy_seed":1,"lean":0})
    gm.trees.append({"x":12.0,"y":10.0,"type":"balete","scale":1.0,"tint":255,"radius":0.35,"canopy_seed":2,"lean":0})
    for t in gm.trees:
        gm.spatial_hash.insert(t, t["x"], t["y"], t["radius"])
    p = _make_player(11.0, 9.0, math.pi / 2)
    for _ in range(20):
        p.update(0.016, _fake_keys(forward=True), 0.0, 0.0, gm)
    assert p.y > 9.1, f"Player trapped between trees (y={p.y:.3f})"
    print(f"[PASS] Player passed between two trees (y={p.y:.3f})")

def run_all():
    print("=== STARTING COLLISION TEST SUITE ===")
    tests = [test_spatial_hash_neighbor_query, test_spatial_hash_dedup, test_pushout_resolves_overlap, test_slide_along_trunk, test_diagonal_no_extra_speed, test_release_after_collision, test_no_permanent_stick, test_trees_block_movement, test_two_close_trees]
    passed = 0; failed = 0
    for test in tests:
        try:
            test(); passed += 1
        except AssertionError as e:
            print(f"[FAIL] {test.__name__}: {e}"); failed += 1
        except Exception as e:
            import traceback; print(f"[ERROR] {test.__name__}: {e}"); traceback.print_exc(); failed += 1
    print(f"=== COLLISION TEST SUITE: {passed} PASSED, {failed} FAILED ===")
    return failed == 0

if __name__ == "__main__":
    sys.exit(0 if run_all() else 1)
