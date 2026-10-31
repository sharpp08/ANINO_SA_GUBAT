"""
Jumpscare System v2 - Intense, layered death sequence (drop-in replacement for jumpscare.py)

Same public API as v1: get_jumpscare_manager(), trigger(), update(dt),
render(surface), is_playing(). main.py needs NO changes.

What v2 adds over the 4-phase ellipse-face:
  * 7-phase structure: subliminal pre-flashes -> accelerating lunge with
    jump-cuts -> chromatic aberration -> film static -> impact flash ->
    iris snap -> lingering after-image fade.
  * Enemy-themed faces (aswang / manananggal / tikbalang / kapre / white_lady /
    multo / sigbin) - trigger(enemy_type=...) picks palette & eye style.
  * Trauma shake that actually shakes the whole rendered frame (v1 returned a
    shake value main.py never used; here it is applied internally).
  * RGB-split aberration scaled by approach velocity.
  * 13 Hz edge strobe (near the peak sensitivity of peripheral vision).
  * Audio layering: scream wav + optional stinger + sub-bass thump, all
    defensive try/except so a missing file never crashes the game.
  * INTENSITY config: 1.0 standard, crank to 1.5-1.6 for extreme.

Swap: back up the old jumpscare.py, then copy this file over it as jumpscare.py.
"""
import os
import math
import random
import pygame
import numpy as np

try:
    from settings import BASE_PATH
except Exception:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

INTENSITY = 1.0          # 1.0 = standard, 1.5-1.6 = extreme
STATIC_ENABLED = True    # film-static overlay
ABERRATION_ENABLED = True
STROBE_HZ = 13.0         # edge strobe frequency


