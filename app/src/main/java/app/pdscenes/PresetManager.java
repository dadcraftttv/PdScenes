// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import android.content.Context;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Built-in presets plus user presets stored as small JSON files. */
final class PresetManager {

    static final class Preset {
        final String name;
        final Map<String, Float> values;

        Preset(String name, Map<String, Float> values) {
            this.name = name;
            this.values = values;
        }
    }

    private static final String DIR = "presets";
    private static final String FORMAT = "pdscenes-preset";
    private static final int MAX_BYTES = 64 * 1024;

    // Positions in the filter-type menu (see "filter_type" in Params).
    private static final int DIST_SOFT = 0;
    private static final int DIST_HARD = 1;
    private static final int DIST_FOLD = 2;
    private static final int FILTER_LOW = 0;
    private static final int FILTER_BAND = 2;

    private static final Map<String, Map<String, Float>> BUILT_IN = new LinkedHashMap<>();

    static {
        BUILT_IN.put("Default", defaults());
        BUILT_IN.put("Slapback", make(120f, 0.15f, 0.6f, 80f, 0f));
        BUILT_IN.put("Long echo", make(800f, 0.6f, 0.6f, 80f, 0f));
        BUILT_IN.put("Robot", make(90f, 0.2f, 0.15f, 150f, 0.9f));
        BUILT_IN.put("Dalek", make(200f, 0.3f, 0.2f, 30f, 1f));
        BUILT_IN.put("Chipmunk", pitched(110f, 0.2f, 0.15f, 9f, 1f));
        BUILT_IN.put("Demon", pitched(300f, 0.35f, 0.3f, -7f, 1f));
        BUILT_IN.put("Harmony", pitched(250f, 0.3f, 0.3f, 7f, 0.5f));
        BUILT_IN.put("Octave-down echoes", pitched(450f, 0.5f, 0.6f, -12f, 0.6f));

        Map<String, Float> lofi = make(250f, 0.3f, 0.3f, 80f, 0f);
        crush(lofi, 0.9f, 6f, 6000f);
        BUILT_IN.put("Lo-fi", lofi);

        Map<String, Float> arcade = make(120f, 0.2f, 0.2f, 80f, 0f);
        crush(arcade, 1f, 4f, 11000f);
        BUILT_IN.put("8-bit arcade", arcade);

        Map<String, Float> cave = make(400f, 0.4f, 0.4f, 80f, 0f);
        reverb(cave, 0.6f, 0.9f, 3000f);
        BUILT_IN.put("Cave", cave);

        Map<String, Float> underwater = make(300f, 0.4f, 0.3f, 80f, 0f);
        filter(underwater, 1f, FILTER_LOW, 600f, 2f);
        reverb(underwater, 0.4f, 0.7f, 2500f);
        BUILT_IN.put("Underwater", underwater);

        Map<String, Float> lush = make(300f, 0.35f, 0.3f, 80f, 0f);
        chorus(lush, 0.6f, 0.7f, 4f);
        BUILT_IN.put("Lush chorus", lush);

        Map<String, Float> helicopter = make(150f, 0.2f, 0.2f, 80f, 0f);
        tremolo(helicopter, 1f, 9f);
        BUILT_IN.put("Helicopter", helicopter);

        // Presets with automatic movement (shape 0 = smooth wave, 1 = random drift).
        Map<String, Float> drifting = make(500f, 0.5f, 0.5f, 80f, 0f);
        mover(drifting, "echo_time", 1, 0.08f, 0.4f);
        mover(drifting, "feedback", 0, 0.15f, 0.3f);
        BUILT_IN.put("Drifting echoes", drifting);

        Map<String, Float> wobbly = pitched(200f, 0.3f, 0.3f, 0f, 0.7f);
        mover(wobbly, "pitch_semi", 0, 0.25f, 0.35f);
        BUILT_IN.put("Wobbly pitch", wobbly);

        Map<String, Float> wandering = pitched(300f, 0.4f, 0.4f, -3f, 1f);
        wandering.put("ring_freq", 120f);
        wandering.put("ring_mix", 0.4f);
        mover(wandering, "pitch_semi", 1, 0.15f, 0.5f);
        mover(wandering, "ring_freq", 1, 0.1f, 0.4f);
        BUILT_IN.put("Wandering voice", wandering);

        Map<String, Float> melting = make(350f, 0.45f, 0.4f, 80f, 0f);
        crush(melting, 1f, 8f, 8000f);
        mover(melting, "crush_bits", 1, 0.1f, 0.5f);
        mover(melting, "crush_rate", 1, 0.07f, 0.6f);
        BUILT_IN.put("Melting", melting);

        Map<String, Float> swirl = make(450f, 0.5f, 0.6f, 80f, 0f);
        mover(swirl, "space_pan", 0, 0.2f, 1f);
        mover(swirl, "space_shift", 1, 0.1f, 0.6f);
        BUILT_IN.put("Swirl", swirl);

        Map<String, Float> wah = make(250f, 0.3f, 0.3f, 80f, 0f);
        filter(wah, 1f, FILTER_BAND, 900f, 4f);
        mover(wah, "filter_freq", 0, 0.8f, 0.6f);
        BUILT_IN.put("Auto-wah", wah);

        Map<String, Float> dream = make(450f, 0.5f, 0.5f, 80f, 0f);
        chorus(dream, 0.5f, 0.5f, 5f);
        filter(dream, 0.6f, FILTER_LOW, 3000f, 1f);
        reverb(dream, 0.5f, 0.8f, 4000f);
        mover(dream, "filter_freq", 1, 0.07f, 0.5f);
        mover(dream, "space_pan", 0, 0.1f, 0.5f);
        BUILT_IN.put("Dream", dream);

        Map<String, Float> pulse = make(350f, 0.45f, 0.45f, 80f, 0f);
        tremolo(pulse, 0.7f, 5f);
        mover(pulse, "trem_rate", 1, 0.1f, 0.6f);
        BUILT_IN.put("Pulsing", pulse);

        Map<String, Float> fuzz = make(150f, 0.25f, 0.2f, 80f, 0f);
        distortion(fuzz, 1f, DIST_HARD, 14f);
        filter(fuzz, 1f, FILTER_LOW, 3500f, 1f);
        BUILT_IN.put("Fuzz", fuzz);

        Map<String, Float> warm = make(250f, 0.3f, 0.3f, 80f, 0f);
        distortion(warm, 0.7f, DIST_SOFT, 5f);
        BUILT_IN.put("Warm drive", warm);

        Map<String, Float> fold = make(200f, 0.3f, 0.25f, 80f, 0f);
        distortion(fold, 1f, DIST_FOLD, 8f);
        BUILT_IN.put("Wavefold", fold);

        Map<String, Float> ghost = make(450f, 0.5f, 0.4f, 80f, 0f);
        reverseEcho(ghost, 0.8f, 500f);
        reverb(ghost, 0.3f, 0.7f, 5000f);
        BUILT_IN.put("Ghost echoes", ghost);

        Map<String, Float> stutter = make(200f, 0.3f, 0.2f, 80f, 0f);
        stutterHold(stutter, 0.5f, 90f);
        mover(stutter, "glitch_hold", 0, 1.5f, 0.5f);
        mover(stutter, "glitch_len", 1, 0.3f, 0.6f);
        BUILT_IN.put("Stutter", stutter);

        Map<String, Float> jet = make(200f, 0.3f, 0.25f, 80f, 0f);
        flanger(jet, 1f, 0.2f, 5f, 0.75f);
        BUILT_IN.put("Jet flanger", jet);

        Map<String, Float> sweep = make(300f, 0.35f, 0.3f, 80f, 0f);
        phaser(sweep, 1f, 0.4f, 0.8f, 0.5f);
        BUILT_IN.put("Phaser sweep", sweep);

        Map<String, Float> spaceSweep = make(450f, 0.5f, 0.4f, 80f, 0f);
        phaser(spaceSweep, 1f, 0.15f, 1f, 0.6f);
        flanger(spaceSweep, 0.4f, 0.07f, 6f, -0.5f);
        reverb(spaceSweep, 0.5f, 0.85f, 4500f);
        mover(spaceSweep, "space_pan", 0, 0.12f, 0.7f);
        mover(spaceSweep, "phaser_rate", 1, 0.05f, 0.5f);
        BUILT_IN.put("Space sweep", spaceSweep);

        // Shapes 2 and 3 follow the loudness of the room instead of a clock.
        Map<String, Float> reactive = make(400f, 0.4f, 0.2f, 80f, 0f);
        filter(reactive, 1f, FILTER_LOW, 500f, 2f);
        reverb(reactive, 0.3f, 0.7f, 5000f);
        mover(reactive, "filter_freq", 2, 0.5f, 1f);   // louder opens the filter
        mover(reactive, "wet", 2, 0.4f, 0.8f);         // louder brings in more echo
        BUILT_IN.put("Room reactive", reactive);

        Map<String, Float> freezeLoud = make(300f, 0.3f, 0.3f, 80f, 0f);
        stutterHold(freezeLoud, 0f, 250f);
        reverb(freezeLoud, 0.3f, 0.8f, 5000f);
        mover(freezeLoud, "glitch_hold", 2, 2f, 1f);   // a loud sound freezes and loops the room
        BUILT_IN.put("Freeze on loud", freezeLoud);

        Map<String, Float> spatial = pitched(300f, 0.4f, 0.4f, -2f, 0.4f);
        mover(spatial, "space_pan", 1, 0.1f, 0.8f);
        mover(spatial, "space_shift", 1, 0.08f, 0.5f);
        mover(spatial, "echo_time", 1, 0.05f, 0.3f);
        BUILT_IN.put("Spatial drift", spatial);

        // One preset for each automatic "world" (see Worlds); they are ordinary presets, so they also work by hand.
        Map<String, Float> tranquil = make(600f, 0.55f, 0.5f, 80f, 0f);
        reverb(tranquil, 0.6f, 0.9f, 4500f);
        chorus(tranquil, 0.5f, 0.4f, 5f);
        phaser(tranquil, 0.4f, 0.1f, 0.9f, 0.4f);
        tranquil.put("pitch_semi", 12f);
        tranquil.put("pitch_mix", 0.25f);
        mover(tranquil, "space_pan", 0, 0.07f, 0.6f);
        mover(tranquil, "reverb_mix", 1, 0.05f, 0.4f);
        tranquil.put("music_pad", 0.22f);                 // soft and low; only heard if Music is switched on
        tranquil.put("music_arp", 0.25f);
        tranquil.put("music_res", 0.3f);
        BUILT_IN.put("Tranquil world", tranquil);

        Map<String, Float> flux = make(180f, 0.45f, 0.35f, 120f, 0.3f);
        distortion(flux, 0.45f, DIST_HARD, 6f);
        crush(flux, 0.3f, 6f, 9000f);
        flanger(flux, 0.5f, 0.3f, 4f, 0.6f);
        mover(flux, "echo_time", 11, 1.5f, 0.6f);        // Random jump
        mover(flux, "ring_freq", 11, 1f, 0.5f);
        mover(flux, "glitch_hold", 2, 2f, 0.8f);         // loud sounds freeze the room
        flux.put("music_pad", 0.08f);
        flux.put("music_arp", 0.35f);
        flux.put("music_res", 0.7f);                    // the loud room rings in key
        BUILT_IN.put("Flux world", flux);

        Map<String, Float> kinetic = make(250f, 0.5f, 0.45f, 80f, 0f);
        tremolo(kinetic, 0.6f, 4f);
        filter(kinetic, 0.6f, FILTER_BAND, 1200f, 3f);
        mover(kinetic, "trem_rate", 6, 1.5f, 0.7f);      // Shake = higher: the pulse follows your movement
        mover(kinetic, "filter_freq", 6, 1.5f, 0.8f);
        kinetic.put("beat_level", 0.6f);                 // your footsteps play drums
        kinetic.put("music_pad", 0.1f);                 // the notes start soft and swell as your pace rises
        kinetic.put("music_arp", 0.65f);
        kinetic.put("music_res", 0.25f);                // footsteps and wind should not swamp the arpeggio
        BUILT_IN.put("Kinetic world", kinetic);

        Map<String, Float> ghostWorld = make(450f, 0.5f, 0.4f, 80f, 0f);
        reverseEcho(ghostWorld, 0.8f, 600f);
        reverb(ghostWorld, 0.6f, 0.95f, 3500f);
        filter(ghostWorld, 0.6f, FILTER_LOW, 2500f, 1f);
        ghostWorld.put("pitch_semi", -5f);
        ghostWorld.put("pitch_mix", 0.3f);
        ghostWorld.put("music_res", 0.3f);
        mover(ghostWorld, "space_pan", 1, 0.05f, 0.9f);
        mover(ghostWorld, "rvs_time", 1, 0.04f, 0.5f);
        BUILT_IN.put("Ghost world", ghostWorld);

        // In a pocket the mic only hears cloth and rustle, so keep the room quiet and soft and let the
        // music and your footsteps carry it.
        Map<String, Float> pocketWorld = make(300f, 0.3f, 0.4f, 80f, 0f);
        reverb(pocketWorld, 0.45f, 0.8f, 3000f);
        filter(pocketWorld, 0.7f, FILTER_LOW, 1800f, 1f);
        pocketWorld.put("dry", 0.25f);
        pocketWorld.put("beat_level", 0.45f);
        pocketWorld.put("music_pad", 0.2f);
        pocketWorld.put("music_arp", 0.45f);
        pocketWorld.put("music_res", 0f);               // the mic only hears cloth: no ringing rustle
        BUILT_IN.put("Pocket world", pocketWorld);
    }

