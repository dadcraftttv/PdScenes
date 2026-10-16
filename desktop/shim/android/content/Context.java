// SPDX-License-Identifier: GPL-3.0-or-later
package android.content;

import java.io.File;
import java.util.HashMap;
import java.util.Map;

/**
 * The desktop's stand-in for the little of Android's Context that the shared logic uses: a files folder (saved
 * presets) and named settings stores, kept as JSON files.
 */
public class Context {

    public static final int MODE_PRIVATE = 0;

    private final File files;
    private final File config;
    private final Map<String, SharedPreferences> stores = new HashMap<>();

    public Context(File files, File config) {
        this.files = files;
        this.config = config;
    }

    public File getFilesDir() {
        files.mkdirs();
        return files;
    }

    public Context getApplicationContext() {
        return this;
    }

    public synchronized SharedPreferences getSharedPreferences(String name, int mode) {
        return stores.computeIfAbsent(name, n -> new JsonPrefs(new File(config, n + ".json")));
    }
}
