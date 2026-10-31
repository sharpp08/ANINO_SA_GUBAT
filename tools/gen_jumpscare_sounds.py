"""
Generate an individual jumpscare sound for each enemy.

    python tools/gen_jumpscare_sounds.py            # writes any missing files
    python tools/gen_jumpscare_sounds.py --force    # regenerate everything (also multo)

Output: enemy_animations_pack/<enemy>_jumpscare.wav  (44.1 kHz, 16-bit stereo)
jumpscare.py auto-loads these. multo_jumpscare.wav (your own sound) is never
overwritten unless you pass --force --include-multo.

Only needs numpy (already a game dependency).
"""
import os
import sys
import wave
import numpy as np

SR = 44100
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'enemy_animations_pack')


# ── building blocks ────────────────────────────────────────────────────────────
def tvec(dur):
    return np.arange(int(dur * SR)) / SR


def phase(f):
    return np.cumsum(2 * np.pi * f / SR)


def saw(f):
    return 2.0 * ((phase(f) / (2 * np.pi)) % 1.0) - 1.0


def sine(f):
    return np.sin(phase(f))


def smooth(rng, n, hz):
    """Slow random wobble in [-1, 1]."""
    pts = rng.uniform(-1, 1, max(2, int(n / SR * hz) + 2))
    return np.interp(np.linspace(0, len(pts) - 1, n), np.arange(len(pts)), pts)


def env(n, att=0.01, rel=0.2, hold=None):
    e = np.ones(n)
    a = max(1, int(att * SR))
    e[:a] = np.linspace(0, 1, a)
    r = max(1, int(rel * SR))
    e[-r:] *= np.linspace(1, 0, r) ** 1.5
    return e


def formants(x, peaks, base=0.08):
    """Static vowel colouring via FFT: peaks = [(freq, bandwidth, gain), ...]."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    H = np.full_like(f, base)
    for fc, bw, g in peaks:
        H += g * np.exp(-0.5 * ((f - fc) / bw) ** 2)
    return np.fft.irfft(X * H, len(x))


def lowpass(x, fc):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X / (1 + (f / fc) ** 4), len(x))


def highpass(x, fc):
    return x - lowpass(x, fc)


def drive(x, d):
    return np.tanh(d * x) / np.tanh(d)


def reverb(x, rng, rt60=1.2, wet=0.3):
    n = int(rt60 * SR)
    ir = rng.standard_normal(n) * np.exp(-6.9 * np.arange(n) / n)
    ir = lowpass(ir, 5000)
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    size = len(x) + n
    y = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)
    out = np.zeros(size)
    out[:len(x)] += x * (1 - wet)
    out += y * wet * 1.4
    return out


def impact(rng, dur=0.9, boom_hz=120, punch=1.0):
    """Sub-bass boom + noise crack: the 'hit' that makes a jumpscare land."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    sweep = boom_hz * np.exp(-t * 5.5) + 32
    boom = np.sin(phase(sweep)) * np.exp(-t * 4.0)
    crack = lowpass(rng.standard_normal(n), 6000) * np.exp(-t * 28.0)
    thump = highpass(rng.standard_normal(n), 120) * np.exp(-t * 9.0) * 0.25
    return punch * (1.0 * boom + 0.9 * crack + thump)


def pad(x, n):
    out = np.zeros(n)
    out[:min(n, len(x))] = x[:n]
    return out


def place(dst, src, start_s, gain=1.0):
    s = int(start_s * SR)
    e = min(len(dst), s + len(src))
    if e > s:
        dst[s:e] += src[:e - s] * gain


# ── enemy voices ───────────────────────────────────────────────────────────────
def aswang(rng):
    """Raspy, wet, rising shriek over a gurgling growl."""
    d = 1.9
    n = int(d * SR)
    t = tvec(d)
    rise = np.clip(t / 0.30, 0, 1) ** 1.5
    f0 = (170 + 380 * rise) * (1 + 0.05 * np.sin(2 * np.pi * 9 * t)) * (1 + 0.04 * smooth(rng, n, 30))
    v = saw(f0) * 0.7 + saw(f0 * 1.012) * 0.5
    v += lowpass(rng.standard_normal(n), 5000) * 0.55 * (0.4 + 0.6 * np.abs(smooth(rng, n, 25)))
    v = formants(v, [(800, 120, 1.0), (1150, 150, 0.8), (2700, 300, 0.4)])
    v = drive(v * 1.4, 4.0) * env(n, 0.012, 0.55)
    gurgle = saw(np.full(n, 82.0) * (1 + 0.1 * np.sin(2 * np.pi * 5 * t)))
    gurgle = lowpass(gurgle * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 21 * t))), 600) * env(n, 0.05, 0.9)
    return v * 0.85 + gurgle * 0.55


