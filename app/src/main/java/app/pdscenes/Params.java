// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * The single list of parameters. The UI, presets, randomize and (later) sensor
 * mapping are all driven from this. To add a parameter: add an entry here (in the
 * right section) and a matching [r name] in the Pd patch.
 */
final class Params {

    /** A collapsible group on the screen. Order here is display order. */
    static final class Section {
        final String id;
        final String title;
        final boolean openByDefault;

        Section(String id, String title, boolean openByDefault) {
            this.id = id;
            this.title = title;
            this.openByDefault = openByDefault;
        }
    }

    static final List<Section> SECTIONS = Collections.unmodifiableList(Arrays.asList(
            new Section("main", "Input & output", true),
            new Section("beat", "Walking beat", true),
            new Section("music", "Music", true),
            new Section("echo", "Echo", true),
            new Section("ring", "Ring modulator", true),
            new Section("pitch", "Pitch shifter", true),
            new Section("crush", "Bit crusher", true),
            new Section("dist", "Distortion", true),
            new Section("filter", "Filter", true),
            new Section("chorus", "Chorus", true),
            new Section("flange", "Flanger", true),
            new Section("phaser", "Phaser", true),
            new Section("tremolo", "Tremolo", true),
            new Section("reverse", "Reverse echo", true),
            new Section("glitch", "Glitch / freeze", true),
            new Section("reverb", "Reverb", true),
            new Section("space", "Spatial", true),
            new Section("behavior", "Behavior", false)
    ));

    /**
     * What the old three shared movers could drive, in their old menu order. Only used to convert
     * presets and saved state made before every slider had its own mover. Never change this list.
     */
    private static final String[] LEGACY_MOVER_TARGETS = {
            "dry", "echo_time", "feedback", "wet", "ring_freq", "ring_mix", "pitch_semi", "pitch_mix",
            "crush_mix", "crush_bits", "crush_rate",
            "space_pan", "space_shift", "filter_mix", "filter_freq", "filter_q",
            "reverb_mix", "reverb_size", "reverb_tone", "chorus_mix", "chorus_rate", "chorus_depth",
            "trem_depth", "trem_rate", "dist_mix", "dist_drive", "rvs_mix", "rvs_time", "glitch_hold",
            "glitch_len", "flange_mix", "flange_rate", "flange_depth", "flange_fb", "phaser_mix",
            "phaser_rate", "phaser_depth", "phaser_fb"};

    /**
     * How a slider's mover moves it. The first two run on a clock, the rest follow the room or the phone
     * (mic loudness, tilt, shake, spin, compass heading, the touch pad, light, pocket, climbing stairs). Random jump hops to a new random
     * position {@code speed} times a second; "speed" then sets how fast they
     * react. New shapes go on the end: presets store the position in this list.
     */
    static final String[] MOVER_SHAPES = {
            "Off", "Smooth wave", "Random drift", "Louder = higher", "Louder = lower",
            "Upright = higher", "Lean right = higher", "Shake = higher", "Spin = higher",
            "Facing south = higher", "Pad X (right = higher)", "Pad Y (up = higher)", "Random jump",
            "Brighter = higher", "In pocket = higher", "Climbing = higher"};

