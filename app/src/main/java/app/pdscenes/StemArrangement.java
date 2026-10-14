// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

/**
 * Which of a pack's stems play now (Samuel, Oct 14): pad always; bass while walking or in a livelier room; drums
 * while walking; lead in a lively room or on a brisk walk; texture at night, in a pocket or in the Ghost realm.
 * A role, once on or off, holds at least HOLD_S (no flapping); the patch applies a change at the next downbeat,
 * faded over one bar. With sections (pad_A, pad_B ...) only the current one plays, and the pack moves to the next
 * every SECTION_LOOPS loops of its longest stem. Pure logic (test K).
 */
final class StemArrangement {

    static final double HOLD_S = 8;
    static final int SECTION_LOOPS = 4;
    static final float BRISK_PACE = 0.6f;

    /** What the phone senses now. */
    static final class Situation {
        boolean walking, lively, loud, night, pocket;
        float pace;          // 0 = strolling .. 1 = brisk
        String realm;        // the Realm playing, or null
    }

    private final StemPack pack;
    private final boolean[] roleOn = new boolean[StemPack.ROLES.length + 1];   // (+1: any other role)
    private final double[] roleSince = new double[roleOn.length];
    private double time;
    private double sectionS;
    private int section;
    private final double sectionLength;

    StemArrangement(StemPack pack) {
        this.pack = pack;
        double longest = 0;
        for (StemPack.Stem s : pack.stems) {
            longest = Math.max(longest, pack.loopSeconds(s));
        }
        sectionLength = SECTION_LOOPS * longest;
        for (int i = 0; i < roleSince.length; i++) {
            roleSince[i] = -1e9;
        }
    }

    /** Moves on by {@code dt} seconds and returns the level (0 or 1) for each stem, in the pack's order. */
    float[] tick(double dt, Situation s) {
        time += dt;
        if (pack.sections.size() > 1) {
            sectionS += dt;
            if (sectionS >= sectionLength) {
                sectionS = 0;
                section = (section + 1) % pack.sections.size();
            }
        }
        boolean[] want = {
                true,                                                       // pad
                s.walking || s.lively || s.loud,                            // bass
                s.walking,                                                  // drums
                s.lively || (s.walking && s.pace >= BRISK_PACE),            // lead
                s.night || s.pocket || "ghost".equals(s.realm),             // texture
                s.night || s.pocket || "ghost".equals(s.realm),             // other roles: like texture
        };
        for (int r = 0; r < roleOn.length; r++) {
            if (want[r] != roleOn[r] && time - roleSince[r] >= HOLD_S) {
                roleOn[r] = want[r];
                roleSince[r] = time;
            }
        }
        String current = pack.sections.get(section);
        float[] levels = new float[pack.stems.size()];
        for (int i = 0; i < levels.length; i++) {
            StemPack.Stem st = pack.stems.get(i);
            boolean inSection = st.section.equals(current)
                    || (!hasSection(st.role, current) && st.section.equals(firstSection(st.role)));
            levels[i] = inSection && roleOn[roleIndex(st.role)] ? 1f : 0f;
        }
        return levels;
    }

    /** True if the role has a stem in this section (else its first section stands in). */
    private boolean hasSection(String role, String section) {
        for (StemPack.Stem st : pack.stems) {
            if (st.role.equals(role) && st.section.equals(section)) {
                return true;
            }
        }
        return false;
    }

    /** The earliest section a role has (it stands in where the role has none). */
    private String firstSection(String role) {
        String first = null;
        for (StemPack.Stem st : pack.stems) {
            if (st.role.equals(role) && (first == null || st.section.compareTo(first) < 0)) {
                first = st.section;
            }
        }
        return first;
    }

    static int roleIndex(String role) {
        for (int r = 0; r < StemPack.ROLES.length; r++) {
            if (StemPack.ROLES[r].equals(role)) {
                return r;
            }
        }
        return StemPack.ROLES.length;
    }

    int section() {
        return section;
    }
}
