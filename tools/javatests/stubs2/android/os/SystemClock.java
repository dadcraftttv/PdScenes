package android.os; public class SystemClock { public static long elapsedRealtimeNanos(){return System.nanoTime();} public static long uptimeMillis(){return System.nanoTime()/1000000;} }
