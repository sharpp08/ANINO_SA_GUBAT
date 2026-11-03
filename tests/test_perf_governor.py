"""
Headless tests for the adaptive performance governor (no pygame needed).

Run: python tests/test_perf_governor.py
"""
import os
import sys
import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.pop('ANINO_ADAPTIVE', None)

from perf_governor import PerfGovernor, MAX_LEVEL


def make():
    rm = types.SimpleNamespace(ENABLE_PARTICLES=True, ENABLE_PARTICLE_PHYSICS=True,
                               ENABLE_ENV_ANIM=True, MAX_RENDER_TREES=150)
    sm = types.SimpleNamespace(ENABLE_FOG=True)
    renderer = types.SimpleNamespace(shader_renderer=types.SimpleNamespace(enabled=True),
                                     perf_no_stars=False)
    return PerfGovernor(renderer, rm, sm), renderer, rm, sm


def run(gov, ms, frames, playing=True):
    for _ in range(frames):
        gov.update(ms, playing)


def test_stays_at_full_quality_when_fast():
    gov, renderer, rm, sm = make()
    run(gov, 8.0, 2000)
    assert gov.level == 0 and renderer.shader_renderer.enabled and rm.MAX_RENDER_TREES == 150


def test_sheds_levels_when_slow_and_reaches_max():
    gov, renderer, rm, sm = make()
    run(gov, 30.0, 400)
    assert gov.level >= 1 and renderer.shader_renderer.enabled is False
    run(gov, 30.0, 3000)
    assert gov.level == MAX_LEVEL
    assert rm.ENABLE_PARTICLES is False and rm.ENABLE_PARTICLE_PHYSICS is False
    assert renderer.perf_no_stars is True and rm.ENABLE_ENV_ANIM is False
    assert sm.ENABLE_FOG is False and rm.MAX_RENDER_TREES == int(150 * 0.35)


def test_restores_exactly_when_headroom_returns():
    gov, renderer, rm, sm = make()
    run(gov, 30.0, 3000)
    assert gov.level == MAX_LEVEL
    run(gov, 6.0, 20000)
    assert gov.level == 0
    assert renderer.shader_renderer.enabled is True and rm.ENABLE_PARTICLES is True
    assert rm.ENABLE_ENV_ANIM is True and rm.MAX_RENDER_TREES == 150 and sm.ENABLE_FOG is True
    assert renderer.perf_no_stars is False


def test_ignores_hitches_and_non_gameplay():
    gov, *_ = make()
    run(gov, 500.0, 2000)            # loading-style hitches are ignored
    run(gov, 40.0, 2000, playing=False)   # menus/pause never count
    assert gov.level == 0


def test_respects_user_settings_that_were_off():
    rm = types.SimpleNamespace(ENABLE_PARTICLES=False, ENABLE_PARTICLE_PHYSICS=True,
                               ENABLE_ENV_ANIM=True, MAX_RENDER_TREES=80)
    sm = types.SimpleNamespace(ENABLE_FOG=False)
    renderer = types.SimpleNamespace(shader_renderer=types.SimpleNamespace(enabled=False),
                                     perf_no_stars=False)
    gov = PerfGovernor(renderer, rm, sm)
    run(gov, 30.0, 3000)
    run(gov, 6.0, 20000)
    assert gov.level == 0
    assert rm.ENABLE_PARTICLES is False and sm.ENABLE_FOG is False   # never force on
    assert renderer.shader_renderer.enabled is False and rm.MAX_RENDER_TREES == 80


def test_no_flapping_after_failed_restore():
    gov, *_ = make()
    run(gov, 30.0, 3000)
    top = gov.level
    run(gov, 6.0, 700)               # headroom long enough to restore one level
    assert gov.level == top - 1
    run(gov, 30.0, 400)              # ...but that level can't hold 60 fps: shed again
    assert gov.level == top and gov.floor == top
    run(gov, 6.0, 5000)              # and it must not retry restoring below the floor
    assert gov.level == top


def test_skips_gpu_post_level_when_gpu_presenter_active():
    rm = types.SimpleNamespace(ENABLE_PARTICLES=True, ENABLE_PARTICLE_PHYSICS=True,
                               ENABLE_ENV_ANIM=True, MAX_RENDER_TREES=150)
    sm = types.SimpleNamespace(ENABLE_FOG=True)
    renderer = types.SimpleNamespace(shader_renderer=types.SimpleNamespace(enabled=False),
                                     perf_no_stars=False)   # old readback shader inert (SKIP)
    gov = PerfGovernor(renderer, rm, sm)
    run(gov, 30.0, 400)
    assert gov.level == 2 and rm.ENABLE_PARTICLES is False   # went straight to level 2
    run(gov, 6.0, 20000)
    assert gov.level == 0 and rm.ENABLE_PARTICLES is True


def test_can_be_disabled():
    gov, *_ = make()
    gov.enabled = False
    run(gov, 40.0, 3000)
    assert gov.level == 0


if __name__ == '__main__':
    test_stays_at_full_quality_when_fast()
    test_sheds_levels_when_slow_and_reaches_max()
    test_restores_exactly_when_headroom_returns()
    test_ignores_hitches_and_non_gameplay()
    test_respects_user_settings_that_were_off()
    test_no_flapping_after_failed_restore()
    test_skips_gpu_post_level_when_gpu_presenter_active()
    test_can_be_disabled()
    print("All perf governor tests passed.")
