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
- Player-side helpers for scenes live in `scene_lib/`: `closebang`, `rj_time`, `rj_compass`, `rj_loc`, `rjdj` (from PdParty, BSD), our own `rj_text` and `scene_lib/rj/rj_image`,
  and stand-ins for externals some imported scenes use: `declip`, `avg~`, `aubiopitch~` (sigmund~, MIDI out) and a silent `keys`.
  `SceneEvents` answers their `#pdparty` requests (time); compass is streamed all the time; there is no location permission, so `rj_loc` stays quiet;
  **Scene graphics** (roadmap item 9, Oct 14; `SceneGraphics.java` test G, `tools/test_scene_graphics.py`): `rj_image`/`rj_text`
  send `rj_gfx <$0> <command> ...` (`[pdcontrol]` args for the text's words); AudioService subscribes before opening a
  scene (the load-time `image`/`text` arrive then) and clears on open/stop; ScenePad draws visible items over the cover
  on the 320 grid (images at their file size, one pixel = one grid step, centred; white text with a shadow), checking
  `version()` 30x a second. Six of Samuel's 55 scenes use them (Atsuke, Moogarina, MoonBootSynthPad, Showtime, Smile,
  TouchVocoder). Left unfixable: Gem objects (Atsuke, desktop only), objects the authors disabled with a leading "-",
  and abstractions missing from the scenes themselves (s-loader, 808_state, tr808-bd~). `pdtest.Engine.lists` keeps
  whole lists heard (floats and symbols).
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
3. Java logic tests (no Android): `tools/javatests/run.sh` (or one at a time: `tools/javatests/run.sh W`; D = diagnostics, H = handling, I = intensity, F = first run, B = calm build, G = scene graphics, K = stem packs). All must pass
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
  Upstream fix tested Oct 14 (branch `oboe-fix-test`, pd-core built locally into mavenLocal as 1.4.2-oboefix from
  pd-for-android PR #198 6306ff8 + libpd PR #428 56c7021 cherry-picked onto libpd 3fc60ea = Pd 0.55.2, NDK 29): build A
  (fix + 600 ms delay) and build B (fix, delay 0, `PdAudio.setAutoReopen(false)`) each 10 wired unplugs while playing
  (Music + beat on) and 10 unplugs right after Stop on the Moto G: 40/40 clean, no crash, no sound on the speaker;
  B stopped ~20 ms after the unplug. Bluetooth not tested. When a pd-core release has both PRs: set
  `PdAudio.setAutoReopen(false)` before initAudio and DISCONNECT_SETTLE_MS to 0 (check Pd 0.56 + StreetBeatz first).
- **Bluetooth mic = call mode** (mono, poor quality). Uses MODE_IN_COMMUNICATION and `setCommunicationDevice` matched by type + address
  (the mic and speaker are separate devices with separate ids; matching by id failed). LE Audio headsets can be better. The UI hints about it.
- **Soft limiter** at the output (`clip~` base plus cubic-eased excess, never above 1.0). Hard clipping sounded fuzzy.
- **Defaults:** input gain 2.5, compressor -30 dB 4:1. Gain, gate, compressor, smoothing, nudge and music on/key/scale are `noPreset`.
- **Auto Worlds:** Tranquil / Flux / Kinetic / Ghost / Pocket / Unstable, priority Unstable > Ghost > Kinetic > Flux > Tranquil > Pocket.
  **Unstable** (roadmap 5): shaking the phone (`PhoneContext.secondsSinceShake`: 3 jolts past 1.2 g, gravity taken out,
  within 1.5 s; one bump or walking bumps don't count) while not walking brings it *at once* (no dwell or min hold,
  0.3 s fade instead of 3 s) and keeps it until 5 s after the last shake; then the normal 5 s dwell hands back.
  Preset: glitch cloud at full (no stretch), crush, ring mod, pitch +7, echo scatter 1, with Shake = higher movers on
  ring freq, pitch and crush rate. Now line says "shaken". **Off by default** (Samuel: it adds little; opt-in in the
  world list, `World.onByDefault`). Worlds skip locked params and `*_on`
  switches and never flip `music_on`.
- **Sensors / Pocket world:** `PhoneContext` (pure logic, test X) holds brightness/pocket/climb and the rotation-vector heading; `SensorInput` feeds it. Mover shapes 13-15 are Brighter/In pocket/Climbing.
  Brightness is *room-relative* (Samuel: "it should respond to the world/room/situation around the user"): 75% where the light sits between
  the darkest/brightest of the last ~90 s (min span 10x lux, steady = 0.5), 25% the fixed sun scale. Pocket detection still uses absolute lux. Pocket is a *layer*, not a rival world (Samuel's idea): in a pocket the world still follows night/walking/room, the pocket hush
  rides on top, and the Pocket world only plays when nothing else fits. In a pocket, loudness is judged from the room's floor
  (quietest moments, rising <= 3 dB/s, +6 dB for cloth muffling) so rustle bursts don't count as a loud room. Tuning of the Pocket world preset and the climb scale (`CLIMB_FULL_HPA`) is untested on a real phone.
- **Mic input shaping** (roadmap 15, Samuel Oct 12; section "Gate and compressor shape", folded, noPreset/noRandom/
  `noMover()`): the gate has its own fast meter (`env~ 256 64`: 5 ms window every 1.3 ms; the shared 21 ms meter
  still drives the compressor, triggers and movers) so it opens on time without a lookahead delay (the room is heard
  live: Android already adds 20-40 ms). It opens at the threshold, starts closing only `GATE_HYST_DB` (4) below it,
  stays open `gate_hold` ms, opens over `gate_attack` (default 5) and fades over `gate_release` (80). The compressor's
  gain moves at `comp_attack` going down and `comp_release` going up (both 40 = before); an unchanged target keeps
  its last speed, and changes under ~0.1 dB don't count (the meter ripples). Measured: defaults open 3 ms after a
  sound, rise 3 ms, fade 64 ms; attack 30/hold 150/release 400 -> 23/196/320 ms; a level hovering at the threshold
  doesn't flutter; the fastest release doesn't chop harmony. +6% of the idle patch.
- **Pocket hush** (`pocket_hush`, main section, noPreset, default 0.5 = -12 dB; 0.9 hid a finger snap next to the pocket): AudioService sends `pocket 0|1` to the built-in
  patch whenever `PhoneContext.inPocket()` flips, whether or not Auto Worlds is on. The mic is turned down after the compressor (so it
  cannot lift the rustle back up), Room notes hear the hushed mic, and rustle-triggered chimes are scaled by the hush. Footstep
  arpeggio, beat and pad are untouched. Needed because walking with the phone pocketed picks Kinetic, not Pocket, so the Pocket
  world alone never quieted the rustle (Samuel heard all the cloth noise at the store). Pocket and world changes, plus a
  "Hearing:" line every 30 s (level, floor, swing), go to `files/events.log` (64 KB, one rollover):
  `adb shell run-as app.pdscenes cat files/events.log`. Phone logcat only holds ~10 minutes.
- **Handling noise** (roadmap item 3, Oct 13; `HandlingDetector.java`, test H; `add_handling`, `handling_gate`):
  taps, grips and rubbing on the phone. Measured on Samuel's phone (jerk = change of acceleration between readings at
  200 Hz): table ~0, held still 0.1-0.3, walking in hand 0.4-0.9 (once 2.0), rubbing/fiddling 0.6-1.7 steadily, taps
  4-7, grips 2.5-8 (a 15 Hz high-pass could NOT tell walking from taps). A jolt = jerk > 3 (walking or not, one per
  100 ms): SensorInput sends `jolt` straight to Pd (built-in patch only). Handling level = max(jolt fading over 0.3 s,
  fiddling = the jerk's recent peak 0.7..2.0 while NOT walking), sent as `handling` from the mover tick. Pd: `hush_ln`
  = pocket hush x handling duck (`handling_hush`, main, noPreset, default 0.5 = -12 dB at full; 15 ms down, 300 up)
  for everything that hears the hushed mic (mic_comp, found kit, glitch buffer, room notes, harmony tracker). A jolt
  sets `value hjolt` for 200 ms; chimes and found room notes skip a sudden sound while hjolt or handling > 0.3 (no
  wait); glitches check 40 ms later (`HND_CHECK_MS`); a found-sound slice is dropped (`fs_caught 4`, "Skipped a
  handling noise") when a jolt was within 200 ms before its start or during it (`fs_jv`). Diagnostics count skips in
  the last minute; the Now line says "handling". Untested on the phone: whether the jolt reaches Pd before the mic's
  onset (the chimes assume so).
- **Intensity** (roadmap item 4, Oct 13; `Intensity.java`, test I): `intensity` (main section, first row, and a
  compact slider in the bottom card; noPreset, noRandom, movable; Samuel: the user's own control, Realms and presets
  never touch it). 0.5 = as set. `Modulation.output` (the one path every value takes to Pd) applies the mover, then
  `Intensity.apply` to the params in its RULES: only what is already there is scaled (0 stays 0), down by `calm` x the
  value at 0, up by `lift` x at 1, capped at max(value, randMax). Wet/reverb/scatter/room notes 0.6/0.6, feedback
  0.5/0.3, glitch amount/glitch loops/reverse echo 1/0.8, colour effects and tremolo 1/0.6, music react 0.6/0.5,
  harmony 0.5/0.3, chimes level and beat level 0.4/0.3. Not scaled: dry, pad, input chain, hushes, key/tempo.
  A stronger top (lifts doubled, up to each slider's top, more glitches above the middle) was tried and reverted:
  Samuel, Oct 13: "too much... I'm good with it as it was before".
  Moving it (by hand: `ParamStore.set`; by its mover: `Modulation.tick`, on a change > 0.003) resends every scaled
  param. The patch hears `intensity` too: the beat's drive +-0.3 (`INT_DRIVE`), measured standing in a quiet room
  4.6 / 4.7 / 7.6 hits a second at 0 / 0.5 / 1 (a quiet room's drive is already near the bottom).
- **First run** (roadmap item 5, Oct 13; `Walkthrough.java`, `FirstRun.java` test F): Samuel: "everything should be
  off ... the only thing they should hear on pressing start is the dry audio". Echo level (`wet`) now defaults to 0,
  the last audible default (Realms, music, beat, glitch were already off); a Pd test sends every Params default and
  checks a click comes back once. Existing installs keep their stored values. Six full-screen pages (welcome,
  headphones with a live check, privacy + "Allow microphone" (REQ_MIC, doesn't start the sound), it starts quiet:
  explore one thing at a time, the card and tabs, ready: Start + feedback email dadcraftstudios@gmail.com). Opens
  by itself only on a fresh install (firstInstallTime == lastUpdateTime) and once (`UiSettings` walkthrough_seen;
  Reset everything leaves it); Setup, About has "Show the walkthrough again" and the feedback email (Samuel: email
  only, no Discord).
- **Mix** (Samuel, Oct 13: "every musical and rhythmic element should either have a volume slider or on/off
  switch"): section `mix` on the Music tab, in presets (Samuel: shared with a preset), a Realm ingredient (`Worlds.GROUPS`
  "mix"). It holds the existing beat_snare, beat_hats, beat_glitch, music_pad, music_harm (moved from Rhythm/Music,
  ids unchanged) and new trims 0-1.5 (default 1 = as before, noRandom, NOT resetWhenAbsent so older presets and the
  built-in Realms leave them alone): `mix_kick` (synth kick and found kick; the found one is `fs_ks_kick`, named into
  the fsound group: outside it the trim made a DSP loop between the toplevel and that group), `mix_bass` (synth +
  found bass, `ba_sm`), `mix_chimes` / `mix_walk` (the chimes and walking notes share the 4 voices, so the trims scale
  each note's velocity: chimes at `mu_deg` and motif replays, the arpeggio writes its own trimmed velocity on each
  note from `apvel` (`mu_arp_t` outlet 3; before, an arpeggio note after a chime played at the chime's velocity) and
  the groove note), `mix_ring` / `mix_bells` (`rn_out` / `rnf_out`). At 0 a part is silent but still runs (no extra
  switch~ factors). Turning Auto realms on asks first ("Let Realms change your sound?": they set the sliders from
  their own preset, the mix too; "What it changes" keeps a part).
- **Reverse reverb** (roadmap item 7, Oct 13; `add_reverse_reverb`, `reverb_rev` Reverb section 0..1, in presets,
  Intensity rule 1/0.8, Ghost realm 0.5): a sudden sound (`gc_det_sel` through `handling_gate`, one swell at a time)
  books a swell: its reverb tail (`rr_buf`, the reverb's mono wet, 7 s) L ms long read backwards so it peaks at B.
  Free: L = 600 + 900 x room size, B = 2L after the sound. Synced (`msync`, Samuel: "time the swells to the beat"): L =
  one beat (`tc_P`, max 1500), B = the first beat at least 2L away (`r tempo` resets a timer). Delay ramp
  B - 2L + lead -> B + lead over L (`RR_LEAD_MS` 25: the sound is noticed ~60 ms late and the reverb's first echo
  is ~30 ms after it, so the loudest moment lands on time; 70 ended 50 ms early), 30 ms in, 20 ms out. Measured: a
  clap's swell rises x40 over its last 0.6 s; synced it ends 11 ms from the beat. The first try (Reverse echo's
  continuous two-grain reversal fed the reverb) rose nicely but peaked wherever the sound fell, never on the beat.
  Audio group `revrev` (reverb_on x reverb_mix x reverb_rev).
- **Calm builds** (roadmap item 8, Oct 14; `CalmBuild.java`, test B; `calm_build` toggle in Music, off by default,
  noPreset, noPd: Samuel, "keeping it your own works best"): calm = switch on, music on, not walking, room not
  loud-and-lively. After `WAIT_S` 30 s of calm, the level rises over 180 s, holds 60, falls over 120, then rests 180
  before another; not calm -> it fades within `DROP_S` 5 s and waits for 30 s of calm again. Layers join along the
  rise (pad from 0, room notes from 0.25, standing-still chimes from 0.5, harmony and reverb from 0.75) and each is
  lifted up to +40% at the top in `Modulation.output` after Intensity (only what is on, never past the slider's top;
  resent on a change > 0.005). The chimes layer goes to Pd as `calm_chimes`: an extra still-pattern chance of
  `CALM_CHIME_P` (40 in 1000 per 0.25 s at the top, about one soft chime every ~6 s in a quiet room). Event log
  "Calm build starts/ends"; the Now line says "building".
- **Stems player** (roadmap 9 in ROADMAP.md, Oct 14; `StemPack` parse, `StemArrangement`, `PackPlayer`, `PackLibrary`,
  test K; `add_stems`, Pd test "stems:"; `tools/make_test_pack.py` writes a synth test pack): packs live in
  files/packs/<name>/ with pack.txt (title, bpm, key "A minor", bars; "file role: x [bars: n] [section: B]", _A/_B
  file suffixes = sections; max 8 stems). Import zip/folder (Music tab "Stem packs"); non-WAV stems are decoded once
  with MediaExtractor/MediaCodec into `.decoded-<file>.wav`; loop lengths are checked (warnings). Selected pack in
  prefs `pdscenes_packs`, not in presets (Samuel); built-in sound only. While playing, `Modulation.output` lets
  `PackPlayer` override tempo_mode (2 = locked: the clock sits on tc_Pu, steps change nothing), tempo_bpm, music_key,
  music_scale, and beat_level x 0.3 while the pack's drums play (Samuel agreed). Pd: STEM_SLOTS 8, each two tables via
  soundfiler (`[list]` after `[route]`: route leaves a path as a selector), restarted by vline~ (N / file rate, so any
  sample rate plays at its speed) on downbeats where bar % bars == 0 (`stem_start` -> next downbeat is bar 0), level
  taken at the downbeat and faded over a bar; stereo into in_l/in_r before the spatial stage, x `stems_level` (Mix,
  0.8). Arrangement: pad always, bass walking/lively/loud, drums walking, lead lively or brisk (pace >= 0.6), texture
  night/pocket/Ghost; 8 s hold per role; sections every 4 loops of the longest stem. Import refuses a pack over
  `StemPack.MAX_STEREO_S` (240 s of stereo, mono counts half, ~92 MB as Pd floats) and gives up decoding a file after
  60 s (`DECODE_LIMIT_S`), from the Oct 14 hardening review. Health check that day (phone): audio thread 31-41% of a
  core with Samuel's settings, 45-60% with everything on and Intensity full, no underruns while running; battery
  ~0.5% per 30 min for the app in the background (12.6 mAh CPU of a 266 mAh, 6% drop). Untested on the phone (Samuel
  has no packs yet; the test pack was put on his phone and selected).
- **Call and response** (roadmap 12, Oct 14; `CallResponse.java`, test L; `music_answer` Music 0..1 default 0.5, in
  presets): the Harmony tracker (now also run for it: `fpc_run` includes music_answer) sends `heard_deg <step>` at each
  note-on and `heard_off` at note-off; a phrase = notes with pauses < 1.5 s (max 6); after `ANSWER_AFTER_S` 1.6 s of
  quiet (Samuel: 0.7 was "answering too soon") it is answered once (cooldown 3 s) through the motif path (`motif
  <step> <vel>`, velocity 0.55 x level): same rhythm, +2 steps (-2 if it reached step 14), 40% the last note on the key
  note's octave. The "Hearing:" harmony count only counts while Harmony > 0. Tests set music_answer 0 unless testing it.
- **Send feedback** (Setup, About; Oct 14): a mailto email to dadcraftstudios@gmail.com, subject with the version,
  body with a prompt, phone/Android/app version, what's playing, and (box ticked by default, explained) the last 200
  event-log lines in the body (no attachment, no FileProvider). 0.9.0-rc2 = versionCode 10.
- **Rustle detector: REMOVED** (Oct 14, Samuel: "take it out completely... hold on to it in our backpocket"). The full
  version (`add_rustle`, `rustle_guard`, tests, Now line/Diagnostics) is in commit ea57dde. Why: on Samuel's phone a
  quiet room already reads 12-20k zero crossings/s and highs only 5-7 dB under the whole (mic hiss); sleeve rubbing
  read as a few loud thumps (+33 dB, highs -6..-13, 1 burst), talking and music as 2-3 bursts a few dB over the room:
  no cheap feature separated them. Motion handling (fiddle) and pocket hush/guard are the protection.
- **Mic-down protection** (`pocket_guard`, main, noPreset, default 0.6; 0 = no change): Samuel found mic-end-down pockets
  rustly but mic-up pockets fine. `PhoneContext.micDown()` (gravity along +y averaged ~1 s, hysteresis 0.5/0.3) and
  AudioService sends `pocket_down` = pocket && micDown. The patch adds guard*12 dB more cut and crossfades in a 2x `hip~ 300`.
- **Flux needs a lively room:** loud AND the level swinging >3 dB around its average (leave <2). Running water hit Flux and
  became pure fuzz; a steady roar now leaves the user's own settings. Flux preset was softened (dist 0.2 soft, crush 0.15,
  ring 0.15, freeze mover depth 0.4) so the room still comes through.
- **Walking beat:** StepDetector sends `step <interval>` messages; foot drift was fixed and confirmed on the phone.
- **Rhythm section** (renamed from "Walking beat", Samuel Oct 12: it now holds the found rhythm, not just footsteps).
  **Tempo** (`tempo_mode` Auto / Set, `tempo_bpm` "Set tempo" 60-160, default Auto / 100, noPreset): Set = your BPM
  (`tc_Pu`); standing, the beat glides there by `TEMPO_RETURN` (0.25) per beat; walking, each step moves it
  `TEMPO_NUDGE` (0.3) toward a target `TEMPO_WALK_PULL` (0.5) of the way from your BPM to the step rate in the octave
  nearest your BPM, with no phase pull (two tempos would wobble). Measured: set 90, walking 100 steps/min -> 94.7.
- **Tempo clock** (roadmap 16 part 1, step B; `add_tempo_clock`): a steady beat in Pd that follows the steps like a
  band follows its drummer: each step moves the next beat 35% of the way to it, the beat length 10% of the error plus
  15% toward the step interval; one step = one beat, folded into 80-160 BPM (an amble at 60 steps/min plays at 120).
  A step after >2 s (+a beat) starts a fresh walk on its own beat. It sends `pulse <beat s>` while walking (until
  1.25 step intervals after the last step, so stopping still stops the drums) and `tempo <bpm>` on every beat; it
  keeps ticking at the last tempo. `beat_follow` (Walking beat section, noPreset, default 1 = clock; 0 = "Your steps",
  the old behaviour: steps passed straight on as pulses). Drums, arpeggio notes, chime queue, bass duck, echo sync
  and the glitch step lock listen to `pulse`; the arpeggio's pace and the stop breath still use the real `step`.
  The Now line says "walking 112 BPM". Measured: steps wobbling +-40 ms -> beats within 13 ms of even, a pace change
  followed within ~2 steps, a missed step leaves no hole. Tests run with `beat_follow=0` unless they test the clock.
  **Pd lessons:** a [t] outlet feeding two objects has no defined order (one read a stale time and the tempo ran away);
  an interval of 0 made a 0 ms beat that rescheduled itself forever (guarded). `CLOCK_DEBUG=1` prints P, N, I, now.
- **Pattern engine** (roadmap 16 step C1, `add_rhythm`; Samuel: the old kick-snare-hat "never changes, grows stale"):
  the clock also sends `tick16 <0-15>` (a metro at a quarter beat, restarted on each beat; no 5th tick when slowing).
  Bars from `KICK_PATS`/`SNARE_PATS`/`HAT_PATS` (calm -> busy; hats > 2 = open) play the drum voices (which now take a
  velocity). On tick 15 the next bar picks per lane a pattern near the drive (or a neighbour), the kick never the same
  twice; hits may drop (8%), extra 8th kicks and ghost snares come with the drive, every 4th bar ends in a snare fill
  when the drive is up. Drive: walking 0.55 + 0.45 x pace; standing 0.1 + 0.5 x the room's liveliness (slow mic
  level vs a creeping floor). `beat_when` (Walking beat, noPreset): 1 = Always (default; standing still at
  0.35-0.75 of the level, Samuel: "the rhythm should be constant... always making a rhythm out of what it hears"),
  0 = only while walking (the clock's `clock_walking` turns it off, 150 ms fade, ~0.75 s after the last step).
  Calmed after Samuel's first walk ("slightly too busy/random"): a choice holds `RH_HOLD_BARS` (2) bars, drops 4%,
  extra kicks (1-3%/8th) and ghost snares (~1-2%/16th) rarer, fills every `RH_FILL_EVERY` (8) bars, walking drive
  0.4 + 0.45 x pace. The clock now starts ticking at load (50 ms, then 100 BPM), so standing still from Start has a pulse.
  Only with `beat_follow` 1; "Your steps" keeps the old one-hit-per-step drums. The level moves only on real changes
  (a ramp restarted every 100 ms never arrived). Tests hear `drum_kick/snare/hat` and `rh_bar_patterns`.
  Next (C2/C3): found sounds from the mic become the kit; synth drums stay as the fallback.
- **Breakbeat** (Oct 15, from Samuel's other chat; `beat_break` Rhythm 0..1, default 0, in presets; Pd test
  "breakbeat:"): at 0 nothing changes. Each pick takes `BREAK_KICK_PATS`/`BREAK_SNARE_PATS` (stored after the usual
  pools in `rh_kpat`/`rh_spat`, index + 5) with chance `BB_POOL` (0.8) x the slider. Per bar (decided at tick 15 into
  `rh_*_next`, applied at tick 0 like `rh_brk`; never in a sparse bar): a chop (`BB_CHOP` 0.25 x slider: tick t
  reads the patterns' step `CHOP_MAPS[c][t]`, downbeat kept, all three lanes), a roll (`BB_ROLL` 0.2: 3-4 snares a
  32nd apart from tick 5, 9 or 13; the in-between hits are `rh_hits` outlet 4 through a `[pipe]` of tc_P/8; never
  inside a fill) and a long fill (`BB_FILL` 0.1, or a usual fill made long with chance `BB_FILL_LONGER` 0.4 x slider: `FILL_LONG` from
  tick 8). Chimes, learned groove and glitch loops keep the straight tick; hats and tempo stay with the pace (the
  other chat's open choice: pace stays in charge). `rh_bb_bar` reports roll, chop, long fill. Measured at 1 vs 0
  (150 BPM, 42 bars): 29 vs 18 distinct loud kick+snare bars, kicks off the beat 77% vs 49%. expr `random()` is
  used for these (no new [random] objects, so other tests' random sequences are unchanged). Feel untested.
- **Found-sound kit** (roadmap 16 C2/C3, `add_found_kit`; Samuel: "the sounds around you become the rhythm"): on each
  sudden sound (the glitch cloud's detector, `gc_det_sel`, always running; never while in a pocket) a `FS_SLICE_S` (0.25 s) slice of the hushed
  mic from `FS_PREROLL_MS` (15 ms) earlier is recorded (`tabwrite~ fs_stage` from a 100 ms `fs_buf`) while env~ maxima
  of all/lows (<150 Hz)/highs (>4 kHz) are kept; then filed: below `FS_MIN_DB` (-45 dBFS) dropped, lows within 6 dB of
  the whole -> kick, highs within 6 dB (3 caught no real taps) and lows 15 dB under -> hat, else snare; copied (`array get/set`) into the
  role's next slot `fs_<role><slot>` (`FS_SLOTS` 5 per role since Oct 12, was 3; round robin, memory only) with a gain levelling its peak to 0.5
  (`fs_gains`) but its loudest 10 ms no higher than `FS_RMS_TARGET` (0.3; a snap at the mic overloaded it into a
  clipped, dense slice that played as a "deafening boom"), and the found drums get `FS_MAKEUP` (3x) into a tanh
  limit at `FS_LIMIT` (0.9): a thump kit ~5 dB under the synth kit, a clipped boom at its level, never above
  (Samuel, Oct 12: "not quite present enough"). `fs_filled` counts. Voices (one per role): a random filled slot of
  its role through `tabread4~` at rate 0.8/1/1.3, lop 3.5k / hip 160 / hip 1.5k, level 1/0.8/0.7, decay
  260/200/hat's own; a role with nothing of its own borrows any caught slot, so one catch makes the whole kit found.
  Each hit varies (Samuel, Oct 12: "a little too predictable"): pitch +-`FS_VAR_SEMI` (1) semitone, 30% start up
  to 10 ms into the slice (`FS_VAR_START`), loudness 0.9-1.1 (`FS_VAR_VEL`). **Swing** (step 2): odd ticks reach
  the pattern engine `rh_sw` of a 16th late (`[pipe]` before `rh_on`; the clock's own tick16 stays straight, so
  chimes, the learned groove and glitch loops keep to it); every `SWING_EVERY_BARS` (8) a new amount from
  `SWING_CHOICES` (0-0.26) is glided to by `SWING_GLIDE` (0.4) per bar; `rh_swing` reports, `rh_swing_set` (tests)
  sets it. **Arrangement moments** (step 3): after each bar's pick, at least `BREAK_MIN_BARS` (8) apart, chance
  `BREAK_CHANCE` (0.2), never on a fill bar, the next bar may be sparse (`rh_brk` 1 hats only, 2 no kick, 3 downbeat
  kick + hats), applied from tick 0 (`rh_brk_next`: the engine picks the next bar before tick 15's own hits).
  `rh_break` reports. **Flourishes** (step 4): per 1000 found hits `FS_FLOURISH` (25, 25) play backwards
  (read end -> start, the envelope swelling over its length then a 15 ms stop) or at half speed (twice as long, fading
  twice as long); the chances are values `fs_rv`/`fs_hf` (set at load; `fs_flourish_set` sets both, tests). Test lesson: Pd seeds every [random] from a process-wide counter, so adding objects reshuffles
  which ghost snares (0.22, ~1-2%/16th) land where in later tests: count learned snares by their velocity.
  The slot switch is a `[set $1(` message (a `makefilename set ...` symbol was ignored: until Oct 12 every voice
  played fs_00 only, and the snare/hat were silent without a kick). `rhythm_src` ("Beat sounds", default 1 =
  found; 0 synth, 2 both): found mode plays the synth at `FS_PLACEHOLDER` (0.25) until the first catch, then never.
  A mic pop is not kept: louder than `FS_POP_DB` (-6 dBFS) with the lows within 6 dB of the whole (Samuel's
  "explosive" snap logged at +8 dBFS, lows 0, highs -18; real knocks -16 to -42 dB; snaps at the mic -1 to -14 dB but
  carried by their highs, kept as hats). Each catch's levels go to the event log (`fs_levels`: all, lows, highs), a dropped pop as `fs_caught 3` ("Skipped a mic pop").
  The catcher has its own detector (`fs_det`): in a loud room (average > -35 dBFS) a 6 dB jump counts (else 10,
  like the glitch cloud's, which is unchanged). Its audio is switched (`fsound`,
  on while rhythm_src x beat_level > 0). Reports `fs_caught <role>`: the Now line shows "kit K2 S1 H3", the event
  log each catch with "kit K3 S2 H1 · 24 caught" (the slots fill to 3, the total keeps counting). Pd lessons again: a running max needs its own output fed back; a stored decay never banged was 0.
- **Found melody** (Samuel, Oct 12: "can we use the found sound for melodies"; `add_found_note`, `melody_src` "Melody
  sounds" in Music, noPreset, 0 synth / 1 found (default) / 2 both): every melodic note (chimes, arpeggio, groove,
  motif) goes through the 4 chime voices; each has a found twin `fm<k>_*`. A note plays a caught slice (snares/hats
  preferred, kicks only if nothing else) at note / `FM_REF_HZ` (600; kicks / `FM_KICK_REF_HZ` 150, so a knock is
  pitched up to the note; rate 0.5-4) as a short strike (5 ms attack, band-passed around the note, `vcf~` Q 1.2,
  so neither its own low pitch nor its harsh top fights the note, `FM_RAW` 2.5) that rings one `vcf~` resonator on
  the note (Q from the chime's fade, 60 dB over cdec; drive `FM_RES` 18 x Q, kicks x `FM_KICK_GAIN` 0.45). Samuel
  (Oct 12): in key, but "could sound rounder" and "a little loud" -> the octave resonator went, level down. A
  delay-line string was not possible: Pd's feedback needs a block (64 samples), too slow above ~750 Hz. An automatic
  level (`env~` every 5 ms, only down, 0.9 of the way to `FM_LEVEL_DB` 85) keeps a clap and a knock 2-6 dB under the
  synth chimes, then tanh at 0.7 (without it every found note hit the limiter). **Chime character** (`chime_char`,
  Music, in presets, default 0.5; Samuel: the found sounds should *be* the chimes): toward 1 the hit gets
  x(1 + `FM_CHAR_RAW` 6) louder and its band widens (Q 1.2 -> 0.3), the ring `FM_CHAR_RING` (0.85) quieter and
  `FM_CHAR_SHORT` (0.7) shorter. Measured with a clap: the note's share in the tuned ring 0.67 -> 0.05; at 1 the
  notes are ~4 dB quieter by rms (short hits at the limiter; more lift only squashed them). Found mode plays
  the synth until the first catch. Catching and the recording audio now run when the beat OR the melody needs them
  (`fs_need` = rhythm_src x beat_level or music_on x melody_src). Each voice is its own switch~ group `fmv<k>`, on
  at its note and off cdec + 600 ms later (like the glitch voices); the mix is group `fmelody`. Cost (desktop,
  everything on): the found melody ~8% of the patch, the whole patch ~10% less than with always-on voices. Phone,
  everything on (Music, beat, found kit and melody, before the per-voice switches): audio thread 65-74% of a core. Tests use
  melody_src 0 unless they test it.
- **Learned groove** (roadmap 16 C4, replacing "rhythm memory": with the beat always on it never stopped cold
  anyway): at each catch the spot in the bar is noted (the last `tick16`, +1 past half a 16th: `fs_pos`), and when the
  slice is filed, `rh_heard[role*16+spot]` gains `FS_HEARD_ADD` (0.8, max 1). Every bar all 48 spots keep
  `FS_HEARD_KEEP` (0.55); a spot >= `FS_HEARD_MIN` (0.3) plays that role at 0.9x its value on top of the pattern. So
  claps on one off-beat put snares there from the next bar, echoing ~2 bars after the clapping stops. Tests sync on
  the clock's own ticks (the harness runs a little audio while setting a patch up, so bar 0 isn't at load).
- **Glitch loops** (roadmap 16 C5, `add_glitch_loop`; `beat_glitch` "Glitch loops woven into the beat", Walking beat,
  default 0.4, in presets): on `gc_mode` (a glitch fired) one bar of the glitch voices' own sound (`gc_pre_mono`,
  before the glitch level) is recorded into `gl_stage`, noting its 16th; when done, a take whose peak is >=
  `GL_MIN_PEAK` (0.02) is copied to `gl_loop` (quiet free-clock takes on near-silence used to overwrite good loops),
  and from then on it plays one bar every bar at that 16th inside the beat mix, keeping `GL_KEEP` (0.65) per bar,
  until a new loud take replaces it. Audio switched (`gloop`: beat_glitch x beat_level x gc_amount > 0).
- **Dropdowns keep their value** (fixed Oct 12): rows are created at their stored value and a Spinner selects it
  before its listener is set; a Spinner reports its first entry as selected on first layout, and folded rows aren't
  refreshed, so key and scale kept snapping back to C major.
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
  in with the arpeggio (latest one wins); standing still it plays at once. Samuel liked it on a walk (Oct 9).
  **Synced to the beat** (Samuel, Oct 12: "it should be on the same quantization as the drums"): while the walking
  beat runs on its tempo clock (`beat_on`, `beat_level` > 0, `beat_follow` 1; `s msync`), walking or standing,
  sudden-sound chimes wait for the clock's next 8th (tick16 even), the still pattern rolls on the 8ths (its chance
  scaled by 8th/250 ms, so the density holds), and motif notes go to the nearest 16th (`pipe`). Arpeggio and groove
  were already on the pulse. Harmony answers stay live, pad changes free. Beat off or "Your steps": as before.
  **Pad register** (`music_pad_reg` Low/Mid/Both, default Both, noPreset; Samuel's idea, he likes it: deep without overpowering): a bass voice (sine + 0.35 2nd + 0.15
  3rd harmonic, folded to 65-131 Hz) on the key root, moving to the chord root on 40% of chord changes; note changes dip out
  and back in (no slides); each footstep ducks it 60% while the walking beat is audible. It rides the pad level/swell.
  **Pace tiers:** `ARP_PATTERNS` run calm -> busy; each bar picks one near the pace (`mu_pace_f`) or a neighbour, never
  the same twice; rests 25% strolling -> 5% brisk. **Step strength:** StepDetector compares each bump's peak with the
  walk's average and sends `step_strength` (0.5 usual, one step of lag) before `step`: it opens the hi-hat (louder,
  25-95 ms), lifts kick/snare (0.8-1.2x) and the arpeggio note. **Groove:** after 30 s of steady steps (within 15% of
  the usual interval; >30% off or a pause starts over) the app sends `groove 1`: a soft note (45% of the arpeggio,
  fading in over 4 s) joins on every half-step, a third above the last arpeggio note.
  The arpeggio's pace swell starts at 40% (was 18%; Samuel found strolling too quiet). The hat uses `step_hit`, sent
  once the step's own bump is over (before the hat plays), so a stomp opens its own hat (amp 0.1+1.2s^2, decay 20-220 ms).
  **Uneven walking** (Samuel: drums "get tripped up"): a bump sooner than 65% of the usual interval is skipped as extra
  (scuff, heel-toe, pocket knock), unless skipped bumps sat halfway (+-7%) between steps, which means the pace doubled.
  `beat_sure` (0.4..1, -0.3 per step >30% off, +0.15 per even step) softens the drums while the rhythm is uneven.
  **Room notes sound** (`res_src` Ring / Found (default) / Both, Music, noPreset; Samuel Oct 12: the found sounds
  should be the bells): Found = each sudden sound (`fs_det_sel`, not in a pocket, at most one per `RNF_GAP_MS` 180)
  plays a caught sound on a chord tone from `RES_NOTES` (`mchord` + octaves x `scale_n` + step) through
  `add_found_note(prefix="rf")` (2 voices, groups `rfv<k>`, the Chime character applies), with its own level control
  and soft limit (`RNF_GAIN` 0.08: level with the ring) times the Room notes slider. The ring resonators run only
  unless Found only (`rn_ring` in the roomnotes switch). Catching (`fs_need`) also runs for it.
  **Harmony** (`music_harm`, Music section, default 0.6, in presets; Pocket world 0; 0 = nothing answered): `sigmund~` tracks
  the (hushed) mic; a pitch in C2-G#7 (sigmund~ reads hiss as ~MIDI 123), steady within 0.6 semitone for 12 frames (~130 ms;
  up to 2 misread frames in a row are forgiven, only good frames set the pitch) and 6 dB above the room's quiet (`mthr`) gets
  an answer from the pad's chord (`mchord`; chord notes = root, +2, +4 steps; heard pitch snapped via the `pc_deg` table):
  the nearest chord note at least 2 steps above it plus an octave (below E5) or at least 2 steps below it minus an octave
  (whistles, birds). Samuel asked for this so it never doubles his note (the first version folded into C4-C5 and blended).
  Soft organ (1, 0.5, 0.3, 0.15 harmonics), held while the sound lasts (150 ms in, 1.8 s out), two voices taking turns.
  Notes go to `s harm_deg`; the "Hearing:" log line counts them. Pd's console goes to logcat tag `Pd`;
  `HARM_DEBUG=1 python3 tools/make_patch.py` prints pitch/loudness 3x a second (do not ship it).
  Test harness: call `e.listen(...)` once with all names (a second call leaks the first binding into later engines).
  **Your voice as the harmony** (Samuel, Oct 12: close harmony, one voice, default "Your voice"; `harm_src` "Harmony
  sound" Organ / Your voice / Both, Music, noPreset): the same detection, but the answer is a pitch-shifted copy of
  the mic (`hv_*`, a two-grain delay shifter like the Pitch effect) on the close chord note: the organ's choice
  without the octave jump (`mu_hm_vdeg`: a third or more above a voice below `HV_SPLIT` (60, middle C), a third or
  more below from there up and for whistles: Samuel heard a chipmunk singing high, and most women's and children's
  voices sit there; a downward shift only darkens a little). The interval (heard
  pitch -> chord note, `harm_semi`) is set at note-on and held, so the copy follows vibrato. Grains are an even
  number of the heard note's periods near `HV_WINDOW_MS` (40): fixed-length grains on a steady tone half-cancelled
  at the crossfades (energy at 258/266 Hz instead of 262, a warble); in step they are clean and a third louder.
  `mu_hm_vwr` writes `hv_buf` all the time; the grains are group `hvoice`, on at note-on, off `HV_RELEASE_MS`
  (400; the organ's 1.8 s would shift the room too long) + window + 100 later. `HV_GAIN` 0.7 x Harmony. The organ
  voices are group `horgan` (music_on x music_harm x `harm_organ` = harm_src != 1). Tests use harm_src 0 unless
  they test it.
  **Found pad / bass** (Samuel, Oct 12; `add_found_pad`; "Pad sounds" `pad_src` Synth / Found (default) / Both,
  "Bass sound" `bass_src` Synth (default) / Found, Music, noPreset): when the Harmony tracker hears a steady pitch
  (its note-on), a `FP_TAKE_S` (0.6 s) take from `FP_PREROLL_MS` (180) earlier is recorded from `hv_buf` (group
  `fprec`) and kept if the note is still held at its end, with its pitch (`fpad_f0`), a peak gain (`fpad_g`), in
  `FP_SLOTS` (2) round-robin tables `fpad_<n>` (`fpad_n`: count, newest); never in a pocket. Each pad set
  (`fpad<k>` groups, 4 voices `fp<k><i>_*`) takes the newest take when it takes its chord; each voice is two
  `FP_GRAIN_MS` (120) grains, a new one every half grain, starting a whole number of the take's periods from where
  the playing grain is (so a steady note stays steady), wandering in `FP_LOOP_S`, rate = chord note / take pitch
  folded within a tritone (`FP_GAIN` 0.075: as loud as the synth pad). Each set's sound (synth or found, `fpw_m`)
  is latched at its chord change (a new take joins at the next one; a fading set is never cut; a Pad sounds change
  re-latches at once); the switches (`fpw_*`: active x register != Low x mode) run only what is heard, so with Pad
  register Low no pad set runs. The found bass (`fb_*`, group `fbass`) is one such voice on the bass note, not
  folded, `FB_GAIN` 2.8; it starts on the current note when switched on; the synth bass gives way. The tracker and
  detection now run while Harmony is up OR a found pad/bass wants takes (`harm_run`; the voice harmony still only
  while Harmony > 0). The event log says "Kept a held note for the found pad (A3)". The found bass has faint grain
  sidebands (~16 dB down) when pulled far down; untested on the phone.
  **Melody rhythm** (Oct 15, from Samuel's other chat, levels 1+2; `mel_rhythm` Music, Off (as before, default) /
  Straight / Dotted / Mixed, noPreset; `add_melody_rhythm`; Pd test "melody rhythm:"): one-bar cells
  (`MEL_CELLS_STRAIGHT`/`_DOTTED`, note lengths in 16ths, negative = rest; Mixed = both sorted by onsets) on the
  clock's tick16 (always running). Each bar picks one near `rh_drive` (+-1, never the same twice). On an onset:
  `mlen` = the ring (len x 16th x 1 + 200 ms, 250-3000; `mu_tim_dec` uses it instead of the random 0.9-2.6 s, and
  the found voices read the same cdec), then walking (`mwalk`, from mu_q_walk/stop) the arpeggio plays its next
  note (the per-pulse trigger is closed: `mu_mr_arp`), standing the still pattern rolls (its own 250 ms / 8th
  rolls closed: `mu_mr_stf`/`mu_mr_sts`) with `mu_p` inlet 2 = bar / onsets, so the density holds. Sound-triggered
  chimes, motif replays, groove, density memory unchanged. Reports `mel_cell`, `mel_note <tick> <len> <ring>`.
  Found on the way and fixed (Samuel: "fix the chime density first"): `mu_p_len` (the still pattern's "8th / 250"
  scaling when synced) was written into its cold inlet, so synced chimes came ~17-25% more often at 150 BPM (fewer
  under 120); Pd test "still pattern:" (free vs synced at 150 and 90 BPM within 0.85-1.1). Feel untested. Level 3 (phrase logic) is a later note.
  **Melody phrases** (Oct 15, level 3; `mel_phrase` Music toggle, default off, noPreset, needs Melody rhythm;
  `add_phrases`; Pd test "melody phrases:"): bars count A A' B A (`mph_bar` 0-3, -1 while off, set at tick 0 before
  the cell pick); A' and the last A reuse A's cell (`ph_row`). Before each cell note the phrase stage sets
  `mphdeg`/`mphon` (cleared with mlen): A and B make a note one step from the last (two `PH_STEP2_PCT` 30% of the
  time), within CHIME_SPAN of the register middle (walking: scale_n + mchord + 3, the arpeggio's; standing: the
  brightness note), snapped to the nearest chord tone on ticks 0 and 8; A stores it in `ph_a[tick]`; A' and the
  last A replay ph_a, A''s last onset (`mel_lo`) goes to the chord root nearest A's last note. `mu_pick_ph` and
  `mu_arp_ph` take mphdeg while mphon (sound-triggered chimes and motifs never set it). Standing, only the chimes
  whose chance comes up play, so a phrase is heard in part. Reports `ph_note <phase> <tick> <step> <mchord> <n>`.
  Feel untested.
  **Density memory** (roadmap 8, no slider): `value mdens` = notes played lately (a chime +1, an arpeggio note +0.3
  so the walking bed doesn't silence chimes on the beat), fading over 8 s. Sudden-sound and still-pattern chimes play
  with chance 1/(1+(mdens/10)^2); the arpeggio rests up to 30% more past 16. Busy test room: 1.45 -> 1.0 notes/s.
  `density_on 0` (tests only) turns it off.
  **Motif memory** (roadmap 12, `MotifMemory.java`, test W): the patch reports chimes (not arpeggio notes or replays)
  on `s chime_note`; the app keeps the last phrase of 3-6 chimes less than 2.5 s apart. After 8 s without chimes,
  standing still, at most once per quiet spell and per 30 s, with chance 0.6, it sends `motif <step> 0.45` for each
  note: the phrase moved -2..+2 scale steps (sometimes 0), one note bent +-1 (40%), the rhythm x0.8-1.25. It counts
  for density memory. The event log says "Motif comes back". (Java's Random: small seeds all start near 0.73.)
  **Key drift** (`music_drift`, Music, default on, noPreset; roadmap 12): every 3-6 min while the music plays the
  home chord moves to a related one on the same notes (`value mdrift` scale steps added to each pad pick, mod n), 60%
  of the time back home when away. Allowed homes per scale (`drift_options`): every pool chord moved there must not be
  diminished (C major: C, D, G, A minor feel; minor: 0, 2, 3, 6). No contrast chord while drifted; the bass's home
  note follows. A scale change resets it; switching it off brings home back at once. `drift_now` (tests) drifts now.
  Pattern picker fix: a repeated pattern now moves toward the pace's own pattern (it used to bump upward, so a stroll
  sometimes got a mid-level pattern).
  **Register from sensors** (`music_follow`, Music, default on, noPreset, app-only `noPd`; `NoteRegister.java`, test W):
  room-relative light < 0.25 -> 2 scale steps down + warm, > 0.75 -> 2 up; a pocket -> an octave down + warm; climbing
  (climb > 0.5) +2. A new register must hold 3 s and changes come at most every 8 s. The app sends `music_register
  <steps>` (added to chimes, arpeggio, groove and motif notes on their way to the voices; the reported degrees stay
  unshifted) and `music_warm 0|1` (chime low-pass x0.45). Pad and bass stay put. Compass-picks-the-bass was left out.
  **Stop breath:** 1.2 s after the last step the pad+bass ease to 55% over 2.5 s, then return over 8 s (a step
  brings them back in 0.8 s); only steps start it.
  Music joins after the filter, so chorus/flanger/phaser/tremolo/reverse/glitch/echo/reverb/spatial shape it; pitch/ring/crush/dist/filter do not.
  It no longer follows the Dry level (Samuel, Oct 13): Dry scales the mic just before the music joins (`filtered_dry`;
  the chain from there to `voice` is linear, so the mic sounds as before) and the echo gets the part Dry took away
  (`echo_mic_rest` = mic x (1 - dry)), so at Dry 0 it still repeats the mic. Only the real room tells us if the tuning is right — expect further tweaks from Samuel's reports.
- **Tabs** (step D, Oct 12): Sound (presets/shortcuts, XY pad, input, effects), Music (Rhythm, Music), Realms, Scenes,
  Setup (audio devices, appearance, behaviour, reset, about); the strip is the bottom card's top row (selected = accent
  pill), each tab keeps its scroll, the last tab is remembered (`UiSettings.tab`). While a scene plays, Sound/Music/
  Realms show a notice. The pad view moves between Sound (XY pad) and Scenes. **Realms** = Auto worlds renamed on
  screen only: internal ids stay "world"; built-in presets are now "X realm" and `Worlds.renamedBuiltIn` migrates a
  stored "X world" choice on load (test W). **Ingredients** (`Worlds.GROUPS`: Rhythm, Music, Echo, Reverb, Glitch +
  reverse, Color, Motion, Space and dry level; `uses`/`setUses`, prefs `skip_<world>_<group>`, cleared by Reset): a
  Realm leaves a group it doesn't use at the user's values; `touched` tracks what a Realm actually set, so going home,
  a stop, or the next Realm leaving a group alone gives back only that (test W). Under each Realm "What it changes:
  everything / all but ..." folds open to the switches. **Polish:** a dot after a slider's label while a mover
  pushes it (`Modulation.isMoving`, checked with the Now line once a second); a Realm cue (`realm_cue 1|0` from
  AudioService on each Realm change; Samuel asked for "a dreamy warp": a tone gliding A4 -> A5 over 900 ms into a
  Realm, A5 -> A4 back home, Realm to Realm (`realm_cue 2`, Samuel: "a lateral, sideways warp") a swerve around E5
  (-6%, +6%, back) sweeping from one ear to the other (random way; the others stay centred), with a 1.007 detuned twin and a quiet fifth, 300 ms swell, 1.2 s fade, a touch of echo
  (320 ms, feedback 0.4, wet 0.4; Samuel), peak ~0.05 after the limiter, group `cue`; `cue_sound` "Realm change sound" in Behavior/Setup, noPreset, default on); content descriptions on
  tabs, sliders, lock boxes and the pad; the step accelerometer tried at 100 Hz and put back to 200 (Samuel, Oct 13:
  walking was noticed too late).
- **Screen:** a bar pinned to the bottom (thumb reach while walking) holds the status, a "Now: <world> · why" line
  (night/walking/pocket/room words from `Worlds.room*()`, refreshed 1/s while visible), Start/Stop, Hold world
  (`Worlds.setHeld`: the selector keeps listening but nothing changes; a stop lets go) and Save sound (a preset named
  like "Thu 8-12" from the live values). Only Input & output and Music start unfolded. `refreshRows` skips rows in
  folded sections (they catch up when opened).
- **Reset everything button:** `ParamStore.resetAll` + `Worlds.resetSettings` + `AudioSettings.reset` + `SceneSettings.resetAll`, only after confirmation.
  Keeps saved presets, imported scenes and appearance (and brings back any deleted built-in scene). Nothing may ever reset settings except that button.
- **Diagnostics** (roadmap item 2, Oct 13; `add_clip_watch`, `ClipWatch.java`, test D): once a second the patch
  sends `diag_clip_in`, `diag_clip_gain`, `diag_clip_out` (out last) = how many `CLIP_WINDOW` (512-sample, ~12 ms)
  stretches held a sample at/over full scale: the adc~ as it arrives (`CLIP_IN` 0.99), after Input gain (1.0; float,
  the compressor soaks it up, so it is informational) and the output limiter's input (1.0). abs~, `-~ thr`, `*~ 1e9`,
  `clip~ 0 1`, one env~ each. ClipWatch: a warning starts at 3 stretches within 5 s and ends after 5 s without any;
  "episodes" = runs of seconds with any in the last minute. Setup tab "Diagnostics" (folded): the mic really in use
  (`AudioDevices.inputInUse`, from this app's own `getActiveRecordingConfigurations`), call-mode note, output label +
  rate, mic level (after gain) with a bar and the gate, episode counts. The status line says "Mic overloading" while
  the input warning is on (only the mic's own overload: Input gain can't cause real clipping, it is applied in float).
  Event log: "Mic overloading", "Mic overloaded for a moment" (at most every 10 s), "Output limiter working hard".
  Scenes send no counts (the section says so).
- **Calls and other audio** (Samuel's rule): the app never requests audio focus (Start must not pause the user's music).
  `AudioService.checkForCall` reads the audio mode every 0.5 s: call/ringing/VoIP -> `computeAudio(false)` until it ends
  (MODE_IN_COMMUNICATION is ignored while our own Bluetooth mic set it). An `AudioPlaybackCallback` counts the listed players
  (Android lists only playing ones and hides uid/device from other apps; Moto G: 1 alone, 2 with Musicolet); more than our own -> `duck 0.3` (~3 dB, 600 ms ramp, after the limiter; scenes
  get `#volume` scaled instead). Only slight: the app's effects must still be heard.
- **Start path:** the Bluetooth-mic link wait runs on a background thread (`starting`, `startGeneration` cancels it on
  stop). `patches` and `scene_lib` are copied only when the install changes (`.copied` stamp = lastUpdateTime).
- **Input gain/gate stay one setting for all mics** (Samuel, Oct 9): per-device values were rejected because Android names
  USB/Bluetooth mics generically ("USB-C HEADSET"), so two headsets could be confused. Earbud mics read ~15-20 dB quieter
  than the phone mic (USB-C earbuds: -65 vs -45 dB) and need more gain and a lower gate. The event log records the devices
  asked for and every listed mic with its rates/channels at each start.
- **No recording audio** to files (Samuel, Oct 9): the mic never touches disk. Revisit only for a feature that unlocks a lot.
- **Echo follows your steps** (`echo_sync` Off/1/half/quarter step, default half, in presets): while walking the echo
  time is the averaged step interval (20 ms grid, so step wobble doesn't warble it); 2.5 s after the last step the
  slider's time returns.
- **Dice morph:** with audio running, Randomize glides there over 6 s (`ParamStore.morphTick` from the service tick,
  smoothstep; switches/menus flip halfway). A slider moved meanwhile (hand or world) drops out of the glide; undo,
  nudge, presets and reset stop it. Stopped audio: Randomize jumps as before.
- **Glitch cloud** (Glitch section; `gc_amount` default 0 = off and no CPU, `gc_level` 0.7, kinds by the glitch matrix below;
  roadmap 5b, after dblue Glitch): the hushed mic goes into a 4 s ring buffer (memory only). Triggers: a sudden sound (5 ms
  meter jumps 10 dB over its ~0.25 s average and > -45 dBFS; chance = Amount; then a rest of 2.4 s at Amount 0 -> 0.6 s at 1)
  and a free clock ((2-8 s)*0.6/(0.2+Amount), reset by sounds; it never starts the rest, so a sound always wins). Walking
  (a step in the last 2.5 s): it waits for the next step or half-step, and a stutter slice is a quarter step. Kinds:
  stutter (slice 60-180 ms, or quarter step, x4-7), reverse (plays back the last ~2L ms backwards, after waiting until
  the sound was heard), shuffle (a random slice 0.25-3.25 s old). One voice:
  read position = d0 + a*t - c*fmod(t,S) from plain objects (expr~ cost 3x more), 3 ms slice windows, a new
  glitch fades the old one 4 ms first. Random pan per glitch; it joins both ears before the reverb and feeds it too.
  **Stretch** (`gc_stretch`, 5th kind, roadmap 3 "Ghost capture"; own voice `gc2_*`): the sound smeared at rate
  0.08-0.25 (4-12x slower) for 1.5-3.5 s (capped by the 4 s buffer) in two 100 ms Hann grains, pitch unchanged,
  40 ms in and 600 ms out. The Ghost world turns on stretch + reverse only (Amount 0.45, level 0.8).
  **Glitch matrix** (Samuel, Oct 10): `gc_pct_stutter/reverse/shuffle/stretch` (0-100 %, defaults 35/25/20/20)
  share each chance; together at most 100 and what's left is the chance nothing happens. `Param.budget("glitch_matrix")`:
  the UI stops a slider at `ParamStore.budgetRoom` (others never move), the dice scale picked shares to fit (locked ones
  kept); past 100 (presets, movers) the patch treats them as proportions. Amount = how often a chance comes. Ghost world
  50 reverse / 50 stretch. Under the sliders a bold "Glitch budget: 80% used · 20% left to silence" line
  (`MainActivity.budgetLines`, updated on slider moves and in refreshRows). No `;` in Params.java comments (the test parser stops there; bit us again).
  **Tape stop and a turntable Scratch were built and removed** (Samuel, Oct 10: not wanted in the mix; git has them).
  **Voices switch on only while they play** (groups `gcv` = gc0_*, `gcs` = gc2_*, `sw_gcv`/`sw_gcs` sent at each
  glitch, off L+100/L+700 ms later); only the 4 s buffer runs all the time. Two voices work fine this way.
  Width (Samuel: "around me but not wide enough"): each glitch sits 45-100% out to one side (balance law: near ear
  full, far ear quieter) and the far ear is up to 0.6 ms later (`delread~`, not `delread4~`: that tripled the cost).
  Cost (desktop, vs the patch before it): Amount 0 +3% (echo scatter), glitching nonstop +11% (reverb on +70%, music +310%);
  phone with Music on: 37-39% of a core at Amount 0 and at full, i.e. lost in the noise.
- **Echo scatter** (`echo_scatter`, Echo section, default 0.5, in presets; Samuel's idea): every repeat lands
  somewhere else between the ears. The echo returns every T ms, so a new place is picked every T ms (snapshot of the
  delay time): at least half the width from the last one (else the other side), 15 ms move. The wet signal now joins
  both ears after the beat (and still feeds the reverb); at 0 it is centred as before. ~+5% of the idle patch, always on.
  **Pd lessons from it:** a value stored with `[f]`'s right inlet never reaches anyone: send the message to every
  consumer's cold inlet. `[pipe]` with several arguments splits a list into outlets (use `[list split]` + `[del]` + `[list]`).
  A second voice in the same switch~ group was silently lost (never explained); voices in their own groups work.
- **Switchable DSP:** make_patch.py groups reverb, pitch, chorus, flanger, phaser, reverse echo, Room notes and music
  into `[switch~]` subpatches (`Patch.group` + `add_switch`), on while their level > 0, off 3x smoothing + tail after.
  Room notes fade in 200 ms on switch-on. Phone: music on ~39% of a core on the audio thread, music off ~18%.
- **CPU (Oct 12, Samuel: "is there any way we can optimize it"):** measured by stripping one object type at a time
  (desktop, everything on): `sigmund~` was ~32% of the patch, oscillators ~13%, `vcf~` ~10%, `delread4~` ~6% (all
  moving delays, kept), `expr~` ~3%. Now: Harmony's tracker runs at half the sample rate in its own group `harmsig`
  (`add_switch(..., block="64 1 0.5")`, a `lop~ 6000` before it; `HARM_HOP` 512 / `HARM_NPTS` 1024 there = ~21 ms
  frames over ~43 ms, 7 steady frames ~150 ms; an 80 ms blip still plays nothing) and Harmony is its own group
  `harm` (music_on x music_harm); each synth chime voice
  is a group `chv<k>` (on at its note, off cdec + 300 ms later), each pad crossfade set a group `pads<k>` (with its
  `mu_xf<k>` ramp: leaving the ramp in the music group made a DSP loop between groups, "DSP loop detected"), the
  limiters are `soft_limit` (rational tanh from plain objects) and the zero-crossing sign is `*~ 1e9` + `clip~`.
  Result: -34% everything on, -49% with Harmony 0; with Samuel's own settings (reverb 0.6, phaser 0.4, chorus 0.5,
  pitch 0.25, glitch cloud full, music, beat) -22%. What's left there: music 37% (Harmony 18 of it), reverb 13%,
  phaser 10% (its coefficients every 4 ms with [expr]; 8 ms would zipper at 5 Hz), glitch cloud 7%, pitch 7%. Room notes stay always on (with react < 1 their input never
  closes). The step accelerometer stays at 200 Hz (~7.5% of a core, own thread): 100 Hz noticed walking too late (Oct 13).
- Presets store: sliders, movers, music pad/notes/tone/follow, beat, dry. A slider kept out of presets keeps its mover out too
  (`Params.withMovers`), or loading a preset or world switched it off. Not stored: gain/gate/compressor, smoothing/nudge,
  music on/key/scale, locks, worlds choices, audio device, scenes, appearance.

## Desktop stream mode (`desktop/`, Oct 16)
- Samuel wants the app on Linux as background music for his stream (no sensors, Set tempo, Realms by room level).
  Step 1 done: `desktop/run.sh` runs the built-in patch in libpd for Java (`make javalib` in tools/.libpd, via
  `desktop/fetch_libs.sh`, with JNAJack 1.4.0 / JNA 5.14.0 / org.json 20240303 from Maven Central, SHA-1 checked,
  not in git) through PipeWire's JACK layer (`pw-jack`). Mic (+ optional game sound = a sink's monitor) mixed to the
  patch's one input; output to its own null sink "pdscenes" (description "PdScenes", made with pactl, removed on
  exit), which OBS records with Audio Output Capture. The JACK client is "PdScenes Engine" (JACK port names are
  device *descriptions*, so the sink's "PdScenes" would clash). Routes (output, mic, game, --listen) are re-checked
  every 2 s and reconnected; devices match by name or part of name/description. Never hears itself: the sink is
  never an input, --listen refused/skipped while the game sound comes from that sink. Typed lines change settings.
- Samuel's machine: PreSonus AudioBox Go (its USB link drops now and then; nodes come back renamed ".3"/".4"),
  EasyEffects on the mic (OBS reads Easy Effects Source). Through the patch the EasyEffects source (peaks at 0 dBFS)
  sounded overdriven; the AudioBox directly with the compressor off "sounds amazing" -> `DESKTOP_DEFAULTS`
  comp_thresh 0. Pd 0.55.2's expr prints "realloc called with N bytes" to stdout (filtered in run.sh).
- **Window** (Oct 16; `DesktopApp` tick + Pd receiver, `DesktopWindow` Swing, `DesktopEngine` routes): compiles the
  phone's 15 logic classes unchanged (`run.sh` SHARED list) with `desktop/shim/` stand-ins: android.content.Context
  (files dir ~/.local/share/pdscenes, prefs ~/.config/pdscenes/<store>.json via JsonPrefs) and AudioService
  (isRunning). Tabs Sound/Music/Realms/Presets/Setup built from Params (sections as on the phone; mover params,
  section mover switches and `PHONE_ONLY` hidden), rows refreshed 4x a second from ParamStore. The tick is the
  phone's mover tick minus sensors: `PdBase.pollPdMessageQueue()` first (desktop libpd queues messages; without it
  mic_level/tempo never arrived), morph, Modulation, realm_cue, Worlds.tick(walking/pocket false, no shake),
  CalmBuild + calm_chimes, call and response, motif. `DESKTOP_DEFAULTS` (first start and Reset): comp_thresh 0,
  tempo_mode Set. First start connects no mic (Samuel's laptop mic reads 0 dBFS nonstop) and opens Setup. Device
  menus / `mic_device`, `game_device`, `listen` commands call `engine.apply`. A loop the engine can't see: OBS
  monitoring PdScenes onto the output the game sound is taken from (UI and README say: give the game its own
  output). `desktop/test.sh` (DesktopTest): phone preset in (unknown keys ignored, clamped, noPreset not taken,
  sensor mover kept), out in the same format, settings file written. `--snapshot prefix` draws each tab to a png.
- Responsiveness (Samuel: sliders and dB readings "sluggish"): FlatLaf 3.4.1 instead of the GTK look (slow to
  draw), screen changes sent to ParamStore from a "settings" thread (latest value per id), one ParamStore.snapshot
  per screen refresh, meters 20x a second (falling 30 dB/s), 256-sample cycles (`PIPEWIRE_LATENCY=256/<graph
  rate>`; `pw-jack -p` forced 48 kHz while Pd ran at 44.1 = 9% sharp; the engine reopens Pd on a rate change).
  Pd took ~0.6 ms of a 23 ms cycle, so its lock was not the cause.
- Echo scatter in a quiet room: steady mic hiss in the echo hops ear to ear each repeat (Samuel heard it on the
  desktop; outdoors on the phone it was masked). Not a bug (only with the echo on). Fix: raise the noise gate (~-55 dB): Samuel, "raising the noise gate works fine" (README tip).
- Realms tab: "What it changes" per Realm (Worlds.uses/setUses, as the phone), phone-only Realms greyed. Cleanup
  round 1: window size/place, last tab and open sections kept (pdscenes_desktop), wider label column, the glitch
  budget line, "Mic in"/"Out" meters. Samuel (Oct 16): stem packs and scenes are not part of the desktop app; it is
  for showing the engine on stream.
- App menu launcher (Oct 16): `desktop/install-launcher.sh` writes ~/.local/share/applications/pdscenes-desktop.desktop
  (no app icon yet: the theme's audio-x-generic), `desktop/launch.sh` = flock on ~/.local/state/pdscenes/running.lock
  (a second start: notify-send and exit), log to desktop.log (one rotation), zenity on an error exit. Installed on
  Samuel's machine. The desktop stays in this repo (it compiles the phone's sources in place; split later with a
  shared library if it gets its own releases). Movers: not wanted for now (Samuel).
- Not yet: a walking/pace stand-in, more cleanup.

## Open / next
- **Ideas queue with details: `docs/ROADMAP.md`** (in-key resonators, pitch-following harmony, Ghost capture, Kinetic tiers, Unstable and Collective worlds, stems player).
- Release prep: final name + applicationId, `source_url` in strings.xml, privacy policy, Play foreground-service + microphone declarations, icon, store listing.
- Ideas, not requested: beat-offset slider if drift returns,
  location (`#loc`) scene input, unported scene objects.
- The Beta Tester Guide lives in this repo: `docs/TESTER-GUIDE.md` (tester-facing: "Dad"/"DadCraft", plain words; moved
  from Samuel's Claude Docs on Oct 12, where an older Oct 10 copy remains). When behavior changes, update it in the
  same commit or tell Samuel it needs an update.
