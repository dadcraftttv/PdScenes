// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import android.app.Dialog;
import android.graphics.Typeface;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/**
 * The first-run walkthrough (roadmap item 5, Samuel Oct 13): six short pages on a fresh install. Everything starts
 * off, so Start plays only the room, and the pages encourage switching things on one at a time. Reopened from
 * Setup, About. The host (MainActivity) supplies what the pages need from the phone.
 */
final class Walkthrough {

    /** What the pages ask of the screen behind them. */
    interface Host {
        boolean headphonesConnected();

        boolean micAllowed();

        void askForMic();

        void start();

        int dp(int v);
    }

    static final int PAGES = 6;
    private static final int PAGE_HEADPHONES = 1, PAGE_MIC = 2, PAGE_READY = 5;

    private final Dialog dialog;
    private final Host host;
    private final android.content.Context context;
    private final TextView title, body, status;
    private final Button action, back, next;
    private int page;

    Walkthrough(android.app.Activity activity, int theme, Host host) {
        this.context = activity;
        this.host = host;
        dialog = new Dialog(activity, theme);
        LinearLayout root = new LinearLayout(activity);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad = host.dp(24);
        root.setPadding(pad, pad, pad, host.dp(16));

        ScrollView scroll = new ScrollView(activity);
        LinearLayout content = new LinearLayout(activity);
        content.setOrientation(LinearLayout.VERTICAL);
        scroll.addView(content);
        root.addView(scroll, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        title = new TextView(activity);
        title.setTextSize(24);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setPadding(0, host.dp(24), 0, host.dp(16));
        content.addView(title);
        body = new TextView(activity);
        body.setTextSize(17);
        body.setLineSpacing(0, 1.15f);
        body.setAutoLinkMask(android.text.util.Linkify.EMAIL_ADDRESSES);
        content.addView(body);
        status = new TextView(activity);
        status.setTextSize(16);
        status.setTypeface(Typeface.DEFAULT_BOLD);
        status.setPadding(0, host.dp(16), 0, 0);
        content.addView(status);
        action = new Button(activity);
        action.setAllCaps(false);
        LinearLayout.LayoutParams ap = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        ap.topMargin = host.dp(16);
        content.addView(action, ap);

        // dots, then Back / Skip / Next, in thumb reach
        LinearLayout row = new LinearLayout(activity);
        row.setGravity(Gravity.CENTER_VERTICAL);
        back = new Button(activity, null, android.R.attr.borderlessButtonStyle);
        back.setAllCaps(false);
        back.setText(R.string.walk_back);
        back.setOnClickListener(v -> show(page - 1));
        Button skip = new Button(activity, null, android.R.attr.borderlessButtonStyle);
        skip.setAllCaps(false);
        skip.setText(R.string.walk_skip);
        skip.setOnClickListener(v -> dialog.dismiss());
        next = new Button(activity);
        next.setAllCaps(false);
        next.setOnClickListener(v -> {
            if (page == PAGES - 1) {
                dialog.dismiss();
            } else {
                show(page + 1);
            }
        });
        row.addView(back);
        row.addView(skip);
        View gap = new View(activity);
        row.addView(gap, new LinearLayout.LayoutParams(0, 1, 1f));
        row.addView(next);
        root.addView(row);

        dialog.setContentView(root);
        dialog.setOnShowListener(d -> {
            if (dialog.getWindow() != null) {
                dialog.getWindow().setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT);
            }
        });
    }

    void open() {
        show(0);
        dialog.show();
    }

    boolean isShowing() {
        return dialog.isShowing();
    }

    /** Called once a second and after the mic question: the live lines (headphones, permission) catch up. */
    void refresh() {
        if (dialog.isShowing()) {
            show(page);
        }
    }

    private static final int[] TITLES = {R.string.walk_t0, R.string.walk_t1, R.string.walk_t2, R.string.walk_t3,
            R.string.walk_t4, R.string.walk_t5};
    private static final int[] BODIES = {R.string.walk_b0, R.string.walk_b1, R.string.walk_b2, R.string.walk_b3,
            R.string.walk_b4, R.string.walk_b5};

    private void show(int p) {
        page = Math.max(0, Math.min(PAGES - 1, p));
        title.setText(TITLES[page]);
        body.setText(context.getString(BODIES[page]));
        back.setVisibility(page == 0 ? View.INVISIBLE : View.VISIBLE);
        next.setText(page == PAGES - 1 ? context.getString(R.string.walk_done)
                : context.getString(R.string.walk_next, page + 1, PAGES));
        status.setVisibility(View.GONE);
        action.setVisibility(View.GONE);
        if (page == PAGE_HEADPHONES) {
            status.setVisibility(View.VISIBLE);
            status.setText(host.headphonesConnected() ? R.string.walk_phones_yes : R.string.walk_phones_no);
        } else if (page == PAGE_MIC) {
            status.setVisibility(View.VISIBLE);
            boolean allowed = host.micAllowed();
            status.setText(allowed ? R.string.walk_mic_yes : R.string.walk_mic_no);
            if (!allowed) {
                action.setVisibility(View.VISIBLE);
                action.setText(R.string.walk_mic_allow);
                action.setOnClickListener(v -> host.askForMic());
            }
        } else if (page == PAGE_READY) {
            action.setVisibility(View.VISIBLE);
            action.setText(R.string.start);
            action.setOnClickListener(v -> {
                dialog.dismiss();
                host.start();
            });
        }
    }
}
