// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes.desktop;

import org.jaudiolibs.jnajack.Jack;
import org.jaudiolibs.jnajack.JackClient;
import org.jaudiolibs.jnajack.JackException;
import org.jaudiolibs.jnajack.JackOptions;
import org.jaudiolibs.jnajack.JackPort;
import org.jaudiolibs.jnajack.JackPortFlags;
import org.jaudiolibs.jnajack.JackPortType;
import org.jaudiolibs.jnajack.JackStatus;
import org.puredata.core.PdBase;
import org.puredata.core.PdReceiver;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.FloatBuffer;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * The desktop version's sound engine (stream mode, step 1: the proof). The built-in patch runs in libpd, fed by the
 * mic and, if wanted, the computer's own sound (a monitor of the speakers' output, e.g. a game), each with its own
 * level, mixed to the one input the patch listens to. Its output goes to a virtual output of its own, "PdScenes",
 * which OBS records with an Audio Output Capture source. That output is never offered as an input, and the
 * speakers it would loop through are refused while the game sound is on, so the app can never hear itself.
 *
 * <pre>
 * --mic NAME         the mic: a PipeWire source by name or part of its name or description, e.g. "AudioBox"
 *                    (default: the system's default input; "none" = no mic)
 * --game [NAME]      also hear the computer's sound: the monitor of this output (default: the default output)
 * --mic-level X      --game-level X   (default 1)
 * --listen           also play to the default output (to hear it yourself; refused when the game sound is taken
 *                    from that same output)
 * --set id=value     a setting, as the phone app's ids (repeatable)
 * --seconds N        stop after N seconds (for tests)
 * </pre>
 * While it runs, lines typed into its terminal change things live: "mic 0.2", "game 0.5" (the input levels) or any
 * setting by its id, "gain 1" or "wet=0.3".
 */
public final class Engine {

    static final String SINK = "pdscenes";          // the virtual output OBS records
    /**
     * The phone's defaults that don't suit a desktop mic. The compressor (-30 dB, 4:1) evens out a phone mic, but a
     * desktop mic chain usually already arrives levelled (EasyEffects peaks at full scale), and squeezing it again
     * sounded overdriven (Samuel, Oct 16: the AudioBox directly with the compressor off "sounds amazing").
     */
    static final Map<String, Float> DESKTOP_DEFAULTS = Map.of("comp_thresh", 0f);
    static final String CLIENT = "PdScenes Engine";   // (the virtual output is "PdScenes")

    private final float[] in;
    private final float[] out;
    private final int block;
    private volatile float micLevel = 1, gameLevel = 1;
    private volatile float peakIn, peakOut;
    private volatile int xruns;
    private static volatile boolean closing;   // (shutting down: devices vanish, nothing to report)
    private JackPort micL, micR, gameL, gameR, outL, outR;

    private Engine(int maxFrames) {
        block = PdBase.blockSize();
        in = new float[maxFrames];
        out = new float[maxFrames * 2];
    }

    public static void main(String[] args) throws Exception {
        String patch = null, mic = null, game = null;
        boolean wantGame = false, listen = false;
        float micLevel = 1, gameLevel = 1;
        double seconds = -1;
        Map<String, Float> sets = new LinkedHashMap<>();
        for (int i = 0; i < args.length; i++) {
            String a = args[i];
            String next = i + 1 < args.length ? args[i + 1] : null;
            switch (a) {
                case "--patch": patch = next; i++; break;
                case "--mic": mic = next; i++; break;
                case "--game":
                    wantGame = true;
                    if (next != null && !next.startsWith("--")) { game = next; i++; }
                    break;
                case "--mic-level": micLevel = Float.parseFloat(next); i++; break;
                case "--game-level": gameLevel = Float.parseFloat(next); i++; break;
                case "--listen": listen = true; break;
                case "--seconds": seconds = Double.parseDouble(next); i++; break;
                case "--set": {
                    int eq = next.indexOf('=');
                    sets.put(next.substring(0, eq), Float.parseFloat(next.substring(eq + 1)));
                    i++;
                    break;
                }
                default: throw new IllegalArgumentException("Unknown option " + a);
            }
        }
        if (patch == null || !new File(patch).isFile()) {
            throw new IllegalArgumentException("No patch: " + patch);
        }
        // never hear ourselves: our own output is not an input, and with the game sound on we don't play to the
        // output whose monitor we listen to (checked again whenever a device comes back: see keep)
        if (listen && wantGame && game == null) {
            fail("--listen plays to your default output, which the game sound is taken from: it would feed back. "
                    + "Listen in OBS instead (its audio monitoring), or take the game sound from another output.");
        }
        int sinkModule = ensureSink();

        Jack jack = Jack.getInstance();
        EnumSet<JackStatus> status = EnumSet.noneOf(JackStatus.class);
        JackClient client = jack.openClient(CLIENT, EnumSet.of(JackOptions.JackNoStartServer), status);
        int rate = client.getSampleRate();
        int frames = client.getBufferSize();
        PdBase.setReceiver(new Printer());
        PdBase.openAudio(1, 2, rate);
        int h = PdBase.openPatch(patch);
        for (Map.Entry<String, Float> s : DESKTOP_DEFAULTS.entrySet()) {   // (before the user's own --set)
            PdBase.sendFloat(s.getKey(), s.getValue());
        }
        for (Map.Entry<String, Float> s : sets.entrySet()) {
            PdBase.sendFloat(s.getKey(), s.getValue());
        }
        PdBase.computeAudio(true);
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            closing = true;
            client.close();
            PdBase.closePatch(h);
            PdBase.release();
            unloadSink(sinkModule);
        }));
        Engine e = new Engine(Math.max(frames, 8192));
        e.micLevel = micLevel;
        e.gameLevel = gameLevel;
        try {
            e.start(jack, client, mic, wantGame, game, listen);
        } catch (JackException ex) {   // (JACK's threads would keep a half-started engine alive)
            fail("Couldn't connect the audio: " + ex);
        }
        System.out.printf(Locale.US, "PdScenes running at %d Hz, %d frames per cycle. Mic: %s. Game sound: %s. "
                        + "Output: \"PdScenes\"%s.%n", rate, frames, "none".equals(mic) ? "off" : e.nodeOf("mic"),
                wantGame ? "monitor of " + e.nodeOf("game") : "off", listen ? " and " + e.nodeOf("out") : "");
        startCommands(e);
        long end = seconds < 0 ? Long.MAX_VALUE : System.currentTimeMillis() + (long) (seconds * 1000);
        while (System.currentTimeMillis() < end) {
            Thread.sleep(Math.min(2000, Math.max(1, end - System.currentTimeMillis())));
            System.out.printf(Locale.US, "in %5.1f dBFS   out %5.1f dBFS   xruns %d%n", db(e.peakIn), db(e.peakOut), e.xruns);
            e.peakIn = e.peakOut = 0;
        }
        System.exit(0);
    }

    /** Typed commands: "mic X", "game X", or "id value" / "id=value" for a setting. */
    private static void startCommands(Engine e) {
        Thread t = new Thread(() -> {
            try (BufferedReader r = new BufferedReader(new InputStreamReader(System.in))) {
                for (String line; (line = r.readLine()) != null; ) {
                    String[] f = line.trim().split("[\\s=]+");
                    if (f.length != 2) {
                        if (!line.isBlank()) {
                            System.out.println("Type a name and a number, like: mic 0.2   game 0.5   gain 1   wet 0.3");
                        }
                        continue;
                    }
                    float v;
                    try {
                        v = Float.parseFloat(f[1]);
                    } catch (NumberFormatException ex) {
                        System.out.println("Not a number: " + f[1]);
                        continue;
                    }
                    switch (f[0]) {
                        case "mic": e.micLevel = v; break;
                        case "game": e.gameLevel = v; break;
                        default: PdBase.sendFloat(f[0], v);
                    }
                    System.out.println(f[0] + " = " + v);
                }
            } catch (IOException ignored) {
                // no terminal: fine
            }
        }, "commands");
        t.setDaemon(true);
        t.start();
    }

    /**
     * A connection kept up while the engine runs: a PipeWire device, found by its name or part of its name or
     * description (or the system's default when {@code pattern} is null), and our two ports. Devices come and go
     * (a USB interface reconnecting, EasyEffects restarting): every 2 s each route is checked and made again.
     */
    private static final class Route {
        final String what, kind, portKind, pattern;   // kind: "sources" or "sinks"; portKind: capture, monitor, playback
        final boolean intoUs;
        String node;                                  // the device's name when last found
        boolean up;

        Route(String what, String kind, String portKind, String pattern, boolean intoUs) {
            this.what = what;
            this.kind = kind;
            this.portKind = portKind;
            this.pattern = pattern;
            this.intoUs = intoUs;
        }
    }

    private final List<Route> routes = new ArrayList<>();
    private Route gameRoute, listenRoute;

    private void start(Jack jack, JackClient c, String mic, boolean game, String gamePattern, boolean listen)
            throws JackException {
        micL = c.registerPort("mic_L", JackPortType.AUDIO, JackPortFlags.JackPortIsInput);
        micR = c.registerPort("mic_R", JackPortType.AUDIO, JackPortFlags.JackPortIsInput);
        gameL = c.registerPort("game_L", JackPortType.AUDIO, JackPortFlags.JackPortIsInput);
        gameR = c.registerPort("game_R", JackPortType.AUDIO, JackPortFlags.JackPortIsInput);
        outL = c.registerPort("out_L", JackPortType.AUDIO, JackPortFlags.JackPortIsOutput);
        outR = c.registerPort("out_R", JackPortType.AUDIO, JackPortFlags.JackPortIsOutput);
        c.setProcessCallback((client, n) -> process(n));
        c.setXrunCallback(client -> xruns++);
        c.activate();
        routes.add(new Route("output", "sinks", "playback", SINK, false));
        if (!"none".equals(mic)) {
            routes.add(new Route("mic", "sources", "capture", mic, true));
        }
        if (game) {
            routes.add(gameRoute = new Route("game", "sinks", "monitor", gamePattern, true));
        }
        if (listen) {
            routes.add(listenRoute = new Route("out", "sinks", "playback", null, false));
        }
        for (Route r : routes) {
            for (int tries = 0; !r.up && tries < 40; tries++) {   // (a sink made just now takes a moment to show)
                keep(jack, c, r);
                if (!r.up) {
                    sleep(50);
                }
            }
            if (!r.up) {
                fail("Couldn't find " + describeWanted(r) + ". " + listChoices(r.kind));
            }
        }
        Thread t = new Thread(() -> {
            while (!closing) {
                sleep(2000);
                for (Route r : routes) {
                    boolean was = r.up;
                    try {
                        keep(jack, c, r);
                    } catch (JackException | RuntimeException ex) {
                        r.up = false;
                    }
                    if (was != r.up && !closing) {
                        System.out.println(r.up ? "Reconnected the " + r.what + " (" + r.node + ")."
                                : "Lost the " + r.what + " (" + r.node + "): waiting for it to come back.");
                    }
                }
            }
        }, "routes");
        t.setDaemon(true);
        t.start();
    }

    String micName() {
        return nodeOf("mic");
    }

    String nodeOf(String what) {
        for (Route r : routes) {
            if (r.what.equals(what)) {
                return r.node;
            }
        }
        return null;
    }

    /** Finds the route's device and connects whatever isn't connected. Never hears our own output. */
    private void keep(Jack jack, JackClient c, Route r) throws JackException {
        String[] dev = find(r.kind, r.pattern != null ? r.pattern : defaultOf(r.kind));
        if (dev == null) {
            r.up = false;
            return;
        }
        if (r.intoUs && dev[0].equals(SINK)) {
            fail("PdScenes can't listen to its own output (that would feed back).");
        }
        if (r == listenRoute && gameRoute != null && dev[0].equals(gameRoute.node)) {
            if (!dev[0].equals(r.node) || r.up) {
                System.out.println("Not playing to " + dev[0] + ": the game sound is taken from it (it would feed back).");
            }
            r.node = dev[0];
            r.up = false;
            return;
        }
        r.node = dev[0];
        String[] ports = jack.getPorts(c, "^" + rx(dev[1]) + ":" + r.portKind + "_", JackPortType.AUDIO,
                EnumSet.of(r.intoUs ? JackPortFlags.JackPortIsOutput : JackPortFlags.JackPortIsInput));
        if (ports == null || ports.length == 0) {
            r.up = false;
            return;
        }
        String me = c.getName() + ":";
        if (r.intoUs) {
            String base = r.what.equals("mic") ? "mic" : "game";
            link(jack, c, ports[0], me + base + "_L", true);
            link(jack, c, ports.length > 1 ? ports[1] : ports[0], me + base + "_R", true);   // (mono feeds both)
        } else {
            link(jack, c, me + "out_L", ports[0], false);
            link(jack, c, me + "out_R", ports.length > 1 ? ports[1] : ports[0], false);
        }
        r.up = true;
    }

    private static void link(Jack jack, JackClient c, String from, String to, boolean toIsOurs) throws JackException {
        String[] now = jack.getAllConnections(c, toIsOurs ? to : from);
        if (now != null) {
            for (String p : now) {
                if (p.equals(toIsOurs ? from : to)) {
                    return;
                }
            }
        }
        jack.connect(c, from, to);
    }

    /**
     * A device of this kind ("sources"/"sinks") by its exact name, else the first whose name or description holds
     * the pattern (any case). Monitors aren't sources here, and our own output is never offered. {name, description}.
     */
    private static String[] find(String kind, String pattern) {
        if (pattern == null) {
            return null;
        }
        List<String[]> all = devices(kind);
        for (String[] d : all) {
            if (d[0].equals(pattern)) {
                return d;
            }
        }
        String p = pattern.toLowerCase(Locale.ROOT);
        for (String[] d : all) {
            if (!d[0].equals(SINK) && (d[0].toLowerCase(Locale.ROOT).contains(p) || d[1].toLowerCase(Locale.ROOT).contains(p))) {
                return d;
            }
        }
        return null;
    }

    private static List<String[]> devices(String kind) {
        List<String[]> out = new ArrayList<>();
        try {
            String name = null;
            for (String line : run("pactl", "list", kind)) {
                String t = line.trim();
                if (t.startsWith("Name: ")) {
                    name = t.substring(6);
                } else if (t.startsWith("Description: ") && name != null) {
                    if (!(kind.equals("sources") && (name.endsWith(".monitor") || name.startsWith(SINK)))) {
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

    private static String defaultOf(String kind) {
        try {
            return pactl(kind.equals("sources") ? "get-default-source" : "get-default-sink");
        } catch (IOException | InterruptedException e) {
            return null;
        }
    }

    private static String describeWanted(Route r) {
        String which = r.what.equals("mic") ? "a mic" : r.what.equals("game") ? "an output to take the game sound from"
                : "an output to play to";
        return which + (r.pattern != null ? " matching \"" + r.pattern + "\"" : " (the system default)");
    }

    private static String listChoices(String kind) {
        StringBuilder b = new StringBuilder(kind.equals("sources") ? "Mics:" : "Outputs:");
        for (String[] d : devices(kind)) {
            if (!d[0].equals(SINK)) {
                b.append("\n  ").append(d[1]).append("   (").append(d[0]).append(")");
            }
        }
        return b.toString();
    }

    /** JACK's audio thread: mic and game sound, each at its level, into the patch's one input; its two outputs out. */
    private boolean process(int n) {
        FloatBuffer ml = micL.getFloatBuffer(), mr = micR.getFloatBuffer();
        FloatBuffer gl = gameL.getFloatBuffer(), gr = gameR.getFloatBuffer();
        FloatBuffer ol = outL.getFloatBuffer(), or = outR.getFloatBuffer();
        float mk = micLevel * 0.5f, gk = gameLevel * 0.5f, pin = peakIn, pout = peakOut;
        for (int i = 0; i < n; i++) {
            float v = (ml.get(i) + mr.get(i)) * mk + (gl.get(i) + gr.get(i)) * gk;   // (a mono source feeds both)
            in[i] = v;
            pin = Math.max(pin, Math.abs(v));
        }
        if (n % block == 0) {
            PdBase.process(n / block, in, out);
        } else {
            java.util.Arrays.fill(out, 0, 2 * n, 0f);   // (PipeWire always uses whole Pd blocks; just in case)
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

    /** The virtual output "PdScenes" (a PipeWire null sink): made if missing. Returns its module id, -1 if it was there. */
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

    private static void unloadSink(int module) {
        if (module >= 0) {
            try {
                run("pactl", "unload-module", String.valueOf(module));
            } catch (IOException | InterruptedException ignored) {
                // PipeWire drops it on its next restart anyway
            }
        }
    }

    private static String pactl(String what) throws IOException, InterruptedException {
        List<String> out = run("pactl", what);
        if (out.isEmpty()) {
            fail("pactl " + what + " gave nothing (is PipeWire running?)");
        }
        return out.get(0).trim();
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

    /** A node name as a literal in JACK's (POSIX) port regex. */
    private static String rx(String name) {
        return name.replaceAll("([\\\\.\\[\\]{}()*+?^$|])", "\\\\$1");
    }

    private static void sleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private static double db(float v) {
        return v <= 1e-6f ? -120 : 20 * Math.log10(v);
    }

    private static void fail(String why) {
        System.err.println(why);
        System.exit(2);
    }

    /** Pd's console (errors from the patch) to stderr. */
    private static final class Printer implements PdReceiver {
        private final StringBuilder line = new StringBuilder();

        @Override public void print(String s) {
            line.append(s);
            if (s.endsWith("\n")) {
                System.err.print("Pd: " + line);
                line.setLength(0);
            }
        }

        @Override public void receiveBang(String source) { }
        @Override public void receiveFloat(String source, float x) { }
        @Override public void receiveSymbol(String source, String symbol) { }
        @Override public void receiveList(String source, Object... args) { }
        @Override public void receiveMessage(String source, String symbol, Object... args) { }
    }
}
