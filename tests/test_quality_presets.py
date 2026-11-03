"""Tests for the graphics quality presets (including the Ultra tier).

Run with:  python tests\\test_quality_presets.py
No display or audio device is required.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_ultra_preset_definition():
    import settings as s
    assert 'ultra' in s.QUALITY_PRESETS, "ultra tier missing from QUALITY_PRESETS"
    u = s.QUALITY_PRESETS['ultra']
    h = s.QUALITY_PRESETS['high']
    m = s.QUALITY_PRESETS['medium']
    # Resolution target
    assert (u['internal_width'], u['internal_height']) == (1280, 720)
    assert h['internal_width'] == m['internal_width']  # high keeps the medium canvas
    # Higher fidelity than high
    assert u['max_render_trees'] > h['max_render_trees']
    assert u['vegetation_scale'] > h['vegetation_scale']
    assert u['tree_lod_far_dist'] >= h['tree_lod_far_dist']
    assert u['rain_density'] > h['rain_density']
    assert u['terrain_tex_size'] >= 1024
    assert u['enable_contact_shadows'] is True
    assert u['enable_bloom'] is True
    assert u['god_ray_samples'] >= h['god_ray_samples']
    # Medium stays untouched (no silent upgrade)
    assert m['internal_width'] == 640 and m['internal_height'] == 360
    assert m['enable_contact_shadows'] is False


def test_apply_ultra_sets_globals():
    import settings as s
    s.apply_quality_preset('ultra')
    assert s.QUALITY_TIER == 'ultra'
    assert s.INTERNAL_WIDTH == 1280 and s.INTERNAL_HEIGHT == 720
    assert s.NUM_RAYS == 1280
    assert s.MAX_RENDER_TREES == s.QUALITY_PRESETS['ultra']['max_render_trees']
    assert s.VEGETATION_SCALE == 1.5
    assert s.TREE_LOD_FAR_DIST == 16.0
    assert s.RAIN_DENSITY == 1.6
    assert s.TERRAIN_TEX_SIZE == 1024
    s.apply_quality_preset('medium')   # restore for any later test in the same process
    assert s.INTERNAL_WIDTH == 640 and s.QUALITY_TIER == 'medium'


def test_graphics_manager_ultra():
    import settings as s
    s.apply_quality_preset('medium')
    from graphics_manager import GraphicsManager
    gm = GraphicsManager()
    assert gm.stage_transition('ultra') is True
    cfg = gm._pending[1]
    assert cfg['internal_width'] == 1280
    assert cfg['enable_contact_shadows'] is True
    gm.rollback()
    assert gm.stage_transition('not_a_tier') is False


def test_governor_preserves_ambient_visibility():
    """The governor must be able to shed GPU post effects without touching the
    flashlight-off ambient light (the night has to stay readable)."""
    import settings as s
    import renderer as rmod
    from perf_governor import PerfGovernor, _gl_presenter_for
    s.apply_quality_preset('medium')

    class _FakeGL:
        def __init__(self):
            self.state = True
        def set_effects_enabled(self, on):
            self.state = bool(on)

    class _FakeRenderer:
        shader_renderer = None
        perf_no_stars = False
        gl_presenter = None

    fr = _FakeRenderer()
    gov = PerfGovernor(fr, rmod, s, enabled=True)
    gov._set_level(2, "test")                # shed level 2 (bypass warmup window)
    assert fr.perf_no_stars is True
    assert _gl_presenter_for(gov) is None    # no presenter -> no crash
    fr.gl_presenter = _FakeGL()
    gov._set_level(2, "test")
    assert fr.gl_presenter.state is False    # effects shed
    gov._set_level(0, "test")
    assert fr.gl_presenter.state is True      # effects restored
    # Ambient visibility constants are never modified by the governor:
    assert s.AMBIENT_LIGHT_OFF > 0.4


def test_audio_volume_groups():
    import settings as s
    s.apply_quality_preset('medium')
    from audio_synth import SoundManager
    assert hasattr(SoundManager, '_load_recording')
    defaults = s.load_settings(path='__anino_defaults_missing__.json')
    for key in ('master_volume', 'music_volume', 'sfx_volume',
                'ambient_volume', 'enemy_volume', 'weapons_volume',
                'ui_volume', 'weather_volume'):
        assert key in defaults, f"missing volume default: {key}"


def main():
    checks = [
        test_ultra_preset_definition,
        test_apply_ultra_sets_globals,
        test_graphics_manager_ultra,
        test_governor_preserves_ambient_visibility,
        test_audio_volume_groups,
    ]
    failed = 0
    for fn in checks:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {fn.__name__}: {exc}")
        except Exception as exc:
            failed += 1
            print(f"ERROR {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(checks) - failed}/{len(checks)} preset tests passed.")
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
