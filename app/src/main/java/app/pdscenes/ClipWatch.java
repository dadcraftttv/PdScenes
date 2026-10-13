// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

/**
 * Turns the patch's once-a-second overload counts into the on-screen diagnostics. The patch counts ~12 ms stretches
 * with a sample at full scale in three places: the mic as it arrives (the phone's own mic overloading: harsh, and
 * Input gain can't help), after Input gain (over 1.0, which the compressor soaks up) and at the output limiter.
 * Pure logic (test D).
 */
final class ClipWatch {
    static final int IN = 0, GAIN = 1, OUT = 2;
    /** Seconds of history kept (the "last minute" counts). */
    static final int HISTORY_S = 60;
    /** A warning starts when this many stretches overloaded within WINDOW_S seconds... */
    static final int START_COUNT = 3;
    static final int WINDOW_S = 5;
    // ...and lasts until WINDOW_S seconds go by without any. One loud clap (1-2 stretches) doesn't start it.

    private final int[][] counts = new int[3][HISTORY_S];
    private int seconds;   // reports so far (the newest is at (seconds - 1) % HISTORY_S)
    private final boolean[] on = new boolean[3];

    /** One report from the patch. Returns a bit per place (1 << IN etc.) whose warning has just started. */
    synchronized int onSecond(int in, int gain, int out) {
        int slot = seconds % HISTORY_S;
        counts[IN][slot] = Math.max(0, in);
        counts[GAIN][slot] = Math.max(0, gain);
        counts[OUT][slot] = Math.max(0, out);
        seconds++;
        int started = 0;
        for (int k = 0; k < 3; k++) {
            int recent = sum(k, WINDOW_S);
            boolean was = on[k];
            on[k] = recent >= START_COUNT || (was && recent > 0);
            if (on[k] && !was) {
                started |= 1 << k;
            }
        }
        return started;
    }

    /** True while {@code place} keeps overloading (see START_COUNT). */
    synchronized boolean warning(int place) {
        return on[place];
    }

    /** Separate overloads in the last minute: runs of seconds with any, counted once each. */
    synchronized int episodes(int place) {
        int n = Math.min(seconds, HISTORY_S), result = 0;
        boolean before = false;
        for (int i = n; i >= 1; i--) {   // oldest first
            boolean any = counts[place][(seconds - i) % HISTORY_S] > 0;
            if (any && !before) {
                result++;
            }
            before = any;
        }
        return result;
    }

    /** True once at least one report has come (scenes don't send them). */
    synchronized boolean hasReports() {
        return seconds > 0;
    }

    synchronized void reset() {
        for (int[] c : counts) {
            java.util.Arrays.fill(c, 0);
        }
        java.util.Arrays.fill(on, false);
        seconds = 0;
    }

    private int sum(int place, int last) {
        int n = Math.min(seconds, last), s = 0;
        for (int i = 1; i <= n; i++) {
            s += counts[place][(seconds - i) % HISTORY_S];
        }
        return s;
    }
}
