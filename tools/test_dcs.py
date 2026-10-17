# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for our own Pd objects (dcs/, built with `make -C dcs`), each in a small patch of its own.

    tools/.venv/bin/python tools/test_dcs.py tools/.libpd/libpd.so
"""
import ctypes, os, sys, tempfile
import numpy as np
from pdtest import Engine, SR

LIB = sys.argv[1] if len(sys.argv) > 1 else "tools/.libpd/libpd.so"
TMP = tempfile.mkdtemp(prefix="dcs_test_")
fails = []


def check(ok, what):
    print(("ok:   " if ok else "FAIL: ") + what)
    if not ok:
        fails.append(what)


def patch(name, objs, conns):
    """A patch from a list of object texts and (from, outlet, to, inlet) connections."""
    lines = ["#N canvas 0 0 600 400 12;", "#X declare -lib dcs;", "#X obj 10 10 declare -lib dcs;"]
    lines += [f"#X obj 10 {40 + 25 * i} {t};" for i, t in enumerate(objs)]
    lines += [f"#X connect {a + 1} {o} {b + 1} {i};" for a, o, b, i in conns]
    path = os.path.join(TMP, name + ".pd")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return path


def peak_hz(x, lo, hi):
    """The strongest frequency between lo and hi, finely (Hann window, zero-padded FFT, parabolic peak)."""
    n = 1 << 20
    X = np.abs(np.fft.rfft(x * np.hanning(len(x)), n))
    f = np.fft.rfftfreq(n, 1 / SR)
    band = np.where((f >= lo) & (f <= hi))[0]
    k = band[np.argmax(X[band])]
    a, b, c = np.log(X[k - 1:k + 2] + 1e-30)
    return f[k] + 0.5 * (a - c) / (a - 2 * b + c) * (f[1] - f[0])


def rms(x):
    return float(np.sqrt(np.mean(np.asarray(x, dtype=float) ** 2)))


def db_frames(x, ms=20):
    m = int(SR * ms / 1000)
    fr = x[:len(x) // m * m].reshape(-1, m)
    return 20 * np.log10(np.sqrt((fr ** 2).mean(axis=1)) + 1e-12)


# ---------------------------------------------------------------- dcs_string~
print("dcs_string~:")
p = patch("string", ["adc~", "dcs_string~ 220 1500 0.5", "r sfreq", "r sdecay", "r sbright", "dac~"],
          [(0, 0, 1, 0), (2, 0, 1, 1), (3, 0, 1, 2), (4, 0, 1, 3), (1, 0, 5, 0), (1, 0, 5, 1)])
rng = np.random.default_rng(1)
burst = np.zeros(int(SR * 1.6), dtype=np.float32)
burst[:int(SR * 0.004)] = rng.uniform(-1, 1, int(SR * 0.004))
worst_cents = 0
for bright in (0.0, 0.5, 1.0):
    for f0 in (65.4, 220, 440, 1046.5, 2093):
        e = Engine(LIB, p)
        check(not any("couldn't create" in m for m in e.log), "dcs loads") if (bright, f0) == (0.0, 65.4) else None
        e.send("sbright", bright); e.send("sdecay", 3000); e.send("sfreq", f0)
        out = e.run(burst)[:, 0]
        e.close()
        got = peak_hz(out[int(SR * 0.1):], f0 * 0.9, f0 * 1.1)
        cents = 1200 * np.log2(got / f0) if np.abs(out).max() > 1e-3 else 1e9
        worst_cents = max(worst_cents, abs(cents))
        if abs(cents) > 3:
            print(f"      {f0} Hz at brightness {bright}: {got:.2f} Hz ({cents:+.1f} cents)")
check(worst_cents < 3, f"in tune from C2 to C7 at every brightness (worst {worst_cents:.2f} cents)")
def fall_t60(x, f0):
    """How long the f0 partial takes to fall 60 dB: its level in 50 ms frames, fitted from 0.2 s on."""
    m = int(SR * 0.05)
    k = np.arange(m)
    ref = np.exp(-2j * np.pi * f0 * k / SR) * np.hanning(m)
    lv = np.array([20 * np.log10(abs((x[i:i + m] * ref).sum()) + 1e-12) for i in range(0, len(x) - m, m)])
    t = np.arange(len(lv)) * 0.05
    use = (t >= 0.2) & (lv > lv.max() - 50)
    slope = np.polyfit(t[use], lv[use], 1)[0]
    return -60 / slope

for decay in (500, 1500, 3000):
    for bright in (0.1, 0.9):
        e = Engine(LIB, p)
        e.send("sbright", bright); e.send("sdecay", decay); e.send("sfreq", 220)
        out = e.run(np.concatenate([burst, np.zeros(SR * 3, dtype=np.float32)]))[:, 0]
        e.close()
        t60 = fall_t60(out, 220)
        check(0.9 < t60 / (decay / 1000) < 1.1,
              f"decay {decay} ms at brightness {bright}: the note rings that long ({t60 * 1000:.0f} ms to fall 60 dB)")
e = Engine(LIB, p)
e.send("sbright", 0); e.send("sdecay", 1500); e.send("sfreq", 2093)
out = e.run(np.concatenate([burst, np.zeros(SR * 2, dtype=np.float32)]))[:, 0]
e.close()
t60 = fall_t60(out, 2093)
check(0.9 < t60 / 1.5 < 1.1, f"a dark high note still rings ({t60 * 1000:.0f} ms at C7, brightness 0)")
e = Engine(LIB, p)
e.send("sbright", 1); e.send("sdecay", 60000); e.send("sfreq", 2000)
out = e.run(np.concatenate([burst, np.zeros(SR * 5, dtype=np.float32)]))[:, 0]
e.close()
check(np.isfinite(out).all() and 1e-3 < np.abs(out).max() < 4, f"bright, high and endless stays stable (peak {np.abs(out).max():.2f})")
noise = rng.uniform(-0.3, 0.3, SR * 2).astype(np.float32)
levels = []
for decay in (300, 3000):
    e = Engine(LIB, p)
    e.send("sbright", 0.5); e.send("sdecay", decay); e.send("sfreq", 330)
    out = e.run(noise)[:, 0]
    e.close()
    levels.append(20 * np.log10(np.sqrt((out[SR:] ** 2).mean())))
check(abs(levels[0] - levels[1]) < 8, f"steady noise comes out about as loud for a short and a long ring ({levels[0]:.1f} / {levels[1]:.1f} dB)")

p2 = patch("pluck", ["dcs_string~ 220 1500 0.3", "r spl", "dac~", "msg pluck 0.5"],
           [(1, 0, 3, 0), (3, 0, 0, 0), (0, 0, 2, 0), (0, 0, 2, 1)])
src = open(p2).read().replace("#X obj 10 115 msg pluck", "#X msg 10 115 pluck"); open(p2, "w").write(src)
e = Engine(LIB, p2)
e.run(np.zeros(640, dtype=np.float32)); e.lib.libpd_bang(b"spl")
out = e.run(np.zeros(SR, dtype=np.float32))[:, 0]
e.close()
w = out[int(SR * 0.05):int(SR * 0.5)]
h = [abs(np.mean(w * np.exp(-2j * np.pi * 220 * m * np.arange(len(w)) / SR))) for m in (1, 2, 3)]
check(0.2 < np.abs(out).max() < 1 and h[0] > 3 * max(h[1], h[2]) and abs(peak_hz(w, 200, 240) / 220 - 1) < 0.002,
      f"pluck: the note itself leads (harmonics 1-3: {h[0]:.3f} {h[1]:.3f} {h[2]:.3f}), in tune, peak {np.abs(out).max():.2f}")

# ---------------------------------------------------------------- dcs_glitch~
print("dcs_glitch~:")
g = patch("glitch", ["adc~", "dcs_glitch~ 4000 4", "r g", "dac~", "r gdel", "del 1.3", "msg slice 50 10 1 0 1e+07 -1",
                     "msg 1 5", "vline~", "+~"],
          [(0, 0, 1, 0), (2, 0, 1, 0), (1, 0, 3, 0), (1, 1, 9, 0), (8, 0, 9, 1), (9, 0, 3, 1),
           (4, 0, 5, 0), (5, 0, 6, 0), (6, 0, 1, 0), (5, 0, 7, 0), (7, 0, 8, 0)])
# the patch file needs a message box, not an object, for the two messages
src = open(g).read().replace("#X obj 10 190 msg slice", "#X msg 10 190 slice").replace("#X obj 10 215 msg 1 5", "#X msg 10 215 1 5")
open(g, "w").write(src)

e = Engine(LIB, g)
check(not any("couldn't create" in m for m in e.log), "loads")
ones = np.ones(SR, dtype=np.float32)
e.run(ones[:SR // 2])
e.lib.libpd_bang(b"gdel")
out = e.run(ones[:6400])
e.close()
gl = np.argmax(out[:, 0] > 1e-6)
vl = np.argmax(out[:, 1] > 1e-6)
check(abs(gl - vl) <= 2 and gl % 64 not in (0, 1, 2),
      f"a glitch from a [del 1.3] starts on its sample, with vline~ (sample {gl}, vline~ {vl}, not a block edge)")

noise = np.random.default_rng(2).uniform(-1, 1, SR * 2).astype(np.float32)
ms = SR // 1000
# stutter: a 100 ms slice repeated
e = Engine(LIB, g)
e.run(noise[:SR])
e.send_msg("g", "slice", 600, 200, 0, 1, 100, -1)
out = e.run(noise[SR:SR + 700 * ms])[:, 0]
e.close()
a1, a2 = out[110 * ms:190 * ms], out[210 * ms:290 * ms]
check(np.abs(a1 - a2).max() < 1e-4 and np.abs(a1).max() > 0.5, "stutter: each 100 ms slice repeats exactly")
# reverse: the last bit backwards
e = Engine(LIB, g)
e.run(noise[:SR])
e.send_msg("g", "slice", 400, 10, -1, 0, 1e7, -1)
out = e.run(noise[SR:SR + 500 * ms])[:, 0]
e.close()
t = np.arange(50 * ms, 350 * ms)
want = noise[SR + t - (10 * ms + 2 * t)]          # read back d0 + 2t: time runs backwards
check(np.abs(out[t] - want).max() < 1e-3, "reverse: plays what came before it backwards, sample for sample")
# several at once, on both sides
e = Engine(LIB, g)
e.run(ones[:SR // 2])
e.send_msg("g", "slice", 300, 50, 1, 0, 1e7, -1)
e.send_msg("g", "slice", 300, 50, 1, 0, 1e7, 1)
out = e.run(ones[:200 * ms])
e.close()
check(abs(out[100 * ms, 0] - 1) < 1e-3 and abs(out[100 * ms, 1] - 1) < 1e-3,
      "two glitches play at once, one in each ear")
e = Engine(LIB, g)
e.run(ones[:SR // 2])
for _ in range(7):
    e.send_msg("g", "slice", 300, 50, 1, 0, 1e7, -1)
out = e.run(ones[:200 * ms])
e.close()
check(3.9 < out[100 * ms, 0] < 4.1, f"at most 4 voices: extra glitches take the oldest's place ({out[100 * ms, 0]:.2f})")
# stretch: slower, same pitch, even level
sine = (0.5 * np.sin(2 * np.pi * 440 * np.arange(SR * 3) / SR)).astype(np.float32)
sweep = (0.5 * np.sin(2 * np.pi * np.cumsum(np.linspace(300, 900, SR * 3)) / SR)).astype(np.float32)
e = Engine(LIB, g)
e.run(sine[:SR])
e.send_msg("g", "stretch", 2500, 600, 0.1, -1)
out = e.run(np.zeros(SR * 3, dtype=np.float32))[:, 0]
e.close()
mid = out[300 * ms:1800 * ms]
check(abs(peak_hz(mid, 300, 600) / 440 - 1) < 0.005, f"stretch keeps the pitch ({peak_hz(mid, 300, 600):.1f} Hz from 440)")
d = db_frames(mid)
check(mid.std() > 0.05 and d.max() - d.min() < 3, f"stretch holds an even level on a steady tone (swing {d.max() - d.min():.1f} dB)")
e = Engine(LIB, g)
e.run(sweep[:SR * 2])                     # 300 -> 700 Hz over the 2 s so far
e.send_msg("g", "stretch", 2500, 1000, 0.1, -1)   # from 1 s back (~500 Hz), moving on at a tenth of the speed
out = e.run(np.zeros(SR * 3, dtype=np.float32))[:, 0]
e.close()
f_a = peak_hz(out[100 * ms:600 * ms], 300, 900)
f_b = peak_hz(out[1500 * ms:2000 * ms], 300, 900)
check(0 < f_b - f_a < 60, f"stretch moves on slowly: a rising sweep rises 10x slower ({f_a:.0f} -> {f_b:.0f} Hz over 1.4 s)")

# ---------------------------------------------------------------- dcs_derustle~
print("dcs_derustle~:")
d = patch("derustle", ["adc~", "dcs_derustle~", "r dr", "dac~"], [(0, 0, 1, 0), (2, 0, 1, 0), (1, 0, 3, 0), (1, 1, 3, 1)])
rng = np.random.default_rng(4)
def rustle_room(secs=8.0, room_db=-45, burst_db=-22, every=0.6, burst_ms=80):
    """A steady room (noise) with bursts of rustle every `every` s from 2 s on; returns the signal and a burst mask."""
    n = int(secs * SR); x = rng.standard_normal(n) * 10 ** (room_db / 20)
    mask = np.zeros(n, bool)
    for t in np.arange(2.0, secs - 0.2, every):
        i = int(t * SR); k = int(burst_ms * SR / 1000)
        x[i:i + k] += rng.standard_normal(k) * 10 ** (burst_db / 20) * np.hanning(k) * 1.6; mask[i:i + k] = True
    return x.astype(np.float32), mask
def derustle(x, amount):
    e = Engine(LIB, d); e.send_msg("dr", "amount", amount); y = e.run(x); e.close(); return y
x, mask = rustle_room()
y1, y0 = derustle(x, 1), derustle(x, 0)
lv = lambda v: 20 * np.log10(np.sqrt(np.mean(v ** 2)) + 1e-12)
late = np.arange(len(x)) > 3 * SR
gap = late & ~np.convolve(mask, np.ones(int(0.12 * SR)), "same").astype(bool)     # well clear of a burst
cut = lv(x[late & mask]) - lv(y1[late & mask, 0]); room = lv(x[gap]) - lv(y1[gap, 0])
check(cut > 15 and abs(room) < 1, f"bursts 23 dB over the room come down {cut:.1f} dB, the room between them {room:+.2f} dB")
check(np.allclose(y0[:, 0], x[:len(y0)], atol=1e-7), "amount 0 leaves the sound untouched")
tone = (0.2 * np.sin(2 * np.pi * 220 * np.arange(4 * SR) / SR)).astype(np.float32)
g = derustle(tone, 1)[SR:, 1]
check(g.min() > 0.97, f"a steady tone isn't pumped (lowest gain {g.min():.3f})")
step = np.concatenate([rng.standard_normal(3 * SR) * 0.003, rng.standard_normal(5 * SR) * 0.05]).astype(np.float32)
g = derustle(step, 1)[:, 1]
check(g[int(5.5 * SR):].min() > 0.9, f"a room that gets 24 dB louder and stays is let through within ~2.5 s (gain after {g[int(5.5 * SR):].min():.2f})")

# ---------------------------------------------------------------- dcs_pitch~
print("dcs_pitch~:")
pp = patch("pitch", ["adc~", "dcs_pitch~ 512", "s pt_p", "s pt_l", "s pt_s"], [(0, 0, 1, 0), (1, 0, 2, 0), (1, 1, 3, 0), (1, 2, 4, 0)])
def track(x):
    e = Engine(LIB, pp); e.listen("pt_p", "pt_l", "pt_s"); e.run(x); h = dict(e.heard); e.close(); return h
t = np.arange(2 * SR) / SR
worst = 0
for f in (80, 220, 440, 1000, 3000):
    h = track((0.1 * np.sin(2 * np.pi * f * t)).astype(np.float32))
    p = np.array(h["pt_p"][20:]); want = 69 + 12 * np.log2(f / 440)
    worst = max(worst, np.max(np.abs(p - want)) * 100 if len(p) and (p > 0).all() else 1e9)
check(worst < 5, f"sines from 80 Hz to 3 kHz within {worst:.1f} cents")
saw = (0.1 * (2 * ((150 * t) % 1) - 1)).astype(np.float32)
p = np.array(track(saw)["pt_p"][20:]); want = 69 + 12 * np.log2(150 / 440)
check((np.abs(p - want) < 0.1).mean() > 0.97, f"a bright 150 Hz sawtooth: no octave mistakes ({(np.abs(p - want) < 0.1).mean() * 100:.0f}% right)")
h = track((rng.standard_normal(2 * SR) * 0.05).astype(np.float32))
check(np.mean(np.array(h["pt_p"][20:]) < 0) > 0.9, f"noise has no pitch ({np.mean(np.array(h['pt_p'][20:]) < 0) * 100:.0f}% of frames)")
h = track((0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32))
check(abs(np.median(h["pt_l"][20:]) - (100 + 20 * np.log10(0.1 / np.sqrt(2)))) < 0.5, f"level in Pd dB ({np.median(h['pt_l'][20:]):.1f})")
import time
def cost(obj):
    q = patch("cost", ["adc~", obj], [(0, 0, 1, 0)])
    e = Engine(LIB, q); x = (0.1 * np.sin(2 * np.pi * 220 * np.arange(20 * SR) / SR)).astype(np.float32)
    t0 = time.process_time(); e.run(x); c = time.process_time() - t0; e.close(); return c
cs, cd = min(cost("sigmund~ -hop 512 -npts 1024 pitch env") for _ in range(2)), min(cost("dcs_pitch~ 512") for _ in range(2))
check(cd < cs, f"costs {100 * cd / cs:.0f}% of sigmund~ with the same hop (both ~0.1% of real time: the win is accuracy)")

# ---------------------------------------------------------------- dcs_shift~
print("dcs_shift~:")
sp = patch("shift", ["adc~", "dcs_shift~ 7", "dac~"], [(0, 0, 1, 0), (1, 0, 2, 0), (1, 0, 2, 1)])
def vowel(f0=150, secs=3.0, formant=700):
    """A synthetic voice: a pulse train at f0 through a resonance at `formant` (its tone colour)."""
    n = int(secs * SR); x = np.zeros(n); x[(np.arange(0, n, SR / f0)).astype(int)] = 1.0
    r, th = 0.995, 2 * np.pi * formant / SR; y = np.zeros(n)
    for i in range(2, n):
        y[i] = x[i] + 2 * r * np.cos(th) * y[i - 1] - r * r * y[i - 2]
    return (0.1 * y / np.abs(y).max()).astype(np.float32)
v = vowel()
y = Engine(LIB, sp).run(v)[:, 0][SR:]
f0 = peak_hz(y, 180, 270)
check(abs(1200 * np.log2(f0 / (150 * 2 ** (7 / 12)))) < 5, f"a voice up a fifth lands on the fifth ({f0:.1f} Hz for {150 * 2 ** (7 / 12):.1f})")
S_ = np.abs(np.fft.rfft(y * np.hanning(len(y)))); fr = np.fft.rfftfreq(len(y), 1 / SR)
harm = [(k * f0, S_[np.argmin(np.abs(fr - k * f0))]) for k in range(1, 12)]
form = max(harm, key=lambda h: h[1])[0]
check(abs(form - 700) < f0 * 0.75, f"its tone colour stays: the strongest harmonic at {form:.0f} Hz (formant 700; a plain shifter: ~1050)")
d = db_frames(y)
check(d.max() - d.min() < 2, f"no warble: the level holds within {d.max() - d.min():.1f} dB")

# ---------------------------------------------------------------- dcs_onset~
print("dcs_onset~:")
op = patch("onset", ["adc~", "dcs_onset~", "f 1", "s on_b"], [(0, 0, 1, 0), (1, 0, 2, 0), (2, 0, 3, 0)])   # (the test hears numbers, not bangs)
def onsets(x):
    e = Engine(LIB, op); e.listen("on_b"); out, n, k = [], 64, 0
    for i in range(0, len(x) - n + 1, n):                  # block by block, so each onset has a time
        e.run(x[i:i + n]); m = len(e.heard["on_b"])
        out += [i / SR] * (m - k); k = m
    e.close(); return out
def claps_over(room_db, clap_db, secs=8.0, seed=11):
    r = np.random.default_rng(seed); n = int(secs * SR); x = r.standard_normal(n) * 10 ** (room_db / 20); at = []
    for t in np.arange(1.0, secs - 0.5, 0.7):
        i = int(t * SR); k = int(0.05 * SR); x[i:i + k] += r.standard_normal(k) * 10 ** (clap_db / 20) * np.exp(-np.arange(k) / (0.01 * SR)); at.append(t)
    return x.astype(np.float32), at
def score(found, at, tol=0.03):
    hit = [min((f - a for f in found if 0 <= f - a < tol), default=None) for a in at]
    late = [h for h in hit if h is not None]
    false = sum(1 for f in found if not any(0 <= f - a < tol for a in at))
    return len(late), false, (max(late) if late else 1)
x, at = claps_over(-60, -15)
h, fa, lat = score(onsets(x), at)
check(h == len(at) and fa == 0 and lat < 0.012, f"claps in a quiet room: {h}/{len(at)} found, {fa} false, at most {lat * 1000:.0f} ms late")
x, at = claps_over(-25, -17)
h, fa, lat = score(onsets(x), at)
check(h >= len(at) - 1 and fa <= 1, f"claps 8 dB over a loud roar: {h}/{len(at)} found, {fa} false")
t = np.arange(4 * SR) / SR
vib = (0.1 * np.sin(2 * np.pi * np.cumsum(440 * 2 ** (0.05 * np.sin(2 * np.pi * 6 * t))) / SR)).astype(np.float32)
f = [v for v in onsets(vib) if v > 0.5]
check(len(f) == 0, f"a held note with vibrato: {len(f)} onsets after its start")
env = np.clip(t / 0.4, 0, 1) ** 2
swell = (rng.standard_normal(len(t)) * 0.1 * env + rng.standard_normal(len(t)) * 0.001).astype(np.float32)
f = onsets(swell)
check(len(f) <= 1, f"a sound swelling up over 0.4 s: {len(f)} onsets (a level detector fires on swells)")

# ---------------------------------------------------------------- dcs_reverb~
print("dcs_reverb~:")
COMB, ALLP, EXTRA = [25.3, 26.9, 29.0, 30.7, 32.2, 33.8, 35.3, 36.7], [12.6, 10.0, 7.7, 5.1], 0.52   # (make_patch.py's)
def reverb_reference():
    """The reverb as make_patch.py builds it from Pd objects (both ears), fed by adc~, feedback 0.9, tone 4000."""
    objs, conns = ["adc~", "sig~ 0.9", "r tone", "dac~"], []
    def add(t):
        objs.append(t); return len(objs) - 1
    for side, extra, outlet in (("l", 0.0, 0), ("r", EXTRA, 1)):
        combs = []
        for i, ms in enumerate(COMB):
            rd = add(f"delread~ c{side}{i} {ms + extra:.2f}"); lp = add("lop~ 6000"); fbm = add("*~"); sm = add("+~")
            wr = add(f"delwrite~ c{side}{i} 100")
            conns += [(rd, 0, lp, 0), (2, 0, lp, 1), (lp, 0, fbm, 0), (1, 0, fbm, 1), (0, 0, sm, 0), (fbm, 0, sm, 1), (sm, 0, wr, 0)]
            combs.append(rd)
        acc = combs[0]
        for c in combs[1:]:
            a = add("+~"); conns += [(acc, 0, a, 0), (c, 0, a, 1)]; acc = a
        for k, ms in enumerate(ALLP):
            rd = add(f"delread~ a{side}{k} {ms + extra:.2f}"); g1 = add("*~ 0.5"); wv = add("+~"); wr = add(f"delwrite~ a{side}{k} 100")
            g2 = add("*~ 0.5"); y = add("-~")
            conns += [(rd, 0, g1, 0), (acc, 0, wv, 0), (g1, 0, wv, 1), (wv, 0, wr, 0), (wv, 0, g2, 0), (rd, 0, y, 0), (g2, 0, y, 1)]
            acc = y
        conns.append((acc, 0, 3, outlet))
    return patch("rev_ref", objs, conns)
def reverb_dcs():
    args = " ".join(str(v) for v in [EXTRA, len(COMB)] + COMB + ALLP)
    return patch("rev_dcs", ["adc~", "sig~ 0.9", "r tone", "dac~", f"dcs_reverb~ {args}", "msg tone \\$1"],
                 [(0, 0, 4, 0), (1, 0, 4, 1), (2, 0, 5, 0), (5, 0, 4, 0), (4, 0, 3, 0), (4, 1, 3, 1)])
rd_ = reverb_dcs(); src = open(rd_).read().replace("#X obj 10 165 msg tone", "#X msg 10 165 tone"); open(rd_, "w").write(src)
xin = np.zeros(4 * SR, np.float32); xin[100] = 0.5; xin[SR:SR + 2000] = rng.standard_normal(2000) * 0.2
outs, costs = [], []
for p in (reverb_reference(), rd_):
    e = Engine(LIB, p); e.send("tone", 4000); e.run(np.zeros(640, np.float32))
    t0 = time.process_time(); outs.append(e.run(xin)); costs.append(time.process_time() - t0); e.close()
diff = np.abs(outs[0] - outs[1]).max(); peak = np.abs(outs[0]).max()
check(peak > 0.05 and diff < 1e-5 * max(peak, 1), f"matches the Pd-object reverb sample for sample (worst {diff:.1e}, peak {peak:.2f}), both ears")
check(costs[1] < 0.75 * costs[0], f"costs {100 * costs[1] / costs[0]:.0f}% of the Pd-object version (the maths is the same: it saves the overhead of ~100 objects)")

# ---------------------------------------------------------------- dcs_voice~
print("dcs_voice~:")
vp = patch("voice", ["r vc", "dcs_voice~", "dac~"], [(0, 0, 1, 0), (1, 0, 2, 0), (1, 0, 2, 1)])
def play(msgs, secs, then=(), then_at=None):
    e = Engine(LIB, vp)
    for m in msgs:
        e.send_msg("vc", m[0], *m[1:])
    if then_at is None:
        y = e.run(np.zeros(int(secs * SR), np.float32))[:, 0]
    else:
        a = e.run(np.zeros(int(then_at * SR), np.float32))[:, 0]
        for m in then:
            e.send_msg("vc", m[0], *m[1:])
        y = np.concatenate([a, e.run(np.zeros(int((secs - then_at) * SR), np.float32))[:, 0]])
    e.close(); return y
def harm(y, f0, k):
    t = np.arange(len(y)) / SR; return abs(np.mean(y * np.exp(-2j * np.pi * f0 * k * t)))
y = play([("engine", 1), ("bright", 0.3), ("note", 220, 0.5, 1500)], 2.0)
w = y[int(0.05 * SR):int(0.5 * SR)]
check(abs(peak_hz(w, 200, 240) / 220 - 1) < 0.002 and harm(w, 220, 1) > 3 * harm(w, 220, 2) and 0.05 < np.abs(y).max() < 1
      and db_frames(y)[-5:].mean() < db_frames(y)[:5].mean() - 30,
      f"pluck: in tune, the note leads its overtones, dies away (peak {np.abs(y).max():.2f})")
y = play([("engine", 2), ("attack", 300), ("release", 600), ("pnote", 0, 110)], 4.0, [("pnote", 0, 165)], 2.5)
held = db_frames(y[int(1.0 * SR):int(2.4 * SR)], 100)   # (100 ms frames: 20 ms hold ~2 periods of 110 Hz and ripple by themselves)
late = y[int(3.4 * SR):]
check(held.max() - held.min() < 4 and held.mean() > -20 and abs(peak_hz(y[int(1.0 * SR):int(2.4 * SR)], 100, 120) / 110 - 1) < 0.003
      and harm(late, 165, 1) > 5 * harm(late, 110, 1),
      f"bowed: a held note stays level ({held.max() - held.min():.1f} dB swing), then the slot moves to the new note")
y = play([("engine", 2), ("release", 300), ("pnote", 0, 110)], 3.0, [("poff", 0)], 1.5)
check(np.abs(y[int(2.4 * SR):]).max() < 1e-3, "bowed: poff lets it go")
y = play([("engine", 3), ("modal", 1), ("note", 440, 0.5, 2000)], 2.5)
w = y[int(0.02 * SR):int(0.6 * SR)]
check(abs(peak_hz(w, 400, 480) / 440 - 1) < 0.002 and harm(w, 440 * 2.76, 1) > 0.1 * harm(w, 440, 1) and 0.02 < np.abs(y).max() < 1,
      f"modal bell: the note and its 2.76x partial, struck once (peak {np.abs(y).max():.2f})")
check(np.abs(play([("engine", 0), ("note", 440, 0.5, 1000)], 1.0)).max() == 0, "engine 0 plays nothing")
def cent(y):
    S_ = np.abs(np.fft.rfft(y * np.hanning(len(y)))); f = np.fft.rfftfreq(len(y), 1 / SR); return (S_ * f).sum() / S_.sum()
an = [("engine", 4), ("fenv", 0), ("reso", 0), ("attack", 5), ("detune", 0)]   # (detuned saws beat on purpose: off here)
y = play(an + [("cutoff", 4), ("pnote", 0, 220)], 1.5); w = y[int(0.3 * SR):]
dark = play(an + [("cutoff", 1.5), ("pnote", 0, 220)], 1.5)[int(0.3 * SR):]
bright = play(an + [("cutoff", 16), ("pnote", 0, 220)], 1.5)[int(0.3 * SR):]
check(abs(peak_hz(w, 200, 240) / 220 - 1) < 0.003 and cent(dark) < 0.7 * cent(w) < 0.7 * cent(bright) and 0.05 < np.abs(w).max() < 1,
      f"analog: in tune, the cutoff darkens and brightens it (brightness {cent(dark):.0f} / {cent(w):.0f} / {cent(bright):.0f} Hz)")
res = play([("engine", 4), ("fenv", 0), ("attack", 5), ("sub", 0), ("cutoff", 6), ("reso", 0.9), ("pnote", 0, 110)], 1.5)[int(0.3 * SR):]
flat = play([("engine", 4), ("fenv", 0), ("attack", 5), ("sub", 0), ("cutoff", 6), ("reso", 0), ("pnote", 0, 110)], 1.5)[int(0.3 * SR):]
check(harm(res, 110, 6) / harm(res, 110, 1) > 3 * harm(flat, 110, 6) / harm(flat, 110, 1),
      f"analog: resonance lifts the harmonics at the cutoff ({harm(res, 110, 6) / harm(res, 110, 1):.2f} vs {harm(flat, 110, 6) / harm(flat, 110, 1):.2f})")
hot = play([("engine", 4), ("fenv", 8), ("attack", 5), ("cutoff", 8), ("reso", 1), ("pnote", 0, 55)], 3.0)
check(np.isfinite(hot).all() and np.abs(hot).max() < 2, f"analog: full resonance stays stable (peak {np.abs(hot).max():.2f})")
hi = play(an + [("cutoff", 16), ("sub", 0), ("pnote", 0, 3000)], 1.0)[int(0.3 * SR):]
S_ = np.abs(np.fft.rfft(hi * np.hanning(len(hi)))) ** 2; f = np.fft.rfftfreq(len(hi), 1 / SR)
on_harm = sum(S_[np.abs(f - 3000 * k) < 15].sum() for k in range(1, 9))
check(on_harm / S_.sum() > 0.9, f"analog: a 3 kHz saw is band-limited ({100 * on_harm / S_.sum():.0f}% of its energy on its harmonics)")
dr = [("engine", 5)]
k = play(dr + [("hit", 0, 1)], 1.0)
check(abs(peak_hz(k[int(0.15 * SR):int(0.45 * SR)], 30, 120) - 50) < 4 and 0.3 < np.abs(k).max() <= 1.05
      and np.abs(k[int(0.9 * SR):]).max() < 0.25 * np.abs(k).max(),
      f"drums: the kick dives to its 50 Hz tune and dies away (peak {np.abs(k).max():.2f})")
sn = play(dr + [("hit", 1, 1)], 0.5)[:int(0.2 * SR)]
S_ = np.abs(np.fft.rfft(sn)) ** 2; fr = np.fft.rfftfreq(len(sn), 1 / SR)
check(S_[fr > 2000].sum() > 0.3 * S_.sum() and harm(sn, 185, 1) > 0.01, f"drums: the snare has its tone and its crack ({100 * S_[fr > 2000].sum() / S_.sum():.0f}% above 2 kHz)")
hc = play(dr + [("hit", 2, 1, 45)], 0.6); ho = play(dr + [("hit", 2, 1, 300)], 0.6)
S_ = np.abs(np.fft.rfft(hc)) ** 2; fr = np.fft.rfftfreq(len(hc), 1 / SR)
check(S_[fr > 5000].sum() > 0.8 * S_.sum() and rms(ho[int(0.15 * SR):]) > 10 * rms(hc[int(0.15 * SR):]),
      f"drums: hats are high ({100 * S_[fr > 5000].sum() / S_.sum():.0f}% above 5 kHz), an open one rings on")
check(np.abs(play([("engine", 4), ("hit", 0, 1)], 0.3)).max() == 0, "drums: hits only play on the drums engine")
one = play(an + [("cutoff", 16), ("saws", 1), ("pnote", 0, 220)], 1.5)[int(0.3 * SR):]
sev = play(an + [("cutoff", 16), ("saws", 7), ("detune", 25), ("pnote", 0, 220)], 1.5)[int(0.3 * SR):]
lift = 20 * np.log10(rms(sev) / rms(one))
check(abs(lift) < 3 and abs(peak_hz(sev, 210, 230) / 220 - 1) < 0.01, f"supersaw: 7 saws across 25 cents, about as loud as one ({lift:+.1f} dB), around the note")
def env_rate(y):
    """The strongest rate (Hz) at which y's level moves (2-20 Hz)."""
    e = np.sqrt(np.convolve(y ** 2, np.ones(240) / 240, "same"))[::48]; e = e - e.mean()
    S_ = np.abs(np.fft.rfft(e * np.hanning(len(e)), 1 << 16)); f = np.fft.rfftfreq(1 << 16, 48 / SR)
    b = (f > 2) & (f < 20); return float(f[b][np.argmax(S_[b])]), float(S_[b].max() / (np.abs(e).sum() + 1e-9))
