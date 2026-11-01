"""
Headless regression test: every Bible page (and the exit) must be reachable on foot
WITHOUT having to open a door, using the player's real collision circle.

Closed doors are solid in play and only open when the player finds and uses them, so a
page sealed behind one can be missed entirely. (The map's own reachability validator
treats doors as passable, so it does not catch this.)

Run: python tests/test_page_access.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from map_system import GameMap
from settings import PLAYER_SIZE


def _reachable_with_closed_doors(gm):
    sx, sy = int(gm.player_start[0]), int(gm.player_start[1])
    seen = {(sx, sy)}
    stack = [(sx, sy)]
    while stack:
        cx, cy = stack.pop()
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if (nx, ny) in seen or not (0 < nx < gm.width - 1 and 0 < ny < gm.height - 1):
                continue
            if not gm.is_circle_solid(nx + 0.5, ny + 0.5, PLAYER_SIZE, doors_block=True):
                seen.add((nx, ny))
                stack.append((nx, ny))
    return seen


def test_pages_and_exit_reachable_without_opening_doors():
    for ch in (1, 2):
        gm = GameMap(ch)
        reach = _reachable_with_closed_doors(gm)
        for p in gm.pickups:
            if p['type'] != 'bible_page':
                continue
            assert (int(p['x']), int(p['y'])) in reach, \
                f"chapter {ch}: Bible page at ({p['x']}, {p['y']}) is sealed off by walls/doors"
            assert not gm.is_circle_solid(p['x'], p['y'], PLAYER_SIZE, doors_block=True), \
                f"chapter {ch}: Bible page at ({p['x']}, {p['y']}) overlaps a wall"
        ex, ey = gm.exit_pos
        assert (int(ex), int(ey)) in reach, f"chapter {ch}: exit is unreachable"


if __name__ == '__main__':
    test_pages_and_exit_reachable_without_opening_doors()
    print('page access test passed')
