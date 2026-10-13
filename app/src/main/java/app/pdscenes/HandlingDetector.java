// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

/**
 * Handling noise: the phone being tapped, gripped, rubbed or fiddled with makes the mic hear it loudly, and the phone
 * itself moves at that moment (a clap across the room doesn't shake it). The measure is the jerk: how much the
 * acceleration changes from one reading to the next (200 a second). Measured on Samuel's phone (Oct 13): flat on a
 * table ~0, held still 0.1-0.3, walking with it in hand 0.4-0.9 (once 2.0), rubbing and fiddling 0.6-1.7 all the
 * time, finger taps 4-7, grip changes 2.5-8.
 * So a JOLT is a reading over JOLT_JERK, walking or not (a tap or a grip), and FIDDLING is the jerk staying up while
 * not walking (rubbing; walking makes the same kind of jitter). Fed from the sensor thread. Pure logic (test H).
 */
final class HandlingDetector {

    static final float JOLT_JERK = 3.0f;          // m/s^2 change between readings: a tap or a grip
    static final double JOLT_GAP_S = 0.1;         // one jolt per tap (a tap rings for a few readings)
    static final double JOLT_FADE_S = 0.3;        // a jolt's share of the handling level fades over this
    static final float FIDDLE_LOW = 0.7f;         // the jerk's recent peak from here (held still is under 0.3)...
    static final float FIDDLE_FULL = 2.0f;        // ...to here is fiddling, 0 to 1
    static final double PEAK_RELEASE_S = 0.25;    // the recent peak lets go over this

    private static final float[] prev = new float[3];
    private static double lastT = -1;
    private static double lastJolt = -1e9;
    private static float peak;
    private static float level;
    private static int jolts;

    private HandlingDetector() { }

    static synchronized void reset() {
        lastT = -1;
        lastJolt = -1e9;
        peak = 0;
        level = 0;
        jolts = 0;
    }

    /**
     * One accelerometer reading (m/s^2) at {@code t} seconds, and whether the person is walking.
     * Returns true when it is a jolt (a tap or a grip), once per jolt.
     */
    static synchronized boolean onAcceleration(float x, float y, float z, double t, boolean walking) {
        if (lastT < 0 || t - lastT > 0.5) {   // first reading, or after a gap: no change to measure yet
            prev[0] = x;
            prev[1] = y;
            prev[2] = z;
            lastT = t;
            return false;
        }
        double dt = t - lastT;
        lastT = t;
        float dx = x - prev[0], dy = y - prev[1], dz = z - prev[2];
        prev[0] = x;
        prev[1] = y;
        prev[2] = z;
        float jerk = (float) Math.sqrt(dx * dx + dy * dy + dz * dz);
        peak = Math.max(jerk, peak * (float) Math.exp(-dt / PEAK_RELEASE_S));
        boolean jolt = jerk > JOLT_JERK && t - lastJolt >= JOLT_GAP_S;
        if (jolt) {
            lastJolt = t;
            jolts++;
        }
        float fiddle = walking ? 0f : clamp((peak - FIDDLE_LOW) / (FIDDLE_FULL - FIDDLE_LOW));
        float joltPart = (float) Math.exp(-(t - lastJolt) / JOLT_FADE_S);
        level = Math.max(fiddle, joltPart);
        return jolt;
    }

    /** How much the phone is being handled now: 0 = not at all, 1 = a jolt just now or steady fiddling. */
    static synchronized float level() {
        return level;
    }

    /** Jolts since the last reset (for tests). */
    static synchronized int jolts() {
        return jolts;
    }

    private static float clamp(float v) {
        return v < 0 ? 0 : v > 1 ? 1 : v;
    }
}
