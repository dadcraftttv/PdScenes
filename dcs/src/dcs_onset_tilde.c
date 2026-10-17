/* dcs_onset~: finds sudden sounds by how their spectrum jumps, not only how loud they get.
 *
 * A level detector fires on anything that gets louder fast, including a voice swelling, a held note's vibrato
 * and a steady roar's wobble, and misses a clap in a loud room. This one (spectral flux, after SuperFlux, Böck and
 * Widmer 2013) looks at 24 bands, 80 Hz to 16 kHz, every ~2.7 ms over ~11 ms frames, and adds up how far each band
 * rose above what that band AND its neighbours held two frames before: a new sound lights up bands that were
 * quiet; a note sliding between bands, or a room humming on, does not. The threshold rides on the recent average
 * of that (busy rooms need a bigger jump), and a sound must be over `min dB` too. One hop after the peak it
 * reports the onset, then waits `refractory` ms.
 *
 *   [dcs_onset~ <threshold, default 40> <min dB (Pd dB, 100 = full scale), default 55>]
 *   inlet:   signal; `threshold <f>`, `min <dB>`, `refractory <ms>` (default 50)
 *   outlets: bang at each onset; then a list: level (Pd dB), lows (dB under the whole, < 150 Hz), highs (dB under
 *            the whole, > 4 kHz), brightness (spectral centroid, Hz), jump (the flux that fired it)
 *
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 dadcraft (DadCraft Studios)
 */
#include "m_pd.h"
#include <math.h>
#include <string.h>

#define MAXN 2048
#define NBANDS 24
#define FLO 80.
#define FHI 16000.
#define FRAME_MS 10.7
#define HOP_MS 2.7
#define AVG_MS 500.
#define ALPHA 1.5                /* the threshold: ALPHA x the recent average + `threshold` */
#define FLOOR_REL 1e-3           /* band levels count from 30 dB under the frame's whole */

static t_class *dcs_onset_class;

typedef struct _dcs_onset
{
    t_object x_obj;
    t_float x_f;
    double x_sr;
    int x_N, x_H, x_w, x_count;
    t_sample x_ring[MAXN], x_fft[MAXN], x_win[MAXN];
    int x_edge[NBANDS + 1];
    double x_L[3][NBANDS];       /* band levels (dB): this frame, one and two frames ago */
    double x_flux[3], x_level[3], x_feat[3][4];
    double x_avg, x_avgk;
    double x_thresh, x_min, x_refrac, x_wait;
    int x_frames;
    t_atom x_out[5];
    t_clock *x_clock;
    t_outlet *x_bang, *x_list;
} t_dcs_onset;

static void dcs_onset_tick(t_dcs_onset *x)
{
    outlet_bang(x->x_bang);
    outlet_list(x->x_list, &s_list, 5, x->x_out);
}

static void dcs_onset_setup_sr(t_dcs_onset *x, double sr)
{
    int N = 1, b, k;
    x->x_sr = sr;
    while (N < FRAME_MS * sr / 1000 && N < MAXN) N <<= 1;
    x->x_N = N;
    x->x_H = (int)(HOP_MS * sr / 1000);
    if (x->x_H < 16) x->x_H = 16;
    for (k = 0; k < N; k++)
        x->x_win[k] = (t_sample)(0.5 - 0.5 * cos(2 * M_PI * k / N));
    for (b = 0; b <= NBANDS; b++)
    {
        double f = FLO * pow(FHI / FLO, (double)b / NBANDS);
        if (f > sr / 2) f = sr / 2;
        x->x_edge[b] = (int)(f * N / sr + 0.5);
        if (b > 0 && x->x_edge[b] <= x->x_edge[b - 1]) x->x_edge[b] = x->x_edge[b - 1] + 1;
        if (x->x_edge[b] > N / 2) x->x_edge[b] = N / 2;
    }
    x->x_avgk = exp(-HOP_MS / AVG_MS);
    memset(x->x_ring, 0, sizeof(x->x_ring));
    memset(x->x_L, 0, sizeof(x->x_L));
    x->x_frames = 0;
}

