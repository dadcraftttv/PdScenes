/* dcs_reverb~: a stereo Freeverb-style reverb (parallel low-passed combs into series all-passes), in one object.
 *
 * The same algorithm a patch can build from delwrite~ / delread~ / lop~ / *~ objects, sample for sample (delays
 * rounded as delread~ rounds them, the damping as lop~ computes it), at a fraction of the cost: one object
 * instead of about a hundred.
 *
 *   [dcs_reverb~ <right ear extra ms> <number of combs> <comb ms ...> <all-pass ms ...>]
 *   inlets:  signal in (mono); signal: comb feedback (0..1); `tone <Hz>`: the damping low-pass in the combs
 *   outlets: left, right (the right ear's delays are `extra` ms longer, so the two ears differ)
 *   Comb:     y = delay(D)[w]; w = in + feedback x lowpass(y). The combs' outputs are summed.
 *   All-pass: r = delay(D)[w]; w = x + 0.5 r; out = r - 0.5 w.
 *
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 dadcraft (DadCraft Studios)
 */
#include "m_pd.h"
#include <math.h>
#include <string.h>

#define MAXCOMBS 16
#define MAXALLP 8

static t_class *dcs_reverb_class;

typedef struct _line
{
    t_sample *buf;
    int len, w;
    t_sample lp;                /* the comb's low-pass state */
} t_line;

typedef struct _dcs_reverb
{
    t_object x_obj;
    t_float x_f;
    int x_nc, x_na;
    double x_extra, x_cms[MAXCOMBS], x_ams[MAXALLP];
    t_line x_c[2][MAXCOMBS], x_a[2][MAXALLP];
    double x_sr;
    t_float x_tone;
    t_sample x_coef;
    t_outlet *x_outr;
} t_dcs_reverb;

static void line_alloc(t_line *l, int len)
{
    if (l->buf) freebytes(l->buf, l->len * sizeof(t_sample));
    if (len < 1) len = 1;
    l->buf = (t_sample *)getbytes(len * sizeof(t_sample));
    l->len = len;
    l->w = 0;
    l->lp = 0;
}

static void dcs_reverb_coef(t_dcs_reverb *x)
{
    t_sample c = (t_sample)(x->x_tone * (2 * 3.14159265358979 / x->x_sr));
    x->x_coef = c > 1 ? 1 : (c < 0 ? 0 : c);
}

/* Every delay is at least a block long, so each line can run a whole block at once (nothing it reads in this block
   was written in this block): one tight loop per line instead of all of them per sample. */
#define MAXBLOCK 8192
static t_int *dcs_reverb_perform(t_int *w)
{
    t_dcs_reverb *x = (t_dcs_reverb *)(w[1]);
    t_sample *in = (t_sample *)(w[2]), *fb = (t_sample *)(w[3]);
    t_sample *out[2] = { (t_sample *)(w[4]), (t_sample *)(w[5]) };
    int n = (int)(w[6]), i, s, k;
    t_sample coef = x->x_coef, keep = 1 - coef;
    t_sample acc[MAXBLOCK], vin[MAXBLOCK], vfb[MAXBLOCK];
    if (n > MAXBLOCK) n = MAXBLOCK;
    memcpy(vin, in, n * sizeof(t_sample));                  /* (in and out may share memory) */
    memcpy(vfb, fb, n * sizeof(t_sample));
    for (s = 0; s < 2; s++)
    {
        memset(acc, 0, n * sizeof(t_sample));
        for (k = 0; k < x->x_nc; k++)
        {
            t_line *l = &x->x_c[s][k];
            t_sample *buf = l->buf, lp = l->lp;
            int wi = l->w, len = l->len;
            for (i = 0; i < n; i++)
            {
                t_sample y = buf[wi];
                lp = coef * y + keep * lp;
                buf[wi] = vin[i] + vfb[i] * lp;
                if (++wi >= len) wi = 0;
                acc[i] += y;
            }
            if (PD_BIGORSMALL(lp)) lp = 0;
            l->lp = lp; l->w = wi;
        }
        for (k = 0; k < x->x_na; k++)
        {
            t_line *l = &x->x_a[s][k];
            t_sample *buf = l->buf;
            int wi = l->w, len = l->len;
            for (i = 0; i < n; i++)
            {
                t_sample r = buf[wi], wv = acc[i] + 0.5f * r;
                buf[wi] = wv;
                if (++wi >= len) wi = 0;
                acc[i] = r - 0.5f * wv;
            }
            l->w = wi;
        }
        memcpy(out[s], acc, n * sizeof(t_sample));
    }
    return (w + 7);
}

