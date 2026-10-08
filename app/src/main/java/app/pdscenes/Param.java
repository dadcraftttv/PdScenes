// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import java.util.Locale;

/** Definition of one controllable parameter. The id is the Pd receiver name. */
final class Param {

    enum Curve { LINEAR, LOG }

    final String id;
    final String label;
    final float min;
    final float max;
    final float def;
    final String unit;
    final Curve curve;

    /** Range used by randomize/nudge, so random values stay musical and safe. */
    float randMin;
    float randMax;
    boolean randomizable = true;
    /** False for things like input gain, which depend on the device, not the sound. */
    boolean inPreset = true;
    /** On/off switch: values are 0 or 1 and the UI shows a switch instead of a slider. */
    boolean toggle = false;
    /** False for app-only settings (e.g. nudge strength) that Pd never sees. */
    boolean sendToPd = true;
    /** Which collapsible group on the screen this belongs to (see Params.SECTIONS). */
    String section = "main";
    /** Digits shown after the decimal point; -1 picks a sensible default from the range. */
    int decimals = -1;
    /** Pick-one setting: the value is an index into these names and the UI shows a dropdown. */
    String[] choices = null;
    /** For a mover setting: the id of the slider it moves; null for everything else. */
    String moverOf = null;
    /** When a preset doesn't mention this parameter, reset it to its default instead of keeping it. */
    boolean resetWhenAbsent = false;

    Param(String id, String label, float min, float max, float def, String unit, Curve curve) {
        this.id = id;
        this.label = label;
        this.min = min;
        this.max = max;
        this.def = def;
        this.unit = unit;
        this.curve = curve;
        this.randMin = min;
        this.randMax = max;
    }

    Param rand(float lo, float hi) {
        randMin = lo;
        randMax = hi;
        return this;
    }

    Param noRandom() {
        randomizable = false;
        return this;
    }

    Param noPreset() {
        inPreset = false;
        return this;
    }

    Param toggle() {
        toggle = true;
        randomizable = false;
        return this;
    }

    Param inSection(String sectionId) {
        section = sectionId;
        return this;
    }

    Param noPd() {
        sendToPd = false;
        return this;
    }

    Param choices(String... names) {
        choices = names;
        randomizable = false;
        return this;
    }

    Param moverOf(String paramId) {
        moverOf = paramId;
        return this;
    }

    Param resetWhenAbsent() {
        resetWhenAbsent = true;
        return this;
    }

    Param decimals(int n) {
        decimals = n;
        return this;
    }

    float clamp(float v) {
        if (toggle) {
            return v >= 0.5f ? 1f : 0f;
        }
        float c = Math.max(min, Math.min(max, v));
        return choices != null ? Math.round(c) : c;
    }

    /** Slider position (0..1) to parameter value. */
    float toValue(float t) {
        t = Math.max(0f, Math.min(1f, t));
        if (curve == Curve.LOG) {
            return (float) (min * Math.pow(max / min, t));
        }
        return min + (max - min) * t;
    }

    /** Parameter value to slider position (0..1). */
    float toNorm(float v) {
        v = clamp(v);
        if (curve == Curve.LOG) {
            return (float) (Math.log(v / min) / Math.log(max / min));
        }
        return (v - min) / (max - min);
    }

    String format(float v) {
        if (toggle) {
            return v >= 0.5f ? "on" : "off";
        }
        if (choices != null) {
            return choices[Math.round(clamp(v))];
        }
        int d = decimals >= 0 ? decimals : (max >= 100f ? 0 : 2);
        return String.format(Locale.US, "%." + d + "f%s", v, unit);
    }
}
