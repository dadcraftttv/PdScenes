#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Checks that an RjDj-style scene runs against the player's soundinput/soundoutput abstractions.

    python3 tools/test_scene_loader.py /path/to/libpd.so

Builds a throwaway scenes folder the way the app lays it out (scenes/pd/ for the player's
abstractions, scenes/Test.rj/ for the scene, with its own rj/ folder) and opens the scene.
"""
import os, shutil, sys, tempfile
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from pdtest import Engine, SR

ROOT = os.path.join(os.path.dirname(__file__), "..")
LIB_ASSETS = os.path.join(ROOT, "app/src/main/assets/scene_lib")
LIB = sys.argv[1] if len(sys.argv) > 1 else "libpd.so"

fails = 0
def check(cond, msg):
    global fails
    print(("ok:   " if cond else "FAIL: ") + msg)
    if not cond:
        fails += 1

tmp = tempfile.mkdtemp()
scenes = os.path.join(tmp, "scenes")
shutil.copytree(LIB_ASSETS, os.path.join(scenes, "pd"))
scene = os.path.join(scenes, "Test.rj")
os.makedirs(os.path.join(scene, "rj"))
# A scene's own abstraction, found through "declare -path rj".
open(os.path.join(scene, "rj", "half.pd"), "w").write(
    "#N canvas 0 0 300 200 10;\n#X obj 10 10 inlet~;\n#X obj 10 40 *~ 0.5;\n#X obj 10 70 outlet~;\n"
    "#X connect 0 0 1 0;\n#X connect 1 0 2 0;\n")
# The header every RjDj scene starts with, then mic -> half -> speakers.
open(os.path.join(scene, "_main.pd"), "w").write(
    "#N canvas 0 0 450 300 10;\n"
    "#X declare -path . -path rj -path ../pd -path ../../pd;\n"
    "#X obj 10 10 soundinput;\n#X obj 10 50 half;\n#X obj 10 90 soundoutput;\n"
    "#X connect 0 0 1 0;\n#X connect 1 0 2 0;\n#X connect 1 0 2 1;\n")

e = Engine(LIB, os.path.join(scene, "_main.pd"))
x = (0.4 * np.sin(2 * np.pi * 440 * np.arange(SR) / SR)).astype(np.float32)
y = e.run(x)
tail = slice(SR // 2, SR)
ratio = float(np.abs(y[tail, 0]).max() / np.abs(x[tail]).max())
check(not [m for m in e.log if "couldn't create" in m or "error" in m.lower()], "scene opens with no Pd errors: %s" % e.log[-3:])
check(abs(ratio - 0.5) < 0.02, "mic reaches the speakers through soundinput/half/soundoutput (gain %.3f, expected 0.5)" % ratio)
check(np.allclose(y[tail, 0], y[tail, 1], atol=1e-6), "left and right both carry the signal")

loud = (3.0 * np.sin(2 * np.pi * 300 * np.arange(SR // 2) / SR)).astype(np.float32)
over = e.run(loud)
check(float(np.abs(over).max()) <= 1.0 + 1e-6, "soundoutput limits to +-1 (peak %.3f)" % float(np.abs(over).max()))

# player controls: #volume, #micvolume, #transport
def level(sig):
    return float(np.abs(e.run(sig)[-4000:, 0]).max())
tone = (0.4 * np.sin(2 * np.pi * 440 * np.arange(SR) / SR)).astype(np.float32)
base = level(tone)
e.send_msg("#volume", "set", 0.5)
check(abs(level(tone) / base - 0.5) < 0.03, "#volume set 0.5 halves the output (%.3f -> %.3f)" % (base, level(tone)))
e.send_msg("#volume", "set", 1)
e.send_msg("#micvolume", "x") if False else e.send("#micvolume", 0.25)
check(abs(level(tone) / base - 0.25) < 0.03, "#micvolume 0.25 scales the microphone to a quarter (ratio %.3f)" % (level(tone) / base))
e.send("#micvolume", 1)
e.send_msg("#transport", "play", 0)
check(level(tone) < 1e-4, "#transport play 0 mutes the output (%.5f)" % level(tone))
e.send_msg("#transport", "play", 1)
check(abs(level(tone) / base - 1.0) < 0.03, "#transport play 1 brings it back at the same volume (ratio %.3f)" % (level(tone) / base))
e.send_msg("#volume", "set", 0.5); e.send_msg("#transport", "play", 0); e.send_msg("#transport", "play", 1)
check(abs(level(tone) / base - 0.5) < 0.03, "pausing and resuming keeps the chosen volume (ratio %.3f)" % (level(tone) / base))
e.send_msg("#volume", "set", 1)

dc = e.run(np.full(SR, 0.3, np.float32))
check(abs(float(dc[-2000:, 0].mean())) < 0.01, "soundinput removes DC offset (%.4f left)" % float(dc[-2000:, 0].mean()))

# ---- the bundled [rjdispatch] and [rjloader] ----
disp = os.path.join(scenes, "Dispatch.rj")
os.makedirs(disp)
open(os.path.join(disp, "_main.pd"), "w").write("""#N canvas 0 0 450 300 10;
#X obj 10 10 rjloader some-module 0;
#X obj 10 40 r in;
#X obj 10 70 rjdispatch scene attack;
#X obj 10 100 rjdispatch scene decay;
#X obj 10 130 route release;
#X obj 10 160 s other;
#X obj 150 70 r scene-attack;
#X obj 150 100 s got_attack;
#X obj 250 70 r scene-decay;
#X obj 250 100 s got_decay;
#X connect 1 0 2 0;
#X connect 2 0 3 0;
#X connect 3 0 4 0;
#X connect 4 0 5 0;
#X connect 6 0 7 0;
#X connect 8 0 9 0;
""")
e = Engine(LIB, os.path.join(disp, "_main.pd"), search_path=[os.path.join(scenes, "pd"), os.path.join(scenes, "pd", "rj")])
e.listen("got_attack", "got_decay", "other")
e.send_msg("in", "attack", 5)
e.send_msg("in", "decay", 7)
e.send_msg("in", "release", 9)
e.run(e.silence(0.05))
check(e.heard["got_attack"] == [5.0] and e.heard["got_decay"] == [7.0], "[rjdispatch] sends matching messages to name-key, key removed: %s %s" % (e.heard["got_attack"], e.heard["got_decay"]))
check(e.heard["other"] == [9.0], "unmatched messages pass through the outlet to the next object: %s" % e.heard["other"])
e.close()

shutil.rmtree(tmp)
print("ALL PASSED" if fails == 0 else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
