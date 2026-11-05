"""
Headless tests for the performance monitor (no pygame needed).

Run: python tests/test_perf_governor.py
"""
import os
import sys
import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.pop('ANINO_ADAPTIVE', None)

from perf_governor import PerfGovernor


def make():
    rm = types.SimpleNamespace(
        ENABLE_PARTICLES=True,
        ENABLE_PARTICLE_PHYSICS=True,
        ENABLE_ENV_ANIM=True,
        MAX_RENDER_TREES=150,
    )
    sm = types.SimpleNamespace(ENABLE_FOG=True)
    shader = types.SimpleNamespace(enabled=True)
    renderer = types.SimpleNamespace(
        shader_renderer=shader,
        perf_no_stars=False,
        perf_no_grade=False,
    )
    return PerfGovernor(renderer, rm, sm), renderer, rm, sm


def run(gov, ms, frames, playing=True):
    for _ in range(frames):
        gov.update(ms, playing)


def snapshot(renderer, rm, sm):
    return (
        renderer.shader_renderer.enabled,
        renderer.perf_no_stars,
        renderer.perf_no_grade,
        rm.ENABLE_PARTICLES,
        rm.ENABLE_PARTICLE_PHYSICS,
        rm.ENABLE_ENV_ANIM,
        rm.MAX_RENDER_TREES,
        sm.ENABLE_FOG,
    )


def test_slow_frames_never_reduce_visual_quality():
    gov, renderer, rm, sm = make()
    before = snapshot(renderer, rm, sm)
    run(gov, 30.0, 5000)
    assert gov.level == 0
    assert gov.over_budget is True
    assert gov.avg_ms == 30.0
    assert snapshot(renderer, rm, sm) == before


def test_fast_frames_are_measured_without_mutation():
    gov, renderer, rm, sm = make()
    before = snapshot(renderer, rm, sm)
    run(gov, 8.0, 2000)
    assert gov.level == 0
    assert gov.over_budget is False
    assert snapshot(renderer, rm, sm) == before


def test_hitches_and_non_gameplay_are_ignored():
    gov, renderer, rm, sm = make()
    before = snapshot(renderer, rm, sm)
    run(gov, 500.0, 2000)
    run(gov, 40.0, 2000, playing=False)
    assert gov.level == 0
    assert gov.over_budget is False
    assert snapshot(renderer, rm, sm) == before


def test_user_disabled_features_are_never_changed_or_enabled():
    rm = types.SimpleNamespace(
        ENABLE_PARTICLES=False,
        ENABLE_PARTICLE_PHYSICS=True,
        ENABLE_ENV_ANIM=True,
        MAX_RENDER_TREES=80,
    )
    sm = types.SimpleNamespace(ENABLE_FOG=False)
    renderer = types.SimpleNamespace(
        shader_renderer=types.SimpleNamespace(enabled=False),
        perf_no_stars=True,
        perf_no_grade=True,
    )
    gov = PerfGovernor(renderer, rm, sm)
    before = snapshot(renderer, rm, sm)
    run(gov, 30.0, 5000)
    run(gov, 6.0, 5000)
    assert snapshot(renderer, rm, sm) == before


def test_disabled_monitor_does_not_change_anything():
    gov, renderer, rm, sm = make()
    gov.enabled = False
    before = snapshot(renderer, rm, sm)
    run(gov, 40.0, 5000)
    assert gov.level == 0
    assert gov.avg_ms == 0.0
    assert snapshot(renderer, rm, sm) == before


def test_reset_clears_measurement_history():
    gov, *_ = make()
    run(gov, 30.0, 5000)
    assert gov.over_budget is True
    gov.reset()
    assert gov.avg_ms == 0.0
    assert gov.over_budget is False
    assert len(gov._samples) == 0


if __name__ == '__main__':
    test_slow_frames_never_reduce_visual_quality()
    test_fast_frames_are_measured_without_mutation()
    test_hitches_and_non_gameplay_are_ignored()
    test_user_disabled_features_are_never_changed_or_enabled()
    test_disabled_monitor_does_not_change_anything()
    test_reset_clears_measurement_history()
    print("All performance-monitor tests passed.")
