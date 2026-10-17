// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import org.puredata.core.PdBase;

import java.util.ArrayDeque;
import java.util.HashMap;
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
        if ((Kits.ID.equals(id) || id.startsWith("kitp_")) && AudioService.isRunning()) {
            sendKit(false);
        }
        if (p.sendToPd && AudioService.isRunning()) {
            PdBase.sendFloat(id, Modulation.output(p, v));
            if (Intensity.ID.equals(id)) {   // everything Intensity scales goes out again
                for (String s : Intensity.scaled()) {
                    Param q = Params.byId(s);
                    if (q != null) {
                        PdBase.sendFloat(s, Modulation.output(q, get(s)));
                    }
                }
            }
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
        morph.clear();
        pushUndo();
        applyValues(preset);
    }

    /** The most a budget slider may be set to now: its max minus what the others in its budget already take. */
    static synchronized float budgetRoom(Param p) {
        if (p.budget == null) {
            return p.max;
        }
        float others = 0;
        for (Param q : Params.ALL) {
            if (q != p && p.budget.equals(q.budget)) {
                others += get(q.id);
            }
        }
        return Math.max(0f, p.max - others);
    }

    /** Jump every unlocked, randomizable parameter to a random value in its safe range. */
    static synchronized void randomize() {
        pushUndo();
        morph.clear();
        Map<String, Float> targets = new LinkedHashMap<>();
        for (Param p : Params.ALL) {
            if (!p.randomizable || locked.contains(p.id)) {
                continue;
            }
            float lo = p.toNorm(p.randMin);
            float hi = p.toNorm(p.randMax);
            targets.put(p.id, p.toValue(lo + rng.nextFloat() * (hi - lo)));
        }
        // a budget (the glitch matrix) that came out past its max is scaled down to fit; locked members keep theirs
        Map<String, Float> fixed = new HashMap<>();   // what the members the dice leave alone take
        Map<String, Float> free = new HashMap<>();    // what the dice picked for the others
        for (Param p : Params.ALL) {
            if (p.budget != null) {
                Float t = targets.get(p.id);
                (t != null ? free : fixed).merge(p.budget, t != null ? t : get(p.id), Float::sum);
            }
        }
        for (Param p : Params.ALL) {
            Float t = targets.get(p.id);
            if (p.budget != null && t != null) {
                float f = fixed.getOrDefault(p.budget, 0f);
                float picked = free.get(p.budget);
                if (f + picked > p.max && picked > 0) {
                    targets.put(p.id, t * Math.max(0f, p.max - f) / picked);
                }
            }
        }
        for (Map.Entry<String, Float> e : targets.entrySet()) {
            Param p = Params.byId(e.getKey());
            float target = e.getValue();
            if (AudioService.isRunning()) {
                morph.put(p.id, new float[]{get(p.id), target, get(p.id)});   // from, to, last written
            } else {
                set(p.id, target);   // nothing to hear: jump
            }
        }
        morphT = 0;
    }

    // ---- dice morph: Randomize glides to its new sound instead of jumping ----
    static final double MORPH_S = 6.0;
    private static final Map<String, float[]> morph = new LinkedHashMap<>();
    private static double morphT;

    static synchronized boolean isMorphing() {
        return !morph.isEmpty();
    }

    /** Stop a glide where it is (undo, presets, reset, nudge). */
    static synchronized void stopMorph() {
        morph.clear();
    }

    /**
     * Advance the glide (called by the service's 30 Hz tick). Sliders move with an ease in and out; switches
     * and menus change halfway. A slider someone (a hand, a world) moved meanwhile is left where it was put.
     */
    static synchronized void morphTick(double dt) {
        if (morph.isEmpty()) {
            return;
        }
        morphT = Math.min(1, morphT + dt / MORPH_S);
        double e = morphT * morphT * (3 - 2 * morphT);
        java.util.Iterator<Map.Entry<String, float[]>> it = morph.entrySet().iterator();
        while (it.hasNext()) {
            Map.Entry<String, float[]> en = it.next();
            Param p = Params.byId(en.getKey());
            float[] m = en.getValue();
            if (get(p.id) != m[2]) {
                it.remove();   // someone else moved it
                continue;
            }
            float v;
            if (p.toggle || p.choices != null) {
                v = e >= 0.5 ? m[1] : m[0];
            } else {
                float a = p.toNorm(m[0]);
                v = p.toValue((float) (a + (p.toNorm(m[1]) - a) * e));
            }
            set(p.id, v);
            m[2] = get(p.id);
        }
        if (morphT >= 1) {
            morph.clear();
        }
    }

    /** Move every unlocked, randomizable parameter a little (amount is a slider fraction). */
    static synchronized void nudge(float amount) {
        morph.clear();
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
        morph.clear();
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
        morph.clear();
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
        sendKit(true);
    }

    /** Each part's kit (the Kit, or the part's own "from" choice), as messages to its kit voice (Kits); only the
     *  parts that changed unless `all`. */
    static void sendKit(boolean all) {
        int[] from = new int[Kits.PARTS.length];
        for (int k = 0; k < from.length; k++) {
            from[k] = Math.round(get("kitp_" + Kits.PARTS[k]));
        }
        Kits.send(Math.round(get(Kits.ID)), from, all, (recv, sel, val) -> PdBase.sendMessage(recv, sel, val));
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
