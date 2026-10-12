# Roadmap: ideas to work into the app

Gathered from research (Designing Sound "RjDj: crafting Dimensions", CDM's Dimensions write-up, the 99% Invisible
episode). The sources give ideas, not thresholds or timings; tune everything by ear on the phone. Samuel decides the order.
Suggested order is the numbering. Each one needs a test in `tools/test_patch.py` (or a new test file) and a tester-guide update.

**Agreed order (Samuel, 2026-10-09):** (1) tester guide catch-up (done Oct 9), (2) glitch engine part 1 (item 5b),
(3) Ghost capture/stretch (3), (4) Unstable world (5), (5) Collective scratch (6), (6) music: density memory, motif
memory, key drift, register from sensors (8, 12), (7) screen polish + accel 100 Hz trial (14), (8) release prep.
The glitch engine must stay cheap: off at Amount 0 (switch~), measured on the phone.
Steps 1-6 done by Oct 10 (Unstable and the scratch were built and then set aside by Samuel), plus the glitch matrix.

**Next order (Samuel, 2026-10-12):** (A) mic input shaping (item 15), (B) tempo clock (item 16, part 1), (C) found-sound
rhythm section (item 16, parts 2-6), (D) tabs and Realms, replacing the old step-7 screen polish (item 17), (E) release prep.
Plan first, agreed with Samuel, then build; test on the phone after every step. None of these are started yet.

1. **(BUILT 2026-10-08 as "Room notes", `music_res`; needs tuning by ear) The room plays the notes (Dimensions "Flux").** Run the mic through resonators/filterbank tuned to the chosen
   key and scale; filter frequencies move with pitch changes and onsets, so sounds around you ring notes in key.
   Likely a new voice in the Music section (level slider + on/off) or part of the Flux world. Joins the output after
   the filter like the other music voices, so echo/reverb/spatial shape it.
2. **(BUILT 2026-10-09 as the Harmony slider) Pitch-following harmony (Dimensions "Travelling Dream", RjDj "Eargasm").** Track the pitch of what the mic hears
   (rjlib `analysepitch` / the fiddle external, already in `scene_lib` and the native libs) and answer with in-key notes or
   harmony. Needs a confidence gate so noise does not produce random notes.
3. **(BUILT 2026-10-09 as the Stretch glitch kind, on in the Ghost world; reverse reverb not done) Ghost: capture and stretch.** On a detected onset, record the moment and replay it granularly stretched in time,
   with reverse reverb; optionally a very short randomized mic delay for atonal pitched noise. Extends the Ghost world
   (which today only has reverse echo).
4. **(BUILT 2026-10-09 with step strength and the cadence groove) Kinetic pattern tiers.** Dimensions switches among five patterns by accelerometer level, with random variation. Ours
   now has five 8-step patterns picked at random each bar, with rests (2026-10-08); still to do: tie the pattern to pace tiers. Stopping must still drop the drums immediately.
5. **(BUILT 2026-10-09: shake the phone, at once, 5 s hold; off by default, Samuel found it adds little) Unstable world.** Jolt-triggered stack of many ordinary effects on the mic at once (glitch, pitch shift, ring mod,
   crush, delay), glitchy by design. We have all the effects; it needs a trigger and a preset.
