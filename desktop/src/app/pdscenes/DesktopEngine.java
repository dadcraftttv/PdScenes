// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import org.jaudiolibs.jnajack.Jack;
import org.jaudiolibs.jnajack.JackClient;
import org.jaudiolibs.jnajack.JackException;
import org.jaudiolibs.jnajack.JackOptions;
import org.jaudiolibs.jnajack.JackPort;
import org.jaudiolibs.jnajack.JackPortFlags;
import org.jaudiolibs.jnajack.JackPortType;
import org.jaudiolibs.jnajack.JackStatus;
import org.puredata.core.PdBase;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.FloatBuffer;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.EnumSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.function.Consumer;

/**
 * The desktop version's sound engine: the built-in patch in libpd, connected through PipeWire's JACK layer. The
 * mic and, if wanted, the computer's own sound (the monitor of an output, e.g. where a game plays) are mixed, each
 * at its level, into the one input the patch listens to. Its output goes to a virtual output of its own,
 * "PdScenes", which OBS records with an Audio Output Capture source, and if wanted also to the default output.
 *
 * <p>It never hears itself: "PdScenes" is never an input, and it doesn't play to the output the game sound is
 * taken from. Devices come and go (a USB interface reconnecting, EasyEffects restarting), so every connection is a
 * {@link Route}, checked every 2 s and made again when its device is back.
 */
final class DesktopEngine {

    static final String SINK = "pdscenes";               // the virtual output OBS records
    static final String CLIENT = "PdScenes Engine";       // (JACK names ports by device description: the sink is
                                                          //  "PdScenes", so the engine can't be)

    /** What to connect: device names, or a part of a device's name or description (null = the system default). */
    static final class Setup {
        String mic;               // null = default input; "none" = no mic
        boolean game;
        String gameOutput;        // "app:<name>" = that app's own sound, else an output's monitor (null = the default)
        boolean listen;           // also play to the default output
        float micLevel = 1, gameLevel = 1;
    }

    private final Consumer<String> say;   // messages for the person (lost or found devices, refusals)
    private Jack jack;
    private JackClient client;
    private int sinkModule = -1;
    private JackPort micL, micR, gameL, gameR, outL, outR;
    private float[] in, out;
    private int block;
    private volatile float micLevel = 1, gameLevel = 1;
    private volatile float peakIn, peakOut;
    private volatile int xruns;
    private volatile boolean closing;
    private final List<Route> routes = new ArrayList<>();
    private volatile int rate, frames;

    DesktopEngine(Consumer<String> say) {
        this.say = say;
    }

    /** A connection kept up while the engine runs. */
    private static final class Route {
        final String what, kind, portKind, pattern;   // kind: "sources"/"sinks"; portKind: capture, monitor, playback
        final boolean intoUs;
        String node;                                  // the device's name when last found
        boolean up;
        boolean refused;                              // (said once: not playing there, it would feed back)

        Route(String what, String kind, String portKind, String pattern, boolean intoUs) {
            this.what = what;
            this.kind = kind;
            this.portKind = portKind;
            this.pattern = pattern;
            this.intoUs = intoUs;
        }
    }

    // ---- start and stop ----

