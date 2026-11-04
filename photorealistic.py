"""Low-cost photorealistic presentation helpers for the Pygame raycaster.

These effects are deliberately screen-space / procedural: they improve material
readability and atmosphere without changing world geometry, collision, or gameplay.
All expensive masks are built once and reused.
"""
import math
import numpy as np
import pygame


def grade_rgb_array(rgb, daylight=0.0):
    """Apply a restrained cold-night film grade in-place to a (w, h, 3) uint8 view."""
    day = max(0.0, min(1.0, float(daylight)))
    arr = rgb.astype(np.float32)
    # Preserve highlights while adding contrast and the cold blue-green night palette.
    arr = np.maximum(0.0, (arr - 18.0) * 1.055 + 18.0)
    night = np.asarray((0.91, 0.985, 1.045), dtype=np.float32)
    dawn = np.asarray((1.045, 1.015, 0.94), dtype=np.float32)
    tint = night[None, None, :] * (1.0 - day) + dawn[None, None, :] * day
    arr *= tint
    # Gentle highlight roll-off; no hard clipping or crushed blacks.
    arr = 255.0 * (arr / (arr + 230.0)) * 1.94
    rgb[:, :, :] = np.clip(arr, 0, 255).astype(np.uint8)


class PhotorealisticPass:
    """Cached wet-ground micro highlights, layered mist and final cinematic grade."""

    def __init__(self, width, height):
        self.width, self.height = int(width), int(height)
        self._mist = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        rng = np.random.default_rng(7319)
        # Stable micro-roughness pattern. It is never regenerated during gameplay.
        self._wet_noise = rng.random((self.width, self.height), dtype=np.float32)
        x = np.arange(self.width, dtype=np.float32)[:, None]
        y = np.arange(self.height, dtype=np.float32)[None, :]
        self._x = x
        self._y = y
        # Precompute the moving wet-ground wave as sin(a+b) = sin(a)cos(b)+cos(a)sin(b).
        # This avoids evaluating a full floor-sized sine field every frame.
        wave_phase = x * 0.075 + y * 0.11
        self._wet_wave_sin = np.sin(wave_phase).astype(np.float32)
        self._wet_wave_cos = np.cos(wave_phase).astype(np.float32)
        self._vignette = np.clip(
            1.0 - 0.12 * (((x - self.width * 0.5) / max(1, self.width * 0.72)) ** 2
                          + ((y - self.height * 0.52) / max(1, self.height * 0.72)) ** 2),
            0.82, 1.0).astype(np.float32)
        # Integer vignette factors and one reusable work plane avoid repeated
        # full-frame float32 conversions/allocations in apply_grade().
        self._vignette_u8 = {
            amount: np.rint((1.0 - amount * (1.0 - self._vignette)) * 255.0)
                         .clip(0, 255).astype(np.uint16)
            for amount in (1.0, 0.65)
        }
        self._grade_tmp = np.empty((self.width, self.height), dtype=np.uint16)

    def enhance_floor(self, surface, horizon_y, time_s=0.0, strength=1.0):
        """Add restrained wet-leaf / puddle glints to the exposed ground plane."""
        horizon = max(0, min(self.height, int(horizon_y)))
        if horizon >= self.height:
            return
        amount = max(0.0, min(1.0, float(strength)))
        if amount <= 0.0:
            return
        rgb = pygame.surfarray.pixels3d(surface)
        noise = self._wet_noise[:, horizon:]
        phase = float(time_s) * 0.7
        wave = (self._wet_wave_sin[:, horizon:] * math.cos(phase)
                + self._wet_wave_cos[:, horizon:] * math.sin(phase))
        ripple = 0.5 + 0.5 * wave
        # Sparse, broken highlights avoid the appearance of a uniform glossy filter.
        glint = np.maximum(0.0, (noise * 0.58 + ripple * 0.42) - 0.79)
        glint *= amount * 13.0
        rgb[:, horizon:, 0] = np.minimum(255, rgb[:, horizon:, 0].astype(np.float32) + glint * 0.72).astype(np.uint8)
        rgb[:, horizon:, 1] = np.minimum(255, rgb[:, horizon:, 1].astype(np.float32) + glint * 0.88).astype(np.uint8)
        rgb[:, horizon:, 2] = np.minimum(255, rgb[:, horizon:, 2].astype(np.float32) + glint).astype(np.uint8)
        del rgb

    def draw_mist(self, surface, horizon_y, time_s=0.0, daylight=0.0,
                  strength=1.0, ambient=0.4):
        """Layer faint low forest mist; reveal it a little more in darker conditions."""
        day = max(0.0, min(1.0, float(daylight)))
        ambient_level = max(0.0, min(1.0, float(ambient)))
        darkness = 1.0 - ambient_level
        # A restrained 0–35% boost keeps the haze readable without washing out the scene.
        dark_boost = 1.0 + darkness * 0.55
        alpha_scale = (max(0.0, min(1.0, float(strength)))
                       * (1.0 - day * 0.72) * dark_boost)
        if alpha_scale <= 0.01:
            return
        h = self.height
        self._mist.fill((0, 0, 0, 0))
        base = max(int(horizon_y) + 5, int(h * 0.52))
        # Broad overlapping ribbons with slow lateral drift, not opaque full-screen fog.
        for layer in range(3):
            y = min(h - 12, base + int(h * (0.085 + layer * 0.085)))
            drift = math.sin(time_s * (0.12 + layer * 0.035) + layer * 2.1) * self.width * 0.07
            width = int(self.width * (0.92 + layer * 0.18))
            height = max(12, int(h * (0.075 + layer * 0.018)))
            a = int((22 - layer * 4) * alpha_scale)
            rect = (int(self.width * 0.5 + drift - width * 0.5), y - height // 2, width, height)
            # Cool blue-gray haze is stronger near the ground while preserving readable silhouettes.
            pygame.draw.ellipse(self._mist, (96, 116, 124, a), rect)
        surface.blit(self._mist, (0, 0))

    def apply_grade(self, surface, daylight=0.0, strength=1.0):
        """Apply subtle vignette and cold/warm exposure grade to the 3D scene."""
        amount = max(0.0, min(1.0, float(strength)))
        if amount <= 0.0:
            return
        rgb = pygame.surfarray.pixels3d(surface)

        # Build tiny per-channel 256-entry LUTs for the contrast/tint/film curve.
        # Applying them in-place avoids the several full-frame float32 arrays used
        # by grade_rgb_array() on every frame.
        day = max(0.0, min(1.0, float(daylight)))
        night = (0.91, 0.985, 1.045)
        dawn = (1.045, 1.015, 0.94)
        lut_input = np.arange(256, dtype=np.float32)
        factors = self._vignette_u8[1.0 if amount >= 0.999 else 0.65]
        work = self._grade_tmp
        for channel in range(3):
            tint = night[channel] * (1.0 - day) + dawn[channel] * day
            values = np.maximum(0.0, (lut_input - 18.0) * 1.055 + 18.0)
            values *= tint
            values = 255.0 * (values / (values + 230.0)) * 1.94
            lut = np.clip(values, 0.0, 255.0).astype(np.uint8)
            np.take(lut, rgb[:, :, channel], out=rgb[:, :, channel])

            # Integer multiply/divide reproduces the vignette blend while using
            # one reusable uint16 plane instead of a new float32 image per channel.
            np.multiply(rgb[:, :, channel], factors, out=work, dtype=np.uint16)
            work += 127
            np.floor_divide(work, 255, out=work)
            rgb[:, :, channel] = work

        del rgb
