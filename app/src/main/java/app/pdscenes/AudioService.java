// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.res.AssetManager;
import android.media.AudioManager;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;

import org.puredata.android.io.PdAudio;
import org.puredata.core.PdBase;
import org.puredata.core.PdReceiver;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Hosts libpd in a foreground service so the mic -> Pd -> headphones loop keeps
 * running with the screen off or the app in the background. Android only lets an
 * app keep using the microphone in the background from a foreground service of
 * type "microphone".
 */
public class AudioService extends Service {

    public static final String ACTION_START = "app.pdscenes.START";
    public static final String ACTION_STOP = "app.pdscenes.STOP";
    /** Stop and start again, e.g. after the user picks a different audio device. */
    public static final String ACTION_RESTART = "app.pdscenes.RESTART";

    private static final String TAG = "AudioService";
    private static final String CHANNEL_ID = "pd_audio";
    private static final int NOTIFICATION_ID = 1;
    private static final String SCENE_FILE = "test_scene.pd";

    private static volatile boolean running = false;
    private static volatile String lastError = null;
    /** Sample rate Pd is really running at (Android may not grant the one asked for); 0 if unknown. */
    private static volatile int actualRate = 0;

    /** Lets the screen react to start/stop/errors instead of polling. Called on the main thread. */
    public interface StateListener {
        void onStateChanged();
    }

    private static volatile StateListener stateListener;

    /** How often the movers update. The patch's glide smooths the steps between updates. */
    private static final long MOVER_INTERVAL_MS = 33;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private static final long CLOCK_CHECK_MS = 5000;

    private long lastMoverTick;
    private long lastClockCheck = -CLOCK_CHECK_MS;
    private int minuteOfDay;
    /** True while the built-in effects run (not a scene): then the automatic worlds may change the sliders. */
    private boolean autoWorlds;
    /** Last pocket state sent to the patch (it hushes the mic while pocketed) and last world logged. */
    private boolean pocketSent;
    private boolean micDownSent;
    private String worldLogged;
    private static final long HEARING_LOG_MS = 30_000;
    private long lastHearingLog;
    /** Harmony answers since the last "Hearing:" line (the patch sends each one on harm_deg). */
    private static final String HARMONY_RECEIVER = "harm_deg";
    /** The patch reports each chime it plays here (not arpeggio notes or replays); motif memory listens. */
    private static final String CHIME_NOTE = "chime_note";
    private static final String MOTIF_PLAY = "motif";
    /** The patch's tempo clock reports its tempo on each beat. */
    private static final String TEMPO = "tempo";
    private static volatile float tempoBpm;
    /** The found-sound kit: how many kicks, snares and hats have been caught (the patch keeps the latest 5 of each). */
    private static final String FS_CAUGHT = "fs_caught";
    private static final int[] kitCaught = new int[3];
    /** The last judged slice's levels (dBFS: all, lows, highs), logged with its catch. */
    private static final String FS_LEVELS = "fs_levels";
    /** Overload counts from the patch, once a second (diagnostics): the mic as it arrives, after Input gain, output. */
    private static final String CLIP_IN = "diag_clip_in", CLIP_GAIN = "diag_clip_gain", CLIP_OUT = "diag_clip_out";
    private static final ClipWatch clips = new ClipWatch();
    private int clipIn, clipGain;
    private long lastMicClipLog;
    /** The headphones being played to and the mic asked for (null = Automatic), for the diagnostics. */
    private static volatile String outputLabel, inputAsked;
    private static volatile boolean callModeMic;

    /** When the found sounds last skipped a handling noise (uptime ms), for the diagnostics' "last minute". */
    private static final java.util.ArrayDeque<Long> handlingSkips = new java.util.ArrayDeque<>();
    private float handlingSent;
    private float calmChimesSent;

    /** Sounds skipped as handling noise in the last minute. */
    static int handlingSkipsLastMinute() {
        long cutoff = SystemClock.uptimeMillis() - 60000;
        synchronized (handlingSkips) {
            while (!handlingSkips.isEmpty() && handlingSkips.peekFirst() < cutoff) {
                handlingSkips.removeFirst();
            }
            return handlingSkips.size();
        }
    }

    static ClipWatch clips() {
        return clips;
    }

    static String outputLabel() {
        return outputLabel;
    }

    static String inputAsked() {
        return inputAsked;
    }

    /** True while the mic is a Bluetooth headset's call-mode mic (mono, low quality). */
    static boolean callModeMic() {
        return callModeMic;
    }

    /** The found pad kept a held note (its pitch, MIDI). */
    private static final String FPAD_CAUGHT = "fpad_caught";
    private volatile String fsLevels = "";
    private final MotifMemory motif = new MotifMemory(new java.util.Random());
    private final NoteRegister noteRegister = new NoteRegister();
    /** Kicks, snares and hats in the found-sound kit now (0-5 each). */
    static int[] kit() {
        synchronized (kitCaught) {
            return new int[]{Math.min(kitCaught[0], 5), Math.min(kitCaught[1], 5), Math.min(kitCaught[2], 5),
                    kitCaught[0] + kitCaught[1] + kitCaught[2]};   // ...and how many were caught in all
        }
    }