    /** Opens the patch and the connections. Throws with a plain-words reason. */
    void start(String patch, Setup setup) throws IOException {
        try {
            sinkModule = ensureSink();
        } catch (InterruptedException e) {
            throw new IOException("Interrupted");
        }
        try {
            jack = Jack.getInstance();
            client = jack.openClient(CLIENT, EnumSet.of(JackOptions.JackNoStartServer), EnumSet.noneOf(JackStatus.class));
        } catch (JackException | UnsatisfiedLinkError e) {
            unloadSink();
            throw new IOException("Couldn't reach PipeWire's JACK layer (is it started with pw-jack?): " + e);
        }
        try {
            rate = client.getSampleRate();
            frames = client.getBufferSize();
            block = PdBase.blockSize();
            in = new float[Math.max(frames, 8192)];
            out = new float[2 * in.length];
            PdBase.openAudio(1, 2, rate);
            if (PdBase.openPatch(patch) == 0) {
                throw new IOException("Couldn't open the patch " + patch);
            }
            micL = client.registerPort("mic_L", JackPortType.AUDIO, JackPortFlags.JackPortIsInput);
            micR = client.registerPort("mic_R", JackPortType.AUDIO, JackPortFlags.JackPortIsInput);
            gameL = client.registerPort("game_L", JackPortType.AUDIO, JackPortFlags.JackPortIsInput);
            gameR = client.registerPort("game_R", JackPortType.AUDIO, JackPortFlags.JackPortIsInput);
            outL = client.registerPort("out_L", JackPortType.AUDIO, JackPortFlags.JackPortIsOutput);
            outR = client.registerPort("out_R", JackPortType.AUDIO, JackPortFlags.JackPortIsOutput);
            client.setProcessCallback((c, n) -> process(n));
            client.setXrunCallback(c -> xruns++);
            client.setSampleRateCallback((c, r) -> {   // (PipeWire can switch the whole graph's rate)
                if (r != rate) {
                    rate = r;
                    PdBase.openAudio(1, 2, r);
                    say.accept("The audio now runs at " + r + " Hz.");
                }
            });
            client.activate();
        } catch (JackException e) {
            stop();
            throw new IOException("Couldn't set up the audio: " + e);
        }
        Route output = new Route("output", "sinks", "playback", SINK, false);
        synchronized (routes) {
            routes.add(output);
        }
        for (int tries = 0; !output.up && tries < 40; tries++) {   // (a sink made just now takes a moment to show)
            keepSafely(output);
            if (!output.up) {
                sleep(50);
            }
        }
        if (!output.up) {
            stop();
            throw new IOException("Couldn't connect to the PdScenes output.");
        }
        apply(setup);
        AudioService.running = true;
        Thread t = new Thread(() -> {
            while (!closing) {
                sleep(2000);
                List<Route> now;
                synchronized (routes) {
                    now = new ArrayList<>(routes);
                }
                for (Route r : now) {
                    boolean was = r.up;
                    keepSafely(r);
                    if (was != r.up && !closing && r.node != null && !r.refused) {
                        say.accept(r.up ? "Reconnected the " + r.what + " (" + r.node + ")."
                                : "Lost the " + r.what + " (" + r.node + "): waiting for it to come back.");
                    }
                }
            }
        }, "routes");
        t.setDaemon(true);
        t.start();
    }

    void stop() {
        closing = true;
        AudioService.running = false;
        if (client != null) {
            client.close();
            client = null;
        }
        PdBase.release();
        unloadSink();
    }

    int sampleRate() {
        return rate;
    }

    int framesPerCycle() {
        return frames;
    }

    // ---- what is connected (can change while running) ----

    /** Connects the mic, the game sound and the headphones as asked; what is no longer wanted is disconnected. */
    void apply(Setup s) {
        micLevel = s.micLevel;
        gameLevel = s.gameLevel;
        List<Route> wanted = new ArrayList<>();
        if (!"none".equals(s.mic)) {
            wanted.add(new Route("mic", "sources", "capture", s.mic, true));
        }
        if (s.game) {
            boolean app = s.gameOutput != null && s.gameOutput.startsWith(APP);
            wanted.add(app ? new Route("game sound", "apps", "output", s.gameOutput.substring(APP.length()), true)
                    : new Route("game sound", "sinks", "monitor", s.gameOutput, true));
        }
        if (s.listen) {
            wanted.add(new Route("headphones", "sinks", "playback", null, false));
        }
        synchronized (routes) {
            for (String what : new String[]{"mic", "game sound", "headphones"}) {
                Route old = route(what), now = null;
                for (Route r : wanted) {
                    if (r.what.equals(what)) {
                        now = r;
                    }
                }
                boolean same = old != null && now != null && java.util.Objects.equals(old.pattern, now.pattern);
                if (same) {
                    continue;
                }
                if (old != null) {
                    routes.remove(old);
                    disconnect(old);
                }
                if (now != null) {
                    routes.add(now);
                    keepSafely(now);
                    if (!now.up && !now.refused) {
                        say.accept(now.kind.equals("apps")
                                ? now.pattern + " isn't playing sound right now: PdScenes connects to it when it does."
                                : "Couldn't find " + wantedWords(now) + " yet: it connects when it shows up.");
                    }
                }
            }
        }
    }

    void setLevels(float mic, float game) {
        micLevel = mic;
        gameLevel = game;
    }

    /** The device a route is connected to now, or null. */
    String connected(String what) {
        synchronized (routes) {
            Route r = route(what);
            return r != null && r.up ? r.node : null;
        }
    }

