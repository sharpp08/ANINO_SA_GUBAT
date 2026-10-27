"""
Animation Core v2 - Realistic motion upgrade (drop-in replacement for animation_core.py)

Same public API as v1 (SpringScalar, Spring2D, Timeline, ParticleSystem, VerletRope,
CameraShake, SpriteAnimation, get_enemy_animation_system) so nothing breaks, plus:

  * Stable springs        - sub-stepped semi-implicit Euler, velocity/value clamps,
                            impulse() hits, critically-damped factory presets.
  * ValueNoise1D          - coherent Perlin-style noise: organic idle motion with
                            temporal continuity (replaces frame-random jitter).
  * Frame-rate independence - particle drag / verlet gravity no longer depend on FPS.
  * Trauma CameraShake    - layered multi-frequency shake, intensity = trauma^2.
  * Flicker               - flashlight/light flicker with intensity levels.
  * Easing library        - anticipation & follow-through curves for attacks.

Swap: back up the old animation_core.py, then copy this file over it.
"""
import math
import random
import numpy as np
import pygame

TAU = math.pi * 2


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


# ─── Easing (v1 curves kept identical, new ones added) ───────────────────────
def ease_out_back(t):
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)


def ease_in_out_cubic(t):
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2


def ease_out_cubic(t):
    return 1.0 - pow(1.0 - t, 3)


def ease_in_quad(t):
    return t * t


def ease_out_quad(t):
    return 1.0 - (1.0 - t) * (1.0 - t)


def ease_out_elastic(t):
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return pow(2.0, -10.0 * t) * math.sin((t * 10.0 - 0.75) * (TAU / 3.0)) + 1.0


def ease_out_bounce(t):
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


# ─── Coherent value noise (organic, temporally smooth) ───────────────────────
class ValueNoise1D:
    """Seeded 1D value noise with fBm octaves. Output in [-1, 1].

    Use for idle sway, breathing wobble, tree rustle, flicker patterns -
    anything that should look alive instead of random-per-frame.
    """
    def __init__(self, seed=None, octaves=2):
        self.seed = random.randint(0, 2 ** 30) if seed is None else int(seed)
        self.octaves = max(1, int(octaves))

    def _hash(self, i):
        n = (i * 374761393 + self.seed * 668265263) & 0xFFFFFFFF
        n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
        return (((n ^ (n >> 16)) & 0xFFFF) / 32767.5) - 1.0

    def sample(self, x):
        total, amp, freq, norm = 0.0, 1.0, 1.0, 0.0
        for _ in range(self.octaves):
            xi = math.floor(x * freq)
            f = x * freq - xi
            u = f * f * (3.0 - 2.0 * f)
            total += amp * (self._hash(xi) * (1.0 - u) + self._hash(xi + 1) * u)
            norm += amp
            amp *= 0.5
            freq *= 2.0
        return total / norm if norm > 0.0 else 0.0


# ─── Springs ─────────────────────────────────────────────────────────────────
class SpringScalar:
    """1D mass-spring-damper, sub-stepped for stability at any frame rate.

    v1-compatible: update(dt, target), snap(value). New: impulse(), settled,
    min/max clamps, and critically_damped() factory.
    """
    def __init__(self, value=0.0, stiffness=120.0, damping=12.0,
                 min_value=None, max_value=None):
        self.value = float(value)
        self.target = float(value)
        self.velocity = 0.0
        self.stiffness = float(stiffness)
        self.damping = float(damping)
        self.min_value = min_value
        self.max_value = max_value
        self.max_velocity = None  # set to clamp runaway impulses

    @classmethod
    def critically_damped(cls, value=0.0, frequency=8.0, **kw):
        """No-overshoot spring: damping = 2*sqrt(k*m), m = 1."""
        k = frequency * frequency
        c = 2.0 * math.sqrt(k)
        return cls(value, stiffness=k, damping=c, **kw)

    def update(self, dt, target):
        self.target = float(target)
        # sub-step so stiff springs stay stable even if the frame hitches
        steps = max(1, int(dt / 0.008) + 1)
        h = dt / steps
        for _ in range(steps):
            force = (-self.stiffness * (self.value - self.target)
                     - self.damping * self.velocity)
            self.velocity += force * h          # semi-implicit Euler
            self.value += self.velocity * h
        if self.max_velocity is not None:
            self.velocity = clamp(self.velocity, -self.max_velocity, self.max_velocity)
        if self.min_value is not None:
            self.value = max(self.min_value, self.value)
        if self.max_value is not None:
            self.value = min(self.max_value, self.value)
        return self.value

    def impulse(self, velocity):
        """Kick the spring (hit reactions, recoil, landings)."""
        self.velocity += velocity

    @property
    def settled(self):
        return abs(self.value - self.target) < 0.001 and abs(self.velocity) < 0.001

    def snap(self, value):
        self.value = float(value)
        self.target = float(value)
        self.velocity = 0.0