    private PresetManager() { }

    private static Map<String, Float> defaults() {
        Map<String, Float> m = new LinkedHashMap<>();
        for (Param p : Params.ALL) {
            if (p.inPreset) {
                m.put(p.id, p.def);
            }
        }
        return m;
    }

    private static void flanger(Map<String, Float> m, float mix, float rateHz, float depthMs, float fb) {
        m.put("flange_mix", mix);
        m.put("flange_rate", rateHz);
        m.put("flange_depth", depthMs);
        m.put("flange_fb", fb);
    }

    private static void phaser(Map<String, Float> m, float mix, float rateHz, float width, float fb) {
        m.put("phaser_mix", mix);
        m.put("phaser_rate", rateHz);
        m.put("phaser_depth", width);
        m.put("phaser_fb", fb);
    }

    private static void distortion(Map<String, Float> m, float mix, int type, float drive) {
        m.put("dist_mix", mix);
        m.put("dist_type", (float) type);
        m.put("dist_drive", drive);
    }

    private static void reverseEcho(Map<String, Float> m, float level, float chunkMs) {
        m.put("rvs_mix", level);
        m.put("rvs_time", chunkMs);
    }

    private static void stutterHold(Map<String, Float> m, float hold, float loopMs) {
        m.put("glitch_hold", hold);
        m.put("glitch_len", loopMs);
    }

