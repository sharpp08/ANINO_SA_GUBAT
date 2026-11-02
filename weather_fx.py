"""Storm weather for ANINO SA GUBAT: layered rain, ground splashes, lightning and thunder.

Two halves:

* ``StormClock`` and the helpers above it are pure Python.  They decide *when* lightning
  strikes, how bright each flash is over time, where the bolt goes and when the thunder
  arrives.  No pygame is needed, so they are unit-tested headless (tests/test_weather_fx.py).
* ``WeatherFX`` owns the rain particles and does all the drawing.  The renderer calls
  ``update`` once per played frame (never while paused) and the ``draw_*`` methods from
  ``render_frame``.

Light travels faster than sound, so every strike queues its thunder with a delay.  Close
strikes (short delay) are bright, throw a bolt and shake the screen; far ones are a dim
glow in the clouds followed by a long, muffled rumble.
"""
import math
import random

import numpy as np

try:
    import pygame
except ImportError:           # the logic classes still work without it (headless tests)
    pygame = None

NEAR, MID, FAR = 'near', 'mid', 'far'

# Per-kind strike parameters.  ``delay`` is flash->thunder in seconds, ``peak`` the flash
# brightness (0..1), ``bolt`` the bolt height as a fraction of the screen (0 = no bolt,
# just glow in the clouds), ``volume`` the thunder gain and ``shake`` the screen shake.
STRIKE_KINDS = {
    NEAR: dict(weight=0.22, delay=(0.15, 0.75), peak=(0.90, 1.00), strokes=(2, 3),
               bolt=0.78, volume=(0.60, 0.80), shake=3.0),
    MID:  dict(weight=0.43, delay=(1.10, 3.00), peak=(0.45, 0.65), strokes=(2, 3),
               bolt=0.52, volume=(0.38, 0.55), shake=0.0),
    FAR:  dict(weight=0.35, delay=(3.20, 7.00), peak=(0.20, 0.34), strokes=(1, 2),
               bolt=0.0, volume=(0.25, 0.40), shake=0.0),
}

MAX_STROKES = 3          # flashes per strike; kept low so nothing strobes (<= 3 flashes/second)


def _wrap(angle):
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def rain_strength(sunrise_progress):
    """1.0 at night, easing to 0.0 as the sun comes up (same curve the renderer always used)."""
    p = max(0.0, min(1.0, sunrise_progress))
    return 1.0 - max(0.0, min(1.0, (p - 0.45) / 0.55))


def storm_activity(sunrise_progress):
    """1.0 while the storm rages; thunder moves off earlier than the rain stops (0 at 80% dawn)."""
    p = max(0.0, min(1.0, sunrise_progress))
    return 1.0 - max(0.0, min(1.0, (p - 0.45) / 0.35))


# ─── lightning flash envelope ─────────────────────────────────────────────────
def make_strokes(rng, count, peak):
    """[(start_s, amplitude, decay_tau_s), ...]: a bright first stroke, dimmer return strokes."""
    strokes = []
    t = 0.0
    for i in range(max(1, min(MAX_STROKES, count))):
        amp = peak if i == 0 else peak * rng.uniform(0.45, 0.85)
        tau = rng.uniform(0.055, 0.080) if i == 0 else rng.uniform(0.035, 0.060)
        strokes.append((t, amp, tau))
        t += rng.uniform(0.14, 0.22)
    return strokes


def strike_intensity(strokes, t):
    """Flash brightness (0..1) ``t`` seconds after the strike began."""
    if t < 0.0 or not strokes:
        return 0.0
    best = 0.0
    for start, amp, tau in strokes:
        dt = t - start
        if dt < 0.0:
            continue
        v = amp * min(1.0, dt / 0.012) * math.exp(-dt / tau)     # ~12 ms attack, then decay
        if v > best:
            best = v
    # the sky stays faintly lit for a moment after the last crackle
    glow = 0.20 * strokes[0][1] * math.exp(-t / 0.40)
    return max(0.0, min(1.0, max(best, glow)))


def strokes_duration(strokes):
    return max(0.9, max(start + 5.0 * tau for start, _amp, tau in strokes))


