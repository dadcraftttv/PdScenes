// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Canvas;
import android.graphics.Typeface;
import android.media.AudioDeviceCallback;
import android.media.AudioDeviceInfo;
import android.media.AudioManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.RadioGroup;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.Spinner;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONException;
import org.puredata.core.PdBase;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Control screen: engine on/off, presets, randomize, and one control per parameter. */
public class MainActivity extends Activity {

    private static final int REQ_PERMISSIONS = 1;
    private static final int REQ_EXPORT = 2;
    private static final int REQ_MIC = 3;   // the walkthrough's "Allow microphone" (doesn't start the sound)
    private Walkthrough walkthrough;
    /** Name chosen in the export dialog, used once the file picker returns. */
    private String exportName = "preset";
    private static final int REQ_IMPORT = 3;
    private static final int REQ_IMPORT_SCENE = 4;
    private static final int REQ_IMPORT_SCENE_FOLDER = 5;

    private final List<Row> rows = new ArrayList<>();
    /** The mover controls under each slider, greyed out while their section's movers are off. */
    private final List<MoverUi> moverUis = new ArrayList<>();
    private AudioManager audioManager;

    private TextView status;
    /** The bar pinned to the bottom: what is playing and why, Start/Stop, hold the world, save this sound. */
    private TextView nowLine;
    private final Map<String, TextView> budgetLines = new HashMap<>();   // budget name -> its "used / left" line
    private Button holdButton;
    private Button snapButton;
    private final android.os.Handler uiHandler = new android.os.Handler(android.os.Looper.getMainLooper());
    private static final long NOW_LINE_MS = 1000;
    private final Runnable nowLineTick = new Runnable() {
        @Override
        public void run() {
            updateNowLine();
            updateMoverDots();
            updateIntensityRow();
            updateStatus();
            if (walkthrough != null) {
                walkthrough.refresh();   // headphones plugged in meanwhile
            }
            updateDiagnostics();
            uiHandler.postDelayed(this, NOW_LINE_MS);
        }
    };
    private TextView warning;
    private Button startStop;
    private Button undoButton;
    private TextView sceneLabel;
    /** Presets, randomize and the effect sections: hidden while an imported scene is selected. */
    // ---- tabs: Sound, Music, Realms, Scenes, Setup (the one long list had outgrown itself) ----
    private static final int TAB_SOUND = 0, TAB_MUSIC = 1, TAB_REALMS = 2, TAB_SCENES = 3, TAB_SETUP = 4;
    private static final int[] TAB_NAMES = {R.string.tab_sound, R.string.tab_music, R.string.tab_realms,
            R.string.tab_scenes, R.string.tab_setup};
    private final LinearLayout[] tabPages = new LinearLayout[TAB_NAMES.length];     // each tab's whole page
    private final LinearLayout[] tabBodies = new LinearLayout[TAB_NAMES.length];    // its controls (hidden for a scene)
    private final TextView[] tabNotices = new TextView[TAB_NAMES.length];           // "paused while a scene plays"
    private final TextView[] tabButtons = new TextView[TAB_NAMES.length];
    private final int[] tabScroll = new int[TAB_NAMES.length];
    private int currentTab = -1;
    private LinearLayout xyPadSlot;          // where the pad sits on the Sound tab (an XY pad for the movers)
    private LinearLayout scenePadSlot;       // ...and on the Scenes tab (the scene's own pad)
    /** One dropdown per automatic world, and the line saying which one is playing. */
    private final List<WorldRow> worldRows = new ArrayList<>();
    private TextView worldStatus;

    private static final class WorldRow {
        final Worlds.World world;
        final Spinner spinner;
        List<String> presets = new ArrayList<>();

        WorldRow(Worlds.World world, Spinner spinner) {
            this.world = world;
            this.spinner = spinner;
        }
    }
    private ScenePad scenePad;
    private LinearLayout sceneLevels;
    private TextView padHint;

    /** One on-screen control: a slider with a label, or a switch (for toggles). */
    private static final class MoverUi {
        final String sectionId;
        final String paramId;
        final View box;        // everything: the movement dropdown and the details
        final View details;    // speed and depth, shown only while a movement is chosen

        MoverUi(String sectionId, String paramId, View box, View details) {
            this.sectionId = sectionId;
            this.paramId = paramId;
            this.box = box;
            this.details = details;
        }
    }

    private static final class Row {
        final Param param;
        final TextView label;     // slider rows only
        final SeekBar slider;     // slider rows only
        final Switch switchView;  // toggle rows only
        final Spinner spinner;    // pick-one rows only

        Row(Param param, TextView label, SeekBar slider, Switch switchView, Spinner spinner) {
            this.param = param;
            this.label = label;
            this.slider = slider;
            this.switchView = switchView;
            this.spinner = spinner;
        }
    }

    /** A dropdown of connected audio devices, plus "Automatic" as the first entry. */
    private static final class DevicePicker {
        final boolean input;
        final Spinner spinner;
        List<AudioDevices.Device> devices = new ArrayList<>();
        String shownKey = AudioSettings.AUTOMATIC;   // what the dropdown currently displays

        DevicePicker(boolean input, Spinner spinner) {
            this.input = input;
            this.spinner = spinner;
        }
    }

    private DevicePicker inputPicker;
    private DevicePicker outputPicker;
    private TextView micHint;

    /** Advice that appears when a Bluetooth headset is the chosen microphone. */
    private void updateMicHint() {
        if (micHint == null) {
            return;
        }
        AudioDevices.Device in = AudioDevices.find(this, true);
        if (AudioDevices.isLeAudio(in)) {
            micHint.setText(R.string.mic_hint_le);
        } else if (AudioDevices.isBluetoothMic(in)) {
            micHint.setText(R.string.mic_hint_call);
        } else if (AudioDevices.wiredWithoutMic(this)) {
            micHint.setText(R.string.mic_hint_no_wired_mic);
        } else {
            micHint.setText("");
        }
        micHint.setVisibility(micHint.length() == 0 ? View.GONE : View.VISIBLE);
    }

    /** Re-checks for headphones when something is plugged in or removed. */
    private final AudioDeviceCallback deviceCallback = new AudioDeviceCallback() {
        @Override
        @SuppressWarnings("NullableProblems")
        public void onAudioDevicesAdded(AudioDeviceInfo[] added) {
            refreshDevicePickers();
            updateUi();
        }

        @Override
        @SuppressWarnings("NullableProblems")
        public void onAudioDevicesRemoved(AudioDeviceInfo[] removed) {
            refreshDevicePickers();
            updateUi();
        }
    };

    // ---- lifecycle ----

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        int theme = UiSettings.theme(this);
        setTheme(UiSettings.themeResource(theme));   // must be set before any view is created
        super.onCreate(savedInstanceState);
        ParamStore.loadOnce(this);
        SceneLibrary.installBuiltIns(this, SceneSettings.scenesDir(this));
        audioManager = getSystemService(AudioManager.class);

        // The settings scroll; the bar with Start/Stop stays at the bottom, in reach of a thumb while walking.
        android.widget.FrameLayout screen = new android.widget.FrameLayout(this);
        ScrollView scroll = new ScrollView(this);
        mainScroll = scroll;
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(16);
        root.setPadding(pad, pad, pad, pad);
        scroll.addView(root);
        screen.addView(scroll, new android.widget.FrameLayout.LayoutParams(
                android.widget.FrameLayout.LayoutParams.MATCH_PARENT, android.widget.FrameLayout.LayoutParams.MATCH_PARENT));
        // The card floats over the settings, which scroll on behind it; the end of the list stops just above it.
        View bar = buildBottomBar();
        android.widget.FrameLayout.LayoutParams barParams = new android.widget.FrameLayout.LayoutParams(
                android.widget.FrameLayout.LayoutParams.MATCH_PARENT, android.widget.FrameLayout.LayoutParams.WRAP_CONTENT,
                android.view.Gravity.BOTTOM);
        int m = Math.max(0, dp(10) - barGlow);   // AMOLED's glow already brings its own room
        barParams.setMargins(m, 0, m, Math.max(0, dp(10) - barGlow));
        screen.addView(bar, barParams);
        bar.addOnLayoutChangeListener((v, l, t, r, b2, ol, ot, or, ob) -> {
            int under = v.getHeight() + barParams.bottomMargin;
            if (root.getPaddingBottom() != pad + under) {
                root.setPadding(pad, pad, pad, pad + under);
            }
        });
        screen.setClipToPadding(false);   // the card's shadow may spill into the navigation bar area, not stop at it
        setContentView(screen);

        // Targeting Android 15+ draws edge-to-edge; keep content clear of the system bars.
        if (Build.VERSION.SDK_INT >= 30) {
            screen.setOnApplyWindowInsetsListener((v, insets) -> {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
                v.setPadding(bars.left, bars.top, bars.right, bars.bottom);
                return WindowInsets.CONSUMED;
            });
        }

        TextView title = new TextView(this);
        title.setText(R.string.app_name);
        title.setTextSize(28);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        root.addView(title);

        warning = new TextView(this);
        warning.setTextSize(14);
        warning.setTextColor(UiSettings.isLight(theme) ? 0xFFB00020 : 0xFFFF6E6E);
        warning.setText(R.string.no_headphones_warning);
        root.addView(warning);

