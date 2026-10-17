package app.pdscenes;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/** Kits: the kit files parse, and choosing a kit sends each part its defaults, then its settings, then its engine. */
public class Q {
    static int fails = 0;

    static void check(boolean ok, String what) {
        System.out.println((ok ? "ok:   " : "FAIL: ") + what);
        if (!ok) fails++;
    }

    public static void main(String[] a) throws Exception {
        Path kits = Path.of(System.getProperty("user.dir"), "app/src/main/assets/kits");
        Kits.source = name -> {
            try {
                return Files.readString(kits.resolve(name + ".txt"));
            } catch (Exception e) {
                return null;
            }
        };
        check(Kits.BUILT_IN.length == Params.byId(Kits.ID).choices.length,
                "every built-in kit has an entry in the Kit menu (" + Kits.BUILT_IN.length + ")");
        for (String name : Kits.BUILT_IN) {
            check(Kits.source.read(name) != null && !Kits.parse(Kits.source.read(name)).title.isEmpty(),
                    "kit file " + name + ".txt is there and has a title");
        }
        Kits.Kit ac = Kits.parse(Kits.source.read("acoustic"));
        check(ac.title.equals("Acoustic") && ac.parts.size() == 3, "Acoustic gives all three parts a sound");
        List<String> sent = new ArrayList<>();
        Kits.send(0, (r, s, v) -> sent.add(r + " " + s + " " + v));
        check(sent.contains("kit_mel engine 0.0") && sent.contains("kit_bass engine 0.0") && sent.contains("kit_pad engine 0.0")
                && sent.stream().noneMatch(m -> m.contains("engine") && !m.endsWith(" 0.0")),
                "Classic: every part's engine 0 (its own sound) (" + sent.size() + " messages)");
        sent.clear();
        Kits.send(1, (r, s, v) -> sent.add(r + " " + s + " " + v));
        int lastMel = sent.lastIndexOf("kit_mel engine 1.0"), brightMel = sent.lastIndexOf("kit_mel bright 0.45");
        check(lastMel > brightMel && brightMel > sent.indexOf("kit_mel engine 0.0") && sent.contains("kit_bass engine 2.0")
                && sent.contains("kit_pad attack 1200.0"),
                "Acoustic: defaults first, then its settings, the engine last (melody pluck, bass bowed, pad attack 1200)");
        // mix and match: the Acoustic kit with the Classic pad; then only the pad changes back
        for (int k = 0; k < Kits.PARTS.length; k++) {
            check(Params.byId("kitp_" + Kits.PARTS[k]) != null
                    && Params.byId("kitp_" + Kits.PARTS[k]).choices.length == Kits.BUILT_IN.length + 1,
                    "the " + Kits.PARTS[k] + " has a 'from' menu: the kit + every built-in kit");
        }
        sent.clear();
        Kits.send(1, new int[]{0, 0, 1}, true, (r, s, v) -> sent.add(r + " " + s + " " + v));
        check(sent.contains("kit_mel engine 1.0") && sent.contains("kit_bass engine 2.0")
                && sent.stream().noneMatch(m -> m.startsWith("kit_pad engine") && !m.endsWith(" 0.0")),
                "Acoustic with the pad from Classic: melody pluck, bass bowed, pad its own sound");
        sent.clear();
        Kits.send(1, new int[]{0, 0, 0}, false, (r, s, v) -> sent.add(r + " " + s + " " + v));
        check(!sent.isEmpty() && sent.stream().allMatch(m -> m.startsWith("kit_pad")) && sent.contains("kit_pad engine 2.0"),
                "switching only the pad back to the kit sends only the pad (melody and bass keep their notes)");
        check(Params.byId(Kits.ID).inPreset && !Params.byId(Kits.ID).resetWhenAbsent && !Params.byId("kitp_pad").resetWhenAbsent,
                "kit settings are in presets, and a preset or Realm that doesn't mention them leaves them alone");
        Kits.Kit odd = Kits.parse("title: X\nmel: engine pluck, wobble 3, bright high, bright 0.2\nnoise: engine bowed\n");
        check(odd.parts.size() == 1 && odd.parts.get("mel").size() == 3,
                "unknown parts and unreadable values are skipped (" + odd.parts.get("mel").size() + " settings kept)");
        System.out.println(fails == 0 ? "ALL PASSED" : fails + " FAILED");
    }
}
