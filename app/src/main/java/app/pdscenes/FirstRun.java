// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

/** When the first-run walkthrough opens by itself. Pure logic (test F). */
final class FirstRun {

    private FirstRun() { }

    /**
     * Only on a fresh install (never updated since, so testers who already had the app don't get it) and only once.
     */
    static boolean showWalkthrough(boolean seen, long firstInstallMs, long lastUpdateMs) {
        return !seen && firstInstallMs == lastUpdateMs;
    }
}
