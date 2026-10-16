// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import java.awt.BorderLayout;
import java.awt.Component;
import java.awt.Dimension;
import java.awt.FlowLayout;
import java.awt.Font;
import java.awt.GridBagConstraints;
import java.awt.GridBagLayout;
import java.awt.Insets;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.function.Consumer;

import javax.swing.BorderFactory;
import javax.swing.Box;
import javax.swing.BoxLayout;
import javax.swing.DefaultListModel;
import javax.swing.JButton;
import javax.swing.JCheckBox;
import javax.swing.JComboBox;
import javax.swing.JComponent;
import javax.swing.JFileChooser;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JList;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JProgressBar;
import javax.swing.JScrollPane;
import javax.swing.JSlider;
import javax.swing.JTabbedPane;
import javax.swing.JTextArea;
import javax.swing.ListSelectionModel;
import javax.swing.SwingUtilities;
import javax.swing.Timer;
import javax.swing.UIManager;
import javax.swing.filechooser.FileNameExtensionFilter;

/**
 * The desktop window: the phone app's settings, built from the same list (Params), on the same tabs (Sound, Music,
 * Realms), plus presets (the phone's file format, both ways) and Setup (what it listens to and plays to). Rows
 * follow ParamStore a few times a second, so presets, Realms, the dice and Intensity's movers all show.
 */
final class DesktopWindow {

    private static final int STEPS = 1000;                 // slider resolution
    private static final long REFRESH_MS = 250;
    private static final int TEXT_WIDTH = 430;            // explanations wrap at this many pixels
    /**
     * Settings that only mean something on a phone: the pocket and handling hushes, notes following light and
     * stairs, the beat following your steps or playing only while walking. Kept at their defaults here (the beat on
     * its own clock, always playing) and out of sight; presets don't carry them.
     */
    static final java.util.Set<String> PHONE_ONLY = java.util.Set.of("pocket_hush", "pocket_guard", "handling_hush",
            "music_follow", "beat_follow", "beat_when");

    private final JFrame frame = new JFrame("PdScenes");
    private JTabbedPane tabs;
    private final JLabel status = new JLabel("Starting...");
    private final JLabel now = new JLabel(" ");
    private final JProgressBar meterIn = meter(), meterOut = meter();
    private final JTextArea log = new JTextArea(8, 40);
    private final List<Row> rows = new ArrayList<>();
    private final DefaultListModel<String> presetModel = new DefaultListModel<>();
    private final JList<String> presetList = new JList<>(presetModel);
    private final List<Runnable> realmRefresh = new ArrayList<>();
    private JComboBox<Device> micBox, gameBox;
    private JCheckBox gameOn, listenOn;
    private JSlider micLevel, gameLevel;
    private boolean quiet;                                 // (setting controls from code: don't act on it)

    /** One setting on screen. */
    private final class Row {
        final Param p;
        final JLabel label;
        final JComponent control;
        final JLabel value;

        Row(Param p, JLabel label, JComponent control, JLabel value) {
            this.p = p;
            this.label = label;
            this.control = control;
            this.value = value;
        }

        void refresh() {
            float v = ParamStore.get(p.id);
            if (control instanceof JSlider) {
                JSlider s = (JSlider) control;
                int pos = Math.round(p.toNorm(v) * STEPS);
                if (!s.getValueIsAdjusting() && s.getValue() != pos) {
                    s.setValue(pos);
                }
            } else if (control instanceof JCheckBox) {
                ((JCheckBox) control).setSelected(v >= 0.5f);
            } else if (control instanceof JComboBox) {
                JComboBox<?> c = (JComboBox<?>) control;
                int i = Math.round(p.clamp(v));
                if (c.getSelectedIndex() != i && i < c.getItemCount()) {
                    c.setSelectedIndex(i);
                }
            }
            if (value != null) {
                value.setText(p.format(v));
            }
            if (label != null) {
                String text = p.label + (Modulation.isMoving(p.id) ? " •" : "");   // (a dot while a mover pushes it)
                if (!text.equals(label.getText())) {
                    label.setText(text);
                }
            }
        }
    }

    private DesktopWindow() { }

