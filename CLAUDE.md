# PdScenes (working name) — notes for Claude Code

Open-source (GPLv3-or-later, bundles RjDj's rjlib) Android app: RjDj-style reactive music on libpd / Pure Data.
Free on Google Play eventually. **The final name and applicationId must not contain "RjDj".**
Owner: Samuel, community name "dadcraft". Testers call him "Dad" or "DadCraft" (never his real name in tester-facing text).
Test device: Moto G Stylus 2025, Android 16, no root. Build machine: Linux Mint with Android Studio.

## How we work
- You can build and install yourself now: `./gradlew assembleDebug`, then `adb install -r app/build/outputs/apk/debug/app-debug.apk`
  (adb wireless debugging is fine). Read crashes with `adb logcat`. Do this instead of asking Samuel to copy files.
- Only Samuel can judge the sound (pad level, chime density, walking feel). Make a change, tell him exactly what to listen for, wait for his report.
- Commit small, descriptive commits. Do not push or publish anything unless asked.

## Layout
- `app/src/main/java/app/pdscenes/` — Java, plain Views (no Compose; do not rewrite).
  Param/Params/ParamStore/PresetManager/Modulation (slider registry, presets, movers), Worlds/WorldSelector (Auto Worlds),
  StepDetector (walking beat), AudioService/AudioDevices/AudioSettings (audio engine and devices), SceneSettings, MainActivity.
- `app/src/main/assets/patches/test_scene.pd` — the built-in effects patch. **Generated.** Edit `tools/make_patch.py`, then run
  `python3 tools/make_patch.py`. Never hand-edit the .pd.
- `app/src/main/assets/scene_lib` — bundled rjlib. `docs/RJDJ-NOTES.md` — notes on the original format.
- `app/src/main/assets/builtin_scenes/` — the four official RjDj example scenes (GPLv3), copied to the scenes folder on first start by
  `SceneLibrary.installBuiltIns`. Their `rj/` folders keep only files that differ from `scene_lib/rj`. Reset everything restores deleted ones.
  `scene_lib/rj/s_fplaytable.pd` carries a fix for current Pd (`[list split]` output order); keep it when refreshing rjlib.
- Player-side helpers for scenes live in `scene_lib/`: `closebang`, `rj_time`, `rj_compass`, `rj_loc`, `rj_text`, `rjdj` (from PdParty, BSD) and the `rj_image` in `scene_lib/rj`.
  `SceneEvents` answers their `#pdparty` requests (time); compass is streamed all the time; there is no location permission, so `rj_loc` stays quiet;
  `rj_text`/`rj_image` messages are accepted but nothing is drawn on screen yet.
- `app/src/main/res/values/strings.xml` — escape apostrophes as `\'` (an unescaped one broke the aapt build once).

## Dependencies
- `io.github.libpd.android:pd-core:1.4.2-SNAPSHOT` from the Sonatype snapshots repo (declared in `settings.gradle.kts`, snapshotsOnly,
  restricted to group `io.github.libpd.android`). It is needed for `PdAudio.setDevicesId` (input picker). The last numbered release,
  1.2.1-rc6, lacks it. **Switch to a numbered release before the Play release.**

## Tests (run these after touching patch or Java logic)
1. Desktop libpd is needed for the Pd tests: `tools/build_libpd.sh` builds it into `tools/.libpd/libpd.so` (needs git, make, gcc).
   It is pinned to libpd 0.15.0 = Pd 0.55.2, the same Pd as the app's pd-core. Pd 0.56 breaks StreetBeatz.rj (`hip~` multichannel
   error); move the pin only together with pd-core. numpy lives in `tools/.venv` (run the tests with `tools/.venv/bin/python`).
2. `python3 tools/make_patch.py && tools/.venv/bin/python tools/test_patch.py tools/.libpd/libpd.so` — must end `ALL PASSED`.
   Also `tools/test_scene_loader.py`, `test_scene_sensors.py`, `test_rj_analysis.py`, `test_bundled_scenes.py`, `test_scene_helpers.py` (same libpd argument).
