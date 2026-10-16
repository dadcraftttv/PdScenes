// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import android.content.Context;

import java.io.File;
import java.nio.file.Files;
import java.util.Map;

/**
 * Desktop logic tests (no sound, no window): presets swap with the phone's format both ways, sensor movers load and
 * stay put, unknown settings are ignored, settings survive a restart. Run by desktop/test.sh.
 */
public final class DesktopTest {

    private static int failed;

    private static void check(boolean ok, String what) {
        System.out.println((ok ? "ok:   " : "FAIL: ") + what);
        if (!ok) {
            failed++;
        }
    }

    public static void main(String[] args) throws Exception {
        File dir = Files.createTempDirectory("pdscenes-test").toFile();
        Context ctx = new Context(new File(dir, "data"), new File(dir, "config"));
        ParamStore.loadOnce(ctx);

        // a preset as the phone writes it, plus a setting from a newer version and a sensor mover (In pocket = higher)
        String phone = "{\"format\": \"pdscenes-preset\", \"version\": 1, \"name\": \"From the phone\", \"values\": {"
                + "\"wet\": 0.45, \"echo_time\": 420, \"beat_break\": 0.6, \"feedback\": 7,"
                + "\"wet_mv\": 14, \"wet_mvdepth\": 0.5, \"echo_movers\": 1, \"a_future_setting\": 3, \"gain\": 9}}";
        PresetManager.Preset p = PresetManager.parse(phone);
        check(p.name.equals("From the phone") && p.values.get("wet") == 0.45f && p.values.get("beat_break") == 0.6f,
                "a phone preset loads (name, values)");
        check(!p.values.containsKey("a_future_setting"), "a setting this version doesn't know is ignored");
        check(p.values.get("feedback") <= Params.byId("feedback").max, "values are clamped to the slider's range ("
                + p.values.get("feedback") + ")");
        check(!p.values.containsKey("gain"), "settings kept out of presets (input gain) aren't taken from a file");
        check(Math.round(p.values.get("wet_mv")) == 14, "a sensor mover (In pocket) is kept");

        String saved = PresetManager.save(ctx, PresetManager.uniqueName(ctx, p.name), p.values);
        check(PresetManager.userNames(ctx).contains(saved) && new File(dir, "data/presets/" + saved + ".json").isFile(),
                "imported into the presets folder as \"" + saved + "\"");
        ParamStore.applyPreset(p.values);
        check(ParamStore.get("wet") == 0.45f && ParamStore.get("beat_break") == 0.6f, "applied to the settings");

        // the sensor mover can't move here: no pocket, so it sits at its low end, as on a phone out of a pocket
        for (int i = 0; i < 100; i++) {
            Modulation.tick(0.033, (id, v) -> { });
        }
        float moved = Modulation.output(Params.byId("wet"), ParamStore.get("wet"));
        check(Float.isFinite(moved) && moved >= 0 && moved <= 0.45f + 1e-4f,
                "the In pocket mover runs without a pocket and stays at its resting end (" + moved + ")");

        // and back out: the desktop writes the phone's format
        String out = PresetManager.toJson("Back to the phone", ParamStore.snapshot());
        PresetManager.Preset again = PresetManager.parse(out);
        boolean same = true;
        for (Map.Entry<String, Float> e : p.values.entrySet()) {
            Float v = again.values.get(e.getKey());
            same &= v != null && Math.abs(v - e.getValue()) < 1e-5f;
        }
        check(out.contains("\"format\": \"pdscenes-preset\"") && out.contains("\"version\": 1") && same,
                "exported in the phone's format, every value it had (sensor mover included) comes back");

        // settings survive a restart (the phone's own store, as a JSON file)
        ParamStore.set("reverb_mix", 0.37f);
        ParamStore.save(ctx);
        String stored = new String(Files.readAllBytes(new File(dir, "config/pdscenes_state.json").toPath()));
        check(stored.contains("reverb_mix"), "settings are written to ~/.config/pdscenes/pdscenes_state.json");

        System.out.println(failed == 0 ? "ALL PASSED" : failed + " FAILED");
        System.exit(failed == 0 ? 0 : 1);
    }
}
