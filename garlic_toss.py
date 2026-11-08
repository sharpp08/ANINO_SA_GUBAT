"""
Garlic toss mechanic: a short 3-phase projectile flight between the player's
hand and the landing spot where the garlic protection zone will form.

Phases
  'charge' 0.15s : the viewmodel garlic sprite pops up at bottom-center of the
                   screen (world pass is not involved yet).
  'flight' 0.50s : parabolic arc in world space.
                   horizontal: easeOutCubic decel into the landing point
                   z(t)      = 4 * Z_MAX * t * (1 - t)   (pseudo-Z height,
                   same convention as manananggal_flight)
                   the bulb tumbles at 720 deg/s while a pale vapor trail
                   is emitted each frame.
  landed          : caller receives the landing tile and creates the zone.

Update/draw failures are swallowed: the toss is pure presentation.
"""
import math

import pygame
import settings as _settings_mod

_ROTATE_CACHE = {}
_ROTATE_CACHE_MAX = 192


def _rotated_bulb(img, angle):
    """Quantized, bounded rotation cache: smooth-looking tumble without per-frame transforms."""
    angle = int(round(angle / 15.0) * 15) % 360
    key = (id(img), img.get_width(), img.get_height(), angle)
    hit = _ROTATE_CACHE.get(key)
    if hit is None:
        if len(_ROTATE_CACHE) >= _ROTATE_CACHE_MAX:
            _ROTATE_CACHE.clear()
        hit = pygame.transform.rotate(img, angle)
        _ROTATE_CACHE[key] = hit
    return hit


FLIGHT_TIME = 0.5
CHARGE_TIME = 0.15
TOSS_RANGE = 4.5      # tiles the bulb lands ahead of the thrower
Z_MAX = 0.45           # peak arc height in tile units
SPIN_DPS = 720.0      # degrees per second


class GarlicToss:
    def __init__(self, x0, y0, angle, target=None):
        self.x0, self.y0 = float(x0), float(y0)
        self.angle = float(angle)
        if target is None:
            target = (x0 + math.cos(angle) * TOSS_RANGE,
                      y0 + math.sin(angle) * TOSS_RANGE)
        self.x1, self.y1 = float(target[0]), float(target[1])
        self.phase = 'charge'
        self.phase_time = 0.0
        self.landed = False
        self.land_x, self.land_y = self.x1, self.y1

    # ── Simulation ──────────────────────────────────────────────────────────
    def update(self, dt):
        """Advance the toss. Returns True on the exact frame of landing."""
        if self.landed:
            return False
        self.phase_time += dt
        if self.phase == 'charge':
            if self.phase_time >= CHARGE_TIME:
                self.phase = 'flight'
                self.phase_time = 0.0
        else:  # flight
            if self.phase_time >= FLIGHT_TIME:
                self.landed = True
                return True
        return False

    # ── Per-phase kinematics (for rendering) ───────────────────────────────

    # ── Rendering ───────────────────────────────────────────────────────────
    def draw(self, renderer, player):
        """Draw the in-flight bulb (or the charge viewmodel) onto the world surface."""
        if self.landed:
            return
        try:
            if self.phase == 'charge':
                self._draw_charge(renderer, player)
            else:
                self._draw_flight(renderer, player)
        except Exception:
            pass

    def _draw_charge(self, renderer, player):
        """Viewmodel pop-in at bottom-center during the windup."""
        img = renderer.pickup_sprites.get('garlic')
        if img is None:
            return
        u = min(1.0, self.phase_time / CHARGE_TIME)
        from zone_fx import ease_out_back
        scale = 0.5 + 0.5 * ease_out_back(u)
        sw = max(4, int(img.get_width() * scale))
        sh = max(4, int(img.get_height() * scale))
        thumb = img.get_scaled((sw, sh))
        x = int(renderer.w * 0.5 + renderer.w * 0.22 * (1.0 - u))
        y = int(renderer.h * 0.92 - 18 * u)
        renderer.surface.blit(thumb, (x - sw // 2, y - sh // 2))

    def _draw_flight(self, renderer, player):
        wx, wy, z = self.world_pos()
        from zone_fx import ZoneFX
        proj = ZoneFX._project(renderer, player, wx, wy)
        if proj is None:
            return
        screen_x, floor_y, unit, dist = proj
        img = renderer.pickup_sprites.get('garlic')
        if img is None:
            return
        # Same depth-scaling as the pickup pass; the bulb rides z() pixels above
        # its floor contact point.
        sw = max(3, int(unit * 0.32))
        sh = max(3, int(unit * 0.32 * img.get_height() / max(1, img.get_width())))
        lift = int(z * unit)
        img2 = img.get_scaled((sw, sh)) if (sw, sh) != img.get_size() else img
        # True tumbling rotation, quantized to 15-degree steps and cached.
        # The cache is bounded so depth changes cannot grow memory indefinitely.
        spin_img = _rotated_bulb(img2, self.spin())
        cx = int(screen_x) - spin_img.get_width() // 2
        cy = int(floor_y) - sh - lift - (spin_img.get_height() - sh) // 2
        renderer.surface.blit(spin_img, (cx, cy))
        # Pungent vapor trail
        if _settings_mod.ENABLE_PARTICLES:
            try:
                renderer.physics_particles.emit(
                    cx + sw // 2, cy + sh, vx=0.0, vy=-4.0,
                    life=0.5, size=1.0, color=(190, 185, 160),
                    gravity_scale=0.0, drag_scale=0.9)
            except Exception:
                pass

    def flight_t(self):
        return min(1.0, self.phase_time / FLIGHT_TIME)

    def world_pos(self):
        t = self.flight_t()
        # easeOutCubic horizontal deceleration into the landing point
        u = 1.0 - (1.0 - t) ** 3
        x = self.x0 + (self.x1 - self.x0) * u
        y = self.y0 + (self.y1 - self.y0) * u
        z = 4.0 * Z_MAX * t * (1.0 - t)          # parabola, peak at t=0.5
        return x, y, z

    def spin(self):
        return (self.phase_time * SPIN_DPS) % 360.0