    private Route route(String what) {
        for (Route r : routes) {
            if (r.what.equals(what)) {
                return r;
            }
        }
        return null;
    }

    private void keepSafely(Route r) {
        try {
            keep(r);
        } catch (JackException | RuntimeException e) {
            r.up = false;
        }
    }

    /** Finds the route's device and connects whatever isn't connected. Never hears our own output. */
    private void keep(Route r) throws JackException {
        if (client == null) {
            return;
        }
        boolean ours = r.what.equals("output");   // (only the output route may find our own sink)
        String[] dev = r.kind.equals("apps") ? (apps().contains(r.pattern) ? new String[]{r.pattern, r.pattern} : null)
                : ours ? findAny(r.kind, SINK) : find(r.kind, r.pattern != null ? r.pattern : defaultOf(r.kind));
        if (dev == null) {
            r.up = false;
            return;
        }
        if (r.intoUs && dev[0].equals(SINK)) {   // (find never offers it: belt and braces)
            r.up = false;
            return;
        }
        Route game;
        synchronized (routes) {
            game = route("game sound");
        }
        if (!r.intoUs && game != null && dev[0].equals(game.node)) {
            if (!r.refused) {
                say.accept("Not playing to " + dev[1] + ": the game sound is taken from it, so it would feed back. "
                        + "Give the game its own output and take the game sound from that.");
            }
            r.refused = true;
            r.node = dev[0];
            r.up = false;
            disconnect(r);
            return;
        }
        r.refused = false;
        if (r.node != null && !r.node.equals(dev[0])) {
            disconnect(r);   // (the default changed: leave the old device)
        }
        r.node = dev[0];
        String[] ports = jack.getPorts(client, "^" + rx(dev[1]) + ":" + r.portKind + "_", JackPortType.AUDIO,
                EnumSet.of(r.intoUs ? JackPortFlags.JackPortIsOutput : JackPortFlags.JackPortIsInput));
        if (ports == null || ports.length == 0) {
            r.up = false;
            return;
        }
        String me = client.getName() + ":";
        if (r.intoUs) {
            String base = r.what.equals("mic") ? "mic" : "game";
            link(ports[0], me + base + "_L", true);
            link(ports.length > 1 ? ports[1] : ports[0], me + base + "_R", true);   // (mono feeds both)
        } else {
            link(me + "out_L", ports[0], false);
            link(me + "out_R", ports.length > 1 ? ports[1] : ports[0], false);
        }
        r.up = true;
    }

    private void link(String from, String to, boolean toIsOurs) throws JackException {
        String[] now = jack.getAllConnections(client, toIsOurs ? to : from);
        if (now != null) {
            for (String p : now) {
                if (p.equals(toIsOurs ? from : to)) {
                    return;
                }
            }
        }
        jack.connect(client, from, to);
    }

    /** Cuts our side of a route: our two input ports, or our outputs' links to its device. */
    private void disconnect(Route r) {
        if (client == null) {
            return;
        }
        String me = client.getName() + ":";
        try {
            if (r.intoUs) {
                String base = r.what.equals("mic") ? "mic" : "game";
                for (String ours : new String[]{me + base + "_L", me + base + "_R"}) {
                    String[] now = jack.getAllConnections(client, ours);
                    for (String p : now == null ? new String[0] : now) {
                        jack.disconnect(client, p, ours);
                    }
                }
            } else if (r.node != null) {
                String desc = describe(r.kind, r.node);
                for (String ours : new String[]{me + "out_L", me + "out_R"}) {
                    String[] now = jack.getAllConnections(client, ours);
                    for (String p : now == null ? new String[0] : now) {
                        if (desc != null && p.startsWith(desc + ":")) {
                            jack.disconnect(client, ours, p);
                        }
                    }
                }
            }
        } catch (JackException | RuntimeException ignored) {
            // already gone
        }
        r.up = false;
    }

    // ---- the audio thread ----

