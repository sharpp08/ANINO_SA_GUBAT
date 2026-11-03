"""
Headless tests for the pure helpers of the GPU presenter (no pygame / OpenGL needed).

Run: python tests/test_gl_present.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gl_present import compute_swizzle, letterbox, map_to_surface


def test_swizzle_matches_pixel_layout():
    assert compute_swizzle((16, 8, 0, 0)) == 'BGR1'    # pygame default: stored B,G,R,X
    assert compute_swizzle((16, 8, 0, 24)) == 'BGR1'
    assert compute_swizzle((0, 8, 16, 24)) == 'RGB1'   # stored R,G,B,A
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


if __name__ == '__main__':
    test_swizzle_matches_pixel_layout()
    test_letterbox_keeps_aspect()
    test_mouse_mapping_round_trips()
    print("All GL presenter helper tests passed.")
