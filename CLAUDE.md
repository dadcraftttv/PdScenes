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
- **Mic-down protection** (`pocket_guard`, main, noPreset, default 0.6; 0 = no change): Samuel found mic-end-down pockets
  rustly but mic-up pockets fine. `PhoneContext.micDown()` (gravity along +y averaged ~1 s, hysteresis 0.5/0.3) and
  AudioService sends `pocket_down` = pocket && micDown. The patch adds guard*12 dB more cut and crossfades in a 2x `hip~ 300`.
- **Flux needs a lively room:** loud AND the level swinging >3 dB around its average (leave <2). Running water hit Flux and
  became pure fuzz; a steady roar now leaves the user's own settings. Flux preset was softened (dist 0.2 soft, crush 0.15,
  ring 0.15, freeze mover depth 0.4) so the room still comes through.
- **Walking beat:** StepDetector sends `step <interval>` messages; foot drift was fixed and confirmed on the phone.
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
- **Found-sound kit** (roadmap 16 C2/C3, `add_found_kit`; Samuel: "the sounds around you become the rhythm"): on each
  sudden sound (the glitch cloud's detector, `gc_det_sel`, always running; never while in a pocket) a `FS_SLICE_S` (0.25 s) slice of the hushed
  mic from `FS_PREROLL_MS` (15 ms) earlier is recorded (`tabwrite~ fs_stage` from a 100 ms `fs_buf`) while env~ maxima
  of all/lows (<150 Hz)/highs (>4 kHz) are kept; then filed: below `FS_MIN_DB` (-45 dBFS) dropped, lows within 6 dB of
  the whole -> kick, highs within 6 dB (3 caught no real taps) and lows 15 dB under -> hat, else snare; copied (`array get/set`) into the
  role's next slot `fs_<role><slot>` (3 per role, round robin, memory only) with a gain levelling its peak to 0.5
  (`fs_gains`) but its loudest 10 ms no higher than `FS_RMS_TARGET` (0.3; a snap at the mic overloaded it into a
  clipped, dense slice that played as a "deafening boom"), and the found drums get `FS_MAKEUP` (3x) into a tanh
  limit at `FS_LIMIT` (0.9): a thump kit ~5 dB under the synth kit, a clipped boom at its level, never above
  (Samuel, Oct 12: "not quite present enough"). `fs_filled` counts. Voices (one per role): a random filled slot of
  its role through `tabread4~` at rate 0.8/1/1.3, lop 3.5k / hip 160 / hip 1.5k, level 1/0.8/0.7, decay
  260/200/hat's own; a role with nothing of its own borrows any caught slot, so one catch makes the whole kit found.
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
  synth chimes, then tanh at 0.7 (without it every found note hit the limiter). Found mode plays
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
  It follows the Dry level. Only the real room tells us if the tuning is right — expect further tweaks from Samuel's reports.
- **Screen:** a bar pinned to the bottom (thumb reach while walking) holds the status, a "Now: <world> · why" line
  (night/walking/pocket/room words from `Worlds.room*()`, refreshed 1/s while visible), Start/Stop, Hold world
  (`Worlds.setHeld`: the selector keeps listening but nothing changes; a stop lets go) and Save sound (a preset named
  like "Thu 8-12" from the live values). Only Input & output and Music start unfolded. `refreshRows` skips rows in
  folded sections (they catch up when opened).
- **Reset everything button:** `ParamStore.resetAll` + `Worlds.resetSettings` + `AudioSettings.reset` + `SceneSettings.resetAll`, only after confirmation.
  Keeps saved presets, imported scenes and appearance (and brings back any deleted built-in scene). Nothing may ever reset settings except that button.
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
  moving delays, kept), `expr~` ~3%. Now: Harmony's tracker hops 1024 (`HARM_HOP`, 7 steady frames ~150 ms; an
  80 ms blip still plays nothing) and Harmony is its own group `harm` (music_on x music_harm); each synth chime voice
  is a group `chv<k>` (on at its note, off cdec + 300 ms later), each pad crossfade set a group `pads<k>` (with its
  `mu_xf<k>` ramp: leaving the ramp in the music group made a DSP loop between groups, "DSP loop detected"), the
  limiters are `soft_limit` (rational tanh from plain objects) and the zero-crossing sign is `*~ 1e9` + `clip~`.
  Result: -34% everything on, -49% with Harmony 0. Room notes stay always on (with react < 1 their input never
  closes). The 200 Hz accelerometer (~7.5% of a core, own thread) is kept for step timing.
- Presets store: sliders, movers, music pad/notes/tone/follow, beat, dry. A slider kept out of presets keeps its mover out too
  (`Params.withMovers`), or loading a preset or world switched it off. Not stored: gain/gate/compressor, smoothing/nudge,
  music on/key/scale, locks, worlds choices, audio device, scenes, appearance.

## Open / next
- **Ideas queue with details: `docs/ROADMAP.md`** (in-key resonators, pitch-following harmony, Ghost capture, Kinetic tiers, Unstable and Collective worlds, stems player).
- Release prep: final name + applicationId, `source_url` in strings.xml, privacy policy, Play foreground-service + microphone declarations, icon, store listing.
- Ideas, not requested: on-screen route/clipping diagnostics, beat-offset slider if drift returns, music independent of Dry level,
  location (`#loc`) scene input, unported scene objects.
- The Beta Tester Guide lives in Samuel's Claude Docs (not in this repo). If behavior changes, tell him the guide needs an update.