    /** JACK's audio thread: mic and game sound, each at its level, into the patch's one input; its two outputs out. */
    private boolean process(int n) {
        FloatBuffer ml = micL.getFloatBuffer(), mr = micR.getFloatBuffer();
        FloatBuffer gl = gameL.getFloatBuffer(), gr = gameR.getFloatBuffer();
        FloatBuffer ol = outL.getFloatBuffer(), or = outR.getFloatBuffer();
        float mk = micLevel * 0.5f, gk = gameLevel * 0.5f, pin = peakIn, pout = peakOut;
        for (int i = 0; i < n; i++) {
            float v = (ml.get(i) + mr.get(i)) * mk + (gl.get(i) + gr.get(i)) * gk;
            in[i] = v;
            pin = Math.max(pin, Math.abs(v));
        }
        if (n % block == 0 && n <= in.length) {
            PdBase.process(n / block, in, out);
        } else {
            Arrays.fill(out, 0f);   // (PipeWire always uses whole Pd blocks; just in case)
        }
        for (int i = 0; i < n; i++) {
            float l = out[2 * i], r = out[2 * i + 1];
            ol.put(i, l);
            or.put(i, r);
            pout = Math.max(pout, Math.max(Math.abs(l), Math.abs(r)));
        }
        peakIn = pin;
        peakOut = pout;
        return true;
    }

    /** The loudest input and output since the last call, in dBFS, and the dropouts so far: {in, out, xruns}. */
    float[] meters() {
        float[] m = {(float) db(peakIn), (float) db(peakOut), xruns};
        peakIn = peakOut = 0;
        return m;
    }

    // ---- apps (a game's own sound, taken straight from it, like OBS's Application Audio Capture) ----

    static final String APP = "app:";

    /**
     * Apps playing sound now, by the name their ports carry ("Chromium", a game). Left out: PdScenes itself, OBS
     * (its monitoring can carry PdScenes's music: a loop), EasyEffects' filters and system helpers.
     */
    List<String> apps() {
        List<String> out = new ArrayList<>();
        if (client == null) {
            return out;
        }
        try {
            String[] ports = jack.getPorts(client, ":output_", JackPortType.AUDIO, EnumSet.of(JackPortFlags.JackPortIsOutput));
            String me = client.getName();
            for (String p : ports == null ? new String[0] : ports) {
                int c = p.lastIndexOf(':');
                String app = p.substring(0, c);
                String low = app.toLowerCase(Locale.ROOT);
                if (!app.equals(me) && !low.startsWith("pdscenes") && !low.contains("obs") && !low.startsWith("ee_")
                        && !low.startsWith("speech-dispatcher") && !low.startsWith("midi") && !out.contains(app)) {
                    out.add(app);
                }
            }
        } catch (JackException ignored) {
            // nothing listed
        }
        return out;
    }