class Spring2D:
    """2D mass-spring-damper (camera roll, weapon inertia, UI pops)."""
    def __init__(self, x=0.0, y=0.0, stiffness=140.0, damping=14.0):
        self.x, self.y = float(x), float(y)
        self.tx, self.ty = float(x), float(y)
        self.vx = self.vy = 0.0
        self.stiffness = float(stiffness)
        self.damping = float(damping)

    def update(self, dt, tx, ty):
        self.tx, self.ty = float(tx), float(ty)
        steps = max(1, int(dt / 0.008) + 1)
        h = dt / steps
        for _ in range(steps):
            fx = -self.stiffness * (self.x - self.tx) - self.damping * self.vx
            fy = -self.stiffness * (self.y - self.ty) - self.damping * self.vy
            self.vx += fx * h
            self.vy += fy * h
            self.x += self.vx * h
            self.y += self.vy * h
        return self.x, self.y

    def impulse(self, vx, vy):
        self.vx += vx
        self.vy += vy

    def snap(self, x, y):
        self.x = self.tx = float(x)
        self.y = self.ty = float(y)
        self.vx = self.vy = 0.0


# ─── Timeline (unchanged) ────────────────────────────────────────────────────
class Timeline:
    """Sequenced animation timeline for chaining timed callbacks."""
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
                try:
                    cb()
                except Exception:
                    pass
            else:
                remaining.append((t, cb))
        self.events = remaining

    def reset(self):
        self.time = 0.0


