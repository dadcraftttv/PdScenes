// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

/**
 * A stem pack (Samuel's own tracks, Oct 14): a folder of loops plus pack.txt, for example
 * <pre>
 * title: Neon Drive
 * bpm: 108
 * key: A minor
 * bars: 8
 *
 * drums.wav      role: drums
 * pad_A.wav      role: pad
 * pad_B.wav      role: pad
 * lead.wav       role: lead   bars: 16
 * </pre>
 * Roles: pad, bass, drums, lead, texture (anything else plays like texture). A file ending in _A, _B ... is that
 * section of the song (or "section: B"); the app moves between sections every few loops. Pure logic (test K).
 */
final class StemPack {

    static final String FILE = "pack.txt";
    static final int MAX_STEMS = 8;   // the patch's STEM_SLOTS
    static final String[] ROLES = {"pad", "bass", "drums", "lead", "texture"};
    /** The patch's scales, by music_scale. */
    static final String[] SCALES = {"major", "minor", "major pentatonic", "minor pentatonic", "dorian", "mixolydian",
            "lydian", "whole tone"};

    static final class Stem {
        final String file;
        final String role;
        final String section;
        final int bars;

        Stem(String file, String role, String section, int bars) {
            this.file = file;
            this.role = role;
            this.section = section;
            this.bars = bars;
        }
    }

    final String title;
    final float bpm;
    final int key;      // 0 = C .. 11 = B
    final int scale;    // index into SCALES
    final int bars;     // the pack's default loop length
    final List<Stem> stems;
    /** The sections in the order they come (A, B, ...). */
    final List<String> sections;

    private StemPack(String title, float bpm, int key, int scale, int bars, List<Stem> stems) {
        this.title = title;
        this.bpm = bpm;
        this.key = key;
        this.scale = scale;
        this.bars = bars;
        this.stems = Collections.unmodifiableList(stems);
        List<String> s = new ArrayList<>();
        for (Stem st : stems) {
            if (!s.contains(st.section)) {
                s.add(st.section);
            }
        }
        Collections.sort(s);
        this.sections = Collections.unmodifiableList(s);
    }

    /**
     * A pack is held in memory while it plays (about 0.4 MB per second of stereo at 48 kHz), so its loops together may
     * hold at most MAX_STEREO_S seconds of stereo (a mono loop counts half): about 92 MB. Plenty for loops, but a pack
     * of eight 32-bar stems at a slow tempo would need several times that and could crash a smaller phone.
     */
    static final double MAX_STEREO_S = 240;

    /** Null if loops of these lengths (s) and channel counts fit in memory, else why not, in plain words. */
    static String tooLong(double[] seconds, int[] channels) {
        double total = 0;
        for (int i = 0; i < seconds.length; i++) {
            total += seconds[i] * Math.min(2, Math.max(1, channels[i])) / 2.0;
        }
        if (total <= MAX_STEREO_S) {
            return null;
        }
        return String.format(Locale.US, "This pack is too long to hold in memory while it plays: its loops add up to "
                + "%d:%02d of stereo audio, and the limit is %d:%02d. Shorten the loops (8 bars is usually plenty) or use "
                + "fewer of them.", (int) total / 60, (int) total % 60, (int) MAX_STEREO_S / 60, (int) MAX_STEREO_S % 60);
    }

    /** A loop's length in seconds. */
    double loopSeconds(Stem s) {
        return s.bars * 4 * 60.0 / bpm;
    }

