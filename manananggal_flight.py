"""Manananggal flight behaviour.

A Manananggal is a *flying* hunter: it hovers and swoops through the sky
rather than scurrying on the ground. In a top-down raycaster the "sky" is a
pseudo-Z height, so this module owns the horizontal steering plus a
**terrain-relative altitude** that keeps the creature at a *medium* height
above the landscape.

Core guarantee (the "never flies too high" rule):

    altitude  = terrain_height(x, y) + loft
    loft      = clamp(base_altitude + bob, altitude_min, altitude_max)

``altitude`` always tracks the ground beneath it, and the amount *above* the
terrain (``loft``) is clamped to a medium band ``[altitude_min, altitude_max]``.
Because of the hard upper clamp the creature can physically never climb higher
than ``terrain + altitude_max`` no matter how the steering/loitering behaves.

Everything here is pure math + a couple of well-known map helpers
(``clamp_position``) so the module is headless-unit-testable with a fake map.
No pygame / NumPy / renderer imports.
"""

import math

# Enemy types that use this full flight controller (airborne hunters).
FLYING_TYPES = ('manananggal',)

# Flight behaviour modes (selected from the enemy AI state in enemies.py).
CHASE = 'chase'      # fly toward the player, orbiting the attack band (high)
LOITER = 'loiter'    # cruise in a circle around the creature's anchor (high)
FLEE = 'flee'        # bank away from the threat, then orbit behind it (high)
DESCEND = 'descend'  # level out while keeping the high-altitude band
STRIKE = 'strike'    # dive down to a low altitude to attack the player


class TerrainHeightSampler:
    """Sample the ground height at a world position.

    The current maps are flat, so the default provider returns 0.0. If a
    ``game_map`` exposes a NumPy ``terrain_height`` 2-D array it is used
    instead, which makes the altitude genuinely *relative to the terrain* on
    any height-mapped map. Out-of-range samples are treated as the map's own
    height (0.0) rather than extrapolating.
    """

    def __init__(self, provider=None):
        self._provider = provider

    def height(self, x, y, game_map):
        """Return the terrain height (tiles) at ``game_map`` position (x, y)."""
        if self._provider is not None:
            return float(self._provider(x, y, game_map))
        th = getattr(game_map, 'terrain_height', None)
        if th is None:
            return 0.0
        ix = int(math.floor(x))
        iy = int(math.floor(y))
        w = getattr(game_map, 'width', 0) or 0
        h = getattr(game_map, 'height', 0) or 0
        if w <= 0 or h <= 0 or not (0 <= ix < w and 0 <= iy < h):
            return 0.0
        try:
            return float(th[iy, ix])
        except Exception:
            return 0.0