def manananggal(rng):
    """Piercing high screech with fluttering wing beats."""
    d = 1.8
    n = int(d * SR)
    t = tvec(d)
    f0 = (900 + 900 * np.clip(t / 0.4, 0, 1)) * (1 + 0.035 * np.sin(2 * np.pi * 7.5 * t))
    v = saw(f0) * 0.6 + sine(f0 * 2) * 0.3
    v += lowpass(rng.standard_normal(n), 7000) * 0.25
    v = formants(v, [(1500, 250, 1.0), (2900, 400, 0.9), (4200, 500, 0.4)])
    flap = 0.55 + 0.45 * np.sin(2 * np.pi * 6.0 * t) ** 2
    v = drive(v * 1.5, 3.2) * flap * env(n, 0.008, 0.6)
    flutter = highpass(lowpass(rng.standard_normal(n), 3000), 300)
    flutter *= (np.sin(2 * np.pi * 6.0 * t) > 0.35) * np.exp(-t * 1.2) * 0.5
    return v * 0.8 + flutter


def tikbalang(rng):
    """Demonic horse whinny: swooping hee-haw bray over galloping hooves."""
    d = 2.0
    n = int(d * SR)
    t = tvec(d)
    swoop = np.clip(t / 0.35, 0, 1) ** 1.3
    flip = 0.5 + 0.5 * np.tanh(5.0 * np.sin(2 * np.pi * 2.8 * t + 0.6))
    f0 = (300 + 800 * swoop) * (0.62 + 0.55 * flip) * (1 + 0.05 * np.sin(2 * np.pi * 14 * t))
    v = saw(f0) * 0.8 + saw(f0 * 1.007) * 0.5
    v += lowpass(rng.standard_normal(n), 4500) * 0.3
    v = formants(v, [(900, 160, 1.0), (2200, 300, 0.8), (3400, 400, 0.4)])
    v = drive(v * 1.5, 3.5) * env(n, 0.02, 0.5)
    hooves = np.zeros(n)
    for k in range(int(d * 7.0)):
        thud = lowpass(rng.standard_normal(int(0.09 * SR)), 450) * np.exp(-np.arange(int(0.09 * SR)) / (0.02 * SR))
        place(hooves, thud * 3.0, k / 7.0 + (0.035 if k % 2 else 0.0), np.exp(-k / 9.0))
    return v * 0.85 + hooves * 0.7


def kapre(rng):
    """Huge, deep, booming roar with a rumbling laugh."""
    d = 2.2
    n = int(d * SR)
    t = tvec(d)
    f0 = (72 + 38 * np.clip(t / 0.5, 0, 1)) * (1 + 0.03 * smooth(rng, n, 7))
    v = saw(f0) * 0.8 + saw(f0 * 0.5) * 0.7 + saw(f0 * 2.01) * 0.3
    v += lowpass(rng.standard_normal(n), 900) * 0.6
    v = formants(v, [(500, 90, 1.0), (900, 140, 0.8), (1800, 250, 0.3)], base=0.05)
    ho = 0.55 + 0.45 * np.abs(np.sin(np.pi * 2.7 * t))
    v = drive(v * 1.6, 5.0) * ho * env(n, 0.03, 0.8)
    rumble = sine(np.full(n, 38.0)) * np.exp(-t * 1.1)
    return v * 0.9 + rumble * 0.8


def white_lady(rng):
    """Haunting wail that cracks into a shriek, drowning in reverb."""
    d = 2.4
    n = int(d * SR)
    t = tvec(d)
    arc = np.sin(np.pi * np.clip(t / 1.8, 0, 1))
    f0 = (560 + 360 * arc) * (1 + 0.04 * np.sin(2 * np.pi * 5.5 * t))
    v = saw(f0) * 0.5 + sine(f0) * 0.6 + sine(f0 * 3) * 0.15
    v += lowpass(rng.standard_normal(n), 6000) * 0.22
    v = formants(v, [(600, 100, 1.0), (1000, 140, 0.8), (2500, 300, 0.5)])
    v = v * env(n, 0.06, 0.9)
    m = int(0.45 * SR)
    tt = np.arange(m) / SR
    shriek = saw(1650 * (1 + 0.05 * np.sin(2 * np.pi * 11 * tt)))
    shriek = formants(shriek, [(1700, 250, 1.0), (3200, 400, 0.7)])
    shriek = drive(shriek * 1.5, 4.0) * env(m, 0.004, 0.35)
    out = np.zeros(n)
    out += v * 0.85
    place(out, shriek, 0.0, 0.8)
    return out