    /** The tempo clock's tempo (beats a minute), 0 before the first beat. */
    static float tempo() {
        return tempoBpm;
    }

    private static final int[] SCALE_SIZES = {7, 7, 5, 5, 7, 7, 7, 6};   // the patch's scales, by music_scale
    private final java.util.concurrent.atomic.AtomicInteger harmonyNotes = new java.util.concurrent.atomic.AtomicInteger();
    private final Runnable moverTick = new Runnable() {
        @Override
        public void run() {
            long now = SystemClock.uptimeMillis();
            // Cap dt so a stalled main thread doesn't make the movers jump.
            double dt = Math.min((now - lastMoverTick) / 1000.0, 0.25);
            ParamStore.morphTick(dt);   // Randomize gliding to its new sound
            Modulation.tick(dt, (id, value) -> PdBase.sendFloat(id, value));
            if (now - lastCallCheck >= CALL_CHECK_MS) {
                lastCallCheck = now;
                checkForCall();
            }
            if (autoWorlds) {
                boolean pocket = PhoneContext.inPocket();
                if (pocket != pocketSent) {
                    pocketSent = pocket;
                    PdBase.sendFloat("pocket", pocket ? 1f : 0f);
                    logEvent(pocket ? "Phone went into a pocket" : "Phone came out of the pocket");
                }
                // handling noise (taps, grips, rubbing): the mic turned down while it lasts
                float handling = HandlingDetector.level();
                if (Math.abs(handling - handlingSent) > 0.02f || (handling == 0f) != (handlingSent == 0f)) {
                    handlingSent = handling < 0.01f ? 0f : handling;
                    PdBase.sendFloat("handling", handlingSent);
                }
                boolean down = pocket && PhoneContext.micDown();
                if (down != micDownSent) {
                    micDownSent = down;
                    PdBase.sendFloat("pocket_down", down ? 1f : 0f);
                    logEvent(down ? "In the pocket mic end down" : "Mic end no longer down in the pocket");
                }
                String world = Worlds.currentWorld();
                if (world != null ? !world.equals(worldLogged) : worldLogged != null) {
                    // the warp: up into a Realm, down back home, sideways from one Realm to another
                    float cue = world == null ? 0f : worldLogged == null ? 1f : 2f;
                    worldLogged = world;
                    logEvent("World: " + (world == null ? "own settings" : world) + " (" + Worlds.hearing() + ")");
                    PdBase.sendFloat("realm_cue", cue);   // (if on in Setup)
                }
                if (Worlds.isEnabled() && now - lastHearingLog >= HEARING_LOG_MS) {   // a trace of the room, to tune the thresholds by
                    lastHearingLog = now;
                    int answered = harmonyNotes.getAndSet(0);
                    logEvent("Hearing: " + Worlds.hearing() + (answered > 0 ? ", harmony " + answered : ""));
                }
                if (now - lastClockCheck > CLOCK_CHECK_MS) {   // the time of day changes slowly
                    minuteOfDay = Worlds.minuteOfDayNow();
                    lastClockCheck = now;
                }
                double nowS = SystemClock.elapsedRealtimeNanos() / 1e9;   // the sensors' clock
                Worlds.tick(dt, Modulation.micLevelDb(), StepDetector.walking(nowS),
                        PhoneContext.inPocket(), minuteOfDay, PhoneContext.secondsSinceShake(nowS));
                // calm builds: standing still in a calm room, the music grows a layer at a time (if switched on)
                boolean calm = ParamStore.get(CalmBuild.ID) >= 0.5f && ParamStore.get("music_on") >= 0.5f
                        && !StepDetector.walking(nowS) && !(Worlds.roomLoud() && Worlds.roomLively());
                if (CalmBuild.tick(dt, calm)) {
                    logEvent(CalmBuild.phase() == CalmBuild.Phase.RISING ? "Calm build starts" : "Calm build ends");
                }
                float chimes = CalmBuild.layer(CalmBuild.CHIMES);
                if (Math.abs(chimes - calmChimesSent) > 0.01f || (chimes == 0f) != (calmChimesSent == 0f)) {
                    calmChimesSent = chimes;
                    PdBase.sendFloat("calm_chimes", chimes);
                }
                int scale = Math.round(ParamStore.get("music_scale"));
                if (noteRegister.tick(dt, PhoneContext.brightness(), PhoneContext.inPocket(), PhoneContext.climb(),
                        SCALE_SIZES[Math.max(0, Math.min(SCALE_SIZES.length - 1, scale))],
                        ParamStore.get("music_follow") > 0.5f)) {
                    PdBase.sendFloat("music_register", noteRegister.steps());
                    PdBase.sendFloat("music_warm", noteRegister.warm() ? 1f : 0f);
                    logEvent("Notes moved " + noteRegister.steps() + " steps" + (noteRegister.warm() ? ", warm" : ""));
                }
                List<MotifMemory.Note> phrase = motif.poll(nowS, StepDetector.walking(nowS));
                if (phrase != null) {
                    logEvent("Motif comes back: " + phrase.size() + " notes");
                    for (MotifMemory.Note n : phrase) {
                        handler.postDelayed(() -> {
                            if (running) {
                                PdBase.sendList(MOTIF_PLAY, (float) n.degree, MotifMemory.VELOCITY);
                            }
                        }, Math.round(n.at * 1000));
                    }
                }
            }
            lastMoverTick = now;
            handler.postDelayed(this, MOVER_INTERVAL_MS);
        }
    };

