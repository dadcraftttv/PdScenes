/* dcs_yin.h: a light YIN pitch detector shared by dcs_pitch~ and dcs_shift~.
 *
 * The signal is low-passed (two one-poles) as it arrives and kept in a ring. To analyse, it is read at about 11 kHz
 * (every D-th sample), YIN's cumulative mean normalised difference picks the period there (a 25 ms window, 60 Hz
 * up to ~3.5 kHz), and the period is then refined at the full rate over a few lags around it. Much cheaper than
 * sigmund~'s FFT and peak analysis, and all it answers is "which note, and how sure".
 *
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 dadcraft (DadCraft Studios)
 */
#ifndef DCS_YIN_H
#define DCS_YIN_H
#include <math.h>
#include <string.h>

#define YIN_RING 16384          /* power of two: ~340 ms at 48 kHz, enough for any window */
#define YIN_RATE 11025.         /* the analysis rate, about */
#define YIN_WIN_MS 25.
#define YIN_FMIN 60.
#define YIN_THRESH 0.15         /* the first dip under this is the period (YIN's absolute threshold) */
#define YIN_VOICED 0.3          /* ...and it counts as a pitch under this */
#define YIN_MAXLAG 512

typedef struct _dcs_yin
{
    float ring[YIN_RING];       /* the low-passed input, full rate */
    int w;                      /* next write index */
    double lp1, lp2, lpk;
    double sr;
    int D;                      /* read every D-th sample to analyse */
    float dec[2 * YIN_MAXLAG + 2048];
    float d[YIN_MAXLAG + 2];
} t_dcs_yin;

static void dcs_yin_init(t_dcs_yin *y, double sr)
{
    double fc;
    memset(y, 0, sizeof(*y));
    y->sr = sr;
    y->D = (int)floor(sr / YIN_RATE + 0.5);
    if (y->D < 1) y->D = 1;
    fc = 0.4 * sr / y->D;                                    /* anti-alias for the decimated read */
    y->lpk = exp(-2 * M_PI * fc / sr);
}

static inline void dcs_yin_write(t_dcs_yin *y, float s)
{
    y->lp1 = s + (y->lp1 - s) * y->lpk;
    y->lp2 = y->lp1 + (y->lp2 - y->lp1) * y->lpk;
    y->ring[y->w] = (float)y->lp2;
    y->w = (y->w + 1) & (YIN_RING - 1);
}

/* the full-rate difference at lag L over n samples ending at the newest (every 2nd sample) */
static double dcs_yin_diff(const t_dcs_yin *y, int L, int n)
{
    int j, start = y->w - n - L;
    double s = 0;
    for (j = 0; j < n; j += 2)
    {
        double a = y->ring[(start + j) & (YIN_RING - 1)] - y->ring[(start + j + L) & (YIN_RING - 1)];
        s += a * a;
    }
    return s;
}

/* Analyse the newest window. Returns the period in full-rate samples (0 = no pitch) and sets *sure (0..1). */
static double dcs_yin_period(t_dcs_yin *y, double *sure)
{
    double rate = y->sr / y->D, cum = 0, best, ap;
    int D = y->D, W = (int)(YIN_WIN_MS * rate / 1000), T = (int)(rate / YIN_FMIN), n = W + T, i, j, tau = -1, L0, L;
    double dl, dm, dr, tf, Lf, P;
    if (T > YIN_MAXLAG) T = YIN_MAXLAG;
    if (n > (int)(sizeof(y->dec) / sizeof(float))) n = sizeof(y->dec) / sizeof(float);
    for (i = 0; i < n; i++)
        y->dec[i] = y->ring[(y->w - (n - i) * D) & (YIN_RING - 1)];
    /* the difference at each lag (every 2nd sample of the window), stopping once the dip under the threshold has
       bottomed out: a voice at 150 Hz needs well under half the lags */
    y->d[0] = 1;
    for (i = 1; i <= T; i++)
    {
        double s = 0;
        for (j = 0; j < W; j += 2)
        {
            double a = y->dec[j] - y->dec[j + i];
            s += a * a;
        }
        cum += s;
        y->d[i] = (float)(cum > 0 ? s * i / cum : 1);
        if (tau < 0 && i >= 3 && y->d[i - 1] < YIN_THRESH && y->d[i] >= y->d[i - 1])
        {
            tau = i - 1;
            if (i < T) { T = i + 1; break; }               /* (one more lag for the parabola) */
        }
    }
    if (tau >= 0 && tau + 1 > T) tau = -1;
    if (tau >= 0)
    {
        double s = 0;                                       /* d[tau + 1] for the parabola */
        for (j = 0; j < W; j += 2)
        {
            double a = y->dec[j] - y->dec[j + tau + 1];
            s += a * a;
        }
        y->d[tau + 1] = (float)(s * (tau + 1) / (cum + s));
        T = tau + 2;
    }
    if (tau < 0)
    {
        best = 1e9;
        for (i = 2; i < T; i++)
            if (y->d[i] < best) { best = y->d[i]; tau = i; }
    }
    ap = y->d[tau];
    *sure = ap < 1 ? 1 - ap : 0;
    if (ap > YIN_VOICED || tau < 2 || tau >= T - 1)
        return 0;
    dl = y->d[tau - 1]; dm = y->d[tau]; dr = y->d[tau + 1];
    tf = tau + (dl - dr) / (2 * (dl - 2 * dm + dr) + 1e-12) ;
    if (fabs(tf - tau) > 1) tf = tau;
    /* refine at the full rate around tau x D */
    L0 = (int)floor(tf * D + 0.5);
    {
        int lo = L0 - D / 2 - 1, hi = L0 + D / 2 + 1, nf = W * D / 2, bestL = L0;
        double bd = 1e30, v[3];
        if (lo < 2) lo = 2;
        for (L = lo; L <= hi; L++)
        {
            double s = dcs_yin_diff(y, L, nf);
            if (s < bd) { bd = s; bestL = L; }
        }
        if (bestL <= lo || bestL >= hi)
            return tf * D;
        v[0] = dcs_yin_diff(y, bestL - 1, nf); v[1] = bd; v[2] = dcs_yin_diff(y, bestL + 1, nf);
        Lf = bestL + (v[0] - v[2]) / (2 * (v[0] - 2 * v[1] + v[2]) + 1e-30);
        P = fabs(Lf - bestL) <= 1 ? Lf : bestL;
    }
    return P;
}

/* the level of the newest n full-rate samples of the original (unfiltered) signal is the caller's job */
#endif
