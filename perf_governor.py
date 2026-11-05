"""
Performance monitor for ANINO SA GUBAT.

This module measures gameplay frame work without changing graphics quality.
The previous adaptive governor disabled shaders, particles, wind animation,
fog, tree density and photo grading when frame time exceeded its target.
That made performance numbers look better by silently degrading the game.

The monitor-only policy keeps every feature at its configured quality and
reports sustained over-budget frame work so expensive stages can be profiled
and optimized directly. It deliberately imports no pygame modules.
"""
import os
from collections import deque


class PerfGovernor:
    """Backward-compatible name; now monitors performance without shedding quality."""

    BUDGET_MS = 14.5
    WINDOW = 90
    WARMUP = 150
    HITCH_MS = 100.0
    REPORT_INTERVAL = 300  # at most one warning every ~5 seconds at 60 FPS

    def __init__(self, renderer, renderer_module, settings_module, enabled=True):
        # Keep the constructor signature used by main.py and older integrations.
        self.renderer = renderer
        self.rm = renderer_module
        self.sm = settings_module
        env = os.environ.get("ANINO_ADAPTIVE")
        if env in ("0", "1"):
            enabled = env == "1"
        self.enabled = bool(enabled)

        # Compatibility/diagnostic fields. No quality level is ever applied.
        self.level = 0
        self.floor = 0
        self.avg_ms = 0.0
        self.over_budget = False
        self._samples = deque(maxlen=self.WINDOW)
        self._warm = 0
        self._frames = 0
        self._last_report_frame = -self.REPORT_INTERVAL

    def update(self, work_ms, playing):
        """Record CPU frame-work time; never toggle rendering or gameplay features."""
        if not self.enabled:
            return
        if not playing:
            self._warm = 0
            self._frames = 0
            self._samples.clear()
            self.avg_ms = 0.0
            self.over_budget = False
            self._last_report_frame = -self.REPORT_INTERVAL
            return

        try:
            sample = float(work_ms)
        except (TypeError, ValueError):
            return
        if sample < 0.0 or sample > self.HITCH_MS:
            return

        self._warm += 1
        self._frames += 1
        if self._warm <= self.WARMUP:
            return

        self._samples.append(sample)
        if len(self._samples) < self.WINDOW:
            return

        self.avg_ms = sum(self._samples) / len(self._samples)
        self.over_budget = self.avg_ms > self.BUDGET_MS
        if self.over_budget and self._frames - self._last_report_frame >= self.REPORT_INTERVAL:
            print(
                f"[PERF] sustained frame work {self.avg_ms:.1f} ms "
                f"> {self.BUDGET_MS:.1f} ms; visual quality unchanged. "
                "Use F3 stage timings to profile the bottleneck."
            )
            self._last_report_frame = self._frames

    def reset(self):
        """Forget timing history (for example, after loading a new chapter)."""
        self._samples.clear()
        self._warm = 0
        self._frames = 0
        self.avg_ms = 0.0
        self.over_budget = False
        self._last_report_frame = -self.REPORT_INTERVAL