wob = an + [("cutoff", 3), ("wrate", 2), ("tempo", 120)]
yw = play(wob + [("wobble", 1), ("pnote", 0, 220)], 3.0)[SR:]; y0 = play(wob + [("wobble", 0), ("pnote", 0, 220)], 3.0)[SR:]
rw, sw_ = env_rate(yw); _, s0_ = env_rate(y0)
check(abs(rw - 4) < 0.2 and sw_ > 5 * s0_, f"wobble: 2 a beat at 120 BPM pulses at {rw:.2f} Hz (vs no wobble: {sw_ / max(s0_, 1e-9):.0f}x stronger)")
yb = play(an + [("cutoff", 8), ("bend", -2), ("bendms", 150), ("pnote", 0, 220)], 1.0)
check(peak_hz(yb[int(0.005 * SR):int(0.04 * SR)], 150, 260) < 210 and abs(peak_hz(yb[int(0.5 * SR):], 200, 240) / 220 - 1) < 0.003,
      f"bend: a note starts low ({peak_hz(yb[int(0.005 * SR):int(0.04 * SR)], 150, 260):.0f} Hz) and glides to 220")
cp = patch("chop", ["r vc", "dcs_voice~", "dac~", "table fpad_0 48000", "table fpad_f0 2", "table fpad_g 2", "table fpad_n 2"],
           [(0, 0, 1, 0), (1, 0, 2, 0), (1, 0, 2, 1)])