    /** The sound parameters. The Pd patch has a receiver for each one that is not noPd(). */
    private static final List<Param> CORE = Arrays.asList(
            // ---- Input & output ----
            new Param("gain", "Input gain", 0f, 10f, 2.5f, "x", Param.Curve.LINEAR)
                    .inSection("main").noRandom().noPreset(),
            // Input conditioning: depends on the room and the mic, so not part of presets/randomize.
            new Param("gate_thresh", "Noise gate threshold (-80 = off)", -80f, -20f, -80f, " dB",
                    Param.Curve.LINEAR).inSection("main").noRandom().noPreset().decimals(0),
            new Param("comp_thresh", "Compressor threshold (0 = off)", -50f, 0f, -30f, " dB",
                    Param.Curve.LINEAR).inSection("main").noRandom().noPreset().decimals(0),
            new Param("comp_ratio", "Compressor ratio", 1f, 20f, 4f, ":1", Param.Curve.LOG)
                    .inSection("main").noRandom().noPreset().decimals(1),
            new Param("comp_makeup", "Compressor make-up gain", 0f, 24f, 0f, " dB",
                    Param.Curve.LINEAR).inSection("main").noRandom().noPreset().decimals(0),
            // In a pocket the mic hears only cloth and rustle: turn it down (1 = about -24 dB) before the effects and music.
            new Param("pocket_hush", "Pocket hush (mic quieter while in a pocket)", 0f, 1f, 0.9f, "",
                    Param.Curve.LINEAR).inSection("main").noRandom().noPreset().resetWhenAbsent(),
            new Param("dry", "Dry level (direct sound)", 0f, 1.5f, 1f, "", Param.Curve.LINEAR)
                    .inSection("main").rand(0.3f, 1.2f),

            // ---- Walking beat ---- (drums played by your footsteps, added after the first presets)
            new Param("beat_on", "Walking beat enabled", 0f, 1f, 1f, "", Param.Curve.LINEAR)
                    .inSection("beat").toggle().resetWhenAbsent(),
            new Param("beat_level", "Beat level (plays when you walk; 0 = off)", 0f, 1f, 0f, "",
                    Param.Curve.LINEAR).inSection("beat").rand(0f, 0.7f).resetWhenAbsent(),
            new Param("beat_hats", "Hi-hat level", 0f, 1f, 0.5f, "", Param.Curve.LINEAR)
                    .inSection("beat").rand(0f, 1f).resetWhenAbsent(),
            new Param("beat_snare", "Snare level", 0f, 1f, 0.6f, "", Param.Curve.LINEAR)
                    .inSection("beat").rand(0f, 1f).resetWhenAbsent(),
            new Param("beat_pitch", "Kick drum pitch", 40f, 120f, 55f, " Hz", Param.Curve.LOG)
                    .inSection("beat").rand(45f, 90f).decimals(0).resetWhenAbsent(),

            // ---- Music ---- (a reactive synth: notes snapped to a key and scale, added after the first presets)
            new Param("music_on", "Music enabled", 0f, 1f, 0f, "", Param.Curve.LINEAR)
                    .inSection("music").toggle().noPreset().resetWhenAbsent(),
            new Param("music_key", "Key", 0f, 11f, 0f, "", Param.Curve.LINEAR)
                    .choices("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
                    .inSection("music").noPreset().resetWhenAbsent(),
            new Param("music_scale", "Scale", 0f, 7f, 0f, "", Param.Curve.LINEAR)
                    .choices("Major", "Minor", "Major pentatonic", "Minor pentatonic", "Dorian",
                            "Mixolydian", "Lydian", "Whole tone")
                    .inSection("music").noPreset().resetWhenAbsent(),
            new Param("music_pad", "Pad level (soft chords that drift)", 0f, 1f, 0.33f, "",
                    Param.Curve.LINEAR).inSection("music").rand(0f, 0.6f).resetWhenAbsent(),
            new Param("music_arp", "Notes and chimes level", 0f, 1f, 0.4f, "", Param.Curve.LINEAR)
                    .inSection("music").rand(0f, 0.8f).resetWhenAbsent(),
            new Param("music_tone", "Tone (dark to bright)", 0f, 1f, 0.5f, "", Param.Curve.LINEAR)
                    .inSection("music").rand(0.2f, 0.9f).resetWhenAbsent(),
            new Param("music_react", "How much the music follows what it hears", 0f, 1f, 0.8f, "",
                    Param.Curve.LINEAR).inSection("music").rand(0.3f, 1f).resetWhenAbsent(),
            new Param("music_res", "Room notes (sounds around you ring the chord)", 0f, 1f, 0.8f, "",
                    Param.Curve.LINEAR).inSection("music").rand(0.2f, 1f).resetWhenAbsent(),

            // ---- Echo ----
            new Param("echo_on", "Echo enabled", 0f, 1f, 1f, "", Param.Curve.LINEAR)
                    .inSection("echo").toggle(),
            new Param("echo_time", "Echo time", 50f, 1500f, 350f, " ms", Param.Curve.LOG)
                    .inSection("echo").rand(80f, 1200f),
            new Param("feedback", "Echo feedback", 0f, 0.85f, 0.4f, "", Param.Curve.LINEAR)
                    .inSection("echo").rand(0f, 0.7f),
            new Param("wet", "Echo level (wet)", 0f, 1f, 0.5f, "", Param.Curve.LINEAR)
                    .inSection("echo").rand(0f, 0.8f),

            // ---- Ring modulator ----
            new Param("ring_on", "Ring mod enabled", 0f, 1f, 1f, "", Param.Curve.LINEAR)
                    .inSection("ring").toggle(),
            new Param("ring_freq", "Ring-mod frequency", 20f, 1000f, 80f, " Hz", Param.Curve.LOG)
                    .inSection("ring").rand(30f, 800f),
            new Param("ring_mix", "Ring-mod amount", 0f, 1f, 0f, "", Param.Curve.LINEAR)
                    .inSection("ring").rand(0f, 0.7f),

            // ---- Pitch shifter ----
            new Param("pitch_on", "Pitch shift enabled", 0f, 1f, 1f, "", Param.Curve.LINEAR)
                    .inSection("pitch").toggle(),
            new Param("pitch_semi", "Pitch shift amount (semitones)", -12f, 12f, 0f, " st",
                    Param.Curve.LINEAR).inSection("pitch").rand(-7f, 7f).decimals(1),
            new Param("pitch_mix", "Pitch shift mix (0 = original only)", 0f, 1f, 0f, "",
                    Param.Curve.LINEAR).inSection("pitch").rand(0f, 0.8f),
            new Param("pitch_window", "Pitch grain size", 20f, 200f, 60f, " ms", Param.Curve.LOG)
                    .inSection("pitch").noRandom(),

            // ---- Bit crusher ---- (added after the first presets: older presets switch it off)
            new Param("crush_on", "Bit crusher enabled", 0f, 1f, 1f, "", Param.Curve.LINEAR)
                    .inSection("crush").toggle().resetWhenAbsent(),
            new Param("crush_mix", "Bit-crush amount (0 = clean)", 0f, 1f, 0f, "",
                    Param.Curve.LINEAR).inSection("crush").rand(0f, 0.8f).resetWhenAbsent(),
            new Param("crush_bits", "Bit depth (lower = grittier)", 1f, 16f, 8f, " bits",
                    Param.Curve.LINEAR).inSection("crush").rand(3f, 12f).decimals(1)
                    .resetWhenAbsent(),
            new Param("crush_rate", "Sample-rate reduction", 500f, 24000f, 8000f, " Hz",
                    Param.Curve.LOG).inSection("crush").rand(1500f, 16000f).resetWhenAbsent(),

            // ---- Spatial ---- (added after the first presets: older presets centre it)
            new Param("space_on", "Spatial enabled", 0f, 1f, 1f, "", Param.Curve.LINEAR)
                    .inSection("space").toggle().resetWhenAbsent(),
            new Param("space_pan", "Pan (left to right)", -1f, 1f, 0f, "", Param.Curve.LINEAR)
                    .inSection("space").rand(-0.8f, 0.8f).decimals(2).resetWhenAbsent(),
            new Param("space_shift", "Ear delay (+ = sound from the left)", -25f, 25f, 0f, " ms",
                    Param.Curve.LINEAR).inSection("space").rand(-15f, 15f).decimals(1)
                    .resetWhenAbsent(),

            // ---- Filter ---- (added after the first presets: older presets switch it off)
            new Param("filter_on", "Filter enabled", 0f, 1f, 1f, "", Param.Curve.LINEAR)
                    .inSection("filter").toggle().resetWhenAbsent(),
            new Param("filter_mix", "Filter amount (0 = clean)", 0f, 1f, 0f, "", Param.Curve.LINEAR)
                    .inSection("filter").rand(0f, 0.9f).resetWhenAbsent(),
            new Param("filter_type", "Filter type", 0f, 2f, 0f, "", Param.Curve.LINEAR)
                    .choices("Low-pass", "High-pass", "Band-pass").inSection("filter")
                    .resetWhenAbsent(),
            new Param("filter_freq", "Filter frequency", 80f, 12000f, 1500f, " Hz", Param.Curve.LOG)
                    .inSection("filter").rand(150f, 8000f).resetWhenAbsent(),
            new Param("filter_q", "Filter resonance (Q)", 0.5f, 12f, 1f, "", Param.Curve.LOG)
                    .inSection("filter").rand(0.7f, 6f).decimals(1).resetWhenAbsent(),

            // ---- Reverb ---- (added after the first presets: older presets switch it off)
            new Param("reverb_on", "Reverb enabled", 0f, 1f, 1f, "", Param.Curve.LINEAR)
                    .inSection("reverb").toggle().resetWhenAbsent(),
            new Param("reverb_mix", "Reverb level", 0f, 1f, 0f, "", Param.Curve.LINEAR)
                    .inSection("reverb").rand(0f, 0.6f).resetWhenAbsent(),
            new Param("reverb_size", "Room size", 0f, 1f, 0.5f, "", Param.Curve.LINEAR)
                    .inSection("reverb").rand(0.2f, 0.9f).resetWhenAbsent(),
            new Param("reverb_tone", "Reverb brightness", 1500f, 16000f, 6000f, " Hz",
                    Param.Curve.LOG).inSection("reverb").rand(2500f, 12000f).resetWhenAbsent(),

            // ---- Chorus ---- (added after the first presets: older presets switch it off)
            new Param("chorus_on", "Chorus enabled", 0f, 1f, 1f, "", Param.Curve.LINEAR)
                    .inSection("chorus").toggle().resetWhenAbsent(),
            new Param("chorus_mix", "Chorus amount (0 = clean)", 0f, 1f, 0f, "", Param.Curve.LINEAR)
                    .inSection("chorus").rand(0f, 0.8f).resetWhenAbsent(),
            new Param("chorus_rate", "Chorus speed", 0.05f, 5f, 0.8f, " Hz", Param.Curve.LOG)
                    .inSection("chorus").rand(0.2f, 3f).decimals(2).resetWhenAbsent(),
            new Param("chorus_depth", "Chorus depth", 0.2f, 8f, 3f, " ms", Param.Curve.LOG)
                    .inSection("chorus").rand(1f, 6f).decimals(1).resetWhenAbsent(),

            // ---- Tremolo ---- (added after the first presets: older presets switch it off)
            new Param("trem_on", "Tremolo enabled", 0f, 1f, 1f, "", Param.Curve.LINEAR)
                    .inSection("tremolo").toggle().resetWhenAbsent(),
            new Param("trem_depth", "Tremolo depth (0 = off)", 0f, 1f, 0f, "", Param.Curve.LINEAR)
                    .inSection("tremolo").rand(0f, 0.8f).resetWhenAbsent(),
            new Param("trem_rate", "Tremolo speed", 0.5f, 20f, 5f, " Hz", Param.Curve.LOG)
                    .inSection("tremolo").rand(1f, 12f).decimals(1).resetWhenAbsent(),

            // ---- Distortion ---- (added after the first presets: older presets switch it off)
            new Param("dist_on", "Distortion enabled", 0f, 1f, 1f, "", Param.Curve.LINEAR)
                    .inSection("dist").toggle().resetWhenAbsent(),
            new Param("dist_mix", "Distortion amount (0 = clean)", 0f, 1f, 0f, "", Param.Curve.LINEAR)
                    .inSection("dist").rand(0f, 0.7f).resetWhenAbsent(),
            new Param("dist_drive", "Distortion drive", 1f, 40f, 4f, "x", Param.Curve.LOG)
                    .inSection("dist").rand(1.5f, 15f).decimals(1).resetWhenAbsent(),
            new Param("dist_type", "Distortion type", 0f, 2f, 0f, "", Param.Curve.LINEAR)
                    .choices("Soft clip", "Hard clip", "Wavefold").inSection("dist")
                    .resetWhenAbsent(),

            // ---- Reverse echo ---- (added after the first presets: older presets switch it off)
            new Param("rvs_on", "Reverse echo enabled", 0f, 1f, 1f, "", Param.Curve.LINEAR)
                    .inSection("reverse").toggle().resetWhenAbsent(),
            new Param("rvs_mix", "Reverse echo level", 0f, 1f, 0f, "", Param.Curve.LINEAR)
                    .inSection("reverse").rand(0f, 0.7f).resetWhenAbsent(),
            new Param("rvs_time", "Reversed chunk length", 100f, 1000f, 400f, " ms", Param.Curve.LOG)
                    .inSection("reverse").rand(150f, 800f).resetWhenAbsent(),

            // ---- Glitch / freeze ---- (added after the first presets: older presets switch it off)
            new Param("glitch_on", "Glitch/freeze enabled", 0f, 1f, 1f, "", Param.Curve.LINEAR)
                    .inSection("glitch").toggle().resetWhenAbsent(),
            new Param("glitch_hold", "Freeze (0 = live, 1 = frozen)", 0f, 1f, 0f, "",
                    Param.Curve.LINEAR).inSection("glitch").noRandom().resetWhenAbsent(),
            new Param("glitch_len", "Freeze loop length", 20f, 500f, 120f, " ms", Param.Curve.LOG)
                    .inSection("glitch").rand(40f, 300f).resetWhenAbsent(),

            // ---- Flanger ---- (added after the first presets: older presets switch it off)
            new Param("flange_on", "Flanger enabled", 0f, 1f, 1f, "", Param.Curve.LINEAR)
                    .inSection("flange").toggle().resetWhenAbsent(),
            new Param("flange_mix", "Flanger amount (0 = clean)", 0f, 1f, 0f, "", Param.Curve.LINEAR)
                    .inSection("flange").rand(0f, 0.8f).resetWhenAbsent(),
            new Param("flange_rate", "Flanger speed", 0.05f, 5f, 0.3f, " Hz", Param.Curve.LOG)
                    .inSection("flange").rand(0.1f, 2f).decimals(2).resetWhenAbsent(),
            new Param("flange_depth", "Flanger depth", 0.5f, 8f, 4f, " ms", Param.Curve.LOG)
                    .inSection("flange").rand(1f, 6f).decimals(1).resetWhenAbsent(),
            new Param("flange_fb", "Flanger feedback (negative = hollow)", -0.9f, 0.9f, 0.5f, "",
                    Param.Curve.LINEAR).inSection("flange").rand(-0.7f, 0.7f).decimals(2)
                    .resetWhenAbsent(),

            // ---- Phaser ---- (added after the first presets: older presets switch it off)
            new Param("phaser_on", "Phaser enabled", 0f, 1f, 1f, "", Param.Curve.LINEAR)
                    .inSection("phaser").toggle().resetWhenAbsent(),
            new Param("phaser_mix", "Phaser amount (0 = clean)", 0f, 1f, 0f, "", Param.Curve.LINEAR)
                    .inSection("phaser").rand(0f, 0.8f).resetWhenAbsent(),
            new Param("phaser_rate", "Phaser speed", 0.05f, 5f, 0.4f, " Hz", Param.Curve.LOG)
                    .inSection("phaser").rand(0.1f, 2f).decimals(2).resetWhenAbsent(),
            new Param("phaser_depth", "Phaser sweep width", 0f, 1f, 0.7f, "", Param.Curve.LINEAR)
                    .inSection("phaser").rand(0.3f, 1f).decimals(2).resetWhenAbsent(),
            new Param("phaser_fb", "Phaser feedback", 0f, 0.9f, 0.4f, "", Param.Curve.LINEAR)
                    .inSection("phaser").rand(0f, 0.7f).decimals(2).resetWhenAbsent(),

            // ---- Behavior ----
            // How long parameter changes take to glide. Not part of presets.
            new Param("smooth", "Smoothing (change glide time)", 1f, 500f, 30f, " ms",
                    Param.Curve.LOG).inSection("behavior").noRandom().noPreset(),
            // App-only: how far Nudge moves each slider (fraction of its travel).
            new Param("nudge_amount", "Nudge strength", 0.005f, 0.3f, 0.04f, "", Param.Curve.LOG)
                    .inSection("behavior").noRandom().noPreset().noPd().decimals(3));

    /** Everything: the sound parameters plus the settings of each mover (app-side only). */
    static final List<Param> ALL = Collections.unmodifiableList(withMovers(CORE));

    /** Id of the section's "movers on" switch. */
    static String moversSwitchId(String sectionId) {
        return sectionId + "_movers";
    }

    /** Id of the setting of {@code param}'s mover: "mv" (movement), "mvspeed" or "mvdepth". */
    static String moverId(String paramId, String field) {
        return paramId + "_" + field;
    }

    /** True for sliders that can have a mover: not switches, dropdowns or app-only settings. */
    private static boolean movable(Param p) {
        return !p.toggle && p.choices == null && p.sendToPd;
    }

    /**
     * Every slider gets its own mover, which slowly pushes it around its slider position: three
     * settings (movement, speed, depth) per slider, and one switch per section to turn that section's
     * movers on or off.
     */
    private static List<Param> withMovers(List<Param> core) {
        List<Param> all = new ArrayList<>(core);
        for (Section section : SECTIONS) {
            boolean any = false, anyInPreset = false;
            for (Param p : core) {
                if (p.section.equals(section.id) && movable(p)) {
                    any = true;
                    anyInPreset |= p.inPreset;
                    List<Param> mover = new ArrayList<>();
                    mover.add(new Param(moverId(p.id, "mv"), "Movement", 0f, MOVER_SHAPES.length - 1, 0f, "",
                            Param.Curve.LINEAR).choices(MOVER_SHAPES).inSection(section.id).noPd()
                            .resetWhenAbsent().moverOf(p.id));
                    mover.add(new Param(moverId(p.id, "mvspeed"), "Speed (or reaction time)", 0.02f, 2f, 0.2f,
                            " Hz", Param.Curve.LOG).inSection(section.id).noRandom().noPd()
                            .resetWhenAbsent().decimals(2).moverOf(p.id));
                    mover.add(new Param(moverId(p.id, "mvdepth"), "Depth", 0f, 1f, 0.3f, "",
                            Param.Curve.LINEAR).inSection(section.id).noRandom().noPd().resetWhenAbsent()
                            .decimals(2).moverOf(p.id));
                    // A slider kept out of presets (gain, gate, compressor, smoothing) keeps its mover out too,
                    // or loading a preset or a world would switch that mover off.
                    for (Param m : mover) {
                        all.add(p.inPreset ? m : m.noPreset());
                    }
                }
            }
            if (any) {
                Param sw = new Param(moversSwitchId(section.id), "Movers (automatic movement) for this section",
                        0f, 1f, 0f, "", Param.Curve.LINEAR).inSection(section.id).toggle().noPd()
                        .resetWhenAbsent();
                all.add(anyInPreset ? sw : sw.noPreset());
            }
        }
        return all;
    }

    /** The sliders that can have a mover, in screen order. */
    static final List<Param> MOVABLE = Collections.unmodifiableList(movableOf(CORE));

    private static List<Param> movableOf(List<Param> core) {
        List<Param> result = new ArrayList<>();
        for (Param p : core) {
            if (movable(p)) {
                result.add(p);
            }
        }
        return result;
    }

    /**
     * Turns the settings of the old three shared movers ("mover1_target" ...) found in {@code values} into
     * the per-slider ones, so presets and saved state from earlier versions keep working. Does not overwrite
     * a per-slider mover that is already there.
     */
    static void upgradeLegacyMovers(org.json.JSONObject values) throws org.json.JSONException {
        for (int n = 1; n <= 3; n++) {
            int target = (int) Math.round(values.optDouble("mover" + n + "_target", 0));
            if (target < 1 || target > LEGACY_MOVER_TARGETS.length) {
                continue;
            }
            Param p = byId(LEGACY_MOVER_TARGETS[target - 1]);
            if (values.has(moverId(p.id, "mv"))) {
                continue;
            }
            // The old list had no "Off": its shapes sit one place later in the new one.
            values.put(moverId(p.id, "mv"), Math.round(values.optDouble("mover" + n + "_shape", 0)) + 1);
            values.put(moverId(p.id, "mvspeed"), values.optDouble("mover" + n + "_speed", 0.2));
            values.put(moverId(p.id, "mvdepth"), values.optDouble("mover" + n + "_depth", 0.3));
            values.put(moversSwitchId(p.section), 1);
        }
    }

    private static Param find(List<Param> list, String id) {
        for (Param p : list) {
            if (p.id.equals(id)) {
                return p;
            }
        }
        throw new IllegalStateException("Unknown parameter " + id);
    }

    private Params() { }

    private static final Map<String, Param> BY_ID = indexById(ALL);

    private static Map<String, Param> indexById(List<Param> params) {
        Map<String, Param> index = new HashMap<>();
        for (Param p : params) {
            index.put(p.id, p);
        }
        return index;
    }

    static Param byId(String id) {
        return BY_ID.get(id);
    }
}