# ─── bolt geometry ────────────────────────────────────────────────────────────
def _jag(rng, p0, p1, depth, amp):
    """Midpoint displacement: a jagged line from p0 to p1."""
    pts = [p0, p1]
    for _ in range(depth):
        out = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(dx, dy) or 1.0
            off = rng.uniform(-amp, amp)
            out.append(((a[0] + b[0]) * 0.5 - dy / ln * off, (a[1] + b[1]) * 0.5 + dx / ln * off))
            out.append(b)
        pts = out
        amp *= 0.55
    return pts


def build_bolt(rng, width, height):
    """A forked bolt inside a ``width`` x ``height`` box, from the top edge to the bottom edge.

    Returns ``{'main': [(x, y)...], 'branches': [[(x, y)...]...], 'anchor_x': x of the strike point}``.
    All points are clamped inside the box.
    """
    spread = width * 0.32
    top = (width * 0.5 + rng.uniform(-spread, spread) * 0.4, 0.0)
    bottom = (width * 0.5 + rng.uniform(-spread, spread), float(height - 1))
    main = _jag(rng, top, bottom, 6, height * 0.12)
    branches = []
    for _ in range(rng.randint(2, 4)):
        i = rng.randint(len(main) // 5, (len(main) * 3) // 4)
        sx, sy = main[i]
        ang = rng.uniform(0.35, 1.0) * rng.choice((-1.0, 1.0))
        length = height * rng.uniform(0.12, 0.28)
        end = (sx + math.sin(ang) * length, sy + math.cos(ang) * length)
        branches.append(_jag(rng, (sx, sy), end, 4, length * 0.16))

    def clamp(pts):
        return [(min(width - 1.0, max(0.0, x)), min(height - 1.0, max(0.0, y))) for x, y in pts]

    main = clamp(main)
    return {'main': main, 'branches': [clamp(b) for b in branches], 'anchor_x': main[-1][0]}


# ─── strike scheduling ────────────────────────────────────────────────────────
class Strike:
    """One lightning strike: its flash strokes, bolt and the thunder that follows."""
    __slots__ = ('serial', 'kind', 'azimuth', 'strokes', 'duration', 'age',
                 'bolt_scale', 'bolt_seed', 'thunder_delay', 'thunder_volume')


class StormClock:
    """Schedules strikes and queues thunder; pure logic, driven by ``update(dt, ...)``."""

    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self._serial = 0
        self.reset()

    def reset(self):
        self.strike = None          # the Strike currently flashing (or None)
        self.flash = 0.0            # brightness 0..1 right now
        self.pending = []           # thunder still travelling: dicts with 'left' seconds
        self.timer = self.rng.uniform(6.0, 12.0)
        self.followups = 0

    # -- helpers --
    def _pick_kind(self, storm):
        k = STRIKE_KINDS
        weights = [(NEAR, k[NEAR]['weight'] * storm * storm),
                   (MID, k[MID]['weight']),
                   (FAR, k[FAR]['weight'] + 0.25 * (1.0 - storm))]
        r = self.rng.uniform(0.0, sum(w for _n, w in weights))
        for name, w in weights:
            r -= w
            if r <= 0.0:
                return name
        return FAR

    def begin_strike(self, player_angle, fov_rad, storm=1.0, kind=None):
        rng = self.rng
        kind = kind or self._pick_kind(storm)
        cfg = STRIKE_KINDS[kind]
        peak = rng.uniform(*cfg['peak'])
        st = Strike()
        self._serial += 1
        st.serial = self._serial
        st.kind = kind
        # most strikes happen somewhere in front of the player so the bolt can be seen
        if rng.random() < 0.7:
            st.azimuth = _wrap(player_angle + rng.uniform(-0.55, 0.55) * fov_rad)
        else:
            st.azimuth = rng.uniform(-math.pi, math.pi)
        st.strokes = make_strokes(rng, rng.randint(*cfg['strokes']), peak)
        st.duration = strokes_duration(st.strokes)
        st.age = 0.0
        st.bolt_scale = cfg['bolt']
        st.bolt_seed = rng.randrange(1 << 30)
        st.thunder_delay = rng.uniform(*cfg['delay'])
        st.thunder_volume = rng.uniform(*cfg['volume'])
        self.strike = st
        self.flash = strike_intensity(st.strokes, 0.0)
        self.pending.append({'left': st.thunder_delay, 'kind': kind, 'volume': st.thunder_volume,
                             'azimuth': st.azimuth, 'shake': cfg['shake']})
        return st

    def update(self, dt, sunrise_progress, player_angle, fov_rad):
        """Advance ``dt`` seconds.  Returns thunder events that arrive this frame:
        ``[{'kind', 'volume', 'pan', 'shake'}]``."""
        events = []
        for item in self.pending:
            item['left'] -= dt
        if any(item['left'] <= 0.0 for item in self.pending):
            still = []
            for item in self.pending:
                if item['left'] <= 0.0:
                    pan = 0.75 * math.sin(_wrap(item['azimuth'] - player_angle))
                    events.append({'kind': item['kind'], 'volume': item['volume'],
                                   'pan': pan, 'shake': item['shake']})
                else:
                    still.append(item)
            self.pending = still

        if self.strike is not None:
            self.strike.age += dt
            if self.strike.age >= self.strike.duration:
                self.strike = None
                self.flash = 0.0
            else:
                self.flash = strike_intensity(self.strike.strokes, self.strike.age)

        storm = storm_activity(sunrise_progress)
        if storm <= 0.0:
            self.timer = max(self.timer, 4.0)         # the storm has passed: no new strikes
        else:
            self.timer -= dt
            if self.timer <= 0.0 and self.strike is None:
                self.begin_strike(player_angle, fov_rad, storm)
                if self.followups < 2 and self.rng.random() < 0.30:
                    self.followups += 1
                    gap = self.rng.uniform(2.2, 4.5)
                else:
                    self.followups = 0
                    gap = self.rng.uniform(10.0, 26.0)
                self.timer = gap / max(0.4, storm)
        return events


# ─── drawing ──────────────────────────────────────────────────────────────────
# name, drop count, streak length px (at 360p), width px, fall speed px/s (at 360p)
RAIN_LAYERS = (
    ('far', 110, (4.0, 7.0), 1, (210.0, 270.0), 80),
    ('mid', 80, (8.0, 13.0), 1, (330.0, 430.0), 120),
    ('near', 28, (17.0, 27.0), 2, (540.0, 680.0), 140),
)
LEN_BINS = 3
SLANT_BINS = 5
SLANT0, SLANT_STEP = 0.08, 0.10      # streak slant (dx per dy) of bin i = SLANT0 + i * SLANT_STEP
TIER_ALPHA = (1.0, 0.70, 0.45)       # sprite opacity as the rain eases off at dawn
SPLASH_FRAMES = 4
MAX_SPLASHES = 40


def _stroke(surf, pts, color, width):
    """Polyline with round joints (plain thick lines leave notches at sharp bends)."""
    pts = [(int(round(x)), int(round(y))) for x, y in pts]
    for a, b in zip(pts, pts[1:]):
        pygame.draw.line(surf, color, a, b, width)
    if width > 2:
        r = width // 2
        for p in pts:
            pygame.draw.circle(surf, color, p, r)


class WeatherFX:
    """Rain, ground splashes, mist, lightning bolt/glow and screen flash."""

    def __init__(self, w, h, fov_rad, seed=None, rain=True, lightning=True,
                 rain_density=1.0, flash_strength=1.0):
        self.w, self.h = int(w), int(h)
        self.k = max(0.5, self.h / 360.0)             # resolution scale (tuned at 640x360)
        self.fov_rad = float(fov_rad)
        self.rain_on = bool(rain)
        self.lightning_on = bool(lightning)
        self.flash_strength = max(0.0, float(flash_strength))
        self.density = max(0.1, float(rain_density))
        self.storm = StormClock(seed)
        self._np_rng = np.random.default_rng(seed)
        self._rng = random.Random(seed)
        self.strength = 1.0                           # rain intensity (fades towards dawn)
        self.slant = 0.25                             # current wind slant of the streaks
        self.horizon_y = self.h // 2
        self._last_yaw = None
        self._last_pitch = None
        self.splashes = []                            # [x_px, floor_frac, age, life, size_bin]
        self._splash_acc = 0.0
        self._sprites = {}
        self._splash_sprites = {}
        self._glow = None
        self._haze = None
        self._bolt = None
        self._bolt_serial = -1
        self._init_rain()

    # ── rain particles ────────────────────────────────────────────────────────
    def _init_rain(self):
        rng = self._np_rng
        layers, lbins, speeds = [], [], []
        for idx, (_name, count, _ln, _wd, (s0, s1), _a) in enumerate(RAIN_LAYERS):
            n = max(1, int(round(count * self.density)))
            layers.append(np.full(n, idx, dtype=np.int64))
            lbins.append(rng.integers(0, LEN_BINS, n))
            speeds.append(rng.uniform(s0, s1, n) * self.k)
        layer = np.concatenate(layers)
        lbin = np.concatenate(lbins)
        speed = np.concatenate(speeds)
        order = rng.permutation(len(layer))           # thinning the rain then thins every layer evenly
        self._layer = layer[order]
        self._lbin = lbin[order]
        self._speed = speed[order]
        n = len(self._layer)
        self._x = rng.uniform(-30.0, self.w + 30.0, n)
        self._y = rng.uniform(-30.0 * self.k, self.h + 30.0 * self.k, n)

    def _step_rain(self, dt, wind, shift_x, shift_y):
        k = self.k
        target = 0.04 + 0.6 * max(0.0, min(1.0, wind))
        self.slant += (target - self.slant) * min(1.0, dt * 1.2)
        x, y = self._x, self._y
        x += -self.slant * self._speed * dt - shift_x
        y += self._speed * dt + shift_y
        margin = 40.0 * k
        # drops that hit the bottom restart above the screen at a fresh x
        over = y > self.h + margin
        n_over = int(over.sum())
        if n_over:
            span = self.w + 60.0 + self.slant * (self.h + 2.0 * margin)
            x[over] = self._np_rng.uniform(-30.0, -30.0 + span, n_over)
            y[over] = self._np_rng.uniform(-2.0 * margin, -0.5 * margin, n_over)
        # looking down moves drops off the top: wrap them to the bottom
        y[y < -2.5 * margin] += self.h + 4.0 * margin
        # sideways wrap (turning the camera or wind drift)
        span = self.w + 60.0 + self.slant * (self.h + 2.0 * margin)
        x[:] = (x + 30.0) % span - 30.0

    def _spawn_splashes(self, dt):
        if self.h - self.horizon_y < 12:
            return
        self._splash_acc = min(2.0, self._splash_acc + 42.0 * self.strength * self.density * dt)
        while self._splash_acc >= 1.0 and len(self.splashes) < MAX_SPLASHES:
            self._splash_acc -= 1.0
            f = 0.06 + 0.94 * (self._rng.random() ** 1.6)        # more small splashes far away
            size = 0 if f < 0.25 else 1 if f < 0.5 else 2 if f < 0.75 else 3
            self.splashes.append([self._rng.uniform(0.0, self.w), f, 0.0,
                                  self._rng.uniform(0.30, 0.45), size])

    # ── per-frame update ──────────────────────────────────────────────────────
    def update(self, dt, sunrise_progress, yaw=0.0, pitch=0.0, wind=0.3):
        """Advance rain and lightning.  Returns thunder events for the caller to play."""
        dt = max(0.0, min(float(dt), 0.1))
        self.strength = rain_strength(sunrise_progress)

        dyaw = dpitch = 0.0
        if self._last_yaw is not None:
            dyaw = _wrap(yaw - self._last_yaw)
            dpitch = pitch - self._last_pitch
            if abs(dyaw) > 0.6 or abs(dpitch) > 0.6:      # teleport / new chapter: no rain smear
                dyaw = dpitch = 0.0
        self._last_yaw, self._last_pitch = yaw, pitch

        if self.rain_on and self.strength > 0.01:
            # rain is attached to the world, so it slides across the screen as the camera turns
            self._step_rain(dt, wind, dyaw * self.w / self.fov_rad, dpitch * self.h)
            for s in self.splashes:
                s[2] += dt
            self.splashes = [s for s in self.splashes if s[2] < s[3]]
            self._spawn_splashes(dt)
        elif self.splashes:
            self.splashes = []

        if self.lightning_on:
            return self.storm.update(dt, sunrise_progress, yaw, self.fov_rad)
        return []

    # ── sprites (built lazily, cached) ────────────────────────────────────────
    @staticmethod
    def _new_surface(size):
        surf = pygame.Surface(size, pygame.SRCALPHA)
        if pygame.display.get_surface() is not None:
            try:
                surf = surf.convert_alpha()
            except pygame.error:
                pass
        return surf

    def _rain_sprite(self, layer, lbin, sbin, tier, lit):
        key = (layer, lbin, sbin, tier, lit)
        got = self._sprites.get(key)
        if got is not None:
            return got
        _name, _count, (l0, l1), width, _spd, base_alpha = RAIN_LAYERS[layer]
        length = max(3, int(round((l0 + (l1 - l0) * lbin / (LEN_BINS - 1)) * self.k)))
        width = max(1, int(round(width * (self.k if width > 1 else 1.0))))
        dx = -(SLANT0 + SLANT_STEP * sbin) * length               # streak leans left, like the wind
        sw = int(abs(dx)) + width + 3
        sh = length + width + 3
        surf = self._new_surface((sw, sh))
        tx, ty = sw - 2.0, 1.0                                    # tail (upper right)
        hx, hy = tx + dx, ty + length                             # head (lower left)
        color = (206, 222, 244) if lit else (150, 176, 204)
        gain = TIER_ALPHA[tier] * (1.35 if lit else 1.0)
        segs = 4
        for i in range(segs):                                     # dim tail -> bright head
            t0, t1 = i / segs, (i + 1) / segs
            a = int(min(255, base_alpha * gain * (0.12 + 0.88 * t1 ** 1.5)))
            pygame.draw.line(surf, color + (a,),
                             (int(round(tx + (hx - tx) * t0)), int(round(ty + (hy - ty) * t0))),
                             (int(round(tx + (hx - tx) * t1)), int(round(ty + (hy - ty) * t1))),
                             width)
        got = (surf, int(tx), int(ty))
        self._sprites[key] = got
        return got

    def _splash_sprite(self, size, frame, lit):
        key = (size, frame, lit)
        got = self._splash_sprites.get(key)
        if got is not None:
            return got
        k = self.k
        grow = 0.45 + 0.55 * (frame + 1) / SPLASH_FRAMES
        rx = max(1.0, (1.8 + 2.4 * size) * k * grow)
        ry = max(1.0, rx * 0.36)
        sw = int(2 * rx) + 5
        sh = int(2 * ry) + 9
        surf = self._new_surface((sw, sh))
        cx, cy = sw // 2, sh - int(ry) - 2
        alpha = int(min(255, 150 * (1.0 - 0.7 * frame / (SPLASH_FRAMES - 1)) * (1.3 if lit else 1.0)))
        color = ((205, 222, 244) if lit else (175, 198, 220)) + (alpha,)
        pygame.draw.ellipse(surf, color, pygame.Rect(int(cx - rx), int(cy - ry),
                                                     int(2 * rx), max(2, int(2 * ry))), 1)
        if frame < 2:                                             # a few droplets thrown up
            for ox in (-0.55, 0.0, 0.6):
                px = int(cx + ox * rx * 0.8)
                py = int(cy - ry - (2 + frame * 1.5) * k)
                if 0 <= px < sw and 0 <= py < sh:
                    surf.set_at((px, py), color)
        got = (surf, cx, cy)
        self._splash_sprites[key] = got
        return got

    def _get_glow(self):
        if self._glow is None:
            gw, gh = int(self.w * 0.95), int(self.h * 0.62)
            xx = (np.arange(gw) - gw / 2.0) / (gw / 2.0)
            yy = (np.arange(gh) - gh / 2.0) / (gh / 2.0)
            alpha = 170.0 * np.exp(-(xx[:, None] ** 2 * 1.4 + yy[None, :] ** 2 * 2.2))
            surf = self._new_surface((gw, gh))
            surf.fill((150, 175, 255, 0))
            arr = pygame.surfarray.pixels_alpha(surf)
            arr[:, :] = alpha.astype(np.uint8)
            del arr
            self._glow = surf
        return self._glow

    def _get_haze(self):
        if self._haze is None:
            bh = max(8, int(self.h * 0.34))
            ys = np.arange(bh)
            prof = np.exp(-(((ys - bh * 0.5) / (bh * 0.2)) ** 2)) * 30.0
            surf = self._new_surface((self.w, bh))
            surf.fill((120, 138, 160, 0))
            arr = pygame.surfarray.pixels_alpha(surf)
            arr[:, :] = np.tile(prof.astype(np.uint8), (self.w, 1))
            del arr
            self._haze = surf
        return self._haze

    def _ensure_bolt(self, st):
        if self._bolt_serial == st.serial:
            return
        self._bolt_serial = st.serial
        bh = max(16, int(self.h * st.bolt_scale))
        bw = max(32, int(self.w * 0.5 * (1.0 if st.kind == NEAR else 0.6)))
        geo = build_bolt(random.Random(st.bolt_seed), bw, bh)
        surf = self._new_surface((bw, bh))
        k = self.k
        thick = 1.0 if st.kind == NEAR else 0.6
        for pts, scale in [(geo['main'], 1.0)] + [(b, 0.55) for b in geo['branches']]:
            _stroke(surf, pts, (120, 150, 255, 40), max(3, int(round(7 * k * scale * thick))))
        for pts, scale in [(geo['main'], 1.0)] + [(b, 0.55) for b in geo['branches']]:
            _stroke(surf, pts, (175, 198, 255, 120), max(2, int(round(3 * k * scale * thick))))
        for pts, scale in [(geo['main'], 1.0)] + [(b, 0.55) for b in geo['branches']]:
            _stroke(surf, pts, (248, 250, 255, 255), max(1, int(round(1.4 * k * scale * thick))))
        self._bolt = (surf, int(geo['anchor_x']), bh)

    # ── drawing ───────────────────────────────────────────────────────────────
    def draw_sky(self, surface, yaw, horizon_y):
        """Cloud glow and the bolt itself.  Call after the sky, before the floor and walls so
        trees and terrain cut across the bottom of the bolt."""
        self.horizon_y = horizon_y
        st = self.storm.strike
        if not self.lightning_on or st is None or horizon_y <= 0 or self.flash_strength <= 0.0:
            return
        inten = self.storm.flash * min(1.0, self.flash_strength)
        if inten < 0.02:
            return
        diff = _wrap(st.azimuth - yaw)
        if abs(diff) > self.fov_rad * 0.5 + 0.9:
            return
        sx = int(self.w // 2 + diff / self.fov_rad * self.w)
        glow = self._get_glow()
        glow.set_alpha(int(min(255, 255 * inten)))
        surface.blit(glow, (sx - glow.get_width() // 2,
                            horizon_y - glow.get_height() + int(0.12 * self.h)))
        if st.bolt_scale > 0.0 and abs(diff) < self.fov_rad * 0.5 + 0.3:
            self._ensure_bolt(st)
            surf, anchor_x, bh = self._bolt
            surf.set_alpha(int(min(255, 330 * inten)))
            surface.blit(surf, (sx - anchor_x, horizon_y - bh + 2))

    def draw_rain(self, surface, horizon_y, occlude=None):
        """Mist, falling streaks and ground splashes.  ``occlude(col, dist)`` -> True when a
        ground point at that distance is visible (not hidden behind a wall)."""
        self.horizon_y = horizon_y
        if not self.rain_on or self.strength <= 0.01:
            return
        st = self.strength
        lit = self.lightning_on and self.storm.flash > 0.12
        tier = 0 if st > 0.66 else 1 if st > 0.33 else 2

        haze = self._get_haze()
        haze.set_alpha(int(255 * st))
        surface.blit(haze, (0, horizon_y - haze.get_height() // 2))

        n = max(1, int(len(self._x) * st ** 0.7))
        sbin = max(0, min(SLANT_BINS - 1, int(round((self.slant - SLANT0) / SLANT_STEP))))
        seq = []
        sprite = self._rain_sprite
        for x, y, ly, lb in zip(self._x[:n].tolist(), self._y[:n].tolist(),
                                self._layer[:n].tolist(), self._lbin[:n].tolist()):
            spr, ax, ay = sprite(ly, lb, sbin, tier, lit)
            seq.append((spr, (int(x) - ax, int(y) - ay)))
        surface.blits(seq, False)

        floor_h = self.h - horizon_y
        if floor_h > 12 and self.splashes:
            seq = []
            for u, f, age, life, size in self.splashes:
                row = int(horizon_y + f * floor_h)
                col = int(u)
                if occlude is not None and not occlude(col, self.h / (2.0 * max(1, row - horizon_y))):
                    continue
                frame = min(SPLASH_FRAMES - 1, int(age / life * SPLASH_FRAMES))
                spr, cx, cy = self._splash_sprite(size, frame, lit)
                seq.append((spr, (col - cx, row - cy)))
            if seq:
                surface.blits(seq, False)

    def draw_flash(self, surface):
        """Cold white-blue wash over the whole frame while lightning flashes."""
        if not self.lightning_on or self.flash_strength <= 0.0:
            return
        add = int(150 * self.storm.flash * self.flash_strength)
        if add < 3:
            return
        add = min(255, add)
        surface.fill((int(add * 0.82), int(add * 0.90), add), special_flags=pygame.BLEND_RGB_ADD)
