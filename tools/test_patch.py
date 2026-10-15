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
                music_tone=0.5, music_react=0.8, music_res=0.8, music_harm=0, echo_scatter=0, beat_follow=0, music_pad_reg=2, pocket_hush=0.5, pocket_guard=0.6, melody_src=0, harm_src=0, pad_src=0, bass_src=0, chime_char=0, res_src=0, music_answer=0, rustle_guard=0)
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
receivers = set(re.findall(r"#X obj \d+ \d+ r (\w+);", patch_text)) - {"step", "scale_n", "pad_glide", "mic_level", "pad_slot", "pool_n", "pool_x", "pocket", "pocket_down", "duck", "step_strength", "step_hit", "beat_sure", "groove", "gc_mode", "gc_try", "density_on", "motif", "drift_now", "drift_set", "drift_n", "music_register", "music_warm", "pulse", "tick16", "clock_walking", "gc_mode", "fs_need", "harm_organ", "fpad_need", "harm_run", "fpad_kick", "fpad_caught", "rh_swing_set", "fs_flourish_set", "rn_ring", "rnf_found", "realm_cue", "handling", "jolt", "msync", "tempo", "calm_chimes", "stem_on", "stem_file", "stem_bars", "stem_lvl", "stem_start", "heard_deg", "heard_off", "rustle_on"} - {r for r in re.findall(r"#X obj \d+ \d+ r (sw_\w+);", open(PATCH).read())}   # events and internal links, not settings
pd_ids = {i for i, _, nopd in jp if not nopd}
check(len(jp) >= 10, "parsed %d params from Params.java" % len(jp))
check(pd_ids == receivers, "Params.java ids == patch receivers (java-only %s, patch-only %s)"
      % (sorted(pd_ids - receivers), sorted(receivers - pd_ids)))
msg = re.search(r"#X msg \d+ \d+ (\\; gain .*?);\n", patch_text).group(1)
loadbang = {k: float(v) for k, v in re.findall(r"\; (\w+) ([-\d.]+)", msg)}
mism = [(i, d, loadbang.get(i)) for i, d, nopd in jp if not nopd and abs(loadbang.get(i, 1e9) - d) > 1e-6]
check(not mism, "loadbang defaults match Params.java defaults %s" % (mism or ""))

# a new install (every slider at its default, as the app sends them) plays only the room: a click comes back once
e = Engine(LIB, PATCH)
for i, d, nopd in jp:
    if not nopd:
        e.send(i, d)
