/* dcs_voice~: one part of a kit (melody, bass, pad...): a small polyphonic instrument with several engines.
 *
 * The music engine decides the notes; a kit decides what they sound like by choosing an engine and its settings
 * with messages, so a kit is data (a text file), not patch code.
 *
 *   [dcs_voice~]
 *   inlet:   messages
 *     engine <0 off | 1 pluck | 2 bowed | 3 modal | 4 analog | 5 drums | 6 chop>
 *     note <Hz> <velocity 0..1> <length ms> [<brightness 0..1>]   a note that rings and dies away by itself
 *     pnote <slot> <Hz> [<velocity>]   a held note in a slot (a pad's chord tone, the bass): when the slot gets a new
 *                                      pitch, the old note fades out over `release` while the new one comes in
 *     poff <slot>, alloff
 *     bright <0..1>, level <gain>, attack <ms>, release <ms>, decay <ms> (how long a held pluck rings)
 *     modal <1 bell | 2 marimba | 3 bowl>
 *     analog: cutoff <x the note's pitch>, reso <0..1>, fenv <how far the filter opens at a note, x pitch>,
 *             detune <cents between the two saws>, sub <0..1, a square an octave down>, saws <1..7: more saws
 *             spread across `detune`, a supersaw>
 *     drums: hit <0 kick | 1 snare | 2 hat> <velocity> [<hat decay ms>]; ktune <Hz>, kdecay <ms>, kdrive <0..1>,
 *             stone <Hz>, sdecay <ms>, hdecay <ms> (closed hats; a hit's own decay overrides)
 *     analog: wobble <0..1> and wrate <cycles a beat>: a tempo-synced wobble (the volume dips and the filter closes
 *             each cycle, every voice together, restarted on each `tempo <bpm>` the patch sends at every beat);
 *             bend <semitones> and bendms: each note starts that far off and glides to its pitch
 *     chop: a note plays a short slice of the newest held voice the patch kept (tables fpad_<n>, fpad_f0, fpad_g,
 *             fpad_n), pitched to the note (folded by octaves); chop <ms> = its length. Nothing kept yet: analog.
 *     pump, pumprel: accepted and ignored (a kit's sidechain settings, read by the patch)
 *   outlet:  the sound (mono)
 *
 * Engines: pluck = a plucked string (Karplus-Strong: a delay loop tuned to the note through a loss filter designed
 * from two decay times, plucked by a triangle so the note itself leads; see dcs_string~). bowed = the same string
 * kept sounding by soft low-passed noise, with an attack and a release. modal = a bank of resonators tuned to an
 * instrument's partials (a bell's inharmonic ones, a marimba's, a singing bowl's), struck by a click. analog = two
 * detuned band-limited saws and a sub square through a 4-pole ladder filter (zero-delay feedback, tanh in the loop
 * so the resonance growls rather than whistles), the cutoff following the note and opened by an envelope at each
 * note, with an attack and a release. drums = a drum machine: a kick (a sine diving from ~4x to its tune, a click,
 * soft drive), a snare (two tones and high-passed noise), hats (high-passed noise, short or open).
 *
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 dadcraft (DadCraft Studios)
 */
#include "m_pd.h"
#include <math.h>
#include <string.h>
#include <stdio.h>

#define NV 10
#define DLEN 4096                 /* power of two: 20 Hz at 48 kHz (the bass goes down to ~40) */
#define NMODES 6
#define DC_HZ 10.
#define PLUCK_GAIN 1.5f               /* each engine near the classic voices' loudness at velocity 1 */
#define BOWED_GAIN 6.f

enum { E_OFF, E_PLUCK, E_BOWED, E_MODAL, E_ANALOG, E_DRUMS, E_CHOP };
#define MAXSAWS 7
#define CHOP_GAIN 0.15f               /* a chop near the analog fallback at the same `level` */
#define ANALOG_GAIN 0.35f

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
    /* analog */
    double ph[MAXSAWS + 1];            /* the saws, then the sub square */
    /* drums */
    int role;
    double t, dph, dhx, dhy, dh2x, dh2y, dec;
    float bendcur, bendk;              /* analog: semitones still to glide, the glide factor per sample */
    /* chop */
    t_word *cvec;
    int clen;
    double cpos, crate, ctotal;
    float cgain;
    float lad[4], fenv, fenvk;
} t_vvoice;

