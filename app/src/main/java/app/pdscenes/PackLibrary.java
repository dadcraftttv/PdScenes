// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import android.content.Context;
import android.media.MediaCodec;
import android.media.MediaExtractor;
import android.media.MediaFormat;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.RandomAccessFile;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;

/**
 * Stem packs kept in the app's private storage (files/packs/&lt;name&gt;/), imported from a zip or a folder. At import
 * every stem that isn't WAV (MP3, OGG, FLAC, M4A...) is decoded once with the phone's own decoders into a 16-bit
 * WAV next to it (Pd reads WAV), and each loop's length is checked against the pack's tempo.
 */
final class PackLibrary {

    private static final String DIR = "packs";
    private static final String PREFS = "pdscenes_packs";
    private static final String KEY_SELECTED = "selected";

    private PackLibrary() { }

    static File packsDir(Context context) {
        return new File(context.getFilesDir(), DIR);
    }

    /** One pack on the phone. */
    static final class Entry {
        final File dir;
        final StemPack pack;     // null if pack.txt can't be read
        final String problem;

        Entry(File dir, StemPack pack, String problem) {
            this.dir = dir;
            this.pack = pack;
            this.problem = problem;
        }

        String title() {
            return pack != null ? pack.title : dir.getName();
        }
    }

    static List<Entry> list(Context context) {
        List<Entry> out = new ArrayList<>();
        File[] dirs = packsDir(context).listFiles(f -> f.isDirectory() && !f.getName().startsWith("."));
        if (dirs == null) {
            return out;
        }
        Arrays.sort(dirs);
        for (File d : dirs) {
            out.add(read(d));
        }
        return out;
    }

    static Entry read(File dir) {
        try {
            String text = new String(readAll(new File(dir, StemPack.FILE)), StandardCharsets.UTF_8);
            return new Entry(dir, StemPack.parse(text, dir.getName()), null);
        } catch (IOException | IllegalArgumentException e) {
            return new Entry(dir, null, e.getMessage());
        }
    }

