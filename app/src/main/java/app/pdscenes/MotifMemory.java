// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/**
 * Motif memory: remembers the last short phrase of chimes (notes close together) and, once the room has gone quiet
 * for a while and you are standing still, now and then plays it back changed a little (moved up or down the scale,
 * one note bent, a bit faster or slower), so the music seems to have themes. Pure logic: told about each chime the
 * patch played and polled from the service tick; times in seconds on any steady clock. Thread-safe.
 */
final class MotifMemory {

    static final double PHRASE_GAP_S = 2.5;   // a longer gap between chimes ends a phrase
    static final int MIN_NOTES = 3;           // shorter phrases are not worth remembering
    static final int MAX_NOTES = 6;
    static final double QUIET_S = 8.0;        // no chimes for this long before a phrase may come back
    static final double COOLDOWN_S = 30.0;    // and never more often than this
    static final double CHANCE = 0.6;         // each quiet spell, the chance it does
    static final float VELOCITY = 0.45f;

    /** One note of a replay: when (seconds after the replay starts) and which scale step. */
    static final class Note {
        final double at;
        final int degree;

        Note(double at, int degree) {
            this.at = at;
            this.degree = degree;
        }
    }

    private final List<Integer> degrees = new ArrayList<>();
    private final List<Double> gaps = new ArrayList<>();   // seconds before each note (0 for the first)
    private int[] savedDegrees;
    private double[] savedGaps;
    private double lastNote = -1e9;
    private double lastReplay = -1e9;
    private boolean decided;   // this quiet spell already had its chance
    private final Random random;

    MotifMemory(Random random) {
        this.random = random;
    }

    synchronized void reset() {
        degrees.clear();
        gaps.clear();
        savedDegrees = null;
        savedGaps = null;
        lastNote = -1e9;
        lastReplay = -1e9;
        decided = false;
    }

    /** A chime the patch played (not the walking arpeggio, not a replay). */
    synchronized void onNote(int degree, double now) {
        double gap = now - lastNote;
        if (gap > PHRASE_GAP_S) {
            finishPhrase();
            gap = 0;
        }
        if (degrees.size() < MAX_NOTES) {
            degrees.add(degree);
            gaps.add(gap);
        }
        lastNote = now;
        decided = false;
    }

    private void finishPhrase() {
        if (degrees.size() >= MIN_NOTES) {
            savedDegrees = new int[degrees.size()];
            savedGaps = new double[degrees.size()];
            for (int i = 0; i < degrees.size(); i++) {
                savedDegrees[i] = degrees.get(i);
                savedGaps[i] = gaps.get(i);
            }
        }
        degrees.clear();
        gaps.clear();
    }

    /** Called often. Returns a phrase to play now (notes timed from now), or null. */
    synchronized List<Note> poll(double now, boolean walking) {
        if (now - lastNote > PHRASE_GAP_S && !degrees.isEmpty()) {
            finishPhrase();
        }
        if (savedDegrees == null || walking || decided || now - lastNote < QUIET_S || now - lastReplay < COOLDOWN_S) {
            return null;
        }
        decided = true;
        if (random.nextDouble() >= CHANCE) {
            return null;
        }
        lastReplay = now;
        return vary();
    }

    /** The saved phrase moved 1-2 steps up or down (now and then not at all), one note bent, the rhythm stretched. */
    private List<Note> vary() {
        int[] moves = {-2, -1, 0, 1, 2, 1, -1};
        int shift = moves[random.nextInt(moves.length)];
        int bent = random.nextDouble() < 0.4 ? 1 + random.nextInt(savedDegrees.length - 1) : -1;
        double rate = 0.8 + 0.45 * random.nextDouble();
        List<Note> out = new ArrayList<>();
        double at = 0;
        for (int i = 0; i < savedDegrees.length; i++) {
            at += Math.min(Math.max(savedGaps[i] * rate, i == 0 ? 0 : 0.12), 1.5);
            int d = savedDegrees[i] + shift + (i == bent ? (random.nextBoolean() ? 1 : -1) : 0);
            out.add(new Note(at, d));
        }
        return out;
    }
}
