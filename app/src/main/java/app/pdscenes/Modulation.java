// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import java.util.Random;

/**
 * The movers: slow automatic changes that push a slider up and down around its position. Every slider
 * can have one (settings "<id>_mv", "<id>_mvspeed", "<id>_mvdepth" in ParamStore), and a section's movers
 * only act while that section's "movers" switch is on. This class turns the settings into motion. {@link #tick} runs about 30 times a second from the audio service (main thread) and
 * the glide in the Pd patch smooths the steps into continuous movement.
 */
final class Modulation {

    /** Where the moved value is delivered (the service passes PdBase.sendFloat). */
    interface Sink {
        void send(String id, float value);
    }

    private static final Random rng = new Random();
    private static final int MOVERS = Params.MOVABLE.size();

    // Per-mover state, touched only by tick() and reset().
    private static final double[] phase = new double[MOVERS];   // 0..1 within a cycle
    private static final float[] driftFrom = new float[MOVERS];
    private static final float[] driftTo = new float[MOVERS];
    private static final float[] follower = new float[MOVERS];   // where a following mover is, -1..1

    /** Loudness of the mic in dB relative to full scale, reported by the patch (about 30 a second). */
    private static volatile float micLevelDb = -100f;

    // Mic levels from QUIET_DB (nothing) to LOUD_DB (everything) map to 0..1 for the movers.
    private static final float QUIET_DB = -60f;
    private static final float LOUD_DB = -15f;
    // Positions in Params.MOVER_SHAPES.
    private static final int SHAPE_OFF = 0;
    private static final int SHAPE_DRIFT = 2;
    private static final int SHAPE_LOUDER_HIGHER = 3;
    private static final int SHAPE_LOUDER_LOWER = 4;
    private static final int SHAPE_UPRIGHT = 5;
    private static final int SHAPE_LEAN_RIGHT = 6;
    private static final int SHAPE_SHAKE = 7;
    private static final int SHAPE_SPIN = 8;
    private static final int SHAPE_SOUTH = 9;
    private static final int SHAPE_PAD_X = 10;
    private static final int SHAPE_PAD_Y = 11;
    private static final int SHAPE_JUMP = 12;
    private static final int SHAPE_LIGHT = 13;
    private static final int SHAPE_POCKET = 14;
    private static final int SHAPE_CLIMB = 15;
    private static final float MIN_JUMP = 0.5f;   // a jump moves at least this far (of the -1..1 span), so it is always audible

    // Setting ids per mover, built once so the 30-times-a-second tick doesn't concatenate strings.
    private static final String[] SHAPE_ID = new String[MOVERS];
    private static final String[] SPEED_ID = new String[MOVERS];
    private static final String[] DEPTH_ID = new String[MOVERS];
    private static final String[] SWITCH_ID = new String[MOVERS];
    static {
        for (int i = 0; i < MOVERS; i++) {
            Param p = Params.MOVABLE.get(i);
            SHAPE_ID[i] = Params.moverId(p.id, "mv");
            SPEED_ID[i] = Params.moverId(p.id, "mvspeed");
            DEPTH_ID[i] = Params.moverId(p.id, "mvdepth");
            SWITCH_ID[i] = Params.moversSwitchId(p.section);
        }
    }

    private static final float GRAVITY = 9.80665f;
    private static final float SPIN_FULL_RAD_PER_S = 6f;      // spinning this fast counts as "all the way"
    private static final double SHAKE_RELEASE_S = 0.4;        // how long a shake takes to fade away

    // Latest sensor readings, each scaled to the range the movers use. Written from the sensor thread.
    private static volatile float upright;      // -1 flat .. +1 standing on its end
    private static volatile float leanRight;    // -1 .. +1
    private static volatile float spin;         // 0 .. 1
    private static volatile float south;        // -1 facing north .. +1 facing south
    private static volatile float padX;         // -1 left .. +1 right
    private static volatile float padY;         // -1 bottom .. +1 top
    private static float shakePeak;             // strongest shake since the last tick (guarded by Modulation.class)
    private static float shakeLevel;            // shake with its fade-out, touched only by tick()

