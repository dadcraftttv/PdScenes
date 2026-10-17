/* dcs_shift~: a pitch shifter that keeps a voice's own tone colour (PSOLA).
 *
 * A plain grain shifter replays the sound faster or slower, so its formants (the tone colour that makes a voice
 * sound like that person) move with the pitch: up a fifth sounds like a chipmunk. This one tracks the pitch (YIN,
 * dcs_yin.h, or the pitch you give it) and cuts grains one period apart, two periods long, exactly in step with
 * the waveform, then lays them down closer together (higher) or further apart (lower). Each grain keeps its
 * shape, so the tone colour stays where it was, and grains in step don't beat against each other (no warble).
 * Sounds with no clear pitch (breath, noise, a room) are shifted with 8 ms grains instead.
 *
 *   [dcs_shift~ <semitones>]
 *   inlet:   signal; `semi <semitones>`; `freq <Hz>` (the pitch, if you know it; 0 = find it)
 *   outlet:  the shifted signal, 30 ms late (the grains need what follows them)
 *
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 dadcraft (DadCraft Studios)
 */
#include "m_pd.h"
#include "dcs_yin.h"

#define BUF 16384               /* power of two */
#define LAT_MS 30.
#define HOP_MS 10.              /* how often the pitch is looked for */
#define NOISE_MS 8.             /* the "period" used for sounds with no pitch */
#define HOLD_MS 60.             /* a pitch is kept this long through a blip of no pitch */
#define MAXGRAINS 24
#define HANNLEN 1024

static t_class *dcs_shift_class;
static float shift_hann[HANNLEN + 1];

typedef struct _grain
{
    double start;               /* where in the buffer (absolute sample count) */
    double len, pos, gain;
} t_grain;

typedef struct _dcs_shift
{
    t_object x_obj;
    t_float x_f;
    t_dcs_yin x_yin;
    float x_buf[BUF];
    double x_now;               /* samples written so far */
    double x_semi, x_freq;
    double x_P, x_lastvoiced;   /* current period (samples), when a pitch was last found */
    double x_nextmark, x_lasta;
    int x_hopcount;
    t_grain x_g[MAXGRAINS];
} t_dcs_shift;

static inline float shift_read(const float *b, double p)
{
    long i = (long)floor(p);
    float f = (float)(p - i), a = b[i & (BUF - 1)], c = b[(i + 1) & (BUF - 1)];
    return a + f * (c - a);
}

static inline float shift_win(double ph)
{
    double p = ph * HANNLEN;
    int i = (int)p;
    if (i < 0 || i >= HANNLEN) return 0;
    return shift_hann[i] + (float)(p - i) * (shift_hann[i + 1] - shift_hann[i]);
}

static void dcs_shift_spawn(t_dcs_shift *x)
{
    double sr = x->x_yin.sr, P = x->x_P, r = pow(2, x->x_semi / 12.), S = P / r;
    double lat = LAT_MS * sr / 1000, target = x->x_now - lat, a, L;
    int k;
    /* the analysis point: whole periods on from the last one (in step), as near as can be to `target` */
    if (x->x_lasta > 0 && fabs(target - x->x_lasta) < 8 * P)
        a = x->x_lasta + P * floor((target - x->x_lasta) / P + 0.5);
    else
        a = target;
    L = 2 * (P > S ? P : S);
    if (L > 2 * lat - 2) L = 2 * lat - 2;                    /* (all of it must have arrived) */
    if (a + L / 2 > x->x_now - 1) a = x->x_now - 1 - L / 2;
    x->x_lasta = a;
    for (k = 0; k < MAXGRAINS; k++)
        if (x->x_g[k].len <= 0)
        {
            x->x_g[k].start = a - L / 2;
            x->x_g[k].len = L;
            x->x_g[k].pos = 0;
            x->x_g[k].gain = 2 * S / L;                       /* Hann grains L long, S apart, add up to L / 2S */
            break;
        }
    x->x_nextmark += S;
}

static t_int *dcs_shift_perform(t_int *w)
{
    t_dcs_shift *x = (t_dcs_shift *)(w[1]);
    t_sample *in = (t_sample *)(w[2]), *out = (t_sample *)(w[3]);
    int n = (int)(w[4]), i, k;
    double sr = x->x_yin.sr, hop = HOP_MS * sr / 1000, noise = NOISE_MS * sr / 1000, hold = HOLD_MS * sr / 1000;
    for (i = 0; i < n; i++)
    {
        float s = in[i], o = 0;
        x->x_buf[(long)x->x_now & (BUF - 1)] = s;
        dcs_yin_write(&x->x_yin, s);
        x->x_now += 1;
        if (++x->x_hopcount >= hop)
        {
            double sure, P = x->x_freq > 0 ? sr / x->x_freq : dcs_yin_period(&x->x_yin, &sure);
            x->x_hopcount = 0;
            if (P > 0)
                x->x_P = P, x->x_lastvoiced = x->x_now;
            else if (x->x_now - x->x_lastvoiced > hold)
                x->x_P = noise;
        }
        if (x->x_now >= x->x_nextmark)
            dcs_shift_spawn(x);
        for (k = 0; k < MAXGRAINS; k++)
        {
            t_grain *g = &x->x_g[k];
            if (g->len <= 0) continue;
            o += shift_read(x->x_buf, g->start + g->pos) * shift_win(g->pos / g->len) * (float)g->gain;
            if ((g->pos += 1) >= g->len) g->len = 0;
        }
        out[i] = o;
    }
    return (w + 5);
}

static void dcs_shift_dsp(t_dcs_shift *x, t_signal **sp)
{
    if (sp[0]->s_sr != x->x_yin.sr)
    {
        dcs_yin_init(&x->x_yin, sp[0]->s_sr);
        x->x_P = NOISE_MS * sp[0]->s_sr / 1000;
        x->x_now = x->x_nextmark = 0;
        x->x_lasta = -1;
        memset(x->x_g, 0, sizeof(x->x_g));
    }
    dsp_add(dcs_shift_perform, 4, x, sp[0]->s_vec, sp[1]->s_vec, (t_int)sp[0]->s_n);
}

static void dcs_shift_semi(t_dcs_shift *x, t_floatarg f) { x->x_semi = f < -24 ? -24 : (f > 24 ? 24 : f); }
static void dcs_shift_freq(t_dcs_shift *x, t_floatarg f) { x->x_freq = f > 20 ? f : 0; }

static void *dcs_shift_new(t_floatarg semi)
{
    t_dcs_shift *x = (t_dcs_shift *)pd_new(dcs_shift_class);
    x->x_semi = semi;
    x->x_lasta = -1;
    outlet_new(&x->x_obj, &s_signal);
    return (x);
}

void dcs_shift_tilde_setup(void)
{
    int i;
    for (i = 0; i <= HANNLEN; i++)
        shift_hann[i] = (float)(0.5 - 0.5 * cos(2 * M_PI * i / HANNLEN));
    dcs_shift_class = class_new(gensym("dcs_shift~"), (t_newmethod)dcs_shift_new, 0,
        sizeof(t_dcs_shift), CLASS_DEFAULT, A_DEFFLOAT, 0);
    CLASS_MAINSIGNALIN(dcs_shift_class, t_dcs_shift, x_f);
    class_addmethod(dcs_shift_class, (t_method)dcs_shift_dsp, gensym("dsp"), A_CANT, 0);
    class_addmethod(dcs_shift_class, (t_method)dcs_shift_semi, gensym("semi"), A_FLOAT, 0);
    class_addmethod(dcs_shift_class, (t_method)dcs_shift_freq, gensym("freq"), A_FLOAT, 0);
}
