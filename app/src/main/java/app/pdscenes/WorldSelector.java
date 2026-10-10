// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import java.util.Set;

/**
 * Decides which "world" fits what is going on around the phone: late at night, walking, in a pocket, a loud room
 * or a quiet one. Pure logic with no Android in it. It reacts slowly on purpose: a clap must not flip the sound,
 * and a world only changes after the new situation has lasted a few seconds.
 */
final class WorldSelector {

    static final String GHOST = "ghost";
    static final String KINETIC = "kinetic";
    static final String FLUX = "flux";
    static final String TRANQUIL = "tranquil";
    static final String POCKET = "pocket";
    /** Shaking the phone: comes at once (no waiting), stays while shaking goes on, leaves a few seconds after. */
    static final String UNSTABLE = "unstable";
    static final double UNSTABLE_HOLD_S = 5.0;

    /**
     * Which world wins when several fit: the first one in this list. Pocket comes last: in a pocket the world still
     * follows the time, your walking and the room, and the pocket is a layer on top (the patch's pocket hush). The
     * Pocket world only plays when nothing else fits.
     */
    static final String[] PRIORITY = {UNSTABLE, GHOST, KINETIC, FLUX, TRANQUIL, POCKET};

    static final int NIGHT_START_MINUTE = 0;          // midnight...
    static final int NIGHT_END_MINUTE = 5 * 60;       // ...to 5 AM

    // Room loudness in the same dB units as the mic level reports (see Modulation). Two thresholds each
    // (enter / leave) so a level hovering at the edge doesn't flicker.
    static final float LOUD_ENTER_DB = -28f;
    static final float LOUD_LEAVE_DB = -33f;
    static final float QUIET_ENTER_DB = -50f;
    static final float QUIET_LEAVE_DB = -45f;

    private static final double LEVEL_SMOOTH_S = 3.0;   // loudness is averaged over about this long
    private static final double DWELL_S = 5.0;          // a new situation must last this long...
    private static final double MIN_HOLD_S = 10.0;      // ...and the old world must have run this long
    private static final float NO_READING_DB = -99f;    // the mic level before the patch has reported anything
    /**
     * In a pocket, rustle comes in bursts, so the room is judged by its quietest moments instead: this floor follows
     * the level down at once and creeps up at most this fast. Rustle's gaps keep it down; a loud shop's steady
     * noise lifts it within a few seconds.
     */
    static final float FLOOR_RISE_DB_PER_S = 3f;
    /** The floor sits below the average, and cloth muffles the mic: in a pocket the floor counts this much louder. */
    static final float POCKET_FLOOR_BOOST_DB = 6f;
    /**
     * Flux wants a lively loud place (voices, music, clatter), not a steady roar: running water, a fan or a vacuum
     * is loud but hardly moves. "Liveliness" is how far the level swings from its average (dB, averaged over a few
     * seconds); a steady noise swings about 1 dB, speech and music 5 or more.
     */
    static final float LIVELY_ENTER_DB = 3f;
    static final float LIVELY_LEAVE_DB = 2f;

    private float level = NO_READING_DB;
    private float floor = NO_READING_DB;
    private float swing;
    private boolean lively;
    private boolean haveLevel;
    private boolean loud;
    private boolean quiet;
    private boolean pocket;
    private String active;
    private String pending;
    private double pendingFor;
    private double sinceSwitch = MIN_HOLD_S;

    /** Forget everything (engine start or stop). */
    void reset() {
        level = NO_READING_DB;
        floor = NO_READING_DB;
        swing = 0;
        lively = false;
        haveLevel = false;
        loud = false;
        quiet = false;
        pocket = false;
        active = null;
        pending = null;
        pendingFor = 0;
        sinceSwitch = MIN_HOLD_S;
    }

    /**
     * Advances by {@code dt} seconds and returns the world that should be playing, or null for "none: the
     * user's own settings". Only worlds in {@code allowed} are considered.
     */
    String update(double dt, float levelDb, boolean walking, int minuteOfDay, Set<String> allowed) {
        return update(dt, levelDb, walking, false, minuteOfDay, allowed);
    }

