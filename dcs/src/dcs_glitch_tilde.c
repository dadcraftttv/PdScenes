/* dcs_glitch~: a polyphonic glitch voice.
 *
 * It keeps the last few seconds of its input in a ring buffer and plays glitches from it, several at once, each
 * placed somewhere between the ears. Glitches start on the exact sample their message was sent for (like vline~),
 * not at the next block.
 *
 *   [dcs_glitch~ <buffer ms, default 4000> <voices, default 4>]
 *   inlet:   signal in; messages
 *   outlets: left, right
 *
 * Messages (times in ms; "back" = how long ago in the buffer):
 *   slice <L> <d0> <c1> <c2> <S> <place>
 *       A glitch L ms long reading d0 + (1 - c1) t - c2 (t mod S) ms back at t ms into it:
 *       stutter c1 0, c2 1 (an S ms slice repeated); reverse c1 -1, c2 0; replay c1 1, c2 0.
 *       Each S-long slice fades in and out over 3 ms; the glitch over 5 ms in and 20 ms out.
 *   stretch <L> <d0> <rate> <place>
 *       The sound from d0 ms back smeared out: it moves on at `rate` (0.1 = 10x slower) while overlapping
 *       grains play it at its own pitch. 40 ms in, 600 ms out. Each new grain starts where its waveform lines
 *       up best with the grain already playing (WSOLA, searched within 8 ms), so a held tone stays smooth
 *       instead of beating and cancelling where the grains overlap.
 *   place: -1 left .. 1 right. A slice sits with the near ear at full level, the far ear quieter and up to
 *       0.6 ms later; a stretch only by level.
 *   stop: every voice fades out over 4 ms.  clear: empties the buffer.
 *
 * When all voices are busy, the oldest fades out over 4 ms to make room.
 *
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 dadcraft (DadCraft Studios)
 */
#include "m_pd.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

#define MAXVOICES 16
#define ITDLEN 64                 /* far-ear delay line per voice, samples (0.6 ms is 58 at 96 kHz) */
#define ITD_MS 0.6
#define NGRAIN 4                  /* stretch: overlapping grains */
#define GRAIN_MS 100.0
#define SEARCH_MS 8.0             /* stretch: a new grain may start this much either side of where it should */
#define MATCH_MS 5.3              /* ...lined up over this much of the waveform (every 2nd sample) */
#define STEAL_MS 4.0
#define HANNLEN 1024
#define PD_BLOCK 64               /* Pd's top-level block (DEFDACBLKSIZE, internal to Pd) */

static t_class *dcs_glitch_class;
static float hann[HANNLEN + 1];

enum { V_OFF, V_WAITING, V_PLAYING };
enum { K_SLICE, K_STRETCH };

typedef struct _gvoice
{
    int state, kind;
    double start;                 /* logical time it starts (ms since x_ref) */
    double t, f;                  /* ms into the glitch, ms into the current slice */
    double L, d0, a, c, S, rate;
    float gl, gr;
    int itdl, itdr, itdw;
    float itd[ITDLEN];
    float fade, fadestep;         /* stolen: falling to 0 */
    double gph[NGRAIN], gd[NGRAIN];   /* stretch grains: phase (< 0 = not started yet), ms back */
    int glast;                        /* the grain started last (-1 = none yet) */
    unsigned long order;
} t_gvoice;

typedef struct _dcs_glitch
{
    t_object x_obj;
    t_float x_f;
    t_sample *x_buf;
    int x_bufn, x_mask, x_w;      /* buffer: power of two, next write index */
    double x_bufms, x_maxback;
    double x_sr, x_msps;
    double x_ref, x_lastlogical, x_nextblock;
    int x_nvoices;
    t_gvoice x_v[2 * MAXVOICES];  /* room for the stolen ones fading out */
    unsigned long x_count;
    t_outlet *x_outr;
} t_dcs_glitch;

/* 4-point interpolated read, `back` samples before index w (back >= 3) */
static inline t_sample dcs_glitch_read(const t_sample *buf, int mask, int w, double back)
{
    double p = (double)w - back;
    double fl = floor(p);
    int i = (int)fl;
    t_sample frac = (t_sample)(p - fl);
    t_sample a = buf[(i - 1) & mask], b = buf[i & mask], c = buf[(i + 1) & mask], d = buf[(i + 2) & mask];
    t_sample cminusb = c - b;
    return b + frac * (cminusb - 0.1666667f * (1.f - frac) *
        ((d - a - 3.0f * cminusb) * frac + (d + 2.0f * a - 3.0f * b)));
}