    private static void filter(Map<String, Float> m, float mix, int type, float freqHz, float q) {
        m.put("filter_mix", mix);
        m.put("filter_type", (float) type);
        m.put("filter_freq", freqHz);
        m.put("filter_q", q);
    }

    private static void reverb(Map<String, Float> m, float mix, float size, float toneHz) {
        m.put("reverb_mix", mix);
        m.put("reverb_size", size);
        m.put("reverb_tone", toneHz);
    }

    private static void chorus(Map<String, Float> m, float mix, float rateHz, float depthMs) {
        m.put("chorus_mix", mix);
        m.put("chorus_rate", rateHz);
        m.put("chorus_depth", depthMs);
    }

    private static void tremolo(Map<String, Float> m, float depth, float rateHz) {
        m.put("trem_depth", depth);
        m.put("trem_rate", rateHz);
    }

    private static void crush(Map<String, Float> m, float mix, float bits, float rateHz) {
        m.put("crush_mix", mix);
        m.put("crush_bits", bits);
        m.put("crush_rate", rateHz);
    }

    /** Gives the slider {@code target} a mover (shape: 0 smooth wave, 1 random drift, 2 louder = higher ...). */
    private static void mover(Map<String, Float> m, String target, int shape, float speedHz, float depth) {
        Param p = Params.byId(target);
        if (p == null || Params.byId(Params.moverId(target, "mv")) == null) {
            throw new IllegalArgumentException("Not a mover target: " + target);
        }
        m.put(Params.moverId(target, "mv"), (float) (shape + 1));   // 0 in the menu is "Off"
        m.put(Params.moverId(target, "mvspeed"), speedHz);
        m.put(Params.moverId(target, "mvdepth"), depth);
        m.put(Params.moversSwitchId(p.section), 1f);
    }