    /** Builds and shows the window (on Swing's thread) and returns it. */
    static DesktopWindow open() throws Exception {
        DesktopWindow[] w = new DesktopWindow[1];
        SwingUtilities.invokeAndWait(() -> {
            try {
                UIManager.setLookAndFeel(UIManager.getSystemLookAndFeelClassName());
            } catch (Exception ignored) {
                // Swing's own look is fine too
            }
            UIManager.put("Slider.paintValue", Boolean.FALSE);   // (GTK draws the raw position over the knob)
            w[0] = new DesktopWindow();
            w[0].build();
        });
        return w[0];
    }

    // ---- messages ----

    /** A message for the person: shown at the top and kept in Setup's list. Any thread. */
    void say(String message) {
        System.out.println(message);
        SwingUtilities.invokeLater(() -> {
            status.setText(message);
            log.append(LocalTime.now().format(DateTimeFormatter.ofPattern("HH:mm:ss")) + "  " + message + "\n");
            log.setCaretPosition(log.getDocument().getLength());
        });
    }

    /** The engine couldn't start: say why, then close. */
    void fatal(String why) {
        SwingUtilities.invokeLater(() -> {
            JOptionPane.showMessageDialog(frame, why, "PdScenes couldn't start", JOptionPane.ERROR_MESSAGE);
            System.exit(2);
        });
    }

    /** First start: open Setup and ask for the mic. */
    void pickMic() {
        SwingUtilities.invokeLater(() -> {
            tabs.setSelectedIndex(4);
            say("Pick your mic in Setup, under Listening and playing (no mic is connected until you do).");
        });
    }

    /** The engine runs: fill in what depends on it and keep the screen in step. */
    void started() {
        SwingUtilities.invokeLater(() -> {
            refreshDevices();
            new Timer((int) REFRESH_MS, e -> refresh()).start();
        });
    }

    /** Draws each tab into prefix-N.png (for checking the layout without a screen grab). */
    void snapshot(String prefix) throws Exception {
        for (int t = 0; t < 5; t++) {
            int tab = t;
            SwingUtilities.invokeAndWait(() -> tabs.setSelectedIndex(tab));
            Thread.sleep(400);
            SwingUtilities.invokeAndWait(() -> {
                java.awt.image.BufferedImage img = new java.awt.image.BufferedImage(frame.getWidth(), frame.getHeight(),
                        java.awt.image.BufferedImage.TYPE_INT_RGB);
                frame.getRootPane().paint(img.getGraphics());
                try {
                    javax.imageio.ImageIO.write(img, "png", new File(prefix + "-" + tab + ".png"));
                } catch (IOException e) {
                    throw new RuntimeException(e);
                }
            });
        }
    }

    // ---- building ----

    private void build() {
        frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        JPanel top = new JPanel();
        top.setLayout(new BoxLayout(top, BoxLayout.Y_AXIS));
        top.setBorder(BorderFactory.createEmptyBorder(8, 10, 6, 10));
        status.setFont(status.getFont().deriveFont(Font.BOLD));
        top.add(left(status));
        top.add(left(now));
        JPanel meters = new JPanel(new GridBagLayout());
        GridBagConstraints g = new GridBagConstraints();
        g.insets = new Insets(2, 0, 2, 6);
        g.anchor = GridBagConstraints.WEST;
        g.gridy = 0;
        meters.add(new JLabel("In"), g);
        g.weightx = 1;
        g.fill = GridBagConstraints.HORIZONTAL;
        meters.add(meterIn, g);
        g.weightx = 0;
        g.fill = GridBagConstraints.NONE;
        meters.add(new JLabel("Out"), g);
        g.weightx = 1;
        g.fill = GridBagConstraints.HORIZONTAL;
        meters.add(meterOut, g);
        meters.setAlignmentX(Component.LEFT_ALIGNMENT);
        top.add(meters);
        Param intensity = Params.byId("intensity");
        if (intensity != null) {
            JPanel ip = new JPanel(new GridBagLayout());
            ip.setAlignmentX(Component.LEFT_ALIGNMENT);
            addRow(ip, intensity);
            top.add(ip);
        }

        tabs = new JTabbedPane();
        JPanel sound = page(), music = page(), realms = page(), presets = page(), setup = page();
        for (Params.Section section : Params.SECTIONS) {
            JPanel tab = "beat".equals(section.id) || "music".equals(section.id) || "mix".equals(section.id) ? music
                    : "behavior".equals(section.id) ? setup : sound;
            section(tab, section.title, section.openByDefault, body -> fillSection(body, section));
        }
        fillRealms(realms);
        fillPresets(presets);
        section(setup, "Listening and playing", true, this::fillAudio);
        section(setup, "Messages", true, body -> {
            log.setEditable(false);
            log.setLineWrap(true);
            log.setWrapStyleWord(true);
            body.add(new JScrollPane(log), full(body));
        });
        section(setup, "Start over", false, body -> {
            body.add(note("Reset everything puts every setting back to how a new install starts. Your saved "
                    + "presets and what the app listens to and plays to are kept."), full(body));
            JButton reset = new JButton("Reset everything...");
            reset.addActionListener(e -> resetAll());
            body.add(reset, full(body));
        });
        tabs.addTab("Sound", scroll(sound));
        tabs.addTab("Music", scroll(music));
        tabs.addTab("Realms", scroll(realms));
        tabs.addTab("Presets", scroll(presets));
        tabs.addTab("Setup", scroll(setup));

        frame.getContentPane().add(top, BorderLayout.NORTH);
        frame.getContentPane().add(tabs, BorderLayout.CENTER);
        frame.setSize(620, 860);
        frame.setLocationByPlatform(true);
        frame.setVisible(true);
    }