        // the five tab pages, one shown at a time (the strip that switches them sits on the bottom card)
        for (int t = 0; t < TAB_NAMES.length; t++) {
            LinearLayout page = new LinearLayout(this);
            page.setOrientation(LinearLayout.VERTICAL);
            TextView notice = new TextView(this);
            notice.setText(R.string.tab_paused_scene);
            notice.setTextSize(15);
            notice.setPadding(0, dp(16), 0, dp(16));
            notice.setVisibility(View.GONE);
            page.addView(notice);
            LinearLayout body = new LinearLayout(this);
            body.setOrientation(LinearLayout.VERTICAL);
            page.addView(body);
            page.setVisibility(View.GONE);
            root.addView(page);
            tabPages[t] = page;
            tabNotices[t] = notice;
            tabBodies[t] = body;
        }
        LinearLayout sound = tabBodies[TAB_SOUND], music = tabBodies[TAB_MUSIC], realms = tabBodies[TAB_REALMS];
        LinearLayout scenes = tabBodies[TAB_SCENES], setup = tabBodies[TAB_SETUP];

        // ---- Scenes ----
        sceneLabel = new TextView(this);
        sceneLabel.setTextSize(16);
        sceneLabel.setPadding(0, dp(12), 0, dp(4));
        scenes.addView(sceneLabel);
        LinearLayout sceneRow = newButtonRow(scenes);
        addButton(sceneRow, R.string.choose_scene, this::showScenes);
        addButton(sceneRow, R.string.import_scene, this::startImportScene);
        addButton(sceneRow, R.string.import_scene_folder, this::startImportSceneFolder);
        scenePadSlot = new LinearLayout(this);
        scenePadSlot.setOrientation(LinearLayout.VERTICAL);
        scenes.addView(scenePadSlot);

        scenePad = new ScenePad(this);
        scenePad.setContentDescription(getString(R.string.pad_description));
        scenePad.setListener(this::sendTouch);
        padHint = new TextView(this);
        padHint.setText(R.string.pad_hint);
        padHint.setTextSize(13);

        sceneLevels = new LinearLayout(this);
        sceneLevels.setOrientation(LinearLayout.VERTICAL);
        addLevelSlider(sceneLevels, R.string.scene_volume, SceneSettings.volume(this), v -> {
            SceneSettings.setVolume(this, v);
            sendSceneLevelsIfRunning();
        });
        addLevelSlider(sceneLevels, R.string.scene_mic_volume, SceneSettings.micVolume(this), v -> {
            SceneSettings.setMicVolume(this, v);
            sendSceneLevelsIfRunning();
        });
        CheckBox timing = new CheckBox(this);
        timing.setText(R.string.scene_rjdj_timing);
        timing.setChecked(SceneSettings.rjdjTiming(this));
        timing.setOnCheckedChangeListener((b, on) -> {
            SceneSettings.setRjdjTiming(this, on);
            if (AudioService.isRunning()) {   // the rate is chosen when the engine starts
                startForegroundService(new Intent(this, AudioService.class).setAction(AudioService.ACTION_RESTART));
            }
        });
        sceneLevels.addView(timing);
        TextView hint = new TextView(this);
        hint.setText(R.string.scene_headphones_hint);
        hint.setTextSize(13);
        sceneLevels.addView(hint);
        scenes.addView(sceneLevels);

        // ---- Sound: presets and shortcuts, the XY pad, then the input and the effects ----
        LinearLayout presetRow = newButtonRow(sound);
        addButton(presetRow, R.string.presets, this::showPresets);
        addButton(presetRow, R.string.save, this::showSave);
        addButton(presetRow, R.string.export, this::startExport);
        addButton(presetRow, R.string.import_preset, this::startImport);

        LinearLayout randomRow = newButtonRow(sound);
        addButton(randomRow, R.string.randomize, () -> {
            ParamStore.randomize();
            refreshRows();
            uiHandler.removeCallbacks(morphFollow);
            uiHandler.post(morphFollow);   // the sliders follow the glide on screen
        });
        addButton(randomRow, R.string.nudge, () -> {
            ParamStore.nudge(ParamStore.get("nudge_amount"));
            refreshRows();
        });
        undoButton = addButton(randomRow, R.string.undo, () -> {
            ParamStore.undo();
            refreshRows();
        });
        xyPadSlot = new LinearLayout(this);
        xyPadSlot.setOrientation(LinearLayout.VERTICAL);
        sound.addView(xyPadSlot);

        // ---- Realms ----
        Worlds.load(this);
        addSection(realms, "worlds", getString(R.string.section_worlds), true, this::fillWorldsSection);

        // ---- the sections, each on its tab ----
        for (Params.Section section : Params.SECTIONS) {
            LinearLayout tab = "beat".equals(section.id) || "music".equals(section.id) ? music
                    : "behavior".equals(section.id) ? setup : sound;
            addSection(tab, section.id, section.title, section.openByDefault,
                    body -> fillEffectSection(body, section));
        }

