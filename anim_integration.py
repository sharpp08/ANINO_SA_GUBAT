"""
anim_integration.py - Realistic enemy motion for ANINO SA GUBAT.

Drop this file next to the other modules. It replaces the raw math.sin() /
random.uniform() animation block in renderer.py::_draw_enemy with spring-driven,
noise-modulated motion that has real anticipation and follow-through:

  idle   : slow coherent breathing (noise + micro sway, per-enemy seed)
  walk   : weight shift + gait bob
  stalk  : low, prowling sway with pauses
  attack : WINDUP (0.16s squash crouch) -> LUNGE (0.13s stretch) -> spring RECOVER
  hit    : per-hit squash/rebound, sideways flinch and tilt, scaled by hit strength
  hover  : floating types bob on a soft spring instead of a fixed sine

WIRING (2 small edits in renderer.py - see INTEGRATION_GUIDE.md):
  1) In Renderer.__init__ add:   self.enemy_animator = get_enemy_animator()
  2) In render_frame() (has dt) add:
         self.enemy_animator.update_all(enemies, dt)
  3) In _draw_enemy() replace the breathe/sway/hover block with:
         tr = self.enemy_animator.transform(enemy, t_ticks * 0.001)
         breathe, sway, hover, jit = tr['breathe'], tr['sway'], tr['hover'], tr['jitter']
"""
import math
from animation_core import SpringScalar, ValueNoise1D

WINDUP = 0.16
LUNGE = 0.13


