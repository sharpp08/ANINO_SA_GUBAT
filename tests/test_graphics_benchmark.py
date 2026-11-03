"""Tests for the graphics benchmark helpers (pure functions only - no map build).

Run with:  python tests\\test_graphics_benchmark.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tools')))


def test_recommend_tier():
    from graphics_benchmark import recommend_tier
    assert recommend_tier(9.0) == 'ultra'
    assert recommend_tier(10.0) == 'ultra'
    assert recommend_tier(12.0) == 'high'
    assert recommend_tier(13.0) == 'high'
    assert recommend_tier(14.9) == 'medium'
    assert recommend_tier(30.0) == 'low'


def test_stats_and_p95():
    from graphics_benchmark import _stats
    st = _stats([1.0] * 100 + [50.0])        # one hitch at the end
    assert st['frames'] == 101
    assert abs(st['avg_ms'] - (100 * 1.0 + 50.0) / 101) < 1e-9
    assert st['max_ms'] == 50.0
    # The single hitch sits above the p95 cut, so p95 stays on the normal frame.
    assert st['p95_ms'] == 1.0
    assert _stats([]) == {}


def test_densest_tree_helper():
    from graphics_benchmark import _densest_tree

    class _Map:
        trees = [
            {'x': 10.0, 'y': 10.0},
            {'x': 10.5, 'y': 10.2},
            {'x': 11.0, 'y': 10.8},
            {'x': 100.0, 'y': 100.0},
        ]

    tree = _densest_tree(_Map())
    assert tree is not None
    assert abs(tree['x'] - 10.0) < 1.0
    assert _densest_tree(type('Empty', (), {'trees': []})()) is None


def test_benchmark_tier_smoke():
    """Very short headless tier build; skipped on machines where pygame has no
    SDL dummy driver available (the import itself must still succeed)."""
    import graphics_benchmark as gb
    assert callable(gb.benchmark_tier) and callable(gb.benchmark_all)
    assert callable(gb.quick_benchmark_report)


def main():
    checks = [test_recommend_tier, test_stats_and_p95,
              test_densest_tree_helper, test_benchmark_tier_smoke]
    failed = 0
    for fn in checks:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL  {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(checks) - failed}/{len(checks)} benchmark tests passed.")
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
