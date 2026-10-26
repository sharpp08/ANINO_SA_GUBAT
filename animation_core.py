"""
Animation Core - Physics, Springs, Easing, Particles, and Verlet Dynamics.
Built with pure Python, NumPy, and pygame-ce.
"""
import math
import random
import numpy as np
import pygame


class SpringScalar:
    """1D Mass-Spring-Damper system for smooth interpolation and follow-through."""
    def __init__(self, value=0.0, stiffness=120.0, damping=12.0):
        self.value = value
        self.target = value
        self.velocity = 0.0
        self.stiffness = stiffness
        self.damping = damping

    def update(self, dt, target):
        self.target = target
        force = -self.stiffness * (self.value - self.target) - self.damping * self.velocity
        self.velocity += force * dt
        self.value += self.velocity * dt
        return self.value

    def snap(self, value):
        self.value = value
        self.target = value
        self.velocity = 0.0


class Spring2D:
    """2D Mass-Spring-Damper system for camera roll, weapon inertia, and UI pops."""
    def __init__(self, x=0.0, y=0.0, stiffness=140.0, damping=14.0):
        self.x = x
        self.y = y
        self.tx = x
        self.ty = y
        self.vx = 0.0
        self.vy = 0.0
        self.stiffness = stiffness
        self.damping = damping

    def update(self, dt, tx, ty):
        self.tx = tx
        self.ty = ty
        fx = -self.stiffness * (self.x - self.tx) - self.damping * self.vx
        fy = -self.stiffness * (self.y - self.ty) - self.damping * self.vy
        self.vx += fx * dt
        self.vy += fy * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        return self.x, self.y

    def snap(self, x, y):
        self.x = x
        self.y = y
        self.tx = x
        self.ty = y
        self.vx = 0.0
        self.vy = 0.0


def ease_out_back(t):
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)


def ease_in_out_cubic(t):
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2


class Timeline:
    """Sequenced animation timeline for chaining timed callbacks and transitions."""
    def __init__(self):
        self.time = 0.0
        self.events = []

    def add(self, time_offset, callback):
        self.events.append((time_offset, callback))
        self.events.sort(key=lambda x: x[0])

    def update(self, dt):
        self.time += dt
        remaining = []
        for t, cb in self.events:
            if self.time >= t:
                try: cb()
                except Exception: pass
            else:
                remaining.append((t, cb))
        self.events = remaining

    def reset(self):
        self.time = 0.0


class ParticleSystem:
    """NumPy-accelerated vector particle emitter for casings, smoke, sparks, and blood."""
    def __init__(self, max_particles=300):
        self.max_particles = max_particles
        self.count = 0
        self.pos = np.zeros((max_particles, 2), dtype=np.float32)
        self.vel = np.zeros((max_particles, 2), dtype=np.float32)
        self.life = np.zeros(max_particles, dtype=np.float32)
        self.max_life = np.ones(max_particles, dtype=np.float32)
        self.size = np.ones(max_particles, dtype=np.float32)
        self.colors = np.zeros((max_particles, 3), dtype=np.int32)
        self.gravity = 250.0
        self.drag = 0.98
        self.restitution = 0.4

    def emit(self, x, y, vx, vy, life=1.0, size=2.0, color=(200, 200, 200)):
        if self.count >= self.max_particles:
            idx = random.randint(0, self.max_particles - 1)
        else:
            idx = self.count
            self.count += 1
        self.pos[idx] = [x, y]
        self.vel[idx] = [vx, vy]
        self.life[idx] = life
        self.max_life[idx] = max(0.01, life)
        self.size[idx] = size
        self.colors[idx] = color

    def update(self, dt):
        if self.count == 0: return
        active = self.life > 0
        if not np.any(active):
            self.count = 0
            return
        self.vel[active, 1] += self.gravity * dt
        self.vel[active] *= self.drag
        self.pos[active] += self.vel[active] * dt
        self.life[active] -= dt

        ground_y = 350.0
        hit_ground = active & (self.pos[:, 1] >= ground_y)
        if np.any(hit_ground):
            self.pos[hit_ground, 1] = ground_y
            self.vel[hit_ground, 1] = -self.vel[hit_ground, 1] * self.restitution
            self.vel[hit_ground, 0] *= 0.7

    def draw(self, surface):
        if self.count == 0: return
        active_indices = np.where(self.life > 0)[0]
        for idx in active_indices:
            px, py = int(self.pos[idx, 0]), int(self.pos[idx, 1])
            if 0 <= px < surface.get_width() and 0 <= py < surface.get_height():
                sz = max(1, int(self.size[idx] * (self.life[idx] / self.max_life[idx])))
                col = tuple(int(c) for c in self.colors[idx])
                if sz == 1:
                    surface.set_at((px, py), col)
                else:
                    pygame.draw.circle(surface, col, (px, py), sz)


class VerletRope:
    """Verlet integration chain for rosary, hair, vines, and hanging chains."""
    def __init__(self, start_pos, length=6, segment_length=8.0):
        import pygame
        self.points = []
        x, y = start_pos
        for i in range(length):
            self.points.append({'x': x, 'y': y + i * segment_length, 'ox': x, 'oy': y + i * segment_length})
        self.segment_length = segment_length

    def update(self, dt, anchor_pos, wind_x=0.0):
        if not self.points: return
        self.points[0]['x'], self.points[0]['y'] = anchor_pos
        self.points[0]['ox'], self.points[0]['oy'] = anchor_pos
        for i in range(1, len(self.points)):
            p = self.points[i]
            vx = (p['x'] - p['ox']) * 0.98 + wind_x * dt
            vy = (p['y'] - p['oy']) * 0.98 + 400.0 * dt
            p['ox'], p['oy'] = p['x'], p['y']
            p['x'] += vx
            p['y'] += vy
        for _ in range(3):
            self.points[0]['x'], self.points[0]['y'] = anchor_pos
            for i in range(len(self.points) - 1):
                p1 = self.points[i]
                p2 = self.points[i + 1]
                dx = p2['x'] - p1['x']
                dy = p2['y'] - p1['y']
                dist = math.hypot(dx, dy)
                if dist < 1e-5: continue
                diff = (dist - self.segment_length) / dist
                if i > 0:
                    p1['x'] += dx * 0.5 * diff
                    p1['y'] += dy * 0.5 * diff
                    p2['x'] -= dx * 0.5 * diff
                    p2['y'] -= dy * 0.5 * diff
                else:
                    p2['x'] -= dx * diff
                    p2['y'] -= dy * diff


class CameraShake:
    """Decaying smooth camera/screen shake using coherent noise summation."""
    def __init__(self):
        self.intensity = 0.0
        self.duration = 0.0
        self.timer = 0.0

    def add(self, intensity, duration=0.3):
        self.intensity = max(self.intensity, intensity)
        self.duration = max(self.duration, duration)
        self.timer = self.duration

    def update(self, dt):
        if self.timer > 0:
            import pygame
            self.timer -= dt
            if self.timer <= 0:
                self.intensity = 0.0
                return 0, 0
            factor = self.timer / self.duration
            t = pygame.time.get_ticks() * 0.05
            ox = int(math.sin(t * 3.7) * self.intensity * factor * 10)
            oy = int(math.cos(t * 4.3) * self.intensity * factor * 10)
            return ox, oy
        return 0, 0

