package app.pdscenes;

import java.util.Calendar;
import java.util.TimeZone;

/** Checks SceneEvents.timeValues (the list rj_time outputs). */
public class E {
    static int fails = 0;
    static void check(boolean ok, String msg) {
        System.out.println((ok ? "ok:   " : "FAIL: ") + msg);
        if (!ok) fails++;
    }
    public static void main(String[] a) {
        Calendar c = Calendar.getInstance(TimeZone.getTimeZone("America/New_York"));
        c.clear();
        c.set(2026, Calendar.OCTOBER, 7, 20, 1, 9);   // a Wednesday, daylight time (UTC-4)
        c.set(Calendar.MILLISECOND, 250);
        float[] t = SceneEvents.timeValues(c);
        check(t.length == 10, "ten values");
        check(t[0] == 2026 && t[1] == 10 && t[2] == 7, "year, month, day: " + t[0] + " " + t[1] + " " + t[2]);
        check(t[3] == 4, "Wednesday is day 4 of the week (Sunday = 1): " + t[3]);
        check(t[4] == 280, "day of year: " + t[4]);
        check(t[5] == -400, "UTC-4 is -400: " + t[5]);
        check(t[6] == 20 && t[7] == 1 && t[8] == 9 && t[9] == 250, "hour minute second ms");
        Calendar k = Calendar.getInstance(TimeZone.getTimeZone("Asia/Kolkata"));
        check(SceneEvents.timeValues(k)[5] == 530, "UTC+5:30 is 530");
        Calendar w = Calendar.getInstance(TimeZone.getTimeZone("America/St_Johns"));
        w.clear(); w.set(2026, Calendar.JANUARY, 15, 12, 0, 0);
        check(SceneEvents.timeValues(w)[5] == -330, "UTC-3:30 is -330: " + SceneEvents.timeValues(w)[5]);
        System.out.println(fails == 0 ? "ALL PASSED" : fails + " FAILED");
        if (fails != 0) System.exit(1);
    }
}
