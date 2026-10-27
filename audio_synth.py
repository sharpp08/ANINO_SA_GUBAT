"""
Procedural audio synthesis module using NumPy and Pygame mixer.
Generates all sound effects, ambient loops, whispers, and directional 3D audio at runtime.
Enhanced with NumPy-based spatial positioning, acoustic reverb/muffling, and rich multi-harmonic texture.
"""
import pygame
import numpy as np
import random
import math

class SoundManager:
    def __init__(self):
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        except Exception:
            try:
                pygame.mixer.init(frequency=22050, size=-16, channels=2)
            except Exception:
                pass
        self.sounds = {}
        self._generate_sounds()

    def _generate_sound(self, samples_mono_or_stereo):
        if samples_mono_or_stereo.ndim == 1:
            stereo = np.column_stack((samples_mono_or_stereo, samples_mono_or_stereo))
        else:
            stereo = samples_mono_or_stereo
        stereo = np.clip(stereo * 32767, -32768, 32767).astype(np.int16)
        try:
            return pygame.mixer.Sound(buffer=stereo.tobytes())
        except Exception:
            return None

    def _apply_reverb(self, samples, delay_samples=2205, decay=0.4, num_echoes=3):
        n = len(samples)
        out = np.copy(samples)
        if out.ndim == 1:
            out = np.column_stack((out, out))
        for i in range(1, num_echoes + 1):
            d = delay_samples * i
            amp = (decay ** i)
            if d < n:
                out[d:, :] += out[:n - d, :] * amp
        return out

    def _apply_lowpass(self, samples, alpha=0.3):
        out = np.copy(samples).astype(np.float64)
        if out.ndim == 1:
            out = np.column_stack((out, out))
        n_k = min(len(out), max(8, int(8 / alpha)))
        kernel = alpha * (1 - alpha) ** np.arange(n_k)
        for ch in range(out.shape[1]):
            out[:, ch] = np.convolve(out[:, ch], kernel, mode='full')[:len(out)]
        return out

    def _generate_sounds(self):
        rate = 44100
        t = np.linspace(0, 0.4, int(rate * 0.4), endpoint=False)
        shotgun_mono = (np.sin(2 * np.pi * 90 * t) * 0.5 + np.sin(2 * np.pi * 180 * t) * 0.2) * np.exp(-t * 8) + (np.random.randn(len(t)) * 0.6 * np.exp(-t * 12))
        self.sounds['shotgun'] = self._generate_sound(self._apply_reverb(shotgun_mono, delay_samples=4410, decay=0.3))

        t_rev = np.linspace(0, 0.25, int(rate * 0.25), endpoint=False)
        revolver_mono = (np.sin(2 * np.pi * 220 * t_rev) * 0.6 + np.sin(2 * np.pi * 440 * t_rev) * 0.2) * np.exp(-t_rev * 12) + (np.random.randn(len(t_rev)) * 0.3 * np.exp(-t_rev * 20))
        self.sounds['revolver'] = self._generate_sound(self._apply_reverb(revolver_mono, delay_samples=3300, decay=0.25))

        t_bolo = np.linspace(0, 0.18, int(rate * 0.18), endpoint=False)
        bolo_mono = (np.sin(2 * np.pi * 650 * t_bolo) * 0.4 + np.sin(2 * np.pi * 1300 * t_bolo) * 0.15) * np.exp(-t_bolo * 20)
        self.sounds['bolo'] = self._generate_sound(bolo_mono)

        t_foot = np.linspace(0, 0.12, int(rate * 0.12), endpoint=False)
        foot_mono = (np.random.randn(len(t_foot)) * 0.25 * np.exp(-t_foot * 25))
        self.sounds['footstep'] = self._generate_sound(self._apply_lowpass(foot_mono, alpha=0.4))

        t_pick = np.linspace(0, 0.3, int(rate * 0.3), endpoint=False)
        pick_mono = (np.sin(2 * np.pi * 587.33 * t_pick) * 0.4 + np.sin(2 * np.pi * 880 * t_pick) * 0.2) * np.exp(-t_pick * 6)
        self.sounds['pickup'] = self._generate_sound(pick_mono)

        t_door = np.linspace(0, 0.5, int(rate * 0.5), endpoint=False)
        door_mono = (np.sin(2 * np.pi * (150 + t_door * 250) * t_door) * 0.4) * np.exp(-t_door * 4) + (np.random.randn(len(t_door)) * 0.15 * np.exp(-t_door * 8))
        self.sounds['door'] = self._generate_sound(door_mono)

        tw = np.linspace(0, 4.0, int(rate * 4.0), endpoint=False)
        wind_mono = np.random.randn(len(tw)) * 0.15 * np.exp(-tw * 0.3)
        self.sounds['intro_wind'] = self._generate_sound(self._apply_lowpass(wind_mono, alpha=0.15))

        td = np.linspace(0, 5.0, int(rate * 5.0), endpoint=False)
        drone_mono = (np.sin(2 * np.pi * 48 * td) * 0.3 + np.sin(2 * np.pi * 96 * td) * 0.15 + np.sin(2 * np.pi * 144 * td) * 0.05) * 0.8
        self.sounds['drone'] = self._generate_sound(self._apply_reverb(drone_mono, delay_samples=11025, decay=0.5, num_echoes=4))

        tc = np.linspace(0, 1.8, int(rate * 1.8), endpoint=False)
        creature_mono = (np.sin(2 * np.pi * (280 - tc * 120) * tc) * 0.35 + np.sin(2 * np.pi * (560 - tc * 240) * tc) * 0.15) * np.exp(-tc * 1.5)
        self.sounds['creature_call'] = self._generate_sound(self._apply_reverb(creature_mono, delay_samples=5500, decay=0.35))

        tf = np.linspace(0, 0.12, int(rate * 0.12), endpoint=False)
        click_mono = (np.sin(2 * np.pi * 1400 * tf) * 0.4) * np.exp(-tf * 35)
        self.sounds['flashlight_click'] = self._generate_sound(click_mono)

        tp = np.linspace(0, 0.45, int(rate * 0.45), endpoint=False)
        page_mono = np.random.randn(len(tp)) * 0.35 * np.exp(-tp * 7)
        self.sounds['page_rustle'] = self._generate_sound(self._apply_lowpass(page_mono, alpha=0.6))

        ts = np.linspace(0, 2.5, int(rate * 2.5), endpoint=False)
        sting_mono = (np.sin(2 * np.pi * 40 * ts) * 0.6 + np.sin(2 * np.pi * 80 * ts) * 0.3) * np.exp(-ts * 2.5) + (np.random.randn(len(ts)) * 0.25 * np.exp(-ts * 4))
        self.sounds['title_sting'] = self._generate_sound(self._apply_reverb(sting_mono, delay_samples=8820, decay=0.4))

        # Procedural forest ambience (crickets, owl, rustle)
        tcrik = np.linspace(0, 1.5, int(rate * 1.5), endpoint=False)
        cricket_mono = (np.sin(2 * np.pi * 4800 * tcrik) * 0.2 * (np.sin(2 * np.pi * 25 * tcrik) > 0)) * np.exp(-tcrik * 0.5)
        self.sounds['crickets'] = self._generate_sound(cricket_mono)

        towl = np.linspace(0, 1.2, int(rate * 1.2), endpoint=False)
        owl_mono = (np.sin(2 * np.pi * 380 * towl) * 0.3 + np.sin(2 * np.pi * 300 * towl) * 0.2) * np.sin(towl * math.pi / 1.2)
        self.sounds['owl'] = self._generate_sound(self._apply_reverb(owl_mono, delay_samples=4410, decay=0.4))

        trustle = np.linspace(0, 1.0, int(rate * 1.0), endpoint=False)
        rustle_mono = np.random.randn(len(trustle)) * 0.2 * np.exp(-trustle * 3.0)
        self.sounds['rustle'] = self._generate_sound(self._apply_lowpass(rustle_mono, alpha=0.5))


    def start_intro_ambience(self):
        self.play('intro_wind', 0.5)

    def stop_intro_ambience(self):
        try:
            pygame.mixer.stop()
        except Exception:
            pass

    def play_drone(self, vol=0.4):
        self.play('drone', vol)

    def play(self, name, volume=1.0, pan=0.0):
        if name in self.sounds and self.sounds[name]:
            try:
                snd = self.sounds[name]
                vol = max(0.0, min(1.0, volume))
                pan = max(-1.0, min(1.0, pan))
                left_vol = vol * (1.0 - max(0.0, pan))
                right_vol = vol * (1.0 - max(0.0, -pan))
                try:
                    snd.set_volume(left_vol, right_vol)
                except TypeError:
                    snd.set_volume(vol)
                snd.play()
            except Exception:
                pass

    def play_spatial(self, name, player_x, player_y, player_angle, target_x, target_y, base_volume=1.0, max_dist=15.0):
        dx = target_x - player_x
        dy = target_y - player_y
        dist = math.hypot(dx, dy)
        if dist > max_dist:
            return
        attenuation = max(0.0, 1.0 - (dist / max_dist))
        volume = base_volume * (attenuation ** 1.5)
        angle_to_target = math.atan2(dy, dx)
        angle_diff = angle_to_target - player_angle
        angle_diff = (angle_diff + math.pi) % (2 * math.pi) - math.pi
        pan = math.sin(angle_diff)
        self.play(name, volume=volume, pan=pan)

audio_mgr = SoundManager()
