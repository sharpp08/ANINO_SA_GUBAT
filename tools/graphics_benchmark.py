"""
Graphics benchmark for ANINO SA GUBAT.

Two entry points:

* ``quick_benchmark_report(game)`` - called from the settings menu ("Run
  Graphics Benchmark").  Measures the *live* renderer's CPU frame work time
  on the player's current scene (flashlight toggling + dawn sweep) and returns
  a recommendation.  Blocks for a few seconds; never crashes the game.

* ``benchmark_all()`` / CLI - headless, deterministic tier comparison.  For
  each quality tier it builds a real GameMap + Renderer, places a synthetic
  player in the densest part of the forest with several enemies, toggles the
  flashlight, enables rain and sweeps the dawn, then reports:
    average / minimum / p95 CPU frame work time, estimated FPS, and which
    tier stays inside the 60 FPS budget.

GPU timings are NOT measured (the renderer has no GPU query path on the
pyglet/SDL2 pipeline; only CPU work time is).  This is stated in the report.
"""
import os
import sys
from time import perf_counter

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)
os.chdir(_BASE)

# 60 FPS budget in ms of CPU work per frame (the PerfGovernor uses 14.5 ms;
# the same number keeps the benchmark consistent with the adaptive governor).
FPS_BUDGET_MS = 14.5
# Tier recommendation thresholds on the p95 frame work time.
THRESH_ULTRA_MS = 10.0
THRESH_HIGH_MS = 13.0
THRESH_MEDIUM_MS = 15.0

ENEMY_TYPES = ('aswang', 'manananggal', 'tikbalang', 'kapre', 'white_lady', 'multo')


def recommend_tier(p95_ms):
    """Pure mapping from a p95 frame work time to the highest tier that holds 60 FPS."""
    if p95_ms <= THRESH_ULTRA_MS:
        return 'ultra'
    if p95_ms <= THRESH_HIGH_MS:
        return 'high'
    if p95_ms <= THRESH_MEDIUM_MS:
        return 'medium'
    return 'low'


def _stats(times_ms):
    times_ms = sorted(times_ms)
    n = len(times_ms)
    if n == 0:
        return {}
    p95 = times_ms[min(n - 1, int(n * 0.95))]
    return {
        'frames': n,
        'avg_ms': sum(times_ms) / n,
        'min_ms': times_ms[0],
        'p95_ms': p95,
        'max_ms': times_ms[-1],
        'est_fps_at_60_budget': '60+' if p95 <= FPS_BUDGET_MS else f'~{int(1000.0 / max(1.0, p95))}',
    }


def _dummy_enemy(etype, x, y):
    """Lightweight stand-in that satisfies Renderer._draw_enemy's attribute
    surface, so the benchmark stresses the enemy sprite path without the full
    AI / audio stack (headless mode has no mixer running)."""
    class _Enemy:
        def __init__(self, t, px, py):
            self.type = t
            self.x, self.y = px, py
            self.angle = 0.0
            self.alive = True
            self.dying = False
            self.animation_state = 'idle'
            self.anim_frame = 0
            self.death_t = 0.0
            self.hit_flash = 0.0
            self.hit_seq = 0
            self._fx_seq = 0
            self.bound = False
            self.last_damage_type = 'physical'
            self.last_hit_x = None
            self.last_hit_y = None
            self.spawn_x, self.spawn_y = px, py

        def distance_to(self, x, y):
            import math
            return math.hypot(self.x - x, self.y - y)

    return _Enemy(etype, x, y)


