"""
Renderer Enhancement Integration - adds visual effects to the main render loop
Minimal, focused modifications to the existing Renderer class
"""

def add_enhancement_methods_to_renderer():
    """
    Methods to be added to the Renderer class for visual enhancement support.
    This keeps enhancements modular and easy to test.
    """
    
    def update_enhancements(self, dt: float, player, enemies, game_map):
        """Update all visual enhancement systems each frame."""
        # Update dynamic lighting
        self.dynamic_lights.update(dt)
        
        # Update atmosphere particles
        self.atmosphere_particles.update(dt)
        
        # Update film grain frame counter
        self.film_grain.frame += 1
        
        # Add ambient environmental lights based on map features
        self._update_map_lights(game_map)
        
        # Add enemy auras for supernatural lighting
        self._update_enemy_auras(enemies)
    
    def _update_map_lights(self, game_map):
        """Add dynamic lights based on map features (torches, lamps, etc)."""
        if not hasattr(game_map, 'lights'):
            return
        
        for light_data in getattr(game_map, 'lights', []):
            x = light_data.get('x', 0)
            y = light_data.get('y', 0)
            radius = light_data.get('radius', 10)
            color = tuple(light_data.get('color', (255, 240, 200)))
            intensity = light_data.get('intensity', 0.8)
            flicker = light_data.get('flicker', 0.1)
            
            self.dynamic_lights.add(x, y, radius, color, intensity, flicker)
    
    def _update_enemy_auras(self, enemies):
        """Add subtle supernatural auras around creatures for atmospheric lighting."""
        from renderer import ENEMY_AURA
        
        for enemy in enemies:
            if not getattr(enemy, 'alive', True):
                continue
            
            enemy_type = getattr(enemy, 'type', 'aswang')
            aura_color = ENEMY_AURA.get(enemy_type, (100, 100, 100))
            aura_radius = 5.0
            aura_intensity = 0.3
            
            self.dynamic_lights.add(enemy.x, enemy.y, aura_radius, aura_color, aura_intensity, 0.15)
    
    def apply_enhancements(self, surface):
        """Apply post-processing enhancements to the rendered frame."""
        import pygame
        
        # Apply color grading first (foundational color shift)
        if self.color_grader.strength > 0:
            surface = self.color_grader.apply(surface)
        
        # Apply film grain for analog horror aesthetic
        if self.film_grain.enabled and self.film_grain.amount > 0:
            surface = self.film_grain.apply(surface)
        
        return surface
    
    def get_enhanced_light_color(self, x: float, y: float, base_color: tuple) -> tuple:
        """Get light color with dynamic lighting applied."""
        light = self.dynamic_lights.get_light(x, y)
        
        # Blend with base ambient
        r = (base_color[0] + light[0]) // 2
        g = (base_color[1] + light[1]) // 2
        b = (base_color[2] + light[2]) // 2
        
        return (min(255, r), min(255, g), min(255, b))
    
    # Attach methods to Renderer class
    import renderer
    renderer.Renderer.update_enhancements = update_enhancements
    renderer.Renderer._update_map_lights = _update_map_lights
    renderer.Renderer._update_enemy_auras = _update_enemy_auras
    renderer.Renderer.apply_enhancements = apply_enhancements
    renderer.Renderer.get_enhanced_light_color = get_enhanced_light_color


# Call this on import to patch the Renderer class
try:
    add_enhancement_methods_to_renderer()
    print("[ENHANCEMENT INTEGRATION] Renderer methods patched successfully")
except Exception as e:
    print(f"[ENHANCEMENT INTEGRATION] Error patching Renderer: {e}")