e.run(e.silence(1.0))
x = np.zeros(2 * SR, np.float32); x[SR // 10] = 0.2
yd = np.abs(e.run(x))
after = float(yd[SR // 10 + int(0.03 * SR):].max())
check(yd.max() > 0.1 and after < 1e-3, "defaults: a click is heard once and nothing follows (peak %.2f, after it %.5f)" % (yd.max(), after))
e.close()

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
# the music keeps its own level whatever Dry is (it used to follow it); the echo still repeats the mic at Dry 0
def music_level(dry):
    e = fresh(dry=dry, wet=0, music_on=1, music_pad=1, music_pad_reg=1, music_arp=0, music_res=0)
    return rms(e.run(e.silence(5.0))[2 * SR:, 0])
m1, m0 = music_level(1), music_level(0)
e = fresh(dry=0, wet=1, feedback=0, echo_time=200, echo_sync=0); x = np.zeros(SR, np.float32); x[0] = 0.5
ye = np.abs(e.run(x)[:, 0]); echo_at = 1000 * int(np.argmax(ye)) / SR
check(m1 > 0.005 and abs(m0 - m1) < 0.1 * m1 and abs(echo_at - 200) < 8 and ye.max() > 0.2,
      "Dry doesn't touch the music (pad %.4f at Dry 1, %.4f at Dry 0); at Dry 0 the echo still repeats the mic (%.0f ms, %.2f)"
      % (m1, m0, echo_at, ye.max()))

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
def off_key(freqs, key, scale, overtones=False):
    """Peaks that are not within 0.25 semitone of a note of the scale (overtones: a chime's 3rd harmonic of an in-key
    note is not counted; chimes have a random brightness, so now and then that overtone is a peak of its own)."""
    bad = []
    for f in freqs:
        if overtones and not off_key([f / 3], key, scale):
            continue
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
# (a 20% contrast chord can miss ~21 picks of one scale about 1% of the time, and Pd's random seeds shift whenever
# objects are added, so its presence is checked over all the scales together)
contrast_seen = 0
for scale, (pool, contrast) in POOLS.items():
    picks = pad_choices(200, 40, music_scale=scale) + pad_choices(3000, 40, music_scale=scale) + pad_choices(800, 60, music_scale=scale)
    allowed = pool | ({contrast} if contrast is not None else set())
    n_con = sum(1 for c in picks if c == contrast)
    contrast_seen += n_con if contrast is not None else 0
    ok = set(picks) <= allowed and (contrast is None or n_con <= 0.45 * len(picks))
    check(ok, "music: %s pad uses only its chords %s%s (picked %s)" % (NAMES[scale], sorted(pool), "" if contrast is None else " + contrast %d" % contrast, picks))
check(contrast_seen >= 3, "music: the contrast chords do turn up (%d times over the scales)" % contrast_seen)
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
steady_q, steady_l = room(0.001, 120, music_react=0), room(0.3, 120, music_react=0)   # (long: ~10 chimes each)
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
check(not off_key(spec_peaks(brisk[-SR * 3:]), 0, 0, True), "music: the walking arpeggio stays in the key (off-key %s)"
      % off_key(spec_peaks(brisk[-SR * 3:]), 0, 0, True))
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
after = [t for t in still if t > 0.3]                                   # (a still-pattern chime may come before the clap)
check(after and after[0] < 0.36,
      "music: standing still, a clap's chime plays at once (%.0f ms after)" % ((after[0] - 0.3) * 1000 if after else -1))
check(None not in off and any(abs(t - 2.75) < 0.006 for t in walk_t) and 4.5 in walk_t and not any(4.35 < t < 4.5 for t in walk_t),
      "music: walking, chimes fall on steps or half-steps (%d notes; clap at 2.58 s chimed at %s, clap at 4.35 s waited for the 4.5 s step)"
      % (len(walk_t), [round(t, 3) for t in walk_t if 2.5 < t < 3.0]))

# with the walking beat on its tempo clock, notes land on the drums' grid standing still too: sudden-sound chimes
# on the clock's 8ths, motif notes on its 16ths; with the beat off a clap's chime still plays at once
def grid_times(e, mic, chunk=64, motif_at=()):
    """Runs `mic` in chunks: (times of chime_deg notes, {time: tick16} of the clock's ticks). motif_at: times to send
    a motif note."""
    notes, ticks, todo = [], {}, sorted(motif_at)
    for i in range(0, len(mic), chunk):
        while todo and todo[0] <= i / SR:
            e.send_list("motif", 3, 0.5); todo.pop(0)
        n, k = len(e.heard["chime_deg"]), len(e.heard["tick16"])
        e.run(mic[i:i + chunk]); t = (i + chunk) / SR
        notes += [t] * (len(e.heard["chime_deg"]) - n)
        for v in e.heard["tick16"][k:]:
            ticks[t] = int(v)
    return notes, ticks
def synced(**over):
    e = fresh(**dict(dict(music_on=1, music_pad=0, music_arp=1, wet=0, gain=1, beat_level=1, beat_follow=1, beat_when=1), **over))
    e.listen("chime_deg", "tick16"); e.run(clap_at(3.0, None)); return e
rng = np.random.default_rng(8); x = rng.standard_normal(8 * SR) * 0.0005
claps = [0.43, 1.61, 2.97, 4.18, 5.55, 6.9]
for c in claps:
    k = np.arange(int(0.03 * SR)); a = int(c * SR); x[a:a + len(k)] += rng.standard_normal(len(k)) * 0.5 * np.exp(-k / (0.008 * SR))
e = synced(); notes, ticks = grid_times(e, x.astype(np.float32))
on8 = [t in ticks and ticks[t] % 2 == 0 for t in notes]
waits = [min([t - c for t in notes if t >= c] or [9]) for c in claps]
waits = [w for w in waits if w < 0.6] or [9]                              # (density memory may skip a clap's chime)
check(len(notes) >= 4 and all(on8) and len(waits) >= 3 and max(waits) < 0.4,
      "music synced to the beat: standing still, chimes land on the clock's 8ths (%d notes, all on 8ths: %s, longest wait %.0f ms)"
      % (len(notes), all(on8), max(waits) * 1000))
e = synced(); motif_t = [0.37, 0.52, 0.91, 1.33, 2.08]
mnotes, mticks = grid_times(e, clap_at(3.0, None), motif_at=motif_t)
last_tick = lambda t: t - max(u for u in mticks if u <= t)
check(len(mnotes) == len(motif_t) and all(last_tick(t) < 0.002 or t - mt < 0.04 for t, mt in zip(mnotes, motif_t)),
      "music synced: motif notes go to the nearest 16th (%s)" % [round(t, 3) for t in mnotes])
e = synced(beat_level=0); still_s = note_times(e, clap_at(1.0, 0.3))
check(still_s and 0.3 < still_s[0] < 0.36,
      "music: with the beat off nothing waits (a clap's chime %.0f ms after)" % ((still_s[0] - 0.3) * 1000 if still_s else -1))
# the still pattern keeps about its density on the 8ths (a lively room: noise swinging every half second)
def still_count(**over):
    e = synced(**over); r = np.random.default_rng(11)
    lv = np.repeat(r.uniform(0.005, 0.05, 80), SR // 2)
    e.run((r.standard_normal(len(lv)) * lv).astype(np.float32)); return len(e.heard["chime_deg"])
c_sync, c_free = still_count(), still_count(beat_level=0)
check(c_free > 0 and 0.5 * c_free <= c_sync <= 2 * c_free, "music synced: the still chimes keep their density (%d vs %d free)" % (c_sync, c_free))

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
walking, dipped, back = db(lv[1]), min(db(v) for v in lv[4:9]), db(max(lv[21:28]))   # (its best: a chord change dips the bass)
check(abs(walking) < 1.5 and -6.5 < dipped < -2.5 and abs(back) < 1.5,
      "music: stopping after a walk, the pad breathes %.1f dB down and comes back (%.1f dB at 12-14 s; 1 s after %.1f dB)"
      % (dipped, back, walking))

# pace tiers: a stroll plays the calm patterns and rests more; a brisk walk plays the busy, leaping ones
def arp_run(interval, n=256):
    e = fresh(music_on=1, music_pad=0, music_arp=1, wet=0); e.listen("chime_deg", "pad_chord")
    per_step, chord_moved = [], []                             # the note each step played (None = a rest)
    for _ in range(n):
        k, c = len(e.heard["chime_deg"]), len(e.heard["pad_chord"])
        e.send("step", interval); e.run(e.silence(interval))
        new = e.heard["chime_deg"][k:]
        per_step.append(int(new[0]) if new else None); chord_moved.append(len(e.heard["pad_chord"]) > c)
    # (a chord change shifts the arpeggio whatever the pace, so those steps are left out of the jump measure)
    jumps = [abs(b - a) for a, b, moved in zip(per_step, per_step[1:], chord_moved[1:]) if a is not None and b is not None and not moved]
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
    return band_rms(e.run(sine(50, 0.3, 90))[:, 0])
free, pocketed = pocket_room(0), pocket_room(1)
check(pocketed < 0.4 * free, "pocket hush: rustle rings fewer, softer chimes in a pocket (%.5f vs %.4f)" % (pocketed, free))
def pocket_res(pocket):
    e = fresh(music_on=1, music_pad=0, music_arp=0, music_res=1, wet=0, dry=1, gain=1); e.send("pocket", pocket); e.run(e.silence(1))
    rng = np.random.default_rng(5)
    x = np.concatenate([rng.standard_normal(int(0.05 * SR)) * 0.5, np.zeros(SR)]).astype(np.float32)
    return e.run(x)[:, 0][int(0.1 * SR):]          # the ringing after the burst (the dry burst is over by then)
rfree, rpocket = rms(pocket_res(0)), rms(pocket_res(1))
check(0.05 * rfree < rpocket < 0.5 * rfree, "pocket hush: Room notes ring softer in a pocket but still ring (%.6f vs %.4f)" % (rpocket, rfree))

# density memory: in a busy room the chimes start eager, then thin out once a lot has been played lately
def note_rate(on=1):
    e = fresh(music_on=1, music_pad=0, music_arp=1, wet=0, music_react=1, gain=1); e.listen("chime_deg"); e.send("density_on", on)
    rng = np.random.default_rng(3); per_s = []
    for sec in range(30):
        x = rng.standard_normal(SR) * 0.003
        for k in range(3):                                         # three loud bursts a second: clatter, voices
            i = int((0.05 + 0.33 * k) * SR); n = int(0.15 * SR)
            x[i:i + n] += rng.standard_normal(n) * 0.3 * np.exp(-np.arange(n) / (0.06 * SR))
        n0 = len(e.heard["chime_deg"]); e.run(x.astype(np.float32)); per_s.append(len(e.heard["chime_deg"]) - n0)
    return per_s
with_mem, without = np.mean(note_rate(1)[10:]), np.mean(note_rate(0)[10:])
check(with_mem < 0.85 * without,
      "music: density memory thins a busy room's notes (%.2f a second, %.2f without it)" % (with_mem, without))

# key drift: the home chord moves to a related one on the same notes; never a diminished chord; off = home again
def drift_run(scale, n, **over):
    e = fresh(music_on=1, music_pad=1, music_arp=0, music_res=0, wet=0, music_scale=scale, **over); e.listen("drift", "pad_chord")
    e.send("music_on", 1); e.run(e.silence(0.5))
    for _ in range(n):
        e.send("drift_now", 1); e.run(e.silence(0.3))
    return e, [int(v) for v in e.heard["drift"]], [int(v) for v in e.heard["pad_chord"]]
e, drifts, chords = drift_run(0, 24)
check(set(drifts) <= {0, 1, 4, 5} and len(set(drifts)) >= 3 and 6 not in chords and len(set(chords)) >= 4,
      "music: key drift in C major moves home among %s and never plays the diminished chord (chords %s)" % (sorted(set(drifts)), sorted(set(chords))))
_, drifts_m, chords_m = drift_run(1, 24)
check(set(drifts_m) <= {0, 2, 3, 6} and 1 not in chords_m,
      "music: key drift in minor stays off the diminished chord (homes %s, chords %s)" % (sorted(set(drifts_m)), sorted(set(chords_m))))
e, _, _ = drift_run(0, 3)                                                  # (its own patch: the one above is closed)
e.send("music_drift", 0); e.run(e.silence(0.3)); n0 = len(e.heard["drift"])
for _ in range(5):
    e.send("drift_now", 1); e.run(e.silence(0.3))
check(e.heard["drift"][-1] == 0 and all(v == 0 for v in e.heard["drift"][n0:]),
      "music: switching key drift off brings the home chord back and keeps it (%s)" % [int(v) for v in e.heard["drift"][-6:]])

# register from the sensors (the app sends it): steps move the chimes up or down the scale, warm darkens their tone
def motif_notes(n=1, **sends):
    """Plays C5 through the motif input n times; returns its frequency and how bright it is on average (3rd harmonic
    vs the note: each chime has a random overtone colour, so one note says little)."""
    e = fresh(music_on=1, music_pad=0, music_arp=1, wet=0, music_tone=0.8)
    for k, v in sends.items():
        e.send(k, v)
    e.run(e.silence(0.3)); ratios = []; f1 = 0
    for _ in range(n):
        e.send_list("motif", 14, 0.5); y = e.run(e.silence(0.6))[:, 0]
        sp = np.abs(np.fft.rfft(y * np.hanning(len(y)))); f = np.fft.rfftfreq(len(y), 1 / SR)
        f1 = f[np.argmax(sp)]; ratios.append(tone_level(y, 3 * f1) / max(tone_level(y, f1), 1e-9))
        e.run(e.silence(2.5))
    return f1, float(np.mean(ratios))
(f0, _), (f7, _), (fd, _) = motif_notes(), motif_notes(music_register=7), motif_notes(music_register=-2)
e = fresh(music_on=1, music_tone=0.8); e.listen("chime_cut"); e.send("music_tone", 0.8); e.run(e.silence(0.1))
cut0 = e.heard["chime_cut"][-1]; e.send("music_warm", 1); e.run(e.silence(0.1)); cut1 = e.heard["chime_cut"][-1]
e.send("music_warm", 0); e.run(e.silence(0.1)); cut2 = e.heard["chime_cut"][-1]
check(abs(f7 / f0 - 2) < 0.03 and abs(fd / f0 - 2 ** (-3 / 12)) < 0.03 and abs(cut1 / cut0 - 0.45) < 0.01 and cut2 == cut0,
      "music: register moves the notes (C %.0f Hz, +7 steps %.0f Hz, -2 steps %.0f Hz); warm lowers the chimes' tone (%.0f -> %.0f -> %.0f Hz)"
      % (f0, f7, fd, cut0, cut1, cut2))

# motif memory (the app replays phrases): [motif step velocity( plays that chime, and is not reported as a new chime
e = fresh(music_on=1, music_pad=0, music_arp=1, wet=0); e.listen("chime_deg", "chime_note")
e.run(e.silence(1.0)); n_note = len(e.heard["chime_note"])
e.send_list("motif", 9, 0.5); y = e.run(e.silence(1.0))[:, 0]
check(9 in [int(v) for v in e.heard["chime_deg"]] and len(e.heard["chime_note"]) == n_note and rms(y[:int(0.5 * SR)]) > 0.005,
      "music: a motif note plays as a chime (rms %.4f) and is not remembered as a new one" % rms(y[:int(0.5 * SR)]))
e = fresh(music_on=1, music_pad=0, music_arp=1, wet=0, gain=1); e.listen("chime_note")
rng = np.random.default_rng(1); x = rng.standard_normal(6 * SR) * 0.0005
for k in range(3):
    i = int((3.0 + k) * SR); n = int(0.03 * SR); x[i:i + n] += rng.standard_normal(n) * 0.5 * np.exp(-np.arange(n) / (0.008 * SR))
e.run(x.astype(np.float32))
check(len(e.heard["chime_note"]) >= 1, "music: chimes from sudden sounds are reported for motif memory (%d)" % len(e.heard["chime_note"]))

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
_, degs_g, _ = harmony(hum(220, 1.5), gate_thresh=-50, gate_release=10, gate_hold=0)
check(len(degs_g) == 1, "harmony: the fastest gate release doesn't chop a held hum (%s)" % degs_g)
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

# the tempo clock: a steady beat that follows the walking (its pulses, timed to the 5 ms slice)
def clock_pulses(step_times, total, **over):
    e = fresh(**dict(dict(dry=0, wet=0, beat_follow=1), **over)); e.listen("pulse", "tempo")
    blk = 256; t = 0.0; last = None; n = 0; pulses = []; steps = sorted(step_times)
    while t < total:
        c = len(e.heard["pulse"])                                         # ("your steps" pulses come with the step)
        while n < len(steps) and steps[n] <= t + 1e-9:
            e.send("step", float(steps[n] - last if last is not None else 0.55)); last = steps[n]; n += 1
        e.run(np.zeros(blk, np.float32))
        if len(e.heard["pulse"]) > c:
            pulses.append(t)
        t += blk / SR
    return np.array(pulses), [float(v) for v in e.heard["tempo"]]
rng = np.random.default_rng(1)
wobbly = [1.0 + 0.5 * i + rng.uniform(-0.04, 0.04) for i in range(20)]
pl, tempo = clock_pulses(wobbly + [11.0 + 0.4 * i for i in range(15)], 18.0)
mid = np.diff(pl)[(pl[1:] > 3) & (pl[1:] < 10)]; fast = np.diff(pl)[pl[1:] > 12.5]
check(abs(np.mean(mid) - 0.5) < 0.01 and np.std(mid) < 0.012 and abs(np.mean(fast) - 0.4) < 0.015 and pl[-1] < 11.0 + 0.4 * 14 + 1.3 * 0.4,   # (one beat after the last step is filled in)
      "tempo clock: steps wobbling +-40 ms give an even beat (%.3f s, spread %.3f), a faster walk is followed (%.3f s), "
      "stopping stops it (last pulse %.2f s after the last step)" % (np.mean(mid), np.std(mid), np.mean(fast), pl[-1] - (11.0 + 0.4 * 14)))
pl, _ = clock_pulses([1.0 + 0.5 * i for i in range(16) if i != 9], 9.5)   # one step not detected
gaps = np.diff(pl[(pl > 2.5) & (pl < 8.6)])
check(np.max(gaps) < 0.55, "tempo clock: a missed step doesn't make a hole in the beat (longest gap %.2f s)" % np.max(gaps))
pl, tempo = clock_pulses([1.0 + 1.0 * i for i in range(10)], 11.0)       # an amble, 60 steps a minute
check(abs(tempo[-1] - 120) < 4 and abs(np.median(np.diff(pl)) - 0.5) < 0.02,
      "tempo clock: a slow amble plays at double time (%.0f BPM, a beat every %.2f s)" % (tempo[-1], np.median(np.diff(pl))))
pl, _ = clock_pulses(wobbly, 12.0, beat_follow=0)
check(np.std(np.diff(pl[(pl > 3) & (pl < 10)])) > 0.015, "tempo clock: 'your steps' passes the steps straight on, wobble and all (spread %.3f s)"
      % np.std(np.diff(pl[(pl > 3) & (pl < 10)])))

# the clock ticks from the start: standing still from Start there is a beat (Samuel heard none)
e = fresh(dry=0, wet=0, beat_level=1, beat_follow=1, beat_when=1); e.listen("tick16", "drum_kick", "drum_hat")
yq = e.run(np.zeros(4 * SR, np.float32))[:, 0]
n_hits = len(e.heard["drum_kick"]) + len(e.heard["drum_hat"])
check(len(e.heard["tick16"]) >= 20 and n_hits >= 5 and rms(yq[SR:]) > 0.003,
      "rhythm: with no step yet it already keeps a soft beat (%d ticks, %d hits in 4 s)" % (len(e.heard["tick16"]), n_hits))

# the pattern engine: bars of kick/snare/hat patterns on the clock's 16ths, varied every bar, softer standing still
def rhythm_run(walk_s, stand_s, x_stand=None, **over):
    e = fresh(**dict(dict(dry=0, wet=0, beat_level=1, beat_follow=1, beat_when=1), **over))
    e.listen("drum_kick", "drum_snare", "drum_hat", "rh_bar_patterns", "tempo", "tick16")
    out = []
    for k in range(int(walk_s * 2)):
        e.send("step", 0.5); out.append(e.run(np.zeros(SR // 2, np.float32))[:, 0])
    walk = {k: list(v) for k, v in e.heard.items()}
    for k in e.heard: e.heard[k] = []
    xs = x_stand if x_stand is not None else np.zeros(int(stand_s * SR), np.float32)
    ys = e.run(xs)[:, 0]
    return walk, {k: list(v) for k, v in e.heard.items()}, np.concatenate(out), ys
walk, stand, yw, ys = rhythm_run(32, 10)
bars = [int(v) for v in walk["rh_bar_patterns"]]
check(len(walk["tick16"]) == 4 * len(walk["tempo"]) and len(set(bars)) >= 3 and all(a != b for a, b in zip(bars, bars[1:])),
      "rhythm: 16ths on the clock (%d ticks, %d beats); the kick pattern changes every 2 bars, never repeating (%s)" % (len(walk["tick16"]), len(walk["tempo"]), bars))
quiet = rms(ys[2 * SR:]) / rms(yw[4 * SR:])
check(len(stand["drum_kick"]) >= 3 and 0.1 < quiet < 0.5 and max(int(v) for v in stand["rh_bar_patterns"]) <= 2,
      "rhythm: standing still in a quiet room it keeps a soft, sparse beat (%.2f of the walking level, patterns %s)"
      % (quiet, [int(v) for v in stand["rh_bar_patterns"]]))
_, stand0, _, ys0 = rhythm_run(8, 6, beat_when=0)
w4 = int(0.25 * SR); tail = [rms(ys0[i:i + w4]) for i in range(0, len(ys0) - w4, w4)]
quiet_at = next((i * 0.25 for i, v in enumerate(tail) if all(u < 1e-4 for u in tail[i:])), 99)
check(quiet_at <= 1.5, "rhythm: 'only while walking' goes silent soon after you stop (%.2f s after the last step)" % quiet_at)
rng = np.random.default_rng(4); lively = rng.standard_normal(12 * SR) * 0.0005
for k in range(30):                                                  # voices and clatter: bursts every 0.4 s
    i = int((0.2 + 0.4 * k) * SR); n = int(0.12 * SR); lively[i:i + n] += rng.standard_normal(n) * 0.08
lively = np.tile(lively, 3)                                          # (36 s: patterns are held 2 bars, so enough picks)
_, standL, _, ysL = rhythm_run(8, 36, x_stand=lively.astype(np.float32))
_, standQ, _, _ = rhythm_run(8, 36)
hitsQ = len(standQ["drum_hat"]) + len(standQ["drum_snare"]) + len(standQ["drum_kick"])
hitsL = len(standL["drum_hat"]) + len(standL["drum_snare"]) + len(standL["drum_kick"])
check(hitsL / 36 > 1.3 * hitsQ / 36, "rhythm: a lively room gets a busier beat standing still (%.1f vs %.1f hits a second)" % (hitsL / 36, hitsQ / 36))
# Intensity (the app's macro) moves the drive: calmer patterns at 0, busier at 1, the same at 0.5
def int_hits(t):
    _, st, _, _ = rhythm_run(8, 36, intensity=t)
    return (len(st["drum_hat"]) + len(st["drum_snare"]) + len(st["drum_kick"])) / 36
i0, i1 = int_hits(0), int_hits(1)
check(i1 > 1.3 * i0 and i0 <= hitsQ / 36 < i1, "rhythm: Intensity 0 calms the beat, 1 makes it busier (%.1f / %.1f / %.1f hits a second)" % (i0, hitsQ / 36, i1))

# found sounds: sudden sounds are caught and filed as kick / snare / hat, and the patterns play them
def fs_sounds(seed=2):
    rng = np.random.default_rng(seed)
    def thump(f=150):
        k = np.arange(int(0.2 * SR)); return 0.6 * np.sin(2 * np.pi * f * k / SR) * np.exp(-k / (0.05 * SR))
    def clap():                                            # noise band-passed around 1-3 kHz, like a real clap
        k = int(0.12 * SR); S = np.fft.rfft(rng.standard_normal(k)); f = np.fft.rfftfreq(k, 1 / SR)
        S[(f < 800) | (f > 3500)] = 0; x = np.fft.irfft(S, k); return 0.5 * x / np.max(np.abs(x)) * np.exp(-np.arange(k) / (0.03 * SR))
    def tick():
        k = np.arange(int(0.03 * SR)); x = rng.standard_normal(len(k)) * np.exp(-k / (0.004 * SR)); return 0.4 * np.diff(np.concatenate([[0], x]))
    return thump, clap, tick
def fs_catch(events, total, **over):
    thump, clap, tick = fs_sounds()
    x = (np.random.default_rng(3).standard_normal(int(total * SR)) * 0.0005).astype(np.float32)
    for t, f in events:
        s = {"k": thump, "s": clap, "h": tick}[f](); i = int(t * SR); x[i:i + len(s)] += s.astype(np.float32)
    e = fresh(**dict(dict(dry=0, wet=0, beat_level=1, beat_follow=1, beat_when=1, rhythm_src=1), **over))
    e.listen("fs_caught", "drum_kick")
    return e, e.run(x)[:, 0], [int(v) for v in e.heard["fs_caught"]]
e, y, caught = fs_catch([(1.0, "k"), (2.0, "s"), (3.0, "h"), (4.0, "k"), (5.0, "s"), (6.0, "h")], 7.0)
check(caught == [0, 1, 2, 0, 1, 2], "found sounds: a thump is caught as a kick, a clap as a snare, a tick as a hat (%s)" % caught)
e, y, caught = fs_catch([(1.0 + 0.6 * k, "k") for k in range(5)], 5.0)
check(len(caught) == 5, "found sounds: every thump is caught (%d), the kit keeps the latest %d of them" % (len(caught), 5))
_, _, none = fs_catch([], 4.0)
check(not none, "found sounds: a quiet room catches nothing (%s)" % none)
def pocketed_catch():
    thump, clap, tick = fs_sounds()
    x = (np.random.default_rng(3).standard_normal(4 * SR) * 0.0005).astype(np.float32)
    s = clap(); x[2 * SR:2 * SR + len(s)] += s.astype(np.float32)
    e = fresh(dry=0, wet=0, beat_level=1, beat_follow=1, beat_when=1, rhythm_src=1, pocket_hush=0); e.listen("fs_caught")
    e.send("pocket", 1); e.run(x); return [int(v) for v in e.heard["fs_caught"]]
check(not pocketed_catch(), "found sounds: nothing is caught while the phone is in a pocket")
# handling noise: a jolt (a tap or grip on the phone, from the app) near a sound means the sound is not caught
def jolted_catch(jolt_at):
    thump, clap, tick = fs_sounds()
    x = (np.random.default_rng(3).standard_normal(4 * SR) * 0.0005).astype(np.float32)
    s = clap(); x[2 * SR:2 * SR + len(s)] += s.astype(np.float32)
    e = fresh(dry=0, wet=0, beat_level=1, beat_follow=1, beat_when=1, rhythm_src=1); e.listen("fs_caught")
    if jolt_at is None:
        e.run(x)
    else:
        j = int(jolt_at * SR); e.run(x[:j]); e.send("jolt", 1); e.run(x[j:])
    return [int(v) for v in e.heard["fs_caught"]]
jc = {k: jolted_catch(k) for k in (None, 1.0, 1.9, 2.05)}
check(jc[None] == [1] and jc[1.0] == [1] and jc[1.9] == [4] and jc[2.05] == [4],
      "handling: a sound with a jolt 100 ms before or 50 ms into it is skipped (4), a jolt a second earlier doesn't matter %s" % jc)
# ...and it starts no chime or glitch, while the same claps without jolts do
def jolted_triggers(jolts, claps=True):
    thump, clap, tick = fs_sounds()
    x = (np.random.default_rng(3).standard_normal(12 * SR) * 0.0005).astype(np.float32)
    at = [1.0 + 1.3 * k for k in range(8)]
    for t in (at if claps else []):
        s = clap(); i = int(t * SR); x[i:i + len(s)] += s.astype(np.float32)
    e = fresh(music_on=1, music_pad=0, music_arp=0, music_react=1, wet=0, gc_amount=1, music_res=0); e.listen("chime_note", "gc_mode")
    pos = 0
    for t in at:
        j = int((t - 0.02) * SR); e.run(x[pos:j]); pos = j
        if jolts:
            e.send("jolt", 1)
    e.run(x[pos:])
    return len(e.heard["chime_note"]), len(e.heard["gc_mode"])
free, held, none = jolted_triggers(False), jolted_triggers(True), jolted_triggers(False, claps=False)
check(free[0] >= 3 and held[0] == 0 and free[1] > none[1] + 2 and held[1] <= none[1] + 2,
      "handling: claps with a jolt 20 ms before start no chimes and no glitches beyond the free clock's (chimes, glitches: %s without jolts, %s with, %s with no claps)" % (free, held, none))
# ...and the mic is turned down while the phone is handled: 0.5 -> -12 dB, back within a second
def handled_level(h):
    e = fresh(wet=0, dry=1, handling_hush=0.5)
    e.send("handling", h); y = e.run(sine(440, 0.1, 1.0))[:, 0]
    e.send("handling", 0); z = e.run(sine(440, 0.1, 1.0))[:, 0]
    return rms(y[SR // 2:]), rms(z[SR // 2:])
(h0, _), (h1, back) = handled_level(0), handled_level(1)
check(abs(20 * np.log10(h1 / h0) + 12) < 0.5 and abs(back / h0 - 1) < 0.02,
      "handling: full handling at hush 0.5 turns the mic down %.1f dB, and it comes back (%.3f)" % (20 * np.log10(h1 / h0), back / h0))
# the patterns play the caught sound: a 150 Hz thump comes back as kicks at 150 x 0.8 = 120 Hz; the synth kick is lower
def kick_tones(src, catch):
    ev = [(0.5, "k")] if catch else []
    e, y, _ = fs_catch(ev, 14.0, rhythm_src=src, beat_snare=0, beat_hats=0, beat_pitch=55, fs_flourish_set=0)   # (a half-speed flourish sits near 60 Hz)
    tail = y[4 * SR:]
    # (energy in a band, not a projection on one frequency: kicks at random times have random phases and can cancel)
    S_ = np.abs(np.fft.rfft(tail)) / len(tail); fr = np.fft.rfftfreq(len(tail), 1 / SR)
    band_e = lambda lo, hi: float(np.sqrt(np.sum(S_[(fr >= lo) & (fr < hi)] ** 2)))
    return band_e(110, 130), band_e(45, 65), rms(tail)
f120, f55, _ = kick_tones(1, True)
s120, s55, _ = kick_tones(0, True)
_, _, fallback = kick_tones(1, False)
_, _, synth_full = kick_tones(0, False)
# (each against itself: the synth kick's pitch drop also sweeps through 120 Hz)
check(f120 > 3 * f55 and s55 > 1.5 * s120 and 0.1 * synth_full < fallback < 0.4 * synth_full,
      "found sounds: the kicks play the caught thump (120 Hz %.4f vs synth %.4f; synth 55 Hz %.4f vs %.4f), nothing caught -> "
      "the synth faintly (rms %.4f vs %.4f)" % (f120, s120, s55, f55, fallback, synth_full))
# every hit is a little different: the same caught thump comes back at slightly different pitches (and loudness)
def kick_hit_pitches():
    thump, clap, tick = fs_sounds()
    x = (np.random.default_rng(3).standard_normal(16 * SR) * 0.0005).astype(np.float32); s_ = thump(); x[SR // 2:SR // 2 + len(s_)] += s_.astype(np.float32)
    e = fresh(dry=0, wet=0, beat_level=1, beat_follow=1, beat_when=1, rhythm_src=1); e.listen("drum_kick")
    y, times = [], []
    for i in range(0, len(x), 512):
        n = len(e.heard["drum_kick"]); y.append(e.run(x[i:i + 512])[:, 0])
        if len(e.heard["drum_kick"]) > n and i > 3 * SR:
            times.append(i)
    y = np.concatenate(y); out = []
    for t in times:
        seg = y[t:t + int(0.09 * SR)]
        if len(seg) < int(0.09 * SR):
            continue
        S_ = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 16 * len(seg))); fr = np.fft.rfftfreq(16 * len(seg), 1 / SR)
        S_[(fr < 95) | (fr > 145)] = 0; out.append(float(fr[np.argmax(S_)])); 
    return out
hp = kick_hit_pitches()
inr = [f for f in hp if 108 < f < 132]                                   # (a borrowed snare may share a kick's 16th)
check(len(hp) >= 5 and len(inr) >= 0.8 * len(hp) and max(inr) - min(inr) > 4,
      "found sounds: each hit is a little different (the thump's kicks at %s Hz, around 120)" % [round(f) for f in hp[:10]])
# flourishes: now and then a found hit plays backwards (its attack at the end) or at half speed (an octave down)
def flourish_hits(chance):
    thump, clap, tick = fs_sounds()
    x = (np.random.default_rng(3).standard_normal(14 * SR) * 0.0005).astype(np.float32); s_ = thump(); x[SR // 2:SR // 2 + len(s_)] += s_.astype(np.float32)
    e = fresh(dry=0, wet=0, beat_level=1, beat_follow=1, beat_when=1, rhythm_src=1, beat_snare=0, beat_hats=0)
    e.send("fs_flourish_set", chance); e.listen("drum_kick")
    y, times = [], []
    for i in range(0, len(x), 512):
        n = len(e.heard["drum_kick"]); y.append(e.run(x[i:i + 512])[:, 0])
        if len(e.heard["drum_kick"]) > n and i > 3 * SR:
            times.append(i)
    y = np.concatenate(y); low = late = 0
    for t in times:
        seg = y[t:t + int(0.2 * SR)]
        if len(seg) < int(0.2 * SR):
            continue
        S_ = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 4 * len(seg))); fr = np.fft.rfftfreq(4 * len(seg), 1 / SR)
        S_[(fr < 40) | (fr > 145)] = 0; low += fr[np.argmax(S_)] < 85                      # (half speed: ~60 Hz, not ~120)
        env = np.abs(seg); late += np.argmax(env) > 0.03 * SR                           # (backwards: loudest late)
    return len(times), low, late
n0, low0, late0 = flourish_hits(0); n1, low1, late1 = flourish_hits(500)
check(n1 >= 8 and low0 == 0 and late0 == 0 and low1 >= 2 and late1 >= 2,
      "found sounds: flourishes, a hit now and then backwards or at half speed (none at chance 0: %d/%d; at 50%%: %d half "
      "speed, %d backwards of %d)" % (low0, late0, low1, late1, n1))
# one catch makes the whole kit found: a lone clap (a snare) also plays as the kick and hat, the synth stays silent
def band(y, lo, hi):
    S = np.abs(np.fft.rfft(y)); f = np.fft.rfftfreq(len(y), 1 / SR); return float(np.sqrt(np.mean(S[(f >= lo) & (f < hi)] ** 2)))
e, y, caught = fs_catch([(0.5, "s")], 14.0, beat_pitch=55)
tail = y[4 * SR:]; kicks = len(e.heard["drum_kick"])
check(caught == [1] and kicks > 0 and band(tail, 40, 70) < 0.2 * band(tail, 800, 3000) and rms(tail) > 0.01,
      "found sounds: one clap makes the whole kit found (no synth kick at 55 Hz: %.2f vs the clap's band %.2f, rms %.4f)"
      % (band(tail, 40, 70), band(tail, 800, 3000), rms(tail)))
# each voice plays its own role's slice (the voices once all read the first kick slot): the clap is heard as a snare
_, y1, _ = fs_catch([(0.5, "k")], 14.0, beat_hats=0)
_, y2, c2 = fs_catch([(0.5, "k"), (1.5, "s")], 14.0, beat_hats=0)
check(c2 == [0, 1] and band(y2[4 * SR:], 800, 3000) > 3 * band(y1[4 * SR:], 800, 3000),
      "found sounds: with a kick and a snare caught, the snare plays the clap (1-3 kHz %.2f vs kick only %.2f)"
      % (band(y2[4 * SR:], 800, 3000), band(y1[4 * SR:], 800, 3000)))
# in a loud, steady room (-30 dBFS) a sound 8 dB over it is caught, a 4 dB bump is not
def loud_room_catch(lift):
    x = (np.random.default_rng(4).standard_normal(7 * SR) * 0.03).astype(np.float32)
    for t in (3.0, 4.5, 6.0):
        i = int(t * SR); x[i:i + int(0.08 * SR)] *= lift
    e = fresh(dry=0, wet=0, beat_level=1, beat_follow=1, beat_when=1, rhythm_src=1); e.listen("fs_caught")
    e.run(x[:2 * SR]); n0 = len(e.heard["fs_caught"]); e.run(x[2 * SR:]); return len(e.heard["fs_caught"]) - n0
l8, l4 = loud_room_catch(2.5), loud_room_catch(1.6)
check(l8 == 3 and l4 == 0, "found sounds: in a loud room, sounds 8 dB over it are caught (%d of 3), 4 dB bumps are not (%d)" % (l8, l4))

# a snap right at the mic overloads it: a clipped, dense slice must not come back as a deafening boom
def fs_catch_raw(events, total):
    x = (np.random.default_rng(3).standard_normal(int(total * SR)) * 0.0005).astype(np.float32)
    for t, snd in events:
        i = int(t * SR); x[i:i + len(snd)] += snd.astype(np.float32)
    e = fresh(dry=0, wet=0, beat_level=1, beat_follow=1, beat_when=1, rhythm_src=1); e.listen("fs_caught")
    e.run(x); return [int(v) for v in e.heard["fs_caught"]]
def found_playback(sound):
    x = (np.random.default_rng(3).standard_normal(14 * SR) * 0.0005).astype(np.float32)
    x[int(0.5 * SR):int(0.5 * SR) + len(sound)] += sound.astype(np.float32)
    e = fresh(dry=0, wet=0, beat_level=1, beat_follow=1, beat_when=1, rhythm_src=1, beat_snare=0, beat_hats=0)
    y = e.run(x)[:, 0]
    return np.max(np.abs(y[4 * SR:])), rms(y[4 * SR:])
thump = fs_sounds()[0]()
k = np.arange(int(0.25 * SR)); boom = np.clip(3 * np.sin(2 * np.pi * 90 * k / SR) + np.random.default_rng(5).standard_normal(len(k)), -0.99, 0.99)
p_t, r_t = found_playback(thump); p_b, r_b = found_playback(boom)
_, _, popped = fs_catch([(0.5, "k")], 2.0); popped2 = fs_catch_raw([(0.5, boom)], 2.0)
check(popped == [0] and popped2 == [3], "found sounds: a thump is kept, a mic pop (clipped and all lows) is not (%s, %s)" % (popped, popped2))
e = fresh(dry=0, wet=0, beat_level=1, beat_follow=1, beat_when=1, rhythm_src=0)                # (the whole synth kit)
r_syn = rms(e.run((np.random.default_rng(3).standard_normal(14 * SR) * 0.0005).astype(np.float32))[4 * SR:, 0])
check(r_b < 1.15 * r_syn and p_b < 0.75 and r_t > 0.45 * r_syn,
      "found sounds: a clipped snap at the mic (a pop: not kept) plays back no louder than the synth kit (rms %.3f vs %.3f, peak %.2f), and a thump "
      "kit is near it (%.3f)" % (r_b, r_syn, p_b, r_t))

# your voice as the harmony: a held hum gets a pitch-shifted copy of itself on the close chord note (a third or more
# above, same octave), carrying the hum's own overtones; no organ; it fades soon after the hum stops and only runs then
def voice_harmony(src):
    base = dict(music_on=1, music_pad=0, music_arp=0, music_res=0, wet=0, harm_src=src)
    x = hum(220, 1.5)
    e = fresh(**dict(base, music_harm=1)); e.listen("harm_deg", "harm_semi", "sw_hvoice"); e.send("music_on", 1)
    y = e.run(x)[:, 0] - fresh(**dict(base, music_harm=0)).run(x)[:, 0]
    return y, [int(v) for v in e.heard["harm_deg"]], list(e.heard["harm_semi"]), list(e.heard["sw_hvoice"])
yv, degs_v, semis_v, sw_v = voice_harmony(1)
held_v = yv[int(2.6 * SR):int(3.4 * SR)]
f_v = step_hz(degs_v[0] - 7) if degs_v else 1; f_org = step_hz(degs_v[0]) if degs_v else 1
check(len(degs_v) == 1 and 2.9 <= semis_v[-1] <= 9.1 and abs(f_v - 220 * 2 ** (semis_v[-1] / 12)) < 3
      and tone_level(held_v, f_v) > 0.02 and tone_level(held_v, 2 * f_v) > 0.2 * tone_level(held_v, f_v)
      and tone_level(held_v, 3 * f_org) < 0.05 * tone_level(held_v, f_v),
      "harmony, your voice: a hummed A3 is copied %.1f semitones up onto the chord note (%.0f Hz, level %.4f) with the "
      "hum's overtones (2nd %.4f), and no organ (%.5f)" % (semis_v[-1] if semis_v else 0, f_v, tone_level(held_v, f_v),
                                                           tone_level(held_v, 2 * f_v), tone_level(held_v, 3 * f_org)))
check(rms(yv[int(4.3 * SR):]) < 0.1 * rms(held_v) and sw_v[:1] == [1] and sw_v[-1] == 0,
      "harmony, your voice: it fades within half a second of the hum stopping (%.5f vs %.4f) and its shifter only runs "
      "while it sings (%s)" % (rms(yv[int(4.3 * SR):]), rms(held_v), sw_v))
def voice_semis(freq):
    e = fresh(music_on=1, music_pad=0, music_arp=0, music_res=0, wet=0, harm_src=1, music_harm=1); e.listen("harm_semi")
    e.send("music_on", 1); e.run(hum(freq, 1.5)); return list(e.heard["harm_semi"])
hi_v, wh_v = voice_semis(330), voice_semis(1568)
check(hi_v and -9 <= hi_v[-1] <= -3 and wh_v and -9 <= wh_v[-1] <= -3,
      "harmony, your voice: from middle C up a voice is answered a third or more below (E4: %s semitones; whistle %s), no chipmunk"
      % ([round(v, 1) for v in hi_v], [round(v, 1) for v in wh_v]))
yb, _, _, _ = voice_harmony(2); yo, _, _, sw_o = voice_harmony(0); held_b, held_o = yb[int(2.6 * SR):int(3.4 * SR)], yo[int(2.6 * SR):int(3.4 * SR)]
check(not sw_o and tone_level(held_o, f_v) < 0.2 * tone_level(held_v, f_v) and tone_level(held_b, f_v) > 0.5 * tone_level(held_v, f_v)
      and tone_level(held_b, 3 * f_org) > 0.5 * tone_level(held_o, 3 * f_org),
      "harmony sound: Organ plays no voice copy, Both plays the copy and the organ")

# the Realm cue: a dreamy warp, gliding up an octave when a Realm starts, down when your settings come back
def realm_cue(state, on=1):
    e = fresh(dry=0, wet=0, cue_sound=on); e.run(e.silence(0.2)); e.send("realm_cue", state)
    y = e.run(e.silence(4.5))[:, 0]
    def peak_hz(seg):
        S_ = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 8 * len(seg))); f = np.fft.rfftfreq(8 * len(seg), 1 / SR)
        S_[(f < 300) | (f > 1000)] = 0; return float(f[np.argmax(S_)])
    return (peak_hz(y[int(0.05 * SR):int(0.2 * SR)]), peak_hz(y[int(0.95 * SR):int(1.15 * SR)]), np.max(np.abs(y)),
            rms(y[int(4.3 * SR):]), rms(y[int(1.55 * SR):int(1.95 * SR)]))

up0, up1, up_pk, up_end, up_echo = realm_cue(1); dn0, dn1, _, _, _ = realm_cue(0); _, _, off_pk, _, _ = realm_cue(1, on=0)
check(up0 < 520 and abs(up1 - 880) < 15 and dn0 > 780 and abs(dn1 - 440) < 10 and 0.02 < up_pk < 0.12 and up_end < 0.0005
      and up_echo > 0.001 and off_pk < 1e-4,
      "realm cue: a warp gliding up into a Realm (%.0f -> %.0f Hz) and down back home (%.0f -> %.0f Hz), soft (peak %.3f), "
      "its echo still heard after the tone (%.4f), all gone by ~4 s, silent when switched off" % (up0, up1, dn0, dn1, up_pk, up_echo))

# from one Realm to another the warp swerves sideways: around one note, sweeping from one ear to the other
e = fresh(dry=0, wet=0, cue_sound=1); e.run(e.silence(0.2)); e.send("realm_cue", 2); ys = e.run(e.silence(2.0))
def side_bal(seg):
    l, r = rms(seg[:, 0]), rms(seg[:, 1]); return (r - l) / max(r + l, 1e-9)
b_early, b_late = side_bal(ys[int(0.1 * SR):int(0.3 * SR)]), side_bal(ys[int(0.8 * SR):int(1.0 * SR)])
seg = ys[int(0.1 * SR):int(1.2 * SR), 0] + ys[int(0.1 * SR):int(1.2 * SR), 1]
S_ = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))); f_ = np.fft.rfftfreq(len(seg), 1 / SR); S_[(f_ < 300) | (f_ > 1000)] = 0
fside = float(f_[np.argmax(S_)])
check(abs(b_late - b_early) > 0.4 and 590 < fside < 730,
      "realm cue, Realm to Realm: a sideways warp around E5 (%.0f Hz), sweeping across (balance %.2f -> %.2f)" % (fside, b_early, b_late))

# found pad: a held hum is kept with its pitch; from the next chord change the pad's chord is sung by it (each note
# folded within a tritone of the hum, its overtones carried), as loud as the synth pad; until then the synth plays.
# Noise and short blips are not kept; with the synth pad and Harmony at 0 nothing is even tracked.
def pad_peaks(y, n=8):
    S_ = np.abs(np.fft.rfft(y * np.hanning(len(y)))); fr = np.fft.rfftfreq(len(y), 1 / SR); S_[fr < 60] = 0; out = []
    for i in np.argsort(S_)[::-1]:
        if all(abs(fr[i] - f) > 4 for f in out): out.append(float(fr[i]))
        if len(out) >= n: break
    return out
def found_pad(x, src, secs=14, **over):
    e = fresh(**dict(dict(music_on=1, music_pad=1, music_pad_reg=1, music_arp=0, music_res=0, music_harm=0, wet=0, pad_src=src), **over))
    e.listen("fpad_caught", "pad_chord", "harm_deg", "sw_fbass")
    y = e.run(np.concatenate([x, np.zeros(secs * SR, np.float32)]))[:, 0]
    return y, e.heard["fpad_caught"], [int(v) for v in e.heard["pad_chord"]], e.heard["harm_deg"], e.heard["sw_fbass"]
yf, cf, chords_f, _, _ = found_pad(hum(220, 1.5), 1)
ys, cs, chords_s, hd_s, _ = found_pad(hum(220, 1.5), 0)
seg_f, seg_s = yf[9 * SR:12 * SR], ys[9 * SR:12 * SR]
pk = pad_peaks(seg_f, 8)
pcs = {round(12 * np.log2(f / 440)) % 12 for f in pk[:4]}                 # (the 4 strongest: the chord's notes)
chord_pc = {(SCALE_IV[0][(chords_f[0] + d) % 7]) % 12 for d in (0, 2, 4)} if chords_f else set()
key_pc = {(p - 9) % 12 for p in chord_pc}                                 # (relative to A = 440 Hz)
ovt = sum(1 for f in pk if any(abs(f - m * g) < 4 for g in pk for m in (2, 3) if g < f))
check(len(cf) == 1 and abs(cf[0] - 57) < 0.5 and pcs <= key_pc and len(pcs) == 3 and ovt >= 2
      and 0.6 * rms(seg_s) < rms(seg_f) < 1.5 * rms(seg_s),
      "found pad: a hummed A3 is kept (%s) and sings the next chord (%s, the chord's 3 notes; %d overtones among the peaks), "
      "as loud as the synth pad (%.4f vs %.4f)" % (cf, sorted(pcs), ovt, rms(seg_f), rms(seg_s)))
check(0.7 * rms(ys[4 * SR:6 * SR]) < rms(yf[4 * SR:6 * SR]) < 1.4 * rms(ys[4 * SR:6 * SR]) and not cs and not hd_s,
      "found pad: until the next chord change the synth pad plays on (%.4f vs %.4f); with the synth pad and Harmony at 0 "
      "nothing is tracked (%s)" % (rms(yf[4 * SR:6 * SR]), rms(ys[4 * SR:6 * SR]), hd_s))
_, c_noise, _, _, _ = found_pad(noise, 1, secs=2); _, c_blip, _, _, _ = found_pad(hum(330, 0.08), 1, secs=2)
_, c_short, _, _, _ = found_pad(hum(220, 0.3), 1, secs=2)
check(not c_noise and not c_blip and not c_short, "found pad: noise, a blip and a hum shorter than a take are not kept (%s %s %s)"
      % (c_noise, c_blip, c_short))
yb0, _, _, _, _ = found_pad(hum(220, 1.5), 1, secs=10, music_pad_reg=0, bass_src=0)
yb1, _, _, _, swb = found_pad(hum(220, 1.5), 1, secs=10, music_pad_reg=0, bass_src=1)
b0, b1 = rms(yb0[5 * SR:12 * SR]), rms(yb1[5 * SR:12 * SR]); pkb = pad_peaks(yb1[5 * SR:12 * SR], 3)
check(swb == [1] and 0.6 * b0 < b1 < 1.5 * b0 and min(pkb) < 135,
      "found bass: on a take it plays the bass from it (%s Hz), about as loud as the synth bass (%.4f vs %.4f)"
      % ([round(f) for f in pkb], b1, b0))

# found melody: the melody's notes play a caught sound striking resonators tuned to the note, in key, about as loud as
# the synth chimes; before anything is caught, "Found" plays the synth chimes; catching runs for it with the beat off
def peak_hz(y):
    S = np.abs(np.fft.rfft(y * np.hanning(len(y)))); f = np.fft.rfftfreq(len(y), 1 / SR)
    S[f < 80] = 0; return f[np.argmax(S)]
def top3_hz(y):
    S = np.abs(np.fft.rfft(y * np.hanning(len(y)))); f = np.fft.rfftfreq(len(y), 1 / SR); S[f < 80] = 0; out = []
    for i in np.argsort(S)[::-1]:
        if all(abs(f[i] - g) > 8 for g in out): out.append(float(f[i]))
        if len(out) >= 3: return out
def melody_notes(src, sound=None, **over):
    x = (np.random.default_rng(3).standard_normal(7 * SR) * 0.0005).astype(np.float32)
    if sound is not None:
        x[SR:SR + len(sound)] += sound.astype(np.float32)
    e = fresh(**dict(dict(music_on=1, music_pad=0, music_arp=1, wet=0, music_res=0, music_react=0, melody_src=src), **over))
    e.listen("fs_caught"); e.run(x[:3 * SR]); out = []
    for deg in (7, 9, 11):
        e.send_list("motif", deg, 0.5); out.append(e.run(x[3 * SR:4 * SR])[:, 0])
    return [int(v) for v in e.heard["fs_caught"]], [top3_hz(o) for o in out], [rms(o) for o in out]
thump, clap, tick = fs_sounds()
_, syn_t3, syn_r = melody_notes(0, clap()); syn_hz = [t[0] for t in syn_t3]
for nm, snd in (("clap", clap()), ("thump", thump())):
    c, hz, r = melody_notes(1, snd)
    in_key = all(any(abs(h - f * m) < 6 for m in (1, 2) for h in t3) for t3, f in zip(hz, syn_hz))   # (among its 3 peaks)
    hz = [t3[0] for t3 in hz]
    check(len(c) == 1 and in_key and all(0.3 * a < b < 1.8 * a for a, b in zip(syn_r, r)),
          "found melody: a caught %s plays the notes in key (%s Hz vs the synth's %s) about as loud (rms %s vs %s)"
          % (nm, [round(h) for h in hz], [round(h) for h in syn_hz], [round(v, 3) for v in r], [round(v, 3) for v in syn_r]))
_, hz0, r0 = melody_notes(1, None); hz0 = [t[0] for t in hz0]
check(all(abs(a - b) < 2 for a, b in zip(hz0, syn_hz)) and all(0.6 * b < a < 1.5 * b for a, b in zip(r0, syn_r)),
      "found melody: nothing caught yet -> the synth chimes play (rms %s vs %s)" % ([round(v, 3) for v in r0], [round(v, 3) for v in syn_r]))
def voices_on(src):
    """How often the found melody's voices were switched on (they run only while a note rings) and the rms."""
    x = (np.random.default_rng(3).standard_normal(6 * SR) * 0.0005).astype(np.float32); c = clap(); x[SR:SR + len(c)] += c.astype(np.float32)
    e = fresh(music_on=1, music_pad=0, music_arp=1, wet=0, music_res=0, music_react=0, melody_src=src)
    e.listen("sw_fmv0", "sw_fmv1", "sw_fmv2", "sw_fmv3"); e.run(x[:3 * SR])
    for deg in (7, 9, 11):
        e.send_list("motif", deg, 0.5); e.run(x[3 * SR:4 * SR])
    e.run(e.silence(4.0))                                               # (a fade lasts up to 2.6 s, then 0.6 s more)
    return sum(v == 1 for k in range(4) for v in e.heard["sw_fmv%d" % k]), sum(v == 0 for k in range(4) for v in e.heard["sw_fmv%d" % k])
on_s, _ = voices_on(0); on_f, off_f = voices_on(1); on_b, _ = voices_on(2)
_, _, rb = melody_notes(2, clap())
check(on_s == 0 and on_f >= 3 and on_b >= 3 and off_f >= 1 and sum(rb) > 0.8 * sum(syn_r),
      "found melody: its voices switch on only for notes (synth %d, found %d, both %d, off again %d), Both keeps the synth "
      "chimes (rms %s vs %s)" % (on_s, on_f, on_b, off_f, [round(v, 3) for v in rb], [round(v, 3) for v in syn_r]))
# Chime character: toward "your sound" the hit carries more of the note (less of it in the tuned ring), the ring is
# shorter, and the level holds
def chime_char(cc):
    x = (np.random.default_rng(3).standard_normal(6 * SR) * 0.0005).astype(np.float32); c = clap(); x[SR:SR + len(c)] += c.astype(np.float32)
    e = fresh(music_on=1, music_pad=0, music_arp=1, wet=0, music_res=0, music_react=0, melody_src=1, chime_char=cc)
    e.run(x[:3 * SR]); tonal, early, late, lvl = [], [], [], []
    for deg in (7, 9, 11):
        e.send_list("motif", deg, 0.5); y = e.run(x[3 * SR:4 * SR])[:, 0]
        S_ = np.abs(np.fft.rfft(y[:int(0.5 * SR)])) ** 2; f = np.fft.rfftfreq(int(0.5 * SR), 1 / SR)
        pk = f[np.argmax(S_ * (f > 150))]; band = sum(S_[(np.abs(f - pk * m) < 6)].sum() for m in (1, 2))
        tonal.append(band / S_[f > 150].sum()); early.append(rms(y[:int(0.15 * SR)])); late.append(rms(y[int(0.5 * SR):]))
        lvl.append(rms(y))
    return np.mean(tonal), np.mean(late) / max(np.mean(early), 1e-9), np.mean(lvl)
t0, d0, l0 = chime_char(0); t1, d1, l1 = chime_char(1)
check(t1 < 0.7 * t0 and d1 < 0.6 * d0 and 0.4 < l1 / l0 < 2.5,
      "found melody: Chime character from ring to your sound: the note's share in the tuned ring %.2f -> %.2f, the ring after "
      "0.5 s %.2f -> %.2f of the start, level %.3f -> %.3f" % (t0, t1, d0, d1, l0, l1))
# Room notes, found: after a catch, each sudden sound plays a caught sound on a chord tone (the ring resonators off)
def room_found(src):
    x = (np.random.default_rng(3).standard_normal(9 * SR) * 0.0005).astype(np.float32)
    for t in (1.0, 2.5, 3.3, 4.1, 4.9):                                    # (the pad changes chord at ~6.5 s)
        c = clap(); x[int(t * SR):int(t * SR) + len(c)] += c.astype(np.float32)
    base = dict(music_on=1, music_pad=0, music_arp=0, wet=0, music_react=1, res_src=src, chime_char=0)
    e = fresh(**dict(base, music_res=1)); e.listen("sw_rfv0", "sw_rfv1", "sw_roomnotes", "pad_chord"); e.send("music_on", 1)
    y = e.run(x)[:, 0] - fresh(**dict(base, music_res=0)).run(x)[:, 0]          # (music follows Dry: the room notes alone)
    on = sum(v == 1 for k in (0, 1) for v in e.heard["sw_rfv%d" % k])
    return y, on, e.heard["sw_roomnotes"], int(e.heard["pad_chord"][0]) if e.heard["pad_chord"] else None
yr, on_r, swr, root_r = room_found(1); y0, on_0, sw0, _ = room_found(0)
seg = yr[int(2.4 * SR):int(6.3 * SR)]
S_ = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))); fr = np.fft.rfftfreq(len(seg), 1 / SR); S_[fr < 150] = 0
pk = []
for i in np.argsort(S_)[::-1]:
    if all(abs(fr[i] - g) > 8 for g in pk): pk.append(float(fr[i]))
    if len(pk) >= 3: break