    /** Pocket and world changes, kept in a small file so a whole outing can be read back afterwards
     *  ({@code adb shell run-as app.pdscenes cat files/events.log}); logcat on the phone only holds minutes. */
    private static final String EVENT_LOG = "events.log";
    private static final long EVENT_LOG_MAX_BYTES = 64 * 1024;

    /** Writes the event log off the main thread, so a slow flash write can't hold up the movers. */
    private final ExecutorService logWriter = Executors.newSingleThreadExecutor();
    private final SimpleDateFormat logTime = new SimpleDateFormat("MM-dd HH:mm:ss", Locale.US);   // main thread only

    private void logEvent(String what) {
        Log.i(TAG, what);
        String line = logTime.format(new Date()) + "  " + what + "\n";
        File dir = getFilesDir();
        logWriter.execute(() -> {
            try {
                File f = new File(dir, EVENT_LOG);
                if (f.length() > EVENT_LOG_MAX_BYTES) {
                    File old = new File(dir, EVENT_LOG + ".1");
                    old.delete();
                    f.renameTo(old);
                }
                try (FileOutputStream out = new FileOutputStream(f, true)) {
                    out.write(line.getBytes(StandardCharsets.UTF_8));
                }
            } catch (IOException e) {
                Log.w(TAG, "Could not write the event log", e);
            }
        });
    }

    // ---- phone calls and other apps' audio ----
    // The app never asks for audio focus (that would pause the user's music app on Start). Instead it watches:
    // during a phone call (or ringing) the output is silenced, and while another app plays it dips a little so
    // both can be heard (Samuel: duck only slightly, never drown the app's effects; always stop for a call).
    private static final long CALL_CHECK_MS = 500;
    /** How far the output dips while other audio plays: 0.3 = about 3 dB. */
    static final float OTHER_AUDIO_DUCK = 0.3f;
    private long lastCallCheck;
    private static volatile boolean pausedForCall;
    private int otherPlayers;
    private String lastPlayersReport = "";

    /** True while a phone call has silenced the output. */
    static boolean isPausedForCall() {
        return pausedForCall;
    }

    @SuppressWarnings("deprecation")
    private void checkForCall() {
        int mode = getSystemService(AudioManager.class).getMode();
        boolean call = mode == AudioManager.MODE_IN_CALL || mode == AudioManager.MODE_RINGTONE
                || mode == AudioManager.MODE_CALL_SCREENING || mode == AudioManager.MODE_CALL_REDIRECT
                || mode == AudioManager.MODE_COMMUNICATION_REDIRECT
                // a voice/video call app; but a Bluetooth mic puts the phone in this mode for us, so not then
                || (mode == AudioManager.MODE_IN_COMMUNICATION && !bluetoothMicRouted);
        if (call == pausedForCall) {
            return;
        }
        pausedForCall = call;
        if (!outputLost) {
            PdBase.computeAudio(!call);
        }
        logEvent(call ? "Paused for a phone call" : "Call over, playing again");
        notifyStateChanged();
    }

    private final AudioManager.AudioPlaybackCallback playbackWatcher = new AudioManager.AudioPlaybackCallback() {
        @Override
        public void onPlaybackConfigChanged(List<android.media.AudioPlaybackConfiguration> configs) {
            updateOtherAudio(configs);
        }
    };

    /**
     * Counts the players with an audible kind of sound. Android lists only players that are playing (paused ones
     * drop out) and hides their details from other apps (no uid, no device), so the app's own output is simply
     * one of them. Key clicks and calls don't count (calls are handled above). Seen on the Moto G: 1 player with
     * the app alone, 2 while Musicolet plays, 1 again when it pauses. Android 12+ only, as tested.
     */
    private void updateOtherAudio(List<android.media.AudioPlaybackConfiguration> configs) {
        if (!running || Build.VERSION.SDK_INT < 31) {
            return;
        }
        int playing = 0;
        StringBuilder seen = new StringBuilder();   // what Android reports, for tuning this on real phones
        for (android.media.AudioPlaybackConfiguration c : configs) {
            int usage = c.getAudioAttributes().getUsage();
            seen.append(" u").append(usage);
            if (usage != android.media.AudioAttributes.USAGE_ASSISTANCE_SONIFICATION
                    && usage != android.media.AudioAttributes.USAGE_VOICE_COMMUNICATION
                    && usage != android.media.AudioAttributes.USAGE_VOICE_COMMUNICATION_SIGNALLING) {
                playing++;
            }
        }
        String report = configs.size() + " players:" + seen;
        if (!report.equals(lastPlayersReport)) {
            lastPlayersReport = report;
            logEvent("Playback changed, " + report);
        }
        int others = Math.max(0, playing - 1);
        if ((others > 0) != (otherPlayers > 0)) {
            logEvent(others > 0 ? "Other audio playing (" + others + "), ducking a little" : "Other audio stopped");
        }
        otherPlayers = others;
        sendDuck();
    }

