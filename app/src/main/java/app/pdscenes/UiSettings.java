// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import android.content.Context;
import android.content.SharedPreferences;

/** Screen preferences: chosen theme, which sections are expanded, the tab shown. Not part of presets. */
final class UiSettings {

    static final int THEME_LIGHT = 0;
    static final int THEME_DARK = 1;
    static final int THEME_AMOLED = 2;

    private static final String PREFS = "pdscenes_ui";
    private static final String KEY_THEME = "theme";
    private static final String KEY_OPEN_PREFIX = "open_";

    private UiSettings() { }

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    static int theme(Context context) {
        return prefs(context).getInt(KEY_THEME, THEME_DARK);
    }

    static void setTheme(Context context, int theme) {
        prefs(context).edit().putInt(KEY_THEME, theme).apply();
    }

    static int themeResource(int theme) {
        switch (theme) {
            case THEME_LIGHT:
                return R.style.Theme_PdScenes_Light;
            case THEME_AMOLED:
                return R.style.Theme_PdScenes_Amoled;
            default:
                return R.style.Theme_PdScenes_Dark;
        }
    }

    static boolean isLight(int theme) {
        return theme == THEME_LIGHT;
    }

    private static final String KEY_TAB = "tab";

    /** The tab last shown (0 Sound, 1 Music, 2 Realms, 3 Scenes, 4 Setup). */
    static int tab(Context context) {
        return prefs(context).getInt(KEY_TAB, 0);
    }

    static void setTab(Context context, int tab) {
        prefs(context).edit().putInt(KEY_TAB, tab).apply();
    }

    static boolean isExpanded(Context context, String sectionId, boolean defaultOpen) {
        return prefs(context).getBoolean(KEY_OPEN_PREFIX + sectionId, defaultOpen);
    }

    static void setExpanded(Context context, String sectionId, boolean open) {
        prefs(context).edit().putBoolean(KEY_OPEN_PREFIX + sectionId, open).apply();
    }
}
