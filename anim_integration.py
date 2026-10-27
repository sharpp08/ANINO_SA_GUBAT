"""
anim_integration.py - Realistic enemy motion for ANINO SA GUBAT.

Drop this file next to the other modules. It replaces the raw math.sin() /
random.uniform() animation block in renderer.py::_draw_enemy with spring-driven,
noise-modulated motion that has real anticipation and follow-through:

  idle   : slow coherent breathing (noise + micro sway, per-enemy seed)
  walk   : weight shift + gait bob
  stalk  : low, prowling sway with pauses
  attack : WINDUP (0.16s squash crouch) -> LUNGE (0.13s stretch) -> spring RECOVER
  hit    : scale impulse kicks the spring (visible stagger)
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
                'atk_t': None,
                'was_attacking': False,
                'was_hit': False,
            }
            enemy._ra = rec
        return rec

    def update_all(self, enemies, dt):
        for e in enemies:
            self._update_one(e, dt)

    def _update_one(self, enemy, dt):
        rec = self._rec(enemy)
        attacking = enemy.animation_state in ('attack', 'lunge')

        # attack phase timing
        if attacking and not rec['was_attacking']:
            rec['atk_t'] = 0.0
        elif not attacking:
            rec['atk_t'] = None
        rec['was_attacking'] = attacking
        if rec['atk_t'] is not None:
            rec['atk_t'] += dt

        # hit reaction: kick the scale spring when hit_flash spikes
        if enemy.hit_flash > 0.95 and not rec['was_hit']:
            rec['spring_scale'].impulse(6.0)
            rec['spring_hover'].impulse(-2.2)
        rec['was_hit'] = enemy.hit_flash > 0.5

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

    def transform(self, enemy, t_s):
        """Return render transform values. t_s = seconds (pygame.time.get_ticks()/1000)."""
        rec = self._rec(enemy)
        n = rec['noise']
        ph = (enemy.spawn_x * 0.37 + enemy.spawn_y * 0.91) % 10.0
        st = enemy.animation_state

        # organic breathing: noise-modulated, never a pure metronome sine
        breath_amp = 0.030
        breathe = rec['spring_scale'].value * (1.0 + breath_amp * n.sample(t_s * 0.45 + ph))

        # gait / stalk sway
        if st in ('run', 'sprint'):
            sway = n.sample(t_s * 1.4 + ph) * 0.9
        elif st in ('crawl', 'stalk'):
            sway = n.sample(t_s * 0.8 + ph) * 0.5
        else:
            sway = n.sample(t_s * 0.5 + ph) * 0.35

        # hover: floating types ride the spring; grounded types keep tiny settle
        floats = enemy.type in ('manananggal', 'multo', 'white_lady')
        if floats:
            hover = rec['spring_hover'].value + 0.06 * n.sample(t_s * 0.4 + ph)
        elif st in ('crawl', 'crouch', 'stalk'):
            hover = -0.18
        else:
            hover = rec['spring_hover'].value * 0.3

        # coherent attack jitter (v1 used random.uniform per frame: TV static)
        jitter = 0.0
        if rec['atk_t'] is not None and rec['atk_t'] > WINDUP:
            jitter = rec['noise_fast'].sample(t_s * 11.0) * 2.4

        return {'breathe': breathe, 'sway': sway, 'hover': hover, 'jitter': jitter}


_animator = None


def get_enemy_animator():
    global _animator
    if _animator is None:
        _animator = RealisticEnemyAnimator()
    return _animator