    private void sendDuck() {
        float cut = otherPlayers > 0 ? OTHER_AUDIO_DUCK : 0f;
        if (sceneRunning) {
            PdBase.sendMessage("#volume", "set", SceneSettings.volume(this) * (1f - cut));
        } else {
            PdBase.sendFloat("duck", cut);
        }
    }

    private int patchHandle = -1;
    private boolean sceneRunning;
    /** True while waiting (off the main thread) for a Bluetooth headset's call link before opening the audio. */
    private boolean starting;
    /** Bumped by every stop, so a Bluetooth wait that finishes after a stop is ignored. */
    private int startGeneration;
    private boolean bluetoothMicRouted = false;
    private SensorInput sensors;

    public static void setStateListener(StateListener listener) {
        stateListener = listener;
    }

    private static void notifyStateChanged() {
        StateListener l = stateListener;
        if (l != null) {
            l.onStateChanged();
        }
    }

    /**
     * PdAudio.setDevicesId only exists in newer pd-core releases than 1.2.1-rc6. It is called by
     * reflection so the app builds against either; when it is missing, Android picks the devices.
     */
    private static final java.lang.reflect.Method SET_DEVICES_ID = findSetDevicesId();

    private static java.lang.reflect.Method findSetDevicesId() {
        try {
            return PdAudio.class.getMethod("setDevicesId", int.class, int.class);
        } catch (NoSuchMethodException e) {
            return null;
        }
    }

    /** True if the audio library can be told which devices to use. */
    public static boolean canSelectDevices() {
        return SET_DEVICES_ID != null;
    }

    private static void selectDevices(int inputId, int outputId) {
        if (SET_DEVICES_ID == null) {
            return;
        }
        try {
            SET_DEVICES_ID.invoke(null, inputId, outputId);
        } catch (ReflectiveOperationException e) {
            Log.w(TAG, "Could not select audio devices", e);
        }
    }

    /** Tells a scene it is playing and at what volume, the way RjDj's player did. */
    static void sendSceneLevels(Context context) {
        PdBase.sendMessage("#transport", "play", 1f);
        PdBase.sendMessage("#volume", "set", SceneSettings.volume(context));
        PdBase.sendFloat("#micvolume", SceneSettings.micVolume(context));
    }

    static int actualSampleRateHz() {
        return actualRate;
    }

    public static boolean isRunning() {
        return running;
    }

    public static String getLastError() {
        return lastError;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent != null ? intent.getAction() : null;

        if (ACTION_STOP.equals(action)) {
            shutDown();
            return START_NOT_STICKY;
        }

        // Without the permission, startForeground() with a microphone type throws on Android 14+.
        if (checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            lastError = getString(R.string.err_no_mic_permission);
            notifyStateChanged();
            stopSelf();
            return START_NOT_STICKY;
        }

        enterForeground();

        if (ACTION_RESTART.equals(action)) {
            if (!running && !starting) {
                return START_NOT_STICKY;   // nothing to restart; the new choice applies on next Start
            }
            stopEngine();
        }
        if (!running && !starting) {
            try {
                startEngine();
                lastError = null;
            } catch (IOException | RuntimeException e) {
                Log.e(TAG, "Failed to start audio", e);
                lastError = getString(R.string.err_start_failed, e.getMessage());
                shutDown();
            }
        }
        return START_NOT_STICKY;
    }

    private void enterForeground() {
        NotificationManager nm = getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel(
                CHANNEL_ID, getString(R.string.notification_channel),
                NotificationManager.IMPORTANCE_LOW));

        Intent stop = new Intent(this, AudioService.class).setAction(ACTION_STOP);
        PendingIntent stopPi = PendingIntent.getService(
                this, 0, stop, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Intent open = new Intent(this, MainActivity.class);
        PendingIntent openPi = PendingIntent.getActivity(
                this, 1, open, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);

        Notification n = new Notification.Builder(this, CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_btn_speak_now)
                .setContentTitle(getString(R.string.notification_title))
                .setContentText(getString(R.string.notification_text))
                .setContentIntent(openPi)
                .addAction(new Notification.Action.Builder(null, getString(R.string.stop), stopPi).build())
                .setOngoing(true)
                .build();

        if (Build.VERSION.SDK_INT >= 30) {
            startForeground(NOTIFICATION_ID, n,
                    android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE
                            | android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK);
        } else {
            // API 28-29: types come from the manifest.
            startForeground(NOTIFICATION_ID, n);
        }
    }

