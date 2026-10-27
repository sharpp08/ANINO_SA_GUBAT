"""
Jumpscare System - Plays fullscreen video + synthesized scream on enemy grab.
"""
import os
import pygame
import math
import random
from settings import BASE_PATH


class JumpscareManager:
    """Manages jumpscare playback triggered by enemy grabs."""
    
    def __init__(self):
        self.active = False
        self.timer = 0.0
        self.duration = 1.2  # Faster: 1.2 seconds (was 2.6)
        self.scream_sound = None
        self.frame_time = 0.0
        
        self._load_assets()
    
    def _load_assets(self):
        """Load jumpscare audio from the animation pack."""
        pack_dir = os.path.join(BASE_PATH, 'enemy_animations_pack')
        scream_path = os.path.join(pack_dir, 'jumpscare_scream.wav')
        if os.path.exists(scream_path):
            try:
                self.scream_sound = pygame.mixer.Sound(scream_path)
                print(f"[Jumpscare] Loaded scream audio: {scream_path}")
            except Exception as e:
                print(f"[Jumpscare] Failed to load scream: {e}")
    
    def trigger(self):
        """Trigger the jumpscare sequence."""
        self.active = True
        self.timer = 0.0
        self.frame_time = 0.0
        
        # Play scream at maximum volume
        if self.scream_sound:
            try:
                self.scream_sound.set_volume(1.0)  # MAX VOLUME
                self.scream_sound.play()
            except Exception:
                pass
        
        print("[Jumpscare] TRIGGERED - fullscreen horror sequence")
        
        # Return stun duration for player
        return 2.0  # Stun player for 2 seconds
    
    def update(self, dt):
        """Update jumpscare state."""
        if not self.active:
            return False
        
        self.timer += dt
        if self.timer >= self.duration:
            self.active = False
            return False
        
        return True
    
    def render_procedural(self, surface):
        """Render procedural jumpscare (aswang face rushing at camera).
        FAST VERSION: 1.2 seconds total
        """
        if not self.active or self.timer < 0:
            return 0
        
        w, h = surface.get_size()
        t = self.timer
        progress = t / self.duration
        
        # Phase 1: Darkness (0.0-0.15s) - FASTER
        if t < 0.15:
            alpha = int(255 * (t / 0.15))
            dark = pygame.Surface((w, h), pygame.SRCALPHA)
            dark.fill((0, 0, 0, alpha))
            surface.blit(dark, (0, 0))
            shake = int(math.sin(t * 50) * 20 * (1 - t / 0.15))
            return shake
        
        # Phase 2: Face rush (0.15-0.6s) - FASTER
        elif t < 0.6:
            phase = (t - 0.15) / 0.45
            
            dark = pygame.Surface((w, h), pygame.SRCALPHA)
            dark.fill((0, 0, 0, 200))
            surface.blit(dark, (0, 0))
            
            # Procedural aswang face - LARGER FASTER
            face_size = int(100 + phase * 600)  # Bigger face, faster rush
            face_x = w // 2 - face_size // 2
            face_y = h // 2 - face_size // 2
            
            pygame.draw.ellipse(surface, (40, 20, 20), (face_x, face_y, face_size, face_size))
            
            # Eye flares - BRIGHTER
            for ex in [face_x + face_size * 0.35, face_x + face_size * 0.65]:
                ey = face_y + face_size * 0.4
                glow_size = int(face_size * 0.18 * (1 + 0.8 * math.sin(t * 20)))
                pygame.draw.circle(surface, (255, 80, 80), (int(ex), int(ey)), max(2, glow_size))
                pygame.draw.circle(surface, (255, 255, 150), (int(ex), int(ey)), max(1, glow_size // 2))
            
            # Motion streaks - MORE INTENSE
            for i in range(12):
                streak_y = face_y + (face_size / 12) * i
                pygame.draw.line(surface, (255, 100, 100), (0, int(streak_y)), (w, int(streak_y)), 3)
            
            shake = int(math.sin(t * 40) * 40)  # MORE SHAKE
            return shake
        
        # Phase 3: Impact flash (0.6-0.9s) - FASTER
        elif t < 0.9:
            phase = (t - 0.6) / 0.3
            
            flash_alpha = int(255 * (1 - phase))
            flash = pygame.Surface((w, h), pygame.SRCALPHA)
            flash.fill((255, 255, 255, flash_alpha))
            surface.blit(flash, (0, 0))
            
            # Radial burst
            for i in range(12):
                radius = int((w // 2) * (1 + phase * 3))
                pygame.draw.circle(surface, (255, 150, 150), (w // 2, h // 2), radius, 4)
            
            shake = int(60 * (1 - phase))  # EXTREME SHAKE
            return shake
        
        # Phase 4: Black fade (0.9-1.2s) - FASTER
        else:
            phase = (t - 0.9) / 0.3
            alpha = int(255 * phase)
            black = pygame.Surface((w, h), pygame.SRCALPHA)
            black.fill((0, 0, 0, alpha))
            surface.blit(black, (0, 0))
        
        return 0
    
    def render(self, surface):
        """Render the jumpscare sequence."""
        if not self.active:
            return 0
        return self.render_procedural(surface)
    
    def is_playing(self):
        """Check if jumpscare is currently active."""
        return self.active


_jumpscare_manager = None

def get_jumpscare_manager():
    """Get or create the global jumpscare manager."""
    global _jumpscare_manager
    if _jumpscare_manager is None:
        _jumpscare_manager = JumpscareManager()
    return _jumpscare_manager
