#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Checks the Pure Data ports of RjDj's analysis objects (rj_senergy~, rj_centroid~, rj_accum,
rj_barkflux_accum~) against the arithmetic of the original C externals.

    python3 tools/test_rj_analysis.py /path/to/libpd.so

The ports were also compared sample by sample with the C originals compiled for the desktop
(see docs/RJDJ-NOTES.md); this test keeps the same arithmetic as small numpy models.
"""
import math, os, sys, tempfile
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from pdtest import Engine, SR

LIB = sys.argv[1] if len(sys.argv) > 1 else "libpd.so"
ABS = os.path.join(os.path.dirname(__file__), "..", "app/src/main/assets/scene_lib")
f32 = np.float32
fails = 0
def check(cond, msg):
    global fails
    print(("ok:   " if cond else "FAIL: ") + msg)
    if not cond:
        fails += 1

tmp = tempfile.mkdtemp()

def run_signal(obj, signal, block="1024 1", messages=()):
    """Mic signal -> [block~] -> obj -> list of the floats the object produced."""
    path = os.path.join(tmp, "sig.pd")
    open(path, "w").write(
        "#N canvas 0 0 600 400 10;\n#X obj 10 10 adc~ 1;\n"
        "#N canvas 0 0 450 300 sub 0;\n#X obj 10 10 inlet~;\n#X obj 120 10 block~ %s;\n"
        "#X obj 10 60 %s;\n#X obj 10 90 s res;\n#X obj 200 10 r msgs;\n"
        "#X connect 4 0 2 0;\n#X connect 0 0 2 0;\n#X connect 2 0 3 0;\n"
        "#X restore 10 40 pd sub;\n#X connect 0 0 1 0;\n" % (block, obj))
    e = Engine(LIB, path, search_path=[ABS])
    e.listen("res")
    for sel, val in messages:
        e.send_msg("msgs", sel, val)
    for i in range(0, len(signal), 6400):
        e.run(signal[i:i + 6400])
    out = np.array(e.heard["res"])
    errors = [l for l in e.log if "error" in l or "couldn't" in l]
    e.close()
    return out, errors

def run_floats(obj, values, messages=()):
    """Floats -> obj -> list of the floats it produced (messages are sent first)."""
    path = os.path.join(tmp, "flt.pd")
    open(path, "w").write(
        "#N canvas 0 0 400 300 10;\n#X obj 10 10 r in;\n#X obj 10 40 %s;\n#X obj 10 70 s res;\n"
        "#X obj 100 10 r msgs;\n#X connect 0 0 1 0;\n#X connect 1 0 2 0;\n#X connect 3 0 1 0;\n" % obj)
    e = Engine(LIB, path, search_path=[ABS])
    e.listen("res")
    for sel, val in messages:
        e.send_msg("msgs", sel, val)
    for v in values:
        e.send("in", v)
    out = np.array(e.heard["res"])
    errors = [l for l in e.log if "error" in l or "couldn't" in l]
    e.close()
    return out, errors

# ---- rj_senergy~: mean square of the first 513 samples
out, err = run_signal("rj_senergy~", np.full(SR // 2, 0.5, np.float32))
check(not err and len(out) > 10, "rj_senergy~ loads and reports once per block")
check(abs(out[-1] - 0.25) < 1e-6, "rj_senergy~ of a constant 0.5 is 0.25")
out, _ = run_signal("rj_senergy~", np.zeros(SR // 4, np.float32))
check(np.all(out == 0), "rj_senergy~ of silence is 0")

# ---- rj_centroid~: sum(j * x[j]) / sum(x[j]) * samplerate / 513 over 513 bins
out, err = run_signal("rj_centroid~", np.ones(SR // 2, np.float32))
want = 256.0 * SR / 513
check(not err and abs(out[-1] - want) < want * 1e-4, "rj_centroid~ of a flat spectrum is %.1f Hz (got %.1f)" % (want, out[-1]))
out, _ = run_signal("rj_centroid~", np.zeros(SR // 4, np.float32))
check(np.all(out == 0), "rj_centroid~ of silence is 0")

# ---- rj_accum: relative change of a short mean against a long mean (ring-buffer model of the C code)
def accum_model(values, hop=512, st=5.0, lt=30.0):
    class Ring:
        def __init__(s, seconds):
            s.n = max(2, int(f32(seconds) * f32(SR) / f32(hop)))
            s.buf = np.zeros(s.n, np.float32); s.total = f32(0); s.idx = 0; s.cnt = 0
        def push(s, x):
            if s.cnt < s.n - 1:
                s.cnt += 1
            s.total = f32(s.total - s.buf[s.idx]) + f32(x)
            s.buf[s.idx] = x
            s.idx = (s.idx + 1) % s.n
            return s.total / f32(s.cnt)
    a, b = Ring(st), Ring(lt)
    out = []
    for x in values:
        m1, m2 = a.push(x), b.push(x)
        out.append(0.0 if m2 == 0 else (m1 - m2) / m2)
    return np.array(out)

rng = np.random.default_rng(7)
values = np.abs(rng.standard_normal(1500)) * np.repeat([0.2, 1.0, 0.1], 500)
for obj, msgs, kw in (("rj_accum 512", [], {}),
                      ("rj_accum", [("st", 0.5), ("lt", 3.0)], {"st": 0.5, "lt": 3.0}),
                      ("rj_accum 0.25 20", [], {})):     # more than one argument: defaults
    out, err = run_floats(obj, values, msgs)
    ok = not err and len(out) == len(values) and np.allclose(out, accum_model(values, **kw), atol=1e-4)
    check(ok, "[%s] matches the C ring-buffer arithmetic" % obj)
out, _ = run_floats("rj_accum 512", np.full(50, 0.7), [])
check(np.allclose(out, 0, atol=1e-6), "rj_accum of a constant input has no relative change")

# ---- rj_barkflux_accum~: 12 Bark bands, sum of squares per band, short vs long running averages
def freq2bark(x): return f32(26.81) / (f32(1) + f32(1960) / f32(x)) - f32(0.53)
def bark2freq(z): return f32(1960) / (f32(26.81) / (f32(z) + f32(0.53)) - f32(1))
def bands(sr):
    zb, ze = freq2bark(40), freq2bark(8000)
    bw = (ze - zb) / f32(12)
    edge = lambda k: int(math.ceil((513 * 2 * float(bark2freq(zb + bw * f32(k)))) / sr))
    return [(edge(i), edge(i + 1) - edge(i) + 1) for i in range(12)]

def flux_model(levels, sr=SR):
    band = bands(sr)
    nst, nlt = int(5 * sr / 1024), int(30 * sr / 1024)
    st = np.zeros(12, np.float32); lt = np.zeros(12, np.float32); cs = cl = 0
    out = []
    for v in levels:
        en = np.array([n * f32(v) * f32(v) / f32(513) for _, n in band], np.float32)
        if cs < nst - 1: cs += 1
        if cl < nlt - 1: cl += 1
        st = st * f32(cs / (cs + 1)) + en * f32(1 / (cs + 1))
        lt = lt * f32(cl / (cl + 1)) + en * f32(1 / (cl + 1))
        out.append(float(np.sum((st - lt) ** 2)))
    return np.array(out)

levels = np.repeat([0.1, 0.5, 0.05], 300)
signal = np.repeat(levels, 1024).astype(np.float32)
out, err = run_signal("rj_barkflux_accum~", signal)
want = flux_model(levels)
best = min((np.abs(out[s:s + 800] - want[:800]).max() if len(out) >= s + 800 else 1e9) for s in range(3))
check(not err and len(out) >= 800, "rj_barkflux_accum~ loads and reports once per block")
check(best < want.max() * 2e-2, "rj_barkflux_accum~ follows the C arithmetic (worst error %.2g of %.2g)" % (best, want.max()))
check(want.max() > 0 and out.max() > 0, "rj_barkflux_accum~ reacts to a level change")

print("\n%s" % ("all passed" if fails == 0 else "%d FAILED" % fails))
sys.exit(1 if fails else 0)
