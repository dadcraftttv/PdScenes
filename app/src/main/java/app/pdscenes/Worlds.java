// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import android.content.Context;
import android.content.SharedPreferences;

import java.util.Calendar;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

/**
 * "Auto worlds": while the built-in effects run, the app notices what is going on around the phone (late at
 * night, walking, a loud room, a quiet room, see {@link WorldSelector}) and fades the sliders to a preset chosen
 * for that situation. When no situation applies, the user's own settings fade back in. Locked sliders are left
 * alone. Everything happens on the main thread, driven by the service's mover tick.
 */
final class Worlds {

    /** One automatic situation. */
    static final class World {
        final String id;
        final String title;
        final String when;
        final String defaultPreset;
        /** False: the world starts out switched off (its preset is still there to pick). */
        final boolean onByDefault;

        World(String id, String title, String when, String defaultPreset) {
            this(id, title, when, defaultPreset, true);
        }

        World(String id, String title, String when, String defaultPreset, boolean onByDefault) {
            this.id = id;
            this.title = title;
            this.when = when;
            this.defaultPreset = defaultPreset;
            this.onByDefault = onByDefault;
        }
    }

    static final World[] ALL = {
            new World(WorldSelector.TRANQUIL, "Tranquil", "quiet room", "Tranquil realm"),
            new World(WorldSelector.FLUX, "Flux", "loud room", "Flux realm"),
            new World(WorldSelector.KINETIC, "Kinetic", "walking", "Kinetic realm"),
            new World(WorldSelector.GHOST, "Ghost", "midnight to 5 AM", "Ghost realm"),
            new World(WorldSelector.POCKET, "Pocket", "phone in a pocket", "Pocket realm"),
            new World(WorldSelector.UNSTABLE, "Unstable", "shaking the phone", "Unstable realm", false),   // Samuel: opt-in
    };

    /** Stored in place of a preset name when the user switches a world off. */
    static final String NONE = "";

    private static final String PREFS = "pdscenes_worlds";
    private static final String KEY_ENABLED = "enabled";
    private static final String KEY_PRESET_PREFIX = "preset_";
    private static final String KEY_SKIP_PREFIX = "skip_";   // skip_<world>_<group>: that Realm leaves the group alone

    /**
     * Realm ingredients: the groups of sections a Realm may change. Each Realm can leave any group at the user's own
     * settings ("this Realm uses it" off), like a locked slider. {id, title, sections...}
     */
    static final String[][] GROUPS = {
            {"rhythm", "Rhythm", "beat"},
            {"music", "Music", "music"},
            {"mix", "Mix (the level of each part)", "mix"},
            {"echo", "Echo", "echo"},
            {"reverb", "Reverb", "reverb"},
            {"glitch", "Glitch", "glitch", "reverse"},
            {"color", "Color (ring, pitch, crush, distortion, filter)", "ring", "pitch", "crush", "dist", "filter"},
            {"motion", "Motion (chorus, flanger, phaser, tremolo)", "chorus", "flange", "phaser", "tremolo"},
            {"space", "Space and dry level", "space", "main"},
    };
    private static final Map<String, Set<String>> skipped = new HashMap<>();   // world -> groups it leaves alone
    private static final Set<String> touched = new HashSet<>();                  // params a Realm set since home

    private static final double RAMP_S = 3.0;               // how long the sliders take to fade to a new world
    private static final double FAST_RAMP_S = 0.3;          // ...except into Unstable, which answers a shake at once
    private static double rampS = RAMP_S;
    private static final double NOTIFY_EVERY_S = 0.25;      // how often the screen is told during a fade

    private static final WorldSelector selector = new WorldSelector();
    private static final Map<String, String> presetFor = new HashMap<>();
    private static final Set<String> allowed = new HashSet<>();
    private static Context app;
    private static boolean enabled;

    private static String current;                  // the world playing now, null for the user's own settings
    private static Map<String, Float> home;         // the user's own settings, kept while a world is playing
    private static Map<String, Float> from;
    private static Map<String, Float> to;
    private static double ramp = 1;                 // 0..1; 1 = not fading
    private static double sinceNotify;
    private static Runnable listener;
    /** While held, the world playing now stays (doorways and shops flip light and loudness every few seconds). */
    private static boolean held;

    private Worlds() { }

    // ---- settings ----

    /** The new name of a built-in preset from before Worlds became Realms ("Flux world" -> "Flux realm"), else null. */
    static String renamedBuiltIn(String name) {
        if (name == null || !name.endsWith(" world")) {
            return null;
        }
        String realm = name.substring(0, name.length() - " world".length()) + " realm";
        return PresetManager.builtIn(realm) != null ? realm : null;
    }

