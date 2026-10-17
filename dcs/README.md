# dcs — Pd objects by DadCraft Studios

Audio objects for [Pure Data](https://puredata.info), written in C. They do things a Pd patch can't do well on
its own: sample-exact timing, feedback shorter than a 64-sample block, and searches inside the audio.
BSD 3-Clause licensed (see `LICENSE`), like Pd itself.

Load them all with `[declare -lib dcs]`. Every object starts with `dcs_`, so they can never clash with Pd's own
objects or with anyone's abstractions.

## Objects

- **`[dcs_string~ freq decay brightness]`** — a plucked or bowed string (extended Karplus-Strong). Whatever
  comes into it rings on the string, and a `pluck amp [position]` message plucks it like a finger. A one-pole
  loss filter is designed from two decay times, so brightness behaves the same at every pitch. The tuning
  accounts for every filter in the loop: it stays within 0.1 cent from C2 to C7.
- **`[dcs_glitch~ buffer-ms voices]`** — a polyphonic glitch voice over its own ring buffer:
  - `slice L d0 c1 c2 S place` plays a stutter, a reverse or a replay;
  - `stretch L d0 rate place` plays a time-stretch whose grains line up with each other (WSOLA), so a held
    tone stays smooth;
  - several glitches can sound at once, each starting on its exact sample (as with `vline~`) and placed
    between the ears.

- **`[dcs_derustle~ amount above-dB release-ms]`** — squashes sudden bursts that jump far above a signal's own
  quiet floor and leaves the floor alone (made for cloth rustle on a pocketed phone's mic). Outputs the processed
  signal and the gain it applied, so other signals can be squashed alike.

- **`[dcs_voice~]`** — one part of a kit: a small polyphonic instrument (engines: plucked string, bowed string,
  modal bell / marimba / bowl, analog: detuned saws and a sub through a resonant ladder filter), configured by messages, playing one-shot notes or held "slot" notes that
  crossfade when they move.
- Also: `dcs_pitch~` (YIN pitch tracker), `dcs_shift~` (PSOLA pitch shifter that keeps a voice's tone colour),
  `dcs_onset~` (spectral-flux onset detector), `dcs_reverb~` (Freeverb-style stereo reverb in one object).

Each object's source file starts with a full description of what it does.

## Building

- Desktop (Linux): `make` builds `build/dcs.pd_linux`. Put `build/` on Pd's search path. `PD_SRC` points at
  Pd's `src` folder (for `m_pd.h`).
- Android: `tools/build_dcs_android.sh` (in the PdScenes repo) builds `libdcs.so` for each ABI. It links against
  pd-for-android's `libpd.so`; Pd on Android finds `lib<name>.so` in the app's native library folder.

Tests: `tools/test_dcs.py` in the PdScenes repo checks tuning, decay, stability, sample-exact starts, each
glitch kind, voice stealing and the stretch.
