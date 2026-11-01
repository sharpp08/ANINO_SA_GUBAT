"""
Performance Profiling and Benchmarking Suite for ANINO SA GUBAT.
Measures average FPS, frame-time percentiles (p50, p95, p99), test scene,
internal/display resolution, and hardware platform info.
"""
import os
import sys
import time
import platform
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

# The renderer copies resolution/quality constants from settings at import time,
# and main.py applies settings.json's quality_tier on import. So the preset must
# be chosen BEFORE importing main/renderer, which means one process per preset
# (see __main__ below). Without this every preset measured the same resolution.
_PRESET = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ('low', 'medium', 'high') else None
import settings as _settings
if _PRESET:
    _orig_load_settings = _settings.load_settings
    _settings.load_settings = lambda *a, **k: {**_orig_load_settings(*a, **k), 'quality_tier': _PRESET}
    _settings.apply_quality_preset(_PRESET)

import pygame
pygame.init()

from settings import *
from main import Game, STATE_PLAYING


def run_benchmark(preset_name='medium', num_frames=300):
    print(f"\n=== RUNNING PERFORMANCE BENCHMARK [Preset: {preset_name}] ===")
    
    game = Game()
    game.load_chapter(1)
    game.state = STATE_PLAYING
    
    frame_times = []
    
    # Warmup
    for _ in range(10):
        game.dt = 0.016
        game.update_playing(0.016, 0, 0)
        game.renderer.render_frame(game.player, game.game_map, game.enemy_manager.get_alive_enemies(), game.effects, 0.016)
    
    # Benchmark loop
    start_total = time.perf_counter()
    for i in range(num_frames):
        t0 = time.perf_counter()
        game.dt = 0.016
        game.update_playing(0.016, 0.1 if i % 10 == 0 else 0.0, 0.0)
        game.renderer.render_frame(game.player, game.game_map, game.enemy_manager.get_alive_enemies(), game.effects, 0.016)
        t1 = time.perf_counter()
        frame_times.append((t1 - t0) * 1000.0)  # in milliseconds
        
    total_time = time.perf_counter() - start_total
    
    ft_arr = np.array(frame_times)
    avg_fps = num_frames / total_time
    p50 = np.percentile(ft_arr, 50)
    p95 = np.percentile(ft_arr, 95)
    p99 = np.percentile(ft_arr, 99)
    
    hardware_info = {
        "Platform": platform.platform(),
        "Processor": platform.processor() or "Unknown CPU",
        "Python": platform.python_version(),
        "CPU Cores": os.cpu_count() or 1,
    }
    
    report = {
        "Test Scene": "Chapter 1 (Outdoor Forest & Cabin)",
        "Internal Resolution": f"{INTERNAL_WIDTH}x{INTERNAL_HEIGHT}",
        "Display Resolution": f"{SCREEN_WIDTH}x{SCREEN_HEIGHT}",
        "Quality Preset": preset_name,
        "Frames Renders": num_frames,
        "Average FPS": round(avg_fps, 2),
        "Frame Time p50 (median)": round(p50, 2),
        "Frame Time p95": round(p95, 2),
        "Frame Time p99": round(p99, 2),
        "Hardware": hardware_info,
    }
    
    print("\n--- BENCHMARK RESULTS REPORT ---")
    for k, v in report.items():
        print(f"  {k}: {v}")
    print("--------------------------------\n")
    return report


if __name__ == '__main__':
    if _PRESET:
        # Child process: measure exactly one preset.
        run_benchmark(_PRESET, num_frames=150)
    else:
        # Parent: one fresh interpreter per preset so the settings really apply.
        import subprocess
        os.makedirs('reports', exist_ok=True)
        for preset in ['low', 'medium', 'high']:
            subprocess.run([sys.executable, os.path.abspath(__file__), preset], check=True)
        print("[PASS] Performance profiling and benchmarking completed successfully.")
