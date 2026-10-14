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
    // Groove: how long the step rhythm has stayed steady. Half a minute of it and extra notes join the music.
    static final double GROOVE_AFTER_S = 30;
    private static final double STEADY_DEV = 0.15;   // within 15% of the usual interval counts as steady...
    private static final double BREAK_DEV = 0.30;    // ...more than 30% off (a stumble, a new pace) starts over
    private static double avgInterval;

    /** How brisk the walk is: 0 = a stroll (1 step a second or slower) .. 1 = brisk (2.6 steps a second), as the patch's pace. */
    static synchronized float pace() {
        if (avgInterval <= 0) {
            return 0;
        }
        return (float) Math.max(0, Math.min(1, (1 / Math.max(avgInterval, 0.25) - 1) / 1.6));
    }
    private static double steadyS;
    // Extra bumps (a scuff, a heel and toe, the phone knocking in a pocket) come much sooner than the next step would.
    // They are skipped, so the drums don't stumble. If skipped bumps fall about halfway between steps, the pace
    // really did double (a jog) and the next quick bump counts again.
    private static final double EXTRA_FRAC = 0.65;   // sooner than this part of the usual interval = an extra bump
    private static double skippedT = -1;
    private static double skippedFrac;               // where in its step interval the skipped bump fell, 0..1
    // How sure the rhythm is, 0.4..1: an uneven step lowers it, each even one raises it again. The drums play softer
    // while it's low, so an irregular walk sounds tentative rather than tripped up.
    private static final float SURE_MIN = 0.4f;
    private static float sure = 1f;
    private static boolean live;   // the bump being measured belongs to a step that was sent to the listener

    private StepDetector() { }

    /**
     * Told about every footstep of a walk (not the first two), with the time since the one before it in seconds and
     * how hard the steps are landing: 0.5 = as usual for this walk, towards 1 harder, towards 0 softer.
     */
    interface Listener {
        void onStep(double intervalS, float strength);
    }

    /** Told when a sent step's bump is over, with how hard that very step landed (same scale as above). */
    interface LandingListener {
        void onLanded(float strength);
    }

    private static final double STALE_GAP_S = 1.5;       // after a pause the first step has no usable interval...
    private static final double FIRST_INTERVAL_S = 0.55; // ...so it gets a typical walking one
    private static volatile Listener listener;
    private static volatile LandingListener landingListener;

    /** Set (or clear, with null) the listener. It is called on the sensor thread. */
    static void setListener(Listener l) {
        listener = l;
    }

    static void setLandingListener(LandingListener l) {
        landingListener = l;
    }

    /** Accelerometer reading in m/s&sup2;, with the time it was taken in seconds (any steady clock). */
    static void onAcceleration(float x, float y, float z, double nowS) {
        double interval = detect(x, y, z, nowS);
        Listener l = listener;
        if (interval > 0 && l != null) {
            l.onStep(interval, strength());   // outside the lock: the listener talks to the audio engine
        }
        float landed = landed();
        LandingListener ll = landingListener;
        if (landed >= 0 && ll != null) {
            ll.onLanded(landed);
        }
    }

    private static float landedStrength = -1;

    private static synchronized float landed() {
        float v = landedStrength;
        landedStrength = -1;
        return v;
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
                if (isExtraBump(gap, nowS)) {
                    return 0;
                }
                stepTimes[stepCount % HISTORY] = nowS;
                stepCount++;
                if (stepsInWindow(nowS) < STEPS_TO_PLAY) {
                    return 0;   // fiddling with the phone makes bumps too: wait for a real walk
                }
                live = true;
                if (gap > STALE_GAP_S) {
                    avgInterval = 0;
                    steadyS = 0;
                    sure = 1f;
                    return FIRST_INTERVAL_S;
                }
                trackSteadiness(gap);
                return gap;
            }
        } else if (above && smoothed < STEP_LOW) {
            above = false;
            if (live && avgPeak > 0) {
                landedStrength = toStrength(peak / avgPeak);
            }
            live = false;
            lastPeak = peak;
            avgPeak = avgPeak == 0 ? peak : avgPeak * 0.85f + peak * 0.15f;
            peak = 0;
        }
        if (above) {
            peak = Math.max(peak, smoothed);
        }
        return 0;
    }

    /**
     * True if a bump {@code gap} seconds after the last step is an extra one to skip. A run of skipped bumps
     * sitting about halfway between steps means the pace doubled: then this one counts, and the usual interval
     * starts over from it.
     */
    private static boolean isExtraBump(double gap, double nowS) {
        if (avgInterval <= 0 || gap >= EXTRA_FRAC * avgInterval || nowS - latestStep() > STALE_GAP_S) {
            return false;
        }
        boolean doubled = skippedT >= 0 && nowS - skippedT < 3 * avgInterval
                && Math.abs(skippedFrac - 0.5) < 0.07 && Math.abs(gap - (skippedT - previousStep())) < 0.25 * gap;
        if (doubled) {
            avgInterval = gap;
            steadyS = 0;
            skippedT = -1;
            return false;
        }
        skippedT = nowS;
        skippedFrac = 0;   // known once the next step lands
        return true;
    }

    private static void trackSteadiness(double gap) {
        if (skippedT >= 0 && skippedT > previousStep() && skippedFrac == 0) {
            skippedFrac = (skippedT - previousStep()) / gap;   // the bump skipped inside this step's interval
        }
        if (avgInterval <= 0) {
            avgInterval = gap;
            return;
        }
        double dev = Math.abs(gap - avgInterval) / avgInterval;
        if (dev < STEADY_DEV) {
            steadyS += gap;
            sure = Math.min(1f, sure + 0.15f);
        } else if (dev > BREAK_DEV) {
            steadyS = 0;
            sure = Math.max(SURE_MIN, sure - 0.3f);
        }
        avgInterval = avgInterval * 0.8 + gap * 0.2;
    }

    /** True after {@link #GROOVE_AFTER_S} of steady steps in this walk. */
    static synchronized boolean grooving() {
        return steadyS >= GROOVE_AFTER_S;
    }

    /** How hard the last step landed compared with this walk's usual: 0.5 = usual, 0..1. */
    static synchronized float strength() {
        if (avgPeak <= 0 || lastPeak <= 0) {
            return 0.5f;
        }
        return toStrength(lastPeak / avgPeak);
    }

    private static float toStrength(float ratio) {
        return Math.max(0f, Math.min(1f, 0.5f + STRENGTH_SPREAD * (ratio - 1f)));
    }

    /** How sure the step rhythm is: 1 = even steps, down to 0.4 while they come unevenly. */
    static synchronized float sureness() {
        return sure;
    }

    private static double latestStep() {
        return stepTimes[(stepCount - 1) % HISTORY];
    }

    /** The step before the latest one, or -1. */
    private static double previousStep() {
        return stepCount < 2 ? -1 : stepTimes[(stepCount - 2) % HISTORY];
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
        avgInterval = 0;
        steadyS = 0;
        skippedT = -1;
        sure = 1f;
        live = false;
        landedStrength = -1;
    }
}
