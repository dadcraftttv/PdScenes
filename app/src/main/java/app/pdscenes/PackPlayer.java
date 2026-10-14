// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

/**
 * The stem pack playing now, and what it changes on the way to Pd while it plays (never the stored settings, which
 * come back when it stops): the tempo is locked to the pack's BPM (tempo_mode 2: walking changes the arrangement,
 * not the tempo), the music follows its key and scale, and while its drums play the app's own beat steps back to
 * BEAT_BACK of its level (Samuel: a pack's drums are usually the better groove). Test K.
 */
final class PackPlayer {

    static final float BEAT_BACK = 0.3f;
    private static final String[] OVERRIDES = {"tempo_mode", "tempo_bpm", "music_key", "music_scale", "beat_level"};

    private static volatile StemPack pack;
    private static volatile float drums;   // 0..1: how much the pack's drums play

    private PackPlayer() { }

    static void start(StemPack p) {
        pack = p;
        drums = 0;
    }

    static void stop() {
        pack = null;
        drums = 0;
    }

    static StemPack pack() {
        return pack;
    }

    /** The pack's drums are playing (1) or not (0); the beat level goes out again when this changes. */
    static void setDrums(float level) {
        drums = level;
    }

    static boolean overrides(String id) {
        for (String o : OVERRIDES) {
            if (o.equals(id)) {
                return true;
            }
        }
        return false;
    }

    static Iterable<String> overridden() {
        return java.util.Arrays.asList(OVERRIDES);
    }

    /** The value Pd gets for {@code id}, which would otherwise be {@code value}. */
    static float apply(String id, float value) {
        StemPack p = pack;
        if (p == null) {
            return value;
        }
        switch (id) {
            case "tempo_mode":
                return 2f;
            case "tempo_bpm":
                return p.bpm;
            case "music_key":
                return p.key;
            case "music_scale":
                return p.scale;
            case "beat_level":
                return value * (1 - (1 - BEAT_BACK) * drums);
            default:
                return value;
        }
    }
}