5b. **(PHASE 1 BUILT 2026-10-09: buffer, stutter/reverse/tape stop/shuffle, sound trigger + free clock + step lock, Amount) Samuel's idea (Oct 9): "glitch cloud" — Ableton warp + the Glitch VST (v1.3).** Random bits of what the mic hears
   are grabbed into a RAM-only ring buffer (never to disk) and played back around the listener: extreme time-stretch
   (granular, like Ableton's warp pushed very far), tape stop (playback rate falling to 0), stutter/retrigger (a
   slice repeated at step-synced divisions, getting shorter), reverse slices, pitch drops, scattered across the
   stereo field so "the stuttering glitched sound echoes all around". Could tie to steps (stutters on the beat) and to
   jolts (Unstable world, item 5) and share code with Ghost capture (3) and the Collective scratch (6). Today's
   `glitch_hold`/`glitch_len` freeze is the only piece that exists.
   Researched Oct 9: dblue Glitch 1.x is a tempo-synced slicer: it cuts the incoming audio into slices and a
   64-step sequencer (or its random mode) applies one of nine effects per slice: retrigger, shuffler, reverser,
   tape stop, stretcher, crusher, gater, delay, modulator (each with its own filter). Glitch2 (illformed, now free)
   adds pitch bend, distortion, ring mod, beat repeat, trance gate, a randomizer and scenes. Plan sketch: footsteps
   are our "host tempo" (standing still: onsets or a slow clock); a RAM ring buffer of ~2-4 s; one reader that can
   jump (shuffle), loop short (retrigger, shrinking), run backwards (reverse), slow to 0 (tape stop) or granulate
   (stretch); per slice a random pick weighted by an Amount slider, effects switchable; crusher, delay, ring mod and
   filters already exist and can join per slice; gater = step-synced chopping; Worlds act like Glitch2 scenes.
   Phase 1: buffer + retrigger/reverse/tape stop/shuffle. Phase 2: stretch, gater, per-slice filter, Unstable world.
   Glitch2 extras worth taking: lanes (several effects on one slice, in series), a Randomizer with a chance per effect,
   Mutate (small variations of the current settings: our nudge), per-effect pan (the "all around you" spread), gater
   volume steps, one-shot vs looping. Not useful on a phone: MIDI scene triggers, a drawn pattern editor.
   Clock without walking (Samuel asked): a free clock (own tempo, or slow and loose), sudden sounds as triggers
   (the room plays the sequencer), random timing by density, phone gestures (twist = tape stop, shake = stutter), and
   later maybe the tempo of music heard nearby. Walking locks it to steps; stopping hands over to the other clocks,
   as the chime queue already does.
   Samuel's pick (Oct 9): sudden sounds as the trigger first, then the free clock (walking still locks to steps).
