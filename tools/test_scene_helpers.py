#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Checks the player-side helper abstractions scenes may use: closebang, rj_time, rj_compass, rj_loc, rj_text, rjdj.

    python3 tools/test_scene_helpers.py /path/to/libpd.so
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
scene = os.path.join(scenes, "Helpers.rj")
os.makedirs(scene)
patch = """#N canvas 0 0 600 500 10;
#X declare -path . -path rj -path ../pd -path ../../pd;
#X obj 10 10 closebang;
#X obj 10 40 s cb;
#X obj 10 70 r reqc;
#X obj 10 100 rj_compass;
#X obj 10 130 s comp;
#X obj 10 160 r reqt;
#X obj 10 190 rj_time;
#X obj 10 220 s ty;
#X obj 60 220 s thr;
#X obj 10 250 r reql;
#X obj 10 280 rj_loc;
#X obj 10 310 s lat;
#X obj 10 340 rj_text hello;
#X obj 10 370 rjdj;
#X obj 200 10 r #pdparty;
#X obj 200 40 route time compass loc;
#X msg 200 70 1;
#X msg 250 70 1;
#X msg 300 70 1;
#X obj 200 100 s reqtime;
#X obj 250 100 s reqcompass;
#X obj 300 100 s reqloc;
#X obj 200 130 soundoutput;
#X connect 0 0 1 0;
#X connect 2 0 3 0;
#X connect 3 0 4 0;
#X connect 5 0 6 0;
#X connect 6 0 7 0;
#X connect 6 6 8 0;
#X connect 9 0 10 0;
#X connect 10 0 11 0;
#X connect 14 0 15 0;
#X connect 15 0 16 0;
#X connect 15 1 17 0;
#X connect 15 2 18 0;
#X connect 16 0 19 0;
#X connect 17 0 20 0;
#X connect 18 0 21 0;
"""
open(os.path.join(scene, "_main.pd"), "w").write(patch)
e = Engine(LIB, os.path.join(scene, "_main.pd"), search_path=[os.path.join(scenes, "pd"), os.path.join(scenes, "pd", "rj")])
e.listen("cb", "comp", "ty", "thr", "lat", "reqtime", "reqcompass", "reqloc")
e.run(np.zeros(SR // 4, dtype=np.float32))
bad = [m for m in e.log if "couldn't create" in m or "error" in m.lower()]
check(not bad, "closebang, rj_compass, rj_time, rj_loc, rj_text and rjdj all create %s" % bad[:3])

e.send("#closebang", 1.0)
check(e.heard.get("cb") == [1.0], "closebang passes the player's #closebang through: %s" % e.heard.get("cb"))
e.send_list("#compass", 123.0)
check(e.heard.get("comp") == [123.0], "rj_compass outputs the #compass reading: %s" % e.heard.get("comp"))
e.send_list("#time", 2026, 10, 7, 4, 280, -400, 20, 1, 9, 250)
check(e.heard.get("ty") == [2026.0] and e.heard.get("thr") == [20.0],
      "rj_time outputs year and hour from #time: %s %s" % (e.heard.get("ty"), e.heard.get("thr")))

# a bang in each helper asks the player (through #pdparty) for the data
e.send("reqt", 1.0)
e.send("reqc", 1.0)
e.send("reql", 1.0)
e.run(np.zeros(SR // 10, dtype=np.float32))
check(e.heard.get("reqtime") == [1.0], "rj_time asks the player for the time")
check(e.heard.get("reqcompass") == [1.0], "rj_compass asks the player for a compass reading")
check(e.heard.get("reqloc") == [1.0], "rj_loc asks the player for a location")

print("ALL PASSED" if fails == 0 else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