3. Java logic tests (no Android): `tools/javatests/run.sh` (or one at a time: `tools/javatests/run.sh W`). All must pass
   (C and P print no summary line, just no `FAIL:`). Android classes are stand-ins in `tools/javatests/stubs*`: when app code
   starts using a new Android method, add it there. Java is not on PATH: `export JAVA_HOME=~/.jdks/jbr-21.0.11` and put its
   `bin` on PATH (Android Studio's bundled JDK 25 is too new for Gradle 8.14). adb: `~/Android/Sdk/platform-tools/adb -s ZD222T44PP`.
4. Android build: `./gradlew assembleDebug`. Real-device check is Samuel's.

## Pd gotchas
- In message boxes write commas as space + `\,`.
- A `[value]` that feeds several destinations fires them all on a bang: use one reader object per consumer.
- `[t b b f]` fires right to left.
- No `;` inside comments in Params.java (the test regex stops at `;`).

## Design decisions to keep
- **Output never goes to the phone speaker.** Headphones only (wired first, then Bluetooth). `startEngine` throws `err_no_headphones`
  without them; `outputWatcher` switches or stops when they are unplugged. It first mutes (`computeAudio(false)`) and waits
  `DISCONNECT_SETTLE_MS` (600 ms): libpd's `OboeEngine::onErrorAfterClose` closes and reopens the streams on Oboe's thread with no lock,
  and stopping at the same moment crashed in `OboeEngine::closeStream`. Reported upstream as https://github.com/libpd/libpd/issues/427; drop the delay once a fixed pd-core release is used.
- **Bluetooth mic = call mode** (mono, poor quality). Uses MODE_IN_COMMUNICATION and `setCommunicationDevice` matched by type + address
  (the mic and speaker are separate devices with separate ids; matching by id failed). LE Audio headsets can be better. The UI hints about it.
- **Soft limiter** at the output (`clip~` base plus cubic-eased excess, never above 1.0). Hard clipping sounded fuzzy.
- **Defaults:** input gain 2.5, compressor -30 dB 4:1. Gain, gate, compressor, smoothing, nudge and music on/key/scale are `noPreset`.
- **Auto Worlds:** Tranquil / Flux / Kinetic / Ghost / Pocket, priority Ghost > Kinetic > Flux > Tranquil > Pocket. Worlds skip locked params and `*_on`
  switches and never flip `music_on`.
- **Sensors / Pocket world:** `PhoneContext` (pure logic, test X) holds brightness/pocket/climb and the rotation-vector heading; `SensorInput` feeds it. Mover shapes 13-15 are Brighter/In pocket/Climbing.
  Brightness is *room-relative* (Samuel: "it should respond to the world/room/situation around the user"): 75% where the light sits between
  the darkest/brightest of the last ~90 s (min span 10x lux, steady = 0.5), 25% the fixed sun scale. Pocket detection still uses absolute lux. Pocket is a *layer*, not a rival world (Samuel's idea): in a pocket the world still follows night/walking/room, the pocket hush
  rides on top, and the Pocket world only plays when nothing else fits. In a pocket, loudness is judged from the room's floor
  (quietest moments, rising <= 3 dB/s, +6 dB for cloth muffling) so rustle bursts don't count as a loud room. Tuning of the Pocket world preset and the climb scale (`CLIMB_FULL_HPA`) is untested on a real phone.
- **Pocket hush** (`pocket_hush`, main section, noPreset, default 0.5 = -12 dB; 0.9 hid a finger snap next to the pocket): AudioService sends `pocket 0|1` to the built-in
  patch whenever `PhoneContext.inPocket()` flips, whether or not Auto Worlds is on. The mic is turned down after the compressor (so it
  cannot lift the rustle back up), Room notes hear the hushed mic, and rustle-triggered chimes are scaled by the hush. Footstep
  arpeggio, beat and pad are untouched. Needed because walking with the phone pocketed picks Kinetic, not Pocket, so the Pocket
  world alone never quieted the rustle (Samuel heard all the cloth noise at the store). Pocket and world changes, plus a
  "Hearing:" line every 30 s (level, floor, swing), go to `files/events.log` (64 KB, one rollover):
  `adb shell run-as app.pdscenes cat files/events.log`. Phone logcat only holds ~10 minutes.
- **Mic-down protection** (`pocket_guard`, main, noPreset, default 0.6; 0 = no change): Samuel found mic-end-down pockets
  rustly but mic-up pockets fine. `PhoneContext.micDown()` (gravity along +y averaged ~1 s, hysteresis 0.5/0.3) and
  AudioService sends `pocket_down` = pocket && micDown. The patch adds guard*12 dB more cut and crossfades in a 2x `hip~ 300`.
- **Flux needs a lively room:** loud AND the level swinging >3 dB around its average (leave <2). Running water hit Flux and
  became pure fuzz; a steady roar now leaves the user's own settings. Flux preset was softened (dist 0.2 soft, crush 0.15,
  ring 0.15, freeze mover depth 0.4) so the room still comes through.
- **Walking beat:** StepDetector sends `step <interval>` messages; foot drift was fixed and confirmed on the phone.
- **Music (off by default):** key + scale snap the notes; pad is soft glue (default 0.33, Samuel likes ~0.20); chimes/arpeggio follow the room.
  Pad chords come from `CHORD_POOLS` per scale (Samuel chose: home chord + its two strongest neighbours, picked by brightness, plus one
  contrast chord ~20% of changes; e.g. C major = C F G + Am; pentatonic/whole tone keep all). No diminished chords. Chord changes
  crossfade between two oscillator sets (no pitch slides, which sounded like an eerie slide into minor). Chosen roots go to `s pad_chord`.
  Listening uses an *adaptive noise floor* so a quiet room is quiet (chime chance ~ eff^3). Walking arpeggio swells with pace.
  **Room notes** (`music_res`, `add_room_notes`): the mic through 6 `vcf~` resonators on the pad chord's root/third/fifth, 1 and 2
  octaves up (octave = scale size, so pentatonic stays in range). Input opens from the 5 ms level meter vs the room floor (20 ms
  lookahead), soft-limited at 0.3. Ring length follows what was heard (`rn_int`: loudness jumps it, duration builds it over 1.5 s,
  relaxes over 8 s): soft tap ~0.4 s chime, clap ~0.9 s, long loud sound ~2.2 s bell (20 dB fades). Longer rings are fed harder so
  notes start as loud. Default 0.8 (Samuel found 0.4 too quiet). Worlds: Flux 1.0, Tranquil/Ghost 0.6, Kinetic 0.5, Pocket 0.
  Variety (Samuel found the chimes repetitive): chimes walk a melody (+-1/2 scale steps, never the same note twice, within 4 steps
  of the brightness note), each chime gets a random fade (0.9-2.6 s) and overtone colour, footsteps switch among 5 eight-step
  `ARP_PATTERNS` every bar with ~12% rests, and the pad's chord pick wanders more (jitter 0.9). Notes played go to `s chime_deg`.
  While walking (a step in the last 2.5 s), a sudden-sound chime waits for the next footstep or half-step so it falls
  in with the arpeggio (latest one wins); standing still it plays at once.
  **Pad register** (`music_pad_reg` Low/Mid/Both, default Both, noPreset; Samuel's idea, he likes it: deep without overpowering): a bass voice (sine + 0.35 2nd + 0.15
  3rd harmonic, folded to 65-131 Hz) on the key root, moving to the chord root on 40% of chord changes; note changes dip out
  and back in (no slides); each footstep ducks it 60% while the walking beat is audible. It rides the pad level/swell.
  Music joins after the filter, so chorus/flanger/phaser/tremolo/reverse/glitch/echo/reverb/spatial shape it; pitch/ring/crush/dist/filter do not.
  It follows the Dry level. Only the real room tells us if the tuning is right — expect further tweaks from Samuel's reports.
- **Reset everything button:** `ParamStore.resetAll` + `Worlds.resetSettings` + `AudioSettings.reset` + `SceneSettings.resetAll`, only after confirmation.
  Keeps saved presets, imported scenes and appearance (and brings back any deleted built-in scene). Nothing may ever reset settings except that button.
- Presets store: sliders, movers, music pad/notes/tone/follow, beat, dry. A slider kept out of presets keeps its mover out too
  (`Params.withMovers`), or loading a preset or world switched it off. Not stored: gain/gate/compressor, smoothing/nudge,
  music on/key/scale, locks, worlds choices, audio device, scenes, appearance.

## Open / next
- **Ideas queue with details: `docs/ROADMAP.md`** (in-key resonators, pitch-following harmony, Ghost capture, Kinetic tiers, Unstable and Collective worlds, stems player).
- Release prep: final name + applicationId, `source_url` in strings.xml, privacy policy, Play foreground-service + microphone declarations, icon, store listing.
- Ideas, not requested: on-screen route/clipping diagnostics, beat-offset slider if drift returns, music independent of Dry level,
  location (`#loc`) scene input, unported scene objects.
- The Beta Tester Guide lives in Samuel's Claude Docs (not in this repo). If behavior changes, tell him the guide needs an update.
