"""
Headless tests for the pure helpers of the GPU presenter (no pygame / OpenGL needed).

Run: python tests/test_gl_present.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gl_present import (compute_swizzle, letterbox, map_to_surface,
                        VERTEX_SHADER, FRAGMENT_SHADER)


def test_swizzle_matches_pixel_layout():
    assert compute_swizzle((16, 8, 0, 0)) == 'BGR1'    # pygame default: stored B,G,R,X
    assert compute_swizzle((16, 8, 0, 24)) == 'BGR1'
    assert compute_swizzle((0, 8, 16, 24)) == 'RGB1'   # opaque scene upload
    assert compute_swizzle((16, 8, 0, 24), preserve_alpha=True) == 'BGRA'
    assert compute_swizzle((0, 8, 16, 24), preserve_alpha=True) == 'RGBA'
    for bad in ((16, 16, 0, 0), (5, 8, 0, 0), (40, 8, 0, 0)):
        try:
            compute_swizzle(bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted bad layout {bad}")


def test_letterbox_keeps_aspect():
    assert letterbox(1280, 720, 640, 360) == (0, 0, 1280, 720)
    assert letterbox(1920, 1080, 640, 360) == (0, 0, 1920, 1080)
    x, y, w, h = letterbox(1024, 768, 640, 360)          # 4:3 monitor -> bars top/bottom
    assert (x, w, h) == (0, 1024, 576) and y == 96
    x, y, w, h = letterbox(2560, 1080, 640, 360)         # ultrawide -> bars left/right
    assert h == 1080 and w == 1920 and x == 320 and y == 0


def test_mouse_mapping_round_trips():
    assert map_to_surface((512, 384), 1024, 768, 640, 360) == (320, 180)   # window centre
    assert map_to_surface((0, 96), 1024, 768, 640, 360) == (0, 0)           # image top-left
    assert map_to_surface((1023, 96 + 575), 1024, 768, 640, 360) == (639, 359)
    assert map_to_surface((960, 540), 1920, 1080, 640, 360) == (320, 180)


def test_shader_targets_opengl_33_core():
    # Intel UHD's Windows driver supports this GLSL baseline; keep the presenter
    # independent of newer desktop-only shader features.
    assert VERTEX_SHADER.startswith("#version 330 core")
    assert FRAGMENT_SHADER.startswith("#version 330 core")
    assert "in vec2 in_position" in VERTEX_SHADER
    assert "in vec2 in_uv" in VERTEX_SHADER
    for uniform in ("u_texture", "u_overlay", "u_has_overlay", "u_time", "u_flashlight_on",
                    "u_fog_density", "u_supernatural_intensity",
                    "u_post", "u_bloom_strength"):
        assert f"uniform " in FRAGMENT_SHADER and uniform in FRAGMENT_SHADER
    assert "over.rgb * over.a + col.rgb * (1.0 - over.a)" in FRAGMENT_SHADER
    # smoothstep edges must be ascending; reversed edges are undefined in GLSL.
    assert "smoothstep(0.48, 0.05" not in FRAGMENT_SHADER
    assert "smoothstep(0.05, 0.48" not in FRAGMENT_SHADER


def test_overlay_is_composited_on_the_post_processed_path():
    # Regression: PLAYING/PAUSED present with post=True. The overlay (HUD, hands, weapons,
    # crosshair) used to be composited only inside the `u_post == 0` early-return branch, so
    # it vanished in-game. It must also be sampled after the post-processing stages.
    src = FRAGMENT_SHADER
    assert src.count("texture(u_overlay") >= 2
    post_branch_end = src.index("fragColor = vec4(col.rgb, 1.0);\n        return;")
    last_overlay = src.rindex("texture(u_overlay")
    last_effect = max(src.rindex("rand(uv"), src.rindex("smoothstep(0.25, 0.95"))
    assert post_branch_end < last_overlay, "overlay must be composited on the post path"
    assert last_overlay > last_effect, "overlay must be composited after grade/vignette/grain"


if __name__ == '__main__':
    test_overlay_is_composited_on_the_post_processed_path()
    test_swizzle_matches_pixel_layout()
    test_letterbox_keeps_aspect()
    test_mouse_mapping_round_trips()
    test_shader_targets_opengl_33_core()
    print("All GL presenter helper tests passed.")
