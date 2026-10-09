// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import android.content.Context;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.SystemClock;

import org.puredata.core.PdBase;

/**
 * Feeds the phone's motion sensors to the running scene the way RjDj and its descendants did, as Pd lists:
 * <ul>
 * <li>{@code #accelerate x y z} in g (RjDj's original; see below for the sign),</li>
 * <li>{@code #gyro x y z} rotation rate in rad/s,</li>
 * <li>{@code #magnet x y z} magnetic field in microtesla,</li>
 * <li>{@code #compass degrees} the direction the phone points, clockwise from magnetic north (fused, steady,
 * and still sensible when the phone is held upright; see {@link PhoneContext#headingDegrees}),</li>
 * <li>extras beyond RjDj: {@code #light lux}, {@code #proximity 0|1} (1 = something against the phone),
 * {@code #pocket 0|1} and {@code #pressure hPa} (air pressure).</li>
 * </ul>
 * Phones without a gyroscope or magnetometer simply don't send those. The same readings also drive the
 * built-in effects' movers (see {@link Modulation}); with no scene selected nothing is sent to Pd.
 *
 * <p>RjDj scenes were written for iOS, where gravity reads with the opposite sign to Android: a phone
 * lying face-up reads z = -1 there but +9.8 m/s&sup2; here. {@link #toScene} converts, so a scene's
 * shake detector (for example "louder than 2.3 g") behaves as its author intended.
 */
final class SensorInput implements SensorEventListener {

    /** Pd receiver that scenes listen on for accelerometer values. */
    static final String ACCELERATE_RECEIVER = "#accelerate";
    static final String GYRO_RECEIVER = "#gyro";
    static final String MAGNET_RECEIVER = "#magnet";
    static final String COMPASS_RECEIVER = "#compass";
    static final String LIGHT_RECEIVER = "#light";
    static final String PROXIMITY_RECEIVER = "#proximity";
    static final String POCKET_RECEIVER = "#pocket";
    static final String PRESSURE_RECEIVER = "#pressure";

    private final SensorManager sensorManager;
    /** False for the built-in effects, which use the sensors only for their movers. */
    /** 200 readings a second; asking for more needs a permission most phones show a warning for. */
    private static final int ACCEL_PERIOD_FOR_STEPS_US = 5000;

    private final boolean sendToPd;
    private HandlerThread thread;
    /** Latest gravity reading (Android axes), kept for the compass. */
    private final float[] gravity = new float[3];
    private boolean haveGravity;
    /** True when the phone has a fused rotation vector sensor; then it supplies the compass. */
    private boolean haveRotationVector;
    private float proximityRange = 5f;
    private boolean lastPocket;
    private long lastLightSentMs;

    SensorInput(Context context, boolean sendToPd) {
        sensorManager = context.getSystemService(SensorManager.class);
        this.sendToPd = sendToPd;
    }