    /** How far each parameter is currently pushed, in slider units (-1..1). Replaced whole. */
    private static volatile Map<String, Float> offsets = Collections.emptyMap();

    private Modulation() { }

    /** Accelerometer reading in Android units (m/s&sup2;, gravity included). Safe to call from any thread. */
    static void onAcceleration(float x, float y, float z) {
        upright = clamp(2f * clamp(y / GRAVITY, 0f, 1f) - 1f);
        leanRight = clamp(-x / GRAVITY * 1.4f);   // 45 degrees of lean is full scale
        float motion = Math.abs((float) Math.sqrt(x * x + y * y + z * z) - GRAVITY) / GRAVITY;
        synchronized (Modulation.class) {
            shakePeak = Math.max(shakePeak, Math.min(1f, motion));
        }
    }

    /** Gyroscope reading in rad/s. */
    static void onGyro(float x, float y, float z) {
        spin = Math.min(1f, (float) Math.sqrt(x * x + y * y + z * z) / SPIN_FULL_RAD_PER_S);
    }

    /** Compass heading in degrees clockwise from north (the way the top of the phone points). */
    static void onCompass(float degrees) {
        south = -(float) Math.cos(Math.toRadians(degrees));
    }

    /** Touch pad position as fractions of its size: x from the left, y from the top (0..1). */
    static void onPad(float x, float y) {
        padX = clamp(2f * x - 1f);
        padY = clamp(1f - 2f * y);
    }

    private static float clamp(float v) {
        return clamp(v, -1f, 1f);
    }

    private static float clamp(float v, float lo, float hi) {
        return Math.max(lo, Math.min(hi, v));
    }

    private static synchronized float takeShakePeak() {
        float peak = shakePeak;
        shakePeak = 0f;
        return peak;
    }

    /** The latest mic loudness (dB, about -100 = silence, 0 = full scale). */
    static float micLevelDb() {
        return micLevelDb;
    }

    /** Called with each level report from the patch. Safe to call from any thread. */
    static void setMicLevelDb(float db) {
        micLevelDb = db;
    }

    /** Start from rest: no offsets, fresh random drift. Call when the engine starts or stops. */
    static void reset() {
        offsets = Collections.emptyMap();
        micLevelDb = -100f;
        upright = leanRight = spin = south = padX = padY = 0f;
        shakeLevel = 0f;
        takeShakePeak();
        for (int i = 0; i < MOVERS; i++) {
            follower[i] = 0;
            phase[i] = 0;
            driftFrom[i] = 0;
            driftTo[i] = randomPosition();
        }
    }