# ─── Particles ───────────────────────────────────────────────────────────────
class ParticleSystem:
    """NumPy particle emitter. v1-compatible emit(); fixes frame-rate-dependent
    drag, adds per-particle gravity/drag, colour fade, and burst emitters."""

    def __init__(self, max_particles=300):
        self.max_particles = max_particles
        self.count = 0
        n = max_particles
        self.pos = np.zeros((n, 2), dtype=np.float32)
        self.vel = np.zeros((n, 2), dtype=np.float32)
        self.life = np.zeros(n, dtype=np.float32)
        self.max_life = np.ones(n, dtype=np.float32)
        self.size = np.ones(n, dtype=np.float32)
        self.colors = np.zeros((n, 3), dtype=np.int32)
        self.grav_scale = np.ones(n, dtype=np.float32)
        self.drag_scale = np.ones(n, dtype=np.float32)
        self.gravity = 250.0
        self.drag = 0.98          # per-60fps-frame multiplier (dt-corrected in update)
        self.restitution = 0.4
        self.ground_y = 350.0

    def emit(self, x, y, vx, vy, life=1.0, size=2.0, color=(200, 200, 200),
             gravity_scale=1.0, drag_scale=1.0):
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
        self.grav_scale[idx] = gravity_scale
        self.drag_scale[idx] = drag_scale
        return idx

    def burst(self, x, y, count=12, speed=(40, 160), life=1.0, size=2.0,
              color=(200, 200, 200), angle=0.0, spread=TAU,
              gravity_scale=1.0, drag_scale=1.0, up_bias=0.0):
        """Radial/cone burst. angle + spread in radians; up_bias lifts velocities."""
        for _ in range(count):
            a = angle + random.uniform(-spread / 2.0, spread / 2.0)
            s = random.uniform(speed[0], speed[1])
            self.emit(x, y,
                      math.cos(a) * s,
                      math.sin(a) * s - up_bias,
                      life=random.uniform(life * 0.6, life * 1.2),
                      size=random.uniform(size * 0.6, size * 1.3),
                      color=color,
                      gravity_scale=gravity_scale,
                      drag_scale=drag_scale)

    def update(self, dt):
        if self.count == 0:
            return
        active = self.life > 0
        if not np.any(active):
            self.count = 0
            return

        # dt-corrected drag: same look at any FPS (v1 multiplied raw per frame)
        drag_now = self.drag ** (dt * 60.0)
        self.vel[active, 1] += self.gravity * self.grav_scale[active] * dt
        self.vel[active] *= (drag_now ** self.drag_scale[active])
        self.pos[active] += self.vel[active] * dt
        self.life[active] -= dt

        hit = active & (self.pos[:, 1] >= self.ground_y)
        if np.any(hit):
            self.pos[hit, 1] = self.ground_y
            self.vel[hit, 1] = -self.vel[hit, 1] * self.restitution
            self.vel[hit, 0] *= 0.7

    def draw(self, surface):
        if self.count == 0:
            return
        w, h = surface.get_width(), surface.get_height()
        for idx in np.where(self.life > 0)[0]:
            px, py = int(self.pos[idx, 0]), int(self.pos[idx, 1])
            if 0 <= px < w and 0 <= py < h:
                fade = self.life[idx] / self.max_life[idx]
                sz = max(1, int(self.size[idx] * fade))
                base = self.colors[idx]
                col = (int(base[0] * fade), int(base[1] * fade), int(base[2] * fade))
                if sz == 1:
                    surface.set_at((px, py), col)
                else:
                    pygame.draw.circle(surface, col, (px, py), sz)


# ─── Verlet rope ─────────────────────────────────────────────────────────────
class VerletRope:
    """Verlet chain (rosary, hair, vines). v1 API; gravity/dt fixed for any FPS."""

    def __init__(self, start_pos, length=6, segment_length=8.0, seed=None):
        self.points = []
        x, y = start_pos
        for i in range(length):
            self.points.append({'x': x, 'y': y + i * segment_length,
                                'ox': x, 'oy': y + i * segment_length})
        self.segment_length = segment_length
        self.wind_noise = ValueNoise1D(seed=seed, octaves=2)
        self.wind_time = 0.0

    def update(self, dt, anchor_pos, wind_x=0.0):
        if not self.points:
            return
        self.wind_time += dt
        # organic gusts layered on top of the caller's wind
        wind = wind_x + self.wind_noise.sample(self.wind_time * 0.7) * 60.0

        self.points[0]['x'], self.points[0]['y'] = anchor_pos
        self.points[0]['ox'], self.points[0]['oy'] = anchor_pos
        for i in range(1, len(self.points)):
            p = self.points[i]
            vx = (p['x'] - p['ox']) * 0.98 + wind * dt * dt * 60.0
            vy = (p['y'] - p['oy']) * 0.98 + 2400.0 * dt * dt  # verlet: a*dt^2
            p['ox'], p['oy'] = p['x'], p['y']
            p['x'] += vx
            p['y'] += vy
        for _ in range(3):
            self.points[0]['x'], self.points[0]['y'] = anchor_pos
            for i in range(len(self.points) - 1):
                p1, p2 = self.points[i], self.points[i + 1]
                dx, dy = p2['x'] - p1['x'], p2['y'] - p1['y']
                dist = math.hypot(dx, dy)
                if dist < 1e-5:
                    continue
                diff = (dist - self.segment_length) / dist
                if i > 0:
                    p1['x'] += dx * 0.5 * diff
                    p1['y'] += dy * 0.5 * diff
                    p2['x'] -= dx * 0.5 * diff
                    p2['y'] -= dy * 0.5 * diff
                else:
                    p2['x'] -= dx * diff
                    p2['y'] -= dy * diff