static inline double clampd(double v, double lo, double hi)
{
    return v < lo ? lo : (v > hi ? hi : v);
}

static inline float hannat(double ph)   /* ph 0..1 */
{
    double p = ph * HANNLEN;
    int i = (int)p;
    if (i >= HANNLEN) return 0;
    return hann[i] + (float)(p - i) * (hann[i + 1] - hann[i]);
}

/* a stretch grain starts: target ms back, lined up with the grain playing now (prev ms back, or < 0 for none) */
static double dcs_glitch_wsola(t_dcs_glitch *x, int cur, double target, double prev)
{
    double spms = 1. / x->x_msps;
    int W = (int)(MATCH_MS * spms), tol = (int)(SEARCH_MS * spms), c0, p, o, j, best = 0;
    double bestsum = -1e30;
    const t_sample *buf = x->x_buf;
    int mask = x->x_mask;
    if (prev < 0) return target;
    c0 = (int)(target * spms + 0.5);
    p = (int)(prev * spms + 0.5);
    /* only what has been written can be compared, and only inside the buffer */
    if (p < W + 3 || c0 - tol < W + 3 || c0 + tol > (int)(x->x_maxback * spms)) return target;
    for (o = -tol; o <= tol; o++)
    {
        double sum = 0;
        int a = cur - (c0 + o), b = cur - p;
        for (j = 0; j < W; j += 2)
            sum += buf[(a + j) & mask] * buf[(b + j) & mask];
        if (sum > bestsum) { bestsum = sum; best = o; }
    }
    return (c0 + best) * x->x_msps;
}

static t_gvoice *dcs_glitch_alloc(t_dcs_glitch *x)
{
    int i, busy = 0;
    t_gvoice *oldest = 0, *free = 0, *oldfading = 0;
    for (i = 0; i < 2 * MAXVOICES; i++)
    {
        t_gvoice *v = &x->x_v[i];
        if (v->state == V_OFF) { if (!free) free = v; continue; }
        if (v->fadestep > 0)
        {
            if (!oldfading || v->order < oldfading->order) oldfading = v;
            continue;
        }
        busy++;
        if (!oldest || v->order < oldest->order) oldest = v;
    }
    if (busy >= x->x_nvoices && oldest)
    {
        if (oldest->state == V_WAITING) oldest->state = V_OFF;   /* never heard: just drop it */
        else oldest->fadestep = (float)(x->x_msps / STEAL_MS);
        if (!free && oldest->state == V_OFF) free = oldest;
    }
    if (!free) free = oldfading;          /* (only if every slot is busy fading: cut the oldest) */
    if (!free) return 0;
    memset(free, 0, sizeof(*free));
    free->fade = 1;
    free->order = ++x->x_count;
    free->start = clock_gettimesince(x->x_ref);
    free->state = V_WAITING;
    return free;
}

static void dcs_glitch_place(t_dcs_glitch *x, t_gvoice *v, t_float place, int itd)
{
    double p = clampd(place, -1, 1);
    v->gl = (float)(p > 0 ? 1 - p : 1);
    v->gr = (float)(p < 0 ? 1 + p : 1);
    if (itd)
    {
        double samps = ITD_MS * x->x_sr / 1000.;
        v->itdl = (int)(samps * (p > 0 ? p : 0) + 0.5);
        v->itdr = (int)(samps * (p < 0 ? -p : 0) + 0.5);
        if (v->itdl >= ITDLEN) v->itdl = ITDLEN - 1;
        if (v->itdr >= ITDLEN) v->itdr = ITDLEN - 1;
    }
}

static void dcs_glitch_slice(t_dcs_glitch *x, t_symbol *s, int argc, t_atom *argv)
{
    t_gvoice *v;
    if (argc < 6) { pd_error(x, "dcs_glitch~: slice needs L d0 c1 c2 S place"); return; }
    if (atom_getfloat(argv) <= 0 || !(v = dcs_glitch_alloc(x))) return;
    v->kind = K_SLICE;
    v->L = atom_getfloat(argv);
    v->d0 = atom_getfloat(argv + 1);
    v->a = 1 - atom_getfloat(argv + 2);
    v->c = atom_getfloat(argv + 3);
    v->S = atom_getfloat(argv + 4);
    if (v->S < 1) v->S = 1;
    dcs_glitch_place(x, v, atom_getfloat(argv + 5), 1);
}