def sigbin(rng):
    """Chittering, snarling creature that ends in a high shriek."""
    d = 1.6
    n = int(d * SR)
    t = tvec(d)
    fm = 1 + 0.25 * np.sin(2 * np.pi * 40 * t)
    f0 = (300 + 700 * np.clip((t - 0.9) / 0.5, 0, 1) ** 2) * fm
    v = saw(f0) * 0.8 + lowpass(rng.standard_normal(n), 5000) * 0.5
    v = formants(v, [(700, 120, 1.0), (1800, 250, 0.9), (3300, 400, 0.4)])
    chit = np.clip((np.sin(2 * np.pi * 18 * t) + 0.35) * 3.0, 0, 1)
    gate = np.where(t < 1.0, chit, 0.6 + 0.4 * chit)
    v = drive(v * 1.5, 3.8) * gate * env(n, 0.01, 0.4)
    return v


def multo(rng):
    """Only used with --include-multo (otherwise your own mp3/wav is kept)."""
    d = 1.8
    n = int(d * SR)
    t = tvec(d)
    f0 = 245 * (1 + 0.02 * np.sin(2 * np.pi * 3.5 * t)) * (1.0 + 1.1 * np.clip((t - 0.2) / 0.5, 0, 1))
    v = sine(f0) * 0.7 + saw(f0) * 0.3 + lowpass(rng.standard_normal(n), 3000) * 0.5
    v = formants(v, [(400, 80, 1.0), (800, 120, 0.8)])
    return drive(v * 1.5, 3.0) * (0.7 + 0.3 * np.sin(2 * np.pi * 9 * t)) * env(n, 0.03, 0.6)


# name -> (voice fn, boom_hz, impact punch, reverb rt60, reverb wet, squash)
# squash = how hard the final soft-clipper pushes (higher = louder / denser)
ENEMIES = {
    'aswang':      (aswang,      130, 1.0, 0.9, 0.18, 1.8),
    'manananggal': (manananggal, 160, 0.9, 1.2, 0.22, 2.0),
    'tikbalang':   (tikbalang,   110, 1.0, 0.9, 0.18, 1.8),
    'kapre':       (kapre,        90, 1.3, 1.6, 0.25, 2.1),
    'white_lady':  (white_lady,  100, 0.8, 2.0, 0.30, 4.0),
    'sigbin':      (sigbin,      140, 1.0, 0.7, 0.15, 1.8),
}


def render(name, seed):
    fn, boom, punch, rt60, wet, squash = ENEMIES[name]
    rng = np.random.default_rng(seed)
    voice = fn(rng)
    total = len(voice) + int(0.2 * SR)
    mix = np.zeros(total)
    place(mix, impact(rng, 0.9, boom, punch), 0.0, 1.0)
    place(mix, voice, 0.02, 1.0)
    mix = reverb(mix, rng, rt60, wet)
    # glue + loudness: soft-clip then normalise like a loud horror stinger
    mix = np.tanh(squash * mix / (np.max(np.abs(mix)) + 1e-9))
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * 0.97
    # trim silent tail, short fade
    loud = np.nonzero(np.abs(mix) > 0.004)[0]
    if len(loud):
        mix = mix[:loud[-1] + 1]
    k = min(len(mix), int(0.03 * SR))
    mix[-k:] *= np.linspace(1, 0, k)
    # stereo width: Haas delay + slight decorrelation
    d = int(0.011 * SR)
    left = mix
    right = np.concatenate([np.zeros(d), mix[:-d]]) * 0.96
    return np.stack([left, right], axis=1)


def write_wav(path, stereo):
    data = (np.clip(stereo, -1, 1) * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def main():
    force = '--force' in sys.argv
    include_multo = '--include-multo' in sys.argv
    os.makedirs(OUT_DIR, exist_ok=True)
    names = list(ENEMIES)
    if include_multo:
        ENEMIES['multo'] = (multo, 120, 1.0, 2.0, 0.4, 2.0)
        names.append('multo')
    for i, name in enumerate(names):
        path = os.path.join(OUT_DIR, f'{name}_jumpscare.wav')
        if os.path.exists(path) and not force:
            print(f'[skip] {path} already exists (use --force to regenerate)')
            continue
        stereo = render(name, seed=1000 + i)
        write_wav(path, stereo)
        print(f'[ok]   {path}  ({len(stereo) / SR:.2f}s)')


if __name__ == '__main__':
    main()
