"""Regression tests for the read-only enemy debug population counter."""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from renderer import enemy_debug_counts


def test_counts_unique_live_enemies_and_cumulative_total():
    a = SimpleNamespace(alive=True)
    b = SimpleNamespace(alive=False)
    c = SimpleNamespace(alive=True)
    assert enemy_debug_counts([a, b, a, c], chapter_total=5) == (2, 5)


def test_survival_spawn_increases_population_denominator():
    enemies = [SimpleNamespace(alive=True) for _ in range(6)]
    assert enemy_debug_counts(enemies, chapter_total=5) == (6, 6)


def test_removed_dead_enemy_does_not_shrink_cumulative_total():
    remaining = [SimpleNamespace(alive=True) for _ in range(4)]
    assert enemy_debug_counts(remaining, chapter_total=6) == (4, 6)


if __name__ == "__main__":
    test_counts_unique_live_enemies_and_cumulative_total()
    test_survival_spawn_increases_population_denominator()
    test_removed_dead_enemy_does_not_shrink_cumulative_total()
    print("Enemy debug counter tests passed.")
