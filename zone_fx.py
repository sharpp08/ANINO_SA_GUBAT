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
                proj = self._project(renderer, player, zone.get("x", 0.0), zone.get("y", 0.0))
                if proj is None:
                    continue
                sx, fy, unit, dist = proj
                if not renderer._col_visible(sx, dist):
                    continue
                diameter = max(8.0, min(renderer.w * 0.78,
                    2.0 * float(zone.get("radius", 2.0)) * unit * formation * breath))
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

    def on_zone_appeared(self, renderer, zone):
        if not _settings_mod.ENABLE_PARTICLES:
            return
        style = ZONE_STYLE.get(zone.get("type"))
        if style is None:
            return
        try:
            renderer.physics_particles.burst(
                int(renderer.w * 0.5), int(renderer.h * 0.72),
                count=18 if zone.get("type") == "salt" else 14,
                speed=(24, 82), life=0.72, size=1.6,
                color=style[2], up_bias=24, gravity_scale=0.9)
        except Exception:
            pass
