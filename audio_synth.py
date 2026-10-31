"""
Procedural audio engine for ANINO SA GUBAT (NumPy + Pygame mixer).

Every sound is synthesised at start-up from physical-style models instead of
plain sine/noise blips:

* gunshots   - muzzle crack + blast + pitch-dropping boom + room tail + outdoor
               slap-back echoes off the trees, plus a pump-action rack
* footsteps  - heel thump + soil + leaf/twig crunch grains (4 random variants)
* door       - latch click, stick-slip hinge creak through wood resonances, knock
* chimes     - inharmonic modal synthesis (bell partials with their own decay)
* wind       - gusting multi-band noise with a wandering howl
* crickets   - real chirp/pulse structure, 5 overlapping insects, seamless loop
* owl, snap, rustle - distant forest one-shots
* voices     - glottal source + formant filtering (used for creature / enemy calls)

At play time sounds are positioned with equal-power panning, distance
air-absorption (progressively muffled copies, cached lazily) and rear-facing
muffling, and a quiet forest ambience bed is looped on reserved channels.

Public API (unchanged): audio_mgr.play / play_spatial / start_intro_ambience /
stop_intro_ambience / play_drone.  New: spatial_params, play_object, muffled,
set_ambience_active, update_ambience.
"""
import math
import random
import zlib

import numpy as np
import pygame

# scipy's FFT is ~2x faster and multi-threaded; numpy's is the dependency-free fallback.
try:
    from scipy import fft as _fftmod
    _FFT_KW = {'workers': -1}
except Exception:                                   # pragma: no cover
    _fftmod = np.fft
    _FFT_KW = {}


def _rfft(x, n=None, axis=-1):
    return _fftmod.rfft(x, n, axis, **_FFT_KW)


def _irfft(x, n=None, axis=-1):
    return _fftmod.irfft(x, n, axis, **_FFT_KW)


# ─────────────────────────────────────────────────────────────────────────────
#  DSP toolkit (numpy only)
# ─────────────────────────────────────────────────────────────────────────────
def _rng(name):
    """Reproducible RNG per sound name so every launch sounds identical."""
    return np.random.default_rng(zlib.crc32(str(name).encode('utf-8')))


def _pow2(n):
    return 1 << max(1, int(n - 1).bit_length())


def _t(n, rate):
    return np.arange(n, dtype=np.float64) / rate


def _stereo(x):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        return np.column_stack((x, x))
    return x


def _pk(x):
    """Normalise to unit peak (leaves silence untouched)."""
    m = float(np.max(np.abs(x))) if len(x) else 0.0
    return x / m if m > 1e-12 else x


def _std1(x):
    s = float(np.std(x))
    return x / s if s > 1e-12 else x


def fft_filter(x, rate, lo=None, hi=None, order=2, pad=True):
    """Butterworth-magnitude high/low-pass applied in the frequency domain.

    pad=False filters circularly, which keeps looping material seamless.
    """
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 2:
        return np.column_stack([
            fft_filter(x[:, c], rate, lo, hi, order, pad) for c in range(x.shape[1])
        ])
    n = len(x)
    big = _pow2(n * 2) if pad else n
    spec = _rfft(x, big)
    f = np.fft.rfftfreq(big, 1.0 / rate)
    h = np.ones(len(f))
    if hi:
        h /= np.sqrt(1.0 + (f / hi) ** (2 * order))
    if lo:
        h /= np.sqrt(1.0 + (lo / np.maximum(f, 1e-6)) ** (2 * order))
    return _irfft(spec * h, big)[:n]


