"""
Advanced Lighting System for ANINO SA GUBAT: Mga Bulong ng Dilim
Provides dynamic multi-light support, shadow occlusion, colored lights,
and integration with the raycasting renderer.
"""
import math
import pygame
import numpy as np
from typing import List, Dict, Tuple, Optional

# ─── Type Definitions ─────────────────────────────────────────────────────────
LightColor = Tuple[int, int, int]
LightPos = Tuple[float, float]
LightData = Dict

# ─── Light Types ─────────────────────────────────────────────────────────────
LIGHT_POINT = 'point'
LIGHT_CONE = 'cone'
LIGHT_AMBIENT = 'ambient'
LIGHT_DIRECTIONAL = 'directional'

# ─── Constants ────────────────────────────────────────────────────────────────
MIN_LIGHT_DIST = 0.1
MAX_SHADOW_RAYS = 32
FLICKER_BASE = 0.95


class Light:
    """Represents a single light source in the world."""
    
    def __init__(self, 
                 light_type: str,
                 x: float, 
                 y: float,
                 radius: float,
                 color: LightColor = (255, 255, 255),
                 intensity: float = 1.0,
                 direction: Optional[float] = None,
                 cone_angle: float = 0.0,
                 flicker_amount: float = 0.0,
                 flicker_speed: float = 3.0):
        self.type = light_type
        self.x = x
        self.y = y
        self.radius = max(MIN_LIGHT_DIST, radius)
        self.color = color
        self.intensity = max(0.0, intensity)
        self.direction = direction or 0.0
        self.cone_angle = max(0.0, cone_angle)
        self.flicker_amount = max(0.0, min(1.0, flicker_amount))
        self.flicker_speed = max(0.1, flicker_speed)
        
        self.time_alive = 0.0
        self.enabled = True
        self.fade_duration = 0.0
        self.fade_remaining = 0.0
        
    def update(self, dt: float):
        """Update light animation state."""
        self.time_alive += dt
        if self.fade_remaining > 0.0:
            self.fade_remaining = max(0.0, self.fade_remaining - dt)
            fade_progress = self.fade_remaining / self.fade_duration if self.fade_duration > 0 else 0.0
            self.intensity = self.intensity * fade_progress
        
    def get_flicker_intensity(self) -> float:
        """Get current intensity including flicker."""
        if self.flicker_amount <= 0.0:
            return self.intensity
        
        base_flicker = math.sin(self.time_alive * self.flicker_speed * math.pi)
        secondary_flicker = math.sin(self.time_alive * self.flicker_speed * 0.3 * math.pi) * 0.5
        combined = (base_flicker + secondary_flicker) * 0.5
        
        flicker_mod = 1.0 - self.flicker_amount * (1.0 - combined) * 0.5
        return self.intensity * flicker_mod
    
    def fade_out(self, duration: float):
        """Begin fading out the light."""
        self.fade_duration = max(0.1, duration)
        self.fade_remaining = self.fade_duration
    
    def set_position(self, x: float, y: float):
        """Update light position."""
        self.x = x
        self.y = y
    
    def get_effective_color(self) -> LightColor:
        """Get color with intensity applied."""
        intensity = self.get_flicker_intensity()
        return tuple(int(c * intensity) for c in self.color)


class ShadowOccluder:
    """Represents geometry that casts shadows."""
    
    def __init__(self, x: float, y: float, radius: float, height: float = 1.0):
        self.x = x
        self.y = y
        self.radius = radius
        self.height = height
    
    def get_shadow_edges(self, light_pos: LightPos) -> Tuple[float, float]:
        """Calculate angular range blocked by occluder."""
        dx = self.x - light_pos[0]
        dy = self.y - light_pos[1]
        dist = math.sqrt(dx * dx + dy * dy)
        
        if dist < MIN_LIGHT_DIST:
            return 0.0, 0.0
        
        angular_width = math.atan2(self.radius, dist)
        center_angle = math.atan2(dy, dx)
        
        return center_angle - angular_width, center_angle + angular_width


