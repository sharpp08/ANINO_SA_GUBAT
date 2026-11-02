"""Checks the storm logic (lightning schedule, flash envelope, thunder timing, bolt shape, rain
particles).  No pygame or display needed:

    python tests/test_weather_fx.py
"""
import math
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import weather_fx as wf                       # noqa: E402

FOV = math.radians(60)
DT = 1.0 / 60.0


def run_clock(clock, seconds, progress=0.0, angle=0.0):
    """Drive a StormClock at 60 fps; return (strike_starts, thunder_events) with timestamps."""
    t = 0.0
    seen = set()
    starts, thunder = [], []
    for _ in range(int(seconds / DT)):
        events = clock.update(DT, progress, angle, FOV)
        t += DT
        st = clock.strike
        if st is not None and st.serial not in seen:
            seen.add(st.serial)
            starts.append((t, st))
        for ev in events:
            thunder.append((t, ev))
    return starts, thunder


def test_envelope():
    rng = random.Random(1)
    for _ in range(200):
        peak = rng.uniform(0.2, 1.0)
        strokes = wf.make_strokes(rng, rng.randint(1, 6), peak)
        assert 1 <= len(strokes) <= wf.MAX_STROKES            # never more than 3 flashes per strike
        starts = [s[0] for s in strokes]
        assert all(b - a >= 0.14 - 1e-9 for a, b in zip(starts, starts[1:]))   # no strobing
        dur = wf.strokes_duration(strokes)
        vals = [wf.strike_intensity(strokes, i * 0.005) for i in range(int(dur / 0.005) + 1)]
        assert all(0.0 <= v <= 1.0 for v in vals)
        assert max(vals) > 0.6 * peak                          # first stroke really flashes
        assert wf.strike_intensity(strokes, dur) < 0.05        # and it is over when the strike ends
        assert wf.strike_intensity(strokes, -1.0) == 0.0


def test_thunder_follows_flash():
    clock = wf.StormClock(seed=7)
    starts, thunder = run_clock(clock, 600.0)
    assert len(starts) >= 15
    assert len(thunder) >= len(starts) - 1                     # at most the last one still in flight
    matched = 0
    for t_start, st in starts:
        cfg = wf.STRIKE_KINDS[st.kind]
        due = t_start + st.thunder_delay
        # thunder from different strikes may overlap or arrive out of order (a slow far rumble
        # can land after the next strike's crack), so match each strike by its own arrival time
        hits = [(t, ev) for t, ev in thunder
                if abs(t - due) < 0.05 and ev['kind'] == st.kind and ev['volume'] == st.thunder_volume]
        if not hits and due > 600.0:
            continue                                            # still in flight when the run ended
        assert hits, (st.kind, due)
        matched += 1
        assert cfg['delay'][0] <= st.thunder_delay <= cfg['delay'][1]
        assert cfg['volume'][0] <= st.thunder_volume <= cfg['volume'][1]
        assert hits[0][0] > t_start                              # thunder never beats the light
    assert matched >= len(starts) - 1
    kinds = {st.kind for _t, st in starts}
    assert kinds == {wf.NEAR, wf.MID, wf.FAR}                  # a real storm mixes all three
    # farther strikes are dimmer and slower
    peaks = {k: [] for k in kinds}
    for _t, st in starts:
        peaks[st.kind].append(max(a for _s, a, _tau in st.strokes))
    assert min(peaks[wf.NEAR]) > max(peaks[wf.FAR])


def test_strike_rate_is_sane():
    clock = wf.StormClock(seed=3)
    starts, _ = run_clock(clock, 3600.0)
    assert 150 <= len(starts) <= 400, len(starts)              # ~ one every 10-25 s with clusters
    gaps = [b[0] - a[0] for a, b in zip(starts, starts[1:])]
    assert min(gaps) >= 2.0                                    # never flashes more than ~once per 2 s


def test_storm_passes_at_dawn():
    clock = wf.StormClock(seed=5)
    starts, _ = run_clock(clock, 300.0, progress=0.9)
    assert starts == []
    assert wf.storm_activity(0.0) == 1.0 and wf.storm_activity(0.45) == 1.0
    assert wf.storm_activity(0.8) == 0.0 and wf.storm_activity(1.0) == 0.0
    assert 0.0 < wf.storm_activity(0.6) < 1.0
    assert wf.rain_strength(0.45) == 1.0 and wf.rain_strength(1.0) == 0.0
    # near strikes become rare, far ones common, as the storm weakens
    clock = wf.StormClock(seed=9)
    kinds = [clock._pick_kind(0.15) for _ in range(4000)]
    assert kinds.count(wf.NEAR) < 0.05 * 4000
    assert kinds.count(wf.FAR) > kinds.count(wf.MID)


