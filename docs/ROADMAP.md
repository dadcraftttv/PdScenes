# Roadmap: ideas to work into the app

Gathered from research (Designing Sound "RjDj: crafting Dimensions", CDM's Dimensions write-up, the 99% Invisible
episode). The sources give ideas, not thresholds or timings; tune everything by ear on the phone. Samuel decides the order.
Suggested order is the numbering. Each one needs a test in `tools/test_patch.py` (or a new test file) and a tester-guide update.

1. **(BUILT 2026-10-08 as "Room notes", `music_res`; needs tuning by ear) The room plays the notes (Dimensions "Flux").** Run the mic through resonators/filterbank tuned to the chosen
   key and scale; filter frequencies move with pitch changes and onsets, so sounds around you ring notes in key.
   Likely a new voice in the Music section (level slider + on/off) or part of the Flux world. Joins the output after
   the filter like the other music voices, so echo/reverb/spatial shape it.
2. **(BUILT 2026-10-09 as the Harmony slider) Pitch-following harmony (Dimensions "Travelling Dream", RjDj "Eargasm").** Track the pitch of what the mic hears
   (rjlib `analysepitch` / the fiddle external, already in `scene_lib` and the native libs) and answer with in-key notes or
   harmony. Needs a confidence gate so noise does not produce random notes.
3. **Ghost: capture and stretch.** On a detected onset, record the moment and replay it granularly stretched in time,
   with reverse reverb; optionally a very short randomized mic delay for atonal pitched noise. Extends the Ghost world
   (which today only has reverse echo).
4. **(BUILT 2026-10-09 with step strength and the cadence groove) Kinetic pattern tiers.** Dimensions switches among five patterns by accelerometer level, with random variation. Ours
   now has five 8-step patterns picked at random each bar, with rests (2026-10-08); still to do: tie the pattern to pace tiers. Stopping must still drop the drums immediately.
5. **Unstable world.** Jolt-triggered stack of many ordinary effects on the mic at once (glitch, pitch shift, ring mod,
   crush, delay), glitchy by design. We have all the effects; it needs a trigger and a preset.
5b. **Samuel's idea (Oct 9): "glitch cloud" — Ableton warp + the Glitch VST (v1.3).** Random bits of what the mic hears
   are grabbed into a RAM-only ring buffer (never to disk) and played back around the listener: extreme time-stretch
   (granular, like Ableton's warp pushed very far), tape stop (playback rate falling to 0), stutter/retrigger (a
   slice repeated at step-synced divisions, getting shorter), reverse slices, pitch drops, scattered across the
   stereo field so "the stuttering glitched sound echoes all around". Could tie to steps (stutters on the beat) and to
   jolts (Unstable world, item 5) and share code with Ghost capture (3) and the Collective scratch (6). Today's
   `glitch_hold`/`glitch_len` freeze is the only piece that exists.
6. **Collective world.** Capture a buffer and "scratch" it back and forth like a turntablist. A new scratch effect.
7. **Optional: "calm builds" mode.** Dimensions' Tranquil adds layers the longer you stay quiet and lets noise make the music
   shrink away. Opposite of the current behavior (quiet room = quiet notes), so only as an option, if Samuel wants it.
8. **Density memory.** Generative rule sets that look at how dense the recent music has been and adapt (avoids too many
   notes in a row).
9. **Stems player (hybrid approach).** Dimensions used stems made in a DAW, layered and faded by sensor data; all-Pd
   synthesis was too heavy. Samuel makes synthwave stems, so the app could play his loops. Plan: ship compressed audio,
   decode once with MediaExtractor/MediaCodec into WAV in the app's cache, stream with `readsf~` (from disk, not RAM).
   Needs a size budget for the APK/AAB and a layering/fade rule set.
10. **Skipped: weather and GPS contexts** ("Sunny" world). The app has no internet permission by design.
11. **Other small items:** location (`#loc`) scene input, unported scene objects, on-screen route/clipping diagnostics,
    beat-offset slider if drift returns, music independent of the Dry level, `rj_zcr~` port if a scene needs it,
    check other rjlib abstractions for the same `[list split]` output-order problem fixed in `s_fplaytable`.

