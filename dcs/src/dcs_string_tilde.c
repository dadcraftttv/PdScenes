/* dcs_string~: a plucked or bowed string (an extended Karplus-Strong loop) that rings whatever is fed into it.
 *
 * The input excites a delay loop tuned to the note: a short sound plucks it, a longer one bows it. Each pass
 * through the loop goes through a one-pole loss filter and a DC blocker. The loss filter is designed from two
 * decay times (Valimaki's one-pole loss filter): `decay` at the bottom and decay x 10^(2b - 2.5) at the top
 * (b = brightness: 0.3% of it dark, 3% in the middle, 32% bright), so high harmonics fade first like a real
 * string's, and brightness means the same at every pitch. The fundamental is then set to ring exactly `decay`,
 * and the tuning takes both filters' delay into account, so the note is in tune at any brightness.
 * Pd can't build this from its own objects: a feedback loop in a patch needs at least one 64-sample block,
 * which is too long above ~700 Hz.
 *
 *   [dcs_string~ <freq> <decay ms> <brightness>]
 *   inlets:  signal (the excitation), freq (Hz), decay (ms to fall 60 dB at the fundamental),
 *            brightness (0 dark .. 1 bright)
 *   outlet:  the string
 *   pluck <amp> [<position 0..1, default 0.3>]: plucks it like a finger: a triangle across one period (peaked at
 *            `position`, its overtones falling as 1/n^2, so the note itself leads) is added to the string, peaking
 *            at about `amp`. A sound fed in only rings what it has: a clap has nothing down at a low note.
 *
 * The input is scaled so that steady noise comes out about as loud whatever the decay (a long ring would
 * otherwise pile up), so a short pluck comes out quieter the longer the string rings.
 *
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 dadcraft (DadCraft Studios)
 */
#include "m_pd.h"
#include <math.h>
#include <string.h>

#define DLEN 8192            /* power of two: 20 Hz at 96 kHz */
#define MINFREQ 20.
#define DC_HZ 10.

static t_class *dcs_string_class;

typedef struct _dcs_string
{
    t_object x_obj;
    t_float x_f;
    t_float x_freq, x_decay, x_bright;          /* set by the inlets */
    t_float x_cfreq, x_cdecay, x_cbright;       /* what the coefficients were made for */
    double x_sr;
    t_sample x_dl[DLEN];
    int x_w;
    double x_delay;                             /* samples */
    t_sample x_b0, x_a1, x_ing, x_R;
    t_sample x_lp, x_hpx, x_hpy;
} t_dcs_string;

static void dcs_string_coefs(t_dcs_string *x)
{
    double sr = x->x_sr, f = x->x_freq, w, R, cw, sw, phase, mag, N, r, gpi, a1, b0, D;
    double decay = x->x_decay > 1 ? x->x_decay : 1, b = x->x_bright;
    if (f < MINFREQ) f = MINFREQ;
    if (f > sr / 6) f = sr / 6;
    if (b < 0) b = 0;
    if (b > 1) b = 1;
    w = 2 * M_PI * f / sr;
    cw = cos(w); sw = sin(w);
    N = sr / f;                                 /* the whole loop, in samples */
    r = pow(10., -3. * N / (sr * decay / 1000.));                       /* per pass, at the bottom */
    gpi = pow(10., -3. * N / (sr * decay * pow(10., 2 * b - 2.5) / 1000.));   /* per pass, at the top */
    a1 = (gpi - r) / (gpi + r);                 /* the loss filter: y = b0 x - a1 y[-1] */
    if (a1 < -0.9) a1 = -0.9;                   /* (a long low note: no darker than a pole at 0.9, ~760 Hz) */
    /* The loop's gain at DC is (DC gain / gain at the fundamental) x r: above 1 it would grow, and capping it
       would cut the note short. So when the filter is that dark, make it just bright enough (bisection). */
    if (hypot(1 + a1 * cw, a1 * sw) / (1 + a1) * r > 0.9999)
    {
        double lo = a1, hi = 0, mid;
        int it;
        for (it = 0; it < 40; it++)
        {
            mid = 0.5 * (lo + hi);
            if (hypot(1 + mid * cw, mid * sw) / (1 + mid) * r > 0.9999) lo = mid; else hi = mid;
        }
        a1 = hi;
    }
    R = 1 - 2 * M_PI * DC_HZ / sr;              /* the DC blocker: y = x - x[-1] + R y[-1] */
    /* their phase and gain at the fundamental (b0 aside) */
    phase = atan2(a1 * sw, 1 + a1 * cw)
          + atan2(sw, 1 - cw) - atan2(R * sw, 1 - R * cw);
    mag = 1 / hypot(1 + a1 * cw, a1 * sw)
        * hypot(1 - cw, sw) / hypot(1 - R * cw, R * sw);
    D = N + phase / w;                          /* (phase < 0: the filters' own delay) */
    if (D < 3) D = 3;
    if (D > DLEN - 4) D = DLEN - 4;
    b0 = r / mag;                               /* the fundamental falls 60 dB in `decay` */
    if (b0 > 0.9999 * (1 + a1)) b0 = 0.9999 * (1 + a1);   /* (gain at DC, the loop's most, below 1: stable) */
    x->x_delay = D;
    x->x_b0 = (t_sample)b0;
    x->x_a1 = (t_sample)a1;
    x->x_R = (t_sample)R;
    x->x_ing = (t_sample)sqrt(1 - r * r);
    x->x_cfreq = x->x_freq; x->x_cdecay = x->x_decay; x->x_cbright = x->x_bright;
}