def benchmark_tier(tier, frames=360):
    """Headless benchmark of one quality tier.  Returns a stats dict."""
    import pygame
    import settings
    settings.apply_quality_preset(tier)
    # Modules such as renderer do ``from settings import *`` at import time, so
    # every tier must get a fresh module graph (NUM_RAYS & friends are copied
    # at import).  Drop the cached modules, keep pygame + numpy, then re-apply
    # the preset on the fresh settings module.
    for mod_name in list(sys.modules):
        if mod_name not in ('pygame', 'numpy', 'sys', 'builtins', '__main__') \
                and not mod_name.startswith(('pygame.', 'numpy.')):
            del sys.modules[mod_name]
    import settings as s
    s.apply_quality_preset(tier)

    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    pygame.init()
    try:
        pygame.display.set_mode((s.SCREEN_WIDTH, s.SCREEN_HEIGHT))
    except Exception:
        pass

    from asset_generator import (
        generate_all_textures, generate_all_weapons,
        generate_all_enemies, generate_all_pickups, generate_crosshair,
    )
    from map_system import GameMap
    from renderer import Renderer
    from player import Player

    internal = pygame.Surface((s.INTERNAL_WIDTH, s.INTERNAL_HEIGHT))
    textures = generate_all_textures()
    enemy_spr = generate_all_enemies()
    pickup_spr = {k: v.convert_alpha() for k, v in generate_all_pickups().items()}
    renderer = Renderer(internal, textures, generate_all_weapons(), enemy_spr, pickup_spr)
    renderer.crosshair = generate_crosshair(16)

    game_map = GameMap()
    player = Player()
    spot = _densest_tree(game_map)
    if spot is not None:
        player.x, player.y = float(spot['x']), float(spot['y'])
        player.angle = 0.0
    player.flashlight_on = True
    player.flashlight_battery = 100

    enemies = [_dummy_enemy(ET, player.x + dx, player.y + dy)
               for ET, (dx, dy) in zip(ENEMY_TYPES,
                                        [(6, 0), (-5, 3), (2, -7), (-8, -4), (9, -2), (-3, 8)])]

    # Force the heaviest weather the tier allows on (rain without lightning).
    renderer.weather.rain_on = True
    renderer.weather.lightning_on = False
    renderer.weather.strength = 1.0

    warm = min(30, frames // 4)
    times = []
    for i in range(frames + warm):
        # Scene mix: flashlight on for the first half, off for the second;
        # dawn sweeps 0 -> 1 across the whole run.
        if i >= warm:
            player.flashlight_on = i < (warm + frames) // 2
        sunrise = (i / float(frames + warm))
        t0 = perf_counter()
        renderer.render_frame(player, game_map, enemies, [], 1 / 60.0, sunrise)
        dt_ms = (perf_counter() - t0) * 1000.0
        if i >= warm:
            times.append(dt_ms)

    stats = _stats(times)
    stats['tier'] = tier
    stats['internal_resolution'] = f"{s.INTERNAL_WIDTH}x{s.INTERNAL_HEIGHT}"
    stats['recommendation'] = recommend_tier(stats.get('p95_ms', FPS_BUDGET_MS + 1))
    return stats


def benchmark_all(tiers=('low', 'medium', 'high', 'ultra'), frames=360):
    results = {}
    for tier in tiers:
        try:
            results[tier] = benchmark_tier(tier, frames=frames)
        except Exception as exc:
            results[tier] = {'tier': tier, 'error': str(exc)}
    return results


def _densest_tree(game_map):
    """The tree with the most neighbours within 6 tiles (representative dense forest)."""
    trees = getattr(game_map, 'trees', [])
    if not trees:
        return None
    best, best_n = None, -1
    for i, t in enumerate(trees[::7]):            # stride keeps the scan cheap
        n = 0
        for j in range(i * 7, min(i * 7 + 7, len(trees))):
            u = trees[j]
            dx, dy = u['x'] - t['x'], u['y'] - t['y']
            if dx * dx + dy * dy < 36.0:
                n += 1
        if n > best_n:
            best, best_n = t, n
    return best


def _print_report(results):
    order = ['low', 'medium', 'high', 'ultra']
    print("\n" + "=" * 78)
    print("ANINO SA GUBAT - GRAPHICS BENCHMARK (CPU frame work time)")
    print("=" * 78)
    print(f"{'tier':<8} {'resolution':<14} {'avg ms':>7} {'min ms':>7} {'p95 ms':>7} {'FPS est':>9}")
    print('-' * 78)
    best = None
    for tier in order:
        st = results.get(tier)
        if not st or 'error' in st:
            err = st.get('error') if st else 'missing'
            print(f"{tier:<8} {'-':<14} {'ERROR':>7}  {err}")
            continue
        print(f"{tier:<8} {st['internal_resolution']:<14} {st['avg_ms']:>7.2f} "
              f"{st['min_ms']:>7.2f} {st['p95_ms']:>7.2f} {str(st['est_fps_at_60_budget']):>9}")
        if st.get('p95_ms', 99.0) <= FPS_BUDGET_MS:
            best = tier
    print('-' * 78)
    if best:
        rank = order.index(best)
        print(f"Recommended preset: {best.upper()}  (highest tier within the "
              f"{FPS_BUDGET_MS} ms/frame 60 FPS budget)")
        for higher in reversed(order[rank + 1:]):
            st = results.get(higher)
            if st and 'error' not in st:
                print(f"  - {higher.upper()} rejected: p95 {st['p95_ms']:.2f} ms > budget")
    else:
        print("No preset holds 60 FPS; use LOW and enable adaptive performance.")
    print("\nNote: only CPU work time is measured - the engine has no GPU query")
    print("path, so no GPU utilisation numbers are reported (by design).")
    print("=" * 78)


def quick_benchmark_report(game, frames=240):
    """Settings-menu benchmark: measure the live renderer on the live scene."""
    p = game.player
    r = game.renderer
    enemies = getattr(game, 'enemy_manager', None)
    enemy_list = []
    if enemies is not None:
        try:
            enemy_list = enemies.get_alive_enemies() or []
        except Exception:
            enemy_list = []
    was_on = bool(p.flashlight_on)
    times = []
    for i in range(frames):
        # Alternate the flashlight every 60 frames so both lighting paths are
        # sampled; sweep the dawn so fog/sky work is exercised too.
        p.flashlight_on = (i // 60) % 2 == 0
        t0 = perf_counter()
        r.render_frame(p, game.game_map, enemy_list, getattr(game, 'effects', []),
                       1 / 60.0, (i / float(frames)))
        times.append((perf_counter() - t0) * 1000.0)
    p.flashlight_on = was_on
    st = _stats(times)
    p95 = st.get('p95_ms', FPS_BUDGET_MS + 1)
    rec = recommend_tier(p95)
    st['verdict'] = (f"{rec.upper()} recommended - p95 {p95:.1f} ms/frame "
                     f"(avg {st.get('avg_ms', 0.0):.1f} ms; budget {FPS_BUDGET_MS} ms)")
    return st


if __name__ == '__main__':
    args = sys.argv[1:]
    tier_arg = None
    frames_arg = 360
    i = 0
    while i < len(args):
        if args[i] == '--frames' and i + 1 < len(args):
            i += 1
            frames_arg = int(args[i])
        else:
            tier_arg = args[i]
        i += 1
    if tier_arg:
        known = [t for t in ('low', 'medium', 'high', 'ultra') if t in tier_arg.split(',')]
        res = benchmark_all(known, frames=frames_arg)
    else:
        res = benchmark_all(frames=frames_arg)
    _print_report(res)