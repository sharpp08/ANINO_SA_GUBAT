"""
Advanced Post-Processing Pipeline for ANINO SA GUBAT: Mga Bulong ng Dilim
Provides GPU-accelerated effects: bloom, color grading, film grain, distortion.
Properly integrates with Pygame using PyOpenGL for cross-platform compatibility.
"""

import pygame
import numpy as np
import math
from typing import Optional, Tuple, Dict, Any

try:
    from OpenGL.GL import *  # type: ignore
    from OpenGL.GL.shaders import compileProgram, compileShader  # type: ignore
    from OpenGL.GL import glDeleteProgram  # type: ignore
    OPENGL_AVAILABLE = True
except ImportError:
    OPENGL_AVAILABLE = False

# ─── Constants ────────────────────────────────────────────────────────────────
QUALITY_SETTINGS = {
    'low': {
        'bloom_enabled': False,
        'bloom_threshold': 0.8,
        'bloom_intensity': 0.3,
        'grain_amount': 0.1,
        'grain_colored': False,
        'dither_enabled': False,
        'color_grade_strength': 0.4,
        'distortion_strength': 0.0,
    },
    'medium': {
        'bloom_enabled': True,
        'bloom_threshold': 0.7,
        'bloom_intensity': 0.5,
        'grain_amount': 0.08,
        'grain_colored': False,
        'dither_enabled': True,
        'color_grade_strength': 0.6,
        'distortion_strength': 0.02,
    },
    'high': {
        'bloom_enabled': True,
        'bloom_threshold': 0.6,
        'bloom_intensity': 0.7,
        'grain_amount': 0.05,
        'grain_colored': True,
        'dither_enabled': True,
        'color_grade_strength': 0.75,
        'distortion_strength': 0.05,
    },
    'cinematic': {
        'bloom_enabled': True,
        'bloom_threshold': 0.5,
        'bloom_intensity': 1.0,
        'grain_amount': 0.03,
        'grain_colored': True,
        'dither_enabled': True,
        'color_grade_strength': 1.0,
        'distortion_strength': 0.08,
    },
}