    private void fillSection(JPanel body, Params.Section section) {
        for (Param p : Params.ALL) {
            if (p.section.equals(section.id) && p.moverOf == null && !p.id.equals(Params.moversSwitchId(section.id))
                    && !p.id.equals("intensity") && !PHONE_ONLY.contains(p.id)) {
                addRow(body, p);
            }
        }
    }

    /** A setting as a row: a switch, a menu or a slider with its value. */
    private void addRow(JPanel body, Param p) {
        GridBagConstraints g = new GridBagConstraints();
        g.gridy = nextRow(body);
        g.gridx = 0;
        g.insets = new Insets(3, 2, 3, 6);
        g.anchor = GridBagConstraints.WEST;
        if (p.toggle) {
            JCheckBox box = new JCheckBox(p.label);
            box.addActionListener(e -> {
                if (!quiet) {
                    ParamStore.set(p.id, box.isSelected() ? 1f : 0f);
                }
            });
            g.gridwidth = 3;
            g.weightx = 1;
            body.add(box, g);
            Row r = new Row(p, null, box, null);
            rows.add(r);
            r.refresh();
            return;
        }
        JLabel label = new JLabel(p.label);
        label.setPreferredSize(new Dimension(230, label.getPreferredSize().height));
        label.setToolTipText(p.label);
        body.add(label, g);
        JComponent control;
        JLabel value = null;
        if (p.choices != null) {
            JComboBox<String> box = narrow(new JComboBox<>(p.choices));
            box.addActionListener(e -> {
                if (!quiet && box.getSelectedIndex() >= 0) {
                    ParamStore.set(p.id, box.getSelectedIndex());
                }
            });
            control = box;
        } else {
            JSlider s = new JSlider(0, STEPS, Math.round(p.toNorm(ParamStore.get(p.id)) * STEPS));
            value = new JLabel("0000000");
            value.setPreferredSize(new Dimension(80, value.getPreferredSize().height));
            JLabel shown = value;
            s.addChangeListener(e -> {
                if (quiet) {
                    return;
                }
                float v = p.clamp(p.toValue(s.getValue() / (float) STEPS));
                if (p.budget != null) {
                    v = Math.min(v, ParamStore.budgetRoom(p));   // the glitch matrix: shares can't pass 100%
                }
                if (Math.abs(v - ParamStore.get(p.id)) > 1e-6f) {
                    ParamStore.set(p.id, v);
                }
                shown.setText(p.format(ParamStore.get(p.id)));
            });
            control = s;
        }
        control.getAccessibleContext().setAccessibleName(p.label);
        g.gridx = 1;
        g.weightx = 1;
        g.fill = GridBagConstraints.HORIZONTAL;
        body.add(control, g);
        if (value != null) {
            g.gridx = 2;
            g.weightx = 0;
            g.fill = GridBagConstraints.NONE;
            body.add(value, g);
        }
        Row r = new Row(p, label, control, value);
        rows.add(r);
        r.refresh();
    }

