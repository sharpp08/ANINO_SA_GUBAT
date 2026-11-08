"""
Zone FX: renders active salt/garlic protection zones (EnemyManager.active_effects).

The zone pass projects each zone's ground position with the same math as the
pickup sprite pass (relative bearing -> screen column, WALL_HEIGHT_SCALE depth
squish -> floor contact line) and draws:
  * a perspective-squished elliptical ring decal on the ground,
  * an additive emissive glow ring registered on Renderer._emissive
    (drawn AFTER the darkness pass, so wards stay visible in the dark),
  * phosphorescent salt motes / garlic vapor drifting up from the ring.

Lifecycle animation (per zone, driven by timer vs max_timer):
  * Formation  : first 0.5s, ring radius scales in with easeOutQuad.
  * Sustained  : breathing pulse sin(age*3) +-5% radius.
  * Dissipation: last 0.5s, alpha ramps to 0 and grains scatter.

All drawing is wrapped defensively: a zone pass failure must never crash
the render loop.
"""
import math
import random

import pygame
import settings as _settings_mod

# Per-zone-type visual profile: (ring RGB, emissive RGB, mote RGB)
ZONE_STYLE = {
    'salt':   ((220, 240, 255), (90, 100, 125),  (210, 230, 255)),
    'garlic': ((230, 220, 200), (120, 110, 80),  (190, 185, 160)),
}

FORMATION_TIME = 0.5   # seconds of easeOutQuad ring scale-in
FADE_TIME = 0.5       # seconds of alpha fade-out
MOTES_INTERVAL = 0.35 # seconds between mote spawns per visible zone


def ease_out_quad(t):
    t = min(1.0, max(0.0, t))
    return 1.0 - (1.0 - t) ** 2


def ease_out_cubic(t):
    t = min(1.0, max(0.0, t))
    return 1.0 - (1.0 - t) ** 3


def ease_out_back(t):
    """Overshooting pop-in, used for the cross manifestation."""
    t = min(1.0, max(0.0, t))
    c1, c3 = 1.70158, 2.70158
    return 1.0 + c3 * (t - 1.0) ** 3 + c1 * (t - 1.0) ** 2


class ZoneFX:
    """Draws every active salt/garlic zone for the current frame."""

    def __init__(self):
        # zone id -> last mote-emit timestamp (seconds)
        self._mote_timers = {}
        self._time = 0.0

    # ── Projection (mirrors Renderer._unit_h / pickup pass) ───────────────
    @staticmethod
    def _project(renderer, player, wx, wy):
        dx = wx - player.x
        dy = wy - player.y
        dist = math.hypot(dx, dy)
        if dist < 0.05:
            dist = 0.05
        rel = math.atan2(dy, dx) - player.angle
        while rel > math.pi:
            rel -= 2.0 * math.pi
        while rel < -math.pi:
            rel += 2.0 * math.pi
        if abs(rel) > renderer.half_fov + 0.5:
            return None
        if dist > _settings_mod.MAX_DEPTH:
            return None
        screen_x = int((rel / renderer.fov_rad + 0.5) * renderer.w)
        unit = renderer._unit_h(dist)
        horizon_y = max(0, renderer.h // 2 + int(player.pitch * renderer.h))
        floor_y = horizon_y + unit * 0.5
        return screen_x, floor_y, unit, dist

    def update(self, dt):
        self._time += dt
        if len(self._mote_timers) > 64:
            self._mote_timers.clear()


    def draw(self, renderer, player, zones):
        """One zone pass per frame. Appends ('ring', ...) to renderer._emissive."""
        if not zones:
            return
        surface = renderer.surface
        try:
            for zone in zones:
                ztype = zone.get('type')
                style = ZONE_STYLE.get(ztype)
                if style is None:
                    continue
                ring_col, glow_col, mote_col = style
                radius = float(zone.get('radius', 2.0))
                timer = float(zone.get('timer', 0.0))
                max_timer = float(zone.get('max_timer', timer))
                if timer <= 0.0:
                    continue
                proj = self._project(renderer, player, zone.get('x', 0.0), zone.get('y', 0.0))
                if proj is None:
                    continue
                screen_x, floor_y, unit, dist = proj

                # ── Lifecycle envelopes ──
                age = max(0.0, max_timer - timer)
                scale = ease_out_quad(min(1.0, age / FORMATION_TIME))
                # breathing pulse, seeded per-zone so circles don't sync
                seed = int(zone.get('x', 0.0)) * 7 + int(zone.get('y', 0.0)) * 13
                breath = 1.0 + 0.05 * math.sin(self._time * 3.0 + seed)
                fade = timer / FADE_TIME if timer < FADE_TIME else 1.0
                alpha = int(max(0, min(255, 190 * scale * fade)))

                # Occlusion: a wall column in front hides the ring
                if not renderer._col_visible(screen_x, dist):
                    continue

                w_px = max(2.0, 2.0 * radius * unit * scale * breath)
                h_px = max(1.0, w_px * 0.32)
                rx, ry = int(w_px / 2), max(1, int(h_px / 2))
                cx, cy = screen_x, int(floor_y)

                # ── Ground decal: squished elliptical ring (pre-darkness, so the
                # flashlight actually illuminates the salt line; the emissive
                # ring below carries the glow + fade in the dark) ──
                faint = (int(ring_col[0] * 0.7), int(ring_col[1] * 0.7), int(ring_col[2] * 0.7))
                rect = pygame.Rect(0, 0, rx * 2 + 1, ry * 2 + 1)
                rect.center = (cx, cy)
                pygame.draw.ellipse(surface, ring_col, rect, max(1, int(1.5 + unit * 0.4)))
                # inner speckle pass reads as scattered grains when close
                if unit > 0.35:
                    inner = int(0.82 * rx)
                    if inner > 1:
                        inner_rect = pygame.Rect(0, 0, inner * 2 + 1, max(1, int(inner * 0.32 * 2)) + 1)
                        inner_rect.center = (cx, cy)
                        pygame.draw.ellipse(surface, faint, inner_rect, 1)

                # ── Emissive ring glow (drawn after darkness) ──
                renderer._emissive.append(('ring', cx, cy, int(w_px * 0.5), glow_col, alpha))

                # ── Mote / vapor particles, throttled per zone ──
                if _settings_mod.ENABLE_PARTICLES:
                    key = id(zone)
                    last = self._mote_timers.get(key, -1.0)
                    if self._time - last >= MOTES_INTERVAL:
                        self._mote_timers[key] = self._time
                        try:
                            for _ in range(2):
                                off = (random.random() * 2 - 1.0) * w_px * 0.45
                                renderer.physics_particles.emit(
                                    cx + off, cy - 1,
                                    vx=(random.random() - 0.5) * 14.0,
                                    vy=-(8.0 + random.random() * 14.0),
                                    life=0.8, size=1.0, color=mote_col,
                                    gravity_scale=0.0, drag_scale=0.9)
                        except Exception:
                            pass
        except Exception:
            # Zone visuals must never take down the frame
            pass


    def on_zone_appeared(self, renderer, zone):
        """Formation burst: one crackle of consecrated dust / vapor."""
        if not _settings_mod.ENABLE_PARTICLES:
            return
        style = ZONE_STYLE.get(zone.get('type'))
        if style is None:
            return
        try:
            renderer.physics_particles.burst(
                int(renderer.w * 0.5), int(renderer.h * 0.72),
                count=24, speed=(30, 110), life=0.9, size=2.0,
                color=style[2], up_bias=30, gravity_scale=1.2)
        except Exception:
            pass
