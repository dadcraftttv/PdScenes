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
2. `python3 tools/make_patch.py && python3 tools/test_patch.py tools/.libpd/libpd.so` — must end `ALL PASSED`.
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
  without them; `outputWatcher` switches or stops when they are unplugged.
- **Bluetooth mic = call mode** (mono, poor quality). Uses MODE_IN_COMMUNICATION and `setCommunicationDevice` matched by type + address
  (the mic and speaker are separate devices with separate ids; matching by id failed). LE Audio headsets can be better. The UI hints about it.
- **Soft limiter** at the output (`clip~` base plus cubic-eased excess, never above 1.0). Hard clipping sounded fuzzy.
- **Defaults:** input gain 2.5, compressor -30 dB 4:1. Gain, gate, compressor, smoothing, nudge and music on/key/scale are `noPreset`.
- **Auto Worlds:** Tranquil / Flux / Kinetic / Ghost / Pocket, priority Ghost > Kinetic > Pocket > Flux > Tranquil. Worlds skip locked params and `*_on`
  switches and never flip `music_on`.
- **Sensors / Pocket world:** `PhoneContext` (pure logic, test X) holds brightness/pocket/climb and the rotation-vector heading; `SensorInput` feeds it. Mover shapes 13-15 are Brighter/In pocket/Climbing.
  Brightness is *room-relative* (Samuel: "it should respond to the world/room/situation around the user"): 75% where the light sits between
  the darkest/brightest of the last ~90 s (min span 10x lux, steady = 0.5), 25% the fixed sun scale. Pocket detection still uses absolute lux. Auto Worlds priority is now Ghost > Kinetic > Pocket > Flux > Tranquil. Tuning of the Pocket world preset and the climb scale (`CLIMB_FULL_HPA`) is untested on a real phone.
- **Walking beat:** StepDetector sends `step <interval>` messages; foot drift was fixed and confirmed on the phone.
- **Music (off by default):** key + scale snap the notes; pad is soft glue (default 0.33, Samuel likes ~0.20); chimes/arpeggio follow the room.
  Listening uses an *adaptive noise floor* so a quiet room is quiet (chime chance ~ eff^3). Walking arpeggio swells with pace.
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
