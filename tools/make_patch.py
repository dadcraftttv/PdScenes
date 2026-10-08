#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generates app/src/main/assets/patches/test_scene.pd.

Pd patch files address objects by index, which is easy to break by hand. This builds the
graph from named nodes instead, so adding an effect is a few lines. Run from anywhere:

    python3 tools/make_patch.py
"""
import os

BS = chr(92)  # a literal backslash; Pd writes escaped semicolons as "\;"
OUT = os.path.join(os.path.dirname(__file__), "..", "app", "src", "main", "assets",
                   "patches", "test_scene.pd")

# Defaults for the loadbang message (lets the patch also run standalone in desktop Pd).
# tools/test_patch.py checks these against Params.java so they cannot drift.
DEFAULTS = [
    ("gain", 2.5), ("dry", 1), ("echo_on", 1), ("echo_time", 350), ("feedback", 0.4),
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
    ("music_tone", 0.5), ("music_react", 0.8), ("music_res", 0.8),
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
ARP_PATTERN = (0, 2, 4, 7, 4, 2)    # scale steps above the current chord root, one per footstep
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

    def text(self):
        out = ["#N canvas 0 0 900 900 12;"] + self.lines
        for a, o, b, i in self.conns:
            out.append(f"#X connect {self.index[a]} {o} {self.index[b]} {i};")
        return "\n".join(out) + "\n"


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
    h_amp = env("h_amp", "0, 1 1, 0 45 1", "hat_del", 0, x + 750, 220)
    P.obj("h_hp", "hip~ 7000", x + 750, 250)
    P.c("noise", "h_hp")
    P.sig2("hat_raw", "*~", "h_hp", h_amp, x + 750, 350)
    hats = smoothed(P, "beat_hats", "beat_hats", x + 900, 20)
    P.sig2("hat", "*~", "hat_raw", hats, x + 750, 380)

    # Mix, master level and on/off switch (a little headroom so the drums never clip the output).
    P.sig2("beat_kick_snare", "+~", "kick", "snare", x, 500)
    P.sig2("beat_sum", "+~", "beat_kick_snare", "hat", x, 530)
    lvl = smoothed(P, "beat_level", "beat_level", x + 1050, 20)
    bon = smoothed(P, "beat_on", "beat_on", x + 1150, 20)
    P.sig2("beat_gain", "*~", lvl, bon, x + 1050, 120)
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
    P.obj("mu_r_scale", "r music_scale", x, 50)
    P.obj("mu_scale_t", "t b f", x, 65)                                  # table first, then re-pick the chord
    sel = P.obj("mu_scale_sel", "sel " + " ".join(str(i) for i in range(len(SCALES))), x, 80)
    P.c("mu_r_scale", "mu_scale_t"); P.c("mu_scale_t", sel, 1, 0)
    for i, iv in enumerate(SCALES):
        pool, contrast = CHORD_POOLS[i]
        text = (f"{BS}; scale_iv 0 {' '.join(str(v) for v in iv)} {BS}; scale_n {len(iv)}"
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
    P.obj("mu_deg", "t b b f", cx, cy)                                    # in: a velocity from 0 to 1
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
    P.c("mu_note_t", "mu_rr", 0, 0)
    P.c("mu_rr", "mu_rr_add"); P.c("mu_rr_add", "mu_rr_mod"); P.c("mu_rr_mod", "mu_rr", 0, 1)
    P.c("mu_rr", "mu_rr_sel")
    P.obj("mu_v_vel", "value cvel", cx, cy + 40)
    P.c("mu_deg", "mu_v_vel", 2, 0)
    voices = []
    for k in range(4):
        vx = cx + 600 + k * 260
        P.obj(f"mu_v{k}_trig", "t b b", vx, cy)
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
        P.c(f"mu_v{k}_trig", f"mu_v{k}_f", 1, 0)
        P.c(f"mu_v{k}_f", f"mu_v{k}_ft")
        P.c(f"mu_v{k}_ft", f"mu_v{k}_o1", 2, 0)
        P.c(f"mu_v{k}_ft", f"mu_v{k}_f2", 1, 0); P.c(f"mu_v{k}_f2", f"mu_v{k}_o2")
        P.c(f"mu_v{k}_ft", f"mu_v{k}_f3", 0, 0); P.c(f"mu_v{k}_f3", f"mu_v{k}_o3")
        P.c(f"mu_v{k}_o2", f"mu_v{k}_g2"); P.c(f"mu_v{k}_o3", f"mu_v{k}_g3")
        P.sig2(f"mu_v{k}_s12", "+~", f"mu_v{k}_o1", f"mu_v{k}_g2", vx + 60, cy + 180)
        P.sig2(f"mu_v{k}_s", "+~", f"mu_v{k}_s12", f"mu_v{k}_g3", vx + 60, cy + 210)
        P.obj(f"mu_v{k}_vel", "value cvel", vx, cy + 30)
        P.c(f"mu_v{k}_trig", f"mu_v{k}_vel", 0, 0)
        P.msg(f"mu_v{k}_env_msg", ("0, " + BS + "$1 4, 0 1600 4").replace(",", comma), vx, cy + 60)
        P.obj(f"mu_v{k}_env", "vline~", vx, cy + 90)
        P.c(f"mu_v{k}_vel", f"mu_v{k}_env_msg"); P.c(f"mu_v{k}_env_msg", f"mu_v{k}_env")
        P.sig2(f"mu_v{k}_out", "*~", f"mu_v{k}_s", f"mu_v{k}_env", vx + 60, cy + 240)
        voices.append(f"mu_v{k}_out")
    acc = voices[0]
    for i, v in enumerate(voices[1:]):
        acc = P.sig2(f"mu_chime_acc{i}", "+~", acc, v, cx + 600, cy + 280 + 30 * i)
    P.obj("mu_chime_scale", "*~ 0.22", cx + 600, cy + 380)
    P.c(acc, "mu_chime_scale")
    P.obj("mu_chime_lp", "lop~ 3000", cx + 600, cy + 410)
    P.c("mu_chime_scale", "mu_chime_lp")
    # mu_deg: store velocity, then pick a degree from the brightness (plus a little wander).
    P.obj("mu_jit", "random 3", cx + 100, cy + 40)
    P.obj("mu_jit_m", "- 1", cx + 100, cy + 70)
    P.c("mu_deg", "mu_jit", 1, 0); P.c("mu_jit", "mu_jit_m")
    ex("mu_pick", "int($f1*2*$f2+0.5)+$f2+$f3", cx, cy + 100)
    P.obj("mu_rd_pick", "value mbright", cx, cy + 70)                     # a bang makes it output its number
    P.c("mu_deg", "mu_rd_pick", 0, 0)
    P.c("mu_rd_pick", "mu_pick", 0, 0)
    P.c("mu_r_n", "mu_pick", 0, 1)
    P.c("mu_jit_m", "mu_pick", 0, 2)
    P.c("mu_pick", degree_in)

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
    ex("mu_ons_vel", "0.3+0.5*$f1", x + 300, 660)
    P.obj("mu_rd_ons", "value mloud", x + 300, 640)
    P.c("mu_ons_t", "mu_rd_ons", 0, 0); P.c("mu_rd_ons", "mu_ons_vel"); P.c("mu_ons_vel", "mu_deg")

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
    ex("mu_p", "320*pow($f1,3)", x + 900, 720)                       # chance in 1000 every 0.25 s: 0 in a quiet room, about 1 in 3 when lively
    P.obj("mu_rd_p", "value mloud", x + 900, 690)
    P.c("mu_still_t", "mu_roll", 0, 0)
    P.c("mu_still_t", "mu_rd_p", 1, 0); P.c("mu_rd_p", "mu_p"); P.c("mu_p", "mu_chance", 0, 1)
    P.c("mu_roll", "mu_chance")
    P.obj("mu_chance_sel", "sel 1", x + 800, 780)
    P.c("mu_chance", "mu_chance_sel")
    ex("mu_still_vel", "0.12+0.5*$f1", x + 800, 840)
    P.obj("mu_still_load", "t b", x + 800, 810)
    P.obj("mu_rd_still", "value mloud", x + 900, 810)
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
    ex("mu_pace_vel", "0.18+0.82*$f1", x + 1200, 720)
    P.c("mu_step_t", "mu_pace", 1, 0); P.c("mu_pace", "mu_pace_f"); P.c("mu_pace_f", "mu_pace_vel")
    P.c("mu_pace_vel", "mu_v_vel")
    P.obj("mu_arp_gate", "spigot", x + 1100, 660)
    P.c("mu_step_t", "mu_arp_gate", 0, 0)
    P.obj("mu_arp_t", "t b b b", x + 1100, 690)
    P.c("mu_arp_gate", "mu_arp_t")
    P.obj("mu_v_chord", "value mchord", x + 1100, 720)
    P.obj("mu_ptab", "table arp_pat 6", x + 1300, 20)
    P.msg("mu_ptab_init", f"{BS}; arp_pat 0 {' '.join(str(v) for v in ARP_PATTERN)}", x + 1300, 50)
    P.c("mu_load", "mu_ptab_init")
    P.obj("mu_pat_i", "f", x + 1100, 750)
    P.obj("mu_pat_add", "+ 1", x + 1100, 780)
    P.obj("mu_pat_mod", "mod 6", x + 1100, 810)
    P.obj("mu_pat_tab", "tabread arp_pat", x + 1100, 840)
    P.c("mu_pat_i", "mu_pat_add"); P.c("mu_pat_add", "mu_pat_mod"); P.c("mu_pat_mod", "mu_pat_i", 0, 1)
    P.c("mu_pat_i", "mu_pat_tab")
    ex("mu_arp_deg", "$f1+$f2+$f3", x + 1100, 870)
    P.obj("mu_arp_n", "value scale_n", x + 1250, 780)
    P.c("mu_arp_t", "mu_arp_n", 2, 0)                                 # bang: output the scale size
    P.c("mu_arp_n", "mu_arp_deg", 0, 2)
    P.c("mu_arp_t", "mu_v_chord", 1, 0); P.c("mu_v_chord", "mu_arp_deg", 0, 1)
    P.c("mu_arp_t", "mu_pat_i", 0, 0)
    P.c("mu_pat_tab", "mu_arp_deg")
    P.c("mu_arp_deg", degree_in)
    # The arpeggio note itself needs the chime path's tail (frequency, round robin): it joins at degree_in.
    # Walking state: while steps keep coming the "still" pattern stays quiet.
    P.obj("mu_walk_t", "t b b", x + 1100, 900)
    P.c("mu_step_t", "mu_walk_t", 0, 0)
    P.obj("mu_walk_del", "del 2500", x + 1160, 930)
    P.c("mu_walk_t", "mu_still_off", 1, 0); P.c("mu_walk_t", "mu_walk_del", 0, 0)
    P.c("mu_walk_del", "mu_still_back")
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
    ex("mu_pad_idx", "int(min(max($f1*($f3-1)+$f2*0.6,0),$f3-1)+0.5)", px, 140)
    P.c("mu_chord_go", "mu_pad_jit", 1, 0); P.c("mu_pad_jit", "mu_pad_jit_m"); P.c("mu_pad_jit_m", "mu_pad_idx", 0, 1)
    P.c("mu_r_pool_n", "mu_pad_idx", 0, 2)
    P.obj("mu_rd_root", "value mbright", px + 160, 110)
    P.c("mu_chord_go", "mu_rd_root", 0, 0); P.c("mu_rd_root", "mu_pad_idx")
    P.obj("mu_pad_pool", "tabread chord_pool", px, 160)
    P.c("mu_pad_idx", "mu_pad_pool")
    # now and then the contrast chord instead (when the scale has one)
    P.obj("mu_pad_roll", "random 100", px + 160, 140)
    P.c("mu_chord_go", "mu_pad_roll", 2, 0)
    P.obj("mu_r_pool_x", "r pool_x", px + 300, 140)
    ex("mu_pad_root", f"if($f2<{CONTRAST_PCT}&&$f3>=0,$f3,$f1)", px, 180)
    P.c("mu_pad_pool", "mu_pad_root"); P.c("mu_pad_roll", "mu_pad_root", 0, 1); P.c("mu_r_pool_x", "mu_pad_root", 0, 2)
    P.obj("mu_pad_root_v", "t f f b", px, 200)
    P.c("mu_pad_root", "mu_pad_root_v")
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
    P.sig2("mu_pad_out", "*~", "mu_pad_b", pad_lvl, px, 900)
    P.sig2("mu_chime_out", "*~", "mu_chime_lp", arp_lvl, px + 200, 900)
    P.sig2("mu_mix0", "+~", "mu_pad_out", "mu_chime_out", px, 930)
    P.sig2("mu_mix", "+~", "mu_mix0", add_room_notes(P, x + 2500, ex, degree_to_hz), px, 945)
    P.sig2("mu_out", "*~", "mu_mix", mon, px, 960)
    return "mu_out"


def add_room_notes(P, rx, ex, degree_to_hz):
    """The room plays the notes: the mic goes through narrow resonators tuned to the current chord, so a clap,
    a voice or traffic rings in key. Quiet rooms stay quiet (the input follows the room's liveliness). The
    resonators glide to the new notes when the chord, key or scale changes. Returns the output signal."""
    # Input: the gated mic without rumble. It opens as soon as the level rises above the room's own quiet
    # (the floor the chimes use), so a single clap rings but a quiet room stays silent. With react = 0 it stays open.
    P.obj("rn_hip", "hip~ 120", rx, 20)
    P.c("mic_gated", "rn_hip")
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
    P.sig2("rn_out", "*~", "rn_soft", lvl, rx, 600)
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
    P.sig2("mic_comp", "*~", "mic_gated", "ln_comp", 20, 380)

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
    P.c("r_echo_time", "pk_echo_time")
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

    # --- dry level and output ---
    dry = smoothed(P, "dry", "dry", 250, 300)
    P.sig2("dry_sig", "*~", "voice", dry, 250, 380)
    P.sig2("mix_pre", "+~", "dry_sig", "wet_sig", 250, 420)
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
    P.sig2("rev_in", "*~", "mix_out", "ln_rin", 1600, 540)

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
        P.sig2(f"in_{side}", "+~", "mix_out", f"rev_{side}", x0 + 400, 1200)

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
        P.obj(f"limit_{side}", "*~ 1", x, 400)
        P.c(f"lim_{side}_sum", f"limit_{side}")
    P.obj("dac", "dac~ 1 2", 1400, 430)
    P.c("limit_l", "dac", 0, 0)
    P.c("limit_r", "dac", 0, 1)

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
