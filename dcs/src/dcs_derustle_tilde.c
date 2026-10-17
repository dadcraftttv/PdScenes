/* dcs_derustle~: squashes sudden bursts that jump far above the room's quiet, and leaves the quiet alone.
 *
 * Made for a phone in a pocket: cloth rustle arrives as bursts 15-25 dB over the room, while the room itself (heard
 * through the cloth) stays fairly steady. A plain volume cut lowers both. This follows the room's floor (it drops
 * at once into the quiet between bursts and climbs only slowly, `rise` dB a second) and pulls anything more than
 * `above` dB over it back toward that line, at once (no lookahead: the gain falls on the sample a burst arrives)
 * and lets go over `release` ms. Something that stays over the line for 1.5 s without a gap is the room itself
 * getting louder (rustle comes in bursts): the floor then climbs quickly (60 dB a second) to meet it. Loudness is
 * judged as a short mean square (1 ms up, 10 ms down) against a floor built on a 50 ms average, so noise's own
 * peaks don't count as bursts; at amount 0 the floor simply follows the room.
 *
 *   [dcs_derustle~ <amount 0..1> <above dB, default 6> <release ms, default 80>]
 *   inlet:   signal; `amount <0..1>` (0 = untouched, 1 = held to the line), `above <dB>`, `release <ms>`,
 *            `rise <dB/s>` (how fast the floor may climb, default 3)
 *   outlets: the signal with the bursts squashed; the gain applied (1 = untouched), for squashing other signals alike
 *
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 dadcraft (DadCraft Studios)
 */
#include "m_pd.h"
#include <math.h>

#define FAST_ATTACK_MS 1.         /* the loudness that is judged: mean square rising over this... */
#define FAST_RELEASE_MS 10.       /* ...and falling over this (noise's own peaks average out) */
#define SLOW_MS 50.               /* the floor is built on the loudness averaged over this */
#define FLOOR_FALL_MS 40.         /* the floor drops this fast into a quiet gap */
#define WARM_MS 50.               /* for this long at the start (and whenever amount is 0) the floor is the room */
#define FLOOR_MIN 1e-6
#define SUSTAIN_MS 1500.          /* over the line this long without a gap: it's the room getting louder, not rustle... */
#define SUSTAIN_RISE_DB 60.       /* ...so the floor climbs this fast (dB a second) */

static t_class *dcs_derustle_class;

typedef struct _dcs_derustle
{
    t_object x_obj;
    t_float x_f;
    t_float x_amount, x_above, x_release, x_rise;
    double x_sr;
    double x_env, x_floor, x_gain;
    double x_over;                /* samples over the line without a gap */
    double x_ms, x_slow, x_warm;  /* fast and slow mean squares, samples of warm-up done */
    t_outlet *x_gout;
} t_dcs_derustle;