    /** Starts listening. Returns false if the phone has no accelerometer. */
    boolean start() {
        Sensor accel = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER);
        if (accel == null) {
            return false;
        }
        // Own thread, so a busy screen never delays the readings (about 50 per second).
        thread = new HandlerThread("scene-sensors");
        thread.start();
        Handler handler = new Handler(thread.getLooper());
        // Scenes get the fast rate for everything. For the built-in effects the gyroscope and compass only
        // steer movers (30 updates a second), so the slower, battery-friendlier rate is plenty; the
        // accelerometer is read 200 times a second (the most Android allows without a special permission)
        // so the beat lands on the step; scenes get the usual 50.
        int accelRate = sendToPd ? SensorManager.SENSOR_DELAY_GAME : ACCEL_PERIOD_FOR_STEPS_US;
        int rate = sendToPd ? SensorManager.SENSOR_DELAY_GAME : SensorManager.SENSOR_DELAY_UI;
        sensorManager.registerListener(this, accel, accelRate, handler);
        register(Sensor.TYPE_GYROSCOPE, handler, rate);
        PhoneContext.reset();
        lastPocket = false;
        haveRotationVector = register(Sensor.TYPE_ROTATION_VECTOR, handler, rate);
        // Scenes may want the raw field; the built-in effects only need it when there is no fused sensor.
        if (sendToPd || !haveRotationVector) {
            register(Sensor.TYPE_MAGNETIC_FIELD, handler, rate);
        }
        // Environment sensors change slowly, so the slow rate is plenty.
        register(Sensor.TYPE_LIGHT, handler, SensorManager.SENSOR_DELAY_UI);
        Sensor prox = sensorManager.getDefaultSensor(Sensor.TYPE_PROXIMITY);
        if (prox != null) {
            proximityRange = prox.getMaximumRange();
            sensorManager.registerListener(this, prox, SensorManager.SENSOR_DELAY_NORMAL, handler);
        }
        register(Sensor.TYPE_PRESSURE, handler, SensorManager.SENSOR_DELAY_UI);
        return true;
    }

    private boolean register(int type, Handler handler, int rate) {
        Sensor sensor = sensorManager.getDefaultSensor(type);
        if (sensor != null) {
            return sensorManager.registerListener(this, sensor, rate, handler);
        }
        return false;
    }

    /** A one-line list of which sensors this phone is reporting, for the diagnostics. */
    static String describe(Context context) {
        SensorManager m = context.getSystemService(SensorManager.class);
        int[] types = {Sensor.TYPE_ACCELEROMETER, Sensor.TYPE_GYROSCOPE, Sensor.TYPE_MAGNETIC_FIELD,
                Sensor.TYPE_ROTATION_VECTOR, Sensor.TYPE_LIGHT, Sensor.TYPE_PROXIMITY, Sensor.TYPE_PRESSURE};
        String[] names = {"accelerometer", "gyroscope", "magnetometer", "rotation", "light", "proximity",
                "barometer"};
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < types.length; i++) {
            if (sb.length() > 0) {
                sb.append(", ");
            }
            sb.append(names[i]).append(m.getDefaultSensor(types[i]) != null ? " yes" : " no");
        }
        return sb.toString();
    }

    void stop() {
        sensorManager.unregisterListener(this);
        if (thread != null) {
            thread.quitSafely();
            thread = null;
        }
    }

    @Override
    public void onSensorChanged(SensorEvent event) {
        // Light, proximity and pressure report a single value; only the motion sensors have y and z.
        float[] v = event.values;
        float x = v[0], y = v.length > 1 ? v[1] : 0f, z = v.length > 2 ? v[2] : 0f;
        switch (event.sensor.getType()) {
            case Sensor.TYPE_ACCELEROMETER:
                if (sendToPd) {
                    float[] g = toScene(x, y, z);
                    PdBase.sendList(ACCELERATE_RECEIVER, g[0], g[1], g[2]);
                }
                Modulation.onAcceleration(x, y, z);
                double at = SystemClock.elapsedRealtimeNanos() / 1e9;
                StepDetector.onAcceleration(x, y, z, at);
                PhoneContext.onAcceleration(x, y, z, at);
                gravity[0] = x;
                gravity[1] = y;
                gravity[2] = z;
                haveGravity = true;
                break;
            case Sensor.TYPE_GYROSCOPE:
                // Same axes and right-hand rule as iOS, so no conversion.
                if (sendToPd) {
                    PdBase.sendList(GYRO_RECEIVER, x, y, z);
                }
                Modulation.onGyro(x, y, z);
                break;
            case Sensor.TYPE_MAGNETIC_FIELD:
                if (sendToPd) {
                    PdBase.sendList(MAGNET_RECEIVER, x, y, z);
                }
                if (haveGravity && !haveRotationVector) {
                    float degrees = compassDegrees(gravity, event.values);
                    if (sendToPd) {
                        PdBase.sendFloat(COMPASS_RECEIVER, degrees);
                    }
                    Modulation.onCompass(degrees);
                }
                break;
            case Sensor.TYPE_ROTATION_VECTOR:
                float degrees = PhoneContext.headingDegrees(event.values);
                if (degrees >= 0f) {
                    if (sendToPd) {
                        PdBase.sendFloat(COMPASS_RECEIVER, degrees);
                    }
                    Modulation.onCompass(degrees);
                }
                break;
            case Sensor.TYPE_LIGHT:
                PhoneContext.onLight(x);
                // Lux can flicker a lot; scenes get at most ten updates a second.
                long nowMs = SystemClock.uptimeMillis();
                if (sendToPd && nowMs - lastLightSentMs >= 100) {
                    lastLightSentMs = nowMs;
                    PdBase.sendFloat(LIGHT_RECEIVER, x);
                }
                sendPocketIfChanged();
                break;
            case Sensor.TYPE_PROXIMITY:
                boolean near = x < Math.min(proximityRange, 5f);
                PhoneContext.onProximity(near);
                if (sendToPd) {
                    PdBase.sendFloat(PROXIMITY_RECEIVER, near ? 1f : 0f);
                }
                sendPocketIfChanged();
                break;
            case Sensor.TYPE_PRESSURE:
                PhoneContext.onPressure(x, SystemClock.elapsedRealtimeNanos() / 1e9);
                if (sendToPd) {
                    PdBase.sendFloat(PRESSURE_RECEIVER, x);
                }
                sendPocketIfChanged();
                break;
            default:
                break;
        }
    }

    /** Scenes hear {@code #pocket} when it flips. (A dwell timer needs events, so also checked on each light change.) */
    private void sendPocketIfChanged() {
        boolean pocket = PhoneContext.inPocket();
        if (pocket != lastPocket) {
            lastPocket = pocket;
            if (sendToPd) {
                PdBase.sendFloat(POCKET_RECEIVER, pocket ? 1f : 0f);
            }
        }
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) { }

    /** Android m/s&sup2; to the iOS-style g values scenes expect (sign flipped, 1 g = 9.80665 m/s&sup2;). */
    static float[] toScene(float x, float y, float z) {
        float g = SensorManager.GRAVITY_EARTH;
        return new float[]{-x / g, -y / g, -z / g};
    }

    /**
     * Direction the top edge of the phone points, in degrees clockwise from magnetic north (0 to 360),
     * from the gravity and magnetic field vectors (the same maths as SensorManager.getRotationMatrix).
     * Most accurate with the phone held flat; upright it reads where the top edge leans.
     */
    static float compassDegrees(float[] gravity, float[] magnetic) {
        float ax = gravity[0], ay = gravity[1], az = gravity[2];
        // East = magnetic x gravity
        float hx = magnetic[1] * az - magnetic[2] * ay;
        float hy = magnetic[2] * ax - magnetic[0] * az;
        float hz = magnetic[0] * ay - magnetic[1] * ax;
        float normH = (float) Math.sqrt(hx * hx + hy * hy + hz * hz);
        float normA = (float) Math.sqrt(ax * ax + ay * ay + az * az);
        if (normH < 0.1f || normA == 0f) {
            return 0f;   // free fall, or field parallel to gravity: no usable heading
        }
        hx /= normH;
        hy /= normH;
        hz /= normH;
        ax /= normA;
        ay /= normA;
        az /= normA;
        float northY = az * hx - ax * hz;   // y component of gravity x east, i.e. north in device axes
        float degrees = (float) Math.toDegrees(Math.atan2(hy, northY));
        return degrees < 0 ? degrees + 360f : degrees;
    }
}