    /** Advance every mover by dt seconds and send the changed values to the sink. */
    static void tick(double dt, Sink sink) {
        Map<String, Float> next = new HashMap<>();
        // A shake rises at once and fades over a fraction of a second.
        shakeLevel = Math.max(takeShakePeak(), (float) (shakeLevel * Math.exp(-dt / SHAKE_RELEASE_S)));
        for (int i = 0; i < MOVERS; i++) {
            int shape = Math.round(ParamStore.get(SHAPE_ID[i]));
            if (shape == SHAPE_OFF || ParamStore.get(SWITCH_ID[i]) < 0.5f) {
                continue;
            }
            Param p = Params.MOVABLE.get(i);
            float speed = ParamStore.get(SPEED_ID[i]);
            phase[i] += dt * speed;
            float position;
            switch (shape) {
                case SHAPE_DRIFT:
                    position = driftPosition(i);
                    break;
                case SHAPE_JUMP:
                    position = jumpPosition(i);
                    break;
                case SHAPE_LOUDER_HIGHER:
                case SHAPE_LOUDER_LOWER:
                    float loud = clamp((micLevelDb - QUIET_DB) / (LOUD_DB - QUIET_DB), 0f, 1f);
                    position = follow(i, dt, speed, shape == SHAPE_LOUDER_HIGHER ? loud : -loud);
                    break;
                case SHAPE_UPRIGHT:
                    position = follow(i, dt, speed, upright);
                    break;
                case SHAPE_LEAN_RIGHT:
                    position = follow(i, dt, speed, leanRight);
                    break;
                case SHAPE_SHAKE:
                    position = follow(i, dt, speed, shakeLevel);
                    break;
                case SHAPE_SPIN:
                    position = follow(i, dt, speed, spin);
                    break;
                case SHAPE_SOUTH:
                    position = follow(i, dt, speed, south);
                    break;
                case SHAPE_LIGHT:
                    position = follow(i, dt, speed, PhoneContext.brightness() * 2f - 1f);
                    break;
                case SHAPE_POCKET:
                    position = follow(i, dt, speed, PhoneContext.inPocket() ? 1f : -1f);
                    break;
                case SHAPE_CLIMB:
                    position = follow(i, dt, speed, PhoneContext.climb());
                    break;
                case SHAPE_PAD_X:
                    position = follow(i, dt, speed, padX);
                    break;
                case SHAPE_PAD_Y:
                    position = follow(i, dt, speed, padY);
                    break;
                default:
                    position = (float) Math.sin(2 * Math.PI * phase[i]);
                    break;
            }
            phase[i] -= Math.floor(phase[i]);   // keep it in 0..1 (drift handles its own wrap)

            float span = p.toNorm(p.randMax) - p.toNorm(p.randMin);   // swing within the safe range
            next.put(p.id, position * ParamStore.get(DEPTH_ID[i]) * span);
        }

        Map<String, Float> previous = offsets;
        if (next.isEmpty() && previous.isEmpty()) {
            return;   // no movers running: nothing to send
        }
        offsets = next;
        for (String paramId : next.keySet()) {
            sink.send(paramId, output(Params.byId(paramId), ParamStore.get(paramId)));
        }
        for (String paramId : previous.keySet()) {
            if (!next.containsKey(paramId)) {   // mover switched off or retargeted: go back to the slider
                sink.send(paramId, ParamStore.get(paramId));
            }
        }
    }

    /** The value to give Pd for a parameter whose slider is at {@code base}. */
    static float output(Param p, float base) {
        Float offset = offsets.get(p.id);
        if (offset == null) {
            return base;
        }
        float baseNorm = p.toNorm(base);
        // Stay inside the safe range, but never fight a slider the user put outside it.
        float lo = Math.min(p.toNorm(p.randMin), baseNorm);
        float hi = Math.max(p.toNorm(p.randMax), baseNorm);
        return p.toValue(Math.max(lo, Math.min(hi, baseNorm + offset)));
    }

    /**
     * Eases mover {@code i} towards {@code target} (-1..1) so it reacts in a fraction of a second; a
     * higher "speed" reacts faster.
     */
    private static float follow(int i, double dt, float speedHz, float target) {
        double k = 1 - Math.exp(-dt * 2 * Math.PI * speedHz * 4);
        follower[i] += (float) ((target - follower[i]) * k);
        return follower[i];
    }

    /** Random drift: glide (cosine-eased) from one random position to the next, once per cycle. */
    private static float driftPosition(int i) {
        while (phase[i] >= 1) {
            phase[i] -= 1;
            driftFrom[i] = driftTo[i];
            driftTo[i] = randomPosition();
        }
        double ease = 0.5 - 0.5 * Math.cos(Math.PI * phase[i]);
        return (float) (driftFrom[i] + (driftTo[i] - driftFrom[i]) * ease);
    }

    /** Random jump: holds a position, then hops straight to a new random one, {@code speed} times a second. */
    private static float jumpPosition(int i) {
        while (phase[i] >= 1) {
            phase[i] -= 1;
            float next = randomPosition();
            for (int tries = 0; tries < 50 && Math.abs(next - driftTo[i]) < MIN_JUMP; tries++) {
                next = randomPosition();
            }
            driftTo[i] = next;
        }
        return driftTo[i];
    }

    private static float randomPosition() {
        return rng.nextFloat() * 2f - 1f;
    }
}