typedef struct _dcs_voice
{
    t_object x_obj;
    double x_sr;
    int x_engine, x_modal;
    float x_bright, x_level, x_attack, x_release, x_decay;
    float x_cutoff, x_reso, x_fenv, x_detune, x_sub;
    int x_saws;
    float x_wobble, x_wrate, x_bend, x_bendms, x_chop;
    double x_bpm, x_lfoph;
    float x_ktune, x_kdecay, x_kdrive, x_stone, x_sdecay, x_hdecay;
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
    case E_CHOP:
        {
            t_float fn, fs, f0, g;
            t_garray *a;
            char name[32];
            int size;
            t_word *vec;
            {
                t_garray *na = (t_garray *)pd_findbyclass(gensym("fpad_n"), garray_class);
                t_word *nv; int nn;
                fn = 0; fs = 0;
                if (na && garray_getfloatwords(na, &nn, &nv) && nn >= 2) { fn = nv[0].w_float; fs = nv[1].w_float; }
            }
            snprintf(name, sizeof(name), "fpad_%d", (int)fs);
            a = fn >= 1 ? (t_garray *)pd_findbyclass(gensym(name), garray_class) : 0;
            if (a && garray_getfloatwords(a, &size, &vec) && size > sr * 0.4)
            {
                t_garray *fa = (t_garray *)pd_findbyclass(gensym("fpad_f0"), garray_class), *ga = (t_garray *)pd_findbyclass(gensym("fpad_g"), garray_class);
                t_word *fv, *gv; int fz, gz;
                f0 = (fa && garray_getfloatwords(fa, &fz, &fv) && fz > (int)fs) ? fv[(int)fs].w_float : 0;
                g = (ga && garray_getfloatwords(ga, &gz, &gv) && gz > (int)fs) ? gv[(int)fs].w_float : 1;
                if (f0 > 20)
                {
                    double r = hz / f0;
                    while (r > 1.5) r *= 0.5;            /* (folded by octaves: close to the voice's own range) */
                    while (r < 0.75) r *= 2;
                    v->cvec = vec; v->clen = size; v->crate = r; v->cgain = g > 0 ? g : 1;
                    v->cpos = sr * (0.2 + 0.1 * (0.5 + 0.5 * voice_noise(x)));   /* past its start, into the held note */
                    v->ctotal = (x->x_chop > 20 ? x->x_chop : 20) * sr / 1000;
                    if (v->ctotal > len_ms * sr / 1000) v->ctotal = len_ms * sr / 1000;
                    v->t = 0;
                    v->gain = 1; v->gstep = 0;
                    break;
                }
            }
            v->engine = E_ANALOG;                        /* nothing kept yet: the analog voice plays it */
        }
        /* fall through */
    case E_ANALOG:
        {
            int o;                               /* each saw from its own phase (a supersaw doesn't "zap" in phase) */
            for (o = 0; o <= MAXSAWS; o++) v->ph[o] = 0.5 + 0.5 * voice_noise(x);
        }
        v->gstep = (float)(1000. / ((x->x_attack > 1 ? x->x_attack : 1) * sr));
        v->bendcur = x->x_bend;                          /* a bend: starts off its pitch, glides to it */
        v->bendk = (float)exp(-1. / ((x->x_bendms > 1 ? x->x_bendms : 1) * 0.25 * sr / 1000.));
        v->fenv = 1;                                     /* the filter opens at the note, closing over its length */
        v->fenvk = (float)exp(-1. / ((slot < 0 ? len_ms : x->x_decay) * 0.25 * sr / 1000.));
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
        if (v->engine == E_ANALOG)
        {
            double sr = x->x_sr, f0 = v->hz * pow(2, v->bendcur / 12.), inc[MAXSAWS + 1];
            /* the wobble: shared by every voice, restarted on each beat; volume dips and the filter closes as it runs */
            double wph = x->x_lfoph, wob = x->x_wobble < 0 ? 0 : (x->x_wobble > 1 ? 1 : x->x_wobble);
            float wgain = (float)(1 - 0.8 * wob * wph);
            int ns = x->x_saws < 1 ? 1 : (x->x_saws > MAXSAWS ? MAXSAWS : x->x_saws), o2;
            float sawgain = ns == 2 ? 1.f : (float)(1.41 / sqrt((double)ns));   /* (two saws: as before) */
            for (o2 = 0; o2 < ns; o2++)          /* two: the note and `detune` above; more: spread across `detune` */
                inc[o2] = f0 * pow(2, (ns == 2 ? o2 : (ns > 1 ? (double)o2 / (ns - 1) - 0.5 : 0)) * x->x_detune / 1200.) / sr;
            inc[ns] = f0 * 0.5 / sr;
            double fc = f0 * x->x_cutoff * (1 + x->x_fenv * v->fenv) * (1 + 2 * wob * (1 - wph)), g, G, k = 3.9 * (x->x_reso < 0 ? 0 : (x->x_reso > 1 ? 1 : x->x_reso));
            float sub = x->x_sub;
            if (fc > 0.45 * sr) fc = 0.45 * sr;
            if (fc < 20) fc = 20;
            g = tan(M_PI * fc / sr);
            G = g / (1 + g);                             /* (the cutoff moves per block: tan per sample is costly) */
            for (i = 0; i < n; i++)
            {
                int o;
                float osc = 0, xin, G4 = (float)(G * G * G * G), S, y4, u;
                for (o = 0; o <= ns; o++)
                {
                    /* band-limited by PolyBLEP: the jump smoothed over a sample either side */
                    double t = v->ph[o], dt = inc[o], blep = 0, val;
                    if (t < dt) { double q = t / dt; blep = q + q - q * q - 1; }
                    else if (t > 1 - dt) { double q = (t - 1) / dt; blep = q * q + q + q + 1; }
                    if (o < ns) val = (2 * t - 1 - blep) * sawgain;  /* saw */
                    else
                    {                                               /* square: two saws half a cycle apart */
                        double t2 = t + 0.5 - floor(t + 0.5), b2 = 0;
                        if (t2 < dt) { double q = t2 / dt; b2 = q + q - q * q - 1; }
                        else if (t2 > 1 - dt) { double q = (t2 - 1) / dt; b2 = q * q + q + q + 1; }
                        val = ((2 * t - 1 - blep) - (2 * t2 - 1 - b2)) * sub;
                    }
                    osc += (float)val;
                    v->ph[o] = t + dt - floor(t + dt);
                }
                xin = osc * 0.5f;
                /* the ladder: four one-pole TPT stages, the feedback solved without a delay, tanh on the input */
                S = (float)(G * G * G * (1 - G) * v->lad[0] + G * G * (1 - G) * v->lad[1] + G * (1 - G) * v->lad[2] + (1 - G) * v->lad[3]);
                y4 = (G4 * xin + S) / (1 + (float)k * G4);
                u = tanhf(xin - (float)k * y4);
                for (o = 0; o < 4; o++)
                {
                    float vv = (u - v->lad[o]) * (float)G, yy = vv + v->lad[o];
                    v->lad[o] = yy + vv;
                    u = yy;
                }
                if (v->gain != v->gtarget)
                {
                    if (v->gain < v->gtarget) { v->gain += v->gstep; if (v->gain > v->gtarget) v->gain = v->gtarget; }
                    else { v->gain -= v->gstep; if (v->gain < v->gtarget) v->gain = v->gtarget; }
                }
                out[i] += u * v->gain * v->amp * ANALOG_GAIN * level * wgain;
            }
            v->bendcur *= (float)pow(v->bendk, n);
            v->fenv *= (float)pow(v->fenvk, n);
            for (m = 0; m < 4; m++)
                if (PD_BIGORSMALL(v->lad[m])) v->lad[m] = 0;
            if (v->releasing && v->gain <= 0) v->on = 0;
        }
        else if (v->engine == E_CHOP)
        {
            /* a slice of the held voice at the note's rate: 3 ms in, 25 ms out at the end of its length */
            double sr = x->x_sr, att = 0.003 * sr, rel = 0.025 * sr;
            for (i = 0; i < n; i++)
            {
                long ip = (long)v->cpos;
                float fr = (float)(v->cpos - ip), a, b, e;
                if (ip + 1 >= v->clen || v->t >= v->ctotal) { v->on = 0; break; }
                a = v->cvec[ip].w_float; b = v->cvec[ip + 1].w_float;
                e = (float)(v->t < att ? v->t / att : (v->t > v->ctotal - rel ? (v->ctotal - v->t) / rel : 1));
                out[i] += (a + fr * (b - a)) * e * v->amp * v->cgain * level * CHOP_GAIN;
                v->cpos += v->crate;
                v->t += 1;
            }
        }
        else if (v->engine == E_DRUMS)
        {
            double sr = x->x_sr;
            for (i = 0; i < n; i++)
            {
                double t = v->t / sr, s = 0;
                float nz = voice_noise(x);
                if (v->role == 0)
                {                                /* kick: a sine diving from 4x its tune, a click, a soft drive */
                    double f = x->x_ktune * (1 + 3 * exp(-t / 0.03));
                    v->dph += f / sr;
                    s = sin(2 * M_PI * v->dph) * exp(-t * 1000. / (x->x_kdecay > 10 ? x->x_kdecay : 10));
                    if (t < 0.003) s += nz * 0.5 * (1 - t / 0.003);
                    s = tanh(s * (1 + 3 * x->x_kdrive)) / tanh(1 + 3 * x->x_kdrive);
                }
                else if (v->role == 1)
                {                                /* snare: two tones and a crack of high-passed noise */
                    double hp, td = exp(-t * 1000. / 80.), nd = exp(-t * 1000. / (x->x_sdecay > 10 ? x->x_sdecay : 10));
                    v->dph += x->x_stone / sr;
                    hp = nz - v->dhx + 0.95 * v->dhy; v->dhx = nz; v->dhy = hp;
                    s = 0.5 * (sin(2 * M_PI * v->dph) + 0.6 * sin(2 * M_PI * v->dph * 1.83)) * td + hp * 0.8 * nd;
                }
                else
                {                                /* hat: noise high-passed twice (~7 kHz), short or open */
                    double a = 0.4, h1 = (nz - v->dhx) + a * v->dhy, h2;
                    v->dhx = nz; v->dhy = h1;
                    h2 = (h1 - v->dh2x) + a * v->dh2y; v->dh2x = h1; v->dh2y = h2;
                    s = h2 * 0.5 * exp(-t * 1000. / (v->dec > 5 ? v->dec : 5));
                }
                out[i] += (float)(s * v->amp) * level;
                v->t += 1;
            }
            if (v->t > sr * 3) v->on = 0;
        }
        else if (v->engine == E_MODAL)
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
                if (v->engine == E_BOWED || v->engine == E_ANALOG) voice_release(x, v);
                else v->on = 0;
            }
        }
    }
    x->x_lfoph += x->x_wrate * x->x_bpm / 60. / x->x_sr * n;   /* the wobble, `wrate` cycles a beat */
    x->x_lfoph -= floor(x->x_lfoph);
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