    // ---- Realms ----

    private void fillRealms(JPanel page) {
        section(page, "Realms", true, body -> {
            body.add(note("Realms change the sound by themselves when the room changes: Tranquil when it's "
                    + "quiet, Flux when it's loud and lively, Ghost after midnight. Each plays a preset; your own settings "
                    + "come back when none fits. (Walking, a pocket and shaking need the phone.)"), full(body));
            JCheckBox on = new JCheckBox("Auto realms");
            on.setSelected(Worlds.isEnabled());
            on.addActionListener(e -> {
                if (on.isSelected() && JOptionPane.showConfirmDialog(frame, "Realms set the sliders from their own "
                        + "presets while they play (\"What it changes\" on the phone keeps a part). Your own settings "
                        + "come back when no Realm fits.", "Let Realms change your sound?", JOptionPane.OK_CANCEL_OPTION)
                        != JOptionPane.OK_OPTION) {
                    on.setSelected(false);
                    return;
                }
                Worlds.setEnabled(on.isSelected());
            });
            body.add(on, full(body));
            JCheckBox hold = new JCheckBox("Hold the Realm playing now");
            hold.addActionListener(e -> Worlds.setHeld(hold.isSelected()));
            body.add(hold, full(body));
            realmRefresh.add(() -> {
                on.setSelected(Worlds.isEnabled());
                hold.setSelected(Worlds.isHeld());
            });
            for (Worlds.World w : Worlds.ALL) {
                boolean here = !w.id.equals(WorldSelector.KINETIC) && !w.id.equals(WorldSelector.POCKET)
                        && !w.id.equals(WorldSelector.UNSTABLE);
                GridBagConstraints g = full(body);
                g.gridwidth = 1;
                g.weightx = 0;
                g.fill = GridBagConstraints.NONE;
                JLabel title = new JLabel("<html><b>" + w.title + "</b> - " + w.when + (here ? "" : " (phone only)") + "</html>");
                title.setPreferredSize(new Dimension(260, title.getPreferredSize().height));
                body.add(title, g);
                JComboBox<String> preset = narrow(new JComboBox<>());
                Runnable fill = () -> {
                    quiet = true;
                    preset.removeAllItems();
                    preset.addItem("Off");
                    for (String n : PresetManager.builtInNames()) {
                        preset.addItem(n);
                    }
                    for (String n : PresetManager.userNames(DesktopApp.context)) {
                        preset.addItem(n);
                    }
                    String chosen = Worlds.presetName(w.id);
                    preset.setSelectedItem(chosen == null || chosen.equals(Worlds.NONE) ? "Off" : chosen);
                    quiet = false;
                };
                fill.run();
                preset.addActionListener(e -> {
                    if (!quiet && preset.getSelectedItem() != null) {
                        String s = (String) preset.getSelectedItem();
                        Worlds.setPreset(w.id, s.equals("Off") ? Worlds.NONE : s);
                    }
                });
                realmRefresh.add(fill);
                g.gridx = 1;
                g.weightx = 1;
                g.fill = GridBagConstraints.HORIZONTAL;
                body.add(preset, g);
            }
        });
    }

    // ---- presets ----

    private void fillPresets(JPanel page) {
        section(page, "Presets", true, body -> {
            body.add(note("The same preset files as the phone app: export one there and import it here, "
                    + "or the other way round."), full(body));
            presetList.setSelectionMode(ListSelectionModel.SINGLE_SELECTION);
            presetList.setVisibleRowCount(14);
            presetList.addMouseListener(new java.awt.event.MouseAdapter() {
                @Override
                public void mouseClicked(java.awt.event.MouseEvent e) {
                    if (e.getClickCount() == 2) {
                        loadSelected();
                    }
                }
            });
            fillPresetList();
            body.add(new JScrollPane(presetList), full(body));
            JPanel buttons = new JPanel(new FlowLayout(FlowLayout.LEFT, 4, 2));
            buttons.add(button("Load", this::loadSelected));
            buttons.add(button("Save current as...", this::saveCurrent));
            buttons.add(button("Delete", this::deleteSelected));
            body.add(buttons, full(body));
            JPanel files = new JPanel(new FlowLayout(FlowLayout.LEFT, 4, 2));
            files.add(button("Import file...", this::importFile));
            files.add(button("Export current sound...", this::exportFile));
            body.add(files, full(body));
            JPanel dice = new JPanel(new FlowLayout(FlowLayout.LEFT, 4, 2));
            dice.add(button("Randomize", ParamStore::randomize));
            dice.add(button("Undo", () -> {
                if (ParamStore.canUndo()) {
                    ParamStore.undo();
                }
            }));
            body.add(dice, full(body));
        });
    }