    private void startEngine() throws IOException {
        AudioManager am = getSystemService(AudioManager.class);
        int sampleRate = parseInt(am.getProperty(AudioManager.PROPERTY_OUTPUT_SAMPLE_RATE), 48000);
        // Scenes were written for 22050 Hz; Android resamples to the hardware.
        boolean rjdjTiming = SceneSettings.current(this) != null && SceneSettings.rjdjTiming(this);
        if (rjdjTiming) {
            sampleRate = SceneSettings.RJDJ_SAMPLE_RATE;
        }

        File patchDir = new File(getFilesDir(), "patches");
        copyAssetsIfChanged("patches", patchDir);

        PdBase.addToSearchPath(patchDir.getAbsolutePath());
        // Where Android unpacks libfiddle_tilde.so and the other optional externals scenes use.
        PdBase.addToSearchPath(getApplicationInfo().nativeLibraryDir);

        // Scenes find the player's soundinput/soundoutput through "declare -path ../pd".
        File scenesDir = SceneSettings.scenesDir(this);
        File libDir = new File(scenesDir, SceneLibrary.LIB_DIR);
        copyAssetsIfChanged("scene_lib", libDir);
        PdBase.addToSearchPath(libDir.getAbsolutePath());                       // soundinput, accelerate, rj/...
        PdBase.addToSearchPath(new File(libDir, "rj").getAbsolutePath());       // RjDj library, by bare name
        SceneLibrary.Scene scene = SceneSettings.current(this);
        File patchFile = scene != null ? scene.mainPatch() : new File(patchDir, SCENE_FILE);

        // The patch reports the mic loudness about 30 times a second for the "Louder" movers.
        PdBase.setReceiver(new PdReceiver.Adapter() {
            @Override
            public void print(String s) {
                Log.i("Pd", s.trim());   // Pd's own console: object creation errors, scene prints
            }

            @Override
            public void receiveFloat(String source, float x) {
                if (FS_CAUGHT.equals(source)) {
                    int role = Math.round(x);
                    if (role >= 0 && role < 3) {
                        synchronized (kitCaught) {
                            kitCaught[role]++;
                        }
                        logEvent("Caught a " + new String[]{"kick", "snare", "hat"}[role] + " for the found-sound beat" + fsLevels);
                    }
                    if (role == 3) {
                        logEvent("Skipped a mic pop" + fsLevels);
                    }
                    if (role == 4) {
                        synchronized (handlingSkips) {
                            handlingSkips.addLast(SystemClock.uptimeMillis());
                        }
                        logEvent("Skipped a handling noise (a tap or grip on the phone)" + fsLevels);
                    }
                    return;
                }
                if (FPAD_CAUGHT.equals(source)) {
                    String[] names = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"};
                    int midi = Math.round(x);
                    logEvent("Kept a held note for the found pad (" + names[((midi % 12) + 12) % 12] + (midi / 12 - 1) + ")");
                    return;
                }
                if (CLIP_IN.equals(source)) {
                    clipIn = Math.round(x);
                    return;
                }
                if (CLIP_GAIN.equals(source)) {
                    clipGain = Math.round(x);
                    return;
                }
                if (CLIP_OUT.equals(source)) {   // sent last: the second's report is complete
                    int in = clipIn, started = clips.onSecond(in, clipGain, Math.round(x));
                    long now = SystemClock.uptimeMillis();
                    if ((started & 1 << ClipWatch.IN) != 0) {
                        logEvent("Mic overloading (too loud or too close to the mic)");
                    } else if (in > 0 && now - lastMicClipLog > 10000) {
                        logEvent("Mic overloaded for a moment (" + in + " x 12 ms)");
                    }
                    if (in > 0) {
                        lastMicClipLog = now;
                    }
                    if ((started & 1 << ClipWatch.OUT) != 0) {
                        logEvent("Output limiter working hard");
                    }
                    return;
                }
                if (TEMPO.equals(source)) {
                    tempoBpm = x;
                    return;
                }
                if (CHIME_NOTE.equals(source)) {
                    motif.onNote(Math.round(x), SystemClock.elapsedRealtimeNanos() / 1e9);
                    return;
                }
                if (HARMONY_RECEIVER.equals(source)) {
                    harmonyNotes.incrementAndGet();
                    return;
                }
                Modulation.setMicLevelDb(x - 100f);   // env~ reports dB with 100 = full scale
            }

            @Override
            public void receiveList(String source, Object... args) {
                if (FS_LEVELS.equals(source) && args.length == 3) {
                    float all = ((Number) args[0]).floatValue() - 100;   // (Pd's dB: 100 = full scale)
                    float lo = ((Number) args[1]).floatValue() - 100;
                    float hi = ((Number) args[2]).floatValue() - 100;
                    fsLevels = String.format(java.util.Locale.US, " (level %.0f dB, lows %+.0f, highs %+.0f)", all, lo - all, hi - all);
                }
            }

            @Override
            public void receiveMessage(String source, String symbol, Object... args) {
                if (SceneEvents.REQUEST_RECEIVER.equals(source) && "time".equals(symbol)) {
                    // rj_time asked for the clock. (compass is streamed all the time; loc has no
                    // permission here, so rj_loc stays quiet.)
                    float[] t = SceneEvents.timeValues();
                    Object[] list = new Object[t.length];
                    for (int i = 0; i < t.length; i++) {
                        list[i] = t[i];
                    }
                    PdBase.sendList(SceneEvents.TIME_RECEIVER, list);
                }
            }
        });
        PdBase.subscribe("mic_level");
        PdBase.subscribe(HARMONY_RECEIVER);
        PdBase.subscribe(CHIME_NOTE);
        PdBase.subscribe(TEMPO);
        PdBase.subscribe(FS_CAUGHT);
        PdBase.subscribe(FS_LEVELS);
        PdBase.subscribe(FPAD_CAUGHT);
        PdBase.subscribe(CLIP_IN);
        PdBase.subscribe(CLIP_GAIN);
        PdBase.subscribe(CLIP_OUT);
        clips.reset();
        synchronized (handlingSkips) {
            handlingSkips.clear();
        }
        handlingSent = 0f;
        calmChimesSent = 0f;
        CalmBuild.reset();
        synchronized (kitCaught) {
            java.util.Arrays.fill(kitCaught, 0);   // a fresh patch starts with an empty kit
        }
        PdBase.subscribe(SceneEvents.REQUEST_RECEIVER);

        // Must come before initAudio. DEFAULT_ID lets Android choose ("Automatic").
        AudioDevices.Device in = AudioDevices.find(this, true);
        AudioDevices.Device out = AudioDevices.chooseOutput(this);   // headphones only, never the speaker
        if (out == null) {
            throw new IOException(getString(R.string.err_no_headphones));
        }
        if (!canSelectDevices()) {
            Log.w(TAG, "pd-core cannot pick devices; headphones-only output is not enforced");
        }
        if (!AudioDevices.isBluetoothMic(in)) {
            openAudio(sampleRate, patchFile, scene, in, out);
            return;
        }
        String address = requestBluetoothMic(am, in);
        if (address == null) {
            releaseBluetoothMic();
            throw new IOException(getString(R.string.err_bluetooth_mic));
        }
        // Android takes up to a few seconds to bring the link up. Wait on another thread (waiting here froze
        // the screen), then open the audio back on the main thread.
        starting = true;
        int generation = startGeneration;
        final int rate = sampleRate;
        final AudioDevices.Device output = out;
        new Thread(() -> {
            boolean up = waitForBluetoothMic(am, in, address);
            handler.post(() -> {
                if (generation != startGeneration) {
                    return;   // stopped meanwhile
                }
                starting = false;
                try {
                    if (!up) {
                        releaseBluetoothMic();
                        throw new IOException(getString(R.string.err_bluetooth_mic));
                    }
                    openAudio(rate, patchFile, scene, in, output);
                    lastError = null;
                } catch (IOException | RuntimeException e) {
                    Log.e(TAG, "Failed to start audio", e);
                    lastError = getString(R.string.err_start_failed, e.getMessage());
                    shutDown();
                }
            });
        }, "bluetooth-mic-wait").start();
    }

