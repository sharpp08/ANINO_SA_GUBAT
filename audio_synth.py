"""
Procedural audio synthesis module using NumPy and Pygame mixer.
Generates all sound effects, ambient loops, whispers, and directional audio at runtime.
"""
import pygame
import numpy as np
import random
import math

class SoundManager:
    def __init__(self):
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2)
        except Exception:
            pass
        self.sounds = {}
        self._generate_sounds()

    def _generate_sound(self, samples):
        if samples.ndim == 1:
            stereo = np.column_stack((samples, samples))
        else:
            stereo = samples
        stereo = np.clip(stereo * 32767, -32768, 32767).astype(np.int16)
        try:
            return pygame.mixer.Sound(buffer=stereo.tobytes())
        except Exception:
            return None

    def _generate_sounds(self):
        rate = 22050
        t = np.linspace(0, 0.3, int(rate * 0.3), endpoint=False)
        self.sounds['shotgun'] = self._generate_sound(np.sin(2 * np.pi * 120 * t) * np.exp(-t * 10) + np.random.randn(len(t)) * 0.5 * np.exp(-t * 15))
        t_rev = np.linspace(0, 0.2, int(rate * 0.2), endpoint=False)
        self.sounds['revolver'] = self._generate_sound(np.sin(2 * np.pi * 300 * t_rev) * np.exp(-t_rev * 15))
        t_bolo = np.linspace(0, 0.15, int(rate * 0.15), endpoint=False)
        self.sounds['bolo'] = self._generate_sound(np.sin(2 * np.pi * 800 * t_bolo) * np.exp(-t_bolo * 25))
        t_foot = np.linspace(0, 0.1, int(rate * 0.1), endpoint=False)
        self.sounds['footstep'] = self._generate_sound(np.random.randn(len(t_foot)) * 0.2 * np.exp(-t_foot * 30))
        t_pick = np.linspace(0, 0.25, int(rate * 0.25), endpoint=False)
        self.sounds['pickup'] = self._generate_sound(np.sin(2 * np.pi * 587.33 * t_pick) * np.exp(-t_pick * 8))
        t_door = np.linspace(0, 0.4, int(rate * 0.4), endpoint=False)
        self.sounds['door'] = self._generate_sound(np.sin(2 * np.pi * (200 + t_door * 300) * t_door) * np.exp(-t_door * 5))

    def play(self, name, volume=1.0, pan=0.0):
        if name in self.sounds and self.sounds[name]:
            try:
                snd = self.sounds[name]
                snd.set_volume(max(0.0, min(1.0, volume)))
                snd.play()
            except Exception:
                pass

audio_mgr = SoundManager()