12. **Music ideas from Samuel's Oct 8 test notes** (after the bass pad, built 2026-10-08 as "Pad register"):
    - (BUILT 2026-10-09) Lock chimes to the walking pulse: while walking, onset chimes wait for the next step or half-step.
    - Motif memory: remember a short phrase of recent chime notes and bring it back later with variation.
    - Slow key-centre drift every few minutes (keeps the chosen key's notes, moves the home chord).
    - Register from sensors: brighter = higher octave, dark/pocket = lower and warmer; climbing raises notes;
      compass heading picks the bass root.
    - Call-and-response: answer a clearly pitched sound a beat later with a harmony note (= item 2).
13. **Pocket rustle, other options** (mic-down protection was built 2026-10-08): footstep-synchronised ducking (the step is
    detected after the strike, and walking rustle is continuous, so likely weak alone) and a rustle detector (spectral
    flatness / zero crossings) that tightens a high-pass only while the sound looks like cloth.

14. **Outside reviews (Gemini and Grok, 2026-10-09), checked against the code.** Accepted, not built yet:
    - *Hardening pass* (BUILT 2026-10-09, needs a phone check of call pause and ducking): audio focus (other audio -> duck the app only slightly so its
      effects still come through; a phone call -> always pause/stop), event log on a background thread with one date
      format, `PhoneContext.inPocket()` under the lock, no per-event `float[3]` in `SensorInput.toScene`, no per-tick
      HashMap in `Modulation.tick`, Bluetooth-mic wait (up to ~3.3 s of `Thread.sleep`) off the main thread, copy
      `patches`/`scene_lib` assets only when a version stamp changes (393 files on every Start today), a step-detector
      test for shaking the phone while sitting.
    - *CPU* (BUILT 2026-10-09: switch~ groups; accel 100 Hz still to try): measured on the phone (built-in patch, music on): ~50% of one core, the audio thread ~44% (desktop 2.4%).
      Effects at 0 or off cost the same as on. Wrap effects and music voices in `switch~` subpatches (reverb and pitch
      shifter first) via a helper in make_patch.py, with tests that an off effect is unchanged and toggling doesn't click.
      Try the accelerometer at 100 Hz instead of 200 Hz if the beat still lands.
    - *UI* (BUILT 2026-10-09: why-line, pinned bar, folded sections, hold, snapshot): a "why this world" status line (`Worlds.hearing()`), Start/Stop and status pinned (sticky), effect sections
      collapsed by default, a mover indicator on moving sliders, a "hold this world" control, a one-tap snapshot preset
      (time-stamped, name later), an optional quiet earcon on world change, SeekBar content descriptions, the Bluetooth
      hint on the input picker, a short first-run flow, later a simple "walk mode" screen.
    - *Sound* (BUILT 2026-10-09: step-synced echo, stop breath, dice morph): echo time synced to steps, dice morph (Randomize glides over 5-10 s), shake-to-scatter while still
      (overlaps item 5), cadence groove reward, an Intensity macro, step strength (harder step opens the hat), a
      2-3 s thin-out of pad and chimes when you stop, a wind/handling detector that ducks only the reactive voices
      (overlaps item 13).
    - *Release*: R8 keep rules for the `PdAudio.setDevicesId` and `audioRuntimeInfo` reflection when minify is on,
      a real notification icon, Data safety form (mic used on-device, not collected), mention `events.log` in the privacy policy.
    - Rejected: pocket hush before the compressor (the compressor would undo it), head tracking from the phone's
      rotation (the phone isn't on the head), GPS/weather. Already done: low cut in a pocket (mic-down protection),
      16 KB page alignment (all 64-bit .so files are 0x4000), world hysteresis test.
    - Not now (Samuel): anything that records audio ("sound capsule", "remember this minute"). Only if it would unlock a
      lot; he isn't ready to make that concession.

Release prep (separate list): final name + applicationId (not "RjDj"), `source_url`, privacy policy, Play foreground-service
and microphone declarations, icon, store listing, numbered pd-core release.

## Compatibility and scene findings (PdParty, rjlib PDF, composer pack)

- **Real scenes for testing.** `danomatika/PdParty` ships RjDj scenes in `res/patches/samples/rjdj/` (ApolloVoice, Atsuke, Boomerang,
  CanOfBeats, Eargasm, bouncy) and `res/patches/tests/rjdj/` (Sensors, Widgets, NoBackground). On desktop libpd with only our
  `scene_lib` all of them open without "couldn't create" errors; all but ApolloVoice (needs a touch) and the test scenes (need
  sensors/touch) make sound from a test input. Eargasm prints `no such object` for a few unconnected `[s]` names (compress,
  inputvolume, notechan1-4): harmless sends with no receiver. Samuel can import them himself on his own phone with Import folder
  (point it at the `samples/rjdj` folder).
- **Licences decide what we may bundle.** Safe (GPLv3 text and "or later" in the patch): **Boomerang** (voice echo, 283 ms, by Luke
  Loeffler and Dan Wilcox), **ApolloVoice** (touch plays Quindar tones, Dan Wilcox) and **Atsuke** (Frank Barknecht, built on the RjDj
  template). No licence given, so do not bundle: Eargasm (Damian Stewart), CanOfBeats (Chris McCormick), bouncy (Georg Bosch).
- **Player-provided wrappers (DONE: ported `closebang`, `rj_time`, `rj_compass`, `rj_loc`, `rj_text`, `rjdj`; still open: draw `rj_text`/`rj_image` on screen, and `rj_loc` needs `#loc`).** PdParty supplies `rj_text`, `rj_time`, `rj_compass`, `rj_loc`, `rjdj` and `closebang`
  (`res/patches/lib/pdparty`, BSD). Scenes that rely on the player to provide them would fail in our app. Port the missing ones
  (rj_time from `#time`, rj_compass from `#compass`, rj_text as a no-op or an on-screen caption, rj_loc once `#loc` exists).
- **Older scene packs may use `index.rdf`** for their name and author instead of `Info.plist` (rjlib PDF). Add a fallback reader.
- **State saving.** rjlib scenes can save and restore parameters (`u_dispatch`, SSSAD, `u_loader`, a send to `RJ_SCENE_SAVE`). Check that
  our copies of `rjsave-ex`, `rjloader` and `sssad` actually persist state in the app, or document that they do not.
- **PdParty also lists `rj_zcr~`** among its externals, but no scene in its samples uses it, so keep skipping it unless one turns up.
- **Sample rate:** the RjDj material says 22050 Hz (`u_samplebank` defaults to it). Our RjDj timing setting already does this.
- **Perspective.** The rjlib PDF says its analysis section was the least finished part and held only basic onset detection. Our
  adaptive noise floor and brightness tracking already go beyond what RjDj shipped.
- **Composer pack cookbook** (`doc/composerpack/cookbook`: accel_tilt, accel_smooth, accel_pitch_roll) is a source of ideas for the Kinetic
  pattern tiers and for tilt-driven movers.
- **PdParty's User Guide** (danomatika.com/code/pdparty/guide) is the reference for exact sensor receiver names, value ranges and
  quirks. Ask Samuel to paste it into the chat so it can be read (tools can only open links he sends).

## Research batch (ChatGPT/Gemini/PDF notes)
Mostly confirmation of the Designing Sound / CDM material. New small ideas:
- Compass trick: sound "behind" the listener gets low-passed (cheap spatial cue, needs `#compass`).
- Granular playback of one captured table, scaled by a control value (proximity-style), for Ghost/Collective.
- More Android sensors worth considering: step counter, rotation vector, proximity, light, barometer.
- Mic conditioning check: high-pass the mic before analysis; duck or gate it before long feedback delays.
- Keep one obvious reactive behavior per layer (the Dimensions lesson).
- Pointers: Pure Data forum thread "Dimensions augmented audio app", the libpd paper, Brinkmann's Making Musical Apps.

## Sensor integration (done, needs on-phone tuning)
Fused compass (rotation vector), light, proximity, barometer; `PhoneContext`; mover shapes Brighter/In pocket/Climbing; Pocket auto world;
scene messages `#light #proximity #pocket #pressure`; sensor list in About. Still to consider: GPS `#loc` (permission), hardware step
counter (permission), significant-motion/activity (Play Services), linear-acceleration/gravity sensors for cleaner motion.
