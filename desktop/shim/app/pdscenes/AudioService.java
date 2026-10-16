// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

/** The desktop's stand-in for the phone's audio service: the shared logic only asks whether the engine runs. */
final class AudioService {

    static volatile boolean running;

    private AudioService() { }

    static boolean isRunning() {
        return running;
    }
}
