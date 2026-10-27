import random
import math
import pygame
from settings import INTERNAL_WIDTH, INTERNAL_HEIGHT, GOLD, WHITE, BLACK, HEALTH_RED
from lore import (
    TITLE_FILIPINO, TITLE_ENGLISH, SUBTITLE_FIL, BUILD_STAMP,
    WARNING_FILIPINO, WARNING_ENGLISH,
    SCENE2_FIL, SCENE2_ENG, SCENE3_CAPTION,
    SCENE4_CAPTION, SCENE5_FIL, SCENE5_ENG,
    CLOSING_FILIPINO, CLOSING_ENGLISH, PRESS_SPACE
)
from audio_synth import audio_mgr


class Cinematic:
    def __init__(self, surf):
        self.surface = surf
        self.w = INTERNAL_WIDTH
        self.h = INTERNAL_HEIGHT
        self.duration = 75.0
        self.time = 0.0
        self.skipped = False
        self.finished = False
        self.show_skip = True  # set False when rendering to video
        try:
            pygame.font.init()
            self.font_sm = pygame.font.SysFont('consolas', 16)
            self.font_md = pygame.font.SysFont('consolas', 22, bold=True)
            self.font_lg = pygame.font.SysFont('consolas', 34, bold=True)
            self.font_tiny = pygame.font.SysFont('consolas', 12)
        except Exception:
            self.font_sm = pygame.font.Font(None, 18)
            self.font_md = pygame.font.Font(None, 24)
            self.font_lg = pygame.font.Font(None, 36)
            self.font_tiny = pygame.font.Font(None, 14)
        random.seed(1337)
        self.cues = set()
        self.stars = [(random.randint(0, self.w - 1), random.randint(0, self.h // 2), random.random()) for _ in range(60)]
        self.eyes_data = [
            (120, 140, 24.5, (255, 50, 40)),
            (320, 100, 26.0, (255, 140, 40)),
            (500, 180, 28.0, (255, 60, 40)),
            (210, 220, 30.5, (255, 160, 50)),
            (440, 120, 32.0, (255, 40, 40)),
            (580, 160, 34.5, (255, 150, 40)),
        ]
        self.pages_data = [
            (150, 80, 0.5, 2.0),
            (350, 120, 1.2, 3.5),
            (520, 90, 2.0, 1.5),
            (260, 160, 3.1, 4.0),
        ]

    def reset(self):
        self.time = 0.0
        self.skipped = False
        self.finished = False
        self.cues.clear()
        try:
            audio_mgr.start_intro_ambience()
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
        try:
            if 0.5 <= t < 1.0 and 1 not in self.cues:
                self.cues.add(1); audio_mgr.play('intro_wind', 0.6)
            elif 12.0 <= t < 12.5 and 2 not in self.cues:
                self.cues.add(2); audio_mgr.play_drone(0.4)
            elif 26.0 <= t < 26.5 and 3 not in self.cues:
                self.cues.add(3); audio_mgr.play('creature_call', 0.7)
            elif 41.0 <= t < 41.5 and 4 not in self.cues:
                self.cues.add(4); audio_mgr.play('flashlight_click', 0.8)
            elif 56.0 <= t < 56.5 and 5 not in self.cues:
                self.cues.add(5); audio_mgr.play('page_rustle', 0.7)
            elif 64.5 <= t < 65.0 and 6 not in self.cues:
                self.cues.add(6); audio_mgr.play('title_sting', 1.0)
        except Exception:
            pass
        return False

    def render(self):
        t = self.time
        self.surface.fill((2, 2, 8))
        if t < 10.0:
            self._render_scene_1(t)
        elif t < 24.0:
            self._render_scene_2(t - 10.0)
        elif t < 38.0:
            self._render_scene_3(t - 24.0)
        elif t < 52.0:
            self._render_scene_4(t - 38.0)
        elif t < 64.0:
            self._render_scene_5(t - 52.0)
        else:
            self._render_scene_6(t - 64.0)

        self._draw_overlays(t)
        if self.show_skip:
            skip = self.font_tiny.render("[Press Space / Enter to Skip]", True, (140, 140, 140))
            self.surface.blit(skip, (self.w - skip.get_width() - 10, 10))

    def _draw_txt(self, text, font, color, pos):
        txt = font.render(text, True, color)
        shd = font.render(text, True, BLACK)
        rect = txt.get_rect(center=pos)
        self.surface.blit(shd, (rect.x + 1, rect.y + 1))
        self.surface.blit(txt, rect)

    def _render_scene_1(self, st):
        self.surface.fill((1, 1, 3))
        pulse = (math.sin(st * 3.0) + 1.0) * 0.5
        vig_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        pygame.draw.rect(vig_surf, (180, 20, 20, int(30 + pulse * 45)), (0, 0, self.w, self.h), 18)
        self.surface.blit(vig_surf, (0, 0))
        self._draw_txt(WARNING_FILIPINO, self.font_md, (245, 245, 250), (self.w // 2, self.h // 2 - 20))
        if st > 3.0:
            self._draw_txt(WARNING_ENGLISH, self.font_sm, (180, 160, 150), (self.w // 2, self.h // 2 + 25))
        stamp = self.font_tiny.render(BUILD_STAMP, True, (90, 90, 100))
        self.surface.blit(stamp, (12, self.h - 22))

    def _render_scene_2(self, st):
        self.surface.fill((8, 12, 22))
        for sx, sy, brightness in self.stars:
            twinkle = max(0, min(255, int(150 + 105 * math.sin(st * 4.0 + sx))))
            self.surface.set_at((sx, sy), (twinkle, twinkle, min(255, twinkle + 20)))
        moon_x = self.w - 120 + int(st * 0.5)
        moon_y = 60 + int(math.sin(st * 0.2) * 5)
        pygame.draw.circle(self.surface, (220, 230, 245), (moon_x, moon_y), 28)
        glow = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(glow, (220, 230, 255, 30), (40, 40), 38)
        self.surface.blit(glow, (moon_x - 40, moon_y - 40))
        pan_offset = int(st * 6) % self.w
        for layer in range(3):
            col = (12 - layer * 3, 18 - layer * 4, 32 - layer * 6)
            for i in range(-1, 8):
                tx = i * 90 - (pan_offset * (layer + 1) // 2) % 90
                th = 120 + layer * 35 + (i * 17) % 45
                pygame.draw.rect(self.surface, col, (tx + 20, self.h - th, 14, th))
                pygame.draw.polygon(self.surface, col, [(tx + 10, self.h - th + 30), (tx + 27, self.h - th - 20), (tx + 44, self.h - th + 30)])
        fog_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        for fx in range(-50, self.w + 50, 40):
            foff = fx + int(math.sin(st + fx * 0.05) * 20)
            pygame.draw.ellipse(fog_surf, (150, 160, 180, 25), (foff, self.h - 70, 120, 45))
        self.surface.blit(fog_surf, (0, 0))
        if st > 2.0:
            self._draw_txt(SCENE2_FIL, self.font_lg, (240, 240, 245), (self.w // 2, self.h // 2 - 10))
        if st > 7.0:
            self._draw_txt(SCENE2_ENG, self.font_sm, (180, 190, 200), (self.w // 2, self.h // 2 + 30))

    def _render_scene_3(self, st):
        self.surface.fill((12, 6, 20))
        fog_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        pygame.draw.rect(fog_surf, (30, 20, 40, 100), (0, 0, self.w, self.h))
        self.surface.blit(fog_surf, (0, 0))
        pulse_alpha = 0
        for ex, ey, appear_t, ecolor in self.eyes_data:
            if st >= appear_t - 24.0 + 0.0 and False:
                pass
        # eye appear times are stored as absolute seconds (24.5 ...), convert to scene time
        for ex, ey, appear_abs, ecolor in self.eyes_data:
            appear_t = appear_abs - 24.0
            if st >= appear_t:
                age = st - appear_t
                if age < 0.6:
                    pulse_alpha = max(pulse_alpha, int(120 * (1.0 - age / 0.6)))
                eye_glow = pygame.Surface((24, 12), pygame.SRCALPHA)
                pygame.draw.circle(eye_glow, ecolor, (6, 6), 3)
                pygame.draw.circle(eye_glow, ecolor, (18, 6), 3)
                pygame.draw.circle(eye_glow, (ecolor[0], ecolor[1], ecolor[2], 50), (6, 6), 7)
                pygame.draw.circle(eye_glow, (ecolor[0], ecolor[1], ecolor[2], 50), (18, 6), 7)
                self.surface.blit(eye_glow, (ex - 12, ey - 6))
        if pulse_alpha > 0:
            flash = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            flash.fill((200, 20, 20, pulse_alpha))
            self.surface.blit(flash, (0, 0))
        if st > 1.0:
            self._draw_txt(SCENE3_CAPTION, self.font_sm, (230, 180, 170), (self.w // 2, 45))

    def _render_scene_4(self, st):
        self.surface.fill((10, 12, 16))
        sway = math.sin(st * 4.0) * 45
        beam_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        center_x = self.w // 2 + int(sway)
        pygame.draw.polygon(beam_surf, (255, 235, 180, 60), [
            (self.w // 2, self.h),
            (center_x - 90, 40),
            (center_x + 90, 40)
        ])
        self.surface.blit(beam_surf, (0, 0))
        if 4.0 < st < 8.0:
            sil_surf = pygame.Surface((40, 80), pygame.SRCALPHA)
            pygame.draw.rect(sil_surf, (20, 20, 25, 200), (10, 0, 20, 80))
            self.surface.blit(sil_surf, (self.w // 2 + int(sway * 0.5) - 20, self.h // 2 - 20))
        if st > 1.0:
            self._draw_txt(SCENE4_CAPTION, self.font_sm, (180, 200, 190), (self.w // 2, 40))

    def _render_scene_5(self, st):
        self.surface.fill((12, 14, 18))
        for px, py, p_speed, p_rot in self.pages_data:
            curr_y = (py + int(st * 15 * p_speed)) % (self.h + 40) - 20
            curr_x = px + int(math.sin(st * p_rot) * 35)
            page_surf = pygame.Surface((28, 36), pygame.SRCALPHA)
            page_surf.fill((255, 220, 130, 220))
            halo = pygame.Surface((60, 60), pygame.SRCALPHA)
            pygame.draw.circle(halo, (255, 240, 180, 40), (30, 30), 28)
            self.surface.blit(halo, (curr_x - 16, curr_y - 12))
            self.surface.blit(page_surf, (curr_x, curr_y))
        if st > 1.0:
            self._draw_txt(SCENE5_FIL, self.font_md, (255, 240, 200), (self.w // 2, self.h - 75))
            self._draw_txt(SCENE5_ENG, self.font_sm, (200, 180, 150), (self.w // 2, self.h - 45))

    def _render_scene_6(self, st):
        self.surface.fill((2, 2, 5))
        if st < 0.8:
            flash_alpha = int(255 * (1.0 - st / 0.8))
            fl = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            fl.fill((255, 255, 255, flash_alpha))
            self.surface.blit(fl, (0, 0))
        shake_x = random.randint(-3, 3) if st < 0.8 else 0
        shake_y = random.randint(-3, 3) if st < 0.8 else 0
        self._draw_txt(TITLE_FILIPINO, self.font_lg, GOLD, (self.w // 2 + shake_x, self.h // 2 - 30 + shake_y))
        if st > 1.5:
            self._draw_txt(SUBTITLE_FIL, self.font_md, HEALTH_RED, (self.w // 2, self.h // 2 + 15))
        if st > 3.5:
            if int(st * 2) % 2 == 0:
                self._draw_txt(PRESS_SPACE, self.font_sm, WHITE, (self.w // 2, self.h - 60))

    def _draw_overlays(self, t):
        pygame.draw.rect(self.surface, BLACK, (0, 0, self.w, 28))
        pygame.draw.rect(self.surface, BLACK, (0, self.h - 28, self.w, 28))
        vig = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        pygame.draw.rect(vig, (0, 0, 0, 80), (0, 0, self.w, self.h), 12)
        self.surface.blit(vig, (0, 0))