class RealisticEnemyAnimator:
    """Per-enemy spring+noise animation state. Attach state onto enemy objects."""

    def _rec(self, enemy):
        rec = getattr(enemy, '_ra', None)
        if rec is None:
            # stable seed from spawn position (v1 used id(enemy): memory address,
            # which changes between runs and can collide)
            seed = (int(enemy.spawn_x * 131) ^ int(enemy.spawn_y * 57)) & 0x7FFFFFFF
            rec = {
                'noise': ValueNoise1D(seed=seed, octaves=2),
                'noise_fast': ValueNoise1D(seed=seed + 999, octaves=1),
                'spring_scale': SpringScalar(1.0, stiffness=240.0, damping=20.0,
                                             min_value=0.55, max_value=1.65),
                'spring_hover': SpringScalar(0.0, stiffness=70.0, damping=8.0),
                # lateral flinch (fraction of sprite width) and tilt (degrees) from hits
                'spring_flinch': SpringScalar(0.0, stiffness=190.0, damping=13.0),
                'spring_tilt': SpringScalar(0.0, stiffness=130.0, damping=9.0),
                'atk_t': None,
                'was_attacking': False,
                'hit_seq': getattr(enemy, 'hit_seq', 0),
                'last_x': float(enemy.x), 'last_y': float(enemy.y),
                'move_speed': 0.0, 'gait_phase': (seed % 628) / 100.0,
                'last_facing': float(getattr(enemy, 'facing_angle', 0.0)),
                'turn_rate': 0.0,
                'spring_lean': SpringScalar(0.0, stiffness=95.0, damping=16.0),
            }
            enemy._ra = rec
        return rec

    def update_all(self, enemies, dt):
        for e in enemies:
            self._update_one(e, dt)

    def _update_one(self, enemy, dt):
        rec = self._rec(enemy)
        attacking = enemy.animation_state in ('attack', 'lunge')

        # Measure actual movement so gait cadence follows acceleration and collisions.
        dt_safe = max(1.0 / 240.0, min(float(dt), 0.05))
        dx = float(enemy.x) - rec['last_x']
        dy = float(enemy.y) - rec['last_y']
        measured_speed = math.hypot(dx, dy) / dt_safe
        rec['last_x'], rec['last_y'] = float(enemy.x), float(enemy.y)
        base_speed = max(0.1, float(getattr(enemy, 'base_speed', 1.0)))
        speed_ratio = min(1.35, measured_speed / base_speed)
        blend = 1.0 - math.exp(-8.0 * dt_safe)
        rec['move_speed'] += (speed_ratio - rec['move_speed']) * blend
        facing = float(getattr(enemy, 'facing_angle', rec['last_facing']))
        turn_delta = (facing - rec['last_facing'] + math.pi) % (math.pi * 2.0) - math.pi
        rec['last_facing'] = facing
        turn_rate = turn_delta / dt_safe
        rec['turn_rate'] += (turn_rate - rec['turn_rate']) * (1.0 - math.exp(-10.0 * dt_safe))
        lean_target = max(-5.0, min(5.0, -rec['turn_rate'] * 0.055))
        rec['spring_lean'].update(dt_safe, lean_target)
        if rec['move_speed'] > 0.035:
            rec['gait_phase'] = (rec['gait_phase'] + dt_safe * (5.0 + rec['move_speed'] * 8.0)) % (math.pi * 2.0)

        # attack phase timing
        if attacking and not rec['was_attacking']:
            rec['atk_t'] = 0.0
        elif not attacking:
            rec['atk_t'] = None
        rec['was_attacking'] = attacking
        if rec['atk_t'] is not None:
            rec['atk_t'] += dt

        # Hit reaction, fired once per hit (hit_seq), scaled by how hard it landed:
        #   impact squash -> rebound overshoot, sideways flinch, tilt away, hover jolt.
        seq = getattr(enemy, 'hit_seq', 0)
        if seq != rec['hit_seq']:
            rec['hit_seq'] = seq
            s = getattr(enemy, 'hit_strength', 0.6)
            side = getattr(enemy, 'hit_side', 1)
            rec['spring_scale'].impulse(-5.5 * s)
            rec['spring_hover'].impulse(-2.4 * s)
            rec['spring_flinch'].impulse(side * 3.4 * s)
            rec['spring_tilt'].impulse(-side * 95.0 * s)

        # phase-driven targets
        target_scale, target_hover = 1.0, 0.0
        if rec['atk_t'] is not None:
            t = rec['atk_t']
            if t < WINDUP:
                # anticipation: squash down, coil
                target_scale, target_hover = 0.84, -0.05
            elif t < WINDUP + LUNGE:
                # follow-through: stretch up and forward
                target_scale, target_hover = 1.30, 0.04
        rec['spring_scale'].update(dt, target_scale)
        rec['spring_hover'].update(dt, target_hover)
        rec['spring_flinch'].update(dt, 0.0)
        rec['spring_tilt'].update(dt, 0.0)

    def transform(self, enemy, t_s):
        """Return render transform values. t_s = seconds (pygame.time.get_ticks()/1000)."""
        rec = self._rec(enemy)
        n = rec['noise']
        ph = (enemy.spawn_x * 0.37 + enemy.spawn_y * 0.91) % 10.0
        st = enemy.animation_state

        # organic breathing: noise-modulated, never a pure metronome sine
        breath_amp = 0.030
        moving = rec['move_speed']
        gait = math.sin(rec['gait_phase'])
        gait_abs = abs(gait)
        gait_amount = min(1.0, moving * 1.25) if st in ('run', 'sprint', 'walk', 'crawl', 'stalk') else 0.0
        breathe = rec['spring_scale'].value * (1.0 + breath_amp * n.sample(t_s * 0.45 + ph) - 0.018 * gait_abs * gait_amount)

        # Gait follows actual speed, with a restrained alternating weight shift.
        if gait_amount > 0.0:
            sway = gait * 0.52 * gait_amount + n.sample(t_s * 0.55 + ph) * 0.12
        else:
            sway = n.sample(t_s * 0.42 + ph) * 0.28
        turn_lean = rec['spring_lean'].value

        # hover: floating types ride the spring; grounded types keep tiny settle
        floats = enemy.type in ('manananggal', 'multo', 'white_lady')
        if floats:
            hover = rec['spring_hover'].value + 0.045 * n.sample(t_s * 0.4 + ph) + 0.018 * math.sin(rec['gait_phase'] * 0.5)
        elif st in ('crawl', 'crouch', 'stalk'):
            hover = -0.18 - 0.018 * gait_abs * gait_amount
        else:
            hover = rec['spring_hover'].value * 0.3 + 0.012 * gait_abs * gait_amount

        # coherent attack jitter (v1 used random.uniform per frame: TV static)
        jitter = 0.0
        if rec['atk_t'] is not None and rec['atk_t'] > WINDUP:
            jitter = rec['noise_fast'].sample(t_s * 11.0) * 2.4

        return {'breathe': breathe, 'sway': sway, 'hover': hover, 'jitter': jitter,
                'flinch': rec['spring_flinch'].value, 'tilt': rec['spring_tilt'].value + turn_lean}


_animator = None


def get_enemy_animator():
    global _animator
    if _animator is None:
        _animator = RealisticEnemyAnimator()
    return _animator
