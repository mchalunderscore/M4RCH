/* Exercise the actual staged Mesa header without linking Mesa or touching DRM. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "agx_g16_model.h"

int main(void)
{
   unsigned cases = 0;
   uint64_t masks[64] = {0x3db, 0x3db};
   struct agx_g16_device_info info;
#define DECODE(chip, variant, dies, clusters, slots, count) \
   agx_g16_decode_device(chip, variant, dies, clusters, slots, masks, count, &info)
#define CHECK(expr) do { assert(expr); ++cases; } while (0)
   CHECK(DECODE(0x6040, 'S', 1, 2, 10, 64));
   CHECK(info.model == AGX_G16_S && info.enabled_cores == 16);
   CHECK(info.clusters == 2 && info.slots_per_cluster == 10);
   CHECK(info.core_masks[0] == 0x3db && info.core_masks[1] == 0x3db);
   CHECK(!agx_g16_layout_qualified(info.model));
   printf("BIND,16,%u,%u,%u,%u,%u,%u,%llu,%llu\n", info.chip, info.variant,
          info.dies, info.clusters, info.slots_per_cluster, info.enabled_cores,
          (unsigned long long)info.core_masks[0], (unsigned long long)info.core_masks[1]);
   CHECK(!DECODE(0x8132, 'S', 1, 2, 10, 64));
   CHECK(!DECODE(0x6040, 'G', 1, 2, 10, 64));
   CHECK(!DECODE(0x6040, 'S', 2, 2, 10, 64));
   CHECK(!DECODE(0x6040, 'S', 1, 1, 10, 64));
   CHECK(!DECODE(0x6040, 'S', 1, 2, 8, 64));
   CHECK(!DECODE(0x6040, 'S', 1, 2, 10, 1));
   CHECK(!agx_g16_decode_device(0x6040, 'S', 1, 2, 10, NULL, 64, &info));
   CHECK(!agx_g16_decode_device(0x6040, 'S', 1, 2, 10, masks, 64, NULL));
   masks[1] = 0;
   CHECK(!DECODE(0x6040, 'S', 1, 2, 10, 64));
   CHECK(DECODE(0x8132, 'G', 1, 1, 10, 64));
   CHECK(info.enabled_cores == 8 && agx_g16_layout_qualified(info.model));
   masks[0] = UINT64_C(1) << 32;
   CHECK(!DECODE(0x8132, 'G', 1, 1, 10, 64));
   masks[0] = 0x3db; masks[1] = 0x3db;
   for (unsigned i = 2; i < 64; ++i) {
      masks[i] = 1;
      CHECK(!DECODE(0x6040, 'S', 1, 2, 10, 64));
      masks[i] = 0;
   }
   for (uint64_t mask = 1; mask <= 0x3ff; ++mask) {
      masks[0] = mask; masks[1] = 0;
      CHECK(DECODE(0x8132, 'G', 1, 1, 10, 64));
      CHECK(info.core_masks[0] == mask && info.core_masks[1] == 0);
      CHECK(info.enabled_cores == (unsigned)__builtin_popcountll(mask));
      masks[1] = 0x3db;
      CHECK(DECODE(0x6040, 'S', 1, 2, 10, 64));
      CHECK(info.enabled_cores == (unsigned)__builtin_popcountll(mask) + 8);
   }
   printf("Mesa topology assertions: %u\n", cases);
   return 0;
}