    private static final String USER_MARK = "  (yours)";

    private void fillPresetList() {
        presetModel.clear();
        for (String n : PresetManager.userNames(DesktopApp.context)) {
            presetModel.addElement(n + USER_MARK);
        }
        for (String n : PresetManager.builtInNames()) {
            presetModel.addElement(n);
        }
        realmRefresh.forEach(Runnable::run);   // (the Realms' menus list the presets too)
    }

    private String selectedName(boolean[] user) {
        String s = presetList.getSelectedValue();
        if (s == null) {
            return null;
        }
        user[0] = s.endsWith(USER_MARK);
        return user[0] ? s.substring(0, s.length() - USER_MARK.length()) : s;
    }

    private void loadSelected() {
        boolean[] user = new boolean[1];
        String name = selectedName(user);
        if (name == null) {
            return;
        }
        Map<String, Float> values = user[0] ? PresetManager.readUser(DesktopApp.context, name) : PresetManager.builtIn(name);
        if (values == null) {
            say("Couldn't read the preset " + name + ".");
            return;
        }
        ParamStore.applyPreset(values);
        say("Loaded " + name + ".");
    }

    private void saveCurrent() {
        String name = JOptionPane.showInputDialog(frame, "Name for this sound:", "Save sound", JOptionPane.PLAIN_MESSAGE);
        if (name == null || name.isBlank()) {
            return;
        }
        String clean = PresetManager.sanitize(name);
        if (PresetManager.userNames(DesktopApp.context).stream().anyMatch(n -> n.equalsIgnoreCase(clean))
                && JOptionPane.showConfirmDialog(frame, "Replace your preset " + clean + "?", "Save sound",
                JOptionPane.OK_CANCEL_OPTION) != JOptionPane.OK_OPTION) {
            return;
        }
        try {
            String used = PresetManager.save(DesktopApp.context, clean, ParamStore.snapshot());
            fillPresetList();
            say("Saved " + used + ".");
        } catch (IOException e) {
            say("Couldn't save: " + e.getMessage());
        }
    }

    private void deleteSelected() {
        boolean[] user = new boolean[1];
        String name = selectedName(user);
        if (name == null || !user[0]) {
            say("Only your own presets can be deleted.");
            return;
        }
        if (JOptionPane.showConfirmDialog(frame, "Delete your preset " + name + "?", "Delete",
                JOptionPane.OK_CANCEL_OPTION) == JOptionPane.OK_OPTION) {
            PresetManager.delete(DesktopApp.context, name);
            fillPresetList();
            say("Deleted " + name + ".");
        }
    }

    private void importFile() {
        JFileChooser chooser = new JFileChooser();
        chooser.setFileFilter(new FileNameExtensionFilter("PdScenes presets (.json)", "json"));
        if (chooser.showOpenDialog(frame) != JFileChooser.APPROVE_OPTION) {
            return;
        }
        try (InputStream in = Files.newInputStream(chooser.getSelectedFile().toPath())) {
            PresetManager.Preset preset = PresetManager.parse(PresetManager.readAll(in));
            String name = PresetManager.isBuiltInName(PresetManager.sanitize(preset.name))
                    ? preset.name + " (imported)" : preset.name;
            String used = PresetManager.save(DesktopApp.context, PresetManager.uniqueName(DesktopApp.context, name),
                    preset.values);
            ParamStore.applyPreset(preset.values);
            fillPresetList();
            say("Imported " + used + " and loaded it.");
        } catch (IOException | RuntimeException e) {
            say("Couldn't import that file: " + e.getMessage());
        }
    }

