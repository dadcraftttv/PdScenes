// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.view.MotionEvent;
import android.view.View;

import java.io.File;

/**
 * The touch area for a scene: the scene's cover image with fingers reported the RjDj way. Scenes
 * see positions on a 320 x 320 grid laid over the image, and each finger gets a number starting at 1
 * (the lowest free one), with "down", "xy" (moved) and "up" events.
 */
final class ScenePad extends View {

    /** Receives touch events in scene coordinates. */
    interface Listener {
        void onTouch(String type, int finger, int x, int y);
    }

    static final String DOWN = "down";
    static final String MOVE = "xy";
    static final String UP = "up";
    static final int GRID = 320;

    private static final float NO_IMAGE_ASPECT = 0.7f;   // a plain pad is a bit wider than tall
    private static final float MIN_ASPECT = 0.5f;   // height / width limits for odd-shaped images
    private static final float MAX_ASPECT = 1.2f;
    private static final int MAX_IMAGE_PX = 1024;
    private static final int MAX_FINGERS = 10;
    static final float CORNER_DP = 8f;   // the bottom bar card uses the same corners

    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF imageRect = new RectF();
    private final Path clip = new Path();
    private Bitmap image;
    private File sceneDir;
    /** The scene's own pictures (rj_image), loaded once each; their size in the file, for the 320 grid. */
    private final java.util.Map<String, Bitmap> pictures = new java.util.HashMap<>();
    private final java.util.Map<String, int[]> pictureSize = new java.util.HashMap<>();
    private final Paint textPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private int drawnVersion = -1;
    /** Redraws when the scene changed what it shows (checked 30 times a second while on screen). */
    private final Runnable gfxWatch = new Runnable() {
        @Override
        public void run() {
            int v = SceneGraphics.SCENE.version();
            if (v != drawnVersion) {
                invalidate();
            }
            postDelayed(this, 33);
        }
    };
    private Listener listener;
    /** Android pointer id for each finger number - 1; -1 when that number is free. */
    private final int[] fingerPointer = new int[MAX_FINGERS];
    /** Where each held finger is, for the on-screen marker. */
    private final float[] fingerX = new float[MAX_FINGERS];
    private final float[] fingerY = new float[MAX_FINGERS];

    ScenePad(Context context) {
        super(context);
        java.util.Arrays.fill(fingerPointer, -1);
    }

    void setListener(Listener listener) {
        this.listener = listener;
    }

    /** Shows this scene's image (image.jpg, image.png or thumb.jpg), or a plain pad if it has none. */
    void setScene(SceneLibrary.Scene scene) {
        image = scene == null ? null : loadImage(scene.dir);
        sceneDir = scene == null ? null : scene.dir;
        pictures.clear();
        pictureSize.clear();
        requestLayout();
        invalidate();
    }

    @Override
    protected void onAttachedToWindow() {
        super.onAttachedToWindow();
        post(gfxWatch);
    }

    @Override
    protected void onDetachedFromWindow() {
        removeCallbacks(gfxWatch);
        super.onDetachedFromWindow();
    }

    /**
     * The scene's own images and texts (rj_image, rj_text) over its cover, on the same 320 x 320 grid as touches:
     * each centred on its position, an image at its file's size (one pixel = one grid step), turned and faded as
     * the scene says.
     */
    private void drawSceneGraphics(Canvas canvas) {
        drawnVersion = SceneGraphics.SCENE.version();
        float gx = imageRect.width() / GRID, gy = imageRect.height() / GRID;
        for (SceneGraphics.Item it : SceneGraphics.SCENE.snapshot()) {
            if (!it.showing()) {
                continue;
            }
            float cx = imageRect.left + it.x * gx, cy = imageRect.top + it.y * gy;
            canvas.save();
            canvas.rotate(it.rotate, cx, cy);
            if (it.image) {
                Bitmap b = picture(it.file);
                if (b != null) {
                    int[] size = pictureSize.get(it.file);
                    float w = size[0] * gx * it.scaleX, h = size[1] * gy * it.scaleY;
                    paint.setAlpha(Math.round(255 * it.alpha));
                    canvas.drawBitmap(b, null, new RectF(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), paint);
                    paint.setAlpha(255);
                }
            } else if (!it.text.isEmpty()) {
                textPaint.setTextAlign(Paint.Align.CENTER);
                textPaint.setTextSize(it.size * gx);
                textPaint.setColor(0xFFFFFFFF);
                textPaint.setAlpha(Math.round(255 * it.alpha));
                textPaint.setShadowLayer(3f, 0f, 1f, 0xCC000000);
                Paint.FontMetrics fm = textPaint.getFontMetrics();
                canvas.drawText(it.text, cx, cy - (fm.ascent + fm.descent) / 2, textPaint);
            }
            canvas.restore();
        }
    }

