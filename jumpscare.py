"""
Jumpscare System v3 - an INDIVIDUAL jumpscare for every enemy.

Same public API as before: get_jumpscare_manager(), trigger(enemy_type, distance),
update(dt), render(surface), is_playing(). main.py needs no changes.

Every enemy now has its own:
  * BODY      - its own pixel-art attack sprite (assets/sprites/enemies/<type>_attack.png)
                scaled up crisp; falls back to a procedural face if the sprite is missing.
  * MOTION    - aswang rises from below, manananggal swoops in on wings, tikbalang gallops
                in from the side, kapre looms slow and heavy, white_lady teleports in
                stutter-steps, multo phases/flickers, sigbin pounces in an arc.
  * EFFECTS   - aswang blood drips, manananggal wing-flap, tikbalang speed trails, kapre
                smoke + cigar ember, white_lady falling hair, multo ghost-split + flicker,
                sigbin leap trails.  Each has its own flash colour and timing.
  * SOUND     - drop a file named  <enemy>_jumpscare.wav / .ogg / .mp3  into
                enemy_animations_pack/  and it is used for that enemy (multo already has
                one).  Otherwise that enemy's own synthesized 'jumpscare' cry is used
                (every enemy has a different voice), layered with a short stinger.

Common layers kept from v2: RGB-split aberration, 13 Hz edge strobe, film static,
whole-frame trauma shake, impact flash, after-image fade. Every audio / sprite step is
wrapped so a missing file can never crash the game.
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
AUDIO_EXTS = ('.wav', '.ogg', '.mp3')


# ── per-enemy style ───────────────────────────────────────────────────────────
# rush   : seconds of subliminal flicker before the lunge
# impact : time at which the lunge ends and the flash hits
# tail   : seconds of after-image fade after the flash
# flash  : impact flash colour
# trail  : number of motion-trail ghosts behind the body
# shake  : trauma-shake multiplier
STYLES = {
    'aswang':      dict(rush=0.12, impact=0.52, tail=0.70, flash=(255, 70, 55),  trail=1, shake=1.25),
    'manananggal': dict(rush=0.12, impact=0.60, tail=0.70, flash=(255, 110, 130), trail=2, shake=1.0),
    'tikbalang':   dict(rush=0.10, impact=0.50, tail=0.65, flash=(255, 190, 60),  trail=3, shake=1.3),
    'kapre':       dict(rush=0.15, impact=0.75, tail=0.75, flash=(255, 140, 40),  trail=0, shake=1.5),
    'white_lady':  dict(rush=0.14, impact=0.70, tail=0.80, flash=(190, 215, 255), trail=0, shake=0.8),
    'multo':       dict(rush=0.12, impact=0.58, tail=0.75, flash=(160, 190, 255), trail=3, shake=0.9),
    'sigbin':      dict(rush=0.08, impact=0.42, tail=0.65, flash=(255, 90, 30),   trail=3, shake=1.3),
}


def _clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def style_pose(etype, p):
    """Pure motion function. p in [0,1] = lunge progress.
    Returns (nx, ny, height_scale, rotation_deg, x_stretch, alpha)
    nx/ny are the sprite centre as a fraction of the screen, height_scale is the
    sprite height as a multiple of the screen height."""
    e = p * p
    if etype == 'aswang':        # crawls up out of the dark, head jerking
        return (0.5 + 0.015 * math.sin(p * 55), 0.78 - 0.28 * e,
                0.50 + 1.60 * e, 7.0 * math.sin(p * 31), 1.0, 255)
    if etype == 'manananggal':   # swoops down diagonally, wings flapping
        return (0.18 + 0.32 * e + 0.05 * math.sin(p * 13), 0.12 + 0.38 * e + 0.03 * math.cos(p * 11),
                0.42 + 1.55 * e, -14.0 * (1.0 - e) + 7.0 * math.sin(p * 21),
                1.0 + 0.16 * math.sin(p * 46), 255)
    if etype == 'tikbalang':     # gallops in from the right, hooves bobbing
        return (1.05 - 0.55 * (p ** 1.4), 0.55 + 0.05 * abs(math.sin(p * 20)),
                0.50 + 1.55 * e, -6.0 * math.sin(p * 20), 1.0, 255)
    if etype == 'kapre':         # slow, heavy, unstoppable
        return (0.5 + 0.01 * math.sin(p * 9), 0.50 + 0.05 * math.sin(p * 7),
                0.40 + 1.90 * (p ** 1.6), 0.0, 1.0, 255)
    if etype == 'white_lady':    # teleports closer in stuttering steps
        steps = 6
        q = (math.floor(p * steps) + 0.18 * ((p * steps) % 1.0)) / steps
        return (0.5, 0.5, 0.34 + 1.75 * (q ** 1.15), 0.0, 1.0, 255)
    if etype == 'multo':         # drifts, phases in and out of reality
        flick = 175 + 80 * math.sin(p * 48)
        return (0.5 + 0.09 * math.sin(p * 26), 0.5 + 0.05 * math.sin(p * 17 + 1.0),
                0.45 + 1.65 * e, 0.0, 1.0, int(_clamp(flick, 70, 255)))
    if etype == 'sigbin':        # pounces in a high arc from the lower left
        return (0.22 + 0.28 * e, 0.92 - 0.42 * e - 0.38 * math.sin(math.pi * e),
                0.32 + 1.95 * (e ** 1.15), -22.0 * (1.0 - e), 1.0, 255)
    return (0.5, 0.5, 0.25 + 1.9 * e, 0.0, 1.0, 255)


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
        self.enemy_type = 'aswang'
        self.theme = self.THEMES['aswang']
        self.style = STYLES['aswang']
        self.scream_sound = None
        self.stinger_sound = None
        self.enemy_sounds = {}    # enemy_type -> custom jumpscare Sound (from files)
        self._sprites = {}        # enemy_type -> cropped base sprite Surface
        self._noise_frames = {}   # (w,h) -> [surface, ...]
        self._fx = None           # reusable fx surface
        self._rng = random.Random()
        self._proximity = 0.0
        self._set_timing(self.style)

        self._load_assets()

    def _set_timing(self, style):
        k = INTENSITY
        self.t_rush = style['rush']
        self.t_impact = style['impact'] / min(k, 1.3)
        self.t_burst = self.t_impact + 0.10
        self.t_fade = self.t_burst + 0.25
        self.duration = self.t_fade + (style['tail'] / k)

    # ── assets ────────────────────────────────────────────────────────────
    def _load_assets(self):
        pack_dir = os.path.join(BASE_PATH, 'enemy_animations_pack')

        # generic fallback audio
        for name, attr in (('jumpscare_scream.wav', 'scream_sound'),
                           ('jumpscare_stinger.wav', 'stinger_sound')):
            path = os.path.join(pack_dir, name)
            if os.path.exists(path):
                try:
                    setattr(self, attr, pygame.mixer.Sound(path))
                    print(f"[Jumpscare] Loaded audio: {path}")
                except Exception as e:
                    print(f"[Jumpscare] Failed to load {name}: {e}")

        # enemy-specific audio: <enemy>_jumpscare.(wav|ogg|mp3)
        for etype in self.THEMES:
            for ext in AUDIO_EXTS:
                path = os.path.join(pack_dir, f"{etype}_jumpscare{ext}")
                if not os.path.exists(path):
                    continue
                try:
                    self.enemy_sounds[etype] = pygame.mixer.Sound(path)
                    print(f"[Jumpscare] Loaded {etype} audio: {path}")
                    break
                except Exception as e:
                    print(f"[Jumpscare] Failed to load {os.path.basename(path)}: {e}")

        # enemy sprites
        sprite_dir = os.path.join(BASE_PATH, 'assets', 'sprites', 'enemies')
        for etype in self.THEMES:
            path = os.path.join(sprite_dir, f"{etype}_attack.png")
            if not os.path.exists(path):
                continue
            try:
                img = pygame.image.load(path)
                try:
                    img = img.convert_alpha()
                except Exception:
                    pass
                box = img.get_bounding_rect()
                if box.width > 0 and box.height > 0:
                    img = img.subsurface(box).copy()
                self._sprites[etype] = img
            except Exception as e:
                print(f"[Jumpscare] Failed to load sprite {etype}: {e}")

    def _play(self, snd, volume):
        if snd is None:
            return
        try:
            snd.set_volume(volume)
            snd.play()
        except Exception:
            pass

    def _play_forced(self, snd, volume=1.0):
        """Play on a forced channel so the sound can never be dropped."""
        try:
            snd.set_volume(volume)
            ch = pygame.mixer.find_channel(True)
            if ch is not None:
                ch.play(snd)
            else:
                snd.play()
            return True
        except Exception as e:
            print(f"[Jumpscare] Could not play audio: {e}")
            return False

    def _play_enemy_audio(self):
        etype = self.enemy_type
        # 1) a dedicated audio file for this enemy
        custom = self.enemy_sounds.get(etype)
        if custom is not None:
            self._play_forced(custom, 1.0)
            print(f"[Jumpscare] audio: custom file for {etype} ({custom.get_length():.1f}s)")
            return
        # 2) this enemy's own synthesized jumpscare cry (+ short stinger)
        try:
            from enemy_audio import enemy_audio_mgr
            snd = enemy_audio_mgr.sounds.get((etype, 'jumpscare'))
        except Exception:
            snd = None
        if snd is not None and self._play_forced(snd, 1.0):
            self._play(self.stinger_sound, 0.6)
            print(f"[Jumpscare] audio: synthesized {etype} cry")
            return
        # 3) generic fallback
        print(f"[Jumpscare] audio: generic fallback for {etype}")
        self._play(self.scream_sound, 1.0)
        self._play(self.stinger_sound, 0.9)
        try:
            from audio_synth import audio_mgr
            audio_mgr.play('creature_call', volume=1.0)
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
        self.style = STYLES.get(self.enemy_type, STYLES['aswang'])
        self._set_timing(self.style)

        # closer killer = faster, nastier pop
        proximity = max(0.0, min(1.0, 1.0 - distance / 10.0))
        self._proximity = proximity

        self._play_enemy_audio()

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
        """Procedural horror face (fallback when an enemy has no sprite)."""
        fw, fh = size, int(size * 1.15)
        x0, y0 = int(cx - fw / 2), int(cy - fh / 2)

        pygame.draw.ellipse(surf, theme['skin'], (x0, y0, fw, fh))
        shade = tuple(max(0, c - 18) for c in theme['skin'])
        pygame.draw.ellipse(surf, shade, (x0 + fw * 0.12, y0 + fh * 0.30, fw * 0.76, fh * 0.62))

        er = max(2, int(fw * 0.085 * eye_scale))
        for fx_ in (0.34, 0.66):
            ex, ey = int(x0 + fw * fx_), int(y0 + fh * 0.40)
            pygame.draw.circle(surf, (8, 4, 4), (ex, ey), er + 3)
            pulse = 1.0 + 0.35 * math.sin(self.timer * 40.0)
            pygame.draw.circle(surf, theme['glow'], (ex, ey), max(1, int(er * pulse)))
            pygame.draw.circle(surf, theme['eye'], (ex, ey), max(1, int(er * 0.45 * pulse)))

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

    def _blit_sprite(self, dest, cx, cy, height, rot=0.0, xs=1.0, tint=None, alpha=255):
        """Draw this enemy's sprite centred at (cx, cy), `height` px tall. Returns False
        if the enemy has no sprite (caller then falls back to the procedural face)."""
        base = self._sprites.get(self.enemy_type)
        if base is None:
            return False
        s = base
        if abs(rot) > 0.5:
            s = pygame.transform.rotate(s, rot)
        ht = int(_clamp(height, 8, dest.get_height() * 2.6))
        wt = int(max(4, s.get_width() * ht / max(1, s.get_height()) * xs))
        s = pygame.transform.scale(s, (wt, ht))          # nearest = crisp pixel art
        if tint is not None:
            s = s.copy()
            s.fill((*tint, 255), special_flags=pygame.BLEND_RGBA_MULT)
        if alpha < 255:
            s.set_alpha(int(alpha))
        dest.blit(s, s.get_rect(center=(int(cx), int(cy))))
        return True

    def _draw_enemy(self, dest, w, h, p, theme, fx_scale=1.0, flicker_seed=0):
        """Body + aberration ghosts + motion trails for the lunge at progress p."""
        etype = self.enemy_type
        k = INTENSITY
        nx, ny, hs, rot, xs, alpha = style_pose(etype, p)
        prox = 1.0 + 0.15 * self._proximity
        height = hs * h * prox
        cx, cy = nx * w, ny * h
        has_sprite = etype in self._sprites

        # motion trails (earlier poses, fading)
        for i in range(self.style['trail'], 0, -1):
            pp = max(0.0, p - 0.045 * i)
            tnx, tny, ths, trot, txs, _ = style_pose(etype, pp)
            a = int(95 / i)
            if has_sprite:
                self._blit_sprite(dest, tnx * w, tny * h, ths * h * prox, trot, txs,
                                  tint=(200, 200, 255), alpha=a)

        # RGB split ghosts
        if ABERRATION_ENABLED and has_sprite:
            split = int((3 + 14 * p * k) * fx_scale)
            self._blit_sprite(dest, cx - split, cy, height, rot, xs, tint=(255, 40, 40), alpha=140)
            self._blit_sprite(dest, cx + split, cy, height, rot, xs, tint=(40, 255, 255), alpha=140)

        # the body itself
        if has_sprite:
            self._blit_sprite(dest, cx, cy, height, rot, xs, alpha=alpha)
        else:
            self._draw_face(dest, cx, cy, int(height * 0.8), theme,
                            eye_scale=1.0 + 0.8 * p, open_frac=min(1.0, 0.4 + p))
        return cx, cy, height

    def _enemy_overlay(self, dest, w, h, p, t, cx, cy, height):
        """Effects unique to each enemy, drawn over the body."""
        etype = self.enemy_type
        rng = self._rng
        if etype == 'aswang':                       # blood drips from the top
            for i in range(int(6 + 14 * p)):
                x = rng.randint(0, w)
                ln = int(h * (0.10 + 0.55 * p) * rng.random())
                pygame.draw.line(dest, (150, 5, 8), (x, 0), (x, ln), rng.randint(2, 4))
        elif etype == 'kapre':                      # cigar ember + rising smoke
            glow = 0.6 + 0.4 * math.sin(t * 22)
            ex, ey = int(cx + height * 0.30), int(cy - height * 0.10)
            pygame.draw.circle(dest, (255, int(120 * glow), 20), (ex, ey), max(3, int(height * 0.035)))
            smoke = pygame.Surface((w, h), pygame.SRCALPHA)
            for i in range(int(4 + 10 * p)):
                px = ex + rng.randint(-int(height * 0.1), int(height * 0.1)) + int(18 * math.sin(t * 5 + i))
                py = ey - int((t * 90 + i * 37) % (h * 0.6))
                r = int(height * (0.05 + 0.12 * rng.random()))
                pygame.draw.circle(smoke, (150, 150, 150, 70), (px, py), max(2, r))
            dest.blit(smoke, (0, 0))
        elif etype == 'white_lady':                 # long black hair falling over the screen
            for i in range(int(10 + 40 * p)):
                x = rng.randint(0, w)
                ln = int(h * (0.15 + 0.85 * p) * (0.4 + 0.6 * rng.random()))
                pygame.draw.line(dest, (4, 4, 8), (x, 0), (x + rng.randint(-6, 6), ln), rng.randint(1, 3))
        elif etype == 'multo':                      # horizontal ghost tearing
            for i in range(int(3 + 7 * p)):
                y = rng.randint(0, h - 6)
                band = dest.subsurface((0, y, w, min(rng.randint(3, 10), h - y))).copy()
                dest.blit(band, (rng.randint(-24, 24), y))
        elif etype == 'sigbin':                     # claw slashes
            if p > 0.55:
                for i in range(3):
                    x0 = int(w * (0.25 + 0.2 * i)) + rng.randint(-10, 10)
                    pygame.draw.line(dest, (200, 20, 10), (x0, 0), (x0 + int(w * 0.18), h),
                                     max(2, int(5 * p)))
        elif etype == 'tikbalang':                  # speed lines
            for i in range(int(6 + 12 * p)):
                y = rng.randint(0, h)
                x = rng.randint(int(w * 0.4), w)
                pygame.draw.line(dest, (255, 215, 140), (x, y), (min(w, x + int(w * 0.35)), y), 1)
        elif etype == 'manananggal':                # feathers / blood spray
            for i in range(int(4 + 10 * p)):
                x, y = rng.randint(0, w), rng.randint(0, h)
                pygame.draw.circle(dest, (170, 20, 40), (x, y), rng.randint(1, 3))

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

        if shake_x or shake_y:
            frame = surface.copy()
            surface.fill((0, 0, 0))
            surface.blit(frame, (shake_x, shake_y))
        return 0

    def _compose(self, surface, t, w, h, theme):
        fx = self._fx
        shake_x = shake_y = 0
        k = INTENSITY
        sk = self.style['shake']

        # ── Phase 0: subliminal pre-flashes ────────────────────────────────
        if t < self.t_rush:
            if int(t * 30) % 2 == 0:
                fx.fill((0, 0, 0, 255))
                jx = self._rng.randint(-w // 8, w // 8)
                jy = self._rng.randint(-h // 8, h // 8)
                nx, ny, hs, rot, xs, alpha = style_pose(self.enemy_type, 0.55)
                if not self._blit_sprite(fx, w // 2 + jx, h // 2 + jy, h * 1.1, rot, xs):
                    self._draw_face(fx, w // 2 + jx, h // 2 + jy, int(w * 0.9),
                                    theme, eye_scale=1.6, open_frac=0.6)
                surface.blit(fx, (0, 0))
                fx.fill((0, 0, 0, 0))
            shake_x = self._rng.randint(-6, 6)
            shake_y = self._rng.randint(-6, 6)
            return shake_x, shake_y

        # ── Phase 1: this enemy's own lunge ─────────────────────────────────
        if t < self.t_impact:
            p = (t - self.t_rush) / max(0.01, (self.t_impact - self.t_rush))
            p = _clamp(p)

            fx.fill((0, 0, 0, 235))
            body = pygame.Surface((w, h), pygame.SRCALPHA)
            cx, cy, height = self._draw_enemy(body, w, h, p, theme)
            fx.blit(body, (0, 0))
            self._enemy_overlay(fx, w, h, p, t, cx, cy, height)

            # edge strobe tinted with this enemy's colour
            strobe = 0.5 + 0.5 * math.sin(t * STROBE_HZ * math.pi * 2)
            edge = pygame.Surface((w, h), pygame.SRCALPHA)
            fl = self.style['flash']
            pygame.draw.rect(edge, (fl[0] // 2, fl[1] // 6, fl[2] // 6, int(90 * strobe * p)),
                             (0, 0, w, h), max(2, w // 22))
            fx.blit(edge, (0, 0))

            if STATIC_ENABLED:
                nf = self._noise_frames_for(w, h)
                static = nf[int(t * 30) % len(nf)]
                fx.blit(static, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
                fx.fill((255, 255, 255, 26), special_flags=pygame.BLEND_RGBA_MULT)

            surface.blit(fx, (0, 0))
            fx.fill((0, 0, 0, 0))

            amp = int((4 + 26 * p) * k * sk)
            shake_x = self._rng.randint(-amp, amp)
            shake_y = self._rng.randint(-amp, amp)
            return shake_x, shake_y

        # ── Phase 2: impact flash in this enemy's colour ────────────────────
        if t < self.t_burst:
            p = (t - self.t_impact) / max(0.01, (self.t_burst - self.t_impact))
            flash = pygame.Surface((w, h), pygame.SRCALPHA)
            col = (255, 255, 255) if p < 0.5 else self.style['flash']
            flash.fill((*col, int(255 * (1.0 - p))))
            surface.blit(flash, (0, 0))
            if STATIC_ENABLED and p < 0.35:
                nf = self._noise_frames_for(w, h)
                surface.blit(nf[self._rng.randrange(len(nf))], (0, 0),
                             special_flags=pygame.BLEND_RGB_ADD)
            shake_x = int(self._rng.randint(-14, 14) * sk)
            shake_y = int(self._rng.randint(-14, 14) * sk)
            return shake_x, shake_y

        # ── Phase 3: after-image linger, fade to black ──────────────────────
        p = (t - self.t_burst) / max(0.01, (self.duration - self.t_burst))
        linger = max(0.0, 1.0 - p * 2.2)
        if linger > 0.0 and int(t * 9) % 2 == 0:
            fx.fill((0, 0, 0, 0))
            nx, ny, hs, rot, xs, alpha = style_pose(self.enemy_type, 1.0)
            if not self._blit_sprite(fx, nx * w, ny * h, hs * h, rot, xs, alpha=int(70 * linger)):
                self._draw_face(fx, w // 2, h // 2, int(w * 1.1), theme,
                                eye_scale=1.2, open_frac=1.0)
                fx.set_alpha(int(70 * linger))
            surface.blit(fx, (0, 0))
            fx.set_alpha(255)
            fx.fill((0, 0, 0, 0))
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