def test_pan_follows_direction():
    clock = wf.StormClock(seed=1)
    st = clock.begin_strike(0.0, FOV, kind=wf.NEAR)
    st.azimuth = 0.5
    clock.pending[0]['azimuth'] = 0.5
    ev = []
    for _ in range(120):
        ev += clock.update(DT, 0.0, 0.0, FOV)
    assert ev and ev[0]['pan'] > 0.2
    st = clock.begin_strike(0.0, FOV, kind=wf.NEAR)
    clock.pending[-1]['azimuth'] = -0.5
    ev = []
    for _ in range(120):
        ev += clock.update(DT, 0.0, 0.0, FOV)
    assert ev and ev[0]['pan'] < -0.2
    assert all(abs(e['pan']) <= 0.75 + 1e-9 for e in ev)


def test_deterministic_for_seed():
    a, ta = run_clock(wf.StormClock(seed=11), 200.0)
    b, tb = run_clock(wf.StormClock(seed=11), 200.0)
    assert [(round(t, 3), s.kind, round(s.azimuth, 6)) for t, s in a] == \
           [(round(t, 3), s.kind, round(s.azimuth, 6)) for t, s in b]
    assert [(round(t, 3), e['kind']) for t, e in ta] == [(round(t, 3), e['kind']) for t, e in tb]


def test_bolt_geometry():
    for seed in range(60):
        w, h = 320, 280
        geo = wf.build_bolt(random.Random(seed), w, h)
        main = geo['main']
        assert len(main) > 20
        assert main[0][1] == 0.0 and main[-1][1] == h - 1          # top edge to bottom edge
        assert 2 <= len(geo['branches']) <= 4
        for pts in [main] + geo['branches']:
            assert all(0.0 <= x <= w - 1 and 0.0 <= y <= h - 1 for x, y in pts)
        assert geo['anchor_x'] == main[-1][0]
    g1 = wf.build_bolt(random.Random(4), 320, 280)
    g2 = wf.build_bolt(random.Random(4), 320, 280)
    assert g1 == g2


def test_rain_particles():
    fx = wf.WeatherFX(640, 360, FOV, seed=2)
    assert len(fx._x) == 110 + 80 + 28
    light = wf.WeatherFX(640, 360, FOV, seed=2, rain_density=0.5)
    assert len(light._x) < len(fx._x)
    for _ in range(600):                                        # 10 s of rain
        fx.update(DT, 0.0, yaw=0.0, pitch=0.0, wind=0.4)
    assert np.isfinite(fx._x).all() and np.isfinite(fx._y).all()
    # the sky is still evenly filled (nothing piled up or drained away)
    inside = (fx._y > 0) & (fx._y < 360)
    assert inside.mean() > 0.6
    for lo in (0, 120, 240):
        assert ((fx._y >= lo) & (fx._y < lo + 120)).sum() > 20
    left = (fx._x < 320).sum()
    assert 0.25 < left / len(fx._x) < 0.75
    # three depth layers fall at clearly different speeds
    by_layer = [fx._speed[fx._layer == i].mean() for i in range(3)]
    assert by_layer[0] < by_layer[1] < by_layer[2]
    # splashes appear, stay bounded and live briefly
    fx.horizon_y = 180
    for _ in range(300):
        fx.update(DT, 0.0)
        fx.horizon_y = 180
    assert 0 < len(fx.splashes) <= wf.MAX_SPLASHES
    assert all(0.0 <= s[1] <= 1.0 and s[2] < s[3] for s in fx.splashes)


def test_rain_slides_with_camera_turn():
    fx = wf.WeatherFX(640, 360, FOV, seed=2)
    fx.update(0.0, 0.0, yaw=0.0, pitch=0.0)
    x0, y0 = fx._x.copy(), fx._y.copy()
    fx.update(0.0, 0.0, yaw=0.05, pitch=0.02)
    expected_x = -0.05 * 640 / FOV
    assert abs(np.median(fx._x - x0) - expected_x) < 1.0
    assert abs(np.median(fx._y - y0) - 0.02 * 360) < 1.0
    # a teleport (new chapter) must not smear the rain across the screen
    before = fx._x.copy()
    fx.update(0.0, 0.0, yaw=2.5, pitch=0.0)
    assert np.allclose(fx._x, before)


def test_rain_fades_with_dawn():
    fx = wf.WeatherFX(640, 360, FOV, seed=2)
    fx.horizon_y = 180
    for _ in range(120):
        fx.update(DT, 0.0)
    assert fx.splashes
    fx.update(DT, 1.0)
    assert fx.strength == 0.0 and fx.splashes == []
    fx.update(DT, 0.7)
    assert 0.0 < fx.strength < 1.0
    quiet = wf.WeatherFX(640, 360, FOV, seed=2, rain=False, lightning=False)
    assert quiet.update(1.0, 0.0) == []


if __name__ == '__main__':
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith('test_') and callable(f)]
    for name, fn in tests:
        fn()
        print('ok  ', name)
    print(f'{len(tests)} weather_fx checks passed')
