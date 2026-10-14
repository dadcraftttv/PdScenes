// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/**
 * Call and response (roadmap 12, Samuel Oct 14; "Call and response" in Music, 0 = off): sing, hum or whistle a short
 * phrase and, a moment after it ends, the app answers with it: the same rhythm and contour as chimes, moved a third
 * up (a third down for a high voice), in key. The patch's pitch tracker (the one Harmony uses) reports each steady
 * note as a scale step (heard_deg, 0 = the key note) and its end (heard_off); the answer is played like a remembered
 * phrase (motif), so it follows the Melody sounds, the Chimes level and, while the Rhythm runs, the beat grid.
 * Pure logic (test L).
 */
final class CallResponse {

    static final double PHRASE_GAP_S = 1.5;   // a longer pause between notes starts a new phrase
    static final double ANSWER_AFTER_S = 1.6; // the phrase has ended when nothing is sung for this long (longer than a
                                              // pause inside a phrase; Samuel: at 0.7 "answering too soon")
    static final int MAX_NOTES = 6;           // longer phrases are answered with their last six notes
    static final double MAX_SPAN_S = 4.0;     // and an answer never lasts longer than this
    static final double COOLDOWN_S = 3.0;     // at most one answer this often
    static final int HIGH_STEP = 14;          // a phrase reaching two octaves above the key note is answered a third below
    static final float VELOCITY = 0.55f;      // at Call and response 1

    private final List<Integer> degrees = new ArrayList<>();
    private final List<Double> starts = new ArrayList<>();
    private boolean noteOn;
    private double lastEnd = -1e9, lastStart = -1e9, lastAnswer = -1e9;
    private final Random random;

    CallResponse(Random random) {
        this.random = random;
    }

    synchronized void reset() {
        degrees.clear();
        starts.clear();
        noteOn = false;
        lastEnd = lastStart = lastAnswer = -1e9;
    }

    /** A steady note was heard: {@code degree} scale steps above the key note. */
    synchronized void onNote(int degree, double t) {
        double since = noteOn ? t - lastStart : t - lastEnd;
        if (!noteOn && since > PHRASE_GAP_S) {
            degrees.clear();
            starts.clear();
        }
        degrees.add(degree);
        starts.add(t);
        if (degrees.size() > MAX_NOTES) {
            degrees.remove(0);
            starts.remove(0);
        }
        noteOn = true;
        lastStart = t;
    }

    /** The note being heard ended. */
    synchronized void onNoteOff(double t) {
        if (noteOn) {
            noteOn = false;
            lastEnd = t;
        }
    }

    /**
     * The answer, once, when a phrase has just ended: notes with times (seconds after the answer starts) and scale
     * steps; null otherwise. {@code level} is the Call and response setting (0 = never), {@code scaleSize} the
     * notes per octave of the scale playing.
     */
    synchronized List<MotifMemory.Note> poll(double t, float level, int scaleSize) {
        if (level <= 0 || noteOn || degrees.isEmpty() || t - lastEnd < ANSWER_AFTER_S || t - lastAnswer < COOLDOWN_S) {
            return null;
        }
        int high = 0;
        for (int d : degrees) {
            high = Math.max(high, d);
        }
        int shift = high >= HIGH_STEP ? -2 : 2;
        List<MotifMemory.Note> out = new ArrayList<>();
        double t0 = starts.get(0);
        for (int i = 0; i < degrees.size(); i++) {
            double at = starts.get(i) - t0;
            if (at > MAX_SPAN_S) {
                break;
            }
            out.add(new MotifMemory.Note(at, degrees.get(i) + shift));
        }
        // a little life: now and then the last note lands on the key note's nearest octave instead (a resolution)
        if (out.size() >= 3 && random.nextFloat() < 0.4f) {
            MotifMemory.Note last = out.remove(out.size() - 1);
            int n = Math.max(1, scaleSize);
            out.add(new MotifMemory.Note(last.at, Math.round(last.degree / (float) n) * n));
        }
        degrees.clear();
        starts.clear();
        lastAnswer = t;
        return out;
    }

    static float velocity(float level) {
        return VELOCITY * Math.max(0, Math.min(1, level));
    }
}