    private static Map<String, Float> make(float echoTime, float feedback, float wet,
                                           float ringFreq, float ringMix) {
        Map<String, Float> m = defaults();
        m.put("echo_time", echoTime);
        m.put("feedback", feedback);
        m.put("wet", wet);
        m.put("ring_freq", ringFreq);
        m.put("ring_mix", ringMix);
        return m;
    }

    private static Map<String, Float> pitched(float echoTime, float feedback, float wet,
                                              float semitones, float pitchMix) {
        Map<String, Float> m = make(echoTime, feedback, wet, 80f, 0f);
        m.put("pitch_semi", semitones);
        m.put("pitch_mix", pitchMix);
        return m;
    }

    static List<String> builtInNames() {
        return new ArrayList<>(BUILT_IN.keySet());
    }

    static boolean isBuiltInName(String name) {
        return BUILT_IN.containsKey(name);
    }

    static Map<String, Float> builtIn(String name) {
        return BUILT_IN.get(name);
    }

    static List<String> userNames(Context context) {
        List<String> names = new ArrayList<>();
        File[] files = new File(context.getFilesDir(), DIR).listFiles();
        if (files != null) {
            for (File f : files) {
                String n = f.getName();
                if (n.endsWith(".json")) {
                    names.add(n.substring(0, n.length() - 5));
                }
            }
        }
        Collections.sort(names, String.CASE_INSENSITIVE_ORDER);
        return names;
    }