    /** A picture from the scene's folder (or its rj folder), loaded once; null if it can't be read. */
    private Bitmap picture(String name) {
        if (pictures.containsKey(name)) {
            return pictures.get(name);
        }
        Bitmap b = null;
        if (sceneDir != null && name != null) {
            for (File f : new File[]{new File(sceneDir, name), new File(new File(sceneDir, "rj"), name)}) {
                if (!f.isFile()) {
                    continue;
                }
                BitmapFactory.Options bounds = new BitmapFactory.Options();
                bounds.inJustDecodeBounds = true;
                BitmapFactory.decodeFile(f.getPath(), bounds);
                BitmapFactory.Options opts = new BitmapFactory.Options();
                opts.inSampleSize = sampleSize(Math.max(bounds.outWidth, bounds.outHeight));
                b = BitmapFactory.decodeFile(f.getPath(), opts);
                if (b != null) {
                    pictureSize.put(name, new int[]{bounds.outWidth, bounds.outHeight});
                    break;
                }
            }
        }
        pictures.put(name, b);
        return b;
    }

    private static Bitmap loadImage(File dir) {
        for (String name : new String[]{"image.jpg", "image.png", "thumb.jpg"}) {
            File f = new File(dir, name);
            if (!f.isFile()) {
                continue;
            }
            BitmapFactory.Options bounds = new BitmapFactory.Options();
            bounds.inJustDecodeBounds = true;
            BitmapFactory.decodeFile(f.getPath(), bounds);
            BitmapFactory.Options opts = new BitmapFactory.Options();
            opts.inSampleSize = sampleSize(Math.max(bounds.outWidth, bounds.outHeight));
            Bitmap b = BitmapFactory.decodeFile(f.getPath(), opts);
            if (b != null) {
                return b;
            }
        }
        return null;
    }

    /** Power-of-two shrink factor that brings the longest side to about MAX_IMAGE_PX. */
    static int sampleSize(int longestSide) {
        int size = 1;
        while (longestSide / (size * 2) >= MAX_IMAGE_PX) {
            size *= 2;
        }
        return size;
    }

    @Override
    protected void onMeasure(int widthSpec, int heightSpec) {
        int width = MeasureSpec.getSize(widthSpec);
        float aspect = NO_IMAGE_ASPECT;
        if (image != null) {
            aspect = Math.max(MIN_ASPECT, Math.min(MAX_ASPECT,
                    image.getHeight() / (float) image.getWidth()));
        }
        setMeasuredDimension(width, Math.round(width * aspect));
    }

    @Override
    protected void onDraw(Canvas canvas) {
        updateImageRect();
        float corner = getResources().getDisplayMetrics().density * CORNER_DP;
        paint.setStyle(Paint.Style.FILL);
        paint.setColor(0xFF1B1B1F);
        canvas.drawRect(0, 0, getWidth(), getHeight(), paint);
        // Everything inside the pad is clipped to rounded corners.
        clip.reset();
        clip.addRoundRect(imageRect, corner, corner, Path.Direction.CW);
        canvas.save();
        canvas.clipPath(clip);
        if (image != null) {
            canvas.drawBitmap(image, null, imageRect, paint);
        } else {
            paint.setColor(0xFF2E2E36);
            canvas.drawRect(imageRect, paint);
        }
        drawSceneGraphics(canvas);
        canvas.restore();
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(2f);
        paint.setColor(0x66FFFFFF);
        canvas.drawRoundRect(imageRect, corner, corner, paint);
        // A ring under every held finger, so presses are visibly registered.
        float radius = getResources().getDisplayMetrics().density * 28f;
        for (int i = 0; i < MAX_FINGERS; i++) {
            if (fingerPointer[i] >= 0) {
                paint.setStyle(Paint.Style.FILL);
                paint.setColor(0x55FFFFFF);
                canvas.drawCircle(fingerX[i], fingerY[i], radius, paint);
                paint.setStyle(Paint.Style.STROKE);
                paint.setStrokeWidth(4f);
                paint.setColor(0xFFFFFFFF);
                canvas.drawCircle(fingerX[i], fingerY[i], radius, paint);
            }
        }
    }