6. **(Built 2026-10-09 as a Scratch glitch kind, then removed with tape stop on Oct 10: Samuel didn't want them) Collective world.** Capture a buffer and "scratch" it back and forth like a turntablist. A new scratch effect.
7. **Optional: "calm builds" mode.** Dimensions' Tranquil adds layers the longer you stay quiet and lets noise make the music
   shrink away. Opposite of the current behavior (quiet room = quiet notes), so only as an option, if Samuel wants it.
8. **(BUILT 2026-10-09: chimes thin out when lots was played in the last ~8 s) Density memory.** Generative rule sets that look at how dense the recent music has been and adapt (avoids too many
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
    - (BUILT 2026-10-10) Motif memory: remember a short phrase of recent chime notes and bring it back later with variation.
    - (BUILT 2026-10-10, Key drift switch) Slow key-centre drift every few minutes (keeps the chosen key's notes, moves the home chord).
    - (BUILT 2026-10-10 without the compass part) Register from sensors: brighter = higher octave, dark/pocket = lower and warmer; climbing raises notes;
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

15. **Mic input shaping: attack, hold, release (Samuel, Oct 12; the order's step A).** Like Ableton's Gate and Compressor,
    the way he shaped drums in his mixes. Today (make_patch.py input stage): `env~ 1024 256` meter (21 ms window,
    every 5 ms); the gate opens in 5 ms and closes over 80 ms, one threshold, no hold, so it can flutter near it; the
    compressor's gain moves with a fixed `pack f 40` both ways. Plan:
    - Gate: hysteresis (open at the threshold, close a few dB below), a hold time, and a **faster detector of its own**
      (3-5 ms window) so it opens on time. No lookahead delay on the audible path: the user hears the room through
      the headphones live, Android already adds ~20-40 ms, and 20 ms more would make claps feel late and smear against
      the real sound leaking past earbuds (Room notes can delay; it's an effect).
    - Compressor: separate attack (gain going down) and release (coming back up).
    - Sliders folded under Input & output ("Gate and compressor shape"): gate attack, hold, release; compressor attack,
      release. noPreset like gain/gate/compressor, one setting for all mics. Defaults = today (5/0/80 ms, 40/40 ms).
    - Triggers (glitch onsets, chimes, Room notes' opening) already use the meter and stay that way. Note: the glitch
      buffer, harmony's pitch tracker and Room notes' resonators take the gated sound itself, so a slow gate attack
      also blunts what they get. Check harmony isn't chopped by a fast release or short hold.
    - Test: a step signal into the patch, measuring the real attack, hold and release times.
    - Purpose: pocket rustle (hold + slightly slower attack + faster release should shut between cloth bursts; it
      complements pocket hush and mic-down protection, and the mic-up pocket sound Samuel likes must not get worse)
      and earbud mics (15-20 dB quieter than the phone's).

16. **Found-sound rhythm section (Samuel, Oct 12; steps B and C).** The walking beat is "neat but not my favorite"
    (not yet known whether it's the drum sounds or the pattern: a quick listen test with another synth kit is worth
    doing, it's much smaller work). The idea: the room supplies the drum sounds and the walking pace sets a tempo, the
    RjDj premise itself. Today there is no BPM or grid: drums fire on each detected step, chimes wait for the next step
    or half-step (`mu_q_*`), the glitch cloud's "free clock" is random on purpose. Pieces that exist: StepDetector's
    averaged interval (the pace), the glitch cloud's 4 s RAM buffer, the sudden-sound detector (gc meter onsets),
    MotifMemory, density memory, ARP_PATTERNS tiers.
    1. **Tempo clock** (step B): its own steady beat, nudged by each footstep (phase-locked, like following a drummer),
       so a grid with subdivisions exists, uneven steps don't throw it, and it holds (or settles to a default) when
       you stop. Fold very slow paces up into a musical range. Useful on its own: drums, chimes and arpeggio on it.
    2. **Hit catcher:** on a sudden sound, copy a short slice from the RAM buffer into a small kit (never to disk),
       sorted by simple traits (low and thumpy -> kick, mid and noisy -> snare, high and short -> hat), keeping the
       best few recent ones per role. Pocket hush stays in front of it. In a pocket, footfall thumps will be caught and
       land on the tempo: maybe natural kicks, maybe mush.
    3. **Sequencer:** slices on the grid, patterns busier with pace (like ARP_PATTERNS), shaped to sit in the mix
       (pitch drop for kicks, high-pass for hats, a short envelope: ties in with item 15).
    4. **Rhythm memory:** like MotifMemory but looping and decaying: the last bar or two of hits carry on a few bars
       after the room goes quiet, varied each pass, thinning with density memory, then fading out.
    5. **Loop layering:** glitch-cloud results (stutter, reverse, stretch) captured and layered into the rhythm.
    6. **"Rhythm source" setting:** Synth drums / Found sounds / Both; the current walking beat stays as an option.
    Watch: sounds can't land on the beat as they happen, so they come back in later bars as echoes on the grid; a quiet
    room means an empty kit (fall back to soft synth drums or silence); slice choice and shaping decide musical vs
    messy; measure phone CPU (Music on is ~39% of a core).

17. **Tabs and Realms (Samuel, Oct 12; step D, replaces the step-7 screen polish).** The one long scroll has outgrown
    itself. Tabs, roughly Sound, Music, Scenes, Realms, Setup (devices, appearance, reset, about); five at most. The
    bottom bar (status, Start/Stop, Hold, Save) stays on every tab. A tab that does nothing right now says so ("Realms
    are paused while a scene is playing"). Plain Views, no new libraries: a tab strip switching containers.
    - **Realms** = Auto worlds renamed. Change only what is displayed: keep internal ids and built-in preset names
      ("Kinetic world"...) or migrate them, so nobody's choices reset (the reset-button rule).
    - **Realm ingredients:** each Realm expands to show its groups (Beat, Music, Echo, Reverb, Glitch...), each with a
      "this Realm uses it" switch; off = the Realm leaves that section at the user's own settings (an extension of the
      locked-param skip Worlds already do). Editing values inside a Realm stays preset editing (preset dropdown, Save
      sound), so Realms don't become a second settings screen.
    - Fold in the leftover polish ideas where they fit (mover dot, earcon on a Realm change, Bluetooth hint on the
      input picker, content descriptions) and the 100 Hz accelerometer trial.
    - Build in stages, each checked on the phone: split screens with no behaviour change, then tabs, then ingredient
      switches, then the rename. The tester guide gets rewritten once, after this lands.

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
