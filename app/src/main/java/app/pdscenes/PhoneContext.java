// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

/**
 * What the phone's environment sensors say, boiled down to a few easy numbers. Pure logic with no Android in
 * it. Light, proximity and air pressure (barometer) arrive from {@link SensorInput} on its own thread; the
 * movers and the automatic worlds read the results from the main thread.
 * <ul>
 * <li>{@link #brightness()} 0 (dark) to 1 (bright), judged against the light of where you are now, so covering
 * the sensor in a lit room reads dark and a steady room reads about the middle.</li>
 * <li>{@link #inPocket()} true once something has been right against the proximity sensor for a moment and
 * the light is dim (or there is no light sensor).</li>
 * <li>{@link #climb()} -1 (going down stairs or a lift) to +1 (going up), from how fast the air pressure
 * changes.</li>
 * </ul>
 * Also converts the fused rotation vector into a compass heading ({@link #headingDegrees}).
 */
final class PhoneContext {

    /** Below this many lux, with something against the sensor, the phone counts as pocketed. */
    static final float POCKET_MAX_LUX = 10f;
    /** Something has to stay against the proximity sensor this long (seconds) before it counts. */
    static final double POCKET_DWELL_S = 1.0;
    /** About 100,000 lux (direct sun) is full scale, 1 lux (a dim room) is zero. */
    private static final double LUX_FULL_SCALE_LOG = 5.0;
    /** How long (time constant, seconds) the room's darkest and brightest light are remembered. */
    static final double ROOM_MEMORY_S = 90.0;
    /** A change has to span at least this much (log10 lux, so 10x) to cover the whole 0..1 range. */
    private static final double MIN_SPAN_LOG = 1.0;
    /** Share of brightness that follows the fixed sun scale, so a sunny street still reads above a dark room. */
    private static final double ABSOLUTE_SHARE = 0.25;
    /** The fast and slow averages of air pressure; their gap is proportional to the climb rate. */
    private static final double FAST_TAU_S = 2.0;
    private static final double SLOW_TAU_S = 8.0;
    /** A gap of this many hPa (fast below slow) counts as a full-scale climb: about 0.2 m/s of climbing. */
    static final float CLIMB_FULL_HPA = 0.10f;

    private static volatile boolean haveLight;
    private static volatile float lux;
    /** Light level in log10(1 + lux), the room's remembered darkest and brightest, and when they were set. */
    private static double level, darkRef, brightRef, lightAt;
    private static volatile boolean haveProximity;
    private static volatile boolean near;
    private static volatile double nearSince = Double.MAX_VALUE;
    private static volatile float climb;
    private static double fastP, slowP, lastPressureAt;
    private static boolean havePressure;
    /**
     * Which end of the phone points down. The main mic sits on the bottom edge, so "mic down" means the top edge
     * points up (gravity along +y in Android's axes). Averaged over about a second so walking doesn't flip it,
     * with two thresholds so it doesn't flicker when the phone lies flat-ish.
     */
    static final double TILT_TAU_S = 1.0;
    static final float MIC_DOWN_ENTER = 0.5f;
    static final float MIC_DOWN_LEAVE = 0.3f;
    private static double upY, lastTiltAt;
    private static boolean haveTilt;
    private static volatile boolean micDown;

    // Shaking the phone: three hard jolts (the pull with gravity taken out, past 1.2 g) within 1.5 s. Putting the
    // phone down or a bump is one jolt; walking bumps stay well under 1 g. (Running is ruled out by the caller.)
    static final double SHAKE_JOLT_G = 1.2;
    static final double SHAKE_RELEASE_G = 0.5;
    static final double SHAKE_WINDOW_S = 1.5;
    static final int SHAKE_JOLTS = 3;
    private static final double[] jolts = new double[SHAKE_JOLTS];
    private static int joltCount;
    private static boolean inJolt;
    private static double lastShake = -1e9;

    private PhoneContext() { }

    /** An accelerometer reading (m/s&sup2;, Android axes) at time {@code at} (seconds). */
    static synchronized void onAcceleration(float x, float y, float z, double at) {
        double g = Math.sqrt(x * x + y * y + z * z);
        if (g < 1e-3) {
            return;
        }
        double jolt = Math.abs(g - 9.80665) / 9.80665;
        if (!inJolt && jolt > SHAKE_JOLT_G) {
            inJolt = true;
            jolts[joltCount % SHAKE_JOLTS] = at;
            joltCount++;
            if (joltCount >= SHAKE_JOLTS && at - jolts[joltCount % SHAKE_JOLTS] <= SHAKE_WINDOW_S) {
                lastShake = at;   // (the slot about to be reused holds the oldest of the last three)
            }
        } else if (inJolt && jolt < SHAKE_RELEASE_G) {
            inJolt = false;
        }
        double ny = y / g;
        if (!haveTilt || at - lastTiltAt > 5.0) {
            upY = ny;
            haveTilt = true;
        } else {
            upY += (ny - upY) * (1 - Math.exp(-(at - lastTiltAt) / TILT_TAU_S));
        }
        lastTiltAt = at;
        if (!micDown && upY > MIC_DOWN_ENTER) {
            micDown = true;
        } else if (micDown && upY < MIC_DOWN_LEAVE) {
            micDown = false;
        }
    }

    /** Seconds since the phone was last shaken (same clock as {@link #onAcceleration}); huge if never. */
    static synchronized double secondsSinceShake(double at) {
        return at - lastShake;
    }

    /** True while the bottom edge (where the main mic is) points down, as when the phone goes into a pocket mic first. */
    static boolean micDown() {
        return micDown;
    }

    static double now() {
        return System.nanoTime() / 1e9;
    }