    /** The image is drawn as large as fits without stretching; touches map onto this rectangle. */
    private void updateImageRect() {
        float w = getWidth();
        float h = getHeight();
        float aspect = image == null ? NO_IMAGE_ASPECT : image.getHeight() / (float) image.getWidth();
        float drawW = Math.min(w, h / aspect);
        float drawH = drawW * aspect;
        float left = (w - drawW) / 2f;
        float top = (h - drawH) / 2f;
        imageRect.set(left, top, left + drawW, top + drawH);
    }

    @Override
    public boolean onTouchEvent(MotionEvent e) {
        updateImageRect();
        switch (e.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                // Keep the surrounding ScrollView from stealing the gesture.
                getParent().requestDisallowInterceptTouchEvent(true);
                press(e, 0);
                break;
            case MotionEvent.ACTION_POINTER_DOWN:
                press(e, e.getActionIndex());
                break;
            case MotionEvent.ACTION_MOVE:
                for (int i = 0; i < e.getPointerCount(); i++) {
                    int finger = fingerFor(e.getPointerId(i));
                    if (finger >= 0) {
                        send(MOVE, finger, e.getX(i), e.getY(i));
                    }
                }
                break;
            case MotionEvent.ACTION_POINTER_UP:
                release(e, e.getActionIndex());
                break;
            case MotionEvent.ACTION_UP:
                release(e, 0);
                break;
            case MotionEvent.ACTION_CANCEL:
                for (int i = 0; i < e.getPointerCount(); i++) {
                    release(e, i);
                }
                break;
            default:
                break;
        }
        return true;
    }

    private void press(MotionEvent e, int index) {
        float x = e.getX(index);
        float y = e.getY(index);
        if (!imageRect.contains(x, y)) {
            return;   // outside the image: not a scene touch
        }
        int finger = lowestFreeFinger();
        if (finger < 0) {
            return;
        }
        fingerPointer[finger] = e.getPointerId(index);
        send(DOWN, finger, x, y);
    }

    private void release(MotionEvent e, int index) {
        int finger = fingerFor(e.getPointerId(index));
        if (finger < 0) {
            return;
        }
        fingerPointer[finger] = -1;
        send(UP, finger, e.getX(index), e.getY(index));
    }

    private int fingerFor(int pointerId) {
        for (int i = 0; i < MAX_FINGERS; i++) {
            if (fingerPointer[i] == pointerId) {
                return i;
            }
        }
        return -1;
    }

    private int lowestFreeFinger() {
        for (int i = 0; i < MAX_FINGERS; i++) {
            if (fingerPointer[i] < 0) {
                return i;
            }
        }
        return -1;
    }

    private void send(String type, int finger, float px, float py) {
        fingerX[finger] = px;
        fingerY[finger] = py;
        invalidate();
        if (listener != null) {
            listener.onTouch(type, finger + 1,
                    toGrid(px, imageRect.left, imageRect.width()),
                    toGrid(py, imageRect.top, imageRect.height()));
        }
    }

    /** Pixel position to the 0..320 grid scenes expect (whole numbers, clamped to the image). */
    static int toGrid(float pixel, float start, float length) {
        int v = (int) ((pixel - start) / length * GRID);
        return Math.max(0, Math.min(GRID, v));
    }
}
