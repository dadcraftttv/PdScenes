// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import java.util.HashMap;
import java.util.Map;

/**
 * The Intensity macro (roadmap item 4, Samuel Oct 13): one control for how much is going on. At 0.5 everything plays
 * as set; lower calms it, higher makes it busier. It never changes a stored value: it scales what is sent to Pd, so
 * presets, Realms and the sliders keep their own values. It only scales what is already there (a 0 stays 0: an effect
 * the user switched down never comes on), downward by up to {@code calm} of the value at Intensity 0, upward by up
 * to {@code lift} times more at Intensity 1, never past the slider's safe range (or its own value, if set higher).
 * The patch also hears {@code intensity} and makes the drum patterns calmer or busier. Pure logic (test I).
 */
final class Intensity {

    static final String ID = "intensity";

    /** {calm, lift} per parameter. */
    private static final Map<String, float[]> RULES = new HashMap<>();

    static {
        rule(0.6f, 0.6f, "wet", "reverb_mix", "echo_scatter", "music_res");
        rule(0.5f, 0.3f, "feedback");
        rule(1f, 0.8f, "gc_amount", "beat_glitch", "rvs_mix");
        rule(1f, 0.6f, "ring_mix", "crush_mix", "dist_mix", "flange_mix", "phaser_mix", "chorus_mix", "pitch_mix",
                "filter_mix", "trem_depth");
        rule(0.6f, 0.5f, "music_react");
        rule(0.5f, 0.3f, "music_harm");
        rule(0.4f, 0.3f, "music_arp", "beat_level");
    }

    private Intensity() { }

    private static void rule(float calm, float lift, String... ids) {
        for (String id : ids) {
            RULES.put(id, new float[]{calm, lift});
        }
    }

    /** True for the parameters Intensity scales (they are sent again whenever it moves). */
    static boolean scales(String id) {
        return RULES.containsKey(id);
    }

    static Iterable<String> scaled() {
        return RULES.keySet();
    }

    /** The value to send for {@code p} at {@code value} with Intensity {@code t} (0..1, 0.5 = unchanged). */
    static float apply(Param p, float value, float t) {
        float[] r = RULES.get(p.id);
        if (r == null || Math.abs(t - 0.5f) < 1e-4f) {
            return value;
        }
        float u = Math.max(-1f, Math.min(1f, (t - 0.5f) * 2f));
        float n = p.toNorm(value), lo = p.toNorm(p.min);
        float from = n - lo;   // how much of it there is
        if (u < 0) {
            return p.toValue(lo + from * (1f + u * r[0]));
        }
        float cap = Math.max(n, p.toNorm(p.randMax));
        return p.toValue(Math.min(cap, lo + from * (1f + u * r[1])));
    }
}
