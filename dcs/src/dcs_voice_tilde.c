/* dcs_voice~: one part of a kit (melody, bass, pad...): a small polyphonic instrument with several engines.
 *
 * The music engine decides the notes; a kit decides what they sound like by choosing an engine and its settings
 * with messages, so a kit is data (a text file), not patch code.
 *
 *   [dcs_voice~]
 *   inlet:   messages
 *     engine <0 off | 1 pluck | 2 bowed | 3 modal>
 *     note <Hz> <velocity 0..1> <length ms> [<brightness 0..1>]   a note that rings and dies away by itself
 *     pnote <slot> <Hz> [<velocity>]   a held note in a slot (a pad's chord tone, the bass): when the slot gets a new
 *                                      pitch, the old note fades out over `release` while the new one comes in
 *     poff <slot>, alloff
 *     bright <0..1>, level <gain>, attack <ms>, release <ms>, decay <ms> (how long a held pluck rings)
 *     modal <1 bell | 2 marimba | 3 bowl>
 *   outlet:  the sound (mono)
 *
 * Engines: pluck = a plucked string (Karplus-Strong: a delay loop tuned to the note through a loss filter designed
 * from two decay times, plucked by a triangle so the note itself leads; see dcs_string~). bowed = the same string
 * kept sounding by soft low-passed noise, with an attack and a release. modal = a bank of resonators tuned to an
 * instrument's partials (a bell's inharmonic ones, a marimba's, a singing bowl's), struck by a click.
 *
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 dadcraft (DadCraft Studios)
 */
#include "m_pd.h"
#include <math.h>
#include <string.h>

#define NV 10
#define DLEN 4096                 /* power of two: 20 Hz at 48 kHz (the bass goes down to ~40) */
#define NMODES 6
#define DC_HZ 10.
#define PLUCK_GAIN 1.5f               /* each engine near the classic voices' loudness at velocity 1 */
#define BOWED_GAIN 6.f

enum { E_OFF, E_PLUCK, E_BOWED, E_MODAL };

static const double MODAL_RATIO[4][NMODES] = {
    {0}, {1, 2.76, 5.40, 8.93, 13.34, 18.64},          /* bell (a free bar / bell's inharmonic partials) */
    {1, 3.99, 10.65, 0, 0, 0},                         /* marimba (a tuned bar) */
    {1, 2.71, 5.15, 8.24, 11.9, 0} };                  /* singing bowl */
static const double MODAL_AMP[4][NMODES] = {
    {0}, {1, 0.6, 0.45, 0.3, 0.2, 0.1}, {1, 0.35, 0.12, 0, 0, 0}, {1, 0.55, 0.3, 0.15, 0.08, 0} };
static const double MODAL_DECAY[4][NMODES] = {          /* each partial's ring, as a share of the note's */
    {0}, {1, 0.7, 0.5, 0.35, 0.25, 0.18}, {1, 0.35, 0.15, 0, 0, 0}, {1, 0.9, 0.75, 0.6, 0.45, 0} };

static t_class *dcs_voice_class;

typedef struct _vvoice
{
    int on, slot, engine, struck;
    unsigned long order;
    double hz;
    float amp, gain, gstep, gtarget;   /* the envelope: gain moves by gstep toward gtarget */
    int releasing;
    /* string */
    float dl[DLEN];
    int w, di;
    float frac, b0, a1, R, ing, lp, hpx, hpy, bowlp;
    double bowph, bowinc;              /* the bow's pulse: once a period, so the tone stands steady */
    /* modal */
    float c1[NMODES], c2[NMODES], mg[NMODES], y1[NMODES], y2[NMODES];
    int nmodes;
    double life;                       /* samples until a ringing note is let go (0 = held) */
} t_vvoice;

typedef struct _dcs_voice
{
    t_object x_obj;
    double x_sr;
    int x_engine, x_modal;
    float x_bright, x_level, x_attack, x_release, x_decay;
    unsigned long x_count;
    unsigned int x_seed;
    t_vvoice x_v[NV];
} t_dcs_voice;

static float voice_noise(t_dcs_voice *x)
{
    x->x_seed = x->x_seed * 1664525u + 1013904223u;
    return (float)((int)(x->x_seed >> 9) - (1 << 22)) / (float)(1 << 22);
}

