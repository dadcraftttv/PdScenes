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
    private String worldLogged;
    private final Runnable moverTick = new Runnable() {
        @Override
        public void run() {
            long now = SystemClock.uptimeMillis();
            // Cap dt so a stalled main thread doesn't make the movers jump.
            double dt = Math.min((now - lastMoverTick) / 1000.0, 0.25);
            Modulation.tick(dt, (id, value) -> PdBase.sendFloat(id, value));
            if (autoWorlds) {
                boolean pocket = PhoneContext.inPocket();
                if (pocket != pocketSent) {
                    pocketSent = pocket;
                    PdBase.sendFloat("pocket", pocket ? 1f : 0f);
                    Log.i(TAG, pocket ? "Phone went into a pocket" : "Phone came out of the pocket");
                }
                String world = Worlds.currentWorld();
                if (world != null ? !world.equals(worldLogged) : worldLogged != null) {
                    worldLogged = world;
                    Log.i(TAG, "World: " + (world == null ? "own settings" : world));
                }
                if (now - lastClockCheck > CLOCK_CHECK_MS) {   // the time of day changes slowly
                    minuteOfDay = Worlds.minuteOfDayNow();
                    lastClockCheck = now;
                }
                Worlds.tick(dt, Modulation.micLevelDb(),
                        StepDetector.walking(SystemClock.elapsedRealtimeNanos() / 1e9),
                        PhoneContext.inPocket(), minuteOfDay);
            }
            lastMoverTick = now;
            handler.postDelayed(this, MOVER_INTERVAL_MS);
        }
    };

    private int patchHandle = -1;
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
            if (!running) {
                return START_NOT_STICKY;   // nothing to restart; the new choice applies on next Start
            }
            stopEngine();
        }
        if (!running) {
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
        copyAssetDir(getAssets(), "patches", patchDir);

        PdBase.addToSearchPath(patchDir.getAbsolutePath());
        // Where Android unpacks libfiddle_tilde.so and the other optional externals scenes use.
        PdBase.addToSearchPath(getApplicationInfo().nativeLibraryDir);

        // Scenes find the player's soundinput/soundoutput through "declare -path ../pd".
        File scenesDir = SceneSettings.scenesDir(this);
        File libDir = new File(scenesDir, SceneLibrary.LIB_DIR);
        copyAssetDir(getAssets(), "scene_lib", libDir);
        PdBase.addToSearchPath(libDir.getAbsolutePath());                       // soundinput, accelerate, rj/...
        PdBase.addToSearchPath(new File(libDir, "rj").getAbsolutePath());       // RjDj library, by bare name
        SceneLibrary.Scene scene = SceneSettings.current(this);
        File patchFile = scene != null ? scene.mainPatch() : new File(patchDir, SCENE_FILE);

        // The patch reports the mic loudness about 30 times a second for the "Louder" movers.
        PdBase.setReceiver(new PdReceiver.Adapter() {
            @Override
            public void receiveFloat(String source, float x) {
                Modulation.setMicLevelDb(x - 100f);   // env~ reports dB with 100 = full scale
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
        if (!routeBluetoothMic(am, in)) {
            releaseBluetoothMic();
            throw new IOException(getString(R.string.err_bluetooth_mic));
        }
        if (AudioDevices.isBluetoothMic(in)) {
            // Sound and mic share the headset's one link, so play to its matching output.
            AudioDevices.Device paired = AudioDevices.pairedOutput(this, in);
            if (paired != null) {
                out = paired;
            }
        }
        activeOutputId = out.id;
        selectDevices(AudioDevices.idOrDefault(in), out.id);

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
        getSystemService(AudioManager.class).registerAudioDeviceCallback(outputWatcher, handler);
        Modulation.reset();
        StepDetector.reset();
        // Footsteps drive the built-in patch's drums; scenes have their own business with the sensors.
        StepDetector.setListener(scene == null ? interval -> PdBase.sendFloat("step", (float) interval) : null);
        Worlds.load(this);
        Worlds.reset();
        autoWorlds = scene == null;
        pocketSent = false;   // a freshly opened patch starts out of the pocket
        lastClockCheck = -CLOCK_CHECK_MS;
        lastMoverTick = SystemClock.uptimeMillis();
        handler.postDelayed(moverTick, MOVER_INTERVAL_MS);
        notifyStateChanged();
        Log.i(TAG, "Audio started, asked for " + sampleRate + " Hz, got " + actualRate + " Hz");
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
        if (!running && patchHandle < 0) {
            return;
        }
        running = false;
        outputLost = false;
        handler.removeCallbacks(afterHeadphonesLost);
        getSystemService(AudioManager.class).unregisterAudioDeviceCallback(outputWatcher);
        handler.removeCallbacks(moverTick);
        Modulation.reset();
        StepDetector.setListener(null);
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
     * opens that link on request and takes a moment to do it, so this puts the phone in call mode,
     * asks for the headset and waits (up to 3 seconds) until the link is up. The audio streams are
     * opened only after that, or they would have no device to attach to and stay silent.
     *
     * @return true once the headset's call link is active
     */
    @SuppressWarnings("deprecation")
    private boolean routeBluetoothMic(AudioManager am, AudioDevices.Device device) {
        if (!AudioDevices.isBluetoothMic(device)) {
            return true;
        }
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
            return false;
        }
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
