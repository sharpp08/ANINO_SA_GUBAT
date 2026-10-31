"""Unique procedural creature voices for every enemy type.

Each creature is a source-filter voice (glottal harmonics + vocal-tract
formants) with its own anatomy, so they read as living things instead of
buzzing tones:

* aswang      - rasping vocal-fry growl, chest formants, hard distortion
* manananggal - harsh amplitude-modulated shriek + leathery wing flaps
* tikbalang   - donkey/horse hee-haw: pitch flips between a high 'hee' and low 'haw'
* kapre       - huge smoky 'ho-ho-ho' laugh, each ho sinking in pitch
* white_lady  - breathy, vibrato-rich wail in a long cave-like reverb
* multo       - whispered moan, detuned and fluttering
* sigbin      - rodent-like chittering with clicks
"""
import math
import zlib

import numpy as np
import pygame

from audio_synth import (
    audio_mgr, fft_band, fft_filter, reverb, smooth_noise, synth_voice, _pk, _t,
)


ENEMY_AUDIO_PROFILES = {
    'aswang': {
        'base_hz': 95, 'duration': 1.20, 'vowel': ('a', 'o'), 'tilt': 1.1,
        'breath': 0.22, 'jitter': 0.03, 'subharm': 0.65, 'rough': (26.0, 0.45),
        'vibrato': 6.0, 'vib_depth': 0.02, 'pulse_hz': 8.0, 'pulse_depth': 0.30,
        'drive': 3.0, 'rt60': 0.9, 'wet': 0.28, 'bright': 0.4,
        'shape': 'growl', 'gain': 0.90,
    },
    'manananggal': {
        'base_hz': 410, 'duration': 1.35, 'vowel': ('i', 'a'), 'tilt': 1.0,
        'breath': 0.12, 'jitter': 0.015, 'subharm': 0.0, 'rough': (68.0, 0.40),
        'vibrato': 10.0, 'vib_depth': 0.035, 'pulse_hz': 3.0, 'pulse_depth': 0.10,
        'drive': 2.0, 'rt60': 1.5, 'wet': 0.40, 'bright': 0.6,
        'shape': 'shriek', 'flap': 0.38, 'gain': 0.75,
    },
    'tikbalang': {
        'base_hz': 150, 'duration': 1.10, 'vowel': ('e', 'a'), 'tilt': 1.2,
        'breath': 0.28, 'jitter': 0.025, 'subharm': 0.15, 'rough': (0.0, 0.0),
        'vibrato': 5.0, 'vib_depth': 0.015, 'pulse_hz': 7.0, 'pulse_depth': 0.40,
        'drive': 2.2, 'rt60': 1.1, 'wet': 0.30, 'bright': 0.5,
        'shape': 'bray', 'gain': 0.88,
    },
    'kapre': {
        'base_hz': 62, 'duration': 1.65, 'vowel': ('o', 'u'), 'tilt': 1.3,
        'breath': 0.18, 'jitter': 0.02, 'subharm': 0.30, 'rough': (0.0, 0.0),
        'vibrato': 2.5, 'vib_depth': 0.015, 'pulse_hz': 2.0, 'pulse_depth': 0.0,
        'drive': 1.6, 'rt60': 1.8, 'wet': 0.38, 'bright': 0.25,
        'shape': 'boom', 'gain': 1.00,
    },
    'white_lady': {
        'base_hz': 520, 'duration': 1.80, 'vowel': ('o', 'a'), 'tilt': 1.9,
        'breath': 0.30, 'jitter': 0.004, 'subharm': 0.0, 'rough': (0.0, 0.0),
        'vibrato': 5.0, 'vib_depth': 0.04, 'pulse_hz': 0.8, 'pulse_depth': 0.18,
        'drive': 1.0, 'rt60': 3.0, 'wet': 0.55, 'bright': 0.3,
        'shape': 'wail', 'chorus': 14, 'gain': 0.66,
    },
    'multo': {
        'base_hz': 245, 'duration': 1.55, 'vowel': ('u', 'o'), 'tilt': 2.2,
        'breath': 0.20, 'jitter': 0.01, 'subharm': 0.0, 'rough': (0.0, 0.0),
        'whisper': 0.55, 'vibrato': 3.5, 'vib_depth': 0.02, 'pulse_hz': 9.0,
        'pulse_depth': 0.25, 'drive': 1.0, 'rt60': 2.4, 'wet': 0.55, 'bright': 0.2,
        'shape': 'spectral', 'chorus': -22, 'gain': 0.70,
    },
    'sigbin': {
        'base_hz': 300, 'duration': 0.75, 'vowel': ('i', 'e'), 'tilt': 1.2,
        'breath': 0.20, 'jitter': 0.03, 'subharm': 0.20, 'rough': (0.0, 0.0),
        'vibrato': 13.0, 'vib_depth': 0.04, 'pulse_hz': 18.0, 'pulse_depth': 0.85,
        'drive': 1.5, 'rt60': 0.5, 'wet': 0.20, 'bright': 0.6,
        'shape': 'chitter', 'gain': 0.78,
    },
}

