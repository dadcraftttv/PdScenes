#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Checks the scene objects for on-screen images and text (rj_image, rj_text: their messages reach the app on
rj_gfx, tagged with the object) and the stand-ins for externals some scenes use (declip, avg~, aubiopitch~, keys).

    python3 tools/test_scene_graphics.py /path/to/libpd.so
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
scene = os.path.join(scenes, "Graphics.rj")
os.makedirs(scene)
patch = """#N canvas 0 0 600 500 10;
#X declare -path . -path rj -path ../pd -path ../pd/rj;
#X obj 10 10 rj_image smiley.png;
#X obj 200 10 rj_text hello there;
#X obj 10 40 r img;
#X obj 200 40 r txt;
#X obj 10 100 adc~;
#X obj 10 130 aubiopitch~;
#X obj 10 160 s pitch;
#X obj 200 100 r dc;
#X obj 200 130 declip;
#X obj 200 160 snapshot~;
#X obj 280 100 r dcsnap;
#X obj 200 190 s dcout;
#X obj 400 100 osc~ 0.5;
#X obj 400 130 avg~;
#X obj 400 160 s avg;
#X obj 400 190 keys;
#X obj 280 130 t b;
#X connect 2 0 0 0;
#X connect 3 0 1 0;
#X connect 4 0 5 0;
#X connect 5 0 6 0;
#X connect 7 0 8 0;
#X connect 8 0 9 0;
#X connect 10 0 16 0;
#X connect 16 0 9 0;
#X connect 9 0 11 0;
#X connect 12 0 13 0;
#X connect 13 0 14 0;
"""
open(os.path.join(scene, "_main.pd"), "w").write(patch)
# listen first, then open the scene (the app subscribes before it opens one, so it hears what the objects say at load)
blank = os.path.join(tmp, "blank.pd"); open(blank, "w").write("#N canvas 0 0 100 100 10;\n")
e = Engine(LIB, blank, search_path=[os.path.join(scenes, "pd"), os.path.join(scenes, "pd", "rj")])
e.listen("rj_gfx", "pitch", "dcout", "avg")
import ctypes
e.lib.libpd_openfile.restype = ctypes.c_void_p
assert e.lib.libpd_openfile(b"_main.pd", scene.encode())
e.run(np.zeros(SR // 10, dtype=np.float32))
bad = [m for m in e.log if "couldn't create" in m or "error" in m.lower()]
check(not bad, "rj_image, rj_text, aubiopitch~, declip, avg~ and keys all create %s" % bad[:3])

# at load each says what it is: the image its file, the text its words (with its own id first)
got = e.lists.get("rj_gfx", [])
kinds = {tuple(l[1:]) for l in got}
check(("image", "smiley.png") in kinds and ("text", "hello", "there") in kinds and all(isinstance(l[0], float) for l in got),
      "at load: the image names its file and the text its words, each tagged with its id: %s" % got)
ids = {l[1]: l[0] for l in got}
e.lists["rj_gfx"] = []
e.send_msg("img", "move", 100, 200)
e.send_msg("img", "visible", 1)
e.send_msg("txt", "text", 42)
e.send_msg("txt", "size", 22)
got = e.lists.get("rj_gfx", [])
want = [[ids["image"], "move", 100.0, 200.0], [ids["image"], "visible", 1.0], [ids["text"], "text", 42.0], [ids["text"], "size", 22.0]]
check(got == want, "messages to them reach the app tagged with their id: %s" % got)

# aubiopitch~ hears an A4 as MIDI 69, and nothing in silence
x = (0.3 * np.sin(2 * np.pi * 440 * np.arange(2 * SR) / SR)).astype(np.float32)
e.heard["pitch"] = []
e.run(np.zeros(SR // 2, np.float32)); quiet = len(e.heard["pitch"])
e.run(x)
p = e.heard["pitch"]
check(quiet == 0 and len(p) >= 10 and abs(np.median(p) - 69) < 0.3,
      "aubiopitch~ stand-in: silence gives nothing (%d), a 440 Hz tone MIDI %.2f (%d readings)" % (quiet, np.median(p) if p else 0, len(p)))

# declip turns a number into a signal that glides there; avg~ gives a number about every 10 ms
e.send("dc", 0.8); e.run(np.zeros(SR // 20, np.float32)); e.send("dcsnap", 1)
e.run(np.zeros(64, np.float32))
check(e.heard["dcout"] and abs(e.heard["dcout"][-1] - 0.8) < 1e-3, "declip stand-in: 0.8 becomes a signal at 0.8 (%s)" % e.heard["dcout"][-1:])
e.heard["avg"] = []; e.run(np.zeros(SR, np.float32))
a = e.heard["avg"]
check(80 <= len(a) <= 120 and 0 < max(a) <= 1, "avg~ stand-in: a number about every 10 ms (%d a second, up to %.2f)" % (len(a), max(a) if a else 0))

print("ALL PASSED" if fails == 0 else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
