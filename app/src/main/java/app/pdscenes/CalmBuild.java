// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import java.util.HashMap;
import java.util.Map;

/**
 * Calm builds (roadmap item 8, Samuel Oct 14; "Calm builds" switch in Music, off by default, the user's own, not in
 * presets): standing still in a calm room for a while, the music slowly grows a layer at a time, holds, eases back,
 * then rests. Walking or a lively, loud room fades it away within seconds. Like Intensity it never changes a stored
 * value: {@link #apply} lifts what is sent to Pd (only what is already on), and the patch hears {@code calm_chimes}
 * for a gentle extra chance of standing-still chimes. Fed once per service tick. Pure logic (test B).
 */
final class CalmBuild {

    static final String ID = "calm_build";
    static final double WAIT_S = 30;      // this long standing still in a calm room before a build starts
    static final double RISE_S = 180;     // then it grows over this long...
    static final double HOLD_S = 60;      // ...holds...
    static final double FALL_S = 120;     // ...and eases back over this long
    static final double REST_S = 180;     // after a whole build, at least this long before the next one
    static final double DROP_S = 5;       // walking or a lively room: gone in about this long

    enum Phase { WAITING, RISING, HOLDING, FALLING, RESTING }

    /** Layers join one after another: {where along the build it starts (0..1)} per layer. */
    static final float PAD = 0f, ROOM = 0.25f, CHIMES = 0.5f, OPEN = 0.75f;

    /** {layer start, lift at the peak} per parameter. */
    private static final Map<String, float[]> RULES = new HashMap<>();

    static {
        RULES.put("music_pad", new float[]{PAD, 0.4f});
        RULES.put("music_res", new float[]{ROOM, 0.4f});
        RULES.put("music_harm", new float[]{OPEN, 0.4f});
        RULES.put("reverb_mix", new float[]{OPEN, 0.4f});
    }

    private static Phase phase = Phase.WAITING;
    private static double phaseS;          // time in the current phase (WAITING: calm time so far)
    private static float level;            // 0..1: how far the build has grown

    private CalmBuild() { }

    static synchronized void reset() {
        phase = Phase.WAITING;
        phaseS = 0;
        level = 0;
    }

    /**
     * One tick: {@code calm} = standing still in a calm room with the music on and the switch on.
     * Returns true when a build has just started or just ended (for the event log).
     */
    static synchronized boolean tick(double dt, boolean calm) {
        Phase before = phase;
        if (!calm && phase != Phase.RESTING) {
            // interrupted (or switched off): fade away fast, then wait for calm again
            level = (float) Math.max(0, level - dt / DROP_S);
            phase = Phase.WAITING;
            phaseS = 0;
            return before != Phase.WAITING && before != Phase.RESTING;
        }
        phaseS += dt;
        switch (phase) {
            case WAITING:
                level = (float) Math.max(0, level - dt / DROP_S);
                if (phaseS >= WAIT_S && level == 0) {
                    next(Phase.RISING);
                }
                break;
            case RISING:
                level = (float) Math.min(1, phaseS / RISE_S);
                if (phaseS >= RISE_S) {
                    next(Phase.HOLDING);
                }
                break;
            case HOLDING:
                level = 1;
                if (phaseS >= HOLD_S) {
                    next(Phase.FALLING);
                }
                break;
            case FALLING:
                level = (float) Math.max(0, 1 - phaseS / FALL_S);
                if (phaseS >= FALL_S) {
                    next(Phase.RESTING);
                }
                break;
            case RESTING:
                level = 0;
                if (phaseS >= REST_S) {
                    next(Phase.WAITING);
                }
                break;
        }
        return (before == Phase.WAITING && phase == Phase.RISING) || (before == Phase.FALLING && phase == Phase.RESTING);
    }

    private static void next(Phase p) {
        phase = p;
        phaseS = 0;
    }

    static synchronized float level() {
        return level;
    }

    static synchronized Phase phase() {
        return phase;
    }

    /** How far one layer has joined (0..1) at the current build level. */
    static float layer(float start) {
        float l = level();
        return start >= 1 ? 0 : Math.max(0, Math.min(1, (l - start) / (1 - start)));
    }

    static boolean scales(String id) {
        return RULES.containsKey(id);
    }

    static Iterable<String> scaled() {
        return RULES.keySet();
    }

    /** The value to send for {@code p}: lifted by its layer, only if it is already on, never past the slider's top. */
    static float apply(Param p, float value) {
        float[] r = RULES.get(p.id);
        if (r == null || value <= p.min) {
            return value;
        }
        float lift = r[1] * layer(r[0]);
        return lift <= 0 ? value : Math.min(p.max, value * (1 + lift));
    }
}
