"""
ANINO SA GUBAT: Intro Cinematic
"""
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
        try:
            pygame.font.init()
            self.font_sm = pygame.font.SysFont('consolas', 16)
            self.font_md = pygame.font.SysFont('consolas', 22, bold=True)
            self.font_lg = pygame.font.SysFont('consolas', 32, bold=True)
            self.font_tiny = pygame.font.SysFont('consolas', 12)
        except Exception:
            self.font_sm = pygame.font.Font(None, 18)
            self.font_md = pygame.font.Font(None, 24)
            self.font_lg = pygame.font.Font(None, 34)
            self.font_tiny = pygame.font.Font(None, 14)
        random.seed(1337)
        self.cues = set()

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
                self.skipped = True; self.finished = True
                try:
                    audio_mgr.stop_intro_ambience()
                except Exception:
                    pass
                return True
        if self.finished or self.skipped: return True
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
            elif 68.0 <= t < 68.5 and 6 not in self.cues:
                self.cues.add(6); audio_mgr.play('title_sting', 1.0)
        except Exception:
            pass
        return False

    def render(self):
        t = self.time
        self.surface.fill((5, 5, 10))
        if t < 10.0: self._render_scene_1(t)
        elif t < 25.0: self._render_scene_2(t - 10.0)
        elif t < 40.0: self._render_scene_3(t - 25.0)
        elif t < 55.0: self._render_scene_4(t - 40.0)
        elif t < 70.0: self._render_scene_5(t - 55.0)
        else: self._render_scene_6(t - 70.0)
        self._draw_overlays()
        skip = self.font_tiny.render("[Press Space / Enter to Skip]", True, (150, 150, 150))
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
        moon_x = self.w - 120 + int(st * 0.5)
        moon_y = 60 + int(math.sin(st * 0.2) * 5)
        pygame.draw.circle(self.surface, (220, 230, 245), (moon_x, moon_y), 28)
        if st > 2.0:
            self._draw_txt(SCENE2_FIL, self.font_lg, (240, 240, 245), (self.w // 2, self.h // 2 - 10))
        if st > 7.0:
            self._draw_txt(SCENE2_ENG, self.font_sm, (180, 190, 200), (self.w // 2, self.h // 2 + 30))

    def _render_scene_3(self, st):
        self.surface.fill((12, 6, 20))
        pygame.draw.circle(self.surface, (220, 100, 80), (120, 80), 35)
        if st > 1.0:
            self._draw_txt(SCENE3_CAPTION, self.font_sm, (230, 180, 170), (self.w // 2, 45))

    def _render_scene_4(self, st):
        self.surface.fill((10, 12, 16))
        if st > 1.0:
            self._draw_txt(SCENE4_CAPTION, self.font_sm, (180, 200, 190), (self.w // 2, 40))

    def _render_scene_5(self, st):
        self.surface.fill((12, 14, 18))
        if st > 1.0:
            self._draw_txt(SCENE5_FIL, self.font_md, (255, 240, 200), (self.w // 2, self.h - 75))
            self._draw_txt(SCENE5_ENG, self.font_sm, (200, 180, 150), (self.w // 2, self.h - 45))

    def _render_scene_6(self, st):
        self.surface.fill((2, 2, 5))
        if st < 0.8:
            fl = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            fl.fill((255, 255, 255, int(255 * (1.0 - st / 0.8))))
            self.surface.blit(fl, (0, 0))
        shake_x = random.randint(-3, 3) if st < 0.8 else 0
        shake_y = random.randint(-3, 3) if st < 0.8 else 0
        self._draw_txt(TITLE_FILIPINO, self.font_lg, GOLD, (self.w // 2 + shake_x, self.h // 2 - 30 + shake_y))
        if st > 1.5:
            self._draw_txt(SUBTITLE_FIL, self.font_md, HEALTH_RED, (self.w // 2, self.h // 2 + 15))
        if st > 3.5:
            if int(st * 2) % 2 == 0:
                self._draw_txt(PRESS_SPACE, self.font_sm, WHITE, (self.w // 2, self.h - 60))

    def _draw_overlays(self):
        v = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        pygame.draw.rect(v, (0, 0, 0, 120), (0, 0, self.w, self.h), 15)
        self.surface.blit(v, (0, 0))
        pygame.draw.rect(self.surface, BLACK, (0, 0, self.w, 25))
        pygame.draw.rect(self.surface, BLACK, (0, self.h - 25, self.w, 25))