static void dcs_glitch_stretch(t_dcs_glitch *x, t_symbol *s, int argc, t_atom *argv)
{
    int g;
    t_gvoice *v;
    if (argc < 4) { pd_error(x, "dcs_glitch~: stretch needs L d0 rate place"); return; }
    if (atom_getfloat(argv) <= 0 || !(v = dcs_glitch_alloc(x))) return;
    v->kind = K_STRETCH;
    v->L = atom_getfloat(argv);
    v->d0 = atom_getfloat(argv + 1);
    v->rate = clampd(atom_getfloat(argv + 2), 0, 1);
    for (g = 0; g < NGRAIN; g++)
        v->gph[g] = -(double)g / NGRAIN;    /* they start one after another */
    v->glast = -1;
    dcs_glitch_place(x, v, atom_getfloat(argv + 3), 0);
}

static void dcs_glitch_stop(t_dcs_glitch *x)
{
    int i;
    for (i = 0; i < 2 * MAXVOICES; i++)
    {
        t_gvoice *v = &x->x_v[i];
        if (v->state == V_WAITING) v->state = V_OFF;
        else if (v->state == V_PLAYING && v->fadestep == 0) v->fadestep = (float)(x->x_msps / STEAL_MS);
    }
}

static void dcs_glitch_clear(t_dcs_glitch *x)
{
    if (x->x_buf) memset(x->x_buf, 0, x->x_bufn * sizeof(t_sample));
}

static t_int *dcs_glitch_perform(t_int *w)
{
    t_dcs_glitch *x = (t_dcs_glitch *)(w[1]);
    t_sample *in = (t_sample *)(w[2]), *outl = (t_sample *)(w[3]), *outr = (t_sample *)(w[4]);
    int n = (int)(w[5]), i, k, g;
    t_sample *buf = x->x_buf;
    int mask = x->x_mask, w0 = x->x_w;
    double msps = x->x_msps, spms = 1. / msps, maxback = x->x_maxback;
    double logicalnow = clock_gettimesince(x->x_ref), blockstart;

    /* where this block sits in logical time (as in vline~) */
    if (logicalnow != x->x_lastlogical)
    {
        int sampstotime = (n > PD_BLOCK ? n : PD_BLOCK);
        x->x_lastlogical = logicalnow;
        x->x_nextblock = logicalnow - sampstotime * msps;
    }
    blockstart = x->x_nextblock;
    x->x_nextblock = blockstart + n * msps;

    /* the input goes in first (in and out may share memory) */
    for (i = 0; i < n; i++)
        buf[(w0 + i) & mask] = in[i];
    x->x_w = (w0 + n) & mask;
    for (i = 0; i < n; i++)
        outl[i] = outr[i] = 0;

    for (k = 0; k < 2 * MAXVOICES; k++)
    {
        t_gvoice *v = &x->x_v[k];
        int i0 = 0;
        if (v->state == V_OFF) continue;
        if (v->state == V_WAITING)
        {
            double off = (v->start - blockstart) * spms;
            if (off >= n) continue;
            i0 = off > 0 ? (int)ceil(off - 1e-4) : 0;     /* (exactly on a block edge reads a hair past it) */
            if (i0 >= n) continue;
            v->state = V_PLAYING;
            if (off > 0 && i0 > off)                       /* it began between two samples */
                v->t = v->f = (i0 - off) * msps;
        }
        if (v->kind == K_SLICE)
        {
            for (i = i0; i < n; i++)
            {
                double t = v->t, f = v->f, d, win, env;
                t_sample s;
                d = clampd(v->d0 + v->a * t - v->c * f, 1, maxback);
                win = clampd(f / 3, 0, 1) * clampd((v->S - f) / 3, 0, 1);
                env = clampd(t / 5, 0, 1) * clampd((v->L - 5 - t) / 20, 0, 1);
                s = dcs_glitch_read(buf, mask, w0 + i, d * spms) * (t_sample)(win * env) * v->fade;
                v->itd[v->itdw] = s;
                outl[i] += v->gl * v->itd[(v->itdw - v->itdl) & (ITDLEN - 1)];
                outr[i] += v->gr * v->itd[(v->itdw - v->itdr) & (ITDLEN - 1)];
                v->itdw = (v->itdw + 1) & (ITDLEN - 1);
                v->t = t + msps;
                v->f = f + msps;
                if (v->f >= v->S) v->f -= v->S;
                if (v->fadestep > 0 && (v->fade -= v->fadestep) <= 0) { v->state = V_OFF; break; }
                if (v->t >= v->L + ITD_MS) { v->state = V_OFF; break; }
            }
        }
        else
        {
            double k1 = 1 - v->rate, ginc = msps / GRAIN_MS;
            for (i = i0; i < n; i++)
            {
                double t = v->t, D = v->d0 + k1 * t, env;
                t_sample s = 0;
                for (g = 0; g < NGRAIN; g++)
                {
                    double ph = v->gph[g];
                    if (ph >= 0)      /* (within a grain the distance back stays put: it plays at normal speed) */
                        s += dcs_glitch_read(buf, mask, w0 + i, v->gd[g] * spms) * hannat(ph);
                    ph += ginc;
                    if (ph >= 1 || (ph >= 0 && v->gph[g] < 0))
                    {
                        if (ph >= 1) ph -= 1;
                        v->gd[g] = clampd(dcs_glitch_wsola(x, w0 + i, clampd(D, 1, maxback),
                            v->glast >= 0 ? v->gd[v->glast] : -1), 1, maxback);
                        v->glast = g;
                    }
                    v->gph[g] = ph;
                }
                env = clampd(t / 40, 0, 1) * clampd((v->L - 50 - t) / 600, 0, 1);
                s *= (t_sample)(env * (2.0 / NGRAIN)) * v->fade;     /* NGRAIN Hann grains add up to NGRAIN/2 */
                outl[i] += v->gl * s;
                outr[i] += v->gr * s;
                v->t = t + msps;
                if (v->fadestep > 0 && (v->fade -= v->fadestep) <= 0) { v->state = V_OFF; break; }
                if (v->t >= v->L) { v->state = V_OFF; break; }
            }
        }
    }
    return (w + 6);
}

