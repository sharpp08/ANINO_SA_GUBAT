"""
ANINO SA GUBAT: Intro Cinematic  (INTENSE EDITION)

75 seconds, 6 scenes. Everything is drawn procedurally with pygame + numpy.
Rendering is fully deterministic (no random calls while drawing), so
render_intro.py produces the exact same video on every run.

Scene timeline (seconds)
  1 WARNING    0-10   heartbeat red vignette, typewriter warning, embers
  2 FOREST    10-24   moonlit forest: 4 parallax layers, fog, fireflies
  3 AWAKENING 24-38   glowing eyes open one by one, heartbeat + shake, surge
  4 TRAVELER  38-52   flickering flashlight, stalking figure, blackout
  5 PAGES     52-64   tumbling golden Bible pages in holy light shafts
  6 TITLE     64-75   title slam: flash, shake, shockwave, sparks, RGB split
"""
import math
import random

import numpy as np
import pygame

from settings import INTERNAL_WIDTH, INTERNAL_HEIGHT, GOLD, WHITE, BLACK, HEALTH_RED
from lore import (
    TITLE_FILIPINO, TITLE_ENGLISH, SUBTITLE_FIL, BUILD_STAMP,
    WARNING_FILIPINO, WARNING_ENGLISH,
    SCENE2_FIL, SCENE2_ENG, SCENE2_CAPTION, SCENE3_CAPTION,
    SCENE4_CAPTION, SCENE5_FIL, SCENE5_ENG,
    CLOSING_FILIPINO, CLOSING_ENGLISH, PRESS_SPACE
)
from audio_synth import audio_mgr


# ─── tiny deterministic helpers ──────────────────────────────────────────────
def _hash(x):
    """Deterministic pseudo-random in [0, 1) from a float."""
    return (math.sin(x * 12.9898 + 78.233) * 43758.5453) % 1.0


def _clamp01(v):
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def _smooth(v):
    v = _clamp01(v)
    return v * v * (3.0 - 2.0 * v)


def _fade(t, a, b):
    """0 before a, 1 after b, smooth in between."""
    return _smooth((t - a) / (b - a))


def _bump(x, center, width):
    return math.exp(-((x - center) / width) ** 2)


def _heartbeat(t, bpm):
    """Lub-dub pulse in [0, 1]."""
    ph = (t * bpm / 60.0) % 1.0
    return max(_bump(ph, 0.06, 0.045), 0.65 * _bump(ph, 0.30, 0.05))


def _ir(*vals):
    return tuple(int(v) for v in vals)