static void dcs_voice_engine(t_dcs_voice *x, t_floatarg f) { x->x_engine = (int)f >= 0 && (int)f <= 6 ? (int)f : 0; if (!x->x_engine) dcs_voice_alloff(x); }
static void dcs_voice_wobble(t_dcs_voice *x, t_floatarg f) { x->x_wobble = f; }
static void dcs_voice_wrate(t_dcs_voice *x, t_floatarg f) { x->x_wrate = f > 0 ? f : 0; }
static void dcs_voice_bend(t_dcs_voice *x, t_floatarg f) { x->x_bend = f; }
static void dcs_voice_bendms(t_dcs_voice *x, t_floatarg f) { x->x_bendms = f; }
static void dcs_voice_chopms(t_dcs_voice *x, t_floatarg f) { x->x_chop = f; }
static void dcs_voice_tempo(t_dcs_voice *x, t_floatarg f) { if (f > 20) x->x_bpm = f; x->x_lfoph = 0; }   /* (sent on every beat) */
static void dcs_voice_saws(t_dcs_voice *x, t_floatarg f) { x->x_saws = (int)f; }
static void dcs_voice_ignore(t_dcs_voice *x, t_floatarg f) { }
static void dcs_voice_set(t_dcs_voice *x, t_symbol *s, t_floatarg f)
{
    if (s == gensym("ktune")) x->x_ktune = f;
    else if (s == gensym("kdecay")) x->x_kdecay = f;
    else if (s == gensym("kdrive")) x->x_kdrive = f < 0 ? 0 : (f > 1 ? 1 : f);
    else if (s == gensym("stone")) x->x_stone = f;
    else if (s == gensym("sdecay")) x->x_sdecay = f;
    else if (s == gensym("hdecay")) x->x_hdecay = f;
}
static void dcs_voice_ktune(t_dcs_voice *x, t_floatarg f) { dcs_voice_set(x, gensym("ktune"), f); }
static void dcs_voice_kdecay(t_dcs_voice *x, t_floatarg f) { dcs_voice_set(x, gensym("kdecay"), f); }
static void dcs_voice_kdrive(t_dcs_voice *x, t_floatarg f) { dcs_voice_set(x, gensym("kdrive"), f); }
static void dcs_voice_stone(t_dcs_voice *x, t_floatarg f) { dcs_voice_set(x, gensym("stone"), f); }
static void dcs_voice_sdecay(t_dcs_voice *x, t_floatarg f) { dcs_voice_set(x, gensym("sdecay"), f); }
static void dcs_voice_hdecay(t_dcs_voice *x, t_floatarg f) { dcs_voice_set(x, gensym("hdecay"), f); }