    /** As above, also told whether the phone is in a pocket (see {@link PhoneContext#inPocket()}). */
    String update(double dt, float levelDb, boolean walking, boolean inPocket, int minuteOfDay,
                  Set<String> allowed) {
        return update(dt, levelDb, walking, inPocket, minuteOfDay, Double.MAX_VALUE, allowed);
    }

    /** As above, also told how long ago the phone was shaken (see {@link PhoneContext#secondsSinceShake}). */
    String update(double dt, float levelDb, boolean walking, boolean inPocket, int minuteOfDay, double sinceShake,
                  Set<String> allowed) {
        pocket = inPocket;
        trackLevel(dt, levelDb);
        if (allowed.contains(UNSTABLE) && !walking && sinceShake < UNSTABLE_HOLD_S) {
            sinceSwitch = UNSTABLE.equals(active) ? sinceSwitch + dt : 0;
            active = UNSTABLE;   // no waiting: a shake is a deliberate act
            pending = null;
            return active;
        }
        String wanted = null;
        for (String id : PRIORITY) {
            if (allowed.contains(id) && fits(id, walking, minuteOfDay)) {
                wanted = id;
                break;
            }
        }
        sinceSwitch += dt;
        if (equal(wanted, active)) {
            pending = null;
            return active;
        }
        if (!equal(wanted, pending)) {
            pending = wanted;
            pendingFor = 0;
        }
        pendingFor += dt;
        if (pendingFor >= DWELL_S && sinceSwitch >= MIN_HOLD_S) {
            active = pending;
            pending = null;
            sinceSwitch = 0;
        }
        return active;
    }

    private void trackLevel(double dt, float levelDb) {
        if (levelDb <= NO_READING_DB) {
            return;   // no real reading yet: don't mistake it for a silent room
        }
        if (!haveLevel) {
            level = levelDb;
            floor = levelDb;
            haveLevel = true;
        } else {
            level += (levelDb - level) * (float) (1 - Math.exp(-dt / LEVEL_SMOOTH_S));
            floor = Math.min(levelDb, floor + FLOOR_RISE_DB_PER_S * (float) dt);
            swing += (Math.abs(levelDb - level) - swing) * (float) (1 - Math.exp(-dt / LEVEL_SMOOTH_S));
        }
        if (!lively && swing > LIVELY_ENTER_DB) {
            lively = true;
        } else if (lively && swing < LIVELY_LEAVE_DB) {
            lively = false;
        }
        float room = pocket ? floor + POCKET_FLOOR_BOOST_DB : level;
        if (!loud && room > LOUD_ENTER_DB) {
            loud = true;
        } else if (loud && room < LOUD_LEAVE_DB) {
            loud = false;
        }
        if (!quiet && room < QUIET_ENTER_DB) {
            quiet = true;
        } else if (quiet && room > QUIET_LEAVE_DB) {
            quiet = false;
        }
    }

    private boolean fits(String id, boolean walking, int minuteOfDay) {
        switch (id) {
            case GHOST:
                return minuteOfDay >= NIGHT_START_MINUTE && minuteOfDay < NIGHT_END_MINUTE;
            case KINETIC:
                return walking;
            case POCKET:
                return pocket;
            case UNSTABLE:
                return false;   // decided above, from the shake
            case FLUX:
                return loud && lively;
            default:
                return quiet;
        }
    }

    float levelDb() {
        return level;
    }

    boolean isLoud() {
        return loud;
    }

    boolean isQuiet() {
        return quiet;
    }

    boolean isLively() {
        return lively;
    }

    /** What the selector is hearing, for the event log. */
    String describe() {
        return String.format(java.util.Locale.US, "level %.0f dB, floor %.0f dB, swing %.1f dB%s%s%s%s",
                level, floor, swing, loud ? ", loud" : "", quiet ? ", quiet" : "", lively ? ", lively" : "",
                pocket ? ", in pocket" : "");
    }

    private static boolean equal(String a, String b) {
        return a == null ? b == null : a.equals(b);
    }
}