class JumpscareManager:
    """Manages the fullscreen jumpscare sequence triggered on lethal grabs."""

    THEMES = {
        'aswang':      {'skin': (46, 22, 22),  'glow': (255, 60, 60),  'eye': (255, 255, 170), 'mouth': (120, 10, 10)},
        'manananggal': {'skin': (190, 185, 195),'glow': (255, 80, 80),  'eye': (255, 240, 240), 'mouth': (60, 5, 8)},
        'tikbalang':   {'skin': (40, 26, 18),  'glow': (255, 190, 40), 'eye': (255, 230, 150), 'mouth': (90, 40, 10)},
        'kapre':       {'skin': (34, 24, 16),  'glow': (255, 130, 25), 'eye': (255, 210, 140), 'mouth': (70, 30, 8)},
        'white_lady':  {'skin': (215, 220, 235),'glow': (170, 200, 255),'eye': (240, 248, 255), 'mouth': (30, 35, 60)},
        'multo':       {'skin': (140, 160, 205),'glow': (150, 180, 255),'eye': (235, 242, 255), 'mouth': (40, 50, 90)},
        'sigbin':      {'skin': (52, 30, 26),  'glow': (255, 90, 25),  'eye': (255, 220, 160), 'mouth': (110, 20, 8)},
    }

    def __init__(self):
        self.active = False
        self.timer = 0.0
        self.duration = 1.6
        self.enemy_type = 'aswang'
        self.theme = self.THEMES['aswang']
        self.scream_sound = None
        self.multo_sound = None
        self.stinger_sound = None
        self._noise_frames = {}   # (w,h) -> [surface, ...]
        self._fx = None           # reusable fx surface
        self._rng = random.Random()

        # phase boundaries (seconds) - scale a bit with INTENSITY
        k = INTENSITY
        self.t_flash1 = 0.10
        self.t_rush = 0.12
        self.t_impact = 0.55 / min(k, 1.3)
        self.t_burst = self.t_impact + 0.10
        self.t_fade = self.t_burst + 0.25
        self.duration = self.t_fade + (0.75 / k)

        self._load_assets()

    # ── assets ────────────────────────────────────────────────────────────
    def _load_assets(self):
        pack_dir = os.path.join(BASE_PATH, 'enemy_animations_pack')
        for name, attr in (('jumpscare_scream.wav', 'scream_sound'),
                           ('multo_jumpscare.mp3', 'multo_sound'),
                           ('jumpscare_stinger.wav', 'stinger_sound')):
            path = os.path.join(pack_dir, name)
            if os.path.exists(path):
                try:
                    snd = pygame.mixer.Sound(path)
                    setattr(self, attr, snd)
                    print(f"[Jumpscare] Loaded audio: {path}")
                except Exception as e:
                    print(f"[Jumpscare] Failed to load {name}: {e}")

    def _play(self, snd, volume):
        """Play once on a free channel, stopping any earlier copy of the same
        sound so retriggers never overlap or stack repeats."""
        if snd is None:
            return
        try:
            # Stop every channel still bound to this exact Sound object
            # (find_channel() in pygame-ce returns a Channel, not an index,
            # and cannot locate a channel by sound, so scan explicitly).
            for i in range(pygame.mixer.get_num_channels()):
                try:
                    ch = pygame.mixer.Channel(i)
                    if ch.get_sound() is snd:
                        ch.stop()
                except Exception:
                    continue
            snd.set_volume(volume)
            snd.play()
        except Exception:
            pass

    # ── trigger / update ──────────────────────────────────────────────────
    def trigger(self, enemy_type=None, distance=0.0):
        """Fire the sequence. Returns stun seconds for the player (main.py API)."""
        self.active = True
        self.timer = 0.0
        self._rng = random.Random()

        etype = (enemy_type or 'aswang').lower()
        self.enemy_type = etype if etype in self.THEMES else 'aswang'
        self.theme = self.THEMES[self.enemy_type]

        # closer killer = faster, nastier pop
        proximity = max(0.0, min(1.0, 1.0 - distance / 10.0))
        self._proximity = proximity

        # Multo uses the dedicated multo_jumpscare.mp3 exclusively (no shared
        # stinger / creature layer, so it never overlaps the general audio).
        # If that file is missing or undecodable, fall back to the legacy
        # shared scream layers so the jumpscare is never silent.  All other
        # enemies keep their original shared scream + stinger + creature_call.
        if self.enemy_type == 'multo' and self.multo_sound is not None:
            self._play(self.multo_sound, 1.0)
        else:
            self._play(self.scream_sound, 1.0)
            self._play(self.stinger_sound, 0.9)
            try:
                from audio_synth import audio_mgr
                audio_mgr.play('creature_call', volume=1.0)
            except Exception:
                pass

        print(f"[Jumpscare] TRIGGERED ({self.enemy_type}, proximity={proximity:.2f})")
        return 2.0

    def update(self, dt):
        if not self.active:
            return False
        self.timer += dt
        if self.timer >= self.duration:
            self.active = False
            return False
        return True

    def is_playing(self):
        return self.active

    # ── helpers ───────────────────────────────────────────────────────────
    def _noise_frames_for(self, w, h):
        key = (w, h)
        frames = self._noise_frames.get(key)
        if frames is None:
            frames = []
            for _ in range(5):
                arr = np.random.randint(0, 255, (w, h, 3), dtype=np.uint8)
                surf = pygame.Surface((w, h))
                pygame.surfarray.blit_array(surf, arr)
                frames.append(surf)
            self._noise_frames[key] = frames
        return frames

    def _draw_face(self, surf, cx, cy, size, theme, eye_scale=1.0, open_frac=1.0):
        """Procedural horror face: skull ellipse, glowing eyes, jagged maw."""
        w, h = surf.get_size()
        fw, fh = size, int(size * 1.15)
        x0, y0 = int(cx - fw / 2), int(cy - fh / 2)

        # head
        pygame.draw.ellipse(surf, theme['skin'], (x0, y0, fw, fh))
        # gaunt cheek shading
        shade = tuple(max(0, c - 18) for c in theme['skin'])
        pygame.draw.ellipse(surf, shade, (x0 + fw * 0.12, y0 + fh * 0.30, fw * 0.76, fh * 0.62))

        # eye sockets + glow
        er = max(2, int(fw * 0.085 * eye_scale))
        for fx in (0.34, 0.66):
            ex, ey = int(x0 + fw * fx), int(y0 + fh * 0.40)
            pygame.draw.circle(surf, (8, 4, 4), (ex, ey), er + 3)
            pulse = 1.0 + 0.35 * math.sin(self.timer * 40.0)
            pygame.draw.circle(surf, theme['glow'], (ex, ey), max(1, int(er * pulse)))
            pygame.draw.circle(surf, theme['eye'], (ex, ey), max(1, int(er * 0.45 * pulse)))

        # jagged mouth
        mw, mh = fw * 0.5, fh * 0.30 * open_frac
        mx, my = x0 + fw * 0.25, y0 + fh * 0.62
        pygame.draw.ellipse(surf, theme['mouth'], (int(mx), int(my), int(mw), int(mh)))
        teeth = max(3, int(6 * open_frac))
        for i in range(teeth + 1):
            tx = mx + mw * i / teeth
            pygame.draw.polygon(surf, (225, 220, 205), [
                (int(tx), int(my)),
                (int(tx + mw / teeth * 0.4), int(my)),
                (int(tx + mw / teeth * 0.2), int(my + mh * 0.45)),
            ])

    # ── render ────────────────────────────────────────────────────────────
    def render(self, surface):
        """Render the sequence on top of the current frame (applies its own shake)."""
        if not self.active or self.timer < 0:
            return 0
        t = self.timer
        w, h = surface.get_size()
        theme = self.theme

        if self._fx is None or self._fx.get_size() != (w, h):
            self._fx = pygame.Surface((w, h), pygame.SRCALPHA)

        shake_x, shake_y = self._compose(surface, t, w, h, theme)

        # apply whole-frame shake (v1 returned this but main.py never used it)
        if shake_x or shake_y:
            frame = surface.copy()
            surface.fill((0, 0, 0))
            surface.blit(frame, (shake_x, shake_y))
        return 0

    def _compose(self, surface, t, w, h, theme):
        fx = self._fx
        shake_x = shake_y = 0
        k = INTENSITY

        # ── Phase 0: subliminal pre-flashes (2 one-frame pops) ────────────
        if t < self.t_rush:
            if int(t * 30) % 2 == 0:
                fx.fill((0, 0, 0, 255))
                jx = self._rng.randint(-w // 8, w // 8)
                jy = self._rng.randint(-h // 8, h // 8)
                self._draw_face(fx, w // 2 + jx, h // 2 + jy, int(w * 0.9),
                                theme, eye_scale=1.6, open_frac=0.6)
                surface.blit(fx, (0, 0))
                fx.fill((0, 0, 0, 0))
            shake_x = self._rng.randint(-6, 6)
            shake_y = self._rng.randint(-6, 6)
            return shake_x, shake_y

        # ── Phase 1: accelerating lunge with jump-cuts ──────────────────────
        if t < self.t_impact:
            p = (t - self.t_rush) / max(0.01, (self.t_impact - self.t_rush))
            ease = p * p * (1.4 + 0.6 * k)                    # ease-in: real lunge feel
            size = w * (0.25 + 1.9 * ease) * (1.0 + 0.15 * self._proximity)

            # jump-cut: 12 hard cuts/sec, each with a new offset
            cut = int(t * 12.0)
            self._rng.seed(cut * 7919)
            jx = self._rng.randint(-int(w * 0.04), int(w * 0.04)) * (1.0 - p)
            jy = self._rng.randint(-int(h * 0.04), int(h * 0.04)) * (1.0 - p)
            cx, cy = w // 2 + jx, h // 2 + jy

            fx.fill((0, 0, 0, 235))
            if ABERRATION_ENABLED:
                # RGB-split: red & cyan ghosts scaled by approach velocity
                split = int(3 + 14 * p * k)
                ghost = pygame.Surface((w, h), pygame.SRCALPHA)
                self._draw_face(ghost, cx - split, cy, int(size),
                                dict(theme, glow=(255, 0, 0), eye=(255, 0, 0),
                                     skin=(0, 0, 0), mouth=(0, 0, 0)), 1.0 + p)
                fx.blit(ghost, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
                ghost.fill((0, 0, 0, 0))
                self._draw_face(ghost, cx + split, cy, int(size),
                                dict(theme, glow=(0, 255, 255), eye=(0, 220, 220),
                                     skin=(0, 0, 0), mouth=(0, 0, 0)), 1.0 + p)
                fx.blit(ghost, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

            self._draw_face(fx, cx, cy, int(size), theme,
                            eye_scale=1.0 + 0.8 * p, open_frac=min(1.0, 0.4 + p))

            # 13 Hz edge strobe
            strobe = 0.5 + 0.5 * math.sin(t * STROBE_HZ * math.pi * 2)
            edge = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(edge, (120, 0, 0, int(90 * strobe * p)), (0, 0, w, h), max(2, w // 22))
            fx.blit(edge, (0, 0))

            if STATIC_ENABLED:
                nf = self._noise_frames_for(w, h)
                static = nf[int(t * 30) % len(nf)]
                fx.blit(static, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
                fx.fill((255, 255, 255, 26), special_flags=pygame.BLEND_RGBA_MULT)

            surface.blit(fx, (0, 0))
            fx.fill((0, 0, 0, 0))

            amp = int((4 + 26 * p) * k)
            shake_x = self._rng.randint(-amp, amp)
            shake_y = self._rng.randint(-amp, amp)
            return shake_x, shake_y

        # ── Phase 2: impact white-out + full-static burst ───────────────────
        if t < self.t_burst:
            p = (t - self.t_impact) / max(0.01, (self.t_burst - self.t_impact))
            flash = pygame.Surface((w, h), pygame.SRCALPHA)
            col = (255, 255, 255) if p < 0.5 else (255, 120, 110)
            flash.fill((*col, int(255 * (1.0 - p))))
            surface.blit(flash, (0, 0))
            if STATIC_ENABLED and p < 0.35:
                nf = self._noise_frames_for(w, h)
                surface.blit(nf[self._rng.randrange(len(nf))], (0, 0),
                             special_flags=pygame.BLEND_RGB_ADD)
            shake_x = self._rng.randint(-14, 14)
            shake_y = self._rng.randint(-14, 14)
            return shake_x, shake_y

        # ── Phase 3: after-image linger, fade to black through deep red ─────
        p = (t - self.t_burst) / max(0.01, (self.duration - self.t_burst))
        linger = max(0.0, 1.0 - p * 2.2)
        if linger > 0.0 and int(t * 9) % 2 == 0:
            fx.fill((0, 0, 0, 0))
            self._draw_face(fx, w // 2, h // 2, int(w * 2.1), theme,
                            eye_scale=1.2, open_frac=1.0)
            fx.set_alpha(int(70 * linger))
            surface.blit(fx, (0, 0))
            fx.set_alpha(255)
        red = pygame.Surface((w, h), pygame.SRCALPHA)
        red.fill((40, 0, 0, int(200 * p)))
        surface.blit(red, (0, 0))
        black = pygame.Surface((w, h), pygame.SRCALPHA)
        black.fill((0, 0, 0, int(255 * max(0.0, p - 0.25) / 0.75)))
        surface.blit(black, (0, 0))
        return 0, 0


_jumpscare_manager = None


def get_jumpscare_manager():
    """Get or create the global jumpscare manager."""
    global _jumpscare_manager
    if _jumpscare_manager is None:
        _jumpscare_manager = JumpscareManager()
    return _jumpscare_manager