class Cinematic:
    SCENES = (10.0, 24.0, 38.0, 52.0, 64.0)   # scene boundaries (seconds)

    def __init__(self, surf):
        self.surface = surf
        self.w = INTERNAL_WIDTH
        self.h = INTERNAL_HEIGHT
        self.duration = 75.0
        self.time = 0.0
        self.skipped = False
        self.finished = False
        self.show_skip = True       # set False when rendering to video
        self.cues = set()
        self.eye_cues = set()
        self._text_cache = {}
        self._glow_cache = {}
        self._init_fonts()
        self._build_assets()

    # ─── setup ────────────────────────────────────────────────────────────
    def _init_fonts(self):
        try:
            pygame.font.init()
            self.font_tiny = pygame.font.SysFont('consolas', 12)
            self.font_sm = pygame.font.SysFont('consolas', 16)
            self.font_md = pygame.font.SysFont('consolas', 22, bold=True)
            self.font_lg = pygame.font.SysFont('consolas', 34, bold=True)
            self.font_xl = pygame.font.SysFont('consolas', 58, bold=True)
        except Exception:
            self.font_tiny = pygame.font.Font(None, 14)
            self.font_sm = pygame.font.Font(None, 18)
            self.font_md = pygame.font.Font(None, 24)
            self.font_lg = pygame.font.Font(None, 36)
            self.font_xl = pygame.font.Font(None, 66)

    def _build_assets(self):
        w, h = self.w, self.h
        rng = random.Random(1337)

        # sky gradient
        top = np.array((3, 5, 14), dtype=np.float32)
        bot = np.array((28, 40, 60), dtype=np.float32)
        k = np.clip(np.arange(h) / (h * 0.78), 0.0, 1.0) ** 1.4
        col = top[None, :] * (1 - k[:, None]) + bot[None, :] * k[:, None]      # (h, 3)
        arr = np.repeat(col[None, :, :], w, axis=0).astype(np.uint8)           # (w, h, 3)
        self.sky = pygame.surfarray.make_surface(arr)

        self.stars = [(rng.uniform(0, w - 1), rng.uniform(30, 200),
                       rng.uniform(0, 6.28), rng.random() < 0.15) for _ in range(150)]

        # moon
        moon = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(moon, (232, 238, 252), (40, 40), 30)
        pygame.draw.circle(moon, (190, 202, 225), (32, 33), 8)
        pygame.draw.circle(moon, (200, 210, 235), (50, 46), 6)
        pygame.draw.circle(moon, (208, 216, 238), (36, 52), 4)
        self.moon = moon

        # fog sprites
        self.fog_light = self._make_fog(300, 110, (125, 140, 165), 58)
        self.fog_dark = self._make_fog(280, 70, (16, 22, 38), 120)
        self.fog_red = self._make_fog(300, 120, (150, 30, 45), 70)
        self.fog_gold = self._make_fog(300, 110, (170, 130, 60), 46)

        # parallax forest layers (period == screen width so they tile)
        specs = [((18, 28, 48), 14, 150, 215, ('pine', 'pine', 'bamboo'), 11),
                 ((12, 20, 38), 11, 190, 260, ('pine', 'balete', 'dead'), 22),
                 ((7, 12, 24), 8, 240, 320, ('balete', 'dead', 'pine'), 33),
                 ((2, 4, 9), 5, 300, 390, ('dead', 'balete'), 44)]
        self.layers = [self._build_layer(*sp) for sp in specs]
        self.layer_speed = (5.0, 11.0, 20.0, 34.0)

        # fireflies
        self.fireflies = [(rng.uniform(40, w - 40), rng.uniform(190, 330),
                           rng.uniform(10, 40), rng.uniform(6, 18),
                           rng.uniform(0.2, 0.7), rng.uniform(0.3, 0.9),
                           rng.uniform(0, 6.28)) for _ in range(26)]

        # embers (scene 1, 5, 6)
        self.embers = [(rng.uniform(0, w), rng.uniform(0, h), rng.uniform(10, 38),
                        rng.uniform(0, 6.28), rng.choice((1, 1, 2))) for _ in range(70)]

        # eyes: (x, y, appear_time_in_scene, colour, size)
        red, amber = (255, 40, 30), (255, 150, 30)
        self.eyes = [
            (70, 175, 0.8, red, 1.0), (190, 140, 2.0, amber, 0.8),
            (330, 205, 3.2, red, 1.2), (470, 155, 4.2, red, 0.9),
            (560, 200, 5.2, amber, 1.1), (130, 230, 6.2, red, 1.3),
            (260, 120, 7.2, amber, 0.7), (410, 240, 8.0, red, 1.4),
            (520, 120, 8.8, red, 0.8), (610, 160, 9.6, amber, 1.0),
            (40, 120, 10.4, red, 0.9), (300, 170, 11.2, red, 1.6),
        ]
        self.eye_abs = [24.0 + e[2] for e in self.eyes]

        # scene 4 assets
        self._build_beam()
        self._build_world4()
        self._build_figure4()
        self.motes = [(rng.uniform(0, w), rng.uniform(40, 320), rng.uniform(-6, 6),
                       rng.uniform(-5, 3)) for _ in range(60)]
        self.cone = pygame.Surface((w, h), pygame.SRCALPHA)

        # scene 5 assets
        k5 = np.clip(np.arange(h) / float(h), 0.0, 1.0)
        top5 = np.array((5, 4, 8), dtype=np.float32)
        bot5 = np.array((26, 18, 10), dtype=np.float32)
        col5 = top5[None, :] * (1 - k5[:, None]) + bot5[None, :] * k5[:, None]
        self.bg5 = pygame.surfarray.make_surface(
            np.repeat(col5[None, :, :], w, axis=0).astype(np.uint8))
        self.shaft = pygame.Surface((w, h), pygame.SRCALPHA)
        page = pygame.Surface((28, 36), pygame.SRCALPHA)
        page.fill((244, 224, 164, 255))
        pygame.draw.rect(page, (196, 160, 92), (0, 0, 28, 36), 2)
        for ly in range(10, 32, 4):
            pygame.draw.line(page, (130, 98, 48), (5, ly), (23, ly), 1)
        pygame.draw.line(page, (150, 40, 30), (14, 2), (14, 8), 2)
        pygame.draw.line(page, (150, 40, 30), (11, 4), (17, 4), 2)
        self.page_sprite = page
        pages = []
        for i in range(14):
            depth = rng.uniform(0.6, 1.5)
            pages.append((rng.uniform(30, w - 30), rng.uniform(0, h), rng.uniform(0.7, 1.6),
                          rng.uniform(20, 60), rng.uniform(0.5, 1.4), rng.uniform(0, 6.28),
                          rng.uniform(0.8, 2.2), depth, rng.uniform(15, 55)))
        pages.sort(key=lambda p: p[7])          # far first
        self.pages = pages

        # scene 6 assets
        self.title_gold = self.font_xl.render(TITLE_FILIPINO, True, GOLD)
        self.title_red = self._to32(self.font_xl.render(TITLE_FILIPINO, True, (255, 30, 30), (0, 0, 0)))
        self.title_cyan = self._to32(self.font_xl.render(TITLE_FILIPINO, True, (30, 220, 255), (0, 0, 0)))
        self.sparks = []
        palette = [(255, 220, 120), (255, 150, 40), (255, 255, 230), (255, 90, 30)]
        for _ in range(90):
            self.sparks.append((rng.uniform(0, 6.283), rng.uniform(90, 430),
                                rng.uniform(0.5, 1.7), rng.choice((1, 1, 2, 2, 3)),
                                rng.choice(palette)))

        # global overlays
        self.vig = self._make_edge((0, 0, 0), 190, 0.42)
        self.red_vig = self._make_edge((170, 0, 0), 255, 0.30)
        self.tint3 = pygame.Surface((w, h), pygame.SRCALPHA)
        self.tint3.fill((28, 0, 10, 118))
        self.red_flash = pygame.Surface((w, h))
        self.red_flash.fill((210, 12, 12))
        self.white = pygame.Surface((w, h))
        self.white.fill((255, 255, 255))
        self.black = pygame.Surface((w, h))
        self.black.fill((0, 0, 0))
        nrng = np.random.default_rng(7)
        self.grain = []
        for _ in range(8):
            n = nrng.integers(0, 24, (w, h), dtype=np.uint8)
            self.grain.append(pygame.surfarray.make_surface(np.stack([n, n, n], axis=2)))
        self.scan = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(0, h, 2):
            pygame.draw.line(self.scan, (0, 0, 0, 34), (0, y), (w, y))

    # ─── procedural asset builders ────────────────────────────────────────
    @staticmethod
    def _to32(img):
        """Text rendered with a background can be 8-bit; convert so it can be scaled."""
        try:
            return img.convert()
        except Exception:
            return img

    @staticmethod
    def _make_fog(w, h, color, peak):
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((color[0], color[1], color[2], 255))
        ys, xs = np.ogrid[:h, :w]
        d = np.sqrt(((xs - w / 2.0) / (w / 2.0)) ** 2 + ((ys - h / 2.0) / (h / 2.0)) ** 2)
        a = np.clip(1.0 - d, 0.0, 1.0) ** 1.6 * peak
        av = pygame.surfarray.pixels_alpha(surf)
        av[:, :] = a.T.astype(np.uint8)
        del av
        return surf

    def _make_edge(self, color, max_alpha, inner):
        w, h = self.w, self.h
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((color[0], color[1], color[2], 255))
        cx, cy = w / 2.0, h / 2.0
        md = math.sqrt(cx * cx + cy * cy)
        ys, xs = np.ogrid[:h, :w]
        d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
        t = np.clip((d - md * inner) / max(1.0, md * (1.0 - inner)), 0.0, 1.0)
        av = pygame.surfarray.pixels_alpha(surf)
        av[:, :] = ((t ** 2) * max_alpha).T.astype(np.uint8)
        del av
        return surf

    def _glow(self, radius, color):
        radius = max(2, min(200, int(radius)))
        col = tuple(max(0, min(255, (int(c) // 8) * 8)) for c in color)
        key = (radius, col)
        g = self._glow_cache.get(key)
        if g is None:
            size = radius * 2 + 1
            ys, xs = np.ogrid[-radius:radius + 1, -radius:radius + 1]
            f = np.clip(1.0 - np.sqrt(xs * xs + ys * ys) / float(radius), 0.0, 1.0) ** 2
            arr = np.zeros((size, size, 3), dtype=np.uint8)
            for c in range(3):
                arr[:, :, c] = (f * col[c]).astype(np.uint8)
            g = pygame.Surface((size, size))
            pygame.surfarray.blit_array(g, arr)
            self._glow_cache[key] = g
        return g

    def _add_glow(self, x, y, radius, color):
        g = self._glow(radius, color)
        self.surface.blit(g, (int(x - g.get_width() / 2), int(y - g.get_height() / 2)),
                          special_flags=pygame.BLEND_RGB_ADD)

    def _build_layer(self, color, count, hmin, hmax, kinds, seed):
        rng = random.Random(seed)
        surf = pygame.Surface((self.w * 2, self.h), pygame.SRCALPHA)
        for i in range(count):
            x = (i + rng.uniform(0.1, 0.9)) * self.w / count
            th = rng.randint(hmin, hmax)
            kind = rng.choice(kinds)
            tseed = rng.random()
            for ox in (0, self.w):
                self._draw_tree(surf, x + ox, self.h + 6, th, color, kind, tseed)
        return surf

    @staticmethod
    def _draw_tree(surf, x, base, th, color, kind, tseed):
        r = random.Random(tseed)
        c = (color[0], color[1], color[2], 255)
        top = base - th
        if kind == 'pine':
            tw = max(3, th // 16)
            pygame.draw.rect(surf, c, _ir(x - tw // 2, top + th * 0.2, tw, th * 0.8))
            for i in range(6):
                yt = top + i * th * 0.13
                hw = 5 + i * th * 0.045
                pygame.draw.polygon(surf, c, [(x, yt - th * 0.12), (x - hw, yt + th * 0.14),
                                              (x + hw, yt + th * 0.14)])
        elif kind == 'bamboo':
            for k in range(4):
                bx = x + (k - 1.5) * 7 + r.uniform(-2, 2)
                bh = th * r.uniform(0.7, 1.0)
                pygame.draw.rect(surf, c, _ir(bx - 2, base - bh, 4, bh))
                for ny in range(int(base - bh) + 12, int(base), 28):
                    pygame.draw.rect(surf, c, _ir(bx - 3, ny, 6, 2))
                for lf in range(3):
                    sgn = r.choice((-1, 1))
                    pygame.draw.line(surf, c, (bx, base - bh + lf * 10),
                                     (bx + sgn * r.uniform(10, 22), base - bh + lf * 10 - 6), 2)
        elif kind == 'balete':
            tw = max(8, th // 9)
            pygame.draw.polygon(surf, c, [(x - tw, base), (x - tw * 0.5, top + th * 0.35),
                                          (x + tw * 0.5, top + th * 0.35), (x + tw, base)])
            for k in range(4):
                cx = x + (k - 1.5) * th * 0.12
                cy = top + th * 0.22 + r.uniform(-6, 6)
                pygame.draw.ellipse(surf, c, _ir(cx - th * 0.17, cy - th * 0.12, th * 0.34, th * 0.24))
            for k in range(5):
                rx = x + r.uniform(-th * 0.2, th * 0.2)
                pygame.draw.line(surf, c, (rx, top + th * 0.3),
                                 (rx + r.uniform(-4, 4), top + th * 0.3 + r.uniform(th * 0.25, th * 0.55)), 2)
        else:   # dead tree
            tw = max(5, th // 18)
            pygame.draw.polygon(surf, c, [(x - tw, base), (x - tw * 0.4, top),
                                          (x + tw * 0.4, top), (x + tw, base)])
            for k in range(6):
                by = top + th * (0.08 + k * 0.11)
                side = -1 if k % 2 == 0 else 1
                ln = r.uniform(th * 0.12, th * 0.28)
                ex = x + side * ln
                ey = by - ln * r.uniform(0.3, 0.8)
                pygame.draw.line(surf, c, (x, by), (ex, ey), max(2, tw // 2))
                pygame.draw.line(surf, c, (ex, ey), (ex + side * ln * 0.4, ey - ln * 0.4), 1)

    def _build_beam(self):
        w, h = self.w, self.h
        mw, mh = w * 2, h * 2
        rx = w * 0.30
        ry = rx * 0.85
        ys, xs = np.ogrid[:mh, :mw]
        r = np.sqrt(((xs - w) / rx) ** 2 + ((ys - h) / ry) ** 2)
        t = np.clip((r - 0.12) / 0.88, 0.0, 1.0)
        t = t * t * (3.0 - 2.0 * t)
        dm = pygame.Surface((mw, mh), pygame.SRCALPHA)
        dm.fill((3, 5, 12, 255))
        av = pygame.surfarray.pixels_alpha(dm)
        av[:, :] = (t * int(0.93 * 255)).T.astype(np.uint8)
        del av
        self.dark_mask = dm
        f = np.clip(1.0 - r, 0.0, 1.0) ** 2
        rgb = np.zeros((mw, mh, 3), dtype=np.uint8)
        for c, v in enumerate((120, 96, 52)):
            rgb[:, :, c] = (f * v).T.astype(np.uint8)
        gm = pygame.Surface((mw, mh))
        pygame.surfarray.blit_array(gm, rgb)
        self.glow_mask = gm
        self.dark_off = pygame.Surface((w, h), pygame.SRCALPHA)
        self.dark_off.fill((3, 5, 12, 238))
        self.beam_rx = rx

    def _build_world4(self):
        W, H = self.w + 20, self.h + 20
        s = pygame.Surface((W, H))
        s.fill((8, 11, 10))
        horizon = int(H * 0.58)
        for y in range(horizon, H):
            t = (y - horizon) / float(H - horizon)
            pygame.draw.line(s, _ir(18 + 26 * t, 22 + 28 * t, 17 + 20 * t), (0, y), (W, y))
        rng = random.Random(404)

        def trunk(x, wd, y1, col, hl):
            pygame.draw.rect(s, col, (x, 0, wd, y1))
            pygame.draw.rect(s, hl, _ir(x + wd * 0.2, 0, max(1, wd * 0.15), y1))

        for _ in range(16):
            trunk(rng.randint(0, W), rng.randint(8, 16), rng.randint(horizon - 10, horizon + 30),
                  (30, 38, 32), (42, 52, 44))
        for _ in range(9):
            trunk(rng.randint(0, W), rng.randint(16, 28), rng.randint(horizon + 40, horizon + 90),
                  (44, 52, 42), (62, 74, 58))
        for _ in range(5):
            trunk(rng.randint(0, W), rng.randint(30, 52), H, (60, 68, 54), (86, 98, 76))
        for _ in range(130):
            x = rng.randint(0, W)
            y = rng.randint(horizon + 10, H - 4)
            ln = rng.randint(6, 16)
            for a in (-50, -25, 0, 25, 50):
                ang = math.radians(-90 + a)
                pygame.draw.line(s, (40, 72, 44), (x, y),
                                 (x + math.cos(ang) * ln, y + math.sin(ang) * ln), 1)
        for _ in range(1500):
            v = rng.randint(30, 70)
            s.set_at((rng.randint(0, W - 1), rng.randint(0, H - 1)), (v, v + 8, v - 4))
        self.world4 = s

    def _build_figure4(self):
        f = pygame.Surface((60, 170), pygame.SRCALPHA)
        col = (9, 9, 13, 255)
        pygame.draw.circle(f, col, (30, 14), 10)
        pygame.draw.polygon(f, col, [(26, 24), (34, 24), (40, 36), (38, 86), (22, 86), (20, 36)])
        pygame.draw.line(f, col, (21, 38), (8, 100), 4)
        pygame.draw.line(f, col, (8, 100), (10, 130), 3)
        pygame.draw.line(f, col, (39, 38), (52, 100), 4)
        pygame.draw.line(f, col, (52, 100), (50, 132), 3)
        pygame.draw.line(f, col, (26, 86), (24, 168), 6)
        pygame.draw.line(f, col, (34, 86), (37, 168), 6)
        self.figure4 = f

    # ─── text helpers ─────────────────────────────────────────────────────
    def _text_img(self, text, font, color):
        key = (text, id(font), color)
        img = self._text_cache.get(key)
        if img is None:
            img = font.render(text, True, color)
            if len(self._text_cache) > 600:
                self._text_cache.clear()
            self._text_cache[key] = img
        return img

    def _txt(self, text, font, color, center, alpha=255.0, shadow=True, glow=False):
        a = int(max(0.0, min(255.0, alpha)))
        if a <= 0 or not text:
            return
        img = self._text_img(text, font, color)
        rect = img.get_rect(center=_ir(*center))
        if shadow:
            sh = self._text_img(text, font, BLACK)
            sh.set_alpha(int(a * 0.85))
            self.surface.blit(sh, (rect.x + 2, rect.y + 2))
        if glow:
            img.set_alpha(int(a * 0.22))
            for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                self.surface.blit(img, (rect.x + ox, rect.y + oy))
        img.set_alpha(a)
        self.surface.blit(img, rect)

    def _txt_left(self, text, font, color, topleft, alpha=255.0):
        a = int(max(0.0, min(255.0, alpha)))
        if a <= 0 or not text:
            return
        img = self._text_img(text, font, color)
        sh = self._text_img(text, font, BLACK)
        sh.set_alpha(int(a * 0.85))
        self.surface.blit(sh, (topleft[0] + 2, topleft[1] + 2))
        img.set_alpha(a)
        self.surface.blit(img, topleft)

    @staticmethod
    def _wrap(text, font, maxw):
        words, lines, cur = text.split(), [], ''
        for wd in words:
            trial = (cur + ' ' + wd).strip()
            if font.size(trial)[0] <= maxw or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = wd
        if cur:
            lines.append(cur)
        return lines

    def _shake(self, dx, dy):
        if dx or dy:
            self.surface.scroll(int(dx), int(dy))

    # ─── shared effects ───────────────────────────────────────────────────
    def _embers(self, st, count, color, speed_mul=1.0, alpha=1.0):
        s = self.surface
        for i in range(min(count, len(self.embers))):
            x0, y0, spd, ph, size = self.embers[i]
            y = (y0 - st * spd * speed_mul) % self.h
            x = (x0 + math.sin(st * 0.9 + ph) * 16) % self.w
            fl = 0.55 + 0.45 * math.sin(st * 5.0 + ph * 3.0)
            c = _ir(color[0] * fl * alpha, color[1] * fl * alpha, color[2] * fl * alpha)
            pygame.draw.circle(s, c, (int(x), int(y)), size)

    def _draw_layers(self, st, fog_tex, speed_mul=1.0, fog_alpha=255):
        s = self.surface
        for idx, layer in enumerate(self.layers):
            off = (st * self.layer_speed[idx] * speed_mul) % self.w
            s.blit(layer, (-int(off), int(math.sin(st * 0.4 + idx) * 2)))
            if idx < 3:
                for j in range(2):
                    fx = ((j * 330 + idx * 110 + st * (7 + idx * 5)) % (self.w + 360)) - 330
                    fy = self.h - 175 + idx * 34 + j * 14 + math.sin(st * 0.5 + j + idx) * 6
                    fog_tex.set_alpha(fog_alpha)
                    s.blit(fog_tex, (int(fx), int(fy)))

    def _draw_eyes(self, x, y, size, color, alpha, blink):
        s = self.surface
        aq = round(max(0.0, min(1.0, alpha)) * 8) / 8.0
        if aq <= 0.0:
            return
        g = self._glow(18 * size, tuple(c * 0.55 * aq for c in color))
        s.blit(g, (int(x - g.get_width() / 2), int(y - g.get_height() / 2)),
               special_flags=pygame.BLEND_RGB_ADD)
        sep = 7.0 * size
        ew = max(2, int(6 * size))
        eh = max(1, int(3.2 * size * (1.0 - blink)))
        ec = _ir(color[0] * aq, color[1] * aq, color[2] * aq)
        for sx in (-sep, sep):
            r = pygame.Rect(0, 0, ew, eh)
            r.center = (int(x + sx), int(y))
            pygame.draw.ellipse(s, ec, r)
            core = pygame.Rect(0, 0, max(1, ew // 2), max(1, eh // 2))
            core.center = r.center
            pygame.draw.ellipse(s, _ir(255 * aq, 235 * aq, 220 * aq), core)

    # ─── lifecycle ────────────────────────────────────────────────────────
    def reset(self):
        self.time = 0.0
        self.skipped = False
        self.finished = False
        self.cues.clear()
        self.eye_cues.clear()
        try:
            audio_mgr.start_intro_ambience()
        except Exception:
            pass

    def _play(self, name, vol):
        try:
            audio_mgr.play(name, vol)
        except Exception:
            pass

    def update(self, dt, events):
        for e in events:
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE):
                self.skipped = True
                self.finished = True
                try:
                    audio_mgr.stop_intro_ambience()
                except Exception:
                    pass
                return True
        if self.finished or self.skipped:
            return True
        self.time += dt
        if self.time >= self.duration:
            self.finished = True
            try:
                audio_mgr.stop_intro_ambience()
            except Exception:
                pass
            return True
        t = self.time
        if 0.5 <= t < 1.0 and 1 not in self.cues:
            self.cues.add(1); self._play('intro_wind', 0.6)
        elif 12.0 <= t < 12.5 and 2 not in self.cues:
            self.cues.add(2)
            try:
                audio_mgr.play_drone(0.4)
            except Exception:
                pass
        elif 26.0 <= t < 26.5 and 3 not in self.cues:
            self.cues.add(3); self._play('creature_call', 0.7)
        elif 41.0 <= t < 41.5 and 4 not in self.cues:
            self.cues.add(4); self._play('flashlight_click', 0.8)
        elif 56.0 <= t < 56.5 and 5 not in self.cues:
            self.cues.add(5); self._play('page_rustle', 0.7)
        elif 64.5 <= t < 65.0 and 6 not in self.cues:
            self.cues.add(6); self._play('title_sting', 1.0)
        for i, ta in enumerate(self.eye_abs):          # heartbeat thump per pair of eyes
            if t >= ta and i not in self.eye_cues:
                self.eye_cues.add(i)
                self._play('heartbeat', 0.5)
        return False

    # ─── main render ──────────────────────────────────────────────────────
    def render(self):
        t = self.time
        if t < 10.0:
            self._scene1(t)
        elif t < 24.0:
            self._scene2(t - 10.0)
        elif t < 38.0:
            self._scene3(t - 24.0)
        elif t < 52.0:
            self._scene4(t - 38.0)
        elif t < 64.0:
            self._scene5(t - 52.0)
        else:
            self._scene6(t - 64.0)
        self._post(t)

    # ─── scene 1: WARNING ─────────────────────────────────────────────────
    def _scene1(self, st):
        s = self.surface
        w, h = self.w, self.h
        s.fill((1, 1, 3))
        hb = _heartbeat(st, 52 + st * 3.0)
        base = 0.22 + 0.025 * st
        self.red_vig.set_alpha(int(255 * min(1.0, base * 0.6 + hb * 0.55)))
        s.blit(self.red_vig, (0, 0))
        self._embers(st, 26, (190, 30, 20), speed_mul=0.7)

        if ' — ' in WARNING_FILIPINO:
            head, body = WARNING_FILIPINO.split(' — ', 1)
        else:
            head, body = '', WARNING_FILIPINO
        if ' — ' in WARNING_ENGLISH:
            body_en = WARNING_ENGLISH.split(' — ', 1)[1]
        else:
            body_en = WARNING_ENGLISH
        cx = w // 2

        if head:
            flick = 1.0 if _hash(math.floor(st * 18)) > 0.12 else 0.35
            jit = int((_hash(st * 50) - 0.5) * 5) if _hash(math.floor(st * 9) + 3.0) > 0.9 else 0
            self._txt(head, self.font_lg, (225, 35, 35), (cx + jit, 112),
                      alpha=255 * _fade(st, 0.6, 1.6) * flick, glow=True)

        lines = self._wrap(body, self.font_md, 540)
        total = sum(len(l) for l in lines)
        chars = int(max(0.0, st - 1.8) * 24)
        rem = chars
        y = 160
        for ln in lines:
            if rem <= 0:
                break
            part = ln[:rem]
            rem -= len(ln)
            fw = self.font_md.size(ln)[0]
            cursor = '_' if (rem <= 0 and chars < total and int(st * 3) % 2 == 0) else ''
            self._txt_left(part + cursor, self.font_md, (245, 245, 250), (cx - fw // 2, y))
            y += 28
        y_en = 160 + 28 * len(lines) + 20
        for ln in self._wrap(body_en, self.font_sm, 540):
            self._txt(ln, self.font_sm, (185, 165, 155), (cx, y_en), alpha=255 * _fade(st, 4.8, 6.0))
            y_en += 20
        self._txt_left(BUILD_STAMP, self.font_tiny, (110, 110, 125), (12, h - 46),
                       alpha=255 * _fade(st, 1.0, 2.0))

    # ─── scene 2: FOREST ──────────────────────────────────────────────────
    def _scene2(self, st):
        s = self.surface
        w, h = self.w, self.h
        s.blit(self.sky, (0, 0))
        for x, y, ph, big in self.stars:
            v = int(150 + 105 * (0.55 + 0.45 * math.sin(st * 3.2 + ph)))
            col = (v, v, min(255, v + 25))
            if big:
                pygame.draw.rect(s, col, (int(x), int(y), 2, 2))
            else:
                s.set_at((int(x), int(y)), col)
        mx = int(w * 0.76 + st * 0.5)
        my = 84 + int(math.sin(st * 0.25) * 4)
        self._add_glow(mx, my, 110, (36, 46, 70))
        self._add_glow(mx, my, 52, (64, 74, 100))
        s.blit(self.moon, (mx - 40, my - 40))
        for i in range(3):
            cx = ((i * 250 + st * (6 + 2 * i)) % (w + 320)) - 300
            s.blit(self.fog_dark, (int(cx), 60 + i * 38))
        self._draw_layers(st, self.fog_light)
        for x0, y0, ax, ay, fx, fy, ph in self.fireflies:
            b = max(0.0, math.sin(st * 1.7 + ph)) ** 2
            if b < 0.08:
                continue
            px = x0 + math.sin(st * fx + ph) * ax
            py = y0 + math.cos(st * fy + ph) * ay
            self._add_glow(px, py, 8, (190 * b, 210 * b, 90 * b))
            pygame.draw.circle(s, _ir(235 * b, 250 * b, 160 * b), (int(px), int(py)), 1)
        out = 1.0 - _fade(st, 12.6, 13.6)
        self._txt(SCENE2_FIL, self.font_lg, (240, 240, 248), (w // 2, 168),
                  alpha=255 * _fade(st, 2.0, 3.4) * out, glow=True)
        self._txt(SCENE2_ENG, self.font_sm, (185, 195, 210), (w // 2, 200),
                  alpha=255 * _fade(st, 4.4, 5.6) * out)
        self._txt(SCENE2_CAPTION, self.font_tiny, (150, 160, 175), (w // 2, 224),
                  alpha=255 * _fade(st, 7.5, 8.8) * out)

    # ─── scene 3: AWAKENING ───────────────────────────────────────────────
    def _scene3(self, st):
        s = self.surface
        w, h = self.w, self.h
        s.fill((9, 4, 14))
        hb = _heartbeat(st, 60 + st * 5.5)
        self._add_glow(w // 2, h - 70, 240, (50 + 40 * hb, 4, 6))
        self._add_glow(int(w * 0.3), 100, 140, (22, 0, 12))
        self._draw_layers(st, self.fog_red, speed_mul=0.5)
        s.blit(self.tint3, (0, 0))

        surge = max(0.0, st - 12.0)
        pulse_max = 0.0
        shake = 0.0
        for x, y, t0, col, size in self.eyes:
            if st < t0:
                continue
            age = st - t0
            fi = _smooth(age / 0.35)
            pulse_max = max(pulse_max, max(0.0, 1.0 - age / 0.7))
            shake = max(shake, max(0.0, 1.0 - age / 0.4) * 5.0)
            ph = (st * 0.6 + t0 * 3.1) % 4.0
            blink = _clamp01(1.0 - abs(ph - 0.06) / 0.06) if ph < 0.12 else 0.0
            ex = x + math.sin(st * 0.7 + t0) * 3.0
            sz = size * (1.0 + surge * 0.45) * (0.6 + 0.4 * fi)
            self._draw_eyes(ex, y, sz, col, fi * (0.75 + 0.25 * hb), blink)

        self.red_vig.set_alpha(int(min(255, 90 + 120 * hb + 60 * st / 14.0)))
        s.blit(self.red_vig, (0, 0))
        fa = 90 * pulse_max + 40 * hb + 130 * _smooth((st - 12.0) / 2.0)
        self.red_flash.set_alpha(int(min(255, fa)))
        s.blit(self.red_flash, (0, 0))
        self._txt(SCENE3_CAPTION, self.font_sm, (235, 185, 175), (w // 2, 58),
                  alpha=255 * _fade(st, 1.2, 2.4) * (1.0 - _fade(st, 11.8, 12.8)), glow=True)
        amp = shake + 7.0 * _smooth((st - 12.0) / 2.0)
        if amp > 0.3:
            self._shake((_hash(st * 47.0) - 0.5) * 2 * amp, (_hash(st * 53.0 + 1.0) - 0.5) * 2 * amp)

    # ─── scene 4: TRAVELER ────────────────────────────────────────────────
    def _scene4(self, st):
        s = self.surface
        w, h = self.w, self.h
        bx = int(math.sin(st * 5.5) * 2)
        by = int(abs(math.sin(st * 5.5)) * 3)
        s.blit(self.world4, (-10 + bx, -10 + by))

        fig_on = st > 6.5
        fig_x = 500 - max(0.0, st - 6.5) * 14.0
        fig_scale = 0.8 + max(0.0, st - 6.5) * 0.09
        fw = fh = fx = fy = 0
        if fig_on:
            fw, fh = int(60 * fig_scale), int(170 * fig_scale)
            fig = pygame.transform.smoothscale(self.figure4, (fw, fh))
            fx = int(fig_x - fw / 2 + bx)
            fy = int(305 - fh + by)
            s.blit(fig, (fx, fy))

        cx = w * 0.5 + math.sin(st * 0.8) * 150 + math.sin(st * 2.3) * 25
        cy = h * 0.5 + math.sin(st * 1.3) * 14 + by * 0.5
        if st > 6.5:
            k = _smooth((st - 6.5) / 2.0) * (1.0 - _smooth((st - 11.5) / 1.0))
            cx = cx * (1 - k) + fig_x * k
            cy = cy * (1 - k) + 215 * k
        cx += (_hash(st * 40.0) - 0.5) * 3
        cy += (_hash(st * 41.0 + 2.0) - 0.5) * 3

        inten = 1.0
        f = _hash(math.floor(st * 14.0))
        if st > 9.0 and f < 0.25:
            inten = 0.3
        if st > 11.5 and f < 0.5:
            inten = 0.0
        if st > 4.0 and _hash(math.floor(st * 6.0) + 9.0) > 0.93:
            inten = min(inten, 0.5)

        pos = (int(max(0, min(w, cx))) - w, int(max(0, min(h, cy))) - h)
        if inten <= 0.0:
            s.blit(self.dark_off, (0, 0))
        else:
            s.blit(self.dark_mask, pos)
            if inten >= 0.99:
                s.blit(self.glow_mask, pos, special_flags=pygame.BLEND_RGB_ADD)
                self.cone.fill((0, 0, 0, 0))
                pygame.draw.polygon(self.cone, (255, 238, 190, 17),
                                    [(w // 2 + 70, h), (int(cx - self.beam_rx * 0.5), int(cy)),
                                     (int(cx + self.beam_rx * 0.5), int(cy))])
                s.blit(self.cone, (0, 0))
            else:
                self.black.set_alpha(int((1.0 - inten) * 150))
                s.blit(self.black, (0, 0))
            for mx0, my0, vx, vy in self.motes:
                px = (mx0 + vx * st) % w
                py = (my0 + vy * st) % h
                d = math.hypot(px - cx, py - cy) / self.beam_rx
                b = _clamp01(1.0 - d) * inten
                if b > 0.06:
                    pygame.draw.circle(s, _ir(255 * b, 240 * b, 200 * b), (int(px), int(py)), 1)

        if fig_on and st > 8.2:
            ew = 0.85 + 0.15 * math.sin(st * 9.0)
            hx = fx + fw * (30 / 60.0)
            hy = fy + fh * (13 / 170.0)
            self._draw_eyes(hx, hy, 0.5 * fig_scale * 1.5, (255, 40, 30), _smooth((st - 8.2) / 0.6) * ew, 0.0)

        self._txt(SCENE4_CAPTION, self.font_sm, (190, 210, 198), (w // 2, 56),
                  alpha=255 * _fade(st, 1.2, 2.4) * (1.0 - _fade(st, 5.8, 6.8)), glow=True)
        if st > 6.5:
            self.red_vig.set_alpha(int(min(255, 120 * _smooth((st - 6.5) / 5.0))))
            s.blit(self.red_vig, (0, 0))
        bo = _fade(st, 12.6, 13.8)
        if bo > 0.0:
            self.black.set_alpha(int(255 * bo))
            s.blit(self.black, (0, 0))

    # ─── scene 5: PAGES ───────────────────────────────────────────────────
    def _scene5(self, st):
        s = self.surface
        w, h = self.w, self.h
        s.blit(self.bg5, (0, 0))
        self.shaft.fill((0, 0, 0, 0))
        for i in range(4):
            x0 = 120 + i * 140 + math.sin(st * 0.3 + i) * 30
            pygame.draw.polygon(self.shaft, (255, 225, 150, 13 + 3 * (i % 2)),
                                [(x0 - 8, 0), (x0 + 8, 0), (x0 + 60 + i * 10, h), (x0 - 70, h)])
        s.blit(self.shaft, (0, 0))
        for j in range(3):
            fx = ((j * 300 + st * (8 + j * 4)) % (w + 360)) - 330
            s.blit(self.fog_gold, (int(fx), h - 170 + j * 26))
        self._embers(st, 70, (255, 200, 90), speed_mul=-0.6, alpha=0.8)

        for x0, y0, spd, amp, sf, ph, ff, depth, rot in self.pages:
            y = ((y0 + st * spd * 30.0) % (h + 80)) - 40
            x = x0 + math.sin(st * sf + ph) * amp
            flip = math.cos(st * ff + ph)
            wsc = max(3, int(28 * depth * abs(flip)))
            hsc = max(4, int(36 * depth))
            img = pygame.transform.scale(self.page_sprite, (wsc, hsc))
            img = pygame.transform.rotate(img, math.sin(st * 0.8 + ph) * rot)
            v = int(110 + 145 * abs(flip))
            img.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
            self._add_glow(x, y, 30 * depth, (110, 90, 40))
            s.blit(img, (int(x - img.get_width() / 2), int(y - img.get_height() / 2)))

        out = 1.0 - _fade(st, 10.8, 11.8)
        self._txt(SCENE5_FIL, self.font_md, (255, 240, 200), (w // 2, h - 96),
                  alpha=255 * _fade(st, 1.5, 2.7) * out, glow=True)
        self._txt(SCENE5_ENG, self.font_sm, (205, 185, 150), (w // 2, h - 68),
                  alpha=255 * _fade(st, 3.0, 4.2) * out)

    # ─── scene 6: TITLE ───────────────────────────────────────────────────
    def _scene6(self, st):
        s = self.surface
        w, h = self.w, self.h
        s.fill((2, 2, 5))
        cx, cy = w // 2, h // 2 - 30
        self._embers(st, 40, (255, 120, 30), speed_mul=1.4, alpha=0.9)
        if st < 0.35:
            return
        a = st - 0.35

        scale = 1.0 + 2.6 * max(0.0, 1.0 - a / 0.28) ** 2
        tw, th = self.title_gold.get_size()
        sw, sh = int(tw * scale), int(th * scale)
        pulse = 0.75 + 0.25 * math.sin(st * 3.0)
        self._add_glow(cx, cy, 170, (70 * pulse, 52 * pulse, 10 * pulse))

        def scaled(img):
            if scale <= 1.01:
                return img
            try:
                return pygame.transform.smoothscale(img, (sw, sh))
            except Exception:
                return pygame.transform.scale(img, (sw, sh))

        if a < 1.1:
            amt = int(8 * max(0.0, 1.0 - a / 1.0))
            for img, dx in ((self.title_red, -amt), (self.title_cyan, amt)):
                s.blit(scaled(img), (cx - sw // 2 + dx, cy - sh // 2), special_flags=pygame.BLEND_RGB_ADD)
        s.blit(scaled(self.title_gold), (cx - sw // 2, cy - sh // 2))

        if a < 0.8:
            ring = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.circle(ring, (255, 230, 180, int(200 * (1.0 - a / 0.8))),
                               (cx, cy), max(2, int(a * 620)), 5)
            s.blit(ring, (0, 0))
        for ang, spd, life, size, col in self.sparks:
            if a > life:
                continue
            f = 1.0 - a / life
            px = cx + math.cos(ang) * spd * a
            py = cy + math.sin(ang) * spd * a + 220.0 * a * a
            pygame.draw.circle(s, _ir(col[0] * f, col[1] * f, col[2] * f), (int(px), int(py)), size)

        sub_a = _fade(st, 1.8, 2.6)
        if sub_a > 0.0:
            self._add_glow(cx, cy + 50, 80, (60 * sub_a, 6 * sub_a, 6 * sub_a))
            self._txt(SUBTITLE_FIL, self.font_md, HEALTH_RED, (cx, cy + 50), alpha=255 * sub_a, glow=True)
        cl = _fade(st, 5.2, 6.4)
        self._txt(CLOSING_FILIPINO, self.font_tiny, (170, 160, 150), (cx, h - 112), alpha=210 * cl)
        self._txt(CLOSING_ENGLISH, self.font_tiny, (130, 125, 120), (cx, h - 96), alpha=210 * cl)
        if st > 3.8 and int(st * 2) % 2 == 0:
            self._txt(PRESS_SPACE, self.font_sm, WHITE, (cx, h - 60))

        if a < 0.9:
            self.white.set_alpha(int(255 * max(0.0, 1.0 - a / 0.9)))
            s.blit(self.white, (0, 0))
        amp = 16.0 * max(0.0, 1.0 - a / 0.8) ** 2
        if amp > 0.3:
            self._shake((_hash(st * 61.0) - 0.5) * 2 * amp, (_hash(st * 67.0 + 3.0) - 0.5) * 2 * amp)

    # ─── post processing ──────────────────────────────────────────────────
    def _dip_alpha(self, t):
        a = 0.0
        for b in (10.0, 24.0, 38.0, 52.0):
            a = max(a, 1.0 - abs(t - b) / 0.45)
        if 63.3 < t < 64.0:
            a = max(a, (t - 63.3) / 0.7)
        if t < 0.7:
            a = max(a, 1.0 - t / 0.7)
        if t > 73.2:
            a = max(a, (t - 73.2) / 1.8)
        return _clamp01(a)

    def _glitch(self, t):
        g = 0.0
        for b in self.SCENES:
            g = max(g, 1.0 - abs(t - b) / 0.5)
        if _hash(math.floor(t * 12.0) + 7.0) > 0.975:
            g = max(g, 0.6)
        if g <= 0.0:
            return
        n = 3 + int(g * 6)
        for k in range(n):
            y = int(_hash(t * 31.0 + k * 7.1) * (self.h - 60)) + 28
            hh = 3 + int(_hash(t * 17.0 + k * 3.3) * 12)
            dx = int((_hash(t * 23.0 + k * 5.7) - 0.5) * 2 * (8 + 30 * g))
            if y + hh > self.h:
                continue
            strip = self.surface.subsurface((0, y, self.w, hh)).copy()
            self.surface.blit(strip, (dx, y))

    def _post(self, t):
        s = self.surface
        self._glitch(t)
        s.blit(self.vig, (0, 0))
        s.blit(self.grain[int(t * 24.0) % len(self.grain)], (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        s.blit(self.scan, (0, 0))
        d = self._dip_alpha(t)
        if d > 0.0:
            self.black.set_alpha(int(255 * d))
            s.blit(self.black, (0, 0))
        pygame.draw.rect(s, BLACK, (0, 0, self.w, 28))
        pygame.draw.rect(s, BLACK, (0, self.h - 28, self.w, 28))
        if self.show_skip:
            skip = self.font_tiny.render("[Press Space / Enter to Skip]", True, (140, 140, 140))
            s.blit(skip, (self.w - skip.get_width() - 10, 8))
