/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef M4RCH_GFX_RESET_STARTUP_H
#define M4RCH_GFX_RESET_STARTUP_H

/* The root runner first validates a nonresident allocation-only shadow, then
 * admits the retained no-work owner. Neither mode may request a lifecycle
 * operation whose teardown/restart contract this experiment does not prove.
 * bool and EINVAL are supplied by the module or the actual-C replay preamble.
 */
static int gfx_reset_scope_startup_admission(unsigned int gate,bool resident,
 bool shutdown,bool warm,bool release)
{
 if(shutdown || warm || release) return -EINVAL;
 if((gate==1 && !resident) || (gate==2 && resident)) return 0;
 return -EINVAL;
}

#endif