# time: length multiplier   pitch/sweep/bump: contour   att/decay: amplitude shape
ENEMY_AUDIO_EVENTS = {
    'alert':     {'time': 1.00, 'pitch': 1.00, 'sweep': -0.25, 'bump': 0.18, 'att': 0.12,  'decay': 1.3, 'gain': 0.80, 'breath': 1.0, 'drive': 1.0},
    'attack':    {'time': 0.38, 'pitch': 1.25, 'sweep': 0.30,  'bump': -0.10, 'att': 0.008, 'decay': 2.6, 'gain': 1.00, 'breath': 1.2, 'drive': 1.3},
    'hurt':      {'time': 0.30, 'pitch': 1.50, 'sweep': -0.20, 'bump': 0.35, 'att': 0.008, 'decay': 3.2, 'gain': 0.72, 'breath': 0.8, 'drive': 1.0},
    'death':     {'time': 1.20, 'pitch': 0.80, 'sweep': -0.55, 'bump': 0.05, 'att': 0.04,  'decay': 2.2, 'gain': 0.90, 'breath': 2.0, 'drive': 0.8},
    'jumpscare': {'time': 0.85, 'pitch': 1.15, 'sweep': 0.45,  'bump': 0.10, 'att': 0.015, 'decay': 0.9, 'gain': 1.00, 'breath': 1.4, 'drive': 1.8},
}