    /** Forget everything (engine start or stop). */
    static synchronized void reset() {
        haveTilt = false;
        micDown = false;
        joltCount = 0;
        inJolt = false;
        lastShake = -1e9;
        haveLight = false;
        lux = 0;
        haveProximity = false;
        near = false;
        nearSince = Double.MAX_VALUE;
        climb = 0;
        havePressure = false;
    }

    static void onLight(float luxValue) {
        onLight(luxValue, now());
    }

    /** {@code at} is any steadily increasing clock in seconds, the same one later given to {@link #brightness(double)}. */
    static synchronized void onLight(float luxValue, double at) {
        lux = Math.max(0f, luxValue);
        double v = Math.log10(1.0 + lux);
        if (!haveLight) {
            darkRef = brightRef = v;
        } else {
            // A darker or brighter moment than remembered becomes the new edge of the room at once.
            darkRef = Math.min(relaxed(darkRef, at), v);
            brightRef = Math.max(relaxed(brightRef, at), v);
        }
        level = v;
        lightAt = at;
        haveLight = true;
    }

    /** A remembered edge fades toward the current light (the light sensor only reports changes). */
    private static double relaxed(double ref, double at) {
        return level + (ref - level) * Math.exp(-Math.max(0, at - lightAt) / ROOM_MEMORY_S);
    }

    static void onProximity(boolean isNear) {
        onProximity(isNear, now());
    }

    static void onProximity(boolean isNear, double at) {
        haveProximity = true;
        if (isNear && !near) {
            nearSince = at;
        } else if (!isNear) {
            nearSince = Double.MAX_VALUE;
        }
        near = isNear;
    }

    /** Air pressure in hPa. {@code at} is any steadily increasing clock in seconds. */
    static synchronized void onPressure(float hPa, double at) {
        if (!havePressure || at - lastPressureAt > 30) {
            fastP = slowP = hPa;
            havePressure = true;
            climb = 0;
        } else {
            double dt = Math.max(0, at - lastPressureAt);
            fastP += (hPa - fastP) * (1 - Math.exp(-dt / FAST_TAU_S));
            slowP += (hPa - slowP) * (1 - Math.exp(-dt / SLOW_TAU_S));
            // Going up: pressure falls, so the fast average sits below the slow one.
            float gap = (float) (slowP - fastP);
            climb = Math.max(-1f, Math.min(1f, gap / CLIMB_FULL_HPA));
        }
        lastPressureAt = at;
    }

    static float lux() {
        return lux;
    }

    static boolean haveLight() {
        return haveLight;
    }

    static boolean near() {
        return near;
    }

    static float brightness() {
        return brightness(now());
    }

    /**
     * 0 (dark) to 1 (bright), mostly relative to the room: where the light sits between the darkest and brightest
     * of the last minute or two, plus a little of the fixed sun scale. 0.5 (no change) without a light sensor.
     */
    static synchronized float brightness(double at) {
        if (!haveLight) {
            return 0.5f;
        }
        double lo = relaxed(darkRef, at), hi = relaxed(brightRef, at);
        if (hi - lo < MIN_SPAN_LOG) {   // steady light or small flicker: stay near the middle
            double mid = (lo + hi) / 2;
            lo = mid - MIN_SPAN_LOG / 2;
            hi = mid + MIN_SPAN_LOG / 2;
        }
        double relative = clamp01((level - lo) / (hi - lo));
        double absolute = clamp01(level / LUX_FULL_SCALE_LOG);
        return (float) ((1 - ABSOLUTE_SHARE) * relative + ABSOLUTE_SHARE * absolute);
    }

    private static double clamp01(double v) {
        return Math.max(0, Math.min(1, v));
    }

    static boolean inPocket() {
        return inPocket(now());
    }

    static synchronized boolean inPocket(double at) {   // several fields, read together under the lock
        if (!haveProximity || !near || at - nearSince < POCKET_DWELL_S) {
            return false;
        }
        return !haveLight || lux < POCKET_MAX_LUX;
    }

    /** -1 (descending) to +1 (climbing); 0 without a barometer or while the air pressure holds steady. */
    static float climb() {
        return climb;
    }

    // ---- compass from the fused rotation vector ----

    /**
     * Compass heading in degrees clockwise from magnetic north, from the rotation vector sensor's
     * (x, y, z[, w]). Flat on a table it is where the top edge points. Held up in front of you it is where the
     * back of the phone faces, which is the way you are looking, so the compass stays useful when the phone
     * is upright (the raw top-edge method gives nonsense there). Returns -1 when the vector is unusable.
     */
    static float headingDegrees(float[] rv) {
        if (rv == null || rv.length < 3) {
            return -1f;
        }
        float x = rv[0], y = rv[1], z = rv[2];
        float w = rv.length > 3 ? rv[3] : (float) Math.sqrt(Math.max(0, 1 - x * x - y * y - z * z));
        // Rotation matrix entries we need (device axes to world East, North, Up).
        float r1 = 2 * (x * y - z * w), r2 = 2 * (x * z + y * w);
        float r4 = 1 - 2 * (x * x + z * z), r5 = 2 * (y * z - x * w);
        float topE = r1, topN = r4;      // device +y (top edge) in world
        float backE = -r2, backN = -r5;  // device -z (the back of the phone) in world
        float topLen = (float) Math.hypot(topE, topN), backLen = (float) Math.hypot(backE, backN);
        float e, n;
        if (topLen >= backLen) {
            e = topE;
            n = topN;
        } else {
            e = backE;
            n = backN;
        }
        if (e == 0f && n == 0f) {
            return -1f;
        }
        float deg = (float) Math.toDegrees(Math.atan2(e, n));
        return deg < 0 ? deg + 360f : deg;
    }
}
