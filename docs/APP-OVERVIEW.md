# PdScenes: overview for an outside review

PdScenes is a working name. It is an open-source Android app (GPLv3-or-later) that turns the world around you into music
through headphones. It is in the spirit of RjDj, the 2008-2013 "reactive music" iPhone app, and Dimensions, its successor.
The phone's mic, motion sensors and light sensor feed a Pure Data patch that runs inside the app through libpd. What you
hear is the room around you, processed and set to music, and it changes with how loud the room is, how you move, how bright
it is and whether the phone is in your pocket.

The app is made by one hobbyist developer ("dadcraft", a synthwave musician, not a professional Android developer) with an
AI coding assistant. A few beta testers use it. It will be free on Google Play. The final name must not contain "RjDj".

This file explains the product and how it works. The code comes with it as a separate file. **Please read "What we would
like from you" and "Please don't suggest" at the end before you start.**

---

## 1. What the user experiences

1. Put on headphones (wired or Bluetooth) and press **Start**. The app refuses to play through the phone speaker, because
   the mic would hear its own output and howl.
2. You hear the room through the headphones, with effects on it. By default the sound is close to clean, with a soft
   compressor so quiet sounds come up.
3. You can switch on **Music** (it is off by default). It adds sound in a key you choose:
   - A soft **pad** of chords that drift, with an optional **bass** voice under it.
   - **Chimes** when something happens in the room, such as a clap, a door or a voice.
   - **Room notes**: the room's own sounds ring at the pitches of the current chord, through tuned resonators.
   - A **walking arpeggio**: every footstep plays a note.
4. When you walk, a **walking beat** (kick, snare, hi-hat) follows your steps. The beat is off by default. While you walk,
   the chimes lock to your step rhythm.
5. **Auto Worlds** switches the whole sound to fit your situation. Each world is a preset that fades in:

   | World    | When                                                        | Sound                                    |
   |----------|-------------------------------------------------------------|------------------------------------------|
   | Ghost    | Dark, quiet, still (night)                                  | Reverse echoes, airy reverb              |
   | Kinetic  | You are walking                                             | Rhythmic: beat, arpeggio, tremolo        |
   | Flux     | The room is loud *and* lively (voices, clatter, music)      | Edgy and glitchy, with freezes and jumps |
   | Tranquil | The room is quiet                                           | Soft, wide, gentle reverb                |
   | Pocket   | The phone is in a pocket and nothing else fits              | Muffled and warm                         |

   Priority: Ghost > Kinetic > Flux > Tranquil > Pocket. Pocket is mostly a *layer*. In a pocket, the world still follows
   night, walking and the room, and a "pocket hush" turns the mic down on top. You can lock individual sliders so the
   worlds leave them alone.
6. **Hand-tuning**: about 80 sliders in collapsible sections, listed below. Every effect slider can have a **mover**: a
   modulation source with a shape, depth and speed that moves the slider by itself (see section 3).
7. **Presets**: save, load, export and import (JSON files). **Randomize**, **Nudge** (small random changes) and **Undo**.
   **Reset everything** asks for confirmation and is the only thing that ever resets settings.
8. **Scenes**: the app can also run original RjDj scene files (`.rj` folders with a Pd patch and samples) instead of its own
   effects. It ships the four official RjDj example scenes (GPLv3), and users can import more from a file or a folder. A
   scene gets a touch pad (its cover image) plus the mic, accelerometer, compass and time, the RjDj way.
9. **Settings**: audio device pickers (input and output), appearance (light, dark or AMOLED theme), and an about page with
   licences.

### Slider sections, in screen order

- **Worlds (automatic)**: Auto Worlds on/off, which worlds are allowed, and the current world.
- **Input & output**: input gain, noise gate, compressor (threshold, ratio, make-up), pocket hush, mic-down protection, dry level.
- **Walking beat**: on/off, level, hi-hat, snare, kick pitch.
- **Music**: on/off, key, scale, pad level, pad register (Low bass / Mid chords / Both), notes-and-chimes level, tone,
  "how much the music follows what it hears", room notes.
