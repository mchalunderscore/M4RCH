#define _GNU_SOURCE
#include <assert.h>
#include <stdio.h>
#include "smoke-criteria.h"
int main(void)
{
   unsigned cases = 0;
#define CHECK(expr) do { assert(expr); ++cases; } while (0)
   CHECK(smoke_hardware_renderer("Apple M4 Pro (G16S B1)"));
   CHECK(!smoke_hardware_renderer("llvmpipe (LLVM 20)"));
   CHECK(!smoke_hardware_renderer("Apple M4 Pro (G16S B1) software"));
   CHECK(!smoke_hardware_renderer("Apple M4 (G16G B1)"));
   CHECK(!smoke_hardware_renderer(NULL));
   uint64_t masks[2] = {0x3db, 0x3db};
   struct agx_g16_device_info info;
   CHECK(agx_g16_decode_device(0x6040, 'S', 1, 2, 10, masks, 2, &info));
   CHECK(smoke_j614_identity(16, 0x11, &info));
   CHECK(!smoke_j614_identity(16, 0x10, &info));
   CHECK(!smoke_j614_identity(17, 0x11, &info));
   info.core_masks[1] = 0x3ff;
   CHECK(!smoke_j614_identity(16, 0x11, &info));
   uint8_t pixels[SMOKE_BYTES];
   for (unsigned frame = 0; frame < 2; ++frame) {
      for (unsigned i = 0; i < SMOKE_WIDTH * SMOKE_HEIGHT; ++i) {
         uint8_t *p = pixels + i * 4;
         p[0] = 0; p[1] = 0; p[2] = 255; p[3] = 255;
      }
      /* Synthetic CPU fixture exercises acceptance/rejection only. */
      for (unsigned y = 8; y < 40; ++y)
         for (unsigned x = 16; x < 48; ++x) {
            uint8_t *p = pixels + (y * SMOKE_WIDTH + x) * 4;
            p[0] = frame == 0 ? 255 : 0; p[1] = frame == 1 ? 255 : 0;
            p[2] = 0;
         }
      unsigned count;
      CHECK(smoke_pixels(pixels, frame, &count) && count == 1024);
      CHECK(!smoke_pixels(pixels, 1 - frame, NULL));
      pixels[0] = 1;
      CHECK(!smoke_pixels(pixels, frame, NULL));
      pixels[0] = 0;
      pixels[(24 * SMOKE_WIDTH + 32) * 4 + 3] = 0;
      CHECK(!smoke_pixels(pixels, frame, NULL));
   }
   memset(pixels, 0, sizeof(pixels));
   CHECK(!smoke_pixels(pixels, 0, NULL));
   memset(pixels, 0xa5, sizeof(pixels));
   CHECK(!smoke_pixels(pixels, 0, NULL));
   CHECK(!smoke_pixels(pixels, 2, NULL));
   CHECK(!smoke_pixels(NULL, 0, NULL));
   printf("Smoke criteria assertions: %u (synthetic CPU fixtures; no EGL/DRM)\n", cases);
   return 0;
}