def fft_band(x, rate, center, bw_oct=1.0, pad=True):
    """Gaussian band-pass in log-frequency (bandwidth in octaves)."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 2:
        return np.column_stack([
            fft_band(x[:, c], rate, center, bw_oct, pad) for c in range(x.shape[1])
        ])
    n = len(x)
    big = _pow2(n * 2) if pad else n
    spec = _rfft(x, big)
    f = np.maximum(np.fft.rfftfreq(big, 1.0 / rate), 1.0)
    h = np.exp(-0.5 * (np.log2(f / center) / max(bw_oct * 0.5, 1e-3)) ** 2)
    return _irfft(spec * h, big)[:n]


def fft_conv(a, b):
    n = len(a) + len(b) - 1
    big = _pow2(n)
    return _irfft(_rfft(a, big) * _rfft(b, big), big)[:n]


def smooth_noise(n, rate, hz, rng, loop=False):
    """Slowly wandering random curve (~unit variance) - used for gusts, jitter."""
    k = max(3, int(n / rate * hz) + 2)
    pts = rng.standard_normal(k)
    if loop:
        pts[-1] = pts[0]
    x = np.arange(n) * ((k - 1) / n)
    i = np.minimum(x.astype(int), k - 2)
    u = x - i
    s = u * u * (3.0 - 2.0 * u)
    return pts[i] * (1.0 - s) + pts[i + 1] * s


def fade(x, rate, fade_in=0.0, fade_out=0.0):
    n = len(x)
    g = np.ones(n)
    a = int(fade_in * rate)
    b = int(fade_out * rate)
    if a > 1:
        g[:a] = np.sin(np.linspace(0, np.pi / 2, a)) ** 2
    if b > 1:
        g[-b:] *= np.cos(np.linspace(0, np.pi / 2, b)) ** 2
    return x * (g[:, None] if x.ndim == 2 else g)


def sine_sweep(t, rate, f_start, f_end, tau):
    """Sine whose pitch decays exponentially from f_start to f_end."""
    f = f_end + (f_start - f_end) * np.exp(-t / tau)
    return np.sin(2 * np.pi * np.cumsum(f) / rate)


_IR_CACHE = {}


def _get_ir(rate, rt60, brightness):
    key = (rate, round(rt60, 2), round(brightness, 2))
    ir = _IR_CACHE.get(key)
    if ir is not None:
        return ir
    rng = np.random.default_rng(int(rt60 * 1000) * 7 + int(brightness * 100))
    n = int(rate * rt60 * 1.1)
    t = _t(n, rate)
    ir = np.zeros((n, 2))
    for c in range(2):
        noise = rng.standard_normal(n)
        dark = fft_filter(noise, rate, hi=700 + 2600 * brightness, order=2)
        dark = _std1(dark)
        w = np.exp(-t / (0.12 * rt60 + 0.04)) * brightness
        sig = dark * (1.0 - w) + noise * w * 0.6
        ir[:, c] = sig * np.exp(-6.9078 * t / rt60)
    pre = int(0.008 * rate)
    ir[:pre] = 0.0
    for c in range(2):                      # sparse early reflections
        for _ in range(7):
            d = pre + int(rng.uniform(0.004, 0.07) * rate)
            if d < n:
                ir[d, c] += rng.uniform(-1, 1) * 3.0
    ir /= math.sqrt(float(np.sum(ir ** 2)) / 2.0)
    _IR_CACHE[key] = ir
    return ir


def reverb(x, rate, rt60=1.0, wet=0.3, brightness=0.5, echoes=None, dry=1.0):
    """Stereo convolution reverb (synthetic decorrelated IR) with optional
    discrete slap-back echoes [(delay_s, gain, lowpass_hz), ...]."""
    x = _stereo(x)
    n = len(x)
    ir = _get_ir(rate, rt60, brightness)
    m = len(ir)
    echo_len = 0
    if echoes:
        echo_len = max(int(d * rate) for d, _, _ in echoes) + n
    total = max(n + m - 1, echo_len)
    big = _pow2(n + m - 1)
    wet_sig = _irfft(
        _rfft(x, big, axis=0) * _rfft(ir, big, axis=0), big, axis=0
    )[:n + m - 1]
    out = np.zeros((total, 2))
    out[:n] += x * dry
    out[:n + m - 1] += wet_sig * wet
    if echoes:
        for delay, gain, cutoff in echoes:
            d = int(delay * rate)
            src = fft_filter(x, rate, hi=cutoff, order=1)
            out[d:d + n] += src * gain
    return out


def _formant_response(f, formants, floor=0.04):
    h = np.full(len(f), floor) + 0.5 / (1.0 + (f / 300.0) ** 2)
    for fc, bw, g in formants:
        h += g / (1.0 + ((f - fc) / (bw * 0.5)) ** 2)
    return h


def formant_filter(x, rate, formants, floor=0.04):
    """Shape a source with vocal-tract resonances [(centre_hz, bw_hz, gain)]."""
    n = len(x)
    big = _pow2(n * 2)
    spec = _rfft(x, big)
    f = np.fft.rfftfreq(big, 1.0 / rate)
    return _irfft(spec * _formant_response(f, formants, floor), big)[:n]


def _vowel(f1, f2, f3):
    return [(f1, 90, 1.0), (f2, 120, 0.75), (f3, 180, 0.45), (3500, 260, 0.2)]


VOWELS = {
    'a': _vowel(730, 1090, 2440),
    'e': _vowel(530, 1840, 2480),
    'i': _vowel(270, 2290, 3010),
    'o': _vowel(570, 840, 2410),
    'u': _vowel(300, 870, 2240),
}


def synth_voice(rate, f0, vowel_a='a', vowel_b=None, morph=None, tilt=1.6,
                breath=0.1, jitter=0.01, subharm=0.0, rough=(0.0, 0.0),
                whisper=0.0, rng=None, max_harm=34):
    """Source-filter voice.  f0 is a per-sample pitch curve in Hz."""
    rng = rng or np.random.default_rng(1)
    n = len(f0)
    t = _t(n, rate)
    f = f0 * (1.0 + jitter * smooth_noise(n, rate, 45, rng))
    phase = np.cumsum(f) / rate
    fmin = max(float(np.min(f)), 20.0)
    kmax = int(max(4, min(max_harm, 5500.0 / fmin)))
    theta = 2 * np.pi * phase
    cos_t = np.cos(theta)
    prev2 = np.zeros(n)                      # sin(0*theta)
    prev1 = np.sin(theta)                    # sin(1*theta)
    kcut = 0.45 * rate / f                   # harmonics above Nyquist-ish are dropped
    src = prev1 * (kcut > 1.0)
    for k in range(2, kmax + 1):             # Chebyshev recurrence: one multiply-add per harmonic
        cur = 2.0 * cos_t * prev1 - prev2
        src += (k ** -tilt) * cur * (kcut > k)
        prev2, prev1 = prev1, cur
    if subharm > 0.0:                       # vocal-fry / bi-phonation roughness
        for k in range(4):
            src += subharm * ((k + 0.5) ** -tilt) * np.sin(2 * np.pi * (k + 0.5) * phase)
    if rough[0] > 0.0 and rough[1] > 0.0:
        src *= 1.0 - rough[1] * (0.5 + 0.5 * np.sin(2 * np.pi * rough[0] * t))
    src = _std1(src)
    noise = rng.standard_normal(n)
    exc = (1.0 - whisper) * src + (whisper + breath) * noise
    big = _pow2(n * 2)
    spec = _rfft(exc, big)
    freqs = np.fft.rfftfreq(big, 1.0 / rate)
    ya = _irfft(spec * _formant_response(freqs, VOWELS[vowel_a]), big)[:n]
    if vowel_b is not None and morph is not None:
        yb = _irfft(spec * _formant_response(freqs, VOWELS[vowel_b]), big)[:n]
        ya = ya * (1.0 - morph) + yb * morph
    return _pk(ya)


# ─────────────────────────────────────────────────────────────────────────────
#  Sound manager
# ─────────────────────────────────────────────────────────────────────────────
MUFFLE_CUTOFFS = (None, 5000.0, 2400.0, 1100.0)
AMBIENCE_RESERVED = 2          # channels 0/1 hold the wind + cricket beds


class SoundManager:
    def __init__(self):
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        except Exception:
            try:
                pygame.mixer.init(frequency=22050, size=-16, channels=2)
            except Exception:
                pass
        mixer_init = pygame.mixer.get_init()
        self.sample_rate = mixer_init[0] if mixer_init else 44100
        self.rate = self.sample_rate
        self.channels = mixer_init[2] if mixer_init and len(mixer_init) > 2 else 2
        try:
            pygame.mixer.set_num_channels(32)
            pygame.mixer.set_reserved(AMBIENCE_RESERVED)
        except Exception:
            pass
        self.sounds = {}
        self.variants = {}
        self._muffle_cache = {}
        self._muffle_keep = []
        self._amb_active = False
        self._amb_timers = {}
        self._generate_sounds()

    # ── low level helpers (kept for backwards compatibility) ─────────────────
    def _generate_sound(self, samples):
        stereo = _stereo(samples)
        stereo = np.clip(stereo * 32767, -32768, 32767).astype(np.int16)
        try:
            return pygame.mixer.Sound(buffer=stereo.tobytes())
        except Exception:
            return None

    def _apply_reverb(self, samples, delay_samples=2205, decay=0.4, num_echoes=3):
        rt60 = float(np.clip(delay_samples * num_echoes * 2.5 / self.rate, 0.3, 4.0))
        return reverb(samples, self.rate, rt60=rt60, wet=float(decay))

    def _apply_lowpass(self, samples, alpha=0.3):
        alpha = min(max(alpha, 0.01), 0.99)
        cutoff = -math.log(1.0 - alpha) * self.rate / (2 * math.pi)
        return fft_filter(_stereo(samples), self.rate, hi=cutoff, order=1)

    def _finish(self, x, peak=0.9, fade_ms=10, loop=False):
        """Trim silent tail, fade the end, normalise and wrap in a Sound.
        loop=True keeps the exact length so seamless loops stay seamless."""
        x = _stereo(x)
        env = np.max(np.abs(x), axis=1)
        top = float(env.max()) if len(env) else 0.0
        if top <= 1e-9:
            return self._generate_sound(x)
        if not loop:
            loud = np.nonzero(env > top * 3e-4)[0]
            if len(loud):
                x = x[:loud[-1] + 1]
            x = fade(x, self.rate, fade_out=fade_ms / 1000.0)
        x = x - x.mean(axis=0)
        x = x * (peak / max(float(np.max(np.abs(x))), 1e-9))
        return self._generate_sound(x)

    def _mix(self, parts, length=None):
        """Sum [(offset_s, array)] into one array."""
        r = self.rate
        total = length or max(int(o * r) + len(a) for o, a in parts)
        out = None
        for off, a in parts:
            a = _stereo(a) if getattr(a, 'ndim', 1) == 2 else a
            if out is None:
                out = np.zeros((total, 2)) if a.ndim == 2 else np.zeros(total)
            if a.ndim == 2 and out.ndim == 1:
                out = np.column_stack((out, out))
            s = int(off * r)
            e = min(total, s + len(a))
            if e > s:
                out[s:e] += a[:e - s]
        return out

    # ── building blocks ───────────────────────────────────────────────────────
    def _click(self, dur, rng, rings, tau_noise=0.0015, tau_ring=0.008, noise_hp=1500):
        r = self.rate
        n = int(r * dur)
        t = _t(n, r)
        nz = fft_filter(rng.standard_normal(n), r, lo=noise_hp) * np.exp(-t / tau_noise)
        out = _pk(nz) * 0.9
        for f, a in rings:
            if f < 0.45 * r:
                out += a * np.sin(2 * np.pi * f * t) * np.exp(-t / tau_ring)
        return out

    def _grains(self, n, rng, count, positions, band, grain_ms=6.0, tau_ms=1.2):
        """Scatter noisy micro-bursts (leaf / twig / paper crackle)."""
        r = self.rate
        imp = np.zeros(n)
        pos = np.clip(positions, 0, n - 1)
        np.add.at(imp, pos, rng.lognormal(0, 0.7, count) * rng.choice([-1.0, 1.0], count))
        g = int(grain_ms / 1000 * r)
        kernel = rng.standard_normal(g) * np.exp(-np.arange(g) / (tau_ms / 1000 * r))
        sig = fft_conv(imp, kernel)[:n]
        return fft_band(sig, r, band[0], band[1])

    def _sweep_noise(self, n, rng, f0, f1, bw_oct=1.2, bands=10):
        """Noise whose band centre glides f0 -> f1 (whoosh / swish)."""
        r = self.rate
        t = _t(n, r)
        pos = t / max(t[-1], 1e-9)
        out = np.zeros(n)
        base = rng.standard_normal(n)
        for i in range(bands):
            u = i / (bands - 1)
            centre = f0 * (f1 / f0) ** u
            win = np.exp(-0.5 * ((pos - u) / (0.9 / bands)) ** 2)
            out += fft_band(base, r, centre, bw_oct) * win
        return out

    # ── sound design ──────────────────────────────────────────────────────────
    def _build_shotgun(self):
        r = self.rate
        rng = _rng('shotgun')
        n = int(r * 0.6)
        t = _t(n, r)
        crack = fft_filter(rng.standard_normal(n), r, lo=250) * np.exp(-t / 0.004)
        blast = fft_filter(rng.standard_normal(n), r, hi=2200) * np.exp(-t / 0.055)
        boom = sine_sweep(t, r, 150, 38, 0.05) * np.exp(-t / 0.11) * (1 - np.exp(-t / 0.0008))
        body = fft_filter(rng.standard_normal(n), r, lo=90, hi=700) * np.exp(-t / 0.22)
        shot = 1.1 * _pk(crack) + 1.0 * _pk(blast) + 1.4 * _pk(boom) + 0.9 * _pk(body)
        shot = np.tanh(1.6 * shot)
        wet = reverb(shot, r, rt60=1.5, wet=0.35, brightness=0.35,
                     echoes=[(0.16, 0.22, 2500), (0.34, 0.12, 1800), (0.58, 0.06, 1300)])
        # pump-action rack: scrape + two heavy clicks
        rack_rng = _rng('shotgun_rack')
        scrape_n = int(r * 0.07)
        scrape = fft_band(rack_rng.standard_normal(scrape_n), r, 2800, 2.0)
        scrape *= np.sin(np.linspace(0, np.pi, scrape_n)) ** 2 * 0.25
        c1 = self._click(0.12, rack_rng, [(1900, 0.5), (3300, 0.3), (410, 0.4)], tau_ring=0.012)
        c2 = self._click(0.12, rack_rng, [(1500, 0.55), (2700, 0.3), (330, 0.5)], tau_ring=0.014)
        rack = self._mix([(0.0, scrape), (0.07, c1 * 0.6), (0.19, c2 * 0.7)])
        parts = [(0.0, wet), (0.62, _stereo(rack) * 0.45)]
        return self._finish(self._mix(parts), peak=0.95)

    def _build_revolver(self):
        r = self.rate
        rng = _rng('revolver')
        n = int(r * 0.4)
        t = _t(n, r)
        crack = fft_filter(rng.standard_normal(n), r, lo=500) * np.exp(-t / 0.0028)
        blast = fft_filter(rng.standard_normal(n), r, hi=3500) * np.exp(-t / 0.03)
        boom = sine_sweep(t, r, 260, 85, 0.03) * np.exp(-t / 0.06) * (1 - np.exp(-t / 0.0006))
        ring = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t / tau)
                   for f, a, tau in ((2150, 0.10, 0.05), (3400, 0.07, 0.035), (5200, 0.04, 0.02))
                   if f < 0.45 * r)
        shot = 1.3 * _pk(crack) + 0.9 * _pk(blast) + 0.9 * _pk(boom) + ring
        shot = np.tanh(1.5 * shot)
        wet = reverb(shot, r, rt60=1.0, wet=0.3, brightness=0.5,
                     echoes=[(0.13, 0.18, 3000), (0.29, 0.09, 2000)])
        return self._finish(wet, peak=0.92)

    def _build_bolo(self):
        r = self.rate
        rng = _rng('bolo')
        n = int(r * 0.32)
        t = _t(n, r)
        whoosh = self._sweep_noise(n, rng, 450, 3200, bw_oct=1.3)
        whoosh *= np.sin(np.pi * np.clip(t / 0.26, 0, 1)) ** 2
        low = fft_filter(rng.standard_normal(n), r, hi=300) * np.sin(np.pi * np.clip(t / 0.25, 0, 1)) ** 2
        steel = np.zeros(n)
        for f, a, tau in ((1180, 0.5, 0.14), (2750, 0.35, 0.09), (4880, 0.2, 0.05), (7400, 0.1, 0.03)):
            if f < 0.45 * r:
                steel += a * np.sin(2 * np.pi * f * t) * np.exp(-t / tau)
        steel *= np.clip((t - 0.09) / 0.02, 0, 1) * 0.35        # blade 'sings' at end of swing
        out = 1.0 * _pk(whoosh) + 0.35 * _pk(low) + steel
        out = reverb(out, r, rt60=0.5, wet=0.12, brightness=0.6)
        return self._finish(out, peak=0.8)

    def _build_footstep(self, seed):
        r = self.rate
        rng = _rng(f'footstep{seed}')
        n = int(r * 0.32)
        t = _t(n, r)
        f0 = 58 + rng.uniform(-8, 14)
        thump = np.sin(2 * np.pi * np.cumsum(f0 * (1 + 0.9 * np.exp(-t / 0.02))) / r)
        thump *= np.exp(-t / 0.028) * (1 - np.exp(-t / 0.002))
        soil = fft_filter(rng.standard_normal(n), r, hi=380) * np.exp(-t / 0.035)
        count = int(rng.integers(16, 30))
        pos = (rng.beta(1.2, 3.5, count) * 0.13 * r).astype(int) + int(0.004 * r)
        crunch = self._grains(n, rng, count, pos, (2600 + rng.uniform(-500, 700), 2.2))
        crunch *= np.exp(-t / 0.09)
        scuff_n = int(r * 0.09)
        scuff = np.zeros(n)
        s0 = int(r * (0.11 + rng.uniform(0, 0.03)))
        scuff[s0:s0 + scuff_n] = fft_band(rng.standard_normal(scuff_n), r, 1800, 2.0) * \
            np.sin(np.linspace(0, np.pi, scuff_n)) ** 2
        mix = 0.85 * _pk(thump) + 0.7 * _pk(soil) + 1.0 * _pk(crunch) + 0.22 * _pk(scuff)
        mix = reverb(mix, r, rt60=0.3, wet=0.08, brightness=0.4)
        return self._finish(mix, peak=0.55)

    def _build_chime(self):
        r = self.rate
        n = int(r * 2.6)
        t = _t(n, r)
        modes = ((1.0, 1.0, 0.55), (2.0, 0.5, 0.38), (2.76, 0.42, 0.26), (5.4, 0.2, 0.12), (8.93, 0.1, 0.06))

        def note(f, amp):
            s = np.zeros(n)
            for ratio, a, tau in modes:
                fm = f * ratio
                if fm < 0.45 * r:
                    s += a * np.sin(2 * np.pi * fm * t + ratio) * np.exp(-t / tau)
            return s * amp * (1 - np.exp(-t / 0.0015))

        parts = [(0.0, note(659.25, 1.0)), (0.085, note(987.77, 0.75))]
        out = self._mix(parts, length=n)
        out = fade(out, r, 0.0, 0.35)          # let the bell die away, no cut-off click
        out = reverb(out, r, rt60=1.5, wet=0.3, brightness=0.7)
        return self._finish(out, peak=0.6, fade_ms=30)

    def _build_door(self):
        r = self.rate
        rng = _rng('door')
        n = int(r * 1.0)
        t = _t(n, r)
        p = t / t[-1]
        f_base = 78 + 40 * np.sin(np.pi * np.clip(p * 1.1, 0, 1)) + 22 * smooth_noise(n, r, 9, rng)
        f = np.maximum(30, f_base * (1 + 0.12 * smooth_noise(n, r, 40, rng)))
        phase = np.cumsum(f) / r
        src = np.zeros(n)
        for k in range(1, 28):
            mask = (k * f) < 0.45 * r
            src += (k ** -1.0) * np.sin(2 * np.pi * k * phase) * mask
        slip = np.clip(0.55 + 0.9 * smooth_noise(n, r, 14, rng), 0.0, 1.6) ** 2     # stick-slip bursts
        src *= slip
        creak = (0.9 * fft_band(src, r, 700, 0.5) + 0.7 * fft_band(src, r, 1450, 0.5)
                 + 0.4 * fft_band(src, r, 2350, 0.6))
        creak = _pk(creak)
        env = np.clip(t / 0.12, 0, 1) * np.clip((t[-1] - t) / 0.18, 0, 1)
        creak *= env * 0.55
        latch = self._click(0.1, rng, [(1700, 0.5), (900, 0.4), (260, 0.5)], tau_noise=0.002, tau_ring=0.012)
        tk = _t(int(r * 0.2), r)
        knock = (np.sin(2 * np.pi * 185 * tk) * 0.9 + np.sin(2 * np.pi * 335 * tk) * 0.4) * np.exp(-tk / 0.035)
        knock += fft_filter(rng.standard_normal(len(tk)), r, hi=900) * np.exp(-tk / 0.012) * 0.8
        out = self._mix([(0.0, latch * 0.8), (0.05, creak), (0.9, knock * 0.5)], length=int(r * 1.15))
        out = reverb(out, r, rt60=0.7, wet=0.2, brightness=0.35)
        return self._finish(out, peak=0.8)

    def _build_wind(self, dur, loop, seed, peak, fade_in=0.0, fade_out=0.0):
        r = self.rate
        rng = _rng(seed)
        n = int(r * dur)
        pad = not loop
        gust = np.clip(0.6 + 0.45 * smooth_noise(n, r, 0.28, rng, loop), 0.08, 1.6) ** 1.6
        howl_amt = np.clip(0.45 + 0.6 * smooth_noise(n, r, 0.45, rng, loop), 0.0, 1.5) ** 2
        drift = np.clip(0.5 + 0.35 * smooth_noise(n, r, 0.3, rng, loop), 0, 1)
        # build each band once, then give the right ear a circularly-shifted copy:
        # wide, decorrelated stereo for half the FFT cost (and still loops seamlessly)
        low = _std1(fft_filter(rng.standard_normal(n), r, hi=220, pad=pad))
        mid = _std1(fft_band(rng.standard_normal(n), r, 480, 2.0, pad=pad))
        h1 = _std1(fft_band(rng.standard_normal(n), r, 640, 0.45, pad=pad))
        h2 = _std1(fft_band(rng.standard_normal(n), r, 930, 0.45, pad=pad))
        hiss = _std1(fft_band(rng.standard_normal(n), r, 3200, 2.5, pad=pad))
        out = np.zeros((n, 2))
        for c, shift in enumerate((0, int(0.37 * r))):
            def sh(a):
                return np.roll(a, shift) if shift else a
            howl = sh(h1) * (1 - drift) + sh(h2) * drift
            out[:, c] = (0.9 * sh(low) * (0.4 + gust) + 0.6 * sh(mid) * gust
                         + 0.45 * howl * howl_amt * gust + 0.18 * sh(hiss) * gust ** 2)
        out = _pk(out) * peak
        if fade_in or fade_out:
            out = fade(out, r, fade_in, fade_out)
        return out

    def _build_drone(self):
        r = self.rate
        rng = _rng('drone')
        n = int(r * 6.5)
        t = _t(n, r)
        partials = ((41.2, 1.0, 0.0), (41.55, 0.8, 0.5), (61.8, 0.5, 1.1), (82.4, 0.45, 2.0),
                    (87.31, 0.28, 0.3), (123.5, 0.12, 1.7), (155.6, 0.07, 0.4))
        sig = np.zeros(n)
        for i, (f, a, ph) in enumerate(partials):
            wob = 0.4 * smooth_noise(n, r, 0.4, rng)
            trem = 1 + 0.18 * np.sin(2 * np.pi * (0.13 + 0.03 * i) * t)
            sig += a * np.sin(2 * np.pi * f * t + ph + wob) * trem
        rumble = _std1(fft_filter(rng.standard_normal(n), r, hi=90)) * 0.5 * (0.6 + 0.2 * smooth_noise(n, r, 0.5, rng))
        shimmer = 0.02 * np.sin(2 * np.pi * 1318.5 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 5.5 * t)) * \
            (0.5 + 0.5 * np.sin(2 * np.pi * 0.17 * t))
        out = _pk(sig) * 0.8 + rumble * 0.3 + shimmer
        out = fade(out, r, 1.5, 2.2)
        out = reverb(out, r, rt60=3.0, wet=0.5, brightness=0.2)
        return self._finish(out, peak=0.6, fade_ms=40)

    def _build_creature(self):
        r = self.rate
        rng = _rng('creature_call')
        dur = 1.8
        n = int(r * dur)
        t = _t(n, r)
        p = t / dur
        f0 = np.interp(p, [0, 0.12, 0.35, 0.55, 1.0], [170, 300, 560, 520, 105])
        f0 *= 1 + 0.03 * np.sin(2 * np.pi * 7 * t) * np.clip(t / 0.3, 0, 1)
        voice = synth_voice(r, f0, 'a', 'o', morph=np.clip(p * 1.2, 0, 1), tilt=1.2, breath=0.3,
                            jitter=0.02, subharm=0.5, rough=(55, 0.5), rng=rng)
        env = (1 - np.exp(-t / 0.04)) * np.exp(-0.9 * p) * np.clip((1 - p) * 8, 0, 1)
        rasp = fft_band(rng.standard_normal(n), r, 1800, 2.5) * np.exp(-t / 0.5) * 0.25
        out = np.tanh(2.5 * (voice * env + rasp * env))
        out = reverb(out, r, rt60=1.6, wet=0.3, brightness=0.45, echoes=[(0.22, 0.15, 2500)])
        return self._finish(out, peak=0.95, fade_ms=30)

    def _build_flashlight(self):
        r = self.rate
        rng = _rng('flashlight_click')
        main = self._click(0.1, rng, [(2100, 0.6), (3600, 0.3), (220, 0.7)], tau_noise=0.002, tau_ring=0.008)
        rattle = self._click(0.05, rng, [(2900, 0.4), (1300, 0.3)], tau_noise=0.0012, tau_ring=0.005)
        out = self._mix([(0.0, main), (0.022, rattle * 0.35)], length=int(r * 0.13))
        out = reverb(out, r, rt60=0.25, wet=0.06, brightness=0.6)
        return self._finish(out, peak=0.7, fade_ms=6)

    def _build_weapon_click(self):
        r = self.rate
        rng = _rng('weapon_click')
        a = self._click(0.1, rng, [(3200, 0.5), (5500, 0.25), (480, 0.6)], tau_noise=0.002, tau_ring=0.006)
        b = self._click(0.1, rng, [(2500, 0.5), (4400, 0.25), (380, 0.7)], tau_noise=0.002, tau_ring=0.007)
        out = self._mix([(0.0, a * 0.8), (0.058, b)], length=int(r * 0.17))
        out = reverb(out, r, rt60=0.25, wet=0.06, brightness=0.6)
        return self._finish(out, peak=0.7, fade_ms=8)

    def _build_rustle(self, name, dur, density, band, level_curve_hz=3.0, peak=0.5, soft=False):
        r = self.rate
        rng = _rng(name)
        n = int(r * dur)
        count = int(density * dur)
        u = np.clip(rng.beta(2.0, 2.2, count), 0, 0.999)
        pos = (u * n * 0.97).astype(int)
        sig = self._grains(n, rng, count, pos, band, grain_ms=14 if soft else 7, tau_ms=3.0 if soft else 1.4)
        swell = np.clip(0.6 + 0.5 * smooth_noise(n, r, level_curve_hz, rng), 0.1, 1.5)
        sig *= swell
        sig = fade(sig, r, 0.03, 0.12)
        out = reverb(sig, r, rt60=0.6, wet=0.15, brightness=0.5)
        return self._finish(out, peak=peak, fade_ms=20)

    def _build_title_sting(self):
        r = self.rate
        rng = _rng('title_sting')
        n = int(r * 3.2)
        t = _t(n, r)
        boom = sine_sweep(t, r, 95, 28, 0.45) * np.exp(-t / 0.9) * (1 - np.exp(-t / 0.002))
        thud = fft_filter(rng.standard_normal(n), r, hi=1500) * np.exp(-t / 0.08)
        cluster = np.zeros(n)
        for f, a in ((55.0, 1.0), (58.3, 0.8), (82.4, 0.6), (116.5, 0.5)):
            for k in range(1, 6):
                cluster += a * (k ** -1.4) * np.sin(2 * np.pi * f * k * t + k)
        cluster = fft_filter(cluster, r, hi=650) * np.exp(-t / 1.6) * np.clip(t / 0.05, 0, 1)
        shimmer = np.zeros(n)
        for f, a in ((1110, 0.5), (1670, 0.4), (2430, 0.3), (3180, 0.2)):
            shimmer += a * np.sin(2 * np.pi * f * t) * (0.6 + 0.4 * np.sin(2 * np.pi * (3 + f / 900) * t))
        shimmer *= np.exp(-t / 1.1) * 0.05
        out = 1.3 * _pk(boom) + 0.6 * _pk(thud) + 0.55 * _pk(cluster) + shimmer
        out = np.tanh(1.2 * out)
        out = reverb(out, r, rt60=3.2, wet=0.45, brightness=0.25)
        return self._finish(out, peak=0.95, fade_ms=40)

    def _build_crickets(self, dur=6.0):
        r = self.rate
        rng = _rng('crickets')
        n = int(r * dur)
        t = _t(n, r)
        out = np.zeros((n, 2))
        voices = ((4350, 9, 4, 0.030), (4720, 11, 3, 0.034), (5100, 14, 4, 0.027),
                  (5480, 17, 5, 0.024), (4050, 8, 3, 0.038))
        pulse_len = int(0.017 * r)
        u = np.arange(pulse_len) / pulse_len
        shape = np.sin(np.pi * u) ** 2
        for fc, chirps, pulses, spacing in voices:
            env = np.zeros(n)
            period = dur / chirps
            start = rng.uniform(0, period)
            for k in range(chirps):
                s0 = start + k * period
                for j in range(pulses):
                    i0 = int((s0 + j * spacing) * r)
                    env[(i0 + np.arange(pulse_len)) % n] += shape * (1 - 0.08 * j)
            sig = np.sin(2 * np.pi * fc * t) * env
            pan = rng.uniform(0.1, 0.9)
            g = rng.lognormal(0, 0.25)
            out[:, 0] += sig * (1 - pan) * g
            out[:, 1] += sig * pan * g
        out = fft_filter(out, r, lo=2500, hi=8000, pad=False)
        out += rng.standard_normal((n, 2)) * 0.002
        return self._finish(_pk(out) * 0.5, peak=0.5, loop=True)

    def _build_owl(self):
        r = self.rate
        rng = _rng('owl')
        total = 3.4
        n = int(r * total)
        t = _t(n, r)
        # (start, length, f_start, f_end)
        hoots = ((0.00, 0.22, 400, 430), (0.38, 0.85, 440, 355), (1.95, 0.36, 385, 360), (2.45, 0.42, 380, 335))
        f0 = np.full(n, 380.0)
        gate = np.zeros(n)
        for s, ln, fa, fb in hoots:
            i0, i1 = int(s * r), int((s + ln) * r)
            u = np.linspace(0, 1, i1 - i0)
            f0[i0:i1] = fa + (fb - fa) * u
            g = np.sin(np.pi * u) ** 0.8
            gate[i0:i1] = np.maximum(gate[i0:i1], g)
        f0 *= 1 + 0.02 * np.sin(2 * np.pi * 5.5 * t)
        voice = synth_voice(r, f0, 'o', tilt=2.6, breath=0.05, jitter=0.004, rng=rng, max_harm=6)
        voice = voice * gate
        voice = fft_filter(voice, r, hi=2400, order=2)
        out = reverb(voice, r, rt60=2.2, wet=0.5, brightness=0.25,
                     echoes=[(0.45, 0.3, 1600), (0.9, 0.14, 1200)])
        return self._finish(out, peak=0.5, fade_ms=40)

    def _build_snap(self):
        r = self.rate
        rng = _rng('snap')
        n = int(r * 0.35)
        t = _t(n, r)
        crack = fft_filter(rng.standard_normal(n), r, lo=900) * np.exp(-t / 0.0014)
        wood = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t / tau)
                   for f, a, tau in ((380, 0.5, 0.012), (910, 0.4, 0.008), (1700, 0.3, 0.005)))
        out = 1.0 * _pk(crack) + 0.5 * wood
        out = reverb(out, r, rt60=1.3, wet=0.3, brightness=0.4, echoes=[(0.21, 0.2, 2200), (0.47, 0.1, 1500)])
        return self._finish(out, peak=0.7)

    def _build_beds(self):
        wind = self._build_wind(10.0, True, 'wind_bed', 0.5)
        self.sounds['wind_bed'] = self._generate_sound(wind)
        self.sounds['crickets_bed'] = self._build_crickets(6.0)

    def _generate_sounds(self):
        r = self.rate
        builders = (
            ('shotgun', self._build_shotgun),
            ('revolver', self._build_revolver),
            ('bolo', self._build_bolo),
            ('pickup', self._build_chime),
            ('door', self._build_door),
            ('drone', self._build_drone),
            ('creature_call', self._build_creature),
            ('flashlight_click', self._build_flashlight),
            ('click', self._build_weapon_click),
            ('title_sting', self._build_title_sting),
            ('crickets', self._build_crickets),
            ('owl', self._build_owl),
            ('snap', self._build_snap),
            ('rustle', lambda: self._build_rustle('rustle', 1.3, 85, (3200, 2.6), 2.5, 0.45, soft=True)),
            ('page_rustle', lambda: self._build_rustle('page_rustle', 0.75, 70, (4200, 2.4), 6.0, 0.5)),
            ('intro_wind', lambda: self._finish(
                self._build_wind(7.0, False, 'intro_wind', 0.6, 0.8, 1.8), peak=0.6, fade_ms=0)),
        )
        for name, fn in builders:
            try:
                self.sounds[name] = fn()
            except Exception as exc:                       # never let audio crash the game
                print(f"[Audio] failed to build '{name}': {exc}")
                self.sounds[name] = None
        try:
            self._build_beds()
        except Exception as exc:
            print(f"[Audio] failed to build ambience beds: {exc}")
        steps = []
        for i in range(4):
            try:
                steps.append(self._build_footstep(i))
            except Exception as exc:
                print(f"[Audio] failed to build footstep {i}: {exc}")
        steps = [s for s in steps if s]
        if steps:
            self.variants['footstep'] = steps
            self.sounds['footstep'] = steps[0]

    # ── playback ──────────────────────────────────────────────────────────────
    def start_intro_ambience(self):
        self.play('intro_wind', 0.5)

    def stop_intro_ambience(self):
        """Silence one-shots (intro wind, drone, calls) but keep the forest beds."""
        try:
            for i in range(AMBIENCE_RESERVED, pygame.mixer.get_num_channels()):
                pygame.mixer.Channel(i).stop()
        except Exception:
            pass

    def play_drone(self, vol=0.4):
        self.play('drone', vol)

    def play_object(self, snd, volume=1.0, pan=0.0):
        """Play a Sound with equal-power panning.  Returns the channel."""
        if snd is None:
            return None
        try:
            vol = max(0.0, min(1.0, volume))
            pan = max(-1.0, min(1.0, pan))
            theta = (pan + 1.0) * math.pi / 4.0
            left = min(1.0, vol * math.cos(theta) * math.sqrt(2.0))
            right = min(1.0, vol * math.sin(theta) * math.sqrt(2.0))
            channel = snd.play()
            if channel is not None:
                channel.set_volume(left, right)
            return channel
        except Exception:
            return None

    def play(self, name, volume=1.0, pan=0.0):
        variants = self.variants.get(name)
        snd = random.choice(variants) if variants else self.sounds.get(name)
        return self.play_object(snd, volume, pan)

    def muffled(self, snd, level):
        """Air-absorbed (low-passed, quieter) copy of snd, built lazily and cached."""
        if snd is None or level <= 0:
            return snd
        level = min(int(level), len(MUFFLE_CUTOFFS) - 1)
        key = (id(snd), level)
        got = self._muffle_cache.get(key)
        if got is None:
            try:
                raw = np.frombuffer(snd.get_raw(), dtype=np.int16)
                arr = raw.reshape(-1, max(1, self.channels)).astype(np.float64) / 32768.0
                arr = fft_filter(arr, self.rate, hi=MUFFLE_CUTOFFS[level], order=2)
                got = self._generate_sound(arr * (0.88 ** level)) or snd
            except Exception:
                got = snd
            self._muffle_cache[key] = got
            self._muffle_keep.append(snd)       # keep id() stable
        return got

    def spatial_params(self, player_x, player_y, player_angle, target_x, target_y,
                       base_volume=1.0, max_dist=15.0):
        """-> (volume, pan, muffle_level) or None when out of earshot."""
        dx = target_x - player_x
        dy = target_y - player_y
        dist = math.hypot(dx, dy)
        if max_dist <= 0.0 or dist > max_dist:
            return None
        ratio = dist / max_dist
        volume = base_volume * (1.0 - ratio) ** 1.5
        diff = math.atan2(dy, dx) - player_angle
        diff = (diff + math.pi) % (2 * math.pi) - math.pi
        pan = math.sin(diff) * min(1.0, dist / 1.5)         # centred when right on top of you
        level = 0 if ratio < 0.3 else 1 if ratio < 0.55 else 2 if ratio < 0.8 else 3
        if math.cos(diff) < -0.2:                            # head shadow: sources behind you are duller
            level = min(len(MUFFLE_CUTOFFS) - 1, level + 1)
        return volume, pan, level

    def play_spatial(self, name, player_x, player_y, player_angle, target_x, target_y,
                     base_volume=1.0, max_dist=15.0):
        params = self.spatial_params(player_x, player_y, player_angle, target_x, target_y,
                                     base_volume, max_dist)
        if params is None:
            return None
        volume, pan, level = params
        variants = self.variants.get(name)
        snd = random.choice(variants) if variants else self.sounds.get(name)
        return self.play_object(self.muffled(snd, level), volume, pan)

    # ── ambience ──────────────────────────────────────────────────────────────
    _BEDS = (('wind_bed', 0.0, 0.22), ('crickets_bed', 1.0, 0.11))

    def set_ambience_active(self, active):
        """Fade the forest wind + crickets in (gameplay) or out (menus, death)."""
        active = bool(active)
        if active == self._amb_active:
            return
        self._amb_active = active
        try:
            for name, ch_index, vol in self._BEDS:
                channel = pygame.mixer.Channel(int(ch_index))
                if active:
                    snd = self.sounds.get(name)
                    if snd is not None:
                        channel.play(snd, loops=-1, fade_ms=2500)
                        channel.set_volume(vol)        # after play(): playing resets the channel volume
                else:
                    channel.fadeout(900)
        except Exception:
            pass
        if active:
            self._amb_timers = {
                'owl': random.uniform(12, 30),
                'rustle': random.uniform(4, 12),
                'snap': random.uniform(25, 60),
            }

    def update_ambience(self, dt):
        """Sparse forest one-shots (owl, leaves, distant twig snap)."""
        if not self._amb_active:
            return
        schedule = {'owl': (40, 90, 0.10, 0.22), 'rustle': (8, 24, 0.10, 0.25), 'snap': (30, 80, 0.18, 0.35)}
        for key, (lo, hi, v0, v1) in schedule.items():
            self._amb_timers[key] = self._amb_timers.get(key, random.uniform(lo, hi)) - dt
            if self._amb_timers[key] <= 0.0:
                self._amb_timers[key] = random.uniform(lo, hi)
                self.play(key, volume=random.uniform(v0, v1), pan=random.uniform(-1.0, 1.0))


audio_mgr = SoundManager()