pcs = {round(12 * np.log2(f / 261.63)) % 12 for f in pk}
chord = {SCALE_IV[0][(root_r + d) % 7] for d in (0, 2, 4)} if root_r is not None else set()
check(on_r >= 3 and on_0 == 0 and swr[-1:] == [0] and rms(seg) > 0.003 and pcs <= chord,
      "room notes, found: claps play caught sounds on chord tones (%d notes, pitch classes %s in the chord %s, rms %.4f), "
      "the ring resonators off (%s); Ring mode plays none (%d)" % (on_r, sorted(pcs), sorted(chord), rms(seg), swr, on_0))
c_beat_off, _, _ = melody_notes(1, clap(), beat_level=0)
c_none, _, _ = melody_notes(0, clap(), beat_level=0)
check(c_beat_off == [1] and c_none == [], "found melody: sounds are caught for it with the beat off (%s), not when nothing needs them (%s)"
      % (c_beat_off, c_none))

# glitch loops (C5): a glitch is recorded and comes back every bar at its own spot, fading, inside the beat
def glitch_loop(beat_glitch):
    x = (np.random.default_rng(6).standard_normal(16 * SR) * 0.0005).astype(np.float32)
    k = np.arange(int(0.3 * SR)); x[int(1.0 * SR):int(1.0 * SR) + len(k)] += (0.3 * np.sin(2 * np.pi * 700 * k / SR)).astype(np.float32)
    e = fresh(dry=0, wet=0, beat_level=1, beat_follow=1, beat_when=1, rhythm_src=0, beat_snare=0, beat_hats=0, beat_pitch=40,
              gc_amount=1, gc_level=0, beat_glitch=beat_glitch, gc_pct_stutter=100, gc_pct_reverse=0, gc_pct_shuffle=0, gc_pct_stretch=0)
    e.listen("gloop_play", "gc_mode")
    y = e.run(x)[:, 0]
    return [round(v, 2) for v in e.heard["gloop_play"]], tone_level(y[4 * SR:], 700), e.heard["gc_mode"]