- **Effects**, each with an on switch: echo, ring modulator, pitch shifter, bit crusher, distortion (soft, hard or fold),
  filter (low-, high- or band-pass), chorus, flanger, phaser, tremolo, reverse echo, glitch/freeze, reverb, spatial
  (pan plus the time difference between the ears).
- **Global**: smoothing (glide time for every change) and nudge strength.

### The screen today

One long scrolling screen built from plain Android Views (no Compose), in this order:

1. Title, status line and a headphone warning.
2. Start/Stop.
3. The scene row (choose or import a scene), the scene touch pad, and scene volume/mic sliders.
4. Preset buttons, Randomize/Nudge/Undo, Reset everything.
5. The Worlds section, then every slider section (collapsible, most open by default).
6. Audio devices, Appearance, About.

The code for all of this is in `MainActivity.java`, about 1,300 lines.

---

## 2. How it works

### Architecture

```
 Sensors (accelerometer, gyroscope, rotation vector/magnetometer, light, proximity, pressure)
        |                                   Mic --> libpd (Oboe, low latency) --> headphones
        v                                                  ^
 SensorInput -> PhoneContext (pocket, brightness, climb,    |  floats/messages to named receivers
                mic-down tilt, heading)                    |
             -> StepDetector (footsteps, step interval) ---+
 AudioService (foreground service, ~30 Hz "mover" tick):
     Modulation (movers) -> ParamStore (slider values) ----+
     Worlds/WorldSelector (picks a world from level, floor, liveliness, light, walking, pocket)
 MainActivity (UI) <-> ParamStore / PresetManager / Worlds
```

- **Audio engine:** libpd `pd-core` 1.4.2-SNAPSHOT (Pd 0.55.2) on Oboe, at 48 kHz (or 22.05 kHz with "RjDj timing" for
  scenes). The built-in effects are one Pd patch, `test_scene.pd`. **That patch is generated** by
  `tools/make_patch.py` (about 1,500 lines of Python that writes Pd objects and connections). Review the Python, not the
  `.pd` file.
- **Java side**, `app/src/main/java/app/pdscenes/`, about 5,000 lines:
  - `AudioService`: the foreground service. It starts and stops libpd, picks devices, watches for headphones being
    unplugged, runs the 30 Hz tick that applies movers and worlds and sends pocket state, and writes an event log.
  - `AudioDevices` / `AudioSettings`: device selection. A Bluetooth mic needs call mode (`MODE_IN_COMMUNICATION` plus
    `setCommunicationDevice`).
  - `Param`, `Params`, `ParamStore`: the slider registry, ranges, curves, flags (noPreset, noRandom, ...) and storage.
  - `Modulation`: the movers.
  - `PresetManager`: presets, including the five world presets.
  - `Worlds` / `WorldSelector`: Auto Worlds, with hysteresis, a room-floor tracker and a liveliness measure.
  - `PhoneContext`: pure logic, tested on desktop. Pocket detection (proximity plus low light), room-relative
    brightness, climbing from air pressure, mic-down tilt, compass heading.
  - `SensorInput`: registers the sensors and feeds PhoneContext and StepDetector.
  - `StepDetector`: footsteps from the accelerometer. It sends `step <interval seconds>` to Pd.
  - `SceneLibrary`, `ScenePad`, `SceneEvents`, `SceneSettings`, `TreeImporter`: RjDj scene support.
