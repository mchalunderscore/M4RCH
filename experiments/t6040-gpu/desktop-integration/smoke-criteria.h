/* SPDX-License-Identifier: MIT */
#ifndef T6040_SMOKE_CRITERIA_H
#define T6040_SMOKE_CRITERIA_H
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <strings.h>
#include "agx_g16_model.h"
#define SMOKE_WIDTH 64
#define SMOKE_HEIGHT 64
#define SMOKE_BYTES (SMOKE_WIDTH * SMOKE_HEIGHT * 4)

static inline bool smoke_hardware_renderer(const char *renderer)
{
   /* This smoke profile is for the captured J614s, not every Apple GPU. */
   return renderer && strstr(renderer, "Apple M4 Pro") &&
          strstr(renderer, "G16S") && !strcasestr(renderer, "llvmpipe") &&
          !strcasestr(renderer, "softpipe") && !strcasestr(renderer, "software");
}

static inline bool smoke_j614_identity(unsigned generation, unsigned revision,
                                     const struct agx_g16_device_info *info)
{
   return info && generation == 16 && revision == 0x11 &&
          info->chip == 0x6040 && info->model == AGX_G16_S &&
          info->variant == 'S' && info->dies == 1 && info->clusters == 2 &&
          info->slots_per_cluster == 10 && info->enabled_cores == 16 &&
          info->core_masks[0] == 0x3db && info->core_masks[1] == 0x3db;
}

static inline bool smoke_pixel(const uint8_t *p, unsigned frame)
{
   return p[0] == (frame == 0 ? 255 : 0) &&
          p[1] == (frame == 1 ? 255 : 0) && p[2] == 0 && p[3] == 255;
}

static inline bool smoke_pixels(const uint8_t *pixels, unsigned frame,
                                unsigned *colored_pixels)
{
   if (!pixels || frame > 1)
      return false;
   unsigned colored = 0;
   for (unsigned i = 0; i < SMOKE_WIDTH * SMOKE_HEIGHT; ++i) {
      const uint8_t *p = pixels + i * 4;
      if (smoke_pixel(p, frame))
         ++colored;
      else if (!(p[0] == 0 && p[1] == 0 && p[2] == 255 && p[3] == 255))
         return false;
   }
   const uint8_t *inside = pixels + (24 * SMOKE_WIDTH + 32) * 4;
   const uint8_t *outside = pixels + (2 * SMOKE_WIDTH + 2) * 4;
   if (!smoke_pixel(inside, frame) || outside[0] != 0 || outside[1] != 0 ||
       outside[2] != 255 || outside[3] != 255 || colored < 900 || colored > 1400)
      return false;
   if (colored_pixels)
      *colored_pixels = colored;
   return true;
}
#endif