plays, tone, modes = glitch_loop(1)
_, tone0, _ = glitch_loop(0)
# (at Amount 1 new glitches keep restarting the loop at full level; between them it fades)
fades = any(abs(b - a * 0.65) < 0.02 for a, b in zip(plays, plays[1:]))
check(len(modes) >= 1 and len(plays) >= 3 and fades and tone > 5 * tone0 + 1e-4,
      "glitch loops: a glitch (glitch level 0) comes back in the beat every bar, fading (%s), its 700 Hz in the beat %.4f vs off %.4f"
      % (plays[:6], tone, tone0))

# tempo "Set": standing still the beat goes to your BPM; walking pulls it halfway toward the steps; stopping, back
def set_tempo(bpm, steps=0, interval=0.6, secs=8):
    e = fresh(dry=0, wet=0, beat_level=1, beat_follow=1, beat_when=1, rhythm_src=0, tempo_mode=1, tempo_bpm=bpm)
    e.listen("tempo"); e.run(e.silence(secs))
    stand = e.heard["tempo"][-1]
    for _ in range(steps):
        e.send("step", interval); e.run(e.silence(interval))
    walk = e.heard["tempo"][-1]; e.run(e.silence(secs)); back = e.heard["tempo"][-1]
    return stand, walk, back
s125, _, _ = set_tempo(125); s90, w90, b90 = set_tempo(90, steps=24, interval=0.6)
want_walk = 60000 / (0.5 * 60000 / 90 + 0.5 * 600)
check(abs(s125 - 125) < 1.5 and abs(s90 - 90) < 1.5 and abs(w90 - want_walk) < 2.5 and abs(b90 - 90) < 1.5,
      "tempo set: standing at 125 -> %.1f BPM, at 90 -> %.1f; walking 100 steps/min pulls it halfway (%.1f, want %.1f); "
      "stopping, back to %.1f" % (s125, s90, w90, want_walk, b90))