class FlightController:
    """Owns a flying enemy's horizontal position and high, terrain-relative altitude.

    Call :meth:`update` once per rendered frame. It steers the ground-plane
    (x, y) toward a mode-appropriate goal and sets ``altitude`` (tiles above
    terrain) to a smoothed, hard-clamped high band so the creature flies
    through the sky, well above the ground, while still never soaring too high.
    """

    def __init__(self, speed=2.5, base_altitude=2.4,
                 altitude_min=2.0, altitude_max=3.2,
                 strike_altitude=0.5, strike_min=0.2,
                 alt_lerp=2.5, bob_amplitude=0.18, bob_freq=1.6,
                 orbit_radius=5.5, orbit_speed=1.0, arrive_radius=3.0,
                 flee_radius=9.0, turn_rate=4.5, footprint=0.4,
                 terrain=None):
        self.speed = float(speed)
        # High-altitude band (tiles above the ground). The creature hovers
        # well above the tree canopy (~1.45 tiles tall) so it reads as flying
        # through the sky rather than skimming the ground; the hard upper clamp
        # still keeps it from ever soaring out of the landscape.
        self.base_altitude = float(base_altitude)
        self.altitude_min = float(altitude_min)
        self.altitude_max = float(altitude_max)
        if self.altitude_max < self.altitude_min:
            self.altitude_max = self.altitude_min
        self.alt_lerp = float(alt_lerp)
        self.bob_amplitude = float(bob_amplitude)
        self.bob_freq = float(bob_freq)
        self.orbit_radius = float(orbit_radius)
        self.orbit_speed = float(orbit_speed)
        self.arrive_radius = float(arrive_radius)
        self.flee_radius = float(flee_radius)
        self.turn_rate = float(turn_rate)
        self.footprint = float(footprint)
        # Low strike band (tiles above the ground): the creature dives to this
        # altitude to attack the player, then climbs back up when it's not striking.
        self.strike_altitude = float(strike_altitude)
        self.strike_min = float(strike_min)
        self.terrain = terrain or TerrainHeightSampler()

        # Runtime state.
        self.x = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.altitude = self.base_altitude   # tiles above terrain
        self.terrain_height = 0.0            # ground height under us
        self.loft = self.base_altitude       # excess over terrain (clamped)
        self._loft = self.base_altitude      # smoothed excess (drives climb/dive)
        self.facing = 0.0
        self._bob_phase = 0.0
        self._orbit_phase = 0.0
        self._anchor_x = 0.0
        self._anchor_y = 0.0

    # ── public API ───────────────────────────────────────────────────────
    def set_origin(self, x, y):
        """Place the creature (also seeds its loiter anchor and velocity)."""
        self.x = float(x)
        self.y = float(y)
        self._anchor_x = self.x
        self._anchor_y = self.y
        self.vx = 0.0
        self.vy = 0.0

    def update(self, dt, target_x, target_y, mode, game_map):
        """Advance one frame.

        ``mode`` is one of :data:`CHASE`, :data:`LOITER`, :data:`FLEE`,
        :data:`DESCEND`, :data:`STRIKE`. ``target_x/target_y`` is the player
        position for chase/flee/strike and the loiter centre otherwise.
        Returns ``(x, y)``.
        """
        dt = max(0.0, float(dt))
        if mode == FLEE:
            goal = self._flee_goal(target_x, target_y)
        elif mode in (CHASE, STRIKE):
            goal = self._chase_goal(target_x, target_y)
        else:  # LOITER / DESCEND cruise around the anchor
            goal = self._loiter_goal(target_x, target_y)

        # Smoothly steer the velocity toward the goal so turns are banked, not
        # snapped (this is what reads as "flying through the sky").
        gx = goal[0] - self.x
        gy = goal[1] - self.y
        gdist = math.hypot(gx, gy)
        if gdist > 0.05:
            dvx = (gx / gdist) * self.speed
            dvy = (gy / gdist) * self.speed
        else:
            dvx, dvy = 0.0, 0.0
        blend = 1.0 - math.exp(-self.turn_rate * dt)
        self.vx += (dvx - self.vx) * blend
        self.vy += (dvy - self.vy) * blend

        self.x += self.vx * dt
        self.y += self.vy * dt

        # Keep the aircraft inside the playable box. A flying enemy passes
        # *over* trees, so we intentionally do NOT push it out of trunks here;
        # the perimeter of the forest is the hard bound.
        if game_map is not None and hasattr(game_map, 'clamp_position'):
            try:
                self.x, self.y = game_map.clamp_position(self.x, self.y, self.footprint)
            except Exception:
                pass

        if abs(self.vx) > 0.02 or abs(self.vy) > 0.02:
            self.facing = math.atan2(self.vy, self.vx)

        # ── altitude: terrain-relative, high normally / low when striking ──
        self._orbit_phase += dt * self.orbit_speed
        self._bob_phase += dt * self.bob_freq
        self.terrain_height = self.terrain.height(self.x, self.y, game_map)
        bob = self.bob_amplitude * math.sin(self._bob_phase)
        if mode == STRIKE:
            # Dive to the low strike band to attack the player.
            target_loft = self.strike_altitude + 0.5 * bob
            lo, hi = self.strike_min, self.strike_altitude + self.bob_amplitude
        else:
            # Hold the high cruising band; chasing adds a little extra lift.
            target_loft = self.base_altitude + bob
            if mode == CHASE:
                target_loft += self.bob_amplitude
            lo, hi = self.altitude_min, self.altitude_max
        target_loft = max(lo, min(target_loft, hi))
        # Smooth the excess so climbing / diving is a banked swoop, not a snap.
        smooth = 1.0 - math.exp(-self.alt_lerp * dt)
        self._loft += (target_loft - self._loft) * smooth
        self.loft = self._loft
        # Absolute altitude always tracks the terrain beneath us; the clamped
        # band guarantees it never soars above the landscape even on a cliff.
        self.altitude = self.terrain_height + self._loft
        return self.x, self.y

    def altitude_pixels(self, unit):
        """Altitude in screen pixels for the renderer (``unit`` = px per tile)."""
        return self.altitude * unit

    # ── goal constructors ────────────────────────────────────────────────
    def _chase_goal(self, tx, ty):
        """Approach the target, then orbit the arrive band around it."""
        d = math.hypot(tx - self.x, ty - self.y)
        if d > self.arrive_radius:
            return tx, ty
        a = self._orbit_phase
        return tx + math.cos(a) * self.orbit_radius, ty + math.sin(a) * self.orbit_radius

    def _loiter_goal(self, tx, ty):
        """Cruise a circle around the anchor (or the given non-zero centre)."""
        if abs(tx) > 1e-6 or abs(ty) > 1e-6:
            cx, cy = tx, ty
        else:
            cx, cy = self._anchor_x, self._anchor_y
        a = self._orbit_phase
        return cx + math.cos(a) * self.orbit_radius, cy + math.sin(a) * self.orbit_radius

    def _flee_goal(self, tx, ty):
        """Bank to the point just beyond the flee ring, opposite the threat."""
        dx, dy = self.x - tx, self.y - ty
        d = math.hypot(dx, dy)
        if d < 1e-3:
            a = self._orbit_phase
            return self.x + math.cos(a) * self.flee_radius, self.y + math.sin(a) * self.flee_radius
        nx, ny = dx / d, dy / d
        base_x = tx + nx * self.flee_radius
        base_y = ty + ny * self.flee_radius
        a = self._orbit_phase
        return base_x + math.cos(a) * (self.flee_radius * 0.35), base_y + math.sin(a) * (self.flee_radius * 0.35)


