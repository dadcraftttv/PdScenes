/* dcs: Pd objects by DadCraft Studios. Load them all with [declare -lib dcs].
 *
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 dadcraft (DadCraft Studios)
 */
#include "m_pd.h"

#define DCS_VERSION "0.1.0"

void dcs_glitch_tilde_setup(void);
void dcs_string_tilde_setup(void);
void dcs_derustle_tilde_setup(void);
void dcs_pitch_tilde_setup(void);
void dcs_shift_tilde_setup(void);
void dcs_onset_tilde_setup(void);

void dcs_setup(void)
{
    dcs_glitch_tilde_setup();
    dcs_string_tilde_setup();
    dcs_derustle_tilde_setup();
    dcs_pitch_tilde_setup();
    dcs_shift_tilde_setup();
    dcs_onset_tilde_setup();
    post("dcs %s: dcs_glitch~ dcs_string~ dcs_derustle~ dcs_pitch~ dcs_shift~ dcs_onset~", DCS_VERSION);
}
