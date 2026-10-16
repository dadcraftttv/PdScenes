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
 * --mic NODE         the mic (a PipeWire source, default: the system's default input; "none" = no mic)
 * --game [NODE]      also hear the computer's sound (default: the monitor of the default output)
 * --mic-level X      --game-level X   (default 1)
 * --listen           also play to the default output (to hear it yourself; refused together with --game)
 * --set id=value     a setting, as the phone app's ids (repeatable)
 * --seconds N        stop after N seconds (for tests)
 * </pre>
 */
public final class Engine {

    static final String SINK = "pdscenes";          // the virtual output OBS records
    static final String CLIENT = "PdScenes Engine";   // (the virtual output is "PdScenes")

    private final float[] in;
    private final float[] out;
    private final int block;
    private volatile float micLevel = 1, gameLevel = 1;
    private volatile float peakIn, peakOut;
    private volatile int xruns;
    private JackPort micL, micR, gameL, gameR, outL, outR;
    private boolean micMono, gameMono;

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
        String defaultSink = pactl("get-default-sink");
        if (mic == null) {
            mic = pactl("get-default-source");
        }
        if (wantGame && game == null) {
            game = defaultSink;   // its monitor
        }
        // never hear ourselves: our own output is not an input, and with the game sound on we don't play to the
        // output whose monitor we listen to
        if (SINK.equals(mic) || SINK.equals(game)) {
            fail("PdScenes can't listen to its own output (that would feed back).");
        }
        if (listen && wantGame && game.equals(defaultSink)) {
            fail("--listen plays to " + defaultSink + ", which the game sound is taken from: it would feed back. "
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
        for (Map.Entry<String, Float> s : sets.entrySet()) {
            PdBase.sendFloat(s.getKey(), s.getValue());
        }
        PdBase.computeAudio(true);
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            client.close();
            PdBase.closePatch(h);
            PdBase.release();
            unloadSink(sinkModule);
        }));
        Engine e = new Engine(Math.max(frames, 8192));
        e.micLevel = micLevel;
        e.gameLevel = gameLevel;
        e.start(jack, client, mic, wantGame ? game : null, listen ? defaultSink : null);
        System.out.printf(Locale.US, "PdScenes running at %d Hz, %d frames per cycle. Mic: %s. Game sound: %s. "
                        + "Output: \"PdScenes\"%s.%n", rate, frames, mic.equals("none") ? "off" : mic,
                wantGame ? "monitor of " + game : "off", listen ? " and " + defaultSink : "");
        long end = seconds < 0 ? Long.MAX_VALUE : System.currentTimeMillis() + (long) (seconds * 1000);
        while (System.currentTimeMillis() < end) {
            Thread.sleep(Math.min(2000, Math.max(1, end - System.currentTimeMillis())));
            System.out.printf(Locale.US, "in %5.1f dBFS   out %5.1f dBFS   xruns %d%n", db(e.peakIn), db(e.peakOut), e.xruns);
            e.peakIn = e.peakOut = 0;
        }
        System.exit(0);
    }

    private void start(Jack jack, JackClient c, String mic, String game, String listenSink) throws JackException {
        micL = c.registerPort("mic_L", JackPortType.AUDIO, JackPortFlags.JackPortIsInput);
        micR = c.registerPort("mic_R", JackPortType.AUDIO, JackPortFlags.JackPortIsInput);
        gameL = c.registerPort("game_L", JackPortType.AUDIO, JackPortFlags.JackPortIsInput);
        gameR = c.registerPort("game_R", JackPortType.AUDIO, JackPortFlags.JackPortIsInput);
        outL = c.registerPort("out_L", JackPortType.AUDIO, JackPortFlags.JackPortIsOutput);
        outR = c.registerPort("out_R", JackPortType.AUDIO, JackPortFlags.JackPortIsOutput);
        c.setProcessCallback((client, n) -> process(n));
        c.setXrunCallback(client -> xruns++);
        c.activate();
        if (!mic.equals("none")) {
            micMono = connectSource(jack, c, describe("sources", mic), "capture", "mic");
        }
        if (game != null) {
            gameMono = connectSource(jack, c, describe("sinks", game), "monitor", "game");
        }
        connectOut(jack, c, describe("sinks", SINK));
        if (listenSink != null) {
            connectOut(jack, c, describe("sinks", listenSink));
        }
    }

    /** Connects a node's ports of this kind (capture_FL.. or monitor_FL..) to our L/R inputs. True if mono. */
    private static boolean connectSource(Jack jack, JackClient c, String node, String kind, String ours)
            throws JackException {
        String[] ports = jack.getPorts(c, "^" + rx(node) + ":" + kind + "_", JackPortType.AUDIO,
                EnumSet.of(JackPortFlags.JackPortIsOutput));
        if (ports == null || ports.length == 0) {
            fail("Found no " + kind + " ports on \"" + node + "\". Inputs: see pw-link -o.");
        }
        jack.connect(c, ports[0], CLIENT + ":" + ours + "_L");
        jack.connect(c, ports.length > 1 ? ports[1] : ports[0], CLIENT + ":" + ours + "_R");
        return ports.length == 1;
    }

    private static void connectOut(Jack jack, JackClient c, String sink) throws JackException {
        String[] ports = null;
        for (int tries = 0; tries < 40 && (ports == null || ports.length < 2); tries++) {   // (a new sink's ports
            if (tries > 0) {                                                                //  take a moment to show)
                sleep(50);
            }
            ports = jack.getPorts(c, "^" + rx(sink) + ":playback_", JackPortType.AUDIO,
                    EnumSet.of(JackPortFlags.JackPortIsInput));
        }
        if (ports == null || ports.length < 2) {
            fail("Found no playback ports on \"" + sink + "\".");
        }
        jack.connect(c, CLIENT + ":out_L", ports[0]);
        jack.connect(c, CLIENT + ":out_R", ports[1]);
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

    /**
     * Under JACK, PipeWire names a device's ports by its description ("Easy Effects Source:capture_FL"), not by
     * the name pactl uses ("easyeffects_source"): finds the description of a sink or source.
     */
    private static String describe(String kind, String name) {
        try {
            String current = null;
            for (String line : run("pactl", "list", kind)) {
                String t = line.trim();
                if (t.startsWith("Name: ")) {
                    current = t.substring(6);
                } else if (t.startsWith("Description: ") && name.equals(current)) {
                    return t.substring(13);
                }
            }
        } catch (IOException | InterruptedException e) {
            fail("pactl list " + kind + " failed: " + e.getMessage());
        }
        fail("No " + kind.substring(0, kind.length() - 1) + " called \"" + name + "\" (see pactl list short " + kind + ").");
        return null;
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