def make_flight_controller(enemy_type, speed, terrain=None):
    """Return a configured :class:`FlightController` for a flying type, else None.

    Only :data:`FLYING_TYPES` get the full controller; grounded enemies keep
    their existing pathfinding/walking movement.
    """
    if enemy_type not in FLYING_TYPES:
        return None
    return FlightController(speed=float(speed), terrain=terrain)


# ── headless self-test (python manananggal_flight.py) ───────────────────
def _self_test():
    class _FlatMap:
        width, height = 120, 120

        def clamp_position(self, x, y, radius):
            m = 2.0 + radius
            return max(m, min(x, self.width - m)), max(m, min(y, self.height - m))

    class _ReliefMap(_FlatMap):
        """A gentle valley along x so the terrain height is not uniform."""

        def __init__(self):
            import numpy as np
            xg = np.linspace(0.0, 4.0, self.width)
            base = 1.5 * np.sin(xg * 0.5) ** 2
            self.terrain_height = np.tile(base[None, :], (self.height, 1))

    fc = make_flight_controller('manananggal', speed=2.5)
    assert fc is not None, 'manananggal must get a controller'
    assert make_flight_controller('aswang', 2.0) is None, 'grounded types get None'

    # 1) Altitude never exceeds the hard cap over *flat* terrain.
    m = _FlatMap()
    fc.set_origin(60, 60)
    for _ in range(600):
        fc.update(1.0 / 60.0, 60, 60, CHASE, m)
        assert fc.altitude <= fc.altitude_max + 1e-9, fc.altitude
    assert fc.terrain_height == 0.0

    # 2) Altitude *tracks the terrain*: over the relief map the loft stays in
    #    the medium band while the absolute altitude follows the valley.
    rm = _ReliefMap()
    fc2 = make_flight_controller('manananggal', speed=2.5)
    fc2.set_origin(60, 60)
    saw_min, saw_max = None, None
    for _ in range(1200):
        fc2.update(1.0 / 60.0, 0, 0, LOITER, rm)
        loft = fc2.altitude - fc2.terrain_height
        assert fc2.altitude_min - 1e-9 <= loft <= fc2.altitude_max + 1e-9, (loft, fc2.altitude)
        saw_min = fc2.altitude if saw_min is None else min(saw_min, fc2.altitude)
        saw_max = fc2.altitude if saw_max is None else max(saw_max, fc2.altitude)
    assert saw_max - saw_min > 0.15, (saw_min, saw_max)  # the valley must show through

    # 3) Fleeing keeps the enemy on the far side of the threat.
    fc3 = make_flight_controller('manananggal', speed=4.0)
    fc3.set_origin(60, 60)
    threat = (80, 60)
    for _ in range(300):
        fc3.update(1.0 / 60.0, threat[0], threat[1], FLEE, m)
    assert math.hypot(fc3.x - threat[0], fc3.y - threat[1]) > fc3.flee_radius * 0.5

    # 4) The playable-box clamp is respected even mid-flight: a flight that
    # would cross the north edge is pulled back to the clamp floor, and the
    # creature can never leave the box.
    fc4 = make_flight_controller('manananggal', speed=6.0)
    fc4.set_origin(60, 2)
    for _ in range(400):
        x, y = fc4.update(1.0 / 60.0, 60, 2, LOITER, m)
        assert y >= 2.4 - 1e-9, (x, y)          # never crosses the north clamp floor
        assert y <= m.height - 2.4, (x, y)        # and never leaves the box

    print('[manananggal_flight] self-test passed '
          f'(cap={fc.altitude_max}, relief span={saw_max - saw_min:.2f})')


if __name__ == '__main__':
    _self_test()