# ─── Trauma-based camera shake ───────────────────────────────────────────────
class CameraShake:
    """Layered shake: smooth noise (low freq) + jitter (high freq) + roll.
    add() keeps the v1 signature; perceived shake scales with trauma^2 so small
    hits stay subtle and big hits feel violent. update(dt) -> (ox, oy)."""

    def __init__(self):
        self.trauma = 0.0
        self.duration = 0.0
        self.timer = 0.0
        self.max_offset = 14.0
        self.noise_x = ValueNoise1D(seed=1337, octaves=2)
        self.noise_y = ValueNoise1D(seed=7331, octaves=2)
        self.time = 0.0
        self.roll = 0.0

    def add(self, intensity, duration=0.3):
        # v1 mapped intensity straight to pixels; map it into trauma space
        self.trauma = max(self.trauma, clamp(intensity, 0.0, 1.0))
        self.duration = max(self.duration, duration)
        self.timer = self.duration

    def update(self, dt):
        if self.timer <= 0:
            self.roll = 0.0
            return 0, 0
        self.timer -= dt
        if self.timer <= 0:
            self.trauma = 0.0
            self.roll = 0.0
            return 0, 0

        self.time += dt
        decay = self.timer / self.duration if self.duration > 0 else 0.0
        shake = self.trauma * self.trauma * decay  # trauma^2 falloff

        low_x = self.noise_x.sample(self.time * 2.1) * 0.7
        low_y = self.noise_y.sample(self.time * 2.3) * 0.7
        high_x = math.sin(self.time * 47.0) * 0.3
        high_y = math.cos(self.time * 53.0) * 0.3

        ox = int((low_x + high_x) * self.max_offset * shake)
        oy = int((low_y + high_y) * self.max_offset * shake)
        self.roll = (low_x * 2.5) * shake  # degrees, for rotational kick
        return ox, oy


# ─── Light flicker ───────────────────────────────────────────────────────────
class Flicker:
    """Realistic light flicker. Levels: 0 steady, 1 uneasy, 2 violent.
    Returns a brightness multiplier each frame; feed into your darkness pass."""

    PATTERNS = {
        0: (1.0, 1.0, 0.0),     # steady
        1: (0.75, 1.0, 0.6),    # occasional dips
        2: (0.35, 1.0, 2.2),    # hard cutouts + strobing
    }

    def __init__(self, seed=None):
        self.noise = ValueNoise1D(seed=seed, octaves=3)
        self.time = 0.0
        self.level = 0
        self.multiplier = 1.0

    def update(self, dt, level):
        self.time += dt
        self.level = int(clamp(level, 0, 2))
        lo, hi, freq = self.PATTERNS[self.level]
        if self.level == 0:
            self.multiplier = 1.0
            return self.multiplier
        n = self.noise.sample(self.time * freq)
        # bias toward "on", occasional deep cutouts
        t = clamp(0.5 + 0.5 * n, 0.0, 1.0)
        t = t * t
        self.multiplier = lo + (hi - lo) * t
        if self.level == 2 and self.noise.sample(self.time * 7.7) < -0.72:
            self.multiplier = lo * 0.4  # hard blackout beat
        return self.multiplier


