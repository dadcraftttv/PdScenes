#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generates app/src/main/assets/patches/test_scene.pd.

Pd patch files address objects by index, which is easy to break by hand. This builds the
graph from named nodes instead, so adding an effect is a few lines. Run from anywhere:

    python3 tools/make_patch.py
"""
import math
import os
import re

BS = chr(92)  # a literal backslash; Pd writes escaped semicolons as "\;"
OUT = os.path.join(os.path.dirname(__file__), "..", "app", "src", "main", "assets",
                   "patches", "test_scene.pd")

# Defaults for the loadbang message (lets the patch also run standalone in desktop Pd).
# tools/test_patch.py checks these against Params.java so they cannot drift.
DEFAULTS = [
    ("gain", 2.5), ("dry", 1), ("echo_on", 1), ("echo_time", 350), ("echo_sync", 2), ("feedback", 0.4),
    ("wet", 0.5), ("ring_on", 1), ("ring_freq", 80), ("ring_mix", 0), ("smooth", 30),
    ("pitch_on", 1), ("pitch_semi", 0), ("pitch_mix", 0), ("pitch_window", 60),
    ("crush_on", 1), ("crush_mix", 0), ("crush_bits", 8), ("crush_rate", 8000),
    ("space_on", 1), ("space_pan", 0), ("space_shift", 0),
    ("filter_on", 1), ("filter_mix", 0), ("filter_type", 0), ("filter_freq", 1500), ("filter_q", 1),
    ("reverb_on", 1), ("reverb_mix", 0), ("reverb_size", 0.5), ("reverb_tone", 6000),
    ("chorus_on", 1), ("chorus_mix", 0), ("chorus_rate", 0.8), ("chorus_depth", 3),
    ("trem_on", 1), ("trem_depth", 0), ("trem_rate", 5),
    ("gate_thresh", -80), ("comp_thresh", -30), ("comp_ratio", 4), ("comp_makeup", 0),
    ("dist_on", 1), ("dist_mix", 0), ("dist_drive", 4), ("dist_type", 0),
    ("rvs_on", 1), ("rvs_mix", 0), ("rvs_time", 400),
    ("glitch_on", 1), ("glitch_hold", 0), ("glitch_len", 120),
    ("flange_on", 1), ("flange_mix", 0), ("flange_rate", 0.3), ("flange_depth", 4), ("flange_fb", 0.5),
    ("phaser_on", 1), ("phaser_mix", 0), ("phaser_rate", 0.4), ("phaser_depth", 0.7), ("phaser_fb", 0.4),
    ("beat_on", 1), ("beat_level", 0), ("beat_hats", 0.5), ("beat_snare", 0.6), ("beat_pitch", 55),
    ("music_on", 0), ("music_key", 0), ("music_scale", 0), ("music_pad", 0.33), ("music_arp", 0.4),
    ("music_tone", 0.5), ("music_react", 0.8), ("music_res", 0.8), ("music_harm", 0.6), ("music_drift", 1), ("echo_scatter", 0.5), ("gc_amount", 0), ("gc_level", 0.7), ("gc_stutter", 1), ("gc_reverse", 1),
    ("gc_shuffle", 1), ("gc_stretch", 1), ("music_pad_reg", 2), ("pocket_hush", 0.5), ("pocket_guard", 0.6),
]

# Scales as semitone steps above the key note. The patch snaps every note it plays to these.
SCALES = [
    (0, 2, 4, 5, 7, 9, 11),     # Major
    (0, 2, 3, 5, 7, 8, 10),     # Minor
    (0, 2, 4, 7, 9),            # Major pentatonic
    (0, 3, 5, 7, 10),           # Minor pentatonic
    (0, 2, 3, 5, 7, 9, 10),     # Dorian
    (0, 2, 4, 5, 7, 9, 10),     # Mixolydian
    (0, 2, 4, 6, 7, 9, 11),     # Lydian
    (0, 2, 4, 6, 8, 10),        # Whole tone
]
# Pad chords per scale, as scale steps of the chord root (0 = the key chord): the home chord and its two strongest
# neighbours, picked by the brightness of the room, plus one contrast chord now and then (None = no contrast;
# pentatonic and whole-tone chords are all consonant, so they keep every chord). No diminished chords anywhere.
CHORD_POOLS = [
    ((0, 3, 4), 5),            # Major: C F G + Am
    ((0, 3, 4), 2),            # Minor: Cm Fm Gm + Eb
    ((0, 1, 2, 3, 4), None),   # Major pentatonic
    ((0, 1, 2, 3, 4), None),   # Minor pentatonic
    ((0, 3, 4), 6),            # Dorian: Cm F Gm + Bb
    ((0, 3, 6), 4),            # Mixolydian: C F Bb + Gm
    ((0, 1, 4), 5),            # Lydian: C D G + Am
    ((0, 1, 2, 3, 4, 5), None),  # Whole tone
]
CONTRAST_PCT = 20             # chance (in 100) that a chord change picks the contrast chord
# Key drift: every few minutes the home chord moves to a related one on the same notes (C major -> D dorian, G or
# A minor feel), and later comes home. Only moves where every chord of the pool stays free of diminished chords.
DRIFT_MIN_S, DRIFT_MAX_S = 180, 360
DRIFT_HOME_PCT = 60           # away from home, the chance the next drift goes back home


def drift_options(iv, pool):
    """Scale steps the home chord may drift to: those where every pool chord moved there is not diminished."""
    n = len(iv)
    def note(d):
        return iv[d % n] + 12 * (d // n)
    def ok(r):
        return note(r + 4) - note(r) != 6 or note(r + 2) - note(r) != 3
    return [o for o in range(n) if all(ok(o + r) for r in pool)]
# Footstep arpeggios: scale steps above the current chord root, one per footstep. Every bar (8 steps) a new
# pattern is picked at random, and now and then a step rests.
# Ordered calm -> busy: each bar picks one near the walking pace (a stroll stays near the top, a brisk walk near
# the bottom), with a little randomness and never the same one twice.
ARP_PATTERNS = (
    (0, 2, 4, 5, 4, 2, 1, 2),        # a little melody around the root (small steps)
    (0, 2, 4, 7, 4, 2, 0, 2),        # up and back
    (0, 4, 2, 4, 7, 4, 2, 4),        # broken chord
    (7, 4, 2, 0, 2, 4, 6, 4),        # down and up, with a passing note
    (4, 2, 7, 4, 9, 7, 4, 2),        # high and leaping
)
ARP_REST_SLOW_PCT = 25       # chance (in 100) that a footstep plays no note when strolling...
ARP_REST_FAST_PCT = 5        # ...and when walking briskly
# Density memory: the music counts the notes it played lately (each fades over DENSITY_S) and makes room when busy
DENSITY_S = 8.0
DENSITY_BUSY = 10            # notes "in memory" at which half the chimes are skipped (about 1.25 a second)
DENSITY_ARP_FROM = 16        # the walking arpeggio only starts resting more past this...
DENSITY_ARP_PCT = 2          # ...by this many percent per note over it...
DENSITY_ARP_MAX = 30         # ...up to this much
DENSITY_ARP_WEIGHT = 0.3     # an arpeggio note counts this much (the steady bed must not silence the chimes on the beat)
CHIME_SPAN = 4               # chime melodies wander this many scale steps either side of the brightness note
CHIME_DECAY_MS = (900, 2600)     # each chime's fade, picked at random
CHIME_OVERTONE = (0.12, 0.45)    # each chime's 2nd-harmonic level (3rd is a third of it): mellow to bright
BASS_FOLLOW_PCT = 40    # chance (in 100) that a chord change moves the bass to the chord's root; else the key's root
BASS_DIP_MS = 600       # a bass note change fades out over this...
BASS_RISE_MS = 1500     # ...and the new note fades in over this
BASS_GAIN = 0.11
BASS_DUCK = 0.6         # a footstep takes the bass down this share while the walking beat plays...
BASS_DUCK_MS = 220      # ...and it comes back over this
PAD_GLIDE_MS = 3500     # the pad crossfades from one chord to the next over this time (no pitch slides)

# Room notes: resonators that make the mic's own sound ring the current chord: root, third and fifth (scale steps
# 0, 2, 4 above the chord root), one and two octaves above the pad. (octaves, steps) pairs, so pentatonic and
# whole-tone scales get real octaves too.
RES_NOTES = ((1, 0), (1, 2), (1, 4), (2, 0), (2, 2), (2, 4))
# How long they ring follows what was heard: a short soft sound gives a quick chime, a loud one rings longer, and a
# sound that goes on builds up to a long bell. A note rings for about ring * sqrt(262 / Hz) seconds (time constant,
# so low notes longer, high notes shorter), with ring from RES_RING_SHORT_S to RES_RING_LONG_S.
RES_RING_SHORT_S = 0.08
RES_RING_LONG_S = 2.0
RES_LOUD_DB = 30        # this far above the room's quiet counts as fully loud
RES_LOUD_SHARE = 0.5    # how far loudness alone moves the ring toward long (the rest comes from duration)
RES_BUILD_S = 1.5       # a fully loud sound that lasts this long reaches the long bell
RES_RELAX_S = 8.0       # afterwards the ring length relaxes back toward short (time constant)
RES_STEADY = 0.4        # ring length with react = 0 (ignores the room)
RES_RING_REF_S = 0.3    # the ring length RES_GAIN was tuned at
RES_GLIDE_MS = 400
RES_GAIN = 20.0     # make-up: a narrow band holds little of a broad sound
RES_MAX = 0.3       # soft ceiling for the whole voice
RES_OPEN_DB = 10    # the input opens fully this many dB above the room's quiet
RES_LOOKAHEAD_MS = 20
POCKET_HUSH_DB = 24         # pocket hush at 1 turns the mic down this far (0.5, the default: 12 dB)
ECHO_WALK_HOLD_MS = 2500   # echo stays locked to the steps this long after the last one
RES_FADE_IN_MS = 200       # Room notes fade in this long each time their block switches on
STOP_AFTER_MS = 1200       # no step for this long after walking = you stopped
STOP_DIP = 0.55            # the pad and bass breathe down to this share...
STOP_DIP_MS = 2500         # ...over this long...
STOP_RECOVER_MS = 8000     # ...then drift back to full over this long
STOP_RETURN_MS = 800       # walking again brings them straight back
GROOVE_VEL = 0.45           # groove notes are this share of the arpeggio's loudness...
GROOVE_FADE_IN_MS = 4000   # ...reached over this long
# Harmony: a held, clearly pitched sound (humming, whistling, a bird, a horn) gets an in-key note answering it.
HARM_STABLE_FRAMES = 12    # pitch frames (~11 ms each) the pitch must hold steady before it is answered
HARM_STEADY_ST = 0.6       # frame to frame wobble allowed, in semitones (singing vibrato passes)
HARM_ABOVE_DB = 6          # how far above the room's quiet the sound must be
HARM_HIGH = 76             # a pitch from E5 up (a whistle, a bird) is answered below it; lower ones (voices) above
HARM_RANGE = (36, 104)     # heard pitches outside C2..G#7 are hiss or rumble, not a voice, whistle or bird
HARM_ATTACK_MS = 150
# Glitch cloud: bits of what the mic heard (kept in memory only, a few seconds) come back mangled, around you.
GC_BUF_MS = 4000
GC_ONSET_DB = 10           # a sudden sound: the 5 ms level jumps this far above its recent average...
GC_MIN_DB = 55             # ...and is at least this loud (-45 dBFS), so a quiet room's flicker doesn't count
GC_COOL_MS = (600, 2400)   # rest after a glitch: at Amount 1 / near 0 (also keeps the two voices from overlapping)
GC_STEP_WAIT_MS = 2500     # a step this recently = walking: a glitch waits for the next step or half-step
GC_PREROLL_MS = 15         # a glitch of a sudden sound starts this long before it was noticed (5 ms meter), so its attack stays
HARM_RELEASE_MS = 1800


def pc_to_degree(iv):
    """For each semitone above the key note (0..11), the nearest scale step (len(iv) = the key note an octave up)."""
    marks = list(iv) + [12]
    return [min(range(len(marks)), key=lambda i: (abs(marks[i] - pc), marks[i])) for pc in range(12)]
DUCK_MS = 600           # how quickly the output dips (and comes back) when other audio plays
POCKET_HUSH_MS = 400        # how fast the hush fades in and out
POCKET_GUARD_DB = 12        # mic-down protection at 1 turns the mic down this much more...
POCKET_GUARD_HP_HZ = 300    # ...and filters out the cloth thump below about this (12 dB/octave)

# Flanger: the delay sweeps from this minimum up to minimum + depth (ms). [delread4~] cannot go
# below one audio block (1.35 ms at 48 kHz) and the feedback loop needs at least that, so 2 ms.
FLANGE_MIN_MS = 2.0

# Phaser: four allpass sections whose centre frequencies are these multiples of the swept
# frequency; the sweep is centre * 2^(+-2 * depth).
PHASER_CENTRE_HZ = 700
PHASER_STAGES = (1.0, 1.7, 2.9, 5.0)
PHASER_Q = 0.7

# Chorus: two delay taps around these base delays (ms), swept by a shared LFO a quarter cycle
# apart. The sweep depth (ms) is a parameter and must stay below the smaller base delay minus
# about 1.5 ms (the shortest delay [delread4~] can do).
CHORUS_BASE_MS = (15, 21)

# Reverb (a Freeverb-style design): parallel feedback combs, then series allpasses. The delay
# times are in milliseconds, so the sound is the same at any sample rate. The right channel
# uses slightly longer delays so the two channels decorrelate and the reverb sounds wide.
COMB_MS = [25.3, 26.9, 29.0, 30.7, 32.2, 33.8, 35.3, 36.7]
ALLPASS_MS = [12.6, 10.0, 7.7, 5.1]
RIGHT_EXTRA_MS = 0.52

# A short [delread4~] cannot go below about one audio block (1.35 ms at 48 kHz). Both ears are
# therefore delayed by this much, plus the ear-delay offset on one side, so the neutral setting
# is centred and identical in both ears. tools/test_patch.py expects this latency.
EAR_BASE_MS = 1.5


class Patch:
    def __init__(self):
        self.lines, self.index, self.conns = [], {}, []
        self.groups = []

    def _add(self, name, line):
        assert name not in self.index, "duplicate node " + name
        self.index[name] = len(self.lines)
        self.lines.append(line)
        return name

    def obj(self, name, text, x, y):
        return self._add(name, f"#X obj {x} {y} {text};")

    def msg(self, name, text, x, y):
        return self._add(name, f"#X msg {x} {y} {text};")

    def c(self, a, b, outlet=0, inlet=0):
        self.conns.append((a, outlet, b, inlet))

    def sig2(self, name, op, a, b, x, y):
        """Binary signal op: a -> left inlet, b -> right inlet."""
        self.obj(name, op, x, y)
        self.c(a, name, 0, 0)
        self.c(b, name, 0, 1)
        return name

    # ---- switchable blocks ----
    # A block's objects go into a subpatch with [switch~], so its DSP costs nothing while it can't be heard
    # (Pd runs every signal object all the time otherwise: measured on the phone, the patch took about half
    # a core). Membership is by node name; connections that cross the boundary get inlets/outlets added
    # automatically, signal or control after the source object. A switched-off subpatch outputs silence and
    # its delay lines come back empty, so nothing stale is heard when it switches on again.
    # self.groups: (group name, compiled regex); first match wins

    # objects whose name ends in ~ but whose outlets carry messages
    CONTROL_TILDE = {"snapshot~", "env~", "samplerate~", "threshold~", "bonk~", "fiddle~", "sigmund~"}

    def group(self, gname, pattern):
        self.groups.append((gname, re.compile(pattern)))

    def _group_of(self, name):
        if name.startswith("grp_"):
            return name.split("_")[1]
        for g, rx in self.groups:
            if rx.match(name):
                return g
        return None

    def _is_signal(self, name, outlet):
        words = self.lines[self.index[name]].rstrip(";").split()
        if words[1] != "obj" or len(words) < 5:
            return False
        cls = words[4]
        return cls.endswith("~") and cls not in self.CONTROL_TILDE

    def text(self):
        names = sorted(self.index, key=self.index.get)
        member = {n: self._group_of(n) for n in names}
        used = sorted({g for g in member.values() if g}, key=lambda g: min(self.index[n] for n in names if member[n] == g))
        # inlets/outlets per group: one per (source node, outlet)
        ins = {g: [] for g in used}
        outs = {g: [] for g in used}
        for a, o, b, i in self.conns:
            ga, gb = member[a], member[b]
            if ga != gb:
                if ga and (a, o) not in outs[ga]:
                    outs[ga].append((a, o))
                if gb and (a, o) not in ins[gb]:
                    ins[gb].append((a, o))
        # parent indices: top-level objects in order, each group at its first member's position
        parent, local, seen = {}, {}, set()
        order = []
        for n in names:
            g = member[n]
            if g is None:
                parent[n] = len(order); order.append(("obj", n))
            elif g not in seen:
                seen.add(g); parent["grp:" + g] = len(order); order.append(("grp", g))
        out = ["#N canvas 0 0 900 900 12;"]
        for kind, x in order:
            if kind == "obj":
                out.append(self.lines[self.index[x]])
                continue
            g = x
            mem = [n for n in names if member[n] == g]
            body = [self.lines[self.index[n]] for n in mem]
            for k, n in enumerate(mem):
                local[(g, n)] = k
            for k, (a, o) in enumerate(ins[g]):
                local[(g, "in", a, o)] = len(body)
                body.append(f"#X obj {10 + 80 * k} 0 {'inlet~' if self._is_signal(a, o) else 'inlet'};")
            for k, (a, o) in enumerate(outs[g]):
                local[(g, "out", a, o)] = len(body)
                body.append(f"#X obj {10 + 80 * k} 2000 {'outlet~' if self._is_signal(a, o) else 'outlet'};")
            conns = []
            for a, o, b, i in self.conns:
                ga, gb = member[a], member[b]
                src = local[(g, a)] if ga == g else (local[(g, "in", a, o)] if gb == g else None)
                if ga == g and gb == g:
                    conns.append(f"#X connect {local[(g, a)]} {o} {local[(g, b)]} {i};")
                elif gb == g:
                    conns.append(f"#X connect {local[(g, 'in', a, o)]} 0 {local[(g, b)]} {i};")
                elif ga == g:
                    key = (g, "out", a, o)
                    line = f"#X connect {local[(g, a)]} {o} {local[key]} 0;"
                    if line not in conns:
                        conns.append(line)
            out.append(f"#N canvas 0 0 900 900 {g} 0;")
            out += body + conns
            out.append(f"#X restore {200 + 100 * used.index(g)} 2200 pd {g};")
        made = set()
        for a, o, b, i in self.conns:
            ga, gb = member[a], member[b]
            if ga == gb is None:
                out.append(f"#X connect {parent[a]} {o} {parent[b]} {i};")
                continue
            if ga == gb:
                continue
            if ga:   # leaves group ga through its outlet for (a, o)
                src, so = parent["grp:" + ga], outs[ga].index((a, o))
            else:
                src, so = parent[a], o
            if gb:
                dst, di = parent["grp:" + gb], ins[gb].index((a, o))
            else:
                dst, di = parent[b], i
            line = f"#X connect {src} {so} {dst} {di};"
            if line not in made:   # one cable per inlet; the subpatch fans out inside
                made.add(line)
                out.append(line)
        return "\n".join(out) + "\n"


def add_switch(P, g, factors, tail_ms, also=()):
    """Switches block g's DSP on while the product of the receivers `factors` is above 0, and off again
    3 x smoothing + tail_ms after it drops to 0 (so fades and ring-outs finish first). `also` are nodes
    that get the same 0/1 (e.g. a metro that only feeds the block)."""
    x, y = 4600 + 160 * len(P.groups), 1600
    n = f"gate_{g}"
    terms = "*".join(f"$f{k + 1}" for k in range(len(factors)))
    P.obj(f"{n}_calc", ("expr (" + terms + ")>0").replace("$", BS + "$"), x, y + 120)
    P.obj(f"{n}_s0", "f", x, y + 90)
    P.c(f"{n}_s0", f"{n}_calc")
    for k, rcv in enumerate(factors):
        P.obj(f"{n}_r{k}", f"r {rcv}", x + 40 * k, y)
        P.obj(f"{n}_t{k}", "t b f", x + 40 * k, y + 30)
        P.c(f"{n}_r{k}", f"{n}_t{k}")
        if k == 0:
            P.c(f"{n}_t{k}", f"{n}_s0", 1, 1)
        else:
            P.c(f"{n}_t{k}", f"{n}_calc", 1, k)
        P.c(f"{n}_t{k}", f"{n}_s0", 0, 0)
    P.obj(f"{n}_chg", "change -1", x, y + 150)                  # the first answer always goes out
    P.obj(f"{n}_sel", "sel 0", x, y + 180)
    P.obj(f"{n}_del", "del 1000", x, y + 240)
    P.obj(f"{n}_on", "t b b", x + 60, y + 210)
    P.msg(f"{n}_stop", "stop", x + 60, y + 240)
    P.msg(f"{n}_one", "1", x + 110, y + 240)
    P.msg(f"{n}_zero", "0", x, y + 270)
    P.obj(f"{n}_s", f"s sw_{g}", x, y + 300)
    P.c(f"{n}_calc", f"{n}_chg"); P.c(f"{n}_chg", f"{n}_sel")
    P.c(f"{n}_sel", f"{n}_del", 0, 0); P.c(f"{n}_del", f"{n}_zero"); P.c(f"{n}_zero", f"{n}_s")
    P.c(f"{n}_sel", f"{n}_on", 1, 0); P.c(f"{n}_on", f"{n}_stop", 1, 0); P.c(f"{n}_stop", f"{n}_del")
    P.c(f"{n}_on", f"{n}_one", 0, 0); P.c(f"{n}_one", f"{n}_s")
    P.obj(f"{n}_wait", ("expr 3*$f1+" + str(tail_ms)).replace("$", BS + "$"), x + 120, y + 180)
    P.c("r_smooth", f"{n}_wait"); P.c(f"{n}_wait", f"{n}_del", 0, 1)
    # inside the block
    P.obj(f"grp_{g}_r", f"r sw_{g}", 10, 10)
    P.obj(f"grp_{g}_sw", "switch~", 10, 40)
    P.c(f"grp_{g}_r", f"grp_{g}_sw")
    for node in also:
        P.c(f"grp_{g}_r", node)


def smoothed(P, key, recv, x, y, ramp=30, mult=None):
    """[r recv] -> ramped signal. The ramp time follows the global 'smooth' parameter."""
    P.obj(f"r_{key}", f"r {recv}", x, y)
    P.obj(f"pk_{key}", f"pack f {ramp}", x, y + 30)
    P.obj(f"ln_{key}", "line~", x, y + 60)
    P.c(f"r_{key}", f"pk_{key}")
    P.c(f"pk_{key}", f"ln_{key}")
    P.c("smooth_x3" if mult == 3 else "r_smooth", f"pk_{key}", 0, 1)
    return f"ln_{key}"


def add_beat(P):
    """Footstep drums. The app sends [step( with the time since the previous step (seconds) at every
    footstep. Steps alternate kick and snare, and a hi-hat falls half a step after each one. Returns the
    name of the mono output signal."""
    x = 2300
    P.obj("r_step", "r step", x, 20)
    P.obj("step_t", "t b b f", x, 50)
    P.c("r_step", "step_t")
    # Half the interval, in ms, sets the hi-hat delay (right inlet of [del]: sets without starting it).
    P.obj("step_clip", "clip 0.25 1.2", x + 250, 80)
    P.obj("step_half_ms", "* 500", x + 250, 110)
    P.obj("hat_del", "del 270", x + 250, 140)
    P.c("step_t", "step_clip", 2, 0)
    P.c("step_clip", "step_half_ms")
    P.c("step_half_ms", "hat_del", 0, 1)
    P.c("step_t", "hat_del", 1, 0)
    # Even steps kick, odd steps snare.
    P.obj("cnt_f", "f", x, 80)
    P.obj("cnt_add", "+ 1", x, 110)
    P.obj("cnt_mod", "mod 2", x, 140)
    P.obj("cnt_sel", "sel 0 1", x, 170)
    P.c("step_t", "cnt_f", 0, 0)
    P.c("cnt_f", "cnt_add"); P.c("cnt_add", "cnt_mod"); P.c("cnt_mod", "cnt_f", 0, 1)
    P.c("cnt_f", "cnt_sel")

    comma = " " + BS + ","   # Pd writes a message-box comma as a separate escaped token
    def env(name, text, trig, trig_outlet, ex, ey):
        P.msg(name + "_msg", text.replace(",", comma), ex, ey)
        P.obj(name, "vline~", ex, ey + 30)
        P.c(trig, name + "_msg", trig_outlet, 0)
        P.c(name + "_msg", name)
        return name

    # Kick: a sine whose pitch falls from 3.5x to 1x of the "pitch" setting in 70 ms.
    pitch = smoothed(P, "beat_pitch", "beat_pitch", x + 500, 20)
    k_amp = env("k_amp", "0, 1 2, 0 260 2", "cnt_sel", 0, x, 220)
    k_pit = env("k_pit", "3.5, 1 70", "cnt_sel", 0, x + 150, 220)
    P.sig2("k_freq", "*~", k_pit, pitch, x + 150, 290)
    P.obj("k_osc", "osc~", x + 150, 320)
    P.c("k_freq", "k_osc")
    P.sig2("kick", "*~", "k_osc", k_amp, x, 350)

    # Snare: noise and a short tone.
    s_amp = env("s_amp", "0, 1 1, 0 150 1", "cnt_sel", 1, x + 300, 220)
    s_ton = env("s_ton", "0, 1 1, 0 90 1", "cnt_sel", 1, x + 450, 220)
    P.obj("noise", "noise~", x + 600, 220)
    P.obj("s_hp", "hip~ 1800", x + 600, 250)
    P.c("noise", "s_hp")
    P.sig2("s_noise", "*~", "s_hp", s_amp, x + 300, 350)
    P.obj("s_osc", "osc~ 185", x + 450, 290)
    P.sig2("s_tone", "*~", "s_osc", s_ton, x + 450, 350)
    P.obj("s_tone_half", "*~ 0.5", x + 450, 380)
    P.c("s_tone", "s_tone_half")
    P.sig2("snare_raw", "+~", "s_noise", "s_tone_half", x + 300, 410)
    snl = smoothed(P, "beat_snare", "beat_snare", x + 700, 20)
    P.sig2("snare", "*~", "snare_raw", snl, x + 300, 440)

    # Hi-hat: bright noise, very short.
    # A harder step (step_strength, 0.5 = as usual) opens the hat: louder and longer. A soft step leaves it faint.
    # step_strength comes with the step (it is the step before's); step_hit follows once this step's bump is over,
    # before the hat plays, so the hat answers the stomp itself.
    P.obj("st_init", "loadbang", x + 1200, 20)
    P.msg("st_init_msg", BS + "; step_strength 0.5 " + BS + "; beat_sure 1", x + 1200, 50)
    P.c("st_init", "st_init_msg")
    P.obj("h_r_str", "r step_strength", x + 900, 140)
    P.obj("h_str", "f 0.5", x + 750, 170)
    P.obj("h_r_hit", "r step_hit", x + 1000, 140)
    P.c("hat_del", "h_str"); P.c("h_r_str", "h_str", 0, 1); P.c("h_r_hit", "h_str", 0, 1)
    P.obj("h_calc", ("expr 0.1+1.2*$f1*$f1" + " " + BS + "; 20+200*$f1*$f1").replace("$", BS + "$"), x + 750, 190)
    P.obj("h_pack", "pack f f", x + 750, 205)
    P.c("h_str", "h_calc"); P.c("h_calc", "h_pack", 1, 1); P.c("h_calc", "h_pack", 0, 0)
    P.msg("h_amp_msg", ("0, " + BS + "$1 1, 0 " + BS + "$2 1").replace(",", comma), x + 750, 220)
    P.obj("h_amp", "vline~", x + 750, 250)
    P.c("h_pack", "h_amp_msg"); P.c("h_amp_msg", "h_amp")
    h_amp = "h_amp"
    P.obj("h_hp", "hip~ 7000", x + 750, 250)
    P.c("noise", "h_hp")
    P.sig2("hat_raw", "*~", "h_hp", h_amp, x + 750, 350)
    hats = smoothed(P, "beat_hats", "beat_hats", x + 900, 20)
    P.sig2("hat", "*~", "hat_raw", hats, x + 750, 380)

    # Mix, master level and on/off switch (a little headroom so the drums never clip the output).
    P.sig2("beat_ks0", "+~", "kick", "snare", x, 480)
    P.obj("ks_r_str", "r step_strength", x + 1200, 140)
    P.obj("ks_calc", ("expr 0.8+0.4*$f1").replace("$", BS + "$"), x + 1200, 170)
    P.obj("ks_pk", "pack f 5", x + 1200, 200)
    P.obj("ks_gain", "line~", x + 1200, 230)
    P.c("ks_r_str", "ks_calc"); P.c("ks_calc", "ks_pk"); P.c("ks_pk", "ks_gain")
    P.sig2("beat_kick_snare", "*~", "beat_ks0", "ks_gain", x, 500)   # a harder step lifts kick and snare a little
    P.sig2("beat_sum", "+~", "beat_kick_snare", "hat", x, 530)
    lvl = smoothed(P, "beat_level", "beat_level", x + 1050, 20)
    bon = smoothed(P, "beat_on", "beat_on", x + 1150, 20)
    P.sig2("beat_gain0", "*~", lvl, bon, x + 1050, 120)
    # Uneven steps (beat_sure 0.4..1 from StepDetector) play the drums softer until the rhythm settles again.
    P.obj("bs_r", "r beat_sure", x + 1350, 140)
    P.obj("bs_pk", "pack f 300", x + 1350, 170)
    P.obj("bs_ln", "line~", x + 1350, 200)
    P.c("bs_r", "bs_pk"); P.c("bs_pk", "bs_ln")
    P.sig2("beat_gain", "*~", "beat_gain0", "bs_ln", x + 1050, 150)
    P.sig2("beat_lvl", "*~", "beat_sum", "beat_gain", x, 560)
    P.obj("beat_out", "*~ 0.6", x, 590)
    P.c("beat_lvl", "beat_out")
    return "beat_out"


def add_music(P):
    """A reactive synth that plays only notes of the chosen key and scale. It listens to the mic:
    loudness sets how busy and loud it is, the brightness of the sound (zero-crossing rate) sets the
    register and the chords, sudden sounds trigger a chime, and footsteps play an arpeggio that gets
    louder as the pace rises. Returns the name of the mono output signal."""
    x = 4600
    comma = " " + BS + ","
    d = BS + "$"

    def ex(name, text, xx, yy):
        return P.obj(name, "expr " + text.replace(",", BS + ",").replace("$", d), xx, yy)

    # ---- scale and key: the scale lives in a table; a degree (0, 1, 2...) becomes a pitch ----
    P.obj("mu_scale_tab", "table scale_iv 8", x, 20)
    P.obj("mu_pcdeg_tab", "table pc_deg 12", x + 100, 20)
    P.obj("mu_dr_tab", "table drift_opts 8", x + 200, 40)
    P.obj("mu_r_scale", "r music_scale", x, 50)
    P.obj("mu_scale_t", "t b f", x, 65)                                  # table first, then re-pick the chord
    sel = P.obj("mu_scale_sel", "sel " + " ".join(str(i) for i in range(len(SCALES))), x, 80)
    P.c("mu_r_scale", "mu_scale_t"); P.c("mu_scale_t", sel, 1, 0)
    for i, iv in enumerate(SCALES):
        pool, contrast = CHORD_POOLS[i]
        opts = drift_options(iv, pool)
        text = (f"{BS}; drift_opts 0 {' '.join(str(v) for v in opts)} {BS}; drift_n {len(opts)} {BS}; drift_set 0"
                f" {BS}; scale_iv 0 {' '.join(str(v) for v in iv)} {BS}; scale_n {len(iv)}"
                f" {BS}; pc_deg 0 {' '.join(str(v) for v in pc_to_degree(iv))}"
                f" {BS}; chord_pool 0 {' '.join(str(v) for v in pool)} {BS}; pool_n {len(pool)}"
                f" {BS}; pool_x {-1 if contrast is None else contrast}")
        P.msg(f"mu_scale_msg{i}", text, x + 60 * i, 110)
        P.c(sel, f"mu_scale_msg{i}", i, 0)
    P.obj("mu_pool_tab", "table chord_pool 8", x + 200, 20)
    P.obj("mu_r_n", "r scale_n", x + 520, 50)
    P.obj("mu_v_n", "value scale_n", x + 520, 80)
    P.c("mu_r_n", "mu_v_n")
    P.obj("mu_r_key", "r music_key", x + 640, 50)
    P.obj("mu_key_t", "t b f", x + 640, 65)
    P.obj("mu_key_root", "+ 48", x + 640, 80)                    # key note in the octave from C3
    P.c("mu_r_key", "mu_key_t"); P.c("mu_key_t", "mu_key_root", 1, 0)

    def degree_to_hz(tag, xx, yy):
        """Float in: scale degree (0 = the key note). Float out: frequency in Hz."""
        P.obj(f"{tag}_t", "t f f", xx, yy)
        P.obj(f"{tag}_mod", "mod 7", xx + 60, yy + 30)
        P.obj(f"{tag}_iv", "tabread scale_iv", xx + 60, yy + 60)
        P.obj(f"{tag}_div", "div 7", xx, yy + 30)
        P.obj(f"{tag}_oct", "* 12", xx, yy + 60)
        P.obj(f"{tag}_a", "+ 0", xx, yy + 90)
        P.obj(f"{tag}_b", "+ 48", xx, yy + 120)
        P.obj(f"{tag}_hz", "mtof", xx, yy + 150)
        P.c(f"{tag}_t", f"{tag}_mod", 1, 0); P.c(f"{tag}_t", f"{tag}_div", 0, 0)
        P.c(f"{tag}_mod", f"{tag}_iv"); P.c(f"{tag}_iv", f"{tag}_a", 0, 1)
        P.c(f"{tag}_div", f"{tag}_oct"); P.c(f"{tag}_oct", f"{tag}_a")
        P.c(f"{tag}_a", f"{tag}_b"); P.c(f"{tag}_b", f"{tag}_hz")
        P.c("mu_r_n", f"{tag}_mod", 0, 1); P.c("mu_r_n", f"{tag}_div", 0, 1)
        P.c("mu_key_root", f"{tag}_b", 0, 1)
        return f"{tag}_t", f"{tag}_hz"

    # ---- listening: loudness, brightness, onsets ----
    P.obj("mu_r_react", "r music_react", x, 300)
    P.obj("mu_r_level", "r mic_level", x + 150, 300)
    P.obj("mu_raw_sig", "sig~", x + 300, 360)                           # the same level, averaged over ~1 s
    P.obj("mu_slow_lp", "lop~ 0.6", x + 300, 390)
    P.c("mu_r_level", "mu_raw_sig"); P.c("mu_raw_sig", "mu_slow_lp")
    # Brightness: how often the mic signal crosses zero, as a frequency.
    P.obj("mu_zc_sign", "expr~ " + "($v1>0)".replace("$", d), x + 450, 300)
    P.obj("mu_zc_diff", "rzero~ 1", x + 450, 330)
    P.obj("mu_zc_abs", "abs~", x + 450, 360)
    P.obj("mu_zc_lp", "lop~ 1.5", x + 450, 390)
    P.c("mic_gated", "mu_zc_sign"); P.c("mu_zc_sign", "mu_zc_diff")
    P.c("mu_zc_diff", "mu_zc_abs"); P.c("mu_zc_abs", "mu_zc_lp")
    P.obj("mu_half_sr", "/ 2", x + 620, 330)
    P.c("sr", "mu_half_sr")
    # Ten times a second: store the loudness (shaped by "react"), the brightness and the slow level.
    P.obj("mu_load", "loadbang", x + 700, 270)
    P.obj("mu_tick", "metro 100", x + 700, 300)
    P.c("mu_load", "mu_tick")
    P.obj("mu_snap_slow", "snapshot~", x + 300, 420)
    P.obj("mu_snap_zc", "snapshot~", x + 450, 420)
    P.obj("mu_tick_t", "t b b b", x + 700, 330)
    P.c("mu_tick", "mu_tick_t")
    P.c("mu_tick_t", "mu_snap_zc", 0, 0); P.c("mu_tick_t", "mu_snap_slow", 1, 0)
    P.c("mu_slow_lp", "mu_snap_slow"); P.c("mu_zc_lp", "mu_snap_zc")
    # Loudness above the room's own quiet: the floor follows the quietest level lately (and forgets slowly),
    # so a quiet room plays nothing and a sudden or lively sound plays notes, whatever the mic's noise.
    P.obj("mu_fl_t", "t f f b", x + 150, 420)
    P.c("mu_snap_slow", "mu_fl_t")
    P.obj("mu_fl_rd", "value mfloor", x + 220, 450)
    ex("mu_fl_new", "min($f1,$f2+0.03)", x + 150, 480)
    P.obj("mu_fl_t2", "t f f", x + 150, 510)
    P.obj("mu_fl_wr", "value mfloor", x + 220, 540)
    ex("mu_fl_thr", "min(max($f1,46),58)+4", x + 150, 570)
    ex("mu_loud01", "min(max(($f1-$f2)/32,0),1)", x + 300, 600)     # 0 = at the room's quiet, 1 = 32 dB above it
    P.c("mu_fl_t", "mu_fl_rd", 2, 0); P.c("mu_fl_rd", "mu_fl_new", 0, 1)
    P.c("mu_fl_t", "mu_fl_new", 1, 0); P.c("mu_fl_new", "mu_fl_t2")
    P.c("mu_fl_t2", "mu_fl_wr", 1, 0); P.c("mu_fl_t2", "mu_fl_thr", 0, 0)
    P.c("mu_fl_thr", "mu_loud01", 0, 1)
    P.c("mu_fl_t", "mu_loud01", 0, 0)
    P.obj("mu_fl_init", "loadbang", x + 220, 420)
    P.msg("mu_fl_init_msg", "58", x + 220, 435)
    P.obj("mu_fl_init_wr", "value mfloor", x + 220, 465)
    P.c("mu_fl_init", "mu_fl_init_msg"); P.c("mu_fl_init_msg", "mu_fl_init_wr")
    ex("mu_eff", "(1-$f2)*0.4+$f2*$f1", x + 150, 640)                  # liveliness: the room (react = 1) or a steady middle (react = 0)
    P.c("mu_loud01", "mu_eff"); P.c("mu_r_react", "mu_eff", 0, 1)
    P.obj("mu_v_loud", "value mloud", x + 150, 480)
    P.c("mu_eff", "mu_v_loud")
    ex("mu_zc_hz", "$f1*$f2", x + 450, 450)
    P.c("mu_snap_zc", "mu_zc_hz"); P.c("mu_half_sr", "mu_zc_hz", 0, 1)
    ex("mu_bright", "min(max((69+17.3123*ln(max($f1,1)/440)-50)/50,0),1)", x + 450, 480)    # 0 = dull and low, 1 = hissy and high
    P.c("mu_zc_hz", "mu_bright")
    P.obj("mu_v_bright", "value mbright", x + 450, 510)
    P.c("mu_bright", "mu_v_bright")
    # Sudden loud sounds: the level jumps well above its recent average.
    ex("mu_onset_thr", "14-8*$f1", x, 330)
    P.c("mu_r_react", "mu_onset_thr")
    ex("mu_onset", "(($f1-$f2)>$f3)*($f1>46)", x + 300, 450)   # a real jump, and not just room noise
    P.c("mu_r_level", "mu_onset"); P.c("mu_snap_slow", "mu_onset", 0, 1)
    P.c("mu_onset_thr", "mu_onset", 0, 2)
    P.obj("mu_onset_sel", "sel 1", x + 300, 480)
    P.c("mu_onset", "mu_onset_sel")

    # ---- on / off: the switch opens the gates and the first chord appears at once ----
    P.obj("mu_r_on", "r music_on", x + 800, 50)
    P.obj("mu_on_sel", "sel 1", x + 800, 80)
    P.c("mu_r_on", "mu_on_sel")

    # ---- chimes: four voices taken in turn, each a bell-like tone with two overtones ----
    cx = x
    cy = 600
    P.obj("mu_deg", "t b b b f", cx, cy)                                  # in: a velocity from 0 to 1
    # (the three paths below each end in "mu_note": a scale degree in, a chime out)
    degree_in, degree_hz = degree_to_hz("mu_c", cx + 200, cy + 60)
    P.obj("mu_note_t", "t b f", cx + 200, cy + 250)
    P.c(degree_hz, "mu_note_t")
    P.obj("mu_v_freq", "value cfreq", cx + 260, cy + 280)
    P.c("mu_note_t", "mu_v_freq", 1, 0)
    P.obj("mu_rr", "f", cx + 200, cy + 310)
    P.obj("mu_rr_add", "+ 1", cx + 200, cy + 340)
    P.obj("mu_rr_mod", "mod 4", cx + 200, cy + 370)
    P.obj("mu_rr_sel", "sel 0 1 2 3", cx + 200, cy + 400)
    # Each chime gets its own length and colour, so a run of notes does not sound stamped out.
    P.obj("mu_tim_t", "t b b b", cx + 200, cy + 290)
    P.c("mu_note_t", "mu_tim_t", 0, 0)
    P.obj("mu_tim_rd", "random 1000", cx + 330, cy + 310)
    ex("mu_tim_dec", f"{CHIME_DECAY_MS[0]}+{CHIME_DECAY_MS[1] - CHIME_DECAY_MS[0]}*$f1/1000", cx + 330, cy + 340)
    P.obj("mu_tim_wd", "value cdec", cx + 330, cy + 370)
    P.c("mu_tim_t", "mu_tim_rd", 2, 0); P.c("mu_tim_rd", "mu_tim_dec"); P.c("mu_tim_dec", "mu_tim_wd")
    P.obj("mu_tim_rb", "random 1000", cx + 450, cy + 310)
    ex("mu_tim_br", f"{CHIME_OVERTONE[0]}+{CHIME_OVERTONE[1] - CHIME_OVERTONE[0]}*$f1/1000", cx + 450, cy + 340)
    P.obj("mu_tim_wb", "value cbright", cx + 450, cy + 370)
    P.c("mu_tim_t", "mu_tim_rb", 1, 0); P.c("mu_tim_rb", "mu_tim_br"); P.c("mu_tim_br", "mu_tim_wb")
    P.c("mu_tim_t", "mu_rr", 0, 0)
    P.c("mu_rr", "mu_rr_add"); P.c("mu_rr_add", "mu_rr_mod"); P.c("mu_rr_mod", "mu_rr", 0, 1)
    P.c("mu_rr", "mu_rr_sel")
    P.obj("mu_v_vel", "value cvel", cx, cy + 40)
    P.c("mu_deg", "mu_v_vel", 3, 0)
    voices = []
    for k in range(4):
        vx = cx + 600 + k * 260
        P.obj(f"mu_v{k}_trig", "t b b b b", vx, cy)
        P.c("mu_rr_sel", f"mu_v{k}_trig", k, 0)
        P.obj(f"mu_v{k}_f", "value cfreq", vx + 60, cy + 30)
        P.obj(f"mu_v{k}_ft", "t f f f", vx + 60, cy + 60)
        P.obj(f"mu_v{k}_f2", "* 2", vx + 100, cy + 90)
        P.obj(f"mu_v{k}_f3", "* 3", vx + 160, cy + 90)
        P.obj(f"mu_v{k}_o1", "osc~", vx + 60, cy + 120)
        P.obj(f"mu_v{k}_o2", "osc~", vx + 100, cy + 120)
        P.obj(f"mu_v{k}_o3", "osc~", vx + 160, cy + 120)
        P.obj(f"mu_v{k}_g2", "*~ 0.3", vx + 100, cy + 150)
        P.obj(f"mu_v{k}_g3", "*~ 0.1", vx + 160, cy + 150)
        P.c(f"mu_v{k}_trig", f"mu_v{k}_f", 3, 0)
        P.obj(f"mu_v{k}_br", "value cbright", vx + 220, cy + 30)
        P.obj(f"mu_v{k}_br3", "/ 3", vx + 220, cy + 60)
        P.c(f"mu_v{k}_trig", f"mu_v{k}_br", 2, 0)
        P.c(f"mu_v{k}_br", f"mu_v{k}_g2", 0, 1); P.c(f"mu_v{k}_br", f"mu_v{k}_br3"); P.c(f"mu_v{k}_br3", f"mu_v{k}_g3", 0, 1)
        P.obj(f"mu_v{k}_dec", "value cdec", vx + 30, cy + 15)
        P.c(f"mu_v{k}_trig", f"mu_v{k}_dec", 1, 0)
        P.c(f"mu_v{k}_f", f"mu_v{k}_ft")
        P.c(f"mu_v{k}_ft", f"mu_v{k}_o1", 2, 0)
        P.c(f"mu_v{k}_ft", f"mu_v{k}_f2", 1, 0); P.c(f"mu_v{k}_f2", f"mu_v{k}_o2")
        P.c(f"mu_v{k}_ft", f"mu_v{k}_f3", 0, 0); P.c(f"mu_v{k}_f3", f"mu_v{k}_o3")
        P.c(f"mu_v{k}_o2", f"mu_v{k}_g2"); P.c(f"mu_v{k}_o3", f"mu_v{k}_g3")
        P.sig2(f"mu_v{k}_s12", "+~", f"mu_v{k}_o1", f"mu_v{k}_g2", vx + 60, cy + 180)
        P.sig2(f"mu_v{k}_s", "+~", f"mu_v{k}_s12", f"mu_v{k}_g3", vx + 60, cy + 210)
        P.obj(f"mu_v{k}_vel", "value cvel", vx, cy + 30)
        P.c(f"mu_v{k}_trig", f"mu_v{k}_vel", 0, 0)
        P.obj(f"mu_v{k}_pk", "pack f 1600", vx, cy + 45)                 # velocity, decay (ms)
        P.c(f"mu_v{k}_dec", f"mu_v{k}_pk", 0, 1)
        P.msg(f"mu_v{k}_env_msg", ("0, " + BS + "$1 4, 0 " + BS + "$2 4").replace(",", comma), vx, cy + 60)
        P.obj(f"mu_v{k}_env", "vline~", vx, cy + 90)
        P.c(f"mu_v{k}_vel", f"mu_v{k}_pk"); P.c(f"mu_v{k}_pk", f"mu_v{k}_env_msg"); P.c(f"mu_v{k}_env_msg", f"mu_v{k}_env")
        P.sig2(f"mu_v{k}_out", "*~", f"mu_v{k}_s", f"mu_v{k}_env", vx + 60, cy + 240)
        voices.append(f"mu_v{k}_out")
    acc = voices[0]
    for i, v in enumerate(voices[1:]):
        acc = P.sig2(f"mu_chime_acc{i}", "+~", acc, v, cx + 600, cy + 280 + 30 * i)
    P.obj("mu_chime_scale", "*~ 0.22", cx + 600, cy + 380)
    P.c(acc, "mu_chime_scale")
    P.obj("mu_chime_lp", "lop~ 3000", cx + 600, cy + 410)
    P.c("mu_chime_scale", "mu_chime_lp")
    # mu_deg: store velocity, then pick the next note. The melody walks a step or two from the last chime
    # (never the same note twice), around the register the brightness asks for, and turns back at its edges.
    P.obj("mu_jit", "random 4", cx + 100, cy + 40)
    ex("mu_jit_m", "$f1-2+($f1>=2)", cx + 100, cy + 70)                   # -2, -1, +1 or +2 scale steps
    P.c("mu_deg", "mu_jit", 2, 0); P.c("mu_jit", "mu_jit_m")
    P.obj("mu_rd_last", "value clast", cx + 160, cy + 70)
    P.c("mu_deg", "mu_rd_last", 1, 0)
    ex("mu_pick", f"min(max(if(abs($f4+$f2-int($f1*2*$f3+0.5)-$f3)>{CHIME_SPAN},$f4-$f2,$f4+$f2),"
                  f"int($f1*2*$f3+0.5)+$f3-{CHIME_SPAN}),int($f1*2*$f3+0.5)+$f3+{CHIME_SPAN})", cx, cy + 100)
    P.obj("mu_rd_pick", "value mbright", cx, cy + 70)                     # a bang makes it output its number
    P.c("mu_deg", "mu_rd_pick", 0, 0)
    P.c("mu_rd_pick", "mu_pick", 0, 0)
    P.c("mu_r_n", "mu_pick", 0, 2)
    P.c("mu_jit_m", "mu_pick", 0, 1)
    P.c("mu_rd_last", "mu_pick", 0, 3)
    P.obj("mu_pick_t", "t f f", cx, cy + 130)
    P.obj("mu_wr_last", "value clast", cx + 60, cy + 160)
    P.c("mu_pick", "mu_pick_t"); P.c("mu_pick_t", "mu_wr_last", 1, 0)
    P.c("mu_pick_t", degree_in)
    P.obj("mu_note_s", "s chime_deg", cx - 100, cy + 160)              # every note played, for the tests
    P.c("mu_pick_t", "mu_note_s")
    P.obj("mu_chime_s", "s chime_note", cx - 100, cy + 180)            # chimes only: the app's motif memory listens
    P.c("mu_pick_t", "mu_chime_s")
    # A remembered phrase coming back (motif memory, in the app): [motif <scale step> <velocity>( plays one chime.
    P.obj("mu_mo_r", "r motif", cx - 300, cy)
    P.obj("mu_mo_up", "unpack f f", cx - 300, cy + 20)
    P.obj("mu_mo_vel", "value cvel", cx - 240, cy + 40)
    P.obj("mu_mo_t", "t f f f", cx - 300, cy + 60)
    P.obj("mu_mo_s", "s chime_deg", cx - 300, cy + 90)
    P.c("mu_mo_r", "mu_mo_up"); P.c("mu_mo_up", "mu_mo_vel", 1, 0); P.c("mu_mo_up", "mu_mo_t", 0, 0)
    P.c("mu_mo_t", "mu_mo_s", 2, 0); P.c("mu_mo_t", degree_in, 0, 0)
    P._late_dn = getattr(P, "_late_dn", []) + [("mu_mo_t", "mu_dnc_t")]   # it counts as a chime for density

    # ---- density memory: every chime adds 1 (a walking-arpeggio note, the rhythm bed, DENSITY_ARP_WEIGHT), and the
    # count fades away over DENSITY_S ----
    for nm, w, src in (("c", 1, "mu_pick_t"), ("a", DENSITY_ARP_WEIGHT, "mu_rest_gate")):
        P.obj(f"mu_dn{nm}_t", "t b", x - 300 + 60 * (nm == "a"), 620)
        P.obj(f"mu_dn{nm}_rd", "value mdens", x - 300 + 60 * (nm == "a"), 640)
        P.obj(f"mu_dn{nm}_add", f"+ {w}", x - 300 + 60 * (nm == "a"), 660)
        P.obj(f"mu_dn{nm}_wr", "value mdens", x - 300 + 60 * (nm == "a"), 680)
        P._late_dn = getattr(P, "_late_dn", []) + [(src, f"mu_dn{nm}_t")]
        P.c(f"mu_dn{nm}_t", f"mu_dn{nm}_rd"); P.c(f"mu_dn{nm}_rd", f"mu_dn{nm}_add"); P.c(f"mu_dn{nm}_add", f"mu_dn{nm}_wr")
    P.obj("mu_dn_tick", "metro 250", x - 200, 600)
    P.c("mu_load", "mu_dn_tick")
    P.obj("mu_dn_rd2", "value mdens", x - 200, 640)
    P.obj("mu_dn_fade", f"* {math.exp(-0.25 / DENSITY_S):.5f}", x - 200, 660)
    P.obj("mu_dn_wr2", "value mdens", x - 200, 680)
    P.obj("mu_dn_on", "* 1", x - 200, 670)                              # density_on 0 (tests only) forgets at once
    P.obj("mu_dn_r_on", "r density_on", x - 120, 650); P.c("mu_dn_r_on", "mu_dn_on", 0, 1)
    P.c("mu_dn_tick", "mu_dn_rd2"); P.c("mu_dn_rd2", "mu_dn_fade"); P.c("mu_dn_fade", "mu_dn_on"); P.c("mu_dn_on", "mu_dn_wr2")
    keep = f"1000/(1+pow($f2/{DENSITY_BUSY},2))"                       # chance in 1000 a chime still plays

    # Path 1, sudden sounds: a chime whose loudness follows the room.
    P.obj("mu_ons_gate", "spigot 1", x + 300, 510)
    P.obj("mu_ons_gate_on", "spigot", x + 300, 540)
    P.c("mu_onset_sel", "mu_ons_gate")
    P.obj("mu_ons_t", "t b b b", x + 300, 570)
    P.msg("mu_ons_close", "0", x + 360, 600); P.msg("mu_ons_open", "1", x + 420, 600)
    P.obj("mu_ons_wait", "del 700", x + 380, 630)
    P.c("mu_ons_gate", "mu_ons_gate_on"); P.c("mu_ons_gate_on", "mu_ons_t")
    P.c("mu_ons_t", "mu_ons_close", 2, 0); P.c("mu_ons_close", "mu_ons_gate", 0, 1)
    P.c("mu_ons_t", "mu_ons_wait", 1, 0); P.c("mu_ons_wait", "mu_ons_open"); P.c("mu_ons_open", "mu_ons_gate", 0, 1)
    ex("mu_ons_vel", "(0.3+0.5*$f1)*$f2", x + 300, 660)              # in a pocket the "sudden sound" may be rustle
    P.obj("mu_rd_ons", "value mloud", x + 300, 640)
    P.obj("mu_ons_rt", "t b b", x + 240, 610)
    P.obj("mu_ons_hush", "value phush", x + 240, 640)
    P.c("mu_ons_t", "mu_ons_rt", 0, 0); P.c("mu_ons_rt", "mu_ons_hush", 1, 0); P.c("mu_ons_hush", "mu_ons_vel", 0, 1)
    P.c("mu_ons_rt", "mu_rd_ons", 0, 0); P.c("mu_rd_ons", "mu_ons_vel")
    # While you walk, a sudden-sound chime waits for the next footstep or half-step, so it falls in with the
    # arpeggio instead of landing anywhere (Samuel). Standing still it plays at once.
    P.obj("mu_q_now", "spigot 1", x + 200, 690)                      # not walking: straight through
    P.obj("mu_q_hold", "spigot 0", x + 300, 690)                     # walking: keep the latest one for the next slot
    P.obj("mu_dn1_t", "t f b b", x + 200, 670)                        # busy lately? skip some
    P.obj("mu_dn1_rnd", "random 1000", x + 260, 680); P.obj("mu_dn1_rd", "value mdens", x + 330, 680)
    ex("mu_dn1_keep", f"$f1<{keep}", x + 260, 690)
    P.obj("mu_dn1_gate", "spigot", x + 200, 695)
    P.c("mu_ons_vel", "mu_dn1_t"); P.c("mu_dn1_t", "mu_dn1_rd", 2, 0); P.c("mu_dn1_rd", "mu_dn1_keep", 0, 1)
    P.c("mu_dn1_t", "mu_dn1_rnd", 1, 0); P.c("mu_dn1_rnd", "mu_dn1_keep"); P.c("mu_dn1_keep", "mu_dn1_gate", 0, 1)
    P.c("mu_dn1_t", "mu_dn1_gate", 0, 0)
    P.c("mu_dn1_gate", "mu_q_now"); P.c("mu_dn1_gate", "mu_q_hold")
    P.c("mu_q_now", "mu_deg")
    P.obj("mu_q_store", "f", x + 300, 720)
    P.c("mu_q_hold", "mu_q_store", 0, 1)
    P.obj("mu_q_has", "moses 0.000001", x + 300, 750)
    P.obj("mu_q_go", "t f b", x + 300, 780)                          # clear the store, then play
    P.msg("mu_q_clear", "0", x + 380, 750)
    P.c("mu_q_store", "mu_q_has"); P.c("mu_q_has", "mu_q_go", 1, 0)
    P.c("mu_q_go", "mu_q_clear", 1, 0); P.c("mu_q_clear", "mu_q_store", 0, 1)
    P.c("mu_q_go", "mu_deg", 0, 0)

    # Path 2, a slow pattern while you are still: now and then a chime, more often in a livelier room.
    P.obj("mu_still_tick", "metro 250", x + 800, 600)
    P.c("mu_load", "mu_still_tick")
    P.obj("mu_still_gate", "spigot 1", x + 800, 630)
    P.obj("mu_still_on", "spigot", x + 800, 660)
    P.c("mu_still_tick", "mu_still_gate"); P.c("mu_still_gate", "mu_still_on")
    P.obj("mu_still_t", "t b b", x + 800, 690)
    P.c("mu_still_on", "mu_still_t")
    P.obj("mu_roll", "random 1000", x + 800, 720)
    ex("mu_chance", "$f1<$f2", x + 800, 750)
    ex("mu_p", f"320*pow($f1,3)/(1+pow($f2/{DENSITY_BUSY},2))", x + 900, 720)   # chance in 1000 every 0.25 s: 0 in a quiet room, about 1 in 3 when lively (less when busy lately)
    P.obj("mu_p_dn", "value mdens", x + 980, 690)
    P.obj("mu_rd_p", "value mloud", x + 900, 690)
    P.c("mu_still_t", "mu_roll", 0, 0)
    P.obj("mu_p_t", "t b b", x + 900, 680)
    P.c("mu_still_t", "mu_p_t", 1, 0); P.c("mu_p_t", "mu_p_dn", 1, 0); P.c("mu_p_dn", "mu_p", 0, 1)
    P.c("mu_p_t", "mu_rd_p", 0, 0); P.c("mu_rd_p", "mu_p"); P.c("mu_p", "mu_chance", 0, 1)
    P.c("mu_roll", "mu_chance")
    P.obj("mu_chance_sel", "sel 1", x + 800, 780)
    P.c("mu_chance", "mu_chance_sel")
    ex("mu_still_vel", "(0.12+0.5*$f1)*$f2", x + 800, 840)
    P.obj("mu_still_load", "t b b", x + 800, 810)
    P.obj("mu_rd_still", "value mloud", x + 900, 810)
    P.obj("mu_still_hush", "value phush", x + 980, 810)
    P.c("mu_still_load", "mu_still_hush", 1, 0); P.c("mu_still_hush", "mu_still_vel", 0, 1)
    P.c("mu_chance_sel", "mu_still_load"); P.c("mu_still_load", "mu_rd_still"); P.c("mu_rd_still", "mu_still_vel")
    P.c("mu_still_vel", "mu_deg")
    P.msg("mu_still_off", "0", x + 900, 600); P.msg("mu_still_back", "1", x + 960, 600)
    P.c("mu_still_off", "mu_still_gate", 0, 1); P.c("mu_still_back", "mu_still_gate", 0, 1)

    # Path 3, footsteps: an arpeggio around the current chord. Louder when you walk faster.
    P.obj("mu_r_step", "r step", x + 1100, 600)
    P.obj("mu_step_t", "t b f", x + 1100, 630)
    P.c("mu_r_step", "mu_step_t")
    ex("mu_pace", "1/max($f1,0.25)", x + 1200, 660)
    ex("mu_pace_f", "min(max(($f1-1)/1.6,0),1)", x + 1200, 690)       # 0 = ambling (1 step/s), 1 = brisk (2.6+)
    ex("mu_pace_vel", "(0.4+0.6*$f1)*(0.8+0.4*$f2)", x + 1200, 720)    # a harder step pushes the note
    P.obj("mu_r_strength", "r step_strength", x + 1350, 660)
    P.c("mu_r_strength", "mu_pace_vel", 0, 1)
    P.c("mu_step_t", "mu_pace", 1, 0); P.c("mu_pace", "mu_pace_f"); P.c("mu_pace_f", "mu_pace_vel")
    P.c("mu_pace_vel", "mu_v_vel")
    P.obj("mu_arp_gate", "spigot", x + 1100, 660)
    P.c("mu_step_t", "mu_arp_gate", 0, 0)
    P.obj("mu_arp_t", "t b b b b", x + 1100, 690)
    P.c("mu_arp_gate", "mu_arp_t")
    P.obj("mu_v_chord", "value mchord", x + 1100, 720)
    n_pat, bar = len(ARP_PATTERNS), len(ARP_PATTERNS[0])
    P.obj("mu_ptab", f"table arp_pat {n_pat * bar}", x + 1300, 20)
    P.msg("mu_ptab_init", f"{BS}; arp_pat 0 {' '.join(str(v) for pat in ARP_PATTERNS for v in pat)}", x + 1300, 50)
    P.c("mu_load", "mu_ptab_init")
    # step counter within the bar; at the start of each bar a different pattern is picked
    P.obj("mu_pat_i", "f", x + 1100, 750)
    P.obj("mu_pat_add", "+ 1", x + 1100, 780)
    P.obj("mu_pat_mod", f"mod {bar}", x + 1100, 810)
    P.c("mu_pat_i", "mu_pat_add"); P.c("mu_pat_add", "mu_pat_mod"); P.c("mu_pat_mod", "mu_pat_i", 0, 1)
    P.obj("mu_pat_it", "t f f", x + 1020, 780)
    P.c("mu_pat_i", "mu_pat_it")
    P.obj("mu_pat_bar", "sel 0", x + 960, 810)
    P.obj("mu_pat_rnd", "random 3", x + 960, 840)
    # the pace's pattern or a neighbour ($f1 0..2), never the one just played ($f2), pace 0..1 ($f3)
    top = n_pat - 1
    # (a repeat moves toward the pace's own pattern, so a stroll stays on the calm ones and a brisk walk on the busy)
    tgt = f"int($f3*{top}+0.5)"
    ex("mu_pat_new", f"if(min(max({tgt}+$f1-1, 0), {top})==$f2, "
                     f"if($f2<{tgt}, $f2+1, if($f2>{tgt}, $f2-1, if($f2<{top}, $f2+1, $f2-1))), "
                     f"min(max({tgt}+$f1-1, 0), {top}))", x + 960, 870)
    P.c("mu_pace_f", "mu_pat_new", 0, 2)
    P.obj("mu_pat_cur", "t f f", x + 960, 900)
    P.c("mu_pat_it", "mu_pat_bar", 1, 0); P.c("mu_pat_bar", "mu_pat_rnd"); P.c("mu_pat_rnd", "mu_pat_new")
    P.c("mu_pat_new", "mu_pat_cur"); P.c("mu_pat_cur", "mu_pat_new", 1, 1)
    ex("mu_pat_idx", f"$f1+{bar}*$f2", x + 1100, 830)
    P.c("mu_pat_cur", "mu_pat_idx", 0, 1); P.c("mu_pat_it", "mu_pat_idx", 0, 0)
    P.obj("mu_pat_tab", "tabread arp_pat", x + 1100, 845)
    P.c("mu_pat_idx", "mu_pat_tab")
    ex("mu_arp_deg", "$f1+$f2+$f3", x + 1100, 870)
    P.obj("mu_arp_n", "value scale_n", x + 1250, 780)
    P.c("mu_arp_t", "mu_arp_n", 2, 0)                                 # bang: output the scale size
    P.c("mu_arp_n", "mu_arp_deg", 0, 2)
    P.c("mu_arp_t", "mu_v_chord", 1, 0); P.c("mu_v_chord", "mu_arp_deg", 0, 1)
    P.c("mu_arp_t", "mu_pat_i", 0, 0)
    P.c("mu_pat_tab", "mu_arp_deg")
    # now and then a step rests (the bar still moves on)
    P.obj("mu_rest_rnd", "random 100", x + 1300, 690)
    ex("mu_rest_play", f"$f1>=({ARP_REST_SLOW_PCT}-{ARP_REST_SLOW_PCT - ARP_REST_FAST_PCT}*$f2"
                       f"+min({DENSITY_ARP_MAX},max(0,$f3-{DENSITY_ARP_FROM})*{DENSITY_ARP_PCT}))", x + 1300, 720)
    P.obj("mu_rest_dn", "value mdens", x + 1400, 690)
    P.c("mu_pace_f", "mu_rest_play", 0, 1)        # strolling rests more than walking briskly
    P.obj("mu_rest_gate", "spigot 1", x + 1100, 885)
    P.obj("mu_rest_t", "t b b", x + 1300, 680)
    P.c("mu_arp_t", "mu_rest_t", 3, 0); P.c("mu_rest_t", "mu_rest_dn", 1, 0); P.c("mu_rest_dn", "mu_rest_play", 0, 2)
    P.c("mu_rest_t", "mu_rest_rnd", 0, 0); P.c("mu_rest_rnd", "mu_rest_play"); P.c("mu_rest_play", "mu_rest_gate", 0, 1)
    P.c("mu_arp_deg", "mu_rest_gate")
    P.c("mu_rest_gate", degree_in); P.c("mu_rest_gate", "mu_note_s")
    for src, dst in getattr(P, "_late_dn", []):
        P.c(src, dst)
    # The arpeggio note itself needs the chime path's tail (frequency, round robin): it joins at degree_in.
    # Walking state: while steps keep coming the "still" pattern stays quiet.
    P.obj("mu_walk_t", "t b b", x + 1100, 900)
    P.c("mu_step_t", "mu_walk_t", 0, 0)
    P.obj("mu_walk_del", "del 2500", x + 1160, 930)
    P.c("mu_walk_t", "mu_still_off", 1, 0); P.c("mu_walk_t", "mu_walk_del", 0, 0)
    P.c("mu_walk_del", "mu_still_back")
    # Chime slots: every footstep, and halfway to the next one. Walking ends -> anything waiting plays.
    P.msg("mu_q_walk", "0", x + 200, 660); P.msg("mu_q_walk_h", "1", x + 260, 660)
    P.msg("mu_q_stop", "1", x + 200, 630); P.msg("mu_q_stop_h", "0", x + 260, 630)
    P.c("mu_walk_t", "mu_q_walk", 1, 0); P.c("mu_walk_t", "mu_q_walk_h", 1, 0)
    P.c("mu_q_walk", "mu_q_now", 0, 1); P.c("mu_q_walk_h", "mu_q_hold", 0, 1)
    P.c("mu_walk_del", "mu_q_stop"); P.c("mu_walk_del", "mu_q_stop_h")
    P.c("mu_q_stop", "mu_q_now", 0, 1); P.c("mu_q_stop_h", "mu_q_hold", 0, 1)
    P.c("mu_walk_del", "mu_q_store")
    P.obj("mu_q_half_clip", "clip 0.25 1.2", x + 1250, 930)
    P.obj("mu_q_half_ms", "* 500", x + 1250, 960)
    P.obj("mu_q_half", "del 250", x + 1160, 990)
    P.c("mu_step_t", "mu_q_half_clip", 1, 0); P.c("mu_q_half_clip", "mu_q_half_ms"); P.c("mu_q_half_ms", "mu_q_half", 0, 1)
    P.c("mu_walk_t", "mu_q_half", 0, 0)                                  # restarts the half-step timer
    P.c("mu_walk_t", "mu_q_store", 0, 0)                                 # on the step itself
    P.c("mu_q_half", "mu_q_store")
    # Groove: after half a minute of steady steps (the app sends "groove 1"), a soft note joins on every
    # half-step, a third above the last arpeggio note, fading in over a few seconds. It stops with the groove
    # or when you stop walking.
    P.obj("mu_gr_r", "r groove", x + 1400, 900)
    P.obj("mu_gr_chg", "change", x + 1400, 920)
    P.c("mu_gr_r", "mu_gr_chg")
    P.obj("mu_gr_gate", "spigot", x + 1250, 1010)
    P.c("mu_q_half", "mu_gr_gate"); P.c("mu_gr_chg", "mu_gr_gate", 0, 1)
    P.msg("mu_gr_off", "0", x + 1400, 960)
    P.c("mu_walk_del", "mu_gr_off"); P.c("mu_gr_off", "mu_gr_gate", 0, 1); P.c("mu_gr_off", "mu_gr_chg", 0, 0)
    P.obj("mu_gr_sel", "sel 0 1", x + 1400, 990)
    P.msg("mu_gr_down", "0 300", x + 1400, 1010)
    P.msg("mu_gr_up", f"0, 1 {GROOVE_FADE_IN_MS}".replace(",", " " + BS + ","), x + 1460, 1010)
    P.obj("mu_gr_ln", "line 0 50", x + 1400, 1030)
    P.c("mu_gr_chg", "mu_gr_sel"); P.c("mu_gr_sel", "mu_gr_down", 0, 0); P.c("mu_gr_sel", "mu_gr_up", 1, 0)
    P.c("mu_gr_down", "mu_gr_ln"); P.c("mu_gr_up", "mu_gr_ln")
    P.obj("mu_gr_t", "t b b", x + 1250, 1040)
    P.c("mu_gr_gate", "mu_gr_t")
    P.obj("mu_gr_pv", "value apvel", x + 1300, 1060)                   # this step's arpeggio loudness
    ex("mu_gr_vel", f"$f1*{GROOVE_VEL}*$f2", x + 1300, 1080)
    P.c("mu_gr_ln", "mu_gr_vel", 0, 1)
    P.obj("mu_gr_cv", "value cvel", x + 1300, 1100)
    P.c("mu_gr_t", "mu_gr_pv", 1, 0); P.c("mu_gr_pv", "mu_gr_vel"); P.c("mu_gr_vel", "mu_gr_cv")
    P.obj("mu_gr_last", "value alast", x + 1250, 1080)
    ex("mu_gr_deg", "$f1+2", x + 1250, 1110)
    P.c("mu_gr_t", "mu_gr_last", 0, 0); P.c("mu_gr_last", "mu_gr_deg")
    P.c("mu_gr_deg", degree_in); P.c("mu_gr_deg", "mu_note_s")
    P.obj("mu_ap_store", "value apvel", x + 1350, 740)
    P.c("mu_pace_vel", "mu_ap_store")
    P.obj("mu_al_store", "value alast", x + 1150, 900)
    P.c("mu_rest_gate", "mu_al_store")
    # Gates follow the on/off switch.
    for g in ("mu_ons_gate_on", "mu_still_on", "mu_arp_gate"):
        P.c("mu_r_on", g, 0, 1)

    # ---- pad: four soft voices (root, third, fifth, octave) that glide to a new chord now and then ----
    px = x + 1500
    P.obj("mu_chord_tick", "metro 7000", px, 20)
    P.c("mu_load", "mu_chord_tick")
    P.obj("mu_chord_go", "t b b b", px, 50)
    P.c("mu_chord_tick", "mu_chord_go")
    P.c("mu_scale_t", "mu_chord_go", 0, 0); P.c("mu_key_t", "mu_chord_go", 0, 0)
    P.obj("mu_pad_jit", "random 3", px + 80, 80)
    P.obj("mu_pad_jit_m", "- 1", px + 80, 110)
    P.obj("mu_r_pool_n", "r pool_n", px + 240, 80)
    # which of the scale's main chords: brighter sound, higher chord (plus a little wander)
    ex("mu_pad_idx", "int(min(max($f1*($f3-1)+$f2*0.9,0),$f3-1)+0.5)", px, 140)
    P.c("mu_chord_go", "mu_pad_jit", 1, 0); P.c("mu_pad_jit", "mu_pad_jit_m"); P.c("mu_pad_jit_m", "mu_pad_idx", 0, 1)
    P.c("mu_r_pool_n", "mu_pad_idx", 0, 2)
    P.obj("mu_rd_root", "value mbright", px + 160, 110)
    P.c("mu_chord_go", "mu_rd_root", 0, 0); P.c("mu_rd_root", "mu_pad_idx")
    P.obj("mu_pad_pool", "tabread chord_pool", px, 160)
    P.c("mu_pad_idx", "mu_pad_pool")
    # key drift: the pool's chords moved by the drift (mdrift scale steps); no contrast chord while drifted
    P.obj("mu_dr_pt", "t f b b", px, 170)
    P.c("mu_pad_pool", "mu_dr_pt")
    P.obj("mu_dr_rd1", "value mdrift", px + 60, 172); P.obj("mu_dr_rd2", "value mdrift", px + 120, 172)
    P.obj("mu_dr_n", "value scale_n", px + 180, 172)
    # now and then the contrast chord instead (when the scale has one)
    P.obj("mu_pad_roll", "random 100", px + 160, 140)
    P.c("mu_chord_go", "mu_pad_roll", 2, 0)
    P.obj("mu_r_pool_x", "r pool_x", px + 300, 140)
    ex("mu_pad_root", f"if($f2<{CONTRAST_PCT}&&$f3>=0&&$f4==0,$f3,$f1)", px, 180)
    P.c("mu_dr_pt", "mu_pad_root", 0, 0); P.c("mu_pad_roll", "mu_pad_root", 0, 1); P.c("mu_r_pool_x", "mu_pad_root", 0, 2)
    ex("mu_dr_apply", "($f1+$f2)%$f3", px, 190)
    P.c("mu_dr_pt", "mu_dr_rd1", 2, 0); P.c("mu_dr_rd1", "mu_pad_root", 0, 3)
    P.c("mu_dr_pt", "mu_dr_rd2", 1, 0); P.c("mu_dr_rd2", "mu_dr_apply", 0, 1)
    P.c("mu_dr_pt", "mu_dr_n", 1, 0); P.c("mu_dr_n", "mu_dr_apply", 0, 2)
    P.c("mu_pad_root", "mu_dr_apply")
    P.obj("mu_pad_root_v", "t f f b", px, 200)
    P.c("mu_dr_apply", "mu_pad_root_v")
    # the drift itself: every 3-6 minutes while the music plays (and the switch is on) a new home, often back home
    P.obj("mu_dr_r_set", "r drift_set", px + 300, 20); P.obj("mu_dr_wr", "value mdrift", px + 300, 40)
    P.c("mu_dr_r_set", "mu_dr_wr")
    P.obj("mu_dr_s", "s drift", px + 380, 40)                       # for the tests
    P.c("mu_dr_r_set", "mu_dr_s")
    P.obj("mu_dr_del", "del 240000", px + 300, 80)
    P.obj("mu_dr_sched", "t b b", px + 300, 100)
    P.obj("mu_dr_rms", "random 1000", px + 380, 110)
    ex("mu_dr_ms", f"{DRIFT_MIN_S * 1000}+{(DRIFT_MAX_S - DRIFT_MIN_S)}*$f1", px + 380, 130)
    P.c("mu_dr_sched", "mu_dr_rms", 0, 0); P.c("mu_dr_rms", "mu_dr_ms"); P.c("mu_dr_ms", "mu_dr_del")
    P.c("mu_on_sel", "mu_dr_sched")                                  # the clock starts with the music
    P.obj("mu_dr_now", "r drift_now", px + 460, 80)                  # (tests: drift at once)
    P.obj("mu_dr_fire", "t b b b b b", px + 300, 150)
    P.c("mu_dr_del", "mu_dr_fire"); P.c("mu_dr_now", "mu_dr_fire")
    P.obj("mu_dr_on", "r music_drift", px + 560, 80); P.obj("mu_dr_onv", "f 1", px + 560, 110)
    P.c("mu_dr_on", "mu_dr_onv", 0, 1)
    P.obj("mu_dr_r1", "random 1000", px + 360, 180); P.obj("mu_dr_r2", "random 1000", px + 420, 180)
    P.obj("mu_dr_cur", "value mdrift", px + 480, 180); P.obj("mu_dr_nn", "value drift_nv", px + 540, 180)
    P.obj("mu_dr_rnn", "r drift_n", px + 600, 160); P.obj("mu_dr_wnn", "value drift_nv", px + 600, 180)
    P.c("mu_dr_rnn", "mu_dr_wnn")
    ex("mu_dr_pick", f"if($f5==0,0,if($f3!=0&&$f1<{DRIFT_HOME_PCT * 10},0,if(drift_opts[int($f2*$f4/1000)]==$f3,"
                     f"drift_opts[(int($f2*$f4/1000)+1)%max($f4,1)],drift_opts[int($f2*$f4/1000)])))", px + 300, 210)
    P.c("mu_dr_fire", "mu_dr_onv", 4, 0); P.c("mu_dr_onv", "mu_dr_pick", 0, 4)
    P.c("mu_dr_fire", "mu_dr_nn", 3, 0); P.c("mu_dr_nn", "mu_dr_pick", 0, 3)
    P.c("mu_dr_fire", "mu_dr_cur", 2, 0); P.c("mu_dr_cur", "mu_dr_pick", 0, 2)
    P.c("mu_dr_fire", "mu_dr_r2", 1, 0); P.c("mu_dr_r2", "mu_dr_pick", 0, 1)
    P.c("mu_dr_fire", "mu_dr_r1", 0, 0); P.c("mu_dr_r1", "mu_dr_pick")
    P.obj("mu_dr_out", "t b f", px + 300, 240)
    P.c("mu_dr_pick", "mu_dr_out"); P.c("mu_dr_out", "mu_dr_wr", 1, 0); P.c("mu_dr_out", "mu_dr_s", 1, 0)
    P.c("mu_dr_out", "mu_chord_go", 0, 0); P.c("mu_dr_out", "mu_dr_sched", 0, 0)
    # switching drift off brings the home chord back at once
    P.obj("mu_dr_off", "sel 0", px + 560, 130); P.msg("mu_dr_home", "0", px + 560, 150)
    P.c("mu_dr_on", "mu_dr_off"); P.c("mu_dr_off", "mu_dr_home"); P.c("mu_dr_home", "mu_dr_out")
    P.obj("mu_chord_s", "s pad_chord", px + 240, 230)               # for the tests
    P.c("mu_pad_root_v", "mu_chord_s", 1, 0)
    P.obj("mu_v_chord_set", "value mchord", px + 80, 200)
    P.c("mu_pad_root_v", "mu_v_chord_set", 1, 0)
    # Instant chord when the music is switched on; slow glides afterwards.
    P.msg("mu_glide0", "0", px + 160, 20); P.msg("mu_glide1", str(PAD_GLIDE_MS), px + 200, 20)
    P.obj("mu_glide_s", "s pad_glide", px + 160, 50)
    P.c("mu_glide0", "mu_glide_s"); P.c("mu_glide1", "mu_glide_s")
    P.obj("mu_glide_wait", "del 400", px + 240, 50)
    P.obj("mu_on_t", "t b b b", x + 800, 110)          # glide off, pick the chord, then glide on again
    P.c("mu_on_sel", "mu_on_t")
    P.c("mu_on_t", "mu_glide0", 2, 0); P.c("mu_on_t", "mu_chord_go", 1, 0); P.c("mu_on_t", "mu_glide_wait", 0, 0)
    P.c("mu_glide_wait", "mu_glide1")
    P.obj("mu_r_glide", "r pad_glide", px + 160, 80)
    # Crossfade: every chord change flips to the other of two oscillator sets. The silent set takes the new notes at
    # once and fades in while the old one fades out, so no note slides through pitches outside the key.
    P.obj("mu_slot", "f", px + 400, 200)
    P.obj("mu_slot_add", "+ 1", px + 440, 200)
    P.obj("mu_slot_mod", "mod 2", px + 480, 200)
    P.c("mu_pad_root_v", "mu_slot", 2, 0)
    P.c("mu_slot", "mu_slot_add"); P.c("mu_slot_add", "mu_slot_mod"); P.c("mu_slot_mod", "mu_slot", 0, 1)
    P.obj("mu_slot_s", "s pad_slot", px + 400, 230)
    P.c("mu_slot_mod", "mu_slot_s")
    P.obj("mu_r_slot", "r pad_slot", px + 400, 260)
    for k in (0, 1):
        P.obj(f"mu_xf{k}_is", f"== {k}", px + 400 + 80 * k, 290)
        P.obj(f"mu_xf{k}_pk", f"pack 0 {PAD_GLIDE_MS}", px + 400 + 80 * k, 320)
        P.obj(f"mu_xf{k}", "line~", px + 400 + 80 * k, 350)
        P.c("mu_r_slot", f"mu_xf{k}_is"); P.c(f"mu_xf{k}_is", f"mu_xf{k}_pk"); P.c(f"mu_xf{k}_pk", f"mu_xf{k}")
        P.c("mu_r_glide", f"mu_xf{k}_pk", 0, 1)
    pad_sum = None
    offsets = ["+ 0", "+ 2", "+ 4", None]
    for i in range(4):
        vx = px + i * 160
        if offsets[i]:
            P.obj(f"mu_pad{i}_deg", offsets[i], vx, 230)
            P.c("mu_pad_root_v", f"mu_pad{i}_deg", 0, 0)
        else:
            P.obj(f"mu_pad{i}_deg", "expr $f1+$f2".replace("$", d), vx, 230)
            P.c("mu_pad_root_v", f"mu_pad{i}_deg", 0, 0)
            P.c("mu_r_n", f"mu_pad{i}_deg", 0, 1)
        dg_in, dg_hz = degree_to_hz(f"mu_p{i}", vx, 260)
        P.c(f"mu_pad{i}_deg", dg_in)
        parts = []
        for k in (0, 1):                                   # the two crossfaded sets of this voice
            kx = vx + 75 * k
            P.obj(f"mu_pad{i}_{k}_gate", "spigot", kx, 440)
            P.c(dg_hz, f"mu_pad{i}_{k}_gate"); P.c(f"mu_xf{k}_is", f"mu_pad{i}_{k}_gate", 0, 1)
            P.obj(f"mu_pad{i}_{k}_t", "t f f", kx, 460)
            P.obj(f"mu_pad{i}_{k}_det", "* 1.004", kx + 40, 480)
            P.obj(f"mu_pad{i}_{k}_o1", "osc~", kx, 500)
            P.obj(f"mu_pad{i}_{k}_o2", "osc~", kx + 40, 510)
            P.c(f"mu_pad{i}_{k}_gate", f"mu_pad{i}_{k}_t")
            P.c(f"mu_pad{i}_{k}_t", f"mu_pad{i}_{k}_o1", 0, 0)
            P.c(f"mu_pad{i}_{k}_t", f"mu_pad{i}_{k}_det", 1, 0); P.c(f"mu_pad{i}_{k}_det", f"mu_pad{i}_{k}_o2")
            P.sig2(f"mu_pad{i}_{k}_s", "+~", f"mu_pad{i}_{k}_o1", f"mu_pad{i}_{k}_o2", kx, 530)
            parts.append(P.sig2(f"mu_pad{i}_{k}_x", "*~", f"mu_pad{i}_{k}_s", f"mu_xf{k}", kx, 545))
        P.sig2(f"mu_pad{i}_sum", "+~", parts[0], parts[1], vx, 560)
        P.obj(f"mu_pad{i}_g", "*~ " + ("0.042", "0.033", "0.03", "0.021")[i], vx, 590)
        P.c(f"mu_pad{i}_sum", f"mu_pad{i}_g")
        pad_sum = f"mu_pad{i}_g" if pad_sum is None else P.sig2(f"mu_pad_acc{i}", "+~", pad_sum, f"mu_pad{i}_g", vx, 620)
    P.obj("mu_pad_lp", "lop~ 1500", px, 650)
    P.c(pad_sum, "mu_pad_lp")
    # The pad swells and fades with the room, and breathes slowly.
    ex("mu_pad_fac", "0.5+0.5*$f1", px + 300, 650)
    P.obj("mu_pad_fac_sig", "sig~", px + 300, 680); P.obj("mu_pad_fac_lp", "lop~ 0.4", px + 300, 710)
    P.c("mu_pad_fac", "mu_pad_fac_sig"); P.c("mu_pad_fac_sig", "mu_pad_fac_lp")
    P.obj("mu_pad_tick", "metro 200", px + 420, 620)
    P.obj("mu_rd_pad", "value mloud", px + 420, 650)
    P.c("mu_load", "mu_pad_tick"); P.c("mu_pad_tick", "mu_rd_pad"); P.c("mu_rd_pad", "mu_pad_fac")
    P.obj("mu_breath", "osc~ 0.08", px + 300, 740)
    P.obj("mu_breath_g", "*~ 0.125", px + 300, 770)
    P.obj("mu_breath_o", "+~ 0.875", px + 300, 800)
    P.c("mu_breath", "mu_breath_g"); P.c("mu_breath_g", "mu_breath_o")
    P.sig2("mu_pad_a", "*~", "mu_pad_lp", "mu_pad_fac_lp", px, 830)
    P.sig2("mu_pad_b", "*~", "mu_pad_a", "mu_breath_o", px, 860)

    # ---- bass: one low voice under the pad (Samuel's idea), so the chimes keep the upper register ----
    # It sits on the key's root and only sometimes moves to the chord's root, folded into 65-131 Hz, with a little
    # 2nd and 3rd harmonic so earbuds can play it. A note change dips out and back in (no slides). Each footstep
    # ducks it briefly while the walking beat plays, so it doesn't fight the kick.
    bx = px + 900
    P.obj("ba_in", "t f b b", bx, 230)
    P.c("mu_pad_root_v", "ba_in", 1, 0)
    P.obj("ba_roll", "random 100", bx + 80, 250)
    P.c("ba_in", "ba_roll", 1, 0)
    P.obj("ba_home", "value mdrift", bx + 160, 250)                    # the home note moves with the key drift
    P.c("ba_in", "ba_home", 2, 0)
    ex("ba_pick", f"if($f2<{BASS_FOLLOW_PCT},$f1,$f3)", bx, 270)
    P.c("ba_home", "ba_pick", 0, 2)
    P.c("ba_in", "ba_pick", 0, 0); P.c("ba_roll", "ba_pick", 0, 1)
    ba_deg, ba_hz = degree_to_hz("bad", bx, 290)
    P.c("ba_pick", ba_deg)
    ex("ba_fold", "if($f1/2>131,$f1/4,$f1/2)", bx, 460)
    P.c(ba_hz, "ba_fold")
    P.obj("ba_chg", "change", bx, 480)
    P.c("ba_fold", "ba_chg")
    P.obj("ba_ct", "t f b", bx, 500)
    P.c("ba_chg", "ba_ct")
    P.msg("ba_dip", f"0 {BASS_DIP_MS}", bx + 80, 520)
    P.c("ba_ct", "ba_dip", 1, 0)
    P.obj("ba_wait", f"pipe {BASS_DIP_MS}", bx, 520)
    P.c("ba_ct", "ba_wait", 0, 0)
    P.obj("ba_ft", "t b f", bx, 540)
    P.c("ba_wait", "ba_ft")
    P.msg("ba_rise", f"1 {BASS_RISE_MS}", bx + 80, 560)
    P.c("ba_ft", "ba_rise", 0, 0)
    P.obj("ba_env", "line~", bx + 80, 580)
    P.c("ba_dip", "ba_env"); P.c("ba_rise", "ba_env")
    P.obj("ba_f2", "* 2", bx + 60, 560); P.obj("ba_f3", "* 3", bx + 120, 560)
    P.c("ba_ft", "ba_f2", 1, 0); P.c("ba_ft", "ba_f3", 1, 0)
    P.obj("ba_o1", "osc~", bx, 600); P.obj("ba_o2", "osc~", bx + 60, 600); P.obj("ba_o3", "osc~", bx + 120, 600)
    P.c("ba_ft", "ba_o1", 1, 0); P.c("ba_f2", "ba_o2"); P.c("ba_f3", "ba_o3")
    P.obj("ba_g2", "*~ 0.35", bx + 60, 620); P.obj("ba_g3", "*~ 0.15", bx + 120, 620)
    P.c("ba_o2", "ba_g2"); P.c("ba_o3", "ba_g3")
    P.sig2("ba_s12", "+~", "ba_o1", "ba_g2", bx, 640)
    P.sig2("ba_s", "+~", "ba_s12", "ba_g3", bx, 655)
    P.sig2("ba_e", "*~", "ba_s", "ba_env", bx, 670)
    # footstep duck, only while the walking beat is switched on and audible
    P.obj("ba_r_step", "r step", bx + 200, 600)
    P.obj("ba_r_bl", "r beat_level", bx + 280, 600)
    P.obj("ba_r_bo", "r beat_on", bx + 360, 600)
    P.obj("ba_bl", "f", bx + 200, 630)
    ex("ba_duck", f"1-{BASS_DUCK}*($f1>0.02)*$f2", bx + 200, 660)
    P.obj("ba_step_b", "t b", bx + 200, 615)                    # the step brings its interval: only the bang matters
    P.c("ba_r_step", "ba_step_b"); P.c("ba_step_b", "ba_bl"); P.c("ba_r_bl", "ba_bl", 0, 1); P.c("ba_r_bo", "ba_duck", 0, 1)
    P.c("ba_bl", "ba_duck")
    P.msg("ba_duck_msg", ("$1 10, 1 " + str(BASS_DUCK_MS) + " 30").replace("$", BS + "$").replace(",", comma), bx + 200, 690)
    P.obj("ba_duck_env", "vline~", bx + 200, 720)
    P.c("ba_duck", "ba_duck_msg"); P.c("ba_duck_msg", "ba_duck_env")
    P.obj("ba_duck_init", "loadbang", bx + 300, 690); P.msg("ba_duck_one", "1", bx + 300, 705)
    P.c("ba_duck_init", "ba_duck_one"); P.c("ba_duck_one", "ba_duck_env")
    P.sig2("ba_d", "*~", "ba_e", "ba_duck_env", bx, 740)
    P.obj("ba_lp", "lop~ 700", bx, 760)
    P.c("ba_d", "ba_lp")
    P.obj("ba_g", f"*~ {BASS_GAIN}", bx, 780)
    P.c("ba_lp", "ba_g")
    P.sig2("ba_a", "*~", "ba_g", "mu_pad_fac_lp", bx, 800)        # swells with the room like the pad
    P.sig2("ba_b", "*~", "ba_a", "mu_breath_o", bx, 820)
    # register: 0 = low (bass only), 1 = mid (the pad as before), 2 = both
    P.obj("ba_r_reg", "r music_pad_reg", bx + 400, 760)
    P.obj("ba_reg_t", "t f f", bx + 400, 780)
    P.c("ba_r_reg", "ba_reg_t")
    P.obj("ba_mid_on", "!= 0", bx + 400, 800); P.obj("ba_low_on", "!= 1", bx + 480, 800)
    P.c("ba_reg_t", "ba_mid_on", 1, 0); P.c("ba_reg_t", "ba_low_on", 0, 0)
    for nm in ("mid", "low"):
        P.obj(f"ba_{nm}_pk", "pack f 300", bx + 400 + (80 if nm == "low" else 0), 820)
        P.obj(f"ba_{nm}_ln", "line~", bx + 400 + (80 if nm == "low" else 0), 840)
        P.c(f"ba_{nm}_on", f"ba_{nm}_pk"); P.c(f"ba_{nm}_pk", f"ba_{nm}_ln")
    P.obj("ba_reg_init", "loadbang", bx + 560, 760); P.msg("ba_reg_both", "1", bx + 560, 780)
    P.c("ba_reg_init", "ba_reg_both"); P.c("ba_reg_both", "ba_mid_ln"); P.c("ba_reg_both", "ba_low_ln")
    P.sig2("mu_pad_mid", "*~", "mu_pad_b", "ba_mid_ln", px, 870)
    P.sig2("ba_out", "*~", "ba_b", "ba_low_ln", bx, 860)
    P.sig2("mu_pad_c", "+~", "mu_pad_mid", "ba_out", px, 880)

    # ---- tone, levels, on/off ----
    P.obj("mu_r_tone", "r music_tone", x + 800, 300)
    ex("mu_cut", "400*pow(2,$f1*4)", x + 800, 330)
    P.c("mu_r_tone", "mu_cut")
    ex("mu_cut_pad", "$f1*0.6", x + 800, 360)
    P.c("mu_cut", "mu_cut_pad")
    P.c("mu_cut_pad", "mu_pad_lp", 0, 1); P.c("mu_cut", "mu_chime_lp", 0, 1)
    pad_lvl = smoothed(P, "music_pad", "music_pad", px + 500, 20)
    arp_lvl = smoothed(P, "music_arp", "music_arp", px + 600, 20)
    mon = smoothed(P, "music_on", "music_on", px + 700, 20)
    # Stopping after a walk: the pad and bass take a breath (dip, then drift back), so a red light doesn't feel
    # as if the music didn't notice. Only steps start it, so someone who never walks hears no change.
    P.obj("mu_br_step", "r step", px + 300, 820)
    P.obj("mu_br_t", "t b b", px + 300, 840)
    P.obj("mu_br_del", f"del {STOP_AFTER_MS}", px + 300, 860)
    P.msg("mu_br_back", ("1 " + str(STOP_RETURN_MS)), px + 400, 860)
    P.msg("mu_br_dip", (f"{STOP_DIP} {STOP_DIP_MS}, 1 {STOP_RECOVER_MS} {STOP_DIP_MS}").replace(",", " " + BS + ","), px + 300, 880)
    P.obj("mu_br_ln", "vline~", px + 300, 900)
    P.obj("mu_br_init", "loadbang", px + 450, 860)
    P.msg("mu_br_one", "1", px + 450, 880)
    P.c("mu_br_init", "mu_br_one"); P.c("mu_br_one", "mu_br_ln")
    P.c("mu_br_step", "mu_br_t"); P.c("mu_br_t", "mu_br_back", 1, 0); P.c("mu_br_t", "mu_br_del", 0, 0)
    P.c("mu_br_back", "mu_br_ln"); P.c("mu_br_del", "mu_br_dip"); P.c("mu_br_dip", "mu_br_ln")
    P.sig2("mu_pad_br", "*~", "mu_pad_c", "mu_br_ln", px, 890)
    P.sig2("mu_pad_out", "*~", "mu_pad_br", pad_lvl, px, 900)
    P.sig2("mu_chime_out", "*~", "mu_chime_lp", arp_lvl, px + 200, 900)
    P.sig2("mu_mix0", "+~", "mu_pad_out", "mu_chime_out", px, 930)
    P.sig2("mu_mix1", "+~", "mu_mix0", add_room_notes(P, x + 2500, ex, degree_to_hz), px, 940)
    P.sig2("mu_mix", "+~", "mu_mix1", add_harmony(P, x + 3400, ex, degree_to_hz), px, 945)
    P.sig2("mu_out", "*~", "mu_mix", mon, px, 960)
    return "mu_out"


def add_harmony(P, hx, ex, degree_to_hz):
    """Answers a held pitch with a note of the pad's chord: the nearest chord note at least a third above it, an
    octave up (a whistle or bird: the nearest a third below it, an octave down), so it is clearly a second voice and
    never the note being sung. It is held as long as the sound is, in a soft organ tone. Only a
    pitch that stays steady for a moment, clearly above the room's quiet, counts, so noise and speech blips play
    nothing. Two voices take turns, so a new note never bends the one still fading. Returns the output signal."""
    P.sig2("mu_hm_src", "*~", "mic_gated", "ph_ln", hx, 20)          # quieter in a pocket, like the rest
    P.obj("mu_hm_sig", "sigmund~ -hop 512 -npts 2048 pitch env", hx, 50)   # env comes out first, then pitch
    P.c("mu_hm_src", "mu_hm_sig")
    P.obj("mu_hm_thr", "value mthr", hx + 200, 80)
    P.obj("mu_hm_env_t", "t f b", hx + 200, 50)
    ex("mu_hm_loud", f"$f1-$f2", hx + 200, 110)
    P.c("mu_hm_sig", "mu_hm_env_t", 1, 0); P.c("mu_hm_env_t", "mu_hm_thr", 1, 0)
    P.c("mu_hm_thr", "mu_hm_loud", 0, 1); P.c("mu_hm_env_t", "mu_hm_loud", 0, 0)
    # Each pitch frame: steady (close to the frame before) and loud enough? Count the steady frames in a row.
    P.obj("mu_hm_p_t", "t f f", hx, 80)
    P.c("mu_hm_sig", "mu_hm_p_t", 0, 0)
    ex("mu_hm_ok", f"($f1>{HARM_RANGE[0]})*($f1<{HARM_RANGE[1]})*(abs($f1-$f2)<{HARM_STEADY_ST})*($f3>{HARM_ABOVE_DB})*($f4>0)", hx, 140)
    P.c("mu_hm_p_t", "mu_hm_ok", 1, 0); P.c("mu_hm_p_t", "mu_hm_ok", 0, 1)   # right first: compare with the old pitch
    P.c("mu_hm_loud", "mu_hm_ok", 0, 2)
    if os.environ.get("HARM_DEBUG"):
        P.obj("mu_hm_dbg_m", "metro 300", hx + 500, 50); P.obj("mu_hm_dbg_lb", "loadbang", hx + 500, 30)
        P.c("mu_hm_dbg_lb", "mu_hm_dbg_m")
        P.obj("mu_hm_dbg_p", "f", hx + 500, 80); P.obj("mu_hm_dbg_l", "f", hx + 560, 80); P.obj("mu_hm_dbg_e", "f", hx + 620, 80)
        P.obj("mu_hm_dbg_pk", "pack f f f", hx + 500, 110); P.obj("mu_hm_dbg_pr", "print hm", hx + 500, 140)
        P.obj("mu_hm_dbg_t", "t b b b", hx + 500, 65)
        P.c("mu_hm_dbg_m", "mu_hm_dbg_t"); P.c("mu_hm_dbg_t", "mu_hm_dbg_p", 0, 0); P.c("mu_hm_dbg_t", "mu_hm_dbg_l", 1, 0); P.c("mu_hm_dbg_t", "mu_hm_dbg_e", 2, 0)
        P.c("mu_hm_sig", "mu_hm_dbg_p", 0, 1); P.c("mu_hm_loud", "mu_hm_dbg_l", 0, 1); P.c("mu_hm_sig", "mu_hm_dbg_e", 1, 1)
        P.c("mu_hm_dbg_p", "mu_hm_dbg_pk", 0, 0); P.c("mu_hm_dbg_l", "mu_hm_dbg_pk", 0, 1); P.c("mu_hm_dbg_e", "mu_hm_dbg_pk", 0, 2)
        P.c("mu_hm_dbg_pk", "mu_hm_dbg_pr")
        P.obj("mu_hm_dbg_s1", "s hm_cnt", hx + 700, 240); P.c("mu_hm_next", "mu_hm_dbg_s1")
        P.obj("mu_hm_dbg_s2", "s hm_loud", hx + 700, 260); P.c("mu_hm_loud", "mu_hm_dbg_s2")
        P.obj("mu_hm_dbg_s3", "s hm_p", hx + 700, 280); P.c("mu_hm_sig", "mu_hm_dbg_s3")
    P.obj("mu_hm_r_lvl", "r music_harm", hx + 150, 110)                 # at 0 nothing is answered (the voice is silent)
    P.c("mu_hm_r_lvl", "mu_hm_ok", 0, 3)
    # The tracker misreads a frame now and then (an octave or a twelfth off): only three bad frames in a row end a note.
    P.obj("mu_hm_okt", "t f b f", hx, 145)
    ex("mu_hm_eff", "($f1+$f2+$f3)>0", hx + 60, 150)
    P.obj("mu_hm_ok1", "f", hx + 120, 150)
    P.c("mu_hm_ok", "mu_hm_okt"); P.c("mu_hm_okt", "mu_hm_eff", 2, 0); P.c("mu_hm_okt", "mu_hm_ok1", 1, 0)
    P.c("mu_hm_ok1", "mu_hm_eff", 0, 2); P.c("mu_hm_okt", "mu_hm_ok1", 0, 1); P.c("mu_hm_okt", "mu_hm_eff", 0, 1)
    P.obj("mu_hm_good", "spigot", hx + 100, 330)                        # only good frames set the pitch to answer
    P.c("mu_hm_ok", "mu_hm_good", 0, 1)
    P.obj("mu_hm_ok_t", "t f b", hx, 155)                              # read the count, then add to it or clear it
    P.obj("mu_hm_cnt", "f", hx + 60, 170)
    ex("mu_hm_next", "$f1*($f2+1)", hx, 200)
    P.c("mu_hm_eff", "mu_hm_ok_t"); P.c("mu_hm_ok_t", "mu_hm_cnt", 1, 0); P.c("mu_hm_cnt", "mu_hm_next", 0, 1)
    P.c("mu_hm_ok_t", "mu_hm_next", 0, 0)
    P.obj("mu_hm_cnt_t", "t f f", hx, 230)
    P.c("mu_hm_next", "mu_hm_cnt_t"); P.c("mu_hm_cnt_t", "mu_hm_cnt", 1, 1)
    ex("mu_hm_held", f"$f1>={HARM_STABLE_FRAMES}", hx, 260)
    P.c("mu_hm_cnt_t", "mu_hm_held")
    P.obj("mu_hm_chg", "change", hx, 290)
    P.obj("mu_hm_sel", "sel 1 0", hx, 320)
    P.c("mu_hm_held", "mu_hm_chg"); P.c("mu_hm_chg", "mu_hm_sel")
    # The answer. First the heard pitch as a scale step (0 = the key note, n = an octave up), then the chord note.
    P.obj("mu_hm_pitch", "f", hx + 100, 350)
    P.c("mu_hm_p_t", "mu_hm_good", 0, 0); P.c("mu_hm_good", "mu_hm_pitch", 0, 1)
    P.obj("mu_hm_root", "f 48", hx + 260, 350)
    P.c("mu_key_root", "mu_hm_root", 0, 1)
    P.obj("mu_hm_n", "value scale_n", hx + 360, 350)
    P.obj("mu_hm_n2", "value scale_n", hx + 420, 350)
    P.obj("mu_hm_ch", "value mchord", hx + 480, 350)
    P.obj("mu_hm_t", "t f f b b b b", hx + 100, 380)
    P.c("mu_hm_pitch", "mu_hm_t")
    P.c("mu_hm_t", "mu_hm_root", 5, 0); P.c("mu_hm_t", "mu_hm_n", 4, 0); P.c("mu_hm_t", "mu_hm_n2", 3, 0)
    P.c("mu_hm_t", "mu_hm_ch", 2, 0)
    rel = "(rint($f1)-$f2)"
    ex("mu_hm_d", f"floor({rel}/12)*$f3+pc_deg[{rel}-12*floor({rel}/12)]", hx + 100, 410)
    P.c("mu_hm_root", "mu_hm_d", 0, 1); P.c("mu_hm_n", "mu_hm_d", 0, 2); P.c("mu_hm_t", "mu_hm_d", 0, 0)
    # chord notes are the chord root r and 2 and 4 steps up; $f1 = heard step d, $f2 = r, $f3 = n, $f4 = pitch
    up = ("min(min($f2+$f3*ceil(($f1+2-$f2)/$f3),$f2+2+$f3*ceil(($f1-$f2)/$f3)),"
          "$f2+4+$f3*ceil(($f1-2-$f2)/$f3))+$f3")
    down = ("max(max($f2+$f3*floor(($f1-2-$f2)/$f3),$f2+2+$f3*floor(($f1-4-$f2)/$f3)),"
            "$f2+4+$f3*floor(($f1-6-$f2)/$f3))-$f3")
    ex("mu_hm_deg", f"if($f4<{HARM_HIGH},{up},{down})", hx + 100, 440)
    P.c("mu_hm_ch", "mu_hm_deg", 0, 1); P.c("mu_hm_n2", "mu_hm_deg", 0, 2); P.c("mu_hm_t", "mu_hm_deg", 1, 3)
    P.c("mu_hm_d", "mu_hm_deg", 0, 0)
    deg_in, deg_hz = degree_to_hz("mu_hm_c", hx + 100, 470)
    P.c("mu_hm_deg", deg_in)
    P.obj("mu_hm_degout", "s harm_deg", hx + 300, 480)
    P.c("mu_hm_deg", "mu_hm_degout")
    # Note on: frequency first, then pick the other voice and open it; note off closes the voice that is playing.
    P.obj("mu_hm_on", "t b b", hx, 350)
    P.c("mu_hm_sel", "mu_hm_on", 0, 0)
    P.c("mu_hm_on", "mu_hm_pitch", 1, 0)
    P.obj("mu_hm_vc", "f", hx, 680)
    P.obj("mu_hm_flip", "== 0", hx + 60, 680)
    P.c("mu_hm_vc", "mu_hm_flip"); P.c("mu_hm_flip", "mu_hm_vc", 0, 1)
    P.obj("mu_hm_on2", "t b b", hx, 665)
    P.c("mu_hm_on", "mu_hm_on2", 0, 0)
    P.c("mu_hm_on2", "mu_hm_vc", 1, 0)
    P.obj("mu_hm_cur", "f", hx + 120, 700)
    P.c("mu_hm_flip", "mu_hm_cur", 0, 1)
    P.c("mu_hm_on2", "mu_hm_cur", 0, 0)
    P.obj("mu_hm_off", "t b", hx + 200, 700)
    P.c("mu_hm_sel", "mu_hm_off", 1, 0)
    P.obj("mu_hm_vsel", "sel 0 1", hx + 120, 730)
    P.obj("mu_hm_osel", "sel 0 1", hx + 200, 730)
    P.obj("mu_hm_cur2", "f", hx + 200, 715)
    P.c("mu_hm_flip", "mu_hm_cur2", 0, 1)
    P.c("mu_hm_off", "mu_hm_cur2"); P.c("mu_hm_cur2", "mu_hm_osel")
    P.c("mu_hm_cur", "mu_hm_vsel")
    acc = None
    comma = " " + BS + ","
    for k in range(2):
        vx = hx + 400 + k * 200
        P.obj(f"mu_hm{k}_fr", "f", vx, 760)
        P.c(deg_hz, f"mu_hm{k}_fr", 0, 1)
        P.obj(f"mu_hm{k}_t", "t b b", vx, 745)
        P.c("mu_hm_vsel", f"mu_hm{k}_t", k, 0)
        P.c(f"mu_hm{k}_t", f"mu_hm{k}_fr", 1, 0)
        # A soft organ: the note plus its octave, twelfth and double octave, so it doesn't melt into a voice.
        P.obj(f"mu_hm{k}_o1", "osc~", vx, 790)
        P.c(f"mu_hm{k}_fr", f"mu_hm{k}_o1")
        acc_v = f"mu_hm{k}_o1"
        for h, g in ((2, 0.5), (3, 0.3), (4, 0.15)):
            P.obj(f"mu_hm{k}_f{h}", f"* {h}", vx + 40 * h, 775)
            P.obj(f"mu_hm{k}_o{h}", "osc~", vx + 40 * h, 790)
            P.obj(f"mu_hm{k}_g{h}", f"*~ {g}", vx + 40 * h, 810)
            P.c(f"mu_hm{k}_fr", f"mu_hm{k}_f{h}"); P.c(f"mu_hm{k}_f{h}", f"mu_hm{k}_o{h}"); P.c(f"mu_hm{k}_o{h}", f"mu_hm{k}_g{h}")
            acc_v = P.sig2(f"mu_hm{k}_a{h}", "+~", acc_v, f"mu_hm{k}_g{h}", vx, 815 + h)
        P.obj(f"mu_hm{k}_s", "*~ 0.6", vx, 830)
        P.c(acc_v, f"mu_hm{k}_s")
        P.msg(f"mu_hm{k}_atk", f"1 {HARM_ATTACK_MS}", vx, 850)
        P.msg(f"mu_hm{k}_rel", f"0 {HARM_RELEASE_MS}", vx + 80, 850)
        P.obj(f"mu_hm{k}_env", "vline~", vx, 870)
        P.c(f"mu_hm{k}_t", f"mu_hm{k}_atk", 0, 0)
        P.c("mu_hm_osel", f"mu_hm{k}_rel", k, 0)
        P.c(f"mu_hm{k}_atk", f"mu_hm{k}_env"); P.c(f"mu_hm{k}_rel", f"mu_hm{k}_env")
        P.obj(f"mu_hm{k}_sq", "*~", vx, 890)
        P.c(f"mu_hm{k}_env", f"mu_hm{k}_sq", 0, 0); P.c(f"mu_hm{k}_env", f"mu_hm{k}_sq", 0, 1)   # eased in and out
        P.sig2(f"mu_hm{k}_out", "*~", f"mu_hm{k}_s", f"mu_hm{k}_sq", vx, 910)
        acc = f"mu_hm{k}_out" if acc is None else P.sig2("mu_hm_sum", "+~", acc, f"mu_hm{k}_out", vx, 930)
    P.obj("mu_hm_lp", "lop~ 3500", hx, 950)
    P.c(acc, "mu_hm_lp")
    lvl = smoothed(P, "music_harm", "music_harm", hx + 300, 950)
    P.obj("mu_hm_gain", "*~ 0.4", hx, 970)
    P.c("mu_hm_lp", "mu_hm_gain")
    return P.sig2("mu_hm_out", "*~", "mu_hm_gain", lvl, hx, 990)


def add_glitch_cloud(P):
    """Glitch cloud (after dblue Glitch): the hushed mic goes into a ring buffer (memory only, GC_BUF_MS). A sudden
    sound (and now and then a free clock) grabs a bit of it and plays it back mangled: a stutter (a slice repeated,
    while walking a quarter step long), reversed, a tape stop (slowing to a halt), or a shuffled older slice, each one
    somewhere else between the ears. Amount = how often; walking makes glitches wait for the next step or half-step.
    Returns the left and right output signals."""
    x, y = 6600, 20
    def ex(name, text, xx, yy):
        return P.obj(name, "expr " + text.replace(",", BS + ",").replace("$", BS + "$"), xx, yy)
    # The voices only compute while they play (most of the time nothing does): on at each glitch, off after it.
    def voice_switch(name, src_list, tail_ms, xx, yy):
        P.msg(f"gcsw_{name}_on", f"{BS}; sw_{name} 1", xx, yy)
        P.obj(f"gcsw_{name}_t", "t l b", xx, yy + 20)
        P.obj(f"gcsw_{name}_L", "list split 1", xx + 80, yy + 40)
        P.obj(f"gcsw_{name}_tail", f"+ {tail_ms}", xx + 80, yy + 60)
        P.obj(f"gcsw_{name}_del", "del", xx + 80, yy + 80)
        P.msg(f"gcsw_{name}_off", f"{BS}; sw_{name} 0", xx + 80, yy + 100)
        P.c(src_list, f"gcsw_{name}_t"); P.c(f"gcsw_{name}_t", f"gcsw_{name}_on", 1, 0)
        P.c(f"gcsw_{name}_t", f"gcsw_{name}_L", 0, 0); P.c(f"gcsw_{name}_L", f"gcsw_{name}_tail")
        P.c(f"gcsw_{name}_tail", f"gcsw_{name}_del"); P.c(f"gcsw_{name}_del", f"gcsw_{name}_off")
        return f"gcsw_{name}_t"
    P.sig2("gc_src", "*~", "mic_gated", "ph_ln", x, y)                  # quieter in a pocket, like the rest
    P.obj("gc_wr", f"delwrite~ gc_buf {GC_BUF_MS}", x, y + 30)
    P.c("gc_src", "gc_wr")
    P.obj("gc_r_amt", "r gc_amount", x + 300, y)
    P.obj("gc_amt", "f", x + 300, y + 30)
    P.c("gc_r_amt", "gc_amt", 0, 1)
    # ---- sudden sounds: the 5 ms level against its own recent average ----
    P.obj("gc_m_t", "t f f", x, y + 80)
    P.c("meter", "gc_m_t")
    ex("gc_det", f"($f1-$f2>{GC_ONSET_DB})*($f1>{GC_MIN_DB})", x, y + 110)
    ex("gc_slow", "$f1*0.04+$f2*0.96", x + 120, y + 110)                # about a quarter second
    P.obj("gc_slow_t", "t f f", x + 120, y + 140)
    P.c("gc_m_t", "gc_det", 1, 0); P.c("gc_m_t", "gc_slow", 0, 0)
    P.c("gc_slow", "gc_slow_t"); P.c("gc_slow_t", "gc_slow", 1, 1); P.c("gc_slow_t", "gc_det", 0, 1)
    P.obj("gc_det_chg", "change", x, y + 140)
    P.obj("gc_det_sel", "sel 1", x, y + 170)
    P.c("gc_det", "gc_det_chg"); P.c("gc_det_chg", "gc_det_sel")
    # Resting: after a glitch nothing new starts for a while (shorter at a high Amount).
    P.obj("gc_rest", "spigot 1", x, y + 200)
    P.c("gc_det_sel", "gc_rest")
    P.obj("gc_roll_t", "t b b", x, y + 230)
    P.obj("gc_roll", "random 1000", x + 60, y + 260)
    P.obj("gc_amt_rd", "f", x + 140, y + 260)
    ex("gc_pass", "$f1<$f2*1000", x, y + 290)
    P.c("gc_rest", "gc_roll_t"); P.c("gc_roll_t", "gc_amt_rd", 1, 0); P.c("gc_amt_rd", "gc_pass", 0, 1)
    P.c("gc_r_amt", "gc_amt_rd", 0, 1)
    P.c("gc_roll_t", "gc_roll", 0, 0); P.c("gc_roll", "gc_pass")
    P.obj("gc_pass_sel", "sel 1", x, y + 320)
    P.c("gc_pass", "gc_pass_sel")
    # an onset that passes: remember when it began (the timer) and that it was one, then ask for a glitch
    P.obj("gc_ons_t", "t b b b", x, y + 350)
    P.c("gc_pass_sel", "gc_ons_t")
    P.obj("gc_timer", "timer", x + 200, y + 380)
    P.msg("gc_flag1", "1", x + 120, y + 380)
    P.obj("gc_flag", "f", x + 120, y + 410)
    P.c("gc_ons_t", "gc_timer", 2, 0); P.c("gc_ons_t", "gc_flag1", 1, 0); P.c("gc_flag1", "gc_flag", 0, 1)
    P.obj("gc_trig", "t b b", x, y + 440)                               # right: start resting; left: the glitch
    P.c("gc_ons_t", "gc_trig", 0, 0)
    P.msg("gc_rest0", "0", x + 300, y + 200)
    P.msg("gc_rest1", "1", x + 300, y + 260)
    P.obj("gc_rest_del", "del 1000", x + 300, y + 230)
    ex("gc_cool", f"{GC_COOL_MS[1]}-({GC_COOL_MS[1]}-{GC_COOL_MS[0]})*$f1", x + 400, y + 200)
    P.c("gc_r_amt", "gc_cool"); P.c("gc_cool", "gc_rest_del", 0, 1)
    P.obj("gc_rest_t", "t b b", x + 300, y + 170)
    P.c("gc_trig", "gc_rest_t", 1, 0)
    P.c("gc_rest_t", "gc_rest_del", 0, 0); P.c("gc_rest_t", "gc_rest0", 1, 0); P.c("gc_rest0", "gc_rest", 0, 1)
    P.c("gc_rest_del", "gc_rest1"); P.c("gc_rest1", "gc_rest", 0, 1)
    # ---- free clock: when nothing sudden happens, now and then a random older bit (sooner at a high Amount) ----
    P.obj("gc_clk_lb", "loadbang", x + 500, y + 260)
    P.obj("gc_clk_t", "t b b", x + 500, y + 320)
    P.obj("gc_clk_rnd", "random 6000", x + 560, y + 350)
    P.obj("gc_clk_amt", "f", x + 660, y + 350)
    P.c("gc_r_amt", "gc_clk_amt", 0, 1)
    ex("gc_clk_ms", "(2000+$f1)*0.6/(0.2+$f2)", x + 560, y + 380)
    P.obj("gc_clk_del", "del 4000", x + 500, y + 410)
    P.c("gc_clk_lb", "gc_clk_t"); P.c("gc_r_amt", "gc_clk_t")                 # Amount changed: pick a new time
    P.c("gc_clk_t", "gc_clk_amt", 1, 0); P.c("gc_clk_amt", "gc_clk_ms", 0, 1)
    P.c("gc_clk_t", "gc_clk_rnd", 0, 0); P.c("gc_clk_rnd", "gc_clk_ms"); P.c("gc_clk_ms", "gc_clk_del")
    P.c("gc_ons_t", "gc_clk_t", 0, 0)                                   # a sudden sound puts the clock back
    P.obj("gc_clk_fire", "t b b", x + 500, y + 440)
    P.c("gc_clk_del", "gc_clk_fire"); P.c("gc_clk_fire", "gc_clk_t", 1, 0)
    P.obj("gc_clk_on", "spigot", x + 500, y + 470)                       # only while Amount > 0, and not resting
    ex("gc_clk_ok", "$f1>0", x + 600, y + 440)
    P.c("gc_r_amt", "gc_clk_ok"); P.c("gc_clk_ok", "gc_clk_on", 0, 1)
    P.obj("gc_clk_rest", "spigot 1", x + 500, y + 500)
    P.c("gc_rest0", "gc_clk_rest", 0, 1); P.c("gc_rest1", "gc_clk_rest", 0, 1)
    P.c("gc_clk_fire", "gc_clk_on", 0, 0); P.c("gc_clk_on", "gc_clk_rest")
    P.obj("gc_clk_go", "t b b", x + 500, y + 530)
    P.msg("gc_flag0", "0", x + 560, y + 560)
    P.c("gc_clk_rest", "gc_clk_go"); P.c("gc_clk_go", "gc_flag0", 1, 0); P.c("gc_flag0", "gc_flag", 0, 1)
    P.c("gc_clk_go", "gc_ask", 0, 0)                                   # (only sudden sounds start the rest)
    # ---- walking: a glitch waits for the next step or half-step; stutters are a quarter step long ----
    P.obj("gc_r_step", "r step", x + 800, y)
    P.obj("gc_step_t", "t b b f b", x + 800, y + 30)
    P.c("gc_r_step", "gc_step_t")
    P.msg("gc_walk1", "1", x + 800, y + 90); P.msg("gc_walk0", "0", x + 860, y + 120)
    P.obj("gc_walk_del", f"del {GC_STEP_WAIT_MS}", x + 860, y + 90)
    P.obj("gc_walk", "f", x + 800, y + 150)
    P.c("gc_step_t", "gc_walk1", 3, 0); P.c("gc_walk1", "gc_walk", 0, 1)
    P.c("gc_step_t", "gc_walk_del", 3, 0); P.c("gc_walk_del", "gc_walk0"); P.c("gc_walk0", "gc_walk", 0, 1)
    P.obj("gc_step_ms", "* 1000", x + 950, y + 60)
    P.obj("gc_stepms_v", "f", x + 950, y + 90)
    P.c("gc_step_t", "gc_step_ms", 2, 0); P.c("gc_step_ms", "gc_stepms_v", 0, 1)
    P.obj("gc_half", "* 500", x + 1050, y + 60)
    P.obj("gc_half_del", "del 300", x + 1050, y + 90)
    P.c("gc_step_t", "gc_half", 2, 0); P.c("gc_half", "gc_half_del", 0, 1); P.c("gc_step_t", "gc_half_del", 1, 0)
    P.obj("gc_pend", "f", x + 800, y + 200)                              # a glitch waiting for the beat
    P.obj("gc_pend_sel", "sel 1", x + 800, y + 230)
    P.obj("gc_beat_t", "t b b", x + 800, y + 170)
    P.c("gc_step_t", "gc_beat_t", 0, 0); P.c("gc_half_del", "gc_beat_t")
    P.c("gc_beat_t", "gc_pend", 1, 0); P.c("gc_pend", "gc_pend_sel")
    P.msg("gc_pend0", "0", x + 900, y + 230)
    P.c("gc_beat_t", "gc_pend0", 0, 0); P.c("gc_pend0", "gc_pend", 0, 1)
    P.obj("gc_ask", "t b b", x, y + 470)                                # walking? wait. still? now.
    P.c("gc_trig", "gc_ask", 0, 0)
    P.obj("gc_walk_rd", "f", x + 100, y + 500)
    P.c("gc_ask", "gc_walk_rd", 0, 0); P.c("gc_walk1", "gc_walk_rd", 0, 1); P.c("gc_walk0", "gc_walk_rd", 0, 1)
    P.obj("gc_walk_sel", "sel 0 1", x + 100, y + 530)
    P.c("gc_walk_rd", "gc_walk_sel")
    P.msg("gc_pend1", "1", x + 200, y + 560)
    P.c("gc_walk_sel", "gc_pend1", 1, 0); P.c("gc_pend1", "gc_pend", 0, 1)
    P.obj("gc_fire", "t b b b b b b b", x, y + 600)
    P.c("gc_walk_sel", "gc_fire", 0, 0); P.c("gc_pend_sel", "gc_fire")
    # ---- what kind of glitch: a random pick among the switched-on kinds (stutter 35, reverse 25, shuffle 20, stretch 20) ----
    # (tape stop and a turntable scratch were tried and dropped, Samuel, Oct 10)
    P.obj("gc_mode_rnd", "random 1000", x, y + 640)
    w = "($f2*35+$f3*25+$f4*20+$f5*20)"
    c = ["$f2*35", "$f2*35+$f3*25", "$f2*35+$f3*25+$f4*20"]
    pick = "3"
    for k in range(2, -1, -1):
        pick = f"if($f1*{w}/1000<{c[k]},{k},{pick})"
    ex("gc_mode", f"if({w}<=0,-1,{pick})", x, y + 670)
    for k, name in enumerate(("gc_stutter", "gc_reverse", "gc_shuffle", "gc_stretch")):
        P.obj(f"gc_en{k}", f"r {name}", x + 200 + 80 * k, y + 640)
        P.c(f"gc_en{k}", "gc_mode", 0, k + 1)
    P.c("gc_fire", "gc_mode_rnd", 0, 0); P.c("gc_mode_rnd", "gc_mode")
    P.obj("gc_mode_ok", "moses 0", x, y + 700)
    P.c("gc_mode", "gc_mode_ok")
    # randoms, how long ago the sound began (-1 = from the free clock) and the step length (0 = standing)
    for k in range(4):
        P.obj(f"gc_rn{k}", "random 1000", x + 200 + 80 * k, y + 700)
    P.obj("gc_el", "f", x + 520, y + 700)
    ex("gc_el2", "if($f2,$f1,-1)", x + 520, y + 730)
    P.c("gc_timer", "gc_el2"); P.c("gc_flag1", "gc_el2", 0, 1); P.c("gc_flag0", "gc_el2", 0, 1)
    P.obj("gc_st_rd", "f", x + 620, y + 700)
    ex("gc_st2", "$f1*$f2", x + 620, y + 730)
    P.c("gc_stepms_v", "gc_st_rd", 0, 1); P.c("gc_st_rd", "gc_st2"); P.c("gc_walk1", "gc_st2", 0, 1); P.c("gc_walk0", "gc_st2", 0, 1)
    # $f1 mode (0 stutter, 1 reverse, 2 shuffle), $f2 ms since the onset (-1 free), $f3..$f5, $f7 randoms 0..999,
    # $f6 step ms (0 = standing). Out: L, d0, c1, c2, S, place, wait.
    S = "if($f6>0,min(max($f6/4,60),250),60+40*int($f4/250))"
    L = f"if($f1==0,({S})*(4+int($f5/250)),if($f1==1,300+0.4*$f3,150+0.35*$f3))"
    d0 = f"if($f1==1,10,if($f1==2||$f2<0,250+3*$f4,$f2+{GC_PREROLL_MS}))"     # from just before the sound began
    outs = [L, d0, "if($f1==1,-1,if($f1==0,0,1))", "$f1==0", f"if($f1==0,{S},10000000)",
            "if($f7<500,-(0.45+0.55*$f7/500),0.45+0.55*($f7-500)/500)",
            f"if($f1==1&&$f2>=0,max(({L})-$f2,0),0)"]                      # reverse: wait until it has all been heard
    ex("gc_par", " ; ".join(outs).replace(" ; ", " " + BS + "; "), x, y + 770)
    P.obj("gc_kind", "sel 3", x, y + 740)                                # 3 = stretch: its own voice
    P.c("gc_mode_ok", "gc_kind", 1, 0); P.c("gc_kind", "gc_par", 1, 0)
    P.msg("gc_kind4", "3", x + 60, y + 755); P.c("gc_kind", "gc_kind4", 0, 0)
    # stretch (Ghost capture, Ableton warp pushed far): the sound smeared 4-12x slower in 100 ms grains, pitch
    # unchanged, fading out slowly. $f2 ms since the onset (-1 free), $f3-$f5, $f7 randoms. Out: L, d0, rate, place.
    sd0 = f"if($f2>=0,$f2+{GC_PREROLL_MS},300+2.5*$f4)"
    srate = "(0.08+0.17*$f5/1000)"
    souts = [f"min(1500+2000*$f3/1000,(3850-({sd0}))/(1-{srate}))", sd0, srate,
             "if($f7<500,-(0.45+0.55*$f7/500),0.45+0.55*($f7-500)/500)"]
    ex("gc_spar", " ; ".join(souts).replace(" ; ", " " + BS + "; "), x + 700, y + 770)
    P.c("gc_kind4", "gc_spar")
    P.c("gc_rn0", "gc_spar", 0, 6); P.c("gc_rn1", "gc_spar", 0, 4); P.c("gc_rn2", "gc_spar", 0, 3); P.c("gc_rn3", "gc_spar", 0, 2)
    P.c("gc_el2", "gc_spar", 0, 1)
    P.obj("gc_spack", "pack f f f f", x + 700, y + 800)
    for k in range(3, 0, -1):
        P.c("gc_spar", "gc_spack", k, k)
    P.c("gc_spar", "gc_spack", 0, 0)
    voice_switch("gcs", "gc_spack", 700, x + 900, y + 820)
    P.c("gc_fire", "gc_rn0", 6, 0); P.c("gc_rn0", "gc_par", 0, 6)
    P.c("gc_fire", "gc_rn1", 5, 0); P.c("gc_rn1", "gc_par", 0, 4)
    P.c("gc_fire", "gc_rn2", 4, 0); P.c("gc_rn2", "gc_par", 0, 3)
    P.c("gc_fire", "gc_rn3", 3, 0); P.c("gc_rn3", "gc_par", 0, 2)
    P.c("gc_fire", "gc_timer", 2, 1); P.c("gc_el2", "gc_par", 0, 1)
    P.c("gc_fire", "gc_st_rd", 1, 0); P.c("gc_st2", "gc_par", 0, 5)
    P.obj("gc_pack", "pack f f f f f f f", x, y + 810)
    for k in range(6, 0, -1):
        P.c("gc_par", "gc_pack", k, k)
    P.c("gc_par", "gc_pack", 0, 0)
    # a reverse waits (the last number) until the sound has been heard; then the voice plays it. One voice: a glitch
    # arriving while another plays fades that one out over 4 ms before jumping, so there is no click.
    P.obj("gc_wait", "list split 6", x + 100, y + 825)
    P.obj("gc_wait_del", "del", x + 200, y + 840)
    P.obj("gc_wait_l", "list", x + 100, y + 855)
    P.c("gc_pack", "gc_wait"); P.c("gc_wait", "gc_wait_del", 1, 0); P.c("gc_wait", "gc_wait_l", 0, 1)
    P.c("gc_wait_del", "gc_wait_l")
    if os.environ.get("GC_DEBUG"):
        P.obj("gc_dbg1", "s gc_packed", x + 400, y + 920); P.c("gc_pack", "gc_dbg1")
        P.obj("gc_dbg2", "s gc_parL", x + 500, y + 920); P.c("gc_par", "gc_dbg2")
        P.obj("gc_dbg3", "s gc_event", x + 600, y + 920); P.c("gc_wait_l", "gc_dbg3")
        P._probes = ["gc0_d", "gc0_rd", "gc0_ew", "gc0_scm", "gc0_s1", "gc0_win", "gc0_env"]
    P.obj("gc_vc_t", "t l b", x, y + 870)
    P.msg("gc_vc_fade", "0 4", x + 100, y + 890)
    P.obj("gc_vc_l", "list", x, y + 910)
    P.obj("gc_vc_del", "del 5", x + 100, y + 910)
    P.c("gc_wait_l", "gc_vc_t"); P.c("gc_vc_t", "gc_vc_fade", 1, 0); P.c("gc_vc_t", "gc_vc_del", 1, 0)
    P.c("gc_vc_t", "gc_vc_l", 0, 1); P.c("gc_vc_del", "gc_vc_l")
    voice_switch("gcv", "gc_vc_l", 100, x + 300, y + 900)
    P.obj("gc_dbg_mode", "s gc_mode", x + 200, y + 700); P.c("gc_mode_ok", "gc_dbg_mode", 1, 0)
    outs_l, outs_r = [], []
    for k in range(1):
        vx, vy = x + 1200, y + 600
        P.obj(f"gc{k}_up", "unpack f f f f f f", vx, vy)
        P.c("gc_vc_l", f"gc{k}_up")
        P.obj("grp_gcv_r", "r sw_gcv", 10, 10); P.obj("grp_gcv_sw", "switch~", 10, 40); P.c("grp_gcv_r", "grp_gcv_sw")
        P.obj(f"gc{k}_t", "vline~", vx, vy + 90)                           # ms into the glitch
        # read position (ms back): d0 + a*t - c*fmod(t,S), built from plain objects (expr~ costs far more per
        # sample). Stutter: a=1 c=1 (back to the slice start every S ms); reverse: a=2; shuffle: both 0.
        # The unpack gives L, d0, c1, c2, S, place: a = 1-c1, c = c2.
        P.obj(f"gc{k}_a", "expr 1-$f1".replace("$", BS + "$"), vx + 60, vy + 40)
        P.c(f"gc{k}_up", f"gc{k}_a", 2, 0)
        P.obj(f"gc{k}_at", "*~ 0", vx, vy + 120); P.c(f"gc{k}_t", f"gc{k}_at"); P.c(f"gc{k}_a", f"gc{k}_at", 0, 1)
        P.obj(f"gc{k}_invS", "expr 1/$f1".replace("$", BS + "$"), vx + 180, vy + 40)
        P.c(f"gc{k}_up", f"gc{k}_invS", 4, 0)
        P.obj(f"gc{k}_ts", "*~ 0", vx + 120, vy + 120); P.c(f"gc{k}_t", f"gc{k}_ts"); P.c(f"gc{k}_invS", f"gc{k}_ts", 0, 1)
        P.obj(f"gc{k}_wr", "wrap~", vx + 120, vy + 140); P.c(f"gc{k}_ts", f"gc{k}_wr")
        P.obj(f"gc{k}_f", "*~ 0", vx + 120, vy + 160); P.c(f"gc{k}_wr", f"gc{k}_f"); P.c(f"gc{k}_up", f"gc{k}_f", 4, 1)   # fmod(t,S)
        P.obj(f"gc{k}_cn", "* -1", vx + 240, vy + 40); P.c(f"gc{k}_up", f"gc{k}_cn", 3, 0)
        P.obj(f"gc{k}_ctf", "*~ 0", vx + 180, vy + 180); P.c(f"gc{k}_f", f"gc{k}_ctf"); P.c(f"gc{k}_cn", f"gc{k}_ctf", 0, 1)
        P.sig2(f"gc{k}_s2", "+~", f"gc{k}_at", f"gc{k}_ctf", vx, vy + 200)
        P.obj(f"gc{k}_dd", "+~ 0", vx, vy + 210); P.c(f"gc{k}_s2", f"gc{k}_dd"); P.c(f"gc{k}_up", f"gc{k}_dd", 1, 1)
        P.obj(f"gc{k}_d", "clip~ 1 3990", vx, vy + 220); P.c(f"gc{k}_dd", f"gc{k}_d")
        P.obj(f"gc{k}_rd", "delread4~ gc_buf", vx, vy + 230)
        P.c(f"gc{k}_d", f"gc{k}_rd")
        # each stutter slice fades in and out over 3 ms, so the jumps back don't click
        P.obj(f"gc{k}_w1", "*~ 0.333", vx + 250, vy + 170); P.c(f"gc{k}_f", f"gc{k}_w1")
        P.obj(f"gc{k}_w1c", "clip~ 0 1", vx + 250, vy + 180); P.c(f"gc{k}_w1", f"gc{k}_w1c")
        P.obj(f"gc{k}_w2", "*~ -0.333", vx + 320, vy + 170); P.c(f"gc{k}_f", f"gc{k}_w2")
        P.obj(f"gc{k}_S3", "/ 3", vx + 320, vy + 40); P.c(f"gc{k}_up", f"gc{k}_S3", 4, 0)
        P.obj(f"gc{k}_w2o", "+~ 0", vx + 320, vy + 180); P.c(f"gc{k}_w2", f"gc{k}_w2o"); P.c(f"gc{k}_S3", f"gc{k}_w2o", 0, 1)
        P.obj(f"gc{k}_w2c", "clip~ 0 1", vx + 320, vy + 190); P.c(f"gc{k}_w2o", f"gc{k}_w2c")
        P.sig2(f"gc{k}_win", "*~", f"gc{k}_w1c", f"gc{k}_w2c", vx + 250, vy + 200)
        P.obj(f"gc{k}_L", "t f f", vx, vy + 30)
        P.c(f"gc{k}_up", f"gc{k}_L", 0, 0)
        P.msg(f"gc{k}_tmsg", f"0 {BS}, {BS}$1 {BS}$1".replace(f"{BS},", f" {BS},").replace("  ", " "), vx, vy + 60)
        P.obj(f"gc{k}_Lm", "- 25", vx + 100, vy + 45)
        P.msg(f"gc{k}_emsg", f"1 5 {BS}, 0 20 {BS}$1", vx + 100, vy + 60)
        P.obj(f"gc{k}_env", "vline~", vx + 100, vy + 90)
        P.c(f"gc{k}_L", f"gc{k}_Lm", 1, 0); P.c(f"gc{k}_Lm", f"gc{k}_emsg"); P.c(f"gc{k}_emsg", f"gc{k}_env")
        P.c(f"gc{k}_L", f"gc{k}_tmsg", 0, 0); P.c(f"gc{k}_tmsg", f"gc{k}_t")
        P.c("gc_vc_fade", f"gc{k}_env")
        P.sig2(f"gc{k}_ew", "*~", f"gc{k}_env", f"gc{k}_win", vx + 100, vy + 150)
        P.sig2(f"gc{k}_s", "*~", f"gc{k}_rd", f"gc{k}_ew", vx, vy + 180)
        # where it sits (set while the voice is silent; the place comes out of unpack first): always at least
        # halfway out to one side, the near ear at full level, the far ear quieter and up to 0.6 ms later (the
        # time difference is what makes a sound seem really off to the side)
        ex(f"gc{k}_pan", "min(1,1-$f1) ; min(1,1+$f1) ; 1.5+0.6*max($f1,0) ; 1.5+0.6*max(-$f1,0)".replace(" ; ", " " + BS + "; "), vx + 250, vy + 30)
        P.c(f"gc{k}_up", f"gc{k}_pan", 5, 0)
        P.obj(f"gc{k}_gl", "sig~", vx + 250, vy + 60); P.obj(f"gc{k}_gr", "sig~", vx + 320, vy + 60)
        P.obj(f"gc{k}_itd", "delwrite~ gc_itd 10", vx, vy + 215); P.c(f"gc{k}_s", f"gc{k}_itd")
        P.obj(f"gc{k}_rl", "delread~ gc_itd 1.5", vx, vy + 225)            # whole samples are fine for this
        P.obj(f"gc{k}_rr", "delread~ gc_itd 1.5", vx + 100, vy + 225)
        for o, n in enumerate(("gl", "gr", "rl", "rr")):
            P.c(f"gc{k}_pan", f"gc{k}_{n}", o, 0)
        outs_l.append(P.sig2(f"gc{k}_l", "*~", f"gc{k}_rl", f"gc{k}_gl", vx, vy + 240))
        outs_r.append(P.sig2(f"gc{k}_r", "*~", f"gc{k}_rr", f"gc{k}_gr", vx + 100, vy + 240))
    # the stretch voice: two overlapping Hann-windowed grains; the grain start creeps forward at `rate`, each grain
    # plays at normal speed, so time slows and pitch stays. Its own place between the ears (no time offset).
    vx, vy = x + 1800, y + 600
    P.obj("gc2_up", "unpack f f f f", vx, vy); P.c("gc_spack", "gc2_up")
    P.obj("grp_gcs_r", "r sw_gcs", 10, 10); P.obj("grp_gcs_sw", "switch~", 10, 40); P.c("grp_gcs_r", "grp_gcs_sw")
    P.obj("gc2_L", "t f f", vx, vy + 30); P.c("gc2_up", "gc2_L", 0, 0)
    P.msg("gc2_tmsg", f"0 {BS}, {BS}$1 {BS}$1", vx, vy + 60)
    P.obj("gc2_t", "vline~", vx, vy + 90)
    P.obj("gc2_Lm", "- 650", vx + 100, vy + 45)
    P.msg("gc2_emsg", f"1 40 {BS}, 0 600 {BS}$1", vx + 100, vy + 60)
    P.obj("gc2_env", "vline~", vx + 100, vy + 90)
    P.c("gc2_L", "gc2_Lm", 1, 0); P.c("gc2_Lm", "gc2_emsg"); P.c("gc2_emsg", "gc2_env")
    P.c("gc2_L", "gc2_tmsg", 0, 0); P.c("gc2_tmsg", "gc2_t")
    P.obj("gc2_k", "expr 1-$f1 ; (1-$f1)*100".replace("$", BS + "$").replace(" ; ", " " + BS + "; "), vx + 200, vy + 30)
    P.c("gc2_up", "gc2_k", 2, 0)
    P.obj("gc2_Dt", "*~ 0", vx, vy + 120); P.c("gc2_t", "gc2_Dt"); P.c("gc2_k", "gc2_Dt", 0, 1)
    P.obj("gc2_D", "+~ 0", vx, vy + 140); P.c("gc2_Dt", "gc2_D"); P.c("gc2_up", "gc2_D", 1, 1)
    P.obj("gc2_ph", "phasor~ 10", vx + 200, vy + 120)
    P.obj("gc2_ph2o", "+~ 0.5", vx + 300, vy + 120); P.obj("gc2_ph2", "wrap~", vx + 300, vy + 140)
    P.c("gc2_ph", "gc2_ph2o"); P.c("gc2_ph2o", "gc2_ph2")
    taps = []
    for n, ph in (("a", "gc2_ph"), ("b", "gc2_ph2")):
        tx = vx + (0 if n == "a" else 200)
        P.obj(f"gc2_{n}k", "*~ 0", tx, vy + 170); P.c(ph, f"gc2_{n}k"); P.c("gc2_k", f"gc2_{n}k", 1, 1)
        P.sig2(f"gc2_{n}d0", "-~", "gc2_D", f"gc2_{n}k", tx, vy + 190)
        P.obj(f"gc2_{n}d", "clip~ 1.5 3990", tx, vy + 210); P.c(f"gc2_{n}d0", f"gc2_{n}d")
        P.obj(f"gc2_{n}rd", "delread4~ gc_buf", tx, vy + 230); P.c(f"gc2_{n}d", f"gc2_{n}rd")
        P.obj(f"gc2_{n}cos", "cos~", tx + 100, vy + 170); P.c(ph, f"gc2_{n}cos")
        P.obj(f"gc2_{n}cn", "*~ -0.5", tx + 100, vy + 190); P.c(f"gc2_{n}cos", f"gc2_{n}cn")
        P.obj(f"gc2_{n}w", "+~ 0.5", tx + 100, vy + 210); P.c(f"gc2_{n}cn", f"gc2_{n}w")
        taps.append(P.sig2(f"gc2_{n}g", "*~", f"gc2_{n}rd", f"gc2_{n}w", tx, vy + 250))
    P.sig2("gc2_sum", "+~", taps[0], taps[1], vx, vy + 270)
    P.sig2("gc2_s", "*~", "gc2_sum", "gc2_env", vx, vy + 290)
    ex("gc2_pan", "min(1,1-$f1) ; min(1,1+$f1)".replace(" ; ", " " + BS + "; "), vx + 300, vy + 30)
    P.c("gc2_up", "gc2_pan", 3, 0)
    P.obj("gc2_gl", "sig~", vx + 300, vy + 60); P.obj("gc2_gr", "sig~", vx + 370, vy + 60)
    P.c("gc2_pan", "gc2_gl", 0, 0); P.c("gc2_pan", "gc2_gr", 1, 0)
    P.sig2("gc2_l", "*~", "gc2_s", "gc2_gl", vx, vy + 310); P.sig2("gc2_r", "*~", "gc2_s", "gc2_gr", vx + 100, vy + 310)
    P.sig2("gc_mix_l", "+~", outs_l[0], "gc2_l", vx, vy + 330); P.sig2("gc_mix_r", "+~", outs_r[0], "gc2_r", vx + 100, vy + 330)
    outs_l[0], outs_r[0] = "gc_mix_l", "gc_mix_r"
    for i, sig in enumerate(getattr(P, "_probes", [])):
        P.obj(f"gcdbg_E{i}", "env~ 4096", x + 300 + 60 * i, y + 1000); P.obj(f"gcdbg_S{i}", f"s dbg_{sig}", x + 300 + 60 * i, y + 1030)
        P.c(sig, f"gcdbg_E{i}"); P.c(f"gcdbg_E{i}", f"gcdbg_S{i}")
    lvl = smoothed(P, "gc_level", "gc_level", x + 1200, y + 900)
    P.sig2("gcx_out_l", "*~", outs_l[0], lvl, x + 1200, y + 950)
    P.sig2("gcx_out_r", "*~", outs_r[0], lvl, x + 1300, y + 950)
    return "gcx_out_l", "gcx_out_r"


def add_room_notes(P, rx, ex, degree_to_hz):
    """The room plays the notes: the mic goes through narrow resonators tuned to the current chord, so a clap,
    a voice or traffic rings in key. Quiet rooms stay quiet (the input follows the room's liveliness). The
    resonators glide to the new notes when the chord, key or scale changes. Returns the output signal."""
    # Input: the gated mic without rumble. It opens as soon as the level rises above the room's own quiet
    # (the floor the chimes use), so a single clap rings but a quiet room stays silent. With react = 0 it stays open.
    P.sig2("rn_src", "*~", "mic_gated", "ph_ln", rx - 100, 20)    # quieter in a pocket, like the rest
    P.obj("rn_hip", "hip~ 120", rx, 20)
    P.c("rn_src", "rn_hip")
    # The level is measured in short windows, so the gate opens a little late; delay the sound to match.
    P.obj("rn_look_wr", "delwrite~ rn_look 100", rx, 50)
    P.obj("rn_look", f"delread~ rn_look {RES_LOOKAHEAD_MS}", rx, 80)
    P.c("rn_hip", "rn_look_wr")
    P.obj("rn_v_thr", "value mthr", rx + 300, 20)
    P.c("mu_fl_thr", "rn_v_thr")
    P.obj("rn_lvl_t", "t f f b b", rx + 150, 50)                   # the level meter itself: every 5 ms, not 33
    P.obj("rn_rd_thr", "value mthr", rx + 230, 80)
    P.c("meter", "rn_lvl_t"); P.c("rn_lvl_t", "rn_rd_thr", 3, 0)
    ex("rn_open", f"(1-$f3)+$f3*min(max(($f1-$f2)/{RES_OPEN_DB},0),1)", rx + 150, 110)
    P.c("rn_rd_thr", "rn_open", 0, 1); P.c("mu_r_react", "rn_open", 0, 2); P.c("rn_lvl_t", "rn_open", 0, 0)
    # Ring length: "how much was heard" (0..1) jumps with loudness, grows while the sound goes on, then relaxes.
    P.obj("rn_dt", "expr 256/$f1".replace("$", BS + "$"), rx + 450, 20)   # seconds between level readings
    P.c("sr", "rn_dt")
    P.obj("rn_rd_int", "value rn_int", rx + 330, 80)
    P.c("rn_lvl_t", "rn_rd_int", 2, 0)
    ex("rn_int", f"min(max($f3*exp(-$f4/{RES_RELAX_S}),min(max(($f1-$f2)/{RES_LOUD_DB},0),1)*{RES_LOUD_SHARE})"
                 f"+min(max(($f1-$f2)/{RES_LOUD_DB},0),1)*$f4/{RES_BUILD_S},1)", rx + 300, 110)
    P.c("rn_rd_thr", "rn_int", 0, 1); P.c("rn_rd_int", "rn_int", 0, 2); P.c("rn_dt", "rn_int", 0, 3)
    P.c("rn_lvl_t", "rn_int", 1, 0)
    P.obj("rn_int_t", "t f f", rx + 300, 140)
    P.obj("rn_wr_int", "value rn_int", rx + 380, 170)
    P.c("rn_int", "rn_int_t"); P.c("rn_int_t", "rn_wr_int", 1, 0)
    # Squared, so small sounds stay near the short chime and only big or long ones reach the bell.
    ex("rn_ring", f"{RES_RING_SHORT_S}+({RES_RING_LONG_S}-{RES_RING_SHORT_S})*pow((1-$f2)*{RES_STEADY}+$f2*$f1,2)", rx + 300, 170)
    P.c("rn_int_t", "rn_ring", 0, 0); P.c("mu_r_react", "rn_ring", 0, 1)
    # A narrower (longer-ringing) filter catches less of a sharp sound: feed it harder so notes start as loud.
    ex("rn_exc", f"sqrt($f1/{RES_RING_REF_S})", rx + 450, 200)
    P.c("rn_ring", "rn_exc")
    P.obj("rn_exc_sig", "sig~", rx + 450, 230)
    P.obj("rn_exc_lp", "lop~ 20", rx + 450, 260)
    P.c("rn_exc", "rn_exc_sig"); P.c("rn_exc_sig", "rn_exc_lp")
    P.obj("rn_open_sig", "sig~", rx + 150, 140)
    P.obj("rn_open_lp", "lop~ 20", rx + 150, 170)
    P.c("rn_open", "rn_open_sig"); P.c("rn_open_sig", "rn_open_lp")
    P.sig2("rn_in0", "*~", "rn_look", "rn_open_lp", rx, 200)
    P.sig2("rn_in", "*~", "rn_in0", "rn_exc_lp", rx, 290)
    acc = None
    for i, (octs, step) in enumerate(RES_NOTES):
        vx = rx + i * 170
        ex(f"rn{i}_deg", f"$f1+{octs}*$f2+{step}", vx, 180)        # chord root + octaves (scale size each) + step
        P.c("mu_r_n", f"rn{i}_deg", 0, 1)
        P.c("mu_pad_root_v", f"rn{i}_deg", 0, 0)        # the pad's chord root (a scale degree)
        dg_in, dg_hz = degree_to_hz(f"rn{i}", vx, 210)
        P.c(f"rn{i}_deg", dg_in)
        P.obj(f"rn{i}_ft", "t f f", vx, 390)
        P.c(dg_hz, f"rn{i}_ft")
        P.obj(f"rn{i}_pk", f"pack 0 {RES_GLIDE_MS}", vx, 420)
        P.obj(f"rn{i}_ln", "line~", vx, 450)
        P.c(f"rn{i}_ft", f"rn{i}_pk", 1, 0); P.c(f"rn{i}_pk", f"rn{i}_ln")
        ex(f"rn{i}_q", "6.28318*$f2*$f1*sqrt(262/$f2)", vx + 70, 420)    # [vcf~] rings for Q / (2 pi f) s
        P.c(f"rn{i}_ft", f"rn{i}_q", 0, 1)                       # the note (cold), then the ring length (every 5 ms)
        P.c("rn_ring", f"rn{i}_q", 0, 0)
        P.obj(f"rn{i}_vcf", "vcf~", vx, 480)
        P.c("rn_in", f"rn{i}_vcf", 0, 0); P.c(f"rn{i}_ln", f"rn{i}_vcf", 0, 1); P.c(f"rn{i}_q", f"rn{i}_vcf", 0, 2)
        acc = f"rn{i}_vcf" if acc is None else P.sig2(f"rn_acc{i}", "+~", acc, f"rn{i}_vcf", vx, 510)
    P.obj("rn_gain", f"*~ {RES_GAIN}", rx, 540)
    P.c(acc, "rn_gain")
    # Soft limit: a note sung right on a resonator passes at full strength, so cap the voice gently.
    P.obj("rn_soft", "expr~ " + f"{RES_MAX}*tanh($v1/{RES_MAX})".replace("$", BS + "$"), rx, 570)
    P.c("rn_gain", "rn_soft")
    lvl = smoothed(P, "music_res", "music_res", rx + 300, 540)
    # Fade in whenever the block switches on: its resonators start from rest, and with a sound already going
    # they would jump in with a click once the lookahead buffer fills.
    P.obj("rn_fade_sel", "sel 1", rx + 200, 540)
    P.msg("rn_fade_msg", ("0, 1 " + str(RES_FADE_IN_MS) + " " + str(RES_LOOKAHEAD_MS + 10)).replace(",", " " + BS + ","), rx + 200, 560)
    P.obj("rn_fade", "vline~", rx + 200, 580)
    P.c("grp_roomnotes_r", "rn_fade_sel"); P.c("rn_fade_sel", "rn_fade_msg"); P.c("rn_fade_msg", "rn_fade")
    P.sig2("rn_faded", "*~", "rn_soft", "rn_fade", rx, 590)
    P.sig2("rn_out", "*~", "rn_faded", lvl, rx, 600)
    return "rn_out"


def build():
    P = Patch()

    # --- global smoothing time (ms) feeds every ramp ---
    P.obj("r_smooth", "r smooth", 700, 20)
    P.obj("smooth_x3", "* 3", 700, 50)   # echo time glides 3x slower than other controls
    P.c("r_smooth", "smooth_x3")

    # --- input and gain ---
    P.obj("adc", "adc~ 1", 20, 20)
    gain = smoothed(P, "gain", "gain", 20, 60)
    P.sig2("mic", "*~", "adc", gain, 20, 140)

    # --- level meter: RMS in dB (100 = full scale) every ~5 ms, shared by gate and compressor ---
    P.obj("meter", "env~ 1024 256", 20, 170)
    P.c("mic", "meter")
    P.obj("meter_fs", "- 100", 20, 200)                          # dB relative to full scale
    P.c("meter", "meter_fs")
    # The app follows the room's loudness for its "Louder = higher/lower" movers (about 30 a second).
    P.obj("level_clock", "metro 33", 120, 170)
    P.obj("level_hold", "f", 120, 200)                           # latest meter reading
    P.obj("level_send", "s mic_level", 120, 230)
    P.obj("level_start", "loadbang", 120, 140)
    P.c("level_start", "level_clock"); P.c("level_clock", "level_hold")
    P.c("meter", "level_hold", 0, 1); P.c("level_hold", "level_send")

    # --- noise gate: closes when the level is under the threshold (-80 = never closes) ---
    P.obj("r_gate_thresh", "r gate_thresh", 250, 170)
    P.obj("gate_open", "expr ($f1>=$f2)||($f2<=-79.9)".replace("$", BS + "$"), 250, 200)
    P.obj("gate_change", "change", 250, 230)
    P.obj("gate_sel", "sel 0 1", 250, 260)
    P.msg("gate_close", "0 80", 250, 290)                        # fade out over 80 ms
    P.msg("gate_open_msg", "1 5", 330, 290)                      # open within 5 ms
    P.obj("ln_gate", "line~", 250, 320)
    P.c("meter_fs", "gate_open"); P.c("r_gate_thresh", "gate_open", 0, 1)
    P.c("gate_open", "gate_change"); P.c("gate_change", "gate_sel")
    P.c("gate_sel", "gate_close", 0); P.c("gate_sel", "gate_open_msg", 1)
    P.c("gate_close", "ln_gate"); P.c("gate_open_msg", "ln_gate")
    P.sig2("mic_gated", "*~", "mic", "ln_gate", 20, 350)

    # --- compressor: gain reduction = (1 - 1/ratio) * dB over threshold, plus make-up gain ---
    P.obj("r_comp_thresh", "r comp_thresh", 450, 170)
    P.obj("r_comp_ratio", "r comp_ratio", 550, 170)
    P.obj("r_comp_makeup", "r comp_makeup", 650, 170)
    P.obj("comp_calc", "expr 100-(1-1/max($f2{c}1))*max($f1-$f3{c}0)+$f4".replace("{c}", BS + ",").replace("$", BS + "$"), 450, 200)
    P.c("meter_fs", "comp_calc"); P.c("r_comp_ratio", "comp_calc", 0, 1)
    P.c("r_comp_thresh", "comp_calc", 0, 2); P.c("r_comp_makeup", "comp_calc", 0, 3)
    P.obj("comp_lin", "dbtorms", 450, 230)                       # 100 + dB -> linear gain
    P.obj("pk_comp", "pack f 40", 450, 260)
    P.obj("ln_comp", "line~", 450, 290)
    P.c("comp_calc", "comp_lin"); P.c("comp_lin", "pk_comp"); P.c("pk_comp", "ln_comp")
    P.sig2("mic_comp0", "*~", "mic_gated", "ln_comp", 20, 380)

    # --- pocket hush: in a pocket the mic hears cloth and rustle, so turn it down after the compressor
    # (which would otherwise lift the rustle back up). "pocket" (0/1) comes from the app. Mic-down protection adds
    # more, only while the phone sits mic end first ("pocket_down" 0/1): a further cut, and the low cloth thump
    # filtered out. At protection 0 the sound is exactly as without it. ---
    ex = lambda name, text, xx, yy: P.obj(name, "expr " + text.replace(",", BS + ",").replace("$", BS + "$"), xx, yy)
    ex("ph_calc", f"pow(10,-($f1*$f2*{POCKET_HUSH_DB}+$f3*$f4*{POCKET_GUARD_DB})/20)", 800, 260)
    for k, recv in enumerate(("pocket", "pocket_hush", "pocket_down", "pocket_guard")):
        P.obj(f"ph_r{k}", f"r {recv}", 800 + 80 * k, 170)
        if k == 0:
            P.c("ph_r0", "ph_calc")
        else:
            P.obj(f"ph_t{k}", "t b f", 800 + 80 * k, 200)
            P.c(f"ph_r{k}", f"ph_t{k}"); P.c(f"ph_t{k}", "ph_calc", 1, k); P.c(f"ph_t{k}", "ph_calc", 0, 0)
    P.obj("ph_t", "t f f", 800, 290)
    P.obj("ph_v", "value phush", 880, 320)                        # the music reads it too (chimes from rustle)
    P.obj("ph_pk", f"pack f {POCKET_HUSH_MS}", 800, 320)
    P.obj("ph_ln", "line~", 800, 350)
    P.c("ph_calc", "ph_t"); P.c("ph_t", "ph_v", 1, 0); P.c("ph_t", "ph_pk", 0, 0); P.c("ph_pk", "ph_ln")
    P.obj("ph_init", "loadbang", 1160, 230); P.msg("ph_init_msg", "1", 1160, 260)
    P.c("ph_init", "ph_init_msg"); P.c("ph_init_msg", "ph_v"); P.c("ph_init_msg", "ph_ln")
    # the thump filter, crossfaded in by (mic down) x (protection)
    ex("pg_amt", "$f1*$f2", 1100, 290)
    P.obj("pg_down", "f", 1040, 260)
    P.c("ph_t2", "pg_down", 1, 1); P.c("ph_t3", "pg_amt", 1, 1)       # values first, then the bangs below
    P.c("ph_t2", "pg_down", 0, 0); P.c("ph_t3", "pg_down", 0, 0); P.c("pg_down", "pg_amt")
    P.obj("pg_pk", f"pack f {POCKET_HUSH_MS}", 1100, 320)
    P.obj("pg_ln", "line~", 1100, 350)
    P.c("pg_amt", "pg_pk"); P.c("pg_pk", "pg_ln")
    P.obj("pg_hp1", f"hip~ {POCKET_GUARD_HP_HZ}", 120, 380)
    P.obj("pg_hp2", f"hip~ {POCKET_GUARD_HP_HZ}", 120, 395)
    P.c("mic_comp0", "pg_hp1"); P.c("pg_hp1", "pg_hp2")
    P.sig2("pg_diff", "-~", "pg_hp2", "mic_comp0", 120, 410)       # filtered minus plain, times the amount, plus plain
    P.sig2("pg_part", "*~", "pg_diff", "pg_ln", 120, 425)
    P.sig2("mic_comp1", "+~", "mic_comp0", "pg_part", 20, 390)
    P.sig2("mic_comp", "*~", "mic_comp1", "ph_ln", 20, 395)

    # --- ring modulator with bypass ---
    P.obj("r_ring_freq", "r ring_freq", 250, 20)
    P.obj("osc", "osc~ 80", 250, 50)
    P.c("r_ring_freq", "osc")
    mix = smoothed(P, "ring_mix", "ring_mix", 340, 20)
    on = smoothed(P, "ring_on", "ring_on", 450, 20)
    P.sig2("mix_eff", "*~", mix, on, 340, 100)            # amount, forced to 0 when bypassed
    P.sig2("osc_amt", "*~", "osc", "mix_eff", 250, 140)
    P.obj("mix_minus1", "-~ 1", 340, 140)
    P.c("mix_eff", "mix_minus1")
    P.obj("one_minus_mix", "*~ -1", 340, 170)             # 1 - amount
    P.c("mix_minus1", "one_minus_mix")
    P.sig2("carrier", "+~", "osc_amt", "one_minus_mix", 250, 200)
    P.sig2("ring_out", "*~", "mic_comp", "carrier", 20, 230)   # amount 0 -> carrier is 1 -> unchanged

    # --- pitch shifter: two delay taps sweeping through a buffer, crossfaded with Hann windows ---
    # Reading a delay line whose delay changes at rate (1 - ratio) shifts pitch by 'ratio'.
    # The phasor rate (Hz) is (1 - ratio) * 1000 / window_ms; two taps half a cycle apart
    # with windows that sum to 1 hide the wrap-around.
    P.obj("r_pitch_semi", "r pitch_semi", 20, 280)
    P.obj("semi_to_ln", "* 0.0577623", 20, 310)                # semitones * ln(2)/12
    P.obj("ratio", "exp", 20, 340)                              # pitch ratio = 2^(semi/12)
    P.obj("ratio_m1", "- 1", 20, 370)
    P.obj("one_minus_ratio", "* -1", 20, 400)                   # 1 - ratio
    P.obj("pk_rate_a", "pack f 30", 20, 430)
    P.obj("ln_rate_a", "line~", 20, 460)
    P.c("r_pitch_semi", "semi_to_ln"); P.c("semi_to_ln", "ratio"); P.c("ratio", "ratio_m1")
    P.c("ratio_m1", "one_minus_ratio"); P.c("one_minus_ratio", "pk_rate_a"); P.c("pk_rate_a", "ln_rate_a")
    P.c("r_smooth", "pk_rate_a", 0, 1)

    P.obj("r_pitch_window", "r pitch_window", 150, 280)         # grain/window length in ms
    P.obj("pk_win", "pack f 30", 150, 310)
    P.obj("ln_win", "line~", 150, 340)                          # window length, smoothed
    P.c("r_pitch_window", "pk_win"); P.c("pk_win", "ln_win"); P.c("r_smooth", "pk_win", 0, 1)
    P.obj("win_inv", "pow -1", 250, 310)                        # 1 / window
    P.obj("win_inv_k", "* 1000", 250, 340)                      # 1000 / window_ms
    P.obj("pk_rate_b", "pack f 30", 250, 370)
    P.obj("ln_rate_b", "line~", 250, 400)
    P.c("r_pitch_window", "win_inv"); P.c("win_inv", "win_inv_k"); P.c("win_inv_k", "pk_rate_b")
    P.c("pk_rate_b", "ln_rate_b"); P.c("r_smooth", "pk_rate_b", 0, 1)

    P.sig2("rate_hz", "*~", "ln_rate_a", "ln_rate_b", 150, 460)
    P.obj("ph1", "phasor~", 150, 490)
    P.c("rate_hz", "ph1")
    P.obj("ph2_off", "+~ 0.5", 250, 490)
    P.obj("ph2", "wrap~", 250, 520)
    P.c("ph1", "ph2_off"); P.c("ph2_off", "ph2")

    P.obj("delwrite_p", "delwrite~ pitch_buf 400", 20, 500)
    P.c("ring_out", "delwrite_p")
    for n, ph, x in (("1", "ph1", 150), ("2", "ph2", 250)):
        P.sig2(f"tap{n}_ms", "*~", ph, "ln_win", x, 560)
        P.obj(f"tap{n}_off", "+~ 4", x, 590)                    # keep clear of the write head
        P.obj(f"rd{n}", "delread4~ pitch_buf", x, 620)
        P.obj(f"cos{n}", "cos~", x + 90, 560)
        P.obj(f"cos{n}_neg", "*~ -0.5", x + 90, 590)
        P.obj(f"win{n}", "+~ 0.5", x + 90, 620)                 # Hann: 0.5 - 0.5*cos(2*pi*phase)
        P.c(f"tap{n}_ms", f"tap{n}_off"); P.c(f"tap{n}_off", f"rd{n}")
        P.c(ph, f"cos{n}"); P.c(f"cos{n}", f"cos{n}_neg"); P.c(f"cos{n}_neg", f"win{n}")
        P.sig2(f"grain{n}", "*~", f"rd{n}", f"win{n}", x, 650)
    P.sig2("shifted", "+~", "grain1", "grain2", 200, 680)

    pm = smoothed(P, "pitch_mix", "pitch_mix", 350, 280)
    pon = smoothed(P, "pitch_on", "pitch_on", 450, 280)
    P.sig2("pmix_eff", "*~", pm, pon, 350, 360)                 # amount, forced to 0 when bypassed
    P.sig2("shifted_amt", "*~", "shifted", "pmix_eff", 350, 700)
    P.obj("pmix_minus1", "-~ 1", 450, 360)
    P.c("pmix_eff", "pmix_minus1")
    P.obj("pmix_keep", "*~ -1", 450, 390)                       # 1 - amount
    P.c("pmix_minus1", "pmix_keep")
    P.sig2("kept_amt", "*~", "ring_out", "pmix_keep", 450, 700)
    P.sig2("pitched", "+~", "kept_amt", "shifted_amt", 400, 740)

    # --- bit crusher: sample-rate reduction (sample & hold), then bit-depth reduction ---
    # A phasor at the target rate clocks a sample-and-hold: [samphold~] grabs a new input
    # value each time the phasor wraps, so the signal only changes 'crush_rate' times a second.
    # Bit depth rounds to the nearest of 2^(bits-1) steps per polarity, using
    # round(x) = (x + 0.5) - wrap(x + 0.5).
    P.obj("crush_in", "clip~ -1 1", 700, 560)                   # bit depth assumes -1..1
    P.c("pitched", "crush_in")
    crate = smoothed(P, "crush_rate", "crush_rate", 800, 560)
    P.obj("crush_clock", "phasor~", 800, 650)
    P.c(crate, "crush_clock")
    P.obj("crush_hold", "samphold~", 700, 690)
    P.c("crush_in", "crush_hold", 0, 0)
    P.c("crush_clock", "crush_hold", 0, 1)

    P.obj("r_crush_bits", "r crush_bits", 900, 560)
    P.obj("bits_m1", "- 1", 900, 590)
    P.obj("bits_ln", "* 0.693147", 900, 620)                     # times ln(2)
    P.obj("levels", "exp", 900, 650)                             # levels = 2^(bits-1)
    P.obj("pk_levels", "pack f 30", 900, 680)
    P.obj("ln_levels", "line~", 900, 710)
    P.c("r_crush_bits", "bits_m1"); P.c("bits_m1", "bits_ln"); P.c("bits_ln", "levels")
    P.c("levels", "pk_levels"); P.c("pk_levels", "ln_levels"); P.c("r_smooth", "pk_levels", 0, 1)

    P.sig2("scaled", "*~", "crush_hold", "ln_levels", 700, 740)
    P.obj("scaled_half", "+~ 0.5", 700, 770)
    P.c("scaled", "scaled_half")
    P.obj("scaled_frac", "wrap~", 800, 770)
    P.c("scaled_half", "scaled_frac")
    P.sig2("rounded", "-~", "scaled_half", "scaled_frac", 700, 800)
    P.sig2("crushed", "/~", "rounded", "ln_levels", 700, 830)

    cmix = smoothed(P, "crush_mix", "crush_mix", 1000, 560)
    con = smoothed(P, "crush_on", "crush_on", 1100, 560)
    P.sig2("cmix_eff", "*~", cmix, con, 1000, 650)               # amount, forced to 0 when bypassed
    P.sig2("crush_diff", "-~", "crushed", "pitched", 700, 860)
    P.sig2("crush_amt", "*~", "crush_diff", "cmix_eff", 700, 890)
    P.sig2("crushed_mix", "+~", "pitched", "crush_amt", 700, 920)

    # --- distortion: drive the signal into a clipper (three shapes), crossfaded with the clean sound ---
    # Each shape has a small-signal gain of 1, so drive 1 is close to clean and louder only gets
    # grittier. soft = x / (1 + |x|) (never quite reaches 1, so it stays smooth at any drive),
    # hard = x limited to +-1, fold = sin(drive * x * pi/2) * 2/pi (a cosine lookup shifted a
    # quarter cycle).
    drive = smoothed(P, "dist_drive", "dist_drive", 1000, 1000)
    P.sig2("dist_u", "*~", "crushed_mix", drive, 700, 1000)
    P.obj("dist_hard", "clip~ -1 1", 700, 1030)
    P.c("dist_u", "dist_hard")
    P.obj("dist_abs", "abs~", 800, 1030)
    P.obj("dist_den", "+~ 1", 800, 1060)
    P.c("dist_u", "dist_abs"); P.c("dist_abs", "dist_den")
    P.sig2("dist_soft", "/~", "dist_u", "dist_den", 800, 1090)
    P.obj("dist_f1", "*~ 0.25", 900, 1030)
    P.obj("dist_f2", "-~ 0.25", 900, 1060)
    P.obj("dist_f3", "wrap~", 900, 1090)
    P.obj("dist_f4", "cos~", 900, 1120)
    P.obj("dist_fold", "*~ 0.63662", 900, 1150)
    P.c("dist_u", "dist_f1"); P.c("dist_f1", "dist_f2"); P.c("dist_f2", "dist_f3")
    P.c("dist_f3", "dist_f4"); P.c("dist_f4", "dist_fold")
    # shape menu -> three smoothed weights (one is 1, the others 0)
    P.obj("r_dist_type", "r dist_type", 1000, 1030)
    P.obj("dist_sel", "sel 0 1 2", 1000, 1060)
    P.msg("dist_m0", "1 0 0", 1000, 1090); P.msg("dist_m1", "0 1 0", 1060, 1090); P.msg("dist_m2", "0 0 1", 1120, 1090)
    P.obj("dist_unpack", "unpack f f f", 1000, 1120)
    P.c("r_dist_type", "dist_sel")
    for k in range(3):
        P.c("dist_sel", f"dist_m{k}", k)
        P.c(f"dist_m{k}", "dist_unpack")
    shapes = []
    for k, src in enumerate(("dist_soft", "dist_hard", "dist_fold")):
        P.obj(f"dist_pk{k}", "pack f 30", 1000 + 100 * k, 1150)
        P.obj(f"dist_ln{k}", "line~", 1000 + 100 * k, 1180)
        P.c("dist_unpack", f"dist_pk{k}", k)
        P.c(f"dist_pk{k}", f"dist_ln{k}")
        P.c("r_smooth", f"dist_pk{k}", 0, 1)
        shapes.append(P.sig2(f"dist_w{k}", "*~", src, f"dist_ln{k}", 1000 + 100 * k, 1210))
    P.sig2("dist_s01", "+~", shapes[0], shapes[1], 1000, 1240)
    P.sig2("dist_shaped", "+~", "dist_s01", shapes[2], 1000, 1270)
    dmix = smoothed(P, "dist_mix", "dist_mix", 1300, 1000)
    don = smoothed(P, "dist_on", "dist_on", 1400, 1000)
    P.sig2("dmix_eff", "*~", dmix, don, 1300, 1060)              # amount, forced to 0 when bypassed
    P.sig2("dist_diff", "-~", "dist_shaped", "crushed_mix", 1000, 1300)
    P.sig2("dist_amt", "*~", "dist_diff", "dmix_eff", 1000, 1330)
    P.sig2("dist_out", "+~", "crushed_mix", "dist_amt", 1000, 1360)

    # --- filter: one biquad (low-pass / high-pass / band-pass) with coefficients from [expr] ---
    # Standard "audio EQ cookbook" formulas. Frequency changes glide (via [line]); the sample
    # rate comes from [samplerate~]. The max()/min() guards keep the maths finite before the
    # first values arrive, because a NaN would lock the filter up.
    S = "max($f4\\, 8000)"
    W = "6.283185*min(max(exp($f1)\\, 20)\\, 0.45*%s)/%s" % (S, S)   # $f1 is ln(frequency)
    A = "sin(%s)/(2*max($f2\\, 0.1))" % W
    C = "cos(%s)" % W
    a0 = "(1+%s)" % A
    lp, hp, bp = "($f3<0.5)", "(($f3>0.5)*($f3<1.5))", "($f3>1.5)"
    coefs = [
        "2*%s/%s" % (C, a0),                                                      # feedback 1
        "-(1-%s)/%s" % (A, a0),                                                   # feedback 2
        "(%s*(1-%s)/2+%s*(1+%s)/2+%s*%s)/%s" % (lp, C, hp, C, bp, A, a0),         # feedforward 1
        "(%s*(1-%s)-%s*(1+%s))/%s" % (lp, C, hp, C, a0),                          # feedforward 2
        "(%s*(1-%s)/2+%s*(1+%s)/2-%s*%s)/%s" % (lp, C, hp, C, bp, A, a0),         # feedforward 3
    ]
    P.obj("coef", "expr " + (" " + BS + "; ").join(coefs).replace("$", BS + "$"), 1600, 20)
    P.obj("coef_pack", "pack f f f f f", 1600, 70)
    for i in range(5):
        P.c("coef", "coef_pack", i, i)
    P.obj("filt", "biquad~", 1600, 100)
    P.c("coef_pack", "filt")
    P.c("dist_out", "filt")

    P.obj("r_filter_freq", "r filter_freq", 1750, 20)
    P.obj("filter_freq_log", "log", 1750, 35)                    # glide in log frequency: equal-sounding steps
    P.obj("pk_filter_freq", "pack f 30", 1750, 50)
    P.obj("ln_filter_freq", "line 0 3", 1750, 80)                # control-rate glide in 3 ms steps
    P.c("r_filter_freq", "filter_freq_log"); P.c("filter_freq_log", "pk_filter_freq")
    P.c("pk_filter_freq", "ln_filter_freq")
    P.c("r_smooth", "pk_filter_freq", 0, 1)
    P.c("ln_filter_freq", "coef", 0, 0)
    for name, inlet in (("filter_q", 1), ("filter_type", 2)):
        P.obj(f"r_{name}", f"r {name}", 1850 + 100 * inlet, 20)
        P.obj(f"t_{name}", "t b f", 1850 + 100 * inlet, 50)
        P.c(f"r_{name}", f"t_{name}")
        P.c(f"t_{name}", "coef", 1, inlet)                      # value into the cold inlet...
        P.c(f"t_{name}", "coef", 0, 0)                          # ...then re-evaluate
    P.obj("loadbang_sr", "loadbang", 2150, 20)
    P.obj("sr", "samplerate~", 2150, 50)
    P.obj("t_sr", "t b f", 2150, 80)
    P.c("loadbang_sr", "sr"); P.c("sr", "t_sr")
    P.c("t_sr", "coef", 1, 3); P.c("t_sr", "coef", 0, 0)

    fmix = smoothed(P, "filter_mix", "filter_mix", 1600, 160)
    fon = smoothed(P, "filter_on", "filter_on", 1700, 160)
    P.sig2("fmix_eff", "*~", fmix, fon, 1600, 220)               # amount, forced to 0 when bypassed
    P.sig2("filt_diff", "-~", "filt", "dist_out", 1600, 250)
    P.sig2("filt_amt", "*~", "filt_diff", "fmix_eff", 1600, 280)
    P.sig2("filtered_pre", "+~", "dist_out", "filt_amt", 1600, 310)
    # The music joins here, after the tone-changing effects (so pitch shifter and crusher cannot push it
    # out of key) but before chorus, flanger, phaser, tremolo, echo, reverb and the spatial stage.
    music = add_music(P)
    P.sig2("filtered_mix", "+~", "filtered_pre", music, 1600, 340)

    # --- chorus: the signal mixed with two copies whose delay wobbles, which detunes them slightly ---
    P.obj("chorus_wr", "delwrite~ chorus_buf 60", 2300, 20)
    P.c("filtered_mix", "chorus_wr")
    crate = smoothed(P, "chorus_rate", "chorus_rate", 2450, 20)
    P.obj("chorus_ph", "phasor~", 2450, 110)
    P.c(crate, "chorus_ph")
    cdepth = smoothed(P, "chorus_depth", "chorus_depth", 2600, 20)
    for k, (base, offset) in enumerate(zip(CHORUS_BASE_MS, (0, 0.25))):
        n = f"ch{k}"
        P.obj(f"{n}_off", f"+~ {offset}", 2300 + 150 * k, 150)   # quarter-cycle apart
        P.obj(f"{n}_wrap", "wrap~", 2300 + 150 * k, 180)
        P.obj(f"{n}_lfo", "cos~", 2300 + 150 * k, 210)
        P.sig2(f"{n}_sweep", "*~", f"{n}_lfo", cdepth, 2300 + 150 * k, 240)   # +-depth ms
        P.obj(f"{n}_ms", f"+~ {base}", 2300 + 150 * k, 270)
        P.obj(f"{n}_rd", "delread4~ chorus_buf", 2300 + 150 * k, 300)
        P.c("chorus_ph", f"{n}_off"); P.c(f"{n}_off", f"{n}_wrap"); P.c(f"{n}_wrap", f"{n}_lfo")
        P.c(f"{n}_sweep", f"{n}_ms"); P.c(f"{n}_ms", f"{n}_rd")
    P.sig2("ch_sum", "+~", "ch0_rd", "ch1_rd", 2300, 340)
    P.obj("ch_wet", "*~ 0.5", 2300, 370)
    P.c("ch_sum", "ch_wet")
    cmix = smoothed(P, "chorus_mix", "chorus_mix", 2750, 20)
    con = smoothed(P, "chorus_on", "chorus_on", 2850, 20)
    P.sig2("cho_eff", "*~", cmix, con, 2750, 110)                # amount, forced to 0 when bypassed
    P.sig2("cho_diff", "-~", "ch_wet", "filtered_mix", 2300, 400)
    P.sig2("cho_amt", "*~", "cho_diff", "cho_eff", 2300, 430)
    P.sig2("chorused", "+~", "filtered_mix", "cho_amt", 2300, 460)

    # --- flanger: a short delay swept slowly, with feedback, mixed 50/50 with the original at amount 1 ---
    P.obj("fl_wr", "delwrite~ flange_buf 30", 2300, 1000)
    frate = smoothed(P, "flange_rate", "flange_rate", 2450, 1000)
    P.obj("fl_ph", "phasor~", 2450, 1090)
    P.c(frate, "fl_ph")
    fdepth = smoothed(P, "flange_depth", "flange_depth", 2600, 1000)
    P.obj("fl_cos", "cos~", 2450, 1120)
    P.obj("fl_half", "*~ -0.5", 2450, 1150)
    P.obj("fl_unit", "+~ 0.5", 2450, 1180)                       # (1 - cos) / 2, from 0 to 1
    P.sig2("fl_sweep", "*~", "fl_unit", fdepth, 2450, 1210)      # 0 .. depth ms
    P.obj("fl_ms", f"+~ {FLANGE_MIN_MS}", 2450, 1240)
    P.obj("fl_rd", "delread4~ flange_buf", 2450, 1270)
    P.c("fl_ph", "fl_cos"); P.c("fl_cos", "fl_half"); P.c("fl_half", "fl_unit")
    P.c("fl_sweep", "fl_ms"); P.c("fl_ms", "fl_rd")
    ffb = smoothed(P, "flange_fb", "flange_fb", 2750, 1000)
    P.sig2("fl_fb_sig", "*~", "fl_rd", ffb, 2700, 1300)
    P.sig2("fl_in", "+~", "chorused", "fl_fb_sig", 2300, 1330)
    P.c("fl_in", "fl_wr")
    # resonant peaks grow as 1 / (1 - |feedback|); take part of that back out
    P.obj("fl_abs", "abs", 2750, 1050)
    P.obj("fl_k", "* -0.5", 2750, 1080)
    P.obj("fl_k1", "+ 1", 2750, 1110)
    P.obj("pk_fl_k", "pack f 30", 2750, 1140); P.obj("ln_fl_k", "line~", 2750, 1170)
    P.c("r_flange_fb", "fl_abs"); P.c("fl_abs", "fl_k"); P.c("fl_k", "fl_k1"); P.c("fl_k1", "pk_fl_k")
    P.c("pk_fl_k", "ln_fl_k"); P.c("r_smooth", "pk_fl_k", 0, 1)
    P.sig2("fl_wet", "*~", "fl_rd", "ln_fl_k", 2450, 1360)
    fmx = smoothed(P, "flange_mix", "flange_mix", 2900, 1000)
    fon2 = smoothed(P, "flange_on", "flange_on", 3000, 1000)
    P.sig2("fl_eff", "*~", fmx, fon2, 2900, 1060)                # amount, forced to 0 when bypassed
    P.obj("fl_wet_k", "*~ 0.5", 2900, 1090)                      # wet share: 0 .. 0.5
    P.c("fl_eff", "fl_wet_k")
    P.obj("fl_dry_k0", "*~ -1", 3000, 1090)
    P.obj("fl_dry_k", "+~ 1", 3000, 1120)                        # dry share: 1 .. 0.5
    P.c("fl_wet_k", "fl_dry_k0"); P.c("fl_dry_k0", "fl_dry_k")
    P.sig2("fl_wet_part", "*~", "fl_wet", "fl_wet_k", 2450, 1390)
    P.sig2("fl_dry_part", "*~", "chorused", "fl_dry_k", 2800, 1390)
    P.sig2("flanged", "+~", "fl_wet_part", "fl_dry_part", 2450, 1420)

    # --- phaser: four swept allpass filters (biquads), mixed 50/50 with the original at amount 1 ---
    # A control-rate LFO (every 4 ms) sets the sweep frequency; each stage computes its own
    # allpass coefficients from it with [expr] (audio-EQ-cookbook formulas).
    P.obj("ph_start", "loadbang", 3300, 1000)
    P.obj("ph_clock", "metro 4", 3300, 1030)
    P.obj("ph_snap", "snapshot~", 3300, 1060)
    P.c("ph_start", "ph_clock"); P.c("ph_clock", "ph_snap")
    prate = smoothed(P, "phaser_rate", "phaser_rate", 3450, 1000)
    P.obj("ph_osc", "osc~", 3450, 1090)
    P.c(prate, "ph_osc"); P.c("ph_osc", "ph_snap")
    P.obj("r_phaser_depth", "r phaser_depth", 3600, 1000)
    P.obj("ph_sweep", ("expr %d*pow(2%s 2*$f1*$f2)" % (PHASER_CENTRE_HZ, BS + ",")).replace("$", BS + "$"), 3300, 1120)
    P.c("ph_snap", "ph_sweep"); P.c("r_phaser_depth", "ph_sweep", 0, 1)
    P.obj("ph_sr_start", "loadbang", 3750, 1000)
    P.obj("ph_sr", "samplerate~", 3750, 1030)
    P.c("ph_sr_start", "ph_sr")
    S2 = "max($f2" + BS + ", 8000)"
    pfb = smoothed(P, "phaser_fb", "phaser_fb", 3900, 1030)
    P.obj("ph_fb_rd", "delread~ ph_fb 1.4", 3300, 1250)
    P.sig2("ph_fb_sig", "*~", "ph_fb_rd", pfb, 3300, 1280)
    for k, mult in enumerate(PHASER_STAGES):
        W2 = "6.283185*min(max($f1*%s%s 20)%s 0.45*%s)/%s" % (mult, BS + ",", BS + ",", S2, S2)
        A2 = "sin(%s)/(2*%s)" % (W2, PHASER_Q)
        C2 = "cos(%s)" % W2
        a02 = "(1+%s)" % A2
        coefs2 = ["2*%s/%s" % (C2, a02), "-(1-%s)/%s" % (A2, a02),
                  "(1-%s)/%s" % (A2, a02), "-2*%s/%s" % (C2, a02), "(1+%s)/%s" % (A2, a02)]
        P.obj(f"ph_coef{k}", ("expr " + (" " + BS + "; ").join(coefs2)).replace("$", BS + "$"), 3300 + 150 * k, 1160)
        P.obj(f"ph_pack{k}", "pack f f f f f", 3300 + 150 * k, 1190)
        P.obj(f"ph_ap{k}", "biquad~", 3300 + 150 * k, 1220)
        for i in range(5):
            P.c(f"ph_coef{k}", f"ph_pack{k}", i, i)
        P.c(f"ph_pack{k}", f"ph_ap{k}")
        P.c("ph_sweep", f"ph_coef{k}")
        P.c("ph_sr", f"ph_coef{k}", 0, 1)
    P.sig2("ph_in", "+~", "flanged", "ph_fb_sig", 3300, 1310)
    prev = "ph_in"
    for k in range(len(PHASER_STAGES)):
        P.c(prev, f"ph_ap{k}")
        prev = f"ph_ap{k}"
    P.obj("ph_fb_wr", "delwrite~ ph_fb 20", 3600, 1310)
    P.c(prev, "ph_fb_wr")
    pmx = smoothed(P, "phaser_mix", "phaser_mix", 4100, 1000)
    pon2 = smoothed(P, "phaser_on", "phaser_on", 4200, 1000)
    P.sig2("ph_eff", "*~", pmx, pon2, 4100, 1060)                # amount, forced to 0 when bypassed
    P.obj("ph_wet_k", "*~ 0.5", 4100, 1090)
    P.c("ph_eff", "ph_wet_k")
    P.obj("ph_dry_k0", "*~ -1", 4200, 1090)
    P.obj("ph_dry_k", "+~ 1", 4200, 1120)
    P.c("ph_wet_k", "ph_dry_k0"); P.c("ph_dry_k0", "ph_dry_k")
    P.sig2("ph_wet_part", "*~", prev, "ph_wet_k", 3300, 1400)
    P.sig2("ph_dry_part", "*~", "flanged", "ph_dry_k", 3700, 1400)
    P.sig2("phased", "+~", "ph_wet_part", "ph_dry_part", 3300, 1430)

    # --- tremolo: the level swings between full and (1 - depth) at the LFO rate ---
    trate = smoothed(P, "trem_rate", "trem_rate", 2950, 20)
    P.obj("trem_osc", "osc~", 2950, 110)
    P.c(trate, "trem_osc")
    tdepth = smoothed(P, "trem_depth", "trem_depth", 3100, 20)
    ton = smoothed(P, "trem_on", "trem_on", 3200, 20)
    P.sig2("trem_depth_eff", "*~", tdepth, ton, 3100, 110)       # depth, forced to 0 when bypassed
    P.obj("trem_half", "*~ -0.5", 2950, 150)
    P.obj("trem_unit", "+~ 0.5", 2950, 180)                      # (1 - sine) / 2, from 0 to 1
    P.c("trem_osc", "trem_half"); P.c("trem_half", "trem_unit")
    P.sig2("trem_dip", "*~", "trem_unit", "trem_depth_eff", 2950, 210)
    P.obj("trem_neg", "*~ -1", 2950, 240)
    P.obj("trem_gain", "+~ 1", 2950, 270)                        # 1 - dip
    P.c("trem_dip", "trem_neg"); P.c("trem_neg", "trem_gain")
    P.sig2("trem_out", "*~", "phased", "trem_gain", 2950, 310)

    # --- reverse echo: plays the sound backwards in short chunks, mixed in behind the original ---
    # The same two-tap crossfading delay line as the pitch shifter, with playback speed -1: the
    # delay grows by 2 ms per ms, so each tap reads backwards. For chunks of C ms the buffer
    # window is W = 2C ms and the sweep runs at 1000/C Hz.
    P.obj("r_rvs_time", "r rvs_time", 3400, 20)
    P.obj("rvs_w", "* 2", 3400, 50)
    P.obj("pk_rvs_w", "pack f 30", 3400, 80); P.obj("ln_rvs_w", "line~", 3400, 110)
    P.c("r_rvs_time", "rvs_w"); P.c("rvs_w", "pk_rvs_w"); P.c("pk_rvs_w", "ln_rvs_w"); P.c("r_smooth", "pk_rvs_w", 0, 1)
    P.obj("rvs_inv", "pow -1", 3500, 50)
    P.obj("rvs_hz", "* 1000", 3500, 80)
    P.obj("pk_rvs_hz", "pack f 30", 3500, 110); P.obj("ln_rvs_hz", "line~", 3500, 140)
    P.c("r_rvs_time", "rvs_inv"); P.c("rvs_inv", "rvs_hz"); P.c("rvs_hz", "pk_rvs_hz")
    P.c("pk_rvs_hz", "ln_rvs_hz"); P.c("r_smooth", "pk_rvs_hz", 0, 1)
    P.obj("rvs_ph1", "phasor~", 3500, 180)
    P.c("ln_rvs_hz", "rvs_ph1")
    P.obj("rvs_ph2_off", "+~ 0.5", 3600, 180); P.obj("rvs_ph2", "wrap~", 3600, 210)
    P.c("rvs_ph1", "rvs_ph2_off"); P.c("rvs_ph2_off", "rvs_ph2")
    P.obj("rvs_wr", "delwrite~ rvs_buf 2100", 3400, 250)
    P.c("trem_out", "rvs_wr")
    for n, ph, x in (("1", "rvs_ph1", 3400), ("2", "rvs_ph2", 3550)):
        P.sig2(f"rvs_tap{n}_ms", "*~", ph, "ln_rvs_w", x, 290)
        P.obj(f"rvs_tap{n}_off", "+~ 4", x, 320)
        P.obj(f"rvs_rd{n}", "delread4~ rvs_buf", x, 350)
        P.obj(f"rvs_cos{n}", "cos~", x + 80, 290)
        P.obj(f"rvs_cos{n}_neg", "*~ -0.5", x + 80, 320)
        P.obj(f"rvs_win{n}", "+~ 0.5", x + 80, 350)              # Hann window: 0.5 - 0.5*cos(2*pi*phase)
        P.c(f"rvs_tap{n}_ms", f"rvs_tap{n}_off"); P.c(f"rvs_tap{n}_off", f"rvs_rd{n}")
        P.c(ph, f"rvs_cos{n}"); P.c(f"rvs_cos{n}", f"rvs_cos{n}_neg"); P.c(f"rvs_cos{n}_neg", f"rvs_win{n}")
        P.sig2(f"rvs_grain{n}", "*~", f"rvs_rd{n}", f"rvs_win{n}", x, 380)
    P.sig2("rvs_sound", "+~", "rvs_grain1", "rvs_grain2", 3400, 410)
    rmx = smoothed(P, "rvs_mix", "rvs_mix", 3700, 20)
    ron = smoothed(P, "rvs_on", "rvs_on", 3800, 20)
    P.sig2("rvs_eff", "*~", rmx, ron, 3700, 110)                 # level, forced to 0 when bypassed
    P.sig2("rvs_amt", "*~", "rvs_sound", "rvs_eff", 3400, 440)
    P.sig2("rvs_out", "+~", "trem_out", "rvs_amt", 3400, 470)

    # --- glitch / freeze: a feedback loop of 'glitch_len' ms. At hold = 1 the input is replaced by
    # the loop's own output, so the last glitch_len ms repeats until hold comes back down. ---
    hold = smoothed(P, "glitch_hold", "glitch_hold", 3900, 20)
    gon = smoothed(P, "glitch_on", "glitch_on", 4000, 20)
    P.sig2("hold_eff", "*~", hold, gon, 3900, 110)               # forced to 0 when bypassed
    P.obj("hold_inv", "*~ -1", 4000, 110)
    P.obj("live_gain", "+~ 1", 4000, 140)                        # 1 - hold
    P.c("hold_eff", "hold_inv"); P.c("hold_inv", "live_gain")
    glen = smoothed(P, "glitch_len", "glitch_len", 4100, 20)
    P.obj("glitch_rd", "delread4~ glitch_buf", 4100, 110)
    P.c(glen, "glitch_rd")
    P.sig2("glitch_live", "*~", "rvs_out", "live_gain", 3900, 200)
    P.sig2("glitch_loop", "*~", "glitch_rd", "hold_eff", 4100, 200)
    P.sig2("voice", "+~", "glitch_live", "glitch_loop", 4000, 260)   # what the rest of the chain hears
    P.obj("glitch_wr", "delwrite~ glitch_buf 600", 4000, 300)
    P.c("voice", "glitch_wr")

    # --- echo with feedback and bypass ---
    P.obj("r_echo_time", "r echo_time", 560, 20)
    P.obj("pk_echo_time", "pack f 100", 560, 50)
    P.obj("ln_echo_time", "line~", 560, 80)
    # While walking, the echo can lock to the step rhythm (echo_sync: 0 off, 1 = a step, 2 = half, 3 = quarter).
    # The step interval is averaged and moved in 20 ms jumps, so ordinary step-to-step wobble doesn't make the
    # echo warble; 2.5 s after the last step the slider's own time comes back.
    P.obj("ec_r_step", "r step", 700, 20)
    P.obj("ec_step_t", "t b f", 700, 50)
    P.c("ec_r_step", "ec_step_t")
    P.obj("ec_clip", "clip 0.25 1.2", 760, 80)
    ex = lambda n, t, x, y: P.obj(n, "expr " + t.replace(",", BS + ",").replace("$", BS + "$"), x, y)
    ex("ec_avg", "if($f2>0, $f1*0.3+$f2*0.7, $f1)", 760, 110)
    P.obj("ec_avg_t", "t f f", 760, 140)
    ex("ec_grid", "int($f1*50+0.5)/50", 760, 170)
    P.obj("ec_chg", "change", 760, 200)
    P.c("ec_step_t", "ec_clip", 1, 0); P.c("ec_clip", "ec_avg"); P.c("ec_avg", "ec_avg_t")
    P.c("ec_avg_t", "ec_avg", 1, 1); P.c("ec_avg_t", "ec_grid", 0, 0); P.c("ec_grid", "ec_chg")
    P.msg("ec_walk1", "1", 840, 80)
    P.obj("ec_walk_del", f"del {ECHO_WALK_HOLD_MS}", 900, 80)
    P.msg("ec_walk0", "0", 900, 110)
    P.c("ec_step_t", "ec_walk1", 0, 0); P.c("ec_step_t", "ec_walk_del", 0, 0); P.c("ec_walk_del", "ec_walk0")
    P.obj("ec_r_sync", "r echo_sync", 980, 20)
    # gather: slider time, step interval, sync choice, walking -> the echo time to use
    ex("ec_calc", "if($f3>0 && $f4>0.5, min($f2*1000/pow(2, $f3-1), 1900), $f1)", 560, 230)
    P.obj("ec_s0", "f", 560, 200)
    P.c("ec_s0", "ec_calc")
    for k, src in enumerate(("r_echo_time", "ec_chg", "ec_r_sync", None)):
        P.obj(f"ec_in{k}", "t b f", 600 + 60 * k, 170)
        if src:
            P.c(src, f"ec_in{k}")
        if k == 0:
            P.c(f"ec_in{k}", "ec_s0", 1, 1)
        else:
            P.c(f"ec_in{k}", "ec_calc", 1, k)
        P.c(f"ec_in{k}", "ec_s0", 0, 0)
    P.c("ec_walk1", "ec_in3"); P.c("ec_walk0", "ec_in3")
    P.c("ec_calc", "pk_echo_time")
    P.c("pk_echo_time", "ln_echo_time")
    P.c("smooth_x3", "pk_echo_time", 0, 1)
    P.obj("delread", "delread4~ echo_buf", 560, 110)
    P.c("ln_echo_time", "delread")
    fb = smoothed(P, "feedback", "feedback", 560, 150)
    P.sig2("fb_sig", "*~", "delread", fb, 560, 240)
    P.sig2("echo_in", "+~", "voice", "fb_sig", 560, 270)
    P.obj("delwrite", "delwrite~ echo_buf 2000", 560, 300)
    P.c("echo_in", "delwrite")
    wet = smoothed(P, "wet", "wet", 700, 150)
    eon = smoothed(P, "echo_on", "echo_on", 800, 150)
    P.sig2("wet_eff", "*~", wet, eon, 700, 240)           # level, forced to 0 when bypassed
    P.sig2("wet_sig", "*~", "delread", "wet_eff", 700, 270)
    # Echo scatter: each repeat lands somewhere else between the ears. The echo comes back every T ms (the delay time),
    # so a new place is picked every T ms: each repeat of a sound falls in its own window. A new place is at least
    # half the width away from the last (else the other side), and moves there in 15 ms. 0 = in the middle as before.
    P.obj("es_lb", "loadbang", 900, 160)
    P.obj("es_tick", "t b b", 900, 190)
    P.obj("es_T", "snapshot~", 960, 220); P.c("ln_echo_time", "es_T")
    P.obj("es_Tc", "max 20", 960, 250)
    P.obj("es_del", "del 350", 900, 280)
    P.c("es_lb", "es_tick"); P.c("es_tick", "es_T", 0, 0); P.c("es_T", "es_Tc"); P.c("es_Tc", "es_del"); P.c("es_del", "es_tick")
    P.obj("es_rnd", "random 2001", 1040, 220)
    ex("es_pick", "if(abs(($f1/1000-1)-$f2)<0.5, -($f1/1000-1), $f1/1000-1)", 1040, 250)
    P.obj("es_prev", "t f f", 1040, 280)
    P.c("es_tick", "es_rnd", 1, 0); P.c("es_rnd", "es_pick"); P.c("es_pick", "es_prev"); P.c("es_prev", "es_pick", 1, 1)
    P.obj("es_r_amt", "r echo_scatter", 1160, 220)
    ex("es_gains", "min(1,1-$f1*$f2) ; min(1,1+$f1*$f2)".replace(" ; ", " " + BS + "; "), 1040, 310)
    P.c("es_prev", "es_gains", 0, 0); P.c("es_r_amt", "es_gains", 0, 1)
    for k, side in enumerate(("l", "r")):
        P.obj(f"es_pk_{side}", "pack f 15", 1040 + 80 * k, 340); P.obj(f"es_g_{side}", "line~", 1040 + 80 * k, 370)
        P.c("es_gains", f"es_pk_{side}", k, 0); P.c(f"es_pk_{side}", f"es_g_{side}")
        P.sig2(f"wet_{side}", "*~", "wet_sig", f"es_g_{side}", 700 + 80 * k, 400)
    P.obj("es_init", "loadbang", 1200, 340); P.msg("es_one", "1", 1200, 360)
    P.c("es_init", "es_one"); P.c("es_one", "es_g_l"); P.c("es_one", "es_g_r")

    # --- dry level and output ---
    dry = smoothed(P, "dry", "dry", 250, 300)
    P.sig2("dry_sig", "*~", "voice", dry, 250, 380)
    P.obj("mix_pre", "+~", 250, 420); P.c("dry_sig", "mix_pre")      # the echo joins both ears later, scattered
    beat = add_beat(P)
    P.sig2("mix_out", "+~", "mix_pre", beat, 250, 450)       # the beat joins here, so reverb and pan apply to it

    # --- reverb: stereo, added to the mix before the spatial stage ---
    rfb = "0.7+0.28*$f1"                                         # feedback: room size 0..1 -> 0.7..0.98
    P.obj("r_reverb_size", "r reverb_size", 1600, 400)
    P.obj("size_calc", "expr %s %s 0.28*sqrt(1-(%s)*(%s))" % (rfb.replace("$", BS + "$"), BS + ";",
          rfb.replace("$", BS + "$"), rfb.replace("$", BS + "$")), 1600, 430)
    P.c("r_reverb_size", "size_calc")
    P.obj("pk_rfb", "pack f 30", 1600, 470); P.obj("ln_rfb", "line~", 1600, 500)
    P.obj("pk_rin", "pack f 30", 1750, 470); P.obj("ln_rin", "line~", 1750, 500)
    P.c("size_calc", "pk_rfb", 0, 0); P.c("pk_rfb", "ln_rfb"); P.c("r_smooth", "pk_rfb", 0, 1)
    P.c("size_calc", "pk_rin", 1, 0); P.c("pk_rin", "ln_rin"); P.c("r_smooth", "pk_rin", 0, 1)
    P.obj("r_reverb_tone", "r reverb_tone", 1900, 400)           # damping: low-pass cutoff in the loops
    # The input level follows the room size so the reverb stays about equally loud at any size.
    gc_l, gc_r = add_glitch_cloud(P)
    P.sig2("gcx_mono", "+~", gc_l, gc_r, 1700, 520)
    P.obj("gcx_mono_h", "*~ 0.5", 1700, 530)
    P.c("gcx_mono", "gcx_mono_h")
    P.sig2("rev_src0", "+~", "mix_out", "gcx_mono_h", 1600, 525)       # the glitch cloud echoes in the reverb too
    P.sig2("rev_src", "+~", "rev_src0", "wet_sig", 1600, 530)            # and the echo, as before
    P.sig2("rev_in", "*~", "rev_src", "ln_rin", 1600, 540)

    rmix = smoothed(P, "reverb_mix", "reverb_mix", 2000, 400)
    ron = smoothed(P, "reverb_on", "reverb_on", 2100, 400)
    P.sig2("rev_gain", "*~", rmix, ron, 2000, 480)               # level, forced to 0 when bypassed

    for side, extra in (("l", 0.0), ("r", RIGHT_EXTRA_MS)):
        x0 = 1600 if side == "l" else 2000
        combs = []
        for i, ms in enumerate(COMB_MS):
            n = f"c{side}{i}"
            buf = f"comb_{side}{i}"
            P.obj(f"{n}_rd", f"delread~ {buf} {ms + extra:.2f}", x0, 600 + i * 90)
            P.obj(f"{n}_lp", "lop~ 6000", x0, 625 + i * 90)
            P.sig2(f"{n}_fb", "*~", f"{n}_lp", "ln_rfb", x0, 650 + i * 90)
            P.sig2(f"{n}_sum", "+~", "rev_in", f"{n}_fb", x0 + 120, 650 + i * 90)
            P.obj(f"{n}_wr", f"delwrite~ {buf} 100", x0 + 120, 675 + i * 90)
            P.c(f"{n}_rd", f"{n}_lp"); P.c(f"{n}_sum", f"{n}_wr")
            P.c("r_reverb_tone", f"{n}_lp", 0, 1)
            combs.append(f"{n}_rd")
        acc = combs[0]
        for i, c in enumerate(combs[1:]):
            acc = P.sig2(f"c{side}_acc{i}", "+~", acc, c, x0 + 250, 600 + i * 40)
        for k, ms in enumerate(ALLPASS_MS):
            n = f"a{side}{k}"
            buf = f"allp_{side}{k}"
            P.obj(f"{n}_rd", f"delread~ {buf} {ms + extra:.2f}", x0 + 400, 600 + k * 130)
            P.obj(f"{n}_g1", "*~ 0.5", x0 + 400, 625 + k * 130)
            P.sig2(f"{n}_w", "+~", acc, f"{n}_g1", x0 + 400, 650 + k * 130)
            P.obj(f"{n}_wr", f"delwrite~ {buf} 100", x0 + 520, 650 + k * 130)
            P.obj(f"{n}_g2", "*~ 0.5", x0 + 400, 675 + k * 130)
            P.sig2(f"{n}_y", "-~", f"{n}_rd", f"{n}_g2", x0 + 400, 700 + k * 130)
            P.c(f"{n}_rd", f"{n}_g1"); P.c(f"{n}_w", f"{n}_wr"); P.c(f"{n}_w", f"{n}_g2")
            acc = f"{n}_y"
        P.sig2(f"rev_{side}", "*~", acc, "rev_gain", x0 + 400, 1150)
        P.sig2(f"in_{side}0", "+~", "mix_out", f"rev_{side}", x0 + 400, 1200)
        P.sig2(f"in_{side}1", "+~", f"in_{side}0", gc_l if side == "l" else gc_r, x0 + 400, 1210)
        P.sig2(f"in_{side}", "+~", f"in_{side}1", f"wet_{side}", x0 + 400, 1220)

    # --- spatial: ear delay (time difference between the ears), then pan, then output ---
    # Positive 'space_shift' delays the right ear, so the sound seems to come from the left
    # (negative: from the right). Larger values (10-25 ms) widen the sound instead of moving it.
    for side in ("l", "r"):
        P.obj(f"space_wr_{side}", f"delwrite~ space_buf_{side} 100", 250, 440)
        P.c(f"in_{side}", f"space_wr_{side}")
    shift = smoothed(P, "space_shift", "space_shift", 1200, 20)
    son = smoothed(P, "space_on", "space_on", 1300, 20)
    P.sig2("shift_eff", "*~", shift, son, 1200, 110)            # forced to 0 when bypassed
    P.obj("shift_neg", "*~ -1", 1300, 110)
    P.c("shift_eff", "shift_neg")
    for side, src, x in (("l", "shift_neg", 1300), ("r", "shift_eff", 1200)):
        P.obj(f"d_{side}_pos", "clip~ 0 25", x, 150)            # only one ear is delayed at a time
        P.obj(f"d_{side}_ms", f"+~ {EAR_BASE_MS}", x, 180)
        P.obj(f"rd_{side}", f"delread4~ space_buf_{side}", x, 210)
        P.c(src, f"d_{side}_pos"); P.c(f"d_{side}_pos", f"d_{side}_ms"); P.c(f"d_{side}_ms", f"rd_{side}")

    # Balance-style pan: centre leaves both ears at full level, hard pan silences the far ear.
    pan = smoothed(P, "space_pan", "space_pan", 1400, 20)
    P.sig2("pan_eff", "*~", pan, son, 1400, 110)                # forced to 0 when bypassed
    P.obj("pan_up", "clip~ 0 1", 1400, 150)                     # how far right of centre
    P.obj("pan_up_neg", "*~ -1", 1400, 180)
    P.obj("gain_l", "+~ 1", 1400, 210)                          # left gain = 1 - right-of-centre
    P.c("pan_eff", "pan_up"); P.c("pan_up", "pan_up_neg"); P.c("pan_up_neg", "gain_l")
    P.obj("pan_neg", "*~ -1", 1500, 110)
    P.obj("pan_down", "clip~ 0 1", 1500, 150)                   # how far left of centre
    P.obj("pan_down_neg", "*~ -1", 1500, 180)
    P.obj("gain_r", "+~ 1", 1500, 210)                          # right gain = 1 - left-of-centre
    P.c("pan_eff", "pan_neg"); P.c("pan_neg", "pan_down"); P.c("pan_down", "pan_down_neg")
    P.c("pan_down_neg", "gain_r")
    P.sig2("out_l", "*~", "rd_l", "gain_l", 1400, 260)
    P.sig2("out_r", "*~", "rd_r", "gain_r", 1500, 260)

    # Duck: while another app plays (music, navigation), the app sends "duck <cut 0..1>" and the whole output dips a
    # little, so both can be heard. 0 = full level (also before anything arrives).
    P.obj("r_duck", "r duck", 1600, 290)
    P.msg("duck_msg", BS + "$1 " + str(DUCK_MS), 1600, 320)
    P.obj("duck_ln", "line~", 1600, 350)
    P.obj("duck_neg", "*~ -1", 1600, 370)
    P.obj("duck_gain", "+~ 1", 1600, 390)
    P.c("r_duck", "duck_msg"); P.c("duck_msg", "duck_ln"); P.c("duck_ln", "duck_neg"); P.c("duck_neg", "duck_gain")

    # Soft limiter: untouched up to 0.7, then the part above is eased in with a smooth cubic
    # so peaks never pass 1.0 and loud audio rounds off instead of hard-clipping into fuzz.
    for side, x in (("l", 1400), ("r", 1500)):
        o = lambda n, t, y: P.obj(f"lim_{side}_{n}", t, x, y)
        o("base", "clip~ -0.7 0.7", 290)             # the transparent part
        o("neg", "*~ -1", 300)
        o("exc", "+~", 310)                          # excess = input - base
        o("scale", "*~ 3.33333", 320)                # excess in units of the 0.3 headroom
        o("cl", "clip~ -1.5 1.5", 330)
        o("sq", "*~", 340)
        o("k", "*~ -0.148148", 350)
        o("one", "+~ 1", 360)
        o("cub", "*~", 370)
        o("back", "*~ 0.3", 380)
        o("sum", "+~", 390)
        P.c(f"out_{side}", f"lim_{side}_base"); P.c(f"out_{side}", f"lim_{side}_exc", 0, 0)
        P.c(f"lim_{side}_base", f"lim_{side}_neg"); P.c(f"lim_{side}_neg", f"lim_{side}_exc", 0, 1)
        P.c(f"lim_{side}_exc", f"lim_{side}_scale"); P.c(f"lim_{side}_scale", f"lim_{side}_cl")
        P.c(f"lim_{side}_cl", f"lim_{side}_sq", 0, 0); P.c(f"lim_{side}_cl", f"lim_{side}_sq", 0, 1)
        P.c(f"lim_{side}_sq", f"lim_{side}_k"); P.c(f"lim_{side}_k", f"lim_{side}_one")
        P.c(f"lim_{side}_cl", f"lim_{side}_cub", 0, 0); P.c(f"lim_{side}_one", f"lim_{side}_cub", 0, 1)
        P.c(f"lim_{side}_cub", f"lim_{side}_back")
        P.c(f"lim_{side}_back", f"lim_{side}_sum", 0, 0); P.c(f"lim_{side}_base", f"lim_{side}_sum", 0, 1)
        P.sig2(f"limit_{side}", "*~", f"lim_{side}_sum", "duck_gain", x, 400)
    P.obj("dac", "dac~ 1 2", 1400, 430)
    P.c("limit_l", "dac", 0, 0)
    P.c("limit_r", "dac", 0, 1)

    # --- switchable blocks: each one's DSP stops while it can't be heard ---
    P.group("reverb", r"^(c[lr]\d+_|c[lr]_acc\d|a[lr]\d_|rev_in$|rev_[lr]$|pk_rfb$|ln_rfb$|pk_rin$|ln_rin$)")
    add_switch(P, "reverb", ("reverb_on", "reverb_mix"), 300)
    P.group("pitch", r"^(rate_hz|ph1|ph2|ph2_off|delwrite_p|tap[12]_\w+|rd[12]|cos[12]|cos[12]_neg|win[12]|grain[12]|shifted)$")
    add_switch(P, "pitch", ("pitch_on", "pitch_mix"), 300)
    P.group("chorus", r"^(chorus_wr|chorus_ph|ch[01]_\w+|ch_sum|ch_wet)$")
    add_switch(P, "chorus", ("chorus_on", "chorus_mix"), 300)
    P.group("flanger", r"^(fl_wr|fl_ph|fl_cos|fl_half|fl_unit|fl_sweep|fl_ms|fl_rd|fl_fb_sig|fl_in|fl_wet)$")
    add_switch(P, "flanger", ("flange_on", "flange_mix"), 300)
    P.group("phaser", r"^(ph_start|ph_clock|ph_snap|ph_osc|ph_sweep|ph_sr_start|ph_sr|ph_fb_rd|ph_fb_sig|ph_coef\d|ph_pack\d|ph_ap\d|ph_in|ph_fb_wr)$")
    add_switch(P, "phaser", ("phaser_on", "phaser_mix"), 300, also=("ph_clock",))   # the 4 ms clock stops too
    P.group("reverse", r"^(rvs_ph1|rvs_ph2_off|rvs_ph2|rvs_wr|rvs_tap\d_\w+|rvs_rd\d|rvs_cos\d\w*|rvs_win\d|rvs_grain\d|rvs_sound)$")
    add_switch(P, "reverse", ("rvs_on", "rvs_mix"), 300)
    P.group("roomnotes", r"^rn\d*_")
    add_switch(P, "roomnotes", ("music_on", "music_res"), 2500)       # rings run up to ~2 s
    P.group("music", r"^(mu_|ba_)")
    add_switch(P, "music", ("music_on",), 3000)                       # chimes fade over up to 2.6 s
    P.group("gcv", r"^gc0_")                                           # the glitch voices: on only while playing
    P.group("gcs", r"^gc2_")
    P.group("gcloud", r"^gc\d*_(?!r_amt$|amt$|amt_rd$|clk_|rest|cool|m_t$|det|slow|roll|pass|ons_t$|timer$|flag|trig$|ask$|walk|step|half|pend|beat_t$|fire$|mode|en\d$|rn\d$|el2?$|st2$|st_rd$|stepms|par$|pack$|wait|vc|route$|dbg|kind$|spar$|spack$)")
    add_switch(P, "gcloud", ("gc_amount", "gc_level"), 1500)           # a glitch runs up to ~1.3 s

    # --- defaults on load (desktop Pd / standalone) ---
    P.obj("loadbang", "loadbang", 20, 780)
    body = " ".join(f"{BS}; {k} {v}" for k, v in DEFAULTS)
    P.msg("defaults", body, 20, 810)
    P.c("loadbang", "defaults")
    return P


if __name__ == "__main__":
    path = os.path.normpath(OUT)
    with open(path, "w") as f:
        f.write(build().text())
    print("wrote", path)