/* the string's loop for this pitch, decay and brightness (as dcs_string~) */
static void voice_string(t_dcs_voice *x, t_vvoice *v, double hz, double decay_ms, double bright)
{
    double sr = x->x_sr, f = hz < 20 ? 20 : (hz > sr / 6 ? sr / 6 : hz), w = 2 * M_PI * f / sr, cw = cos(w), sw = sin(w);
    double N = sr / f, r = pow(10., -3. * N / (sr * (decay_ms > 1 ? decay_ms : 1) / 1000.));
    double gpi = pow(10., -3. * N / (sr * decay_ms * pow(10., 2 * bright - 2.5) / 1000.));
    double a1 = (gpi - r) / (gpi + r), R = 1 - 2 * M_PI * DC_HZ / sr, phase, mag, D, b0;
    if (a1 < -0.9) a1 = -0.9;
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
    phase = atan2(a1 * sw, 1 + a1 * cw) + atan2(sw, 1 - cw) - atan2(R * sw, 1 - R * cw);
    mag = 1 / hypot(1 + a1 * cw, a1 * sw) * hypot(1 - cw, sw) / hypot(1 - R * cw, R * sw);
    D = N + phase / w;
    if (D < 3) D = 3;
    if (D > DLEN - 4) D = DLEN - 4;
    b0 = r / mag;
    if (b0 > 0.9999 * (1 + a1)) b0 = 0.9999 * (1 + a1);
    v->di = (int)D; v->frac = (float)(D - v->di);
    v->b0 = (float)b0; v->a1 = (float)a1; v->R = (float)R;
    v->ing = (float)sqrt(1 - r * r);
}

static void voice_pluck(t_vvoice *v, double hz, double sr, float amp)
{
    int P = (int)(sr / hz + 0.5), k;
    double peak = 0.3 * P, sum = 0, mean;
    if (P > DLEN - 4) P = DLEN - 4;
    if (P < 2) return;
    for (k = 0; k < P; k++) sum += k < peak ? k / peak : (P - k) / (P - peak);
    mean = sum / P;
    for (k = 0; k < P; k++)
        v->dl[(v->w - P + k) & (DLEN - 1)] += (float)(amp * ((k < peak ? k / peak : (P - k) / (P - peak)) - mean));
}

static void voice_modal(t_dcs_voice *x, t_vvoice *v, double hz, double decay_ms)
{
    int k, p = x->x_modal >= 1 && x->x_modal <= 3 ? x->x_modal : 1;
    v->nmodes = 0;
    for (k = 0; k < NMODES; k++)
    {
        double f = hz * MODAL_RATIO[p][k], T, r, w;
        if (MODAL_RATIO[p][k] <= 0 || f >= x->x_sr * 0.45) continue;
        T = decay_ms * MODAL_DECAY[p][k] / 1000.;
        r = pow(10., -3. / (T * x->x_sr));
        w = 2 * M_PI * f / x->x_sr;
        v->c1[v->nmodes] = (float)(2 * r * cos(w));
        v->c2[v->nmodes] = (float)(-r * r);
        v->mg[v->nmodes] = (float)(MODAL_AMP[p][k] * sin(w) * 0.5 * (0.4 + 0.6 * x->x_bright));   /* (rings ~ g / sin w) */
        v->y1[v->nmodes] = v->y2[v->nmodes] = 0;
        v->nmodes++;
    }
}

static t_vvoice *voice_alloc(t_dcs_voice *x)
{
    int k;
    t_vvoice *best = 0;
    for (k = 0; k < NV; k++)
        if (!x->x_v[k].on) { best = &x->x_v[k]; break; }
    if (!best)                       /* all busy: the oldest one-shot (held notes stay) */
        for (k = 0; k < NV; k++)
            if (x->x_v[k].slot < 0 && (!best || x->x_v[k].order < best->order)) best = &x->x_v[k];
    if (!best) best = &x->x_v[0];
    memset(best, 0, sizeof(*best));
    best->order = ++x->x_count;
    return best;
}

static void voice_start(t_dcs_voice *x, t_vvoice *v, double hz, float vel, double len_ms, double bright, int slot)
{
    double sr = x->x_sr;
    v->on = 1; v->slot = slot; v->engine = x->x_engine; v->hz = hz; v->amp = vel;
    v->gain = 0; v->gtarget = 1; v->releasing = 0;
    switch (v->engine)
    {
    case E_PLUCK:
        voice_string(x, v, hz, len_ms, bright);
        voice_pluck(v, hz, sr, vel);
        v->gain = 1; v->gstep = 0;
        v->life = slot < 0 ? len_ms * 1.3 * sr / 1000 : 0;
        break;
    case E_BOWED:
        voice_string(x, v, hz, 2500, bright);           /* (a long string, kept up by the bow) */
        v->bowinc = hz / sr;
        v->gstep = (float)(1000. / ((x->x_attack > 1 ? x->x_attack : 1) * sr));
        v->life = slot < 0 ? len_ms * sr / 1000 : 0;
        break;
    case E_MODAL:
        voice_modal(x, v, hz, len_ms);                   /* (struck in perform, on its first sample) */
        v->gain = 1; v->gstep = 0;
        v->life = slot < 0 ? len_ms * 1.3 * sr / 1000 : 0;
        break;
    default:
        v->on = 0;
    }
}

