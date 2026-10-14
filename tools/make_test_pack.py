#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Writes a small stem pack of synth loops for trying the stems player before real packs exist:
pad (two sections), bass, drums, lead and texture, 4 bars at 100 BPM in A minor, 44.1 kHz 16-bit stereo WAV.

    python3 tools/make_test_pack.py <output folder> [--zip]
"""
import os, sys, wave, zipfile
import numpy as np

SR, BPM, BARS = 44100, 100, 4
BEAT = 60 / BPM
N = int(round(SR * BARS * 4 * BEAT))          # exactly 4 bars
t = np.arange(N) / SR
A3 = 220.0
def hz(semis): return A3 * 2 ** (semis / 12)

def env(start, length, attack=0.01, release=0.2):
    """A note's envelope placed at start (s), length (s), wrapped so the loop is seamless."""
    e = np.zeros(N)
    k = np.arange(int(length * SR))
    a = np.minimum(1, k / (attack * SR)); r = np.minimum(1, (len(k) - k) / (release * SR))
    idx = (int(start * SR) + k) % N
    e[idx] += a * r
    return e

def tone(f, shape="sine"):
    ph = 2 * np.pi * f * t
    if shape == "saw":
        return sum(np.sin(k * ph) / k for k in range(1, 12)) * 0.6
    if shape == "square":
        return sum(np.sin(k * ph) / k for k in range(1, 12, 2)) * 0.8
    return np.sin(ph)

def pad(chords):
    y = np.zeros(N)
    for bar, chord in enumerate(chords):
        for s in chord:
            for det in (1.0, 1.004):
                y += tone(hz(s) * det, "saw") * env(bar * 4 * BEAT, 4 * BEAT, 0.4, 0.6) * 0.06
    return y

def bass():
    y = np.zeros(N)
    roots = [-12, -12, -16, -14]                                  # A, A, F, G (an octave down)
    for bar, r in enumerate(roots):
        for e8 in range(8):
            y += tone(hz(r), "square") * env((bar * 4 + e8 / 2) * BEAT, BEAT / 2 * 0.8, 0.005, 0.05) * 0.18
    return y

def drums(rng=np.random.default_rng(1)):
    y = np.zeros(N)
    for beat in range(BARS * 4):
        st = beat * BEAT
        k = np.arange(int(0.25 * SR)); idx = (int(st * SR) + k) % N
        if beat % 2 == 0:                                         # kick on 1 and 3
            f = 50 + 70 * np.exp(-k / (0.02 * SR))
            y[idx] += np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-k / (0.12 * SR)) * 0.7
        else:                                                     # snare on 2 and 4
            y[idx] += rng.standard_normal(len(k)) * np.exp(-k / (0.06 * SR)) * 0.25
        for half in (0, 0.5):                                     # hats on the 8ths
            kk = np.arange(int(0.05 * SR)); j = (int((st + half * BEAT) * SR) + kk) % N
            y[j] += np.diff(np.concatenate([[0], rng.standard_normal(len(kk))])) * np.exp(-kk / (0.01 * SR)) * 0.08
    return y

def lead():
    y = np.zeros(N)
    notes = [12, 15, 19, 15, 12, 10, 7, 10] * 2                   # an A minor arpeggio, in 8ths over 2 bars, twice
    for i, s in enumerate(notes):
        y += tone(hz(s), "square") * env(i * BEAT / 2 * 2, BEAT * 0.8, 0.01, 0.2) * 0.08
    return y

def texture(rng=np.random.default_rng(2)):
    noise = rng.standard_normal(N)
    S = np.fft.rfft(noise); f = np.fft.rfftfreq(N, 1 / SR)
    S[(f < 600) | (f > 2500)] = 0
    y = np.fft.irfft(S, N)
    return y / np.max(np.abs(y)) * 0.15 * (0.5 - 0.5 * np.cos(2 * np.pi * t / (N / SR)))

def write(path, mono, width=0.0):
    left = mono * (1 - width); right = mono * (1 + width)
    st = np.stack([left, right], 1)
    st /= max(1.0, np.max(np.abs(st)) / 0.89)                     # peaks under -1 dB
    w = wave.open(path, "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st * 32767).astype(np.int16).tobytes()); w.close()

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
write(os.path.join(out, "pad_A.wav"), pad([[0, 3, 7], [0, 3, 7], [-4, 0, 3], [-2, 2, 5]]), 0.2)   # Am Am F G
write(os.path.join(out, "pad_B.wav"), pad([[-4, 0, 3], [-2, 2, 5], [0, 3, 7], [-5, -2, 2]]), 0.2) # F G Am Em
write(os.path.join(out, "bass.wav"), bass())
write(os.path.join(out, "drums.wav"), drums(), 0.05)
write(os.path.join(out, "lead.wav"), lead(), 0.3)
write(os.path.join(out, "texture.wav"), texture(), 0.5)
open(os.path.join(out, "pack.txt"), "w").write("""title: PdScenes test pack
bpm: 100
key: A minor
bars: 4

pad_A.wav     role: pad
pad_B.wav     role: pad
bass.wav      role: bass
drums.wav     role: drums
lead.wav      role: lead
texture.wav   role: texture
""")
if "--zip" in sys.argv:
    z = out.rstrip("/") + ".zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(os.listdir(out)):
            zf.write(os.path.join(out, f), os.path.join(os.path.basename(out.rstrip("/")), f))
    print("wrote", z)
print("wrote", out)