    /** Second half of starting: opens the streams and the patch on the devices chosen. */
    private void openAudio(int sampleRate, File patchFile, SceneLibrary.Scene scene,
                           AudioDevices.Device in, AudioDevices.Device out) throws IOException {
        if (AudioDevices.isBluetoothMic(in)) {
            // Sound and mic share the headset's one link, so play to its matching output.
            AudioDevices.Device paired = AudioDevices.pairedOutput(this, in);
            if (paired != null) {
                out = paired;
            }
        }
        activeOutputId = out.id;
        outputLabel = out.label;
        inputAsked = in == null ? null : in.label;
        callModeMic = AudioDevices.isBluetoothMic(in) && !AudioDevices.isLeAudio(in);
        selectDevices(AudioDevices.idOrDefault(in), out.id);
        // Which devices were asked for, and every mic Android lists: a tester's mic problem can be read back later.
        StringBuilder mics = new StringBuilder();
        for (android.media.AudioDeviceInfo d : getSystemService(AudioManager.class)
                .getDevices(AudioManager.GET_DEVICES_INPUTS)) {
            mics.append(mics.length() == 0 ? "" : "; ").append("type ").append(d.getType()).append(" id ").append(d.getId())
                    .append(" ").append(d.getProductName()).append(" rates ").append(java.util.Arrays.toString(d.getSampleRates()))
                    .append(" ch ").append(java.util.Arrays.toString(d.getChannelCounts()));
        }
        logEvent("Devices: input " + (in == null ? "Automatic" : in.label + " (type " + in.type + ", id " + in.id + ")")
                + ", output " + out.label + " (type " + out.type + ", id " + out.id + "). Mics: " + mics);

        // 1 input channel (mic), 2 output channels. The ticks-per-buffer argument is
        // ignored by the Oboe backend; Oboe picks the device's low-latency burst size.
        PdAudio.initAudio(sampleRate, 1, 2, 8, true);
        try {
            patchHandle = PdBase.openPatch(patchFile);
        } catch (IOException e) {
            PdAudio.release();   // stopEngine() won't, since nothing is running yet
            throw new IOException(getString(R.string.err_scene_open,
                    scene != null ? scene.name : SCENE_FILE), e);
        }

        ParamStore.sendAllToPd();
        sceneRunning = scene != null;
        if (scene != null) {
            sendSceneLevels(this);
        }

        PdAudio.startAudio(this);
        // Scenes read the sensors as Pd messages; the built-in effects' movers read them directly.
        sensors = new SensorInput(this, scene != null);
        if (!sensors.start()) {
            Log.w(TAG, "No accelerometer on this device");
        }
        actualRate = queryActualRate();
        running = true;
        AudioManager am = getSystemService(AudioManager.class);
        am.registerAudioDeviceCallback(outputWatcher, handler);
        pausedForCall = false;
        lastCallCheck = 0;
        otherPlayers = 0;
        am.registerAudioPlaybackCallback(playbackWatcher, handler);
        updateOtherAudio(am.getActivePlaybackConfigurations());
        Modulation.reset();
        StepDetector.reset();
        motif.reset();
        noteRegister.reset();
        // Footsteps drive the built-in patch's drums; scenes have their own business with the sensors.
        StepDetector.setListener(scene == null ? (interval, strength) -> {
            PdBase.sendFloat("step_strength", strength);   // first, so the step's sounds can use it
            PdBase.sendFloat("groove", StepDetector.grooving() ? 1f : 0f);
            PdBase.sendFloat("beat_sure", StepDetector.sureness());
            PdBase.sendFloat("step", (float) interval);
        } : null);
        // The hi-hat falls half a step later, by when this step's own landing is known.
        StepDetector.setLandingListener(scene == null ? strength -> PdBase.sendFloat("step_hit", strength) : null);
        Worlds.load(this);
        Worlds.reset();
        autoWorlds = scene == null;
        pocketSent = false;   // a freshly opened patch starts out of the pocket
        micDownSent = false;
        lastClockCheck = -CLOCK_CHECK_MS;
        lastMoverTick = SystemClock.uptimeMillis();
        handler.postDelayed(moverTick, MOVER_INTERVAL_MS);
        notifyStateChanged();
        Log.i(TAG, "Audio started, asked for " + sampleRate + " Hz, got " + actualRate + " Hz");
        logEvent(scene == null ? "Audio started (built-in effects)" : "Audio started (scene)");
    }