        // ---- Setup ----
        addAudioSection(setup);
        addDiagnosticsSection(setup);
        addAppearanceSection(setup);
        LinearLayout resetRow = newButtonRow(setup);
        addButton(resetRow, R.string.reset_all, this::confirmResetAll);
        addAboutSection(setup);
        showTab(UiSettings.tab(this));
        refreshRows();
        if (FirstRun.showWalkthrough(UiSettings.walkthroughSeen(this), installTimes()[0], installTimes()[1])) {
            showWalkthrough();
        }
        updateSceneUi();
    }

    /** The tab strip: five equal tabs, the card's top row; the shown one bold, accent-coloured, on a soft pill. */
    private View buildTabStrip() {
        LinearLayout strip = new LinearLayout(this);
        strip.setOrientation(LinearLayout.HORIZONTAL);
        for (int t = 0; t < TAB_NAMES.length; t++) {
            TextView b = new TextView(this);
            b.setText(TAB_NAMES[t]);
            b.setTextSize(15);
            b.setGravity(android.view.Gravity.CENTER);
            b.setPadding(0, dp(8), 0, dp(8));
            final int tab = t;
            b.setOnClickListener(v -> showTab(tab));
            b.setContentDescription(getString(R.string.tab_description, getString(TAB_NAMES[t])));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
            lp.setMargins(dp(2), 0, dp(2), 0);
            strip.addView(b, lp);
            tabButtons[t] = b;
        }
        return strip;
    }

    /** Shows one tab (each keeps its own scroll position) and remembers it for next time. */
    private void showTab(int tab) {
        tab = Math.max(0, Math.min(TAB_NAMES.length - 1, tab));
        if (currentTab >= 0 && mainScroll != null) {
            tabScroll[currentTab] = mainScroll.getScrollY();
        }
        for (int t = 0; t < TAB_NAMES.length; t++) {
            tabPages[t].setVisibility(t == tab ? View.VISIBLE : View.GONE);
            TextView b = tabButtons[t];
            if (b != null) {
                b.setTypeface(t == tab ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
                b.setTextColor(t == tab ? accentColor() : status != null ? status.getCurrentTextColor() : 0xFF888888);
                b.setAlpha(t == tab ? 1f : 0.75f);
                b.setSelected(t == tab);
                if (t == tab) {
                    android.graphics.drawable.GradientDrawable pill = new android.graphics.drawable.GradientDrawable();
                    pill.setCornerRadius(dp(14));
                    pill.setColor((accentColor() & 0x00FFFFFF) | 0x2E000000);
                    b.setBackground(pill);
                } else {
                    b.setBackground(null);
                }
            }
        }
        currentTab = tab;
        UiSettings.setTab(this, tab);
        if (mainScroll != null) {
            final int y = tabScroll[tab];
            mainScroll.post(() -> mainScroll.scrollTo(0, y));
        }
    }

    private View buildBottomBar() {
        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.VERTICAL);
        bar.setPadding(dp(14), dp(6), dp(14), dp(8));
        styleBarCard(bar);
        bar.addView(buildTabStrip());                    // the tabs: the card's top row, in thumb reach
        View rule = new View(this);
        rule.setBackgroundColor(0x33888888);
        LinearLayout.LayoutParams ruleParams = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(1));
        ruleParams.setMargins(0, dp(4), 0, dp(6));
        bar.addView(rule, ruleParams);

        status = new TextView(this);
        status.setTextSize(14);
        bar.addView(status);
        nowLine = new TextView(this);
        nowLine.setTextSize(14);
        nowLine.setTypeface(Typeface.DEFAULT_BOLD);
        nowLine.setPadding(0, dp(2), 0, 0);
        bar.addView(nowLine);
        bar.addView(buildIntensityRow());

        LinearLayout row = newButtonRow(bar);
        startStop = new Button(this);
        startStop.setAllCaps(false);
        startStop.setOnClickListener(v -> onStartStop());
        row.addView(startStop, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1.4f));
        holdButton = addButton(row, R.string.hold_world, () -> {
            Worlds.setHeld(!Worlds.isHeld());
            updateNowLine();
        });
        snapButton = addButton(row, R.string.snapshot, this::saveSnapshot);
        return bar;
    }

    private LinearLayout intensityRow;
    private TextView intensityLabel;
    private SeekBar intensityBar;

    /** Intensity in thumb reach: the same setting as the slider at the top of Input & output. */
    private View buildIntensityRow() {
        intensityRow = new LinearLayout(this);
        intensityRow.setOrientation(LinearLayout.HORIZONTAL);
        intensityRow.setGravity(android.view.Gravity.CENTER_VERTICAL);
        intensityRow.setPadding(0, dp(4), 0, 0);
        intensityLabel = new TextView(this);
        intensityLabel.setTextSize(14);
        intensityRow.addView(intensityLabel);
        intensityBar = new SeekBar(this);
        intensityBar.setMax(100);
        intensityBar.setContentDescription(getString(R.string.intensity_card));
        intensityBar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar b, int progress, boolean fromUser) {
                if (fromUser) {
                    ParamStore.set(Intensity.ID, progress / 100f);
                    updateIntensityRow();
                }
            }

            @Override
            public void onStartTrackingTouch(SeekBar b) { }

            @Override
            public void onStopTrackingTouch(SeekBar b) {
                refreshRows();   // the slider in Input & output follows
            }
        });
        intensityRow.addView(intensityBar, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        updateIntensityRow();
        return intensityRow;
    }

    /** Shows Intensity's value (and the mover dot while a mover pushes it); hidden while a scene plays. */
    private void updateIntensityRow() {
        if (intensityRow == null) {
            return;
        }
        intensityRow.setVisibility(SceneSettings.current(this) == null ? View.VISIBLE : View.GONE);
        float v = ParamStore.get(Intensity.ID);
        if (!intensityBar.isPressed()) {
            intensityBar.setProgress(Math.round(v * 100));
        }
        intensityLabel.setText(getString(R.string.intensity_card_value, Math.round(v * 100))
                + (Modulation.isMoving(Intensity.ID) ? MOVER_DOT : ""));
    }

    /**
     * The bar is a card lifted above the page: rounded like the scene pad, a slightly lighter surface and a
     * shadow. On AMOLED black a dark shadow can't show, so the card gets a thin outline and a glow in the
     * system accent colour (Material You, from the wallpaper, on Android 12+).
     */
    private void styleBarCard(View bar) {
        int theme = UiSettings.theme(this);
        TypedValue bg = new TypedValue();
        getTheme().resolveAttribute(android.R.attr.colorBackground, bg, true);
        android.graphics.drawable.GradientDrawable card = new android.graphics.drawable.GradientDrawable();
        card.setCornerRadius(ScenePad.CORNER_DP * getResources().getDisplayMetrics().density);
        if (theme == UiSettings.THEME_AMOLED) {
            // Android's own shadows don't show on pure black, even tinted, so draw a soft glow ourselves.
            barGlow = dp(14);
            bar.setPadding(bar.getPaddingLeft() + barGlow, bar.getPaddingTop() + barGlow,
                    bar.getPaddingRight() + barGlow, bar.getPaddingBottom() + barGlow);
            bar.setBackground(new GlowCard(ScenePad.CORNER_DP * getResources().getDisplayMetrics().density,
                    barGlow, accentColor()));
            return;
        } else if (UiSettings.isLight(theme)) {
            card.setColor(0xFFFFFFFF);
        } else {
            card.setColor(blend(bg.data, 0xFFFFFFFF, 0.09f));   // dark: a step lighter than the page
        }
        bar.setBackground(card);
        // A gentle lift on Light and Dark; AMOLED needs more so the accent glow shows.
        bar.setElevation(theme == UiSettings.THEME_AMOLED ? dp(10) : dp(4));
    }

    /** Extra room around the bar for the AMOLED glow (0 in the other themes, which use a real shadow). */
    private int barGlow;

    /** A black rounded card with a soft glow in {@code color} around it; the glow takes {@code glow} px each side. */
    private static final class GlowCard extends android.graphics.drawable.Drawable {
        private final android.graphics.Paint paint = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
        private final android.graphics.RectF card = new android.graphics.RectF();
        private final float corner;
        private final int glow;
        private final int color;

        GlowCard(float corner, int glow, int color) {
            this.corner = corner;
            this.glow = glow;
            this.color = color;
        }

        @Override
        public void draw(Canvas canvas) {
            android.graphics.Rect b = getBounds();
            card.set(b.left + glow, b.top + glow, b.right - glow, b.bottom - glow);
            paint.setColor(0xFF000000);
            paint.setShadowLayer(glow * 0.8f, 0, glow * 0.15f, (color & 0x00FFFFFF) | 0x8C000000);
            canvas.drawRoundRect(card, corner, corner, paint);
        }

        @Override
        public void setAlpha(int alpha) { }

        @Override
        public void setColorFilter(android.graphics.ColorFilter filter) { }

        @Override
        @SuppressWarnings("deprecation")
        public int getOpacity() {
            return android.graphics.PixelFormat.TRANSLUCENT;
        }
    }

    /** The wallpaper accent on Android 12+, otherwise the theme's accent. */
    private int accentColor() {
        if (Build.VERSION.SDK_INT >= 31) {
            return getColor(android.R.color.system_accent1_300);
        }
        TypedValue a = new TypedValue();
        getTheme().resolveAttribute(android.R.attr.colorAccent, a, true);
        return a.data;
    }

    private static int blend(int from, int to, float k) {
        int r = Math.round(((from >> 16) & 0xFF) * (1 - k) + ((to >> 16) & 0xFF) * k);
        int g = Math.round(((from >> 8) & 0xFF) * (1 - k) + ((to >> 8) & 0xFF) * k);
        int b = Math.round((from & 0xFF) * (1 - k) + (to & 0xFF) * k);
        return 0xFF000000 | (r << 16) | (g << 8) | b;
    }

    /** One line: the world playing now and, in a few words, why. Refreshed once a second while visible. */
    private void updateNowLine() {
        boolean builtIn = AudioService.isRunning() && SceneSettings.current(this) == null;
        boolean worlds = builtIn && Worlds.isEnabled();
        holdButton.setVisibility(worlds ? View.VISIBLE : View.GONE);
        holdButton.setText(Worlds.isHeld() ? R.string.holding_world : R.string.hold_world);
        snapButton.setVisibility(SceneSettings.current(this) == null ? View.VISIBLE : View.GONE);
        if (!worlds) {
            nowLine.setVisibility(View.GONE);
            return;
        }
        nowLine.setVisibility(View.VISIBLE);
        String id = Worlds.currentWorld();
        String name = getString(R.string.worlds_yours);
        for (Worlds.World w : Worlds.ALL) {
            if (w.id.equals(id)) {
                name = w.title;
            }
        }
        List<String> why = new ArrayList<>();
        int minute = Worlds.minuteOfDayNow();
        if (minute >= WorldSelector.NIGHT_START_MINUTE && minute < WorldSelector.NIGHT_END_MINUTE) {
            why.add(getString(R.string.why_night));
        }
        double nowS = android.os.SystemClock.elapsedRealtimeNanos() / 1e9;
        if (WorldSelector.UNSTABLE.equals(id)) {
            why.add(getString(R.string.why_shaken));
        }
        if (StepDetector.walking(nowS)) {
            boolean clock = ParamStore.get("beat_follow") >= 0.5f && AudioService.tempo() > 0;
            why.add(clock ? getString(R.string.why_walking_bpm, Math.round(AudioService.tempo()))
                    : getString(R.string.why_walking));
        }
        if (PhoneContext.inPocket()) {
            why.add(getString(R.string.why_pocket));
        }
        if (HandlingDetector.level() > 0.3f) {
            why.add(getString(R.string.why_handling));
        }
        int room = Worlds.roomQuiet() ? R.string.why_room_quiet
                : Worlds.roomLoud() ? (Worlds.roomLively() ? R.string.why_room_lively : R.string.why_room_steady)
                : R.string.why_room_middle;
        why.add(getString(room, Math.round(Worlds.roomLevelDb())));
        if (ParamStore.get("beat_level") > 0 && ParamStore.get("beat_follow") >= 0.5f && ParamStore.get("rhythm_src") >= 0.5f) {
            int[] kit = AudioService.kit();
            why.add(getString(R.string.why_kit, kit[0], kit[1], kit[2], kit[3]));
        }
        String line = getString(R.string.now_line, name, String.join(" \u00b7 ", why));
        if (Worlds.isHeld()) {
            line = getString(R.string.now_line_held, line);
        }
        nowLine.setText(line);
    }

    /** Saves the sound playing right now as a preset named after the time, to rename later if wanted. */
    private void saveSnapshot() {
        String base = new java.text.SimpleDateFormat("EEE H-mm", java.util.Locale.getDefault()).format(new java.util.Date());
        List<String> taken = PresetManager.userNames(this);
        String name = base;
        for (int n = 2; taken.contains(name); n++) {
            name = base + " " + n;
        }
        try {
            String used = PresetManager.save(this, name, ParamStore.snapshot());
            toast(R.string.toast_saved, used);
            refreshWorldRows();
        } catch (IOException e) {
            toast(R.string.toast_save_failed, e.getMessage());
        }
    }

    /** While Randomize glides, redraw the sliders a few times a second so they visibly move. */
    private final Runnable morphFollow = new Runnable() {
        @Override
        public void run() {
            refreshRows();
            if (ParamStore.isMorphing()) {
                uiHandler.postDelayed(this, 120);
            }
        }
    };

    /** Where the settings were scrolled to, so a theme change (which rebuilds the screen) keeps the place. */
    private static final String STATE_SCROLL = "scrollY";
    private ScrollView mainScroll;

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        if (mainScroll != null && currentTab >= 0) {
            tabScroll[currentTab] = mainScroll.getScrollY();
            out.putIntArray(STATE_SCROLL, tabScroll);
        }
    }

    @Override
    protected void onRestoreInstanceState(Bundle saved) {
        super.onRestoreInstanceState(saved);
        int[] all = saved.getIntArray(STATE_SCROLL);
        if (all != null && all.length == tabScroll.length) {
            System.arraycopy(all, 0, tabScroll, 0, all.length);
        }
        int y = currentTab >= 0 ? tabScroll[currentTab] : 0;
        if (y <= 0 || mainScroll == null) {
            return;
        }
        // The list reaches its full height over a couple of layout passes (the card's height pads its end),
        // so keep trying until the position fits.
        ScrollView scroll = mainScroll;
        scroll.getViewTreeObserver().addOnGlobalLayoutListener(new android.view.ViewTreeObserver.OnGlobalLayoutListener() {
            int tries;

            @Override
            public void onGlobalLayout() {
                scroll.scrollTo(0, y);
                if (scroll.getScrollY() == y || ++tries >= 5) {
                    scroll.getViewTreeObserver().removeOnGlobalLayoutListener(this);
                }
            }
        });
    }

    @Override
    protected void onResume() {
        super.onResume();
        // Event-driven updates instead of polling: the service and the audio routing tell us.
        AudioService.setStateListener(this::updateUi);
        Worlds.load(this);
        Worlds.setListener(() -> {
            updateWorldStatus();
            refreshRows();   // sliders move on their own while a world fades in
        });
        refreshWorldRows();
        updateWorldStatus();
        uiHandler.post(nowLineTick);
        audioManager.registerAudioDeviceCallback(deviceCallback, null);
        refreshDevicePickers();
        updateUi();
    }

    @Override
    protected void onPause() {
        AudioService.setStateListener(null);
        Worlds.setListener(null);
        uiHandler.removeCallbacks(nowLineTick);
        uiHandler.removeCallbacks(morphFollow);
        audioManager.unregisterAudioDeviceCallback(deviceCallback);
        ParamStore.save(this);
        super.onPause();
    }

    // ---- building the screen ----

    private LinearLayout newButtonRow(LinearLayout parent) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        parent.addView(row, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        return row;
    }

    private Button addButton(LinearLayout row, int textRes, Runnable action) {
        Button b = new Button(this);
        b.setText(textRes);
        b.setAllCaps(false);
        b.setOnClickListener(v -> action.run());
        row.addView(b, new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        return b;
    }

    /** A tappable header that shows or hides the returned container. State is remembered. */
    private LinearLayout addSection(LinearLayout parent, String id, String title,
                                    boolean openByDefault) {
        return addSection(parent, id, title, openByDefault, null);
    }

    /**
     * A foldable section. {@code fill} (may be null) builds the rows the first time the section is shown, so
     * folded sections cost nothing at startup.
     */
    private LinearLayout addSection(LinearLayout parent, String id, String title, boolean openByDefault,
                                    java.util.function.Consumer<LinearLayout> fill) {
        TextView header = new TextView(this);
        header.setTextSize(18);
        header.setTypeface(Typeface.DEFAULT_BOLD);
        header.setPadding(0, dp(20), 0, dp(8));
        TypedValue ripple = new TypedValue();
        getTheme().resolveAttribute(android.R.attr.selectableItemBackground, ripple, true);
        header.setBackgroundResource(ripple.resourceId);

        LinearLayout body = new LinearLayout(this);
        body.setOrientation(LinearLayout.VERTICAL);

        boolean[] filled = {fill == null};
        Runnable show = () -> {
            if (!filled[0]) {
                filled[0] = true;
                fill.accept(body);
                refreshRows();   // the new rows start with the stored values
            }
        };
        boolean open = UiSettings.isExpanded(this, id, openByDefault);
        showSectionState(header, body, title, open);
        if (open) {
            show.run();
        }
        header.setOnClickListener(v -> {
            boolean nowOpen = body.getVisibility() != View.VISIBLE;
            UiSettings.setExpanded(this, id, nowOpen);
            showSectionState(header, body, title, nowOpen);
            if (nowOpen) {
                show.run();
                refreshRows();   // rows skipped while folded catch up
            }
        });

        parent.addView(header);
        parent.addView(body);
        return body;
    }

    /** One effect section: its Movers switch, then each slider followed by its movement settings. */
    private void fillEffectSection(LinearLayout body, Params.Section section) {
        Param moversSwitch = Params.byId(Params.moversSwitchId(section.id));
        if (moversSwitch != null) {
            addRow(body, moversSwitch);
        }
        for (Param p : Params.ALL) {
            if (p.section.equals(section.id) && p.moverOf == null && p != moversSwitch) {
                addRow(body, p);
                if (Params.byId(Params.moverId(p.id, "mv")) != null) {
                    addMoverRows(body, section.id, p);
                }
                if (p.budget != null && lastOfBudget(p)) {   // the glitch matrix: how much of it is in use
                    TextView line = new TextView(this);
                    line.setTextSize(14);
                    line.setTypeface(Typeface.DEFAULT_BOLD);
                    line.setPadding(0, dp(10), 0, dp(4));
                    body.addView(line);
                    budgetLines.put(p.budget, line);
                }
            }
        }
        updateBudgetLines();
    }

    /** True for the last slider of its budget group (the line showing what is used goes under it). */
    private static boolean lastOfBudget(Param p) {
        boolean after = false;
        for (Param q : Params.ALL) {
            if (q == p) {
                after = true;
            } else if (after && p.budget.equals(q.budget)) {
                return false;
            }
        }
        return true;
    }

    /** "Glitch budget: 80% used, 20% left to silence" under the glitch matrix sliders. */
    private void updateBudgetLines() {
        for (Map.Entry<String, TextView> e : budgetLines.entrySet()) {
            float used = 0;
            for (Param q : Params.ALL) {
                if (e.getKey().equals(q.budget)) {
                    used += ParamStore.get(q.id);
                }
            }
            int u = Math.round(used);
            e.getValue().setText(u > 100 ? getString(R.string.glitch_budget_over, u)
                    : getString(R.string.glitch_budget, u, 100 - u));
        }
    }

    /** The Worlds section: an on/off switch, what is playing now, and which preset each world uses. */
    private void fillWorldsSection(LinearLayout body) {
        Switch auto = new Switch(this);
        auto.setText(R.string.worlds_auto);
        auto.setTextSize(16);
        auto.setPadding(0, dp(8), 0, 0);
        auto.setChecked(Worlds.isEnabled());
        auto.setOnClickListener(v -> {
            Worlds.setEnabled(auto.isChecked());
            updateWorldStatus();
        });
        body.addView(auto);

        worldStatus = new TextView(this);
        worldStatus.setTextSize(14);
        worldStatus.setPadding(0, dp(8), 0, dp(4));
        body.addView(worldStatus);

        for (Worlds.World w : Worlds.ALL) {
            TextView label = new TextView(this);
            label.setText(getString(R.string.world_row, w.title, w.when));
            label.setTextSize(14);
            label.setPadding(0, dp(8), 0, 0);
            body.addView(label);
            Spinner spinner = new Spinner(this);
            body.addView(spinner);
            WorldRow row = new WorldRow(w, spinner);
            worldRows.add(row);
            spinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
                @Override
                public void onItemSelected(AdapterView<?> parentView, View v, int position, long id) {
                    String chosen = position == 0 || position > row.presets.size()
                            ? Worlds.NONE : row.presets.get(position - 1);
                    if (!chosen.equals(Worlds.presetName(w.id))) {   // ignore our own refresh
                        Worlds.setPreset(w.id, chosen);
                    }
                }

                @Override
                public void onNothingSelected(AdapterView<?> parentView) { }
            });
            addRealmIngredients(body, w);
        }
        TextView note = new TextView(this);
        note.setText(R.string.worlds_note);
        note.setTextSize(13);
        note.setPadding(0, dp(12), 0, 0);
        body.addView(note);
        refreshWorldRows();
        updateWorldStatus();
    }

    /**
     * A Realm's ingredients: "What it changes: everything" folds open to one switch per group (Rhythm, Music, Echo...).
     * Off = the Realm leaves that group at your own settings.
     */
    private void addRealmIngredients(LinearLayout body, Worlds.World w) {
        TextView summary = new TextView(this);
        summary.setTextSize(13);
        summary.setPadding(dp(8), dp(4), 0, dp(4));
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(16), 0, 0, dp(4));
        box.setVisibility(View.GONE);
        Runnable update = () -> {
            List<String> left = new ArrayList<>();
            for (String[] g : Worlds.GROUPS) {
                if (!Worlds.uses(w.id, g[0])) {
                    left.add(g[1].replaceAll(" \\(.*\\)", ""));
                }
            }
            String what = left.isEmpty() ? getString(R.string.realm_changes_all)
                    : left.size() == Worlds.GROUPS.length ? getString(R.string.realm_changes_none)
                    : getString(R.string.realm_changes_but, String.join(", ", left));
            summary.setText((box.getVisibility() == View.VISIBLE ? "\u25BE " : "\u25B8 ") + what);
        };
        for (String[] g : Worlds.GROUPS) {
            CheckBox c = new CheckBox(this);
            c.setText(g[1]);
            c.setChecked(Worlds.uses(w.id, g[0]));
            c.setOnCheckedChangeListener((b, on) -> {
                Worlds.setUses(w.id, g[0], on);
                update.run();
            });
            box.addView(c);
        }
        summary.setOnClickListener(v -> {
            box.setVisibility(box.getVisibility() == View.VISIBLE ? View.GONE : View.VISIBLE);
            update.run();
        });
        update.run();
        body.addView(summary);
        body.addView(box);
    }

    /** Fills each world's dropdown with the current presets (they change when you save or import one). */
    private void refreshWorldRows() {
        List<String> presets = new ArrayList<>(PresetManager.builtInNames());
        presets.addAll(PresetManager.userNames(this));
        for (WorldRow row : worldRows) {
            row.presets = presets;
            List<String> items = new ArrayList<>();
            items.add(getString(R.string.world_off));
            items.addAll(presets);
            ArrayAdapter<String> adapter = new ArrayAdapter<>(
                    this, android.R.layout.simple_spinner_item, items);
            adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
            row.spinner.setAdapter(adapter);
            row.spinner.setSelection(presets.indexOf(Worlds.presetName(row.world.id)) + 1);
        }
    }

    private void updateWorldStatus() {
        if (worldStatus == null) {
            return;
        }
        String id = Worlds.currentWorld();
        String name = getString(R.string.worlds_yours);
        for (Worlds.World w : Worlds.ALL) {
            if (w.id.equals(id)) {
                name = w.title;
            }
        }
        worldStatus.setText(!Worlds.isEnabled() ? getString(R.string.worlds_off_status)
                : getString(R.string.worlds_now, name));
    }

    private void showSectionState(TextView header, View body, String title, boolean open) {
        body.setVisibility(open ? View.VISIBLE : View.GONE);
        header.setText(getString(open ? R.string.section_open : R.string.section_closed, title));
    }

    private void addAudioSection(LinearLayout parent) {
        LinearLayout body = addSection(parent, "audio", getString(R.string.section_audio), false);
        inputPicker = addDevicePicker(body, R.string.audio_input, true);
        outputPicker = addDevicePicker(body, R.string.audio_output, false);

        if (!AudioService.canSelectDevices()) {
            inputPicker.spinner.setEnabled(false);
            outputPicker.spinner.setEnabled(false);
        }
        micHint = new TextView(this);
        micHint.setTextSize(13);
        micHint.setPadding(0, dp(8), 0, 0);
        body.addView(micHint);
        updateMicHint();
        TextView note = new TextView(this);
        note.setText(AudioService.canSelectDevices()
                ? R.string.audio_note : R.string.audio_unsupported);
        note.setTextSize(13);
        note.setPadding(0, dp(12), 0, 0);
        body.addView(note);
    }

    private DevicePicker addDevicePicker(LinearLayout parent, int labelRes, boolean input) {
        TextView label = new TextView(this);
        label.setText(labelRes);
        label.setTextSize(16);
        label.setPadding(0, dp(16), 0, 0);
        parent.addView(label);

        Spinner spinner = new Spinner(this);
        parent.addView(spinner);
        DevicePicker picker = new DevicePicker(input, spinner);
        spinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parentView, View v, int position, long id) {
                String key = position == 0 || position > picker.devices.size()
                        ? AudioSettings.AUTOMATIC : picker.devices.get(position - 1).key;
                if (key.equals(picker.shownKey)) {
                    return;   // our own refresh, not a user choice
                }
                picker.shownKey = key;
                AudioSettings.setDeviceKey(MainActivity.this, picker.input, key);
                updateMicHint();
                if (AudioService.isRunning()) {
                    startForegroundService(new Intent(MainActivity.this, AudioService.class)
                            .setAction(AudioService.ACTION_RESTART));
                }
            }

            @Override
            public void onNothingSelected(AdapterView<?> parentView) { }
        });
        return picker;
    }

    /** Rebuilds both dropdowns from the devices connected right now. */
    private void refreshDevicePickers() {
        fillPicker(inputPicker);
        fillPicker(outputPicker);
        updateMicHint();
    }

    private void fillPicker(DevicePicker picker) {
        picker.devices = AudioDevices.list(this, picker.input);
        List<String> names = new ArrayList<>();
        names.add(getString(picker.input ? R.string.audio_automatic
                : picker.devices.isEmpty() ? R.string.audio_no_headphones
                : R.string.audio_output_automatic));
        for (AudioDevices.Device d : picker.devices) {
            names.add(d.label);
        }
        // A remembered device that isn't plugged in shows as Automatic, but stays remembered.
        String saved = AudioSettings.deviceKey(this, picker.input);
        int selected = 0;
        for (int i = 0; i < picker.devices.size(); i++) {
            if (picker.devices.get(i).key.equals(saved)) {
                selected = i + 1;
            }
        }
        picker.shownKey = selected == 0 ? AudioSettings.AUTOMATIC : saved;
        ArrayAdapter<String> adapter = new ArrayAdapter<>(
                this, android.R.layout.simple_spinner_item, names);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        picker.spinner.setAdapter(adapter);
        picker.spinner.setSelection(selected);
    }

    private void addAboutSection(LinearLayout parent) {
        LinearLayout body = addSection(parent, "about", getString(R.string.section_about), false);
        TextView text = new TextView(this);
        text.setTextSize(14);
        String source = getString(R.string.source_url);
        text.setText(source.isEmpty() ? getString(R.string.about_text)
                : getString(R.string.about_text_with_source, source));
        text.setPadding(0, 0, 0, dp(8));
        body.addView(text);
        TextView sensorLine = new TextView(this);
        sensorLine.setTextSize(12);
        sensorLine.setText(getString(R.string.sensors_line, SensorInput.describe(this)));
        sensorLine.setPadding(0, 0, 0, dp(8));
        body.addView(sensorLine);
        TextView feedback = new TextView(this);
        feedback.setTextSize(14);
        feedback.setAutoLinkMask(android.text.util.Linkify.EMAIL_ADDRESSES);
        feedback.setText(R.string.about_feedback);
        feedback.setPadding(0, 0, 0, dp(8));
        body.addView(feedback);
        LinearLayout row = newButtonRow(body);
        addButton(row, R.string.show_licenses, this::showLicenses);
        addButton(row, R.string.walk_show_again, this::showWalkthrough);
    }

    /** When the app was first installed and last updated (ms); equal on a fresh install. */
    private long[] installTimes() {
        try {
            android.content.pm.PackageInfo info = getPackageManager().getPackageInfo(getPackageName(), 0);
            return new long[]{info.firstInstallTime, info.lastUpdateTime};
        } catch (PackageManager.NameNotFoundException e) {
            return new long[]{0, 1};
        }
    }

    private void showWalkthrough() {
        UiSettings.setWalkthroughSeen(this);
        walkthrough = new Walkthrough(this, UiSettings.themeResource(UiSettings.theme(this)), new Walkthrough.Host() {
            @Override
            public boolean headphonesConnected() {
                return MainActivity.this.headphonesConnected();
            }

            @Override
            public boolean micAllowed() {
                return checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED;
            }

            @Override
            public void askForMic() {
                List<String> wanted = new ArrayList<>();
                wanted.add(Manifest.permission.RECORD_AUDIO);
                if (Build.VERSION.SDK_INT >= 33) {
                    wanted.add(Manifest.permission.POST_NOTIFICATIONS);
                }
                requestPermissions(wanted.toArray(new String[0]), REQ_MIC);
            }

            @Override
            public void start() {
                if (!AudioService.isRunning()) {
                    onStartStop();
                }
            }

            @Override
            public int dp(int v) {
                return MainActivity.this.dp(v);
            }
        });
        walkthrough.open();
    }

    /** Licence texts shipped inside the app (assets/licenses), as the GPL requires. */
    private void showLicenses() {
        String[][] docs = {
                {"Notice", "NOTICE.txt"},
                {"GNU GPL v3", "GPL-3.0.txt"},
                {"RjDj library (rjlib)", "rjlib-LICENSE.txt"},
                {"Pure Data (BSD)", "pure-data-LICENSE.txt"},
                {"PdParty helper objects (BSD)", "pdparty-LICENSE.txt"},
                {"Oboe and libpd (Apache 2.0)", "Apache-2.0.txt"},
        };
        String[] names = new String[docs.length];
        for (int i = 0; i < docs.length; i++) {
            names[i] = docs[i][0];
        }
        new AlertDialog.Builder(this)
                .setTitle(R.string.show_licenses)
                .setItems(names, (d, which) -> showAssetText(docs[which][0], "licenses/" + docs[which][1]))
                .setNegativeButton(R.string.close, null)
                .show();
    }

    private void showAssetText(String title, String assetPath) {
        String text;
        try (InputStream in = getAssets().open(assetPath)) {
            java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) {
                bytes.write(buf, 0, n);
            }
            text = new String(bytes.toByteArray(), StandardCharsets.UTF_8);
        } catch (IOException e) {
            text = getString(R.string.err_open_file);
        }
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(12);
        view.setTypeface(Typeface.MONOSPACE);
        view.setPadding(dp(16), dp(8), dp(16), dp(8));
        view.setTextIsSelectable(true);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(view);
        new AlertDialog.Builder(this)
                .setTitle(title)
                .setView(scroll)
                .setPositiveButton(R.string.close, null)
                .show();
    }

    private void addAppearanceSection(LinearLayout parent) {
        LinearLayout body = addSection(
                parent, "appearance", getString(R.string.section_appearance), false);
        int[] labels = {R.string.theme_light, R.string.theme_dark, R.string.theme_amoled};
        int current = UiSettings.theme(this);
        RadioGroup group = new RadioGroup(this);
        for (int i = 0; i < labels.length; i++) {
            int theme = i;   // THEME_LIGHT, THEME_DARK, THEME_AMOLED are 0, 1, 2
            RadioButton choice = new RadioButton(this);
            choice.setId(View.generateViewId());
            choice.setText(labels[i]);
            choice.setChecked(theme == current);
            choice.setOnClickListener(v -> {
                if (theme != UiSettings.theme(this)) {
                    UiSettings.setTheme(this, theme);
                    recreate();   // rebuilds the screen in the new theme; audio keeps running
                }
            });
            group.addView(choice);
        }
        body.addView(group);
    }

    private void addRow(LinearLayout parent, Param p) {
        addRow(parent, p, false);
    }

    /** {@code compact} makes a smaller, tighter row, for the mover settings under a slider. */
    private void addRow(LinearLayout parent, Param p, boolean compact) {
        if (p.toggle) {
            Switch sw = new Switch(this);
            sw.setText(p.label);
            sw.setTextSize(16);
            sw.setPadding(0, dp(16), 0, 0);
            sw.setChecked(ParamStore.get(p.id) >= 0.5f);   // right from the start (folded rows aren't refreshed)
            sw.setOnClickListener(v -> {
                ParamStore.set(p.id, sw.isChecked() ? 1f : 0f);
                updateMoverUi();   // a section's movers switch greys its mover controls in or out
            });
            parent.addView(sw);
            rows.add(new Row(p, null, null, sw, null));
            return;
        }
        if (p.choices != null) {
            addChoiceRow(parent, p, compact);
            return;
        }

        LinearLayout head = new LinearLayout(this);
        head.setOrientation(LinearLayout.HORIZONTAL);
        head.setGravity(Gravity.CENTER_VERTICAL);
        head.setPadding(0, dp(compact ? 4 : 16), 0, 0);

        TextView label = new TextView(this);
        label.setTextSize(compact ? 14 : 16);
        head.addView(label, new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        if (p.randomizable) {
            CheckBox lock = new CheckBox(this);
            lock.setText(R.string.lock);
            lock.setContentDescription(getString(R.string.lock) + ": " + p.label);
            lock.setChecked(ParamStore.isLocked(p.id));
            lock.setOnCheckedChangeListener((b, checked) -> ParamStore.setLocked(p.id, checked));
            head.addView(lock);
        }
        parent.addView(head);

        SeekBar slider = new SeekBar(this);
        slider.setMax(1000);
        slider.setContentDescription(p.label);
        float v0 = ParamStore.get(p.id);                  // right from the start (folded rows aren't refreshed)
        slider.setProgress(Math.round(p.toNorm(v0) * 1000f));
        label.setText(valueText(p, v0));
        parent.addView(slider);
        rows.add(new Row(p, label, slider, null, null));

        slider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar s, int progress, boolean fromUser) {
                if (fromUser) {  // ignore changes we make ourselves in refreshRows()
                    float value = p.toValue(progress / 1000f);
                    float room = ParamStore.budgetRoom(p);   // the glitch matrix: the shares can't pass 100%
                    if (value > room) {
                        value = room;
                        s.setProgress(Math.round(p.toNorm(value) * 1000));
                    }
                    ParamStore.set(p.id, value);
                    label.setText(valueText(p, value));
                    if (p.budget != null) {
                        updateBudgetLines();
                    }
                }
            }

            @Override public void onStartTrackingTouch(SeekBar s) { }
            @Override public void onStopTrackingTouch(SeekBar s) { }
        });
    }

    /** A label with a dropdown, for settings that pick one of a few named options. */
    private void addChoiceRow(LinearLayout parent, Param p, boolean compact) {
        TextView label = new TextView(this);
        label.setText(p.label);
        label.setTextSize(compact ? 14 : 16);
        label.setPadding(0, dp(compact ? 4 : 16), 0, 0);
        parent.addView(label);

        Spinner spinner = new Spinner(this);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(
                this, android.R.layout.simple_spinner_item, p.choices);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinner.setAdapter(adapter);
        // Select the stored choice BEFORE listening: a Spinner reports its first entry as "selected" when it is first
        // laid out, and a folded row isn't refreshed, so that once saved C major over the user's key and scale.
        spinner.setSelection(Math.round(ParamStore.get(p.id)), false);
        spinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parentView, View v, int position, long id) {
                if (position != Math.round(ParamStore.get(p.id))) {   // ignore refreshRows()
                    ParamStore.set(p.id, position);
                    updateMoverUi();
                }
            }

            @Override
            public void onNothingSelected(AdapterView<?> parentView) { }
        });
        parent.addView(spinner);
        rows.add(new Row(p, label, null, null, spinner));
    }

    /** The movement, speed and depth controls of one slider's mover, indented under it. */
    private void addMoverRows(LinearLayout parent, String sectionId, Param slider) {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(16), 0, 0, dp(4));
        addRow(box, Params.byId(Params.moverId(slider.id, "mv")), true);
        LinearLayout details = new LinearLayout(this);
        details.setOrientation(LinearLayout.VERTICAL);
        addRow(details, Params.byId(Params.moverId(slider.id, "mvspeed")), true);
        addRow(details, Params.byId(Params.moverId(slider.id, "mvdepth")), true);
        box.addView(details);
        parent.addView(box);
        moverUis.add(new MoverUi(sectionId, slider.id, box, details));
    }

    /** Greys out mover controls whose section has its movers off; hides speed and depth while a mover is Off. */
    private void updateMoverUi() {
        for (MoverUi m : moverUis) {
            boolean on = ParamStore.get(Params.moversSwitchId(m.sectionId)) >= 0.5f;
            boolean moving = Math.round(ParamStore.get(Params.moverId(m.paramId, "mv"))) != 0;
            m.details.setVisibility(moving ? View.VISIBLE : View.GONE);
            setTreeEnabled(m.box, on);
            m.box.setAlpha(on ? 1f : 0.4f);
        }
    }

    private static void setTreeEnabled(View view, boolean enabled) {
        view.setEnabled(enabled);
        if (view instanceof LinearLayout) {
            LinearLayout group = (LinearLayout) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                setTreeEnabled(group.getChildAt(i), enabled);
            }
        }
    }

    private String valueText(Param p, float value) {
        return getString(R.string.param_value, p.label, p.format(value));
    }

    /** Pull current values from the store into every control. */
    /** A small dot after a slider's label while a mover is pushing it around (checked once a second). */
    private static final String MOVER_DOT = "  \u25CF";

    private void updateMoverDots() {
        for (Row r : rows) {
            if (r.label == null || !r.label.isShown()) {
                continue;
            }
            boolean on = AudioService.isRunning() && Modulation.isMoving(r.param.id);
            CharSequence text = r.label.getText();
            boolean has = text.toString().endsWith(MOVER_DOT);
            if (on != has) {
                r.label.setText(valueText(r.param, ParamStore.get(r.param.id)) + (on ? MOVER_DOT : ""));
            }
        }
    }

    private void refreshRows() {
        for (Row r : rows) {
            View shown = r.slider != null ? r.slider : r.switchView != null ? r.switchView : r.spinner;
            if (shown != null && !shown.isShown()) {
                continue;   // folded away: refreshed when its section opens (saves work while worlds fade)
            }
            float v = ParamStore.get(r.param.id);
            if (r.switchView != null) {
                r.switchView.setChecked(v >= 0.5f);
            } else if (r.spinner != null) {
                r.spinner.setSelection(Math.round(v));
            } else {
                r.slider.setProgress(Math.round(r.param.toNorm(v) * 1000f));
                r.label.setText(valueText(r.param, v));
            }
        }
        updateMoverUi();
        updateBudgetLines();
        updateIntensityRow();
        undoButton.setEnabled(ParamStore.canUndo());
    }

    // ---- presets ----

    private void showPresets() {
        List<String> names = new ArrayList<>();
        List<Boolean> isUser = new ArrayList<>();
        for (String n : PresetManager.builtInNames()) {
            names.add(n);
            isUser.add(false);
        }
        for (String n : PresetManager.userNames(this)) {
            names.add(n);
            isUser.add(true);
        }
        String[] labels = new String[names.size()];
        for (int i = 0; i < labels.length; i++) {
            labels[i] = isUser.get(i)
                    ? getString(R.string.preset_saved_suffix, names.get(i)) : names.get(i);
        }

        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle(R.string.presets_title)
                .setItems(labels, (d, which) -> loadPreset(names.get(which), isUser.get(which)))
                .setNegativeButton(R.string.close, null)
                .create();
        dialog.show();
        dialog.getListView().setOnItemLongClickListener((parent, view, pos, id) -> {
            if (!isUser.get(pos)) {
                return false;
            }
            confirmDelete(names.get(pos));
            dialog.dismiss();
            return true;
        });
    }

    private void loadPreset(String name, boolean user) {
        Map<String, Float> values = user
                ? PresetManager.readUser(this, name) : PresetManager.builtIn(name);
        if (values == null) {
            toast(R.string.toast_read_failed, name);
            return;
        }
        ParamStore.applyPreset(values);
        refreshRows();
        toast(R.string.toast_loaded, name);
    }

    /** The one place settings are ever wiped: only when the user taps Reset and confirms. */
    private void confirmResetAll() {
        new AlertDialog.Builder(this)
                .setTitle(R.string.reset_title)
                .setMessage(R.string.reset_message)
                .setPositiveButton(R.string.reset_confirm, (d, w) -> {
                    Worlds.resetSettings();
                    ParamStore.resetAll();
                    ParamStore.save(this);
                    AudioSettings.reset(this);
                    SceneSettings.resetAll(this);
                    if (AudioService.isRunning()) {   // scene, devices and rate are chosen at start
                        startForegroundService(new Intent(this, AudioService.class)
                                .setAction(AudioService.ACTION_RESTART));
                    }
                    toast(R.string.toast_reset);
                    recreate();   // rebuild every control from the fresh settings
                })
                .setNegativeButton(R.string.cancel, null)
                .show();
    }

    private void confirmDelete(String name) {
        new AlertDialog.Builder(this)
                .setTitle(getString(R.string.delete_title, name))
                .setPositiveButton(R.string.delete, (d, w) -> {
                    PresetManager.delete(this, name);
                    refreshWorldRows();
                    toast(R.string.toast_deleted);
                })
                .setNegativeButton(R.string.cancel, null)
                .show();
    }

    private void showSave() {
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setText(R.string.default_preset_name);
        input.selectAll();
        new AlertDialog.Builder(this)
                .setTitle(R.string.save_title)
                .setView(input)
                .setPositiveButton(R.string.save, (d, w) -> {
                    try {
                        String used = PresetManager.save(
                                this, input.getText().toString(), ParamStore.snapshot());
                        toast(R.string.toast_saved, used);
                        refreshWorldRows();
                    } catch (IOException e) {
                        Toast.makeText(this, e.getMessage(), Toast.LENGTH_SHORT).show();
                    }
                })
                .setNegativeButton(R.string.cancel, null)
                .show();
    }

    /** Asks for the preset's name first: it becomes both the file name and the name shown after importing. */
    private void startExport() {
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setText(R.string.default_preset_name);
        input.selectAll();
        new AlertDialog.Builder(this)
                .setTitle(R.string.export_title)
                .setView(input)
                .setPositiveButton(R.string.export, (d, w) -> {
                    exportName = PresetManager.sanitize(input.getText().toString());
                    Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT)
                            .addCategory(Intent.CATEGORY_OPENABLE)
                            .setType("application/json")
                            .putExtra(Intent.EXTRA_TITLE, exportName + ".json");
                    startActivityForResult(intent, REQ_EXPORT);
                })
                .setNegativeButton(R.string.cancel, null)
                .show();
    }

    private void startImport() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE)
                .setType("*/*");
        startActivityForResult(intent, REQ_IMPORT);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (resultCode != RESULT_OK || data == null || data.getData() == null) {
            return;
        }
        Uri uri = data.getData();
        if (requestCode == REQ_EXPORT) {
            exportTo(uri);
        } else if (requestCode == REQ_IMPORT) {
            importFrom(uri);
        } else if (requestCode == REQ_IMPORT_SCENE) {
            importSceneFrom(uri);
        } else if (requestCode == REQ_IMPORT_SCENE_FOLDER) {
            importSceneFolderFrom(uri);
        }
    }

    private void exportTo(Uri uri) {
        try (OutputStream out = getContentResolver().openOutputStream(uri)) {
            if (out == null) {
                throw new IOException(getString(R.string.err_open_file));
            }
            out.write(PresetManager.toJson(exportName, ParamStore.snapshot())
                    .getBytes(StandardCharsets.UTF_8));
            toast(R.string.toast_exported);
        } catch (IOException | RuntimeException e) {
            toast(R.string.toast_export_failed, e.getMessage());
        }
    }

    private void importFrom(Uri uri) {
        try (InputStream in = getContentResolver().openInputStream(uri)) {
            if (in == null) {
                throw new IOException(getString(R.string.err_open_file));
            }
            PresetManager.Preset preset = PresetManager.parse(PresetManager.readAll(in));
            String name = PresetManager.isBuiltInName(PresetManager.sanitize(preset.name))
                    ? getString(R.string.imported_name, preset.name) : preset.name;
            String used = PresetManager.save(this, PresetManager.uniqueName(this, name), preset.values);
            ParamStore.applyPreset(preset.values);
            refreshRows();
            toast(R.string.toast_imported, used);
            refreshWorldRows();
        } catch (IOException | JSONException | RuntimeException e) {
            toast(R.string.toast_import_failed, e.getMessage());
        }
    }

    // ---- scenes ----

    private void updateSceneUi() {
        SceneLibrary.Scene scene = SceneSettings.current(this);
        sceneLabel.setText(getString(R.string.scene_current,
                scene != null ? scene.name : getString(R.string.scene_built_in)));
        // a scene replaces the built-in sound: its tabs say so instead of showing controls that do nothing
        for (int t : new int[]{TAB_SOUND, TAB_MUSIC, TAB_REALMS}) {
            tabBodies[t].setVisibility(scene != null ? View.GONE : View.VISIBLE);
            tabNotices[t].setVisibility(scene != null ? View.VISIBLE : View.GONE);
        }
        scenePad.setScene(scene);
        // With no scene the pad is an XY controller for the effects' movers (on the Sound tab); with one, the
        // scene's own pad (on the Scenes tab).
        LinearLayout slot = scene != null ? scenePadSlot : xyPadSlot;
        if (scenePad.getParent() != slot) {
            if (scenePad.getParent() != null) {
                ((android.view.ViewGroup) scenePad.getParent()).removeView(scenePad);
                ((android.view.ViewGroup) padHint.getParent()).removeView(padHint);
            }
            LinearLayout.LayoutParams padParams = new LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
            padParams.topMargin = dp(8);
            slot.addView(scenePad, padParams);
            slot.addView(padHint);
        }
        padHint.setVisibility(scene != null ? View.GONE : View.VISIBLE);
        sceneLevels.setVisibility(scene != null ? View.VISIBLE : View.GONE);
    }

    private void sendSceneLevelsIfRunning() {
        if (AudioService.isRunning() && SceneSettings.current(this) != null) {
            AudioService.sendSceneLevels(this);
        }
    }

    /** A 0-100% slider with a live label; {@code onChange} gets a fraction from 0 to 1. */
    private void addLevelSlider(LinearLayout parent, int labelRes, float initial,
                                java.util.function.Consumer<Float> onChange) {
        TextView label = new TextView(this);
        label.setPadding(0, dp(8), 0, 0);
        label.setText(getString(labelRes, Math.round(initial * 100)));
        SeekBar bar = new SeekBar(this);
        bar.setMax(100);
        bar.setProgress(Math.round(initial * 100));
        bar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar b, int progress, boolean fromUser) {
                label.setText(getString(labelRes, progress));
                if (fromUser) {
                    onChange.accept(progress / 100f);
                }
            }

            @Override
            public void onStartTrackingTouch(SeekBar b) { }

            @Override
            public void onStopTrackingTouch(SeekBar b) { }
        });
        parent.addView(label);
        parent.addView(bar);
    }

    /** Passes a finger on the scene pad to the scene as an RjDj "#touch" message. */
    private void sendTouch(String type, int finger, int x, int y) {
        if (finger == 1 && !ScenePad.UP.equals(type)) {   // the first finger also drives the Pad X / Pad Y movers
            Modulation.onPad(x / (float) ScenePad.GRID, y / (float) ScenePad.GRID);
        }
        if (AudioService.isRunning() && SceneSettings.current(this) != null) {
            PdBase.sendMessage("#touch", type, (float) finger, (float) x, (float) y);
        }
    }

    private void showScenes() {
        List<SceneLibrary.Scene> scenes = SceneLibrary.list(SceneSettings.scenesDir(this));
        String[] labels = new String[scenes.size() + 1];
        labels[0] = getString(R.string.scene_built_in);
        for (int i = 0; i < scenes.size(); i++) {
            SceneLibrary.Scene sc = scenes.get(i);
            labels[i + 1] = sc.author.isEmpty() ? sc.name
                    : getString(R.string.scene_by_author, sc.name, sc.author);
        }
        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle(scenes.isEmpty() ? getString(R.string.scenes_none) : getString(R.string.scenes_title))
                .setItems(labels, (d, which) -> selectScene(
                        which == 0 ? SceneSettings.BUILT_IN : scenes.get(which - 1).dirName))
                .setNegativeButton(R.string.close, null)
                .create();
        dialog.show();
        dialog.getListView().setOnItemLongClickListener((parent, view, pos, id) -> {
            if (pos == 0) {
                return false;
            }
            confirmDeleteScene(scenes.get(pos - 1));
            dialog.dismiss();
            return true;
        });
    }

    private void selectScene(String dirName) {
        if (dirName.equals(SceneSettings.selected(this))) {
            return;
        }
        SceneSettings.select(this, dirName);
        updateSceneUi();
        if (AudioService.isRunning()) {
            // The patch is opened when the engine starts, so swap scenes by restarting it.
            startForegroundService(
                    new Intent(this, AudioService.class).setAction(AudioService.ACTION_RESTART));
        }
    }

    private void confirmDeleteScene(SceneLibrary.Scene scene) {
        new AlertDialog.Builder(this)
                .setTitle(getString(R.string.delete_scene_title, scene.name))
                .setPositiveButton(R.string.delete, (d, w) -> {
                    boolean wasSelected = scene.dirName.equals(SceneSettings.selected(this));
                    if (wasSelected) {
                        selectScene(SceneSettings.BUILT_IN);   // stops using its files first
                    }
                    SceneLibrary.delete(scene);
                    toast(R.string.toast_scene_deleted);
                })
                .setNegativeButton(R.string.cancel, null)
                .show();
    }

    private void startImportScene() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE)
                .setType("*/*");
        startActivityForResult(intent, REQ_IMPORT_SCENE);
    }

    private void startImportSceneFolder() {
        startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE), REQ_IMPORT_SCENE_FOLDER);
    }

    /** Copies one scene folder, or every scene inside a folder of scenes, on a background thread. */
    private void importSceneFolderFrom(Uri tree) {
        toast(R.string.toast_scene_folder_importing);
        new Thread(() -> {
            File dir = SceneSettings.scenesDir(this);
            if (!dir.isDirectory() && !dir.mkdirs()) {
                runOnUiThread(() -> toast(R.string.toast_scene_import_failed, "Cannot create " + dir));
                return;
            }
            TreeImporter.Result r = TreeImporter.importTree(getContentResolver(), tree, dir);
            runOnUiThread(() -> {
                if (r.imported.isEmpty()) {
                    toast(R.string.toast_scene_none_found);
                } else if (r.imported.size() == 1 && r.failed.isEmpty()) {
                    toast(R.string.toast_scene_imported, r.imported.get(0).name);
                    selectScene(r.imported.get(0).dirName);
                } else {
                    // Don't guess which of many to start; the user picks from the list.
                    toast(R.string.toast_scenes_imported, r.imported.size(), r.failed.size());
                }
            });
        }, "scene-folder-import").start();
    }

    /** Unzips on a background thread (scenes can hold many samples), then offers to switch to it. */
    private void importSceneFrom(Uri uri) {
        String fileName = displayName(uri);
        toast(R.string.toast_scene_importing);
        new Thread(() -> {
            try (InputStream in = getContentResolver().openInputStream(uri)) {
                if (in == null) {
                    throw new IOException(getString(R.string.err_open_file));
                }
                File dir = SceneSettings.scenesDir(this);
                if (!dir.isDirectory() && !dir.mkdirs()) {
                    throw new IOException("Cannot create " + dir);
                }
                SceneLibrary.Scene scene = SceneLibrary.importZip(in, fileName, dir);
                runOnUiThread(() -> {
                    toast(R.string.toast_scene_imported, scene.name);
                    selectScene(scene.dirName);
                });
            } catch (IOException | RuntimeException e) {
                runOnUiThread(() -> toast(R.string.toast_scene_import_failed, e.getMessage()));
            }
        }, "scene-import").start();
    }

    /** The file name behind a picked document, e.g. "Eargasm.rj.zip"; empty if unknown. */
    private String displayName(Uri uri) {
        try (android.database.Cursor c = getContentResolver().query(
                uri, new String[]{android.provider.OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (c != null && c.moveToFirst() && !c.isNull(0)) {
                return c.getString(0);
            }
        } catch (RuntimeException e) {
            // Fall through.
        }
        return "";
    }

    private void toast(int messageRes, Object... args) {
        Toast.makeText(this, getString(messageRes, args), Toast.LENGTH_SHORT).show();
    }

    // ---- engine control ----

    private void onStartStop() {
        if (AudioService.isRunning()) {
            startService(new Intent(this, AudioService.class).setAction(AudioService.ACTION_STOP));
            return;
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            List<String> wanted = new ArrayList<>();
            wanted.add(Manifest.permission.RECORD_AUDIO);
            if (Build.VERSION.SDK_INT >= 33) {
                wanted.add(Manifest.permission.POST_NOTIFICATIONS);
            }
            requestPermissions(wanted.toArray(new String[0]), REQ_PERMISSIONS);
            return;
        }
        startAudio();
    }

    private void startAudio() {
        startForegroundService(
                new Intent(this, AudioService.class).setAction(AudioService.ACTION_START));
    }

    @Override
    @SuppressWarnings("NullableProblems")
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(requestCode, permissions, results);
        if (requestCode == REQ_MIC) {
            if (walkthrough != null) {
                walkthrough.refresh();
            }
            return;
        }
        if (requestCode != REQ_PERMISSIONS) {
            return;
        }
        for (int i = 0; i < permissions.length; i++) {
            if (Manifest.permission.RECORD_AUDIO.equals(permissions[i])
                    && results[i] == PackageManager.PERMISSION_GRANTED) {
                startAudio();
                return;
            }
        }
        status.setText(R.string.mic_permission_required);
    }

    /** Reflects engine state and headphone presence on screen. */
    private void updateUi() {
        boolean on = AudioService.isRunning();
        startStop.setText(on ? R.string.stop : R.string.start);
        updateStatus();
        warning.setVisibility(headphonesConnected() ? View.GONE : View.VISIBLE);
        updateNowLine();
    }

    /** The status line: stopped, running, paused for a call, an error, or the mic overloading (checked once a second). */
    private void updateStatus() {
        boolean on = AudioService.isRunning();
        String error = AudioService.getLastError();
        boolean overload = on && !AudioService.isPausedForCall() && AudioService.clips().warning(ClipWatch.IN);
        status.setTypeface(overload ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
        if (error != null && !on) {
            status.setText(error);
        } else if (overload) {
            status.setText(R.string.status_mic_overload);
        } else {
            int hz = AudioService.actualSampleRateHz();
            status.setText(!on ? getString(R.string.status_stopped)
                    : AudioService.isPausedForCall() ? getString(R.string.status_call)
                    : hz > 0 ? getString(R.string.status_running_rate, hz) : getString(R.string.status_running));
        }
    }

    private TextView diagText;
    private android.widget.ProgressBar diagLevel;

    /** Setup's Diagnostics: the mic and headphones really in use, the mic level and overloads in the last minute. */
    private void addDiagnosticsSection(LinearLayout parent) {
        addSection(parent, "diagnostics", getString(R.string.section_diag), false, body -> {
            diagText = new TextView(this);
            diagText.setTextSize(14);
            diagText.setPadding(0, dp(4), 0, dp(4));
            body.addView(diagText);
            diagLevel = new android.widget.ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
            diagLevel.setMax(80);   // -80 .. 0 dB
            body.addView(diagLevel, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(10)));
            TextView note = new TextView(this);
            note.setText(R.string.diag_note);
            note.setTextSize(13);
            note.setPadding(0, dp(8), 0, 0);
            body.addView(note);
            updateDiagnostics();
        });
    }

    private void updateDiagnostics() {
        if (diagText == null || !diagText.isShown()) {
            return;
        }
        boolean on = AudioService.isRunning();
        diagLevel.setVisibility(on ? View.VISIBLE : View.GONE);
        if (!on) {
            diagText.setText(R.string.diag_not_running);
            return;
        }
        List<String> lines = new ArrayList<>();
        String mic = AudioDevices.inputInUse(this);
        String asked = AudioService.inputAsked();
        lines.add(mic != null ? getString(R.string.diag_mic, mic)
                : getString(R.string.diag_mic_unknown, asked != null ? asked : getString(R.string.diag_automatic)));
        if (AudioService.callModeMic()) {
            lines.add("  " + getString(R.string.diag_call_mode));
        }
        int hz = AudioService.actualSampleRateHz();
        String out = AudioService.outputLabel() != null ? AudioService.outputLabel() : "?";
        lines.add(hz > 0 ? getString(R.string.diag_out_rate, out, hz) : getString(R.string.diag_out, out));
        int level = Math.round(Math.max(-80f, Math.min(0f, Modulation.micLevelDb())));
        int gate = Math.round(ParamStore.get("gate_thresh"));
        lines.add(gate > -80 ? getString(R.string.diag_level_gate, level, gate) : getString(R.string.diag_level, level));
        diagLevel.setProgress(level + 80);
        ClipWatch c = AudioService.clips();
        if (!c.hasReports()) {
            lines.add(getString(R.string.diag_scene));
        } else {
            int in = c.episodes(ClipWatch.IN), outs = c.episodes(ClipWatch.OUT);
            lines.add(getString(R.string.diag_clip_in, in));
            if (in > 0) {
                lines.add("  " + getString(R.string.diag_clip_in_help));
            }
            lines.add(getString(R.string.diag_clip_gain, c.episodes(ClipWatch.GAIN)));
            lines.add(getString(R.string.diag_handling, AudioService.handlingSkipsLastMinute()));
            lines.add(getString(R.string.diag_clip_out, outs));
            if (outs > 0) {
                lines.add("  " + getString(R.string.diag_clip_out_help));
            }
        }
        diagText.setText(String.join("\n", lines));
    }

    private boolean headphonesConnected() {
        for (AudioDeviceInfo d : audioManager.getDevices(AudioManager.GET_DEVICES_OUTPUTS)) {
            switch (d.getType()) {
                case AudioDeviceInfo.TYPE_WIRED_HEADPHONES:
                case AudioDeviceInfo.TYPE_WIRED_HEADSET:
                case AudioDeviceInfo.TYPE_USB_HEADSET:
                case AudioDeviceInfo.TYPE_BLUETOOTH_A2DP:
                    return true;
                default:
                    if (Build.VERSION.SDK_INT >= 31
                            && d.getType() == AudioDeviceInfo.TYPE_BLE_HEADSET) {
                        return true;
                    }
            }
        }
        return false;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }
}
