#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Checks the RjDj sensor messages (#accelerate, #touch) reach a scene as the app sends them.

    python3 tools/test_scene_sensors.py /path/to/libpd.so [path/to/GhostWave.rj]

The optional second argument is a real scene folder; if given, the test also shakes it and checks that it
starts making sound. (Scenes are not bundled with this project: use one you imported.)
"""
import os, shutil, sys, tempfile
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from pdtest import Engine, SR

ROOT = os.path.join(os.path.dirname(__file__), "..")
LIB_ASSETS = os.path.join(ROOT, "app/src/main/assets/scene_lib")
LIB = sys.argv[1] if len(sys.argv) > 1 else "libpd.so"
REAL = sys.argv[2] if len(sys.argv) > 2 else None

fails = 0
def check(cond, msg):
    global fails
    print(("ok:   " if cond else "FAIL: ") + msg)
    if not cond:
        fails += 1

tmp = tempfile.mkdtemp()
scenes = os.path.join(tmp, "scenes")
shutil.copytree(LIB_ASSETS, os.path.join(scenes, "pd"))

# ---- a scene that just forwards what it receives ----
scene = os.path.join(scenes, "Sensors.rj")
os.makedirs(scene)
open(os.path.join(scene, "_main.pd"), "w").write("""#N canvas 0 0 450 300 10;
#X obj 10 10 r #accelerate;
#X obj 10 40 unpack f f f;
#X obj 10 70 s ax;
#X obj 80 70 s ay;
#X obj 150 70 s az;
#X obj 250 10 r #touch;
#X obj 250 40 route down xy up;
#X obj 250 70 unpack f f f;
#X obj 330 70 unpack f f f;
#X obj 410 70 unpack f f f;
#X obj 250 100 s tdown_id;
#X obj 330 100 s txy_x;
#X obj 330 130 s txy_y;
#X obj 410 100 s tup_id;
#X obj 10 160 r #gyro;
#X obj 10 190 unpack f f f;
#X obj 10 220 s gx;
#X obj 70 220 s gy;
#X obj 130 220 s gz;
#X obj 250 160 r #compass;
#X obj 250 190 s comp;
#X obj 330 160 r #magnet;
#X obj 330 190 unpack f f f;
#X obj 330 220 s mz;
#X connect 0 0 1 0;
#X connect 1 0 2 0;
#X connect 1 1 3 0;
#X connect 1 2 4 0;
#X connect 5 0 6 0;
#X connect 6 0 7 0;
#X connect 6 1 8 0;
#X connect 6 2 9 0;
#X connect 7 0 10 0;
#X connect 8 1 11 0;
#X connect 8 2 12 0;
#X connect 9 0 13 0;
#X connect 14 0 15 0;
#X connect 15 0 16 0;
#X connect 15 1 17 0;
#X connect 15 2 18 0;
#X connect 19 0 20 0;
#X connect 21 0 22 0;
#X connect 22 2 23 0;
""")
e = Engine(LIB, os.path.join(scene, "_main.pd"))
e.listen("ax", "ay", "az", "tdown_id", "txy_x", "txy_y", "tup_id", "gx", "gy", "gz", "comp", "mz")
e.send_list("#gyro", 0.5, -1.5, 2.0)
e.send("#compass", 123.5)
e.send_list("#magnet", 1.0, 2.0, -42.0)
e.send_list("#accelerate", 0.25, -0.5, -1.0)
e.send_msg("#touch", "down", 1, 160, 80)
e.send_msg("#touch", "xy", 1, 200, 40)
e.send_msg("#touch", "up", 1, 200, 40)
e.send_msg("#touch", "down", 2, 5, 6)
e.run(e.silence(0.1))
h = e.heard
check(h["ax"] == [0.25] and h["ay"] == [-0.5] and h["az"] == [-1.0], "#accelerate x y z list unpacks to %s %s %s" % (h["ax"], h["ay"], h["az"]))
check(h["tdown_id"] == [1.0, 2.0], "#touch down carries the finger number: %s" % h["tdown_id"])
check(h["txy_x"] == [200.0] and h["txy_y"] == [40.0], "#touch xy carries x y: %s %s" % (h["txy_x"], h["txy_y"]))
check(h["tup_id"] == [1.0], "#touch up carries the finger number: %s" % h["tup_id"])
check(h["gx"] == [0.5] and h["gy"] == [-1.5] and h["gz"] == [2.0], "#gyro x y z (rad/s) list unpacks: %s %s %s" % (h["gx"], h["gy"], h["gz"]))
check(h["comp"] == [123.5], "#compass is a single float of degrees: %s" % h["comp"])
check(h["mz"] == [-42.0], "#magnet x y z list unpacks: %s" % h["mz"])
e.close()

# ---- the bundled [accelerate] and [touch] helpers ----
helper = os.path.join(scenes, "Helpers.rj")
os.makedirs(helper)
open(os.path.join(helper, "_main.pd"), "w").write("""#N canvas 0 0 450 300 10;
#X obj 10 10 accelerate;
#X obj 10 40 touch;
#X obj 150 10 r accelerate;
#X obj 150 40 route magnitude pitch roll x y z status;
#X obj 150 70 s h_mag;
#X obj 210 70 s h_pitch;
#X obj 270 70 s h_roll;
#X obj 330 70 s h_x;
#X obj 390 70 s h_y;
#X obj 450 70 s h_z;
#X obj 510 70 s h_status;
#X obj 150 120 r touch;
#X obj 150 150 route tap;
#X obj 150 180 s h_tap;
#X connect 2 0 3 0;
#X connect 3 0 4 0;
#X connect 3 1 5 0;
#X connect 3 2 6 0;
#X connect 3 3 7 0;
#X connect 3 4 8 0;
#X connect 3 5 9 0;
#X connect 3 6 10 0;
#X connect 11 0 12 0;
#X connect 12 0 13 0;
""")
e = Engine(LIB, os.path.join(helper, "_main.pd"), search_path=[os.path.join(scenes, "pd"), os.path.join(scenes, "pd", "rj")])
e.listen("h_mag", "h_pitch", "h_roll", "h_x", "h_y", "h_z", "h_status", "h_tap")
e.send_list("#accelerate", 0.6, 0.0, -0.8)
e.run(e.silence(0.05))
h = e.heard
check(abs(h["h_mag"][-1] - 1.0) < 1e-5, "[accelerate] magnitude of (0.6, 0, -0.8) is 1: %s" % h["h_mag"])
check(abs(h["h_roll"][-1] - np.arctan(0.6 / -0.8)) < 1e-5, "[accelerate] roll = atan(x/z): %s" % h["h_roll"])
check(abs(h["h_pitch"][-1]) < 1e-5, "[accelerate] pitch = -atan(y/z) = 0 here: %s" % h["h_pitch"])
check((h["h_x"][-1], h["h_y"][-1], h["h_z"][-1]) == (np.float32(0.6), 0.0, np.float32(-0.8)), "[accelerate] raw x y z: %s %s %s" % (h["h_x"], h["h_y"], h["h_z"]))
check(h["h_status"] == [1.0], "[accelerate] status 1 while readings arrive: %s" % h["h_status"])
e.run(e.silence(0.3))
check(h["h_status"] == [1.0, 0.0], "[accelerate] status falls to 0 after ~150 ms of silence: %s" % h["h_status"])
e.send_list("#accelerate", 0.0, 0.5, 0.0)    # z = 0 must not blow up
e.run(e.silence(0.05))
check(all(np.isfinite(h["h_pitch"])) and all(np.isfinite(h["h_roll"])), "[accelerate] is safe when z = 0")
e.send_msg("#touch", "down", 2, 10, 10)
e.send_msg("#touch", "xy", 2, 11, 11)
e.run(e.silence(0.05))
check(h["h_tap"] == [2.0], "[touch] taps once per finger-down with the finger number: %s" % h["h_tap"])
e.close()

# ---- a real scene, if one was given ----
if REAL:
    real = os.path.join(scenes, os.path.basename(REAL.rstrip("/")))
    shutil.copytree(REAL, real)
    e = Engine(LIB, os.path.join(real, "_main.pd"), search_path=[os.path.join(scenes, "pd"), os.path.join(scenes, "pd", "rj")])
    quiet = e.run(e.silence(1.5))
    r0 = float(np.sqrt(np.mean(quiet[SR:] ** 2)))
    for _ in range(6):                      # a vigorous shake: jolts well over 2.3 g with calm between
        for x in (3.5, 0.0, -3.5, 0.0):     # scenes detect the crossing, so it must fall back each time
            e.send_list("#accelerate", x, 0.0, 0.0)
            e.run(e.silence(0.02))
    shaken = e.run(e.silence(2.0))
    r1 = float(np.sqrt(np.mean(shaken ** 2)))
    # "... couldn't create" lines don't name the object, so just report how many there were.
    errors = [m for m in e.log if "couldn't create" in m]
    print("note: %d object(s) could not be created" % len(errors))
    check(r1 > 1e-4 and r1 > 5 * r0, "%s: silent until shaken (rms %.2e before, %.2e after)" % (os.path.basename(real), r0, r1))
    e.close()

shutil.rmtree(tmp)
print("ALL PASSED" if fails == 0 else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
