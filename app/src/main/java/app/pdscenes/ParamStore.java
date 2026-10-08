// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import org.puredata.core.PdBase;

import java.util.ArrayDeque;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Random;
import java.util.Set;

/**
 * Current parameter values, locks and undo history. Whatever changes a value
 * here also forwards it to Pd if the audio engine is running; the service
 * replays everything when it (re)starts. The last state is saved on pause and
 * restored on the next launch.
 */
final class ParamStore {

    private static final String PREFS = "pdscenes_state";
    private static final String KEY = "state";
    private static final int MAX_UNDO = 20;

    private static final Map<String, Float> values = new LinkedHashMap<>();
    private static final Set<String> locked = new HashSet<>();
    private static final ArrayDeque<Map<String, Float>> undoStack = new ArrayDeque<>();
    private static final Random rng = new Random();
    private static boolean loaded = false;

    static {
        for (Param p : Params.ALL) {
            values.put(p.id, p.def);
        }
    }

    private ParamStore() { }

    static synchronized float get(String id) {
        Float v = values.get(id);
        return v != null ? v : 0f;
    }

    /** Set one value (clamped) and forward it to Pd if running. */
    static synchronized void set(String id, float value) {
        Param p = Params.byId(id);
        if (p == null) {
            return;
        }
        float v = p.clamp(value);
        values.put(id, v);
        if (p.sendToPd && AudioService.isRunning()) {
            PdBase.sendFloat(id, Modulation.output(p, v));
        }
    }

    static synchronized Map<String, Float> snapshot() {
        return new LinkedHashMap<>(values);
    }

    static synchronized boolean isLocked(String id) {
        return locked.contains(id);
    }

    static synchronized void setLocked(String id, boolean on) {
        if (on) {
            locked.add(id);
        } else {
            locked.remove(id);
        }
    }

    static synchronized boolean canUndo() {
        return !undoStack.isEmpty();
    }

    /** Apply a preset's values (only known parameters that belong in presets). */
    static synchronized void applyPreset(Map<String, Float> preset) {
        pushUndo();
        applyValues(preset);
    }

    /** Jump every unlocked, randomizable parameter to a random value in its safe range. */
    static synchronized void randomize() {
        pushUndo();
        for (Param p : Params.ALL) {
            if (!p.randomizable || locked.contains(p.id)) {
                continue;
            }
            float lo = p.toNorm(p.randMin);
            float hi = p.toNorm(p.randMax);
            set(p.id, p.toValue(lo + rng.nextFloat() * (hi - lo)));
        }
    }

    /** Move every unlocked, randomizable parameter a little (amount is a slider fraction). */
    static synchronized void nudge(float amount) {
        pushUndo();
        for (Param p : Params.ALL) {
            if (!p.randomizable || locked.contains(p.id)) {
                continue;
            }
            float lo = p.toNorm(p.randMin);
            float hi = p.toNorm(p.randMax);
            float t = p.toNorm(get(p.id)) + (rng.nextFloat() * 2f - 1f) * amount;
            set(p.id, p.toValue(Math.max(lo, Math.min(hi, t))));
        }
    }

    static synchronized void undo() {
        Map<String, Float> previous = undoStack.pollFirst();
        if (previous != null) {
            applyValues(previous);
        }
    }

    /**
     * Back to a fresh install: every parameter at its default (sliders, movers, switches, the music
     * key and scale), every lock off. Only ever called from the Reset button.
     */
    static synchronized void resetAll() {
        pushUndo();
        locked.clear();
        for (Param p : Params.ALL) {
            set(p.id, p.def);
        }
        Modulation.reset();
    }

    /** Called by the service after the patch is open, and again if it restarts. */
    static synchronized void sendAllToPd() {
        for (Param p : Params.ALL) {
            if (p.sendToPd) {
                PdBase.sendFloat(p.id, Modulation.output(p, get(p.id)));
            }
        }
    }

    private static void applyValues(Map<String, Float> map) {
        for (Param p : Params.ALL) {
            if (!p.inPreset) {
                continue;
            }
            Float v = map.get(p.id);
            if (v == null && p.resetWhenAbsent) {
                v = p.def;   // e.g. an older preset has no movers: switch them off
            }
            if (v != null) {
                set(p.id, v);
            }
        }
    }

    private static void pushUndo() {
        undoStack.addFirst(new LinkedHashMap<>(values));
        while (undoStack.size() > MAX_UNDO) {
            undoStack.removeLast();
        }
    }

    // ---- persistence of the last-used state ----

    static synchronized void save(Context context) {
        try {
            JSONObject vals = new JSONObject();
            for (Map.Entry<String, Float> e : values.entrySet()) {
                vals.put(e.getKey(), (double) e.getValue());
            }
            JSONArray locks = new JSONArray();
            for (String id : locked) {
                locks.put(id);
            }
            JSONObject root = new JSONObject();
            root.put("values", vals);
            root.put("locked", locks);
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                    .edit().putString(KEY, root.toString()).apply();
        } catch (JSONException ignored) {
            // Best effort: losing the last-used state is not worth crashing for.
        }
    }

    /** Restore saved state once per process. */
    static synchronized void loadOnce(Context context) {
        if (loaded) {
            return;
        }
        loaded = true;
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String saved = prefs.getString(KEY, null);
        if (saved == null) {
            return;
        }
        try {
            JSONObject root = new JSONObject(saved);
            JSONObject vals = root.optJSONObject("values");
            if (vals != null) {
                Params.upgradeLegacyMovers(vals);
                for (Param p : Params.ALL) {
                    if (vals.has(p.id)) {
                        values.put(p.id, p.clamp((float) vals.getDouble(p.id)));
                    }
                }
            }
            JSONArray locks = root.optJSONArray("locked");
            if (locks != null) {
                for (int i = 0; i < locks.length(); i++) {
                    String id = locks.getString(i);
                    if (Params.byId(id) != null) {
                        locked.add(id);
                    }
                }
            }
        } catch (JSONException ignored) {
            // Corrupt state: fall back to defaults.
        }
    }
}