    /** The pack chosen to play with the built-in sound, or null (none, or it is gone or broken). */
    static Entry selected(Context context) {
        String name = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_SELECTED, null);
        if (name == null) {
            return null;
        }
        File d = new File(packsDir(context), name);
        if (!d.isDirectory()) {
            return null;
        }
        Entry e = read(d);
        return e.pack != null ? e : null;
    }

    static void select(Context context, String dirName) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(KEY_SELECTED, dirName).apply();
    }

    static void delete(Context context, Entry e) {
        SceneLibrary.deleteRecursively(e.dir);
        Entry sel = selected(context);
        if (sel == null || sel.dir.equals(e.dir)) {
            select(context, null);
        }
    }

    /** The playable file for a stem: its own WAV, or the WAV decoded from it at import. */
    static File playable(File dir, StemPack.Stem s) {
        File f = new File(dir, s.file);
        return isWav(s.file) ? f : new File(dir, decodedName(s.file));
    }

    private static boolean isWav(String name) {
        String n = name.toLowerCase(Locale.US);
        return n.endsWith(".wav") || n.endsWith(".wave");
    }

    private static String decodedName(String file) {
        return ".decoded-" + file.replace('/', '_') + ".wav";
    }

    /**
     * Installs the pack found in {@code staging} (pack.txt at its top or one folder down) under {@code packsDir},
     * decoding non-WAV stems. Returns the pack and its warnings (loops not a whole number of bars long...).
     */
    static Result install(File staging, String fallbackName, File packsDir) throws IOException {
        File root = new File(staging, StemPack.FILE).isFile() ? staging : null;
        File[] kids = staging.listFiles(File::isDirectory);
        if (root == null && kids != null) {
            for (File k : kids) {
                if (new File(k, StemPack.FILE).isFile()) {
                    root = k;
                    break;
                }
            }
        }
        if (root == null) {
            throw new IOException("No " + StemPack.FILE + " found. Is this a stem pack?");
        }
        String text = new String(readAll(new File(root, StemPack.FILE)), StandardCharsets.UTF_8);
        String name = SceneLibrary.folderName(root.equals(staging) ? fallbackName : root.getName());
        StemPack pack;
        try {
            pack = StemPack.parse(text, name);
        } catch (IllegalArgumentException e) {
            throw new IOException(e.getMessage());
        }
        Result r = new Result();
        double[] secsAll = new double[pack.stems.size()];
        int[] chansAll = new int[pack.stems.size()];
        int idx = 0;
        for (StemPack.Stem s : pack.stems) {
            File f = new File(root, s.file);
            if (!f.isFile()) {
                throw new IOException("The pack lists " + s.file + " but it isn't there");
            }
            File wav = isWav(s.file) ? f : new File(root, decodedName(s.file));
            if (!isWav(s.file)) {
                decode(f, wav);
            }
            double secs = wavSeconds(wav);
            secsAll[idx] = secs;
            chansAll[idx++] = wavChannels(wav);
            double want = pack.loopSeconds(s);
            if (secs <= 0) {
                throw new IOException(s.file + " can't be read as audio");
            }
            if (Math.abs(secs - want) > 0.01 * want + 0.005) {
                r.warnings.add(String.format(Locale.US, "%s is %.2f s long, but %d bars at %s BPM is %.2f s",
                        s.file, secs, s.bars, trim(pack.bpm), want));
            }
        }
        String tooLong = StemPack.tooLong(secsAll, chansAll);
        if (tooLong != null) {
            throw new IOException(tooLong);
        }
        File target = new File(packsDir, name);
        SceneLibrary.deleteRecursively(target);
        if (!packsDir.isDirectory() && !packsDir.mkdirs()) {
            throw new IOException("Cannot create " + packsDir);
        }
        if (!root.renameTo(target)) {
            throw new IOException("Could not store the pack");
        }
        r.entry = read(target);
        return r;
    }

    static final class Result {
        Entry entry;
        final List<String> warnings = new ArrayList<>();
    }

    private static String trim(float f) {
        return f == Math.rint(f) ? Long.toString((long) f) : Float.toString(f);
    }

    /** Length in seconds of a PCM WAV (from its header), or -1. */
    static double wavSeconds(File f) {
        double[] info = wavInfo(f);
        return info == null ? -1 : info[0];
    }

    /** Channels of a PCM WAV, or 2 if it can't be read (counted as stereo, the larger). */
    static int wavChannels(File f) {
        double[] info = wavInfo(f);
        return info == null ? 2 : (int) info[1];
    }

    /** {seconds, channels} of a PCM WAV from its header, or null. */
    private static double[] wavInfo(File f) {
        try (RandomAccessFile raf = new RandomAccessFile(f, "r")) {
            byte[] head = new byte[12];
            raf.readFully(head);
            if (!new String(head, 0, 4, StandardCharsets.US_ASCII).equals("RIFF")
                    || !new String(head, 8, 4, StandardCharsets.US_ASCII).equals("WAVE")) {
                return null;
            }
            int rate = 0, channels = 0, bits = 0;
            long data = -1;
            byte[] ch = new byte[8];
            while (raf.getFilePointer() + 8 <= raf.length()) {
                raf.readFully(ch);
                String id = new String(ch, 0, 4, StandardCharsets.US_ASCII);
                long size = ByteBuffer.wrap(ch, 4, 4).order(ByteOrder.LITTLE_ENDIAN).getInt() & 0xFFFFFFFFL;
                if (id.equals("fmt ")) {
                    byte[] fmt = new byte[(int) Math.min(size, 64)];
                    raf.readFully(fmt);
                    ByteBuffer b = ByteBuffer.wrap(fmt).order(ByteOrder.LITTLE_ENDIAN);
                    channels = b.getShort(2);
                    rate = b.getInt(4);
                    bits = b.getShort(14);
                    raf.seek(raf.getFilePointer() + size - fmt.length + (size & 1));
                } else if (id.equals("data")) {
                    data = size;
                    break;
                } else {
                    raf.seek(raf.getFilePointer() + size + (size & 1));
                }
            }
            if (rate <= 0 || channels <= 0 || bits <= 0 || data < 0) {
                return null;
            }
            return new double[]{data / (double) (channels * (bits / 8)) / rate, channels};
        } catch (IOException | RuntimeException e) {
            return null;
        }
    }

    private static final long DECODE_LIMIT_S = 60;

    /** Decodes any audio file the phone can play into a 16-bit PCM WAV (giving up after DECODE_LIMIT_S). */
    static void decode(File in, File out) throws IOException {
        MediaExtractor ex = new MediaExtractor();
        MediaCodec codec = null;
        try (FileOutputStream os = new FileOutputStream(out)) {
            ex.setDataSource(in.getPath());
            int track = -1;
            MediaFormat fmt = null;
            for (int t = 0; t < ex.getTrackCount(); t++) {
                MediaFormat f = ex.getTrackFormat(t);
                String mime = f.getString(MediaFormat.KEY_MIME);
                if (mime != null && mime.startsWith("audio/")) {
                    track = t;
                    fmt = f;
                    break;
                }
            }
            if (track < 0) {
                throw new IOException(in.getName() + " has no audio the phone can read");
            }
            ex.selectTrack(track);
            int rate = fmt.getInteger(MediaFormat.KEY_SAMPLE_RATE);
            int channels = fmt.getInteger(MediaFormat.KEY_CHANNEL_COUNT);
            codec = MediaCodec.createDecoderByType(fmt.getString(MediaFormat.KEY_MIME));
            codec.configure(fmt, null, null, 0);
            codec.start();
            os.write(new byte[44]);   // the header, filled in at the end
            long dataBytes = 0;
            MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
            boolean inputDone = false, outputDone = false;
            long started = System.nanoTime();
            while (!outputDone) {
                // a broken file can leave a decoder waiting forever: give up after DECODE_LIMIT_S
                if (System.nanoTime() - started > DECODE_LIMIT_S * 1_000_000_000L) {
                    throw new IOException("decoding took longer than " + DECODE_LIMIT_S + " seconds, the file may be damaged");
                }
                if (!inputDone) {
                    int ib = codec.dequeueInputBuffer(10000);
                    if (ib >= 0) {
                        ByteBuffer buf = codec.getInputBuffer(ib);
                        int n = buf == null ? -1 : ex.readSampleData(buf, 0);
                        if (n < 0) {
                            codec.queueInputBuffer(ib, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM);
                            inputDone = true;
                        } else {
                            codec.queueInputBuffer(ib, 0, n, ex.getSampleTime(), 0);
                            ex.advance();
                        }
                    }
                }
                int ob = codec.dequeueOutputBuffer(info, 10000);
                if (ob == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    MediaFormat of = codec.getOutputFormat();
                    rate = of.getInteger(MediaFormat.KEY_SAMPLE_RATE);
                    channels = of.getInteger(MediaFormat.KEY_CHANNEL_COUNT);
                } else if (ob >= 0) {
                    ByteBuffer buf = codec.getOutputBuffer(ob);
                    if (buf != null && info.size > 0) {
                        byte[] chunk = new byte[info.size];
                        buf.position(info.offset);
                        buf.get(chunk);
                        os.write(chunk);   // (16-bit PCM, the decoders' default output)
                        dataBytes += chunk.length;
                    }
                    codec.releaseOutputBuffer(ob, false);
                    if ((info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) {
                        outputDone = true;
                    }
                }
            }
            os.getChannel().position(0);
            os.write(wavHeader(rate, channels, dataBytes));
        } catch (IOException | RuntimeException e) {
            out.delete();
            throw new IOException("Could not decode " + in.getName() + ": " + e.getMessage(), e);
        } finally {
            if (codec != null) {
                try {
                    codec.stop();
                } catch (RuntimeException ignored) {
                    // already stopped
                }
                codec.release();
            }
            ex.release();
        }
    }

    static byte[] wavHeader(int rate, int channels, long dataBytes) {
        ByteBuffer b = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN);
        b.put("RIFF".getBytes(StandardCharsets.US_ASCII)).putInt((int) (36 + dataBytes));
        b.put("WAVE".getBytes(StandardCharsets.US_ASCII));
        b.put("fmt ".getBytes(StandardCharsets.US_ASCII)).putInt(16).putShort((short) 1).putShort((short) channels);
        b.putInt(rate).putInt(rate * channels * 2).putShort((short) (channels * 2)).putShort((short) 16);
        b.put("data".getBytes(StandardCharsets.US_ASCII)).putInt((int) dataBytes);
        return b.array();
    }

    /** Unpacks a zip into a fresh folder in {@code packsDir} (the caller installs, then deletes it). */
    static File unzipToStaging(InputStream zip, File packsDir) throws IOException {
        if (!packsDir.isDirectory() && !packsDir.mkdirs()) {
            throw new IOException("Cannot create " + packsDir);
        }
        File staging = SceneLibrary.newStaging(packsDir);
        SceneLibrary.unzip(zip, staging);
        return staging;
    }

    private static byte[] readAll(File f) throws IOException {
        try (InputStream in = new FileInputStream(f)) {
            byte[] buf = new byte[(int) Math.min(f.length(), 1 << 20)];
            int n = 0, r;
            while (n < buf.length && (r = in.read(buf, n, buf.length - n)) > 0) {
                n += r;
            }
            return Arrays.copyOf(buf, n);
        }
    }
}
