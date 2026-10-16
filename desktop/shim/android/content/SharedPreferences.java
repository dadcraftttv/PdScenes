// SPDX-License-Identifier: GPL-3.0-or-later
package android.content;

import java.util.Map;
import java.util.Set;

/** The desktop's stand-in for Android's settings store (see JsonPrefs): the calls the shared logic makes. */
public interface SharedPreferences {

    String getString(String key, String def);

    boolean getBoolean(String key, boolean def);

    float getFloat(String key, float def);

    int getInt(String key, int def);

    Set<String> getStringSet(String key, Set<String> def);

    boolean contains(String key);

    Map<String, ?> getAll();

    Editor edit();

    interface Editor {
        Editor putString(String key, String value);

        Editor putBoolean(String key, boolean value);

        Editor putFloat(String key, float value);

        Editor putInt(String key, int value);

        Editor putStringSet(String key, Set<String> value);

        Editor remove(String key);

        Editor clear();

        void apply();

        boolean commit();
    }
}
