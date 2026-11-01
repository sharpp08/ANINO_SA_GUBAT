"""
Headless test for the HUD page-arrow rotation maths (no display needed).

Run: python tests/test_page_arrow.py
"""
import math
import os
import sys
import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    import pygame  # noqa: F401
except ImportError:                      # the maths below does not need a real pygame
    stub = types.ModuleType('pygame')
    stub.error = Exception
    sys.modules['pygame'] = stub

from page_arrow import ART_BEARING_DEG, rotation_for


def _bearing_after_rotation(art_bearing_deg, ccw_deg):
    """Clockwise-from-up bearing of the art after rotating it counter-clockwise."""
    return (art_bearing_deg - ccw_deg) % 360.0


def test_art_points_down_left_before_rotation():
    # The source art arcs from the top-right to a tip at the lower left.
    assert 180.0 < ART_BEARING_DEG % 360.0 < 270.0


def test_rotation_points_arrow_at_target():
    # rel = 0 -> straight ahead (up), +pi/2 -> player's right, -pi/2 -> left, +/-pi -> behind
    for rel in (0.0, math.pi / 2, -math.pi / 2, math.pi, -math.pi + 0.01, 0.7, -2.2):
        got = _bearing_after_rotation(ART_BEARING_DEG, rotation_for(rel))
        want = math.degrees(rel) % 360.0
        diff = abs((got - want + 180.0) % 360.0 - 180.0)
        assert diff < 1e-6, (rel, got, want)


if __name__ == '__main__':
    test_art_points_down_left_before_rotation()
    test_rotation_points_arrow_at_target()
    print('page_arrow tests passed')
