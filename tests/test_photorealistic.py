"""Headless numerical checks for the photorealistic presentation helpers."""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from photorealistic import grade_rgb_array


def test_grade_is_bounded_and_preserves_shape():
    source = np.full((32, 24, 3), 110, dtype=np.uint8)
    view = source.copy()
    grade_rgb_array(view, 0.0)
    assert view.shape == source.shape
    assert view.dtype == np.uint8
    assert int(view.min()) >= 0 and int(view.max()) <= 255
    assert not np.array_equal(view, source)


def test_dawn_grade_differs_from_night_grade():
    night = np.full((8, 8, 3), 90, dtype=np.uint8)
    dawn = night.copy()
    grade_rgb_array(night, 0.0)
    grade_rgb_array(dawn, 1.0)
    assert not np.array_equal(night, dawn)


if __name__ == "__main__":
    test_grade_is_bounded_and_preserves_shape()
    test_dawn_grade_differs_from_night_grade()
    print("Photorealistic numerical tests passed.")