static void dcs_onset_frame(t_dcs_onset *x)
{
    int N = x->x_N, k, b;
    double sq = 0, tot = 0, lo = 0, hi = 0, cen = 0, flux = 0, level;
    t_sample *f = x->x_fft;
    for (k = 0; k < N; k++)
    {
        t_sample s = x->x_ring[(x->x_w + k) & (N - 1)];
        sq += (double)s * s;
        f[k] = s * x->x_win[k];
    }
    mayer_realfft(N, f);
    /* shift the history: [2] <- [1] <- [0] */
    memcpy(x->x_L[2], x->x_L[1], sizeof(x->x_L[0]));
    memcpy(x->x_L[1], x->x_L[0], sizeof(x->x_L[0]));
    x->x_flux[2] = x->x_flux[1]; x->x_flux[1] = x->x_flux[0];
    x->x_level[2] = x->x_level[1]; x->x_level[1] = x->x_level[0];
    memcpy(x->x_feat[2], x->x_feat[1], sizeof(x->x_feat[0]));
    memcpy(x->x_feat[1], x->x_feat[0], sizeof(x->x_feat[0]));
    {
        double e[NBANDS];
        for (b = 0; b < NBANDS; b++)
        {
            e[b] = 0;
            for (k = x->x_edge[b]; k < x->x_edge[b + 1]; k++)
            {
                double re = f[k], im = (k > 0 && k < N / 2) ? f[N - k] : 0, m = re * re + im * im;
                double hz = k * x->x_sr / N;
                e[b] += m;
                tot += m; cen += m * hz;
                if (hz < 150) lo += m;
                if (hz > 4000) hi += m;
            }
        }
        /* each band's level, floored 30 dB under the whole frame (SuperFlux's log compression): a nearly empty band
           (the leakage around a tone sliding with vibrato) can't swing tens of dB and count like a real burst */
        for (b = 0; b < NBANDS; b++)
            x->x_L[0][b] = 10 * log10(e[b] + tot * FLOOR_REL + 1e-12);
    }
    /* the jump: each band over the most its neighbourhood held two frames ago */
    if (x->x_frames >= 2)
        for (b = 0; b < NBANDS; b++)
        {
            double m = x->x_L[2][b];
            if (b > 0 && x->x_L[2][b - 1] > m) m = x->x_L[2][b - 1];
            if (b < NBANDS - 1 && x->x_L[2][b + 1] > m) m = x->x_L[2][b + 1];
            if (x->x_L[0][b] > m) flux += x->x_L[0][b] - m;
        }
    level = sq > 0 ? 100 + 10 * log10(sq / N) : 0;
    x->x_flux[0] = flux;
    x->x_level[0] = level;
    x->x_feat[0][0] = level;
    x->x_feat[0][1] = tot > 0 ? 10 * log10((lo + 1e-12) / tot) : -100;
    x->x_feat[0][2] = tot > 0 ? 10 * log10((hi + 1e-12) / tot) : -100;
    x->x_feat[0][3] = tot > 0 ? cen / tot : 0;
    x->x_frames++;
    /* the frame before this one: a peak, over the threshold, loud enough, not too soon after the last? */
    if (x->x_wait > 0) x->x_wait -= x->x_H;
    if (x->x_frames >= 4 && x->x_flux[1] > x->x_flux[2] && x->x_flux[1] >= x->x_flux[0]
        && x->x_flux[1] > ALPHA * x->x_avg + x->x_thresh && x->x_level[1] > x->x_min && x->x_wait <= 0)
    {
        SETFLOAT(&x->x_out[0], (t_float)x->x_feat[1][0]);
        SETFLOAT(&x->x_out[1], (t_float)x->x_feat[1][1]);
        SETFLOAT(&x->x_out[2], (t_float)x->x_feat[1][2]);
        SETFLOAT(&x->x_out[3], (t_float)x->x_feat[1][3]);
        SETFLOAT(&x->x_out[4], (t_float)x->x_flux[1]);
        x->x_wait = x->x_refrac * x->x_sr / 1000;
        clock_delay(x->x_clock, 0);
    }
    x->x_avg = flux + (x->x_avg - flux) * x->x_avgk;
}

static t_int *dcs_onset_perform(t_int *w)
{
    t_dcs_onset *x = (t_dcs_onset *)(w[1]);
    t_sample *in = (t_sample *)(w[2]);
    int n = (int)(w[3]), i, N = x->x_N;
    for (i = 0; i < n; i++)
    {
        x->x_ring[x->x_w] = in[i];
        x->x_w = (x->x_w + 1) & (N - 1);
        if (++x->x_count >= x->x_H)
        {
            x->x_count = 0;
            dcs_onset_frame(x);
        }
    }
    return (w + 4);
}

static void dcs_onset_dsp(t_dcs_onset *x, t_signal **sp)
{
    if (sp[0]->s_sr != x->x_sr)
        dcs_onset_setup_sr(x, sp[0]->s_sr);
    dsp_add(dcs_onset_perform, 3, x, sp[0]->s_vec, (t_int)sp[0]->s_n);
}

static void dcs_onset_threshold(t_dcs_onset *x, t_floatarg f) { x->x_thresh = f; }
static void dcs_onset_min(t_dcs_onset *x, t_floatarg f) { x->x_min = f; }
static void dcs_onset_refractory(t_dcs_onset *x, t_floatarg f) { x->x_refrac = f > 0 ? f : 0; }

static void *dcs_onset_new(t_floatarg thresh, t_floatarg mindb)
{
    t_dcs_onset *x = (t_dcs_onset *)pd_new(dcs_onset_class);
    x->x_thresh = thresh > 0 ? thresh : 40;
    x->x_min = mindb > 0 ? mindb : 55;
    x->x_refrac = 50;
    dcs_onset_setup_sr(x, sys_getsr() > 0 ? sys_getsr() : 44100);
    x->x_clock = clock_new(x, (t_method)dcs_onset_tick);
    x->x_bang = outlet_new(&x->x_obj, &s_bang);
    x->x_list = outlet_new(&x->x_obj, &s_list);
    return (x);
}

static void dcs_onset_free(t_dcs_onset *x)
{
    clock_free(x->x_clock);
}

void dcs_onset_tilde_setup(void)
{
    dcs_onset_class = class_new(gensym("dcs_onset~"), (t_newmethod)dcs_onset_new, (t_method)dcs_onset_free,
        sizeof(t_dcs_onset), CLASS_DEFAULT, A_DEFFLOAT, A_DEFFLOAT, 0);
    CLASS_MAINSIGNALIN(dcs_onset_class, t_dcs_onset, x_f);
    class_addmethod(dcs_onset_class, (t_method)dcs_onset_dsp, gensym("dsp"), A_CANT, 0);
    class_addmethod(dcs_onset_class, (t_method)dcs_onset_threshold, gensym("threshold"), A_FLOAT, 0);
    class_addmethod(dcs_onset_class, (t_method)dcs_onset_min, gensym("min"), A_FLOAT, 0);
    class_addmethod(dcs_onset_class, (t_method)dcs_onset_refractory, gensym("refractory"), A_FLOAT, 0);
}