# swing: off-beat 16ths reach the drums a share of a 16th late (on-beats stay on the tick); the amount drifts
def swing_lags(sw, steps=40, interval=0.4):
    e = fresh(dry=0, wet=0, beat_level=1, beat_follow=1, beat_when=1, rhythm_src=0)
    e.listen("tick16", "drum_kick", "drum_snare", "drum_hat", "rh_swing")
    names = ("drum_kick", "drum_snare", "drum_hat"); last = {}; lags = {0: [], 1: []}; t = 0.0; n = 64
    seen = {k: 0 for k in names + ("tick16",)}
    for st in range(steps):
        e.send("step", interval)
        if sw is not None:
            e.send("rh_swing_set", sw)
        for _ in range(int(interval * SR) // n):
            e.run(np.zeros(n, np.float32)); t += n / SR
            for v in e.heard["tick16"][seen["tick16"]:]:
                last = {"tick": int(v), "t": t}
            seen["tick16"] = len(e.heard["tick16"])
            for k in names:
                if len(e.heard[k]) > seen[k] and last and st > 8:
                    lags[last["tick"] % 2].append(t - last["t"])
                seen[k] = len(e.heard[k])
    return lags, e.heard["rh_swing"]
l0, _ = swing_lags(0); l25, _ = swing_lags(0.25)
odd0, odd25, even25 = np.median(l0[1]) if l0[1] else 9, np.median(l25[1]) if l25[1] else 9, max(l25[0]) if l25[0] else 9
sixteenth = 60 / 150 / 4                                                   # (steps 0.4 s apart: the clock at 150 BPM)
check(len(l25[1]) >= 10 and odd0 < 0.004 and abs(odd25 - 0.25 * sixteenth) < 0.006 and even25 < 0.004,
      "swing: off-beat 16ths land a share of a 16th late (swing 0.25: %.0f ms, want %.0f; straight: %.0f ms), on-beats on time (%.0f ms)"
      % (odd25 * 1000, 0.25 * sixteenth * 1000, odd0 * 1000, even25 * 1000))
_, drift = swing_lags(None, steps=150)
dv = sorted({round(v, 2) for v in drift})
check(len(drift) >= 20 and max(drift) <= 0.27 and max(drift) - min(drift) > 0.05,
      "swing: it drifts every few bars between straight and lazy (%d bars, %.2f-%.2f)" % (len(drift), min(drift), max(drift)))

# arrangement moments: now and then (at least 8 bars apart) a sparse bar: hats only, no kick, or the downbeat only
def breaks_run(steps=150, interval=0.4):
    e = fresh(dry=0, wet=0, beat_level=1, beat_follow=1, beat_when=1, rhythm_src=0)
    e.listen("tick16", "drum_kick", "drum_snare", "rh_break")
    bar, last_tick, kinds, per_bar, seen = -1, -1, {}, {}, {"tick16": 0, "drum_kick": 0, "drum_snare": 0, "rh_break": 0}
    pending = None
    for st in range(steps):
        e.send("step", interval)
        for _ in range(int(interval * SR) // 64):
            e.run(np.zeros(64, np.float32))
            for v in e.heard["rh_break"][seen["rh_break"]:]:
                pending = int(v)                                            # (decided after tick 15: the next bar)
            seen["rh_break"] = len(e.heard["rh_break"])
            for v in e.heard["tick16"][seen["tick16"]:]:
                if int(v) == 0:
                    bar += 1; kinds[bar] = pending or 0; pending = None
                last_tick = int(v)
            seen["tick16"] = len(e.heard["tick16"])
            for k in ("drum_kick", "drum_snare"):
                for v in e.heard[k][seen[k]:]:
                    if v > 0 and bar >= 0:
                        per_bar.setdefault(bar, []).append((k, last_tick))
                seen[k] = len(e.heard[k])
    return kinds, per_bar, bar
kinds, per_bar, nbars = breaks_run()
brk = [b for b, k in kinds.items() if k > 0]
ok_kind = all((kinds[b] == 1 and not per_bar.get(b)) or (kinds[b] == 2 and not any(k == "drum_kick" for k, _ in per_bar.get(b, [])))
              or (kinds[b] == 3 and all((k, t) == ("drum_kick", 0) for k, t in per_bar.get(b, []))) for b in brk)
gaps = [b - a for a, b in zip(brk, brk[1:])]
busy = sum(1 for b in range(nbars) if b not in brk and per_bar.get(b))
check(len(brk) >= 2 and ok_kind and all(g >= 9 for g in gaps) and busy >= nbars - len(brk) - 2,
      "arrangement: now and then a sparse bar (%d in %d bars, kinds %s, at bars %s), each as thin as its kind, then the groove"
      % (len(brk), nbars, [kinds[b] for b in brk], brk))

# the learned groove (C4): claps on one off-beat spot teach the snare that spot; a few quiet bars later it's gone
def learned_spots(clap_bars, bars, spot=6):
    """Standing still at the default 100 BPM (a 16th = 150 ms). Syncs on the clock's own ticks, then claps 20 ms after
    tick `spot` in clap_bars; returns, per bar, whether a snare played on that spot."""
    thump, clap, tick = fs_sounds()
    e = fresh(dry=0, wet=0, beat_level=1, beat_follow=1, beat_when=1, rhythm_src=1); e.listen("drum_snare", "tick16")
    while not e.heard["tick16"]:
        e.run(np.zeros(128, np.float32))
    v = int(e.heard["tick16"][-1]); hit = {}
    n = int(0.15 * SR) // 64 * 64; snares_at = []
    for j in range(16 * bars + 16):
        k = (v + j) % 16; b = (j + v) // 16                                # chunk j starts just after tick k of bar b
        x = (np.random.default_rng(j).standard_normal(n) * 0.0005).astype(np.float32)
        if b in clap_bars and k == spot:
            c = clap(); i0 = int(0.02 * SR); x[i0:i0 + len(c)] += c[:n - i0].astype(np.float32)
        e.send("rh_swing_set", 0)                                     # (straight: a swung 16th could land in the next chunk)
        s0 = len(e.heard["drum_snare"]); t0 = len(e.heard["tick16"]); e.run(x)
        # (a learned snare plays at 0.9 x what was remembered, ~0.7; ghost snares at 0.22 fall anywhere now and then)
        if len(e.heard["drum_snare"]) > s0 and len(e.heard["tick16"]) > t0 and max(e.heard["drum_snare"][s0:]) > 0.25:
            snares_at.append((b if (k + 1) % 16 else b + 1, int(e.heard["tick16"][-1])))
    return [any(bb == b and tt == spot for bb, tt in snares_at) for b in range(bars)]
hit6 = learned_spots({1, 2, 3}, 11)
check(hit6[2] and hit6[3] and hit6[4] and not any(hit6[8:]) and not hit6[0] and not hit6[1],
      "learned groove: claps on one off-beat teach the snare that spot, then it fades (snare on that spot per bar: %s)"
      % "".join("x" if h else "." for h in hit6))

# input shaping: the gate's own fast meter, hysteresis, hold, attack and release; the compressor's attack and release
def db_tone(db, secs, f=1000):
    return sine(f, np.sqrt(2) * 10 ** (db / 20), secs)
def gain_curve(segments, **over):
    """Plays tone segments [(dB rms, seconds), ...] and returns (times of the steps, the output/input gain every 1 ms)."""
    e = fresh(wet=0, **over)
    x = np.concatenate([db_tone(d, t) for d, t in segments]); y = e.run(x)[:, 0]
    lv = np.repeat([10 ** (d / 20) for d, t in segments], [int(t * SR) for d, t in segments])
    w = int(0.001 * SR); n = len(y) // w
    g = np.array([rms(y[i * w:(i + 1) * w]) / max(lv[i * w], 1e-9) for i in range(n)])
    steps = np.cumsum([0] + [t for _, t in segments])
    return steps, g
def crossing(g, start_ms, level, falling):
    for i in range(int(start_ms), len(g)):
        if (g[i] <= level) if falling else (g[i] >= level):
            return i
    return None
def gate_times(**over):
    steps, g = gain_curve([(-60, 0.5), (-20, 0.6), (-55, 1.5)], gate_thresh=-40, comp_thresh=0, **over)
    up, dn = steps[1] * 1000, steps[2] * 1000
    o10, o90 = crossing(g, up, 0.1, False), crossing(g, up, 0.9, False)
    c90, c10 = crossing(g, dn + 3, 0.9, True), crossing(g, dn + 3, 0.1, True)
    return o10 - up, o90 - o10, c90 - dn, c10 - c90
d_open, rise, hold, fall = gate_times()
check(d_open <= 8 and rise <= 8 and hold <= 20 and 45 <= fall <= 85,   # (hold = until the fade crosses 90%)
      "gate shape: the defaults behave as before (opens %d ms after the sound, rises in %d ms, lets go %d ms after, fades in %d ms)" % (d_open, rise, hold, fall))
d_open, rise, hold, fall = gate_times(gate_attack=30, gate_hold=150, gate_release=400)
check(d_open <= 8 and 18 <= rise <= 32 and 180 <= hold <= 215 and 280 <= fall <= 360,   # hold + meter + 10% of the fade
      "gate shape: attack 30, hold 150, release 400 ms (rises in %d ms, holds %d ms, fades in %d ms)" % (rise, hold, fall))
segs = [(-60, 0.3)] + [(-39 if k % 2 == 0 else -42, 0.03) for k in range(40)]   # hovering at the threshold
steps, g = gain_curve(segs, gate_thresh=-40, comp_thresh=0)
# (the output lags the input ~1.5 ms, so the first 5 ms of each 30 ms level are left out of the measure)
after = np.concatenate([g[int(a * 1000) + 5:int(a * 1000) + 30] for a in steps[2:-1]])
check(np.min(after) > 0.8, "gate shape: a level hovering 1-2 dB around the threshold doesn't flutter (lowest gain %.2f)" % np.min(after))
def comp_times(**over):
    steps, g = gain_curve([(-40, 0.5), (-10, 0.6), (-40, 0.8)], gate_thresh=-80, comp_thresh=-30, comp_ratio=4, **over)
    up, dn = steps[1] * 1000, steps[2] * 1000
    half = 10 ** (-7.5 / 20)                                       # halfway (in dB) to the 15 dB squeeze
    squeeze = crossing(g, up + 5, half, True) - up                  # (from 5 ms: the output lags the input a little)
    letgo = crossing(g, dn + 5, half, False) - dn
    return squeeze, letgo
sq_def, lg_def = comp_times()
sq_fast, lg_slow = comp_times(comp_attack=3, comp_release=400)
sq_slow, lg_fast = comp_times(comp_attack=150, comp_release=15)
# (letting go can't be much quicker than the 21 ms meter window lets the level fall)
check(sq_fast < 0.6 * sq_def and sq_slow > 1.6 * sq_def and lg_fast < lg_def and lg_slow > 1.6 * lg_def,
      "compressor shape: halfway squeeze in %d ms (attack 3) / %d (40, default) / %d (150); let go in %d (release 15) / %d (40) / %d (400)"
      % (sq_fast, sq_def, sq_slow, lg_fast, lg_def, lg_slow))

# glitch cloud: a sudden sound comes back mangled; each kind does what it says
GC_KINDS = ("gc_pct_stutter", "gc_pct_reverse", "gc_pct_shuffle", "gc_pct_stretch")
def gc_run(x, kind=None, steps=None, **over):
    """The glitch cloud alone (dry, echo and music off), with only `kind` switched on. Returns the left+right output
    and the kinds that fired. steps: seconds between footsteps, sent from the start."""
    base = dict(dry=0, wet=0, gc_amount=1, gc_level=1, reverb_mix=0)
    if kind:
        base.update({k: 100 * (k == kind) for k in GC_KINDS})
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
def glitch_part(y, at=3.0, thr=0.01, gap=0.05):
    """Where the first glitch plays: from its first sound after the burst until it goes quiet for `gap` s (a free-clock
    glitch may follow later, depending on the random state the earlier tests leave)."""
    a = np.abs(y[int(at * SR):]); idx = np.nonzero(a > thr)[0]
    if not len(idx):
        return np.zeros(1), None
    jumps = np.nonzero(np.diff(idx) > gap * SR)[0]
    end = idx[jumps[0]] if len(jumps) else idx[-1]
    return y[int(at * SR) + idx[0]:int(at * SR) + end], idx[0] / SR
y0, m0 = gc_run(burst_in(chirp), gc_amount=0)
check(rms(y0) < 1e-4 and not m0, "glitch cloud: Amount 0 plays nothing (%.6f, %s)" % (rms(y0), m0))
y, m = gc_run(burst_in(chirp), "gc_pct_reverse"); g, _ = glitch_part(y); q = len(g) // 4
check(m[:1] == [1] and len(g) > 0.1 * SR and centroid(g[:q]) > 1.3 * centroid(g[-q:]),      # (2L: 0.12-0.36 s)
      "glitch cloud: reverse plays a rising sound falling (centroid %.0f -> %.0f Hz, %s)" % (centroid(g[:q]), centroid(g[-q:]), m))
zc = lambda v: np.mean(np.abs(np.diff(np.sign(v)))) * SR / 2
y, m = gc_run(burst_in(steady), "gc_pct_stutter"); g, _ = glitch_part(y)
check(m[:1] == [0] and len(g) > 0.2 * SR, "glitch cloud: a stutter repeats the sound (%.2f s, %s)" % (len(g) / SR, m))
jump = np.max(np.abs(np.diff(y))) if len(y) > 1 else 0
check(jump < 0.15 * max(np.max(np.abs(y)), 1e-9) + 0.01, "glitch cloud: no clicks where a stutter jumps back (%.3f of peak %.3f)" % (jump, np.max(np.abs(y))))
bed = burst_in(steady); bed += (0.05 * np.sin(2 * np.pi * 300 * np.arange(len(bed)) / SR)).astype(np.float32)   # a room that isn't silent
y, m = gc_run(bed, "gc_pct_shuffle")
check(m[:1] == [2] and rms(y[int(3.0 * SR):]) > 0.005, "glitch cloud: shuffle plays a slice of the last few seconds (%s, rms %.4f)" % (m, rms(y[int(3.0 * SR):])))
y, m = gc_run(burst_in(steady, total=8.0), "gc_pct_stretch"); g, _ = glitch_part(y, thr=0.02)
held = g[int(0.4 * SR):int(1.0 * SR)] if len(g) > SR else np.zeros(4)
pitch = zc(held) / 2                                          # (zc counts the crossings both ways: twice the pitch)
check(m[:1] == [3] and len(g) > 1.0 * SR and 800 < pitch < 1250,   # a 0.3 s sound, 3x+ longer
      "glitch cloud: stretch smears a 0.3 s sound over %.1f s at its own pitch (%.0f Hz, %s)" % (len(g) / SR, pitch, m[:3]))
# the free clock: a steady sound with no sudden start still gets a glitch now and then
rng = np.random.default_rng(9); fade = np.minimum(np.arange(12 * SR) / (3 * SR), 1)
hum12 = (rng.standard_normal(12 * SR) * 0.05 * fade).astype(np.float32)
y, m = gc_run(hum12)
check(len(m) >= 1 and rms(y[4 * SR:]) > 0.002, "glitch cloud: with no sudden sounds the free clock still glitches (%d in 12 s)" % len(m))
# walking: a sudden sound waits for the next step or half-step
y, m = gc_run(burst_in(steady, at=3.1), "gc_pct_stutter", steps=0.5)
_, start = glitch_part(y, at=3.1, thr=0.05)
check(start is not None and 0.15 <= start <= 0.18,   # the half-step at +0.15 s, a 5 ms fade, a few ms of pre-roll
      "glitch cloud: while walking it lands on the half-step (%.3f s after the sound, wanted 0.15-0.18)" % (start or -1))
# the glitch matrix: each kind gets its share of the chances; what is left over is silence
def matrix(**pct):
    e = fresh(dry=0, wet=0, gc_amount=1, gc_level=1, reverb_mix=0, **dict({k: 0 for k in GC_KINDS}, **pct))
    e.listen("gc_mode", "gc_try")
    rng = np.random.default_rng(8); x = rng.standard_normal(90 * SR) * 0.003
    for k in range(60):                                         # a sudden sound every 1.5 s
        i = int((1.0 + 1.5 * k) * SR); n = int(0.05 * SR); x[i:i + n] += rng.standard_normal(n) * 0.4
    e.run(x.astype(np.float32))
    modes = [int(v) for v in e.heard["gc_mode"]]; tries = len(e.heard["gc_try"])
    return modes, tries
modes, tries = matrix(gc_pct_stutter=80, gc_pct_reverse=20)
share = modes.count(0) / max(len(modes), 1)
check(tries >= 40 and set(modes) <= {0, 1} and 0.68 < share < 0.92 and len(modes) > 0.9 * tries,
      "glitch matrix: stutter 80%% / reverse 20%% -> %.0f%% stutter over %d glitches (%d chances)" % (100 * share, len(modes), tries))
modes, tries = matrix(gc_pct_reverse=10, gc_pct_shuffle=10)
check(tries >= 40 and set(modes) <= {1, 2} and 0.08 < len(modes) / tries < 0.35,
      "glitch matrix: reverse 10%% + shuffle 10%% -> %d glitches from %d chances (%.0f%%; the rest is silence)" % (len(modes), tries, 100 * len(modes) / tries))
modes, tries = matrix(gc_pct_stutter=100, gc_pct_reverse=100)
check(set(modes) == {0, 1} and len(modes) > 0.9 * tries, "glitch matrix: past 100%% the shares count as proportions (%d/%d stutter)" % (modes.count(0), len(modes)))

# wide: each glitch sits well out to one side (the far ear quieter and a little later)
def gc_sides(seed):
    x = burst_in(steady, seed=seed)
    e = fresh(dry=0, wet=0, gc_amount=1, gc_level=1, reverb_mix=0, gc_pct_stutter=100, gc_pct_reverse=0, gc_pct_shuffle=0, gc_pct_stretch=0)
    y = e.run(x)[int(3.0 * SR):int(3.6 * SR)]
    l, r = rms(y[:, 0]), rms(y[:, 1])
    return (l - r) / max(l + r, 1e-9)
bal = [gc_sides(s) for s in (11, 12, 13, 14, 15)]   # (now and then a free-clock glitch elsewhere overlaps the window)
# (placed 45-100% out: 45% measures ~0.29)
check(sum(abs(b) > 0.25 for b in bal) >= 4, "glitch cloud: each glitch sits well out to one side (balance %s)" % ["%.2f" % b for b in bal])

# echo scatter: each repeat lands somewhere else; at 0 the echo stays in the middle
def echo_balance(scatter):
    x = np.zeros(5 * SR, np.float32); x[SR:SR + 40] = 0.5
    e = fresh(dry=0, wet=1, feedback=0.8, echo_time=300, echo_sync=0, echo_scatter=scatter, reverb_mix=0)
    y = e.run(x); out = []
    for k in range(1, 12):
        a = int((1.0 + 0.3 * k) * SR); w = y[a - int(0.02 * SR):a + int(0.06 * SR)]
        l, r = rms(w[:, 0]), rms(w[:, 1]); out.append((l - r) / max(l + r, 1e-9))
    return out
b1, b0 = echo_balance(1), echo_balance(0)
# (the place changes every echo period at its own phase, so a window can straddle a move: most, not all, jump clearly)
moves = sum(abs(b - a) > 0.3 for a, b in zip(b1, b1[1:]))
check(moves >= 5 and max(abs(v) for v in b0) < 0.02,
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
    e = fresh(music_on=1, music_pad=0, music_arp=1, dry=1, music_react=1, **over)   # (react 1: a silent room plays no still-pattern chime)
    for _ in range(4):
        e.send("step", 0.4); e.run(e.silence(0.4))
    return rms(e.run(e.silence(3.6))[int(2.9 * SR):int(3.4 * SR), 0])   # after the longest chime fade (2.6 s), reverb still ringing
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

# ---- diagnostics: counting overloads once a second (in, after Input gain, at the output limiter) ----
def clip_counts(sig, **over):
    e = fresh(**over)
    e.listen("diag_clip_in", "diag_clip_gain", "diag_clip_out")
    e.run(sig)
    return tuple(int(sum(e.heard[k])) for k in ("diag_clip_in", "diag_clip_gain", "diag_clip_out")), len(e.heard["diag_clip_out"])
quiet, nq = clip_counts(sine(440, 0.3, 3.0), gain=2.5, dry=1, wet=0)
hot, _ = clip_counts(sine(440, 0.6, 3.0), gain=2.5, dry=1, wet=0)
over_in, _ = clip_counts(np.clip(sine(440, 1.5, 3.0), -1, 1), gain=0.5, dry=1, wet=0)
check(nq >= 2 and quiet[0] == 0 and quiet[1] == 0 and hot[0] == 0 and hot[1] > 100 and hot[2] > 100 and over_in[0] > 100 and over_in[1] == 0,
      "diagnostics count overloads: 0.3 at gain 2.5 %s, 0.6 at gain 2.5 %s, a clipped mic at gain 0.5 %s (%d reports in 3 s)" % (quiet, hot, over_in, nq))

# reverse reverb: a sudden sound comes back as its own reverb tail played backwards, a swell that rises into the
# moment of the sound, peaking 2 x its length later (or on a beat while the Rhythm runs on the tempo clock)
def rr_swell(rev=1, listen=(), **over):
    def one(r):
        e = fresh(**dict(dict(dry=1, wet=0, reverb_mix=1, reverb_size=0.5, reverb_rev=r), **over))
        if listen:
            e.listen(*listen)
        x = np.zeros(6 * SR, np.float32); n = int(0.05 * SR)
        x[SR:SR + n] = np.random.default_rng(1).standard_normal(n) * 0.3 * np.exp(-np.arange(n) / (0.01 * SR))
        t0 = len(e.heard.get("tempo", [])) if listen else 0
        return e.run(x)[:, 0], e
    a, ea = one(rev); b, _ = one(0)
    d = np.abs(a - b); env = np.convolve(d, np.ones(441) / 441, "same")
    end = int(np.max(np.nonzero(env > 0.1 * env.max())[0])) if env.max() > 0 else 0
    return env, end, ea
env, end, _ = rr_swell()
L = 600 + 900 * 0.5
rise = env[end - int(0.1 * SR):end].mean() / max(env[end - int(0.7 * SR):end - int(0.6 * SR)].mean(), 1e-9)
check(abs((end / SR - 1.0) * 1000 - 2 * L) < 120 and rise > 4 and env[:int(1.5 * SR)].max() < 1e-4,
      "reverse reverb: a clap comes back as a rising swell (x%.0f over its last 0.6 s) ending %.0f ms later (2 x %.0f)"
      % (rise, (end / SR - 1.0) * 1000, L))
env0, _, _ = rr_swell(rev=1, reverb_mix=0)
check(env0.max() < 1e-5, "reverse reverb: silent without the reverb (%.6f)" % env0.max())
# with the Rhythm on the clock the swell is a beat long and ends on a beat
def rr_synced(r):
    e = fresh(dry=1, wet=0, reverb_mix=1, reverb_size=0.5, reverb_rev=r, beat_on=1, beat_level=0.0001, beat_follow=1,
              beat_when=1, rhythm_src=0, tempo_mode=1, tempo_bpm=100)
    e.listen("tempo")
    x = np.zeros(6 * SR, np.float32); n = int(0.05 * SR)
    x[int(1.13 * SR):int(1.13 * SR) + n] = np.random.default_rng(1).standard_normal(n) * 0.3 * np.exp(-np.arange(n) / (0.01 * SR))
    out, beats, step = [], [], int(0.01 * SR) // 64 * 64
    for i in range(0, len(x) - step + 1, step):
        k = len(e.heard["tempo"]); out.append(e.run(x[i:i + step])[:, 0])
        if len(e.heard["tempo"]) > k:
            beats.append(i / SR)
    return np.concatenate(out), beats
ys1, beats = rr_synced(1); ys0, _ = rr_synced(0)
ds = np.convolve(np.abs(ys1[:len(ys0)] - ys0[:len(ys1)]), np.ones(441) / 441, "same")
end_s = np.max(np.nonzero(ds > 0.1 * ds.max())[0]) / SR if ds.max() > 1e-4 else 0
off = min(abs(end_s - bt) for bt in beats) if beats else 9
check(ds.max() > 1e-3 and off < 0.03 and end_s > 1.13 + 2 * 0.6 - 0.05,
      "reverse reverb with the Rhythm: the swell ends on a beat (%.0f ms from the nearest, at %.2f s; clap at 1.13 s)" % (off * 1000, end_s))

# calm builds: at its peak the app sends calm_chimes 1, and standing still in a quiet room chimes start to come
def calm_chimes(c):
    e = fresh(music_on=1, music_arp=1, music_pad=0, music_res=0, wet=0); e.listen("chime_note")
    e.send("calm_chimes", c); e.run((np.random.default_rng(5).standard_normal(30 * SR) * 0.0005).astype(np.float32))
    return len(e.heard["chime_note"])
cq0, cq1 = calm_chimes(0), calm_chimes(1)
check(cq0 == 0 and 2 <= cq1 <= 12, "calm build: a quiet room stays quiet (%d chimes in 30 s), at the build's peak a few soft chimes come (%d)" % (cq0, cq1))

# stem packs: a loop plays at its file's own speed (any sample rate), locked to the tempo clock's bars, fading in over a bar
import wave, tempfile
def stem_run(rate, bars=1, lock=True):
    d = tempfile.mkdtemp(); p = os.path.join(d, "s.wav")
    n = int(rate * bars * 2.0); t = np.arange(n) / rate
    w = wave.open(p, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
    w.writeframes((0.5 * np.sin(2 * np.pi * 220 * t) * 32767).astype(np.int16).tobytes()); w.close()
    e = fresh(dry=0, wet=0, beat_level=0, tempo_mode=2 if lock else 0, tempo_bpm=120, stems_level=1)
    e.send("stem_on", 1); e.send_list("stem_file", 0, p); e.send_list("stem_bars", 0, bars); e.send_list("stem_lvl", 0, 1); e.send("stem_start", 1)
    return e.run(np.zeros(SR * 8, np.float32))[:, 0]
ys44, ys22 = stem_run(44100), stem_run(22050)
def peak(y): S = np.abs(np.fft.rfft(y)); return float(np.fft.rfftfreq(len(y), 1 / SR)[np.argmax(S)])
envs = [rms(ys44[i:i + SR // 20]) for i in range(5 * SR, 8 * SR - SR // 20, SR // 20)]
check(abs(peak(ys44[5 * SR:]) - 220) < 1 and abs(peak(ys22[5 * SR:]) - 220) < 1 and min(envs) > 0.9 * max(envs) and rms(ys44[:SR // 2]) < rms(ys44[5 * SR:]) / 3,
      "stems: a 220 Hz loop plays at 220 Hz from a 44.1 or a 22.05 kHz file, fades in over its first bar, and loops with no gap (level %.3f-%.3f)" % (min(envs), max(envs)))
e = fresh(stems_level=1); e.send("stem_on", 1); e.send_list("stem_lvl", 0, 1)
check(rms(e.run(e.silence(2))[:, 0]) < 1e-6, "stems: nothing loaded plays nothing")

# call and response: the pitch tracker runs for it even with Harmony at 0 and reports each steady note as a scale step
def heard(answer):
    e = fresh(music_on=1, music_pad=0, music_arp=0, music_res=0, wet=0, music_harm=0, music_answer=answer)
    e.listen("heard_deg", "harm_deg"); e.run(hum(164.81, 1.0)); return [int(v) for v in e.heard["heard_deg"]], e.heard["harm_deg"]
h1, h0 = heard(1), heard(0)
check(h1[0] == [2] and not h0[0], "call and response: a sung E3 is heard as step 2 in C major (%s); at 0 (and Harmony 0) nothing is tracked (%s)" % (h1[0], h0[0]))

# rustle: cloth rubbing on the mic (noisy, in bursts, above the room) is recognised and turned down; a fan, a voice,
# claps, a chord and speech are not rustle
_rr = np.random.default_rng(7)
def _band(n, lo, hi):
    S = np.fft.rfft(_rr.standard_normal(n)); f = np.fft.rfftfreq(n, 1 / SR); S[(f < lo) | (f > hi)] = 0
    x = np.fft.irfft(S, n); return x / np.std(x)
def _quiet(secs): return _rr.standard_normal(int(secs * SR)) * 0.0005
def _rustle(secs, amp=0.05):
    n = int(secs * SR); x = _band(n, 400, 9000); env = np.zeros(n); i = 0
    while i < n:
        L = int(_rr.uniform(0.04, 0.2) * SR); g = int(_rr.uniform(0.01, 0.12) * SR); m = min(L, n - i)
        env[i:i + m] = _rr.uniform(0.3, 1.0) * np.hanning(2 * m)[:m] ** 0.3; i += L + g
    return x * env * amp
def _voice(secs, f=196, amp=0.1):
    t = np.arange(int(secs * SR)) / SR; ph = 2 * np.pi * np.cumsum(f * (1 + 0.01 * np.sin(2 * np.pi * 5 * t))) / SR
    return amp * (np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.3 * np.sin(3 * ph)) * np.minimum(1, t * 10)
def _speech(secs, amp=0.08):
    n = int(secs * SR); x = np.zeros(n); i = 0
    while i < n - SR // 2:
        L = int(_rr.uniform(0.12, 0.25) * SR); v = _voice(L / SR, _rr.uniform(110, 160), amp)[:L]; x[i:i + len(v)] += v * np.hanning(len(v)); i += L
        if _rr.random() < 0.3:
            k = int(0.1 * SR); x[i:i + k] += _band(k, 4000, 9000) * amp * 0.3 * np.hanning(k); i += k
        i += int(_rr.uniform(0.05, 0.15) * SR)
    return x
def _claps(secs, gap=0.8, amp=0.4):
    n = int(secs * SR); x = np.zeros(n); k = int(0.12 * SR)
    for i in range(int(0.3 * SR), n - k, int(gap * SR)): x[i:i + k] += _band(k, 800, 3500) * np.exp(-np.arange(k) / (0.02 * SR)) * amp
    return x
_rustle_cases = {"rustle": _rustle, "fan": lambda s: _band(int(s * SR), 200, 6000) * 0.03, "voice": _voice, "claps": _claps,
                 "chord": lambda s: 0.05 * sum(np.sin(2 * np.pi * f * np.arange(int(s * SR)) / SR) for f in (261.6, 329.6, 392, 523.3)),
                 "speech": _speech}
def rustle_run(make, guard=0.5):
    e = fresh(gain=2.5, dry=1, wet=0, rustle_guard=guard); e.listen("rustle_on")
    x = np.concatenate([_quiet(3), make(6) + _quiet(6), _quiet(2)]).astype(np.float32)
    return e.heard["rustle_on"], e.run(x)[:, 0]
found = {k: rustle_run(f)[0][:1] == [1.0] for k, f in _rustle_cases.items()}
check(found["rustle"] and not any(v for k, v in found.items() if k != "rustle"),
      "rustle: recognised in bursty cloth-like noise, not in a fan, a voice, claps, a chord or speech %s" % found)
check(not rustle_run(_rustle, 0)[0], "rustle: with the Rustle filter at 0 (its default: shelved, experimental) nothing is detected")

# Mix: each part's level at 0 takes that part out, and only that part
def mix_part(trim, value, x, steps=0.0, **over):
    e = fresh(**dict(dict(dry=0, wet=0, music_pad=0, music_arp=0, music_res=0, music_harm=0, melody_src=0), **over))
    e.send(trim, value); e.run(e.silence(0.3))
    if not steps:
        return rms(e.run(x)[SR:, 0])
    ys = [e.run(x[k:k + int(steps * SR)])[:, 0] for k in range(0, len(x) - int(steps * SR) + 1, int(steps * SR)) if e.send("step", steps) is None]
    return rms(np.concatenate(ys)[SR:])
quiet8 = (np.random.default_rng(3).standard_normal(8 * SR) * 0.0005).astype(np.float32)
cl6 = claps(5, 1.1, 0.5)
mix_cases = {
    "kick": ("mix_kick", quiet8, 0, dict(beat_level=1, beat_follow=1, beat_when=1, rhythm_src=0, beat_snare=0, beat_hats=0, beat_glitch=0)),
    "bass": ("mix_bass", quiet8, 0, dict(music_on=1, music_pad=1, music_pad_reg=0, pad_src=0, bass_src=0)),
    "walking notes": ("mix_walk", quiet8, 0.5, dict(music_on=1, music_arp=1, beat_follow=0)),
    "chimes": ("mix_chimes", cl6, 0, dict(music_on=1, music_arp=1, music_react=1)),
    "room notes ring": ("mix_ring", cl6, 0, dict(music_on=1, music_res=1, res_src=0)),
    "found bells": ("mix_bells", cl6, 0, dict(music_on=1, music_res=1, res_src=1, chime_char=0)),
}
res = {}
for name, (trim, x, st, over) in mix_cases.items():
    res[name] = (mix_part(trim, 1, x, st, **over), mix_part(trim, 0, x, st, **over))
check(all(on > 0.002 and off < 0.05 * on for on, off in res.values()),
      "mix: each part at 0 is silent (rms at 1 / at 0: %s)" % {k: "%.4f/%.5f" % v for k, v in res.items()})
# ...and only that part: the walking notes' trim leaves the chimes alone
ch_on = mix_part("mix_walk", 0, cl6, 0, music_on=1, music_arp=1, music_react=1)
check(abs(ch_on / res["chimes"][0] - 1) < 0.25, "mix: the walking notes at 0 leave the chimes as they were (%.4f vs %.4f)" % (ch_on, res["chimes"][0]))

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
