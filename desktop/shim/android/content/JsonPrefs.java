// SPDX-License-Identifier: GPL-3.0-or-later
package android.content;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** A settings store in a JSON file, written (whole, through a temporary file) on every apply. */
final class JsonPrefs implements SharedPreferences {

    private final File file;
    private final Map<String, Object> values = new LinkedHashMap<>();

    JsonPrefs(File file) {
        this.file = file;
        try {
            if (file.isFile()) {
                JSONObject o = new JSONObject(new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8));
                for (String k : o.keySet()) {
                    Object v = o.get(k);
                    if (v instanceof JSONArray) {
                        Set<String> set = new HashSet<>();
                        for (Object s : (JSONArray) v) {
                            set.add(String.valueOf(s));
                        }
                        v = set;
                    }
                    values.put(k, v);
                }
            }
        } catch (IOException | RuntimeException e) {
            System.err.println("Couldn't read " + file + ": " + e.getMessage() + " (starting from defaults)");
        }
    }

    @Override public synchronized String getString(String k, String d) {
        Object v = values.get(k);
        return v == null ? d : String.valueOf(v);
    }

    @Override public synchronized boolean getBoolean(String k, boolean d) {
        Object v = values.get(k);
        return v instanceof Boolean ? (Boolean) v : v == null ? d : Boolean.parseBoolean(String.valueOf(v));
    }

    @Override public synchronized float getFloat(String k, float d) {
        Object v = values.get(k);
        return v instanceof Number ? ((Number) v).floatValue() : d;
    }

    @Override public synchronized int getInt(String k, int d) {
        Object v = values.get(k);
        return v instanceof Number ? ((Number) v).intValue() : d;
    }

    @SuppressWarnings("unchecked")
    @Override public synchronized Set<String> getStringSet(String k, Set<String> d) {
        Object v = values.get(k);
        return v instanceof Set ? new HashSet<>((Set<String>) v) : d;
    }

    @Override public synchronized boolean contains(String k) {
        return values.containsKey(k);
    }

    @Override public synchronized Map<String, ?> getAll() {
        return new HashMap<>(values);
    }

    @Override public Editor edit() {
        return new Editor() {
            private final Map<String, Object> puts = new LinkedHashMap<>();
            private final List<String> removes = new ArrayList<>();
            private boolean clear;

            @Override public Editor putString(String k, String v) { puts.put(k, v); return this; }
            @Override public Editor putBoolean(String k, boolean v) { puts.put(k, v); return this; }
            @Override public Editor putFloat(String k, float v) { puts.put(k, v); return this; }
            @Override public Editor putInt(String k, int v) { puts.put(k, v); return this; }
            @Override public Editor putStringSet(String k, Set<String> v) { puts.put(k, new HashSet<>(v)); return this; }
            @Override public Editor remove(String k) { removes.add(k); return this; }
            @Override public Editor clear() { clear = true; return this; }

            @Override public void apply() {
                commit();
            }

            @Override public boolean commit() {
                synchronized (JsonPrefs.this) {
                    if (clear) {
                        values.clear();
                    }
                    for (String k : removes) {
                        values.remove(k);
                    }
                    values.putAll(puts);
                    return save();
                }
            }
        };
    }

    private boolean save() {
        JSONObject o = new JSONObject();
        for (Map.Entry<String, Object> e : values.entrySet()) {
            Object v = e.getValue();
            o.put(e.getKey(), v instanceof Set ? new JSONArray((Set<?>) v) : v);
        }
        try {
            file.getParentFile().mkdirs();
            File tmp = new File(file.getPath() + ".tmp");
            Files.write(tmp.toPath(), o.toString(2).getBytes(StandardCharsets.UTF_8));
            Files.move(tmp.toPath(), file.toPath(), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
            return true;
        } catch (IOException e) {
            System.err.println("Couldn't save " + file + ": " + e.getMessage());
            return false;
        }
    }
}