    private void exportFile() {
        String name = JOptionPane.showInputDialog(frame, "Name for this sound:", "Export sound", JOptionPane.PLAIN_MESSAGE);
        if (name == null || name.isBlank()) {
            return;
        }
        String clean = PresetManager.sanitize(name);
        JFileChooser chooser = new JFileChooser();
        chooser.setSelectedFile(new File(clean + ".json"));
        if (chooser.showSaveDialog(frame) != JFileChooser.APPROVE_OPTION) {
            return;
        }
        File f = chooser.getSelectedFile();
        if (!f.getName().toLowerCase(Locale.ROOT).endsWith(".json")) {
            f = new File(f.getPath() + ".json");
        }
        if (f.exists() && JOptionPane.showConfirmDialog(frame, "Replace " + f.getName() + "?", "Export sound",
                JOptionPane.OK_CANCEL_OPTION) != JOptionPane.OK_OPTION) {
            return;
        }
        try {
            Files.write(f.toPath(), PresetManager.toJson(clean, ParamStore.snapshot()).getBytes(StandardCharsets.UTF_8));
            say("Exported to " + f.getPath() + ".");
        } catch (IOException | RuntimeException e) {
            say("Couldn't export: " + e.getMessage());
        }
    }

    // ---- Setup: what it listens to and plays to ----

    /** A device in a menu. */
    private static final class Device {
        final String name, title;

        Device(String name, String title) {
            this.name = name;
            this.title = title;
        }

        @Override
        public String toString() {
            return title;
        }
    }

    private void fillAudio(JPanel body) {
        body.add(note("PdScenes plays to its own output, <b>PdScenes</b>: in OBS add an <i>Audio Output "
                + "Capture</i> source and pick PdScenes. It never hears that output, so it can't feed back."), full(body));
        micBox = narrow(new JComboBox<>());
        micLevel = new JSlider(0, 200, 100);
        gameOn = new JCheckBox("Also hear the computer's sound (a game, music...)");
        gameBox = narrow(new JComboBox<>());
        gameLevel = new JSlider(0, 200, 100);
        listenOn = new JCheckBox("Also play to my headphones (the default output)");
        labeled(body, "Mic", micBox);
        labeled(body, "Mic level", micLevel);
        body.add(gameOn, full(body));
        labeled(body, "Taken from", gameBox);
        labeled(body, "Game level", gameLevel);
        body.add(listenOn, full(body));
        body.add(note("<b>Game sound without a loop:</b> PdScenes must never hear itself. If you listen on the same "
                + "output the game sound is taken from (here, or through OBS's audio monitoring), its music goes round "
                + "and round. Give the game its own output (a virtual sink) and take the game sound from that."), full(body));
        JButton refresh = new JButton("Look for devices again");
        refresh.addActionListener(e -> refreshDevices());
        body.add(refresh, full(body));
        Runnable changed = () -> {
            if (quiet) {
                return;
            }
            DesktopEngine.Setup s = DesktopApp.setup();
            Device mic = (Device) micBox.getSelectedItem(), game = (Device) gameBox.getSelectedItem();
            s.mic = mic == null ? s.mic : mic.name;
            s.game = gameOn.isSelected();
            s.gameOutput = game == null ? s.gameOutput : game.name;
            s.listen = listenOn.isSelected();
            s.micLevel = micLevel.getValue() / 100f;
            s.gameLevel = gameLevel.getValue() / 100f;
            DesktopApp.saveSetup(s);
            if (DesktopApp.engine != null) {
                DesktopApp.engine.apply(s);
            }
        };
        micBox.addActionListener(e -> changed.run());
        gameBox.addActionListener(e -> changed.run());
        gameOn.addActionListener(e -> changed.run());
        listenOn.addActionListener(e -> changed.run());
        micLevel.addChangeListener(e -> changed.run());
        gameLevel.addChangeListener(e -> changed.run());
    }