static void voice_release(t_dcs_voice *x, t_vvoice *v)
{
    if (v->engine == E_BOWED)                            /* let go: the string itself dies over the release */
        voice_string(x, v, v->hz, x->x_release > 50 ? x->x_release : 50, x->x_bright);
    v->releasing = 1;
    v->gtarget = 0;
    v->gstep = (float)(1000. / ((x->x_release > 1 ? x->x_release : 1) * x->x_sr));
    v->slot = -1;
}

static void dcs_voice_note(t_dcs_voice *x, t_symbol *s, int argc, t_atom *argv)
{
    double hz = atom_getfloatarg(0, argc, argv), len = atom_getfloatarg(2, argc, argv);
    float vel = atom_getfloatarg(1, argc, argv);
    double bright = argc > 3 ? atom_getfloat(argv + 3) : x->x_bright;
    t_vvoice *v;
    if (x->x_engine == E_OFF || hz <= 0 || vel <= 0 || x->x_sr <= 0) return;
    v = voice_alloc(x);
    voice_start(x, v, hz, vel, len > 50 ? len : 50, bright, -1);
}

static void dcs_voice_pnote(t_dcs_voice *x, t_floatarg fslot, t_floatarg hz, t_floatarg fvel)
{
    int k, slot = (int)fslot;
    float vel = fvel > 0 ? fvel : 1;
    t_vvoice *v;
    if (x->x_engine == E_OFF || hz <= 0 || x->x_sr <= 0) return;
    for (k = 0; k < NV; k++)
    {
        v = &x->x_v[k];
        if (v->on && v->slot == slot)
        {
            if (fabs(v->hz - hz) < 0.01 && v->engine == x->x_engine) return;     /* the same note: keep it */
            voice_release(x, v);
        }
    }
    v = voice_alloc(x);
    voice_start(x, v, hz, vel, x->x_decay, x->x_bright, slot);
}

static void dcs_voice_poff(t_dcs_voice *x, t_floatarg fslot)
{
    int k;
    for (k = 0; k < NV; k++)
        if (x->x_v[k].on && x->x_v[k].slot == (int)fslot) voice_release(x, &x->x_v[k]);
}

static void dcs_voice_alloff(t_dcs_voice *x)
{
    int k;
    for (k = 0; k < NV; k++)
        if (x->x_v[k].on) voice_release(x, &x->x_v[k]);
}

