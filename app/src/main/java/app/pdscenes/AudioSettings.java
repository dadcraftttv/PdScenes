// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import android.content.Context;
import android.content.SharedPreferences;

/**
 * The chosen input and output device, remembered between runs. A device is stored by a stable
 * key (see {@link AudioDevices}) rather than its numeric id, because Android hands out a new id
 * each time a device is reconnected. An empty key means "Automatic" (let Android choose).
 */
final class AudioSettings {

    static final String AUTOMATIC = "";

    private static final String PREFS = "pdscenes_audio";
    private static final String KEY_INPUT = "input";
    private static final String KEY_OUTPUT = "output";

    private AudioSettings() { }

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    static String deviceKey(Context context, boolean input) {
        return prefs(context).getString(input ? KEY_INPUT : KEY_OUTPUT, AUTOMATIC);
    }

    /** Both devices back to Automatic. */
    static void reset(Context context) {
        prefs(context).edit().clear().apply();
    }

    static void setDeviceKey(Context context, boolean input, String key) {
        prefs(context).edit().putString(input ? KEY_INPUT : KEY_OUTPUT, key).apply();
    }
}