class EnemyAudioManager:
    def __init__(self):
        mixer_init = pygame.mixer.get_init()
        self.rate = mixer_init[0] if mixer_init else 44100
        self.sounds = {}
        self._generate_sounds()

    # ── synthesis ─────────────────────────────────────────────────────────────
    def _contour(self, profile, event, t, p, rng):
        """Per-sample pitch curve for this creature + event."""
        shape = profile['shape']
        f = profile['base_hz'] * event['pitch'] * (
            1.0 + event['sweep'] * p + event['bump'] * np.sin(np.pi * p))
        vib_ramp = np.clip(t / 0.25, 0.0, 1.0)
        f = f * (1.0 + profile['vib_depth'] * vib_ramp * np.sin(2 * np.pi * profile['vibrato'] * t))
        if shape == 'bray':             # hee-haw: smooth flips between high and low registers
            flip = 0.5 + 0.5 * np.tanh(5.0 * np.sin(2 * np.pi * 3.4 * t + 0.6))
            f = f * (1.0 + 1.35 * flip)
        elif shape == 'boom':           # each 'ho' sinks in pitch
            ho = (2.7 * t) % 1.0
            f = f * (1.18 - 0.32 * ho)
        elif shape == 'growl':
            f = f * (1.0 + 0.06 * smooth_noise(len(t), self.rate, 14, rng))
        elif shape == 'shriek':
            f = f * (1.0 + 0.5 * (1.0 - np.exp(-t / 0.08)) * (1.0 - 0.35 * p))
        elif shape == 'wail':
            f = f * (1.0 + 0.22 * np.sin(np.pi * np.clip(p * 1.3, 0, 1)) - 0.18 * p ** 2)
        elif shape == 'chitter':
            f = f * (1.0 + 0.25 * np.sin(2 * np.pi * 18 * t))
        return np.maximum(25.0, f)

    def _amp_gate(self, profile, t, p, rng):
        """Creature-specific amplitude behaviour (laugh pulses, chatter, flutter)."""
        shape = profile['shape']
        n = len(t)
        pulse = 1.0 - profile['pulse_depth'] + profile['pulse_depth'] * (
            0.5 + 0.5 * np.sin(2 * np.pi * profile['pulse_hz'] * t))
        if shape == 'boom':
            ho = (2.7 * t) % 1.0
            return np.sin(np.pi * np.clip(ho * 1.05, 0, 1)) ** 1.2 * 0.85 + 0.15
        if shape == 'chitter':
            gate = np.clip((np.sin(2 * np.pi * 18 * t) + 0.35) * 3.0, 0.0, 1.0)
            return gate * (0.8 + 0.2 * smooth_noise(n, self.rate, 30, rng))
        if shape == 'spectral':
            return pulse * np.clip(0.8 + 0.35 * smooth_noise(n, self.rate, 9, rng), 0.2, 1.4)
        return pulse

    def _synthesize(self, enemy_type, event_name):
        profile = ENEMY_AUDIO_PROFILES[enemy_type]
        event = ENEMY_AUDIO_EVENTS[event_name]
        rate = self.rate

        duration = max(0.12, profile['duration'] * event['time'])
        n = max(1, int(rate * duration))
        t = _t(n, rate)
        p = t / duration

        rng = np.random.default_rng(zlib.crc32(f'{enemy_type}:{event_name}'.encode('utf-8')))
        f0 = self._contour(profile, event, t, p, rng)
        va, vb = profile['vowel']
        morph = np.clip(p ** 1.2, 0.0, 1.0)
        breath = profile['breath'] * event['breath']

        def voice(freq, seed_off=0):
            return synth_voice(
                rate, freq, va, vb, morph=morph, tilt=profile['tilt'], breath=breath,
                jitter=profile['jitter'], subharm=profile['subharm'], rough=profile['rough'],
                whisper=profile.get('whisper', 0.0),
                rng=np.random.default_rng(zlib.crc32(f'{enemy_type}:{event_name}:{seed_off}'.encode('utf-8'))),
            )

        wave = voice(f0)
        chorus = profile.get('chorus')
        if chorus:                                      # second, detuned voice -> ghostly beating
            wave = wave + 0.75 * voice(f0 * 2 ** (chorus / 1200.0), 1)

        wave = wave * self._amp_gate(profile, t, p, rng)

        envelope = (1.0 - np.exp(-t / max(event['att'], 1e-3))) * np.exp(-event['decay'] * p)
        envelope *= np.clip((1.0 - p) * 14.0, 0.0, 1.0)
        wave = wave * envelope

        # extra anatomy
        if profile.get('flap'):                         # leathery wing beats
            flap_t = np.arange(0.0, duration, 1.0 / 4.6) + rng.uniform(0, 0.05)
            flap_env = np.zeros(n)
            for tf in flap_t:
                flap_env += np.exp(-0.5 * ((t - tf) / 0.032) ** 2)
            flaps = fft_filter(rng.standard_normal(n), rate, lo=70, hi=650) * flap_env
            wave = wave / max(float(np.max(np.abs(wave))), 1e-9) + profile['flap'] * _pk(flaps) * np.clip(envelope * 3, 0, 1)
        if profile['shape'] == 'chitter':               # tiny claw/teeth clicks
            clicks = np.zeros(n)
            period = int(rate / 18.0)
            for i in range(0, n, period):
                j = i + int(rng.integers(0, max(1, period // 4)))
                if j < n:
                    clicks[j] += rng.uniform(0.6, 1.0)
            clicks = fft_band(clicks, rate, 3000, 1.2) * envelope
            wave = wave / max(float(np.max(np.abs(wave))), 1e-9) + 0.45 * _pk(clicks)
        if profile['shape'] == 'boom':                  # chest rumble under the voice
            rumble = np.sin(2 * np.pi * 41.0 * t) * envelope * 0.6
            wave = wave / max(float(np.max(np.abs(wave))), 1e-9) + rumble

        # saturation (lungs/throat overdrive), then level
        drive = max(0.3, profile['drive'] * event['drive'])
        wave = _pk(wave)
        if drive > 1.05:
            wave = np.tanh(drive * wave) / np.tanh(drive)
        wave = wave - float(np.mean(wave))
        wave *= 0.9 * profile['gain'] * event['gain']

        out = reverb(
            wave, rate, rt60=profile['rt60'], wet=profile['wet'], brightness=profile['bright'],
            echoes=[(0.19, 0.12 * profile['wet'] / 0.3, 2400)] if profile['rt60'] > 1.2 else None,
        )

        peak = float(np.max(np.abs(out)))
        if peak > 0.97:
            out *= 0.97 / peak
        # trim silent tail + fade to avoid a click at the end
        env = np.max(np.abs(out), axis=1)
        loud = np.nonzero(env > max(peak, 1e-9) * 3e-4)[0]
        if len(loud):
            out = out[:loud[-1] + 1]
        k = min(len(out), int(0.01 * rate))
        if k > 1:
            out[-k:] *= np.linspace(1.0, 0.0, k)[:, None]
        return audio_mgr._generate_sound(out)

    def _generate_sounds(self):
        for enemy_type in ENEMY_AUDIO_PROFILES:
            for event_name in ENEMY_AUDIO_EVENTS:
                key = (enemy_type, event_name)
                try:
                    self.sounds[key] = self._synthesize(enemy_type, event_name)
                except Exception as exc:                 # never let audio crash the game
                    print(f"[EnemyAudio] failed to build {key}: {exc}")
                    self.sounds[key] = None

    # ── playback ──────────────────────────────────────────────────────────────
    def play(self, enemy_type, event_name='alert', volume=1.0, pan=0.0):
        sound = self.sounds.get((enemy_type, event_name))
        if sound is None:
            return None
        return audio_mgr.play_object(sound, volume, pan)

    def play_spatial(self, enemy_type, event_name, player_x, player_y, player_angle,
                     target_x, target_y, base_volume=1.0, max_dist=15.0):
        sound = self.sounds.get((enemy_type, event_name))
        if sound is None:
            return None
        params = audio_mgr.spatial_params(
            player_x, player_y, player_angle, target_x, target_y, base_volume, max_dist)
        if params is None:
            return None
        volume, pan, level = params
        return audio_mgr.play_object(audio_mgr.muffled(sound, level), volume, pan)


enemy_audio_mgr = EnemyAudioManager()