    static void load(Context context) {
        app = context.getApplicationContext();
        SharedPreferences prefs = prefs();
        enabled = prefs.getBoolean(KEY_ENABLED, false);
        presetFor.clear();
        for (World w : ALL) {
            String chosen = prefs.getString(KEY_PRESET_PREFIX + w.id, w.onByDefault ? w.defaultPreset : NONE);
            String renamed = renamedBuiltIn(chosen);
            if (renamed != null) {                  // "Kinetic world" became "Kinetic realm": keep the choice
                chosen = renamed;
                prefs.edit().putString(KEY_PRESET_PREFIX + w.id, chosen).apply();
            }
            presetFor.put(w.id, chosen);
            Set<String> skip = new HashSet<>();
            for (String[] g : GROUPS) {
                if (prefs.getBoolean(KEY_SKIP_PREFIX + w.id + "_" + g[0], false)) {
                    skip.add(g[0]);
                }
            }
            skipped.put(w.id, skip);
        }
        updateAllowed();
    }

    private static SharedPreferences prefs() {
        return app.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    static boolean isEnabled() {
        return enabled;
    }

    static void setEnabled(boolean on) {
        enabled = on;
        prefs().edit().putBoolean(KEY_ENABLED, on).apply();
        if (!on) {
            selector.reset();
            switchTo(null);   // fade the user's own settings back
        }
    }

    /** Auto worlds back to a fresh install: off, each world on its own default preset. */
    static void resetSettings() {
        reset();   // the user's own values come back first, if a world was playing
        if (app == null) {
            return;
        }
        prefs().edit().clear().apply();
        load(app);
    }

    /** The preset a world plays, or {@link #NONE}. */
    static String presetName(String worldId) {
        String name = presetFor.get(worldId);
        return name == null ? NONE : name;
    }

    static void setPreset(String worldId, String presetName) {
        presetFor.put(worldId, presetName);
        prefs().edit().putString(KEY_PRESET_PREFIX + worldId, presetName).apply();
        updateAllowed();
    }

    /** Whether a Realm changes a group of sections (its ingredient switch). */
    static boolean uses(String worldId, String groupId) {
        Set<String> skip = skipped.get(worldId);
        return skip == null || !skip.contains(groupId);
    }

    static void setUses(String worldId, String groupId, boolean on) {
        skipped.computeIfAbsent(worldId, k -> new HashSet<>());
        if (on) {
            skipped.get(worldId).remove(groupId);
        } else {
            skipped.get(worldId).add(groupId);
        }
        if (app != null) {
            prefs().edit().putBoolean(KEY_SKIP_PREFIX + worldId + "_" + groupId, !on).apply();
        }
        if (worldId.equals(current)) {
            switchTo(current);   // a change to the Realm playing now applies at once (the group fades home or in)
        }
    }

    /** The ingredient group a parameter belongs to, or null (always the Realm's). */
    static String groupOf(Param p) {
        for (String[] g : GROUPS) {
            for (int i = 2; i < g.length; i++) {
                if (g[i].equals(p.section)) {
                    return g[0];
                }
            }
        }
        return null;
    }

    private static boolean realmChanges(String worldId, Param p) {
        String g = groupOf(p);
        return g == null || uses(worldId, g);
    }

    private static void updateAllowed() {
        allowed.clear();
        for (World w : ALL) {
            if (!NONE.equals(presetName(w.id))) {
                allowed.add(w.id);
            }
        }
    }

    /** What the automatic choice is hearing (loudness, floor, liveliness), for the event log. */
    static String hearing() {
        return selector.describe();
    }

    static boolean isHeld() {
        return held;
    }

    /** Hold the current world (or the user's own settings) until released. Only for this run of the engine. */
    static void setHeld(boolean on) {
        held = on;
        notifyListener();
    }

    /** The room as the automatic choice judges it: level (dB) and whether it counts as quiet, loud, lively. */
    static float roomLevelDb() {
        return selector.levelDb();
    }

    static boolean roomQuiet() {
        return selector.isQuiet();
    }

    static boolean roomLoud() {
        return selector.isLoud();
    }

    static boolean roomLively() {
        return selector.isLively();
    }

    /** The world playing now, or null. */
    static String currentWorld() {
        return current;
    }

    /** Called (on the main thread) when the world changes and while the sliders fade. */
    static void setListener(Runnable l) {
        listener = l;
    }

    // ---- running ----

    /** Engine start or stop: the user's own settings come back at once and the app forgets what it saw. */
    static void reset() {
        if (home != null) {
            for (Map.Entry<String, Float> e : home.entrySet()) {
                if (touched.contains(e.getKey())) {    // only what a Realm changed (a skipped group stays the user's)
                    ParamStore.set(e.getKey(), e.getValue());
                }
            }
            if (app != null) {
                ParamStore.save(app);   // don't leave a world's values as the "last used" settings
            }
        }
        home = null;
        touched.clear();
        from = null;
        to = null;
        current = null;
        held = false;
        ramp = 1;
        selector.reset();
        notifyListener();
    }

    /** Called about 30 times a second while the built-in effects run. */
    static void tick(double dt, float micLevelDb, boolean walking, int minuteOfDay) {
        tick(dt, micLevelDb, walking, false, minuteOfDay);
    }

    static void tick(double dt, float micLevelDb, boolean walking, boolean inPocket, int minuteOfDay) {
        tick(dt, micLevelDb, walking, inPocket, minuteOfDay, Double.MAX_VALUE);
    }

    static void tick(double dt, float micLevelDb, boolean walking, boolean inPocket, int minuteOfDay,
                     double sinceShake) {
        if (enabled && held) {
            selector.update(dt, micLevelDb, walking, inPocket, minuteOfDay, sinceShake, allowed);   // keep listening, change nothing
        } else if (enabled) {
            String next = selector.update(dt, micLevelDb, walking, inPocket, minuteOfDay, sinceShake, allowed);
            if (!equal(next, current)) {
                switchTo(next);
            }
        }
        advance(dt);
    }

    /** Minutes since midnight on the phone's clock. */
    static int minuteOfDayNow() {
        Calendar now = Calendar.getInstance();
        return now.get(Calendar.HOUR_OF_DAY) * 60 + now.get(Calendar.MINUTE);
    }

    private static void switchTo(String world) {
        Map<String, Float> target;
        if (world == null) {
            target = home;
            if (target != null) {        // only what a Realm changed goes back (a group it left alone stays the user's)
                Map<String, Float> back = new LinkedHashMap<>();
                for (String id : touched) {
                    if (home.containsKey(id)) {
                        back.put(id, home.get(id));
                    }
                }
                target = back;
                touched.clear();
            }
        } else {
            Map<String, Float> preset = loadPreset(presetName(world));
            target = null;
            if (preset != null) {
                if (current == null) {
                    home = presetValues();   // remember the user's own settings before the first Realm
                    touched.clear();
                }
                // its own groups come from its preset; what the last Realm changed but this one leaves alone goes home
                target = new LinkedHashMap<>();
                Set<String> mine = new HashSet<>();
                for (Map.Entry<String, Float> e : preset.entrySet()) {
                    Param p = Params.byId(e.getKey());
                    if (p != null && realmChanges(world, p)) {
                        target.put(e.getKey(), e.getValue());
                        mine.add(e.getKey());
                    }
                }
                for (String id : touched) {
                    if (!mine.contains(id) && home != null && home.containsKey(id)) {
                        target.put(id, home.get(id));
                    }
                }
                touched.clear();
                touched.addAll(mine);
            }
        }
        current = world;
        rampS = WorldSelector.UNSTABLE.equals(world) ? FAST_RAMP_S : RAMP_S;
        if (target != null) {
            from = presetValues();
            to = target;
            ramp = 0;
            sinceNotify = 0;
        }
        if (world == null && target != null) {
            home = null;   // handed back; it is the fade's target now
        }
        notifyListener();
    }

    /** A preset's values for every preset parameter, filling gaps the way loading a preset does. */
    private static Map<String, Float> loadPreset(String name) {
        Map<String, Float> raw = PresetManager.builtIn(name);
        if (raw == null && app != null) {
            raw = PresetManager.readUser(app, name);
        }
        if (raw == null) {
            return null;
        }
        Map<String, Float> full = new LinkedHashMap<>();
        for (Param p : Params.ALL) {
            if (!p.inPreset) {
                continue;
            }
            Float v = raw.get(p.id);
            if (v == null && p.resetWhenAbsent) {
                v = p.def;   // an older preset knows nothing of this setting: switch it off
            }
            if (v != null) {
                full.put(p.id, v);
            }
        }
        return full;
    }

    private static Map<String, Float> presetValues() {
        Map<String, Float> now = new LinkedHashMap<>();
        for (Param p : Params.ALL) {
            if (p.inPreset) {
                now.put(p.id, ParamStore.get(p.id));
            }
        }
        return now;
    }

    private static void advance(double dt) {
        if (ramp >= 1 || to == null) {
            return;
        }
        ramp = Math.min(1, ramp + dt / rampS);
        for (Map.Entry<String, Float> e : to.entrySet()) {
            Param p = Params.byId(e.getKey());
            if (p == null || ParamStore.isLocked(p.id) || isBypassSwitch(p)) {
                continue;
            }
            Float start = from.get(p.id);
            float target = e.getValue();
            float value;
            if (start == null || ramp >= 1) {
                value = target;
            } else if (p.toggle || p.choices != null) {
                value = ramp >= 0.5 ? target : start;   // switches and menus can't be half way
            } else {
                float n = p.toNorm(start) + (p.toNorm(target) - p.toNorm(start)) * (float) ramp;
                value = p.toValue(n);
            }
            if (Math.abs(value - ParamStore.get(p.id)) > 1e-4f * (p.max - p.min)) {
                ParamStore.set(p.id, value);
            }
        }
        sinceNotify += dt;
        if (ramp >= 1) {
            from = null;
            to = null;
            notifyListener();
        } else if (sinceNotify >= NOTIFY_EVERY_S) {
            sinceNotify = 0;
            notifyListener();
        }
    }

    /** The "... enabled" switches are the user's own bypass buttons: a world never flips them. */
    private static boolean isBypassSwitch(Param p) {
        return p.toggle && p.id.endsWith("_on");
    }

    private static void notifyListener() {
        Runnable l = listener;
        if (l != null) {
            l.run();
        }
    }

    private static boolean equal(String a, String b) {
        return a == null ? b == null : a.equals(b);
    }
}