static t_int *dcs_string_perform(t_int *w)
{
    t_dcs_string *x = (t_dcs_string *)(w[1]);
    t_sample *in = (t_sample *)(w[2]), *out = (t_sample *)(w[3]);
    int n = (int)(w[4]), i, wi = x->x_w;
    t_sample *dl = x->x_dl;
    t_sample b0, a1, ing, R, lp = x->x_lp, hpx = x->x_hpx, hpy = x->x_hpy, frac;
    int di;
    if (x->x_freq != x->x_cfreq || x->x_decay != x->x_cdecay || x->x_bright != x->x_cbright)
        dcs_string_coefs(x);
    b0 = x->x_b0; a1 = x->x_a1; ing = x->x_ing; R = x->x_R;
    di = (int)x->x_delay;
    frac = (t_sample)(x->x_delay - di);
    for (i = 0; i < n; i++)
    {
        /* read `delay` samples back: 4-point interpolation between x[wi-di] and x[wi-di-1] */
        t_sample a = dl[(wi - di + 1) & (DLEN - 1)], b = dl[(wi - di) & (DLEN - 1)],
            c = dl[(wi - di - 1) & (DLEN - 1)], d = dl[(wi - di - 2) & (DLEN - 1)];
        t_sample cminusb = c - b;
        t_sample y = b + frac * (cminusb - 0.1666667f * (1.f - frac) *
            ((d - a - 3.0f * cminusb) * frac + (d + 2.0f * a - 3.0f * b)));
        t_sample x0 = in[i] * ing, v;
        lp = b0 * y - a1 * lp;
        hpy = lp - hpx + R * hpy;
        hpx = lp;
        v = x0 + hpy;
        dl[wi] = v;
        wi = (wi + 1) & (DLEN - 1);
        out[i] = v;
    }
    if (PD_BIGORSMALL(lp)) lp = 0;
    if (PD_BIGORSMALL(hpx)) hpx = 0;
    if (PD_BIGORSMALL(hpy)) hpy = 0;
    x->x_lp = lp; x->x_hpx = hpx; x->x_hpy = hpy;
    x->x_w = wi;
    return (w + 5);
}

static void dcs_string_dsp(t_dcs_string *x, t_signal **sp)
{
    if (sp[0]->s_sr != x->x_sr)
    {
        x->x_sr = sp[0]->s_sr;
        dcs_string_coefs(x);
    }
    dsp_add(dcs_string_perform, 4, x, sp[0]->s_vec, sp[1]->s_vec, (t_int)sp[0]->s_n);
}

static void dcs_string_pluck(t_dcs_string *x, t_floatarg amp, t_floatarg pos)
{
    int P, k;
    double sum = 0, mean, peak;
    if (pos <= 0 || pos >= 1) pos = 0.3;
    if (x->x_freq != x->x_cfreq || x->x_decay != x->x_cdecay || x->x_bright != x->x_cbright)
        dcs_string_coefs(x);
    P = (int)(x->x_sr / (x->x_freq > MINFREQ ? x->x_freq : MINFREQ) + 0.5);
    if (P > DLEN - 4) P = DLEN - 4;
    if (P < 2) return;
    peak = pos * P;
    for (k = 0; k < P; k++)
        sum += k < peak ? k / peak : (P - k) / (P - peak);
    mean = sum / P;                             /* (taken away: no thump from a DC step) */
    /* the newest P samples come out over the next period */
    for (k = 0; k < P; k++)
    {
        double tri = (k < peak ? k / peak : (P - k) / (P - peak)) - mean;
        x->x_dl[(x->x_w - P + k) & (DLEN - 1)] += (t_sample)(amp * tri);
    }
}

static void dcs_string_clear(t_dcs_string *x)
{
    memset(x->x_dl, 0, sizeof(x->x_dl));
    x->x_lp = x->x_hpx = x->x_hpy = 0;
}

static void *dcs_string_new(t_floatarg freq, t_floatarg decay, t_floatarg bright)
{
    t_dcs_string *x = (t_dcs_string *)pd_new(dcs_string_class);
    x->x_freq = freq > 0 ? freq : 220;
    x->x_decay = decay > 0 ? decay : 1500;
    x->x_bright = bright > 0 ? bright : 0.5f;
    x->x_sr = sys_getsr() > 0 ? sys_getsr() : 44100;
    dcs_string_coefs(x);
    floatinlet_new(&x->x_obj, &x->x_freq);
    floatinlet_new(&x->x_obj, &x->x_decay);
    floatinlet_new(&x->x_obj, &x->x_bright);
    outlet_new(&x->x_obj, &s_signal);
    return (x);
}

void dcs_string_tilde_setup(void)
{
    dcs_string_class = class_new(gensym("dcs_string~"), (t_newmethod)dcs_string_new, 0,
        sizeof(t_dcs_string), CLASS_DEFAULT, A_DEFFLOAT, A_DEFFLOAT, A_DEFFLOAT, 0);
    CLASS_MAINSIGNALIN(dcs_string_class, t_dcs_string, x_f);
    class_addmethod(dcs_string_class, (t_method)dcs_string_dsp, gensym("dsp"), A_CANT, 0);
    class_addmethod(dcs_string_class, (t_method)dcs_string_clear, gensym("clear"), 0);
    class_addmethod(dcs_string_class, (t_method)dcs_string_pluck, gensym("pluck"), A_FLOAT, A_DEFFLOAT, 0);
}