class LightingSystem:
    """Manages all lights in the game world."""
    
    def __init__(self, ambient_color: LightColor = (40, 50, 70), 
                 ambient_intensity: float = 0.15):
        self.lights: List[Light] = []
        self.occluders: List[ShadowOccluder] = []
        self.ambient_color = ambient_color
        self.ambient_intensity = max(0.0, min(1.0, ambient_intensity))
        
        self.stats = {
            'active_lights': 0,
            'shadow_calcs': 0,
            'light_updates': 0,
        }
    
    def add_light(self, light: Light) -> int:
        """Add a light to the system. Returns light ID."""
        self.lights.append(light)
        return len(self.lights) - 1
    
    def remove_light(self, light_id: int):
        """Remove a light by ID."""
        if 0 <= light_id < len(self.lights):
            self.lights[light_id].enabled = False
    
    def get_light_at_position(self, x: float, y: float, ignore_occluders: bool = False) -> LightColor:
        """Calculate total light color at a world position."""
        r = self.ambient_color[0] * self.ambient_intensity
        g = self.ambient_color[1] * self.ambient_intensity
        b = self.ambient_color[2] * self.ambient_intensity
        
        active_count = 0
        for light in self.lights:
            if not light.enabled:
                continue
            
            dx = x - light.x
            dy = y - light.y
            dist = math.sqrt(dx * dx + dy * dy)
            
            if dist >= light.radius:
                continue
            
            active_count += 1
            
            if not ignore_occluders and self._is_in_shadow(light, x, y, dist):
                continue
            
            attenuation = 1.0 - (dist / light.radius) ** 2
            attenuation = max(0.0, attenuation)
            
            if light.type == LIGHT_CONE:
                if light.cone_angle > 0.0:
                    angle_to_point = math.atan2(dy, dx)
                    angle_diff = self._normalize_angle(angle_to_point - light.direction)
                    
                    if abs(angle_diff) > light.cone_angle:
                        continue
                    
                    edge_falloff = 1.0 - abs(angle_diff) / light.cone_angle * 0.3
                    attenuation *= edge_falloff
            
            light_color = light.get_effective_color()
            
            r += light_color[0] * attenuation
            g += light_color[1] * attenuation
            b += light_color[2] * attenuation
        
        self.stats['active_lights'] = active_count
        
        return (int(min(255, r)), int(min(255, g)), int(min(255, b)))
    
    def get_light_contribution(self, x: float, y: float, light_index: int) -> float:
        """Get brightness contribution from a specific light (0.0-1.0)."""
        if light_index < 0 or light_index >= len(self.lights):
            return 0.0
        
        light = self.lights[light_index]
        if not light.enabled:
            return 0.0
        
        dx = x - light.x
        dy = y - light.y
        dist = math.sqrt(dx * dx + dy * dy)
        
        if dist >= light.radius:
            return 0.0
        
        attenuation = 1.0 - (dist / light.radius) ** 2
        return max(0.0, attenuation * light.get_flicker_intensity())
    
    def _is_in_shadow(self, light: Light, x: float, y: float, dist: float) -> bool:
        """Check if a point is in shadow from a light source."""
        light_pos = (light.x, light.y)
        
        for occluder in self.occluders:
            occ_dx = occluder.x - light.x
            occ_dy = occluder.y - light.y
            occ_dist = math.sqrt(occ_dx * occ_dx + occ_dy * occ_dy)
            
            if occ_dist > dist:
                continue
            
            angle_left, angle_right = occluder.get_shadow_edges(light_pos)
            point_angle = math.atan2(y - light.y, x - light.x)
            
            point_angle = self._normalize_angle(point_angle)
            angle_left = self._normalize_angle(angle_left)
            angle_right = self._normalize_angle(angle_right)
            
            if angle_left < angle_right:
                if angle_left <= point_angle <= angle_right:
                    return True
            else:
                if point_angle >= angle_left or point_angle <= angle_right:
                    return True
        
        return False
    
    @staticmethod
    def _normalize_angle(angle: float) -> float:
        """Normalize angle to -π to π range."""
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi
        return angle
    
    def get_stats(self) -> Dict:
        """Return performance statistics."""
        return self.stats.copy()


    def add_occluder(self, x: float, y: float, radius: float, height: float = 1.0):
        """Add a shadow-casting occluder."""
        self.occluders.append(ShadowOccluder(x, y, radius, height))
    
    def clear_occluders(self):
        """Clear all occluders."""
        self.occluders.clear()
    
    def update(self, dt: float):
        """Update all lights."""
        self.stats['light_updates'] = 0
        for light in self.lights:
            if light.enabled:
                light.update(dt)
                self.stats['light_updates'] += 1
        
        self.lights = [l for l in self.lights if l.enabled or l.fade_remaining > 0]


# ─── Convenience Factories ────────────────────────────────────────────────────

def create_flashlight(x: float, y: float, direction: float, 
                     radius: float = 20.0, cone_angle: float = 0.35,
                     intensity: float = 1.0) -> Light:
    """Create a directional cone light (flashlight)."""
    return Light(
        LIGHT_CONE,
        x, y,
        radius,
        color=(255, 240, 200),
        intensity=intensity,
        direction=direction,
        cone_angle=cone_angle,
        flicker_amount=0.02,
        flicker_speed=1.5
    )


def create_candle(x: float, y: float, 
                 radius: float = 6.0,
                 intensity: float = 0.8) -> Light:
    """Create a flickering candle light."""
    return Light(
        LIGHT_POINT,
        x, y,
        radius,
        color=(255, 200, 100),
        intensity=intensity,
        flicker_amount=0.4,
        flicker_speed=2.5
    )


def create_supernatural_light(x: float, y: float,
                             radius: float = 12.0,
                             color: LightColor = (100, 255, 150),
                             intensity: float = 0.7) -> Light:
    """Create a supernatural (ethereal) light."""
    return Light(
        LIGHT_POINT,
        x, y,
        radius,
        color=color,
        intensity=intensity,
        flicker_amount=0.3,
        flicker_speed=0.8
    )


def create_lantern(x: float, y: float,
                  radius: float = 10.0,
                  intensity: float = 1.0) -> Light:
    """Create an oil lantern light."""
    return Light(
        LIGHT_POINT,
        x, y,
        radius,
        color=(255, 220, 140),
        intensity=intensity,
        flicker_amount=0.25,
        flicker_speed=1.8
    )
