// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

/**
 * Counts footsteps from the accelerometer: every foot-strike is a short bump in how hard the phone is being
 * pushed (the length of the acceleration vector, with gravity taken out, so the way the phone is held doesn't
 * matter). Fed from the sensor thread, read from the main thread.
 */
final class StepDetector {

    private static final float GRAVITY = 9.80665f;
    private static final float STEP_HIGH = 1.5f;       // m/s^2 above gravity that counts as a bump
    private static final float STEP_LOW = 0.6f;        // the bump must fall below this before the next one counts
    private static final double MIN_STEP_GAP_S = 0.28; // faster than ~3.5 steps a second is not walking
    private static final double WINDOW_S = 3.0;        // "walking" = steps within this long...
    private static final int STEPS_TO_WALK = 4;        // ...at least this many
    private static final double SMOOTH_S = 0.015;      // light smoothing against sensor noise (short, so the beat stays tight)
    private static final int STEPS_TO_PLAY = 3;        // the drums start on this step of a walk, not on a stray bump
    private static final int HISTORY = 16;

    private static final double[] stepTimes = new double[HISTORY];
    private static int stepCount;       // total steps ever, so stepTimes is a ring buffer
    private static double lastSample = -1;
    private static float smoothed;
    private static boolean above;
    // Step strength: each bump's peak, against the walk's running average. A step fires on the way up (so the beat
    // stays tight), before its peak is known, so a step carries the strength of the one before it.
    private static final float STRENGTH_SPREAD = 1.2f;   // 30% harder than usual -> strength about 0.86
    private static float peak;
    private static float lastPeak;
    private static float avgPeak;

    private StepDetector() { }

    /**
     * Told about every footstep of a walk (not the first two), with the time since the one before it in seconds and
     * how hard the steps are landing: 0.5 = as usual for this walk, towards 1 harder, towards 0 softer.
     */
    interface Listener {
        void onStep(double intervalS, float strength);
    }

    private static final double STALE_GAP_S = 1.5;       // after a pause the first step has no usable interval...
    private static final double FIRST_INTERVAL_S = 0.55; // ...so it gets a typical walking one
    private static volatile Listener listener;

    /** Set (or clear, with null) the listener. It is called on the sensor thread. */
    static void setListener(Listener l) {
        listener = l;
    }

    /** Accelerometer reading in m/s&sup2;, with the time it was taken in seconds (any steady clock). */
    static void onAcceleration(float x, float y, float z, double nowS) {
        double interval = detect(x, y, z, nowS);
        Listener l = listener;
        if (interval > 0 && l != null) {
            l.onStep(interval, strength());   // outside the lock: the listener talks to the audio engine
        }
    }

    /** Returns the interval to the previous step if this reading is a new step, else 0. */
    private static synchronized double detect(float x, float y, float z, double nowS) {
        float bump = (float) Math.sqrt(x * x + y * y + z * z) - GRAVITY;
        double dt = lastSample < 0 ? 0.02 : Math.max(0.001, Math.min(0.2, nowS - lastSample));
        lastSample = nowS;
        smoothed += (bump - smoothed) * (float) (1 - Math.exp(-dt / SMOOTH_S));
        if (!above && smoothed > STEP_HIGH) {
            above = true;
            if (stepCount == 0 || nowS - latestStep() >= MIN_STEP_GAP_S) {
                double gap = stepCount == 0 ? STALE_GAP_S + 1 : nowS - latestStep();
                stepTimes[stepCount % HISTORY] = nowS;
                stepCount++;
                if (stepsInWindow(nowS) < STEPS_TO_PLAY) {
                    return 0;   // fiddling with the phone makes bumps too: wait for a real walk
                }
                return gap > STALE_GAP_S ? FIRST_INTERVAL_S : gap;
            }
        } else if (above && smoothed < STEP_LOW) {
            above = false;
            lastPeak = peak;
            avgPeak = avgPeak == 0 ? peak : avgPeak * 0.85f + peak * 0.15f;
            peak = 0;
        }
        if (above) {
            peak = Math.max(peak, smoothed);
        }
        return 0;
    }

    /** How hard the last step landed compared with this walk's usual: 0.5 = usual, 0..1. */
    static synchronized float strength() {
        if (avgPeak <= 0 || lastPeak <= 0) {
            return 0.5f;
        }
        return Math.max(0f, Math.min(1f, 0.5f + STRENGTH_SPREAD * (lastPeak / avgPeak - 1f)));
    }

    private static double latestStep() {
        return stepTimes[(stepCount - 1) % HISTORY];
    }

    /** Steps taken in the last few seconds, as steps per second. */
    static synchronized float stepsPerSecond(double nowS) {
        return stepsInWindow(nowS) / (float) WINDOW_S;
    }

    /** True while the phone is clearly being walked (or run) with. */
    static synchronized boolean walking(double nowS) {
        return stepsInWindow(nowS) >= STEPS_TO_WALK;
    }

    private static int stepsInWindow(double nowS) {
        int n = 0;
        for (int i = 0; i < Math.min(stepCount, HISTORY); i++) {
            if (nowS - stepTimes[i] <= WINDOW_S) {
                n++;
            }
        }
        return n;
    }

    static synchronized void reset() {
        stepCount = 0;
        lastSample = -1;
        smoothed = 0;
        above = false;
        peak = lastPeak = avgPeak = 0;
    }
}