    /** The rate Pd really runs at; 0 if the library can't say (PdBase.audioRuntimeInfo is newer than rc6). */
    private static int queryActualRate() {
        try {
            Object rate = PdBase.class.getMethod("audioRuntimeInfo", String.class).invoke(null, "sampleRate");
            return Integer.parseInt(String.valueOf(rate));
        } catch (ReflectiveOperationException | RuntimeException e) {
            return 0;
        }
    }

    /** Id of the headphones being played to, or -1; used to notice when they are unplugged. */
    private int activeOutputId = -1;

    /**
     * Android moves a stream to the phone speaker when its headphones disappear. Instead, switch to
     * other headphones if some are connected, or stop with a message.
     */
    private final android.media.AudioDeviceCallback outputWatcher = new android.media.AudioDeviceCallback() {
        @Override
        public void onAudioDevicesRemoved(android.media.AudioDeviceInfo[] removed) {
            if (!running || outputLost) {
                return;
            }
            for (android.media.AudioDeviceInfo d : removed) {
                if (d.getId() == activeOutputId) {
                    headphonesLost();
                    return;
                }
            }
        }
    };

    /**
     * How long to leave libpd alone after the headphones go. Its Oboe layer reacts to the disconnect on its own
     * thread: it closes both streams and reopens them (on the phone speaker), which took about 0.1 s on the Moto G.
     */
    private static final long DISCONNECT_SETTLE_MS = 600;
    /** True between losing the headphones and acting on it. */
    private boolean outputLost;
    private final Runnable afterHeadphonesLost = this::afterHeadphonesLost;

    private void headphonesLost() {
        // Stopping right away closes the same streams as libpd's own disconnect handling, at the same time and
        // without a lock, and crashes in native code (OboeEngine::closeStream). So go silent at once, which also
        // keeps the reopened speaker stream quiet, and stop only after libpd has finished.
        outputLost = true;
        PdBase.computeAudio(false);
        handler.postDelayed(afterHeadphonesLost, DISCONNECT_SETTLE_MS);
    }

    private void afterHeadphonesLost() {
        outputLost = false;
        if (!running) {
            return;   // stopped by hand meanwhile
        }
        stopEngine();
        try {
            startEngine();   // picks the best headphones still connected, or throws if none
            lastError = null;
        } catch (IOException | RuntimeException e) {
            Log.i(TAG, "Headphones removed, stopping: " + e.getMessage());
            lastError = getString(R.string.err_headphones_removed);
            shutDown();
        }
    }

    private void stopEngine() {
        startGeneration++;
        if (starting) {   // still waiting for a Bluetooth headset: give up
            starting = false;
            releaseBluetoothMic();
            notifyStateChanged();
        }
        if (!running && patchHandle < 0) {
            return;
        }
        running = false;
        outputLost = false;
        handler.removeCallbacks(afterHeadphonesLost);
        getSystemService(AudioManager.class).unregisterAudioDeviceCallback(outputWatcher);
        getSystemService(AudioManager.class).unregisterAudioPlaybackCallback(playbackWatcher);
        pausedForCall = false;
        handler.removeCallbacks(moverTick);
        Modulation.reset();
        StepDetector.setListener(null);
        StepDetector.setLandingListener(null);
        Worlds.reset();   // the user's own settings come back
        autoWorlds = false;
        if (sensors != null) {
            sensors.stop();
            sensors = null;
        }
        notifyStateChanged();
        try {
            PdAudio.stopAudio();
            if (patchHandle >= 0) {
                PdBase.sendBang(SceneEvents.CLOSEBANG_RECEIVER);   // lets a scene tidy up, like [closebang]
                PdBase.closePatch(patchHandle);
                patchHandle = -1;
            }
            PdAudio.release();
        } catch (RuntimeException e) {
            Log.w(TAG, "Error while stopping audio", e);
        }
        releaseBluetoothMic();
    }

    private int savedAudioMode = AudioManager.MODE_NORMAL;

