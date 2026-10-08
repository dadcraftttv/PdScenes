# PdScenes (stage 1)

Mic -> Pure Data (libpd) -> headphones, low latency (libpd's Oboe backend), in a foreground
service so it keeps running with the screen off. The test patch (`app/src/main/assets/patches/test_scene.pd`)
has an echo with feedback and a ring modulator; the five sliders send values into it by receiver name
(`echo_time`, `feedback`, `wet`, `ring_freq`, `ring_mix`). That Java -> Pd path is what sensor
input will use in stage 4.

## Build and run
1. Install Android Studio (current stable). Open this folder. Let it sync (it fetches
   `io.github.libpd.android:pd-core` 1.4.2-SNAPSHOT from the Sonatype snapshot repository, declared in settings.gradle.kts; a prebuilt AAR, no NDK needed. The last numbered release, 1.2.1-rc6, cannot pick audio devices. Move to the next numbered release once one ships).
2. On the phone: Settings > About phone > tap Build number 7 times, then Developer options > USB debugging.
3. Plug in the phone, pick it in the device dropdown, press Run.
4. Plug in headphones FIRST, press Start, grant the microphone permission.

Command line: `./gradlew assembleDebug` (needs ANDROID_HOME set), APK at `app/build/outputs/apk/debug/`.

## Parameters, presets, randomize (step 1)
- `Params.java` is the one list of parameters (id = Pd receiver name, range, curve, safe range for randomize).
  To add one: add a line there and a matching `[r id]` in the patch. The screen builds itself from that list.
- Presets: built-ins plus your own, saved as small JSON files in the app's storage. Export/Import use the
  system file picker, so you can keep a library anywhere (Downloads, Drive, a PC). Input gain is deliberately
  not stored in presets because it depends on the phone and mic, not the sound.
- Randomize picks values inside each parameter's safe range; Lock stops a parameter changing; Nudge moves
  things slightly; Undo steps back (20 levels). The last-used settings and locks are restored on launch.

## Controls added in step 2
- **Echo enabled / Ring mod enabled** switches bypass an effect without clicks.
- **Dry level** sets the direct (pre-echo) sound separately from the echo level.
- **Smoothing** sets how long every control takes to glide to a new value (echo time glides 3x slower).
- **Nudge strength** sets how far Nudge moves each slider. It is an app setting, not part of the sound.
Smoothing, nudge strength and input gain are saved with your last-used settings but not inside presets.

## Pitch shifter (step 3a)
- **Pitch shift amount** (-12 to +12 semitones) and **Pitch shift mix** (0 = original only, 1 = shifted only,
  0.5 = both together, i.e. a harmony). **Pitch grain size** trades smoothness (long) against low
  delay (short); very short grains can sound grainy or phasey on steady tones. A switch bypasses it.
- It sits before the echo, so the echoes repeat the shifted voice too. The shifted sound lags the
  direct sound by roughly half the grain size plus 4 ms.
- New built-in presets: Chipmunk, Demon, Harmony, Octave-down echoes.

## Scenes (stage 2)
- **Import zip** takes a zipped `.rj` folder (`.zip`/`.rjz`, or a zip of the scene's files) and unpacks it
  to the app's private `scenes/` folder. The scene is found by its `_main.pd`; its name and author come from
  `Info.plist` when present. Re-importing a scene of the same name replaces it.
- **Import folder** (system folder picker) copies one scene folder, or every scene inside a folder of scenes such as `rjdj_scenes`.
- **Choose scene** picks Built-in effects or an imported scene (long-press an entry to delete it). Choosing
  while audio is running restarts the engine on the new scene. While a scene is selected the built-in effect
  controls are hidden, since the scene replaces that chain.
- The app provides its own `soundinput` (mic on two outlets, DC removed) and `soundoutput` (two inlets,
  clipped to +-1) in `scenes/pd/`, which scenes reach through their `declare -path ../pd`. They are written
  fresh for this app. The rjlib abstractions are bundled in `scene_lib/rj/` and put on Pd's search path, so a scene
  can leave out its own `rj/` folder or bring just the files that differ.
- **Player helpers.** `closebang`, `rj_time`, `rj_compass`, `rj_loc`, `rj_text` and `rjdj` (from PdParty, BSD) are in `scene_lib/` so scenes that expect
  the player to supply them load. The app answers `rj_time` requests (`SceneEvents`), sends `#closebang` when a scene closes, and streams the compass;
  `rj_loc` stays quiet (no location permission) and `rj_text`/`rj_image` are accepted but not drawn yet.
- **Built-in scenes.** The four official RjDj example scenes (`assets/builtin_scenes/`, GPLv3, from `rjdj/rjlib`
  `examplescenes/`) are copied into the scenes folder on first start. A deleted one stays deleted until *Reset
  everything*. `tools/test_bundled_scenes.py` opens each one on desktop libpd. The shared `s_fplaytable.pd` has a
  small fix: current Pd's `[list split]` sends its right outlet first, so the play message arrived before `set`,
  and `set` then stopped tabplay~, which left sample-playing scenes (Onset Detection) silent.
- RjDj's analysis externals `rj_senergy~`, `rj_accum`, `rj_centroid~` and `rj_barkflux_accum~` were C code. They
  are re-written here as plain Pd abstractions (in `scene_lib/`, with a helper `rj_accum_mean`) so no native
  code is needed, and checked against the C originals sample by sample. `rj_zcr~` is not ported (no known scene uses it).
- Not yet: location (`#loc`), `rj_image`/`rj_text` and other on-screen widgets, Gem
  graphics, and the player side of scene state saving.
- Tests: `python3 tools/test_scene_loader.py <libpd.so>` and `python3 tools/test_rj_analysis.py <libpd.so>`.

### RjDj timing (22 kHz)
- RjDj ran scenes at 22050 Hz, and many scenes hard-code sample counts (loop lengths, delays, filter times).
  With a scene selected, an **RjDj timing (22 kHz)** checkbox (on by default) starts the engine at 22050 Hz so those
  come out as their authors heard them; Android resamples to the hardware. Turn it off to run at the phone's own
  rate (lower latency, full bandwidth). The built-in effects always use the phone's rate. The log line
  `Audio started, asked for ... got ...` shows the rate Pd really ran at.

### Volume and mic volume
- Under the touch pad, **Volume** and **Mic volume** sliders (remembered between runs). They are sent to the scene the
  way RjDj's player did: `#transport play 1`, `#volume set v` and `#micvolume v` (0 to 1). The bundled
  `soundoutput` scales the output by the volume (and mutes on `play 0`); `soundinput` scales the mic. Output is
  limited to +-1 before the volume is applied, like the original, so very hot scenes still clip.

### Motion and touch (stage 3)
- **Accelerometer**: while a scene runs, the phone's accelerometer (about 50 readings a second, also with the
  screen off) is sent to the scene's `#accelerate` receiver as a list `x y z` in g. Android's sign is the
  opposite of iOS (face-up reads z = +1 here, -1 on an iPhone), so values are negated and scaled to match what
  scenes were written for. A shake detector set to 2.3 g behaves as it did on the iPhone.
- **Gyroscope, magnetometer, compass** (the receivers PdParty-style scenes use; RjDj's own scenes don't): `#gyro x y z`
  in rad/s, `#magnet x y z` in microtesla, and `#compass degrees` (the direction the top edge points, clockwise
  from magnetic north; best with the phone flat). Axes match iOS, so no conversion. A phone without one of these
  sensors just doesn't send it.
- **Touch**: a touch pad under the scene name shows (with rounded corners) the scene's `image.jpg` (or `.png`, `thumb.jpg`). Fingers
  are reported to `#touch` as `down`/`xy`/`up` plus finger number (1, 2, ...) and x y on a 320 x 320 grid laid
  over the image. The app is locked to portrait, which is what scenes assume.
- **Helpers**: the app bundles RjDj's own library (`rjlib`, GPLv3) so scenes find what they expect:
  the whole `rj/` abstraction library (added to Pd's search path both as `rj/name` and by bare name; a scene's
  own copy always wins), plus the legacy helpers `accelerate` (broadcasts `magnitude`, `pitch`, `roll`, `x`,
  `y`, `z`, `status` on the receiver `accelerate`), `touch`, `rjdispatch`, `rjloader`, `reverb`, `sssad`,
  `analysepitch`, `analysesimpleonset`, `rjXYZshake`, `rj_fft` and `rjsave-ex`. `hilbert~`, `rev1~`..`rev3~` and
  `complex-mod~` are Pd's own BSD-licensed extras. `soundinput` and `soundoutput` were written for this app.
- **Externals**: Pd's optional externals (`fiddle~`, `bonk~`, `sigmund~`, ...) ship as separate native
  libraries. The app adds its native library folder to Pd's search path and packages the libraries unpacked
  (`useLegacyPackaging` in `app/build.gradle.kts`) so scenes that use them can load.
- Test: `python3 tools/test_scene_sensors.py <libpd.so> [scene folder]`. With a real scene folder it shakes the
  scene and checks that it starts making sound. Of 50 scenes checked headlessly, 33 now load with nothing missing.

## Layout and themes
- Controls are grouped into collapsible sections (Input & output, Echo, Ring modulator, Pitch shifter,
  Bit crusher, Distortion, Filter, Chorus, Flanger, Phaser, Tremolo, Reverse echo, Glitch / freeze, Reverb, Spatial, Behavior, Audio devices, Appearance). Tap a header to fold or unfold it; the app remembers which are open.
  Sections come from `Params.SECTIONS`; each parameter names its section in `Params.ALL`.
- Bit crusher: sample-rate reduction (sample & hold) plus bit-depth reduction, after the pitch shifter and
  before the echo. Amount 0 is clean; the rate and depth sliders only matter once the amount is raised.
- Output limiter: the built-in patch ends in a soft limiter (transparent up to 0.7, then a smooth curve that
  never passes 1.0) instead of a hard clip, so loud peaks round off rather than fuzz.
- Distortion: soft clip (x / (1 + |x|)), hard clip, or wavefold, with a drive control, between the bit
  crusher and the filter. Each shape has a small-signal gain of 1, so drive 1 is near clean.
- Filter: one biquad (low-pass, high-pass or band-pass) with frequency and resonance, after the bit crusher.
  The coefficients are computed in the patch with [expr] (audio-EQ-cookbook formulas); frequency changes glide
  in the log domain so big jumps do not pop. Switching the type live can click once.
- Chorus: the signal crossfaded with two copies delayed by about 15 and 21 ms, with the delays swept by a
  slow LFO (speed and depth adjustable), which detunes the copies slightly. Amount 0 is clean.
- Flanger: a short delay (2 ms up to 2 ms + depth) swept by a slow LFO and mixed with the dry signal, with
  bipolar feedback (negative gives a hollower sound). Mix 1 is 50/50, which gives the deepest notches.
- Phaser: four all-pass stages whose centre frequency sweeps around 700 Hz (up to two octaves each way),
  mixed 50/50 with the dry signal, with feedback. The all-pass coefficients are computed in the patch.
  Both sit after the chorus; the tremolo comes after them.
- Tremolo: the level swings between full and (1 - depth) at the LFO speed. Depth 0 is off. It comes after the
  chorus and before the echo, so the echoes pulse too.
- Reverse echo: the sound played backwards in chunks (100-1000 ms) behind the original. It is the pitch
  shifter's two-tap crossfading delay line run at playback speed -1.
- Glitch / freeze: a feedback loop of 20-500 ms. Freeze 1 replaces the input with the loop's own output, so
  the last stretch of sound repeats until freeze comes back down; in between it is a short feedback echo.
  Movers on Freeze give stutters ("Louder = higher" freezes the room when something loud happens).
- Reverb: a stereo Freeverb-style design (8 combs + 4 allpasses per side, delay times in ms) fed from the
  mix after the echo. Level 0 is off. Room size and brightness (damping) are adjustable; the input level
  follows the size so loudness stays similar.
- Spatial: a balance-style pan and an "ear delay" (a few ms of time difference between the ears: small
  values move the sound left/right, 10-25 ms widen it). It is the last stage before the output, so the echo
  is moved too. The neutral setting adds a fixed 1.5 ms of latency (a short Pd delay cannot go lower).
- Input conditioning (Input & output section, not part of presets): a noise gate (closes under a dB
  threshold; -80 is off) and a compressor (threshold, ratio, make-up gain; threshold 0 is off; the defaults are Input gain 2.5 with the compressor at -30 dB, 4:1, so quiet detail is lifted and loud peaks are held back). Both read the
  mic level from [env~] in the patch, before the effects.
- **Movers**: every slider in a section has its own mover, in a "Movement" dropdown under it. It slowly pushes
  that slider up and down around its position (within the slider's safe random range), with its own speed and
  depth; speed and depth only show once a movement is chosen. Each section has one "Movers" switch: off, the
  section's movers are grayed out and do nothing (the slider values come back); on, they all run. Movers live in
  `Modulation.java`, update about 30 times a second from the service, and are saved in presets (presets without
  movers switch them off). Settings are `<slider>_mv` (movement), `<slider>_mvspeed`, `<slider>_mvdepth` and
  `<section>_movers`. Any slider that is a plain Pd-driven slider gets a mover automatically (`Params.movable`).
  Presets and saved state from the old three shared movers are converted on load (`Params.upgradeLegacyMovers`).
- Movements: **Smooth wave**, **Random drift** and **Random jump** run on a clock. Random jump holds a position, then hops straight to a new random one (at least a quarter of the slider travel away), as many times a second as Speed says. **Louder = higher / lower** follow the loudness of
  the room (the patch reports it about 30 times a second as `mic_level`, dB with 100 = full scale; the app maps
  -60..-15 dB to 0..1; raise the input gain if nothing moves). The rest follow the phone: **Upright = higher**
  (flat on a table is lowest, standing on its end highest), **Lean right = higher** (45 degrees is full scale),
  **Shake = higher** (jolts push it up, then it fades over about 0.4 s), **Spin = higher** (gyroscope; 6 rad/s is
  full scale), **Facing south = higher** (compass; north lowest, east and west in the middle) **Pad X / Pad Y**, and three from the environment sensors: **Brighter = higher** (light sensor, log scale), **In pocket = higher** (proximity sensor plus a dim light) and **Climbing = higher** (barometer: stairs, lifts, hills).
  For these the speed sets how quickly the slider follows. Append new movements to `Params.MOVER_SHAPES` only.
  The sensors run whenever audio runs, also with the screen off; with the built-in effects they only drive movers.
- **Auto worlds** (built-in effects only): a "Worlds (automatic)" section at the top of the effects. Switched on, the app
  watches the room and the phone (`WorldSelector`): midnight to 5 AM is **Ghost**, walking is **Kinetic**, a phone in a pocket is **Pocket**, a loud
  room is **Flux**, a quiet room is **Tranquil** (in that priority order). When a situation has lasted about 5 seconds
  (and the previous world has played 10), `Worlds` fades the sliders to that world's preset over 3 seconds; when nothing
  applies, the user's own settings fade back, and stopping the engine hands them back at once. Each world's preset is a
  dropdown (any built-in or saved preset, or Off), locked sliders are left alone, and the four default presets
  ("Tranquil world", "Flux world", "Kinetic world", "Ghost world", "Pocket world") also work by hand. Loudness is averaged over about
  3 s; the thresholds (`WorldSelector.LOUD_*`, `QUIET_*`, in the mic-level dB units) are first guesses to tune on
  real phones. Walking comes from `StepDetector`, which counts foot-strike bumps in the accelerometer (4 or more steps
  in 3 s); the accelerometer therefore always runs at the fast rate. Original worlds inspired by the idea of context-driven
  music; no RjDj Dimensions assets are used.
- **Walking beat** (built-in effects only): "Walking beat" section. `StepDetector` hears each footstep and sends `step <seconds
  since the last one>` to the patch, which plays a drum for every step: kick on even steps, snare on odd ones, and a hi-hat
  half a step later (so a faster walk gives a faster beat, and standing still is silent). Sliders: level (0 = off), hi-hat
  level, snare level and kick pitch. The drums are synthesized in the patch (`add_beat` in `tools/make_patch.py`), join the
  mix before the reverb and pan. The first two steps of a walk are held back so fiddling with the phone doesn't play drums, and the accelerometer is read 200 times a second so the drums land on the step. The "Kinetic world" preset turns the beat on. Scenes do not get `step` messages.
- **Music** (built-in effects only): "Music" section, off until switched on. `add_music` in `tools/make_patch.py` builds a
  reactive synth that only plays notes of the chosen Key and Scale (C major by default; 8 scales). A degree-to-pitch
  chain reads the scale from a table, so every note is in key. It listens to the mic: loudness above the room's own quiet (the
  level meter the "Louder" movers use, measured against the quietest level lately, which it forgets slowly) sets how busy and loud it is: a quiet room plays
  no chimes at all and a lively one plays plenty; "how much it follows" at 0 gives a steady, sparse pattern instead, brightness (the zero-crossing rate, as a pitch) sets the chords and
  the register, and a sudden jump above the recent average rings a chime. Three voices: a soft **pad** (four sine pairs,
  a new chord every 7 s, glides of 3.5 s, breathing slowly), **chimes** (four bell-like voices taken in turn; a slow
  random pattern while you are still, busier in a livelier room), and a **footstep arpeggio** around the current chord
  that is soft at a stroll and swells to full at about 2.6 steps a second. The music joins the signal after the filter,
  so the pitch shifter, ring mod, crusher, distortion and filter cannot push it out of key, but chorus, flanger, phaser,
  tremolo, reverse echo, glitch, echo, reverb and the spatial stage all shape it. It follows the Dry level like the rest of
  the chain. Key, scale and the on/off switch are not part of presets; Auto worlds never touch the switch (Tranquil plays it
  low, Kinetic starts soft and swells with pace).
- **Reset everything to defaults**: a button under Randomize / Nudge / Undo with a confirmation. It puts every parameter,
  mover, lock and switch back to the fresh-install value, turns Auto worlds off, sets both audio devices to Automatic,
  returns scene volume settings and the built-in effects selection to their defaults, and rebuilds the screen. Saved
  presets, imported scenes and the appearance are kept. Nothing else ever resets settings on its own.
- **XY pad**: with no scene selected, the touch pad under the scene buttons is an XY controller. Give a slider the
  movement Pad X (right = higher) or Pad Y (up = higher), then drag in the pad; it holds the last position when you
  let go. The first finger counts; scenes still get all fingers.
- Audio devices has Input and Output dropdowns (Automatic by default; needs pd-core 1.4.x, otherwise they are disabled). Output is headphones only: the list offers wired, USB and Bluetooth devices, never the phone speaker, and the app refuses to start without headphones. If the active headphones are unplugged it switches to other headphones or stops. The choice is remembered by device
  type and address; if the device is unplugged the app uses Automatic until it returns. Changing a device while
  running restarts the audio. A Bluetooth headset chosen as input uses call mode (mono, low quality) unless it is an LE Audio headset, and sound then plays to that same headset. A hint under the dropdowns recommends the phone's mic in the call-mode case.
- Appearance offers Material Light, Material Dark (default) and AMOLED Black (true black). The choice is
  remembered (`UiSettings`). The three looks are in `res/values/styles.xml`.
- Known quirk: Android draws its launch window from the manifest theme (dark), so choosing Light can show a
  brief dark flash while the app starts.

## Code notes
- All fixed UI text lives in `res/values/strings.xml` (parameter names live in `Params.java`).
- The screen updates on events (engine start/stop/error via `AudioService.StateListener`, headphones via
  an `AudioDeviceCallback`) rather than a polling timer.
- `docs/RJDJ-NOTES.md` records the RjDj scene format, what a player must provide, and licensing.

## Developer tools (tools/)
- `make_patch.py` generates `test_scene.pd` from named nodes (so effects can be added without
  hand-numbering Pd objects). Edit it, run it, commit the regenerated patch.
- `test_patch.py` runs the real patch through a desktop libpd build and checks echo timing,
  bypass, dry level, ring-mod frequencies, click-free toggling, smoothing time, stability at maximum
  settings, and that `Params.java` and the patch agree. Build libpd with `make` in libpd's source
  folder, then: `python3 tools/test_patch.py path/to/libpd.so` (needs numpy).

## Compatibility
- minSdk 28 (Android 9): pd-core's Oboe build requires it. targetSdk/compileSdk 36 (Android 16).
- Release builds for other people: sign the APK/AAB; for Play Store, check the libpd `.so` files for
  16 KB page-size alignment (required for new apps targeting Android 15+).

## Status
Stage 1 audio loop: built and tested on a Moto G Stylus 2025 (Android 16).
Step 1 (registry/presets/randomize): built and running on the phone.
Step 2 (bypass, dry, smoothing, nudge strength): built and running on the phone.
Step 3a (pitch shifter): verified on desktop libpd (tools/test_patch.py); on-phone result not yet confirmed.

## Known limitations / next
- Mic input uses Oboe's default input preset (phone may apply noise suppression/AGC). Stage 1.5: try an unprocessed/voice-recognition preset.
- No audio-focus or route-change handling yet (phone call, headphones unplugged mid-run).
- Bluetooth headphones add noticeable latency; wired or USB-C is best.

## Licence
GPLv3 or later (see `LICENSE`); third-party components and their licences are listed in `NOTICE.md` and shown in
the app under *About and licenses*. To publish, set `source_url` in `app/src/main/res/values/strings.xml` to the
public repository so the About screen links to the source, and link it from the store listing too.


## Sensors

The app reads the accelerometer, gyroscope, magnetometer, the fused rotation vector (compass), light, proximity and barometer.
`PhoneContext` turns light, proximity and pressure into brightness (0 to 1, log scale), pocket (proximity near for a second and
lux under 10, or no light sensor) and climb (-1 to +1 from the gap between a fast and a slow average of air pressure).
The compass comes from the rotation vector when the phone has one (steady, and held upright it gives the way the back of the
phone faces); otherwise the old gravity-plus-magnetometer method is used. Scenes also get `#light lux`, `#proximity 0|1`,
`#pocket 0|1` and `#pressure hPa` (extras beyond RjDj). The **Pocket** auto world (below Kinetic, above Flux) keeps the room soft
when the mic only hears cloth. Not used on purpose: hardware step counter (needs the activity-recognition permission; our
detector works), GPS (location permission), weather (internet).
