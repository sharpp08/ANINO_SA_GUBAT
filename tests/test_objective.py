"""
Headless tests for objective guidance (no pygame needed).

Run: python tests/test_objective.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from map_system import GameMap
from objective import direction_word, nearest_page, next_objective, relative_bearing
from settings import PAGES_REQUIRED_CH1, PAGES_REQUIRED_CH2


def test_bearing_convention():
    # Facing +x: right-hand side is +y (angle + 90 degrees), matching the raycaster/radar.
    assert abs(relative_bearing(0, 0, 0.0, 5, 0)) < 1e-9
    assert abs(relative_bearing(0, 0, 0.0, 0, 5) - math.pi / 2) < 1e-9
    assert abs(relative_bearing(0, 0, 0.0, 0, -5) + math.pi / 2) < 1e-9
    assert abs(abs(relative_bearing(0, 0, 0.0, -5, 0)) - math.pi) < 1e-9
    # Wrap-around: facing almost a full turn still resolves to a small bearing
    assert abs(relative_bearing(0, 0, 2 * math.pi - 0.1, 5, 0) - 0.1) < 1e-9
    for rel in (-math.pi + 0.01, -2.0, -1.0, 0.0, 1.0, 2.0, math.pi):
        assert -math.pi < relative_bearing(0, 0, rel, 3, 4) <= math.pi
    print("[PASS] bearing convention")


def test_direction_words():
    assert direction_word(0.0) == 'ahead'
    assert direction_word(math.pi / 2) == 'right'
    assert direction_word(-math.pi / 2) == 'left'
    assert direction_word(math.pi) == 'behind'
    assert direction_word(-math.pi) == 'behind'
    assert direction_word(math.pi / 4) == 'ahead-right'
    assert direction_word(-math.pi / 4) == 'ahead-left'
    assert direction_word(3 * math.pi / 4) == 'behind-right'
    assert direction_word(-3 * math.pi / 4) == 'behind-left'
    print("[PASS] direction words")


def test_objective_flow_on_real_chapters():
    for ch, need in ((1, PAGES_REQUIRED_CH1), (2, PAGES_REQUIRED_CH2)):
        gm = GameMap(ch)
        px, py = gm.player_start
        pages = [p for p in gm.pickups if p['type'] == 'bible_page']
        assert len(pages) >= need, f"chapter {ch} has fewer pages than the exit needs"

        have = 0
        collected = 0
        while have < need:
            obj = next_objective(px, py, gm.pickups, gm.exit_pos, have, need)
            assert obj and obj['kind'] == 'page', "should point at a page while the exit is sealed"
            expect = min(math.hypot(p['x'] - px, p['y'] - py) for p in pages if p['active'])
            assert abs(obj['dist'] - expect) < 1e-9
            # walk to it and collect it
            for p in pages:
                if p['active'] and (p['x'], p['y']) == (obj['x'], obj['y']):
                    p['active'] = False
                    px, py = p['x'], p['y']
                    break
            have += 1
            collected += 1
        obj = next_objective(px, py, gm.pickups, gm.exit_pos, have, need)
        assert obj['kind'] == 'exit' and (obj['x'], obj['y']) == gm.exit_pos
        print(f"[PASS] chapter {ch}: {collected} pages then exit")


def test_edge_cases():
    # No pages left anywhere but still short: fall back to the exit rather than nothing
    pickups = [{'type': 'bible_page', 'x': 5, 'y': 5, 'active': False}]
    obj = next_objective(0, 0, pickups, (10, 0), 0, 3)
    assert obj['kind'] == 'exit'
    # Pages not required: always the exit
    obj = next_objective(0, 0, [{'type': 'bible_page', 'x': 1, 'y': 1}], (10, 0), 0, 3, require_pages=False)
    assert obj['kind'] == 'exit'
    # No exit and nothing to find
    assert next_objective(0, 0, [], None, 3, 3) is None
    # Non-page pickups are ignored
    assert nearest_page(0, 0, [{'type': 'health', 'x': 1, 'y': 1, 'active': True}]) is None
    print("[PASS] edge cases")


if __name__ == '__main__':
    test_bearing_convention()
    test_direction_words()
    test_objective_flow_on_real_chapters()
    test_edge_cases()
    print("All objective tests passed.")