    /** Fills the device menus from what PipeWire has now, keeping the choices. */
    private void refreshDevices() {
        quiet = true;
        DesktopEngine.Setup s = DesktopApp.setup();
        fillDevices(micBox, "sources", "Default input", s.mic, true);
        fillDevices(gameBox, "sinks", "Default output", s.gameOutput, false);
        gameOn.setSelected(s.game);
        listenOn.setSelected(s.listen);
        micLevel.setValue(Math.round(s.micLevel * 100));
        gameLevel.setValue(Math.round(s.gameLevel * 100));
        quiet = false;
    }

    private static void fillDevices(JComboBox<Device> box, String kind, String defaultTitle, String chosen, boolean none) {
        box.removeAllItems();
        box.addItem(new Device(null, defaultTitle));
        if (none) {
            box.addItem(new Device("none", "No mic"));
        }
        Device pick = box.getItemAt(0);
        String[] match = chosen == null || "none".equals(chosen) ? null : DesktopEngine.find(kind, chosen);
        for (String[] d : DesktopEngine.devices(kind)) {
            Device dev = new Device(match != null && d[0].equals(match[0]) ? chosen : d[0], d[1]);
            box.addItem(dev);
            if (match != null && d[0].equals(match[0])) {
                pick = dev;
            }
        }
        if ("none".equals(chosen)) {
            pick = box.getItemAt(1);
        } else if (chosen != null && match == null) {   // (not here now: keep it, it connects when it shows up)
            pick = new Device(chosen, chosen + " (not connected)");
            box.addItem(pick);
        }
        box.setSelectedItem(pick);
    }

    // ---- reset ----

    private void resetAll() {
        if (JOptionPane.showConfirmDialog(frame, "Put every setting back to how a new install starts? Your saved "
                + "presets and your devices are kept.", "Reset everything", JOptionPane.OK_CANCEL_OPTION,
                JOptionPane.WARNING_MESSAGE) != JOptionPane.OK_OPTION) {
            return;
        }
        ParamStore.resetAll();
        Worlds.resetSettings();
        DesktopApp.applyDesktopDefaults();
        realmRefresh.forEach(Runnable::run);
        say("Everything is back to how a new install starts.");
    }

    // ---- keeping the screen in step ----

    private void refresh() {
        quiet = true;
        for (Row r : rows) {
            r.refresh();
        }
        quiet = false;
        if (DesktopApp.engine != null) {
            float[] m = DesktopApp.engine.meters();
            meterIn.setValue(Math.round(m[0]));
            meterIn.setString(String.format(Locale.US, "%.0f dB", m[0]));
            meterOut.setValue(Math.round(m[1]));
            meterOut.setString(String.format(Locale.US, "%.0f dB", m[1]) + (m[2] > 0 ? "  dropouts " + (int) m[2] : ""));
        }
        String world = Worlds.currentWorld();
        String realm = !Worlds.isEnabled() ? "your own settings" : world == null ? "your own settings (no Realm fits)"
                : title(world) + " realm" + (Worlds.isHeld() ? " (held)" : "");
        float bpm = DesktopApp.tempo();
        float mic = Modulation.micLevelDb();
        now.setText("Now: " + realm + " · " + (Worlds.isEnabled() ? Worlds.hearing()
                : mic <= -99 ? "nothing heard" : String.format(Locale.US, "room %.0f dB", mic))
                + (bpm > 0 ? String.format(Locale.US, " · %.0f BPM", bpm) : "")
                + (CalmBuild.level() > 0.01f ? " · building" : ""));
    }

    private static String title(String worldId) {
        for (Worlds.World w : Worlds.ALL) {
            if (w.id.equals(worldId)) {
                return w.title;
            }
        }
        return worldId;
    }

    // ---- small helpers ----

    private static JProgressBar meter() {
        JProgressBar b = new JProgressBar(-60, 0);
        b.setStringPainted(true);
        b.setString("");
        return b;
    }

    private static JPanel page() {
        JPanel p = new JPanel();
        p.setLayout(new BoxLayout(p, BoxLayout.Y_AXIS));
        p.setBorder(BorderFactory.createEmptyBorder(6, 8, 6, 8));
        return p;
    }

    private static JScrollPane scroll(JPanel page) {
        JPanel holder = new WidthTracking();
        holder.add(page, BorderLayout.NORTH);
        JScrollPane s = new JScrollPane(holder);
        s.getVerticalScrollBar().setUnitIncrement(24);
        s.setBorder(BorderFactory.createEmptyBorder());
        return s;
    }

