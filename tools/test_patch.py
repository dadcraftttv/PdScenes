#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Behaviour tests for the Pd patch, run through a desktop libpd build.

    python3 tools/test_patch.py /path/to/libpd.so
"""
import os, re, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from pdtest import Engine, SR

ROOT = os.path.join(os.path.dirname(__file__), "..")
PATCH = os.path.join(ROOT, "app/src/main/assets/patches/test_scene.pd")
PARAMS_JAVA = os.path.join(ROOT, "app/src/main/java/app/pdscenes/Params.java")
LIB = sys.argv[1] if len(sys.argv) > 1 else "libpd.so"

fails = 0
def check(cond, msg):
    global fails
    print(("ok:   " if cond else "FAIL: ") + msg)
    if not cond:
        fails += 1

# Reads the parameter list straight out of Params.java: (id, default, noPd?)
def java_params():
    src = open(PARAMS_JAVA).read()
    out = []
    for m in re.finditer(r'new Param\("(\w+)",\s*"[^"]*",\s*([-\d.]+)f?,\s*([-\d.]+)f?,\s*([-\d.]+)f?,'
                         r'[^;]*?(?=new Param\(|\)\);)', src, re.S):
        out.append((m.group(1), float(m.group(4)), ".noPd()" in m.group(0)))
    return out

L = 2   # ms of fixed latency from the spatial stage (1.5 ms, rounded in peak reports)

def fresh(**over):
    e = Engine(LIB, PATCH)
    base = dict(gain=1, dry=1, echo_on=1, echo_time=350, feedback=0.4, wet=0.5,
                ring_on=1, ring_freq=80, ring_mix=0, smooth=30,
                pitch_on=1, pitch_semi=0, pitch_mix=0, pitch_window=60,
                crush_on=1, crush_mix=0, crush_bits=8, crush_rate=8000,
                space_on=1, space_pan=0, space_shift=0,
                filter_on=1, filter_mix=0, filter_type=0, filter_freq=1500, filter_q=1,
                reverb_on=1, reverb_mix=0, reverb_size=0.5, reverb_tone=6000,
                chorus_on=1, chorus_mix=0, chorus_rate=0.8, chorus_depth=3,
                trem_on=1, trem_depth=0, trem_rate=5,
                gate_thresh=-80, comp_thresh=0, comp_ratio=4, comp_makeup=0,
                dist_on=1, dist_mix=0, dist_drive=4, dist_type=0,
                rvs_on=1, rvs_mix=0, rvs_time=400,
                glitch_on=1, glitch_hold=0, glitch_len=120,
                flange_on=1, flange_mix=0, flange_rate=0.3, flange_depth=4, flange_fb=0.5,
                phaser_on=1, phaser_mix=0, phaser_rate=0.4, phaser_depth=0.7, phaser_fb=0.4,
                beat_on=1, beat_level=0, beat_hats=0.5, beat_snare=0.6, beat_pitch=55,
                music_on=0, music_key=0, music_scale=0, music_pad=0.33, music_arp=0.4,
                music_tone=0.5, music_react=0.8, music_res=0.8, music_harm=0, echo_scatter=0, music_pad_reg=2, pocket_hush=0.5, pocket_guard=0.6)
    base.update(over)
    for k, v in base.items():
        e.send(k, v)
    e.run(e.silence(0.5))   # let ramps settle
    return e

def sine(freq, amp, secs):
    t = np.arange(int(secs * SR)) / SR
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)

def rms(x):
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0

def tone_level(x, freq):
    """Amplitude of a single frequency in x (Goertzel-like projection)."""
    t = np.arange(len(x)) / SR
    return 2 * abs(np.mean(x * np.exp(-2j * np.pi * freq * t)))

# ---- 1. patch loads cleanly and matches Params.java ----
e = fresh()
bad = [l for l in e.log if "couldn't create" in l or "error" in l.lower() or "bad" in l.lower()]
check(not bad, "patch loads with no Pd errors" + (": %s" % bad if bad else ""))

jp = java_params()
patch_text = open(PATCH).read()
receivers = set(re.findall(r"#X obj \d+ \d+ r (\w+);", patch_text)) - {"step", "scale_n", "pad_glide", "mic_level", "pad_slot", "pool_n", "pool_x", "pocket", "pocket_down", "duck", "step_strength", "step_hit", "beat_sure", "groove", "gc_mode"} - {r for r in re.findall(r"#X obj \d+ \d+ r (sw_\w+);", open(PATCH).read())}   # events and internal links, not settings
pd_ids = {i for i, _, nopd in jp if not nopd}
check(len(jp) >= 10, "parsed %d params from Params.java" % len(jp))
check(pd_ids == receivers, "Params.java ids == patch receivers (java-only %s, patch-only %s)"
      % (sorted(pd_ids - receivers), sorted(receivers - pd_ids)))
msg = re.search(r"#X msg \d+ \d+ (\\; gain .*?);\n", patch_text).group(1)
loadbang = {k: float(v) for k, v in re.findall(r"\; (\w+) ([-\d.]+)", msg)}
mism = [(i, d, loadbang.get(i)) for i, d, nopd in jp if not nopd and abs(loadbang.get(i, 1e9) - d) > 1e-6]
check(not mism, "loadbang defaults match Params.java defaults %s" % (mism or ""))

# ---- 2. echo timing and level ----
e = fresh()
x = np.zeros(SR * 2, np.float32); x[0] = 0.2
y = e.run(x)[:, 0]
def peaks(y, thr=0.005):
    z = np.concatenate(([0.0], y, [0.0]))   # pad so the very first sample can be a peak
    return [(round((i - 1) / SR * 1000), round(float(z[i]), 3)) for i in range(1, len(z) - 1)
            if abs(z[i]) > thr and abs(z[i]) >= abs(z[i - 1]) and abs(z[i]) >= abs(z[i + 1])]
p = peaks(y)
check(p[:3] == [(L, 0.2), (350 + L, 0.1), (700 + L, 0.04)], "echo impulse response (ms, amp): %s" % p[:4])

# ---- 3. echo bypass ----
e = fresh(echo_on=0)
y = e.run(x)[:, 0]
check(peaks(y) == [(L, 0.2)], "echo_on=0 leaves only the dry impulse: %s" % peaks(y))

# bypass keeps working when toggled live, echo returns
e = fresh(echo_on=0)
e.send("echo_on", 1); e.run(e.silence(0.3))
y = e.run(x)[:, 0]
check(len(peaks(y)) >= 3, "echo returns after echo_on 0 -> 1")

# ---- 4. dry level ----
e = fresh(wet=0, dry=0.5)
y = e.run(sine(440, 0.1, 0.5))[:, 0]
check(abs(rms(y[SR // 4:]) / (0.1 * 3 / 3 / np.sqrt(2)) - 0.5) < 0.02, "dry=0.5 halves the direct level")
e = fresh(wet=0, dry=0)
check(rms(e.run(sine(440, 0.3, 0.5))[SR // 4:]) < 1e-6, "dry=0, wet=0 is silent")

# ---- 5. ring modulator ----
e = fresh(wet=0, ring_mix=1, ring_freq=100, ring_on=1)
y = e.run(sine(440, 0.1, 1.0))[SR // 2:, 0]
check(tone_level(y, 340) > 0.04 and tone_level(y, 540) > 0.04 and tone_level(y, 440) < 0.01,
      "ring mod at 100 Hz moves 440 Hz to 340/540 Hz (340=%.3f 540=%.3f 440=%.3f)"
      % (tone_level(y, 340), tone_level(y, 540), tone_level(y, 440)))
e = fresh(wet=0, ring_mix=1, ring_freq=100, ring_on=0)
y = e.run(sine(440, 0.1, 1.0))[SR // 2:, 0]
check(tone_level(y, 440) > 0.095 and tone_level(y, 340) < 0.005, "ring_on=0 passes the signal unchanged")

# ---- 6. smoothing: no clicks when toggling, and ramp time follows 'smooth' ----
def max_jump(y): return float(np.max(np.abs(np.diff(y))))
e = fresh(wet=0, ring_mix=1, ring_freq=100)
src = sine(440, 0.1, 1.0)
natural = 2 * np.pi * 440 / SR * 0.1 * 2   # generous bound for a 440 Hz sine at this level (x2 for ring mod)
e.send("ring_on", 0)
y = e.run(src)[:, 0]
check(max_jump(y) < natural * 1.5, "toggling ring mod live has no click (max step %.4f, bound %.4f)"
      % (max_jump(y), natural * 1.5))

def settle_ms(smooth):
    e = fresh(wet=0, smooth=smooth, gain=3)
    e.run(sine(440, 0.1, 0.3))
    e.send("dry", 0)
    y = e.run(sine(440, 0.1, 2.0))[:, 0]
    env = np.abs(y)
    idx = np.where(np.convolve(env, np.ones(48) / 48, "same") < 0.01)[0]
    return idx[0] / SR * 1000 if len(idx) else float("inf")
fast, slow = settle_ms(5), settle_ms(400)
check(slow > 4 * fast and 250 < slow < 600 and fast < 60, "smooth=5ms settles in %.0f ms, smooth=400ms in %.0f ms" % (fast, slow))

# ---- 7. pitch shifter ----
# A pure tone through a crossfading shifter grows side-bands, so we measure where the energy
# lands (share of power within +-4% of a frequency) rather than the single loudest FFT bin.
def band_share(y, f0, rel=0.04):
    sp = np.abs(np.fft.rfft(y * np.hanning(len(y)))) ** 2
    f = np.fft.rfftfreq(len(y), 1 / SR)
    total = sp[(f > 50) & (f < 4000)].sum()
    return float(sp[(f > f0 * (1 - rel)) & (f < f0 * (1 + rel))].sum() / total)

def pitched(semi, mix=1, win=60, on=1, freq=440, amp=0.1, secs=2.5):
    e = fresh(wet=0, dry=1, pitch_semi=semi, pitch_mix=mix, pitch_window=win, pitch_on=on)
    return e.run(sine(freq, amp, secs))[SR // 2:, 0]

for semi in (12, 7, -5, -12):
    y = pitched(semi); want = 440 * 2 ** (semi / 12)
    check(band_share(y, want) > 0.9 and band_share(y, 440) < 0.01,
          "pitch %+d st: %.0f%% of energy at %.1f Hz, %.1f%% left at 440 Hz"
          % (semi, 100 * band_share(y, want), want, 100 * band_share(y, 440)))
for win in (40, 100, 200):
    y = pitched(7, win=win); want = 440 * 2 ** (7 / 12)
    check(band_share(y, want) > 0.9, "grain size %d ms: +7 st lands on target (%.0f%%)" % (win, 100 * band_share(y, want)))
y = pitched(7, win=20)
check(band_share(y, 440) < 0.02 and rms(y) > 0.04,
      "grain size 20 ms still moves the pitch away from 440 Hz and keeps level (known: pure tones comb at this size)")
y = pitched(12)
check(0.7 < rms(y) / (0.1 / np.sqrt(2)) < 1.1, "shifted level is close to input level (ratio %.2f)" % (rms(y) / (0.1 / np.sqrt(2))))
check(band_share(pitched(0, mix=0), 440) > 0.99, "mix=0 leaves the original untouched")
check(band_share(pitched(12, mix=1, on=0), 440) > 0.99, "pitch_on=0 bypasses even at mix=1")
ym = pitched(12, mix=0.5)
check(0.3 < band_share(ym, 440) < 0.7 and 0.3 < band_share(ym, 880) < 0.7,
      "mix=0.5 gives original and octave-up together (%.0f%% / %.0f%%)" % (100 * band_share(ym, 440), 100 * band_share(ym, 880)))
e = fresh(wet=0, pitch_semi=0, pitch_mix=1)
e.run(sine(440, 0.1, 0.5)); e.send("pitch_semi", 7)
yy = e.run(sine(440, 0.1, 1.0))[:, 0]
check(max_jump(yy) < 0.05, "changing pitch live: no click (max step %.4f)" % max_jump(yy))
e = fresh(wet=0, pitch_semi=7, pitch_mix=1)
check(rms(e.run(e.silence(1.0))) < 1e-6, "shifter adds no noise on silent input")

# ---- 7b. bit crusher ----
def crushed(secs=1.5, amp=0.5, freq=440, **over):
    e = fresh(wet=0, dry=1, crush_mix=1, **over)
    return e.run(sine(freq, amp, secs))[SR // 2:, 0]

for bits in (2, 4, 8):
    y = crushed(crush_bits=bits, crush_rate=24000)
    levels = 2 ** (bits - 1)
    steps = np.unique(np.round(y * levels, 3))
    check(len(steps) <= 2 * levels + 1 and np.allclose(steps, np.round(steps)),
          "%d bits: %d distinct levels, all on the 1/%d grid" % (bits, len(steps), levels))
check(len(np.unique(np.round(crushed(crush_bits=16, crush_rate=24000), 5))) > 200, "16 bits stays smooth")

for rate in (2000, 4000, 8000):
    y = crushed(crush_bits=16, crush_rate=rate, secs=1.5, freq=100)
    changes = np.count_nonzero(np.abs(np.diff(y)) > 1e-7) / (len(y) / SR)
    check(0.9 * rate < changes < 1.1 * rate, "rate %d Hz: signal changes %.0f times a second" % (rate, changes))

e = fresh(wet=0, dry=1, crush_mix=1, crush_bits=3, crush_rate=2000, crush_on=0)
y = e.run(sine(440, 0.1, 1.0))[SR // 2:, 0]
check(tone_level(y, 440) > 0.095, "crush_on=0 bypasses even at mix=1")
e = fresh(wet=0, dry=1, crush_mix=0, crush_bits=3, crush_rate=2000)
y = e.run(sine(440, 0.1, 1.0))[SR // 2:, 0]
check(tone_level(y, 440) > 0.095 and band_share(y, 440) > 0.99, "mix=0 leaves the signal clean")
ym = crushed(crush_bits=16, crush_rate=24000)
check(0.9 < rms(ym) / (0.5 / np.sqrt(2)) < 1.1, "gentle settings keep the level (ratio %.2f)" % (rms(ym) / (0.5 / np.sqrt(2))))
e = fresh(wet=0, dry=1, crush_mix=0, crush_bits=16, crush_rate=24000)
e.run(sine(440, 0.1, 0.3)); e.send("crush_mix", 1)
yy = e.run(sine(440, 0.1, 0.5))[:, 0]
check(max_jump(yy) < 0.05, "turning the crusher on live: no click (max step %.4f)" % max_jump(yy))
e = fresh(wet=0, dry=1, crush_mix=1, crush_bits=1, crush_rate=500, gain=10)
yy = e.run(sine(440, 0.5, 1.0))
check(not np.isnan(yy).any() and float(np.abs(yy).max()) <= 1.0 + 1e-6, "extreme crush settings: no NaN, within +-1")
e = fresh(wet=0, crush_mix=1, crush_bits=3, crush_rate=2000)
check(rms(e.run(e.silence(1.0))) < 1e-6, "crusher adds no noise on silent input")

# ---- 7c. spatial: pan and ear delay ----
def stereo(secs=1.0, amp=0.1, freq=440, **over):
    e = fresh(wet=0, dry=1, **over)
    return e.run(sine(freq, amp, secs))[SR // 2:]
def lr(y):
    return rms(y[:, 0]), rms(y[:, 1])

l0, r0 = lr(stereo())
check(abs(l0 - r0) < 1e-6 and l0 > 0.06, "centre: both ears identical and at full level (%.4f / %.4f)" % (l0, r0))
yc = stereo()
check(np.allclose(yc[:, 0], yc[:, 1], atol=1e-6), "centre: left and right are sample-identical")
for pan, want_l, want_r in ((1, 0, 1), (-1, 1, 0), (0.5, 0.5, 1), (-0.5, 1, 0.5)):
    l, r = lr(stereo(space_pan=pan))
    check(abs(l / l0 - want_l) < 0.02 and abs(r / l0 - want_r) < 0.02,
          "pan %+.1f: left %.2f, right %.2f of centre level" % (pan, l / l0, r / l0))
l, r = lr(stereo(space_pan=1, space_on=0))
check(abs(l - r) < 1e-6, "space_on=0 centres the sound even with pan=1")

def ear_delays(shift):
    e = fresh(wet=0, dry=1, space_shift=shift)
    x = np.zeros(SR // 2, np.float32); x[640] = 0.2
    y = e.run(x)
    return [int(np.argmax(np.abs(y[:, c]))) - 640 for c in (0, 1)]
base = ear_delays(0)
check(base[0] == base[1] and abs(base[0] / SR * 1000 - 1.5) < 0.1, "ear delay 0: both ears %.2f ms behind" % (base[0] / SR * 1000))
for shift in (5, 12, 25):
    dl, dr = ear_delays(shift)
    check(dl == base[0] and abs((dr - dl) / SR * 1000 - shift) < 0.1, "shift +%d ms delays only the right ear (%.2f ms apart)" % (shift, (dr - dl) / SR * 1000))
dl, dr = ear_delays(-8)
check(dr == base[0] and abs((dl - dr) / SR * 1000 - 8) < 0.1, "shift -8 ms delays only the left ear (%.2f ms apart)" % ((dl - dr) / SR * 1000))
dl, dr = ear_delays(0)
e = fresh(wet=0, dry=1, space_shift=20, space_on=0)
x = np.zeros(SR // 2, np.float32); x[640] = 0.2
y = e.run(x)
check(int(np.argmax(np.abs(y[:, 0]))) == int(np.argmax(np.abs(y[:, 1]))), "space_on=0 removes the ear delay")

e = fresh(wet=0, dry=1)
e.run(sine(440, 0.1, 0.3)); e.send("space_pan", 1.0)
yy = e.run(sine(440, 0.1, 0.5))
check(max(max_jump(yy[:, 0]), max_jump(yy[:, 1])) < 0.02, "moving the pan live: no click (max step %.4f)" % max(max_jump(yy[:, 0]), max_jump(yy[:, 1])))
e = fresh(wet=0, dry=1, space_shift=0)
e.run(sine(440, 0.1, 0.3)); e.send("space_shift", 20)
yy = e.run(sine(440, 0.1, 1.0))
check(max(max_jump(yy[:, 0]), max_jump(yy[:, 1])) < 0.05, "changing the ear delay live: no click (max step %.4f)" % max(max_jump(yy[:, 0]), max_jump(yy[:, 1])))
e = fresh(wet=0, space_shift=25, space_pan=0.5)
check(rms(e.run(e.silence(1.0))) < 1e-6, "spatial stage adds no noise on silent input")

# ---- 7d. filter ----
def gain_db(f, **over):
    """Level of a sine at f through the filter, in dB relative to the input."""
    e = fresh(wet=0, dry=1, filter_mix=1, **over)
    y = e.run(sine(f, 0.1, 1.0))[SR // 2:, 0]
    return 20 * np.log10(rms(y) / (0.1 / np.sqrt(2)) + 1e-12)

LP, HP, BP = 0, 1, 2
check(abs(gain_db(250, filter_type=LP, filter_freq=1000, filter_q=0.707)) < 1.5, "low-pass 1 kHz passes 250 Hz (%.1f dB)" % gain_db(250, filter_type=LP, filter_freq=1000, filter_q=0.707))
check(-4.5 < gain_db(1000, filter_type=LP, filter_freq=1000, filter_q=0.707) < -1.5, "low-pass is about -3 dB at its cutoff (%.1f dB)" % gain_db(1000, filter_type=LP, filter_freq=1000, filter_q=0.707))
check(gain_db(4000, filter_type=LP, filter_freq=1000, filter_q=0.707) < -15, "low-pass 1 kHz cuts 4 kHz (%.1f dB)" % gain_db(4000, filter_type=LP, filter_freq=1000, filter_q=0.707))
check(abs(gain_db(4000, filter_type=HP, filter_freq=1000, filter_q=0.707)) < 1.5, "high-pass 1 kHz passes 4 kHz (%.1f dB)" % gain_db(4000, filter_type=HP, filter_freq=1000, filter_q=0.707))
check(gain_db(250, filter_type=HP, filter_freq=1000, filter_q=0.707) < -15, "high-pass 1 kHz cuts 250 Hz (%.1f dB)" % gain_db(250, filter_type=HP, filter_freq=1000, filter_q=0.707))
check(abs(gain_db(1000, filter_type=BP, filter_freq=1000, filter_q=4)) < 1.5, "band-pass passes its centre at ~0 dB (%.1f dB)" % gain_db(1000, filter_type=BP, filter_freq=1000, filter_q=4))
check(gain_db(250, filter_type=BP, filter_freq=1000, filter_q=4) < -12 and gain_db(4000, filter_type=BP, filter_freq=1000, filter_q=4) < -12, "band-pass cuts well below and above (%.1f / %.1f dB)" % (gain_db(250, filter_type=BP, filter_freq=1000, filter_q=4), gain_db(4000, filter_type=BP, filter_freq=1000, filter_q=4)))
check(gain_db(1000, filter_type=LP, filter_freq=1000, filter_q=8) > 10, "high Q adds a resonant peak at the cutoff (%.1f dB)" % gain_db(1000, filter_type=LP, filter_freq=1000, filter_q=8))
check(gain_db(8000, filter_type=LP, filter_freq=500, filter_q=1) < -30, "cutoff moves: low-pass 500 Hz cuts 8 kHz hard (%.1f dB)" % gain_db(8000, filter_type=LP, filter_freq=500, filter_q=1))
e = fresh(wet=0, dry=1, filter_mix=0, filter_freq=300, filter_q=8)
y = e.run(sine(3000, 0.1, 1.0))[SR // 2:, 0]
check(tone_level(y, 3000) > 0.099, "filter amount 0 leaves the signal untouched")
e = fresh(wet=0, dry=1, filter_mix=1, filter_freq=300, filter_on=0)
y = e.run(sine(3000, 0.1, 1.0))[SR // 2:, 0]
check(tone_level(y, 3000) > 0.099, "filter_on=0 bypasses even at amount 1")
ym = gain_db(1000, filter_type=HP, filter_freq=1000, filter_q=0.707)
e = fresh(wet=0, dry=1, filter_mix=0.5, filter_type=LP, filter_freq=300)
y = e.run(sine(3000, 0.1, 1.0))[SR // 2:, 0]
check(0.4 < tone_level(y, 3000) / 0.1 < 0.6, "amount 0.5 blends half dry, half filtered (%.2f)" % (tone_level(y, 3000) / 0.1))
e = fresh(wet=0, dry=1, filter_mix=1, filter_type=LP, filter_freq=200, filter_q=1)
e.run(sine(440, 0.1, 0.3)); e.send("filter_freq", 6000)
yy = e.run(sine(440, 0.1, 1.0))[:, 0]
check(max_jump(yy) < 0.15, "jumping the cutoff 200 -> 6000 Hz live: smoothed, no pop (max step %.3f, input is only 0.1 peak)" % max_jump(yy))
e = fresh(wet=0, dry=1, filter_mix=1, filter_q=12, filter_freq=80)
rng = np.random.default_rng(3)
noise = (rng.standard_normal(SR * 3) * 0.3).astype(np.float32)
bad = False
for t in (0, 1, 2, 0, 2, 1):
    e.send("filter_type", t); e.send("filter_freq", 80 if t == 0 else 12000)
    y = e.run(noise[:SR // 2]); bad |= bool(np.isnan(y).any() or np.abs(y).max() > 1.0 + 1e-6)
check(not bad, "switching filter type and extremes live: no NaN, output within +-1")
e = fresh(wet=0, filter_mix=1, filter_q=12)
check(rms(e.run(e.silence(1.0))) < 1e-6, "filter adds no noise on silent input")
e = fresh(wet=0, dry=1, filter_mix=1, filter_type=LP, filter_freq=1500)
check(not [l for l in e.log if "expr" in l.lower() and "error" in l.lower()], "filter expression parsed without errors")

# ---- 7e. reverb ----
def reverb_only(x, **over):
    """What the reverb adds: output with the reverb on minus output with it off (the reverb
    listens to the mix after the echo, so the direct sound has to be on)."""
    on = fresh(wet=0, dry=1, reverb_mix=1, **over).run(x)
    off = fresh(wet=0, dry=1, reverb_mix=0, **over).run(x)
    return on - off

def reverb_ir(secs=4.0, **over):
    x = np.zeros(int(SR * secs), np.float32); x[0] = 0.5
    return reverb_only(x, **over)

def decay_time(y, drop_db=40, win=0.02):
    """Seconds until the 20 ms RMS envelope falls drop_db below its peak (after the first 50 ms)."""
    n = int(win * SR)
    env = np.sqrt(np.convolve(y ** 2, np.ones(n) / n, "same"))
    peak = env[int(0.05 * SR):].max()
    below = np.where(env[int(0.05 * SR):] < peak * 10 ** (-drop_db / 20))[0]
    return (below[0] / SR + 0.05) if len(below) else float("inf")

y = reverb_ir(reverb_size=0.5)
check(rms(y[:, 0][int(0.1 * SR):int(0.6 * SR)]) > 1e-4, "reverb produces a tail (%.2e rms at 0.1-0.6 s)" % rms(y[:, 0][int(0.1 * SR):int(0.6 * SR)]))
t_small, t_big = decay_time(reverb_ir(8.0, reverb_size=0.2)[:, 0], 30), decay_time(reverb_ir(8.0, reverb_size=0.95)[:, 0], 30)
check(t_big > 2 * t_small and t_small < 2.0, "bigger room rings longer (30 dB decay: %.2f s small, %.2f s big)" % (t_small, t_big))
def centroid(y):
    sp = np.abs(np.fft.rfft(y[int(0.1 * SR):])) ** 2
    f = np.fft.rfftfreq(len(y[int(0.1 * SR):]), 1 / SR)
    return float((sp * f).sum() / sp.sum())
c_dark, c_bright = centroid(reverb_ir(reverb_tone=1500)[:, 0]), centroid(reverb_ir(reverb_tone=16000)[:, 0])
check(c_dark < 0.8 * c_bright, "lower brightness darkens the tail (centroid %.0f Hz vs %.0f Hz)" % (c_dark, c_bright))
yst = reverb_ir()
tl, tr = yst[int(0.1 * SR):, 0], yst[int(0.1 * SR):, 1]
corr = float(np.corrcoef(tl, tr)[0, 1])
check(abs(corr) < 0.8 and rms(tl) > 1e-4 and rms(tr) > 1e-4, "left and right tails differ, so it sounds wide (correlation %.2f)" % corr)

rng = np.random.default_rng(5)
nz = (rng.standard_normal(SR * 3) * 0.1).astype(np.float32)
levels = []
for size in (0.1, 0.5, 0.95):
    levels.append(rms(reverb_only(nz, reverb_size=size)[SR:, 0]) / rms(nz))
check(max(levels) / min(levels) < 2.0 and 0.3 < levels[1] < 1.5, "reverb loudness stays similar across sizes (x input: %s)" % ", ".join("%.2f" % v for v in levels))
e = fresh(wet=0, dry=1, reverb_mix=0, reverb_size=0.9)
y = e.run(sine(440, 0.1, 1.0))[SR // 2:, 0]
check(tone_level(y, 440) > 0.099 and band_share(y, 440) > 0.999, "reverb level 0 leaves the dry sound untouched")
e = fresh(wet=0, dry=1, reverb_mix=1, reverb_on=0)
x = np.zeros(SR, np.float32); x[0] = 0.2
y = e.run(x)[:, 0]
check(peaks(y) == [(L, 0.2)] and rms(y[SR // 2:]) < 1e-6, "reverb_on=0 bypasses even at level 1")
e = fresh(wet=0, dry=1, reverb_mix=0)
e.run(sine(440, 0.1, 0.3)); e.send("reverb_mix", 1)
yy = e.run(sine(440, 0.1, 0.5))
check(max(max_jump(yy[:, 0]), max_jump(yy[:, 1])) < 0.05, "turning the reverb up live: no click (max step %.4f)" % max(max_jump(yy[:, 0]), max_jump(yy[:, 1])))
e = fresh(wet=0, dry=1, reverb_mix=1, reverb_size=1, reverb_tone=16000, gain=10)
loud = (np.random.default_rng(6).standard_normal(SR * 10) * 0.5).astype(np.float32)
y = e.run(loud)
check(not np.isnan(y).any() and float(np.abs(y).max()) <= 1.0 + 1e-6, "loud noise into the biggest reverb: no NaN, within +-1")
tail = e.run(e.silence(30))
check(rms(tail[-SR:]) < 1e-3, "biggest reverb decays to silence (last second rms %.2e)" % rms(tail[-SR:]))
e = fresh(wet=0, reverb_mix=1, reverb_size=1)
check(rms(e.run(e.silence(1.0))) < 1e-6, "reverb adds no noise on silent input")

# ---- 7f. tremolo ----
def envelope(y, win_ms=5):
    n = int(win_ms * SR / 1000)
    return np.sqrt(np.convolve(y ** 2, np.ones(n) / n, "same"))[n:-n]

def trem(secs=3.0, **over):
    e = fresh(wet=0, dry=1, **over)
    return e.run(sine(440, 0.1, secs))[SR // 2:, 0]

env = envelope(trem(trem_depth=1, trem_rate=4))
check(env.min() / env.max() < 0.05, "tremolo depth 1 dips to silence (min/max %.3f)" % (env.min() / env.max()))
env = envelope(trem(trem_depth=0.5, trem_rate=4))
check(0.4 < env.min() / env.max() < 0.6, "tremolo depth 0.5 dips to half (min/max %.2f)" % (env.min() / env.max()))
for rate in (2, 6, 12):
    env = envelope(trem(secs=4.0, trem_depth=1, trem_rate=rate))
    spec = np.abs(np.fft.rfft(env - env.mean()))
    freq = float(np.fft.rfftfreq(len(env), 1 / SR)[np.argmax(spec)])
    check(abs(freq - rate) < 0.4, "tremolo rate %d Hz: envelope repeats at %.2f Hz" % (rate, freq))
env = envelope(trem(trem_depth=0, trem_rate=8), 25)
check(env.max() / env.min() < 1.02, "tremolo depth 0 leaves the level steady")
env = envelope(trem(trem_depth=1, trem_rate=4, trem_on=0), 25)
check(env.max() / env.min() < 1.02, "trem_on=0 bypasses even at depth 1")
check(float(np.abs(trem(trem_depth=1, trem_rate=5)).max()) <= 0.1001, "tremolo never makes the sound louder than the input")
e = fresh(wet=0, dry=1, trem_depth=0, trem_rate=5)
e.run(sine(440, 0.1, 0.3)); e.send("trem_depth", 1)
yy = e.run(sine(440, 0.1, 0.5))[:, 0]
check(max_jump(yy) < 0.02, "turning the tremolo up live: no click (max step %.4f)" % max_jump(yy))
e = fresh(wet=0, trem_depth=1, trem_rate=20)
check(rms(e.run(e.silence(1.0))) < 1e-6, "tremolo adds no noise on silent input")

# ---- 7g. chorus ----
def tap_delays(impulses=20, **over):
    """Delay (ms) of the two chorus taps for impulses fired at different points of the sweep."""
    out = []
    for i in range(impulses):
        e = fresh(wet=0, dry=1, chorus_mix=1, **over) if i == 0 else e
        x = np.zeros(int(0.113 * SR), np.float32); x[100] = 0.4
        y = e.run(x)[:, 0]
        z = np.abs(y); idx = np.where(z > 0.05)[0]
        if len(idx):
            groups = np.split(idx, np.where(np.diff(idx) > 24)[0] + 1)   # separate the two taps
            out.append([(g[np.argmax(z[g])] - 100) / SR * 1000 - 1.5 for g in groups])   # minus spatial latency
    return out

d = tap_delays(chorus_depth=0.2, chorus_rate=0.05)
check(all(len(g) == 2 and abs(g[0] - 15) < 0.8 and abs(g[1] - 21) < 0.8 for g in d), "chorus taps sit near 15 and 21 ms at minimum depth: %s" % [[round(v, 1) for v in g] for g in d[:2]])
d = tap_delays(impulses=40, chorus_depth=5, chorus_rate=3)
firsts = [g[0] for g in d if len(g) == 2]
check(len(firsts) > 30 and min(firsts) > 9.5 and max(firsts) < 20.5 and max(firsts) - min(firsts) > 5,
      "chorus depth 5 ms: tap delay sweeps %.1f..%.1f ms (base 15 +- 5)" % (min(firsts), max(firsts)))
e = fresh(wet=0, dry=1, chorus_mix=1, chorus_rate=2, chorus_depth=5)
y = e.run(sine(440, 0.1, 3.0))[SR // 2:, 0]
check(band_share(y, 440, 0.01) < 0.5, "chorus detunes a pure tone, spreading its energy (%.0f%% stays within 1%% of 440 Hz)" % (100 * band_share(y, 440, 0.01)))
e = fresh(wet=0, dry=1, chorus_mix=0, chorus_rate=2, chorus_depth=5)
y = e.run(sine(440, 0.1, 1.0))[SR // 2:, 0]
check(band_share(y, 440, 0.01) > 0.99 and tone_level(y, 440) > 0.099, "chorus amount 0 leaves the sound clean")
e = fresh(wet=0, dry=1, chorus_mix=1, chorus_on=0, chorus_depth=5)
y = e.run(sine(440, 0.1, 1.0))[SR // 2:, 0]
check(band_share(y, 440, 0.01) > 0.99, "chorus_on=0 bypasses even at amount 1")
e = fresh(wet=0, dry=1, chorus_mix=0.5, chorus_rate=1, chorus_depth=3)
y = e.run(sine(440, 0.1, 2.0))[SR // 2:, 0]
check(0.6 < rms(y) / (0.1 / np.sqrt(2)) < 1.05, "chorus keeps the level (ratio %.2f at amount 0.5)" % (rms(y) / (0.1 / np.sqrt(2))))
e = fresh(wet=0, dry=1, chorus_mix=0)
e.run(sine(440, 0.1, 0.3)); e.send("chorus_mix", 1)
yy = e.run(sine(440, 0.1, 0.5))[:, 0]
check(max_jump(yy) < 0.03, "turning the chorus up live: no click (max step %.4f)" % max_jump(yy))
e = fresh(wet=0, dry=1, chorus_mix=1, chorus_depth=8, chorus_rate=5, gain=10)
y = e.run((np.random.default_rng(8).standard_normal(SR * 5) * 0.5).astype(np.float32))
check(not np.isnan(y).any() and float(np.abs(y).max()) <= 1.0 + 1e-6, "loud noise through the widest, fastest chorus: no NaN, within +-1")
e = fresh(wet=0, chorus_mix=1, chorus_depth=8)
check(rms(e.run(e.silence(1.0))) < 1e-6, "chorus adds no noise on silent input")

# ---- 7h. level meter, noise gate, compressor ----
def db(x): return 20 * np.log10(x + 1e-12)

e = fresh(wet=0, dry=1)
e.listen("mic_level")
e.run(sine(440, 0.2, 2.0))
heard = e.heard["mic_level"]
want = 100 + db(0.2 / np.sqrt(2))
check(abs(np.mean(heard[-20:]) - want) < 1.0, "mic_level reports the loudness: %.1f (expected %.1f, 100 = full scale)" % (np.mean(heard[-20:]), want))
check(20 < len(heard) / 2.0 < 36, "mic_level is sent about 30 times a second (%.0f/s)" % (len(heard) / 2.0))
e.heard["mic_level"].clear(); e.run(e.silence(0.5))
check(np.mean(e.heard["mic_level"][-5:]) < 20, "mic_level falls to the floor in silence (%.0f)" % np.mean(e.heard["mic_level"][-5:]))

def steady(freq=440, amp=0.1, secs=1.5, **over):
    e = fresh(dry=1, wet=0, **over)
    return e.run(sine(freq, amp, secs))[SR // 2:, 0]
base_rms = rms(steady())
check(abs(db(rms(steady(gate_thresh=-80)) / base_rms)) < 0.1 and abs(db(rms(steady(comp_thresh=0, comp_makeup=0)) / base_rms)) < 0.1,
      "gate and compressor are transparent at their default settings")

check(rms(steady(amp=0.01, gate_thresh=-30)) < 0.02 * 0.01, "gate closes on a quiet sound (-37 dB under a -30 dB threshold)")
check(abs(db(rms(steady(amp=0.1, gate_thresh=-30)) / base_rms)) < 0.2, "gate stays open on a louder sound")
e = fresh(dry=1, wet=0, gate_thresh=-30)
e.run(sine(440, 0.002, 1.0))                      # quiet: gate closed
burst = e.run(sine(440, 0.2, 0.2))[:, 0]
first_loud = int(np.argmax(np.abs(burst) > 0.05))
check(first_loud / SR * 1000 < 25, "gate opens within %.0f ms of a loud sound" % (first_loud / SR * 1000))
tail = e.run(sine(440, 0.002, 1.0))[SR // 2:, 0]
check(rms(tail) < 0.02 * 0.002, "gate closes again afterwards")

# 0.5 amplitude sine = -9 dB RMS. Threshold -30, ratio 4: reduction = 0.75 * 21 = 15.75 dB
out = rms(steady(amp=0.5, comp_thresh=-30, comp_ratio=4)) / rms(steady(amp=0.5))
check(abs(db(out) + 15.75) < 1.5, "compressor: 21 dB over threshold at 4:1 lowers the level by %.1f dB (expected 15.75)" % -db(out))
out = rms(steady(amp=0.5, comp_thresh=-30, comp_ratio=4, comp_makeup=12)) / rms(steady(amp=0.5))
check(abs(db(out) + 3.75) < 1.5, "make-up gain adds back 12 dB (net %.1f dB)" % db(out))
out = rms(steady(amp=0.01, comp_thresh=-30, comp_ratio=4)) / rms(steady(amp=0.01))
check(abs(db(out)) < 0.5, "compressor leaves a sound under the threshold alone (%.2f dB)" % db(out))
loud, quiet = rms(steady(amp=0.5, comp_thresh=-40, comp_ratio=8, comp_makeup=10)), rms(steady(amp=0.02, comp_thresh=-40, comp_ratio=8, comp_makeup=10))
check(db(loud / quiet) < db(0.5 / 0.02) - 6, "compressor narrows the gap between loud and quiet (%.1f dB apart instead of %.1f)" % (db(loud / quiet), db(0.5 / 0.02)))
e = fresh(dry=1, wet=0, comp_thresh=-30, comp_ratio=20, comp_makeup=24, gate_thresh=-40, gain=10)
y = e.run((np.random.default_rng(9).standard_normal(SR * 5) * 0.3).astype(np.float32))
check(not np.isnan(y).any() and float(np.abs(y).max()) <= 1.0 + 1e-6, "extreme gate + compressor settings: no NaN, within +-1")
e = fresh(wet=0, comp_thresh=-50, comp_ratio=20, comp_makeup=24, gate_thresh=-20)
check(rms(e.run(e.silence(1.0))) < 1e-6, "gate and compressor add no noise on silent input")

# ---- 7h2. output limiter: app defaults with a moderate mic level must not fuzz ----
for amp in (0.05, 0.2, 0.4):
    e = fresh(gain=3, dry=1, wet=0.5, feedback=0.4)
    y = e.run(sine(440, amp, 2.0))[SR:, 0]
    clipped = float(np.mean(np.abs(y) > 0.99))
    thd = np.sqrt(max(rms(y) ** 2 - (tone_level(y, 440) / np.sqrt(2)) ** 2, 0)) / rms(y)
    print("      limiter amp %.2f: clipped %.1f%% non-fundamental %.0f%%" % (amp, clipped * 100, thd * 100))
    if amp <= 0.2:   # ordinary loud speech/music at the phone mic: should stay clean
        check(thd < 0.06, "input %.2f at default gain stays clean (%.0f%% non-fundamental)" % (amp, thd * 100))

# ---- 7i. distortion ----
SOFT, HARD, FOLD = 0, 1, 2
def dist_out(amp=0.1, secs=1.5, freq=440, **over):
    e = fresh(wet=0, dry=1, dist_mix=1, **over)
    return e.run(sine(freq, amp, secs))[SR // 2:, 0]
def harmonic(y, n=3, freq=440):
    return tone_level(y, freq * n) / max(tone_level(y, freq), 1e-9)

for kind, name in ((SOFT, "soft clip"), (HARD, "hard clip"), (FOLD, "wavefold")):
    g = db(rms(dist_out(amp=0.02, dist_type=kind, dist_drive=1)) / (0.02 / np.sqrt(2)))
    check(abs(g) < 1.0, "%s at drive 1 is close to clean (%.2f dB)" % (name, g))
yh = dist_out(dist_type=HARD, dist_drive=30)
check(0.9 < np.abs(yh).max() <= 1.0 and 0.25 < harmonic(yh) < 0.4, "hard clip at high drive is square-ish: peak %.2f, 3rd harmonic %.2f of fundamental (square = 0.33)" % (np.abs(yh).max(), harmonic(yh)))
ys = dist_out(dist_type=SOFT, dist_drive=30)
check(0.6 < np.abs(ys).max() < 0.9 and 0.02 < harmonic(ys) < 0.8 * harmonic(yh), "soft clip at high drive: peak %.2f, 3rd harmonic %.2f (gentler than hard clip's %.2f)" % (np.abs(ys).max(), harmonic(ys), harmonic(yh)))
yf = dist_out(dist_type=FOLD, dist_drive=8)
check(np.abs(yf).max() <= 0.64 and np.abs(yf).max() > 0.5 and rms(yf) > 0.3, "wavefold at drive 8: peak %.2f, rms %.2f (folds back instead of clipping)" % (np.abs(yf).max(), rms(yf)))
check(abs(float(np.mean(yh))) < 0.01 and abs(float(np.mean(yf))) < 0.01, "distortion adds no DC offset")
e = fresh(wet=0, dry=1, dist_mix=0, dist_drive=40, dist_type=HARD)
y = e.run(sine(440, 0.1, 1.0))[SR // 2:, 0]
check(band_share(y, 440, 0.01) > 0.99 and tone_level(y, 440) > 0.099, "distortion amount 0 leaves the sound clean")
e = fresh(wet=0, dry=1, dist_mix=1, dist_drive=40, dist_type=HARD, dist_on=0)
y = e.run(sine(440, 0.1, 1.0))[SR // 2:, 0]
check(band_share(y, 440, 0.01) > 0.99, "dist_on=0 bypasses even at amount 1")
e = fresh(wet=0, dry=1, dist_mix=0, dist_drive=4)
e.run(sine(440, 0.1, 0.3)); e.send("dist_mix", 1)
yy = e.run(sine(440, 0.1, 0.5))[:, 0]
check(max_jump(yy) < 0.03, "turning the distortion up live: no click (max step %.4f)" % max_jump(yy))
e = fresh(wet=0, dry=1, dist_mix=1, dist_drive=40, gain=10)
noise = (np.random.default_rng(10).standard_normal(SR * 3) * 0.3).astype(np.float32)
bad = False
for t in (0, 1, 2, 1, 0, 2):
    e.send("dist_type", t); y = e.run(noise[:SR // 2]); bad |= bool(np.isnan(y).any() or np.abs(y).max() > 1.0 + 1e-6)
check(not bad, "switching distortion type live at extreme settings: no NaN, within +-1")
e = fresh(wet=0, dist_mix=1, dist_drive=40, dist_type=FOLD)
check(rms(e.run(e.silence(1.0))) < 1e-6, "distortion adds no noise on silent input")

# ---- 7j. reverse echo ----
def rvs_only(x, **over):
    on = fresh(wet=0, dry=1, rvs_mix=1, **over).run(x)
    off = fresh(wet=0, dry=1, rvs_mix=0, **over).run(x)
    return (on - off)[:, 0]

white = (np.random.default_rng(11).standard_normal(SR * 3) * 0.1).astype(np.float32)
r = rvs_only(white, rvs_time=100)
check(0.5 < rms(r[SR:]) / rms(white) < 1.3, "reverse echo at level 1 is about as loud as the input (ratio %.2f)" % (rms(r[SR:]) / rms(white)))

def best_corr(seg, x_range, reverse):
    ref = seg[::-1] if reverse else seg
    num = np.correlate(x_range, ref, "valid")
    energy = np.sqrt(np.convolve(x_range ** 2, np.ones(len(ref)), "valid") * np.sum(ref ** 2))
    return float(np.max(np.abs(num) / (energy + 1e-12)))

C = 100
r = rvs_only(white, rvs_time=C)
n = int(0.03 * SR)
env = np.sqrt(np.convolve(r ** 2, np.ones(n) / n, "same"))
t0 = SR + int(np.argmax(env[SR:SR + int(0.2 * SR)])) - n // 2        # centre of a grain, where it is loudest
seg = r[t0:t0 + n]
lo = max(0, t0 - int(0.35 * SR))
x_range = white[lo:t0 + n]
c_rev, c_fwd = best_corr(seg, x_range, True), best_corr(seg, x_range, False)
check(c_rev > 0.85 and c_fwd < 0.4, "reverse echo plays the input backwards (match with reversed input %.2f, with forward input %.2f)" % (c_rev, c_fwd))

r0 = rvs_only(white, rvs_time=100, rvs_on=0)
check(rms(r0) < 1e-6, "rvs_on=0 bypasses even at level 1")
e = fresh(wet=0, dry=1, rvs_mix=0)
e.run(sine(440, 0.1, 0.3)); e.send("rvs_mix", 1)
yy = e.run(sine(440, 0.1, 0.5))[:, 0]
check(max_jump(yy) < 0.03, "turning the reverse echo up live: no click (max step %.4f)" % max_jump(yy))
for t in (100, 1000):
    e = fresh(wet=0, dry=1, rvs_mix=1, rvs_time=t, gain=10)
    y = e.run((np.random.default_rng(12).standard_normal(SR * 4) * 0.5).astype(np.float32))
    check(not np.isnan(y).any() and float(np.abs(y).max()) <= 1.0 + 1e-6, "loud noise through reverse echo (%d ms chunks): no NaN, within +-1" % t)
e = fresh(wet=0, rvs_mix=1, rvs_time=1000)
check(rms(e.run(e.silence(1.0))) < 1e-6, "reverse echo adds no noise on silent input")

# ---- 7k. glitch / freeze ----
def frozen(extra_secs=1.0, loop_ms=100, then=None):
    e = fresh(wet=0, dry=1, glitch_len=loop_ms)
    e.run(sine(440, 0.1, 1.0))
    e.send("glitch_hold", 1.0); e.run(e.silence(0.2))
    y = e.run(then if then is not None else e.silence(extra_secs))
    return e, y[:, 0]

e, y = frozen()
check(rms(y[SR // 2:]) > 0.05, "freeze keeps the last 100 ms looping after the sound stops (rms %.3f)" % rms(y[SR // 2:]))
lag = int(0.1 * SR)
tail = y[SR // 4:]
check(np.corrcoef(tail[:-lag], tail[lag:])[0, 1] > 0.99, "the frozen loop repeats every 100 ms (correlation %.3f)" % np.corrcoef(tail[:-lag], tail[lag:])[0, 1])
e1, y1 = frozen(then=np.zeros(SR, np.float32))
e2, y2 = frozen(then=(np.random.default_rng(13).standard_normal(SR) * 0.3).astype(np.float32))
check(np.allclose(y1[SR // 4:], y2[SR // 4:], atol=1e-4), "while frozen, new sound from the mic is ignored")
e.send("glitch_hold", 0.0); e.run(e.silence(0.3))
check(rms(e.run(e.silence(0.5))) < 1e-4, "releasing the freeze lets the loop go")
e = fresh(wet=0, dry=1, glitch_len=100)
e.run(sine(440, 0.1, 1.0)); e.send("glitch_hold", 0.5)
y = e.run(e.silence(3.0))[:, 0]
check(rms(y[-SR // 2:]) < 1e-3 and rms(y[:SR // 4]) > 0.02, "hold 0.5 gives repeats that die away (%.3f -> %.1e)" % (rms(y[:SR // 4]), rms(y[-SR // 2:])))
e = fresh(wet=0, dry=1, glitch_len=100, glitch_on=0)
e.run(sine(440, 0.1, 1.0)); e.send("glitch_hold", 1.0)
check(rms(e.run(e.silence(1.0))[SR // 10:]) < 1e-4, "glitch_on=0 bypasses even at hold 1")
e = fresh(wet=0, dry=1, glitch_len=100)
e.run(sine(440, 0.1, 0.5)); e.send("glitch_hold", 1.0)
yy = e.run(sine(440, 0.1, 0.5))[:, 0]
check(max_jump(yy) < 0.03, "engaging the freeze on a steady tone: no click (max step %.4f)" % max_jump(yy))
e = fresh(wet=0, dry=1, glitch_len=500, gain=10)
e.run((np.random.default_rng(14).standard_normal(SR * 2) * 0.5).astype(np.float32)); e.send("glitch_hold", 1.0)
y = e.run(e.silence(30))
check(not np.isnan(y).any() and float(np.abs(y).max()) <= 1.0 + 1e-6 and abs(rms(y[:SR]) - rms(y[-SR:])) < 0.01, "a frozen loud loop stays stable for 30 s (rms %.3f -> %.3f)" % (rms(y[:SR]), rms(y[-SR:])))
e = fresh(wet=0, glitch_hold=0)
check(rms(e.run(e.silence(1.0))) < 1e-6, "glitch/freeze adds no noise on silent input")

# ---- 7l. flanger and phaser ----
def response(x_noise, y):
    """Magnitude of y/x in dB per FFT bin (cross-spectrum average, smoothed over ~100 Hz)."""
    n = 4096
    num = np.zeros(n // 2 + 1, complex); den = np.zeros(n // 2 + 1)
    win = np.hanning(n)
    for i in range(0, len(x_noise) - n, n // 2):
        X = np.fft.rfft(x_noise[i:i + n] * win); Y = np.fft.rfft(y[i:i + n] * win)
        num += Y * np.conj(X); den += np.abs(X) ** 2
    h = np.abs(num / (den + 1e-12))
    f = np.fft.rfftfreq(n, 1 / SR)
    return f, 20 * np.log10(h + 1e-9)

white2 = (np.random.default_rng(21).standard_normal(SR * 2) * 0.1).astype(np.float32)
def through(**over):
    e = fresh(wet=0, dry=1, **over)
    return e.run(white2)[:, 0]

def comb_depth(y, lo=300, hi=6000):
    f, h = response(white2[SR // 2:SR // 2 + 8192 * 2], y[SR // 2:SR // 2 + 8192 * 2])
    band = h[(f > lo) & (f < hi)]
    return float(band.max() - band.min())

# flanger
for fb in (0.0, 0.8):
    yf = through(flange_mix=1, flange_rate=0.05, flange_depth=4, flange_fb=fb)
    check(comb_depth(yf) > 10, "flanger (feedback %.1f) carves a comb into the spectrum: peaks to notches %.0f dB apart" % (fb, comb_depth(yf)))
yf0 = through(flange_mix=0, flange_rate=1, flange_depth=8, flange_fb=0.9)
check(comb_depth(yf0) < 2.0, "flanger amount 0 leaves the spectrum flat (%.1f dB)" % comb_depth(yf0))
yfo = through(flange_mix=1, flange_on=0, flange_rate=1, flange_depth=8, flange_fb=0.9)
check(comb_depth(yfo) < 2.0, "flange_on=0 bypasses even at amount 1")
yn = through(flange_mix=1, flange_fb=-0.8, flange_depth=3)
check(comb_depth(yn) > 15, "negative feedback also combs (%.0f dB)" % comb_depth(yn))

def flange_tap_delays(depth, impulses=40):
    out = []
    e = fresh(wet=0, dry=1, flange_mix=1, flange_fb=0, flange_depth=depth, flange_rate=3)
    for i in range(impulses):
        x = np.zeros(int(0.0113 * SR) * 10, np.float32); x[100] = 0.4
        y = e.run(x)[:, 0]
        z = np.abs(y)
        wet_idx = [k for k in np.where(z > 0.05)[0] if k > 100 + 0.9 * 0.0015 * SR + 24]
        if wet_idx:
            out.append((wet_idx[0] + np.argmax(z[wet_idx[0]:wet_idx[0] + 40]) - 100) / SR * 1000 - 1.5)
    return out
d = flange_tap_delays(6)
check(len(d) > 25 and min(d) > 1.8 and max(d) < 8.4 and max(d) - min(d) > 2.5, "flanger delay sweeps %.1f..%.1f ms (2 ms + up to depth 6)" % (min(d), max(d)))
ys = through(flange_mix=0.5, flange_fb=0.5, flange_depth=4)
check(0.5 < rms(ys[SR // 2:]) / rms(white2) < 1.5, "flanger keeps the level (ratio %.2f)" % (rms(ys[SR // 2:]) / rms(white2)))
e = fresh(wet=0, dry=1, flange_mix=0)
e.run(sine(440, 0.1, 0.3)); e.send("flange_mix", 1)
yy = e.run(sine(440, 0.1, 0.5))[:, 0]
check(max_jump(yy) < 0.03, "turning the flanger up live: no click (max step %.4f)" % max_jump(yy))
for fb in (0.9, -0.9):
    e = fresh(wet=0, dry=1, flange_mix=1, flange_fb=fb, flange_depth=8, flange_rate=5, gain=10)
    y = e.run((np.random.default_rng(22).standard_normal(SR * 5) * 0.5).astype(np.float32))
    check(not np.isnan(y).any() and float(np.abs(y).max()) <= 1.0 + 1e-6, "loud noise through the flanger at feedback %+.1f: no NaN, within +-1" % fb)
e = fresh(wet=0, flange_mix=1, flange_fb=0.9)
check(rms(e.run(e.silence(1.0))[SR // 10:]) < 1e-6, "flanger adds no noise on silent input")

# phaser
yp = through(phaser_mix=1, phaser_rate=0.05, phaser_depth=0, phaser_fb=0)
f, h = response(white2[SR // 2:SR // 2 + 8192 * 2], yp[SR // 2:SR // 2 + 8192 * 2])
low = float(np.mean(h[(f > 40) & (f < 120)]))
check(abs(low) - 6.0 < 0 and comb_depth(yp, 200, 8000) > 8, "phaser carves notches into the spectrum (%.0f dB peak to notch); lows near %.1f dB (50/50 mix)" % (comb_depth(yp, 200, 8000), low))
yp0 = through(phaser_mix=0, phaser_rate=1, phaser_depth=1, phaser_fb=0.9)
check(comb_depth(yp0, 200, 8000) < 2.0, "phaser amount 0 leaves the spectrum flat (%.1f dB)" % comb_depth(yp0, 200, 8000))
ypo = through(phaser_mix=1, phaser_on=0, phaser_rate=1, phaser_depth=1, phaser_fb=0.9)
check(comb_depth(ypo, 200, 8000) < 2.0, "phaser_on=0 bypasses even at amount 1")

def notch_freq(y, start):
    f, h = response(white2[start:start + 8192], y[start:start + 8192])
    band = (f > 200) & (f < 6000)
    return float(f[band][np.argmin(h[band])])
yp = through(phaser_mix=1, phaser_rate=2, phaser_depth=1, phaser_fb=0.3)
notches = [notch_freq(yp, SR // 4 + k * 6000) for k in range(8)]
check(max(notches) / min(notches) > 1.5, "the phaser's deepest notch sweeps: %s Hz" % ", ".join("%d" % v for v in notches))
yq = through(phaser_mix=1, phaser_rate=0.05, phaser_depth=0.5, phaser_fb=0.8)
ya = through(phaser_mix=1, phaser_rate=0.05, phaser_depth=0.5, phaser_fb=0.0)
def peak_db(y):
    f, h = response(white2[SR // 2:SR // 2 + 8192 * 2], y[SR // 2:SR // 2 + 8192 * 2])
    return float(h[(f > 200) & (f < 8000)].max())
check(peak_db(yq) > peak_db(ya) + 1.0, "feedback sharpens the phaser's peaks (%.1f dB vs %.1f dB without)" % (peak_db(yq), peak_db(ya)))
ys = through(phaser_mix=1, phaser_fb=0.5)
check(0.5 < rms(ys[SR // 2:]) / rms(white2) < 1.6, "phaser keeps the level (ratio %.2f)" % (rms(ys[SR // 2:]) / rms(white2)))
e = fresh(wet=0, dry=1, phaser_mix=0)
e.run(sine(440, 0.1, 0.3)); e.send("phaser_mix", 1)
yy = e.run(sine(440, 0.1, 0.5))[:, 0]
check(max_jump(yy) < 0.03, "turning the phaser up live: no click (max step %.4f)" % max_jump(yy))
e = fresh(wet=0, dry=1, phaser_mix=1, phaser_fb=0.9, phaser_depth=1, phaser_rate=5, gain=10)
y = e.run((np.random.default_rng(23).standard_normal(SR * 5) * 0.5).astype(np.float32))
check(not np.isnan(y).any() and float(np.abs(y).max()) <= 1.0 + 1e-6, "loud noise through the strongest phaser: no NaN, within +-1")
e = fresh(wet=0, phaser_mix=1, phaser_fb=0.9)
check(rms(e.run(e.silence(1.0))[SR // 10:]) < 1e-6, "phaser adds no noise on silent input")

# ---- 9. walking beat: footsteps play drums ----
def beat_run(steps, secs=2.0, **over):
    """steps = [(time_s, interval_s)]; returns the left channel after sending [step( at those times."""
    e = fresh(wet=0, dry=0, **over)
    out, t = [], 0.0
    for when, interval in steps:
        out.append(e.run(e.silence(when - t))[:, 0]); t = when
        e.send("step", interval)
    out.append(e.run(e.silence(secs - t))[:, 0])
    return np.concatenate(out)

def seg(y, a, b): return y[int(a * SR):int(b * SR)]
def hf_rms(y, lo=6000):
    spec = np.fft.rfft(y * np.hanning(len(y)))
    f = np.fft.rfftfreq(len(y), 1 / SR)
    return float(np.sqrt(np.sum(np.abs(spec[f > lo]) ** 2))) / len(y)
def centroid_hz(y):
    spec = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    f = np.fft.rfftfreq(len(y), 1 / SR)
    return float(np.sum(f * spec) / (np.sum(spec) + 1e-12))

check(rms(beat_run([], beat_level=1)) < 1e-6, "beat: no steps, no sound (even at level 1)")
check(rms(beat_run([(0.1, 0.5)], beat_level=0)) < 1e-6, "beat: level 0 is silent")
check(rms(beat_run([(0.1, 0.5)], beat_level=1, beat_on=0)) < 1e-6, "beat: switch off is silent")
y1 = beat_run([(0.1, 0.5)], beat_level=1, beat_hats=0, beat_snare=0)
check(rms(seg(y1, 0.1, 0.4)) > 0.02, "beat: a step plays a kick (rms %.3f)" % rms(seg(y1, 0.1, 0.4)))
check(centroid_hz(seg(y1, 0.1, 0.4)) < 300, "beat: the kick is low (centroid %d Hz)" % centroid_hz(seg(y1, 0.1, 0.4)))
check(rms(seg(y1, 0.6, 2.0)) < 0.002, "beat: the kick dies away (rms after 0.5 s %.4f)" % rms(seg(y1, 0.6, 2.0)))
yhi = beat_run([(0.1, 0.5)], beat_level=1, beat_hats=0, beat_snare=0, beat_pitch=100)
ylo = beat_run([(0.1, 0.5)], beat_level=1, beat_hats=0, beat_snare=0, beat_pitch=45)
check(centroid_hz(seg(yhi, 0.1, 0.4)) > centroid_hz(seg(ylo, 0.1, 0.4)) + 15, "beat: the pitch setting moves the kick")
# second step is a snare: noisy, so brighter and not just a low thump
y2 = beat_run([(0.1, 0.5), (0.6, 0.5)], beat_level=1, beat_hats=0)
check(centroid_hz(seg(y2, 0.6, 0.75)) > 3 * centroid_hz(seg(y2, 0.1, 0.25)), "beat: the second step is a snare (centroid %d Hz vs kick %d Hz)"
      % (centroid_hz(seg(y2, 0.6, 0.75)), centroid_hz(seg(y2, 0.1, 0.25))))
y3 = beat_run([(0.1, 0.5), (0.6, 0.5)], beat_level=1, beat_hats=0, beat_snare=0)
check(rms(seg(y3, 0.62, 0.9)) < 0.002, "beat: snare level 0 silences the snare")
y4 = beat_run([(0.1, 0.5), (0.6, 0.5), (1.1, 0.5)], beat_level=1, beat_hats=0)
check(rms(seg(y4, 1.1, 1.4)) > 0.02 and centroid_hz(seg(y4, 1.1, 1.25)) < 300, "beat: the third step is a kick again")
# hi-hat half a step after the step
yh = beat_run([(0.1, 0.8)], secs=1.5, beat_level=1, beat_hats=1, beat_snare=0)
hat_at = seg(yh, 0.1 + 0.4, 0.1 + 0.4 + 0.06)
quiet_at = seg(yh, 0.1 + 0.2, 0.1 + 0.26)
check(hf_rms(hat_at) > 10 * hf_rms(quiet_at) and hf_rms(hat_at) > 1e-4, "beat: the hi-hat lands half a step (0.4 s) after the step")
yh2 = beat_run([(0.1, 0.4)], secs=1.5, beat_level=1, beat_hats=1, beat_snare=0)
check(hf_rms(seg(yh2, 0.1 + 0.2, 0.1 + 0.26)) > 10 * hf_rms(seg(yh2, 0.1 + 0.4, 0.1 + 0.46)) , "beat: a faster walk moves the hi-hat earlier (0.2 s)")
yh0 = beat_run([(0.1, 0.8)], secs=1.5, beat_level=1, beat_hats=0, beat_snare=0)
check(hf_rms(seg(yh0, 0.5, 0.56)) < 1e-4, "beat: hi-hat level 0 is silent")
# level scales the drums
ya = beat_run([(0.1, 0.5)], beat_level=1, beat_hats=0, beat_snare=0)
yb = beat_run([(0.1, 0.5)], beat_level=0.5, beat_hats=0, beat_snare=0)
check(0.4 < rms(seg(yb, 0.1, 0.4)) / rms(seg(ya, 0.1, 0.4)) < 0.6, "beat: level 0.5 is about half as loud")
# silly intervals are tamed; fast stomping never clips
steps = [(0.1 + 0.15 * i, 0.05 if i % 2 else 9.0) for i in range(40)]
yw = beat_run(steps, secs=7.0, beat_level=1, beat_hats=1, beat_snare=1)
check(not np.isnan(yw).any() and float(np.abs(yw).max()) <= 1.0 + 1e-6, "beat: a flood of odd steps stays within +-1 (max %.2f)" % float(np.abs(yw).max()))
e = fresh(wet=0, dry=0, beat_level=1); e.send("step", 0.5); yy = e.run(e.silence(0.5))
check(float(np.max(np.abs(yy[:, 0] - yy[:, 1]))) < 1e-6, "beat: centred (same in both ears)")
# the beat goes through the reverb and the user's dry level is not needed
e = fresh(wet=0, dry=0, beat_level=1, reverb_mix=1, reverb_size=0.9); e.send("step", 0.5); yr = e.run(e.silence(2.0))[:, 0]
check(rms(seg(yr, 1.0, 2.0)) > 5 * rms(seg(y1, 1.0, 2.0)) + 1e-5, "beat: the reverb tails the drums")

# ---- 10. music: a reactive synth that only plays notes of the chosen key and scale ----
SCALE_STEPS = [(0, 2, 4, 5, 7, 9, 11), (0, 2, 3, 5, 7, 8, 10), (0, 2, 4, 7, 9), (0, 3, 5, 7, 10),
               (0, 2, 3, 5, 7, 9, 10), (0, 2, 4, 5, 7, 9, 10), (0, 2, 4, 6, 7, 9, 11), (0, 2, 4, 6, 8, 10)]
def spec_peaks(y, rel=0.1):
    """Frequencies (Hz) of the spectral peaks within `rel` of the strongest one."""
    w = np.hanning(len(y)); S = np.abs(np.fft.rfft(y * w)); f = np.fft.rfftfreq(len(y), 1 / SR)
    return [float(f[i]) for i in range(2, len(S) - 1)
            if S[i] > rel * S.max() and S[i] >= S[i - 1] and S[i] >= S[i + 1] and f[i] > 60]
def off_key(freqs, key, scale):
    """Peaks that are not within 0.25 semitone of a note of the scale."""
    bad = []
    for f in freqs:
        pc = (69 + 12 * np.log2(f / 440) - key) % 12
        if min(min(abs(pc - n), 12 - abs(pc - n)) for n in SCALE_STEPS[scale]) > 0.25:
            bad.append(round(f, 1))
    return bad

e = fresh(music_on=0, music_pad=1, music_arp=1, wet=0)
check(rms(e.run(e.silence(3))) < 1e-6, "music: silent while switched off, even with the levels up")

for key, scale, name in ((0, 0, "C major"), (2, 1, "D minor"), (9, 3, "A minor pentatonic"), (7, 4, "G dorian"), (5, 7, "F whole tone")):
    e = fresh(music_on=1, music_pad=1, music_arp=0, music_key=key, music_scale=scale, wet=0, music_pad_reg=1)
    y = e.run(e.silence(6.5))[:, 0]     # before the first chord change at 7 s, when the notes glide
    pk = spec_peaks(y[SR * 2:])
    check(rms(y[SR * 2:]) > 0.01 and len(pk) >= 3 and not off_key(pk, key, scale),
          "music: the pad plays only notes of %s (peaks %s, off-key %s)" % (name, [round(f) for f in pk[:8]], off_key(pk, key, scale)))

# pad register: Low is a bass voice on a scale note between 65 and 131 Hz, Mid the chords as before, Both the two
def pad_reg(reg, secs=6.5, **over):
    e = fresh(**dict(dict(music_on=1, music_pad=1, music_arp=0, music_res=0, wet=0, music_pad_reg=reg), **over))
    return e, e.run(e.silence(secs))[:, 0]
def band(y, lo, hi):
    S = np.fft.rfft(y); f = np.fft.rfftfreq(len(y), 1 / SR); S[(f < lo) | (f >= hi)] = 0
    return rms(np.fft.irfft(S, len(y)))
for key, scale, name in ((0, 0, "C major"), (11, 1, "B minor"), (5, 7, "F whole tone")):
    _, y = pad_reg(0, music_key=key, music_scale=scale)
    tail = y[SR * 3:]
    f0 = [f for f in spec_peaks(tail, 0.3) if f < 140]
    check(len(f0) >= 1 and all(64 <= f <= 132 for f in f0) and not off_key(f0, key, scale) and band(tail, 0, 140) > 2 * band(tail, 400, 20000),
          "pad register low: a bass note of %s at %s Hz, little above it" % (name, [round(f) for f in f0]))
_, ymid = pad_reg(1)
check(band(ymid[SR * 3:], 0, 120) < 0.05 * rms(ymid[SR * 3:]), "pad register mid: no bass (%.5f of %.4f)" % (band(ymid[SR * 3:], 0, 120), rms(ymid[SR * 3:])))
_, yboth = pad_reg(2)
check(band(yboth[SR * 3:], 0, 140) > 0.2 * rms(yboth[SR * 3:]) and band(yboth[SR * 3:], 140, 2000) > 0.2 * rms(yboth[SR * 3:]),
      "pad register both: bass and chords together")
def after_step(beat_level):
    e, y = pad_reg(0, secs=5.0, beat_level=beat_level, beat_hats=0, beat_snare=0)   # well before the chord change at 7 s
    f0 = min((f for f in spec_peaks(y[SR * 3:], 0.3) if f < 140), default=65.4)   # the fundamental
    e.send("step", 0.5); z = e.run(e.silence(0.12))[:, 0]
    return tone_level(z[int(0.03 * SR):int(0.11 * SR)], f0), tone_level(y[-int(0.08 * SR):], f0)
ducked, steady = after_step(0.05)
undisturbed, steady0 = after_step(0)
check(ducked < 0.7 * steady and undisturbed > 0.9 * steady0,
      "pad register low: a footstep ducks the bass while the beat plays (%.4f vs %.4f), not when it is off (%.4f vs %.4f)" % (ducked, steady, undisturbed, steady0))
e = fresh(music_on=1, music_pad=1, music_arp=1, music_res=1, wet=1, reverb_mix=1, music_pad_reg=2, beat_level=1, gain=10)
rng = np.random.default_rng(4); ys = []
for _ in range(20):
    e.send("step", 0.4); ys.append(e.run((rng.standard_normal(int(0.4 * SR)) * 0.3).astype(np.float32)))
ym = np.concatenate(ys)
check(float(np.abs(ym).max()) <= 1.0 + 1e-6, "pad register both, everything loud: stays within +-1 (max %.2f)" % float(np.abs(ym).max()))
e = fresh(music_on=1, music_pad=1, music_arp=0, wet=0)
e.send("music_key", 1); y = e.run(e.silence(6.0))[:, 0]   # the crossfade to the new key takes 3.5 s
pk = spec_peaks(y[SR * 4:])
check(len(pk) >= 3 and not off_key(pk, 1, 0) and off_key(pk, 0, 0) != [], "music: changing the key moves the pad to C# major (peaks %s)" % [round(f) for f in pk[:8]])

# the pad listens: a high-pitched room picks higher chords than a low-pitched one (the chord choices are announced on pad_chord)
def pad_choices(tone_hz, secs=60, **over):
    e = fresh(**dict(dict(music_on=0, music_pad=1, music_arp=0, music_res=0, wet=0), **over)); e.listen("pad_chord")
    e.run(sine(tone_hz, 0.1, 1.5)); e.send("music_on", 1)
    e.run(sine(tone_hz, 0.1, secs))
    return e.heard.get("pad_chord", [])
low, high = pad_choices(200), pad_choices(3000)
lo_main, hi_main = [c for c in low if c != 5], [c for c in high if c != 5]      # 5 = Am, C major's contrast chord
check(len(low) >= 6 and lo_main and hi_main and np.mean(lo_main) + 1.5 < np.mean(hi_main),
      "music: the chord follows the brightness of the room (low sound %s, high sound %s)" % (low, high))
# pad chords per scale: home chord, its two neighbours, and now and then one contrast chord. Never a diminished chord.
POOLS = {0: ({0, 3, 4}, 5), 1: ({0, 3, 4}, 2), 2: ({0, 1, 2, 3, 4}, None), 4: ({0, 3, 4}, 6), 5: ({0, 3, 6}, 4), 6: ({0, 1, 4}, 5)}
NAMES = {0: "major", 1: "minor", 2: "major pentatonic", 4: "dorian", 5: "mixolydian", 6: "lydian"}
for scale, (pool, contrast) in POOLS.items():
    picks = pad_choices(200, 40, music_scale=scale) + pad_choices(3000, 40, music_scale=scale) + pad_choices(800, 60, music_scale=scale)
    allowed = pool | ({contrast} if contrast is not None else set())
    n_con = sum(1 for c in picks if c == contrast)
    ok = set(picks) <= allowed and (contrast is None or 0 < n_con <= 0.45 * len(picks))
    check(ok, "music: %s pad uses only its chords %s%s (picked %s)" % (NAMES[scale], sorted(pool), "" if contrast is None else " + contrast %d" % contrast, picks))
# chord changes crossfade: no pitch slides through notes outside the key while the chord changes
e = fresh(music_on=1, music_pad=1, music_arp=0, music_res=0, wet=0); e.listen("pad_chord")
y = e.run(sine(3000, 0.05, 40))[:, 0]
changes = e.heard.get("pad_chord", [])
bad = []
for a in range(6, 38, 2):
    seg = y[a * SR:(a + 2) * SR]
    seg = np.fft.irfft(np.where(np.fft.rfftfreq(len(seg), 1 / SR) > 2500, 0, np.fft.rfft(seg)), len(seg))   # drop the input tone
    bad += off_key(spec_peaks(seg, rel=0.15), 0, 0)
check(len(set(changes)) >= 2 and not bad, "music: chord changes crossfade without sliding out of key (chords %s, off-key %s)" % (changes, sorted(set(bad))[:6]))

# a sudden sound makes a chime in the key, then it fades
e = fresh(music_on=1, music_pad=0, music_arp=1, wet=0)
e.run(e.silence(4))
rng = np.random.default_rng(3)
burst = (rng.standard_normal(int(0.15 * SR)) * 0.3).astype(np.float32)
y = e.run(np.concatenate([burst, np.zeros(SR * 3, np.float32)]))[:, 0]
after = y[int(0.45 * SR):int(1.5 * SR)]
check(rms(after) > 1e-3 and not off_key(spec_peaks(after), 0, 0),
      "music: a sudden sound rings a chime in the key (rms %.4f, off-key %s)" % (rms(after), off_key(spec_peaks(after), 0, 0)))
e = fresh(music_on=1, music_pad=0, music_arp=1, wet=0, music_react=0.6)
quiet_after = e.run(np.concatenate([np.zeros(SR * 4, np.float32), np.zeros(SR * 3, np.float32)]))[:, 0]
check(rms(quiet_after[int(4.45 * SR):int(5.5 * SR)]) < rms(after), "music: no chime without a sudden sound at that moment")

# the notes follow the room: nothing in a quiet room, busy in a loud one, and react = 0 means a steady sparse pattern
def band_rms(y, lo=150):
    S = np.fft.rfft(y); f = np.fft.rfftfreq(len(y), 1 / SR); S[f < lo] = 0
    return rms(np.fft.irfft(S, len(y)))
def room(amp, secs, windows=False, **over):
    e = fresh(music_on=1, music_pad=0, music_arp=1, wet=0, gain=1, **over)
    y = e.run(sine(50, amp, secs))[:, 0]
    return [band_rms(y[a * SR:(a + 5) * SR]) for a in range(0, secs, 5)] if windows else band_rms(y)
# with react below 1 a quiet room keeps a tiny chime chance (eff^3 at eff 0.08: about one every 3 minutes), so allow
# two stray chimes in 40 s (Pd's [random] seeds shift whenever objects are added; 2 happens ~2% of the time, 3 ~0.1%)
qw = room(0.001, 40, windows=True); quiet = float(np.median(qw))
check(quiet < 0.0005 and sum(w > 0.002 for w in qw) <= 2, "music: a quiet room plays no notes (5 s windows %s)" % ["%.4f" % w for w in qw])
lively = room(0.3, 40)
check(lively > 10 * quiet + 0.002, "music: a loud room plays plenty of notes (%.4f vs %.5f)" % (lively, quiet))
steady_q, steady_l = room(0.001, 40, music_react=0), room(0.3, 40, music_react=0)
check(0.2 < (steady_l + 1e-9) / (steady_q + 1e-9) < 5, "music: react = 0 ignores the room (quiet %.4f, loud %.4f)" % (steady_q, steady_l))

# footsteps play an arpeggio that is louder at a brisk pace than at a stroll, and always in key
def walk(interval, n=10, **over):
    e = fresh(music_on=1, music_pad=0, music_arp=1, wet=0, **over)
    ys = []
    for _ in range(n):
        e.send("step", interval); ys.append(e.run(e.silence(interval))[:, 0])
    return np.concatenate(ys)
stroll, brisk = walk(1.0), walk(0.38, n=26)
check(rms(brisk[-SR * 3:]) > 2.0 * rms(stroll[-SR * 3:]) > 1e-4,
      "music: the arpeggio swells with pace (stroll %.4f, brisk %.4f)" % (rms(stroll[-SR * 3:]), rms(brisk[-SR * 3:])))
check(not off_key(spec_peaks(brisk[-SR * 3:]), 0, 0), "music: the walking arpeggio stays in the key (off-key %s)" % off_key(spec_peaks(brisk[-SR * 3:]), 0, 0))
e = fresh(music_on=0, music_pad=1, music_arp=1, wet=0)
e.send("step", 0.5)
check(rms(e.run(e.silence(1.0))) < 1e-6, "music: footsteps are silent while the music is off")

# variety: chimes walk a melody (no note twice in a row) and footsteps switch between arpeggio patterns, with rests
e = fresh(music_on=1, music_pad=0, music_arp=1, wet=0, gain=1); e.listen("chime_deg")
e.run(sine(50, 0.3, 40))
cd = [int(v) for v in e.heard["chime_deg"]]
rep = sum(a == b for a, b in zip(cd, cd[1:]))
check(len(cd) >= 10 and len(set(cd)) >= 5 and rep == 0,
      "music: chimes wander through %d different notes, none twice in a row (%d notes, %d repeats)" % (len(set(cd)), len(cd), rep))
e = fresh(music_on=1, music_pad=0, music_arp=1, wet=0); e.listen("chime_deg")
for _ in range(64):
    e.send("step", 0.4); e.run(e.silence(0.4))
ad = [int(v) for v in e.heard["chime_deg"]]
bars = {tuple(ad[i:i + 6]) for i in range(0, len(ad) - 6, 3)}
check(40 <= len(ad) < 64 and len(bars) >= 6,
      "music: 64 footsteps play %d notes (some rest) in %d different phrases" % (len(ad), len(bars)))

# walking locks the chimes to the footsteps: a sudden sound waits for the next step or half-step
def note_times(e, mic, chunk=64):
    """Run `mic` in small chunks and return the time (s) of each note sent to chime_deg."""
    t = []
    for i in range(0, len(mic), chunk):
        n = len(e.heard["chime_deg"])
        e.run(mic[i:i + chunk])
        t += [(i + chunk) / SR] * (len(e.heard["chime_deg"]) - n)
    return t
def clap_at(total, at, seed=5):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(int(total * SR)) * 0.0005
    if at is None:
        return x.astype(np.float32)
    k = np.arange(int(0.03 * SR)); a = int(at * SR)
    x[a:a + len(k)] += rng.standard_normal(len(k)) * 0.5 * np.exp(-k / (0.008 * SR))
    return x.astype(np.float32)
e = fresh(music_on=1, music_pad=0, music_arp=1, wet=0, gain=1); e.listen("chime_deg")
e.run(clap_at(3.0, None))                       # settle the room floor
still = note_times(e, clap_at(1.0, 0.3))
e = fresh(music_on=1, music_pad=0, music_arp=1, wet=0, gain=1); e.listen("chime_deg")
e.run(clap_at(3.0, None))
walk_t = []
claps = {5: 0.08, 8: 0.35}                              # steps every 0.5 s; claps just after step 5 and late in step 8
for k in range(10):
    n = len(e.heard["chime_deg"]); e.send("step", 0.5)
    walk_t += [k * 0.5] * (len(e.heard["chime_deg"]) - n)
    walk_t += [k * 0.5 + t for t in note_times(e, clap_at(0.5, claps.get(k), seed=k))]
off = [round((t % 0.5) / 0.5 * 2) % 2 if min(t % 0.5, 0.5 - t % 0.5, abs(t % 0.5 - 0.25)) < 0.006 else None for t in walk_t]
check(still and 0.3 < still[0] < 0.36,
      "music: standing still, a clap's chime plays at once (%.0f ms after)" % ((still[0] - 0.3) * 1000 if still else -1))
check(None not in off and any(abs(t - 2.75) < 0.006 for t in walk_t) and 4.5 in walk_t and not any(4.35 < t < 4.5 for t in walk_t),
      "music: walking, chimes fall on steps or half-steps (%d notes; clap at 2.58 s chimed at %s, clap at 4.35 s waited for the 4.5 s step)"
      % (len(walk_t), [round(t, 3) for t in walk_t if 2.5 < t < 3.0]))

# echo follows the steps while walking: half a step at 0.5 s steps = 250 ms; the slider's 350 ms otherwise
def echo_delay(sync, walk, after=0.0):
    e = fresh(echo_time=350, feedback=0, wet=1, dry=0, echo_sync=sync, beat_level=0)
    if walk:
        for _ in range(6):
            e.send("step", 0.5); e.run(e.silence(0.5))
    e.run(e.silence(after + 0.6))   # let the echo time glide there
    x = np.zeros(SR, np.float32); x[0] = 0.5
    y = np.abs(e.run(x)[:, 0])
    return 1000 * int(np.argmax(y)) / SR
d_half, d_quarter, d_off, d_still, d_after = (echo_delay(2, True), echo_delay(3, True), echo_delay(0, True),
                                              echo_delay(2, False), echo_delay(2, True, after=3.0))
check(abs(d_half - 250) < 6 and abs(d_quarter - 125) < 6 and abs(d_off - 350) < 6 and abs(d_still - 350) < 6
      and abs(d_after - 350) < 6,
      "echo follows the steps: half %.0f ms, quarter %.0f, off %.0f, standing %.0f, 3 s after stopping %.0f"
      % (d_half, d_quarter, d_off, d_still, d_after))

# stopping after a walk: the pad and bass take a breath (a few dB down within ~3 s), then drift back to full.
# Measured on the bass alone (a steady level); its own short dips at note changes are why we look at ranges.
e = fresh(music_on=1, music_pad=0.5, music_arp=0, music_res=0, wet=0, beat_level=0, music_pad_reg=0)
e.run(e.silence(3.0)); before = rms(e.run(e.silence(1.0))[:, 0])
for _ in range(8):
    e.send("step", 0.5); e.run(e.silence(0.5))
lv = [rms(e.run(e.silence(0.5))[:, 0]) for _ in range(28)]   # half-second windows after the last step
db = lambda a: 20 * np.log10(a / before)
walking, dipped, back = db(lv[1]), min(db(v) for v in lv[4:9]), db(np.mean(lv[23:28]))
check(abs(walking) < 1.5 and -6.5 < dipped < -2.5 and abs(back) < 1.5,
      "music: stopping after a walk, the pad breathes %.1f dB down and comes back (%.1f dB at 12-14 s; 1 s after %.1f dB)"
      % (dipped, back, walking))

# pace tiers: a stroll plays the calm patterns and rests more; a brisk walk plays the busy, leaping ones
def arp_run(interval, n=64):
    e = fresh(music_on=1, music_pad=0, music_arp=1, wet=0); e.listen("chime_deg")
    per_step = []                                              # the note each step played, None for a rest
    for _ in range(n):
        k = len(e.heard["chime_deg"])
        e.send("step", interval); e.run(e.silence(interval))
        new = e.heard["chime_deg"][k:]
        per_step.append(int(new[0]) if new else None)
    jumps = [abs(b - a) for a, b in zip(per_step, per_step[1:]) if a is not None and b is not None]
    return sum(v is not None for v in per_step) / n, float(np.mean(jumps))
stroll_rate, stroll_jump = arp_run(1.0)
brisk_rate, brisk_jump = arp_run(0.38)
check(brisk_jump > 1.15 * stroll_jump and brisk_rate > stroll_rate + 0.1,   # chord changes blur the jump measure
      "music: pace tiers: strolling moves %.1f steps a note and plays %.0f%% of steps, brisk %.1f and %.0f%%"
      % (stroll_jump, 100 * stroll_rate, brisk_jump, 100 * brisk_rate))

# step strength: a hard step opens the hi-hat (louder, longer); a soft one leaves it faint
def hat_energy(strength):
    e = fresh(beat_level=1, beat_hats=1, beat_snare=0, wet=0, dry=0)
    for _ in range(4):
        e.send("step_strength", strength); e.send("step", 0.5); y = e.run(e.silence(0.5))[:, 0]
    seg = y[int(0.24 * SR):int(0.45 * SR)]                    # the hat half a step after the last step
    return rms(np.diff(seg))                                   # high frequencies: the hat, not the kick
hard, usual, soft = hat_energy(1.0), hat_energy(0.5), hat_energy(0.1)
check(hard > 1.8 * usual and usual > 1.8 * soft,
      "beat: step strength opens the hi-hat (hard %.4f, usual %.4f, soft %.4f)" % (hard, usual, soft))

# the landing of the step itself (step_hit, sent once its bump is over) sets the hat that follows it
def hat_after_hit(hit):
    e = fresh(beat_level=1, beat_hats=1, beat_snare=0, wet=0, dry=0)
    for _ in range(4):
        e.send("step_strength", 0.5); e.send("step", 0.5); e.run(e.silence(0.1))
        e.send("step_hit", hit); y = e.run(e.silence(0.4))[:, 0]
    return rms(np.diff(y[int(0.14 * SR):int(0.35 * SR)]))
stomp, plain = hat_after_hit(1.0), hat_after_hit(0.5)
check(stomp > 1.8 * plain, "beat: a stomp opens the hat that follows it (%.4f vs %.4f)" % (stomp, plain))

# uneven steps (beat_sure low) play the drums softer
def beat_level_at(sure):
    e = fresh(beat_level=1, wet=0, dry=0)
    out = []
    for _ in range(4):
        e.send("beat_sure", sure); e.send("step", 0.5); out.append(e.run(e.silence(0.5))[:, 0])
    return rms(out[-1])
sure_full, sure_low = beat_level_at(1.0), beat_level_at(0.4)
check(0.3 < sure_low / sure_full < 0.5, "beat: uneven steps soften the drums (%.2f of full)" % (sure_low / sure_full))

# groove: with "groove 1" a soft note joins on every half-step; without it (or once you stop) only the steps play
def groove_notes(groove, stop_after=False):
    e = fresh(music_on=1, music_pad=0, music_arp=1, wet=0); e.listen("chime_deg")
    for _ in range(20):
        e.send("groove", groove); e.send("step", 0.5); e.run(e.silence(0.5))
    n = len(e.heard["chime_deg"])
    if stop_after:
        e.run(e.silence(4.0))
        return len(e.heard["chime_deg"]) - n
    return n / 20
with_g, without_g, after_stop = groove_notes(1), groove_notes(0), groove_notes(1, stop_after=True)
check(with_g > without_g + 0.7 and after_stop <= 1,
      "music: groove adds half-step notes (%.2f notes a step, %.2f without) and stops when you do (%d after)"
      % (with_g, without_g, after_stop))

# switchable blocks: a block whose level is 0 stops its DSP (after its fade), comes back at once when needed,
# and switching it on doesn't click
SWITCHED = {"reverb": ("reverb_mix", 0.5), "pitch": ("pitch_mix", 0.5), "chorus": ("chorus_mix", 0.5),
            "flanger": ("flange_mix", 0.5), "phaser": ("phaser_mix", 0.5), "reverse": ("rvs_mix", 0.5),
            "roomnotes": ("music_res", 0.8), "music": ("music_on", 1), "gcloud": ("gc_amount", 1)}
bad_sw = []
for g, (k, v) in SWITCHED.items():
    over = {"music_on": 1, "music_res": 0} if g == "roomnotes" else {}
    e = fresh(**over); e.listen("sw_" + g)
    e.run(sine(440, 0.1, 4.0))
    off_at_rest = e.heard["sw_" + g][-1:] in ([], [0])   # it may have switched off before listening began
    e.send(k, v); y = e.run(sine(440, 0.1, 0.5))[:, 0]
    on_now = e.heard["sw_" + g][-1:] == [1]
    jump = np.max(np.abs(np.diff(y[:int(0.12 * SR)])))   # a switching click comes right after switch-on
    e.send(k, 0); e.run(sine(440, 0.1, 4.0))
    off_again = e.heard["sw_" + g][-1:] == [0]
    if not (off_at_rest and on_now and off_again and jump < 0.08):
        bad_sw.append((g, off_at_rest, on_now, off_again, round(float(jump), 3)))
check(not bad_sw, "switchable blocks: off at level 0, on at once, off again after the fade, no click (%s)"
      % (bad_sw or ", ".join(SWITCHED)))

# duck: while another app plays, the app's whole output dips a little, smoothly, and comes back
e = fresh(wet=0, dry=1); e.run(sine(440, 0.1, 0.5))
full = rms(e.run(sine(440, 0.1, 0.5))[:, 0])
e.send("duck", 0.3); y = e.run(sine(440, 0.1, 1.5))[:, 0]
ducked = rms(y[-SR // 2:])
e.send("duck", 0); back = rms(e.run(sine(440, 0.1, 1.5))[:, 0][-SR // 2:])
step = np.max(np.abs(np.diff(y[:SR // 2])))
check(abs(20 * np.log10(ducked / full) + 3.1) < 0.5 and abs(back - full) < 0.01 * full and step < 0.05,
      "duck: other audio dips the output %.1f dB, without a click (largest step %.3f), and it comes back"
      % (20 * np.log10(ducked / full), step))

# pocket hush: in a pocket the mic is turned down before the effects and the chimes
def pocket_level(pocket, hush, **over):
    e = fresh(wet=0, dry=1, **dict(dict(pocket_hush=hush), **over))
    e.send("pocket", pocket); e.run(e.silence(1.0))
    return rms(e.run(sine(440, 0.05, 1.0))[:, 0])
out, inp, off = pocket_level(0, 0.9), pocket_level(1, 0.9), pocket_level(1, 0)
check(inp < 0.1 * out and abs(off - out) < 0.02 * out,
      "pocket hush: the mic drops %.0f dB in a pocket (hush 0: %.1f dB)" % (20 * np.log10(out / inp), 20 * np.log10(off / out)))
e = fresh(wet=0, dry=1); e.run(sine(440, 0.05, 0.5))
e.send("pocket", 1); yy = e.run(sine(440, 0.05, 1.0))[:, 0]
check(max_jump(yy) < 0.03, "pocket hush: fades in without a click (max step %.4f)" % max_jump(yy))
# mic-down protection: only with the phone pocketed mic end first; it cuts the low cloth thump hardest, and at 0 changes nothing
def guarded(down, guard, freq):
    e = fresh(wet=0, dry=1, pocket_guard=guard)
    e.send("pocket", 1); e.send("pocket_down", down); e.run(e.silence(1.0))
    return rms(e.run(sine(freq, 0.05, 1.0))[:, 0])
up_lo, dn_lo, dn_hi, dn0_lo = guarded(0, 0.6, 100), guarded(1, 0.6, 100), guarded(1, 0.6, 2000), guarded(1, 0, 100)
up_hi = guarded(0, 0.6, 2000)
check(dn_lo < 0.2 * up_lo and 0.3 * up_hi < dn_hi < 0.6 * up_hi and abs(dn0_lo - up_lo) < 0.02 * up_lo,
      "mic-down protection: 100 Hz thump %.0f dB, 2 kHz %.0f dB, nothing at 0 (%.1f dB)"
      % (20 * np.log10(dn_lo / up_lo), 20 * np.log10(dn_hi / up_hi), 20 * np.log10(dn0_lo / up_lo)))
e = fresh(wet=0, dry=1, pocket_guard=1); e.send("pocket", 1); e.run(sine(100, 0.05, 1.0))
e.send("pocket_down", 1); yy = e.run(sine(100, 0.05, 1.0))[:, 0]
check(max_jump(yy) < 0.03, "mic-down protection: fades in without a click (max step %.4f)" % max_jump(yy))
def pocket_room(pocket):
    e = fresh(music_on=1, music_pad=0, music_arp=1, wet=0, gain=1); e.send("pocket", pocket)
    return band_rms(e.run(sine(50, 0.3, 30))[:, 0])
free, pocketed = pocket_room(0), pocket_room(1)
check(pocketed < 0.3 * free, "pocket hush: rustle rings fewer, softer chimes in a pocket (%.5f vs %.4f)" % (pocketed, free))
def pocket_res(pocket):
    e = fresh(music_on=1, music_pad=0, music_arp=0, music_res=1, wet=0, dry=1, gain=1); e.send("pocket", pocket); e.run(e.silence(1))
    rng = np.random.default_rng(5)
    x = np.concatenate([rng.standard_normal(int(0.05 * SR)) * 0.5, np.zeros(SR)]).astype(np.float32)
    return e.run(x)[:, 0][int(0.1 * SR):]          # the ringing after the burst (the dry burst is over by then)
rfree, rpocket = rms(pocket_res(0)), rms(pocket_res(1))
check(0.05 * rfree < rpocket < 0.5 * rfree, "pocket hush: Room notes ring softer in a pocket but still ring (%.6f vs %.4f)" % (rpocket, rfree))

# harmony: a held pitch gets an in-key answer a third above; noise and short blips get none
def hum(freq, secs, amp=0.1, quiet=0.0005, seed=4):
    rng = np.random.default_rng(seed); t = np.arange(int(secs * SR)) / SR
    voice = amp * (np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(4 * np.pi * freq * t) + 0.2 * np.sin(6 * np.pi * freq * t))
    lead = rng.standard_normal(2 * SR) * quiet; tail = rng.standard_normal(3 * SR) * quiet
    return np.concatenate([lead, voice + rng.standard_normal(len(t)) * quiet, tail]).astype(np.float32)
def harmony(x, **over):
    """The harmony voice alone (the same input with it on, minus with it off; music follows the Dry level), the
    answered scale steps and the pad's chord root at the time."""
    base = dict(music_on=1, music_pad=0, music_arp=0, music_res=0, wet=0)
    base.update(over)
    e = fresh(**dict(base, music_harm=1)); e.listen("harm_deg", "pad_chord")
    e.send("music_on", 1)                                        # (re)picks the chord, so the test hears which one
    y = e.run(x)[:, 0]
    chord = int(e.heard["pad_chord"][-1])
    return y - fresh(**dict(base, music_harm=0)).run(x)[:, 0], [int(v) for v in e.heard["harm_deg"]], chord
SCALE_IV = [(0, 2, 4, 5, 7, 9, 11), (0, 2, 3, 5, 7, 8, 10)]
def step_hz(step, key=0, scale=0):
    iv = SCALE_IV[scale]; n = len(iv)
    return 440 * 2 ** ((48 + key + 12 * (step // n) + iv[step % n] - 69) / 12)
def step_of(midi, key=0, scale=0):
    iv = SCALE_IV[scale]; n = len(iv); rel = round(midi) - 48 - key
    pc = rel % 12; best = min(range(n + 1), key=lambda i: (abs((list(iv) + [12])[i] - pc), i))
    return (rel // 12) * n + best
def is_chord_note(step, root, n=7):
    return (step - root) % n in (0, 2, 4)
y, degs, root = harmony(hum(220, 1.5))                         # A3 sung, C major
d = step_of(57); held = y[int(2.6 * SR):int(3.4 * SR)]
ok = len(degs) == 1 and is_chord_note(degs[0], root) and d + 7 + 2 <= degs[0] <= d + 7 + 4
f = step_hz(degs[0]) if degs else 1
check(ok and tone_level(held, f) > 0.05 and step_hz(degs[0]) > 2 * 220,
      "harmony: a sung A gets a chord note (root step %d) a third or more above it, an octave up (step %s for %d, %.0f Hz, level %.4f)"
      % (root, degs, d, f, tone_level(held, f)))
check(rms(y[int(4.8 * SR):]) < 0.2 * rms(held), "harmony: the answer fades once the hum stops (%.4f)" % rms(y[int(4.8 * SR):]))
_, degs_w, root_w = harmony(hum(1568, 1.5, amp=0.05))         # a whistled G6: answered below
dw = step_of(91)
check(len(degs_w) == 1 and is_chord_note(degs_w[0], root_w) and dw - 7 - 4 <= degs_w[0] <= dw - 7 - 2,
      "harmony: a whistle gets a chord note a third or more below it, an octave down (step %s for %d)" % (degs_w, dw))
_, degs_m, root_m = harmony(hum(220, 1.5), music_key=2, music_scale=1)   # D minor
dm = step_of(57, 2, 1)
check(len(degs_m) == 1 and is_chord_note(degs_m[0], root_m) and dm + 9 <= degs_m[0] <= dm + 11,
      "harmony: in D minor too (step %s for %d, chord root %d)" % (degs_m, dm, root_m))
rng = np.random.default_rng(5)
noise = np.concatenate([rng.standard_normal(2 * SR) * 0.0005, rng.standard_normal(2 * SR) * 0.1, rng.standard_normal(2 * SR) * 0.0005]).astype(np.float32)
_, degs_n, _ = harmony(noise)
_, degs_b, _ = harmony(hum(330, 0.08))
_, degs_q, _ = harmony(hum(220, 1.5, amp=0.0008))
check(not degs_n and not degs_b and not degs_q,
      "harmony: noise, a short blip and a hum lost in the room's quiet play nothing (%s %s %s)" % (degs_n, degs_b, degs_q))

# glitch cloud: a sudden sound comes back mangled; each kind does what it says
GC_KINDS = ("gc_stutter", "gc_reverse", "gc_tape", "gc_shuffle")
def gc_run(x, kind=None, steps=None, **over):
    """The glitch cloud alone (dry, echo and music off), with only `kind` switched on. Returns the left+right output
    and the kinds that fired. steps: seconds between footsteps, sent from the start."""
    base = dict(dry=0, wet=0, gc_amount=1, gc_level=1, reverb_mix=0)
    if kind:
        base.update({k: int(k == kind) for k in GC_KINDS})
    base.update(over)
    e = fresh(**base); e.listen("gc_mode")
    if steps is None:
        y = e.run(x)
    else:
        n = int(steps * SR); ys = []
        for i in range(0, len(x), n):
            e.send("step", steps); ys.append(e.run(x[i:i + n]))
        y = np.concatenate(ys)
    return y[:, 0] + y[:, 1], [int(v) for v in e.heard["gc_mode"]]
def burst_in(sig, at=3.0, total=6.0, quiet=0.0005, seed=7):
    rng = np.random.default_rng(seed); x = rng.standard_normal(int(total * SR)) * quiet
    i = int(at * SR); x[i:i + len(sig)] += sig
    return x.astype(np.float32)
t3 = np.arange(int(0.3 * SR)) / SR
chirp = (0.3 * np.sin(2 * np.pi * (300 * t3 + 0.5 * 3000 * t3 * t3))).astype(np.float32)    # 300 -> 1200 Hz rising
steady = (0.3 * np.sin(2 * np.pi * 1000 * t3)).astype(np.float32)
def centroid(seg):
    sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))); f = np.fft.rfftfreq(len(seg), 1 / SR)
    return float(np.sum(sp * f) / max(np.sum(sp), 1e-12))
def glitch_part(y, at=3.0, thr=0.01):
    """Where the glitch plays: from its first sound after the burst to its last."""
    a = np.abs(y[int(at * SR):]); idx = np.nonzero(a > thr)[0]
    return (y[int(at * SR) + idx[0]:int(at * SR) + idx[-1]], idx[0] / SR) if len(idx) else (np.zeros(1), None)
y0, m0 = gc_run(burst_in(chirp), gc_amount=0)
check(rms(y0) < 1e-4 and not m0, "glitch cloud: Amount 0 plays nothing (%.6f, %s)" % (rms(y0), m0))
y, m = gc_run(burst_in(chirp), "gc_reverse"); g, _ = glitch_part(y); q = len(g) // 4
check(m[:1] == [1] and len(g) > 0.2 * SR and centroid(g[:q]) > 1.3 * centroid(g[-q:]),
      "glitch cloud: reverse plays a rising sound falling (centroid %.0f -> %.0f Hz, %s)" % (centroid(g[:q]), centroid(g[-q:]), m))
y, m = gc_run(burst_in(steady), "gc_tape"); g, _ = glitch_part(y); q = len(g) // 5
zc = lambda v: np.mean(np.abs(np.diff(np.sign(v)))) * SR / 2
check(m[:1] == [2] and zc(g[:q]) > 900 and zc(g[3 * q:4 * q]) < 0.7 * zc(g[:q]),
      "glitch cloud: tape stop slows the sound down (%.0f -> %.0f Hz, %s)" % (zc(g[:q]), zc(g[3 * q:4 * q]), m))
y, m = gc_run(burst_in(steady), "gc_stutter"); g, _ = glitch_part(y)
check(m[:1] == [0] and len(g) > 0.2 * SR, "glitch cloud: a stutter repeats the sound (%.2f s, %s)" % (len(g) / SR, m))
jump = np.max(np.abs(np.diff(y))) if len(y) > 1 else 0
check(jump < 0.15 * max(np.max(np.abs(y)), 1e-9) + 0.01, "glitch cloud: no clicks where a stutter jumps back (%.3f of peak %.3f)" % (jump, np.max(np.abs(y))))
bed = burst_in(steady); bed += (0.05 * np.sin(2 * np.pi * 300 * np.arange(len(bed)) / SR)).astype(np.float32)   # a room that isn't silent
y, m = gc_run(bed, "gc_shuffle")
check(m[:1] == [3] and rms(y[int(3.0 * SR):]) > 0.005, "glitch cloud: shuffle plays a slice of the last few seconds (%s, rms %.4f)" % (m, rms(y[int(3.0 * SR):])))
# the free clock: a steady sound with no sudden start still gets a glitch now and then
rng = np.random.default_rng(9); fade = np.minimum(np.arange(12 * SR) / (3 * SR), 1)
hum12 = (rng.standard_normal(12 * SR) * 0.05 * fade).astype(np.float32)
y, m = gc_run(hum12)
check(len(m) >= 1 and rms(y[4 * SR:]) > 0.002, "glitch cloud: with no sudden sounds the free clock still glitches (%d in 12 s)" % len(m))
# walking: a sudden sound waits for the next step or half-step
y, m = gc_run(burst_in(steady, at=3.1), "gc_stutter", steps=0.5)
_, start = glitch_part(y, at=3.1, thr=0.05)
check(start is not None and 0.15 <= start <= 0.18,   # the half-step at +0.15 s, a 5 ms fade, a few ms of pre-roll
      "glitch cloud: while walking it lands on the half-step (%.3f s after the sound, wanted 0.15-0.18)" % (start or -1))
# wide: each glitch sits well out to one side (the far ear quieter and a little later)
def gc_sides(seed):
    x = burst_in(steady, seed=seed)
    e = fresh(dry=0, wet=0, gc_amount=1, gc_level=1, reverb_mix=0, gc_stutter=1, gc_reverse=0, gc_tape=0, gc_shuffle=0)
    y = e.run(x)[int(3.0 * SR):int(3.6 * SR)]
    l, r = rms(y[:, 0]), rms(y[:, 1])
    return (l - r) / max(l + r, 1e-9)
bal = [gc_sides(s) for s in (11, 12, 13)]
check(all(abs(b) > 0.3 for b in bal), "glitch cloud: each glitch sits well out to one side (balance %s)" % ["%.2f" % b for b in bal])

# echo scatter: each repeat lands somewhere else; at 0 the echo stays in the middle
def echo_balance(scatter):
    x = np.zeros(4 * SR, np.float32); x[SR:SR + 40] = 0.5
    e = fresh(dry=0, wet=1, feedback=0.75, echo_time=300, echo_sync=0, echo_scatter=scatter, reverb_mix=0)
    y = e.run(x); out = []
    for k in range(1, 7):
        a = int((1.0 + 0.3 * k) * SR); w = y[a - int(0.02 * SR):a + int(0.06 * SR)]
        l, r = rms(w[:, 0]), rms(w[:, 1]); out.append((l - r) / max(l + r, 1e-9))
    return out
b1, b0 = echo_balance(1), echo_balance(0)
moves = sum(abs(b - a) > 0.3 for a, b in zip(b1, b1[1:]))
check(moves >= 3 and max(abs(v) for v in b0) < 0.02,
      "echo scatter: repeats jump between places (%s), at 0 they stay centred (max %.3f)" % (["%.2f" % v for v in b1], max(abs(v) for v in b0)))

# CPU: what the glitch cloud costs while it runs, and that at Amount 0 it costs nothing
import time
def cost(**over):
    e = fresh(**over); x = burst_in(chirp, total=20.0); t0 = time.perf_counter(); e.run(x); return time.perf_counter() - t0
c_off = min(cost(gc_amount=0) for _ in range(2)); c_on = min(cost(gc_amount=1) for _ in range(2))
check(c_on < c_off * 1.35, "glitch cloud: cost while on +%.0f%% of the whole patch (off %.2f s, on %.2f s for 20 s of audio)"
      % (100 * (c_on / c_off - 1), c_off, c_on))

# room notes: resonators make the mic's own sound ring the current chord
def claps(n, gap, amp, quiet=0.0005, seed=1):
    rng = np.random.default_rng(seed)
    seg = [rng.standard_normal(3 * SR) * quiet]
    for _ in range(n):
        k = np.arange(int(0.03 * SR))
        seg += [rng.standard_normal(len(k)) * amp * np.exp(-k / (0.008 * SR)), rng.standard_normal(int(gap * SR)) * quiet]
    return np.concatenate(seg).astype(np.float32)
def room_notes(x, **over):
    """The room-notes voice alone: the same input with the voice on, minus with it off."""
    base = dict(music_on=1, music_pad=0, music_arp=0, wet=0)
    base.update(over)
    on = fresh(**dict(base, music_res=1)).run(x)[:, 0]
    off = fresh(**dict(base, music_res=0)).run(x)[:, 0]
    return on - off
cl = claps(3, 1.5, 0.5); c0 = 3 * SR
for key, scale, name in ((0, 0, "C major"), (2, 1, "D minor"), (9, 3, "A minor pentatonic")):
    y = room_notes(cl, music_key=key, music_scale=scale)
    ring = y[c0:c0 + SR]; pk = spec_peaks(ring)
    check(rms(ring[:int(0.3 * SR)]) > 0.01 and len(pk) >= 3 and not off_key(pk, key, scale) and max(pk) < 1800,
          "room notes: a clap rings notes of %s, below 1800 Hz (rms %.4f, peaks %s, off-key %s)" % (name, rms(ring[:int(0.3 * SR)]), [round(f) for f in pk[:6]], off_key(pk, key, scale)))
y = room_notes(cl)
check(rms(y[SR:c0]) < 0.001, "room notes: a quiet room rings nothing (%.6f)" % rms(y[SR:c0]))
# how long it rings follows what was heard: a soft tap chimes, a loud clap rings, a long loud sound becomes a bell
def burst(amp, secs, seed=2, quiet=0.0005):
    rng = np.random.default_rng(seed); k = np.arange(int(secs * SR))
    env = np.exp(-k / (0.008 * SR)) if secs < 0.1 else np.ones(len(k))
    return np.concatenate([rng.standard_normal(3 * SR) * quiet, rng.standard_normal(len(k)) * amp * env,
                           rng.standard_normal(6 * SR) * quiet]).astype(np.float32), 3 * SR + len(k)
def fade_time(y, end, drop_db=20):
    win = int(0.05 * SR); ref = rms(y[end:end + win])
    for t in range(end, len(y) - win, win):
        if rms(y[t:t + win]) < ref * 10 ** (-drop_db / 20):
            return (t - end) / SR
    return float("inf")
fades = {}
for name, amp, secs in (("tap", 0.03, 0.03), ("clap", 0.5, 0.03), ("long", 0.2, 2.0)):
    x, end = burst(amp, secs)
    fades[name] = fade_time(room_notes(x), end)
check(fades["tap"] < 0.7 and fades["tap"] < fades["clap"] < fades["long"] and fades["long"] > 1.8,
      "room notes: a soft tap chimes, a loud clap rings longer, a long loud sound rings like a bell (20 dB fade %.2f / %.2f / %.2f s)"
      % (fades["tap"], fades["clap"], fades["long"]))
y = room_notes(cl, music_on=0)
check(rms(y) < 1e-5, "room notes: silent while the music is off (%.6f)" % rms(y))
e = fresh(music_on=1, music_pad=0, music_arp=0, music_res=1, wet=0)
e.send("music_key", 1); e.run(e.silence(1.0))
y_on = e.run(cl)[:, 0]
e = fresh(music_on=1, music_pad=0, music_arp=0, music_res=0, wet=0)
e.send("music_key", 1); e.run(e.silence(1.0))
y = y_on - e.run(cl)[:, 0]; pk = spec_peaks(y[c0:c0 + SR])
check(len(pk) >= 3 and not off_key(pk, 1, 0) and off_key(pk, 0, 0), "room notes: changing the key retunes them to C# major (peaks %s)" % [round(f) for f in pk[:6]])
sung = np.concatenate([np.zeros(SR, np.float32), sine(261.63, 0.5, 3)])
y = room_notes(sung, music_react=0)
check(float(np.abs(y).max()) <= 0.31, "room notes: a loud note sung right on a resonator stays soft-limited (peak %.3f)" % float(np.abs(y).max()))

# echo, reverb and the ear stage shape the music like any other sound
def tail(**over):
    e = fresh(music_on=1, music_pad=0, music_arp=1, dry=1, **over)
    for _ in range(4):
        e.send("step", 0.4); e.run(e.silence(0.4))
    return rms(e.run(e.silence(3.0))[int(1.9 * SR):int(2.4 * SR), 0])   # after the chime has faded, before the still pattern resumes
t_dry, t_rev = tail(wet=0, reverb_mix=0), tail(wet=0, reverb_mix=1, reverb_size=0.95)
check(t_rev > 5 * t_dry + 1e-5, "music: the reverb gives the notes a tail (%.5f vs %.5f)" % (t_rev, t_dry))
t_echo = tail(wet=1, feedback=0.5, echo_time=700, reverb_mix=0, echo_sync=0)   # the slider's time, not the steps'
check(t_echo > 5 * t_dry + 1e-5, "music: the echo repeats the notes (%.5f vs %.5f)" % (t_echo, t_dry))
e = fresh(music_on=1, music_pad=1, music_arp=1, wet=0, space_pan=0.8)
y2 = e.run(e.silence(4))
check(rms(y2[:, 1]) > 1.3 * rms(y2[:, 0]), "music: the spatial pan places the music (L %.4f, R %.4f)" % (rms(y2[:, 0]), rms(y2[:, 1])))

# everything at once stays within +-1 and never produces NaN
e = fresh(music_on=1, music_pad=1, music_arp=1, gain=10, wet=1, feedback=0.7, echo_time=120)
ys = []
for i in range(30):
    e.send("step", 0.3); ys.append(e.run((rng.standard_normal(int(0.3 * SR)) * 0.4).astype(np.float32)))
ym = np.concatenate(ys)
check(not np.isnan(ym).any() and float(np.abs(ym).max()) <= 1.0 + 1e-6, "music: loud noise, steps and all voices stay within +-1 (max %.2f)" % float(np.abs(ym).max()))

# ---- 8. safety: loud input, max feedback, max gain ----
e = fresh(gain=10, feedback=0.85, wet=1, dry=1.5, echo_time=50)
rng = np.random.default_rng(1)
loud = (rng.standard_normal(SR * 10) * 0.5).astype(np.float32)
y = e.run(loud)
check(not np.isnan(y).any() and float(np.abs(y).max()) <= 1.0 + 1e-6, "loud noise at max settings: no NaN, output <= 1.0 (max %.3f)" % float(np.abs(y).max()))
tail = e.run(e.silence(20))
check(rms(tail[-SR:]) < 1e-3, "feedback tail decays to silence (last second rms %.2e)" % rms(tail[-SR:]))

print("ALL PASSED" if fails == 0 else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