# ─── Sprite sheet animation (v1-compatible, fps/ping-pong added) ─────────────
class SpriteAnimation:
    """Horizontal-strip sprite animation. Same loading API as v1."""

    STATE_TO_SHEET = {
        'idle': 'run', 'walk': 'run', 'run': 'run', 'sprint': 'run',
        'crawl': 'crawl', 'stalk': 'crawl', 'crouch': 'crawl',
        'attack': 'attack', 'lunge': 'attack', 'stagger': 'attack', 'death': 'attack',
        'hover': 'run', 'float': 'run',
        'transform': 'transform', 'fly': 'fly', 'rear': 'rear',
        'smash': 'smash', 'vanish': 'vanish', 'phase': 'phase', 'pounce': 'pounce',
    }

    UNIQUE_MOVES = {
        'aswang': 'transform', 'manananggal': 'fly', 'tikbalang': 'rear',
        'kapre': 'smash', 'white_lady': 'vanish', 'multo': 'phase', 'sigbin': 'pounce',
    }

    def __init__(self, fps=14.0, pingpong=False):
        self.fps = float(fps)
        self.pingpong = pingpong
        self.frame_time = 1.0 / max(1.0, self.fps)
        self.frames = {}
        self.loaded = False
        self._cycle = 0.0

    def set_fps(self, fps):
        self.fps = max(1.0, float(fps))
        self.frame_time = 1.0 / self.fps

    def get_state_sheet_name(self, enemy_type: str, state: str) -> str:
        if state == 'special' and enemy_type in self.UNIQUE_MOVES:
            state = self.UNIQUE_MOVES[enemy_type]
        return self.STATE_TO_SHEET.get(state, 'run')

    def load_from_pack(self, pack_dir: str, target_size: int = 64):
        import os
        sheets_dir = os.path.join(pack_dir, 'sheets')
        if not os.path.exists(sheets_dir):
            print(f"[SpriteAnimation] Sheets directory not found: {sheets_dir}")
            return False

        enemy_types = ['aswang', 'manananggal', 'tikbalang', 'kapre',
                       'white_lady', 'multo', 'sigbin']

        for etype in enemy_types:
            self.frames[etype] = {}
            for sheet_file in os.listdir(sheets_dir):
                if not sheet_file.startswith(f'{etype}_') or not sheet_file.endswith('.png'):
                    continue
                sheet_name = sheet_file[len(etype) + 1:-4]
                sheet_path = os.path.join(sheets_dir, sheet_file)
                try:
                    sheet_surf = pygame.image.load(sheet_path)
                    try:
                        sheet_surf = sheet_surf.convert_alpha()
                    except Exception:
                        if sheet_surf.get_colorkey() is None:
                            sheet_surf = sheet_surf.convert()
                    sheet_w, sheet_h = sheet_surf.get_size()
                    num_frames = 6
                    frame_w = sheet_w // num_frames
                    frame_list = []
                    for i in range(num_frames):
                        rect = pygame.Rect(i * frame_w, 0, frame_w, sheet_h)
                        frame = sheet_surf.subsurface(rect).copy()
                        frame_list.append(pygame.transform.scale(frame, (target_size, target_size)))
                    self.frames[etype][sheet_name] = frame_list
                    print(f"[SpriteAnimation] Loaded {etype}_{sheet_name}: {num_frames} frames")
                except Exception as e:
                    print(f"[SpriteAnimation] Failed to load {sheet_path}: {e}")

        self.loaded = len(self.frames) > 0
        return self.loaded

    def frame_at(self, state_time: float, num_frames: int):
        """Map a continuous time to a frame index (honours ping-pong)."""
        if num_frames <= 1:
            return 0
        if self.pingpong and num_frames > 2:
            cycle = (state_time * self.fps) % (2 * num_frames - 2)
            idx = int(cycle)
            if idx >= num_frames:
                idx = 2 * num_frames - 2 - idx
            return idx
        return int(state_time * self.fps) % num_frames

    def get_frame(self, enemy_type: str, state: str, frame_index: int):
        if enemy_type not in self.frames:
            return None
        sheet_name = self.get_state_sheet_name(enemy_type, state)
        frame_list = self.frames[enemy_type].get(sheet_name)
        if frame_list is None:
            frame_list = self.frames[enemy_type].get('run')
        if frame_list is None:
            for name in ['attack', 'crawl', 'run']:
                if name in self.frames[enemy_type]:
                    frame_list = self.frames[enemy_type][name]
                    break
        if not frame_list:
            return None
        return frame_list[frame_index % len(frame_list)]

    def get_frames_for_state(self, enemy_type: str, state: str) -> list:
        if enemy_type not in self.frames:
            return []
        sheet_name = self.get_state_sheet_name(enemy_type, state)
        return self.frames[enemy_type].get(sheet_name, [])


_enemy_animation_system = None


def get_enemy_animation_system():
    """Get or create the global enemy animation system."""
    global _enemy_animation_system
    if _enemy_animation_system is None:
        _enemy_animation_system = SpriteAnimation(fps=14.0)
    return _enemy_animation_system
