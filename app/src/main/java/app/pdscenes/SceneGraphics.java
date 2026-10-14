// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * What a scene shows on the scene pad: its [rj_image] and [rj_text] objects (roadmap item 9). Each sends
 * {@code rj_gfx <id> <command> ...}: at load "image <file>" or "text <words>", then visible, move x y (its centre,
 * on the 320 x 320 grid), alpha, rotate, scale sx sy, size, text. Images start hidden and texts shown (as on RjDj),
 * both in the middle. Fed from Pd's thread, drawn by ScenePad. Pure logic (test G).
 */
final class SceneGraphics {

    /** One image or text. Read on the screen's thread from a {@link #snapshot()}, never changed there. */
    static final class Item {
        final boolean image;
        final String file;      // images: the file name in the scene folder
        String text = "";       // texts
        float x = 160, y = 160;
        boolean visible;
        float alpha = 1, rotate, scaleX = 1, scaleY = 1;
        float size = 16;        // texts: points on the 320 grid

        Item(boolean image, String file) {
            this.image = image;
            this.file = file;
            this.visible = !image;
        }

        Item copy() {
            Item c = new Item(image, file);
            c.text = text;
            c.x = x;
            c.y = y;
            c.visible = visible;
            c.alpha = alpha;
            c.rotate = rotate;
            c.scaleX = scaleX;
            c.scaleY = scaleY;
            c.size = size;
            return c;
        }

        /** Shown and on the pad (scenes hide things by moving them far off, e.g. to 500 500). */
        boolean showing() {
            return visible && alpha > 0 && x > -160 && x < 480 && y > -160 && y < 480;
        }
    }

    static final SceneGraphics SCENE = new SceneGraphics();

    private final Map<Float, Item> items = new LinkedHashMap<>();   // drawn in the order they appeared
    private volatile int version;

    /** One message from Pd: {id, command, args...}. Unknown commands and ids are ignored. */
    synchronized void apply(Object[] args) {
        if (args.length < 2 || !(args[0] instanceof Float) || !(args[1] instanceof String)) {
            return;
        }
        Float id = (Float) args[0];
        String cmd = (String) args[1];
        Item it = items.get(id);
        if ("image".equals(cmd)) {
            if (args.length > 2) {
                items.put(id, new Item(true, word(args[2])));
                version++;
            }
            return;
        }
        if ("text".equals(cmd)) {
            if (it == null) {
                it = new Item(false, null);
                items.put(id, it);
            }
            it.text = join(args, 2);
            version++;
            return;
        }
        if (it == null) {
            return;
        }
        switch (cmd) {
            case "visible":
            case "show":
                it.visible = num(args, 2, 1) != 0;
                break;
            case "move":
            case "pos":
                it.x = num(args, 2, it.x);
                it.y = num(args, 3, it.y);
                break;
            case "alpha":
                it.alpha = Math.max(0, Math.min(1, num(args, 2, 1)));
                break;
            case "rotate":
                it.rotate = num(args, 2, 0);
                break;
            case "scale":
                it.scaleX = num(args, 2, 1);
                it.scaleY = num(args, 3, it.scaleX);
                break;
            case "size":
                it.size = Math.max(1, num(args, 2, it.size));
                break;
            default:
                return;
        }
        version++;
    }

    /** Copies of everything, in drawing order. */
    synchronized List<Item> snapshot() {
        List<Item> out = new ArrayList<>(items.size());
        for (Item it : items.values()) {
            out.add(it.copy());
        }
        return out;
    }

    /** A scene stopped or another one opened. */
    synchronized void clear() {
        if (!items.isEmpty()) {
            items.clear();
            version++;
        }
    }

    /** Changes whenever something on screen changed (the pad redraws then). */
    int version() {
        return version;
    }

    private static float num(Object[] a, int i, float fallback) {
        return i < a.length && a[i] instanceof Float ? (Float) a[i] : fallback;
    }

    /** Pd's way of writing a number: 3 not 3.0. */
    static String word(Object o) {
        if (o instanceof Float) {
            float f = (Float) o;
            return f == Math.rint(f) && Math.abs(f) < 1e9 ? Long.toString((long) f) : Float.toString(f);
        }
        return String.valueOf(o);
    }

    private static String join(Object[] a, int from) {
        StringBuilder sb = new StringBuilder();
        for (int i = from; i < a.length; i++) {
            sb.append(i > from ? " " : "").append(word(a[i]));
        }
        return sb.toString();
    }
}