    /**
     * A Bluetooth headset only delivers microphone audio over its hands-free (call) link. Android
     * opens that link on request and takes a moment to do it, so this puts the phone in call mode and
     * asks for the headset; {@link #waitForBluetoothMic} then waits (up to 3 seconds) until the link is up.
     * The audio streams are opened only after that, or they would have no device to attach to and stay silent.
     *
     * @return the headset's address, or null if Android refused
     */
    @SuppressWarnings("deprecation")
    private String requestBluetoothMic(AudioManager am, AudioDevices.Device device) {
        final String address = device.key.substring(device.key.indexOf(':') + 1);
        savedAudioMode = am.getMode();
        am.setMode(AudioManager.MODE_IN_COMMUNICATION);
        bluetoothMicRouted = true;   // so releaseBluetoothMic() undoes this even if the wait fails
        boolean requested = true;
        if (Build.VERSION.SDK_INT >= 31) {
            requested = false;
            for (android.media.AudioDeviceInfo d : am.getAvailableCommunicationDevices()) {
                // The headset's mic and speaker are separate devices with separate ids, so match
                // by type and address, not id.
                if (d.getType() == device.type && d.getAddress().equals(address)) {
                    requested = am.setCommunicationDevice(d);
                }
            }
        } else {
            am.startBluetoothSco();
        }
        if (!requested) {
            Log.w(TAG, "Android would not route calls to the Bluetooth headset");
            return null;
        }
        return address;
    }

    /** Blocks (call it off the main thread) until the headset's call link is up; false after 3 seconds. */
    @SuppressWarnings("deprecation")
    private static boolean waitForBluetoothMic(AudioManager am, AudioDevices.Device device, String address) {
        for (int waited = 0; waited < 3000; waited += 100) {
            boolean up = Build.VERSION.SDK_INT >= 31
                    ? am.getCommunicationDevice() != null
                            && am.getCommunicationDevice().getType() == device.type
                            && am.getCommunicationDevice().getAddress().equals(address)
                    : am.isBluetoothScoOn();
            if (up) {
                try {
                    Thread.sleep(300);   // let the matching output show up in the device list
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
                Log.i(TAG, "Bluetooth call link up after " + waited + " ms");
                return true;
            }
            try {
                Thread.sleep(100);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }
        Log.w(TAG, "Bluetooth call link did not come up");
        return false;
    }

    @SuppressWarnings("deprecation")
    private void releaseBluetoothMic() {
        if (!bluetoothMicRouted) {
            return;
        }
        AudioManager am = getSystemService(AudioManager.class);
        if (Build.VERSION.SDK_INT >= 31) {
            am.clearCommunicationDevice();
        } else {
            am.stopBluetoothSco();
        }
        am.setMode(savedAudioMode);
        bluetoothMicRouted = false;
    }

    private void shutDown() {
        stopEngine();
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf();
        notifyStateChanged();
    }

    @Override
    public void onDestroy() {
        stopEngine();
        logWriter.shutdown();   // lines already queued are still written
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private static int parseInt(String s, int fallback) {
        try {
            return s == null ? fallback : Integer.parseInt(s);
        } catch (NumberFormatException e) {
            return fallback;
        }
    }

    /**
     * Copies an asset directory unless this install already did: the RjDj library alone is ~400 files, and
     * copying it on every Start made starting slow. A stamp file records which install (update time) copied it.
     */
    private void copyAssetsIfChanged(String assetPath, File dest) throws IOException {
        String stamp;
        try {
            stamp = String.valueOf(getPackageManager().getPackageInfo(getPackageName(), 0).lastUpdateTime);
        } catch (PackageManager.NameNotFoundException e) {
            stamp = "";
        }
        File mark = new File(dest, ".copied");
        if (!stamp.isEmpty() && mark.isFile()) {
            try (InputStream in = new java.io.FileInputStream(mark)) {
                byte[] b = new byte[64];
                int n = in.read(b);
                if (n > 0 && stamp.equals(new String(b, 0, n, StandardCharsets.UTF_8))) {
                    return;
                }
            }
        }
        copyAssetDir(getAssets(), assetPath, dest);
        try (OutputStream out = new FileOutputStream(mark)) {
            out.write(stamp.getBytes(StandardCharsets.UTF_8));
        }
    }

    /** Recursively copies an asset directory to the app's private storage. */
    static void copyAssetDir(AssetManager assets, String assetPath, File dest)
            throws IOException {
        String[] children = assets.list(assetPath);
        if (children == null || children.length == 0) {
            // A file, not a directory.
            File parent = dest.getParentFile();
            if (parent != null && !parent.exists() && !parent.mkdirs()) {
                throw new IOException("Cannot create " + parent);
            }
            try (InputStream in = assets.open(assetPath);
                 OutputStream out = new FileOutputStream(dest)) {
                byte[] buf = new byte[8192];
                int n;
                while ((n = in.read(buf)) > 0) {
                    out.write(buf, 0, n);
                }
            }
            return;
        }
        if (!dest.exists() && !dest.mkdirs()) {
            throw new IOException("Cannot create " + dest);
        }
        for (String child : children) {
            copyAssetDir(assets, assetPath + "/" + child, new File(dest, child));
        }
    }
}
