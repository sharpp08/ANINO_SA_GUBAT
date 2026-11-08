"""Cached perspective ground decals for salt and garlic protective zones."""
import math
import random
import pygame
import settings as _settings_mod

ZONE_STYLE = {
    "salt": ((218, 231, 242), (86, 111, 145), (198, 222, 246)),
    "garlic": ((190, 174, 137), (111, 101, 70), (174, 185, 143)),
}
FORMATION_TIME = 0.48
FADE_TIME = 0.5
MOTES_INTERVAL = 0.38
_DECAL_CACHE_LIMIT = 48
_GARLIC_SCALE_CACHE = {}


def ease_out_quad(t):
    t = min(1.0, max(0.0, float(t)))
    return 1.0 - (1.0 - t) ** 2


def ease_out_cubic(t):
    t = min(1.0, max(0.0, float(t)))
    return 1.0 - (1.0 - t) ** 3


def ease_out_back(t):
    t = min(1.0, max(0.0, float(t)))
    c1, c3 = 1.70158, 2.70158
    return 1.0 + c3 * (t - 1.0) ** 3 + c1 * (t - 1.0) ** 2


class ZoneFX:
    """Render active wards; the base visuals never depend on particle settings."""

    def __init__(self):
        self._mote_timers = {}
        self._time = 0.0
        self._decal_cache = {}
        self._salt_grain_samples = None

    @staticmethod
    def _project(renderer, player, wx, wy):
        dx, dy = wx - player.x, wy - player.y
        dist = max(0.05, math.hypot(dx, dy))
        rel = math.atan2(dy, dx) - player.angle
        rel = (rel + math.pi) % math.tau - math.pi
        if abs(rel) > renderer.half_fov + 0.5 or dist > _settings_mod.MAX_DEPTH:
            return None
        sx = int((rel / renderer.fov_rad + 0.5) * renderer.w)
        unit = renderer._unit_h(dist)
        horizon = max(0, renderer.h // 2 + int(player.pitch * renderer.h))
        if dist < 1.25:
            unit = min(unit, max(12.0, renderer.w * 0.17))
            floor_y = min(horizon + unit * 0.5, renderer.h * 0.90)
        else:
            floor_y = horizon + unit * 0.5
        return sx, floor_y, unit, dist

    @staticmethod
    def _project_ground(renderer, player, wx, wy):
        """Project a ground-plane world point using camera-forward depth."""
        dx, dy = float(wx) - player.x, float(wy) - player.y
        dist = math.hypot(dx, dy)
        if dist < 1e-5 or dist > _settings_mod.MAX_DEPTH:
            return None
        forward = dx * math.cos(player.angle) + dy * math.sin(player.angle)
        side = -dx * math.sin(player.angle) + dy * math.cos(player.angle)
        if forward <= 0.08:
            return None
        focal = renderer.w / max(1e-6, 2.0 * math.tan(renderer.fov_rad * 0.5))
        sx = renderer.w * 0.5 + side * focal / forward
        if sx < -renderer.w * 3 or sx > renderer.w * 4:
            return None
        unit = renderer._unit_h(forward)
        horizon = max(0, renderer.h // 2 + int(player.pitch * renderer.h))
        floor_y = horizon + unit * 0.5
        if floor_y > renderer.h * 4:
            return None
        return sx, floor_y, unit, dist

    def update(self, dt):
        self._time += max(0.0, min(0.25, float(dt)))

    def _decal(self, ztype, rx):
        rx = max(4, min(256, int(round(int(rx) / 4.0) * 4)))
        key = (ztype, rx)
        if key in self._decal_cache:
            return self._decal_cache[key]
        ry = max(2, int(rx * 0.32))
        surf = pygame.Surface((rx * 2 + 1, ry * 2 + 1), pygame.SRCALPHA)
        rng = random.Random((rx * 7919) ^ (0x51A7 if ztype == "salt" else 0x6A21))
        base = ZONE_STYLE[ztype][0]
        pygame.draw.ellipse(surf, (*base, 90), (1, 1, rx * 2 - 1, max(2, ry * 2 - 1)), 1)
        count = max(48, min(220, int(rx * 1.45)))
        for i in range(count):
            a = math.tau * i / count
            jitter = rng.uniform(-1.25, 1.25)
            px = int(rx + math.cos(a) * (rx - 1 + jitter))
            py = int(ry + math.sin(a) * (ry - 1 + jitter * 0.32))
            if ztype == "salt":
                shade = rng.choice((0.66, 0.82, 1.0, 1.08))
                col = tuple(max(0, min(255, int(c * shade))) for c in base)
                pygame.draw.circle(surf, (*col, rng.randint(150, 238)),
                                   (px, py), rng.choice((1, 1, 1, 2)))
                if i % 7 == 0:
                    pygame.draw.line(surf, (238, 244, 250, 190),
                                     (px - 1, py), (px + 1, py - 1), 1)
            elif i % 3 == 0:
                pygame.draw.circle(surf, (150, 139, 105, 150), (px, py), 1)
        if ztype == "salt":
            for _ in range(max(20, min(90, rx // 2))):
                a = rng.random() * math.tau
                r = rng.uniform(0.72, 1.06)
                px, py = int(rx + math.cos(a) * rx * r), int(ry + math.sin(a) * ry * r)
                if 1 <= px < rx * 2 and 1 <= py < ry * 2:
                    pygame.draw.circle(surf, (205, 220, 235, rng.randint(90, 190)),
                                       (px, py), rng.choice((1, 1, 2)))
        else:
            for i in range(12):
                a = math.tau * i / 12.0
                px, py = int(rx + math.cos(a) * rx * 0.91), int(ry + math.sin(a) * ry * 0.91)
                pygame.draw.line(surf, (144, 151, 112, 155), (px - 1, py), (px + 1, py - 1), 1)
        if len(self._decal_cache) >= _DECAL_CACHE_LIMIT:
            self._decal_cache.pop(next(iter(self._decal_cache)))
        self._decal_cache[key] = surf
        return surf


    def _salt_samples(self):
        """Cached deterministic grain offsets around a circular world-space band."""
        if self._salt_grain_samples is None:
            rng = random.Random(0x5A17C1)
            samples = []
            for i in range(96):
                angle = math.tau * (i + rng.uniform(-0.32, 0.32)) / 96.0
                radial = rng.uniform(-0.035, 0.035)
                size = rng.choice((1, 1, 1, 2))
                shade = rng.choice((0.76, 0.88, 1.0, 1.06))
                samples.append((angle, radial, size, shade))
            self._salt_grain_samples = tuple(samples)
        return self._salt_grain_samples

    def _draw_salt_ground(self, renderer, player, zone, radius, alpha, phase):
        """Draw the salt band by projecting its actual world-space circumference."""
        cx, cy = float(zone.get("x", 0.0)), float(zone.get("y", 0.0))
        salt = (218, 231, 242)
        dark = (30, 34, 39)
        segments = []
        count = 96
        points = []
        for i in range(count + 1):
            angle = math.tau * i / count
            points.append(self._project_ground(renderer, player,
                cx + math.cos(angle) * radius,
                cy + math.sin(angle) * radius))
        fade_col = tuple(max(0, min(255, int(c * alpha / 255.0))) for c in salt)
        for i in range(count):
            a, b = points[i], points[i + 1]
            if a is None or b is None:
                continue
            x1, y1, u1, d1 = a
            x2, y2, u2, d2 = b
            if abs(x2 - x1) > renderer.w * 0.5:
                continue
            mx = int((x1 + x2) * 0.5)
            md = (d1 + d2) * 0.5
            if 0 <= mx < renderer.w and not renderer._col_visible(mx, md):
                continue
            width = max(1, min(4, int(((u1 + u2) * 0.5) * 0.018)))
            pygame.draw.line(renderer.surface, dark,
                (int(x1), int(y1 + 1)), (int(x2), int(y2 + 1)), width + 1)
            pygame.draw.line(renderer.surface, fade_col,
                (int(x1), int(y1)), (int(x2), int(y2)), width)
            mid_angle = math.tau * (i + 0.5) / count
            delta = abs((mid_angle - phase + math.pi) % math.tau - math.pi)
            if delta < 0.16:
                glint = (int(190 * alpha / 255.0),
                         int(205 * alpha / 255.0),
                         int(225 * alpha / 255.0))
                pygame.draw.line(renderer.surface, glint,
                    (int(x1), int(y1)), (int(x2), int(y2)), max(1, width))
            if -2 <= mx <= renderer.w + 2:
                segments.append((int(x1), int(y1), int(x2), int(y2)))
        grain_spread = min(1.0, max(0.1, radius / 0.25))
        for angle, radial, size, shade in self._salt_samples():
            rr = max(0.02, radius + radial * grain_spread)
            p = self._project_ground(renderer, player,
                cx + math.cos(angle) * rr,
                cy + math.sin(angle) * rr)
            if p is None:
                continue
            sx, sy, unit, dist = p
            ix = int(sx)
            if not 0 <= ix < renderer.w or not renderer._col_visible(ix, dist):
                continue
            grain_size = max(1, min(2, int(size * max(0.8, unit / 100.0))))
            col = tuple(max(0, min(255, int(c * shade * alpha / 255.0)))
                        for c in salt)
            pygame.draw.circle(renderer.surface, (22, 25, 29),
                               (ix, int(sy + 1)), grain_size)
            pygame.draw.circle(renderer.surface, col, (ix, int(sy)), grain_size)
        return segments

    @staticmethod
    def _scaled_garlic(img, size):
        size = max(8, min(36, int(size)))
        key = (id(img), size)
        result = _GARLIC_SCALE_CACHE.get(key)
        if result is None:
            if len(_GARLIC_SCALE_CACHE) >= 48:
                _GARLIC_SCALE_CACHE.clear()
            result = pygame.transform.smoothscale(img, (size, size))
            _GARLIC_SCALE_CACHE[key] = result
        return result

    def draw(self, renderer, player, zones):
        if not zones:
            self._mote_timers.clear()
            return
        live = {id(z) for z in zones}
        for stale in tuple(self._mote_timers):
            if stale not in live:
                self._mote_timers.pop(stale, None)
        for zone in zones:
            try:
                ztype = zone.get("type")
                if ztype not in ZONE_STYLE:
                    continue
                timer = max(0.0, float(zone.get("timer", 0.0)))
                if timer <= 0.0:
                    continue
                lifetime = max(0.01, float(zone.get("max_timer", 8.0 if ztype == "salt" else 6.0)))
                age = max(0.0, lifetime - timer)
                formation = max(0.035, ease_out_quad(age / FORMATION_TIME))
                fade = min(1.0, timer / FADE_TIME)
                seed = float(zone.get("x", 0.0)) * 12.9898 + float(zone.get("y", 0.0)) * 78.233
                phase = (math.sin(seed) * 43758.5453) % math.tau
                breath = 1.0 + 0.018 * math.sin(self._time * 2.4 + phase)
                shimmer = 0.96 + 0.04 * math.sin(self._time * 1.7 + phase * 1.3)
                alpha = int(max(0, min(255, 210 * formation * fade * shimmer)))
                if alpha <= 0:
                    continue
                if ztype == "salt":
                    world_radius = float(zone.get("radius", 2.0)) * formation
                    salt_alpha = int(alpha * (0.92 + 0.08 * math.sin(self._time * 2.1 + phase)))
                    segments = self._draw_salt_ground(
                        renderer, player, zone, world_radius, salt_alpha,
                        (self._time * 2.7 + phase) % math.tau)
                    if segments:
                        renderer._emissive.append(
                            ("salt_ground", segments, ZONE_STYLE["salt"][1], salt_alpha))
                    continue

                proj = self._project(renderer, player, zone.get("x", 0.0), zone.get("y", 0.0))
                if proj is None:
                    continue
                sx, fy, unit, dist = proj
                if not renderer._col_visible(sx, dist):
                    continue
                diameter = max(8.0, min(renderer.w * 0.78,
                    2.0 * float(zone.get("radius", 2.5)) * unit * formation * breath))
                rx = max(4, min(256, int(diameter * 0.5)))
                cx, cy = int(sx), int(fy)
                decal = self._decal(ztype, rx)
                decal.set_alpha(alpha)
                renderer.surface.blit(decal, (cx - decal.get_width() // 2,
                                               cy - decal.get_height() // 2))
                decal.set_alpha(None)
                if ztype == "garlic":
                    bulb = renderer.pickup_sprites.get("garlic")
                    if bulb is not None:
                        img = self._scaled_garlic(bulb, max(8, min(36, unit * 0.24)))
                        sw = max(7, int(img.get_width() * 0.9))
                        pygame.draw.ellipse(renderer.surface, (12, 10, 7),
                                            (cx - sw // 2, cy - 2, sw, max(3, sw // 3)))
                        bob = math.sin(self._time * 1.8 + phase) * 1.1
                        renderer.surface.blit(img, (cx - img.get_width() // 2,
                            int(cy - img.get_height() * 0.72 + bob)))
                renderer._emissive.append(("ring", cx, cy, rx, ZONE_STYLE[ztype][1], alpha))
                if _settings_mod.ENABLE_PARTICLES:
                    key = id(zone)
                    last = self._mote_timers.get(key, -MOTES_INTERVAL)
                    if self._time - last >= MOTES_INTERVAL:
                        self._mote_timers[key] = self._time
                        try:
                            for _ in range(2):
                                off = (random.random() * 2.0 - 1.0) * diameter * 0.42
                                renderer.physics_particles.emit(
                                    cx + off, cy - 1, vx=(random.random() - 0.5) * 5.5,
                                    vy=-(5.0 + random.random() * 8.0),
                                    life=0.85 + random.random() * 0.35,
                                    size=0.8 + random.random() * 0.5,
                                    color=ZONE_STYLE[ztype][2], gravity_scale=0.0, drag_scale=0.96)
                        except Exception:
                            pass
            except (TypeError, ValueError, AttributeError, pygame.error):
                continue

    def on_zone_appeared(self, renderer, zone, player=None):
        if not _settings_mod.ENABLE_PARTICLES:
            return
        style = ZONE_STYLE.get(zone.get("type"))
        if style is None:
            return
        try:
            if zone.get("type") == "salt":
                if player is not None:
                    radius = float(zone.get("radius", 2.0))
                    for i in range(12):
                        angle = math.tau * i / 12.0
                        p = self._project_ground(renderer, player,
                            float(zone["x"]) + math.cos(angle) * radius,
                            float(zone["y"]) + math.sin(angle) * radius)
                        if p is not None and 0 <= int(p[0]) < renderer.w:
                            renderer.physics_particles.emit(
                                int(p[0]), int(p[1]), vx=0.0,
                                vy=-(8.0 + random.random() * 7.0),
                                life=0.45, size=1.0, color=style[2],
                                gravity_scale=0.0, drag_scale=0.96)
                return
            renderer.physics_particles.burst(
                int(renderer.w * 0.5), int(renderer.h * 0.72),
                count=14, speed=(24, 82), life=0.72, size=1.6,
                color=style[2], up_bias=24, gravity_scale=0.9)
        except Exception:
            pass
