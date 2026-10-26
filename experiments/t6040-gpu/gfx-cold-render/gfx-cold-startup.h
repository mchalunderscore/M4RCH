/* SPDX-License-Identifier: GPL-2.0-only */
/* Allocation-only preflight or the sole retained cold render owner. */
static int gfx_cold_startup_admission(unsigned int gate,bool resident,
 bool shutdown,bool warm,bool release)
{
 if(shutdown || warm || release) return -EINVAL;
 if((gate==1 && !resident) || (gate==2 && resident)) return 0;
 return -EINVAL;
}
