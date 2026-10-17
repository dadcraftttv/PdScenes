/* dcs_pitch~: a light pitch tracker (YIN, see dcs_yin.h), a drop-in for [sigmund~ -hop N pitch env].
 *
 *   [dcs_pitch~ <hop samples, default 512>]
 *   inlet:   signal
 *   outlets: pitch (MIDI, fractional; -1500 when there is no clear pitch, as sigmund~), level (dB, 100 = full
 *            scale, 0 = silence), sureness (0..1). Every hop: sureness, then level, then pitch.
 *
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 dadcraft (DadCraft Studios)
 */
#include "m_pd.h"
#include "dcs_yin.h"

static t_class *dcs_pitch_class;

typedef struct _dcs_pitch
{
    t_object x_obj;
    t_float x_f;
    t_dcs_yin x_yin;
    int x_hop, x_count;
    double x_sq;                /* sum of squares over the hop (the level) */
    double x_pitch, x_db, x_sure;
    t_clock *x_clock;
    t_outlet *x_pout, *x_lout, *x_sout;
} t_dcs_pitch;

static void dcs_pitch_tick(t_dcs_pitch *x)
{
    outlet_float(x->x_sout, (t_float)x->x_sure);
    outlet_float(x->x_lout, (t_float)x->x_db);
    outlet_float(x->x_pout, (t_float)x->x_pitch);
}

static t_int *dcs_pitch_perform(t_int *w)
{
    t_dcs_pitch *x = (t_dcs_pitch *)(w[1]);
    t_sample *in = (t_sample *)(w[2]);
    int n = (int)(w[3]), i;
    for (i = 0; i < n; i++)
    {
        float s = in[i];
        dcs_yin_write(&x->x_yin, s);
        x->x_sq += (double)s * s;
        if (++x->x_count >= x->x_hop)
        {
            double rms = sqrt(x->x_sq / x->x_count), sure = 0, P;
            x->x_db = rms > 1e-5 ? 100 + 20 * log10(rms) : 0;
            P = x->x_db > 10 ? dcs_yin_period(&x->x_yin, &sure) : 0;
            x->x_sure = sure;
            x->x_pitch = P > 0 ? 69 + 12 * log2(x->x_yin.sr / P / 440.) : -1500;
            x->x_count = 0;
            x->x_sq = 0;
            clock_delay(x->x_clock, 0);
        }
    }
    return (w + 4);
}

static void dcs_pitch_dsp(t_dcs_pitch *x, t_signal **sp)
{
    if (sp[0]->s_sr != x->x_yin.sr)
        dcs_yin_init(&x->x_yin, sp[0]->s_sr);
    dsp_add(dcs_pitch_perform, 3, x, sp[0]->s_vec, (t_int)sp[0]->s_n);
}

static void *dcs_pitch_new(t_floatarg hop)
{
    t_dcs_pitch *x = (t_dcs_pitch *)pd_new(dcs_pitch_class);
    x->x_hop = hop >= 32 ? (int)hop : 512;
    dcs_yin_init(&x->x_yin, sys_getsr() > 0 ? sys_getsr() : 44100);
    x->x_pitch = -1500;
    x->x_clock = clock_new(x, (t_method)dcs_pitch_tick);
    x->x_pout = outlet_new(&x->x_obj, &s_float);
    x->x_lout = outlet_new(&x->x_obj, &s_float);
    x->x_sout = outlet_new(&x->x_obj, &s_float);
    return (x);
}

static void dcs_pitch_free(t_dcs_pitch *x)
{
    clock_free(x->x_clock);
}

void dcs_pitch_tilde_setup(void)
{
    dcs_pitch_class = class_new(gensym("dcs_pitch~"), (t_newmethod)dcs_pitch_new, (t_method)dcs_pitch_free,
        sizeof(t_dcs_pitch), CLASS_DEFAULT, A_DEFFLOAT, 0);
    CLASS_MAINSIGNALIN(dcs_pitch_class, t_dcs_pitch, x_f);
    class_addmethod(dcs_pitch_class, (t_method)dcs_pitch_dsp, gensym("dsp"), A_CANT, 0);
}
