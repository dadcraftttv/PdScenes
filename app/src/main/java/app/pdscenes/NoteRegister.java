// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

/**
 * Where the chimes and walking notes sit, from the phone's sensors: a bright place lifts them a little, a dark room
 * lowers them and makes them warmer, a pocket drops them an octave (warm), and climbing stairs lifts them. The pad and
 * bass stay put. Pure logic, ticked by the service; a new register must hold for a few seconds, and changes come at
 * most every few seconds, so a passing shadow or a doorway doesn't make the notes jump.
 */
final class NoteRegister {

    static final int LIGHT_STEPS = 2;          // scale steps up when bright, down when dark
    static final int CLIMB_STEPS = 2;          // extra steps up while climbing
    static final float DARK_ENTER = 0.25f, DARK_LEAVE = 0.32f;     // brightness 0..1, room-relative
    static final float BRIGHT_ENTER = 0.75f, BRIGHT_LEAVE = 0.68f;
    static final float CLIMB_ENTER = 0.5f, CLIMB_LEAVE = 0.3f;
    static final double HOLD_S = 3.0;          // a new register must last this long...
    static final double MIN_GAP_S = 8.0;       // ...and changes come at most this often

    private boolean dark, bright, climbing;
    private int steps;
    private boolean warm;
    private int pendingSteps;
    private boolean pendingWarm;
    private double pendingFor;
    private double sinceChange = MIN_GAP_S;

    void reset() {
        dark = bright = climbing = false;
        steps = 0;
        warm = false;
        pendingSteps = 0;
        pendingWarm = false;
        pendingFor = 0;
        sinceChange = MIN_GAP_S;
    }

    /**
     * Advances by {@code dt} seconds. {@code light} 0 (darkest lately) .. 1 (brightest), {@code climb} -1..1,
     * {@code octave} the scale's size in steps. Returns true when {@link #steps()} or {@link #warm()} changed.
     */
    boolean tick(double dt, float light, boolean pocket, float climb, int octave, boolean enabled) {
        dark = dark ? light < DARK_LEAVE : light < DARK_ENTER;
        bright = bright ? light > BRIGHT_LEAVE : light > BRIGHT_ENTER;
        climbing = climbing ? climb > CLIMB_LEAVE : climb > CLIMB_ENTER;
        int want = 0;
        boolean wantWarm = false;
        if (enabled) {
            if (pocket) {
                want = -octave;
                wantWarm = true;
            } else if (dark) {
                want = -LIGHT_STEPS;
                wantWarm = true;
            } else if (bright) {
                want = LIGHT_STEPS;
            }
            if (climbing) {
                want += CLIMB_STEPS;
            }
        }
        sinceChange += dt;
        if (want == steps && wantWarm == warm) {
            pendingFor = 0;
            return false;
        }
        if (want != pendingSteps || wantWarm != pendingWarm) {
            pendingSteps = want;
            pendingWarm = wantWarm;
            pendingFor = 0;
        }
        pendingFor += dt;
        // switching off (or back to the middle with the feature off) is immediate
        boolean now = !enabled || (pendingFor >= HOLD_S && sinceChange >= MIN_GAP_S);
        if (!now) {
            return false;
        }
        steps = pendingSteps;
        warm = pendingWarm;
        sinceChange = 0;
        return true;
    }

    int steps() {
        return steps;
    }

    boolean warm() {
        return warm;
    }
}