- **Bundled rjlib** (RjDj's Pd abstraction library) is in `app/src/main/assets/scene_lib`, along with player helpers
  ported from PdParty.

### Signal chain in the built-in patch

```
mic -> input gain -> level meter (RMS dB every ~5 ms) -> noise gate -> compressor -> pocket hush (+ mic-down thump filter)
    -> ring mod -> pitch shifter (two crossfaded delay taps) -> bit crusher -> distortion -> filter (biquad)
    -> [+ music: pad, bass, chimes, arpeggio, room-note resonators]
    -> chorus -> flanger -> phaser -> tremolo -> reverse echo -> glitch/freeze = "voice"
    -> (voice x dry level) + echo of voice + walking beat -> + reverb (stereo) -> spatial (ear delay, pan)
    -> soft limiter (never above 1.0) -> out
```

The music joins after the pitch, crush, distortion and filter stages so they can't push it out of key, but before the
time-based effects so they shape it.

### How the music works

- **Key and scale** (major, minor, major/minor pentatonic, Dorian, Mixolydian, Lydian, whole tone) snap every note.
- **Listening**: an adaptive noise floor means a quiet room stays quiet; chime chance rises with the cube of how far the
  room is above its floor. Onsets are jumps in level over the slow average. Brightness (zero-crossing pitch estimate) picks
  the register.
- **Pad**: chords from a per-scale pool (the home chord, its two strongest neighbours chosen by brightness, and one
  contrast chord on about 20% of changes; no diminished chords). Changes crossfade between two oscillator sets instead of
  sliding in pitch. The **bass** follows the key root, moving to the chord root on 40% of changes. It dips out and back in
  on note changes and ducks under each footstep while the beat plays.
- **Chimes**: four round-robin bell voices. The melody walks plus or minus 1-2 scale steps from the last chime (never the
  same note twice), within 4 steps of the brightness note. Each note gets a random fade (0.9 to 2.6 s) and overtone colour.
  While you walk, a chime waits for the next step or half-step.
- **Arpeggio**: every footstep plays the next note of an 8-step pattern around the current chord. One of five patterns is
  picked each bar (never the same twice), with about 12% rests. It gets louder at a faster pace.
- **Room notes**: the mic goes through six `vcf~` resonators on the chord's root, third and fifth, one and two octaves up.
  How long they ring follows what was heard: a tap gives a short chime, a long loud sound gives a bell.

### Sensors and context

- **Pocket**: the proximity sensor is covered for 1 s and the light is under 10 lux; this works on the test phone. A "floor" tracker judges the room from its
  quietest moments while in a pocket, so rustle bursts don't count as a loud room. **Pocket hush** turns the mic down
  12 dB by default. **Mic-down protection** applies when the phone sits mic end first (detected from gravity): up to 12 dB
  more cut, plus a 300 Hz high-pass for cloth thumps.
- **Brightness** is room-relative: where the light sits between the darkest and brightest of the last ~90 s, mixed with a
  fixed sun scale.
- **Walking**: the step detector is confirmed on the phone. Steps drive the beat and the arpeggio, and set the step rhythm
  that chimes lock to.

### Testing

- **Pd patch tests**: Python plus a desktop libpd built from the same Pd version (`tools/test_patch.py` and others,
  driven by `tools/pdtest.py`). They feed synthetic mic signals (sines, claps, noise) and check the output with numpy:
  levels, spectra, "in key" checks, clicks, timing.
- **Java logic tests**: `tools/javatests` uses stand-in Android stubs, for the world selector, PhoneContext, presets,
  modulation, the step detector, and so on.
- **The real judge is listening on the phone** (Moto G Stylus 2025, Android 16). The developer tests out in the world: on
  walks, in shops, at home.

---

## 3. Movers (modulation)

Every slider can get a mover with a shape, a depth, a speed and an on switch. The shapes are:

- Off
- Smooth wave
- Random drift
- Random jump
- Louder = higher / Louder = lower
- Upright = higher
- Lean right = higher
- Shake = higher
- Spin = higher
- Facing south = higher
- Pad X / Pad Y (touch)
- Brighter = higher
- In pocket = higher
- Climbing = higher

Movers run in Java at about 30 Hz, and Pd glides between the values it receives.

---

## 4. Design decisions that are settled

- **Headphones only.** The phone speaker is never used.
- **Plain Views UI.** No rewrite to Compose.
- **No internet permission**, so no weather or GPS contexts. Location isn't used.
- **The patch is generated by Python**, not drawn in the Pd editor.
- **Soft limiter, not a hard clip** (hard clipping sounded fuzzy).
- **Pinned versions:** desktop libpd for the tests is pinned to the same Pd as the app (0.55.2). Pd 0.56 breaks one
  bundled scene.
- **Workaround for an upstream crash:** a 600 ms mute-then-stop when headphones are unplugged works around a libpd/Oboe
  race. It is reported upstream as libpd issue #427.
- **Nothing resets settings** except the confirmed Reset everything button.
- **Rules that come from listening tests on the phone:** room-relative brightness, pocket as a layer, Flux only in lively
  rooms (running water used to trigger it and turned into fuzz), a soft pad (~0.2 to 0.33), chord changes that crossfade
  instead of sliding.

## 5. Known gaps and the ideas queue

- **Release prep:** final name and applicationId, privacy policy, Play foreground-service and microphone declarations,
  icon, store listing, and a numbered `pd-core` release instead of the snapshot.
- **Untuned on a real phone:** the Pocket world preset and the climbing scale.
- **Ideas not built yet:**
  - pitch-following harmony (answering a hum or whistle in key)
  - Ghost capture-and-stretch
  - pace-tiered arpeggio patterns
  - an "Unstable" world (a jolt triggers stacked effects)
  - a "Collective" world (turntable-style scratching)
  - motif memory
  - slow key drift
  - register from sensors
  - a stems player for the developer's own synthwave loops
- **Scenes:** the scene text and image overlays (`rj_text` / `rj_image`) are accepted but not drawn yet.

---

## What we would like from you

Please be specific, refer to files and line numbers, and say how sure you are. If something depends on code you could not
see (for example libpd internals or the generated `.pd` file), say so instead of guessing.

1. **Code audit and optimizations**
   - CPU and battery while the audio runs for an hour or more: the Pd patch (DSP objects that always run even when an
     effect is off, `[expr]` / `[expr~]` cost, control-rate traffic), the 30 Hz Java tick, sensor rates, allocations in
     hot paths.
   - Audio-thread safety and the risk of glitches: what touches libpd from which thread, locking, and Android lifecycle
     issues in `AudioService` and `MainActivity`.
   - Bugs, race conditions, leaks, edge cases (headphones unplugged, Bluetooth switching, permission denied, process
     death).
   - Structure: anything that would make `MainActivity` (1,300 lines) or `make_patch.py` easier to maintain, short of a
     rewrite.
   - Gaps in the tests: what is not tested that should be.
2. **Sound design**
   - The worlds: are the five presets distinct and pleasant? What would make each one more characterful?
   - Music: ideas for the pad, chimes, arpeggio, bass and room notes that keep it musical and calm, not busy. Ways to
     avoid fatigue over a long walk.
   - Better or cheaper DSP for any effect (reverb, pitch shifter, the resonators).
   - How to handle the mic in a pocket (cloth rustle) without making the outside world inaudible.
3. **UI and UX**
   - The single long screen with about 80 sliders: how to make it friendly for a first-time user, while keeping the
     depth for tinkerers.
   - Showing what the app is doing: the current world, why it was chosen, what the sensors read.
   - Onboarding: headphones, permissions, Bluetooth mic quality.
   - Accessibility and one-handed use while walking.
4. **Product and release**: anything a Play Store release needs that is missing, privacy concerns about an always-on mic
   app, and naming or positioning ideas (without "RjDj").

## Please don't suggest

- Playing through the phone speaker.
- A rewrite in Compose, Kotlin, Flutter, React Native or another framework.
- Adding internet, location or analytics.
- Replacing Pd/libpd with another engine.
- Hand-editing the generated `test_scene.pd` (change `make_patch.py` instead).
