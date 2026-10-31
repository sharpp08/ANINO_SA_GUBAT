"""
Objective guidance: what the player should head for next, and which way it is.

Kept free of pygame so it can be unit-tested headlessly (see tests/test_objective.py).

Direction convention matches the raycaster and radar.py: the player faces `angle`,
forward is (cos a, sin a) and the right-hand side of the screen is angle + 90 degrees.
"""
import math

# Eight 45-degree sectors, centred on "ahead", going clockwise (towards the right).
_SECTORS = ('ahead', 'ahead-right', 'right', 'behind-right',
            'behind', 'behind-left', 'left', 'ahead-left')


def relative_bearing(px, py, facing, tx, ty):
    """Angle to (tx, ty) relative to where the player faces, in (-pi, pi].

    0 = straight ahead, positive = to the player's right, +/-pi = directly behind.
    """
    rel = math.atan2(ty - py, tx - px) - facing
    while rel > math.pi:
        rel -= 2 * math.pi
    while rel <= -math.pi:
        rel += 2 * math.pi
    return rel


def direction_word(rel):
    """Plain-words direction for a relative bearing from relative_bearing()."""
    return _SECTORS[int(round(rel / (math.pi / 4))) % 8]


def nearest_page(px, py, pickups):
    """Nearest uncollected Bible page as {'x', 'y', 'dist'}, or None if none remain."""
    best = None
    for p in pickups:
        if p.get('type') != 'bible_page' or not p.get('active', True):
            continue
        d = math.hypot(p['x'] - px, p['y'] - py)
        if best is None or d < best['dist']:
            best = {'x': p['x'], 'y': p['y'], 'dist': d}
    return best


def next_objective(px, py, pickups, exit_pos, pages_have, pages_needed, require_pages=True):
    """What to head for next: {'kind': 'page'|'exit', 'x', 'y', 'dist'}, or None.

    While the exit is sealed (pages still needed) the target is the nearest
    uncollected page. Once enough pages are held - or if no page is left to find -
    it is the exit.
    """
    if require_pages and pages_have < pages_needed:
        page = nearest_page(px, py, pickups)
        if page is not None:
            page['kind'] = 'page'
            return page
    if exit_pos:
        ex, ey = exit_pos
        return {'kind': 'exit', 'x': ex, 'y': ey, 'dist': math.hypot(ex - px, ey - py)}
    return None
