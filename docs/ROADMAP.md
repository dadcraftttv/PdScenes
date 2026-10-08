# Roadmap: ideas to work into the app

Gathered from research (Designing Sound "RjDj: crafting Dimensions", CDM's Dimensions write-up, the 99% Invisible
episode). The sources give ideas, not thresholds or timings; tune everything by ear on the phone. Samuel decides the order.
Suggested order is the numbering. Each one needs a test in `tools/test_patch.py` (or a new test file) and a tester-guide update.

1. **(BUILT 2026-10-08 as "Room notes", `music_res`; needs tuning by ear) The room plays the notes (Dimensions "Flux").** Run the mic through resonators/filterbank tuned to the chosen
   key and scale; filter frequencies move with pitch changes and onsets, so sounds around you ring notes in key.
   Likely a new voice in the Music section (level slider + on/off) or part of the Flux world. Joins the output after
   the filter like the other music voices, so echo/reverb/spatial shape it.
2. **Pitch-following harmony (Dimensions "Travelling Dream", RjDj "Eargasm").** Track the pitch of what the mic hears
   (rjlib `analysepitch` / the fiddle external, already in `scene_lib` and the native libs) and answer with in-key notes or
   harmony. Needs a confidence gate so noise does not produce random notes.
3. **Ghost: capture and stretch.** On a detected onset, record the moment and replay it granularly stretched in time,
   with reverse reverb; optionally a very short randomized mic delay for atonal pitched noise. Extends the Ghost world
   (which today only has reverse echo).
4. **Kinetic pattern tiers.** Dimensions switches among five patterns by accelerometer level, with random variation. Ours
   has one walking arpeggio pattern; add pace tiers and variation. Stopping must still drop the drums immediately.
5. **Unstable world.** Jolt-triggered stack of many ordinary effects on the mic at once (glitch, pitch shift, ring mod,
   crush, delay), glitchy by design. We have all the effects; it needs a trigger and a preset.
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
