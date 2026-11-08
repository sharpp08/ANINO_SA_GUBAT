"""
VFX integration tests for the supernatural ward suite:
  * salt/garlic zone rendering (zone_fx pass + 'ring' emissive entries),
  * garlic toss flight -> landing -> zone formation,
  * cross manifestation ward effect ('cross' branch of _draw_ward_effect).

Run directly:  python tests/test_vfx_zones.py
Headless-safe: uses a dummy SDL driver when no display is available.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_results = []


def check(name, fn):
    try:
        fn()
        _results.append((name, True, ''))
        print(f"[PASS] {name}")
    except Exception as exc:
        import traceback
        _results.append((name, False, str(exc)))
        print(f"[FAIL] {name}: {exc}")
        traceback.print_exc()


def make_game():
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    import main
    game = main.Game()
    game.start_new_game()
    game.state = main.STATE_PLAYING
    return game


def test_zone_pass_generates_ring_emissive():
    game = make_game()
    game.player.salt_count = 5
    game._use_salt()
    assert len(game.enemy_manager.active_effects) == 1
    zone = game.enemy_manager.active_effects[0]
    assert zone['type'] == 'salt' and zone['radius'] == 2.0
    # Force the player to face the zone so the projection keeps it on-screen.
    import math
    game.player.angle = math.atan2(zone['y'] - game.player.y, zone['x'] - game.player.y)
    game.render(1.0 / 60.0)
    rings = [e for e in game.renderer._emissive if e[0] == 'ring']
    assert rings, "zone pass should register a 'ring' emissive entry"
    kind, x, y, radius, color, alpha = rings[0]
    assert 0 <= alpha <= 255
    # A zone right under the camera projects off the bottom of the screen and its
    # ring gets view-culled before the cache fills.  Drop a second zone a couple
    # of tiles ahead so the ring actually renders and the sprite cache populates.
    game.enemy_manager.active_effects.append(
        {'type': 'salt', 'x': game.player.x + 2.0, 'y': game.player.y,
         'radius': 2.0, 'timer': 8.0, 'max_timer': 8.0})
    game.player.angle = math.atan2(0.0, 2.0)
    game.render(1.0 / 60.0)
    # Ring sprite cache must be populated and bounded.
    assert len(game.renderer._zone_ring_cache) >= 1


def test_garlic_toss_lands_and_forms_zone():
    game = make_game()
    game.player.garlic_count = 5
    before = len(game.enemy_manager.active_effects)
    game._use_garlic()
    assert game.garlic_toss is not None, "toss object should exist mid-flight"
    assert len(game.enemy_manager.active_effects) == before, "zone must not exist before landing"
    dt = 1.0 / 60.0
    landed = False
    for _ in range(120):
        game.update_playing(dt, 0.0, 0.0)
        if game.garlic_toss is None:
            landed = True
            break
    assert landed, "garlic toss should land within 120 frames"
    assert len(game.enemy_manager.active_effects) == before + 1
    zone = game.enemy_manager.active_effects[-1]
    assert zone['type'] == 'garlic'
    # Landing point is ahead of the player's position at the throw.
    import math
    dist = math.hypot(zone['x'] - game.player.x, zone['y'] - game.player.y)
    assert dist < 8.0


def test_cross_manifestation_ward_effect():
    game = make_game()
    game.player.cross_cooldown = 0.0
    game._use_cross()
    rend = game.renderer
    assert rend.ward_effect_type == 'cross'
    assert rend.ward_effect_timer > 0
    # Step the ward animation across its full lifetime; the 'cross' branch
    # must not raise on any frame.
    for _ in range(100):
        rend._draw_ward_effect(1.0 / 60.0)
        if rend.ward_effect_timer <= 0:
            break
    assert rend.ward_effect_timer <= 0


def test_zone_garlic_visuals_smoke():
    """Full-frame render while two zones live: no exceptions, no leaks."""
    game = make_game()
    game.player.salt_count = 9
    game.player.garlic_count = 9
    game._use_salt()
    game._use_garlic()
    for _ in range(90):
        game.update_playing(1.0 / 60.0, 0.0, 0.0)
        game.render(1.0 / 60.0)
    assert len(game.renderer._zone_ring_cache) <= 64, "ring cache must be bounded"


def main():
    check("Zone pass generates ring emissive entries", test_zone_pass_generates_ring_emissive)
    check("Garlic toss lands and forms its zone", test_garlic_toss_lands_and_forms_zone)
    check("Cross manifestation ward effect", test_cross_manifestation_ward_effect)
    check("Salt + garlic zones smoke render", test_zone_garlic_visuals_smoke)
    failed = [r for r in _results if not r[1]]
    print(f"=== VFX ZONE TESTS: {len(_results) - len(failed)} PASSED, {len(failed)} FAILED ===")
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