    /** Reads pack.txt; {@code fallbackTitle} names it when it has no title. Throws with a plain-words reason. */
    static StemPack parse(String text, String fallbackTitle) throws IllegalArgumentException {
        String title = fallbackTitle;
        float bpm = -1;
        int key = 0, scale = 0, bars = 8;
        List<String[]> stemLines = new ArrayList<>();   // {file, rest}
        int lineNo = 0;
        for (String raw : text.split("\r?\n")) {
            lineNo++;
            String line = raw.trim();
            if (line.isEmpty() || line.startsWith("#")) {
                continue;
            }
            int role = line.toLowerCase(Locale.US).indexOf("role:");
            if (role > 0) {
                stemLines.add(new String[]{line.substring(0, role).trim(), line.substring(role), String.valueOf(lineNo)});
                continue;
            }
            int colon = line.indexOf(':');
            if (colon <= 0) {
                throw new IllegalArgumentException("Line " + lineNo + " of " + FILE + " isn't \"name: value\" or a stem with a role: " + line);
            }
            String name = line.substring(0, colon).trim().toLowerCase(Locale.US);
            String value = line.substring(colon + 1).trim();
            switch (name) {
                case "title":
                    title = value;
                    break;
                case "bpm":
                case "tempo":
                    bpm = number(value, "bpm");
                    if (bpm < 30 || bpm > 300) {
                        throw new IllegalArgumentException("The bpm should be between 30 and 300, not " + value);
                    }
                    break;
                case "key":
                    int[] ks = key(value);
                    key = ks[0];
                    scale = ks[1];
                    break;
                case "bars":
                    bars = barsOf(value);
                    break;
                default:
                    break;   // unknown settings are ignored, so later versions can add some
            }
        }
        if (bpm < 0) {
            throw new IllegalArgumentException(FILE + " needs a bpm line, like \"bpm: 108\"");
        }
        List<Stem> stems = new ArrayList<>();
        for (String[] s : stemLines) {
            String file = s[0];
            String role = null, section = null;
            int stemBars = bars;
            String[] words = s[1].split("\\s+");
            for (int i = 0; i < words.length; i++) {
                String w = words[i].toLowerCase(Locale.US);
                String next = i + 1 < words.length ? words[i + 1] : "";
                if (w.equals("role:")) {
                    role = next.toLowerCase(Locale.US);
                    i++;
                } else if (w.equals("bars:")) {
                    stemBars = barsOf(next);
                    i++;
                } else if (w.equals("section:")) {
                    section = next.toUpperCase(Locale.US);
                    i++;
                }
            }
            if (role == null || role.isEmpty()) {
                throw new IllegalArgumentException("Line " + s[2] + " of " + FILE + ": no role for " + file);
            }
            stems.add(new Stem(file, role, section != null ? section : sectionOf(file), stemBars));
        }
        if (stems.isEmpty()) {
            throw new IllegalArgumentException(FILE + " lists no stems (lines like \"pad.wav  role: pad\")");
        }
        if (stems.size() > MAX_STEMS) {
            throw new IllegalArgumentException("A pack can have at most " + MAX_STEMS + " stems, this one has " + stems.size());
        }
        return new StemPack(title, bpm, key, scale, bars, stems);
    }

    private static float number(String v, String what) {
        try {
            return Float.parseFloat(v.trim());
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("The " + what + " should be a number, not \"" + v + "\"");
        }
    }

    private static int barsOf(String v) {
        float b = number(v, "bars");
        if (b < 1 || b > 64 || b != Math.rint(b)) {
            throw new IllegalArgumentException("Bars should be a whole number from 1 to 64, not " + v);
        }
        return (int) b;
    }

    /** "pad_B.wav" is section B; anything else section A. */
    static String sectionOf(String file) {
        String base = file.contains(".") ? file.substring(0, file.lastIndexOf('.')) : file;
        int u = base.lastIndexOf('_');
        if (u >= 0 && u == base.length() - 2 && Character.isLetter(base.charAt(u + 1))) {
            return String.valueOf(Character.toUpperCase(base.charAt(u + 1)));
        }
        return "A";
    }

    /** "A minor", "F# major", "Bb dorian", "C" -> {key 0-11, scale index}. */
    static int[] key(String v) {
        String s = v.trim().toLowerCase(Locale.US);
        if (s.isEmpty()) {
            throw new IllegalArgumentException("The key is empty");
        }
        int note = "c d ef g a b".indexOf(s.charAt(0));
        if (note < 0 || s.charAt(0) == ' ') {
            throw new IllegalArgumentException("The key should start with a note from A to G, not \"" + v + "\"");
        }
        int[] semis = {0, -1, 2, -1, 4, 5, -1, 7, -1, 9, -1, 11};
        int k = semis[note];
        int i = 1;
        if (s.length() > 1 && (s.charAt(1) == '#' || s.charAt(1) == '♯')) {
            k++;
            i++;
        } else if (s.length() > 1 && (s.charAt(1) == 'b' || s.charAt(1) == '♭')) {
            k--;
            i++;
        }
        k = ((k % 12) + 12) % 12;
        String rest = s.substring(i).trim().replace("-", " ");
        int scale = 0;
        if (!rest.isEmpty()) {
            scale = -1;
            String[][] names = {{"major", "ionian"}, {"minor", "aeolian", "m"},
                    {"major pentatonic", "pentatonic major", "pentatonic"}, {"minor pentatonic", "pentatonic minor"},
                    {"dorian"}, {"mixolydian"}, {"lydian"}, {"whole tone", "wholetone"}};
            for (int n = 0; n < names.length && scale < 0; n++) {
                for (String name : names[n]) {
                    if (rest.equals(name)) {
                        scale = n;
                        break;
                    }
                }
            }
            if (scale < 0) {
                throw new IllegalArgumentException("Unknown scale \"" + rest + "\". Use major, minor, dorian, mixolydian, "
                        + "lydian, major pentatonic, minor pentatonic or whole tone");
            }
        }
        return new int[]{k, scale};
    }

    /** How the key reads on screen: "A minor". */
    String keyName() {
        String[] names = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"};
        return names[key] + " " + SCALES[scale];
    }
}