static void dcs_reverb_dsp(t_dcs_reverb *x, t_signal **sp)
{
    if (sp[0]->s_sr != x->x_sr)
    {
        int s, k;
        x->x_sr = sp[0]->s_sr;
        for (s = 0; s < 2; s++)
        {
            double extra = s ? x->x_extra : 0;
            for (k = 0; k < x->x_nc; k++)                   /* (rounded as delread~ rounds) */
                line_alloc(&x->x_c[s][k], (int)(0.5 + x->x_sr * 0.001 * (x->x_cms[k] + extra)));
            for (k = 0; k < x->x_na; k++)
                line_alloc(&x->x_a[s][k], (int)(0.5 + x->x_sr * 0.001 * (x->x_ams[k] + extra)));
        }
        dcs_reverb_coef(x);
    }
    dsp_add(dcs_reverb_perform, 6, x, sp[0]->s_vec, sp[1]->s_vec, sp[2]->s_vec, sp[3]->s_vec, (t_int)sp[0]->s_n);
}

static void dcs_reverb_tone(t_dcs_reverb *x, t_floatarg f)
{
    x->x_tone = f;
    if (x->x_sr > 0) dcs_reverb_coef(x);
}

static void dcs_reverb_clear(t_dcs_reverb *x)
{
    int s, k;
    for (s = 0; s < 2; s++)
    {
        for (k = 0; k < x->x_nc; k++)
            memset(x->x_c[s][k].buf, 0, x->x_c[s][k].len * sizeof(t_sample)), x->x_c[s][k].lp = 0;
        for (k = 0; k < x->x_na; k++)
            memset(x->x_a[s][k].buf, 0, x->x_a[s][k].len * sizeof(t_sample));
    }
}

static void *dcs_reverb_new(t_symbol *sel, int argc, t_atom *argv)
{
    t_dcs_reverb *x = (t_dcs_reverb *)pd_new(dcs_reverb_class);
    int k;
    x->x_extra = argc > 0 ? atom_getfloat(argv) : 0;
    x->x_nc = argc > 1 ? (int)atom_getfloat(argv + 1) : 0;
    if (x->x_nc > MAXCOMBS) x->x_nc = MAXCOMBS;
    if (x->x_nc < 0 || argc < 2 + x->x_nc) x->x_nc = 0;
    for (k = 0; k < x->x_nc; k++)
        x->x_cms[k] = atom_getfloat(argv + 2 + k);
    x->x_na = argc - 2 - x->x_nc;
    if (x->x_na > MAXALLP) x->x_na = MAXALLP;
    if (x->x_na < 0) x->x_na = 0;
    for (k = 0; k < x->x_na; k++)
        x->x_ams[k] = atom_getfloat(argv + 2 + x->x_nc + k);
    if (!x->x_nc)
        pd_error(x, "dcs_reverb~: give it <right extra ms> <number of combs> <comb ms ...> <all-pass ms ...>");
    x->x_tone = 6000;
    x->x_sr = 0;
    inlet_new(&x->x_obj, &x->x_obj.ob_pd, &s_signal, &s_signal);
    outlet_new(&x->x_obj, &s_signal);
    x->x_outr = outlet_new(&x->x_obj, &s_signal);
    return (x);
}

static void dcs_reverb_free(t_dcs_reverb *x)
{
    int s, k;
    for (s = 0; s < 2; s++)
    {
        for (k = 0; k < MAXCOMBS; k++)
            if (x->x_c[s][k].buf) freebytes(x->x_c[s][k].buf, x->x_c[s][k].len * sizeof(t_sample));
        for (k = 0; k < MAXALLP; k++)
            if (x->x_a[s][k].buf) freebytes(x->x_a[s][k].buf, x->x_a[s][k].len * sizeof(t_sample));
    }
}

void dcs_reverb_tilde_setup(void)
{
    dcs_reverb_class = class_new(gensym("dcs_reverb~"), (t_newmethod)dcs_reverb_new,
        (t_method)dcs_reverb_free, sizeof(t_dcs_reverb), CLASS_DEFAULT, A_GIMME, 0);
    CLASS_MAINSIGNALIN(dcs_reverb_class, t_dcs_reverb, x_f);
    class_addmethod(dcs_reverb_class, (t_method)dcs_reverb_dsp, gensym("dsp"), A_CANT, 0);
    class_addmethod(dcs_reverb_class, (t_method)dcs_reverb_tone, gensym("tone"), A_FLOAT, 0);
    class_addmethod(dcs_reverb_class, (t_method)dcs_reverb_clear, gensym("clear"), 0);
}
