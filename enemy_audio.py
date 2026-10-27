"""Unique procedural audio profiles for every enemy type."""
import math
import zlib

import numpy as np
import pygame

from audio_synth import audio_mgr


ENEMY_AUDIO_PROFILES = {
    'aswang': {
        'base_hz': 95,
        'duration': 1.20,
        'harmonics': (1.0, 0.60, 0.30),
        'noise': 0.32,
        'vibrato': 7.0,
        'pulse_hz': 8.0,
        'pulse_depth': 0.35,
        'reverb': 0.25,
        'echo_ms': 90,
        'shape': 'growl',
        'gain': 0.90,
    },
    'manananggal': {
        'base_hz': 410,
        'duration': 1.35,
        'harmonics': (0.80, 0.55, 0.45),
        'noise': 0.12,
        'vibrato': 11.0,
        'pulse_hz': 3.0,
        'pulse_depth': 0.10,
        'reverb': 0.42,
        'echo_ms': 135,
        'shape': 'shriek',
        'gain': 0.72,
    },
    'tikbalang': {
        'base_hz': 145,
        'duration': 1.10,
        'harmonics': (1.0, 0.35, 0.20),
        'noise': 0.20,
        'vibrato': 5.0,
        'pulse_hz': 6.0,
        'pulse_depth': 0.65,
        'reverb': 0.30,
        'echo_ms': 105,
        'shape': 'bray',
        'gain': 0.85,
    },
    'kapre': {
        'base_hz': 52,
        'duration': 1.65,
        'harmonics': (1.0, 0.45, 0.15),
        'noise': 0.24,
        'vibrato': 2.5,
        'pulse_hz': 2.0,
        'pulse_depth': 0.25,
        'reverb': 0.38,
        'echo_ms': 180,
        'shape': 'boom',
        'gain': 1.00,
    },
    'white_lady': {
        'base_hz': 520,
        'duration': 1.80,
        'harmonics': (0.90, 0.20, 0.35),
        'noise': 0.08,
        'vibrato': 4.5,
        'pulse_hz': 1.5,
        'pulse_depth': 0.08,
        'reverb': 0.52,
        'echo_ms': 220,
        'shape': 'wail',
        'gain': 0.62,
    },
    'multo': {
        'base_hz': 245,
        'duration': 1.55,
        'harmonics': (0.80, 0.40, 0.25),
        'noise': 0.10,
        'vibrato': 3.5,
        'pulse_hz': 2.0,
        'pulse_depth': 0.12,
        'reverb': 0.48,
        'echo_ms': 165,
        'shape': 'spectral',
        'gain': 0.68,
    },
    'sigbin': {
        'base_hz': 290,
        'duration': 0.75,
        'harmonics': (0.70, 0.50, 0.35),
        'noise': 0.26,
        'vibrato': 14.0,
        'pulse_hz': 18.0,
        'pulse_depth': 0.80,
        'reverb': 0.18,
        'echo_ms': 55,
        'shape': 'chitter',
        'gain': 0.75,
    },
}

ENEMY_AUDIO_EVENTS = {
    'alert': {
        'time': 1.00, 'pitch': 1.00, 'sweep': -0.25, 'gain': 0.80,
    },
    'attack': {
        'time': 0.38, 'pitch': 1.30, 'sweep': 0.35, 'gain': 1.00,
    },
    'hurt': {
        'time': 0.30, 'pitch': 1.55, 'sweep': 0.20, 'gain': 0.70,
    },
    'death': {
        'time': 1.20, 'pitch': 0.75, 'sweep': -0.60, 'gain': 0.90,
    },
    'jumpscare': {
        'time': 0.85, 'pitch': 1.15, 'sweep': 0.50, 'gain': 1.00,
    },
}


