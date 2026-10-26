/* SPDX-License-Identifier: MIT */
#ifndef AGX_G16_MODEL_H
#define AGX_G16_MODEL_H
#include <stdbool.h>
#include <stdint.h>
enum agx_g16_model { AGX_G16_UNKNOWN, AGX_G16_G, AGX_G16_S };
/* Metadata selection only; packet/layout qualification remains separate. */
static inline enum agx_g16_model
agx_g16_select(unsigned variant, unsigned clusters, unsigned slots)
{
   if (variant == 'G' && clusters == 1 && slots == 10) return AGX_G16_G;
   if (variant == 'S' && clusters == 2 && slots == 20) return AGX_G16_S;
   return AGX_G16_UNKNOWN;
}
static inline bool agx_g16_layout_qualified(enum agx_g16_model model)
{
   return model == AGX_G16_G;
}
#endif
