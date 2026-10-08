#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Opens each scene shipped in assets/builtin_scenes the way the app lays them out and checks that it
loads without Pd errors and makes sound from a test input.

    python3 tools/test_bundled_scenes.py /path/to/libpd.so
"""
import os, shutil, sys, tempfile
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from pdtest import Engine, SR

ROOT = os.path.join(os.path.dirname(__file__), "..")
LIB_ASSETS = os.path.join(ROOT, "app/src/main/assets/scene_lib")
SCENES = os.path.join(ROOT, "app/src/main/assets/builtin_scenes")
LIB = sys.argv[1] if len(sys.argv) > 1 else "libpd.so"

fails = 0
def check(cond, msg):
    global fails
    print(("ok:   " if cond else "FAIL: ") + msg)
    if not cond:
        fails += 1

names = sorted(d for d in os.listdir(SCENES) if d.endswith(".rj"))
check(len(names) == 4, "four scenes are bundled: %s" % names)
for name in names:
    d = os.path.join(SCENES, name)
    check(os.path.isfile(os.path.join(d, "_main.pd")), name + " has _main.pd")
    check(os.path.isfile(os.path.join(d, "LICENSE.txt")) or os.path.isfile(os.path.join(d, "rj", "LICENSE.txt")),
          name + " carries its licence text")
    check("<key>name</key>" in open(os.path.join(d, "Info.plist")).read(), name + " has a name in Info.plist")
    tmp = tempfile.mkdtemp()
    scenes = os.path.join(tmp, "scenes")
    shutil.copytree(LIB_ASSETS, os.path.join(scenes, "pd"))
    shutil.copytree(d, os.path.join(scenes, name))
    e = Engine(LIB, os.path.join(scenes, name, "_main.pd"),
               search_path=[os.path.join(scenes, "pd"), os.path.join(scenes, "pd", "rj")])   # as in AudioService
    rng = np.random.default_rng(1)
    x = np.zeros(SR * 6, dtype=np.float32)
    x[:SR // 2] = 0.1 * np.sin(2 * np.pi * 200 * np.arange(SR // 2) / SR)
    for k in range(SR // 2, SR * 6 - 3000, SR * 3 // 4):          # sharp noise bursts: onsets
        x[k:k + 1500] = 0.8 * rng.standard_normal(1500)
    y = e.run(x)
    bad = sorted(set(m for m in e.log if "couldn't create" in m or "error" in m.lower() or "can't" in m))
    check(not bad, name + " opens with no Pd errors %s" % bad[:3])
    peak = float(np.abs(y).max())
    check(peak > 0.02, name + " makes sound (peak %.3f)" % peak)
    check(peak <= 1.0 + 1e-6, name + " stays within +-1 (peak %.3f)" % peak)

print("ALL PASSED" if fails == 0 else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