class EnemyAudioManager:
    def __init__(self):
        mixer_init = pygame.mixer.get_init()
        self.rate = mixer_init[0] if mixer_init else 44100
        self.sounds = {}
        self._generate_sounds()

    def _synthesize(self, enemy_type, event_name):
        profile = ENEMY_AUDIO_PROFILES[enemy_type]
        event = ENEMY_AUDIO_EVENTS[event_name]

        duration = max(0.08, profile['duration'] * event['time'])
        count = max(1, int(self.rate * duration))
        t = np.arange(count, dtype=np.float64) / self.rate
        progress = t / duration

        # Pitch contour and vibrato.
        base_hz = profile['base_hz'] * event['pitch']
        frequency = base_hz * (1.0 + event['sweep'] * progress)
        frequency *= (
            1.0
            + 0.035 * np.sin(2 * np.pi * profile['vibrato'] * t)
        )
        frequency = np.maximum(20.0, frequency)
        phase = 2 * np.pi * np.cumsum(frequency) / self.rate

        # Individual harmonic signature.
        wave = np.zeros(count, dtype=np.float64)
        for index, amplitude in enumerate(profile['harmonics']):
            wave += amplitude * np.sin(
                (index + 1) * phase + index * 0.17
            )

        # Additional per-creature timbre.
        shape = profile['shape']
        if shape == 'growl':
            wave += 0.45 * np.tanh(3.0 * np.sin(0.5 * phase))
        elif shape == 'shriek':
            wave += 0.35 * np.sin(3.01 * phase)
        elif shape in ('bray', 'boom'):
            wave = np.tanh(1.8 * wave)
        elif shape == 'wail':
            wave *= 0.75 + 0.25 * np.sin(2 * np.pi * 0.7 * t)
        elif shape == 'spectral':
            wave += 0.45 * np.sin(1.013 * phase + 0.8)
        elif shape == 'chitter':
            wave = 0.55 * wave + 0.35 * np.sign(np.sin(phase))

        # Stable random seed: each sound is reproducible between runs.
        seed = zlib.crc32(
            f'{enemy_type}:{event_name}'.encode('utf-8')
        )
        rng = np.random.default_rng(seed)
        noise = rng.standard_normal(count)
        noise = np.convolve(noise, np.ones(5) / 5.0, mode='same')

        pulse = (
            1.0
            - profile['pulse_depth']
            + profile['pulse_depth']
            * (
                0.5
                + 0.5
                * np.sin(2 * np.pi * profile['pulse_hz'] * t)
            )
        )

        envelope = (
            (1.0 - np.exp(-t * 90.0))
            * np.exp(-2.0 * progress)
        )
        envelope *= np.clip((1.0 - progress) * 12.0, 0.0, 1.0)

        mono = (
            (wave + noise * profile['noise'])
            * pulse
            * envelope
        )
        mono *= 0.24 * profile['gain'] * event['gain']

        peak = float(np.max(np.abs(mono)))
        if peak > 0.95:
            mono *= 0.95 / peak

        echoed = audio_mgr._apply_reverb(
            mono,
            delay_samples=max(
                1,
                int(self.rate * profile['echo_ms'] / 1000.0),
            ),
            decay=profile['reverb'],
            num_echoes=3,
        )

        # Prevent reverb from hard-clipping the final samples.
        peak = float(np.max(np.abs(echoed)))
        if peak > 0.95:
            echoed *= 0.95 / peak

        return audio_mgr._generate_sound(echoed)

    def _generate_sounds(self):
        for enemy_type in ENEMY_AUDIO_PROFILES:
            for event_name in ENEMY_AUDIO_EVENTS:
                key = (enemy_type, event_name)
                self.sounds[key] = self._synthesize(
                    enemy_type,
                    event_name,
                )

    def play(
        self,
        enemy_type,
        event_name='alert',
        volume=1.0,
        pan=0.0,
    ):
        sound = self.sounds.get((enemy_type, event_name))
        if sound is None:
            return None

        volume = max(0.0, min(1.0, volume))
        pan = max(-1.0, min(1.0, pan))

        left = volume * (1.0 - max(0.0, pan))
        right = volume * (1.0 - max(0.0, -pan))

        try:
            channel = sound.play()
            if channel is not None:
                # Channel volume affects this playback instance only.
                channel.set_volume(left, right)
            return channel
        except Exception:
            return None

    def play_spatial(
        self,
        enemy_type,
        event_name,
        player_x,
        player_y,
        player_angle,
        target_x,
        target_y,
        base_volume=1.0,
        max_dist=15.0,
    ):
        dx = target_x - player_x
        dy = target_y - player_y
        distance = math.hypot(dx, dy)

        if max_dist <= 0.0 or distance > max_dist:
            return None

        attenuation = max(0.0, 1.0 - distance / max_dist)
        volume = base_volume * attenuation ** 1.5

        angle_diff = math.atan2(dy, dx) - player_angle
        angle_diff = (
            (angle_diff + math.pi) % (2 * math.pi) - math.pi
        )
        pan = math.sin(angle_diff)

        return self.play(
            enemy_type,
            event_name,
            volume,
            pan,
        )


enemy_audio_mgr = EnemyAudioManager()