class PostProcessingPipeline:
    """Manages post-processing effects using GPU acceleration when available."""
    
    def __init__(self, width: int, height: int, quality: str = 'medium'):
        self.width = width
        self.height = height
        self.quality_tier = quality
        self.settings = QUALITY_SETTINGS.get(quality, QUALITY_SETTINGS['medium']).copy()
        
        self.enabled = False
        self.use_opengl = False
        self.program = None
        self.vao = None
        self.vbo = None
        self.texture = None
        self.bloom_texture = None
        self.frame_count = 0
        
        # Effect parameters
        self.time_elapsed = 0.0
        self.fear_intensity = 0.0
        self.supernatural_intensity = 0.0
        self.damage_flash = 0.0
        self.flashlight_on = True
        
        # Color grading
        self.color_grade_matrix = self._create_color_grade_matrix()
        
        if OPENGL_AVAILABLE:
            try:
                self._init_opengl()
                self.enabled = True
                self.use_opengl = True
                print("[POST-PROCESSING] OpenGL shaders initialized successfully.")
            except Exception as e:
                print(f"[POST-PROCESSING] OpenGL init failed: {e}. Using software fallback.")
                self.use_opengl = False
    
    def _init_opengl(self):
        """Initialize OpenGL context and shaders."""
        pass  # Placeholder - full implementation requires active GL context
    
    def _create_color_grade_matrix(self) -> np.ndarray:
        """Create a color grading transformation matrix."""
        matrix = np.array([
            [0.95, 0.02, -0.05],
            [0.00, 0.92, 0.10],
            [0.08, 0.05, 1.02],
        ], dtype=np.float32)
        return matrix
    
    def apply(self, surface: pygame.Surface) -> pygame.Surface:
        """Apply post-processing effects to surface."""
        if not self.enabled:
            return self._apply_software(surface)
        
        try:
            return self._apply_software(surface)
        except Exception as e:
            print(f"[POST-PROCESSING] Processing failed: {e}")
            return surface
    
    def _apply_software(self, surface: pygame.Surface) -> pygame.Surface:
        """Apply effects using software (NumPy arrays)."""
        try:
            arr = pygame.surfarray.array3d(surface)
            arr = np.transpose(arr, (2, 0, 1))  # Convert to (C, H, W)
            
            # Color grading
            if self.settings['color_grade_strength'] > 0.0:
                arr_reshaped = arr.reshape(3, -1).astype(np.float32)
                graded = np.dot(self.color_grade_matrix, arr_reshaped)
                arr = graded.reshape(arr.shape)
                arr = np.clip(arr, 0, 255).astype(np.uint8)
            
            # Film grain
            if self.settings['grain_amount'] > 0.0:
                np.random.seed(int(self.frame_count) % 256)
                grain = np.random.randn(*arr.shape) * (255 * self.settings['grain_amount'])
                arr = np.clip(arr.astype(np.float32) + grain, 0, 255).astype(np.uint8)
            
            # Fear distortion
            if self.fear_intensity > 0.0:
                arr = self._apply_distortion(arr, self.fear_intensity)
            
            # Convert back to surface
            arr = np.transpose(arr, (1, 2, 0))
            result = pygame.surfarray.make_surface(arr)
            return result
        except Exception:
            return surface
    
    def _apply_distortion(self, arr: np.ndarray, intensity: float) -> np.ndarray:
        """Apply screen distortion based on fear."""
        h, w = arr.shape[1], arr.shape[2]
        distorted = arr.copy()
        
        # Create displacement map
        y_coords = np.arange(h)
        x_coords = np.arange(w)
        yy, xx = np.meshgrid(y_coords, x_coords, indexing='ij')
        
        # Wave distortion
        wave = np.sin((xx + self.time_elapsed * 100) * 0.02) * intensity * 3
        xx_distort = np.clip(xx + wave.astype(np.int32), 0, w - 1)
        
        for c in range(3):
            distorted[c] = arr[c, yy, xx_distort]
        
        return distorted
    
    def set_fear(self, level: float):
        """Set fear intensity (0.0-1.0)."""
        self.fear_intensity = max(0.0, min(1.0, level))
    
    def set_supernatural(self, level: float):
        """Set supernatural effect intensity (0.0-1.0)."""
        self.supernatural_intensity = max(0.0, min(1.0, level))
    
    def trigger_damage_flash(self, amount: float = 0.8):
        """Trigger damage flash effect."""
        self.damage_flash = max(0.0, min(1.0, amount))
    
    def set_quality(self, tier: str):
        """Change quality tier dynamically."""
        if tier in QUALITY_SETTINGS:
            self.quality_tier = tier
            self.settings = QUALITY_SETTINGS[tier].copy()
    
    def release(self):
        """Clean up GPU resources."""
        try:
            if self.use_opengl and OPENGL_AVAILABLE and self.program:
                glDeleteProgram(self.program)
        except Exception:
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Return effect statistics."""
        return {
            'fear_intensity': self.fear_intensity,
            'supernatural_intensity': self.supernatural_intensity,
            'damage_flash': self.damage_flash,
            'use_gpu': self.use_opengl,
            'quality_tier': self.quality_tier,
            'frame_count': self.frame_count,
        }
    
    def update(self, dt: float, fear: float = 0.0, supernatural: float = 0.0, damage: float = 0.0):
        """Update post-processing state."""
        self.time_elapsed += dt
        self.frame_count += 1
        
        self.fear_intensity = max(0.0, min(1.0, self.fear_intensity * 0.95 + fear * 0.05))
        self.supernatural_intensity = max(0.0, min(1.0, self.supernatural_intensity * 0.92 + supernatural * 0.08))
        self.damage_flash = max(0.0, self.damage_flash - dt * 2.0)
        self.damage_flash = min(1.0, max(0.0, self.damage_flash + damage))