    /** Returns null if the preset is missing or unreadable. */
    static Map<String, Float> readUser(Context context, String name) {
        File f = new File(new File(context.getFilesDir(), DIR), sanitize(name) + ".json");
        try (InputStream in = new java.io.FileInputStream(f)) {
            return parse(readAll(in)).values;
        } catch (IOException | JSONException e) {
            return null;
        }
    }

    /** Saves the preset-eligible values under a sanitized name. Returns the name used. */
    static String save(Context context, String name, Map<String, Float> values)
            throws IOException {
        String clean = sanitize(name);
        if (isBuiltInName(clean)) {
            throw new IOException("\"" + clean + "\" is a built-in preset name");
        }
        File dir = new File(context.getFilesDir(), DIR);
        if (!dir.exists() && !dir.mkdirs()) {
            throw new IOException("Cannot create preset folder");
        }
        try (FileOutputStream out = new FileOutputStream(new File(dir, clean + ".json"))) {
            out.write(toJson(clean, values).getBytes(StandardCharsets.UTF_8));
        }
        return clean;
    }

    /** {@code name} if no saved preset has it yet, otherwise "name 2", "name 3" ... so imports never overwrite. */
    static String uniqueName(Context context, String name) {
        String base = sanitize(name);
        List<String> existing = userNames(context);
        String candidate = base;
        for (int n = 2; containsIgnoreCase(existing, candidate); n++) {
            candidate = sanitize(base + " " + n);
        }
        return candidate;
    }

    private static boolean containsIgnoreCase(List<String> names, String name) {
        for (String n : names) {
            if (n.equalsIgnoreCase(name)) {
                return true;
            }
        }
        return false;
    }

    static boolean delete(Context context, String name) {
        return new File(new File(context.getFilesDir(), DIR), sanitize(name) + ".json").delete();
    }

    static String toJson(String name, Map<String, Float> values) {
        try {
            JSONObject vals = new JSONObject();
            for (Param p : Params.ALL) {
                Float v = values.get(p.id);
                if (p.inPreset && v != null) {
                    vals.put(p.id, (double) v);
                }
            }
            JSONObject root = new JSONObject();
            root.put("format", FORMAT);
            root.put("version", 1);
            root.put("name", name);
            root.put("values", vals);
            return root.toString(2);
        } catch (JSONException e) {
            throw new IllegalStateException(e);
        }
    }

    /** Parses a preset, ignoring unknown parameters so old/new files keep working. */
    static Preset parse(String json) throws JSONException {
        JSONObject root = new JSONObject(json);
        JSONObject vals = root.getJSONObject("values");
        Params.upgradeLegacyMovers(vals);
        Map<String, Float> map = new LinkedHashMap<>();
        for (Param p : Params.ALL) {
            if (p.inPreset && vals.has(p.id)) {
                map.put(p.id, p.clamp((float) vals.getDouble(p.id)));
            }
        }
        if (map.isEmpty()) {
            throw new JSONException("No known parameters in file");
        }
        return new Preset(root.optString("name", "Imported preset"), map);
    }

    static String readAll(InputStream in) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int n;
        while ((n = in.read(buf)) > 0) {
            out.write(buf, 0, n);
            if (out.size() > MAX_BYTES) {
                throw new IOException("File too large for a preset");
            }
        }
        return out.toString("UTF-8");
    }

    static String sanitize(String name) {
        String s = name == null ? "" : name.replaceAll("[^A-Za-z0-9 _-]", "").trim();
        if (s.length() > 40) {
            s = s.substring(0, 40).trim();
        }
        return s.isEmpty() ? "preset" : s;
    }
}
