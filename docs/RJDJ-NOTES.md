# RjDj format and licensing notes (for stage 2: the scene loader)

Researched from the public repos `rjdj/rjlib` (Reality Jockey's own library) and `danomatika/PdParty`
(open-source iOS player with RjDj compatibility). Nothing here has been run on Android yet.

## What a scene is
A folder ending in `.rj` (often distributed zipped) containing:
- `_main.pd`    the scene's main Pd patch (required)
- `Info.plist`  XML plist; `info` dict with `name`, `author`, `description`, optionally `category`
- `image.jpg`   background/cover image (PdParty also accepts `thumb.jpg`)
- audio samples (`*.wav`), and usually its own copy of the `rj/` abstraction library
Scenes begin with `#X declare -path .; -path rj; -path ../pd; -path ../../pd`, so they find `rj/`
inside themselves and player-provided abstractions one or two folders up.

## What the player must provide
- Abstractions `soundinput` and `soundoutput` (the mic in / speaker out, volume, DC filter, clipping).
  Reference versions: PdParty `res/patches/lib/pd/` and rjlib `pd/`.
- Sensor/event receivers (sent into Pd by name): `#accelerate`, `#touch`, `#gyro`, `#compass`, `#loc`,
  `#time`, `#magnet`, `#transport`, `#volume`, `#micvolume`, `#closebang`.
- Optional: `rj_image` / `rj_text` (on-screen image and text from the scene), `rj_compass`, `rj_loc`, `rj_time`.
- Sample rate: RjDj scenes assume 22050 Hz (PdParty `RJ_SAMPLERATE`); check before relying on timing.
- iPhone-only assumptions: portrait orientation, accelerometer axes. These need mapping on Android.

## Licensing (this affects what we may bundle)
- `rjlib/rj/` abstraction library and the four example scenes are copyright Reality Jockey Ltd.,
  released under **GPL v3** ("can be distributed freely"), with some files under Standard Improved BSD
  (ADSR, vocoder; see file headers). Source: `rjlib/rj/LICENSE.txt`.
- PdParty is **Standard Improved BSD** (permissive; keep the copyright notice if code is adapted).
- libpd/pd-for-android: BSD-style. Oboe: Apache 2.0. GPLv3 is compatible with both.
- Consequence: bundling rjlib code in the app means distributing the app under GPLv3 (source available).
  Fine for personal use, and fine for sharing if the app is open-sourced. Scenes that bring their own
  `rj/` folder do not require us to bundle rjlib at all.
- Third-party scenes (Eargasm, Inception, etc.) have unverified licences. Do not bundle them in the app
  or in project zips; let the user import scenes they have obtained themselves.

## rjlib contents worth knowing (all GPLv3 unless noted)
~180 abstractions by prefix: `e_` effects (36: chorus, phaser, pitchshift, platereverb, bitcrusher,
tremolo, freqshift, pingpong, stereowidener, vocoder, compressors, ...), `c_` control (24: adsr, drunk,
random, busses), `u_` utilities (45), `s_` synth/sample (28), `m_` music (22), `g_` generators (16),
`a_` analysis (onset, breath), `r_` (6). Good source of ideas and a reference for modulation sources.

## Analysis externals (ported to Pd)
`rj_senergy~` (mean square of the first 513 samples of a block), `rj_centroid~` (spectral centroid of a 513-bin
magnitude spectrum), `rj_accum [hop]` (short-term vs long-term mean, default 5 s / 30 s, `st`/`lt` messages) and
`rj_barkflux_accum~` (12 Bark bands from 40 Hz to 8 kHz, same two averaging times) are small C externals in
rjlib/src. They are re-implemented as abstractions in `scene_lib/`, keeping the originals' quirks (513-sample
window, the band-to-bin mapping, `cnt` stopping one short of the buffer size). To re-verify against the C: compile each
`.c` with `gcc -shared -fPIC -I<libpd>/pure-data/src` into `name.pd_linux` (open libpd with `RTLD_GLOBAL`), put that
folder on the search path and compare outputs. Pd notes learned on the way: message boxes do not expand `$0` (use
`[s \$0-name]`), `expr` treats `1960/8000` as integer division, `[array sum]` takes the onset in its left inlet
and the count in its right one, and Pd 0.54+ `[inlet~]` has a second outlet forwarding control messages sent to the
signal inlet (that is how `rj_barkflux_accum~` receives `st`/`lt`).
