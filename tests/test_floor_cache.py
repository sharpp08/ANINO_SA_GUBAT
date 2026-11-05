"""Regression tests for cached floor perspective constants."""
import unittest
import numpy as np
import floor_fast


class FloorConstantCacheTests(unittest.TestCase):
    def setUp(self):
        floor_fast._floor_const_cache.clear()

    def test_float32_distance_rows_are_cached(self):
        first = floor_fast._get_floor_constants(360, 180, 0, 1.25)
        second = floor_fast._get_floor_constants(360, 180, 0, 2.50)

        # The per-frame mist changes, but pitch-dependent distance rows are reused.
        self.assertEqual(first[1].dtype, np.float32)
        self.assertIs(first[1], second[1])
        self.assertEqual(first[1].shape, second[1].shape)
        self.assertFalse(np.shares_memory(first[-1], second[-1]) is False)

    def test_pitch_change_rebuilds_distance_rows(self):
        first = floor_fast._get_floor_constants(360, 180, 0, 0.0)
        second = floor_fast._get_floor_constants(360, 180, 3, 0.0)
        self.assertIsNot(first[1], second[1])
        self.assertEqual(second[1].dtype, np.float32)


if __name__ == "__main__":
    unittest.main()