def chop(kept, secs=0.6):
    e = Engine(LIB, cp); L = e.lib
    L.libpd_write_array.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
    def put(name, vals):
        a = np.asarray(vals, np.float32); L.libpd_write_array(name.encode(), 0, a.ctypes.data, len(a))
    put("fpad_0", 0.5 * np.sin(2 * np.pi * 220 * np.arange(48000) / SR)); put("fpad_f0", [220, 0]); put("fpad_g", [1, 1])
    put("fpad_n", [kept, 0])
    for m in [("engine", 6), ("chop", 180), ("note", 330, 0.8, 1000)]:
        e.send_msg("vc", m[0], *m[1:])
    y = e.run(np.zeros(int(secs * SR), np.float32))[:, 0]; e.close(); return y
yc = chop(1); yf = chop(0)
on = np.nonzero(np.abs(yc) > 0.01)[0]
check(len(on) and abs(peak_hz(yc[on[0]:on[-1]], 280, 380) / 330 - 1) < 0.005 and 0.15 < (on[-1] - on[0]) / SR < 0.21
      and rms(yf) > 0.01 and peak_hz(yf, 280, 380) > 320,
      f"chop: a slice of the held voice at the note ({peak_hz(yc[on[0]:on[-1]], 280, 380):.1f} Hz, {(on[-1] - on[0]) / SR * 1000:.0f} ms); nothing kept: the analog voice plays it")