/* a drum hit: role 0 kick, 1 snare, 2 hat (with its own decay, if given) */
static void dcs_voice_hit(t_dcs_voice *x, t_floatarg role, t_floatarg vel, t_floatarg dec)
{
    t_vvoice *v;
    if (x->x_engine != E_DRUMS || vel <= 0 || x->x_sr <= 0) return;
    v = voice_alloc(x);
    v->on = 1; v->slot = -1; v->engine = E_DRUMS; v->role = (int)role; v->amp = vel;
    v->dec = dec > 0 ? dec : x->x_hdecay;
}
static void dcs_voice_cutoff(t_dcs_voice *x, t_floatarg f) { x->x_cutoff = f > 0.1f ? f : 0.1f; }
static void dcs_voice_reso(t_dcs_voice *x, t_floatarg f) { x->x_reso = f; }
static void dcs_voice_fenv(t_dcs_voice *x, t_floatarg f) { x->x_fenv = f > 0 ? f : 0; }
static void dcs_voice_detune(t_dcs_voice *x, t_floatarg f) { x->x_detune = f; }
static void dcs_voice_sub(t_dcs_voice *x, t_floatarg f) { x->x_sub = f < 0 ? 0 : (f > 1 ? 1 : f); }
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
    x->x_cutoff = 4; x->x_reso = 0.3f; x->x_fenv = 6; x->x_detune = 8; x->x_sub = 0.3f; x->x_saws = 2;
    x->x_wobble = 0; x->x_wrate = 2; x->x_bend = 0; x->x_bendms = 120; x->x_chop = 180; x->x_bpm = 100;
    x->x_ktune = 50; x->x_kdecay = 350; x->x_kdrive = 0.3f; x->x_stone = 185; x->x_sdecay = 180; x->x_hdecay = 45;
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
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_cutoff, gensym("cutoff"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_reso, gensym("reso"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_fenv, gensym("fenv"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_detune, gensym("detune"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_sub, gensym("sub"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_saws, gensym("saws"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_wobble, gensym("wobble"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_wrate, gensym("wrate"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_bend, gensym("bend"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_bendms, gensym("bendms"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_chopms, gensym("chop"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_tempo, gensym("tempo"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_hit, gensym("hit"), A_FLOAT, A_FLOAT, A_DEFFLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_ktune, gensym("ktune"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_kdecay, gensym("kdecay"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_kdrive, gensym("kdrive"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_stone, gensym("stone"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_sdecay, gensym("sdecay"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_hdecay, gensym("hdecay"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_ignore, gensym("pump"), A_FLOAT, 0);
    class_addmethod(dcs_voice_class, (t_method)dcs_voice_ignore, gensym("pumprel"), A_FLOAT, 0);
}