    /**
     * A name to show for each app that plays sound: its stream's name plus where it comes from, when PipeWire knows
     * (a Flatpak's app id: Minecraft from Prism Launcher plays as "java (PrismLauncher)").
     */
    static Map<String, String> appLabels() {
        Map<String, String> out = new java.util.HashMap<>();
        try {
            // (pactl's JSON: pw-dump's repeats keys, which a strict JSON reader refuses)
            Process p = new ProcessBuilder("pactl", "--format=json", "list", "sink-inputs").start();
            String json = new String(p.getInputStream().readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
            p.waitFor();
            org.json.JSONArray all = new org.json.JSONArray(json);
            for (int i = 0; i < all.length(); i++) {
                org.json.JSONObject props = all.getJSONObject(i).optJSONObject("properties");
                if (props == null) {
                    continue;
                }
                String name = props.optString("node.name", null);
                String from = props.optString("pipewire.access.portal.app_id", "");
                if (from.isEmpty()) {
                    from = props.optString("application.name", "");
                }
                from = from.substring(from.lastIndexOf('.') + 1);
                if (name != null && !from.isEmpty() && !from.equalsIgnoreCase(name)) {
                    out.put(name, name + " (" + from + ")");
                }
            }
        } catch (IOException | InterruptedException | RuntimeException ignored) {
            // just the plain names
        }
        return out;
    }

    // ---- devices ----

    /**
     * Devices of a kind ("sources": mics, "sinks": outputs) as {name, description}. Monitors are not mics here, and
     * our own output is never offered.
     */
    static List<String[]> devices(String kind) {
        List<String[]> out = new ArrayList<>();
        for (String[] d : allDevices(kind)) {
            if (!d[0].startsWith(SINK)) {
                out.add(d);
            }
        }
        return out;
    }

    /** Our own output by its exact name (only for playing to it). */
    private static String[] findAny(String kind, String name) {
        for (String[] d : allDevices(kind)) {
            if (d[0].equals(name)) {
                return d;
            }
        }
        return null;
    }

    private static List<String[]> allDevices(String kind) {
        List<String[]> out = new ArrayList<>();
        try {
            String name = null;
            for (String line : run("pactl", "list", kind)) {
                String t = line.trim();
                if (t.startsWith("Name: ")) {
                    name = t.substring(6);
                } else if (t.startsWith("Description: ") && name != null) {
                    if (!(kind.equals("sources") && name.endsWith(".monitor"))) {
                        out.add(new String[]{name, t.substring(13)});
                    }
                    name = null;
                }
            }
        } catch (IOException | InterruptedException ignored) {
            // no PipeWire right now: nothing found
        }
        return out;
    }

    /** A device by its exact name, else the first whose name or description holds the pattern (any case). */
    static String[] find(String kind, String pattern) {
        if (pattern == null) {
            return null;
        }
        List<String[]> all = devices(kind);
        for (String[] d : all) {
            if (d[0].equals(pattern)) {
                return d;
            }
        }
        for (String[] d : all) {   // (a device back from a dropout gets ".3", ".4" added; a restart drops it again)
            if (base(d[0]).equals(base(pattern))) {
                return d;
            }
        }
        String p = pattern.toLowerCase(Locale.ROOT);
        for (String[] d : all) {
            if (d[0].toLowerCase(Locale.ROOT).contains(p) || d[1].toLowerCase(Locale.ROOT).contains(p)) {
                return d;
            }
        }
        return null;
    }

    /** A device name without the ".N" PipeWire adds when a device comes back under a name still in use. */
    static String base(String name) {
        return name.replaceFirst("\\.\\d+$", "");
    }

    private static String describe(String kind, String name) {
        for (String[] d : allDevices(kind)) {
            if (d[0].equals(name)) {
                return d[1];
            }
        }
        return null;
    }

    static String defaultOf(String kind) {
        try {
            List<String> out = run("pactl", kind.equals("sources") ? "get-default-source" : "get-default-sink");
            return out.isEmpty() ? null : out.get(0).trim();
        } catch (IOException | InterruptedException e) {
            return null;
        }
    }

    private static String wantedWords(Route r) {
        String which = r.what.equals("mic") ? "a mic" : r.what.equals("game sound") ? "the output to take the game sound from"
                : "your default output";
        return which + (r.pattern != null ? " matching \"" + r.pattern + "\"" : "");
    }

    /** The virtual output "PdScenes" (a PipeWire null sink): made if missing. Its module id, -1 if it was there. */
    private static int ensureSink() throws IOException, InterruptedException {
        for (String line : run("pactl", "list", "short", "sinks")) {
            String[] f = line.split("\t");
            if (f.length > 1 && f[1].equals(SINK)) {
                return -1;
            }
        }
        List<String> out = run("pactl", "load-module", "module-null-sink", "sink_name=" + SINK,
                "sink_properties=device.description=PdScenes");
        return out.isEmpty() ? -1 : Integer.parseInt(out.get(0).trim());
    }

    private void unloadSink() {
        if (sinkModule >= 0) {
            try {
                run("pactl", "unload-module", String.valueOf(sinkModule));
            } catch (IOException | InterruptedException ignored) {
                // PipeWire drops it on its next restart anyway
            }
            sinkModule = -1;
        }
    }

    private static List<String> run(String... cmd) throws IOException, InterruptedException {
        Process p = new ProcessBuilder(cmd).redirectErrorStream(true).start();
        List<String> lines = new ArrayList<>();
        try (BufferedReader r = new BufferedReader(new InputStreamReader(p.getInputStream()))) {
            for (String line; (line = r.readLine()) != null; ) {
                lines.add(line);
            }
        }
        if (p.waitFor() != 0) {
            throw new IOException(String.join(" ", cmd) + ": " + String.join(" ", lines));
        }
        return lines;
    }

    /** A device description as a literal in JACK's (POSIX) port regex. */
    private static String rx(String name) {
        return name.replaceAll("([\\\\.\\[\\]{}()*+?^$|])", "\\\\$1");
    }

    static void sleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private static double db(float v) {
        return v <= 1e-6f ? -120 : 20 * Math.log10(v);
    }
}
