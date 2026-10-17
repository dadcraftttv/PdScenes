// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Kits: what each part of the music sounds like (Oct 17). The music engine decides the notes; a kit gives each part
 * (melody, bass, pad) an engine of the patch's kit voice (dcs_voice~) and its settings, or leaves it Classic.
 *
 * A kit is a text file (assets/kits/<name>.txt; user kits later), one line per part:
 * <pre>
 * title: Acoustic
 * mel: engine pluck, bright 0.45, level 1.2
 * bass: engine bowed, bright 0.25, attack 400, release 900
 * </pre>
 * A part not listed stays Classic. On each kit choice (and when the patch opens) every part first gets the voice's
 * defaults, then the kit's settings, as messages to kit_<part>.
 */
final class Kits {
    static final String ID = "kit";
    static final String[] PARTS = {"mel", "bass", "pad"};
    /** The Kit menu, in order (Params' choices for "kit" follow it). */
    static final String[] BUILT_IN = {"classic", "acoustic"};
    static final String[] ENGINES = {"classic", "pluck", "bowed", "modal"};
    static final String[] MODAL = {"", "bell", "marimba", "bowl"};
    /** The voice's own defaults, sent before a kit's settings (so nothing lingers from the kit before). */
    static final String[][] DEFAULTS = {{"engine", "0"}, {"bright", "0.4"}, {"level", "1"}, {"attack", "300"},
            {"release", "800"}, {"decay", "3000"}, {"modal", "1"}};

    /** Reads a built-in kit's text (assets on the phone, files on the desktop); null if missing. */
    interface Source {
        String read(String name);
    }

    /** Where the messages go (the app: PdBase.sendMessage). */
    interface Out {
        void send(String receiver, String selector, float value);
    }

    static final class Kit {
        String title = "";
        /** part -> (setting, value), in file order */
        final Map<String, List<Object[]>> parts = new LinkedHashMap<>();
    }

    static volatile Source source;

    private Kits() {
    }

    /** A kit file's text, parsed. Unknown parts and settings are skipped (a newer kit on an older app still loads). */
    static Kit parse(String text) {
        Kit kit = new Kit();
        for (String raw : text.split("\n")) {
            String line = raw.trim();
            int colon = line.indexOf(':');
            if (line.isEmpty() || line.startsWith("#") || colon < 0) {
                continue;
            }
            String key = line.substring(0, colon).trim().toLowerCase(Locale.ROOT), rest = line.substring(colon + 1).trim();
            if (key.equals("title")) {
                kit.title = rest;
                continue;
            }
            if (!isPart(key)) {
                continue;
            }
            List<Object[]> settings = new ArrayList<>();
            for (String item : rest.split(",")) {
                String[] w = item.trim().split("\\s+");
                if (w.length < 2) {
                    continue;
                }
                String name = w[0].toLowerCase(Locale.ROOT);
                float value;
                if (name.equals("engine")) {
                    value = indexOf(ENGINES, w[1]);
                } else if (name.equals("modal")) {
                    value = indexOf(MODAL, w[1]);
                } else {
                    try {
                        value = Float.parseFloat(w[1]);
                    } catch (NumberFormatException e) {
                        continue;
                    }
                }
                if (value >= 0) {
                    settings.add(new Object[]{name, value});
                }
            }
            kit.parts.put(key, settings);
        }
        return kit;
    }

    /** Sends kit number `index` (the Kit menu's) to the patch: every part reset, then the kit's settings. */
    static void send(int index, Out out) {
        Kit kit = null;
        Source src = source;
        if (src != null && index >= 0 && index < BUILT_IN.length) {
            String text = src.read(BUILT_IN[index]);
            if (text != null) {
                kit = parse(text);
            }
        }
        for (String part : PARTS) {
            String recv = "kit_" + part;
            for (String[] d : DEFAULTS) {
                out.send(recv, d[0], Float.parseFloat(d[1]));
            }
            List<Object[]> settings = kit == null ? null : kit.parts.get(part);
            if (settings == null) {
                continue;
            }
            // settings first, the engine last: a note arriving in between hears the new sound whole
            Object[] engine = null;
            for (Object[] st : settings) {
                if (st[0].equals("engine")) {
                    engine = st;
                } else {
                    out.send(recv, (String) st[0], (Float) st[1]);
                }
            }
            if (engine != null) {
                out.send(recv, "engine", (Float) engine[1]);
            }
        }
    }

    private static boolean isPart(String key) {
        for (String p : PARTS) {
            if (p.equals(key)) {
                return true;
            }
        }
        return false;
    }

    private static int indexOf(String[] names, String word) {
        for (int i = 0; i < names.length; i++) {
            if (names[i].equalsIgnoreCase(word)) {
                return i;
            }
        }
        return -1;
    }
}
