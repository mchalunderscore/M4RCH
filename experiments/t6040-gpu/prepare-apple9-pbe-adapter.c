/* SPDX-License-Identifier: MIT
 * Offline adapter to generated Gravity Mesa PBE packing; no GPU access.
 */
#include <stdbool.h>
#include <stdint.h>
#include <assert.h>
#include "asahi/genxml/agx_pack.h"
void pack(uint8_t *out, unsigned w,unsigned h,uint64_t addr,unsigned stride) {
 struct AGX_PBE cfg={AGX_PBE_header};
 cfg.dimension=AGX_TEXTURE_DIMENSION_2D;cfg.layout=AGX_LAYOUT_LINEAR;
 cfg.channels=AGX_CHANNELS_R8G8B8A8;cfg.type=AGX_TEXTURE_TYPE_UNORM;
 cfg.swizzle_r=AGX_CHANNEL_R;cfg.swizzle_g=AGX_CHANNEL_G;cfg.swizzle_b=AGX_CHANNEL_B;cfg.swizzle_a=AGX_CHANNEL_A;
 cfg.width=w;cfg.height=h;cfg.buffer=addr;cfg.stride=stride-4;cfg.levels=1;cfg.layers=1;
 AGX_PBE_pack((uint32_t *)out,&cfg);
}