    /** A page that is as wide as the window (rows shrink to fit instead of scrolling sideways). */
    private static final class WidthTracking extends JPanel implements javax.swing.Scrollable {
        WidthTracking() {
            super(new BorderLayout());
        }

        @Override public Dimension getPreferredScrollableViewportSize() { return getPreferredSize(); }
        @Override public int getScrollableUnitIncrement(java.awt.Rectangle r, int o, int d) { return 24; }
        @Override public int getScrollableBlockIncrement(java.awt.Rectangle r, int o, int d) { return r.height - 24; }
        @Override public boolean getScrollableTracksViewportWidth() { return true; }
        @Override public boolean getScrollableTracksViewportHeight() { return false; }
    }

    /** A section that folds open and shut, like the phone's. */
    private static void section(JPanel page, String title, boolean open, Consumer<JPanel> fill) {
        JPanel body = new JPanel(new GridBagLayout());
        body.setBorder(BorderFactory.createEmptyBorder(2, 14, 8, 2));
        fill.accept(body);
        JButton head = new JButton();
        head.setHorizontalAlignment(JButton.LEFT);
        head.setBorderPainted(false);
        head.setContentAreaFilled(false);
        head.setFont(head.getFont().deriveFont(Font.BOLD, head.getFont().getSize2D() + 1));
        Runnable show = () -> head.setText((body.isVisible() ? "▾  " : "▸  ") + title);
        body.setVisible(open);
        show.run();
        head.addActionListener(e -> {
            body.setVisible(!body.isVisible());
            show.run();
            page.revalidate();
        });
        head.setAlignmentX(Component.LEFT_ALIGNMENT);
        body.setAlignmentX(Component.LEFT_ALIGNMENT);
        page.add(head);
        page.add(body);
        page.add(Box.createVerticalStrut(2));
    }

    /** The next row of a section's grid. */
    private static int nextRow(JPanel body) {
        Integer r = (Integer) body.getClientProperty("row");
        int n = r == null ? 0 : r;
        body.putClientProperty("row", n + 1);
        return n;
    }

    /** Constraints for a whole new row of a section. */
    private static GridBagConstraints full(JPanel body) {
        GridBagConstraints g = new GridBagConstraints();
        g.gridx = 0;
        g.gridy = nextRow(body);
        g.gridwidth = GridBagConstraints.REMAINDER;
        g.weightx = 1;
        g.fill = GridBagConstraints.HORIZONTAL;
        g.anchor = GridBagConstraints.WEST;
        g.insets = new Insets(3, 2, 3, 6);
        return g;
    }

    private static void labeled(JPanel body, String text, JComponent control) {
        GridBagConstraints g = full(body);
        g.gridwidth = 1;
        g.weightx = 0;
        g.fill = GridBagConstraints.NONE;
        JLabel l = new JLabel(text);
        l.setPreferredSize(new Dimension(110, l.getPreferredSize().height));
        body.add(l, g);
        g = (GridBagConstraints) g.clone();
        g.gridx = 1;
        g.gridwidth = GridBagConstraints.REMAINDER;
        g.weightx = 1;
        g.fill = GridBagConstraints.HORIZONTAL;
        body.add(control, g);
        control.getAccessibleContext().setAccessibleName(text);
    }

    /** An explanation that wraps to the window's width. */
    private static JLabel note(String html) {
        return new JLabel("<html><body style='width: " + TEXT_WIDTH + "px'>" + html + "</body></html>");
    }

    /** A menu that doesn't ask for the width of its longest entry (the window's width decides). */
    private static <T> JComboBox<T> narrow(JComboBox<T> box) {
        box.setPreferredSize(new Dimension(180, box.getPreferredSize().height));
        box.setMinimumSize(new Dimension(80, box.getMinimumSize().height));
        return box;
    }

    private static JComponent left(JComponent c) {
        c.setAlignmentX(Component.LEFT_ALIGNMENT);
        return c;
    }

    private static JButton button(String text, Runnable action) {
        JButton b = new JButton(text);
        b.addActionListener(e -> action.run());
        return b;
    }
}
