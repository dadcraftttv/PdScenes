// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import java.util.Calendar;
import java.util.TimeZone;

/**
 * Answers the requests a scene sends to the player through {@code [s #pdparty]} (the way PdParty's
 * helper abstractions {@code rj_time}, {@code rj_compass} and {@code rj_loc} ask for data).
 */
final class SceneEvents {

    /** Pd receiver the helper abstractions send their requests to. */
    static final String REQUEST_RECEIVER = "#pdparty";
    /** Pd receiver {@code rj_time} listens on for the answer. */
    static final String TIME_RECEIVER = "#time";
    /** Pd receiver the helper {@code closebang} listens on; banged when a scene is closed. */
    static final String CLOSEBANG_RECEIVER = "#closebang";

    private SceneEvents() { }

    /**
     * The ten values {@code rj_time} outputs, in order: year, month (1-12), day of the month, day of the
     * week (1 = Sunday), day of the year, time zone as hours and minutes east of UTC (-400 is UTC-4,
     * 530 is UTC+5:30), hour (0-23), minute, second and millisecond (0-999).
     */
    static float[] timeValues(Calendar now) {
        int offsetMinutes = (now.get(Calendar.ZONE_OFFSET) + now.get(Calendar.DST_OFFSET)) / 60000;
        int sign = offsetMinutes < 0 ? -1 : 1;
        int tz = sign * ((Math.abs(offsetMinutes) / 60) * 100 + Math.abs(offsetMinutes) % 60);
        return new float[] {
                now.get(Calendar.YEAR),
                now.get(Calendar.MONTH) + 1,
                now.get(Calendar.DAY_OF_MONTH),
                now.get(Calendar.DAY_OF_WEEK),
                now.get(Calendar.DAY_OF_YEAR),
                tz,
                now.get(Calendar.HOUR_OF_DAY),
                now.get(Calendar.MINUTE),
                now.get(Calendar.SECOND),
                now.get(Calendar.MILLISECOND),
        };
    }

    static float[] timeValues() {
        return timeValues(Calendar.getInstance(TimeZone.getDefault()));
    }
}