static void dcs_glitch_dsp(t_dcs_glitch *x, t_signal **sp)
{
    double sr = sp[0]->s_sr;
    if (sr != x->x_sr || !x->x_buf)
    {
        int need = (int)ceil(x->x_bufms * sr / 1000.) + 8, size = 1;
        while (size < need) size <<= 1;
        if (x->x_buf) freebytes(x->x_buf, x->x_bufn * sizeof(t_sample));
        x->x_buf = (t_sample *)getbytes(size * sizeof(t_sample));
        x->x_bufn = size;
        x->x_mask = size - 1;
        x->x_w = 0;
        x->x_sr = sr;
        x->x_msps = 1000. / sr;
        x->x_maxback = x->x_bufms - 10;
        memset(x->x_v, 0, sizeof(x->x_v));
    }
    dsp_add(dcs_glitch_perform, 5, x, sp[0]->s_vec, sp[1]->s_vec, sp[2]->s_vec, (t_int)sp[0]->s_n);
}

static void *dcs_glitch_new(t_floatarg bufms, t_floatarg voices)
{
    t_dcs_glitch *x = (t_dcs_glitch *)pd_new(dcs_glitch_class);
    x->x_bufms = bufms > 100 ? bufms : 4000;
    x->x_nvoices = voices >= 1 ? (voices > MAXVOICES ? MAXVOICES : (int)voices) : 4;
    x->x_ref = x->x_lastlogical = x->x_nextblock = clock_getlogicaltime();
    outlet_new(&x->x_obj, &s_signal);
    x->x_outr = outlet_new(&x->x_obj, &s_signal);
    return (x);
}

static void dcs_glitch_free(t_dcs_glitch *x)
{
    if (x->x_buf) freebytes(x->x_buf, x->x_bufn * sizeof(t_sample));
}

void dcs_glitch_tilde_setup(void)
{
    int i;
    for (i = 0; i <= HANNLEN; i++)
        hann[i] = (float)(0.5 - 0.5 * cos(2 * M_PI * i / HANNLEN));
    dcs_glitch_class = class_new(gensym("dcs_glitch~"), (t_newmethod)dcs_glitch_new,
        (t_method)dcs_glitch_free, sizeof(t_dcs_glitch), CLASS_DEFAULT, A_DEFFLOAT, A_DEFFLOAT, 0);
    CLASS_MAINSIGNALIN(dcs_glitch_class, t_dcs_glitch, x_f);
    class_addmethod(dcs_glitch_class, (t_method)dcs_glitch_dsp, gensym("dsp"), A_CANT, 0);
    class_addmethod(dcs_glitch_class, (t_method)dcs_glitch_slice, gensym("slice"), A_GIMME, 0);
    class_addmethod(dcs_glitch_class, (t_method)dcs_glitch_stretch, gensym("stretch"), A_GIMME, 0);
    class_addmethod(dcs_glitch_class, (t_method)dcs_glitch_stop, gensym("stop"), 0);
    class_addmethod(dcs_glitch_class, (t_method)dcs_glitch_clear, gensym("clear"), 0);
}
