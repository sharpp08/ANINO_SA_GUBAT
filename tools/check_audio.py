"""Quick diagnostic for audio_synth.py — run with SDL_AUDIODRIVER=dummy."""
import os
os.environ['SDL_AUDIODRIVER'] = 'dummy'
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
import audio_synth

mgr = audio_synth.audio_mgr
r = mgr.rate
ok = True

# 1) all sounds built
for name, snd in mgr.sounds.items():
    if snd is None:
        print(f'FAIL  sound {name!r} is None (build failed)')
        ok = False

# 2) footstep variants
variants = mgr.variants.get('footstep', [])
print(f'INFO  footstep variants: {len(variants)}')
if len(variants) < 2:
    print('WARN  expected 4 footstep variants, got fewer')

# 3) _mix with mixed mono / stereo
mono  = np.random.default_rng(0).standard_normal(int(r * 0.1))
stereo = np.random.default_rng(1).standard_normal((int(r * 0.1), 2))
mix_ms = mgr._mix([(0.0, mono), (0.05, stereo)])
print(f'INFO  _mix(mono→stereo) shape={mix_ms.shape}  expect ({int(r*0.15)}, 2)')
if mix_ms.ndim != 2 or mix_ms.shape[1] != 2:
    print('FAIL  _mix(mono→stereo) did not produce stereo output')
    ok = False

mix_sm = mgr._mix([(0.0, stereo), (0.05, mono)])
print(f'INFO  _mix(stereo→mono) shape={mix_sm.shape}')
if mix_sm.ndim != 2 or mix_sm.shape[1] != 2:
    print('FAIL  _mix(stereo→mono) did not produce stereo output')
    ok = False

# 4) muffled cache
snd = mgr.sounds['shotgun']
m0 = mgr.muffled(snd, 0)
m1 = mgr.muffled(snd, 1)
m2 = mgr.muffled(snd, 2)
m3 = mgr.muffled(snd, 3)
print(f'INFO  muffled(0)={m0 is not None}  muffled(1)={m1 is not None}  muffled(2)={m2 is not None}  muffled(3)={m3 is not None}')
if m0 is not snd:
    print('WARN  muffled(0) should return the original, not a copy')

# 5) spatial_params out of range
sp_out = mgr.spatial_params(0, 0, 0, 50, 0, base_volume=1.0, max_dist=15.0)
print(f'INFO  spatial_params(50 m, max 15 m) -> {sp_out}  expect None')
if sp_out is not None:
    print('FAIL  spatial_params should return None when out of range')
    ok = False

sp_in = mgr.spatial_params(0, 0, 0, 5, 0, base_volume=1.0, max_dist=15.0)
print(f'INFO  spatial_params(5 m) -> vol={sp_in[0]:.3f} pan={sp_in[1]:+.3f} muffle={sp_in[2]}')

# 6) stop_intro_ambience  (just check it doesn't crash)
try:
    mgr.stop_intro_ambience()
    print('INFO  stop_intro_ambience: OK')
except Exception as e:
    print(f'FAIL  stop_intro_ambience: {e}')
    ok = False

# 7) set_ambience_active
try:
    mgr.set_ambience_active(True)
    mgr.set_ambience_active(False)
    print('INFO  set_ambience_active True→False: OK')
except Exception as e:
    print(f'FAIL  set_ambience_active: {e}')
    ok = False

# 8) update_ambience (with ambience not active, should be no-op)
try:
    mgr.update_ambience(0.016)
    print('INFO  update_ambience (inactive): OK (no-op)')
except Exception as e:
    print(f'FAIL  update_ambience: {e}')
    ok = False

print()
print('ALL CHECKS PASSED' if ok else 'SOME CHECKS FAILED')
sys.exit(0 if ok else 1)