static t_int *dcs_derustle_perform(t_int *w)
{
    t_dcs_derustle *x = (t_dcs_derustle *)(w[1]);
    t_sample *in = (t_sample *)(w[2]), *out = (t_sample *)(w[3]), *gout = (t_sample *)(w[4]);
    int n = (int)(w[5]), i;
    double sr = x->x_sr;
    double attk = exp(-1000. / (FAST_ATTACK_MS * sr)), fastrk = exp(-1000. / (FAST_RELEASE_MS * sr));
    double slowk = exp(-1000. / (SLOW_MS * sr)), warmn = WARM_MS * sr / 1000.;
    double ms = x->x_ms, slow = x->x_slow, warm = x->x_warm;
    double fallk = exp(-1000. / (FLOOR_FALL_MS * sr));
    double risek = pow(10., (x->x_rise > 0 ? x->x_rise : 0) / 20. / sr);       /* per sample, as a factor */
    double relk = exp(-1000. / ((x->x_release > 1 ? x->x_release : 1) * sr));
    double line = pow(10., x->x_above / 20.);
    double amount = x->x_amount < 0 ? 0 : (x->x_amount > 1 ? 1 : x->x_amount);
    double env = x->x_env, floor = x->x_floor, gain = x->x_gain, over = x->x_over;
    double fastk = pow(10., SUSTAIN_RISE_DB / 20. / sr), sustain = SUSTAIN_MS * sr / 1000.;
    for (i = 0; i < n; i++)
    {
        t_sample s = in[i];
        double sq = (double)s * s, target, fl;
        ms = sq + (ms - sq) * (sq > ms ? attk : fastrk);
        slow = sq + (slow - sq) * slowk;
        env = sqrt(ms);
        fl = sqrt(slow);
        if (warm < warmn || amount <= 0)
        {
            floor = fl;                 /* (out of a pocket, and at the start: the floor is simply the room) */
            if (warm < warmn) warm++;
        }
        /* the floor: down into a gap at once (well, over FLOOR_FALL_MS), up only slowly */
        else if (fl < floor)
            floor = fl + (floor - fl) * fallk;
        else
            floor *= (over > sustain ? fastk : risek);
        over = env > floor * line ? over + 1 : 0;
        if (floor < FLOOR_MIN) floor = FLOOR_MIN;
        /* how far over the line: squash by that much (in dB) x amount */
        target = 1;
        if (env > floor * line && amount > 0)
            target = pow(floor * line / env, amount);
        gain = target < gain ? target : target + (gain - target) * relk;
        out[i] = s * (t_sample)gain;
        gout[i] = (t_sample)gain;
    }
    if (PD_BIGORSMALL(ms)) ms = 0;
    if (PD_BIGORSMALL(slow)) slow = 0;
    x->x_env = env; x->x_floor = floor; x->x_gain = gain; x->x_over = over;
    x->x_ms = ms; x->x_slow = slow; x->x_warm = warm;
    return (w + 6);
}

static void dcs_derustle_dsp(t_dcs_derustle *x, t_signal **sp)
{
    x->x_sr = sp[0]->s_sr;
    dsp_add(dcs_derustle_perform, 5, x, sp[0]->s_vec, sp[1]->s_vec, sp[2]->s_vec, (t_int)sp[0]->s_n);
}

static void dcs_derustle_amount(t_dcs_derustle *x, t_floatarg f) { x->x_amount = f; }
static void dcs_derustle_above(t_dcs_derustle *x, t_floatarg f) { x->x_above = f; }
static void dcs_derustle_release(t_dcs_derustle *x, t_floatarg f) { x->x_release = f; }
static void dcs_derustle_rise(t_dcs_derustle *x, t_floatarg f) { x->x_rise = f; }

static void *dcs_derustle_new(t_floatarg amount, t_floatarg above, t_floatarg release)
{
    t_dcs_derustle *x = (t_dcs_derustle *)pd_new(dcs_derustle_class);
    x->x_amount = amount;
    x->x_above = above > 0 ? above : 6;
    x->x_release = release > 0 ? release : 80;
    x->x_rise = 3;
    x->x_sr = sys_getsr() > 0 ? sys_getsr() : 44100;
    x->x_env = 0; x->x_floor = FLOOR_MIN; x->x_gain = 1; x->x_over = 0;
    x->x_ms = x->x_slow = x->x_warm = 0;
    outlet_new(&x->x_obj, &s_signal);
    x->x_gout = outlet_new(&x->x_obj, &s_signal);
    return (x);
}

void dcs_derustle_tilde_setup(void)
{
    dcs_derustle_class = class_new(gensym("dcs_derustle~"), (t_newmethod)dcs_derustle_new, 0,
        sizeof(t_dcs_derustle), CLASS_DEFAULT, A_DEFFLOAT, A_DEFFLOAT, A_DEFFLOAT, 0);
    CLASS_MAINSIGNALIN(dcs_derustle_class, t_dcs_derustle, x_f);
    class_addmethod(dcs_derustle_class, (t_method)dcs_derustle_dsp, gensym("dsp"), A_CANT, 0);
    class_addmethod(dcs_derustle_class, (t_method)dcs_derustle_amount, gensym("amount"), A_FLOAT, 0);
    class_addmethod(dcs_derustle_class, (t_method)dcs_derustle_above, gensym("above"), A_FLOAT, 0);
    class_addmethod(dcs_derustle_class, (t_method)dcs_derustle_release, gensym("release"), A_FLOAT, 0);
    class_addmethod(dcs_derustle_class, (t_method)dcs_derustle_rise, gensym("rise"), A_FLOAT, 0);
}
