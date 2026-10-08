package app.pdscenes;
public class C {
    static int fails = 0;
    static void check(boolean c, String m) { System.out.println((c ? "ok:   " : "FAIL: ") + m); if (!c) fails++; }
    static boolean near(float a, float b) { float d = Math.abs(a - b) % 360f; return Math.min(d, 360f - d) < 1f; }
    public static void main(String[] a) {
        float[] flat = {0, 0, 9.8f};             // phone face up
        float[][] cases = {{0, 20, -40, 0}, {-20, 0, -40, 90}, {0, -20, -40, 180}, {20, 0, -40, 270}, {14.14f, 14.14f, -40, 315}};
        for (float[] c : cases) {
            float d = SensorInput.compassDegrees(flat, new float[]{c[0], c[1], c[2]});
            check(near(d, c[3]), "flat phone, field " + c[0] + "," + c[1] + " -> " + d + " (want " + c[3] + ")");
        }
        check(SensorInput.compassDegrees(new float[]{0, 0, 0}, new float[]{1, 2, 3}) == 0f, "free fall gives 0, no NaN");
        // Tilted 30 degrees about the x axis: the heading of the top edge should not change.
        float s = (float) Math.sin(Math.toRadians(30)), c = (float) Math.cos(Math.toRadians(30));
        float[] g = {0, -9.8f * s, 9.8f * c};
        float[] m = {0, 20 * c + 40 * s, 20 * s * -1 - 40 * c};   // north field rotated into the tilted frame (top edge toward north)
        System.out.println("tilted: " + SensorInput.compassDegrees(g, m));
        System.exit(fails == 0 ? 0 : 1);
    }
}
