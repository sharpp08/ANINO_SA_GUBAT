"""Main-menu soundtrack playback for ANINO SA GUBAT.

Place the supplied "Hawig ng Buhay.mp3" file in assets/audio/.
Uses pygame.mixer.music for streamed playback so the two-minute track does
not need to be decoded into a large in-memory Sound object.
"""
import os

import pygame


class MenuMusic:
    TRACK_NAME = "Hawig ng Buhay.mp3"
    VOLUME_SCALE = 0.55
    FADE_IN_MS = 1800
    FADE_OUT_MS = 1200

    def __init__(self):
        self.path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "assets", "audio", self.TRACK_NAME,
        )
        self._loaded = False
        self._active = False
        self._missing_logged = False
        self._gain = 0.4

    @staticmethod
    def _clamp(value):
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    def set_volume(self, music_gain):
        """Apply the live Master x Music settings with menu-mix headroom."""
        self._gain = self._clamp(music_gain)
        if self._active:
            try:
                pygame.mixer.music.set_volume(self._gain * self.VOLUME_SCALE)
            except pygame.error:
                pass

    def _load(self):
        if self._loaded:
            return True
        if not os.path.isfile(self.path):
            if not self._missing_logged:
                print(
                    "[MENU MUSIC] Track not found. Copy "
                    f"{self.TRACK_NAME!r} into assets/audio/."
                )
                self._missing_logged = True
            return False
        try:
            pygame.mixer.music.load(self.path)
            self._loaded = True
            print(f"[MENU MUSIC] Loaded {self.TRACK_NAME}.")
            return True
        except (pygame.error, OSError) as exc:
            print(f"[MENU MUSIC] Could not load soundtrack: {exc}")
            return False

    def set_active(self, active):
        """Start/restart on menu entry; softly fade out when leaving the menu."""
        active = bool(active)
        if active:
            if self._active and pygame.mixer.music.get_busy():
                return
            if not self._load():
                self._active = False
                return
            try:
                pygame.mixer.music.set_volume(self._gain * self.VOLUME_SCALE)
                pygame.mixer.music.play(loops=-1, fade_ms=self.FADE_IN_MS)
                self._active = True
            except pygame.error as exc:
                self._active = False
                print(f"[MENU MUSIC] Playback failed: {exc}")
            return

        if self._active:
            self._active = False
            try:
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.fadeout(self.FADE_OUT_MS)
            except pygame.error:
                pass