static t_int *dcs_voice_perform(t_int *w)
{
    t_dcs_voice *x = (t_dcs_voice *)(w[1]);
    t_sample *out = (t_sample *)(w[2]);
    int n = (int)(w[3]), i, k, m;
    float level = x->x_level;
    memset(out, 0, n * sizeof(t_sample));
    for (k = 0; k < NV; k++)
    {
        t_vvoice *v = &x->x_v[k];
        if (!v->on) continue;
        if (v->engine == E_MODAL)
        {
            for (i = 0; i < n; i++)
            {
                float exc = 0, s = 0;
                if (!v->struck) { exc = v->amp; v->struck = 1; }
                for (m = 0; m < v->nmodes; m++)
                {
                    float y = exc * v->mg[m] + v->c1[m] * v->y1[m] + v->c2[m] * v->y2[m];
                    v->y2[m] = v->y1[m]; v->y1[m] = y;
                    s += y;
                }
                if (v->releasing) { v->gain -= v->gstep; if (v->gain <= 0) { v->on = 0; break; } }
                out[i] += s * v->gain * level;
            }
        }
        else
        {
            float b0 = v->b0, a1 = v->a1, R = v->R, frac = v->frac, lp = v->lp, hpx = v->hpx, hpy = v->hpy;
            int di = v->di, wi = v->w;
            for (i = 0; i < n; i++)
            {
                float a = v->dl[(wi - di + 1) & (DLEN - 1)], b = v->dl[(wi - di) & (DLEN - 1)],
                    c = v->dl[(wi - di - 1) & (DLEN - 1)], d = v->dl[(wi - di - 2) & (DLEN - 1)];
                float cmb = c - b;
                float y = b + frac * (cmb - 0.1666667f * (1.f - frac) * ((d - a - 3.0f * cmb) * frac + (d + 2.0f * a - 3.0f * b)));
                float in = 0, vv;
                if (v->engine == E_BOWED)
                {
                    /* the bow: a pulse once a period (it locks the string, so the level stands steady) and a
                       little breath noise, at the envelope's level */
                    float pulse = 0;
                    v->bowph += v->bowinc;
                    if (v->bowph >= 1) { v->bowph -= 1; pulse = 1; }
                    v->bowlp += 0.05f * (voice_noise(x) - v->bowlp);
                    in = (pulse * 1.5f + v->bowlp * 0.15f) * v->ing * v->amp * v->gain;
                    if (v->gain != v->gtarget)
                    {
                        if (v->gain < v->gtarget) { v->gain += v->gstep; if (v->gain > v->gtarget) v->gain = v->gtarget; }
                        else { v->gain -= v->gstep; if (v->gain < v->gtarget) v->gain = v->gtarget; }
                    }
                }
                lp = b0 * y - a1 * lp;
                hpy = lp - hpx + R * hpy;
                hpx = lp;
                vv = in + hpy;
                v->dl[wi] = vv;
                wi = (wi + 1) & (DLEN - 1);
                if (v->engine == E_PLUCK && v->releasing) { v->gain -= v->gstep; if (v->gain < 0) v->gain = 0; }
                out[i] += vv * (v->engine == E_PLUCK ? v->gain * PLUCK_GAIN : BOWED_GAIN) * level;
            }
            if (PD_BIGORSMALL(lp)) lp = 0;
            if (PD_BIGORSMALL(hpy)) hpy = 0;
            v->lp = lp; v->hpx = hpx; v->hpy = hpy; v->w = wi;
            if (v->engine == E_PLUCK && v->releasing && v->gain <= 0) v->on = 0;
            if (v->engine == E_BOWED && v->releasing && v->gain <= 0 && fabsf(hpy) < 1e-5f) v->on = 0;
        }
        if (v->on && v->life > 0)
        {
            v->life -= n;
            if (v->life <= 0)
            {
                if (v->engine == E_BOWED) voice_release(x, v);
                else v->on = 0;
            }
        }
    }
    return (w + 4);
}

static void dcs_voice_dsp(t_dcs_voice *x, t_signal **sp)
{
    if (sp[0]->s_sr != x->x_sr)
    {
        x->x_sr = sp[0]->s_sr;
        memset(x->x_v, 0, sizeof(x->x_v));
    }
    dsp_add(dcs_voice_perform, 3, x, sp[0]->s_vec, (t_int)sp[0]->s_n);
}

static void dcs_voice_engine(t_dcs_voice *x, t_floatarg f) { x->x_engine = (int)f >= 0 && (int)f <= 3 ? (int)f : 0; if (!x->x_engine) dcs_voice_alloff(x); }
static void dcs_voice_bright(t_dcs_voice *x, t_floatarg f) { x->x_bright = f < 0 ? 0 : (f > 1 ? 1 : f); }
static void dcs_voice_level(t_dcs_voice *x, t_floatarg f) { x->x_level = f < 0 ? 0 : f; }
static void dcs_voice_attack(t_dcs_voice *x, t_floatarg f) { x->x_attack = f; }
static void dcs_voice_release_ms(t_dcs_voice *x, t_floatarg f) { x->x_release = f; }
static void dcs_voice_decay(t_dcs_voice *x, t_floatarg f) { x->x_decay = f > 50 ? f : 50; }
static void dcs_voice_modalp(t_dcs_voice *x, t_floatarg f) { x->x_modal = (int)f; }

static void *dcs_voice_new(void)
{
    t_dcs_voice *x = (t_dcs_voice *)pd_new(dcs_voice_class);
    x->x_sr = sys_getsr() > 0 ? sys_getsr() : 44100;
    x->x_bright = 0.4f; x->x_level = 1; x->x_attack = 300; x->x_release = 800; x->x_decay = 3000; x->x_modal = 1;
    x->x_seed = (unsigned int)(size_t)x;
    outlet_new(&x->x_obj, &s_signal);
    return (x);
}

void dcs_voice_tilde_setup(void)
{
    dcs_voice_class = class_new(gensym("dcs_voice~"), (t_newmethod)dcs_voice_new, 0,
        sizeof(t_dcs_voice), CLASS_DEFAULT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_dsp, gensym("dsp"), A_CANT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_engine, gensym("engine"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_note, gensym("note"), A_GIMME, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_pnote, gensym("pnote"), A_FLOAT, A_FLOAT, A_DEFFLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_poff, gensym("poff"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_alloff, gensym("alloff"), 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_bright, gensym("bright"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_level, gensym("level"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_attack, gensym("attack"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_release_ms, gensym("release"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_decay, gensym("decay"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_modalp, gensym("modal"), A_FLOAT, 0);
}
