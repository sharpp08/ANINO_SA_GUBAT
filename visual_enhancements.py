"""
Visual Enhancement System - Compact integration module for ANINO SA GUBAT
Provides dynamic lighting, fog, grain, and color grading for the renderer.
"""
import math, pygame, numpy as np
from typing import Dict, Tuple, List, Optional

class DynamicLights:
    """Simple dynamic light manager."""
    def __init__(self):
        self.lights = []
        self.ambient = (40, 50, 70)
        self.ambient_int = 0.15
    
    def add(self, x: float, y: float, r: float, color=(255,240,200), intensity=1.0, flicker=0.0):
        self.lights.append({'x':x,'y':y,'r':r,'c':color,'i':intensity,'f':flicker,'t':0.0})
    
    def update(self, dt: float):
        for light in self.lights: light['t'] += dt
    
    def get_light(self, x: float, y: float) -> Tuple[int,int,int]:
        r = int(self.ambient[0] * self.ambient_int)
        g = int(self.ambient[1] * self.ambient_int)
        b = int(self.ambient[2] * self.ambient_int)
        
        for l in self.lights:
            dx, dy = x - l['x'], y - l['y']
            d = math.sqrt(dx*dx + dy*dy)
            if d < l['r']:
                atten = 1.0 - (d/l['r'])**2
                if l['f'] > 0: atten *= (1.0 + math.sin(l['t']*3.0)*l['f'])
                atten = max(0, min(1, atten))
                r += int(l['c'][0]*l['i']*atten)
                g += int(l['c'][1]*l['i']*atten)
                b += int(l['c'][2]*l['i']*atten)
        return (min(255,r), min(255,g), min(255,b))
    
    def clear(self): self.lights.clear()

class Fog:
    """Volumetric fog effect."""
    def __init__(self):
        self.density = 0.15
        self.color = (12, 18, 15)
        self.distance = 35.0
        self.enabled = True
    
    def apply(self, color: Tuple[int,int,int], dist: float) -> Tuple[int,int,int]:
        if not self.enabled or dist <= 0: return color
        f = min(1.0, (dist / self.distance) * self.density)
        r = int(color[0]*(1-f) + self.color[0]*f)
        g = int(color[1]*(1-f) + self.color[1]*f)
        b = int(color[2]*(1-f) + self.color[2]*f)
        return (r,g,b)

class Grain:
    """Film grain effect."""
    def __init__(self):
        self.amount = 0.05
        self.frame = 0
        self.enabled = True
    
    def apply(self, surf: pygame.Surface) -> pygame.Surface:
        if not self.enabled or self.amount <= 0: return surf
        self.frame += 1
        try:
            a = pygame.surfarray.array3d(surf)
            a = np.transpose(a, (2,0,1))
            np.random.seed(self.frame % 256)
            g = np.random.randn(*a.shape) * (255*self.amount)
            a = np.clip(a.astype(np.float32)+g, 0, 255).astype(np.uint8)
            a = np.transpose(a, (1,2,0))
            return pygame.surfarray.make_surface(a)
        except: return surf

class Grader:
    """Color grading for horror palette."""
    def __init__(self):
        self.strength = 0.6
        self.matrix = np.array([[0.95,0.02,-0.05],[0.0,0.92,0.10],[0.08,0.05,1.02]], dtype=np.float32)
    
    def apply(self, surf: pygame.Surface) -> pygame.Surface:
        if self.strength <= 0: return surf
        try:
            a = pygame.surfarray.array3d(surf)
            a = np.transpose(a, (2,0,1)).astype(np.float32)
            a_r = a.reshape(3,-1)
            g = np.dot(self.matrix, a_r)
            a = g.reshape(a.shape)
            a = np.clip(a, 0, 255).astype(np.uint8)
            a = np.transpose(a, (1,2,0))
            return pygame.surfarray.make_surface(a)
        except: return surf

class Particles:
    """Simple particle system."""
    def __init__(self, max_p=200):
        self.p = []
        self.max_p = max_p
        self.t = 0.0
    
    def spawn(self, x, y, vx=0, vy=0, c=(200,200,200), life=2.0, sz=2.0):
        if len(self.p) < self.max_p:
            self.p.append({'x':x,'y':y,'vx':vx,'vy':vy,'c':c,'life':life,'ml':life,'sz':sz,'t':0})
            return True
        return False
    
    def update(self, dt):
        self.t += dt
        wind_x = math.sin(self.t*0.5)*0.1
        wind_y = math.cos(self.t*0.3)*0.05
        for p in self.p:
            p['vx'] = (p['vx']+wind_x*dt)*0.95
            p['vy'] = (p['vy']+wind_y*dt)*0.95
            p['x'] += p['vx']*dt
            p['y'] += p['vy']*dt
            p['t'] += dt
        self.p = [p for p in self.p if p['t'] < p['life']]