sb = [("engine", 7), ("decay", 2000), ("drive", 0.3)]
y8 = play(sb + [("glide", 120), ("pnote", 0, 55)], 3.0, [("pnote", 0, 82.4)], 1.5)
mid = [peak_hz(y8[int(t * SR):int((t + 0.06) * SR)], 40, 100) for t in (1.50, 1.56, 1.62)]
check(abs(peak_hz(y8[int(0.3 * SR):int(1.4 * SR)], 40, 100) - 55) < 1 and abs(peak_hz(y8[int(1.9 * SR):], 40, 100) - 82.4) < 1
      and mid[0] < mid[1] < 82 and rms(y8[int(1.55 * SR):int(1.7 * SR)]) > rms(y8[int(1.3 * SR):int(1.45 * SR)]),
      f"808: a held 55 Hz slides to 82.4 over ~120 ms ({[round(m) for m in mid]} Hz), its level starting again")
check(db_frames(y8[:int(1.5 * SR)], 100)[1] > db_frames(y8[:int(1.5 * SR)], 100)[13] + 4, "808: each note dies away over its decay")
oc = play([("engine", 4), ("fenv", 0), ("attack", 5), ("detune", 0), ("octave", -1), ("pnote", 0, 220)], 1.0)[int(0.3 * SR):]
check(abs(peak_hz(oc, 90, 130) - 110) < 1, "octave -1 plays a 220 Hz note at 110")
e = Engine(LIB, vp); e.send_msg("vc", "engine", 1); e.send_msg("vc", "chance", 0.3)
heard = 0
for k in range(200):                       # (each note dies within its 0.25 s window, so none is counted twice)
    e.send_msg("vc", "note", 440, 0.5, 120); heard += np.abs(e.run(np.zeros(int(0.25 * SR), np.float32))[:, 0]).max() > 0.01
e.close()
check(40 < heard < 80, f"chance 0.3 plays about a third of the notes ({heard} of 200)")
held = db_frames(play(an + [("cutoff", 4), ("pnote", 0, 110)], 3.0)[int(0.5 * SR):], 100)
check(held.max() - held.min() < 1, f"analog: a held note stands steady ({held.max() - held.min():.2f} dB)")

print("ALL PASSED" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
