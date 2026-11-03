"""
Adaptive performance governor for ANINO SA GUBAT.

Goal: hold 60+ FPS on whatever machine the game runs on. The game is a CPU software
renderer, so frame cost varies a lot between PCs. Instead of guessing, this measures the
real per-frame work time (everything except the vsync/idle wait) and, when the average
stays above the 60 FPS budget, switches off the most expensive optional effects one level
at a time. When the machine has plenty of headroom for a while it switches them back on.

Levels (cumulative, cheapest visual loss first):
  1  GPU post-process pass (per-frame CPU<->GPU readback)
  2  Floating particles, physics particles and twinkling stars
  3  Tree/plant wind sway and 40% fewer billboard trees
  4  Depth-fog overlay and a further tree cut

Disable with "adaptive_perf": false in settings.json or the ANINO_ADAPTIVE=0 env var.
This module deliberately imports nothing heavy (no pygame) so it can be unit-tested.
"""
import os
from collections import deque

LEVEL_NAMES = {
    0: "full quality",
    1: "GPU post-process off",
    2: "particles + stars off",
    3: "wind sway off, fewer trees",
    4: "depth fog off, minimum trees",
}
MAX_LEVEL = 4


class PerfGovernor:
    BUDGET_MS = 14.5        # shed above this average (60 FPS = 16.67 ms; keep headroom for flip/upload)
    RESTORE_MS = 10.0       # only consider restoring below this average
    WINDOW = 90             # frames averaged (~1.5 s at 60 FPS)
    WARMUP = 150            # ignore frames right after loading (cache fills, shader compile)
    COOLDOWN = 180          # frames to wait after any level change
    RESTORE_AFTER = 600     # frames of sustained headroom before restoring one level (~10 s)
    HITCH_MS = 100.0        # single frames longer than this (loading, window drag) are ignored

    def __init__(self, renderer, renderer_module, settings_module, enabled=True):
        self.renderer = renderer
        self.rm = renderer_module
        self.sm = settings_module
        env = os.environ.get('ANINO_ADAPTIVE')
        if env in ('0', '1'):
            enabled = (env == '1')
        self.enabled = bool(enabled)
        self.level = 0
        self.floor = 0              # never restore below this (set if restoring made us shed again)
        self.avg_ms = 0.0
        self._samples = deque(maxlen=self.WINDOW)
        self._warm = 0
        self._cooldown = 0
        self._idle = 0
        self._last_action = None
        # Remember the user's configured values so they can be restored exactly.
        self._orig = {
            'ENABLE_PARTICLES': getattr(self.rm, 'ENABLE_PARTICLES', True),
            'ENABLE_PARTICLE_PHYSICS': getattr(self.rm, 'ENABLE_PARTICLE_PHYSICS', True),
            'ENABLE_ENV_ANIM': getattr(self.rm, 'ENABLE_ENV_ANIM', True),
            'MAX_RENDER_TREES': getattr(self.rm, 'MAX_RENDER_TREES', 150),
            'ENABLE_FOG': getattr(self.sm, 'ENABLE_FOG', True),
        }
        sr = getattr(self.renderer, 'shader_renderer', None)
        self._shader_was_on = bool(sr is not None and getattr(sr, 'enabled', False))

    # ── public API ───────────────────────────────────────────────────────
    def update(self, work_ms, playing):
        """Call once per rendered frame with the CPU work time in milliseconds."""
        if not self.enabled:
            return
        if not playing:
            self._warm = 0
            self._samples.clear()
            return
        self._warm += 1
        if self._warm < self.WARMUP or work_ms > self.HITCH_MS:
            return
        if self._cooldown > 0:
            self._cooldown -= 1
        self._samples.append(work_ms)
        if len(self._samples) < self.WINDOW:
            return
        self.avg_ms = sum(self._samples) / len(self._samples)

        if self.avg_ms > self.BUDGET_MS and self.level < MAX_LEVEL and self._cooldown <= 0:
            if self._last_action == 'restore':
                self.floor = self.level + 1      # restoring didn't hold; stop trying it
            self._set_level(self.level + 1, f"avg work {self.avg_ms:.1f} ms > {self.BUDGET_MS} ms")
            self._last_action = 'shed'
        elif self.avg_ms < self.RESTORE_MS and self.level > self.floor:
            self._idle += 1
            if self._idle >= self.RESTORE_AFTER and self._cooldown <= 0:
                self._set_level(self.level - 1, f"avg work {self.avg_ms:.1f} ms, headroom")
                self._last_action = 'restore'
        else:
            self._idle = 0

    def reset(self):
        """Forget history (e.g. new chapter). Keeps the current level."""
        self._samples.clear()
        self._warm = 0
        self._idle = 0

    # ── internals ────────────────────────────────────────────────────────
    def _set_level(self, level, reason):
        self.level = max(0, min(MAX_LEVEL, level))
        self._cooldown = self.COOLDOWN
        self._idle = 0
        self._samples.clear()
        self._apply(self.level)
        print(f"[PERF] {reason} -> level {self.level}: {LEVEL_NAMES[self.level]}")

    def _apply(self, level):
        o, rm = self._orig, self.rm
        sr = getattr(self.renderer, 'shader_renderer', None)
        if sr is not None and self._shader_was_on:
            sr.enabled = not (level >= 1)
        rm.ENABLE_PARTICLES = o['ENABLE_PARTICLES'] and not (level >= 2)
        rm.ENABLE_PARTICLE_PHYSICS = o['ENABLE_PARTICLE_PHYSICS'] and not (level >= 2)
        self.renderer.perf_no_stars = level >= 2
        rm.ENABLE_ENV_ANIM = o['ENABLE_ENV_ANIM'] and not (level >= 3)
        if level >= 4:
            rm.MAX_RENDER_TREES = max(20, int(o['MAX_RENDER_TREES'] * 0.35))
        elif level >= 3:
            rm.MAX_RENDER_TREES = max(30, int(o['MAX_RENDER_TREES'] * 0.6))
        else:
            rm.MAX_RENDER_TREES = o['MAX_RENDER_TREES']
        self.sm.ENABLE_FOG = o['ENABLE_FOG'] and not (level >= 4)
